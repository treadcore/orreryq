#!/usr/bin/env python3
"""process_film: the whole learning process as one block diagram, walked arrow by arrow, outside in.

    python3 tools/report/process_film.py film [OUT.mp4]     every frame, then the film (docs/process/film.mp4)
    python3 tools/report/process_film.py still T OUT.png    the frame at T seconds, to look at one
    python3 tools/report/process_film.py page               docs/process-film.html and a still of each step
    python3 tools/report/process_film.py list               the scenes and when each begins
    python3 tools/report/process_film.py youtube [MASTER]   the kit for YouTube: output/youtube/SLUG/ (not the repository)
    ... --story docs/NAME/storyboard.json                   another report's film: every output goes beside its storyboard

Paul, 13 November: "I really need only diagrams showing step by step transitions. So like describe the arrows,
from source to destination, each step in context to the whole. I want a visual description of the purpose of
each step. ... Movement of context, moving across borders. ... explain the process outside in, top down."

ONE MAP, AND THE CAMERA MOVES. The diagram is drawn once, on one canvas: three territories (main, the CPU
fleet, the cards) and the line between two of them, every block in its place for the whole film. A step is one
arrow: the camera goes to it, the rest dims, a token carrying what moves travels from the source to the
destination, and the words under it say from where, to where, what moves, why, and the rule at the border if it
crosses one. A small map in the corner keeps the whole in view with the arrow lit, so no step is seen out of
its place. Then two real journeys of 13 November run over the same arrows, and the one shape every border
shares is drawn last.

Every frame is a function of its time, as in ssd_film.py: SVG, rasterised by librsvg, joined by FFmpeg.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import film  # noqa: E402
from film import clamp, smooth, out, back, seg, lerp, mix, esc, appear, swell, clock  # noqa: E402

W, H, FPS = 1920, 1080, 24
BG, INK, DIM, FAINT, PANEL = "#0e1013", "#ece9e1", "#9a978d", "#4a4944", "#15181d"
# The palette is 3Blue1Brown's (Paul, 13 November: "in the style of 3blue1brown"): its blue, green and yellow on near-black,
# a coral for the fleet. Yellow is kept for what the eye should go to: the border, the word being spoken, a thing indicated.
MAIN, CPU, GPU, LINE, RED = "#83c167", "#ff8c5a", "#58c4dd", "#f7d96f", "#fc6255"
SERIF = "Iowan Old Style, Palatino, Georgia, serif"
SANS, MONO = "Avenir Next, Helvetica Neue, Helvetica, Arial, sans-serif", "Menlo, Consolas, monospace"

# THE STORYBOARD IS THE FILM (13 November). Everything a film of this kind says is in one file: the territories
# and blocks and where they stand, each arrow with what moves along it and why, the narration of every scene,
# the journeys, the closing shape. This script is only how such a file is drawn. Another process is another
# storyboard: `--story PATH`.
STORY_PATH = sys.argv[sys.argv.index("--story") + 1] if "--story" in sys.argv else os.path.join(ROOT, "docs", "process", "storyboard.json")
if "--story" in sys.argv:
    del sys.argv[sys.argv.index("--story"):sys.argv.index("--story") + 2]
STORY = json.load(open(STORY_PATH))
REGIONS, LINE_BOX, STEPS, NAR = STORY["regions"], STORY.get("line_box"), STORY["steps"], STORY["narration"]
N = {k: (v["region"], v["x"], v["y"], v["w"], v["h"], v["title"], v["sub"]) for k, v in STORY["nodes"].items()}
ACTS = {k: (v["name"], v["sub"], v["col"]) for k, v in STORY["acts"].items()}
JOURNEYS = [dict(j, legs=[(l["step"], l["words"]) for l in j["legs"]]) for j in STORY.get("journeys", [])]
PATTERN = [(x["name"], x["sub"]) for x in STORY.get("pattern", [])]
PATTERN_ROWS = [(x["name"], x["col"], x["cells"]) for x in STORY.get("pattern_rows", [])]
SLUG = STORY.get("slug") or os.path.basename(os.path.dirname(os.path.abspath(STORY_PATH)))
OUT_DIR = os.path.dirname(os.path.abspath(STORY_PATH))
for _s in STEPS:
    if _s.get("pts"):
        _s["pts"] = [tuple(q) for q in _s["pts"]]
SI = {s["id"]: s for s in STEPS}
WPM, LEAD, TAIL = STORY.get("wpm", 150), 0.8, 1.8   # the narration's pace, and the quiet before and after it in each scene


# ---- geometry ---------------------------------------------------------------------------------------------

def rect_of(n):
    _, x, y, w, h, _, _ = N[n]
    return x, y, w, h


def centre(n):
    x, y, w, h = rect_of(n)
    return x + w / 2, y + h / 2


def clip(n, toward):
    """Where the segment from n's centre toward a point leaves n's box."""
    x, y, w, h = rect_of(n)
    cx, cy = x + w / 2, y + h / 2
    dx, dy = toward[0] - cx, toward[1] - cy
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return cx, cy
    k = min((w / 2) / abs(dx) if dx else 1e9, (h / 2) / abs(dy) if dy else 1e9)
    return cx + dx * k, cy + dy * k


def path_of(s):
    if s.get("pts"):
        return list(s["pts"])
    return [clip(s["a"], centre(s["b"])), clip(s["b"], centre(s["a"]))]


def length(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def along(pts, p):
    """The point at share p of a polyline, and the polyline up to it."""
    want, done, out = clamp(p) * length(pts), 0.0, [pts[0]]
    for a, b in zip(pts, pts[1:]):
        d = math.dist(a, b)
        if done + d >= want - 1e-9:
            k = (want - done) / d if d else 0
            q = (lerp(a[0], b[0], k), lerp(a[1], b[1], k))
            return q, out + [q], (b[0] - a[0], b[1] - a[1])
        done += d
        out.append(b)
    return pts[-1], out, (pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1])


def bbox(s):
    xs, ys = [], []
    for n in (s["a"], s["b"]):
        x, y, w, h = rect_of(n)
        xs += [x, x + w]
        ys += [y, y + h]
    for x, y in path_of(s):
        xs.append(x)
        ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


# ---- the timeline -------------------------------------------------------------------------------------------

def timeline():
    """Every scene, as long as its narration (film.Timeline): the opening, the whole, the borders, each act and its arrows, the journeys, the one shape, the close."""
    tl = film.Timeline(WPM, LEAD, TAIL)
    # THE COLD OPEN, before the title: a true thing that should not be possible, then why it is, then the question.
    for k in ("hook1", "hook2", "hook3"):
        if k in NAR and STORY.get("hook"):
            tl.say(k, NAR[k])
    tl.say("title", NAR["title"])
    tl.say("whole", NAR["whole"])
    tl.say("borders", NAR["borders"])
    act = None
    for s in STEPS:
        if s["act"] != act:
            act = s["act"]
            tl.say("act", NAR["act:" + act], act=act)
        tl.say("step", s["say"], 12.0, step=s["id"])
    for j in JOURNEYS:
        tl.say("journey", "The same arrows, now with one real thing travelling over them. " + " ".join("| " + w_ for _, w_ in j["legs"]), journey=j)
    if PATTERN:
        tl.say("pattern", NAR["pattern"])
    # the close holds long enough to read the credits under it
    tl.say("end", NAR["end"], 12.0 if STORY.get("credits") else 7.0)
    return tl


TL = timeline()
SCENES, LENGTH = TL.scenes, TL.t
STEP_T = {s["step"]: s["t0"] for s in SCENES if s["kind"] == "step"}
FIRST_STEP = min(STEP_T.values())
WH = next(s for s in SCENES if s["kind"] == "whole")
PATTERN_T = next(s["t0"] for s in SCENES if s["kind"] in ("pattern", "end"))
AFTER_STEPS = max(s["t1"] for s in SCENES if s["kind"] == "step")


def scene_at(t):
    for s in SCENES:
        if t < s["t1"]:
            return s
    return SCENES[-1]


def node_born(n):
    """When a block first appears: with the step that first names it (as the source at once, as the destination when the arrow arrives)."""
    best = AFTER_STEPS
    for s in STEPS:
        if s["a"] == n:
            best = min(best, STEP_T[s["id"]] + 0.4)
        if s["b"] == n:
            best = min(best, STEP_T[s["id"]] + 1.6)
    return best


BORN = {n: node_born(n) for n in N}


FAR = 0.52      # the opening's distance: the whole map small in the dark, before the camera comes in
PUSH = 0.022    # a step's slow push in while it is told, so the frame is never quite still


def region_at(pt):
    for k, r in REGIONS.items():
        if r["x"] <= pt[0] <= r["x"] + r["w"] and r["y"] <= pt[1] <= r["y"] + r["h"]:
            return k
    return None


def crossing(s):
    """Where an arrow leaves its source's territory and where it enters its destination's, as shares of
    its path; None when it stays at home. Between the two it is in no territory: on the border."""
    if "cross" not in s:
        a, b, pts = N[s["a"]][0], N[s["b"]][0], path_of(s)
        s["cross"] = None
        if a != b:
            ps = [i / 200.0 for i in range(201)]
            leave = next((p_ for p_ in ps if region_at(along(pts, p_)[0]) != a), 0.5)
            enter = next((p_ for p_ in ps if p_ >= leave and region_at(along(pts, p_)[0]) == b), leave)
            s["cross"] = (leave, max(enter, leave + 0.02))
    return s["cross"]


def camera(t):
    sc = scene_at(t)

    def want(s, end=False):
        if s["kind"] == "title" or s["kind"].startswith("hook"):
            return (W / 2, H / 2, FAR)
        if s["kind"] != "step":
            return (W / 2, H / 2, 1.0)
        x0, y0, x1, y1 = bbox(SI[s["step"]])
        z = max(1.0, min(1.85, 0.80 * W / (x1 - x0 + 60), 0.44 * H / (y1 - y0 + 60)))
        return ((x0 + x1) / 2, (y0 + y1) / 2 + 190 / z, z * (1 + PUSH * (clamp((t - s["t0"]) / (s["t1"] - s["t0"])) if not end else 1.0)))
    i = SCENES.index(sc)
    a = want(SCENES[i - 1], True) if i else want(sc)
    b = want(sc)
    # the opening comes in from far away over its first sentence; every other move takes a second and a half
    p = smooth((t - sc["t0"]) / (sc["cues"][0] if sc["kind"] == "whole" else 1.6))
    return (lerp(a[0], b[0], p), lerp(a[1], b[1], p), math.exp(lerp(math.log(a[2]), math.log(b[2]), p)))


# ---- drawing ----------------------------------------------------------------------------------------------

def text(x, y, s, size=30, fill=INK, anchor="start", weight=400, family=SANS, op=1.0, spacing=0):
    if op <= 0.004 or not s:
        return ""
    return '<text x="%.1f" y="%.1f" font-family="%s" font-size="%.1f" font-weight="%d" fill="%s" fill-opacity="%.3f" text-anchor="%s"%s>%s</text>' % (
        x, y, family, size, weight, fill, clamp(op), anchor, ' letter-spacing="%.1f"' % spacing if spacing else "", esc(s))


def write(x, y, s, size, p, fill=INK, anchor="start", weight=400, family=SANS, op=1.0):
    """Words written on, a letter after another, as a hand would: p is the share written."""
    if p <= 0 or op <= 0.004:
        return ""
    if p >= 1:
        return text(x, y, s, size, fill, anchor, weight, family, op)
    n = len(s)
    spans = "".join('<tspan fill-opacity="%.3f">%s</tspan>' % (op * clamp(p * (n + 4) - i), esc(ch)) for i, ch in enumerate(s))
    return '<text x="%.1f" y="%.1f" font-family="%s" font-size="%.1f" font-weight="%d" fill="%s" text-anchor="%s" xml:space="preserve">%s</text>' % (x, y, family, size, weight, fill, anchor, spans)


def wrap(s, size, width):
    words, lines, cur = s.split(), [], ""
    room = int(width / (size * 0.50))
    for w_ in words:
        if len(cur) + len(w_) + 1 > room and cur:
            lines.append(cur)
            cur = w_
        else:
            cur = (cur + " " + w_).strip()
    return lines + ([cur] if cur else [])


def region(k, op, label_op=1.0, big=0.0):
    r = REGIONS[k]
    b = '<rect x="%d" y="%d" width="%d" height="%d" rx="18" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-opacity="%.3f" stroke-width="2.5"/>' % (
        r["x"], r["y"], r["w"], r["h"], r["col"], 0.07 * op, r["col"], 0.85 * op)
    b += text(r["x"] + 22, r["y"] + 31, r["name"], 20, r["col"], weight=700, op=op * label_op, spacing=2.5)
    b += text(r["x"] + 34 + len(r["name"]) * 15.5, r["y"] + 31, r["sub"], 17, DIM, op=op * label_op * (1 - big))
    if big > 0:
        b += text(r["x"] + r["w"] / 2, r["y"] + r["h"] / 2 + 6, r["name"], 58 if k != "main" else 50, r["col"], "middle", 700, op=op * big, spacing=4)
        for i, l in enumerate(wrap(r["sub"], 26, r["w"] - 120)):
            b += text(r["x"] + r["w"] / 2, r["y"] + r["h"] / 2 + 48 + i * 32, l, 26, INK, "middle", op=op * big * 0.9)
    return b


def node(n, op, hot=0.0, scale=1.0):
    if op <= 0.004:
        return ""
    k, x, y, w, h, title, sub = N[n]
    col = REGIONS[k]["col"]
    if abs(scale - 1) > 1e-4:
        cx, cy = x + w / 2, y + h / 2
        return '<g transform="translate(%.1f %.1f) scale(%.4f) translate(%.1f %.1f)">%s</g>' % (cx, cy, scale, -cx, -cy, node(n, op, hot))
    b = '<rect x="%d" y="%d" width="%d" height="%d" rx="12" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-opacity="%.3f" stroke-width="%.1f"/>' % (
        x, y, w, h, mix(PANEL, col, 0.10 + 0.22 * hot), op, col, op * (0.55 + 0.45 * hot), 2 + 2.5 * hot)
    b += text(x + 16, y + 35, title, 23, INK, weight=600, op=op)
    b += text(x + 16, y + 63, sub, 16.5, DIM, op=op)
    return b


def polyline(pts, col, width, op, dash=False):
    if op <= 0.004 or len(pts) < 2:
        return ""
    return '<polyline points="%s" fill="none" stroke="%s" stroke-width="%.1f" stroke-opacity="%.3f" stroke-linejoin="round" stroke-linecap="round"%s/>' % (
        " ".join("%.1f,%.1f" % p for p in pts), col, width, op, ' stroke-dasharray="9 8"' if dash else "")


def head(q, d, col, size, op):
    if op <= 0.004:
        return ""
    L = math.hypot(*d) or 1
    ux, uy = d[0] / L, d[1] / L
    a, b_, c = (q[0], q[1]), (q[0] - ux * size - uy * size * 0.55, q[1] - uy * size + ux * size * 0.55), (q[0] - ux * size + uy * size * 0.55, q[1] - uy * size - ux * size * 0.55)
    return '<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s" fill-opacity="%.3f"/>' % (a + b_ + c + (col, op))


def arrow(s, p, col, width, op):
    pts = path_of(s)
    q, part, d = along(pts, p)
    return polyline(part, col, width, op, s.get("dash")) + (head(q, d, col, 5 + width * 2.2, op) if p > 0.04 else "")


def token(s, p, col, label, op, scale=1.0):
    """What moves, on its way: a dot with its name, a trail behind it so a still shows which way it goes, and
    across a border the colour of the territory it is entering."""
    if op <= 0.004:
        return ""
    pts = path_of(s)
    q, _, _ = along(pts, p)
    cr = crossing(s)
    if cr:
        col = mix(col, REGIONS[N[s["b"]][0]]["col"], seg(p, cr[0], cr[1]))
    b = ""
    for k in range(1, 9):
        pk = p - k * 0.028
        if pk > 0:
            g, _, _ = along(pts, pk)
            b += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" fill-opacity="%.3f"/>' % (g[0], g[1], (8 - k * 0.7) * scale, col, op * 0.5 * (1 - k / 9.0))
    wd = (len(label) * 9.6 + 30) * scale
    b += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" fill-opacity="%.3f"/><circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" stroke-opacity="%.3f" stroke-width="2"/>' % (
        q[0], q[1], 9 * scale, col, op, q[0], q[1], 16 * scale, col, op * 0.5)
    b += '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-opacity="%.3f" stroke-width="1.5"/>' % (
        q[0] - wd / 2, q[1] - 74 * scale, wd, 30 * scale, 15 * scale, BG, op * 0.94, col, op)
    return b + text(q[0], q[1] - 53.5 * scale, label, 16.5 * scale, INK, "middle", 600, op=op)


def ripple(s, p, op):
    """THE BORDER, CROSSED: a ring opens where the arrow leaves one territory and another where it enters the next."""
    cr = crossing(s)
    if not cr or op <= 0.004:
        return ""
    b, L = "", length(path_of(s))
    for at, col in ((cr[0], LINE), (cr[1], REGIONS[N[s["b"]][0]]["col"])):
        d = (p - at) * L        # how far past the border the token is, in the map's own units
        if 0 <= d <= 170:
            q, _, _ = along(path_of(s), at)
            k = d / 170.0
            b += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" stroke-width="%.1f" stroke-opacity="%.3f"/>' % (q[0], q[1], 10 + 62 * out(k), col, 5 * (1 - k) + 1, op * (1 - k))
    return b


GO, TRAVEL, CYCLE = 2.6, 3.4, 5.6   # a step's token: when it first sets out, how long it travels, and how often it sets out again


def the_map(t):
    """Everything in the camera's world: the territories, the blocks, the arrows."""
    sc = scene_at(t)
    k = sc["kind"]
    wh = WH
    born_r = region_born()
    big = 1 - seg(t, FIRST_STEP - 1.4, FIRST_STEP - 0.4)
    # A faint plane under everything, as under 3Blue1Brown's figures: it gives the camera's moves something to move against.
    go = 0.05 * seg(t, wh["t0"], wh["t0"] + 2.0)
    b = "".join('<line x1="%d" y1="-1200" x2="%d" y2="2300" stroke="%s" stroke-opacity="%.3f"/>' % (x, x, INK, go * (2 if x % 480 == 0 else 1)) for x in range(-1920, 3841, 80))
    b += "".join('<line x1="-1920" y1="%d" x2="3840" y2="%d" stroke="%s" stroke-opacity="%.3f"/>' % (y, y, INK, go * (2 if y % 480 == 0 else 1)) for y in range(-1200, 2301, 80))
    b += "".join(region(r, seg(t, born_r[r], born_r[r] + 1.2), big=big) for r in REGIONS)
    if LINE_BOX:        # a territory inside a territory, drawn when the step that first enters it has landed
        at = STEP_T[LINE_BOX.get("after", STEPS[0]["id"])]
        lo = seg(t, at + 4.6, at + 5.6)
        b += '<rect x="%d" y="%d" width="%d" height="%d" rx="14" fill="none" stroke="%s" stroke-opacity="%.3f" stroke-width="2" stroke-dasharray="4 7"/>' % (
            LINE_BOX["x"], LINE_BOX["y"], LINE_BOX["w"], LINE_BOX["h"], LINE, 0.9 * lo)
        b += text(LINE_BOX["x"] + LINE_BOX["w"] - 12, LINE_BOX["y"] + LINE_BOX["h"] - 10, LINE_BOX.get("name", "THE LINE"), 13, LINE, "end", 700, op=lo, spacing=2)
    cur = SI[sc["step"]] if k == "step" else None
    hot_nodes, lit, scales = {}, {}, {}
    if cur:
        u = t - sc["t0"]
        hot_nodes[cur["a"]] = 1 - 0.6 * seg(u, 4.6, 6.2)
        hot_nodes[cur["b"]] = seg(u, 5.0, 6.2)
        # A MOVE GATHERS, GOES AND LANDS: the source dips as the token sets out, the destination swells as it arrives.
        v = (u - GO) % CYCLE if u >= GO else -9.0
        scales[cur["a"]] = 1 - 0.035 * swell(v + 0.25, 0.5) + 0.05 * swell(u - 0.5, 0.7)
        scales[cur["b"]] = 1 + 0.06 * swell(v - TRAVEL + 0.15, 0.55)
    if k == "journey":
        j, u = sc["journey"], t - sc["t0"]
        i, a, c = leg_at(sc, u)
        if i >= 0:
            s = SI[j["legs"][i][0]]
            hot_nodes[s["a"]] = hot_nodes[s["b"]] = 1.0
            lit[s["id"]] = (seg(u, a + 0.2, a + min(3.0, 0.7 * (c - a))), j["col"])
    dim = 0.30 if cur else 0.55 if k in ("journey",) else 1.0
    if k in ("pattern", "end", "act"):
        dim = 0.16 if k != "act" else 0.5
    # the arrows already walked stay, quiet; the current one is drawn over them
    for s in STEPS:
        born = STEP_T[s["id"]] + 1.6
        if t < born or s is cur:
            continue
        col = REGIONS[N[s["a"]][0]]["col"]
        b += arrow(s, 1.0, col, 2.2, (0.5 if not cur and k not in ("pattern", "end") else 0.22) * (0.3 if k in ("pattern", "end") else 1))
    for n in N:
        o = seg(t, BORN[n], BORN[n] + 0.7)
        h_ = hot_nodes.get(n, 0.0)
        b += node(n, o * (dim + (1 - dim) * max(h_, 0.0 if (cur or k == "journey") else 1.0)), h_, (0.94 + 0.06 * back(o)) * scales.get(n, 1.0))
    if cur:
        u, col = t - sc["t0"], REGIONS[N[cur["a"]][0]]["col"]
        b += arrow(cur, seg(u, 1.6, 3.0), col, 4.5, 1.0)
        # The token sets out again every few seconds while the step is told: the movement is the step.
        v = (u - GO) % CYCLE if u >= GO else -1.0
        pv, ov = seg(v, 0.0, TRAVEL), appear(v, -0.2, CYCLE - 0.6, 0.4) if v >= 0 else 0.0
        b += ripple(cur, pv, ov) + token(cur, pv, col, cur["moves"], ov, 0.9)
        # INDICATE: as the token first lands, a yellow rectangle is drawn round where it landed, and stays.
        x_, y_, w_, h_ = rect_of(cur["b"])
        per, pd = 2 * (w_ + h_ + 40), seg(u, GO + TRAVEL - 0.2, GO + TRAVEL + 0.7)
        if pd > 0:
            b += '<rect x="%d" y="%d" width="%d" height="%d" rx="16" fill="none" stroke="%s" stroke-width="3" stroke-opacity="%.3f" stroke-dasharray="%.1f %.1f"/>' % (
                x_ - 10, y_ - 10, w_ + 20, h_ + 20, LINE, 1 - 0.55 * seg(u, GO + TRAVEL + 1.5, GO + TRAVEL + 3.0), per * pd, per)
    for sid, (p, col) in lit.items():
        b += arrow(SI[sid], 1.0, col, 4.5, 0.95) + ripple(SI[sid], p, 1.0) + token(SI[sid], p, col, SI[sid]["moves"], 1.0, 1.25)
    return b


