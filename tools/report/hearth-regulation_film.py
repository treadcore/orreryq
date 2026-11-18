#!/usr/bin/env python3
"""hearth-regulation_film: the film of *Keeping the Room* (docs/hearth-regulation-lab-report.md), by docs/film-directive.md.

    python3 tools/report/hearth-regulation_film.py list                  the scenes and when each begins
    python3 tools/report/hearth-regulation_film.py still T OUT.png       the frame at T seconds, to look at one
    python3 tools/report/hearth-regulation_film.py film OUT.mp4 [DIR]    every frame (kept in DIR, so a run stopped is taken up), then the film
    python3 tools/report/hearth-regulation_film.py page                  docs/hearth-regulation-film.html, its captions and its narration
    python3 tools/report/hearth-regulation_film.py youtube MASTER.mp4    the kit: output/youtube/hearth-regulation/ (not the repository)

A SLIDESHOW, NOT A WALK. The report is a how-to, then a science, then a record, and has no one block diagram to
walk. So this film has no map, no camera and no arrows: it is the storyboard's scenes in order
(docs/hearth-regulation/storyboard.json, "scenes"), one idea a slide, each as long as its narration. The look,
the teleprompt, the title, the close and its credits, the captions and the YouTube kit are process_film.py's
and film.py's. process_film.py is imported with its own storyboard and then given this one's timeline.

THE KINDS OF SLIDE, each drawn from the scene's own data:

    cards     a heading, a line written on, rows of plates that appear at the narration's cues, and a foot
    picture   one of the report's pictures of Orrery shown whole; what the narration names is ringed at its
              cue (the rings are regions measured on the picture; tools/report/hearth-annotate.py has the
              marks' own places), with its number and its words on a plate beside it
    balance   equation (1) written out, then a row a symbol: what it is, where it comes from, and whether
              it is read, measured or not measured
    calc      one of the report's sample calculations: what is given, then a line at a cue
    table     rows that appear at cues
    ledger    two columns: what is done, and what is not
    cold2     the cold open's scale in degrees Fahrenheit: the target, the ceiling, where the room was held

Every number drawn is in the storyboard, where it was copied from the report or is in the report's pictures.
plate, lines, ring and cue are hearth-auto_film.py's, copied: that file cannot be imported without its storyboard.

NOT DONE: the page has no still of each scene; the film has no sound.
"""
import base64
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import json  # noqa: E402
import film  # noqa: E402
import process_film as pf  # noqa: E402
from film import seg, appear, out, esc, clock  # noqa: E402
from process_film import text, write, wrap, W, H, BG, INK, DIM, FAINT, PANEL, MAIN, CPU, GPU, LINE, RED, SERIF, MONO  # noqa: E402

VIOLET = "#b189c6"
COL = dict(main=MAIN, cpu=CPU, gpu=GPU, line=LINE, red=RED, violet=VIOLET, ink=INK, dim=DIM)
OUT_DIR = os.path.join(ROOT, "docs", "hearth-regulation")
STORY = json.load(open(os.path.join(OUT_DIR, "storyboard.json")))
SLUG = STORY["slug"]


# ---- the timeline: the storyboard's scenes in order, each as long as its words ----------------------------------

def timeline():
    tl = film.Timeline(STORY.get("wpm", 150), pf.LEAD, pf.TAIL)
    for d in STORY["scenes"]:
        tl.say(d["kind"], d["say"], 12.0 if d["kind"] == "end" else 0.0, d=d)
    return tl


TL = timeline()
SCENES, LENGTH = TL.scenes, TL.t
POSTER_T = next(s["t1"] for s in SCENES if s["d"]["id"] == STORY["poster"]) - 3.0


def chapters():
    return [(s["t0"], s["d"]["name"], None) for s in SCENES]


# process_film's title, close, teleprompt, list, still and youtube read these.
pf.STORY, pf.TL, pf.SCENES, pf.LENGTH, pf.SLUG, pf.OUT_DIR, pf.WPM, pf.STEPS, pf.chapters = STORY, TL, SCENES, LENGTH, SLUG, OUT_DIR, TL.wpm, [], chapters


# ---- what the slides share --------------------------------------------------------------------------------------

