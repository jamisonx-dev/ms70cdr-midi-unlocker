#!/usr/bin/env python3
"""Inbound `08` = write a patch straight into memory slot N. Safe test: write patch 50 back with its own content."""
import zlib, mido, zms

out, inp = zms.open_ports()


def X(*b, w=0.6):
    return zms.xfer(out, inp, zms.sx(*b), w)


def build_08(n, u):
    crc = zlib.crc32(bytes(u)) ^ 0xFFFFFFFF
    return ([0xF0, 0x52, 0x00, 0x61, 0x08, 0, 0, n, 122 & 0x7F, 122 >> 7] + zms.pack7(bytes(u))
            + [(crc >> (7 * k)) & 0x7F for k in range(5)] + [0xF7])


X(0x50)
n = 49  # patch 50, "Empty"
d = list([m for m in X(0x09, 0, 0, n, w=1.0) if m.type == 'sysex'][0].bytes())
u = bytes(zms.unpack7(d[10:-6]))[:122]
msg = build_08(n, u)
print('rebuilt message == the dump the pedal sent:', msg == d)
r = zms.xfer(out, inp, mido.Message.from_bytes(msg), 2.0)
print('write reply:')
zms.show(r)
d2 = list([m for m in X(0x09, 0, 0, n, w=1.0) if m.type == 'sysex'][0].bytes())
print('patch 50 unchanged after write:', d2 == d)
X(0x51, w=0.2)
