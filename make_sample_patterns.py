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
import random
from pathlib import Path

from cube_layout import SIZE, led_index
from patterns import new_frame, write_pattern
from patterngen import (ALL, CENTRE, CORNERS, EDGES, FACES, MIDDLE, OUTER,
                        BLUE, CYAN, GREEN, MAGENTA, ORANGE, RED, WHITE, YELLOW,
                        Scene, ball, column, cube, dim, hsv, line, plane, select, square)

patterns_dir = Path(__file__).with_name("Patterns")

def random_rain(time_ms=50):
    """A simple test pattern for the cube's first run."""
    scene = Scene(time_ms)
    for splashes in range(20):
        x = random.randint(0, SIZE - 1)
        y = random.randint(0, SIZE - 1)
        scene.clear()
        scene.hold(100)
        for z in range(SIZE-1,-0,-1):
            scene.paint(column(x, y) & plane("z", z), (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255)))
            #scene.paint(select(lambda px, py, pz: px == x and py == y and pz == z), (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255)))
            #above line retained to remind me how to use select() to pick a single LED, but the column() method is much simpler and more efficient.
            scene.hold(random.randint(30, 500) )
            scene.paint(column(x, y) & plane("z", z), (0,0,0))
        scene.fade_in(plane("z", 0), (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255)), steps=7)
        scene.fade(plane("z", 0), (0, 0, 0), steps=20,time_ms=10)
   return scene.frames


def diagonal_wave(time_ms=70):
    """select(): diagonal planes (x + z = k) sweep through the cube, with a trail."""
    scene = Scene(time_ms)
    for k in range(2 * SIZE - 1):
        scene.scale(ALL, 0.5)
        scene.paint(select(lambda x, y, z, k=k: x + z == k), hsv(k / (2 * SIZE)))
        scene.hold()
    for k in range(3 * SIZE - 2):                                # then the true 3-D diagonal x + y + z = k
        scene.scale(ALL, 0.5)
        scene.paint(select(lambda x, y, z, k=k: x + y + z == k), WHITE)
        scene.hold()
    scene.fade_out(ALL, steps=10)
    return scene.frames


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


# ---- one example per region type ----

def column_rain(drops=20, time_ms=40, seed=1):
    """column(x, y): random columns light up in random hues and fade away."""
    rng = random.Random(seed)
    scene = Scene(time_ms)
    for _ in range(drops):
        scene.scale(ALL, 0.6)                                   # older drops dim
        scene.paint(column(rng.randrange(SIZE), rng.randrange(SIZE)), hsv(rng.random()))
        scene.hold(120)
    scene.fade_out(ALL, steps=15)
    return scene.frames


def top_face_lines(time_ms=80):
    """line(axis, ...): a row scans across the top face, then a column of rows scans the other way."""
    scene = Scene(time_ms)
    top = SIZE - 1
    for y in range(SIZE):                                       # lines along x, stepping back in y
        scene.clear()
        scene.paint(line("x", y=y, z=top), YELLOW)
        scene.hold()
    for x in range(SIZE):                                       # lines along y, stepping across in x
        scene.clear()
        scene.paint(line("y", x=x, z=top), CYAN)
        scene.hold()
    for z in range(SIZE):                                       # vertical line down the front-left edge
        scene.clear()
        scene.paint(line("z", x=0, y=0), dim(WHITE, 0.4))
        scene.paint(select(lambda px, py, pz: px == 0 and py == 0 and pz == top - z), WHITE)
        scene.hold()
    scene.clear()
    return scene.frames


def growing_cube(time_ms=150):
    """cube(n): a solid cube grows from the centre to fill everything, then shrinks."""
    scene = Scene(time_ms)
    for n in (0, 1, 2, 1, 0):
        scene.clear()
        scene.paint(cube(n), hsv(n / 3))
        scene.hold()
    scene.fade_out(ALL, steps=10)
    return scene.frames