def region_born():
    """When each territory appears: with the opening's first words, or at the cue of the narration that names it."""
    return {k: WH["t0"] + (WH["cues"][r["cue"]] - 0.4 if r.get("cue") is not None and r["cue"] < len(WH["cues"]) else 0.2) for k, r in REGIONS.items()}


def leg_at(sc, u):
    """Which leg of a journey is being told at u seconds into its scene, and when it begins and ends."""
    cs = sc["cues"] + [sc["t1"] - sc["t0"]]
    for i in range(len(cs) - 1):
        if cs[i] <= u < cs[i + 1]:
            return i, cs[i], cs[i + 1]
    return -1, 0.0, 0.0


TP = dict(x=1352, y=786, w=540, h=262)


def teleprompter(t, sc):
    """THE TELEPROMPT, in the corner (Paul, 13 November: "like closed captioning but for a teleprompt scroll")."""
    return film.teleprompter(TL, t, sc, (TP["x"], TP["y"], TP["w"], TP["h"]), SANS, INK, DIM, LINE, FAINT)


def crumbs(t, sc):
    """WHERE WE ARE, FROM THE OUTSIDE IN: the whole, the loop, the arrow. Top left of every step."""
    s, u = SI[sc["step"]], t - sc["t0"]
    op = seg(u, 0.4, 1.1) * (1 - seg(t, sc["t1"] - 0.5, sc["t1"]))
    col, x, b = ACTS[s["act"]][2], 44, ""
    parts = [("THE WHOLE", DIM, 600), (ACTS[s["act"]][0], col, 700), ("%s  →  %s" % (N[s["a"]][5], N[s["b"]][5]), INK, 600)]
    wd = sum(len(p_[0]) * 11.4 + 46 for p_ in parts) + 6
    b += '<rect x="%d" y="26" width="%.1f" height="40" rx="20" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-opacity="%.3f"/>' % (x - 16, wd, BG, 0.92 * op, FAINT, op)
    for i, (words, c, wt) in enumerate(parts):
        o = op * seg(u, 0.5 + i * 0.35, 1.0 + i * 0.35, out)
        if i:
            b += text(x, 52, "›", 20, DIM, op=o)
            x += 24
        b += text(x, 52, words, 16, c, weight=wt, op=o, spacing=1.5 if i < 2 else 0)
        x += len(words) * 11.4 + 22
    return b