def plate(x, y, w, h, op, col=FAINT, fill=PANEL):
    """What words stand on."""
    return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="14" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-opacity="%.3f" stroke-width="2"/>' % (x, y, w, h, fill, 0.96 * op, col, op)


def lines(x, y, words, size, width, fill=INK, op=1.0, lead=1.36, weight=400, family=pf.SANS):
    return "".join(text(x, y + i * size * lead, l, size, fill, weight=weight, family=family, op=op) for i, l in enumerate(wrap(words, size, width)))


def ring(x, y, w, h, p, op, col=LINE):
    """A rectangle drawn round a thing as it is named."""
    if p <= 0 or op <= 0.004:
        return ""
    per = 2 * (w + h)
    return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="5" fill="none" stroke="%s" stroke-width="4" stroke-opacity="%.3f" stroke-dasharray="%.1f %.1f"/>' % (x, y, w, h, col, op, per * p, per)


def cue(c, i, end):
    """The i-th cue of a scene; -1 is its beginning; one the narration does not have is never reached."""
    return 0.8 if i < 0 else c[i] if i < len(c) else end + 9.0


def at(c, item, end):
    return cue(c, item.get("cue", -1), end) + item.get("lag", 0.0)


def top(d, u, op):
    """A slide's heading, and under it one line written on."""
    b = text(60, 86, d.get("head", ""), 22, DIM, weight=700, op=op, spacing=4)
    if d.get("title"):
        b += write(60, 178, d["title"], 52, seg(u, 0.8, 0.8 + min(2.6, len(d["title"]) / 16.0)), INK, weight=500, family=SERIF, op=op)
    return b


def foot(d, u, c, end, op, y=858, size=38):
    """The slide's last words, bottom left, beside the teleprompt: each written on at its cue."""
    b = ""
    for f in d.get("foot", []):
        a = at(c, f, end)
        for l in wrap(f["words"], size, 1240):
            b += write(60, y, l, size, seg(u, a, a + min(2.2, len(l) / 22.0)), COL[f.get("col", "ink")], weight=500, family=SERIF, op=op)
            y += size * 1.5
            a += 0.8
    return b


# ---- the kinds of slide -----------------------------------------------------------------------------------------

def cards_scene(t, sc):
    """Rows of plates. A plate has a heading, perhaps one large thing written on, perhaps words, perhaps commands."""
    d, u, end, c = sc["d"], t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    b, y, gap = top(d, u, op), d.get("y", 226), 22
    for row in d["rows"]:
        n = len(row["cards"])
        w = (1800 - (n - 1) * gap) / float(n)
        for i, k in enumerate(row["cards"]):
            a, col, x = at(c, k, end), COL[k.get("col", "ink")], 60 + i * (w + gap)
            o = op * seg(u, a, a + 0.7)
            yy = y + 14 * (1 - seg(u, a, a + 0.7, out))
            b += plate(x, yy, w, row["h"], o, col)
            b += text(x + 26, yy + 42, k["head"].upper(), 19, col, weight=700, op=o, spacing=2.5)
            ty = yy + 54
            if k.get("big"):
                bs = k.get("bigsize", 64)
                ty += bs * 1.02
                b += write(x + 26, ty, k["big"], bs, seg(u, a + 0.2, a + 0.2 + min(1.8, len(k["big"]) / 18.0)), col if col != DIM else INK, weight=600, family=SERIF, op=op)
                ty += 14
            size = k.get("size", 25)
            if k.get("words"):
                b += lines(x + 26, ty + size * 1.1, k["words"], size, w - 52, op=o * seg(u, a + 0.5, a + 1.1), weight=500)
            for j, m in enumerate(k.get("mono", [])):
                b += text(x + 26, yy + row["h"] - 24 - (len(k["mono"]) - 1 - j) * 32, m, 21, col, family=MONO, op=o * seg(u, a + 0.9, a + 1.5))
        y += row["h"] + gap
    return b + foot(d, u, c, end, op)