def expanding_squares(time_ms=90):
    """square(z, n): rings spread outwards on each layer, each layer one step behind the one below."""
    scene = Scene(time_ms)
    for step in range(SIZE + 3 + 2):                             # enough steps for the top layer to finish
        scene.scale(ALL, 0.4)
        for z in range(SIZE):
            n = step - z                                         # this layer's ring radius
            if 0 <= n <= 2:
                scene.paint(square(z, n), hsv(z / SIZE))
        scene.hold()
    scene.fade_out(ALL, steps=10)
    return scene.frames


def breathing_ball(time_ms=70):
    """ball(r): a sphere swells and shrinks; inner and outer parts in different colours."""
    scene = Scene(time_ms)
    radii = [0.5, 1.0, 1.5, 1.8, 2.3, 2.5, 3.0, 3.5]
    for r in radii + radii[-2::-1]:
        scene.clear()
        scene.paint(ball(r), dim(MAGENTA, 0.5))                  # the whole ball, dim
        scene.paint(ball(r - 1.0), WHITE)                        # the core, bright
        scene.hold()
    scene.fade_out(ALL, steps=8)
    return scene.frames


def wireframe(time_ms=60):
    """EDGES, CORNERS and face(): the cube's outline, pulsing corners, then each face in turn."""
    scene = Scene(time_ms)
    scene.fade_in(EDGES, dim(BLUE, 0.5), steps=15)
    for _ in range(3):                                           # corners pulse three times
        scene.fade(CORNERS, WHITE, steps=6)
        scene.fade(CORNERS, dim(BLUE, 0.5), steps=6)
    for name, colour in zip(("front", "right", "back", "left", "top", "bottom"),
                            (RED, ORANGE, YELLOW, GREEN, CYAN, MAGENTA)):
        scene.fade(FACES[name], colour, steps=5)
        scene.hold(200)
        scene.fade(FACES[name] - EDGES, (0, 0, 0), steps=5)      # keep the outline lit
    scene.fade_out(ALL, steps=15)
    return scene.frames




def three_planes(time_ms=100):
    """Set algebra: the three centre planes as a 3-D cross; their intersections picked out."""
    mid = SIZE // 2
    px, py, pz = plane("x", mid), plane("y", mid), plane("z", mid)
    scene = Scene(time_ms)
    scene.fade_in(px | py | pz, dim(GREEN, 0.3), steps=12)       # union: the whole cross
    scene.hold(400)
    scene.fade((px & py) | (py & pz) | (pz & px), YELLOW, steps=10)   # pairwise intersections: three lines
    scene.hold(400)
    scene.fade(px & py & pz, WHITE, steps=8)                     # all three: the centre LED
    scene.hold(600)
    scene.fade(OUTER - (px | py | pz), dim(BLUE, 0.2), steps=12)  # difference: the surface, cross cut out
    scene.hold(800)
    scene.fade_out(ALL, steps=15)
    return scene.frames


def morph_between(time_ms=60):
    """Scene.morph(): cross-fade between complete frames from other generators."""
    scene = Scene(time_ms)
    scene.load(rainbow_layers()[0])                              # start from another generator's frame
    scene.hold(500)
    target = Scene().paint(OUTER, RED).paint(MIDDLE, BLUE).paint(CENTRE, WHITE).current
    scene.morph(target, steps=25)
    scene.hold(500)
    scene.morph(rising_plane()[2], steps=25)
    scene.hold(500)
    scene.fade_out(ALL, steps=15)
    return scene.frames


GENERATORS = {
    "random_rain": random_rain,
    "rainbow_layers": rainbow_layers,
    "rising_plane": rising_plane,
    "chain_test": chain_test,
    "fade_all": fade_all,
    "shells": shells,
    "plane_sweep": plane_sweep,
    "column_rain": column_rain,
    "top_face_lines": top_face_lines,
    "growing_cube": growing_cube,
    "expanding_squares": expanding_squares,
    "breathing_ball": breathing_ball,
    "wireframe": wireframe,
    "diagonal_wave": diagonal_wave,
    "three_planes": three_planes,
    "morph_between": morph_between,
}

if __name__ == "__main__":
    patterns_dir.mkdir(exist_ok=True)
    for name, generator in GENERATORS.items():
        frames = generator()
        write_pattern(patterns_dir / f"{name}.bin", frames)
        print(f"{name}.bin: {len(frames)} frames")
