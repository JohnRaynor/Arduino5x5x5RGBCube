# Arduino5x5x5RGBCube

A 5×5×5 RGB LED cube (125 LEDs) driven by an Arduino Nano, plus the PC tools
to design and play colour patterns on it. Successor to
[Arduino4x4Cube](https://github.com/JohnRaynor/Arduino4x4Cube), which this
project inherits its editor, pattern-file and serial-protocol ideas from.

## Status

**Being built.** The PC tools and the Arduino sketch are written and working
against real hardware: a Nano, an SD module and a handful of LEDs on a
breadboard play patterns, take live previews over USB, and read patterns from
the card. Cube construction is under way and slow. See
[WORKLOG.md](WORKLOG.md) for the running account.

Running on a temporary 2 A bench supply, so `MAX_MILLIAMPS` in the sketch is
set to **1000**. Put it back to 3000 when the 5 V 10 A brick goes in — both
figures are in the comment above the define.

## The LEDs

> **Pin order is `DIN · GND · VDD · DOUT`.** Not the APA106 order this project
> was originally designed around, which has the middle two swapped. Getting it
> wrong destroys the LED instantly — that is how the first one went. Before
> powering anything newly soldered, put **100 Ω in series with the 5 V feed**:
> right way round the chip idles at about 1 mA, wrong way round it draws about
> 40 mA and stays dark, and nothing can be damaged either way.

They are WS2812-family 5 mm diffused parts, so the sketch uses `WS2812B` and
`GRB`. Legs measured: GND 16.5 mm, VDD 15 mm, DIN and DOUT 14 mm each.

## The design decision

The cube uses **4-leg addressable RGB LEDs** — a 5 mm diffused LED with a
WS2812-style driver inside — rather than plain common-anode RGB LEDs with
external drivers. That removes the driver ICs, the layer switching transistors
and the 80 wires from cube to board that a multiplexed design needs, and lets
every LED be lit continuously at full brightness. The Nano is comfortably fast
enough: the whole cube is a 375-byte frame buffer sent over one data pin with
FastLED.

Full wiring plan, with diagrams, parts list and build order:
[docs/wiring-plan.html](docs/wiring-plan.html) (open it in a browser).

In one paragraph: the legs are too short to span the 20.32 mm layer pitch, so
the cube is carried by **25 vertical pillars of 0.9 mm tinned copper wire**,
one per column, with each LED's VDD leg soldered to the pillar that passes it.
GND bends to the back into a rail per row; DIN and DOUT bend sideways so data
snakes along each row, with **alternate rows turned 180°** so each DOUT reaches
the next DIN. The supply legs leave at right angles to the pin row, so turning
a row barely moves them. All five layers are identical — the layers are *not*
rotated, which would stop the pillars lining up — at the cost of one routed
data jumper per layer boundary. Pitch is 20.32 mm, eight holes of 0.1 inch
stripboard, and the stack stands on a 100 × 160 mm Eurocard. The cube is
powered directly from a 5 V supply with a software current cap; the Nano runs
from USB or the same supply through a Schottky diode.

## Layout

| Path | Status | Purpose |
|---|---|---|
| `docs/wiring-plan.html` | done | Hardware plan: leg bends, layer serpentine, stack, controller schematic, parts, build order. |
| `rgb_cube_editor.py` | done | The pattern editor / simulator (below). |
| `cube_layout.py` | done | `led_index(x, y, z)`: the one place the LED chain order is defined. Must match `ledIndex()` in the sketch. |
| `patterns.py` | done | Read / write pattern files. |
| `send_serial.py` | done | `CUBE` serial protocol: live preview and SD-card write. Tested against a model of the sketch, not yet against hardware. |
| `cube_live.py` | done | Watch a pattern as you write it: `show()` puts a frame on screen or on the real cube straight away. |
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
| **Open File** / **Write File** | Load / save a `.bin` pattern file. Opening **inserts** the file after the current frame and leaves you on its last frame, so files chain together; use **New** first to start from nothing. |
| **<** / **>** | Step to the previous / next frame. |
| **Copy frame** | Insert a copy of the current frame in front of it. |
| **Play** / **Stop** | One button: loop through all frames on screen using each frame's display time; click again to stop. |
| **▲** / **▼** | Slow down / speed up the current frame by about 20 % (5 – 65535 ms). |
| **Apply to all frames** | Copy the current frame's display time to every frame. |
| **Start** / **End** / **Clear** | Mark a block of frames; with no block set, block operations act on the current frame. |
| **Copy** / **Cut** / **Paste** / **Reverse** | Copy the block; cut (delete) it; insert the copy after the current frame; reverse its play order. |
| **Preview Cube** | Play the frames on the physical cube over serial. Needs the sketch. |
| **Save to SD** | Save the pattern locally, then write it under the same 8.3 name to the cube's SD card. Needs the sketch. |
| **Playlist** | Choose several `.bin` files, order them, and load them as one pattern. Unlike Open File, this still replaces what is loaded. |
| **Generate…** | Pick a generator from `make_sample_patterns.py` and insert its frames directly, no file needed — same insert-and-chain behaviour as Open File. The generator code is reloaded every time, so edit, save, click Generate. |

### The serial log

Every command sent to the cube and every line it sends back is recorded in
**`cube_serial.log`**, beside these scripts. Nothing to switch on: start the
editor however you normally do, reproduce a fault, then open the file. It is
the only way to see what happened when a fault is intermittent.

```
13:03:47.444  <- READY
13:03:47.445  -> CUBEP +377 bytes
13:03:47.447  <- FRAME
13:03:47.648  -> CUBER
13:03:47.649  <- RESUMED
```

A fresh file is started once it passes about 1 MB. To move it elsewhere, or to
turn it off, set the `CUBE_SERIAL_LOG` environment variable — in PowerShell:

```powershell
$env:CUBE_SERIAL_LOG = "off"
```

The serial port is asked for once and remembered in `.led_cube_settings.json`.
The prompt lists the ports the OS can actually see, likely Arduino adapters
first — on a machine with Bluetooth, most of the COM numbers are decoys. If the
saved port has gone (Windows renumbers USB serial adapters across reboots and
unplugs) the editor says so and asks again rather than failing later.

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
(set algebra), `morph_between` and `handover` (`crossfade`).

Axes: x left–right, y front–back, z bottom–top, each 0–4. Colours are `(r, g, b)`
tuples — `RED`, `BLUE`, … are predefined, `hsv(h)` gives a hue, `dim(colour, 0.3)`
scales one.

Fades come in four kinds. `fade`, `fade_in` and `fade_out` move one region at a
time; the other two move several at once, over the same frames:

```python
scene.crossfade(OUTER, CENTRE, BLUE, steps=20)      # OUTER fades out as CENTRE fades in
scene.fade_many([(layer(0), RED), (layer(4), GREEN), (MIDDLE, BLACK)], steps=20)
```

`crossfade(out_of, into, colour, steps)` takes `out_of` down to black while
`into` comes up to `colour` — pass `from_black=False` to move the incoming
region from its current colour rather than starting it dark. `fade_many` is the
general form: give it `(region, colour)` pairs and every LED named moves from
whatever it is now to its own target together. Where regions overlap, the pair
listed last wins.

`Scene.scale(region, 0.5)` halves the brightness of what is already
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

## Watching a pattern as you write it

Editing a generator, saving, then clicking **Generate…** is a slow way to see
the effect of a one-line change. There are two quicker routes.

### Watch one generator run

```powershell
python make_sample_patterns.py test_fade_many
```

That runs just that generator and plays it in a window, looping, at the
pattern's own speed. Close the window to stop. Edit the function, save, run it
again — that is the whole loop. Add `--cube` to watch it on the real cube
instead of on screen. With no argument the file still regenerates every `.bin`
into `Patterns/` as before.

### Watch it build, line by line

Call `cube_live.show()` from inside the generator and each frame appears as it
is made. Taking `test_fade_many` as it stands:

```python
import cube_live                         # at the top of the file

def test_fade_many(time_ms=100):
    scene = Scene(time_ms)
    for z in range(30):
        column1 = (random.randint(0, SIZE - 1), random.randint(0, SIZE - 1))
        column2 = (random.randint(0, SIZE - 1), random.randint(0, SIZE - 1))
        column3 = (random.randint(0, SIZE - 1), random.randint(0, SIZE - 1))
        scene.fade_many(((column(*column1), RANDOMCOLOUR()),
                         (column(*column2), RANDOMCOLOUR()),
                         (column(*column3), RANDOMCOLOUR())), steps=30)
        cube_live.show(scene)            # <- the cube as it stands after this pass
    return scene.frames
```

Run it the same way (`python make_sample_patterns.py test_fade_many`) and you
see the state after each of the 30 passes, then the finished pattern plays.

`show()` blocks until the frame is actually displayed, so **putting a
breakpoint on that line and stepping walks the cube through the pattern one
frame at a time** — which is the quickest way to find where a pattern stops
doing what you meant. `scene` works directly because `show()` takes a `Scene`
and uses its working frame; `scene.frames[-1]` or a list of 125 colours work
too.

To watch on the real cube, once at the top of the file:

```python
cube_live.target("cube")     # or "both", to see it in each place at once
```

### The rest of cube_live

| Call | What it does |
|---|---|
| `show(x)` | Display one frame. `x` may be a frame, a `Scene`, or a list of 125 colours. A list of frames plays in order. |
| `play(frames)` | Play a whole list, each for its own display time. |
| `off()` | Blank it. |
| `target(where)` | `"window"` (default), `"cube"` or `"both"`. |
| `close()` | Hand the cube back to its SD playback and release the port. Automatic when the script ends. |

Two things to know when the target is the cube. The port is opened once and
held, because reopening it resets the Arduino and costs two seconds — so keep
one script running across edits, and note the editor cannot use the port at
the same time. And the sketch holds the last frame it was sent for 60 seconds
before falling back to random SD playback, so a single `show()` does not stay
up indefinitely.

If you leave `cube_live.show()` calls in a generator that the editor's
**Generate…** dialog also runs, they fire there too and pop up a window.
Harmless, but worth knowing why it appeared.

## Checking the SD card

`sketch/sd_check/` is a standalone test: no FastLED, no cube, no protocol, so
whatever it reports is about the card and its wiring and nothing else. Flash it,
open the Serial Monitor at 115200 and read the report. It tries `begin()` at 1,
4 and 8 MHz in turn — if the slow one works and the fast one does not, the
wiring is too long or too noisy rather than the card being faulty — then lists
the root directory and reads every file right through.

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
