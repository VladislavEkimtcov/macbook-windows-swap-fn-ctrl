# Swap Fn and Control on a MacBook's built-in keyboard in Windows (Boot Camp)

Can you swap the `fn` and `control` keys on a MacBook keyboard while running Windows 10 or 11 under
Boot Camp? Not with AutoHotkey, SharpKeys, PowerToys Keyboard Manager, KeyTweak or the `Scancode Map`
registry value. This repo shows why with measurements from a real **MacBook Air A1465 (MacBookAir6,1)**,
and where the swap *can* be made: Apple's Boot Camp keyboard filter driver, **`KeyMagic.sys`**.

> **Status: research done, patcher written, patched driver not yet booted.**
> The findings below were measured on hardware. The patch is derived from disassembly and its output
> was checked instruction by instruction, but it has **not been loaded on a running system yet**. This
> README will be updated with the result. Treat it as experimental and read *Risks*.

## Why no remapper can swap Fn and Ctrl

On the built-in Apple keyboard, Fn is not a key as far as Windows is concerned. It is one bit
(report ID 1, byte 9, bit 1; HID vendor usage `0xFF:0x03`) inside the keyboard's USB input report.
Apple's `KeyMagic.sys` is a lower filter under `HidUsb`. It reads that bit to decide which translations
to apply, then throws it away before Windows parses the report.

Captured with a low-level keyboard hook on the built-in keyboard:

| pressed | Windows saw |
|---|---|
| Fn alone | nothing |
| Left Control | VK 0xA2, scan 0x1D |
| Fn + Backspace | Delete |
| Fn + Left arrow | Home |
| Fn + Return | Insert |
| Fn + F1 | nothing (brightness is handled below the key layer) |

So Fn has no scan code, no virtual key and no Raw Input event. Tools that remap scan codes or hook keys
have nothing to grab. I also checked the alternatives: the keyboard collection cannot be opened for reading
from user mode, `HidD_GetInputReport` on it fails, `KeyMagic`'s control device (`\\.\AppleKeyboard`) has no
IOCTL for Fn state or keymaps, and the registry `Keymap` / `KeymapFn` / `KeymapNumlock` tables only rewrite the
six key slots and never touch the modifier byte. Details: [docs/KeyMagic-internals.md](docs/KeyMagic-internals.md).

## The patch

`patcher/patch_keymagic.py` reads the `KeyMagic.sys` already installed on your machine and writes a patched
copy. It ships no Apple binary. At the point where the driver has located the modifier byte and the Fn flag,
40 bytes of added code swap them:

```
Ctrl bit := Fn flag was set
Fn flag  := Left Ctrl bit was set
```

The physical Fn key then produces a real Left Ctrl, and the physical Control key drives the driver's own
Fn logic (arrows to Home/End/PgUp/PgDn, Backspace to Delete, the F-row mode).

```
python patcher/patch_keymagic.py --check      # verify your driver build is patchable, writes nothing
python patcher/patch_keymagic.py              # writes KeyMagicFnSwap.sys (unsigned)
```

The patch site is found by byte signature, so it should work on other builds that share the code. It was
developed against `KeyMagic.sys` 6.1.8086.1, SHA-256 `a92d0bff926f23cd28191a0ff77b9a60b2a92d44b62db27f1610d4e3aefac8d8`.

Loading a modified kernel driver on 64-bit Windows needs a valid signature that your machine trusts (for
example test-signing mode). That part depends on your setup and is not automated here yet.

`patcher/Uninstall-FnCtrlSwap.ps1` restores the original driver path if you point the `KeyMagic` service at a
copy; it is a no-op otherwise.

## Risks

`KeyMagic` is a lower filter for the keyboard. A broken replacement can leave the built-in keyboard dead until
you restore the original, so keep an external USB keyboard (KeyMagic only filters Apple keyboards) or remote
access available. Do not overwrite the original `KeyMagic.sys`; load a separate copy so rollback is one registry value.

## User-mode only? (honourable mention)

Without touching the driver you can get part of the way, but not all of it:

* **Control acting as Fn** works in user mode: a low-level keyboard hook can watch for Left Ctrl and translate
  arrows, Backspace and Return into Home/End/PgUp/PgDn, Delete and Insert.
* **Fn acting as Ctrl** cannot be done cleanly: Fn is invisible until another key is pressed. Remapping keys through
  `KeymapFn` to spare usages would give Ctrl+key combos, but never Ctrl+click or Ctrl+scroll.

Neither is implemented here.

## Tools in this repo

| file | what it does |
|---|---|
| `patcher/patch_keymagic.py` | builds the patched copy of your local `KeyMagic.sys` |
| `FnWatch.cs` | low-level hook + Raw Input logger (build with the in-box `csc.exe`); the Raw Input part did not log on the first run |
| `km.py`, `km4.py`, `km5.py`, `km6.py`, `km7.py` | PE parser, per-function disassembler and cross-reference finders used for the analysis (need `capstone`) |
| `docs/KeyMagic-internals.md` | report layout, code paths, tables, IOCTLs |

## Compatibility

Measured on: MacBook Air A1465 (MacBookAir6,1), Windows 10 IoT Enterprise LTSC 2021, Boot Camp 6.1.8086.2, keyboard
`USB\VID_05AC&PID_0290`. `KeyMagic`'s `KeyboardTable` lists about 70 Apple keyboard product IDs, so other Boot Camp
MacBooks likely share the code path, but that is untested.

## Legal

Independent interoperability research on hardware the author owns. Not affiliated with or endorsed by Apple.
"Apple", "MacBook" and "Boot Camp" are trademarks of Apple Inc. No Apple binaries are distributed here.

## License

MIT, see [LICENSE](LICENSE).