def minimap(t, sc):
    op = seg(t, sc["t0"] + 0.6, sc["t0"] + 1.4) * (1 - seg(t, sc["t1"] - 0.5, sc["t1"]))
    if op <= 0.004:
        return ""
    k, ox, oy = 0.158, W - 344, 26
    b = '<rect x="%d" y="%d" width="320" height="188" rx="12" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-opacity="%.3f"/>' % (ox - 8, oy - 8, BG, 0.93 * op, FAINT, op)
    for r in REGIONS.values():
        b += '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="4" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-opacity="%.3f"/>' % (
            ox + r["x"] * k, oy + r["y"] * k, r["w"] * k, r["h"] * k, r["col"], 0.10 * op, r["col"], 0.6 * op)
    s = SI[sc["step"]]
    for n in N:
        x, y, w, h = rect_of(n)
        on = n in (s["a"], s["b"])
        b += '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" fill="%s" fill-opacity="%.3f"/>' % (
            ox + x * k, oy + y * k, w * k, h * k, INK if on else REGIONS[N[n][0]]["col"], (0.95 if on else 0.35) * op)
    b += polyline([(ox + x * k, oy + y * k) for x, y in path_of(s)], INK, 2.2, op)
    cx, cy, z = camera(t)
    b += '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" stroke="%s" stroke-opacity="%.3f" stroke-width="1.5"/>' % (
        ox + (cx - W / 2 / z) * k, oy + max(0, cy - H / 2 / z) * k, W / z * k, min(H / z, 820 / z) * k, INK, 0.75 * op)
    return b + text(ox, oy + 170, "where this step is in the whole", 13, DIM, op=op)


