#!/usr/bin/env python3
"""hearth-auto_film: the film of *Holding the Room* (docs/hearth-auto-lab-report.md), by docs/film-directive.md.

    python3 tools/report/hearth-auto_film.py list                  the scenes and when each begins
    python3 tools/report/hearth-auto_film.py still T OUT.png       the frame at T seconds, to look at one
    python3 tools/report/hearth-auto_film.py film OUT.mp4 [DIR]    every frame (kept in DIR, so a run stopped is taken up), then the film
    python3 tools/report/hearth-auto_film.py page                  docs/hearth-auto-film.html and a still of each step
    python3 tools/report/hearth-auto_film.py youtube MASTER.mp4    the kit: output/youtube/hearth-auto/ (not the repository)

The storyboard is docs/hearth-auto/storyboard.json and the map, the steps, the title, the whole, the borders
and the close are drawn by process_film.py as they are for any storyboard. This file is what process_film.py
--story cannot draw for this report, and nothing else:

THE COLD OPEN. This report's own: the room's two thermometers, inside two Geiger counters on one machine, and
the two things a counter says that are not a temperature (section III); the first pass on the live fleet, which
said to shed 446 W and did nothing (section VIII); and what the controller has not done (section X).

SCENES AFTER AN ACT. A storyboard's "after" names scenes told when an act's arrows are walked, each on an empty
page: the house's balance and the bound one evening gives on its loss, the first live pass in the plan's own words with the four things worth a decision, the simulated room's
table as bars, and the report's three pictures of Orrery, each with what the narration names ringed at its cue.
The third picture is a made-up plan in a scratch queue and says so for as long as it is shown. process_film's
timeline has no place for these, so the timeline is built again here, the same but for them.

DONE, AND NOT DONE. Where the process film draws the one shape every border shares, this one draws the report's
last sections as two columns: what was measured, built, proved and run, and what was not.

THE RENDER. This Mac is the fleet's coordinator, so frames are drawn by two processes, not one a core
(FILM_PROCS), and kept as they are made.

Every number drawn here is read from the storyboard, where it was copied from the report, from its companion
docs/hearth-controller.md, or is in the report's own pictures.
"""
import base64
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
if "--story" not in sys.argv:
    sys.argv += ["--story", os.path.join(ROOT, "docs", "hearth-auto", "storyboard.json")]
import film  # noqa: E402
import process_film as pf  # noqa: E402
from film import seg, appear, out  # noqa: E402
from process_film import text, write, wrap, polyline, head, along, W, H, BG, INK, DIM, FAINT, PANEL, MAIN, CPU, GPU, LINE, RED, SERIF, MONO  # noqa: E402

HOOK, STORY, NAR = pf.HOOK, pf.STORY, pf.NAR
AFTER = STORY.get("after", {})
EXTRA = [k for ks in AFTER.values() for k in ks]


# ---- the timeline: process_film's, with the scenes an act is followed by ---------------------------------------

def timeline():
    tl = film.Timeline(pf.WPM, pf.LEAD, pf.TAIL)
    for k in ("hook1", "hook2", "hook3", "title", "whole", "borders"):
        tl.say(k, NAR[k])
    acts = []
    for s in pf.STEPS:
        if s["act"] not in acts:
            acts.append(s["act"])
    for act in acts:
        tl.say("act", NAR["act:" + act], act=act)
        for s in pf.STEPS:
            if s["act"] == act:
                tl.say("step", s["say"], 12.0, step=s["id"])
        for k in AFTER.get(act, []):
            tl.say(k, NAR[k])
    tl.say("pattern", NAR["pattern"])
    tl.say("end", NAR["end"], 12.0)
    return tl


