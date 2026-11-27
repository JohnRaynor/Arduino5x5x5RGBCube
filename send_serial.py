"""Serial link to the cube: preview frames live, or write a pattern to its SD card.

Protocol (the 4x4x4 project's CUBE protocol, with 377-byte frames, 115200
baud, and two additions marked *).  Every command starts with the ASCII bytes
CUBE so a frame byte can never be mistaken for a command; the Arduino replies
with single-line ASCII messages.

    PC -> Arduino  64 zero bytes *          before every command: FastLED.show()
                                            blocks the UART for ~4 ms, so the
                                            zeros absorb any lost bytes
    PC -> Arduino  CUBE P + one frame       preview this frame for its display time
    Arduino -> PC  FRAME                    frame finished; the cube holds it
    PC -> Arduino  CUBE R                   resume random SD playback
    Arduino -> PC  RESUMED
    PC -> Arduino  CUBE W + len + name + size (uint32 little-endian)   start SD write
    Arduino -> PC  READY                    send the file bytes now
    PC -> Arduino  64-byte block            ... repeated
    Arduino -> PC  NEXT *                   block written; send the next one
    Arduino -> PC  DONE                     last block written, file closed
    Arduino -> PC  ERR ...                  something failed
"""
import struct
import time
from pathlib import Path

import serial

from patterns import FRAME_BYTES, encode_frame

BAUD = 115200
PREAMBLE = bytes(64)   # zeros
BLOCK = 64
MAX_SD_NAME = 32                     # must match MAX_NAME in rgb_cube.ino
SD_FORBIDDEN = set('<>:"/\\|?*')       # characters FAT will not take in a name


def _encode_frames(frames):
    return b"".join(encode_frame(frame) for frame in frames)


# Every command sent and every line received is recorded in cube_serial.log,
# beside these scripts. It costs a few lines a second and it is the only way to
# see what happened when a fault is intermittent. Set the CUBE_SERIAL_LOG
# environment variable to another path to move it, or to "off" to stop logging.
import datetime
import os

LOG_SIZE_LIMIT = 1_000_000          # start a fresh file past about 1 MB


def _log_file():
    setting = os.environ.get("CUBE_SERIAL_LOG")
    if setting is None:
        return Path(__file__).with_name("cube_serial.log")
    if setting.strip().lower() in ("", "off", "0", "no", "none"):
        return None
    return Path(setting)


def _log(text):
    path = _log_file()
    if path is None:
        return
    try:
        if path.exists() and path.stat().st_size > LOG_SIZE_LIMIT:
            path.unlink()
        stamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(stamp + "  " + text + chr(10))
    except OSError:
        pass                        # logging must never break a transfer


LIKELY_ADAPTERS = ("arduino", "ch340", "ch341", "cp210", "ftdi", "wch", "usb serial", "usb-serial")


def available_ports():
    """[(device, description)] for every serial port the OS can see.

    Likely Arduino adapters come first, so the caller can offer a sensible
    default. Windows renumbers these across reboots, so a port that worked
    yesterday may simply not be there today.
    """
    from serial.tools import list_ports
    ports = [(port.device, (port.description or "").strip()) for port in list_ports.comports()]
    def unlikely(entry):
        text = f"{entry[0]} {entry[1]}".lower()
        return not any(name in text for name in LIKELY_ADAPTERS)
    return sorted(ports, key=unlikely)


# Warnings the Arduino printed during its last boot, e.g. a missing SD card.
# Set by _connect(); the caller can show them without the command having failed.
last_boot_warnings = []


class PreviewStopped(Exception):
    """Raised inside a preview when its stop flag is set; preview_frames() handles it."""


def _wait_for(ser, expected, timeout, stop=None):
    """Read lines until `expected` arrives; returns the other lines seen on the way.

    Anything that is not an ERR is passed over, so a WARN in the boot banner (a
    missing SD card, say) does not abort the command that follows it.
    """
    deadline = time.monotonic() + timeout
    responses = []
    while time.monotonic() < deadline:
        if stop is not None and stop.is_set():      # checked every readline, ~0.25 s
            raise PreviewStopped()
        response = ser.readline().decode("ascii", errors="replace").strip()
        if not response:
            continue
        _log("<- " + response)
        responses.append(response)
        if response == expected:
            return responses[:-1]
        if response.startswith("ERR"):
            raise RuntimeError(f"Arduino reported: {response}")
        if response == "READY" and expected != "READY":
            # READY is only printed by setup(), so the board restarted under us.
            raise RuntimeError(
                "The Arduino restarted in the middle of the command: it sent READY, "
                "which only happens at boot. Nothing the PC sends can cause that, so "
                "look at power (a sagging supply browning the board out as the cube "
                "lights up) or a loose USB lead.")
    detail = "; ".join(responses) if responses else "no response"
    raise TimeoutError(f"Expected {expected}; received {detail}.")


