#!/usr/bin/env python3
"""whole-line.py QUEUE -- the figures of docs/whole-line-lab-report.md, from the run as it stands.

Each figure is a fragment of inline SVG in docs/whole-line/, drawn in the report's own colours so it
follows the reader's light or dark. build.py takes it with !html(path). Colours follow a stage,
never its rank; every mark has a title for hovering and every colour is named beside it.
"""
import glob
import html
import json
import os
import re
import sys
import time

Q = os.path.abspath(sys.argv[1])
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "docs", "whole-line")
LINE = json.load(open(os.path.join(HERE, "..", "plans", "line.json")))
PIPE = json.load(open(os.path.join(Q, "plan", "pipeline.json")))
os.makedirs(OUT, exist_ok=True)

STYLE = """<style>
.viz{--s-first:#2a78d6;--s-held:#eb6834;--s-read:#1baf7a;--s-gate:#eda100;--s-guard:#e87ba4;--s-transform:#008300;--s-build:#6250d6;--s-bad:#e34948;--s-gpu:#8a8a84;
 margin:1.4em 0;overflow-x:auto;background:var(--tile);border:1px solid var(--line);border-radius:6px;padding:10px}
.viz svg{display:block;width:100%;min-width:720px;height:auto;font-family:var(--cond)}
.viz text{fill:var(--ink);font-size:12px}.viz .d{fill:var(--dim)}.viz .sm{font-size:10.5px}.viz .b{font-weight:700}
.viz .ln{stroke:var(--line);fill:none}.viz .ar{stroke:var(--accent);fill:none;stroke-width:1.4}.viz .gap{stroke:var(--s-bad);fill:none;stroke-width:1.6;stroke-dasharray:5 3}
.viz .box{fill:var(--panel);stroke:var(--line)}.viz .nb{fill:var(--panel);stroke:var(--s-bad);stroke-width:2;stroke-dasharray:5 3}
.viz .now{stroke:var(--ink);stroke-width:2}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])) .viz{--s-first:#3987e5;--s-held:#d95926;--s-read:#199e70;--s-gate:#c98500;--s-guard:#d55181;--s-transform:#008300;--s-build:#9085e9;--s-bad:#e66767;--s-gpu:#8b8a80}}
:root[data-theme="dark"] .viz{--s-first:#3987e5;--s-held:#d95926;--s-read:#199e70;--s-gate:#c98500;--s-guard:#d55181;--s-build:#9085e9;--s-bad:#e66767;--s-gpu:#8b8a80}
</style>
"""
COL = {"search": "first", "first": "first", "read": "read", "held": "held", "families": "gate", "promote": "gate", "build": "build", "proof": "guard", "anchor": "guard",
       "transform": "transform", "islands": "gpu", "bridge": "gpu", "slot": "transform", "main": "gate", "brain": "gate", "other": "gpu"}
NAME = {"first": "First read", "read": "Read on", "held": "Held-out", "gate": "Families, tests", "build": "Build", "guard": "Proof, anchor", "transform": "Transform", "gpu": "GPU island", "bad": "Failed"}


def c(stage):
    return "var(--s-%s)" % COL.get(stage, stage)


def e(s):
    return html.escape(str(s), quote=True)


def t(x, y, s, cls="", anchor="start"):
    return '<text x="%.1f" y="%.1f" class="%s" text-anchor="%s">%s</text>' % (x, y, cls, anchor, e(s))


def wrap(s, n):
    out, line = [], ""
    for w in s.split():
        if line and len(line) + 1 + len(w) > n:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    return out + ([line] if line else [])


def svg(w, h, body, cap, name, css=False):
    label = re.sub(r"<[^>]+>", "", cap)
    doc = '<figure><div class="viz"><svg viewBox="0 0 %d %d" role="img" aria-label="%s">%s</svg></div><figcaption>%s</figcaption></figure>\n' % (w, h, e(label), "".join(body), cap)
    with open(os.path.join(OUT, name + ".html"), "w") as f:
        f.write((STYLE if css else "") + doc)


def legend(keys, x, y):
    out = []
    for k in keys:
        out.append('<rect x="%d" y="%d" width="10" height="10" rx="2" fill="var(--s-%s)"/>' % (x, y - 9, k))
        out.append(t(x + 14, y, NAME[k], "d sm"))
        x += 24 + 6 * len(NAME[k])
    return out