def lower(t, sc):
    """The words under a step: from, to, what moves, why, the rule, the border."""
    s, u = SI[sc["step"]], t - sc["t0"]
    dur = sc["t1"] - sc["t0"]
    op = seg(u, 0.5, 1.2) * (1 - seg(u, dur - 0.6, dur - 0.1))
    col = REGIONS[N[s["a"]][0]]["col"]
    y0 = 690
    b = '<rect x="0" y="%d" width="%d" height="%d" fill="%s" fill-opacity="%.3f"/><rect x="0" y="%d" width="%d" height="3" fill="%s" fill-opacity="%.3f"/>' % (
        y0, W, H - y0, BG, 0.95 * op, y0, W, col, op)
    i = [x["id"] for x in STEPS].index(s["id"]) + 1
    b += text(60, y0 + 36, "STEP %d OF %d  ·  %s" % (i, len(STEPS), ACTS[s["act"]][0]), 17, col, weight=700, op=op, spacing=2.5)
    b += write(60, y0 + 84, N[s["a"]][5], 40, seg(u, 0.5, 1.5, out), weight=600, op=op)
    xa = 60 + len(N[s["a"]][5]) * 20.5 + 26
    go = seg(u, 1.6, 3.0)
    b += polyline([(xa, y0 + 71), (xa + 30 + 60 * go, y0 + 71)], col, 5, op) + head((xa + 40 + 60 * go, y0 + 71), (1, 0), col, 18, op)
    b += write(xa + 128, y0 + 84, N[s["b"]][5], 40, seg(u, 2.4, 3.4, out), weight=600, op=op)
    rows = [("WHAT MOVES", s["what"], 2.8), ("WHY", s["why"], 5.0)]
    if s.get("rule"):
        rows.append(("THE RULE", s["rule"], 7.0))
    if s.get("border"):
        rows.append(("THE BORDER", s["border"], 7.0 if not s.get("rule") else 8.0))
    y = y0 + 126
    for name, words, at in rows:
        o = op * seg(u, at, at + 0.7)
        dy = 16 * (1 - seg(u, at, at + 0.7, out))     # each row rises into place as it appears, one at a time
        b += text(60, y + dy, name, 13.5, LINE if name == "THE BORDER" else col, weight=700, op=o, spacing=2)
        for l in wrap(words, 22, 1070):
            b += text(214, y + 2 + dy, l, 22, INK, op=o)
            y += 29
        y += 7
    return b


HOOK = STORY.get("hook")


