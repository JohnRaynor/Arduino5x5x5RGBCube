"""More pattern generators, and a quick reference for building your own.

Everything here appears in the editor's Generate... list and in
Test_sample_pattern.py alongside the generators in make_sample_patterns.py.

QUICK REFERENCE
===============

Positions: x left-right, y front-back, z bottom-top, each 0 to 4. MID = 2.0.

A colour is a tuple (r, g, b), each 0-255.
    RED, GREEN, BLUE, CYAN, MAGENTA, YELLOW, ORANGE, PURPLE, WHITE, BLACK
    hsv(h)              h from 0 to 1 round the rainbow (wraps); hsv(h, s, v)
    dim(colour, 0.3)    a colour at 30 % brightness
    mix(a, b, 0.5)      halfway between two colours
    RANDOMCOLOUR()      a function: note the brackets

A region is a set of LEDs. Combine with |  (either)  &  (both)  -  (but not).
    layer(z)                    one horizontal layer
    plane("x", n)               axis as a letter in quotes, then 0-4
    column(x, y)                the 5 LEDs stacked at (x, y)
    line("x", y=2, z=4)         axis letter, then the other two BY NAME
    point(x, y, z)              one LED  (new, in this file)
    shell(n)  cube(n)           n = 0 centre, 1 middle, 2 outside
    ball(r)                     r is a distance, e.g. 1.5
    square(z, n)                ring n out from the centre, on layer z
    face("top")                 "top" "bottom" "left" "right" "front" "back"
    ALL OUTER MIDDLE CENTRE EDGES CORNERS     constants: no brackets
    select(lambda x, y, z: x == y)            anything else

A Scene holds a working frame. Nothing is saved until you capture it.
    scene = Scene(50)                         default 50 ms per frame
    scene.paint(region, colour)               region first, then colour
    scene.clear()  /  scene.clear(region)
    scene.scale(region, 0.5)                  dim what is lit: trails
    scene.hold()  /  scene.hold(500)          CAPTURE one frame
    scene.fade(region, colour, steps)         captures `steps` frames
    scene.fade_in(region, colour, steps)
    scene.fade_out(region, steps)
    scene.crossfade(going, coming, colour, steps)
    scene.fade_many([(region, colour), (region, colour)], steps)
    return scene.frames                       the finished pattern

field(rule, steps)  (new, in this file) - for effects where every LED follows
the same rule: rule(x, y, z, t) returns a colour, with t running 0 -> 1 over
the pattern. Smooth, loopable effects come out of this in a few lines.

Common slips
    RANDOMCOLOUR without ()        is the function, not a colour
    paint(colour, region)          wrong way round
    for one LED, point(x, y, z)    not (x, y, z) on its own
    lambda inside a loop           write lambda x, y, z, k=k: ... to keep k
"""
import random
from math import atan2, cos, exp, pi, sin, sqrt

from cube_layout import SIZE, XYZ, led_index
from patterns import new_frame
from patterngen import (ALL, CYAN, GREEN, MAGENTA, MID, RED, WHITE,
                        Scene, dim, hsv, select)


# ----------------------------------------------------------------- helpers --
def point(x, y, z):
    """A region holding the single LED at (x, y, z)."""
    return frozenset({led_index(x, y, z)})


