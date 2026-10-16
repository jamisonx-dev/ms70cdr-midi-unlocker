#!/usr/bin/env python3
"""zms.py -- probe a Zoom MS-70CDR (original MS series, device id 0x61) over USB MIDI.

Read-only by default. Talks over the ALSA sequencer with mido, so the pedal's
port must NOT also be feeding the ORC brain while probing (cut it with
`aconnect -d <zoom> <brain>`; the brain re-subscribes on restart/replug).

Usage:
  zms.py id                 identity request
  zms.py prog               current program number (0x33)
  zms.py cur                editor on + dump the current patch (0x29), decoded
  zms.py get N              dump stored patch N (1-50) via 0x09, decoded
  zms.py raw HEX...         send arbitrary bytes (F0..F7), print replies
"""
import sys, time, mido

DEV = 0x61
HDR = [0x52, 0x00, DEV]          # mido strips F0/F7


def open_ports():
    name = next(n for n in mido.get_output_names() if 'ZOOM MS' in n)
    iname = next(n for n in mido.get_input_names() if 'ZOOM MS' in n)
    return mido.open_output(name), mido.open_input(iname)


def xfer(out, inp, data, wait=0.6):
    """Send one message (list of bytes incl. F0/F7, or a mido msg); collect replies."""
    for _ in inp.iter_pending():
        pass
    msg = mido.Message.from_bytes(data) if isinstance(data, list) else data
    out.send(msg)
    got, t_end = [], time.time() + wait
    while time.time() < t_end:
        for m in inp.iter_pending():
            got.append(m)
            t_end = max(t_end, time.time() + 0.15)
        time.sleep(0.005)
    return got


def sx(*body):
    return [0xF0] + HDR + list(body) + [0xF7]


def unpack7(data):
    """Zoom 7-in-8: each group = 1 byte of MSBs (bit6 -> first byte) + up to 7 bytes."""
    out, i = [], 0
    while i < len(data):
        hi = data[i]
        grp = data[i + 1:i + 8]
        for k, b in enumerate(grp):
            out.append(b | (0x80 if hi & (1 << (6 - k)) else 0))
        i += 8
    return bytes(out)


def pack7(data):
    """Inverse of unpack7."""
    out = []
    for i in range(0, len(data), 7):
        grp = data[i:i + 7]
        hi = 0
        for k, b in enumerate(grp):
            if b & 0x80:
                hi |= 1 << (6 - k)
        out.append(hi)
        out.extend(b & 0x7F for b in grp)
    return out


# (shift, width) of P0..P8 inside an effect block's little-endian bitfield
PARAM_BITS = [(29, 13), (42, 13), (55, 13)] + [(68 + 8 * k, 8) for k in range(5)] + [(128, 8)]


def set_param(u, slot, idx, value):
    """Return a copy of unpacked patch u with effect `slot` (0-5) param `idx` (0-8) = value."""
    u = bytearray(u)
    blk = slice(18 * slot, 18 * slot + 18)
    n = int.from_bytes(u[blk], 'little')
    sh, w = PARAM_BITS[idx]
    n = (n & ~(((1 << w) - 1) << sh)) | ((value & ((1 << w) - 1)) << sh)
    u[blk] = n.to_bytes(18, 'little')
    return bytes(u)


def patch_msg(u):
    """Unpacked 122 bytes -> full `28` sysex (list incl. F0/F7) for the edit buffer."""
    return [0xF0] + HDR + [0x28] + pack7(u) + [0xF7]


def hexs(bs):
    return ' '.join(f'{b:02X}' for b in bs)


def show(msgs):
    for m in msgs:
        b = m.bytes()
        print(f'  <- [{len(b)}] {hexs(b) if len(b) <= 48 else hexs(b[:48]) + " ..."}')


def decode_patch(m):
    """m: mido sysex whose data = 52 00 61 28 <packed>. Returns unpacked bytes."""
    d = list(m.data)
    if d[:4] != [0x52, 0x00, DEV, 0x28]:
        return None
    u = unpack7(d[4:])
    return u


_FX = None


def fxmap():
    global _FX
    if _FX is None:
        import json, os
        _FX = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'msog_effects.json')))
    return _FX