def cold2_scene(t, sc):
    """The target, the ceiling, where the room was held in the first fifteen hours and where it went once; then the questions."""
    d, u, end, c = sc["d"], t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    b = top(d, u, op)
    b += write(120, 262, "80 °F", 150, seg(u, 0.9, 2.2), MAIN, weight=600, family=SERIF, op=op)
    b += text(560, 262, "the target: 26.7 °C", 34, INK, op=op * seg(u, 2.0, 2.8))
    b += write(1130, 262, "81 °F", 150, seg(u, c[0], c[0] + 1.2), RED, weight=600, family=SERIF, op=op)
    b += text(1560, 262, "the ceiling", 34, INK, op=op * seg(u, c[0] + 0.8, c[0] + 1.6))
    x0, k, y = 200.0, 250.0, 470          # 77 °F at x0, 250 pixels a degree
    X = lambda f: x0 + (f - 77.0) * k
    b += '<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-opacity="%.3f" stroke-width="2"/>' % (X(77), y + 40, X(83), y + 40, DIM, op)
    for f in range(77, 84):
        b += '<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-opacity="%.3f" stroke-width="2"/>' % (X(f), y + 40, X(f), y + 54, DIM, op)
        b += text(X(f), y + 86, "%d °F" % f, 24, DIM, "middle", family=SERIF, op=op)
    g = seg(u, c[1], c[1] + 2.0, out)
    b += '<rect x="%.1f" y="%d" width="%.1f" height="40" rx="5" fill="%s" fill-opacity="%.3f"/>' % (X(d["lo"]), y, (d["hi"] - d["lo"]) * k * g, CPU, 0.85 * op * seg(u, c[1], c[1] + 0.4))
    b += text(X(d["lo"]), y - 16, "the first fifteen hours: held between %.1f and %.1f °F" % (d["lo"], d["hi"]), 26, CPU, weight=600, op=op * seg(u, c[1] + 1.0, c[1] + 1.8))
    for f, col, a in ((d["target"], MAIN, 2.0), (d["ceiling"], RED, c[0] + 0.6)):
        b += '<rect x="%.1f" y="%d" width="5" height="76" fill="%s" fill-opacity="%.3f"/>' % (X(f) - 2.5, y - 8, col, op * seg(u, a, a + 0.6))
    o = op * seg(u, c[1] + 4.6, c[1] + 5.4)
    b += '<circle cx="%.1f" cy="%d" r="13" fill="%s" fill-opacity="%.3f"/>' % (X(d["peak"]), y + 20, RED, o)
    b += text(X(d["peak"]) + 26, y - 26, "about %.1f °F, once, at 18:44" % d["peak"], 26, RED, weight=600, op=o)
    b += text(X(d["peak"]) + 26, y + 8, "a person had to end it", 24, INK, op=o * seg(u, c[1] + 6.6, c[1] + 7.4))
    for i, q in enumerate(d["questions"]):
        a = c[2] + (0.4, 1.8, 3.4, 5.0)[i]
        b += write(120 + (i % 2) * 720, 682 + (i // 2) * 76, q, 46, seg(u, a, a + 1.2), INK, weight=500, family=SERIF, op=op)
    return b


def act_scene(t, sc):
    """A part's name, on a band."""
    d, u = sc["d"], t - sc["t0"]
    op, col = appear(u, 0.2, sc["t1"] - sc["t0"], 0.6), COL[d["col"]]
    return ('<rect x="0" y="390" width="%d" height="4" fill="%s" fill-opacity="%.3f"/>' % (W, col, op) +
            text(W / 2, 452, d["part"], 24, DIM, "middle", 700, op=op, spacing=5) +
            text(W / 2, 546, d["big"], 84, col, "middle", 700, op=op, spacing=5) +
            text(W / 2, 612, d["sub"], 34, INK, "middle", op=op * seg(u, 0.8, 1.6)))


_PIC = {}


def picture(name):
    if name not in _PIC:
        _PIC[name] = "data:image/png;base64," + base64.b64encode(open(os.path.join(OUT_DIR, name), "rb").read()).decode()
    return _PIC[name]


def picture_scene(t, sc):
    """One of the report's pictures, whole. What the narration names is ringed at its cue and the rings before
    it go quiet; beside the picture, a plate for each thing named, with its mark's number if it has one."""
    d, u, end, c = sc["d"], t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    pw, ph = d["size"]
    k = min(1260.0 / pw, 774.0 / ph)
    ix, iy = 40, 108
    b = text(40, 78, d["head"], 21, DIM, weight=700, op=op, spacing=3.5)
    b += '<image x="%d" y="%d" width="%.1f" height="%.1f" href="%s" opacity="%.3f"/>' % (ix, iy, pw * k, ph * k, picture(d["file"]), op * seg(u, 0.3, 1.2))
    b += '<rect x="%d" y="%d" width="%.1f" height="%.1f" fill="none" stroke="%s" stroke-opacity="%.3f" stroke-width="1"/>' % (ix, iy, pw * k, ph * k, FAINT, op)
    whens = sorted(set([at(c, m, end) for m in d["marks"]] + [at(c, m, end) for m in d.get("extra", [])]))
    for i, m in enumerate(d["marks"]):
        a = at(c, m, end)
        later = min([w_ for w_ in whens if w_ > a + 0.01] or [end + 9.0])
        quiet = 1 - 0.72 * seg(u, later, later + 0.8)
        for j, r in enumerate(m["r"]):
            x, y, w, h = [v * k for v in r]
            b += ring(ix + x, iy + y, w, h, seg(u, a + 0.3 + j * 0.35, a + 1.4 + j * 0.35), op * quiet)
        o, py = op * seg(u, a, a + 0.7), 108 + i * 132
        b += plate(1326, py, 566, 122, o, LINE if quiet > 0.99 and u >= a else FAINT)
        hx = 1350
        if m.get("n"):
            x, y = ix + m["r"][0][0] * k - 13, iy + m["r"][0][1] * k - 13      # the number stands off the corner of what it marks
            for cx, cy, oo in ((x, y, o * quiet), (1372, py + 32, o)):
                b += '<circle cx="%.1f" cy="%.1f" r="17" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-opacity="%.3f" stroke-width="3"/>' % (cx, cy, BG, oo, LINE, oo)
                b += text(cx, cy + 7, str(m["n"]), 19, LINE, "middle", 700, op=oo)
            hx = 1402
        b += text(hx, py + 39, m["head"].upper(), 19, LINE, weight=700, op=o, spacing=2.5)
        b += lines(1350, py + 74, m["words"], 20.5, 524, op=o, lead=1.3, weight=500)
    for m in d.get("extra", []):
        a = at(c, m, end)
        x, y, w, h = [v * k for v in m["r"]]
        b += ring(ix + x, iy + y, w, h, seg(u, a + 0.3, a + 1.6), op, COL[m.get("col", "line")])
    a = cue(c, d["foot_cue"], end) if "foot_cue" in d else 1.6
    for i, l in enumerate(d.get("foot", [])):
        b += write(40, 944 + i * 54, l, 38, seg(u, a + 0.4 + i * 1.8, a + 2.0 + i * 1.8), INK, weight=500, family=SERIF, op=op)
    return b


TAGS = {"read": DIM, "measured": MAIN, "not measured": RED}


def balance_scene(t, sc):
    """Equation (1), a colour a term, and under it a row a symbol at the cue that names it."""
    d, u, end, c = sc["d"], t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    b = text(60, 86, d["head"], 22, DIM, weight=700, op=op, spacing=4)
    n = float(len(d["formula"]))
    spans = "".join('<tspan fill="%s" fill-opacity="%.3f">%s</tspan>' % (COL[col], op * seg(u, c[0] + 0.2 + i * 6.0 / n, c[0] + 1.0 + i * 6.0 / n), esc(s)) for i, (s, col) in enumerate(d["formula"]))
    b += '<text x="%d" y="212" font-family="%s" font-size="92" font-weight="600" text-anchor="middle" xml:space="preserve">%s</text>' % (W / 2, SERIF, spans)
    b += text(W / 2, 262, "the room, as one lump of heat", 26, DIM, "middle", op=op * seg(u, 0.8, 1.6))
    for x, hd in ((84, "symbol"), (250, "meaning"), (850, "unit"), (990, "where it comes from")):
        b += text(x, 316, hd.upper(), 15, DIM, weight=700, op=op * seg(u, c[1] - 0.6, c[1]), spacing=2)
    for i, r in enumerate(d["rows"]):
        a, y = at(c, r, end), 364 + i * 60
        o = op * seg(u, a, a + 0.7)
        col = TAGS[r["tag"]]
        b += '<line x1="60" y1="%d" x2="1860" y2="%d" stroke="%s" stroke-opacity="%.3f"/>' % (y - 38, y - 38, FAINT, o)
        b += write(84, y, r["sym"], 40, seg(u, a, a + 0.6), COL[r["col"]], weight=600, family=SERIF, op=op)
        b += text(250, y - 3, r["what"], 26, INK, weight=500, op=o)
        b += text(850, y - 3, r["unit"], 23, DIM, family=MONO, op=o)
        b += text(990, y - 3, r["from"], 24, INK if r["tag"] == "read" else col, op=o)
        if r["tag"] != "read":
            b += '<rect x="1640" y="%d" width="220" height="38" rx="19" fill="none" stroke="%s" stroke-opacity="%.3f" stroke-width="2"/>' % (y - 30, col, o)
            b += text(1750, y - 4, r["tag"].upper(), 17, col, "middle", 700, op=o, spacing=2)
    return b + foot(d, u, c, end, op, 880, 44)


def calc_scene(t, sc):
    """A sample calculation: what is given, as tiles; then a line at each cue, the expression and what it comes to."""
    d, u, end, c = sc["d"], t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    b = top(d, u, op)
    for i, (hd, big, col) in enumerate(d["given"]):
        a, x = 2.2 + i * 1.4, 60 + i * 452
        o = op * seg(u, a, a + 0.6)
        b += plate(x, 226, 430, 150, o, COL[col])
        b += text(x + 24, 268, hd.upper(), 19, COL[col], weight=700, op=o, spacing=2.5)
        b += text(x + 24, 344, big, 54 if len(big) < 14 else 40, COL[col], weight=600, family=SERIF, op=o)
    for i, l in enumerate(d["lines"]):
        a, y, col = at(c, l, end), 478 + i * 104, COL[l["col"]]
        o = op * seg(u, a, a + 0.6)
        b += '<line x1="60" y1="%d" x2="1860" y2="%d" stroke="%s" stroke-opacity="%.3f"/>' % (y - 62, y - 62, FAINT, o)
        b += text(60, y, l["label"], 28, col, weight=600, op=o)
        if l.get("big"):
            b += write(360, y + 8, l["expr"], 76, seg(u, a + 0.2, a + 1.6), col, weight=600, family=SERIF, op=op)
            b += text(1230, y + 2, l.get("note", ""), 27, DIM, op=op * seg(u, a + 2.4, a + 3.2))
            continue
        b += write(360, y, l["expr"], 36, seg(u, a + 0.2, a + 0.2 + min(2.4, len(l["expr"]) / 12.0)), INK, family=MONO, op=op)
        ra = a + 0.6 + min(2.4, len(l["expr"]) / 12.0)
        b += write(1250, y + 2, l["result"], 54, seg(u, ra, ra + 0.9), col, weight=600, family=SERIF, op=op)
        b += text(1620, y, l.get("note", ""), 25, DIM, op=op * seg(u, ra + 1.0, ra + 1.8))
    return b + foot(d, u, c, end, op, 880, 44)


def table_scene(t, sc):
    """Rows that appear at their cues; a row's colour is its first cell's."""
    d, u, end, c = sc["d"], t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    b, size = top(d, u, op), d.get("size", 24)
    for col in d["cols"]:
        b += text(col["x"], 142, col["head"].upper(), 16, DIM, weight=700, op=op, spacing=2)
    y = 196
    for r in d["rows"]:
        a = at(c, r, end)
        o = op * seg(u, a, a + 0.7)
        cells = [wrap(s, size, col["w"]) for s, col in zip(r["cells"], d["cols"])]
        b += '<line x1="60" y1="%d" x2="1860" y2="%d" stroke="%s" stroke-opacity="%.3f"/>' % (y - size * 1.5, y - size * 1.5, FAINT, o)
        for j, (ls, col) in enumerate(zip(cells, d["cols"])):
            for i, l in enumerate(ls):
                b += text(col["x"], y + i * size * 1.34, l, size, COL[r["col"]] if j == 0 else INK, weight=700 if j == 0 else 500 if j < len(cells) - 1 else 400, op=o)
        y += max(len(ls) for ls in cells) * size * 1.34 + size * 1.5
    return b + foot(d, u, c, end, op, 880, 44)


def ledger_scene(t, sc):
    """The report's last section, and what its abstract says stands: two columns, each row at its cue."""
    d, u, end, c = sc["d"], t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.4, end, 0.7)
    b = text(60, 104, "What is done, and what is not", 60, INK, weight=700, op=op)
    for x, name, col, rows in ((60, "done", MAIN, d["done"]), (970, "not done", RED, d["not"])):
        for i, r in enumerate(rows):
            a = at(c, r, end)
            o = op * seg(u, a, a + 0.8)
            y = 150 + i * 126 + 14 * (1 - seg(u, a, a + 0.8, out))
            b += plate(x, y, 890, 116, o, col)
            b += text(x + 22, y + 30, name.upper(), 16, col, weight=700, op=o, spacing=2.5)
            b += lines(x + 22, y + 60, r["words"], 22.5, 850, op=o, lead=1.28, weight=500)
    return b


OVER = {"cards": cards_scene, "cold2": cold2_scene, "act": act_scene, "picture": picture_scene, "balance": balance_scene, "calc": calc_scene, "table": table_scene,
        "ledger": ledger_scene, "title": pf.title_scene, "end": pf.end_scene}


def frame(t):
    """The slide being told at t, the teleprompt in its corner, and how far through the film it is."""
    sc = pf.scene_at(t)
    bar = '<rect x="0" y="%d" width="%.1f" height="4" fill="%s" fill-opacity="0.55"/>' % (H - 4, W * t / LENGTH, INK)
    return ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="%d" height="%d" viewBox="0 0 %d %d"><rect width="%d" height="%d" fill="%s"/>%s%s%s</svg>') % (
        W, H, W, H, W, H, BG, OVER[sc["kind"]](t, sc), pf.teleprompter(t, sc), bar)


