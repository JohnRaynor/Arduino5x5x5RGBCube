"""Tools for building patterns in code: named regions of the cube, and a Scene
that paints and fades them into a list of frames.

Coordinates: x 0..4 left-right, y 0..4 front-back, z 0..4 bottom-top.

A region is a frozenset of chain indices, so regions combine with the set
operators:  OUTER | CENTRE,  layer(2) & plane("x", 2),  ALL - column(0, 0).

Typical generator:

    def my_pattern():
        scene = Scene(time_ms=50)
        scene.paint(OUTER, RED)
        scene.hold(500)                          # one frame shown for 500 ms
        scene.fade_in(MIDDLE, BLUE, steps=20)    # 20 frames, MIDDLE black -> blue
        scene.fade_out(ALL, steps=30)            # 30 frames, everything -> black
        return scene.frames
"""
import colorsys
import copy

from cube_layout import LED_COUNT, SIZE, XYZ, led_index
from patterns import new_frame

MID = (SIZE - 1) / 2            # centre coordinate, 2.0 for a 5-cube
AXES = "xyz"

# --------------------------------------------------------------- colours ----
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
ORANGE = (255, 96, 0)
YELLOW = (255, 200, 0)
GREEN = (0, 255, 0)
CYAN = (0, 255, 255)
BLUE = (0, 0, 255)
PURPLE = (160, 0, 255)
MAGENTA = (255, 0, 255)


def hsv(h, s=1.0, v=1.0):
    """Colour from hue 0..1 (wraps), saturation and value."""
    return tuple(int(channel * 255) for channel in colorsys.hsv_to_rgb(h % 1.0, s, v))


def dim(colour, factor):
    """`colour` scaled by 0..1."""
    return tuple(int(channel * factor) for channel in colour)


def mix(a, b, t):
    """Colour t of the way from a (t=0) to b (t=1)."""
    return tuple(round(ca + (cb - ca) * t) for ca, cb in zip(a, b))


# --------------------------------------------------------------- regions ----
def select(predicate):
    """Region of every LED whose (x, y, z) satisfies predicate(x, y, z)."""
    return frozenset(i for i, (x, y, z) in enumerate(XYZ) if predicate(x, y, z))


def _axis(axis):
    if axis not in AXES:
        raise ValueError(f"axis must be one of {AXES!r}, not {axis!r}")
    return AXES.index(axis)


def plane(axis, n):
    """The 25 LEDs with the given coordinate: plane("z", 0) is the bottom layer,
    plane("x", 0) the left face, plane("y", 4) the back face."""
    a = _axis(axis)
    return select(lambda *p: p[a] == n)


def layer(z):
    """Horizontal layer z (0 = bottom)."""
    return plane("z", z)


def column(x, y):
    """The 5 LEDs stacked vertically at (x, y)."""
    return select(lambda px, py, pz: px == x and py == y)


def line(axis, **fixed):
    """A line of 5 LEDs along `axis`; give the other two coordinates by name,
    e.g. line("x", y=2, z=4) is the middle row of the top layer."""
    a = _axis(axis)
    others = [b for b in AXES if b != axis]
    if sorted(fixed) != others:
        raise ValueError(f"line({axis!r}) needs exactly {others[0]}= and {others[1]}=")
    return select(lambda *p: all(p[_axis(b)] == fixed[b] for b in others))


def cube(n):
    """Solid cube of side 2n+1 around the centre: cube(0) is the centre LED,
    cube(1) the middle 3x3x3, cube(2) the whole cube."""
    return select(lambda x, y, z: max(abs(x - MID), abs(y - MID), abs(z - MID)) <= n)


def shell(n):
    """Hollow cubic shell at distance n from the centre: shell(2) is the outer
    surface (98 LEDs), shell(1) the middle shell (26), shell(0) the centre (1)."""
    return select(lambda x, y, z: max(abs(x - MID), abs(y - MID), abs(z - MID)) == n)


def square(z, n):
    """On layer z, the square ring n out from the centre (n=0 centre LED, n=2 rim)."""
    return select(lambda x, y, pz: pz == z and max(abs(x - MID), abs(y - MID)) == n)


def ball(radius):
    """LEDs within `radius` (Euclidean) of the centre; try 1.5, 2.3, 3.5."""
    return select(lambda x, y, z: (x - MID) ** 2 + (y - MID) ** 2 + (z - MID) ** 2 <= radius ** 2)


def _on_faces(x, y, z):
    return sum(c in (0, SIZE - 1) for c in (x, y, z))


