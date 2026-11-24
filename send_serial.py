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
SD_STEM_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


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


def _wait_for(ser, expected, timeout):
    """Read lines until `expected` arrives; returns the other lines seen on the way.

    Anything that is not an ERR is passed over, so a WARN in the boot banner (a
    missing SD card, say) does not abort the command that follows it.
    """
    deadline = time.monotonic() + timeout
    responses = []
    while time.monotonic() < deadline:
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
    name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].upper()
    if not name.endswith(".BIN"):
        name += ".BIN"
    stem, dot, extension = name.partition(".")
    if (not dot or extension != "BIN" or not 1 <= len(stem) <= 8 or
            len(name) > 12 or any(char not in SD_STEM_CHARS for char in stem)):
        raise ValueError("Use an 8.3-style .BIN name, such as SPIRAL.BIN.")
    return name


def suggest_sd_name(local_path):
    """Derive an 8.3 .BIN name from a local file name.

    Returns (name, exact); exact is False when the stem had to be shortened or
    had characters replaced, so the caller can let the user confirm it.
    """
    stem = local_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0].upper()
    cleaned = "".join(char if char in SD_STEM_CHARS else "_" for char in stem)[:8] or "PATTERN"
    return cleaned + ".BIN", cleaned == stem


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


def _send_preview(ser, data):
    for offset in range(0, len(data), FRAME_BYTES):
        frame = data[offset:offset + FRAME_BYTES]
        _command(ser, b"CUBEP" + frame)
        _wait_for(ser, "FRAME", max(5, int.from_bytes(frame[-2:], "big") / 1000 + 3))


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


def preview_frames(port, frames, after_preview=None):
    """Display the frames on the physical cube without changing the SD card.

    The cube holds the last frame after the pattern finishes.  If after_preview
    is given it is called then; returning "again" replays the pattern, anything
    else resumes random SD playback.  The port stays open throughout, because
    reopening it would reset the Arduino.
    """
    data = _encode_frames(frames)
    with _connect(port) as ser:
        try:
            while True:
                _send_preview(ser, data)
                if after_preview is None or after_preview() != "again":
                    break
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
