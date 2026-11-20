#!/usr/bin/env python3
"""orreryq_film: the film of *The Orrery Q Process* (docs/orreryq-lab-report.md), by docs/film-directive.md.

    python3 tools/report/orreryq_film.py list                  the scenes and when each begins
    python3 tools/report/orreryq_film.py still T OUT.png       the frame at T seconds
    python3 tools/report/orreryq_film.py stills DIR            one frame from the middle of every scene, to look at
    python3 tools/report/orreryq_film.py film OUT.mp4 [DIR]    every frame (kept in DIR), then the film
    python3 tools/report/orreryq_film.py page                  docs/orreryq-film.html, its captions and its narration
    python3 tools/report/orreryq_film.py youtube MASTER.mp4    the kit: output/youtube/orreryq/ (not the repository)

OUTSIDE IN, AS A CAMERA. The report goes from the whole to one generation, and so does the film: the orrery
drawn turning, then the report's figures and pictures of Orrery, each shown whole and then entered. A `zoom`
scene is one picture and a list of stops; at each stop's cue the camera travels, on an ease in and out, from
where it stood to the stop's rectangle, rings it, and a plate under the picture says what is there. Every
frame is a function of its time: the view at t is worked out from the stops whose cues have passed.

THE KINDS OF SCENE:
    orrery    the centre and its three orbits drawn turning; jobs go out along the spokes and come back
    zoom      a picture, whole, then entered stop by stop (the report's figures, and Orrery's own pages)
    cards, table, calc, act, title, end
              hearth-regulation_film.py's, used as they are (imported, and pointed at this film's storyboard)
    ledger2   two columns, what went well and where to step in

Every number is the storyboard's, copied from the report. The look, the teleprompt, the title, the close and
its credits, the captions and the kit are process_film.py's and film.py's.
"""
import importlib.util
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import json  # noqa: E402
import film  # noqa: E402
import process_film as pf  # noqa: E402
from film import seg, appear, out, smooth, clock  # noqa: E402
from process_film import text, write, wrap, W, H, BG, INK, DIM, FAINT, PANEL, MAIN, CPU, GPU, LINE, RED  # noqa: E402

# The slide kinds of the film before this one. Loading it sets process_film to its own storyboard; this one's
# is set after, and its pictures are read from this film's folder.
_spec = importlib.util.spec_from_file_location("hearth_regulation_film", os.path.join(HERE, "hearth-regulation_film.py"))
hr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hr)

OUT_DIR = os.path.join(ROOT, "docs", "orreryq")
STORY = json.load(open(os.path.join(OUT_DIR, "storyboard.json")))
SLUG = STORY["slug"]
hr.OUT_DIR = OUT_DIR
COL = hr.COL


def timeline():
    tl = film.Timeline(STORY.get("wpm", 150), pf.LEAD, pf.TAIL)
    for d in STORY["scenes"]:
        tl.say(d["kind"], d["say"], 12.0 if d["kind"] == "end" else 0.0, d=d)
    return tl


TL = timeline()
SCENES, LENGTH = TL.scenes, TL.t
POSTER_T = next(s["t0"] for s in SCENES if s["d"]["id"] == STORY["poster"]) + 6.0


def chapters():
    return [(s["t0"], s["d"]["name"], None) for s in SCENES]


pf.STORY, pf.TL, pf.SCENES, pf.LENGTH, pf.SLUG, pf.OUT_DIR, pf.WPM, pf.STEPS, pf.chapters = STORY, TL, SCENES, LENGTH, SLUG, OUT_DIR, TL.wpm, [], chapters
hr.STORY, hr.TL, hr.SCENES, hr.LENGTH, hr.SLUG = STORY, TL, SCENES, LENGTH, SLUG


# ---- zoom: a picture, entered ----------------------------------------------------------------------------------

AREA = (40, 104, 1840, 640)       # where the picture is shown; the words' plate and the teleprompt are under it


def fit(view):
    """Scale and offset that put the picture's rectangle `view` in the middle of AREA, whole."""
    ax, ay, aw, ah = AREA
    x, y, w, h = view
    k = min(aw / w, ah / h)
    return k, ax + (aw - w * k) / 2 - x * k, ay + (ah - h * k) / 2 - y * k


def lerp4(a, b, p):
    return [u + (v - u) * p for u, v in zip(a, b)]


