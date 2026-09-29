import struct, re, sys
from capstone import *
d = open(r'C:\Windows\System32\drivers\KeyMagic.sys','rb').read()
pe = struct.unpack_from('<I', d, 0x3c)[0]
nsec = struct.unpack_from('<H', d, pe+6)[0]
optsz = struct.unpack_from('<H', d, pe+20)[0]
opt = pe+24
base = struct.unpack_from('<Q', d, opt+24)[0]
dd = opt+112
exc_rva, exc_sz = struct.unpack_from('<II', d, dd+3*8)
secs = []
for i in range(nsec):
    o = opt+optsz+i*40
    name = d[o:o+8].rstrip(b'\0').decode()
    vs, va, rs, ro = struct.unpack_from('<IIII', d, o+8)
    secs.append((name, va, vs, ro, rs))
def r2o(rva):
    for n,va,vs,ro,rs in secs:
        if va <= rva < va+max(vs,rs): return ro + rva - va
def o2r(off):
    for n,va,vs,ro,rs in secs:
        if ro <= off < ro+rs: return va + off - ro
print('base %x' % base, [(s[0], hex(s[1]), hex(s[2])) for s in secs])
funcs = []
eo = r2o(exc_rva)
for i in range(exc_sz//12):
    b,e,u = struct.unpack_from('<III', d, eo+i*12)
    funcs.append((b,e))
funcs.sort()
print(len(funcs), 'functions')
md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail = False
def func_of(rva):
    for b,e in funcs:
        if b <= rva < e: return b
strs = {}
for m in re.finditer(rb'(?:[\x20-\x7e]\x00){4,}', d):
    s = m.group().decode('utf-16le'); strs[o2r(m.start())] = s
for m in re.finditer(rb'[\x20-\x7e]{6,}', d):
    if o2r(m.start()): strs.setdefault(o2r(m.start()), m.group().decode())
# code xrefs to strings
refs = {}
for b,e in funcs:
    code = d[r2o(b):r2o(b)+(e-b)]
    for ins in md.disasm(code, b):
        if ins.mnemonic == 'lea' and 'rip' in ins.op_str:
            m = re.search(r'\[rip ([+-]) (0x[0-9a-f]+)\]', ins.op_str)
            if m:
                tgt = ins.address + ins.size + (int(m.group(2),16) * (1 if m.group(1)=='+' else -1))
                if tgt in strs: refs.setdefault(b, []).append((ins.address, strs[tgt]))
for b in sorted(refs):
    print('func %x (size %d):' % (b, dict(funcs)[b]-b))
    for a,s in refs[b]: print('    %x -> %r' % (a, s))
import pickle; pickle.dump((base, secs, funcs), open('km.pkl','wb'))
