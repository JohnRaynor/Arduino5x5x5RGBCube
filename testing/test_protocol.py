"""Drive send_serial against a model of the sketch's state machine.

The model mirrors rgb_cube.ino closely enough to catch protocol mistakes without
hardware: the same FIND_MAGIC / READ_COMMAND / READ_PREVIEW states, the same
"refresh only after SERIAL_QUIET_MS of silence" rule, the same preview hold, and
the same no-SD-card behaviour. Run it with `python testing/test_protocol.py`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # the project's own modules

import send_serial  # noqa: E402
from patterngen import RED, Scene, ALL
from patterns import FRAME_BYTES

SERIAL_QUIET_MS = 50
PREVIEW_HOLD_MS = 60000
NUM_LEDS = 125


class ModelArduino:
    """Enough of the sketch to answer the PC, on a virtual clock in milliseconds."""

    def __init__(self, sd_ok=True, pattern_count=3, show_ms=4):
        self.sd_ok, self.pattern_count = sd_ok, pattern_count
        self.show_ms = show_ms              # FastLED.show() blocks this long
        self.now = 0
        self.out = []                       # lines the sketch has printed
        self.rx = bytearray()
        self.state, self.magic_pos, self.count = "FIND_MAGIC", 0, 0
        self.preview_mode = self.preview_waiting = self.preview_pending = False
        self.preview_end = self.preview_hold_end = self.frame_end = 0
        self.preview_time = 0
        self.need_show = False
        self.last_serial_byte = -10_000
        self.shows = 0
        self.boot()

    def boot(self):
        if not self.sd_ok:
            self.out.append("WARN SD initialisation failed; previews still work")
        self.out.append("READY")

    # -- the sketch's receive state machine --
    def byte(self, value):
        self.last_serial_byte = self.now
        if self.state == "FIND_MAGIC":
            magic = b"CUBE"
            if value == magic[self.magic_pos]:
                self.magic_pos += 1
            else:
                self.magic_pos = 1 if value == ord("C") else 0
            if self.magic_pos == 4:
                self.state, self.magic_pos = "READ_COMMAND", 0
        elif self.state == "READ_COMMAND":
            if value == ord("P"):
                self.preview_mode = True
                self.preview_waiting = self.preview_pending = False
                self.count, self.state = 0, "READ_PREVIEW"
            elif value == ord("R"):
                self.preview_mode = self.preview_waiting = self.preview_pending = False
                self.frame_end = self.now
                self.out.append("RESUMED")
                self.reset()
            else:
                self.out.append("ERR unknown command")
                self.reset()
        elif self.state == "READ_PREVIEW":
            if self.count >= NUM_LEDS * 3:
                self.preview_time = (self.preview_time << 8 | value) & 0xFFFF
            self.count += 1
            if self.count == FRAME_BYTES:
                self.preview_pending = self.need_show = True
                self.reset()

    def reset(self):
        self.state, self.magic_pos, self.count = "FIND_MAGIC", 0, 0
        self.preview_time = 0

    # -- the sketch's loop() --
    def loop(self):
        while self.rx:
            self.byte(self.rx.pop(0))
            self.now += 1                     # ~87 us a byte at 115200, rounded up
        if self.preview_waiting and self.now >= self.preview_end:
            self.preview_waiting = False
            self.preview_hold_end = self.now + PREVIEW_HOLD_MS
            self.out.append("FRAME")
        if (self.preview_mode and not self.preview_waiting and not self.preview_pending
                and self.state != "READ_PREVIEW" and self.now >= self.preview_hold_end):
            self.preview_mode = False
            self.frame_end = self.now
        if not self.preview_mode and self.now >= self.frame_end:
            self.load_random_frame()
        self.show_if_quiet()

    def load_random_frame(self):
        if not self.sd_ok or not self.pattern_count:
            return                            # no card: a cheap no-op, every pass
        self.frame_end = self.now + 100
        self.need_show = True

    def show_if_quiet(self):
        if not self.need_show or self.now - self.last_serial_byte < SERIAL_QUIET_MS:
            return
        self.now += self.show_ms              # interrupts off while clocking the LEDs
        self.shows += 1
        self.need_show = False
        if self.preview_pending:
            self.preview_pending = False
            self.preview_waiting = True
            self.preview_end = self.now + self.preview_time

    # -- the serial.Serial surface send_serial uses --
    def write(self, data):
        self.rx.extend(data)
        return len(data)

    def flush(self):
        pass

    def readline(self):
        for _ in range(200_000):              # advance the virtual clock until a line appears
            if self.out:
                return (self.out.pop(0) + "\r\n").encode()
            self.loop()
            self.now += 1
        return b""                            # the sketch said nothing: a real timeout

    def reset_input_buffer(self):
        self.rx.clear()

    def reset_output_buffer(self):
        pass

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def run(sd_ok, pattern_count, label, answers=("resume",), dialog_ms=0):
    """Run a whole preview through preview_frames() against a fresh model.

    dialog_ms is how long the user leaves the after-preview dialog open; past
    PREVIEW_HOLD_MS the sketch gives up waiting and resumes playback on its own.
    """
    model = ModelArduino(sd_ok=sd_ok, pattern_count=pattern_count)
    original_connect, replies = send_serial._connect, list(answers)
    send_serial._connect = lambda port: _connect_model(model)

    def answer():
        for _ in range(dialog_ms):           # the sketch keeps running while we think
            model.loop()
            model.now += 1
        return replies.pop(0) if replies else "resume"
    try:
        frames = Scene(40).paint(ALL, RED).hold().fade_out(ALL, steps=3).frames
        send_serial.preview_frames("MODEL", frames, after_preview=answer)
        print(f"  {label}: preview + resume OK ({model.shows} refreshes)")
        return True
    except Exception as exc:
        print(f"  {label}: FAILED -> {type(exc).__name__}: {exc}")
        return False
    finally:
        send_serial._connect = original_connect


def _connect_model(model):
    """The real _connect's handshake, against the model instead of a port."""
    banner = send_serial._wait_for(model, "READY", 8)
    send_serial.last_boot_warnings = [l[5:].strip() for l in banner if l.startswith("WARN")]
    return model


