"""Diagnostic patterns for finding data faults along the LED chain.

Kept out of the editor's Generate list. To use them, run this file - it writes
the .bin files into testing/patterns/ - then New, Open File one of them in the
editor, and Preview:

    python testing/diagnostic_patterns.py

    stray_hunt_top_dark      layers 0-2 busy; layers 3-4 must stay dark
    stray_hunt_bottom_dark   layers 3-4 busy; layers 0-2 must stay dark

Anything lit in a layer that should be dark is data the chain garbled on its
way. Strays only above some point mean a fault partway along the chain; strays
in the dark layers of both tests mean something cube-wide, such as power.

In November 2026 these found marginal solder joints at the end of the third
layer and the start of the fourth - the handover from layer 2 to layer 3,
counting from 0, where LED 74 at (4,4,2) passes data up to LED 75 at (4,4,3).
Re-touching them cured random coloured flashing in the top two layers.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # the project's own modules

from cube_layout import XYZ                                      # noqa: E402
from patterns import new_frame, write_pattern                    # noqa: E402


def _busy_and_dark(busy_layers, steps, time_ms, seed):
    """Busy random colours on some layers, the rest held at exactly zero."""
    rng = random.Random(seed)
    frames = []
    for _ in range(steps):
        frame = new_frame(time_ms)
        for index, (x, y, z) in enumerate(XYZ):
            if z in busy_layers:
                frame["colours"][index] = [rng.randrange(256) for _ in range(3)]
        frames.append(frame)
    return frames


def stray_hunt_top_dark(steps=150, time_ms=80, seed=11):
    """Layers 0-2 busy, layers 3-4 must stay completely dark."""
    return _busy_and_dark({0, 1, 2}, steps, time_ms, seed)


def stray_hunt_bottom_dark(steps=150, time_ms=80, seed=12):
    """Layers 3-4 busy, layers 0-2 must stay completely dark."""
    return _busy_and_dark({3, 4}, steps, time_ms, seed)


GENERATORS = {
    "stray_hunt_top_dark": stray_hunt_top_dark,
    "stray_hunt_bottom_dark": stray_hunt_bottom_dark,
}

if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "patterns"
    out.mkdir(exist_ok=True)
    for name, generator in GENERATORS.items():
        frames = generator()
        write_pattern(out / f"{name}.bin", frames)
        print(f"{out / name}.bin: {len(frames)} frames")
