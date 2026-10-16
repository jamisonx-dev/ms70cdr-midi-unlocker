# Zoom MS-70CDR (original, hacked v2.10 firmware): MIDI notes

Session 2026-10-13. The pedal is plugged into the Pi: USB `1686:01a1`, ALSA card `Series`,
seq client `ZOOM MS Series`, MIDI only (no USB audio). Tool: `zms.py` (copy on the Pi in `~/zoom_ms/`).

## Prior art (what was already known)
- g200kg/zoom-ms-utility `midimessage.md`: the basic command set + a packed-byte bit table.
- thammer/zoom-explorer: README command table for the original MS series; `ZoomPatch.ts readMSPatch`
  = the working bitfield layout; `public/zoom-effect-mappings-msog.json` = effect IDs + param names/ranges
  (compacted here as `msog_effects.json`).
- shooking/ZoomPedalFun `MS70CDR/`: amidi scripts, a 0x00-0x7F command probe.
- The firmware hack on this pedal: a modified v2.10 updater made with Barsik's Zoom Firmware Editor, ZDL sets from B1on/B1Xon/G1on/G1Xon/MS-50G/60B/70CDR.

## MEASURED on this unit
- Identity reply: `F0 7E 00 06 02 52 61 00 00 00 32 2E 30 30 F7` -> id 0x61, version string "2.00".
- Header for everything else: `F0 52 00 61 <cmd> ... F7`.
- `33` (current program) only answered after `50` (editor mode on): `B0 00 00, B0 20 00, C0 <pp>`.
- `29` -> `28` + 140 packed bytes (146 total) = the EDIT BUFFER (includes unsaved tweaks).
- `09 00 00 <n>` -> `08 00 00 <n> 7A 00 <packed> ...` (156 bytes), n = 0-49 = the STORED patch. Read-only.
  All 50 dumped to `~/zoom_ms/dump/pNN.syx`.
- Packing: Zoom 7-in-8 (one MSB byte, bit6 -> first of the next 7). 140 packed -> 122 bytes.
- Unpacked layout (thammer, verified on all 50 patches): 6 x 18-byte effect blocks, each ONE little-endian
  bitfield: bit0 on, bits1-28 effect ID, P0-P2 13 bits each, P3-P7 8 bits each, 20 unknown, P8 8 bits,
  8 unknown. Then 3 misc bytes (tempo, edit slot, num effects, DSP-full bits), 10-char name, 1 byte.
- **`31 <slot> <param> <lsb> <msb>` edits the edit buffer, slot index direct (0 = first effect), but ONLY
  slots 0-2 take it; 3-5 are silently ignored** (tested on patch 44 with all 6 slots filled). Param 0 =
  on/off, 2.. = knobs. Values clamp to the param's max. Nothing stored.
- Program change to the program that is already selected does NOT reload it, but it DOES trigger auto-save
  (the unit under test runs with auto-save on): it stored my test edits. MIDI `31` edits alone do not seem to trigger a save.
- `32 01 00 00 <n> 00 00 00 00 00` stores the edit buffer into patch n: no reply, the pedal is busy ~1 s
  (a read right after got nothing); verified by re-reading `09`.
- Effect ID at offset 0x40 (LE u32) of every ZDL -> a table of 256 IDs built from the effect files. Names every effect in his
  patches except `020002F1` / `020001F1` (patch 50 "Empty", odd low bit: maybe junk).

- **The pedal REPORTS its own edits** (editor mode on, 90 s listen while the owner turned knobs): every knob
  step = `31 <slot> <param> <value-lsb> <msb>`, same message + same scale as the edit we send (TheVibe Bias
  48 -> 58 -> 48 arrived as `31 04 04 30..3A`). Effect on/off = `31 <slot> 00 <0|1> 00`. Slots 0-5 all
  report (slot 4 included), so the 3-slot limit is on RECEIVE only. A structural change / patch change
  arrives as a full `28` patch dump. ~5-15 messages/s per turned knob.
- **The screen page is NOT the edit limit:** with the pedal showing effect 5, `31 04 02 ...` (TheVibe Speed)
  was still ignored and `31 00 03 ...` still worked; the patch's edit-slot field stayed 1.

- **Full-patch write `28` + 140 packed bytes works, but ALSO only for slots 0-2.** `pack7` round-trips the
  pedal's own dump byte-for-byte (`zms.patch_msg`, `zms.set_param`). A patch changing slot 0 Level AND slot 4
  Speed came back with slot 0 changed, slot 4 untouched (screen agreed: Speed 25). No reply to `28`; the
  pedal's screen redraws the patch. Restoring by re-sending the original `28` = byte-identical.
  => slots 4-6 are locked against EVERY MIDI write path tried (31 and 28); they only report out.