def zoom_scene(t, sc):
    """The picture whole, then each stop at its cue: the camera travels there in 1.6 s, rings it, and its words
    stand on the plate below until the next stop."""
    d, u, end, c = sc["d"], t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    pw, ph = d["size"]
    whole = [0, 0, pw, ph]
    views, prev, now_i = [whole], whole, -1
    for i, s in enumerate(d["stops"]):
        a = hr.at(c, s, end)
        p = seg(u, a, a + 1.6, smooth)
        if p <= 0:
            break
        pad = s.get("pad", 0.12)
        x, y, w, h = s["r"]
        target = [x - w * pad, y - h * pad, w * (1 + 2 * pad), h * (1 + 2 * pad)]
        prev = lerp4(prev, target, p)
        now_i = i
    k, ox, oy = fit(prev)
    ax, ay, aw, ah = AREA
    push = 1.0 + 0.015 * seg(u, 0, end)          # never quite still
    b = text(40, 78, d["head"], 21, DIM, weight=700, op=op, spacing=3.5)
    b += '<clipPath id="za"><rect x="%d" y="%d" width="%d" height="%d"/></clipPath>' % AREA
    cx, cy = ax + aw / 2, ay + ah / 2
    b += '<g clip-path="url(#za)"><g transform="translate(%.2f %.2f) scale(%.4f) translate(%.2f %.2f)">' % (cx, cy, push, -cx, -cy)
    b += '<image x="%.1f" y="%.1f" width="%.1f" height="%.1f" href="%s" opacity="%.3f"/>' % (ox, oy, pw * k, ph * k, hr.picture(d["file"]), op * seg(u, 0.2, 1.0))
    if now_i >= 0:
        s = d["stops"][now_i]
        a = hr.at(c, s, end)
        x, y, w, h = s["r"]
        b += hr.ring(ox + x * k - 4, oy + y * k - 4, w * k + 8, h * k + 8, seg(u, a + 1.2, a + 2.4), op, COL[s.get("col", "line")])
    b += '</g></g>'
    b += '<rect x="%d" y="%d" width="%d" height="%d" fill="none" stroke="%s" stroke-opacity="%.3f"/>' % (ax, ay, aw, ah, FAINT, op)
    # the plate for the stop being told, bottom left, beside the teleprompt
    if now_i >= 0:
        s = d["stops"][now_i]
        a = hr.at(c, s, end)
        o = op * seg(u, a + 0.4, a + 1.1)
        b += hr.plate(40, 772, 1286, 266, o, COL[s.get("col", "line")])
        b += text(66, 812, s["head"].upper(), 19, COL[s.get("col", "line")], weight=700, op=o, spacing=2.5)
        b += hr.lines(66, 856, s["words"], 27, 1230, op=o, lead=1.34, weight=500)
    elif d.get("lede"):
        o = op * seg(u, 0.8, 1.6)
        b += hr.plate(40, 772, 1286, 266, o, FAINT)
        b += hr.lines(66, 830, d["lede"], 30, 1230, op=o, lead=1.34, weight=500, family=pf.SERIF)
    return b


# ---- orrery: the centre and its orbits, turning ---------------------------------------------------------------

def orrery_scene(t, sc):
    """The Mac at the centre; housekeeping, CPU lanes and CUDA islands on three orbits, each turning at its own
    pace; a job goes out along a spoke and its answer comes back. At the cues the orbits are named in turn."""
    d, u, end, c = sc["d"], t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    cx, cy = 760, 470
    b = text(40, 78, d["head"], 21, DIM, weight=700, op=op, spacing=3.5)
    orbits = [(150, LINE, d["names"][0], 6, 0.050), (275, CPU, d["names"][1], 8, 0.022), (395, GPU, d["names"][2], 3, 0.011)]
    for j, (r, col, name, n, w) in enumerate(orbits):
        a = hr.at(c, {"cue": j}, end)
        lit = seg(u, a, a + 0.8)
        quiet = 1 - 0.5 * seg(u, hr.at(c, {"cue": j + 1}, end), hr.at(c, {"cue": j + 1}, end) + 0.8) if j < 2 else 1.0
        oo = op * seg(u, 0.4 + 0.5 * j, 1.2 + 0.5 * j)
        b += '<ellipse cx="%d" cy="%d" rx="%d" ry="%.1f" fill="none" stroke="%s" stroke-opacity="%.3f" stroke-width="%.1f" stroke-dasharray="3 8"/>' % (
            cx, cy, r, r * 0.8, col, oo * (0.35 + 0.5 * lit * quiet), 2 + 2 * lit * quiet)
        for i in range(n):
            ang = 2 * math.pi * i / n + w * t * 2 * math.pi / 6.0
            x, y = cx + r * math.cos(ang), cy + r * 0.8 * math.sin(ang)
            # a job: out along the spoke and back, each planet at its own phase
            ph = (t * (0.35 / (j + 1)) + i / n) % 1.0
            f = ph * 2 if ph < 0.5 else 2 - ph * 2
            jx, jy = cx + (x - cx) * f, cy + (y - cy) * f
            b += '<line x1="%d" y1="%d" x2="%.1f" y2="%.1f" stroke="%s" stroke-opacity="%.3f" stroke-width="1.2"/>' % (cx, cy, x, y, col, oo * 0.18)
            b += '<circle cx="%.1f" cy="%.1f" r="4" fill="%s" fill-opacity="%.3f"/>' % (jx, jy, col if ph < 0.5 else INK, oo * 0.9)
            if j == 2:
                b += '<rect x="%.1f" y="%.1f" width="30" height="20" rx="4" fill="%s" fill-opacity="%.3f"/>' % (x - 15, y - 10, col, oo)
            else:
                b += '<circle cx="%.1f" cy="%.1f" r="%d" fill="%s" fill-opacity="%.3f"/>' % (x, y, 8 if j == 0 else 15, col, oo)
        b += text(1220, 300 + j * 110, name[0], 30, col, weight=700, op=op * lit)
        b += text(1220, 340 + j * 110, name[1], 23, INK, op=op * lit)
    b += '<circle cx="%d" cy="%d" r="70" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-width="3" stroke-opacity="%.3f"/>' % (cx, cy, LINE, 0.16 * op, LINE, op)
    b += text(cx, cy - 6, "THE MAC", 24, LINE, "middle", 700, op=op)
    b += text(cx, cy + 22, "asks every question", 17, INK, "middle", op=op)
    a = hr.at(c, {"cue": 3}, end)
    b += hr.plate(40, 772, 1286, 266, op * seg(u, a, a + 0.8), LINE)
    b += hr.lines(66, 830, d["foot"], 30, 1230, op=op * seg(u, a + 0.3, a + 1.1), lead=1.34, weight=500, family=pf.SERIF)
    return b


