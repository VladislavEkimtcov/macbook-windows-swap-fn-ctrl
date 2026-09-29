#!/usr/bin/env python3
"""
patch_keymagic.py - swap the Fn and Left-Control keys of a MacBook's built-in
keyboard under Windows (Boot Camp), by patching a *local copy* of Apple's
KeyMagic.sys.

This script never ships or downloads any Apple binary. It reads the KeyMagic.sys
already installed on your machine, writes a patched copy with the embedded
signature removed, and leaves the original untouched. Sign and install the copy
with Install-FnCtrlSwap.ps1.

What the patch does
-------------------
KeyMagic.sys is a lower filter under HidUsb. For every 10-byte keyboard input
report (report ID 1) it works out two things:

    r12  -> pointer to the modifier byte (report[1]; bit0 = Left Ctrl)
    r13b -> the Fn flag (report[9] bit1)

and then uses only r13b to decide whether to run the Fn translations
(Backspace->Delete, arrows->Home/End/PgUp/PgDn, Return->Insert, the F-row mode,
the KeymapFn table). The Fn flag is never passed on to Windows, which is why no
remapper can see the Fn key.

The patch hooks the instruction right after r12/r13b are computed and swaps the
two states:

    Ctrl bit  := (Fn flag was set)
    Fn flag   := (Left Ctrl bit was set)

so the physical Fn key now produces a real Left Ctrl, and the physical Control
key drives the driver's own Fn logic.

Usage
-----
    python patch_keymagic.py                       # patches the installed driver
    python patch_keymagic.py --src X.sys --out Y.sys
    python patch_keymagic.py --check               # verify the driver is patchable, write nothing
"""
import argparse
import hashlib
import os
import re
import struct
import sys

DEFAULT_SRC = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "drivers", "KeyMagic.sys")

# Patch site: the two instructions
#     lea  r12, [rcx + r15]      ; r12 = &modifiers
#     mov  al, [r12]
# immediately followed by  "and al,4 / cmp [rdi+0x7e],al / jle" (the Alt-state notifier).
SITE_SIG = bytes.fromhex("4e8d2439" "418a0424" "2404" "3847" "7e")
SITE_LEN = 8          # bytes displaced (lea + mov)
CAVE_LEN = 40         # bytes of code we need
CAVE_SKIP = 4         # stay clear of the previous function's tail padding


def parse_pe(d):
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    if d[pe:pe + 4] != b"PE\0\0":
        raise SystemExit("not a PE file")
    nsec = struct.unpack_from("<H", d, pe + 6)[0]
    optsz = struct.unpack_from("<H", d, pe + 20)[0]
    opt = pe + 24
    if struct.unpack_from("<H", d, opt)[0] != 0x20B:
        raise SystemExit("not a PE32+ (x64) image")
    secs = []
    for i in range(nsec):
        o = opt + optsz + i * 40
        name = d[o:o + 8].rstrip(b"\0").decode()
        vs, va, rs, ro = struct.unpack_from("<IIII", d, o + 8)
        ch = struct.unpack_from("<I", d, o + 36)[0]
        secs.append(dict(name=name, vs=vs, va=va, rs=rs, ro=ro, ch=ch))
    return pe, opt, secs


def patch(d):
    pe, opt, secs = parse_pe(d)

    def r2o(rva):
        for s in secs:
            if s["va"] <= rva < s["va"] + min(s["vs"], s["rs"]):
                return s["ro"] + rva - s["va"]
        raise SystemExit("RVA %#x is not file-backed" % rva)

    text = next(s for s in secs if s["name"] == ".text")
    lo, hi = text["ro"], text["ro"] + min(text["vs"], text["rs"])
    body = bytes(d[lo:hi])

    hits = [m.start() for m in re.finditer(re.escape(SITE_SIG), body)]
    if len(hits) != 1:
        raise SystemExit("patch site signature found %d times (expected 1): this KeyMagic.sys "
                         "build is not supported" % len(hits))
    site_rva = text["va"] + hits[0]

    cave_rva = None
    for m in re.finditer(rb"\xcc{%d,}" % (CAVE_LEN + CAVE_SKIP), body):
        cave_rva = text["va"] + m.start() + CAVE_SKIP
        break
    if cave_rva is None:
        raise SystemExit("no free code cave of %d bytes found" % CAVE_LEN)

    ret_rva = site_rva + SITE_LEN
    displaced = bytes(d[r2o(site_rva):r2o(site_rva) + SITE_LEN])

    cave = displaced                                  # lea r12,[rcx+r15] ; mov al,[r12]
    cave += bytes.fromhex("8ac8")                     # mov  cl, al
    cave += bytes.fromhex("80e1fe")                   # and  cl, 0xFE        ; clear Left Ctrl
    cave += bytes.fromhex("4584ed")                   # test r13b, r13b      ; was Fn down?
    cave += bytes.fromhex("7403")                     # jz   +3
    cave += bytes.fromhex("80c901")                   # or   cl, 1           ; -> Left Ctrl down
    cave += bytes.fromhex("41880c24")                 # mov  [r12], cl
    cave += bytes.fromhex("4531ed")                   # xor  r13d, r13d
    cave += bytes.fromhex("a801")                     # test al, 1           ; was Left Ctrl down?
    cave += bytes.fromhex("7403")                     # jz   +3
    cave += bytes.fromhex("41b501")                   # mov  r13b, 1         ; -> Fn down
    cave += b"\xe9" + struct.pack("<i", ret_rva - (cave_rva + len(cave) + 5))   # jmp back
    assert len(cave) <= CAVE_LEN, len(cave)

    d[r2o(cave_rva):r2o(cave_rva) + len(cave)] = cave
    d[r2o(site_rva):r2o(site_rva) + SITE_LEN] = (
        b"\xe9" + struct.pack("<i", cave_rva - (site_rva + 5)) + b"\x90" * (SITE_LEN - 5))

    # Drop the (now invalid) embedded signature so signtool can sign cleanly.
    dd = opt + 112
    secoff, secsz = struct.unpack_from("<II", d, dd + 4 * 8)
    if secoff and secoff + secsz == len(d):
        del d[secoff:]
    struct.pack_into("<II", d, dd + 4 * 8, 0, 0)
    struct.pack_into("<I", d, opt + 64, 0)            # checksum: signtool recomputes
    return site_rva, cave_rva, len(cave)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=DEFAULT_SRC, help="original KeyMagic.sys (default: installed driver)")
    ap.add_argument("--out", default="KeyMagicFnSwap.sys", help="where to write the patched copy")
    ap.add_argument("--check", action="store_true", help="only verify the driver can be patched")
    a = ap.parse_args()

    d = bytearray(open(a.src, "rb").read())
    print("source : %s" % a.src)
    print("sha256 : %s" % hashlib.sha256(d).hexdigest())
    site, cave, n = patch(d)
    print("patch site rva %#x -> cave rva %#x (%d bytes)" % (site, cave, n))
    if a.check:
        print("OK: this driver can be patched (nothing written).")
        return
    open(a.out, "wb").write(d)
    print("wrote  : %s (%d bytes, UNSIGNED - run Install-FnCtrlSwap.ps1)" % (a.out, len(d)))


if __name__ == "__main__":
    sys.exit(main())
