"""Pattern generators.

Each function returns a list of frames. Add it to GENERATORS at the bottom and
it appears in the editor's Generate... dialog (which reloads this file every
time, so there is no need to restart the editor) and is written to Patterns/
when this script is run directly.

Two ways to build frames, both shown below:
  - fill a frame by (x, y, z) through led_index() and append it (rainbow_layers,
    rising_plane, chain_test);
  - use patterngen's named regions and a Scene (fade_all, shells, plane_sweep).
"""
from pathlib import Path

from cube_layout import SIZE, led_index
from patterns import new_frame, write_pattern
from patterngen import (ALL, CENTRE, MIDDLE, OUTER, BLUE, GREEN, RED, WHITE,
                        Scene, hsv, plane)

patterns_dir = Path(__file__).with_name("Patterns")


def rainbow_layers(steps=30, time_ms=80):
    """Each layer a different hue, the whole cube cycling through the spectrum."""
    frames = []
    for step in range(steps):
        frame = new_frame(time_ms)
        for z in range(SIZE):
            colour = hsv(step / steps + z / SIZE, v=0.6)
            for y in range(SIZE):
                for x in range(SIZE):
                    frame["colours"][led_index(x, y, z)] = list(colour)
        frames.append(frame)
    return frames


def rising_plane(time_ms=120):
    """A single coloured layer rising then falling, changing hue each pass."""
    frames = []
    for pass_no, hue in enumerate((0.0, 0.33, 0.66)):
        for z in list(range(SIZE)) + list(range(SIZE - 2, 0, -1)):
            frame = new_frame(time_ms)
            for y in range(SIZE):
                for x in range(SIZE):
                    frame["colours"][led_index(x, y, z)] = list(hsv(hue, v=0.7))
            frames.append(frame)
    return frames


def chain_test(time_ms=60):
    """Lights LEDs one at a time in chain order: the first thing to run on the real cube."""
    frames = []
    for index in range(SIZE ** 3):
        frame = new_frame(time_ms)
        frame["colours"][index] = [255, 255, 255]
        frames.append(frame)
    return frames


def fade_all(time_ms=60):
    """Fade the whole cube from red to black."""
    scene = Scene(time_ms)
    scene.paint(ALL, RED)
    scene.fade_out(ALL, steps=30)
    return scene.frames


def shells(time_ms=40):
    """Centre, middle and outer shells fade in one after another, then all fade out."""
    scene = Scene(time_ms)
    scene.fade_in(CENTRE, WHITE, steps=15)
    scene.fade_in(MIDDLE, BLUE, steps=15)
    scene.fade_in(OUTER, RED, steps=15)
    scene.hold(500)
    scene.fade(MIDDLE, GREEN, steps=15)   # recolour one shell while the rest stay lit
    scene.hold(500)
    scene.fade_out(ALL, steps=25)
    return scene.frames


def plane_sweep(time_ms=50):
    """A plane sweeps through the cube along each axis in turn, leaving a fading trail."""
    scene = Scene(time_ms)
    for axis, colour in (("x", RED), ("y", GREEN), ("z", BLUE)):
        for n in range(SIZE):
            scene.scale(ALL, 0.5)            # trail: everything already lit dims by half
            scene.paint(plane(axis, n), colour)
            scene.hold()
        scene.fade_out(ALL, steps=6)
    return scene.frames


GENERATORS = {
    "rainbow_layers": rainbow_layers,
    "rising_plane": rising_plane,
    "chain_test": chain_test,
    "fade_all": fade_all,
    "shells": shells,
    "plane_sweep": plane_sweep,
}

if __name__ == "__main__":
    patterns_dir.mkdir(exist_ok=True)
    for name, generator in GENERATORS.items():
        frames = generator()
        write_pattern(patterns_dir / f"{name}.bin", frames)
        print(f"{name}.bin: {len(frames)} frames")