ALL = select(lambda x, y, z: True)
OUTER = shell(2)
MIDDLE = shell(1)
CENTRE = shell(0)
EDGES = select(lambda x, y, z: _on_faces(x, y, z) >= 2)      # the 12 edges, corners included
CORNERS = select(lambda x, y, z: _on_faces(x, y, z) == 3)
FACES = {"left": plane("x", 0), "right": plane("x", SIZE - 1),
         "front": plane("y", 0), "back": plane("y", SIZE - 1),
         "bottom": plane("z", 0), "top": plane("z", SIZE - 1)}


def face(name):
    """One of the six faces by name: left, right, front, back, bottom, top."""
    return FACES[name]


# ----------------------------------------------------------------- scene ----
class Scene:
    """A working frame plus the list of frames captured from it so far.

    paint/clear/scale change the working frame without capturing it; hold()
    captures it once; the fade methods capture one frame per step.
    """

    def __init__(self, time_ms=100):
        self.time_ms = time_ms          # default display time for captured frames
        self.frames = []
        self.current = new_frame(time_ms)

    @property
    def colours(self):
        """The working frame's colours, by chain index; edit directly if you like."""
        return self.current["colours"]

    def colour_at(self, x, y, z):
        return tuple(self.colours[led_index(x, y, z)])

    # -- change the working frame --
    def paint(self, region, colour):
        for i in region:
            self.colours[i] = list(colour)
        return self

    def clear(self, region=ALL):
        return self.paint(region, BLACK)

    def scale(self, region, factor):
        """Multiply the brightness of `region` by 0..1 (or brighten with >1, clipped)."""
        for i in region:
            self.colours[i] = [min(255, int(c * factor)) for c in self.colours[i]]
        return self

    def load(self, frame):
        """Make a copy of an existing frame the working frame."""
        self.current = copy.deepcopy(frame)
        return self

    # -- capture frames --
    def hold(self, time_ms=None):
        """Capture the working frame as one frame shown for time_ms."""
        frame = copy.deepcopy(self.current)
        frame["time"] = self.time_ms if time_ms is None else time_ms
        self.frames.append(frame)
        return self

    def fade(self, region, to, steps, time_ms=None):
        """Capture `steps` frames taking every LED in `region` from its current
        colour to `to`; the last frame lands exactly on `to`."""
        start = {i: tuple(self.colours[i]) for i in region}
        for step in range(1, steps + 1):
            t = step / steps
            for i in region:
                self.colours[i] = list(mix(start[i], to, t))
            self.hold(time_ms)
        return self

    def fade_in(self, region, colour, steps, time_ms=None):
        """`region` from black up to `colour`."""
        self.clear(region)
        return self.fade(region, colour, steps, time_ms)

    def fade_out(self, region, steps, time_ms=None):
        """`region` down to black."""
        return self.fade(region, BLACK, steps, time_ms)

    def morph(self, target, steps, time_ms=None):
        """Cross-fade the whole cube to `target`, a frame or a list of 125 colours."""
        target = target["colours"] if isinstance(target, dict) else target
        if len(target) != LED_COUNT:
            raise ValueError(f"target must have {LED_COUNT} colours")
        start = [tuple(c) for c in self.colours]
        for step in range(1, steps + 1):
            t = step / steps
            self.colours[:] = [list(mix(a, b, t)) for a, b in zip(start, target)]
            self.hold(time_ms)
        return self

    def extend(self, frames):
        """Append ready-made frames (e.g. from an older generator); the last one
        becomes the working frame."""
        self.frames.extend(copy.deepcopy(frames))
        if frames:
            self.load(frames[-1])
        return self


if __name__ == "__main__":
    # Sanity checks on the regions.
    assert len(ALL) == LED_COUNT
    assert len(OUTER) == 98 and len(MIDDLE) == 26 and len(CENTRE) == 1
    assert OUTER | MIDDLE | CENTRE == ALL and not (OUTER & MIDDLE)
    assert len(EDGES) == 44 and len(CORNERS) == 8
    assert all(len(plane(a, n)) == SIZE * SIZE for a in AXES for n in range(SIZE))
    assert all(len(column(x, y)) == SIZE for x in range(SIZE) for y in range(SIZE))
    assert len(line("x", y=2, z=4)) == SIZE and line("x", y=2, z=4) <= face("top")
    assert square(2, 2) == layer(2) & OUTER
    assert len(cube(1)) == 27 and cube(2) == ALL
    scene = Scene(50).paint(OUTER, RED).hold().fade_out(ALL, 4)
    assert len(scene.frames) == 5 and scene.frames[-1]["colours"] == [[0, 0, 0]] * LED_COUNT
    assert scene.frames[2]["colours"][next(iter(OUTER))] == [128, 0, 0]
    print("patterngen OK")
