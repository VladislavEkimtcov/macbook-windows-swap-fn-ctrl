import struct, re, pickle, sys
from capstone import *
exec(open('km.py').read().split("print('base")[0])
base, secs, funcs = pickle.load(open('km.pkl','rb'))
md = Cs(CS_ARCH_X86, CS_MODE_64)
def dis(b):
    e = dict(funcs)[b]
    out=[]
    for ins in md.disasm(d[r2o(b):r2o(b)+(e-b)], b):
        out.append('%x: %-6s %s' % (ins.address, ins.mnemonic, ins.op_str))
    return out
if len(sys.argv) == 1:
    print('funcs:', ' '.join('%x(%d)' % (b, e-b) for b,e in funcs))
    for b,e in funcs:
        for ins in md.disasm(d[r2o(b):r2o(b)+(e-b)], b):
            m = re.search(r'\[rip ([+-]) (0x[0-9a-f]+)\]', ins.op_str)
            if m:
                t = ins.address + ins.size + int(m.group(2),16)*(1 if m.group(1)=='+' else -1)
                if 0x9000 <= t < 0x9060: print('func %x: %x %s %s -> %x' % (b, ins.address, ins.mnemonic, ins.op_str, t))
else:
    for a in sys.argv[1:]: print('\n'.join(dis(int(a,16)))); print()