pf.TL = timeline()
pf.SCENES, pf.LENGTH = pf.TL.scenes, pf.TL.t
pf.STEP_T = {s["step"]: s["t0"] for s in pf.SCENES if s["kind"] == "step"}
pf.FIRST_STEP = min(pf.STEP_T.values())
pf.WH = next(s for s in pf.SCENES if s["kind"] == "whole")
pf.PATTERN_T = next(s["t0"] for s in pf.SCENES if s["kind"] == "pattern")
pf.AFTER_STEPS = max(s["t1"] for s in pf.SCENES if s["kind"] == "step")
pf.BORN = {n: pf.node_born(n) for n in pf.N}

# When the map is put away: over each run of scenes that stand on an empty page.
AWAY, _run = [], None
for _s in pf.SCENES:
    if _s["kind"] in EXTRA:
        _run = [_run[0] if _run else _s["t0"], _s["t1"]]
    elif _run:
        AWAY.append(tuple(_run))
        _run = None


def away(t):
    """The share of the map put away at t: gone while a scene stands on an empty page, and not brought back
    for a moment before the ledger takes it away for good."""
    for a, b in AWAY:
        if a - 0.01 <= t <= b:
            return seg(t, a, a + 0.6) * (1.0 if b >= pf.PATTERN_T - 0.01 else 1 - seg(t, b - 0.6, b))
    return 0.0


# ---- what the scenes share --------------------------------------------------------------------------------------

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


# ---- the cold open ----------------------------------------------------------------------------------------------

def hook1_scene(t, sc):
    """The room's two thermometers, where they are, and the two things a counter says that are not a temperature."""
    u, end, c = t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    b = text(120, 96, HOOK["at"] + "  ·  WHAT READS THE ROOM", 22, DIM, weight=700, op=op, spacing=4)
    b += write(120, 204, "Yesterday: no thermometer in the room.", 50, seg(u, 0.8, 2.8), DIM, weight=500, family=SERIF, op=op * (1 - 0.45 * seg(u, c[0], c[0] + 0.8)))
    for i, p in enumerate(HOOK["probes"]):
        x, a = 120 + i * 600, c[0] + 0.2 + i * 0.5
        o = op * seg(u, a, a + 0.7)
        b += plate(x, 250, 560, 300, o, GPU)
        b += text(x + 30, 300, p["key"], 25, GPU, weight=600, family=MONO, op=o)
        b += write(x + 30, 448, p["c"], 150, seg(u, c[1] + 0.2 + i * 1.6, c[1] + 1.0 + i * 1.6), INK, weight=600, family=SERIF, op=op)
        b += text(x + 372, 448, "°C", 56, DIM, family=SERIF, op=op * seg(u, c[1] + 0.8 + i * 1.6, c[1] + 1.4 + i * 1.6))
        b += text(x + 30, 512, p["from"], 23, DIM, op=o)
    b += write(120, 622, "The temperature that is held is their mean: %s °C." % HOOK["mean"], 36, seg(u, c[1] + 3.6, c[1] + 5.2), INK, weight=500, op=op)
    for i, (hd, words) in enumerate((("inside a counter's case", "Both of them, on the same machine. They read %s °C apart." % HOOK["apart"]),
                                     ("not compared", "Neither has been compared with a thermometer in the air."))):
        a = c[2] + i * 3.2
        o, y = op * seg(u, a, a + 0.7), 250 + i * 196
        b += plate(1330, y, 540, 176, o, LINE)
        b += text(1356, y + 46, hd.upper(), 20, LINE, weight=700, op=o, spacing=2.5)
        b += lines(1356, y + 90, words, 26, 500, op=o)
    o = op * seg(u, c[3], c[3] + 0.8)
    b += plate(120, 690, 1170, 330, o, RED)
    b += text(156, 738, "NOT A TEMPERATURE", 20, RED, weight=700, op=o, spacing=2.5)
    for i, n in enumerate(HOOK["non"]):
        b += write(156 + i * 400, 868, n, 130, seg(u, c[3] + 4.8 + i * 1.6, c[3] + 5.6 + i * 1.6), RED, weight=600, family=SERIF, op=op)
    b += write(156, 932, "What a counter says when its thermometer has no reading to give.", 29, seg(u, c[3] + 7.6, c[3] + 9.6), INK, op=op)
    b += text(156, 982, "The +V4 counter sent -0.0 %s times in the first day's telemetry. Both are discarded." % HOOK["non_times"], 25, DIM, op=op * seg(u, c[3] + 9.8, c[3] + 10.6))
    return b


