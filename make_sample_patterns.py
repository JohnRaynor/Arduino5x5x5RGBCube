"""Generate a few pattern files into Patterns/ so the editor has something to open.

Also a worked example of building patterns in code: fill a frame by (x, y, z)
through led_index(), append it, and write the list with write_pattern().
"""
import colorsys
from pathlib import Path

from cube_layout import SIZE, led_index
from patterns import new_frame, write_pattern

patterns_dir = Path(__file__).with_name("Patterns")


def hsv(h, s=1.0, v=1.0):
    return [int(channel * 255) for channel in colorsys.hsv_to_rgb(h % 1.0, s, v)]


def rainbow_layers(steps=30, time_ms=80):
    """Each layer a different hue, the whole cube cycling through the spectrum."""
    frames = []
    for step in range(steps):
        frame = new_frame(time_ms)
        for z in range(SIZE):
            colour = hsv(step / steps + z / SIZE, v=0.6)
            for y in range(SIZE):
                for x in range(SIZE):
                    frame["colours"][led_index(x, y, z)] = colour
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
                    frame["colours"][led_index(x, y, z)] = hsv(hue, v=0.7)
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


if __name__ == "__main__":
    patterns_dir.mkdir(exist_ok=True)
    for name, frames in [("rainbow_layers", rainbow_layers()), ("rising_plane", rising_plane()),
                         ("chain_test", chain_test())]:
        write_pattern(patterns_dir / f"{name}.bin", frames)
        print(f"{name}.bin: {len(frames)} frames")
