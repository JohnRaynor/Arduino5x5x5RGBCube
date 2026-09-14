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

import serial

from patterns import FRAME_BYTES, encode_frame

BAUD = 115200
PREAMBLE = bytes(64)   # zeros
BLOCK = 64
SD_STEM_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


def _encode_frames(frames):
    return b"".join(encode_frame(frame) for frame in frames)


def _wait_for(ser, expected, timeout):
    deadline = time.monotonic() + timeout
    responses = []
    while time.monotonic() < deadline:
        response = ser.readline().decode("ascii", errors="replace").strip()
        if not response:
            continue
        responses.append(response)
        if response == expected:
            return
        if response.startswith("ERR"):
            raise RuntimeError(f"Arduino reported: {response}")
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
    ser = serial.Serial(port, BAUD, timeout=0.25, write_timeout=5)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(2)  # Opening USB serial normally resets the Arduino.
    _wait_for(ser, "READY", 8)
    return ser


def _command(ser, payload):
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
