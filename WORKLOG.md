# Work Log

## 2026-09-14

- Project created as the successor to Arduino4x4Cube.
- Chose 4-leg addressable LEDs (APA106-F5 / PL9823-F5) over multiplexed common-anode RGB LEDs: no driver ICs, no layer transistors, three wires to the cube, full brightness, Nano is sufficient.
- Wiring plan written (`docs/wiring-plan.html`): leg bend plan, layer serpentine, stack elevation, controller schematic, parts list, build order and the FastLED (x, y, z) -> index mapping.
- Open items before buying: confirm the leg order of the chosen LED part on a breadboard; decide 5 mm vs 8 mm LEDs; decide 25 mm pitch (100 mm cube) vs larger.
- Nothing built or coded yet.

## 2026-09-14 (later)

- PC side written before any hardware: `cube_layout.py` (chain order, verified to be a bijection with every consecutive LED physically adjacent, and identical to the C `ledIndex()` in the wiring plan), `patterns.py` (377-byte frames, round-trip tested), `send_serial.py` (CUBE protocol, handshake tested against a fake port), `rgb_cube_editor.py` (adapted from the 4×4×4 editor: palette + brightness levels + custom colour, left-click paint / right-click off, fill/clear layer and all, block ops, playlist).
- `make_sample_patterns.py` generates `rainbow_layers`, `rising_plane` and `chain_test` into `Patterns/`.
- Editor exercised headlessly (paint, fill, block ops, no overlapping hit-boxes) and screenshotted running.
- Not done: the Arduino sketch; serial paths untested against hardware.

## 2026-09-14 (sketch)

- `sketch/rgb_cube/rgb_cube.ino` written: FastLED (APA106, D6), SdFat32 random playback from the card root, the CUBE protocol with 377-byte frames received straight into `leds[]`.
- Protocol changes versus the 4×4×4: 115200 baud; 64 zero bytes before every command (FastLED.show() blocks the UART for ~4 ms); `NEXT` acknowledgement per 64-byte block during SD writes. `send_serial.py` updated to match and tested against a Python model of the sketch's state machine.
- Compiled with the IDE's bundled arduino-cli for `arduino:avr:nano`: 18.8 KB flash, 1507 B RAM globals (541 B free). Got there from 1615 B by using two `File32` handles instead of four and dropping the file buffer. FastLED 3.10.5 installed into the Arduino libraries folder.
- Not run on hardware.

## 2026-09-16

