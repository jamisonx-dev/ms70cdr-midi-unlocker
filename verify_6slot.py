#!/usr/bin/env python3
"""After the 6SLOT-EDIT flash: do `31` edits reach every effect slot, and does the name editor answer at slot 6?
Every change is put back and the final edit buffer is compared to the starting one."""
import zms

out, inp = zms.open_ports()


def X(*b, w=0.5):
    return zms.xfer(out, inp, zms.sx(*b), w)


def raw():
    return zms.decode_patch([m for m in X(0x29, w=0.8) if m.type == 'sysex'][0])


print('identity:'); zms.show(zms.xfer(out, inp, [0xF0, 0x7E, 0x00, 0x06, 0x01, 0xF7]))
X(0x50)
start = raw()
p = zms.parse(start)
zms.describe(start)
for s, e in enumerate(p['fx']):
    if not e['id']:
        print(f'slot {s + 1}: empty, skipped'); continue
    old = e['params'][0]
    new = old + 1 if old < 5 else old - 1          # small nudge of knob 1
    X(0x31, s, 2, new & 0x7F, new >> 7)
    got = zms.parse(raw())['fx'][s]['params'][0]
    X(0x31, s, 2, old & 0x7F, old >> 7)
    back = zms.parse(raw())['fx'][s]['params'][0]
    print(f'slot {s + 1}: knob1 {old} -> sent {new} -> read {got} -> restored {back}   {"OK" if got == new and back == old else "NO"}')
name = p['name']
X(0x31, 6, 0, ord('Q'), 0)
n2 = zms.parse(raw())['name']
X(0x31, 6, 0, ord(name[0]), 0)
print(f'name editor at slot 6: {name!r} -> {n2!r} -> {zms.parse(raw())["name"]!r}')
print('edit buffer back to start:', raw() == start)
X(0x51, w=0.2)
