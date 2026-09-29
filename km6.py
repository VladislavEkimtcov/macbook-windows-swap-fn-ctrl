import re, pickle
from capstone import *
exec(open('km.py').read().split("print('base")[0])
base, secs, funcs = pickle.load(open('km.pkl','rb'))
md = Cs(CS_ARCH_X86, CS_MODE_64)
for b,e in funcs:
    hits=[]
    for ins in md.disasm(d[r2o(b):r2o(b)+(e-b)], b):
        m = re.search(r'0x(b40[0-9a-f]{5})\b', ins.op_str)
        if m: hits.append('%x:%s %s' % (ins.address, ins.mnemonic, ins.op_str))
    if hits: print('func %x (%d):' % (b, e-b)); [print('   ', h) for h in hits]
