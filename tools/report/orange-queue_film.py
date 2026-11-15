#!/usr/bin/env python3
"""orange-queue_film: the film of *The Orange Queue* (docs/orange-queue-lab-report.md), by docs/film-directive.md.

    python3 tools/report/orange-queue_film.py list                  the scenes and when each begins
    python3 tools/report/orange-queue_film.py still T OUT.png       the frame at T seconds, to look at one
    python3 tools/report/orange-queue_film.py film OUT.mp4 [DIR]    every frame (kept in DIR, so a run stopped is taken up), then the film
    python3 tools/report/orange-queue_film.py page                  docs/orange-queue-film.html and a still of each step
    python3 tools/report/orange-queue_film.py youtube MASTER.mp4    the kit: output/youtube/orange-queue/ (not the repository)

The storyboard is docs/orange-queue/storyboard.json and the map, the steps, the title, the whole, the border
and the close are drawn by process_film.py as they are for any storyboard. This file is what process_film.py
--story cannot draw for this report, and nothing else:

THE COLD OPEN. process_film's three opening scenes are the process report's own charts (ten gains, the curve
of chance). This report's are its own: three cards at 100% that finished nothing (section VI), Table III as
bars with the 123 closes and the 276 put-backs, and Fig. 1, the Timeline of the day, the picture itself.

PROVED, AND NOT PROVED. Where the process film draws the one shape every border shares, this one draws the
report's two ledgers (sections XII and XIII): what a check has shown, what none has, and the cause, not found.

THE RENDER. This Mac is the fleet's coordinator, so frames are drawn by two processes, not one a core
(FILM_PROCS), and kept as they are made.

Every number drawn here is read from the storyboard's "hook" and "pattern", which are copied from the report.
"""
import base64
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
if "--story" not in sys.argv:
    sys.argv += ["--story", os.path.join(ROOT, "docs", "orange-queue", "storyboard.json")]
import film  # noqa: E402
import process_film as pf  # noqa: E402
from film import seg, appear, out, back, clamp, lerp  # noqa: E402
from process_film import text, write, wrap, polyline, W, H, BG, INK, DIM, FAINT, PANEL, MAIN, CPU, GPU, LINE, RED, SERIF, MONO  # noqa: E402

HOOK, STORY = pf.HOOK, pf.STORY


def plate(x, y, w, h, op, col=FAINT, fill=PANEL):
    """What words stand on."""
    return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="14" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-opacity="%.3f" stroke-width="2"/>' % (x, y, w, h, fill, 0.96 * op, col, op)


def hook1_scene(t, sc):
    """Three cards at 100%, the copies on each, and what they finished: nothing."""
    u, end, c = t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    b = text(120, 96, HOOK["at"] + "  ·  THREE GRAPHICS CARDS", 22, DIM, weight=700, op=op, spacing=4)
    for i, (name, procs) in enumerate(HOOK["cards"]):
        x, y, w = 120 + i * 400, 170, 360
        a = 1.0 + i * 0.5
        g = seg(u, a, a + 1.6)
        b += plate(x, y, w, 330, op * seg(u, a - 0.4, a + 0.2), GPU)
        b += text(x + 28, y + 52, name, 34, INK, weight=600, op=op * seg(u, a - 0.2, a + 0.4))
        b += text(x + 28, y + 84, "nvidia-smi", 17, DIM, family=MONO, op=op * seg(u, a - 0.2, a + 0.4))
        b += '<rect x="%d" y="%d" width="%d" height="26" rx="6" fill="%s" fill-opacity="%.3f"/>' % (x + 28, y + 196, w - 56, FAINT, 0.6 * op)
        b += '<rect x="%d" y="%d" width="%.1f" height="26" rx="6" fill="%s" fill-opacity="%.3f"/>' % (x + 28, y + 196, (w - 56) * g, GPU, op)
        b += text(x + 28, y + 172, "%d%%" % round(100 * g), 76, GPU, weight=600, family=SERIF, op=op * seg(u, a, a + 0.4))
        o = op * seg(u, c[0] + i * 0.3, c[0] + 0.7 + i * 0.3)
        b += text(x + 28, y + 268, "%d crucible processes" % procs, 24, INK, op=o)
        b += text(x + 28, y + 300, "busy the whole evening", 19, DIM, op=o)
    o = op * seg(u, c[1], c[1] + 0.8)
    b += plate(120, 560, 1160, 300, o, RED)
    b += write(170, 790, "0", 240, seg(u, c[1] + 0.2, c[1] + 0.8), RED, weight=600, family=SERIF, op=op)
    b += write(340, 680, "segments finished since %s" % HOOK["since"], 52, seg(u, c[1] + 0.8, c[1] + 2.4), INK, weight=600, op=op)
    b += write(340, 744, "seven and a half hours, on three cards", 34, seg(u, c[1] + 2.6, c[1] + 4.2), DIM, op=op)
    return b