class StopAfter:
    """Stands in for threading.Event: reports set from its (checks + 1)th look on."""
    def __init__(self, checks):
        self.left = checks

    def is_set(self):
        self.left -= 1
        return self.left < 0


def run_stopped(label, frame_ms, stop, expect_shown):
    """Preview ten frames, stopping part-way; the cube must end up resumed."""
    import threading
    model = ModelArduino(sd_ok=True, pattern_count=3)
    original_connect = send_serial._connect
    send_serial._connect = lambda port: _connect_model(model)
    shown = []
    if stop == "after two frames":
        stop = threading.Event()
        on_frame = lambda i: (shown.append(i), stop.set() if i == 1 else None)
    else:
        on_frame = shown.append
    try:
        frames = [dict(f, time=frame_ms) for f in Scene(40).fade_in(ALL, RED, steps=10).frames]
        send_serial.preview_frames("MODEL", frames, stop=stop, on_frame=on_frame)
        ok = shown == expect_shown and not model.preview_mode
        print(f"  {label}: {'OK' if ok else 'FAILED'} - frames shown {shown}, "
              f"cube {'back on random playback' if not model.preview_mode else 'STILL IN PREVIEW'}")
        return ok
    except Exception as exc:
        print(f"  {label}: FAILED -> {type(exc).__name__}: {exc}")
        return False
    finally:
        send_serial._connect = original_connect


if __name__ == "__main__":
    print("preview then resume:")
    ok = run(True, 3, "SD card with patterns")
    ok &= run(True, 0, "SD card, no pattern files")
    ok &= run(False, 0, "no SD card")
    print("preview, show again, then resume:")
    ok &= run(False, 0, "no SD card", answers=("again", "resume"))
    print("slow user: dialog left open past the 60 s preview hold:")
    ok &= run(True, 3, "SD card with patterns", dialog_ms=90_000)
    ok &= run(False, 0, "no SD card", dialog_ms=90_000)
    print("stopping part-way:")
    ok &= run_stopped("stop between frames", 40, "after two frames", [0, 1])
    ok &= run_stopped("stop while a 3 s frame is still showing", 3000, StopAfter(1), [])
    print("ALL OK" if ok else "FAILURES ABOVE")
