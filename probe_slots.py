#!/usr/bin/env python3
"""Which effect block does `31 <slot-arg> 07 ...` move? Each edit is undone right after.
Run with the pedal disconnected from the brain (aconnect -d)."""
import zms

out, inp = zms.open_ports()


def X(*b, w=0.5):
    return zms.xfer(out, inp, zms.sx(*b), w)


def raw():
    return zms.decode_patch([m for m in X(0x29, w=0.8) if m.type == 'sysex'][0])


X(0x50)
base = raw()
p0 = zms.parse(base)
print('edit-slot field:', p0['edit_slot'], ' param idx5 per block:', [f['params'][5] for f in p0['fx']])
for k in (3, 4, 5, 0, 1, 2):
    X(0x31, k, 7, 50, 0)
    u = raw()
    blks = sorted({i // 18 for i in range(108) if u[i] != base[i]})
    print(f'slot-arg {k}: moved blocks {[b + 1 for b in blks] if blks else "none"}')
    if blks:
        v = p0['fx'][blks[0]]['params'][5]
        X(0x31, k, 7, v & 0x7F, v >> 7)
        after = raw()
        print('   restored:', after == base)
        base = after
X(0x51, w=0.2)