def hook1_scene(t, sc):
    """Ten gains, each measured, stacked; and beside them the ten measured together."""
    u, end, c = t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    b = text(120, 96, "ONE WEEK IN NOVEMBER", 22, DIM, weight=700, op=op, spacing=4)
    base, k, x0, bw = 860, 92.0, 300, 250
    b += '<line x1="200" y1="%d" x2="1280" y2="%d" stroke="%s" stroke-opacity="%.3f" stroke-width="2"/>' % (base, base, DIM, op)
    each, y, total = (c[1] - c[0] - 0.8) / len(HOOK["claims"]), base, 0.0
    for i, (run, v) in enumerate(HOOK["claims"]):
        a = c[0] + i * each
        land = seg(u, a, a + 0.75, back)
        hgt = v * k
        y -= hgt
        if u >= a:
            total += v * seg(u, a, a + 0.6)
            yy = y - 260 * (1 - land)
            b += '<rect x="%d" y="%.1f" width="%d" height="%.1f" rx="5" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-width="2" stroke-opacity="%.3f"/>' % (
                x0, yy + 2, bw, hgt - 4, mix(CPU, BG, 0.45 + 0.12 * (i % 2)), op * seg(u, a, a + 0.3), CPU, op * seg(u, a, a + 0.3))
            if hgt > 28:
                b += text(x0 + bw / 2, yy + hgt / 2 + 9, "+%.2f" % v, 24, INK, "middle", 500, SERIF, op * seg(u, a + 0.4, a + 0.9))
            b += text(x0 - 16, yy + hgt / 2 + 6, run, 15, DIM, "end", family=MONO, op=op * seg(u, a + 0.4, a + 0.9))
    b += text(x0 + bw / 2, base + 44, "ten changes, each one tested", 24, INK, "middle", op=op * seg(u, c[0], c[0] + 1.0))
    b += text(x0 + bw + 40, y + 60, "+%.2f" % total, 76, CPU, weight=600, family=SERIF, op=op * seg(u, c[0] + 0.3, c[0] + 1.0))
    b += write(x0 + bw + 44, y + 100, "points a seat, added together", 24, seg(u, c[1], c[1] + 1.2), DIM, op=op)
    # the same ten, measured at once
    x1 = 1000
    full, o2 = sum(v for _, v in HOOK["claims"]) * k, op * seg(u, c[2], c[2] + 0.8)
    fall = seg(u, c[3], c[3] + 1.6)
    hh = full * (1 - fall)
    b += '<rect x="%d" y="%.1f" width="%d" height="%.1f" rx="5" fill="none" stroke="%s" stroke-width="2.5" stroke-dasharray="10 9" stroke-opacity="%.3f"/>' % (x1, base - hh, bw, max(hh, 0.1), LINE, o2 * (1 - 0.7 * fall))
    b += text(x1 + bw / 2, base + 44, "all ten, measured together", 24, INK, "middle", op=o2)
    b += write(x1 + bw / 2, base - full - 22, "what we expected", 22, seg(u, c[2] + 0.4, c[2] + 1.4), LINE, "middle", op=op * (1 - fall))
    pd, pe, pn = HOOK["proof"]
    o3 = op * seg(u, c[3] + 1.0, c[3] + 1.8)
    b += '<rect x="%d" y="%.1f" width="%d" height="5" fill="%s" fill-opacity="%.3f"/>' % (x1, base - 2.5 - pd * k, bw, RED, o3)
    b += '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="3" stroke-opacity="%.3f"/>' % (x1 + bw / 2, base - (pd + 2 * pe) * k, x1 + bw / 2, base - (pd - 2 * pe) * k, RED, o3)
    b += write(x1 + bw / 2, base - 70, "%+.2f ± %.2f" % (pd, pe), 64, seg(u, c[3] + 1.0, c[3] + 2.0), RED, "middle", 600, SERIF, op)
    b += text(x1 + bw / 2, base - 132, "what %s games said" % format(pn, ","), 22, DIM, "middle", op=o3)
    return b


def hook2_scene(t, sc):
    """Every trial by its first read, the curve of no effect at all drawn over it, and the winners going home."""
    u, end, c = t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    hist, n = HOOK["hist"], HOOK["trials"]
    x0, x1, base, top = 200, 1260, 800, 250
    bw = (x1 - x0) / len(hist)
    sy = (base - top) / max(hist)
    b = text(120, 96, "%s CHANGES, EACH PLACED BY HOW IT SCORED" % format(n, ","), 22, DIM, weight=700, op=op, spacing=4)
    b += '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-opacity="%.3f" stroke-width="2"/>' % (x0 - 20, base, x1 + 20, base, DIM, op)
    win = seg(u, c[2], c[2] + 0.8)
    home = seg(u, c[3], c[3] + 2.2)
    for i, h_ in enumerate(hist):
        a = 3.4 + i * (c[0] - 4.6) / len(hist)
        g = seg(u, a, a + 1.0, out)
        tail = i >= 12
        hh = h_ * sy * g * (1 - home if tail else 1)
        b += '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" fill="%s" fill-opacity="%.3f"/>' % (x0 + i * bw + 3, base - hh, bw - 6, hh, mix(GPU, LINE, win) if tail else GPU, op * 0.85)
        if i % 2 == 0:
            b += text(x0 + i * bw, base + 34, "%+d" % (i / 2 - 4) if i != 8 else "0", 20, DIM, "middle", family=SERIF, op=op)
    b += text(x1, base + 34, "+4", 20, DIM, "middle", family=SERIF, op=op) + text((x0 + x1) / 2, base + 76, "its score, in units of its own error", 22, DIM, "middle", op=op)
    # the bell of no effect: the same number of trials, each worth exactly nothing
    pts = []
    for j in range(161):
        z = -4 + j * 0.05
        pts.append((x0 + (z + 4) / 8 * (x1 - x0), base - n * 0.5 * math.exp(-z * z / 2) / math.sqrt(2 * math.pi) * sy))
    _, part, _ = along(pts, seg(u, c[0], c[0] + 2.4))
    b += polyline(part, LINE, 5, op * (1 if u >= c[0] else 0))
    b += write(x1 - 250, top + 70, "if none of them did anything", 26, seg(u, c[0] + 1.2, c[0] + 2.4), LINE, op=op)
    b += write((x0 + x1) / 2, top - 44, "the same curve", 54, seg(u, c[1], c[1] + 1.0), INK, "middle", 600, SERIF, op)
    xt = x0 + 12 * bw
    b += polyline([(xt, base - 150), (xt, base - 170), (x1 - 60, base - 170), (x1 - 60, base - 150)], LINE, 3, op * win * (1 - home))
    b += write((xt + x1 - 60) / 2, base - 186, "the best: kept", 26, win, LINE, "middle", 600, op=op * (1 - home))
    # and measured again, they go home: each winner to where a fresh draw puts it
    for j in range(54):
        q = (j * 0.6180339887) % 1.0
        zs = 2.0 + 1.3 * q * q
        ze = math.sqrt(-2 * math.log(1 - 0.98 * ((j * 0.7548776662 + 0.31) % 1.0))) * math.cos(6.2831853 * ((j * 0.5698402909 + 0.17) % 1.0))
        hy = 24 + (j * 37 % 110)
        z = lerp(zs, ze, seg(u, c[3] + 0.012 * j, c[3] + 1.9 + 0.012 * j))
        b += '<circle cx="%.1f" cy="%.1f" r="6" fill="%s" fill-opacity="%.3f"/>' % (x0 + (z + 4) / 8 * (x1 - x0), base - hy, LINE, op * win * 0.95)
    b += write((x0 + x1) / 2, base - 196, "measured again", 30, seg(u, c[3] + 1.4, c[3] + 2.4), LINE, "middle", 600, op=op)
    return b


def hook3_scene(t, sc):
    """The scale of the problem, to scale: what one game's luck is worth beside what a real improvement is."""
    u, end, c = t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    k, x0 = 118.0, 200
    b = text(120, 96, "SIGNAL, AND NOISE, TO SCALE", 22, DIM, weight=700, op=op, spacing=4)
    g1, g2 = seg(u, 1.0, 3.0), seg(u, c[0] - 1.6, c[0] - 0.4)
    b += '<rect x="%d" y="250" width="%.1f" height="74" rx="8" fill="%s" fill-opacity="%.3f"/>' % (x0, HOOK["swing"] * k * g1, GPU, op * 0.85)
    b += write(x0, 228, "the luck of a single game: %.1f points" % HOOK["swing"], 34, seg(u, 1.2, 2.6), INK, op=op)
    b += '<rect x="%d" y="430" width="%.1f" height="74" rx="8" fill="%s" fill-opacity="%.3f"/>' % (x0, HOOK["gain"] * k * g2, LINE, op)
    b += write(x0, 408, "a real improvement to the game: %.2f points" % HOOK["gain"], 34, g2, LINE, op=op)
    b += write(x0, 660, "This is the story of one machine that learns to play a game,", 44, seg(u, c[1], c[1] + 2.4), INK, weight=500, family=SERIF, op=op)
    b += write(x0, 726, "and of the borders it built against its own luck.", 44, seg(u, c[2], c[2] + 2.2), INK, weight=500, family=SERIF, op=op)
    return b


