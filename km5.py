import re, pickle
from capstone import *
exec(open('km.py').read().split("print('base")[0])
base, secs, funcs = pickle.load(open('km.pkl','rb'))
md = Cs(CS_ARCH_X86, CS_MODE_64)
want = ['0xa4','0xa5','0x2a4','0x2a8','0x2a9','0x4a8','0x4ac','0x4ad','0x6ac']
for b,e in funcs:
    for ins in md.disasm(d[r2o(b):r2o(b)+(e-b)], b):
        for w in want:
            if re.search(r'\+ %s\]' % w, ins.op_str) and b not in (0x35c0,):
                print('func %x  %x: %s %s' % (b, ins.address, ins.mnemonic, ins.op_str))
