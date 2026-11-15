#!/usr/bin/env python3
"""hearth_film: the film of *The Fleet as the Hearth* (docs/hearth-lab-report.md), by docs/film-directive.md.

    python3 tools/report/hearth_film.py list                  the scenes and when each begins
    python3 tools/report/hearth_film.py still T OUT.png       the frame at T seconds, to look at one
    python3 tools/report/hearth_film.py film OUT.mp4 [DIR]    every frame (kept in DIR, so a run stopped is taken up), then the film
    python3 tools/report/hearth_film.py page                  docs/hearth-film.html and a still of each step
    python3 tools/report/hearth_film.py youtube MASTER.mp4    the kit: output/youtube/hearth/ (not the repository)

The storyboard is docs/hearth/storyboard.json and the map, the steps, the title, the whole, the borders and
the close are drawn by process_film.py as they are for any storyboard. This file is what process_film.py
--story cannot draw for this report, and nothing else:

THE COLD OPEN. This report's own: the fleet's 1,228 W with a bar a machine, and the room read by nothing
(sections II and VIII); what a computation costs when its heat is wanted (section III); and the Watts panel
of Orrery's Heat, the picture itself, with the line that says the room is read by nothing.

DONE, AND NOT DONE. Where the process film draws the one shape every border shares, this one draws the
report's last section as two columns: what was measured and built, and what was not.

THE RENDER. This Mac is the fleet's coordinator, so frames are drawn by two processes, not one a core
(FILM_PROCS), and kept as they are made.

Every number drawn here is read from the storyboard's "hook" and "pattern", which are copied from the report
and from its picture docs/hearth/heat-watts.png.
"""
import base64
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
if "--story" not in sys.argv:
    sys.argv += ["--story", os.path.join(ROOT, "docs", "hearth", "storyboard.json")]
import film  # noqa: E402
import process_film as pf  # noqa: E402
from film import seg, appear, out  # noqa: E402
from process_film import text, write, wrap, polyline, head, along, W, BG, INK, DIM, FAINT, PANEL, MAIN, CPU, GPU, LINE, RED, SERIF, MONO  # noqa: E402

HOOK = pf.HOOK


def plate(x, y, w, h, op, col=FAINT, fill=PANEL):
    """What words stand on."""
    return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="14" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-opacity="%.3f" stroke-width="2"/>' % (x, y, w, h, fill, 0.96 * op, col, op)


def hook1_scene(t, sc):
    """The fleet's watts at the wall, a bar a machine; what reads the machines; what reads the room: nothing."""
    u, end, c = t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    b = text(120, 96, HOOK["at"] + "  ·  THE FLEET'S WATTS AT THE WALL", 22, DIM, weight=700, op=op, spacing=4)
    b += write(120, 250, "%s W" % format(HOOK["watts"], ","), 150, seg(u, 0.6, 1.8), CPU, weight=600, family=SERIF, op=op)
    b += write(700, 250, "into one house, all of it heat", 40, seg(u, 2.2, 4.0), INK, weight=500, op=op)
    for i, (name, watts) in enumerate(HOOK["machines"]):
        y, a = 318 + i * 54, 1.4 + i * 0.3
        g = seg(u, a, a + 1.0, out)
        b += text(120, y + 27, name, 22, INK, family=MONO, op=op * seg(u, a, a + 0.5))
        b += '<rect x="330" y="%d" width="%.1f" height="36" rx="5" fill="%s" fill-opacity="%.3f"/>' % (y, watts * 2.7 * g, CPU, op * 0.9)
        b += text(344 + watts * 2.7 * g, y + 27, "%d W" % watts, 22, CPU, family=SERIF, op=op * seg(u, a + 0.5, a + 1.0))
    for i, (at, big, small, col) in enumerate(((c[0], "every 5 s", "each Linux machine writes a line of its readings", MAIN),
                                               (c[1], "nothing", "reads the air of the house", RED))):
        o, y = op * seg(u, at, at + 0.7), 300 + i * 196
        b += plate(1290, y, 560, 176, o, col)
        b += write(1318, y + 92, big, 80, seg(u, at + 0.1, at + 0.9), col, weight=600, family=SERIF, op=op)
        b += text(1318, y + 142, small, 23, INK, op=o * seg(u, at + 0.6, at + 1.2))
    o = op * seg(u, c[2], c[2] + 0.8)
    b += plate(120, 760, 1160, 250, o, GPU)
    b += write(160, 950, str(HOOK["coldest"]), 190, seg(u, c[2] + 0.2, c[2] + 0.8), GPU, weight=600, family=SERIF, op=op)
    b += write(420, 846, "a disk in saskatchewan: the coldest reading in the fleet", 31, seg(u, c[2] + 0.8, c[2] + 2.6), INK, weight=600, op=op)
    b += write(420, 902, "The room is no warmer than that.", 31, seg(u, c[2] + 5.0, c[2] + 6.2), DIM, op=op)
    b += write(420, 948, "How much cooler is not known.", 31, seg(u, c[2] + 7.0, c[2] + 8.2), DIM, op=op)
    return b


