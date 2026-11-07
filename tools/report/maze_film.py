#!/usr/bin/env python3
"""maze_film.py TRACE.bin OUT.mp4 [--every K] [--title TEXT] -- a champion's runs of one maze, as a film.

Paul, 6 November: "write a lab report, like the Montage, but specific to training the maze navigation." The
trace is crucible's `--trace OUT --trace-scen FILE --champions C --trace-duels N` (version 3: the arena's
walls and groves recorded): N runs of one gauntlet file, each its own dice. The film follows the run that
did best (a pass first, then the one that closed most of the way), every other run a ghost in the same
maze at the same moment, drawn by montage.py's own Film -- the walls, the trees, the pillboxes, the shells --
a step every K (2) at 15 frames a second. Stills of its first, middle and last frames go beside the film.
"""
import importlib.util
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def montage():
    s = importlib.util.spec_from_file_location("montage", os.path.join(os.path.dirname(HERE), "montage.py"))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def main(a):
    if len(a) < 2:
        print(__doc__)
        sys.exit(2)
    every = int(a[a.index("--every") + 1]) if "--every" in a else 2
    title = a[a.index("--title") + 1] if "--title" in a else ""
    print(film(a[0], a[1], every, title)["said"])


def film(trace, out, every=2, title="", stills=True, m=None):
    """One maze trace as a film (and its first, middle and last stills): {"runs", "passed", "steps", "said"}."""
    m = m or montage()
    tr = m.Trace(trace)
    c = tr.champs[0]
    # The run to follow: a pass, the longest-lived first among them; else the best fitness.
    passes = [d for d in range(tr.nd) if c["outcome"][d] == 1]
    d = min(passes, key=lambda k: c["lasted"][k]) if passes else max(range(tr.nd), key=lambda k: c["fit"][k])
    # The whole maze in the frame, still: the arena 590 pixels high, under the caption.
    film = m.Film(tr, 0, d, None, m.W * (tr.arena + 14.0) / m.H, 3.0)
    film.fixed = (tr.arena / 2.0, tr.arena / 2.0 - 3.0)
    W, H = m.W, m.H
    stills = os.path.splitext(out)[0]
    cap = stills + "-cap.png"
    words = "%s  ·  %d of %d runs passed  ·  following run %d (%s)" % (title or "the maze", len(passes), tr.nd, d + 1, "passed" if c["outcome"][d] == 1 else "did not pass")
    m.label_png(cap, words, 22, font=m.FONT)
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", "15", "-i", "-",
                          "-i", cap, "-filter_complex", "[0][1]overlay=(W-w)/2:16"] + m.X264 + [out], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    last = c["lasted"][d]
    keep = {0: "first", last // 2: "middle", max(0, last - 1): "last"}
    for t in range(0, max(1, last), every):
        fr = film.frame(t, 0.0, m.flashes(tr, 0, d, t, 0.0))
        p.stdin.write(fr)
        near = min(keep, key=lambda k: abs(k - t))
        if stills and abs(near - t) < every and keep.get(near):
            ppm = "%s-%s.ppm" % (stills, keep[near])
            with open(ppm, "wb") as f:
                f.write(b"P6\n%d %d\n255\n" % (W, H) + bytes(fr))
            subprocess.run(["magick", ppm, cap, "-gravity", "north", "-geometry", "+0+16", "-composite", ppm[:-4] + ".png"], check=True)
            os.remove(ppm)
            keep[near] = None
    p.stdin.close()
    err = p.stderr.read().decode(errors="replace")
    if p.wait() != 0:
        raise SystemExit("ffmpeg: %s" % err[-300:])
    os.remove(cap)
    return {"runs": tr.nd, "passed": len(passes), "steps": last,
            "said": "%s: %d runs, %d passed, followed run %d over %d steps" % (out, tr.nd, len(passes), d + 1, last)}


if __name__ == "__main__":
    main(sys.argv[1:])