def distance(x, y, z, cx=MID, cy=MID, cz=MID):
    """Straight-line distance from (x, y, z) to (cx, cy, cz); the centre by default."""
    return sqrt((x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2)


def field(rule, steps, time_ms=60):
    """Frames from one rule applied to every LED.

    rule(x, y, z, t) returns the colour of the LED at (x, y, z) at time t, where
    t runs from 0 up to (not including) 1 across the pattern. A rule that
    repeats when t goes up by 1 loops with no visible jump.
    """
    frames = []
    for step in range(steps):
        t = step / steps
        frame = new_frame(time_ms)
        for index, (x, y, z) in enumerate(XYZ):
            frame["colours"][index] = [max(0, min(255, int(c))) for c in rule(x, y, z, t)]
        frames.append(frame)
    return frames


# ------------------------------------------------------ whole-cube effects --
def plasma(steps=90, time_ms=50):
    """field(): overlapping waves of colour drifting through the whole cube."""
    def rule(x, y, z, t):
        a = 2 * pi * t
        v = (sin(x * 0.9 + a) + sin(y * 0.8 - a) + sin((x + y + z) * 0.6 + 2 * a)
             + sin(distance(x, y, z) * 1.3 - a))
        return hsv(v / 8 + t, 1.0, 0.45)
    return field(rule, steps, time_ms)


def rainbow_swirl(steps=60, time_ms=50):
    """field(): a rainbow wrapped round the vertical axis, twisting as it climbs, and turning."""
    def rule(x, y, z, t):
        angle = atan2(y - MID, x - MID) / (2 * pi)
        return hsv(angle + z * 0.1 + t, 1.0, 0.45)
    return field(rule, steps, time_ms)


def lava_lamp(steps=120, time_ms=50):
    """field(): three soft blobs drifting, merging and parting, in lava-lamp colours."""
    paths = [((1, 2, 1), (0.0, 0.3, 0.7)),          # how fast each blob moves on x, y, z,
             ((2, 1, 1), (0.5, 0.1, 0.2)),          # and where on its path it starts
             ((1, 1, 2), (0.25, 0.6, 0.4))]

    def rule(x, y, z, t):
        heat = 0.0
        for speeds, starts in paths:
            cx, cy, cz = (MID + 1.7 * sin(2 * pi * (s * t + p)) for s, p in zip(speeds, starts))
            heat += 1.0 / (0.35 + distance(x, y, z, cx, cy, cz) ** 2)
        v = max(0.0, min(1.0, (heat - 0.45) / 1.2)) ** 0.7
        return hsv(0.13 * v, 1.0, 0.75 * v)         # dark red through orange to yellow
    return field(rule, steps, time_ms)


def shockwave(steps=40, time_ms=50):
    """field(): spherical ripples spreading out from the centre."""
    def rule(x, y, z, t):
        r = distance(x, y, z)
        wave = (0.5 + 0.5 * cos(2 * pi * (r / 1.6 - 2 * t))) ** 4
        return hsv(0.55 + r * 0.06, 1.0, 0.7 * wave)
    return field(rule, steps, time_ms)


def heartbeat(steps=50, time_ms=20):
    """field(): a double beat radiating from the centre - 60 beats a minute."""
    def rule(x, y, z, t):
        delay = t - distance(x, y, z) * 0.035          # the outside beats a moment later
        beat = (exp(-((delay - 0.10) / 0.035) ** 2)
                + 0.6 * exp(-((delay - 0.30) / 0.035) ** 2))
        return dim(RED, min(1.0, beat))
    return field(rule, steps, time_ms)


# ------------------------------------------------------ things that rotate --
def radar_sweep(steps=48, time_ms=40):
    """field(): a beam sweeping round the centre column, leaving a fading green trail."""
    def rule(x, y, z, t):
        if x == MID and y == MID:                       # the spindle
            return dim(GREEN, 0.35)
        behind = (t - atan2(y - MID, x - MID) / (2 * pi)) % 1.0
        return dim(GREEN, max(0.0, 1 - behind * 3) ** 2)
    return field(rule, steps, time_ms)


def double_helix(steps=60, time_ms=50):
    """field(): two strands twisting round each other, turning as if climbing."""
    def rule(x, y, z, t):
        total = [0.0, 0.0, 0.0]
        for offset, strand in ((0.0, CYAN), (0.5, MAGENTA)):
            angle = 2 * pi * (t + z / SIZE + offset)
            px, py = MID + 1.8 * cos(angle), MID + 1.8 * sin(angle)
            weight = exp(-((x - px) ** 2 + (y - py) ** 2) / 0.5)
            total = [a + c * weight for a, c in zip(total, strand)]
        return total
    return field(rule, steps, time_ms)


# ------------------------------------------------------ things that move --
def bouncing_ball(steps=160, time_ms=40):
    """A glowing ball bouncing round the inside of the cube, changing colour at each bounce."""
    pos, vel = [0.5, 1.2, 4.0], [0.21, 0.13, 0.0]
    gravity, hue = -0.045, 0.0
    top = SIZE - 1
    frames = []
    for _ in range(steps):
        vel[2] += gravity
        for axis in range(3):
            pos[axis] += vel[axis]
            if pos[axis] < 0 or pos[axis] > top:        # reflect off the wall
                pos[axis] = -pos[axis] if pos[axis] < 0 else 2 * top - pos[axis]
                vel[axis] = -vel[axis]
                hue += 0.13
        frame = new_frame(time_ms)
        for index, (x, y, z) in enumerate(XYZ):
            glow = max(0.0, 1 - distance(x, y, z, *pos) / 2.0) ** 1.2
            frame["colours"][index] = list(dim(hsv(hue), glow))
        frames.append(frame)
    return frames


def snake(steps=160, time_ms=70, length=7, seed=5):
    """A worm wandering through the cube, never doubling back on itself, its tail fading."""
    rng = random.Random(seed)
    moves = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    body, heading = [(2, 2, 2)], moves[0]
    frames = []
    for step in range(steps):
        x, y, z = body[-1]
        options = [(m, (x + m[0], y + m[1], z + m[2])) for m in moves
                   if all(0 <= c < SIZE for c in (x + m[0], y + m[1], z + m[2]))]
        free = [o for o in options if o[1] not in body] or options
        ahead = [o for o in free if o[0] == heading]
        heading, nxt = ahead[0] if ahead and rng.random() < 0.6 else rng.choice(free)
        body = (body + [nxt])[-length:]
        frame = new_frame(time_ms)
        colour = hsv(step / steps)
        for k, cell in enumerate(reversed(body)):        # head first, brightest
            frame["colours"][led_index(*cell)] = list(dim(colour, (1 - k / length) ** 1.5))
        frames.append(frame)
    return frames


def fireworks(bursts=6, time_ms=50, seed=3):
    """Rockets climb a column, then burst into an expanding shell of colour."""
    rng = random.Random(seed)
    scene = Scene(time_ms)
    for _ in range(bursts):
        x, y, top = rng.randint(1, 3), rng.randint(1, 3), rng.randint(3, 4)
        colour = hsv(rng.random())
        for z in range(top + 1):                        # the rocket
            scene.scale(ALL, 0.4)
            scene.paint(point(x, y, z), dim(WHITE, 0.6))
            scene.hold()
        for r in (0.0, 1.0, 1.5, 2.1, 2.7):             # the burst, growing
            scene.scale(ALL, 0.55)
            scene.paint(select(lambda a, b, c, r=r: abs(distance(a, b, c, x, y, top) - r) < 0.55),
                        colour)
            scene.hold()
        scene.fade_out(ALL, steps=8)
        scene.hold(rng.choice((100, 250, 400)))         # a pause before the next
    return scene.frames


def digital_rain(steps=150, time_ms=60, seed=7):
    """Green drops falling down the columns at different speeds, bright heads, fading tails."""
    rng = random.Random(seed)
    scene = Scene(time_ms)
    drops = []                                          # [x, y, z, frames per step, tick]
    for _ in range(steps):
        scene.scale(ALL, 0.6)
        if rng.random() < 0.55:
            drops.append([rng.randrange(SIZE), rng.randrange(SIZE), SIZE - 1, rng.choice((1, 1, 2)), 0])
        falling = []
        for drop in drops:
            x, y, z = drop[:3]
            scene.paint(point(x, y, z), (0, 180, 30))   # where it was becomes tail
            drop[4] += 1
            if drop[4] >= drop[3]:
                drop[4], drop[2] = 0, z - 1
            if drop[2] >= 0:
                scene.paint(point(x, y, drop[2]), (170, 255, 170))
                falling.append(drop)
        drops = falling
        scene.hold()
    return scene.frames


GENERATORS = {
    "plasma": plasma,
    "rainbow_swirl": rainbow_swirl,
    "lava_lamp": lava_lamp,
    "shockwave": shockwave,
    "heartbeat": heartbeat,
    "radar_sweep": radar_sweep,
    "double_helix": double_helix,
    "bouncing_ball": bouncing_ball,
    "snake": snake,
    "fireworks": fireworks,
    "digital_rain": digital_rain,
}