def hook2_scene(t, sc):
    """Section III: cost = E x price x (1 - f / COP), and its three cases as the share of the electricity still paid."""
    u, end, c = t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    b = text(120, 96, "WHAT A COMPUTATION COSTS, WHEN THE HOUSE WANTS ITS HEAT", 22, DIM, weight=700, op=op, spacing=4)
    b += write(120, 200, HOOK["formula"], 62, seg(u, 1.0, 3.6), INK, weight=500, family=SERIF, op=op)
    y = 262
    for i, words in enumerate(HOOK["terms"]):
        b += text(120, y, words, 23, DIM, op=op * seg(u, 3.6 + i * 0.8, 4.4 + i * 0.8))
        y += 36
    for i, (case, col) in enumerate(zip(HOOK["cases"], (MAIN, LINE, RED))):
        x, y, a = 120 + i * 400, 400, c[i]
        o = op * seg(u, a, a + 0.7)
        b += plate(x, y, 370, 480, o, col)
        b += text(x + 28, y + 46, case["head"].upper(), 20, col, weight=700, op=o, spacing=2.5)
        b += text(x + 28, y + 82, case["sub"], 25, INK, op=o)
        top, full = y + 120, 320
        g = case["share"] * seg(u, a + 0.4, a + 1.6, out)
        b += '<rect x="%d" y="%d" width="70" height="%d" rx="6" fill="%s" fill-opacity="%.3f"/>' % (x + 28, top, full, FAINT, 0.55 * o)
        b += '<rect x="%d" y="%.1f" width="70" height="%.1f" rx="6" fill="%s" fill-opacity="%.3f"/>' % (x + 28, top + full * (1 - g), full * g, col, o)
        b += text(x + 126, top + 24, "its electricity", 18, DIM, op=o)
        b += write(x + 126, top + 190, case["big"], 44, seg(u, a + 0.6, a + 1.6), col, weight=600, family=SERIF, op=op)
        for j, l in enumerate(wrap(case["small"], 22, 220)):
            b += text(x + 126, top + 232 + j * 29, l, 22, INK, op=o * seg(u, a + 1.4, a + 2.0))
    for j, l in enumerate(wrap(HOOK["missing"], 23, 1180)):
        b += text(120, 928 + j * 32, l, 23, DIM, op=op * seg(u, c[2] + 3.0, c[2] + 3.8))
    return b


_PIC = {}


def picture():
    if "uri" not in _PIC:
        _PIC["uri"] = "data:image/png;base64," + base64.b64encode(open(os.path.join(pf.OUT_DIR, HOOK["picture"]), "rb").read()).decode()
    return _PIC["uri"]


