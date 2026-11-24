# Arduino5x5x5RGBCube

A 5×5×5 RGB LED cube (125 WS2812-family LEDs) on an Arduino Nano, plus Python
tools to design and play patterns. Successor to Arduino4x4Cube, from which the
editor, pattern-file format and serial protocol are inherited.

John is building the cube by hand; construction is slow and ongoing. The
software works against real hardware.

## Facts that cost money if you get them wrong

- **LED pin order is `DIN · GND · VDD · DOUT`.** The middle two are swapped
  versus the APA106 the first revision of the wiring plan assumed. Wrong
  polarity destroys the LED in about a second. Any document or comment saying
  `DIN · VDD · GND · DOUT` is stale — fix it.
- **Before powering anything newly soldered, 100 Ω in series with the 5 V
  feed.** Right way round the chip idles at ~1 mA; wrong way round ~40 mA and
  dark. Nothing can be destroyed either way. A standing habit, not a one-off.
- **The 330 Ω on D6 is not optional.** It is the sacrificial part that stops a
  wiring mistake taking the Nano's pin with it.
- `MAX_MILLIAMPS` must stay below what the supply can deliver. Currently
  **1000** for a temporary 2 A bench supply; 3000 for the real 5 V 10 A brick.

## Layout

| Path | What it is |
|---|---|
| `rgb_cube_editor.py` | The pattern editor and simulator (pygame, with tkinter dialogs). |
| `cube_layout.py` | `led_index(x, y, z)` — the single definition of chain order. Must match `ledIndex()` in the sketch. |
| `patterns.py` | The 377-byte frame format. |
| `patterngen.py` | Named regions (`layer`, `column`, `OUTER`…) and `Scene`, for building patterns in code. |
| `make_sample_patterns.py` | The generators. `GENERATORS` at the bottom drives the editor's **Generate…** dialog. John edits this file constantly. |
| `cube_live.py` | `show()` a frame straight to a window or the real cube while writing a pattern. |
| `Test_sample_pattern.py` | F5 target in VS Code: set `GENERATOR` and watch one generator. |
| `send_serial.py` | The `CUBE` serial protocol. |
| `test_protocol.py` | Drives `send_serial` against a model of the sketch. No hardware needed. |
| `sketch/rgb_cube/` | The Nano sketch: FastLED, SD playback, the serial protocol. |
| `sketch/sd_check/` | Standalone SD diagnostic. |
| `docs/wiring-plan.html` | The build plan. Also published as an artifact John reads at the bench. |
| `WORKLOG.md` | Dated running account, with a handover section at the end. Add an entry for anything worth remembering. |

## Commands

```bash
python test_protocol.py            # protocol against a model of the sketch
python patterngen.py               # region and Scene self-checks
python make_sample_patterns.py     # regenerate every pattern into Patterns/
python cube_live.py                # walk the chain in a window
```

Compiling the sketch — `arduino-cli` is not on PATH, it ships inside the IDE:

```powershell
$cli = Get-ChildItem "C:\Program Files\Arduino IDE" -Recurse -Filter arduino-cli.exe | Select-Object -First 1 -ExpandProperty FullName
& "$cli" compile --fqbn arduino:avr:nano "sketch\rgb_cube"
```

Sketch budget is tight: ~61 % flash, ~70 % RAM, under 600 bytes free. Check
RAM after any change that adds state.

## Gotchas already paid for

- **Opening the serial port resets the Nano** (DTR). The handshake depends on
  it — `_connect()` waits for the `READY` that only `setup()` prints. It also
  means a reset can land mid-SD-read, leaving the card unable to
  re-initialise; `beginSd()` clocks it with CS high to recover. Don't
  "simplify" that away.
- **An unexpected `READY` mid-session means the board restarted.** `_wait_for`
  says so explicitly.
- `WARN` lines are not failures; only `ERR` aborts a command. Warnings go to
  the editor's status line, never a dialog.
- **`cube_serial.log`** beside the scripts records every command and reply.
  Read it before theorising about a serial fault.
- The editor's buttons are **event-driven**. They must never poll the mouse: a
  blocking action (a preview, any modal dialog) would then fire whatever
  button sat under the cursor when it returned.

## Working style here

- Prefer Python patch scripts over the Edit tool for multi-line changes, but
  **write the patch script to a file** — heredocs through this shell eat
  backslashes and have corrupted string literals more than once.
- Verify before claiming: the editor runs headlessly with
  `SDL_VIDEODRIVER=dummy`, and the sketch compiles without hardware.
- Keep `WORKLOG.md` current, and commit with the attribution line the session
  reminder gives.
- John reports bench symptoms precisely, and they have repeatedly been right
  where my reasoning was wrong. Ask for the observation, or the log, before
  reading more code.
- No 8×8×8 follow-on. He has ruled it out; don't propose it.
