"""Run one generator and watch it. Press F5 in VS Code.

Set GENERATOR below to pick which one. Keep it to a single line: a second
GENERATOR = ... line further down silently wins, and then a breakpoint in the
generator you meant never gets hit.

To step through a pattern as it is built, put a breakpoint on a
cube_live.show(...) line inside that generator in make_sample_patterns.py and
press F5. show() blocks until the frame is on screen, so each step moves the
cube on by one frame. Use F5 (Start Debugging), not Ctrl-F5 (Run Without
Debugging) — the latter ignores breakpoints.
"""
import inspect

import cube_live
import make_sample_patterns

# ---------------------------------------------------------------- settings --
GENERATOR = "test_fade_many"    # which generator to watch - one line only
ON_CUBE = False                 # True drives the real cube instead of a window
REPEAT = False                  # keep looping until the window is closed
BUILD_ONLY = False              # True stops after generating, skipping playback
# ----------------------------------------------------------------------------


def main():
    generators = make_sample_patterns.GENERATORS
    if GENERATOR not in generators:
        print(f"No generator called {GENERATOR!r}. Set GENERATOR to one of:")
        for name in generators:
            print("   ", name)
        return

    if ON_CUBE:
        cube_live.target("cube")

    generator = generators[GENERATOR]
    print(f"running {GENERATOR}() ...")      # say it before, not after, so a
    #                                          breakpoint that never fires is
    #                                          obviously in a different function
    if "cube_live.show" not in inspect.getsource(generator):
        print(f"   note: {GENERATOR} contains no cube_live.show(...) call, so you")
        print("   will see the finished pattern rather than it being built, and a")
        print("   breakpoint on a show() line elsewhere will not be reached.")

    frames = generator()                     # show() calls inside fire here
    seconds = sum(frame["time"] for frame in frames) / 1000
    print(f"{GENERATOR}: {len(frames)} frames, {seconds:.1f} s per loop")

    if BUILD_ONLY:
        return
    print("close the window to stop" if not ON_CUBE else "Ctrl-C to stop")
    while True:
        cube_live.play(frames)
        if not REPEAT:
            return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        cube_live.close()       # hand the cube back to its own playback