def hook3_scene(t, sc):
    """The report's own picture of the Watts panel; then the line in it that says the room is read by nothing."""
    u, end, c = t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    k, ix, iy = 0.80, 60, 124
    b = text(60, 86, "ORRERY, HEAT, THE WATTS PANEL, " + HOOK["at"], 22, DIM, weight=700, op=op, spacing=4)
    b += '<image x="%d" y="%d" width="%d" height="%d" href="%s" opacity="%.3f"/>' % (ix, iy, 1400 * k, 860 * k, picture(), op * seg(u, 0.3, 1.2))
    b += '<rect x="%d" y="%d" width="%d" height="%d" fill="none" stroke="%s" stroke-opacity="%.3f"/>' % (ix, iy, 1400 * k, 860 * k, FAINT, op)
    wx, wy, ww, wh = [v * k for v in HOOK["room_line"]]
    per, pd = 2 * (ww + wh), seg(u, c[0], c[0] + 1.4)
    if pd > 0:
        b += '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="5" fill="none" stroke="%s" stroke-width="4" stroke-opacity="%.3f" stroke-dasharray="%.1f %.1f"/>' % (ix + wx, iy + wy, ww, wh, LINE, op, per * pd, per)
    for i, (at, head_, words, col) in enumerate(((1.6, "the fleet's heat", "%s W from %d machines, a bar a machine" % (format(HOOK["watts"], ","), len(HOOK["machines"])), CPU),
                                                 (c[0] + 0.4, "the room", "Read by nothing.", RED),
                                                 (c[1], "three mesh radios", "Asked what they are. None gave a thermometer.", LINE))):
        o, y = op * seg(u, at, at + 0.7), 124 + i * 196
        b += plate(1220, y, 640, 176, o, col)
        b += text(1246, y + 50, head_.upper(), 20, col, weight=700, op=o, spacing=2.5)
        for j, l in enumerate(wrap(words, 28, 590)):
            b += text(1246, y + 96 + j * 38, l, 28, INK, weight=500, op=o)
    b += write(60, 900, "The side that is measured, the side that is not,", 42, seg(u, c[2], c[2] + 2.4), INK, weight=500, family=SERIF, op=op)
    b += write(60, 960, "and what would read it.", 42, seg(u, c[2] + 2.6, c[2] + 3.8), INK, weight=500, family=SERIF, op=op)
    return b


def ledger_scene(t, sc):
    """The report's section X, and what its abstract says stands: two columns, each row at its cue."""
    u, cu = t - sc["t0"], sc["cues"]
    op = appear(u, 0.4, sc["t1"] - sc["t0"], 0.7)
    b = text(W / 2, 120, "What was done, and what was not", 64, INK, "middle", 700, op=op)
    cols = {"measured": (MAIN, 78), "built": (MAIN, 78), "not done": (RED, 990)}
    seen = {78: 0, 990: 0}
    for i, (name, words) in enumerate(pf.PATTERN):
        col, x = cols[name]
        a = cu[min(i, len(cu) - 1)]
        o = op * seg(u, a, a + 0.8)
        y = 180 + seen[x] * 146 + 14 * (1 - seg(u, a, a + 0.8, out))
        seen[x] += 1
        b += plate(x, y, 852, 132, o, col)
        b += text(x + 24, y + 36, name.upper(), 18, col, weight=700, op=o, spacing=2.5)
        for j, l in enumerate(wrap(words, 25, 800)):
            b += text(x + 24, y + 74 + j * 32, l, 25, INK, weight=500, op=o)
    return b


def big_arrow(a, b, col, p, op, label, off=0):
    """process_film's, but an arrow that runs level carries its words above it and not on it."""
    if a[1] != b[1]:
        return _big_arrow(a, b, col, p, op, label, off)
    if op <= 0.004:
        return ""
    q, part, d = along([a, b], p)
    return polyline(part, col, 9, op) + head(q, d, col, 30, op) + text((a[0] + b[0]) / 2, a[1] - 26, label, 24, INK, "middle", 600, op=op * seg(p, 0.6, 1.0))


