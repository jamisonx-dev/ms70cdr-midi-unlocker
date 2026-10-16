# Zoom MS-70CDR: six-slot MIDI control

Notes, tools and a patch for the **Zoom MS-70CDR** multi-effects pedal (only this model was tested).

**What this gets you**

- **All six effect slots editable over MIDI.** Stock firmware accepts a SysEx parameter edit
  (`31 <slot> <param> <lsb> <msb>`) only for slots 1-3 and silently ignores 4-6. `patch_6slot.py`
  fixes that with a two-byte change.
- **The pedal reports back.** With editor mode on (`50`), every knob turn and on/off press on all six slots
  comes out as the same `31` message you send in, so a host can stay in sync with the front panel
  (both directions).
- **A full SysEx map**, decoded from the firmware and measured on a real unit: patch read and write, memory read,
  store, tuner, program change. See `FORMAT.md`.

## Files

| File | What |
|---|---|
| `FORMAT.md` | The protocol, the firmware findings, the patch, what was measured and what is still open |
| `patch_6slot.py` | Applies the two-byte patch to a Zoom updater `.exe` you already have |
| `zms.py` | Small SysEx tool (mido): identity, dump patches, read/set parameters, store |
| `verify_6slot.py`, `probe_*.py` | The scripts used to check the patch and probe the pedal |
| `zdl_params.py` | Builds a parameter table (names, ranges) from a folder of ZDL effect files |
| `msog_effects.json` | Effect IDs and parameter names, compacted from thammer/zoom-explorer (MIT) |

## What is NOT here, on purpose

Zoom's firmware, updater programs, effect files and manual are Zoom's and are not redistributed.
The patch is shipped as a script that edits **your own copy** and checks it is the exact build it was
written for (SHA-256, then the original bytes) before changing anything.

## Using the patch

1. Get the updater the patch was written for: the Zoom Effect Manager 1.1.0 output for the MS-70CDR dated
   2020-09-16 (sha256 begins `58f76bff`). Other builds are refused.
2. `python3 patch_6slot.py "Zoom_updater.exe"` writes `Zoom_updater + 6SLOT-EDIT.exe` beside it.
3. Run that updater as you would any Zoom firmware update.

**This is firmware. You do it at your own risk.** The patch does not touch the pedal's boot program;
if the main program ever fails to start, holding the UP and DOWN cursor keys while plugging in USB
enters the update mode again. Still, no warranty, and read `FORMAT.md` first.

With the patch the patch-name editor moves from "slot 4" to `31 06 <pos> <ascii> 00`.

## Credit

Prior art this builds on: [thammer/zoom-explorer](https://github.com/thammer/zoom-explorer) (MIT, the patch
bit layout and effect maps), [g200kg/zoom-ms-utility](https://github.com/g200kg/zoom-ms-utility) (MIT, the
basic command set), shooking/ZoomPedalFun, and Barsik's Zoom Firmware Editor.

Not affiliated with or endorsed by ZOOM Corporation.

## License

MIT for the code and notes in this repository (see `LICENSE`). `msog_effects.json` derives from MIT-licensed
data by thammer.
