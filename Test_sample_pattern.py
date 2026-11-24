"""Run one generator and watch it. Press F5 in VS Code.

Edit GENERATOR below to pick which one. Nothing else needs changing.

To step through a pattern as it is built, put a breakpoint on the
cube_live.show(scene) line inside the generator in make_sample_patterns.py and
press F5: show() blocks until the frame is on screen, so each step moves the
cube on by one frame.
"""
import cube_live
import make_sample_patterns

# ---------------------------------------------------------------- settings --
GENERATOR = "test_fade_many"    # which generator to watch
ON_CUBE = False                 # True drives the real cube instead of a window
REPEAT = True                   # keep looping until the window is closed
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

    # Any cube_live.show() calls inside the generator fire during this line.
    frames = generators[GENERATOR]()
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
