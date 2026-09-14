# Arduino5x5x5RGBCube

A 5×5×5 RGB LED cube (125 LEDs) driven by an Arduino Nano, plus the PC tools
to design and play colour patterns on it. Successor to
[Arduino4x4Cube](https://github.com/JohnRaynor/Arduino4x4Cube), which this
project inherits its editor, pattern-file and serial-protocol ideas from.

## Status

**PC side written, hardware not started.** The wiring plan is done and the
pattern editor, file format and serial module exist and are tested against a
simulated cube. No LEDs have been bought yet and the Arduino sketch is not
written. See [WORKLOG.md](WORKLOG.md) for progress.

## The design decision

The cube uses **4-leg addressable RGB LEDs** (APA106-F5 or PL9823-F5: a 5 mm
diffused LED with a WS2812-style driver inside) rather than plain common-anode
RGB LEDs with external drivers. That choice removes the driver ICs, the layer
switching transistors and the 80 wires from cube to board that a multiplexed
design needs, and lets every LED be lit continuously at full brightness. The
Nano is comfortably fast enough: the whole cube is a 375-byte frame buffer
sent over one data pin with FastLED.

Full wiring plan, with diagrams, parts list and build order:
[docs/wiring-plan.html](docs/wiring-plan.html) (open it in a browser).

In one paragraph: each LED has DIN, VDD, GND and DOUT legs. VDD stays
straight and is soldered to the LED below, so the 25 VDD legs per layer form
the cube's vertical columns exactly as the anode columns do in the 4×4×4. GND
bends to the back into a rail per layer; DIN and DOUT bend sideways so data
snakes through each layer in a serpentine. Five identical layers are built on
a jig and stacked, alternate layers rotated 180° so the layer-to-layer data
jumper is only 25 mm. The cube is powered directly from a 5 V 5 A supply with
a software current cap; the Nano runs from USB or the same supply via a
Schottky diode.

## Layout

| Path | Status | Purpose |
|---|---|---|
| `docs/wiring-plan.html` | done | Hardware plan: leg bends, layer serpentine, stack, controller schematic, parts, build order. |
| `rgb_cube_editor.py` | done | The pattern editor / simulator (below). |
| `cube_layout.py` | done | `led_index(x, y, z)`: the one place the LED chain order is defined. Must match `ledIndex()` in the sketch. |
| `patterns.py` | done | Read / write pattern files. |
| `send_serial.py` | done | `CUBE` serial protocol: live preview and SD-card write. Untested against hardware until the sketch exists. |
| `make_sample_patterns.py` | done | Generates the files in `Patterns/`; also a worked example of building patterns in code. |
| `Patterns/` | | Pattern files. `chain_test.bin` lights one LED at a time in chain order — the first thing to run on the real cube. |
| `sketch/` | to do | Arduino sketch: FastLED driver, SD-card playback, the serial protocol. |

## Requirements

```bash
pip install pygame pyserial
```

Arduino side (later): the **FastLED** and **SdFat** libraries.

## Running the editor

```bash
python rgb_cube_editor.py
```

The window shows the cube as five rows of 25 dots, one row per layer with the
top layer at the top; within a row the 25 dots are the 5×5 layer seen at an
angle, front row lowest. Unlit LEDs are drawn dark grey.

- **Left-click** a dot to paint it with the paint colour; **right-click** to
  switch it off.
- The **palette** (bottom left) sets the hue; the row under it sets the
  brightness (100 / 50 / 25 / 10 %). The preview box shows the resulting paint
  colour. **Custom…** opens the system colour picker.
- **Fill layer / Clear layer** act on the layer of the last dot you clicked
  (shown as *Layer n*). **Fill all / Clear all** act on the whole frame.

Everything else is the same as the 4×4×4 editor:

| Button | What it does |
|---|---|
| **New** | Start again with a single blank frame (asks first). |
| **Open File** / **Write File** | Load / save a `.bin` pattern file. |
| **<** / **>** | Step to the previous / next frame. |
| **copy Frame** | Insert a copy of the current frame in front of it. |
| **Play File** / **Stop** | Loop through all frames on screen using each frame's display time. |
| **▲** / **▼** | Slow down / speed up the current frame by about 20 % (5 – 65535 ms). |
| **Apply to all frames** | Copy the current frame's display time to every frame. |
| **Start** / **End** / **Clear** | Mark a block of frames; with no block set, block operations act on the current frame. |
| **Copy** / **Cut** / **Paste** / **Reverse** | Copy the block; cut (delete) it; insert the copy after the current frame; reverse its play order. |
| **Preview Cube** | Play the frames on the physical cube over serial. Needs the sketch. |
| **Save to SD** | Save the pattern locally, then write it under the same 8.3 name to the cube's SD card. Needs the sketch. |
| **Playlist** | Choose several `.bin` files, order them, and load them as one pattern. |

The serial port is asked for once and remembered in `.led_cube_settings.json`.

## Pattern file format

A plain sequence of frames with no header, **377 bytes per frame**. A
trailing partial frame is ignored on load.

| Bytes | Content |
|---|---|
| 0 – 374 | 125 × (R, G, B), one byte each, in LED chain order — index `led_index(x, y, z)` from `cube_layout.py`. |
| 375 – 376 | Display time in milliseconds, big-endian. |

Chain order: data snakes through each layer (row 0 left-to-right, row 1
right-to-left, …) and alternate layers are rotated 180°, so every consecutive
pair of LEDs in the chain is physically adjacent. `cube_layout.py` checks this.

To build patterns in code:

```python
from cube_layout import led_index
from patterns import new_frame, write_pattern

frame = new_frame(time_ms=100)
frame["colours"][led_index(x=2, y=0, z=4)] = [255, 80, 0]
write_pattern("Patterns/example.bin", [frame])
```

## Serial protocol

Identical to the 4×4×4 project's `CUBE` protocol with 377-byte frames; see
the docstring in `send_serial.py`. The sketch will be written to match.
