#!/usr/bin/env python3
"""patch_6slot.py: make MIDI "31" parameter edits reach ALL SIX effect slots of a Zoom MS-70CDR.

Stock firmware only applies a `31 <slot> <param> <lsb> <msb>` edit to slots 0-2 (the gate is a
single `cmpltu 2,slot` in the DSP main program). This script changes two instructions inside a
Zoom updater .exe that YOU already have, and writes a new .exe next to it. It never touches
the original and ships none of Zoom's code.

    python3 patch_6slot.py <input updater .exe> [output .exe]

What it changes (offsets are in the .exe; see FORMAT.md, "6-SLOT PATCH"):
  0x62291  4B -> AB   cmpltu 2,slot   ->  cmpltu 5,slot   (slots 0-5 accepted)
  0x622A3  81 -> C1   cmpeq  4,slot   ->  cmpeq  6,slot   (patch-name editor moves from slot 4 to 6:
                                                          `31 06 <pos> <ascii> 00`)

It only runs on the exact build it was written against (checked by SHA-256 below, then by the
original bytes), and refuses anything else, because the offsets mean nothing in another file.

RISK: this is firmware. You flash the result at your own risk. The pedal's boot program is not
changed by this patch; recovery from a bad main program is to hold UP+DOWN (cursor keys) while
plugging in USB. No warranty.
"""
import hashlib
import sys

# Zoom Effect Manager 1.1.0 output, 2020-09-16 build for the MS-70CDR (main program = stock v2.10
# apart from the version string).
EXPECTED_SHA256 = "58f76bffc93fe59f"          # prefix, checked against the full digest below
EDITS = [(0x62291, 0x4B, 0xAB), (0x622A3, 0x81, 0xC1)]
RESULT_SHA256 = "a995d2e19f960980"


def main(argv):
    if not 1 <= len(argv) <= 2:
        sys.exit(__doc__)
    src = argv[0]
    dst = argv[1] if len(argv) == 2 else src.rsplit(".", 1)[0] + " + 6SLOT-EDIT.exe"
    data = bytearray(open(src, "rb").read())
    digest = hashlib.sha256(data).hexdigest()
    if not digest.startswith(EXPECTED_SHA256):
        sys.exit("refusing: this is not the build the patch was written for\n"
                 "  got sha256 %s\n  want sha256 %s..." % (digest, EXPECTED_SHA256))
    for off, old, new in EDITS:
        if data[off] != old:
            sys.exit("refusing: byte at 0x%X is %02X, expected %02X" % (off, data[off], old))
        data[off] = new
    out = hashlib.sha256(data).hexdigest()
    if not out.startswith(RESULT_SHA256):
        sys.exit("internal check failed: patched file hashes to %s" % out)
    open(dst, "wb").write(data)
    print("wrote %s\n  sha256 %s" % (dst, out))


if __name__ == "__main__":
    main(sys.argv[1:])
