"""Physical layout of the 5x5x5 cube: how (x, y, z) maps to the LED chain.

This must match ledIndex() in the Arduino sketch and docs/wiring-plan.html.
Data snakes through each layer in a serpentine (row 0 left-to-right, row 1
right-to-left, ...), and alternate layers are stacked rotated 180 degrees so
the layer-to-layer jumper is short.
"""
SIZE = 5
LED_COUNT = SIZE ** 3


def led_index(x, y, z):
    """Chain index of the LED at x (left-right), y (front-back), z (bottom-top)."""
    if z & 1:  # odd layers are stacked rotated 180 degrees
        x, y = SIZE - 1 - x, SIZE - 1 - y
    col = SIZE - 1 - x if y & 1 else x  # serpentine within the layer
    return z * SIZE * SIZE + y * SIZE + col


# Inverse table: XYZ[index] -> (x, y, z)
XYZ = [None] * LED_COUNT
for _z in range(SIZE):
    for _y in range(SIZE):
        for _x in range(SIZE):
            XYZ[led_index(_x, _y, _z)] = (_x, _y, _z)
assert None not in XYZ, "led_index() is not a bijection"


def layer_indices(z):
    """Chain indices of every LED in layer z."""
    return [led_index(x, y, z) for y in range(SIZE) for x in range(SIZE)]