def arrowhead():
    return '<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="7" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7 Z" fill="var(--accent)"/></marker><marker id="ax" markerWidth="8" markerHeight="8" refX="7" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7 Z" fill="var(--s-bad)"/></marker></defs>'


# ---- 1. The whole road
def flow():
    W, BW, BH, GX, GY = 1180, 130, 98, 19, 24
    pos = {}
    body = [arrowhead()]
    for s in LINE["stages"]:
        pos[s["id"]] = (s["col"] * (BW + GX) + 4, s["row"] * (BH + GY) + 26)
    for a, b, what in LINE["edges"]:
        xa, ya = pos[a]
        xb, yb = pos[b]
        bad = "not built" in what or b == "bridge" or b == "slot"
        cls, m = ("gap", "ax") if bad else ("ar", "ah")
        if xb > xa:
            d = "M%d %d H%d V%d H%d" % (xa + BW, ya + BH / 2, xb - 9, yb + BH / 2, xb)
        elif xb < xa and yb == ya:
            d = "M%d %d V%d H%d V%d" % (xa + BW / 2, ya, ya - 14, xb + BW / 2, yb)
        elif xb < xa:
            d = "M%d %d H%d V%d" % (xa, ya + BH / 2, xb + BW / 2, yb + BH)
        else:
            d = "M%d %d V%d" % (xa + BW / 2, ya + BH, yb) if yb > ya else "M%d %d V%d" % (xa + BW / 2, ya, yb + BH)
        body.append('<path d="%s" class="%s" marker-end="url(#%s)"><title>%s to %s: %s</title></path>' % (d, cls, m, e(a), e(b), e(what)))
    for s in LINE["stages"]:
        x, y = pos[s["id"]]
        f = PIPE.get("flow", {}).get(s["id"])
        gap = s["output"].startswith("NOT BUILT")
        tip = "%s. Takes: %s. Gives: %s. Simulates: %s For treadcore: %s" % (s["title"], s["input"], s["output"], s["simulates"], s["adds"])
        body.append('<g><title>%s</title><rect x="%d" y="%d" width="%d" height="%d" rx="4" class="%s"/><rect x="%d" y="%d" width="5" height="%d" rx="2" fill="%s"/>' % (e(tip), x, y, BW, BH, "nb" if gap else "box", x, y, BH, c(s["id"])))
        yy = y + 15
        for l in wrap(s["title"], 20)[:2]:
            body.append(t(x + 10, yy, l, "b"))
            yy += 14
        for l in wrap(("gives " + s["output"]) if not gap else "NOT BUILT", 24)[:3]:
            body.append(t(x + 10, yy, l, "d sm"))
            yy += 12
        if f:
            body.append(t(x + 10, y + BH - 6, "%d jobs, %.1f h a day" % (f["jobs"], f["hours"]), "d sm"))
        body.append("</g>")
    svg(W, 4 * (BH + GY) + 30, body, "<strong>Fig. 1. The whole road.</strong> Every stage, what it gives the next, and the machine-time it took in the last day, drawn from <code>tools/plans/line.json</code> and the run. Dashed red: not built, so nothing passes. Only the top two rows reach the game. Hover a box for what it takes and simulates.", "fig-flow", css=True)


