import struct, re
exec(open('km.py').read().split("print('base")[0])
for n,va,vs,ro,rs in secs:
    o = pe+24+optsz+[s[0] for s in secs].index(n)*40
    ch = struct.unpack_from('<I', d, o+36)[0]
    print('%-8s va=%x vsize=%x raw=%x rsize=%x  slack=%x  chars=%08x' % (n,va,vs,ro,rs,rs-vs,ch))
print('checksum field', hex(struct.unpack_from('<I', d, opt+64)[0]), 'secdir', struct.unpack_from('<II', d, dd+4*8))
for a in (0x3d63, 0x3d67, 0x3d6b):
    o = r2o(a); print(hex(a), d[o:o+8].hex(' '))
# candidate caves: runs of 0xCC / 0x00 >= 48 inside .text raw range
t = [s for s in secs if s[0]=='.text'][0]
raw = d[t[3]:t[3]+t[4]]
for m in re.finditer(rb'\xcc{40,}|\x00{40,}', raw):
    print('cave rva %x len %d byte %02x' % (t[1]+m.start(), len(m.group()), m.group()[0]))