def hook2_scene(t, sc):
    """The first pass on the live fleet: the room against the target, the watts drawn against the watts wanted, the first rung, and nothing done."""
    u, end, c = t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    b = text(120, 96, HOOK["pass_at"] + "  ·  THE FIRST PASS ON THE LIVE FLEET", 22, DIM, weight=700, op=op, spacing=4)
    b += write(120, 196, "How many watts should the fleet be burning?", 56, seg(u, 0.8, 3.4), INK, weight=500, family=SERIF, op=op)
    for i, (hd, big, small, col) in enumerate((("the room", HOOK["room"] + " °C", "the mean of two probes", CPU),
                                               ("the target", HOOK["target"] + " °C", "set for this pass", GPU),
                                               ("the error", HOOK["error"], "target less room, in degrees", LINE))):
        a = c[0] + (2.8, 5.2, 6.4)[i]
        o, x = op * seg(u, a, a + 0.6), 120 + i * 392
        b += plate(x, 244, 372, 214, o, col)
        b += text(x + 26, 290, hd.upper(), 20, col, weight=700, op=o, spacing=2.5)
        b += write(x + 26, 392, big, 92, seg(u, a + 0.1, a + 0.9), col, weight=600, family=SERIF, op=op)
        b += text(x + 26, 434, small, 22, INK, op=o)
    k, x0, y = 1.6, 120, 548
    o = op * seg(u, c[1], c[1] + 0.6)
    g = seg(u, c[1] + 0.2, c[1] + 1.8, out)
    b += text(x0, 520, "THE FLEET'S WATTS AT THE WALL", 20, DIM, weight=700, op=o, spacing=2.5)
    b += '<rect x="%d" y="%d" width="%.1f" height="56" rx="6" fill="%s" fill-opacity="%.3f"/>' % (x0, y, HOOK["drawn"] * k * g, CPU, 0.9 * o)
    b += text(x0 + HOOK["drawn"] * k * g + 16, y + 40, "%d W drawn" % HOOK["drawn"], 34, CPU, weight=600, family=SERIF, op=op * seg(u, c[1] + 1.2, c[1] + 1.9))
    xm = x0 + HOOK["wanted"] * k
    o2 = op * seg(u, c[1] + 3.4, c[1] + 4.2)
    b += '<rect x="%.1f" y="%d" width="5" height="84" fill="%s" fill-opacity="%.3f"/>' % (xm - 2.5, y - 14, LINE, o2)
    b += polyline([(xm + 8, y + 76), (xm + 8, y + 88), (x0 + HOOK["drawn"] * k, y + 88), (x0 + HOOK["drawn"] * k, y + 76)], INK, 3, o2)
    b += text(xm, y + 126, "%d W wanted" % HOOK["wanted"], 24, LINE, "middle", 600, op=o2)
    b += text((xm + x0 + HOOK["drawn"] * k) / 2 + 40, y + 124, "to shed %d W" % HOOK["shed"], 32, INK, "middle", 600, op=o2)
    o = op * seg(u, c[2], c[2] + 0.7)
    b += plate(120, 716, 1170, 120, o, CPU)
    b += text(150, 758, "THE FIRST RUNG", 20, CPU, weight=700, op=o, spacing=2.5)
    b += write(150, 808, HOOK["first"], 36, seg(u, c[2] + 0.2, c[2] + 2.4), INK, weight=500, op=op)
    o = op * seg(u, c[3], c[3] + 0.7)
    b += plate(120, 858, 1170, 160, o, LINE)
    b += write(150, 964, "advise: nothing was done", 84, seg(u, c[3] + 0.2, c[3] + 1.8), LINE, weight=600, family=SERIF, op=op)
    return b