def hook2_scene(t, sc):
    """Table III as bars: each hour's jobs done and jobs put back; then the closes, the put-backs, the rate."""
    u, end, c = t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    hours, done, backs = HOOK["hours"], HOOK["done"], HOOK["back"]
    x0, base, k, slot, bw = 150, 820, 5.6, 98, 38
    b = text(120, 96, "EACH HOUR OF 14 TO 15 NOVEMBER, FROM THE KEEPER'S EVENTS", 22, DIM, weight=700, op=op, spacing=4)
    b += '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-opacity="%.3f" stroke-width="2"/>' % (x0 - 20, base, x0 + slot * len(hours) + 10, base, DIM, op)
    grow = c[2] - c[1]
    for i, hr in enumerate(hours):
        x = x0 + i * slot
        a = c[0] - 2.6 + i * 0.2
        g = seg(u, a, a + 0.9, out)
        b += '<rect x="%d" y="%.1f" width="%d" height="%.1f" rx="4" fill="%s" fill-opacity="%.3f"/>' % (x + 8, base - done[i] * k * g, bw, done[i] * k * g, MAIN, op * 0.9)
        b += text(x + 8 + bw / 2, base - done[i] * k * g - 10, str(done[i]), 18, MAIN, "middle", family=SERIF, op=op * seg(u, a + 0.5, a + 1.0))
        b += text(x + 8 + bw, base + 34, hr + ":00", 18, DIM, "middle", family=MONO, op=op)
        if backs[i]:
            a2 = c[1] + 0.6 + (i - 3) * min(0.45, (grow - 1.6) / 8.0)
            g2 = seg(u, a2, a2 + 0.9, out)
            b += '<rect x="%d" y="%.1f" width="%d" height="%.1f" rx="4" fill="%s" fill-opacity="%.3f"/>' % (x + 8 + bw + 4, base - backs[i] * k * g2, bw, backs[i] * k * g2, CPU, op * 0.95)
            b += text(x + 8 + bw + 4 + bw / 2, base - backs[i] * k * g2 - 10, str(backs[i]), 18, CPU, "middle", family=SERIF, op=op * seg(u, a2 + 0.5, a2 + 1.0))
    b += '<rect x="%d" y="%d" width="18" height="18" rx="3" fill="%s" fill-opacity="%.3f"/>' % (x0, base + 64, MAIN, op) + text(x0 + 28, base + 80, "jobs done", 22, INK, op=op)
    o1 = op * seg(u, c[1], c[1] + 0.6)
    b += '<rect x="%d" y="%d" width="18" height="18" rx="3" fill="%s" fill-opacity="%.3f"/>' % (x0 + 190, base + 64, CPU, o1) + text(x0 + 218, base + 80, "jobs put back: ssh failed (255)", 22, INK, op=o1)
    # 18:42, the first drop: 42 minutes into the fourth hour drawn
    xd = x0 + 3 * slot + slot * 42 / 60.0
    od = op * seg(u, c[0], c[0] + 0.6)
    b += polyline([(xd, base), (xd, base - 560 * seg(u, c[0], c[0] + 1.0))], LINE, 3, od, True)
    b += write(xd + 14, base - 540, "%s  the first drop" % HOOK["first_drop"], 24, seg(u, c[0] + 0.6, c[0] + 1.8), LINE, weight=600, op=op)
    # the figures, on plates of their own to the right
    px = 1290
    for i, (at, big, small, col) in enumerate(((c[0] + 1.6, str(HOOK["closes"]), "times the Mac closed a shared connection", LINE),
                                               (c[1] + 1.0, str(HOOK["put_back"]), "times a job went back on the queue", CPU),
                                               (c[3], "%d → %d" % (HOOK["rate_before"], HOOK["rate_after"]), "jobs done an hour", MAIN))):
        o, y = op * seg(u, at, at + 0.7), 170 + i * 196
        b += plate(px, y, 560, 176, o, col)
        b += write(px + 28, y + 92, big, 80, seg(u, at + 0.1, at + 0.9), col, weight=600, family=SERIF, op=op)
        b += text(px + 28, y + 142, small, 23, INK, op=o * seg(u, at + 0.6, at + 1.2))
    o2 = op * seg(u, c[2], c[2] + 0.5)
    b += plate(x0 + 3 * slot + 90, 136, 560, 64, o2, LINE, BG)
    b += write(x0 + 3 * slot + 112, 178, "The first copy was never stopped.", 30, seg(u, c[2] + 0.1, c[2] + 1.5), LINE, weight=600, op=op)
    return b


