# Arduino5x5x5RGBCube

A 5×5×5 RGB LED cube (125 LEDs) driven by an Arduino Nano, plus the PC tools
to design and play colour patterns on it. Successor to
[Arduino4x4Cube](https://github.com/JohnRaynor/Arduino4x4Cube), which this
project inherits its editor, pattern-file and serial-protocol ideas from.

## Status

**Design stage.** The wiring plan is done; no hardware has been built and no
code written yet. See [WORKLOG.md](WORKLOG.md) for progress.

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

## Planned layout

| Path | Purpose |
|---|---|
| `docs/wiring-plan.html` | Hardware plan: leg bends, layer serpentine, stack, controller schematic, parts, build order. |
| `sketch/` | Arduino sketch: FastLED driver, SD-card playback, `CUBE` serial protocol from the 4×4×4 project extended to RGB frames. |
| `Patterns/` | RGB pattern files. |
| (PC editor) | RGB version of the 4×4×4 editor: colour picker per LED, same block/playlist tools. |

## Pattern file format (proposed)

Same idea as the 4×4×4 format, scaled up: a plain sequence of frames with no
header, **377 bytes per frame**.

| Bytes | Content |
|---|---|
| 0 – 374 | 125 × (R, G, B), one byte each, in chain order (see `ledIndex()` in the wiring plan). |
| 375 – 376 | Display time in milliseconds, big-endian. |

## Requirements

- Arduino IDE with the **FastLED** and **SdFat** libraries.
- Python 3 with `pygame` and `pyserial` for the editor (when written).
