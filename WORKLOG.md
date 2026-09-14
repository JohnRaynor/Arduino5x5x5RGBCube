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