pf.frame = frame


# ---- the page: process_film's head, player and script, with this film's own account under them ------------------

def page():
    cards = "".join('<article class="step" style="--c:%s"><header><button class="seek" data-t="%.1f" aria-label="Play this scene in the film">&#9654; %s</button><h3>%s</h3></header>'
                    '<dl><dt>Narration</dt><dd class="say">%s</dd></dl></article>' % (
                        COL.get(s["d"].get("col", ""), {"picture": LINE, "calc": GPU, "balance": GPU, "table": CPU, "ledger": RED}.get(s["kind"], MAIN)),
                        s["t0"], clock(s["t0"]), esc(s["d"]["name"]), esc(" ".join(s["words"]))) for s in SCENES)
    nav = "".join('<button data-t="%.1f"><span>%s</span>%s</button>' % (s["t0"], clock(s["t0"]), esc(s["d"]["name"])) for s in SCENES)
    words = film.captions(TL, lambda sc: sc["d"]["name"], OUT_DIR, STORY["title"])
    p = pf.PAGE
    body = """<p class="eyebrow">Orreryq &middot; the fleet &middot; 18 November 2026</p>
<h1>Keeping the Room</h1>
<p class="lede">The film of the lab report <a href="hearth-regulation-lab-report.html">Keeping the Room</a>, as slides: how to use Orrery's thermal regulation, the Hearth and Diagram panels mark by mark, the one heat balance and five of the report's calculations worked line by line, the first fifteen hours, how the heat is drawn, and its upkeep. The film is @LEN@ long and has no sound. Its narration, @WORDS@ words, scrolls in the corner at @WPM@ words a minute, the word to be spoken lit; the same words are the film's captions. The film says what the report says: UA, 120 W/&deg;C, is a figure in use and not a measurement; the other heat is implied; zone 2 has no thermometer; the hold has no proof of its own.</p>
<div class="stage"><video id="film" controls preload="metadata" playsinline poster="@SLUG@/poster.png" src="@SLUG@/film.mp4"><track kind="captions" srclang="en" label="Narration" src="@SLUG@/captions.vtt"></video><nav id="nav">@NAV@</nav></div>
<p class="how files">The narration as a script with its times: <a href="@SLUG@/teleprompt.txt">teleprompt.txt</a>. As captions: <a href="@SLUG@/captions.vtt">captions.vtt</a>.</p>
<h2>Every scene, in order</h2>
<p class="how">Each card is one slide of the film and what is said over it. The button plays that slide in the film above.</p>
@CARDS@
<h2>How the film is made</h2>
<p class="how">The film is one file of words and numbers (<a href="@SLUG@/storyboard.json">storyboard.json</a>) drawn by three scripts: <code>tools/report/film.py</code>, what any such film shares; <code>tools/report/process_film.py</code>, whose look, title, close, teleprompt and kit this film keeps; and <code>tools/report/hearth-regulation_film.py</code>, the kinds of slide.</p>
<dl class="made">
<dt>The words first</dt><dd>Each slide is exactly as long as its narration at @WPM@ words a minute, with a breath before and after. A mark in the narration is a cue, and what appears on a slide appears at a cue.</dd>
<dt>A slideshow</dt><dd>The report is a guide, then a science, then a record. It has no single block diagram to walk, so this film has no map and no camera: one idea a slide.</dd>
<dt>The pictures</dt><dd>The report's two pictures of Orrery are shown whole, five times between them, and what the narration names is ringed as it is named, with its mark's number. The rings are regions measured on the pictures for this film; the report's own marks are numbers at a point. The Diagram is shown twice more for the ways the heat is drawn, and the chart of the report before this one once.</dd>
<dt>The calculations</dt><dd>Five of the report's seven, with its numbers: the budget at 06:37, the budget held at &minus;600 W at 18:37, the three flows at 08:21, the night that gives (P + P0)/UA = 20.3 &deg;C, and how cold it can be. The time constant is on the slide before them. The energy of calculation 7 is not in the film.</dd>
<dt>Not done</dt><dd>There is no still of each slide on this page. The film has no sound.</dd>
</dl>
"""
    html = (p[:p.index('<p class="eyebrow">')] + body + p[p.index("</main><script>"):]).replace("How the Game Learns", STORY["title"])
    html = html.replace("@NAV@", nav).replace("@CARDS@", cards).replace("@LEN@", clock(LENGTH)).replace("@WPM@", str(TL.wpm)).replace("@WORDS@", format(words, ",")).replace("@SLUG@", SLUG)
    dst = os.path.join(ROOT, "docs", "%s-film.html" % SLUG)
    open(dst, "w").write(html)
    print("%s: %d scenes, %d words, %s" % (dst, len(SCENES), words, clock(LENGTH)))