def title_scene(t, sc):
    u = t - sc["t0"]
    op = appear(u, 0.3, sc["t1"] - sc["t0"], 0.7)
    return (text(W / 2, 430 + 18 * (1 - seg(u, 0.3, 1.4, out)), STORY["title"], 96, INK, "middle", 700, op=op) +
            text(W / 2, 510, STORY["subtitle"], 36, DIM, "middle", op=op * seg(u, 1.2, 2.2)) +
            text(W / 2, 640, STORY["byline"], 24, FAINT, "middle", op=op * seg(u, 2.0, 3.0), family=MONO))


def big_arrow(a, b, col, p, op, label, off=0):
    if op <= 0.004:
        return ""
    q, part, d = along([a, b], p)
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    return polyline(part, col, 9, op) + head(q, d, col, 30, op) + text(mx + off, my + 4, label, 24, INK, "start" if off > 0 else "end", 600, op=op * seg(p, 0.6, 1.0))


def whole_scene(t, sc):
    """The whole: the territories and the few arrows between them, each drawn when the narration reaches its cue."""
    u, end, c = t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    wh = STORY.get("whole", {})
    b = text(60, 62, wh.get("head", "THE WHOLE, IN ONE PICTURE"), 22, INK, weight=700, op=appear(u, 0.4, end, 0.6), spacing=3)
    for ar in wh.get("arrows", []):
        if ar["cue"] < len(c):
            a = c[ar["cue"]] + ar.get("lag", 0)
            b += big_arrow(tuple(ar["a"]), tuple(ar["b"]), ar["col"], seg(u, a, a + 1.2), appear(u, a, end), ar["words"], ar.get("off", 26))
    return b


def borders_scene(t, sc):
    """The borders: each lit when it is named, with what it takes to cross it."""
    u, end, c = t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    bd = STORY.get("borders", {})
    b = text(60, 62, bd.get("head", "THE BORDERS"), 22, INK, weight=700, op=appear(u, 0.4, end, 0.6), spacing=3)
    for i, r in enumerate(bd.get("rows", [])):
        if i >= len(c):
            break
        a, col = c[i], r["col"]
        o = appear(u, a, end, 0.6)
        pulse = 0.5 + 0.5 * math.sin((u - a) * 5) if a <= u < a + 5 else 0.0
        b += polyline([tuple(q) for q in r["pts"]], col, 5 + 5 * pulse, o * (0.5 + 0.5 * pulse))
        y = 836 + i * 56
        b += '<rect x="60" y="%d" width="16" height="16" rx="3" fill="%s" fill-opacity="%.3f"/>' % (y - 15, col, o)
        b += text(92, y, r["name"], 28, INK, weight=600, op=o) + text(420, y, r["need"], 28, DIM, op=o * seg(u, a + 0.8, a + 1.6))
    return b


def act_scene(t, sc):
    u, (name, sub, col) = t - sc["t0"], ACTS[sc["act"]]
    op = appear(u, 0.2, sc["t1"] - sc["t0"], 0.6)
    n = sum(1 for s in STEPS if s["act"] == sc["act"])
    return ('<rect x="0" y="390" width="%d" height="300" fill="%s" fill-opacity="%.3f"/>' % (W, BG, 0.90 * op) +
            '<rect x="0" y="390" width="%d" height="4" fill="%s" fill-opacity="%.3f"/>' % (W, col, op) +
            text(W / 2, 520, name, 84, col, "middle", 700, op=op, spacing=5) + text(W / 2, 584, sub, 34, INK, "middle", op=op * seg(u, 0.8, 1.6)) +
            text(W / 2, 646, "%d arrow%s, one at a time" % (n, "" if n == 1 else "s"), 22, DIM, "middle", op=op * seg(u, 1.4, 2.2), family=MONO))


def journey_scene(t, sc):
    j, u = sc["journey"], t - sc["t0"]
    op = appear(u, 0.3, sc["t1"] - sc["t0"], 0.6)
    b = text(60, 58, j["title"].upper(), 24, j["col"], weight=700, op=op, spacing=3) + text(60, 90, j["sub"], 19, DIM, op=op)
    b += '<rect x="0" y="800" width="%d" height="280" fill="%s" fill-opacity="%.3f"/><rect x="0" y="800" width="%d" height="3" fill="%s" fill-opacity="%.3f"/>' % (W, BG, 0.95 * op, W, j["col"], op)
    i, a, c = leg_at(sc, u)
    if i >= 0:
        sid, words = j["legs"][i]
        o = appear(u, a, c + 0.2, 0.4) * op
        b += text(60, 852, "%d OF %d  ·  %s  to  %s" % (i + 1, len(j["legs"]), N[SI[sid]["a"]][5], N[SI[sid]["b"]][5]), 18, j["col"], weight=700, op=o, spacing=2)
        for k, l in enumerate(wrap(words, 36, 1230)):
            b += text(60, 912 + k * 48, l, 36, INK, weight=500, op=o)
    else:
        b += text(60, 912, "The same arrows, with one real thing travelling over them.", 36, INK, weight=500, op=appear(u, 0.5, sc["cues"][0], 0.4))
    return b


def pattern_scene(t, sc):
    u, cu = t - sc["t0"], sc["cues"]
    op = appear(u, 0.4, sc["t1"] - sc["t0"], 0.7)
    each = (cu[1] - cu[0] - 1.0) / len(PATTERN)
    b = text(W / 2, 150, "One shape, at every border", 64, INK, "middle", 700, op=op)
    bw, gap, x0, y = 262, 34, 78, 230
    for i, (name, sub) in enumerate(PATTERN):
        o = op * seg(u, cu[0] + i * each, cu[0] + i * each + 0.8)
        x = x0 + i * (bw + gap)
        b += '<rect x="%d" y="%d" width="%d" height="120" rx="14" fill="%s" stroke="%s" stroke-width="2.5" fill-opacity="%.3f" stroke-opacity="%.3f"/>' % (x, y, bw, PANEL, INK, o, o)
        b += text(x + bw / 2, y + 52, name, 32, INK, "middle", 700, op=o)
        for k, l in enumerate(wrap(sub, 17, bw - 24)):
            b += text(x + bw / 2, y + 82 + k * 21, l, 17, DIM, "middle", op=o)
        if i:
            b += polyline([(x - gap + 4, y + 60), (x - 8, y + 60)], INK, 3, o) + head((x - 4, y + 60), (1, 0), INK, 12, o)
    b += polyline([(x0 + 5 * (bw + gap) + bw / 2, y + 120), (x0 + 5 * (bw + gap) + bw / 2, y + 150), (x0 + bw / 2, y + 150), (x0 + bw / 2, y + 126)], DIM, 2.5, op * seg(u, cu[1] - 1.2, cu[1] - 0.2), True)
    for r, (name, col, cells) in enumerate(PATTERN_ROWS):
        a = cu[1 + r]
        yy = 452 + r * 124
        o = op * seg(u, a, a + 0.8)
        b += text(x0, yy - 16, name.upper(), 20, col, weight=700, op=o, spacing=2.5)
        for i, c in enumerate(cells):
            oo = op * seg(u, a + 0.3 + i * 0.28, a + 0.9 + i * 0.28)
            x = x0 + i * (bw + gap)
            b += '<rect x="%d" y="%d" width="%d" height="78" rx="10" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-opacity="%.3f" stroke-width="2"/>' % (x, yy, bw, col, 0.13 * oo, col, oo)
            for k, l in enumerate(wrap(c, 21, bw - 20)):
                b += text(x + bw / 2, yy + (46 if len(wrap(c, 21, bw - 20)) == 1 else 34) + k * 26, l, 21, INK, "middle", 500, op=oo)
    for k, l in enumerate(["A guess is cheap. A crossing is earned, on seeds the guess never saw.", "And every verdict goes back to where the guess was made."]):
        b += text(78, 880 + k * 46, l, 33, INK, weight=500, op=op * seg(u, cu[4] + k * 1.6, cu[4] + 1.0 + k * 1.6))
    return b