# ---- 2. Past and forecast
def timeline():
    tl = PIPE["timeline"]
    W, L, ROW = 980, 110, 24
    past, ahead = tl["past_h"] * 60.0, 45.0
    now_x = L + (W - L - 6) * 0.78
    x = lambda m: now_x + (max(m, -past) / past) * (now_x - L) if m <= 0 else now_x + (min(m, ahead) / ahead) * (W - 6 - now_x)
    lanes = tl["lanes"]
    H = 30 + ROW * len(lanes) + 42
    body = []
    for h in range(int(tl["past_h"]), 0, -1):
        xx = x(-h * 60)
        body.append('<line x1="%.1f" x2="%.1f" y1="24" y2="%d" class="ln"/>' % (xx, xx, 26 + ROW * len(lanes)))
        body.append(t(xx + 2, 18, "-%d h" % h, "d sm"))
    for m in (15, 30):
        xx = x(m)
        body.append('<line x1="%.1f" x2="%.1f" y1="24" y2="%d" class="ln"/>' % (xx, xx, 26 + ROW * len(lanes)))
        body.append(t(xx + 2, 18, "+%d min" % m, "d sm"))
    for i, l in enumerate(lanes):
        y = 26 + i * ROW
        body.append(t(4, y + 15, l["host"], "" if l["up"] else "d"))
        for a, b, k, ok in l["past"]:
            fill = "var(--s-bad)" if ok == 0 else c(k)
            body.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="%s"><title>%s: %s, %.0f to %.0f min from now%s</title></rect>' % (x(a), y + 2, max(0.8, x(b) - x(a)), ROW - 5, fill, e(l["host"]), e(k), a, b, "" if ok else ", failed or sent back"))
        for a, b, k in l["next"]:
            if a < ahead:
                body.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="none" stroke="%s" stroke-width="1.4"><title>%s, forecast: %s, in %.0f min</title></rect>' % (x(a), y + 3, max(2, x(b) - x(a) - 1), ROW - 7, c(k), e(l["host"]), e(k), a))
    for mk in tl["marks"]:
        if mk["at"] > ahead:
            continue
        col = {"generation": "var(--s-read)", "failed": "var(--s-bad)"}.get(mk["kind"], "var(--s-gate)")
        xx = x(mk["at"])
        body.append('<line x1="%.1f" x2="%.1f" y1="22" y2="%d" stroke="%s" stroke-width="2"><title>%s: %s</title></line>' % (xx, xx, 26 + ROW * len(lanes), col, e(mk["kind"]), e(mk["text"])))
    body.append('<line x1="%.1f" x2="%.1f" y1="20" y2="%d" class="now"/>' % (now_x, now_x, 28 + ROW * len(lanes)))
    body.append(t(now_x + 4, 10, "now: forecast from here", "b sm"))
    body.append(t(L, 10, "measured", "b sm"))
    body += legend(["first", "read", "held", "gate", "build", "guard", "transform", "gpu", "bad"], 4, H - 20)
    body.append(t(4, H - 5, "Solid: done. Outline: forecast. Vertical green: a generation. Vertical red: a passed candidate stopped by tests.", "d sm"))
    svg(W, H, body, "<strong>Fig. 3. Six hours measured, and what comes next.</strong> Each machine's jobs from the event log, then the queue dealt to the lanes at the last day's medians, at %s. The screen Queue, Timeline draws the same data live." % PIPE["checked"][11:16], "fig-timeline")


# ---- 3. Plan, as a Gantt with arrows
def board():
    tasks = PIPE["tasks"]
    W, L, ROW = 980, 300, 24
    span = max(60.0, max(x["end_min"] for x in tasks))
    past = -15.0
    x = lambda m: L + (max(m, past) - past) / (span - past) * (W - L - 8)
    body = [arrowhead()]
    H = 26 + ROW * len(tasks)
    for k in (0, 30, 60, 90):
        if k <= span:
            body.append('<line x1="%.1f" x2="%.1f" y1="20" y2="%d" class="ln"/>' % (x(k), x(k), H))
            body.append(t(x(k) + 2, 14, "now" if k == 0 else "+%d min" % k, "d sm"))
    idx = {v["id"]: i for i, v in enumerate(tasks)}
    for i, v in enumerate(tasks):
        for d in v["deps"]:
            j = idx[d]
            bad = v["state"] == "not built" or tasks[j]["state"] == "not built"
            y0, y1 = 26 + j * ROW + ROW / 2 - 2, 26 + i * ROW + ROW / 2 - 2
            x0, x1 = x(tasks[j]["end_min"]), max(x(v["start_min"]), L)
            mid = x0 + 6 if x1 - x0 < 14 else x1 - 8
            body.append('<path d="M%.1f %.1f H%.1f V%.1f H%.1f" class="%s" marker-end="url(#%s)"/>' % (x0, y0, mid, y1, x1, "gap" if bad else "ar", "ax" if bad else "ah"))
    for i, v in enumerate(tasks):
        y = 26 + i * ROW
        nb = v["state"] == "not built"
        body.append(t(4, y + 14, v["title"], "b" if v.get("essential") else ""))
        who = "NOT BUILT" if nb else (", ".join(v["machines"][:2]) + (" +%d" % (len(v["machines"]) - 2) if len(v["machines"]) > 2 else ""))
        body.append(t(L - 6, y + 14, who[:22], "d sm", "end"))
        a, b = x(v["start_min"]), x(v["end_min"])
        fill = "var(--s-bad)" if nb else c(v["id"])
        op = 0.35 if v["state"] == "done" else 1
        body.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" rx="2" fill="%s" opacity="%s"><title>%s: %s, %.0f min. %s</title></rect>' % (a, y + 3, max(4, b - a), ROW - 9, fill, op, e(v["title"]), e(v["state"]), v["dur_min"], e(v["note"])))
        if v.get("essential"):
            body.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="none" stroke="var(--ink)" stroke-width="2"/>' % (a - 3, y + 1, max(4, b - a) + 6, ROW - 5))
    svg(W, H + 4, body, "<strong>Fig. 4. What is scheduled.</strong> The line as tasks, with dependencies as arrows, machines, and durations the fleet measured. The black box is the next essential task, the one most work depends on. This is the Queue, Board screen at %s." % PIPE["checked"][11:16], "fig-board")