def parse(u):
    """Unpacked 122-byte patch -> dict. Layout per thammer/zoom-explorer readMSPatch:
    6 x 18-byte effect blocks (one little-endian bitfield each: on 1, id 28,
    P0-P2 13 bits, P3-P7 8 bits, 20 unknown, P8 8, 8 unknown), 3 bytes misc
    (tempo, edit slot, num effects), 10-char name, 1 byte."""
    fx = []
    for s in range(6):
        n = int.from_bytes(u[18 * s:18 * s + 18], 'little')
        on, fid = n & 1, (n >> 1) & ((1 << 28) - 1)
        ps = [(n >> 29) & 0x1FFF, (n >> 42) & 0x1FFF, (n >> 55) & 0x1FFF]
        ps += [(n >> (68 + 8 * k)) & 0xFF for k in range(5)]
        ps.append((n >> 128) & 0xFF)
        fx.append(dict(on=on, id=fid, params=ps, unk=((n >> 108) & 0xFFFFF, n >> 136)))
    m = u[108:111]
    return dict(fx=fx,
                tempo=((m[1] & 0xE0) >> 5) | ((m[2] & 0x1F) << 3),
                edit_slot=((m[0] & 0xC0) >> 6) | ((m[1] & 1) << 2),
                num_fx=(m[1] & 0x1C) >> 2, dsp_full=m[0] & 0x3F,
                name=bytes(u[111:121]).decode('ascii', 'replace').rstrip('\x00 '))


def describe(u, verbose=True):
    p = parse(u)
    print(f'  "{p["name"]}"  tempo {p["tempo"]}  fx {p["num_fx"]}  edit-slot {p["edit_slot"]}  dsp-bits {p["dsp_full"]:06b}')
    fm = fxmap()
    for s, e in enumerate(p['fx']):
        if not e['id']:
            continue
        info = fm.get(f'{e["id"]:08X}')
        nm = info['name'] if info else '??'
        line = f'   {s + 1}: {"ON " if e["on"] else "off"} {e["id"]:08X} {nm:<12}'
        if verbose and info:
            vals = []
            for i, pr in enumerate(info['params']):
                v = e['params'][i] if i < 9 else None
                if v is not None and pr.get('values') and v < len(pr['values']):
                    v = pr['values'][v]
                vals.append(f'{pr["name"]}={v}')
            line += ' ' + ', '.join(vals)
        elif verbose:
            line += ' raw params ' + str(e['params'])
        print(line)
    return p


def main():
    a = sys.argv[1:] or ['id']
    out, inp = open_ports()
    cmd = a[0]
    if cmd == 'id':
        show(xfer(out, inp, [0xF0, 0x7E, 0x00, 0x06, 0x01, 0xF7]))
    elif cmd == 'prog':
        show(xfer(out, inp, sx(0x33)))
    elif cmd in ('cur', 'get'):
        show(xfer(out, inp, sx(0x50)))          # editor mode on
        if cmd == 'cur':
            r = xfer(out, inp, sx(0x29), 1.0)
        else:
            n = int(a[1]) - 1
            r = xfer(out, inp, sx(0x09, 0x00, 0x00, n), 1.0)
        show(r)
        for m in r:
            if m.type == 'sysex':
                u = decode_patch(m)
                if u is None and list(m.data[:4]) == [0x52, 0x00, DEV, 0x08]:
                    d = list(m.data)
                    u = unpack7(d[9:])[:d[7] | d[8] << 7]
                if u is not None:
                    describe(u)
                    open(f'patch_{cmd}_{a[1] if cmd == "get" else "cur"}.bin', 'wb').write(bytes(m.bytes()))
        xfer(out, inp, sx(0x51), 0.2)          # editor mode off
    elif cmd == 'all':                         # read every stored patch (0x09), read-only
        xfer(out, inp, sx(0x50), 0.3)
        import os
        os.makedirs('dump', exist_ok=True)
        for n in range(50):
            r = xfer(out, inp, sx(0x09, 0x00, 0x00, n), 0.8)
            sy = [m for m in r if m.type == 'sysex']
            if not sy:
                print(f'#{n + 1}: no reply'); continue
            b = bytes(sy[0].bytes())
            open(f'dump/p{n + 1:02d}.syx', 'wb').write(b)
            d = list(sy[0].data)
            print(f'#{n + 1:2d} [{len(b)}] head {hexs(d[:10])}')
            if d[3] == 0x08:                    # 08 00 00 <n> <lenLSB> <lenMSB> <packed...>
                ln = d[7] | d[8] << 7
                u = unpack7(d[9:])
                describe(u[:ln], verbose=False)
        xfer(out, inp, sx(0x51), 0.2)
    elif cmd == 'raw':
        bs = [int(x, 16) for x in a[1:]]
        show(xfer(out, inp, bs, 1.0))
    out.close(); inp.close()


if __name__ == '__main__':
    main()