## FIRMWARE (2026-10-13): modified v2.10 updater, disassembled
Toolchain: `fw/` (not published: extracted from a modified v2.10 updater's .rsrc). BIN 129 = main
program (TI AIS, C674x DSP, no ARM; loads 0x1181xxxx L2 + 0xC009DFC0.. DDR; entry 0xC00DD800; TI SYS/BIOS
tasks Task_MIDI, UsbTestMidi_Task ...), BIN 136 = 2nd AIS image (0xC03A.., update mode?), BIN 133 = 12 KB
bitmap, BIN 137 = effect filesystem (55AA, 4 KB blocks, 32-byte dir entries x4 copies). an AIS splitter script (not published);
disassembly = GNU objdump built `--target=tic6x-elf` on the Pi (`~/tools/binutils-tic6x/build/binutils/objdump`,
`fw/dis.sh` -> `~/zoom_ms/fw/dis/<addr>.s`).

- SysEx byte parser `0xC00ADD04(byte, pos)`: pos 1 = command (stored 0xC0047BA0); later bytes go to a
  per-command handler via jump tables at 0xC00EEF3C (cmd 0-8) and 0xC00EEF64 (cmd 0x28-0x31). Accepted
  commands: 00 01 02 03 04-08 0E 16 28 29 2A 2B 31 33 50 51 60 (+32). **Undocumented: 03, 2A, 2B, 08 inbound.**
- `31` parser `0xC00AD7E0`: slot -> b14+237, param -> b14+238, value -> b14+240 (lsb + msb<<7), job 16.
- `31` executor `0xC00AEB90`: **`cmpltu 2,slot` at 0xC00AEB94 = THE 3-SLOT GATE.** slot 0-2 -> apply via
  `0xC00BB600(slot, param, value, 0, 1)` (param 0 = on/off, value < 3). slot 3, 5+ -> ignored.
  **slot 4 = PATCH NAME: `31 04 <pos 0-9> <ascii> 00` sets one character** (0xC00C058C, buffer 0xC003C070).
  MEASURED: "Basic CN" -> "Xasic CN" -> back.
- `0xC00BB600` indexes a per-slot table at 0xC003BF58, 44 bytes/slot, room for exactly 6 slots (ends at
  0xC003C060, name buffer at 0xC003C070) => the apply routine is generic; only the gate limits MIDI to 0-2.
- CC handler `0xC00ADF20`: CC 74 (tuner, state 5) AND **CC 75** (sibling, state 6, other routine 0xC00ABC94;
  MEASURED: CC75=127 shows the TUNER too; which one mutes is untested, rig silent); value >= 64 on. Program change < 50 = patch; **PC 127 special** (flag-gated, 0xC00AD52C).

- **BIN 136 = the BOOT + FIRMWARE-UPDATE program** (separate from the main program): SYS/BIOS tasks
  `Task_BootMain`, `Task_VersionUpdateMIDI`, `UsbTestMidi_Task`; screens "Ready for firmware update!",
  "Now Writing...", "Keep Connect To PC", "Complete!", "An Error Occurred.", "FIRMWARE UPDATE".
  => firmware updates travel over USB MIDI (SysEx), and update mode probably lives outside the main program.
  OPEN before any flash: does Task_BootMain check the buttons BEFORE loading BIN 129 (so a bad main image
  is still recoverable)? Is there a checksum on BIN 129? Which button combo enters update mode on this model?
  (G1on: hold Up+Down while plugging in USB, per a Zoom-Firmware-Editor issue #29 comment.)

## FULL COMMAND MAP (decoded from firmware + measured, 2026-10-13)
NOTE: earlier notes said 0xC003xxxx for the slot table / name buffer; the MVKH high half is 0xC009 -> the real
addresses are 0xC009BF58 (live slot table, 6 x 44 B: on, id, P0..P8 as u32) and 0xC009C070 (name). MEASURED.
| cmd | what | evidence |
|-----|------|----------|
| 03 a0..a4 l0 l1 | **MEMORY READ**: 32-bit address (5x7, LSB first), 14-bit length -> reply `02 <addr5> <len2> <packed data> <crc5>` | read "HOLD FOR TUNER/TAP" @0xC00E9015, live slot table, name buffer |
| 08 00 00 n lenL lenH <packed 122> <crc5> | **WRITE PATCH n (0-49) TO MEMORY** (flash); reloads if n is current. Reply `00 <code>`: 0 ok, 3 write fail, 8 CRC bad, 10 bad header | wrote patch 50 back with its own data -> `00 00`, unchanged |
| 09 00 00 n | read stored patch n -> `08` dump (same format as above) | all 50 read |
| 28 <packed 122> | load patch into the edit buffer (job 13) | measured |
| 29 | dump edit buffer -> `28` | measured |
| 2B | read a 24-byte block @0xC009D8F8 -> reply `2A` (first 8 bytes look like an ID; rest ~0). Meaning unknown | measured |
| 2A <24 B packed> | WRITE that block (job 15). NOT tried | firmware |
| 31 s p lsb msb | edit: s 0-5 = effect slots (PATCHED), p 0 on/off, 2.. knobs; s 6 = name char p (PATCHED from 4) | measured |
| 32 01 00 00 n 00.. | store edit buffer to patch n | measured |
| 33 | current program -> CC0/CC32/PC | measured |
| 50 / 51 | editor mode on / off (on: pedal reports its own edits as `31`, structure changes as `28`) | measured |
| 01, 0E | reply `00 0B` (job 22/23) | firmware |
| 16 | info reply (job 10) | thammer |
| 04 / 05 / 06 | jobs 5 / 3 / multi-byte; not probed | firmware |
| 60 | runs a long chain of refresh/init routines (0xC00B2C40). NOT probed | firmware |
CRC (08 dumps, 03 replies) = zlib.crc32(unpacked) ^ 0xFFFFFFFF (= no final xor), sent as 5x7 bits LSB first.
CC: 74 tuner, 75 tuner (other mode); PC 0-49 patch; PC 127 special (flag-gated).
PARAM RANGES: every ZDL holds a param table: after the effect-name entry (name[12] + FFFFFFFF), 48-byte records
name[12], max u32, default u32. `zdl_params.py <dir of ZDLs>` -> `zdl_params.json` (235 effects; GEQs use another layout); the output is not published, run it on your own ZDLs.

## WHICH BUILD IS ON THE PEDAL (2026-10-13)
- NOT the 083120 Firmware-Editor file (lacks 23 effects the owner's patches use, e.g. _B_FZSML in Basic CN).
- It IS the output of Zoom Effect Manager 1.1.0 (`Zoom_updater.exe`, 2020-09-16,
  sha256 58f76bff...8fce, 139 effects; selection `fx list cdr 9 16 20.lst`). Its main program = stock v2.10
  except 2 bytes: version "2.10" -> "2.00" = exactly what the identity reply reports. Effects missing from it
  (ROOM, PLATE, CHAMBER, VIBRATO ...) are only used by old factory patches.
- Zoom Effect Manager = builds an updater from a library of 236 ZDLs from 5 stock updaters (his "library hack").

## 6-SLOT PATCH (FLASHED 2026-10-13, verified)
`patch_6slot.py` turns that build (sha256 58f76bff...) into the 6SLOT-EDIT build (sha256 a995d2e1...260e) = the build + 2 bytes:
- 0xC00AEB94 `cmpltu .L2 2,b4,b0` -> `cmpltu .L2 5,b4,b0` (word 0x00104BDA -> 0x0010ABDA; exe 0x62291 4B->AB):
  `31` edits for slots 0-5.
- 0xC00AEBA6 compact `cmpeq .L2 4,b3,b0` -> `6` (0x81A7 -> 0xC1A7, imm in bits 13-15; exe 0x622A3 81->C1):
  patch-name editor moves from "slot 4" to "slot 6": `31 06 <pos> <ascii> 00`.
Disassembly diff before/after = only those two instructions; AIS re-parses identically.
RISK NOTES: recovery = boot program (unchanged) checks UP+DOWN cursor keys before loading the main program;
boot AIS loader has no CRC; updater carries no resource checksum (editor-built updaters flash fine).
VERIFIED after flash (`verify_6slot.py`, patch 44): knob-1 edits on ALL six slots read back exactly and
restored; name editor at slot 6 ('Basic CN' -> 'Qasic CN' -> back); identity still "2.00"; buffer identical after.
Pedal now USB-bus-powered from the Pi.
Untested: edit to a slot that holds no effect (ORC side should only address existing slots).
Fallbacks: the unpatched build (above) and Zoom's stock v2.10 updater from zoom.co.jp.

## ORC caveat
The brain opens the pedal as a generic `usb engine` input and `_pass`es non-channel messages to the pisound
DIN, so the pedal's SysEx replies would go out the DIN (only Arturia SysEx is filtered). Probing cut it at
runtime with `aconnect -d 40:0 <brain in>`; restored after.


## Open
- Can `28` change the effect TYPE (ID) in slots 0-2, e.g. move TheVibe into slot 3, or drop in a hacked
  effect? If so, "what's playable live" = whatever you put in slots 1-3.
- `31 03 08` = tempo per thammer (clashes with slot 3 param 8); `60`, `16`, `01/04/05/0E` unknowns.
- Param names for effects not in thammer's map: parse each ZDL's param table (mungewell decode_effect.py).