# ---- 4. Where the hours go
def hours():
    fl = PIPE["flow"]
    reach = {"first": 1, "read": 1, "held": 1, "families": 1, "promote": 1, "build": 1, "proof": 1, "anchor": 1}
    rows = sorted(fl.items(), key=lambda kv: -kv[1]["hours"])
    W, L, ROW = 980, 170, 24
    top = max(r[1]["hours"] for r in rows) or 1
    body = []
    for i, (k, r) in enumerate(rows):
        y = 8 + i * ROW
        w = (W - L - 150) * r["hours"] / top
        body.append(t(4, y + 13, NAME.get(COL.get(k, ""), k) if k not in ("families", "promote", "proof", "anchor") else {"families": "Families", "promote": "Tests", "proof": "Proof", "anchor": "Anchor"}[k]))
        body.append('<rect x="%d" y="%d" width="%.1f" height="%d" rx="2" fill="%s"><title>%s: %d jobs, %.1f h</title></rect>' % (L, y + 3, max(2, w), ROW - 9, c(k) if reach.get(k) else "var(--s-gpu)", e(k), r["jobs"], r["hours"]))
        body.append(t(L + w + 6, y + 13, "%.1f h, %d jobs%s" % (r["hours"], r["jobs"], "" if reach.get(k) else ": no road to the game"), "d sm"))
    svg(W, 12 + ROW * len(rows), body, "<strong>Fig. 5. Where a day's machine-hours went.</strong> Grey has no road to the game yet. Families cost almost nothing, which is why making them easier buys nothing.", "fig-hours")


# ---- 5. Promotions
def promotions():
    rows = json.load(open(os.path.join(Q, "archive", "generations.json")))
    parse = lambda s: time.mktime(time.strptime(s, "%Y-%m-%dT%H:%M:%S"))
    t0, t1 = parse(rows[0]["asked"]), max(parse(r["asked"]) for r in rows)
    W, H = 980, 150
    x = lambda v: 30 + (v - t0) / (t1 - t0) * (W - 60)
    body = ['<line x1="20" x2="%d" y1="50" y2="50" class="ln"/><line x1="20" x2="%d" y1="104" y2="104" class="ln"/>' % (W - 10, W - 10), t(20, 40, "became a generation", "d sm"), t(20, 94, "stopped by the brain's tests", "d sm")]
    day = time.mktime(time.strptime(rows[0]["asked"][:10] + "T00:00:00", "%Y-%m-%dT%H:%M:%S"))
    while day < t1:
        day += 86400
        if day < t1:
            body.append('<line x1="%.1f" x2="%.1f" y1="30" y2="122" class="ln"/>' % (x(day), x(day)))
            body.append(t(x(day) + 3, 134, time.strftime("%d %b", time.localtime(day)), "d sm"))
    for r in rows:
        ok = r["status"] in ("approved", "self-modified")
        y = 50 if ok else 104
        tip = "%s %s %s: %s %s" % (r["run"], r["asked"][5:16], r["candidate"], r["status"], r["why"] or "; ".join(r["changed"][:2]))
        body.append('<circle cx="%.1f" cy="%d" r="6" fill="%s" stroke="var(--tile)" stroke-width="2"><title>%s</title></circle>' % (x(parse(r["asked"])), y, "var(--s-read)" if ok else "var(--s-bad)", e(tip)))
    n_ok = sum(r["status"] in ("approved", "self-modified") for r in rows)
    svg(W, H, body, "<strong>Fig. 6. Every promotion ever asked.</strong> %d became generations and %d failed, all at the brain's unit tests and none at a family. The last two failed on tests that read the defaults they were meant to be independent of." % (n_ok, len(rows) - n_ok), "fig-promotions")