_big_arrow = pf.big_arrow
pf.hook1_scene, pf.hook2_scene, pf.hook3_scene, pf.pattern_scene, pf.big_arrow = hook1_scene, hook2_scene, hook3_scene, ledger_scene, big_arrow

# The page is process_film's, with what it says of the process film changed to what is true of this one.
for old, new in (
        ("Orreryq &middot; treadcore &middot; 13 November 2026", "Orreryq &middot; the fleet &middot; 15 November 2026"),
        ('<p class="lede">One block diagram, walked arrow by arrow, from the outside in.',
         '<p class="lede">The film of the lab report <a href="hearth-lab-report.html">The Fleet as the Hearth</a>: the fleet\'s heat, three mesh radios and the house as one block diagram, walked arrow by arrow, from the outside in. No room temperature is read yet, the radios gave no thermometer, the CPU figures are one step each and no controller is built; the film says what the report says and no more.'),
        ("drawn by two scripts:", "drawn by three scripts:"),
        ("and the frames render a core each.", "and the frames render in any order: here by two processes, the Mac being the fleet's coordinator."),
        ("how a block diagram is walked. Another process is another storyboard.",
         "how a block diagram is walked; and <code>tools/report/hearth_film.py</code>, this report's own opening and its two columns of what was done and what was not. Every number in it is the report's."),
        ("a true thing that should not be possible: ten changes that each tested as a gain and together measured as nothing; then why (every trial the search made, lying on the curve of pure chance); then the question the film answers.",
         "a true thing that should not be possible: a fleet that puts 1,228 W into a house and writes down its own temperatures every five seconds, in a room whose air nothing reads; then why it matters (what a computation costs when the house wanted its heat); then the report's own picture of the Watts panel, and that three radios gave no thermometer."),
        ("names three territories, then the four borders and their price, then goes inside one loop at a time.",
         "names four territories, then the four borders and what crosses each, then goes inside: the machines' side, the three radios, and the house."),
        ("A step runs 12 to 24 seconds:", "A step runs 18 to 32 seconds:"),
        ("<dt>Pace</dt>", "<dt>Done, and not done</dt><dd>Before the close, two columns: what was measured and built, and what was not. The room's temperature, the radios' thermometer and the controller are in the second.</dd>\n<dt>Pace</dt>")):
    assert old in pf.PAGE, old
    pf.PAGE = pf.PAGE.replace(old, new)


def _one(i):
    png = os.path.join(_one.dir, "f%05d.png" % i)
    if not os.path.exists(png):
        film.render(pf.frame(i / pf.FPS), png + ".part", W, pf.H)
        os.rename(png + ".part", png)


def render(dst, frames):
    """Every frame, two processes (FILM_PROCS), each kept in `frames` so a run that was stopped is taken up; then the film and its poster."""
    import multiprocessing
    import shutil
    os.makedirs(frames, exist_ok=True)
    n = int(pf.LENGTH * pf.FPS)
    _one.dir = frames
    with multiprocessing.get_context("fork").Pool(int(os.environ.get("FILM_PROCS", "2"))) as pool:
        pool.map(_one, range(n), chunksize=24)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(pf.FPS), "-i", os.path.join(frames, "f%05d.png"), "-frames:v", str(n), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "23", "-preset", "slow", "-tune", "animation", "-movflags", "+faststart", dst], check=True)
    shutil.copy(os.path.join(frames, "f%05d.png" % int((pf.WH["t1"] - 3.0) * pf.FPS)), os.path.join(os.path.dirname(os.path.abspath(dst)), "poster.png"))
    print("%s: %d frames, %s" % (dst, n, film.clock(pf.LENGTH)))


def main(a):
    if a[:1] == ["film"] and len(a) >= 2:
        render(a[1], a[2] if len(a) > 2 else os.path.splitext(a[1])[0] + "-frames")
    elif a[:1] == ["film"]:
        sys.exit(__doc__)        # the master is 1080p and is not kept in the repository: it is given a place
    else:
        pf.main(a)


if __name__ == "__main__":
    main(sys.argv[1:])