def end_scene(t, sc):
    u = t - sc["t0"]
    op = appear(u, 0.3, sc["t1"] - sc["t0"], 0.8)
    cr = STORY.get("credits", [])
    y0 = 400 if cr else 470
    b = (text(W / 2, y0, STORY["closing"][0], 56, INK, "middle", 600, op=op) +
         text(W / 2, y0 + 76, STORY["closing"][1], 56, INK, "middle", 600, op=op * seg(u, TL.lead + 9 * 60.0 / WPM, TL.lead + 9 * 60.0 / WPM + 1.0)))
    # THE CREDITS, under the close (Paul, 13 November: "MIT License Paul Richeson Team Pair under Orrery and treadcore.org")
    for i, l in enumerate(cr):
        b += text(W / 2, y0 + 190 + i * 44, l, 30 if i == 0 else 24, INK if i < 2 else DIM, "middle", 700 if i == 0 else 400, op=op * seg(u, 6.0 + i * 0.5, 6.8 + i * 0.5))
    return b


def frame(t):
    sc = scene_at(t)
    cx, cy, z = camera(t)
    over = {"hook1": hook1_scene, "hook2": hook2_scene, "hook3": hook3_scene, "title": title_scene, "whole": whole_scene, "borders": borders_scene, "act": act_scene, "journey": journey_scene,
            "pattern": pattern_scene, "end": end_scene}.get(sc["kind"])
    ui = (over(t, sc) if over else lower(t, sc) + minimap(t, sc) + crumbs(t, sc)) + teleprompter(t, sc)
    bar = '<rect x="0" y="%d" width="%.1f" height="4" fill="%s" fill-opacity="0.55"/>' % (H - 4, W * t / LENGTH, INK)
    tr = "translate(%.2f %.2f) scale(%.5f) translate(%.2f %.2f)" % (W / 2, H / 2, z, -cx, -cy)
    # The map leaves for the last two scenes: the one shape is drawn on an empty page.
    gone = seg(t, PATTERN_T, PATTERN_T + 1.0)
    if gone > 0:
        tr += '" opacity="%.3f' % (1 - gone)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d"><rect width="%d" height="%d" fill="%s"/><g transform="%s">%s</g>%s%s</svg>') % (
        W, H, W, H, W, H, BG, tr, the_map(t), ui, bar)


def render(svg, png):
    film.render(svg, png, W, H)


def chapters():
    out, n = [], 0
    for s in SCENES:
        k = s["kind"]
        if k == "step":
            n += 1
            st = SI[s["step"]]
            out.append((s["t0"], "%d. %s to %s" % (n, N[st["a"]][5], N[st["b"]][5]), st))
        elif k == "journey":
            out.append((s["t0"], s["journey"]["title"], None))
        elif k == "act":
            out.append((s["t0"], ACTS[s["act"]][0].capitalize(), None))
        else:
            out.append((s["t0"], dict({"hook1": "Ten gains, worth nothing", "hook2": "The same curve", "hook3": "Signal and noise", "title": "Title", "whole": "The whole, in one picture",
                                  "borders": "The borders", "pattern": "One shape, at every border", "end": "The close, and the credits"}, **STORY.get("chapter_names", {}))[k], None))
    return out


def script(out_dir):
    """The teleprompt as files: captions for the film (WebVTT) and the whole narration with its times."""
    names = {round(t0, 1): name for t0, name, _ in chapters()}
    return film.captions(TL, lambda sc: names[round(sc["t0"], 1)], out_dir, STORY["title"])