# ---- 6. The simulation: two measures, two charts, one axis each
def sim():
    grid = [(2.0, 86, 3.8, 25), (2.2, 65, 4.0, 29), (2.4, 48, 3.7, 35), (2.5, 44, 2.6, 42), (2.6, 37, 4.6, 37), (2.75, 34, 2.1, 45), (3.0, 26, 1.1, 49)]
    W, H = 980, 210
    body = []

    def chart(x0, title, idx, top, fmt, col):
        w, h, y0 = 420, 140, 34
        px = lambda e_: x0 + (e_ - 2.0) / 1.0 * w
        py = lambda v: y0 + h - v / top * h
        out = [t(x0, 16, title, "b")]
        for k in range(0, 5):
            v = top * k / 4
            out.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" class="ln"/>' % (x0, x0 + w, py(v), py(v)))
            out.append(t(x0 - 6, py(v) + 4, fmt % v, "d sm", "end"))
        pts = " ".join("%.1f,%.1f" % (px(g[0]), py(g[idx])) for g in grid)
        out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2"/>' % (pts, col))
        for g in grid:
            out.append('<circle cx="%.1f" cy="%.1f" r="4.5" fill="%s" stroke="var(--tile)" stroke-width="2"><title>ease %s: one every %d min, %d%% truly worse, %+.1f a day</title></circle>' % (px(g[0]), py(g[idx]), col, g[0], g[1], g[3], g[2]))
            out.append(t(px(g[0]), y0 + h + 15, "%g" % g[0], "d sm", "middle"))
        chosen = px(2.6)
        out.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="var(--ink)" stroke-dasharray="3 3"/>' % (chosen, chosen, y0, y0 + h))
        out.append(t(chosen + 3, y0 + 10, "set: 2.6", "b sm"))
        return out
    body += chart(50, "Minutes between generations", 1, 100, "%d", "var(--s-first)")
    body += chart(540, "Gain a day, points a seat", 2, 6, "%.1f", "var(--s-read)")
    body.append(t(490, 204, "the ease: how far every bar sits under z 3", "d sm", "middle"))
    svg(W, H, body, "<strong>Fig. 7. What an ease buys, simulated.</strong> 30,000 trials a point, on a prior fitted so the funnel looks like the run's. Pace improves steadily; gain a day stays flat and noisy to 2.6, then falls. These are small differences on a rough model.", "fig-sim")


# ---- 7. Trials through the line
def traces():
    tr = PIPE["traces"]
    W, H = 980, 250
    body = []
    L, R, T, B = 40, W - 150, 16, H - 34
    stages = ["first", "read", "read2", "read3", "held"]
    top, low = 3.0, -3.0
    py = lambda z: T + (top - max(low, min(top, z))) / (top - low) * (B - T)
    for z in (-3, -2, -1, 0, 1, 2, 3):
        body.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" class="ln"/>' % (L, R, py(z), py(z)))
        body.append(t(L - 6, py(z) + 4, "%+d" % z, "d sm", "end"))
    n_ = max(len(x["reads"]) for x in tr)
    px = lambda i: L + i * (R - L) / max(1, n_ - 1)
    bar = PIPE["difficulty"].get("held_z", 0.4)
    body.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="var(--ink)" stroke-dasharray="4 3"/>' % (L, R, py(bar), py(bar)))
    body.append(t(R + 4, py(bar) + 4, "pass bar z %.2f" % bar, "b sm"))
    hi = {"failed": "var(--s-bad)"}
    for x in tr:
        col = hi.get(x["ended"].get("status"), "var(--s-gpu)")
        pts = [(px(i), py(r["z"])) for i, r in enumerate(x["reads"])]
        body.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%s" opacity="%s"/>' % (" ".join("%.1f,%.1f" % p for p in pts), col, 2.5 if col != "var(--s-gpu)" else 1.5, 1 if col != "var(--s-gpu)" else .7))
        for (ax, ay), r in zip(pts, x["reads"]):
            body.append('<circle cx="%.1f" cy="%.1f" r="4" fill="%s" stroke="var(--tile)" stroke-width="1.5"><title>%s %s on %s at %s: %+.2f +/- %.2f over %d seeds, z %+.2f</title></circle>' % (ax, ay, c(r["stage"]), e(x["trial"]), e(r["job"]), e(r["host"]), e(r["ended"]), r["d"], r["se"], r["seeds"], r["z"]))
        if x["ended"].get("status") == "failed" and pts:
            body.append(t(pts[-1][0] + 8, pts[-1][1] + 4, "%s: tests" % x["trial"], "sm"))
    body.append(t(L, H - 14, "each read in turn: first read, then pooled reads on, the last point its own held-out read", "d sm"))
    svg(W, H, body, "<strong>Fig. 2. Trials through the line.</strong> The last eight to reach a held-out read: z after each read. Red: passed, and stopped by a test. High pooled z falling at the held-out read is selection at work: lucky reads get picked, and unseen seeds correct them. Drawn to z -3: the two anchors read as far as -8.9.", "fig-traces")