_PIC = {}


def picture():
    if "uri" not in _PIC:
        _PIC["uri"] = "data:image/png;base64," + base64.b64encode(open(os.path.join(pf.OUT_DIR, HOOK["picture"]), "rb").read()).decode()
    return _PIC["uri"]


def hook3_scene(t, sc):
    """Fig. 1 of the report, the picture itself: the day in blue and green, then the wall."""
    u, end, c = t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    k, ix, iy = 0.80, 60, 124
    b = text(60, 86, "THE TIMELINE, DAY ZOOM, AS ORRERY DREW IT AT 01:47", 22, DIM, weight=700, op=op, spacing=4)
    b += '<image x="%d" y="%d" width="%d" height="%d" href="%s" opacity="%.3f"/>' % (ix, iy, 1400 * k, 860 * k, picture(), op * seg(u, 0.3, 1.2))
    b += '<rect x="%d" y="%d" width="%d" height="%d" fill="none" stroke="%s" stroke-opacity="%.3f"/>' % (ix, iy, 1400 * k, 860 * k, FAINT, op)
    wx, wy, ww, wh = [v * k for v in HOOK["wall"]]
    per, pd = 2 * (ww + wh), seg(u, c[0], c[0] + 1.4)
    if pd > 0:
        b += '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="6" fill="none" stroke="%s" stroke-width="4" stroke-opacity="%.3f" stroke-dasharray="%.1f %.1f"/>' % (ix + wx, iy + wy, ww, wh, LINE, op, per * pd, per)
    px = 1220
    for i, (at, head_, words, col) in enumerate(((1.6, "blue and green", "first reads and reads on: work", MAIN),
                                                 (c[0] + 0.4, "the orange-red wall", "jobs that failed or were sent back, from 18:40 on every row at once", RED),
                                                 (c[1], "the cause", "What closed the connections is not found.", LINE))):
        o, y = op * seg(u, at, at + 0.7), 124 + i * 196
        b += plate(px, y, 640, 176, o, col)
        b += text(px + 26, y + 50, head_.upper(), 20, col, weight=700, op=o, spacing=2.5)
        for j, l in enumerate(wrap(words, 28, 590)):
            b += text(px + 26, y + 96 + j * 38, l, 28, INK, weight=500, op=o)
    b += write(60, 900, "The fault that turned a nuisance into seven lost hours,", 42, seg(u, c[2], c[2] + 2.2), INK, weight=500, family=SERIF, op=op)
    b += write(60, 960, "and what was built after.", 42, seg(u, c[2] + 2.4, c[2] + 3.6), INK, weight=500, family=SERIF, op=op)
    return b


