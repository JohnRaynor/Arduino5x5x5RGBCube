"""Read and write RGB cube pattern files.

A pattern file is a plain sequence of frames, FRAME_BYTES each, with no header:

    bytes 0 .. 374    125 x (R, G, B), one byte each, in LED chain order
    bytes 375 .. 376  display time in milliseconds, big-endian

In memory a frame is {"colours": [[r, g, b], ...] (LED_COUNT entries, chain
order), "time": milliseconds}.
"""
from cube_layout import LED_COUNT

FRAME_BYTES = LED_COUNT * 3 + 2
MIN_TIME, MAX_TIME = 5, 65535


def new_frame(time_ms=100):
    return {"colours": [[0, 0, 0] for _ in range(LED_COUNT)], "time": time_ms}


def encode_frame(frame):
    colours, duration = frame["colours"], frame["time"]
    if len(colours) != LED_COUNT:
        raise ValueError(f"Frame must have {LED_COUNT} colours, not {len(colours)}.")
    if not isinstance(duration, int) or not 0 <= duration <= MAX_TIME:
        raise ValueError(f"Frame time must be 0 to {MAX_TIME} ms.")
    data = bytearray()
    for colour in colours:
        if len(colour) != 3 or any(not 0 <= channel <= 255 for channel in colour):
            raise ValueError(f"Bad colour {colour}; each channel must be 0 to 255.")
        data.extend(colour)
    data.extend(duration.to_bytes(2, "big"))
    return bytes(data)


def decode_frame(chunk):
    if len(chunk) != FRAME_BYTES:
        raise ValueError(f"Frame chunk must be {FRAME_BYTES} bytes.")
    colours = [list(chunk[i:i + 3]) for i in range(0, LED_COUNT * 3, 3)]
    return {"colours": colours, "time": int.from_bytes(chunk[-2:], "big")}


def read_pattern(filename):
    """Return the frames in a pattern file; a trailing partial frame is ignored."""
    with open(filename, "rb") as f:
        data = f.read()
    return [decode_frame(data[i:i + FRAME_BYTES])
            for i in range(0, len(data) - FRAME_BYTES + 1, FRAME_BYTES)]


def write_pattern(filename, frames):
    with open(filename, "wb") as f:
        for frame in frames:
            f.write(encode_frame(frame))


if __name__ == "__main__":
    import sys
    for filename in sys.argv[1:] or ["Patterns/test.bin"]:
        frames = read_pattern(filename)
        total = sum(frame["time"] for frame in frames)
        print(f"{filename}: {len(frames)} frames, {total / 1000:.1f} s per loop")