def ledger2_scene(t, sc):
    """Two columns: what went well, and where to step in."""
    d, u, end, c = sc["d"], t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.4, end, 0.7)
    b = text(60, 104, d["title"], 56, INK, weight=700, op=op)
    for x, name, col, rows in ((60, d["left"], MAIN, d["good"]), (970, d["right"], LINE, d["step"])):
        for i, r in enumerate(rows):
            a = hr.at(c, r, end)
            o = op * seg(u, a, a + 0.8)
            y = 150 + i * 126 + 14 * (1 - seg(u, a, a + 0.8, out))
            b += hr.plate(x, y, 890, 116, o, col)
            b += text(x + 22, y + 30, name.upper(), 16, col, weight=700, op=o, spacing=2.5)
            b += hr.lines(x + 22, y + 60, r["words"], 22.5, 850, op=o, lead=1.28, weight=500)
    return b


OVER = dict(hr.OVER, zoom=zoom_scene, orrery=orrery_scene, ledger2=ledger2_scene)


def frame(t):
    sc = pf.scene_at(t)
    bar = '<rect x="0" y="%d" width="%.1f" height="4" fill="%s" fill-opacity="0.55"/>' % (H - 4, W * t / LENGTH, INK)
    return ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="%d" height="%d" viewBox="0 0 %d %d"><rect width="%d" height="%d" fill="%s"/>%s%s%s</svg>') % (
        W, H, W, H, W, H, BG, OVER[sc["kind"]](t, sc), pf.teleprompter(t, sc), bar)


pf.frame = frame
hr.frame = frame
hr.LENGTH, hr.POSTER_T = LENGTH, POSTER_T


