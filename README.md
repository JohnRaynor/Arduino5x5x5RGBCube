# Arduino5x5x5RGBCube

A 5×5×5 RGB LED cube (125 LEDs) driven by an Arduino Nano, plus the PC tools
to design and play colour patterns on it. Successor to
[Arduino4x4Cube](https://github.com/JohnRaynor/Arduino4x4Cube), which this
project inherits its editor, pattern-file and serial-protocol ideas from.

## Status

**Software written, hardware not started.** The wiring plan, the PC editor
and the Arduino sketch all exist; the sketch compiles for the Nano and the PC
side is tested against a model of it. No LEDs have been bought yet, so nothing
has run on real hardware. See [WORKLOG.md](WORKLOG.md) for progress.

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
| `send_serial.py` | done | `CUBE` serial protocol: live preview and SD-card write. Tested against a model of the sketch, not yet against hardware. |
| `patterngen.py` | done | Building patterns in code: named regions (planes, columns, shells, faces…) and a `Scene` that paints and fades them. |
| `make_sample_patterns.py` | done | The pattern generators. Each appears in the editor's **Generate…** dialog and is written to `Patterns/` when run. |
| `Patterns/` | | Pattern files. `chain_test.bin` lights one LED at a time in chain order — the first thing to run on the real cube. |
| `sketch/rgb_cube/` | compiles | Arduino Nano sketch: FastLED driver, random SD-card playback, the serial protocol. |

## Requirements

```bash
pip install pygame pyserial
```

Arduino side: the **FastLED** and **SdFat** libraries (Library Manager), board
*Arduino Nano*, processor *ATmega328P* (or *Old Bootloader* for clones).

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
- **Fill layer n / Clear layer n** act on the layer of the last dot you clicked
  (the button labels show which). **Fill all / Clear all** act on the whole frame.

Everything else is the same as the 4×4×4 editor:

| Button | What it does |
|---|---|
| **New** | Start again with a single blank frame (asks first). |
| **Open File** / **Write File** | Load / save a `.bin` pattern file. |
| **<** / **>** | Step to the previous / next frame. |
| **Copy frame** | Insert a copy of the current frame in front of it. |
| **Play** / **Stop** | One button: loop through all frames on screen using each frame's display time; click again to stop. |
| **▲** / **▼** | Slow down / speed up the current frame by about 20 % (5 – 65535 ms). |
| **Apply to all frames** | Copy the current frame's display time to every frame. |
| **Start** / **End** / **Clear** | Mark a block of frames; with no block set, block operations act on the current frame. |
| **Copy** / **Cut** / **Paste** / **Reverse** | Copy the block; cut (delete) it; insert the copy after the current frame; reverse its play order. |
| **Preview Cube** | Play the frames on the physical cube over serial. Needs the sketch. |
| **Save to SD** | Save the pattern locally, then write it under the same 8.3 name to the cube's SD card. Needs the sketch. |
| **Playlist** | Choose several `.bin` files, order them, and load them as one pattern. |
| **Generate…** | Pick a generator from `make_sample_patterns.py` and load its frames directly, no file needed. The generator code is reloaded every time, so edit, save, click Generate. |

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

## Building patterns in code

Painting 125 LEDs a frame at a time by hand is slow; most patterns are better
generated. Write a function in `make_sample_patterns.py` that returns a list of
frames, add it to `GENERATORS`, and it appears in the editor's **Generate…**
dialog. `patterngen.py` provides the building blocks:

```python
from patterngen import *

def my_pattern():
    scene = Scene(time_ms=50)                 # default display time per frame
    scene.paint(OUTER, RED)                   # change the working frame...
    scene.hold(500)                           # ...and capture it, shown for 500 ms
    scene.fade_in(MIDDLE, BLUE, steps=20)     # 20 frames, MIDDLE from black to blue
    scene.fade(CENTRE, WHITE, steps=10)       # from whatever it is now to white
    scene.paint(plane("x", 0) | column(4, 4), GREEN)
    scene.hold()
    scene.fade_out(ALL, steps=30)
    return scene.frames
```

Regions are sets of chain indices, so they combine with `|`, `&` and `-`:

| Region | LEDs |
|---|---|
| `ALL` | everything |
| `plane("x" / "y" / "z", n)` | the 25 LEDs with that coordinate; `layer(z)` = `plane("z", z)` |
| `column(x, y)` | the 5 LEDs stacked at (x, y) |
| `line("x", y=2, z=4)` | 5 LEDs along one axis, the other two coordinates given |
| `OUTER`, `MIDDLE`, `CENTRE` | the 98-LED surface, the 26-LED shell inside it, the centre LED (`shell(2/1/0)`) |
| `cube(n)` | solid cube of side 2n+1 around the centre |
| `square(z, n)` | on layer z, the square ring n out from the centre |
| `ball(r)` | LEDs within r of the centre |
| `face("top")` etc., `EDGES`, `CORNERS` | the six faces, the 12 edges, the 8 corners |
| `select(lambda x, y, z: x == y)` | anything else |

`make_sample_patterns.py` has a worked example for each: `column_rain`,
`top_face_lines`, `growing_cube`, `expanding_squares`, `breathing_ball`,
`wireframe` (edges, corners, faces), `diagonal_wave` (`select`), `three_planes`
(set algebra) and `morph_between`.

Axes: x left–right, y front–back, z bottom–top, each 0–4. Colours are `(r, g, b)`
tuples — `RED`, `BLUE`, … are predefined, `hsv(h)` gives a hue, `dim(colour, 0.3)`
scales one. `Scene.scale(region, 0.5)` halves the brightness of what is already
lit (good for trails), `Scene.morph(frame, steps)` cross-fades the whole cube
to another frame, and `Scene.extend(frames)` appends frames built the low-level
way:

```python
from cube_layout import led_index
from patterns import new_frame, write_pattern

frame = new_frame(time_ms=100)
frame["colours"][led_index(x=2, y=0, z=4)] = [255, 80, 0]
write_pattern("Patterns/example.bin", [frame])
```

## The Arduino sketch

`sketch/rgb_cube/rgb_cube.ino`. Open it in the Arduino IDE and upload. At the
top of the file:

| Define | Default | Change when |
|---|---|---|
| `LED_TYPE` | `APA106` | you bought PL9823s: set `PL9823`. |
| `COLOR_ORDER` | `RGB` | red and green (or blue) come out swapped: try `GRB`. |
| `DATA_PIN` | 6 | you wire the data line elsewhere. |
| `SD_CS_PIN` | 3 | your SD module's chip select is on another pin. |
| `MAX_MILLIAMPS` | 4000 | your supply is not 5 A. FastLED dims the whole cube so the total never exceeds this. |
| `PREVIEW_HOLD_MS` | 60000 | you want the cube to hold the last previewed frame for longer or shorter before going back to random playback. |

Pins: LED data on D6 through 330 Ω, SD card on hardware SPI (D11/D12/D13)
with chip select D3.

With no serial traffic the sketch plays files from the SD card root in random
order, one after another. It keeps working without an SD card (it reports
`ERR SD initialisation failed` once, then still answers previews).

`ledIndex()` in the sketch is the same function as `led_index()` in
`cube_layout.py`; if you change one, change the other.

RAM: the Nano has 2 KB; the sketch uses about 1.5 KB for globals (375 for the
LED buffer, 512 for SdFat's sector cache). That is why it uses only two SD
file handles and writes incoming file bytes straight into SdFat's cache.

## Serial protocol

The 4×4×4 project's `CUBE` protocol with 377-byte frames, at **115200 baud**,
plus two additions that the Nano's tiny serial buffer and FastLED make
necessary:

| Direction | Bytes | Meaning |
|---|---|---|
| PC → Arduino | 64 zero bytes | Before every command. `FastLED.show()` blocks the UART for ~4 ms, so bytes arriving then are lost; any received byte stops refreshes for 50 ms, and the zeros absorb the loss. |
| Arduino → PC | `READY` | Sent after reset, and again after a `W` header has been accepted. |
| PC → Arduino | `CUBE` `P` + 377-byte frame | Preview: show this frame for its display time. |
| Arduino → PC | `FRAME` | The frame has been displayed for its time; the cube holds it and random playback stays paused until `R` or 60 s. |
| PC → Arduino | `CUBE` `R` | Resume random SD playback. |
| Arduino → PC | `RESUMED` | |
| PC → Arduino | `CUBE` `W` + name length (1 byte) + name + size (4 bytes, little-endian) | Start an SD write. Size must be a multiple of 377. |
| PC → Arduino | 64-byte block | File data, one block at a time. |
| Arduino → PC | `NEXT` | Block written; send the next. Keeps at most one block in flight, because the Nano's receive buffer is 64 bytes and an SD sector write can stall for tens of ms. |
| Arduino → PC | `DONE` | Last block written, file closed. |
| Arduino → PC | `ERR …` | `unknown command`, `bad filename`, `bad size`, `no SD card`, `SD open failed`, `SD write failed`, `SD initialisation failed`. |

## First power-up checklist

1. Three LEDs on a breadboard, data from D6 via 330 Ω, upload the sketch.
2. *Preview Cube* with `Patterns/chain_test.bin`: LEDs 0, 1, 2 should light in
   turn, white. Wrong colour → change `COLOR_ORDER`. Nothing → check the leg
   order against the datasheet, and that DIN is the leg you think it is.
3. Build the cube; run `chain_test.bin` again: every LED lights once, in the
   snake order shown in the wiring plan. A gap means a bad joint at that LED;
   everything dark after some point means a break in the data chain there.