def hook3_scene(t, sc):
    """What the controller has not done, a plate each; then the questions the film answers."""
    u, end, c = t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    b = text(120, 96, "AS FAR AS IT HAS GONE", 22, DIM, weight=700, op=op, spacing=4)
    for i, n in enumerate(HOOK["nots"]):
        a = (2.4, c[0], c[1], c[2])[i]
        o, x = op * seg(u, a, a + 0.7), 60 + i * 456
        b += plate(x, 150, 432, 280, o, RED)
        b += text(x + 26, 196, n["head"], 20, RED, weight=700, op=o, spacing=2.5)
        b += write(x + 26, 276, n["big"], 62, seg(u, a + 0.2, a + 1.0), RED, weight=600, family=SERIF, op=op)
        b += lines(x + 26, 326, n["words"], 24, 384, op=o * seg(u, a + 0.7, a + 1.3))
    for i, q in enumerate(HOOK["questions"]):
        a = c[3] + (0.6, 3.6, 7.6)[i]
        b += write(120, 560 + i * 78, q, 48, seg(u, a, a + 2.0), INK, weight=500, family=SERIF, op=op)
    return b


# ---- the scenes after an act ------------------------------------------------------------------------------------

def pass_scene(t, sc):
    """A page of the report's own lines, four tiles, a conclusion and four cards. Section VIII: the plan's account of the
    first live pass and the four things in it worth a decision. Section XI: the house's balance, the bound one
    evening gives on its loss, and what the next days give."""
    u, end, c = t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    P = STORY[sc["kind"]]
    b = text(60, 86, P["head"], 22, DIM, weight=700, op=op, spacing=4)
    b += plate(60, 116, 1250, 400, op, FAINT)
    y = 160
    for l in P["lines"]:
        a = cue(c, l["cue"], end)
        o = op * seg(u, a, a + 0.7)
        ws = wrap(l["words"], 19.5 * 1.2, 1130)
        for j, w_ in enumerate(ws):
            b += text(88 + (26 if j or l["words"].startswith(" ") else 0), y, w_, 19.5, LINE if l.get("lit") else INK, weight=700 if l.get("lit") else 400, family=MONO, op=o)
            y += 28
        y += 5
    for i, (hd, big) in enumerate(P["tiles"]):
        a = (1.6, 1.6, c[0], c[0] + 3.4)[i]
        o, x = op * seg(u, a, a + 0.6), 60 + i * 316
        col = (CPU, GPU, CPU, LINE)[i]
        b += plate(x, 540, 302, 150, o, col)
        b += text(x + 22, 580, hd.upper(), 18, col, weight=700, op=o, spacing=2.5)
        b += text(x + 22, 656, big, 60, col, weight=600, family=SERIF, op=o)
    b += write(60, 760, P["shed"], 38, seg(u, c[1], c[1] + 2.0), INK, weight=500, op=op)
    b += write(60, 862, P["big"], 72, seg(u, c[1] + 2.6, c[1] + 3.8), LINE, weight=600, family=SERIF, op=op)
    b += write(60, 946, P["ask"], 32, seg(u, c[2], c[2] + 1.4), DIM, op=op)
    for i, d in enumerate(P["decisions"]):
        a = c[2 + i] + (3.0 if i == 0 else 0)
        o, y = op * seg(u, a, a + 0.7), 116 + i * 164
        b += plate(1334, y, 546, 152, o, LINE)
        b += text(1356, y + 36, d["head"], 18, LINE, weight=700, op=o, spacing=2.5)
        b += lines(1356, y + 68, d["words"], 21.5, 508, op=o, lead=1.3)
    return b