def ledger_scene(t, sc):
    """What a check has shown and what none has: the report's "Proved" and "Not proved", sections XII and XIII."""
    u, cu = t - sc["t0"], sc["cues"]
    op = appear(u, 0.4, sc["t1"] - sc["t0"], 0.7)
    b = text(W / 2, 130, "Proved, and not proved", 64, INK, "middle", 700, op=op)
    cols = {"proved": (MAIN, 78), "not proved": (CPU, 990), "not found": (LINE, 990)}
    seen = {78: 0, 990: 0}
    for i, (name, words) in enumerate(pf.PATTERN):
        col, x = cols[name]
        a = cu[min(i, len(cu) - 1)]
        o = op * seg(u, a, a + 0.8)
        y = 210 + seen[x] * 176 + 14 * (1 - seg(u, a, a + 0.8, out))
        seen[x] += 1
        b += plate(x, y, 852, 156, o, col)
        b += text(x + 24, y + 40, name.upper(), 18, col, weight=700, op=o, spacing=2.5)
        for j, l in enumerate(wrap(words, 25, 800)):
            b += text(x + 24, y + 80 + j * 33, l, 25, INK, weight=500, op=o)
    return b


pf.hook1_scene, pf.hook2_scene, pf.hook3_scene, pf.pattern_scene = hook1_scene, hook2_scene, hook3_scene, ledger_scene

# The page is process_film's, with what it says of the process film changed to what is true of this one.
for old, new in (
        ("Orreryq &middot; treadcore &middot; 13 November 2026", "Orreryq &middot; the fleet &middot; 15 November 2026"),
        ('<p class="lede">One block diagram, walked arrow by arrow, from the outside in.',
         '<p class="lede">The film of the lab report <a href="orange-queue-lab-report.html">The Orange Queue</a>: the night of 14 to 15 November 2026 as one block diagram, walked arrow by arrow, from the outside in. What closed the connections that night was not found; the film says what the report says and no more.'),
        ("drawn by two scripts:", "drawn by three scripts:"),
        ("and the frames render a core each.", "and the frames render in any order: here by two processes, the Mac being the fleet's coordinator."),
        ("how a block diagram is walked. Another process is another storyboard.",
         "how a block diagram is walked; and <code>tools/report/orange-queue_film.py</code>, this report's own opening and its ledger of what is proved. Every number in it is the report's."),
        ("a true thing that should not be possible: ten changes that each tested as a gain and together measured as nothing; then why (every trial the search made, lying on the curve of pure chance); then the question the film answers.",
         "a true thing that should not be possible: three graphics cards 100% busy for seven and a half hours that finished no segment; then why (each hour's jobs done and jobs put back, with the 123 closes and the 276 put-backs); then the report's own picture of the day, and that the cause is not found."),
        ("names three territories, then the four borders and their price, then goes inside one loop at a time.",
         "names three territories, then the one border and what crosses it, then goes inside: an ordinary day, the night, and what was built after."),
        ("<dt>Pace</dt>", "<dt>The ledger</dt><dd>Before the close, two columns: what a check has shown, and what none has. The cause of the closes is in the second.</dd>\n<dt>Pace</dt>")):
    assert old in pf.PAGE, old
    pf.PAGE = pf.PAGE.replace(old, new)


def _one(i):
    png = os.path.join(_one.dir, "f%05d.png" % i)
    if not os.path.exists(png):
        film.render(pf.frame(i / pf.FPS), png + ".part", W, H)
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
