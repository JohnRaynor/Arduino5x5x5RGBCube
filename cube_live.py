"""Watch a pattern as you write it, without going through the editor.

Drop a call into the code you are working on and see the result straight away,
on screen or on the real cube:

    import cube_live

    def my_pattern():
        scene = Scene(50)
        for z in range(SIZE):
            scene.paint(layer(z), RED)
            scene.hold()
            cube_live.show(scene)        # <- look at it right now
        return scene.frames

Run the file however you normally do, including under a debugger: every
cube_live.show() blocks until the frame is actually on screen, so stepping
through the loop walks the cube through the pattern a frame at a time.

By default frames go to a window, which needs no hardware and is instant. To
watch the real thing instead, once at the top of your session:

    cube_live.target("cube")     # or "both"

Anything frame-shaped is accepted: a frame dict, a Scene (its working frame),
a bare list of 125 colours, or a list of frames to play in sequence.
"""
import atexit
import json
from pathlib import Path

from cube_layout import LED_COUNT, SIZE, XYZ, led_index
from patterns import new_frame

LIVE_TIME_MS = 20           # frames sent live are shown briefly, then held
_target = "window"
_serial = None
_screen = None
_pygame = None
_positions = None
_font = None

settings_path = Path(__file__).with_name(".led_cube_settings.json")


# ------------------------------------------------------------------ target --
def target(where):
    """Send frames to "window" (the default), "cube", or "both"."""
    global _target
    if where not in ("window", "cube", "both"):
        raise ValueError('target must be "window", "cube" or "both"')
    _target = where
    return _target


# ------------------------------------------------------------- frame input --
def _as_frame(thing, time_ms):
    """Accept a frame, a Scene, or a plain list of colours."""
    if hasattr(thing, "current"):                 # a Scene: take its working frame
        thing = thing.current
    if isinstance(thing, dict):
        frame = {"colours": [list(c) for c in thing["colours"]],
                 "time": time_ms if time_ms is not None else thing.get("time", LIVE_TIME_MS)}
    else:
        colours = list(thing)
        if len(colours) != LED_COUNT:
            raise ValueError(f"expected {LED_COUNT} colours, got {len(colours)}")
        frame = {"colours": [list(c) for c in colours],
                 "time": LIVE_TIME_MS if time_ms is None else time_ms}
    return frame


# --------------------------------------------------------------------- cube --
def _port():
    try:
        saved = json.loads(settings_path.read_text()).get("serial_port")
    except (OSError, ValueError, AttributeError):
        saved = None
    if saved:
        return saved
    import send_serial
    ports = send_serial.available_ports()
    if not ports:
        raise RuntimeError("No serial ports found. Connect the cube, or use "
                           'cube_live.target("window").')
    return ports[0][0]


def _connection():
    global _serial
    if _serial is None:
        import send_serial
        _serial = send_serial.open_cube(_port())
    return _serial


def close():
    """Hand the cube back to its own playback and let go of the port."""
    global _serial
    if _serial is not None:
        try:
            import send_serial
            send_serial.resume_random(_serial)
        except Exception:
            pass
        try:
            _serial.close()
        except Exception:
            pass
        _serial = None


atexit.register(close)


# ------------------------------------------------------------------- window --
# Laid out from cube_layout, so it cannot disagree with the real chain order.
WIN = (640, 600)
DOT, H_SPACING, H_STAGGER = 13, 100, 30
V_SPACING, V_STAGGER = 118, -15
H_OFFSET, V_OFFSET = 46, 92
OFF_COLOURS = [(64, 64, 64), (56, 56, 56), (48, 48, 48), (40, 40, 40), (32, 32, 32)]


def _dot_positions():
    """Screen position for each chain index, top layer drawn at the top."""
    positions = [None] * LED_COUNT
    for index, (x, y, z) in enumerate(XYZ):
        row = SIZE - 1 - z
        positions[index] = (H_OFFSET + x * H_SPACING + y * H_STAGGER,
                            V_OFFSET + row * V_SPACING + y * V_STAGGER)
    return positions


def _window():
    global _screen, _pygame, _positions, _font
    if _screen is None:
        import pygame
        _pygame = pygame
        pygame.init()
        _screen = pygame.display.set_mode(WIN)
        pygame.display.set_caption("cube_live")
        _positions = _dot_positions()
        _font = pygame.font.SysFont("Arial", 13)
    return _screen


def _draw(frame):
    screen = _window()
    _pygame.event.pump()                    # keep the window answering the OS
    screen.fill((0, 0, 0))
    for index, position in enumerate(_positions):
        r, g, b = frame["colours"][index]
        colour = (r, g, b) if (r or g or b) else OFF_COLOURS[XYZ[index][1]]
        _pygame.draw.circle(screen, colour, position, DOT // 2)
    for z in range(SIZE):
        label = "top" if z == SIZE - 1 else "bottom" if z == 0 else ""
        text = _font.render(f"z = {z} {label}".strip(), True, (150, 150, 150))
        screen.blit(text, (6, V_OFFSET + (SIZE - 1 - z) * V_SPACING + 4 * V_STAGGER - 18))
    _pygame.display.flip()


# -------------------------------------------------------------------- shows --
def show(thing, time_ms=None):
    """Display one frame now, and wait until it is actually showing.

    `thing` may be a frame, a Scene (its working frame is used), or a list of
    125 colours. A list of frames is played in order.
    """
    if isinstance(thing, (list, tuple)) and thing and isinstance(thing[0], dict):
        return play(thing)
    frame = _as_frame(thing, time_ms)
    if _target in ("window", "both"):
        _draw(frame)
    if _target in ("cube", "both"):
        import send_serial
        send_serial.send_frame(_connection(), frame)
    return frame


def play(frames, time_ms=None):
    """Show a whole list of frames in order."""
    for frame in frames:
        show(frame, time_ms)
    return frames


def off():
    """Blank the cube."""
    return show(new_frame(LIVE_TIME_MS))


if __name__ == "__main__":
    # A walk through the chain, which doubles as a check that the view is sane.
    import time
    print('target "window"; call cube_live.target("cube") to use the real cube')
    for index in range(LED_COUNT):
        frame = new_frame(30)
        frame["colours"][index] = [255, 255, 255]
        x, y, z = XYZ[index]
        assert led_index(x, y, z) == index
        show(frame)
        time.sleep(0.01)
    off()
    print("walked all", LED_COUNT, "LEDs in chain order")