def sim_scene(t, sc):
    """Section VII's table of the simulated room, as bars: how close to 21 its third day stays, and what the simulated room is not."""
    u, end, c = t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    S = STORY["sim"]
    b = text(60, 86, S["head"], 21, DIM, weight=700, op=op, spacing=3)
    b += write(60, 178, S["ask"], 52, seg(u, 0.8, 3.0), INK, weight=500, family=SERIF, op=op)
    x0, k = 640, 480.0
    b += '<line x1="%d" y1="212" x2="%d" y2="724" stroke="%s" stroke-opacity="%.3f" stroke-width="2"/>' % (x0, x0, DIM, op)
    for i, r in enumerate(S["rows"]):
        a, y = c[i], 262 + i * 126
        o = op * seg(u, a, a + 0.7)
        ws = wrap(r["name"], 26, 540)
        for j, w_ in enumerate(ws):
            b += text(60, y + j * 33, w_, 26, INK, weight=600, op=o)
        b += text(60, y + len(ws) * 33 + 2, "%d change%s that day" % (r["changes"], "" if r["changes"] == 1 else "s"), 21, DIM, op=o)
        g = seg(u, a + 0.5, a + 1.9, out)
        b += '<rect x="%d" y="%d" width="%.1f" height="58" rx="5" fill="%s" fill-opacity="%.3f"/>' % (x0, y - 30, r["within"] * k * g, r["col"], 0.9 * o)
        b += write(x0 + r["within"] * k * g + 18, y + 12, "within %.2f °C" % r["within"], 40, seg(u, a + 1.2, a + 2.2), r["col"], weight=600, family=SERIF, op=op)
    b += text(60, 766, S["gain"], 24, DIM, op=op * seg(u, c[3] + 4.4, c[3] + 5.2))
    o = op * seg(u, c[4], c[4] + 0.8)
    b += plate(60, 800, 1250, 216, o, LINE)
    b += text(88, 846, "WHAT THE SIMULATED ROOM IS NOT", 20, LINE, weight=700, op=o, spacing=2.5)
    b += lines(88, 896, S["caveat"], 29, 1190, op=o)
    b += write(88, 988, S["caveat2"], 38, seg(u, c[4] + 8.4, c[4] + 9.6), LINE, weight=600, family=SERIF, op=op)
    return b


_PIC = {}


def picture(name):
    if name not in _PIC:
        _PIC[name] = "data:image/png;base64," + base64.b64encode(open(os.path.join(pf.OUT_DIR, name), "rb").read()).decode()
    return _PIC[name]


def picture_scene(t, sc):
    """One of the report's own pictures of Orrery, with what the narration names ringed at its cue, and beside it the words."""
    u, end, c = t - sc["t0"], sc["t1"] - sc["t0"], sc["cues"]
    op = appear(u, 0.2, end, 0.6)
    P = STORY["pictures"][sc["kind"]]
    k, ix, iy = 0.80, 60, 124
    b = text(60, 86, P["head"], 22, LINE if P.get("stamp") else DIM, weight=700, op=op, spacing=4)
    b += '<image x="%d" y="%d" width="%d" height="%d" href="%s" opacity="%.3f"/>' % (ix, iy, 1400 * k, 860 * k, picture(P["file"]), op * seg(u, 0.3, 1.2))
    b += '<rect x="%d" y="%d" width="%d" height="%d" fill="none" stroke="%s" stroke-opacity="%.3f" stroke-width="%d"/>' % (ix, iy, 1400 * k, 860 * k, LINE if P.get("stamp") else FAINT, op, 3 if P.get("stamp") else 1)
    for bx in P["boxes"]:
        a = cue(c, bx["cue"], end) + bx.get("lag", 0.3)
        x, y, w, h = [v * k for v in bx["r"]]
        later = min([cue(c, o_["cue"], end) + o_.get("lag", 0.3) for o_ in P["boxes"] if cue(c, o_["cue"], end) + o_.get("lag", 0.3) > a + 0.01] or [end + 9.0])
        b += ring(ix + x, iy + y, w, h, seg(u, a, a + 1.2), op * (1 - 0.6 * seg(u, later, later + 0.8)))
    for i, p in enumerate(P["plates"]):
        a = cue(c, p["cue"], end)
        o, y = op * seg(u, a, a + 0.7), 124 + i * 196
        b += plate(1220, y, 640, 176, o, p["col"])
        b += text(1246, y + 46, p["head"].upper(), 20, p["col"], weight=700, op=o, spacing=2.5)
        b += lines(1246, y + 88, p["words"], 25, 590, op=o, weight=500)
    last = c[-1] if c else 2.0
    for i, l in enumerate(P["foot"]):
        b += write(60, 896 + i * 62, l, 42, seg(u, last + 1.6 + i * 2.2, last + 3.4 + i * 2.2), LINE if P.get("stamp") else INK, weight=500, family=SERIF, op=op)
    return b