- Decided patterns will mostly be generated in code rather than click-painted.
- `patterngen.py`: named regions as sets of chain indices (`plane`, `layer`, `column`, `line`, `shell`/`OUTER`/`MIDDLE`/`CENTRE`, `cube`, `square`, `ball`, faces, `EDGES`, `CORNERS`, `select`) and a `Scene` with `paint`, `clear`, `scale`, `hold`, `fade`, `fade_in`, `fade_out`, `morph`, `extend`. Self-checks in its `__main__`.
- `make_sample_patterns.py`: `GENERATORS` registry; `fade_all` (John's) rewritten on the Scene; new `shells` and `plane_sweep` examples.
- Editor: **Generate…** button lists the generators and loads frames directly, reloading `patterngen` and `make_sample_patterns` first so edits are picked up without restarting; generator exceptions are shown in a dialog. Tested headlessly (load, reload-on-edit, failure leaves frames intact) and the button checked in the real window.
- PSU chosen: a 5 V 10 A desktop brick (COOLM, Amazon B0G2RXZG5K); cap at ~5 A in the sketch and terminate the lead in a screw block rather than a barrel socket.
- Added one example generator per region type (nine in all) to `make_sample_patterns.py`; LED counts per frame spot-checked.

## 2026-09-17

- Editor tidy-up: buttons pale blue and 36 px high on a 50 px row pitch, laid out by a `button_row()` helper; read-outs (frame, time, block, paint colour) are dark boxes so they no longer look like buttons; the `>` button no longer hides under the frame counter (fixed-width read-outs). Play/Stop is one toggling button. The *Layer n* read-out is gone — the Fill layer / Clear layer buttons now carry the layer number themselves.

## 2026-10-03

- Breadboard: Nano + SD working. First LED destroyed by reverse polarity — the LEDs bought (Amazon B0FVM6PGT7, WS2812/SK6812 family) are **DIN · GND · VDD · DOUT**, i.e. the middle two pins swapped from the APA106 order revision 1 of the wiring plan assumed. Confirmed correct on the bench; 4 LEDs now running with `WS2812B` / `GRB`.
- Leg lengths measured: GND 16.5 mm, VDD 15 mm, DIN/DOUT 14 mm. Too short to span the 20.32 mm pitch, so the structure changes to continuous 0.9 mm tinned-copper pillars with the VDD legs soldered on, plus per-row GND rails.
- Wiring plan rewritten (revision 2): new pinout, pillar structure, 20.32 mm pitch, stripboard base with a detailed power-feed plan, layers no longer rotated (incompatible with vertical pillars — costs one routed data jumper per layer boundary, gains five identical layers).
- Decisions: VDD stays on the verticals (keeps the data return path local to each row); `MAX_MILLIAMPS` to be set to 3000 so the DC socket stays inside its rating; 100 x 160 mm Eurocard stripboard rather than 100 mm square.
- Sourced: Rapid 05-0310 (0.9 mm tinned copper wire), 47-2566 (1N5819), 20-0989 (5.5 x 2.5 mm chassis socket).
- Decoupling reconsidered: none inside the cube volume (solid 0.9 mm copper buses are a far better supply than the PCB strips the "100 nF per LED" rule is written for, and a missed data bit costs one frame, not damage). Two or three 100 nF on the base board instead; retrofit at the top-layer corners only if bright transitions sparkle.

## 2026-11-05

- Build under way, going well.
- Editor: **Open File** and **Generate…** now insert after the current frame and land on the last inserted frame, so repeated calls chain into one long pattern; a still-untouched blank starting frame is replaced instead, so opening into a fresh editor leaves no leading blank. **New** is the way back to an empty pattern. Playlist still replaces.
- `patterngen`: `Scene.crossfade(out_of, into, colour, steps)` and the general `Scene.fade_many([(region, colour), ...], steps)` move several regions at once; `handover` added to the generators as a worked example.
- Current cap temporarily set to 1000 mA for bench work on a 2 A PSU; the 3000 mA figure for the real 10 A brick is kept as a comment next to it. Recompiled clean (18698 B flash, 1451 B RAM).
- Bug found: Preview Cube aborted with an SD error whenever the card was absent or unreadable. The sketch announced a boot-time SD init failure as `ERR ...` immediately before `READY`, and `_wait_for()` treats any ERR line as fatal to the command in flight — so the connection handshake itself failed, on a condition the sketch intends to be harmless for previews. Sketch now emits `WARN ...`; `_wait_for()` returns the lines it passed over, `_connect()` keeps any WARNs in `send_serial.last_boot_warnings`, and the editor shows them once per session after a preview.
- `test_protocol.py` added: drives the real `send_serial` against a model of the sketch (same state machine, quiet-time rule, preview hold, no-card behaviour). Preview-then-resume passes with a working card, a card with no files, no card at all, Show-again, and a dialog left open past the 60 s hold — so the resume failure is not in the protocol logic. Needs the error text from the real hardware to go further.
- Found the cause of Preview Cube "falling through" into the Save to SD dialog: buttons polled the mouse every frame rather than handling click events, so after a long blocking action (a preview, or any modal dialog) the button sitting under the cursor fired the moment control returned. Buttons are now event-driven — `Button.draw()` only draws, `Button.press()` runs the action and then flushes the event queue. Reproduced the old behaviour in a headless test first.
- Serial port handling: `send_serial.available_ports()` lists what the OS can see with likely Arduino adapters first; the editor validates the saved port and re-prompts if it has gone. On this machine the Nano is COM9 and there are five decoy Bluetooth ports, so the old "COM3" default in the prompt was actively misleading.
- `NameError: send_serial` at run time: the editor half of commit 38f2a6f (the `import send_serial`, `report_boot_warnings()` and its call in `previewCube`) was committed, then disappeared from disk before the next commit — an external save of an older buffer. Restored and verified; `git show 38f2a6f:rgb_cube_editor.py` holds the original if it happens again.
- Resume reported an SD init failure, which only `setup()` prints — so the Nano is restarting between the preview finishing and the CUBER command. `_wait_for()` now recognises an unexpected READY and says the board restarted, instead of timing out vaguely. `previewCube()` returns after an error so the boot-warning dialog no longer appears on top of the real one. Added an optional serial log via the `CUBE_SERIAL_LOG` environment variable to capture the next occurrence.
- Key realisation: the sketch never drives the on-board LED, and on a Nano that LED is on D13 = SCK. So the flashing John sees is SD card SPI traffic, nothing else. LED flashing then stopping = the sketch hung inside SdFat, not a reset — and it happens on USB alone with the cube disconnected, so power is not involved. The SD card/module is the common factor in every symptom.
- SD SPI clock made tunable (`SD_SCK_SPEED`) and dropped from 8 MHz to 4 for breadboard wiring. Recompiled clean.
- Serial logging is now on by default to `cube_serial.log` beside the scripts (gitignored, fresh file past ~1 MB), rather than needing an environment variable — the earlier instructions were bash syntax and would not run in PowerShell anyway. `CUBE_SERIAL_LOG` still overrides the path, or "off" disables it.
- The log settled it: resume was never failing. `-> CUBER` / `<- RESUMED` 9 ms apart, after a clean 58-frame preview. The "error" was the boot-warning dialog I added, firing after a *successful* preview to report the unplugged SD card — a warning dressed as a failure. Moved to a status line in the editor window; no modal dialog for warnings. My SD-card diagnosis was wrong, and the unplug test disproved it.
- John reports the SD card was plugged in and working until recent edits. Checked the full sketch diff since the last known-good build: the only SD-related change is `SD_SCK_MHZ(8)` -> `SD_SCK_MHZ(4)`, made *after* the failure first appeared. At the time `sd.begin()` first failed (38f2a6f) the sketch still had the original 8 MHz setting and my only edits were MAX_MILLIAMPS and setBrightness, neither of which touches SPI. So the timeline does not support a software cause.
- Added `sketch/sd_check/` — a standalone SD diagnostic (no FastLED, no protocol): tries begin() at 1/4/8 MHz reporting SdFat error codes, then lists and fully reads every file. Compiles at 13260 B flash, 904 B RAM.
- **Root cause found.** The card was fine all along: random playback reads it happily. `sd.begin()` only failed on the reset that opening the serial port triggers. A DTR reset does not power-cycle the card, and random playback is almost always mid-read when it lands, so the card came back still part-way through a transaction and ignored the init sequence. On a power-up boot the card is fresh, which is why playback worked.
- Fix: `beginSd()` sends 160 idle clocks with CS high (the spec asks for 74) to end any transaction and return the card to its power-up state, then retries `sd.begin()` up to three times. 18904 B flash, 596 B RAM free.
- Asked whether forgetting to switch the cube supply on could damage the Nano or the USB port. It cannot: the 1N5819 has its anode on the cube rail and its cathode on the Nano 5V pin, so current flows supply -> Nano only, and the cube can never draw through USB. The only remaining path is D6 -> 330 ohm -> the first LED DIN clamp, about 10 mA, well inside the 40 mA pin limit. Added a section to the wiring plan including the bench check for diode orientation (brick off + USB in -> cube must stay completely dark).
- Pattern iteration was too slow (edit, save, click Generate). Added `cube_live.py`: `show()` puts a frame on screen or on the real cube immediately, from inside the code being written, and blocks until it is displayed — so stepping a debugger through a generator walks the cube frame by frame. Targets "window" (default, no hardware), "cube", or "both". `send_serial` gained `open_cube()` / `send_frame()` / `resume_random()` so the port can be held open, since reopening resets the Arduino and costs two seconds.

## 2026-11-24 — where things stand

Written at the end of a long session, so a fresh start has the context.

**Working on real hardware:** Nano, SD module and a handful of LEDs on a
breadboard. Previews over USB, random playback from the SD card, pattern
transfer to the card, and the editor all work. Cube construction is under way
and slow.

**Hardware as it sits**

- LEDs are WS2812-family, pin order `DIN · GND · VDD · DOUT`. Sketch uses
  `WS2812B` / `GRB`. Leg lengths: GND 16.5, VDD 15, DIN/DOUT 14 mm.
- Nano on COM9 (a CH340; the other five COM ports on this machine are
  Bluetooth decoys). SD chip select D3, LED data D6 through 330 Ω.
- Temporary 2 A bench supply, so `MAX_MILLIAMPS` is **1000**. Back to 3000
  with the 5 V 10 A brick (COOLM, 5.5 × 2.5 mm plug — the socket must be
  2.5 mm, not 2.1).
- SD SPI clock is 4 MHz (`SD_SCK_SPEED`). It was dropped from 8 while chasing
  a fault that turned out to be something else; 8 would probably be fine.

**Settled decisions, so they are not reopened**

- 20.32 mm pitch (8 holes of 0.1 inch stripboard), 100 × 160 mm Eurocard base.
- VDD on the vertical pillars, GND on per-row rails — keeps each row's data
  return local.
- All five layers identical, *not* rotated; alternate rows within a layer are
  turned 180°. One routed data jumper per layer boundary.
- No decoupling caps inside the cube volume; two or three on the base board.
- No 8×8×8 follow-on.

**Next up**

1. Carry on building layers. Test each one with `chain_test` before stacking.
2. Put `MAX_MILLIAMPS` back to 3000 when the real brick goes in.
3. Bench check still outstanding: brick off, USB in, preview — the cube must
   stay completely dark, which proves the Schottky is the right way round.

**Open, minor**

- `cube_live.show()` calls left in a generator will also fire when the editor's
  **Generate…** runs it, popping up a window. Harmless.
- The editor does not auto-rerun a generator when the file changes; offered,
  not built.
- `python make_sample_patterns.py <generator>` now runs just that generator and loops it in the cube_live window (add `--cube` for the real thing); with no argument it still writes every .bin as before. There was previously no way to run a single generator outside the editor, which is what made cube_live hard to use.
- cube_live window fixes found while testing: layer labels were re-rendered every frame, playback ignored frame times entirely (a pattern raced past), and closing the window did not stop the script. Playback now paces against actual draw cost - measured accurate to a few percent at 10, 25 and 50 ms frames.