def page(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    cards, nav = [], []
    for t0, name, st in chapters():
        nav.append('<button data-t="%.1f"><span>%s</span>%s</button>' % (t0, clock(t0), esc(name)))
        if not st:
            continue
        svg = frame(t0 + 9.4)
        open(os.path.join(out_dir, "step-%s.svg" % st["id"]), "w").write(svg)
        col = REGIONS[N[st["a"]][0]]["col"]
        rows = "".join("<dt>%s</dt><dd%s>%s</dd>" % (k, ' class="say"' if f == "say" else "", esc(st[f]))
                       for k, f in (("What moves", "what"), ("Why", "why"), ("The rule", "rule"), ("The border", "border"), ("Narration", "say")) if st.get(f))
        cards.append('<article class="step" style="--c:%s"><header><button class="seek" data-t="%.1f" aria-label="Play this step in the film">&#9654; %s</button>'
                     '<h3>%s</h3><p class="path"><b>%s</b> <i>&rarr;</i> <b>%s</b> <span>%s</span></p></header>'
                     '<img loading="lazy" src="@SLUG@/step-%s.svg" alt="The block diagram with the arrow from %s to %s lit" width="1920" height="1080"><dl>%s</dl></article>' % (
                         col, t0, clock(t0), esc(name.split(". ", 1)[0] + ". " + ACTS[st["act"]][0].capitalize()), esc(N[st["a"]][5]), esc(N[st["b"]][5]), esc(st["moves"]),
                         st["id"], esc(N[st["a"]][5]), esc(N[st["b"]][5]), rows))
    words = script(out_dir)
    html = (PAGE.replace("@NAV@", "".join(nav)).replace("@CARDS@", "".join(cards)).replace("@LEN@", clock(LENGTH)).replace("@N@", str(len(STEPS)))
            .replace("@WPM@", str(WPM)).replace("@WORDS@", format(words, ","))
            .replace("process/", SLUG + "/").replace("@SLUG@", SLUG).replace("How the Game Learns", STORY["title"].title() if STORY["title"].islower() else STORY["title"])
            .replace("process_film.py</code>, how a block", "process_film.py</code>, how a block"))
    dst = os.path.join(os.path.dirname(out_dir), "%s-film.html" % SLUG)
    open(dst, "w").write(html)
    print("%s: %d steps; %s" % (dst, len(cards), out_dir))


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>How the Game Learns</title>
<style>
:root { --bg:#f6f4ee; --ink:#1b1c1f; --dim:#5d5c57; --line:#d8d5cb; --tile:#fffdf8; --accent:#1c5cab; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#0e1013; --ink:#ece9e1; --dim:#9a978d; --line:#2a2d33; --tile:#15181d; --accent:#6aa5ee; } }
:root[data-theme="dark"] { --bg:#0e1013; --ink:#ece9e1; --dim:#9a978d; --line:#2a2d33; --tile:#15181d; --accent:#6aa5ee; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:17px/1.55 "Avenir Next", "Helvetica Neue", Helvetica, Arial, sans-serif; }
main { max-width:1180px; margin:0 auto; padding:28px 16px 80px; }
h1 { font-size:clamp(30px,5vw,52px); line-height:1.08; margin:.2em 0 .25em; text-wrap:balance; }
.lede { color:var(--dim); max-width:62ch; margin:0 0 22px; }
.eyebrow { font:600 12px/1 Menlo, monospace; letter-spacing:.14em; text-transform:uppercase; color:var(--dim); }
.stage { position:sticky; top:0; z-index:5; background:var(--bg); padding:8px 0 10px; border-bottom:1px solid var(--line); }
video { display:block; width:100%; max-height:62vh; background:#0e1013; border-radius:10px; }
nav { display:flex; gap:6px; overflow-x:auto; padding:10px 0 2px; scrollbar-width:thin; }
nav button, .seek { font:inherit; font-size:13px; white-space:nowrap; color:var(--ink); background:var(--tile); border:1px solid var(--line); border-radius:999px; padding:5px 11px; cursor:pointer; }
nav button span { font-family:Menlo, monospace; font-size:11px; color:var(--dim); margin-right:7px; }
nav button.on, nav button:hover, .seek:hover { border-color:var(--accent); color:var(--accent); }
h2 { font-size:26px; margin:44px 0 6px; }
.how { color:var(--dim); max-width:70ch; }
.step { background:var(--tile); border:1px solid var(--line); border-left:5px solid var(--c); border-radius:12px; padding:16px 18px 6px; margin:18px 0; }
.step header { display:grid; grid-template-columns:auto 1fr; gap:4px 14px; align-items:center; }
.step h3 { margin:0; font-size:13px; letter-spacing:.12em; text-transform:uppercase; color:var(--dim); font-weight:600; }
.step .path { grid-column:1 / -1; margin:2px 0 10px; font-size:clamp(20px,3vw,28px); line-height:1.2; }
.step .path i { color:var(--c); font-style:normal; padding:0 .2em; }
.step .path span { display:inline-block; font-size:14px; border:1px solid var(--c); border-radius:999px; padding:1px 10px; margin-left:8px; vertical-align:middle; color:var(--dim); }
.step img { display:block; width:100%; height:auto; border-radius:8px; }
dl { display:grid; grid-template-columns:8.5em 1fr; gap:6px 14px; margin:14px 0 10px; }
dt { font-size:12px; letter-spacing:.1em; text-transform:uppercase; color:var(--dim); font-weight:600; padding-top:4px; }
dd { margin:0; }
dl.made { grid-template-columns:10em 1fr; max-width:900px; }
code { font-family:Menlo, monospace; font-size:.88em; }
.how a { color:var(--accent); }
dd.say { font-family:"Iowan Old Style", Palatino, Georgia, serif; font-size:18px; line-height:1.6; color:var(--ink); border-left:3px solid var(--line); padding-left:14px; }
.files a { color:var(--accent); }
@media (max-width:640px) { dl { grid-template-columns:1fr; gap:0 0; } dt { padding-top:10px; } }
</style></head><body><main>
<p class="eyebrow">Orreryq &middot; treadcore &middot; 13 November 2026</p>
<h1>How the Game Learns</h1>
<p class="lede">One block diagram, walked arrow by arrow, from the outside in. The film is @LEN@ long and has no sound. Its narration, @WORDS@ words, scrolls in the corner at @WPM@ words a minute, the word to be spoken lit, for whoever reads it aloud; the same words are the film's captions. Under it, every one of its @N@ arrows as a still, with what moves along it, why, the rule at the border, and what is said.</p>
<div class="stage"><video id="film" controls preload="metadata" playsinline poster="process/poster.png" src="process/film.mp4"><track kind="captions" srclang="en" label="Narration" src="process/captions.vtt"></video><nav id="nav">@NAV@</nav></div>
<p class="how files">The narration as a script with its times: <a href="process/teleprompt.txt">teleprompt.txt</a>. As captions: <a href="process/captions.vtt">captions.vtt</a>.</p>
<h2>Every arrow, in order</h2>
<p class="how">Each card is one step of the film. The picture is the whole diagram at that moment, with the arrow lit and the small map in its corner showing where the step sits. The button plays that step in the film above.</p>
@CARDS@
<h2>How the film is made</h2>
<p class="how">The film is one file of words and positions (<a href="process/storyboard.json">storyboard.json</a>) drawn by two scripts: <code>tools/report/film.py</code>, what any such film shares, and <code>tools/report/process_film.py</code>, how a block diagram is walked. Another process is another storyboard.</p>
<dl class="made">
<dt>The words first</dt><dd>Each scene is exactly as long as its narration at @WPM@ words a minute, with a breath before and after. A mark in the narration is a cue, and the picture's moves are written against cues, so the picture can never run ahead of what is said.</dd>
<dt>One stage</dt><dd>The diagram is drawn once, every block in its place for the whole film. Scenes move a camera over it and change what is lit. The viewer learns the map once and is never shown a second one.</dd>
<dt>A function of time</dt><dd>Every frame is computed from its time alone; nothing accumulates. A property is a tween between two times on an easing curve. So any frame renders by itself, a still for this page is the same call as a frame of the film, and the frames render a core each.</dd>
<dt>Gather, go, land</dt><dd>A move has three parts. The source dips as the token sets out, the token eases away and eases in with a trail behind it, the destination swells as it arrives. One thing moves at a time; a row of words rises into place only while nothing else is moving.</dd>
<dt>The border</dt><dd>Where an arrow leaves one territory a ring opens on the border, and the token takes the colour of the territory it enters: what crosses is no longer the first territory's.</dd>
<dt>The cold open</dt><dd>Before the title, a true thing that should not be possible: ten changes that each tested as a gain and together measured as nothing; then why (every trial the search made, lying on the curve of pure chance); then the question the film answers.</dd>
<dt>Outside in</dt><dd>After the title it opens far off on the whole, names three territories, then the four borders and their price, then goes inside one loop at a time. Each step carries the path down to it in the top left and a small map of the whole in the top right, so no step is seen out of its place.</dd>
<dt>Pace</dt><dd>A step runs 12 to 24 seconds: the camera arrives in a second and a half, the arrow draws, the token travels for 3.4 seconds and sets out again every 5.6 while the step is told; what moves appears at 2.8 seconds, why at 5, the rule at 7, the border at 8.</dd>
</dl>
</main><script>
const v = document.getElementById('film'), nav = [...document.querySelectorAll('#nav button')];
document.addEventListener('click', e => { const b = e.target.closest('[data-t]'); if (!b) return; v.currentTime = +b.dataset.t; v.play(); if (b.classList.contains('seek')) window.scrollTo({top: 0, behavior: 'smooth'}); });
v.addEventListener('timeupdate', () => { let on = null; for (const b of nav) if (+b.dataset.t <= v.currentTime + .05) on = b; nav.forEach(b => b.classList.toggle('on', b === on)); if (on && !v.paused) on.scrollIntoView({block: 'nearest', inline: 'center'}); });
</script></body></html>
"""


def main(a):
    out_dir = OUT_DIR
    if a[:1] == ["youtube"]:
        # the kit a person takes to YouTube: output/youtube/SLUG/, outside the repository (.gitignore: output/)
        dst = os.path.join(os.environ.get("ORRERY_OUTPUT") or os.path.join(ROOT, "output"), "youtube", SLUG)
        master = a[1] if len(a) > 1 else os.path.join(out_dir, "film.mp4")
        made = film.youtube(TL, [(t0, name) for t0, name, _ in chapters()], dst, SLUG, STORY.get("youtube_title") or STORY["title"], STORY.get("blurb", STORY.get("subtitle", "")),
                            STORY.get("credits", []), master, os.path.join(out_dir, "poster.png"),
                            "Made by orrery (tools/report/process_film.py) on %s. https://treadcore.org" % __import__("time").strftime("%Y-%m-%d"))
        print("%s: %s" % (dst, ", ".join(made)))
    elif a[:1] == ["list"]:
        for t0, name, _ in chapters():
            print("%6.1f  %s  %s" % (t0, clock(t0), name))
        print("%6.1f  the end" % LENGTH)
    elif a[:1] == ["still"] and len(a) == 3:
        render(frame(float(a[1])), a[2])
        print(a[2])
    elif a[:1] == ["page"]:
        page(out_dir)
    elif a[:1] == ["film"]:
        os.makedirs(out_dir, exist_ok=True)
        out = a[1] if len(a) > 1 else os.path.join(out_dir, "film.mp4")
        n = film.render_film(frame, LENGTH, FPS, (W, H), out, poster_at=WH["t1"] - 3.0)
        print("%s: %d frames, %s" % (out, n, clock(LENGTH)))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