# ---- 8. One gate, many proposers
def unified():
    W, H = 980, 330
    body = [arrowhead()]
    left = [("The fit (suggest.py)", 1), ("A/B: switches, choices", 1), ("Wide trials", 1), ("Older searches (SPSA, tune)", 1), ("Transform (a netlet)", 2), ("Crucible, by the bridge (a netlet)", 3), ("Imitation (a netlet)", 3)]
    stages = [("Check-in", "a weights file or a slot, with where it came from"), ("Preflight", "tests, families: under a minute"), ("Read", "first and read on"), ("Held-out", "the generation's read"), ("Line", "a commit; snapshot"), ("Proof", "z 3 past main"), ("Main", "the game")]
    for i, (name, kind) in enumerate(left):
        y = 18 + i * 42
        cls = "box" if kind == 1 else "nb"
        body.append('<rect x="6" y="%d" width="212" height="32" rx="4" class="%s"/>' % (y, cls))
        body.append(t(14, y + 20, name))
        body.append('<path d="M218 %d H262" class="%s" marker-end="url(#%s)"/>' % (y + 16, "ar" if kind == 1 else "gap", "ah" if kind == 1 else "ax"))
    body.append('<line x1="262" x2="262" y1="30" y2="286" class="ar"/>')
    bw = 92
    for i, (n, sub) in enumerate(stages):
        x = 272 + i * (bw + 8)
        body.append('<rect x="%d" y="110" width="%d" height="96" rx="4" class="box"/>' % (x, bw))
        body.append(t(x + 7, 130, n, "b"))
        yy = 148
        for l in wrap(sub, 15):
            body.append(t(x + 7, yy, l, "d sm"))
            yy += 13
        if i:
            body.append('<path d="M%d 158 H%d" class="ar" marker-end="url(#ah)"/>' % (x - 8, x))
    body.append(t(272, 92, "One road: a proposer only has to produce something the census can seat.", "b"))
    body.append(t(272, 236, "Dashed red: the road exists in the census only, or not at all. Every proposer is judged by the same", "d sm"))
    body.append(t(272, 250, "read, so adding one adds no new process: only a way to ask better questions.", "d sm"))
    svg(W, H, body, "<strong>Fig. 8. The approach proposed.</strong> Every method is a proposer, and one road judges them all. Preflight is new; the rest is what the dial search already has.", "fig-unified")


# ---- 9. Storage
def storage():
    W, H = 980, 230
    body = [arrowhead()]
    tiers = [("Generations: text", "git, a private repo", "%s now, about 40 KB a generation", "Each generation's values, evidence, families, tests. It diffs."), ("Packs: everything raw", "SSD, then GitHub release or disc", "see Section VIII", "Results, logs, champions, ledgers; xz; each file hashed in a manifest."), ("Disc: the long copy", "BD-R or M-DISC, by hand", "one disc lasts months", "A pack and its manifest. Readable with tar and sha256sum alone.")]
    for i, (a, b, _, d) in enumerate(tiers):
        x = 10 + i * 325
        body.append('<rect x="%d" y="24" width="305" height="150" rx="5" class="box"/>' % x)
        body.append(t(x + 12, 48, a, "b"))
        body.append(t(x + 12, 68, b, "d"))
        yy = 94
        for l in wrap(d, 44):
            body.append(t(x + 12, yy, l, "sm"))
            yy += 15
        if i:
            body.append('<path d="M%d 98 H%d" class="ar" marker-end="url(#ah)"/>' % (x - 20, x))
    body.append(t(10, 200, "Each generation writes its record at once. A pack is cut when asked; nothing is deleted and nothing leaves this Mac unless a person sends it.", "d"))
    svg(W, H, body, "<strong>Fig. 9. Where the record goes.</strong> Two kinds of thing, kept in the place that suits each.", "fig-storage")