def stills(dst):
    os.makedirs(dst, exist_ok=True)
    for i, s in enumerate(SCENES):
        t = s["t0"] + 0.7 * (s["t1"] - s["t0"])
        film.render(frame(t), os.path.join(dst, "s%02d-%s.png" % (i, s["d"]["id"])), W // 2, H // 2)
    print("%s: %d stills" % (dst, len(SCENES)))


def page():
    cards = "".join('<article class="step" style="--c:%s"><header><button class="seek" data-t="%.1f" aria-label="Play this scene in the film">&#9654; %s</button><h3>%s</h3></header>'
                    '<dl><dt>Narration</dt><dd class="say">%s</dd></dl></article>' % (
                        {"zoom": LINE, "orrery": LINE, "calc": GPU, "table": CPU, "ledger2": MAIN}.get(s["kind"], MAIN),
                        s["t0"], clock(s["t0"]), film.esc(s["d"]["name"]), film.esc(" ".join(s["words"]))) for s in SCENES)
    nav = "".join('<button data-t="%.1f"><span>%s</span>%s</button>' % (s["t0"], clock(s["t0"]), film.esc(s["d"]["name"])) for s in SCENES)
    words = film.captions(TL, lambda sc: sc["d"]["name"], OUT_DIR, STORY["title"])
    p = pf.PAGE
    body = """<p class="eyebrow">Orreryq &middot; the whole &middot; 19 November 2026</p>
<h1>The Orrery Q Process</h1>
<p class="lede">The film of the lab report <a href="orreryq-lab-report.html">The Orrery Q Process</a>, outside in: the orrery turning, the two learning loops, the application, the pages of the window entered one by one, then one CPU generation and one GPU generation followed from the first question to the last verdict, the net around the tank, the yardsticks, the watts and the room, and where to step in. The film is @LEN@ long and has no sound. Its narration, @WORDS@ words, scrolls in the corner at @WPM@ words a minute; the same words are the captions.</p>
<div class="stage"><video id="film" controls preload="metadata" playsinline poster="@SLUG@/poster.png" src="@SLUG@/film.mp4"><track kind="captions" srclang="en" label="Narration" src="@SLUG@/captions.vtt"></video><nav id="nav">@NAV@</nav></div>
<p class="how files">The narration as a script with its times: <a href="@SLUG@/teleprompt.txt">teleprompt.txt</a>. As captions: <a href="@SLUG@/captions.vtt">captions.vtt</a>.</p>
<h2>Every scene, in order</h2>
<p class="how">Each card is one scene and what is said over it. The button plays that scene above.</p>
@CARDS@
<h2>How the film is made</h2>
<p class="how">One file of words and numbers (<a href="@SLUG@/storyboard.json">storyboard.json</a>) drawn by <code>tools/report/film.py</code>, <code>process_film.py</code> (the look, the title, the close, the teleprompt, the kit), <code>hearth-regulation_film.py</code> (cards, tables, calculations) and <code>orreryq_film.py</code> (the camera that enters a picture, and the orrery turning).</p>
<dl class="made">
<dt>Outside in</dt><dd>Each picture is shown whole and then entered: the camera travels to the next thing named, on an ease in and out, and rings it while its words stand on a plate below.</dd>
<dt>The pictures</dt><dd>The report's figures, drawn by <code>orreryq_figs.py</code>, and Orrery's own pages, drawn by the program's <code>--frame</code> renderer from the live queue.</dd>
<dt>Not done</dt><dd>The film has no sound.</dd>
</dl>
"""
    html = (p[:p.index('<p class="eyebrow">')] + body + p[p.index("</main><script>"):]).replace("How the Game Learns", STORY["title"])
    html = html.replace("@NAV@", nav).replace("@CARDS@", cards).replace("@LEN@", clock(LENGTH)).replace("@WPM@", str(TL.wpm)).replace("@WORDS@", format(words, ",")).replace("@SLUG@", SLUG)
    dst = os.path.join(ROOT, "docs", "%s-film.html" % SLUG)
    open(dst, "w").write(html)
    print("%s: %d scenes, %d words, %s" % (dst, len(SCENES), words, clock(LENGTH)))


def _one(i):
    png = os.path.join(_one.dir, "f%05d.png" % i)
    if not os.path.exists(png):
        film.render(frame(i / pf.FPS), png + ".part", W, H)
        os.rename(png + ".part", png)


def render(dst, frames):
    """hearth-regulation_film's render, here so its worker is this module's (a process pool finds a function by its
    module's name, and the borrowed module has none it can import): every frame kept in `frames`, then the film."""
    import multiprocessing
    import shutil
    import subprocess
    os.makedirs(frames, exist_ok=True)
    n = int(LENGTH * pf.FPS)
    _one.dir = frames
    with multiprocessing.get_context("fork").Pool(int(os.environ.get("FILM_PROCS", "2"))) as pool:
        pool.map(_one, range(n), chunksize=24)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(pf.FPS), "-i", os.path.join(frames, "f%05d.png"), "-frames:v", str(n), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "23", "-preset", "slow", "-tune", "animation", "-movflags", "+faststart", dst], check=True)
    shutil.copy(os.path.join(frames, "f%05d.png" % int(POSTER_T * pf.FPS)), os.path.join(OUT_DIR, "poster.png"))
    print("%s: %d frames, %s" % (dst, n, clock(LENGTH)))


def main(a):
    if a[:1] == ["stills"] and len(a) > 1:
        stills(a[1])
    elif a[:1] == ["film"] and len(a) >= 2:
        render(a[1], a[2] if len(a) > 2 else os.path.splitext(a[1])[0] + "-frames")
    elif a[:1] == ["page"]:
        page()
    elif a[:1] in (["film"], ["youtube"]) and len(a) < 2:
        sys.exit(__doc__)
    else:
        pf.main(a)


if __name__ == "__main__":
    main(sys.argv[1:])
