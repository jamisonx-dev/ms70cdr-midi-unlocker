#!/usr/bin/env python3
"""Parameter tables out of Zoom ZDL effect files (MS-50G/60B/70CDR, G1on/B1on family).

Layout (found 2026-10-13 on SMS_DLY.ZDL, checked against thammer's map):
  effect ID  = u32 LE at file offset 0x40
  name entry = 12-byte name, then FF FF FF FF ...          (48 bytes)
  params     = consecutive 48-byte records: name[12], max u32, default u32, ...
Usage: zdl_params.py <dir-of-ZDLs>... -> writes zdl_params.json {id: {name, file, params:[{name,max,default}]}}
"""
import json, os, re, struct, sys

NAME = re.compile(rb'[\x20-\x7e]{1,12}\x00*$')


def is_name(b):
    return bool(NAME.match(b)) and b[0] != 0


def parse(z):
    fid = struct.unpack_from('<I', z, 0x40)[0]
    for m in re.finditer(rb'\xff\xff\xff\xff', z):
        h = m.start() - 12
        if h < 0x40 or not is_name(z[h:h + 12]):
            continue
        params, o = [], h + 0x30
        while o + 0x14 <= len(z) and is_name(z[o:o + 12]):
            mx, df = struct.unpack_from('<II', z, o + 12)
            if mx > 100000 or df > mx:
                break
            params.append(dict(name=z[o:o + 12].split(b'\0')[0].decode(), max=mx, default=df))
            o += 0x30
        if params:
            return fid, z[h:h + 12].split(b'\0')[0].decode(), params
    return fid, None, []


def main(dirs):
    out = {}
    for d in dirs:
        for f in sorted(os.listdir(d)):
            if not f.upper().endswith('.ZDL'):
                continue
            fid, name, params = parse(open(os.path.join(d, f), 'rb').read())
            key = f'{fid:08X}'
            if key not in out or (params and not out[key]['params']):
                out[key] = dict(name=name or f[:-4], file=f, params=params)
    json.dump(out, open('zdl_params.json', 'w'), indent=1)
    empty = [v['file'] for v in out.values() if not v['params']]
    print(len(out), 'effects;', len(empty), 'without a parsed table:', empty[:20])


if __name__ == '__main__':
    main(sys.argv[1:])