# ---- 10. Mixing the sources
def mix():
    W, H = 980, 250
    body = [arrowhead()]
    for y, name, sub in ((40, "The rules, with today's dials", "built; how every bot plays"), (130, "A learned net in a slot", "built for the census; 20 a seat behind")):
        body.append('<rect x="10" y="%d" width="250" height="56" rx="4" class="box"/>' % y)
        body.append(t(22, y + 22, name, "b"))
        body.append(t(22, y + 40, sub, "d sm"))
    modes = [("A: by seat", "each tank is one or the other: roles and model"), ("B: alternate", "a tank switches on a slow clock: biorhythm's clock"), ("C: override when sure", "the net moves the rules' point if confident: the patch"), ("D: blend", "both aim; the Move point is a weighted mean")]
    for i, (a, b) in enumerate(modes):
        y = 18 + i * 54
        body.append('<rect x="370" y="%d" width="380" height="46" rx="4" class="box"/>' % y)
        body.append(t(382, y + 19, a, "b"))
        body.append(t(382, y + 36, b, "d sm"))
        body.append('<path d="M260 %d H330 V%d H370" class="ar" marker-end="url(#ah)"/>' % (68 if i < 2 else 158, y + 23))
        body.append('<path d="M750 %d H810 V110 H830" class="ar" marker-end="url(#ah)"/>' % (y + 23))
    body.append('<rect x="830" y="82" width="140" height="56" rx="4" class="box"/>')
    body.append(t(840, 104, "A Command", "b"))
    body.append(t(840, 122, "and the census reads it", "d sm"))
    svg(W, H, body, "<strong>Fig. 10. Computing two brains and mixing them.</strong> Four ways to combine sources, each a weight or choice the fleet can read as it reads any other. C is built; A is built for the census. B and D are proposals.", "fig-mix")


# ---- the tables that come from the table
def tables():
    with open(os.path.join(OUT, "screens.html"), "w") as f:
        f.write('<div class="table"><table><thead><tr><th>Screen</th><th>What it does</th><th>Where it ties in</th><th>What to look for</th><th>What is simulated</th></tr></thead><tbody>')
        for s in LINE["screens"]:
            f.write("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (e(s["key"].replace("/", ", ")), e(s["does"]), e(s["ties"]), e(s["look"]), e(s["sim"])))
        f.write("</tbody></table></div>\n")
    with open(os.path.join(OUT, "stages.html"), "w") as f:
        f.write('<div class="table"><table><thead><tr><th>Stage</th><th>Takes</th><th>Gives</th><th>Conditions simulated</th><th>Adds to treadcore</th></tr></thead><tbody>')
        for s in LINE["stages"]:
            f.write("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (e(s["title"]), e(s["input"]), e(s["output"]), e(s["simulates"]), e(s["adds"])))
        f.write("</tbody></table></div>\n")
    with open(os.path.join(OUT, "values.html"), "w") as f:
        f.write('<div class="table"><table><thead><tr><th>Value</th><th>Now</th><th>Range</th><th>What it does</th></tr></thead><tbody>')
        now_ = {v["key"]: v for v in PIPE.get("values", [])}
        for v in LINE["values"]:
            n = now_.get(v["key"], {})
            f.write("<tr><td>%s (<code>%s</code>)</td><td>%s %s%s</td><td>%s to %s</td><td>%s</td></tr>" % (e(v["label"]), e(v["key"]), n.get("value", v["default"]), e(v["unit"]), ", moved" if n.get("moved") else "", v["min"], v["max"], e(v["what"])))
        f.write("</tbody></table></div>\n")


for fn in (flow, timeline, board, hours, promotions, sim, traces, unified, storage, mix, tables):
    fn()
print("figures in", os.path.normpath(OUT))
