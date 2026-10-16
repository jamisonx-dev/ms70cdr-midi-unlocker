#!/usr/bin/env python3
"""Reach slot 5 by sending a WHOLE patch (`28`) to the edit buffer.
Step 1 proves pack7 rebuilds the pedal's own dump byte-for-byte; nothing is sent unless it does.
Usage: probe_fullpatch.py set   (TheVibe speed -> 60, original saved to orig_cur.syx)
       probe_fullpatch.py restore"""
import sys, time
import zms

out, inp = zms.open_ports()


def X(*b, w=0.5):
    return zms.xfer(out, inp, zms.sx(*b), w)


def cur_msg():
    return [m for m in X(0x29, w=0.8) if m.type == 'sysex'][0]


X(0x50)
if sys.argv[1] == 'set':
    m = cur_msg()
    orig = list(m.bytes())
    u = zms.decode_patch(m)
    rebuilt = zms.patch_msg(u)
    print('round-trip identical:', rebuilt == orig)
    if rebuilt != orig:
        print([(i, a, b) for i, (a, b) in enumerate(zip(orig, rebuilt)) if a != b]); sys.exit(1)
    open('orig_cur.syx', 'wb').write(bytes(orig))
    new = zms.set_param(u, 4, 0, 60)
    print('changed bytes (unpacked):', [i for i in range(122) if new[i] != u[i]])
    t = time.time()
    r = zms.xfer(out, inp, mido_msg := __import__('mido').Message.from_bytes(zms.patch_msg(new)), 1.0)
    print('send replies:'); zms.show(r)
    back = zms.decode_patch(cur_msg())
    print('read-back == what we sent:', back == new)
    zms.describe(back)
else:
    orig = list(open('orig_cur.syx', 'rb').read())
    zms.show(zms.xfer(out, inp, __import__('mido').Message.from_bytes(orig), 1.0))
    back = list(cur_msg().bytes())
    print('restored == original:', back == orig)
X(0x51, w=0.2)
