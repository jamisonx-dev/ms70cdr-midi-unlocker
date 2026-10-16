#!/usr/bin/env python3
"""Read-only: `2B` (global settings -> `2A` reply) and `03` memory reads of the name buffer / slot table."""
import zms

out, inp = zms.open_ports()


def X(*b, w=0.6):
    return zms.xfer(out, inp, zms.sx(*b), w)


def mem(addr, n):
    a = [(addr >> (7 * k)) & 0x7F for k in range(5)]
    for m in X(0x03, *a, n & 0x7F, n >> 7, w=0.8):
        d = list(m.bytes())
        if m.type == 'sysex' and d[4] == 0x02:
            return bytes(zms.unpack7(d[12:-6]))[:n]


X(0x50)
for m in X(0x2B, w=0.8):
    d = list(m.bytes())
    print('2B ->', len(d), zms.hexs(d[:12]), '...')
    if d[4] == 0x2A:
        u = bytes(zms.unpack7(d[5:-1]))
        print('   settings (unpacked %d):' % len(u), zms.hexs(u))
print('name buffer 0xC009C070:', mem(0xC009C070, 12))
t = mem(0xC009BF58, 6 * 44)
for s in range(6):
    w = [int.from_bytes(t[44 * s + 4 * k:44 * s + 4 * k + 4], 'little') for k in range(11)]
    print(f'slot table [{s}]:', ' '.join(f'{x:x}' for x in w))
X(0x51, w=0.2)