def _sd_name(filename):
    """The name the file gets on the SD card: the local name, case kept.

    SdFat on the Nano has long-filename support, so any name up to MAX_SD_NAME
    characters (the .bin included) will do, in printable ASCII without the
    characters FAT forbids and not ending in a space or a dot.
    """
    name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].strip()
    if not name.lower().endswith(".bin"):
        name += ".bin"
    stem = name[:-4]
    if (not stem.strip(" .") or stem != stem.rstrip(" .") or len(name) > MAX_SD_NAME
            or any(char in SD_FORBIDDEN or not " " <= char <= "~" for char in name)):
        raise ValueError(f"SD names can be up to {MAX_SD_NAME} characters including .bin, "
                         'without < > : " / \\ | ? *, and cannot end in a space or a dot.')
    return name


def suggest_sd_name(local_path):
    """The SD name for a local file: its own name, if the card can take it.

    Returns (name, exact); exact is False when characters had to be replaced or
    the name shortened, so the caller can let the user confirm it.
    """
    original = local_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if original.lower().endswith(".bin"):
        stem, extension = original[:-4], original[-4:]
    else:
        stem, extension = original.rsplit(".", 1)[0], ".bin"
    cleaned = "".join("_" if char in SD_FORBIDDEN or not " " <= char <= "~" else char for char in stem)
    cleaned = cleaned[:MAX_SD_NAME - len(extension)].rstrip(" .") or "pattern"
    name = cleaned + extension
    return name, name == original


def _connect(port):
    global last_boot_warnings
    _log("=== opening " + str(port) + " on "
         + datetime.datetime.now().strftime("%Y-%m-%d") + " ===")
    ser = serial.Serial(port, BAUD, timeout=0.25, write_timeout=5)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(2)  # Opening USB serial normally resets the Arduino.
    banner = _wait_for(ser, "READY", 8)
    last_boot_warnings = [line[5:].strip() for line in banner if line.startswith("WARN")]
    return ser


def _command(ser, payload):
    _log("-> " + payload[:5].decode("ascii", errors="replace")
         + (f" +{len(payload) - 5} bytes" if len(payload) > 5 else ""))
    ser.write(PREAMBLE + payload)
    ser.flush()


def _send_preview(ser, data, stop=None, on_frame=None):
    for index, offset in enumerate(range(0, len(data), FRAME_BYTES)):
        if stop is not None and stop.is_set():
            raise PreviewStopped()
        frame = data[offset:offset + FRAME_BYTES]
        _command(ser, b"CUBEP" + frame)
        _wait_for(ser, "FRAME", max(5, int.from_bytes(frame[-2:], "big") / 1000 + 3), stop)
        if on_frame is not None:
            on_frame(index)


def _resume_random(ser):
    _command(ser, b"CUBER")
    _wait_for(ser, "RESUMED", 5)


def open_cube(port):
    """Open a connection and leave it open, for sending frames one at a time.

    Opening the port resets the Arduino, so hold on to what this returns for as
    long as you are working: reconnecting costs about two seconds each time.
    Pass it to send_frame() and resume_random(), and close() it when done.
    """
    return _connect(port)


def send_frame(ser, frame):
    """Show one frame on an already-open connection and wait for it to finish."""
    _command(ser, b"CUBEP" + encode_frame(frame))
    _wait_for(ser, "FRAME", max(5, frame["time"] / 1000 + 3))


def resume_random(ser):
    """Hand the cube back to its own SD playback."""
    _resume_random(ser)


def preview_frames(port, frames, after_preview=None, stop=None, on_frame=None):
    """Display the frames on the physical cube without changing the SD card.

    The cube holds the last frame after the pattern finishes.  If after_preview
    is given it is called then; returning "again" replays the pattern, anything
    else resumes random SD playback.  The port stays open throughout, because
    reopening it would reset the Arduino.

    stop, if given, is a threading.Event: set it from another thread and the
    preview ends within about a quarter of a second, handing the cube back to
    random playback. on_frame(index) is called as each frame finishes showing.
    """
    data = _encode_frames(frames)
    with _connect(port) as ser:
        try:
            while True:
                _send_preview(ser, data, stop, on_frame)
                if after_preview is None or after_preview() != "again":
                    break
        except PreviewStopped:
            pass                     # asked to stop: fall through to resume
        except Exception:
            try:
                _resume_random(ser)  # Best effort: do not leave the cube frozen.
            except Exception:
                pass
            raise
        _resume_random(ser)


def write_frames_to_sd(port, filename, frames):
    """Write the frames to filename on the SD card attached to the Arduino."""
    data = _encode_frames(frames)
    name = _sd_name(filename).encode("ascii")
    with _connect(port) as ser:
        _command(ser, b"CUBEW" + bytes([len(name)]) + name + struct.pack("<I", len(data)))
        _wait_for(ser, "READY", 5)
        for offset in range(0, len(data), BLOCK):
            ser.write(data[offset:offset + BLOCK])
            ser.flush()
            if offset + BLOCK < len(data):
                _wait_for(ser, "NEXT", 5)   # the Nano's serial buffer is 64 bytes: one block in flight
        _wait_for(ser, "DONE", 10)