def ledger_scene(t, sc):
    """The report's section X, and what its abstract and method say stands: two columns, each row at its cue."""
    u, cu = t - sc["t0"], sc["cues"]
    op = appear(u, 0.4, sc["t1"] - sc["t0"], 0.7)
    b = text(60, 104, "What was done, and what was not", 60, INK, weight=700, op=op)
    seen = {60: 0, 700: 0}
    for i, (name, words) in enumerate(pf.PATTERN):
        col, x = (RED, 700) if name == "not done" else (MAIN, 60)
        a = cu[min(i, len(cu) - 1)]
        o = op * seg(u, a, a + 0.8)
        y = 150 + seen[x] * 126 + 14 * (1 - seg(u, a, a + 0.8, out))
        seen[x] += 1
        b += plate(x, y, 624, 116, o, col)
        b += text(x + 22, y + 30, name.upper(), 16, col, weight=700, op=o, spacing=2.5)
        b += lines(x + 22, y + 59, words, 21.5, 590, op=o, lead=1.26, weight=500)
    a = cu[min(3, len(cu) - 1)]
    o = op * seg(u, a, a + 0.8)
    b += plate(1344, 150, 536, 600, o, LINE)
    b += text(1372, 200, "ON THE LIVE FLEET", 20, LINE, weight=700, op=o, spacing=2.5)
    for i, (l, col) in enumerate((("One pass,", INK), ("in advise.", INK), ("Nothing", LINE), ("was done.", LINE))):
        b += write(1372, 300 + i * 84, l, 72, seg(u, a + 0.3 + i * 0.5, a + 1.1 + i * 0.5), col, weight=600, family=SERIF, op=op)
    b += lines(1372, 640, "The controller has never changed a real machine.", 27, 480, DIM, o * seg(u, cu[min(5, len(cu) - 1)], cu[min(5, len(cu) - 1)] + 0.8))
    return b


def big_arrow(a, b, col, p, op, label, off=0):
    """process_film's, but an arrow that runs level carries its words above it and not on it."""
    if a[1] != b[1]:
        return _big_arrow(a, b, col, p, op, label, off)
    if op <= 0.004:
        return ""
    q, part, d = along([a, b], p)
    return polyline(part, col, 9, op) + head(q, d, col, 30, op) + text((a[0] + b[0]) / 2, a[1] - 26, label, 24, INK, "middle", 600, op=op * seg(p, 0.6, 1.0))


OVER = {"hook1": hook1_scene, "hook2": hook2_scene, "hook3": hook3_scene, "house": pass_scene, "pass": pass_scene, "sim": sim_scene,
        "panel": picture_scene, "fleetline": picture_scene, "cold": picture_scene, "pattern": ledger_scene}