# ---- the render: hearth-auto_film's, a few processes and the frames kept ----------------------------------------

def _one(i):
    png = os.path.join(_one.dir, "f%05d.png" % i)
    if not os.path.exists(png):
        film.render(frame(i / pf.FPS), png + ".part", W, H)
        os.rename(png + ".part", png)


def render(dst, frames):
    """Every frame, two processes (FILM_PROCS), each kept in `frames` so a run that was stopped is taken up; then the film and its poster."""
    import multiprocessing
    import shutil
    os.makedirs(frames, exist_ok=True)
    n = int(LENGTH * pf.FPS)
    _one.dir = frames
    with multiprocessing.get_context("fork").Pool(int(os.environ.get("FILM_PROCS", "2"))) as pool:
        pool.map(_one, range(n), chunksize=24)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(pf.FPS), "-i", os.path.join(frames, "f%05d.png"), "-frames:v", str(n), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "23", "-preset", "slow", "-tune", "animation", "-movflags", "+faststart", dst], check=True)
    shutil.copy(os.path.join(frames, "f%05d.png" % int(POSTER_T * pf.FPS)), os.path.join(os.path.dirname(os.path.abspath(dst)), "poster.png"))
    print("%s: %d frames, %s" % (dst, n, clock(LENGTH)))


def main(a):
    if a[:1] == ["film"] and len(a) >= 2:
        render(a[1], a[2] if len(a) > 2 else os.path.splitext(a[1])[0] + "-frames")
    elif a[:1] == ["film"]:
        sys.exit(__doc__)        # the master is 1080p and is not kept in the repository: it is given a place
    elif a[:1] == ["page"]:
        page()
    elif a[:1] == ["youtube"] and len(a) < 2:
        sys.exit(__doc__)
    else:
        pf.main(a)


if __name__ == "__main__":
    main(sys.argv[1:])