def frame(t):
    """process_film's frame, with this report's scenes, and the map put away under those that stand on an empty page."""
    sc = pf.scene_at(t)
    cx, cy, z = pf.camera(t)
    over = OVER.get(sc["kind"]) or {"title": pf.title_scene, "whole": pf.whole_scene, "borders": pf.borders_scene, "act": act_scene, "end": pf.end_scene}.get(sc["kind"])
    ui = (over(t, sc) if over else lower(t, sc) + minimap(t, sc) + pf.crumbs(t, sc)) + pf.teleprompter(t, sc)
    bar = '<rect x="0" y="%d" width="%.1f" height="4" fill="%s" fill-opacity="0.55"/>' % (H - 4, W * t / pf.LENGTH, INK)
    tr = "translate(%.2f %.2f) scale(%.5f) translate(%.2f %.2f)" % (W / 2, H / 2, z, -cx, -cy)
    show = (1 - seg(t, pf.PATTERN_T, pf.PATTERN_T + 1.0)) * (1 - away(t))
    return ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="%d" height="%d" viewBox="0 0 %d %d"><rect width="%d" height="%d" fill="%s"/><g transform="%s" opacity="%.3f">%s</g>%s%s</svg>') % (
        W, H, W, H, W, H, BG, tr, show, pf.the_map(t) if show > 0.004 else "", ui, bar)


def token(s, p, col, label, op, scale=1.0):
    """process_film's, but the name of what moves is kept off the blocks' own words: under an arrow that runs
    level, beside one that climbs or falls, or where the step says ("label": [dx, dy] from the dot)."""
    if op <= 0.004:
        return ""
    pts = pf.path_of(s)
    q, _, d = along(pts, p)
    cr = pf.crossing(s)
    if cr:
        col = film.mix(col, pf.REGIONS[pf.N[s["b"]][0]]["col"], seg(p, cr[0], cr[1]))
    b = ""
    for k in range(1, 9):
        pk = p - k * 0.028
        if pk > 0:
            g, _, _ = along(pts, pk)
            b += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" fill-opacity="%.3f"/>' % (g[0], g[1], (8 - k * 0.7) * scale, col, op * 0.5 * (1 - k / 9.0))
    wd, ht = (len(label) * 9.6 + 30) * scale, 30 * scale
    dx, dy = s["label"] if s.get("label") else (0, 54) if abs(d[0]) >= abs(d[1]) else (wd / 2 + 24, 0)
    b += '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" fill-opacity="%.3f"/><circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" stroke-opacity="%.3f" stroke-width="2"/>' % (
        q[0], q[1], 9 * scale, col, op, q[0], q[1], 16 * scale, col, op * 0.5)
    b += '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-opacity="%.3f" stroke-width="1.5"/>' % (
        q[0] + dx - wd / 2, q[1] + dy - ht / 2, wd, ht, ht / 2, BG, op * 0.94, col, op)
    return b + text(q[0] + dx, q[1] + dy + 6.5 * scale, label, 16.5 * scale, INK, "middle", 600, op=op)


def region(k, op, label_op=1.0, big=0.0):
    """process_film's, but a territory marked quiet keeps its second line for the opening and drops it from its
    small label, where an arrow has to come in."""
    r = pf.REGIONS[k]
    if not r.get("quiet"):
        return _region(k, op, label_op, big)
    sub, r["sub"] = r["sub"], ""
    b = _region(k, op, label_op, big)
    r["sub"] = sub
    if big > 0:
        for i, l in enumerate(wrap(sub, 26, r["w"] - 120)):
            b += text(r["x"] + r["w"] / 2, r["y"] + r["h"] / 2 + 48 + i * 32, l, 26, INK, "middle", op=op * big * 0.9)
    return b


def solid(x, y, w, h, op, rx=0):
    return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%d" fill="%s" fill-opacity="%.3f"/>' % (x, y, w, h, rx, BG, op)


def lower(t, sc):
    """process_film's words under a step, on a ground the map does not show through."""
    u, dur = t - sc["t0"], sc["t1"] - sc["t0"]
    return solid(0, 690, W, H - 690, seg(u, 0.5, 1.2) * (1 - seg(u, dur - 0.6, dur - 0.1))) + _lower(t, sc)


def minimap(t, sc):
    return solid(W - 352, 18, 320, 188, seg(t, sc["t0"] + 0.6, sc["t0"] + 1.4) * (1 - seg(t, sc["t1"] - 0.5, sc["t1"])), 12) + _minimap(t, sc)


def act_scene(t, sc):
    return solid(0, 390, W, 300, appear(t - sc["t0"], 0.2, sc["t1"] - sc["t0"], 0.6)) + _act_scene(t, sc)


def bbox(s):
    """process_film's, but a step may say how far its frame reaches ("frame": {"x1": 1900}): the camera then
    stands where neither of its blocks is under the small map in the corner."""
    x0, y0, x1, y1 = _bbox(s)
    f = s.get("frame", {})
    return f.get("x0", x0), f.get("y0", y0), f.get("x1", x1), f.get("y1", y1)


_big_arrow, _bbox, _region, _lower, _minimap, _act_scene = pf.big_arrow, pf.bbox, pf.region, pf.lower, pf.minimap, pf.act_scene
pf.big_arrow, pf.frame, pf.bbox, pf.token, pf.region, pf.lower, pf.minimap, pf.act_scene = big_arrow, frame, bbox, token, region, lower, minimap, act_scene

# The page is process_film's, with what it says of the process film changed to what is true of this one.
for old, new in (
        ("Orreryq &middot; treadcore &middot; 13 November 2026", "Orreryq &middot; the fleet &middot; 16 November 2026"),
        ('<p class="lede">One block diagram, walked arrow by arrow, from the outside in.',
         '<p class="lede">The film of the lab report <a href="hearth-auto-lab-report.html">Holding the Room</a>: the room\'s probes, the law, the ladder and its three modes, the proof and the two screens as one block diagram, walked arrow by arrow, from the outside in. The controller has run on the live fleet in advise mode only and has never changed a machine; wake-on-LAN is untried; the house\'s loss per degree is unknown, so SeaTac\'s temperature is read and shown and not yet used in the law; the room\'s time constant is not measured; the 21.0 &deg;C target was set to give the first pass something to say and Paul has not chosen it; and both room probes are inside two Geiger counters\' cases on one machine. The film says what the report says and no more.'),
        ("drawn by two scripts:", "drawn by three scripts:"),
        ("and the frames render a core each.", "and the frames render in any order: here by a few processes, the Mac being the fleet's coordinator."),
        ("how a block diagram is walked. Another process is another storyboard.",
         "how a block diagram is walked; and <code>tools/report/hearth-auto_film.py</code>, this report's own opening, the scenes that follow four of its acts (the house's heat balance with the bound one evening gives on its loss, the first live pass in the plan's own words, the simulated room, the report's three pictures of Orrery) and its two columns of what was done and what was not. Every number in it is the report's, its guide's, or is in the report's own pictures."),
        ("a true thing that should not be possible: ten changes that each tested as a gain and together measured as nothing; then why (every trial the search made, lying on the curve of pure chance); then the question the film answers.",
         "the room's two thermometers, each inside a Geiger counter's case on one machine, and the two things a counter says that are not a temperature; then the first pass on the live fleet, which read 26.4 &deg;C against 21.0 &deg;C, said to shed 446 W of 704 W, and did nothing; then what the controller has not done, and the questions the film answers."),
        ("names three territories, then the four borders and their price, then goes inside one loop at a time.",
         "names five territories, then the four borders and what crosses each, then goes inside: the probes, the law, the ladder, the proof, the two screens."),
        ("A step runs 12 to 24 seconds:", "A step runs 12 to 29 seconds:"),
        ("<dt>Pace</dt>", "<dt>The pictures</dt><dd>Three of the report's own pictures of Orrery are shown whole, with what the narration names ringed as it is named. The third is a made-up plan in a scratch queue, and its heading and its first words say so for as long as it is shown.</dd>\n"
                          "<dt>Done, and not done</dt><dd>Before the close, two columns: what was measured, built, proved and run, and what was not. Act on the real queue, wake-on-LAN, UA, the house's time constant and the schedule are in the second.</dd>\n<dt>Pace</dt>")):
    assert old in pf.PAGE, old
    pf.PAGE = pf.PAGE.replace(old, new)


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
