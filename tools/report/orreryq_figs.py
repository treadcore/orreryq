#!/usr/bin/env python3
"""orreryq_figs: the drawn figures of *The Orrery Q Process* (docs/orreryq-lab-report.md), and its close-ups.

    python3 tools/report/orreryq_figs.py [QUEUE]      every figure into docs/orreryq/ (needs rsvg-convert)

Each figure is an SVG written by hand in the films' palette (process_film.py: 3Blue1Brown's blue, green and
yellow on near-black, a coral for the CPUs) and turned into a PNG. Numbers come from the live queue (QUEUE,
default ~/code/treadcore/build/queue/grove: hearth/record.tsv, hearth/energy.json, plan/pipeline.json) and from
the two traces in docs/orreryq/ (trace-cpu.json, net.json), which were read from the same queue on 19 November
2026 and are kept so the figures can be drawn again without it.

THE CLOSE-UPS are crops of the report's own pictures of Orrery (docs/orreryq/live/, drawn by the program's
--frame renderer from tools/report/orreryq-shots.list), enlarged twice, with ringed numbers; CROPS says
which picture, which rectangle and where each number stands. A picture taken again with the page laid out
otherwise wants its rectangle moved here.

The house palette is bright on dark by design. Its green and coral are close for a reader with deuteranopia,
so no chart here tells two series apart by those two alone: series are named where they are drawn.
"""
import json
import math
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "docs", "orreryq")
Q = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/code/treadcore/build/queue/grove")

BG, INK, DIM, FAINT, PANEL = "#0e1013", "#ece9e1", "#9a978d", "#4a4944", "#15181d"
MAIN, CPU, GPU, LINE, RED, VIOLET = "#83c167", "#ff8c5a", "#58c4dd", "#f7d96f", "#fc6255", "#b189c6"
SERIF = "Iowan Old Style, Palatino, Georgia, serif"
SANS, MONO = "Avenir Next, Helvetica Neue, Helvetica, Arial, sans-serif", "Menlo, Consolas, monospace"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=18, fill=INK, anchor="start", weight=400, family=SANS, op=1.0, extra=""):
    return '<text x="%.1f" y="%.1f" font-family="%s" font-size="%.1f" font-weight="%d" fill="%s" fill-opacity="%.2f" text-anchor="%s"%s>%s</text>' % (
        x, y, family, size, weight, fill, op, anchor, extra, esc(s))


def box(x, y, w, h, stroke=FAINT, fill=PANEL, rx=10, sw=2, op=1.0, dash=""):
    return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%d" fill="%s" fill-opacity="%.2f" stroke="%s" stroke-width="%.1f"%s/>' % (
        x, y, w, h, rx, fill, op, stroke, sw, ' stroke-dasharray="%s"' % dash if dash else "")


def line(x1, y1, x2, y2, col=FAINT, sw=2, op=1.0, dash="", cap="round"):
    return '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%.2f" stroke-opacity="%.3f" stroke-linecap="%s"%s/>' % (
        x1, y1, x2, y2, col, sw, op, cap, ' stroke-dasharray="%s"' % dash if dash else "")


def arrow(x1, y1, x2, y2, col=DIM, sw=2, op=1.0, dash="", head=11):
    a = math.atan2(y2 - y1, x2 - x1)
    hx, hy = x2 - head * math.cos(a), y2 - head * math.sin(a)
    pts = "%.1f,%.1f %.1f,%.1f %.1f,%.1f" % (x2, y2, hx - head * 0.5 * math.sin(a), hy + head * 0.5 * math.cos(a), hx + head * 0.5 * math.sin(a), hy - head * 0.5 * math.cos(a))
    return line(x1, y1, hx, hy, col, sw, op, dash) + '<polygon points="%s" fill="%s" fill-opacity="%.3f"/>' % (pts, col, op)


def lines_of(s, size, width):
    words, out, cur = s.split(), [], ""
    room = int(width / (size * 0.52))
    for w in words:
        if len(cur) + len(w) + 1 > room and cur:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


def para(x, y, s, size, width, fill=INK, lead=1.32, weight=400, family=SANS, anchor="start"):
    return "".join(text(x, y + i * size * lead, l, size, fill, anchor, weight, family) for i, l in enumerate(lines_of(s, size, width)))


def save(name, w, h, body):
    svg = '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="%d" height="%d" viewBox="0 0 %d %d"><rect width="%d" height="%d" fill="%s"/>%s</svg>' % (
        w, h, w, h, w, h, BG, body)
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name + ".svg")
    open(p, "w").write(svg)
    subprocess.run(["rsvg-convert", "-w", str(w), "-h", str(h), "-o", os.path.join(OUT, name + ".png"), p], check=True)
    os.remove(p)
    print("%s.png %dx%d" % (name, w, h))


def title(s, sub=""):
    return text(40, 54, s, 30, INK, weight=600, family=SERIF) + (text(40, 86, sub, 17, DIM) if sub else "")


# ---- Fig. 1: the orrery ------------------------------------------------------------------------------------------

def fig_orrery():
    """The centre-controlled universe: the Mac at the middle, its housekeeping close in, the CPU machines on one
    orbit with a moon a lane, the cards on the next, and the two things outside it all: the room and main."""
    W, H = 1600, 1080
    cx, cy = 700, 560
    b = title("The orrery: one centre, everything on an orbit", "Every arrow is one ssh connection from the Mac; no machine speaks to another. 19 November 2026.")
    # the orbits
    for r, col, name in ((150, LINE, "housekeeping: every 2 to 5 minutes"), (290, CPU, "CPU lanes: a job of minutes"), (420, GPU, "CUDA islands: a segment of ten minutes or more")):
        b += '<ellipse cx="%d" cy="%d" rx="%d" ry="%d" fill="none" stroke="%s" stroke-opacity="0.45" stroke-width="2" stroke-dasharray="3 7"/>' % (cx, cy, r, r * 0.86, col)
    for k, (col, name) in enumerate(((LINE, "inner orbit: housekeeping, every 2 to 5 minutes"), (CPU, "middle orbit: CPU lanes, a job of minutes"), (GPU, "outer orbit: CUDA islands, a segment of 30 to 50 minutes"))):
        b += line(40, 130 + k * 26, 80, 130 + k * 26, col, 2, 0.8, "3 7")
        b += text(92, 135 + k * 26, name, 14.5, INK)
    # the sun
    b += '<circle cx="%d" cy="%d" r="88" fill="%s" fill-opacity="0.16" stroke="%s" stroke-width="3"/>' % (cx, cy, LINE, LINE)
    b += text(cx, cy - 34, "THE MAC", 20, LINE, "middle", 700)
    for i, s in enumerate(("Orrery.app: the window", "the keeper: lanes, sync", "the planner: what next", "the queue: a folder")):
        b += text(cx, cy - 6 + i * 21, s, 15, INK, "middle")
    # housekeeping, close in
    hk = [("telemetry", 5 / 60.0), ("hearth: the room", 2 / 12.0), ("temps", 4 / 12.0), ("power", 7 / 12.0), ("chores", 9 / 12.0), ("sync", 11 / 12.0)]
    for name, f in hk:
        a = 2 * math.pi * f
        x, y = cx + 150 * math.cos(a), cy + 150 * 0.86 * math.sin(a)
        b += '<circle cx="%.1f" cy="%.1f" r="7" fill="%s"/>' % (x, y, LINE)
        b += text(x + (12 if math.cos(a) >= 0 else -12), y + 5, name, 14, INK, "start" if math.cos(a) >= 0 else "end")
    # the CPU machines, a moon a lane
    cpu = [("macmini", 1, "M1, 8 cores", "on"), ("saskatchewan", 2, "i7-13700F, 24 thr.", "on"), ("boburner", 1, "16 thr. + a card", "on"), ("columbia", 1, "8 cores", "paused"),
           ("whitewolf", 1, "8 thr. + a card", "paused"), ("calber", 1, "8 thr. + a card", "off"), ("jaguaribe", 1, "Xeon X5650 x2", "off"), ("bosporus", 1, "Xeon E5645 x2", "off")]
    for i, (name, lanes, what, state) in enumerate(cpu):
        on = state == "on"
        a = -math.pi / 2 + 2 * math.pi * (i + 0.5) / len(cpu)
        x, y = cx + 290 * math.cos(a), cy + 290 * 0.86 * math.sin(a)
        b += line(cx + 88 * math.cos(a), cy + 88 * 0.86 * math.sin(a), x, y, CPU, 1.5, 0.55 if on else 0.18)
        b += '<circle cx="%.1f" cy="%.1f" r="21" fill="%s" fill-opacity="%.2f" stroke="%s" stroke-width="2"/>' % (x, y, CPU if on else BG, 0.85 if on else 1, CPU)
        for k in range(lanes):
            ma = a + 0.9 + k * 0.7
            b += '<circle cx="%.1f" cy="%.1f" r="6" fill="%s"/>' % (x + 31 * math.cos(ma), y + 31 * math.sin(ma), CPU if on else FAINT)
        tx = x + (34 if math.cos(a) >= -0.1 else -34)
        anc = "start" if math.cos(a) >= -0.1 else "end"
        b += text(tx, y - 26, name, 16, INK if on else DIM, anc, 700)
        b += text(tx, y - 8, what + ("" if on else "  (%s now)" % state), 13, DIM, anc)
    # the cards
    gpu = [("boburner-cuda", "GTX 1070 Ti", "on"), ("whitewolf-cuda", "a card", "paused"), ("calber-cuda", "a card", "off")]
    for i, (name, what, state) in enumerate(gpu):
        on = state == "on"
        a = math.pi * (0.125, 0.625, 0.875)[i]          # each card on its machine's own ray, an orbit further out
        x, y = cx + 420 * math.cos(a), cy + 420 * 0.86 * math.sin(a)
        b += line(cx + 88 * math.cos(a), cy + 88 * 0.86 * math.sin(a), x, y, GPU, 1.5, 0.55 if on else 0.18)
        b += '<rect x="%.1f" y="%.1f" width="40" height="28" rx="5" fill="%s" fill-opacity="%.2f" stroke="%s" stroke-width="2"/>' % (x - 20, y - 14, GPU if on else BG, 0.85 if on else 1, GPU)
        b += text(x, y + 36, name, 15, INK if on else DIM, "middle", 700)
        b += text(x, y + 54, "crucible island, %s" % what + ("" if on else " (%s)" % state), 13, DIM, "middle")
    # outside it all
    b += box(1210, 150, 350, 170, MAIN)
    b += text(1230, 186, "MAIN: the game's code", 17, MAIN, weight=700)
    b += para(1230, 214, "treadcore on GitHub. A generation is a commit on the line; a line that proves itself over 800 seeds is pushed here.", 15, 310)
    b += box(1210, 720, 350, 170, RED)
    b += text(1230, 756, "THE ROOM: 80 °F", 17, RED, weight=700)
    b += para(1230, 784, "Every watt the fleet draws ends as heat in the apartment. The hearth reads two thermometers and sets the fleet's watts.", 15, 310)
    b += arrow(1100, 300, 1205, 250, MAIN, 2)
    b += arrow(1110, 790, 1205, 805, RED, 2)
    b += text(40, 1050, "Each card stands on its machine's ray. Lanes: a filled circle computes now; a hollow one is on the bench or paused. Live state at 17:05, 19 November 2026 (config.json, lanes/).", 15, DIM)
    save("fig-orrery", W, H, b)


# ---- Fig. 2: the application, as a UML component diagram ---------------------------------------------------------

def comp(x, y, w, h, name, stereo, rows, col):
    b = box(x, y, w, h, col)
    b += '<rect x="%.1f" y="%.1f" width="18" height="12" fill="none" stroke="%s" stroke-width="1.5"/>' % (x + w - 30, y + 12, col)
    b += '<rect x="%.1f" y="%.1f" width="8" height="4" fill="%s"/><rect x="%.1f" y="%.1f" width="8" height="4" fill="%s"/>' % (x + w - 34, y + 14, col, x + w - 34, y + 20, col)
    b += text(x + 16, y + 26, "«%s»" % stereo, 13, DIM)
    b += text(x + 16, y + 50, name, 18, col, weight=700)
    for i, r in enumerate(rows):
        b += text(x + 16, y + 76 + i * 20, r, 13.5, INK, family=MONO if r.startswith(("src/", "tools/", "QUEUE/", "~/")) else SANS)
    return b


def fig_uml():
    W, H = 1600, 1040
    b = title("The application, as components", "UML component diagram. Solid arrow: calls or runs. Dashed: reads or writes a file. Every process but the jobs runs on the Mac.")
    C = {
        "app": (40, 120, 430, 250, "Orrery.app", "executable, Rust, no crates", ["src/main.rs  frames, the window", "src/nav.rs  7 chapters, 15 views", "src/training.rs  Queue, Results, Settings", "src/pipeline.rs  the eight Pipeline pages", "src/heat.rs  Heat: six panels", "src/generations.rs, nets.rs, ..."], LINE),
        "view": (40, 430, 430, 160, "treadcore-view.py", "process, Python", ["tools/plans/treadcore-view.py", "reads the queue; one JSON document", "for every Results and Queue page"], LINE),
        "verbs": (40, 650, 430, 150, "fleet-verbs.py", "process", ["tools/fleet-verbs.py", "the window's buttons as commands:", "pause, resume, hearth mode, ..."], LINE),
        "keeper": (580, 120, 440, 230, "the keeper", "daemon, Python", ["tools/fleet-queue.py QUEUE start", "a thread a lane; ssh to its machine", "sync, chores, temps every 2 min", "auto-restart, leftovers, flags", "health: the checks the header shows"], CPU),
        "planner": (580, 410, 440, 210, "the planner", "process, each pass", ["tools/plans/treadcore.py", "trials, read-ons, held-out pieces", "promotion, the line, its proof", "islands: segments, gauntlets, elections", "a pass about every 1.6 min, ~15 s"], CPU),
        "queue": (580, 680, 440, 200, "the queue", "folder", ["QUEUE/queue/, running/, done/", "QUEUE/events.jsonl  every event", "QUEUE/plan/  the planner's state", "QUEUE/hearth/  the room's state", "QUEUE/telemetry/  5 s samples"], DIM),
        "machines": (1130, 120, 430, 230, "a fleet machine", "node, Linux (Copal)", ["~/treadcore: census.sh, the game", "~/crucible: the CUDA program", "fleet-telemetry.sh: 5 s sampler", "radbeeper: the room's thermometers", "reached only by ssh from the Mac"], GPU),
        "hearth": (1130, 410, 430, 210, "the hearth", "process, every 5 min", ["tools/telemetry.py pull", "tools/hearth.py: off|advise|act|full", "tools/hearth_regulator.py: the hold", "wake-on-LAN, power off by order", "pauses and resumes lanes"], RED),
        "main": (1130, 680, 430, 200, "treadcore on GitHub", "repository", ["main: the game as it stands", "the line: generations not yet proved", "a proof over 800 seeds pushes it", "~/code/treadcore on the Mac"], MAIN),
    }
    for k, v in C.items():
        b += comp(*v)

    def edge(a, b_, col, words, dash="", ax=0.5, ay=1.0, bx=0.5, by=0.0, dx=0, dy=0):
        x1, y1 = C[a][0] + C[a][2] * ax, C[a][1] + C[a][3] * ay
        x2, y2 = C[b_][0] + C[b_][2] * bx, C[b_][1] + C[b_][3] * by
        s = arrow(x1, y1, x2, y2, col, 2, 0.9, dash)
        return s + text((x1 + x2) / 2 + 8 + dx, (y1 + y2) / 2 - 6 + dy, words, 13, DIM)
    b += edge("app", "view", LINE, "runs, reads its JSON")
    b += edge("view", "verbs", LINE, "", ay=1.0, by=0.0)
    b += text(60, 625, "a button press", 13, DIM)
    b += edge("verbs", "queue", LINE, "writes a command", "6 5", ax=1.0, ay=0.5, bx=0.0, by=0.5, dy=-8)
    b += edge("view", "queue", LINE, "reads", "6 5", ax=1.0, ay=0.6, bx=0.0, by=0.15, dy=-4)
    b += edge("app", "keeper", LINE, "starts it (autostart)", ax=1.0, ay=0.3, bx=0.0, by=0.3, dx=-60)
    b += edge("keeper", "planner", CPU, "asks for a pass", ax=0.5, ay=1.0, bx=0.5, by=0.0)
    b += edge("planner", "queue", CPU, "writes jobs", "6 5", ax=0.5, ay=1.0, bx=0.5, by=0.0)
    b += edge("keeper", "machines", CPU, "ssh: a job a lane", ax=1.0, ay=0.35, bx=0.0, by=0.35, dx=-40)
    b += edge("keeper", "hearth", RED, "", ax=1.0, ay=0.85, bx=0.0, by=0.3)
    b += text(1030, 380, "chore", 13, DIM)
    b += edge("hearth", "machines", RED, "samples; WOL", ax=0.5, ay=0.0, bx=0.5, by=1.0, dx=4)
    b += edge("hearth", "queue", RED, "pause, resume", "6 5", ax=0.0, ay=0.8, bx=1.0, by=0.3, dy=-6)
    b += edge("planner", "main", MAIN, "pushes a proved line", ax=1.0, ay=0.9, bx=0.0, by=0.3, dy=18)
    b += edge("machines", "main", MAIN, "", "6 5", ax=0.92, ay=1.0, bx=0.92, by=0.0)
    b += text(1520, 660, "pulls", 13, DIM)
    b += para(40, 935, "Read it from the left. A person presses a button in the window; the button is a command a script runs; the command changes a file in the queue folder. The keeper and the planner read that folder and act on the machines through ssh. Nothing on a machine knows the others exist; nothing in the window acts on a machine by itself.", 16, 1500)
    save("fig-uml", W, H, b)


# ---- Fig. 3: the job's sequence --------------------------------------------------------------------------------

def fig_sequence():
    W, H = 1600, 900
    b = title("One job's life, as a sequence", "UML sequence diagram: a census read of one trial, as the fleet ran hundreds on 19 November.")
    parts = [("planner", CPU), ("queue folder", DIM), ("keeper lane", CPU), ("machine", GPU), ("ledger", MAIN), ("window", LINE)]
    xs = [140 + i * 262 for i in range(len(parts))]
    for (n, col), x in zip(parts, xs):
        b += box(x - 100, 110, 200, 46, col)
        b += text(x, 140, n, 17, col, "middle", 700)
        b += line(x, 156, x, 860, FAINT, 1.5, 1, "4 6")
    msgs = [
        (0, 1, "writes queue/wNNNN-rK.json: dial, value, seeds 0-99", CPU, 1.2),
        (2, 1, "takes the oldest it may run (caps, priority)", CPU, 1.4),
        (2, 3, "ssh: census.sh  TRIAL=dial=value  SEEDS  MAP=all", CPU, 1.2),
        (3, 3, "plays 100 seeds x 13 maps against today's defaults", GPU, 4.6),
        (3, 2, "exit 0; results/…/pooled.txt  gain +/- se", GPU, 0.6),
        (2, 1, "running/ -> done/;  events.jsonl: done, seconds", CPU, 0.4),
        (2, 4, "sync: fleet.tsv rows (every 5 min)", MAIN, 1.0),
        (0, 4, "next pass reads the gain: drop, read on, or hold out", CPU, 1.2),
        (5, 1, "reads it all again for the pages (treadcore-view.py)", LINE, 0.5),
    ]
    y = 200
    for a, c, words, col, mins in msgs:
        if a == c:
            b += box(xs[a] - 8, y - 6, 16, 58, col, col, 3, 1, 0.8)
            b += text(xs[a] + 22, y + 26, words, 15, INK)
            b += text(xs[a] + 22, y + 46, "work: about %.1f min" % mins, 13, DIM)
            y += 76
            continue
        b += arrow(xs[a], y, xs[c], y, col, 2.2)
        mid = (xs[a] + xs[c]) / 2
        b += text(mid, y - 10, words, 14.5, INK, "middle")
        y += 66
    b += para(40, 800, "The minutes are the fleet's medians from the Blame page (plan/pipeline.json, 661 trial steps over six hours): 1.2 min waiting on the planner's pass, 1.4 in the queue, 4.6 working. A step waits 2.6 minutes for every 4.6 it works.", 16, 1500)
    save("fig-sequence", W, H, b)


# ---- Fig. 9: three days of the room ------------------------------------------------------------------------------

def rows_of(p):
    out = []
    for l in open(p):
        if l.startswith("#") or not l.strip():
            continue
        out.append([float(x) if x.strip() else None for x in l.rstrip("\n").split("\t")])
    return out


def fig_room():
    rec = rows_of(os.path.join(Q, "hearth", "record.tsv"))           # t, room, outside, fleet watts
    rec = [r for r in rec if r[1] is not None]
    W, H = 1600, 1000
    L, R = 110, 1540
    t0, t1 = rec[0][0], rec[-1][0]
    X = lambda t: L + (t - t0) / (t1 - t0) * (R - L)
    b = title("Three days of the room, and the fleet that heats it", "hearth/record.tsv: a line each pass, 16 Nov 17:37 to 19 Nov 17:05. Three charts, a scale each.")

    def panel(top, bot, lo, hi, step, unit, idx, col, label, fmt="%g"):
        Y = lambda v: bot - (v - lo) / (hi - lo) * (bot - top)
        o = ""
        v = lo
        while v <= hi + 1e-9:
            o += line(L, Y(v), R, Y(v), FAINT, 1, 0.5)
            o += text(L - 12, Y(v) + 5, (fmt % v) + unit, 14, DIM, "end")
            v += step
        segs, pts, prev = [], [], None
        for r in rec:
            if r[idx] is None:
                continue
            if prev is not None and r[0] - prev > 1800:
                segs.append(pts)
                pts = []
            pts.append("%.1f,%.1f" % (X(r[0]), Y(max(lo, min(hi, r[idx])))))
            prev = r[0]
        segs.append(pts)
        o += "".join('<polyline points="%s" fill="none" stroke="%s" stroke-width="2.2" stroke-linejoin="round"/>' % (" ".join(p), col) for p in segs if len(p) > 1)
        o += text(L + 8, top - 10, label, 15, INK, weight=600)
        return o, Y
    ft0, ft1 = time.mktime(time.strptime("2026-11-18 16:32:35", "%Y-%m-%d %H:%M:%S")), time.mktime(time.strptime("2026-11-18 19:17:56", "%Y-%m-%d %H:%M:%S"))
    b += '<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="%s" fill-opacity="0.13"/>' % (X(ft0), 130, X(ft1) - X(ft0), 790, LINE)
    b += text(X(ft0) + 6, 148, "full tilt", 14, LINE, weight=700)
    # the room, on its own scale, with the target's band and the ceiling
    top, bot = 160, 470
    Yr = lambda v: bot - (v - 23.0) / (28.0 - 23.0) * (bot - top)
    b += '<rect x="%d" y="%.1f" width="%d" height="%.1f" fill="%s" fill-opacity="0.16"/>' % (L, Yr(26.95), R - L, Yr(26.45) - Yr(26.95), MAIN)
    b += line(L, Yr(27.2), R, Yr(27.2), RED, 1.5, 0.8, "6 5")
    o, Y = panel(top, bot, 23.0, 28.0, 1.0, " °C", 1, LINE, "the room: the mean of two Geiger counters' thermometers")
    b += o
    b += text(R - 4, Yr(27.2) - 8, "ceiling 27.2 °C (81 °F)", 14, INK, "end")
    b += text(R - 4, Yr(26.45) + 18, "target 26.7 °C (80 °F) ± 0.25", 14, INK, "end")
    o, Y = panel(540, 680, 0.0, 15.0, 5.0, " °C", 2, GPU, "outside: SeaTac airport (KSEA)")
    b += o
    o, Y = panel(750, 920, 0.0, 1600.0, 400.0, " W", 3, CPU, "the fleet's watts at the wall (a model where no counter reads)", "%d")
    b += o
    d = time.localtime(t0)
    day = time.mktime((d.tm_year, d.tm_mon, d.tm_mday + 1, 0, 0, 0, 0, 0, -1))
    while day < t1:
        b += line(X(day), 150, X(day), 920, FAINT, 1, 0.9)
        b += text(X(day) + 6, 942, time.strftime("%a %d Nov", time.localtime(day)), 14, DIM)
        day += 86400
    marks = [("2026-11-17 06:00", "bosporus and jaguaribe on: +428 W"), ("2026-11-17 16:44", "Orrery holds the room"), ("2026-11-18 11:45", "the Mac rebooted"),
             ("2026-11-19 12:18", "the hold switches calber off"), ("2026-11-19 14:42", "calber deaf to 4 packets")]
    for i, (st, words) in enumerate(marks):
        t = time.mktime(time.strptime(st, "%Y-%m-%d %H:%M"))
        if t0 <= t <= t1:
            right = X(t) > R - 260
            b += line(X(t), 950, X(t), 960 + (i % 2) * 18, DIM, 1)
            b += text(X(t) + (-4 if right else 4), 972 + (i % 2) * 18, words, 13.5, INK, "end" if right else "start")
    save("fig-room", W, H, b)


# ---- Fig. 10: the energy, machine by machine -------------------------------------------------------------------

def fig_energy():
    # tools/hearth-energy.py --from "2026-11-16 15:00" --to "2026-11-19 16:56" (73.9 h), run on a scratch copy of the queue
    # whose telemetry had its repeated copies removed (19 Nov; the live files then held 14.9 GB, 0.14 GB of it real).
    rows = [("calber", 51.6, 19.6, "counter"), ("boburner", 50.3, 13.2, "counter"), ("whitewolf", 47.3, 26.8, "counter"), ("saskatchewan", 29.7, 8.0, "counter"),
            ("jaguaribe", 17.9, 36.1, "model"), ("bosporus", 17.0, 47.6, "model"), ("columbia", 3.1, 4.4, "counter")]
    W, H = 1600, 760
    b = title("Where the 217 MJ went, and what each joule bought", "16 Nov 15:00 to 19 Nov 16:56, 73.9 hours; tools/hearth-energy.py on the telemetry without its copies. Two charts, one measure each.")
    L1, R1, L2, R2 = 250, 760, 1010, 1520
    top = 150
    for i, (n, mj, wh, src) in enumerate(rows):
        y = top + i * 74
        b += text(L1 - 14, y + 24, n, 17, INK, "end", 600)
        w = mj / 60.0 * (R1 - L1)
        b += '<rect x="%d" y="%d" width="%.1f" height="32" rx="4" fill="%s"%s/>' % (L1, y, w, CPU, '' if src == "counter" else ' fill-opacity="0.45" stroke="%s" stroke-dasharray="5 4"' % CPU)
        b += text(L1 + w + 10, y + 23, "%.1f MJ" % mj, 15, INK)
        w2 = wh / 50.0 * (R2 - L2)
        b += text(L2 - 14, y + 24, n, 17, INK, "end", 600)
        b += '<rect x="%d" y="%d" width="%.1f" height="32" rx="4" fill="%s"%s/>' % (L2, y, w2, GPU, '' if src == "counter" else ' fill-opacity="0.45" stroke="%s" stroke-dasharray="5 4"' % GPU)
        b += text(L2 + w2 + 10, y + 23, "%.1f Wh a job" % wh, 15, INK)
    b += text(L1, top - 22, "ENERGY INTO THE ROOM", 15, DIM, weight=700)
    b += text(L2, top - 22, "CPU-SIDE ENERGY FOR EACH JOB FINISHED", 15, DIM, weight=700)
    b += para(40, 690, "Dashed bars are a model of the box (tools/plans/power.json): the two Supermicros have no energy counter. 217.0 MJ is 60.3 kWh, a mean of 815 W, about $10.25 at 17 cents. Read from the live files as they stood, with every older day repeated, the same account said 204 MJ and put saskatchewan first at 74 MJ: the copies, not the machine.", 15.5, 1520)
    save("fig-energy", W, H, b)


# ---- Fig. 14: the net around the tank ------------------------------------------------------------------------------

def fig_net():
    """Outside in, left to right: the tank and what it senses; the sensor matrix (12 rays x 3 channels and seven
    small blocks), each cell as bright as holding it at its mean moves the outputs (ablation); the two hidden
    layers of 48 switches; the six outputs; and the gate that decides whether the net's corrections reach the
    tank at all. Lines: the strongest connections by |w| x mean |activation|, blue for a positive weight, coral
    for a negative, as wide as their significance; the single strongest, h2[3] to the gate, in yellow."""
    d = json.load(open(os.path.join(OUT, "net.json")))
    W, H = 1600, 1040
    b = title("M0049's net, around the tank", "64 senses, two layers of 48, 6 outputs, tanh each (5,766 weights). Brightness: what holding a sense at its mean changes (723 recorded duel steps).")
    abl = {x["i"]: x.get("ablation_mean_abs_dout") or 0.0 for x in d["inputs"]}
    act = {x["i"]: x.get("mean_abs_act") or 0.0 for x in d["inputs"]}
    amax = max(abl.values())
    pos = {}
    # the tank and its twelve rays (near channel: length by how near things were on average)
    tx, ty = 160, 330
    for r in range(12):
        a = math.radians(-90 + 30 * r)
        L = 40 + 120 * act[2 * r]
        o = 0.25 + 0.75 * abl[2 * r] / amax
        b += line(tx, ty, tx + L * math.cos(a), ty + L * math.sin(a), LINE, 3, o)
        b += text(tx + (L + 14) * math.cos(a), ty + (L + 14) * math.sin(a) + 5, "%d°" % (30 * r), 12, DIM, "middle")
    b += '<g transform="translate(%d,%d)"><rect x="-17" y="-22" width="34" height="44" rx="6" fill="%s" stroke="%s" stroke-width="2"/><circle cx="0" cy="0" r="9" fill="none" stroke="%s" stroke-width="2"/><line x1="0" y1="0" x2="0" y2="-36" stroke="%s" stroke-width="5" stroke-linecap="round"/></g>' % (tx, ty, PANEL, INK, INK, INK)
    b += para(40, 520, "THE TANK. Twelve rays every 30° from its heading, each read three ways: the nearest thing, the enemy tank, a pillbox. A ray's length is how near things were on average; its brightness, how much the net minds it.", 14, 250, DIM)
    # the sensor matrix
    mx, my, cw, ch = 360, 150, 46, 28
    b += text(mx, my - 26, "SENSOR MATRIX", 14, DIM, weight=700)
    for c, name in enumerate(("near", "enemy", "pillbox")):
        b += text(mx + c * cw + cw / 2 - 2, my - 6, name, 12, DIM, "middle")
    for r in range(12):
        b += text(mx - 8, my + r * ch + 19, "%d°" % (30 * r), 12, DIM, "end")
        for c, i in enumerate((2 * r, 2 * r + 1, 35 + r)):
            o = abl[i] / amax
            b += '<rect x="%d" y="%d" width="%d" height="%d" rx="3" fill="%s" fill-opacity="%.2f" stroke="%s" stroke-opacity="0.5"/>' % (mx + c * cw, my + r * ch, cw - 4, ch - 4, LINE, 0.06 + 0.9 * o, FAINT)
            pos[i] = (mx + c * cw + cw - 4, my + r * ch + (ch - 4) / 2)
    groups = [("body", range(24, 32)), ("rules' answer", range(32, 35)), ("pillbox", range(47, 53)), ("gun", range(53, 55)), ("route", range(55, 59)), ("arcs", range(59, 62)), ("memory", range(62, 64))]
    gy = my + 12 * ch + 30
    for gname, idx in groups:
        b += text(mx - 8, gy + 17, gname, 12.5, INK if gname != "route" else LINE, "end")
        for k, i in enumerate(idx):
            o = abl[i] / amax
            b += '<rect x="%d" y="%d" width="22" height="22" rx="3" fill="%s" fill-opacity="%.2f" stroke="%s" stroke-opacity="0.5"/>' % (mx + k * 26, gy, LINE, 0.06 + 0.9 * o, FAINT)
            pos[i] = (mx + k * 26 + 22, gy + 11)
        gy += 34
    # the hidden layers
    hx1, hx2, hy0, hs = 820, 1050, 140, 17.0
    live1, live2 = set(d["units"]["h1_live"]), set(d["units"]["h2_live"])
    const1, const2 = set(d["units"]["h1_constant_sign"]), set(d["units"]["h2_constant_sign"])
    P1 = {j: (hx1, hy0 + j * hs) for j in range(48)}
    P2 = {j: (hx2, hy0 + j * hs) for j in range(48)}
    sig = d["significance"]
    smax = max(s[3] for s in sig["in_hidden"] + sig["h1_h2"] + sig["hidden_out"])
    outs = ["turn", "speed", "fire", "GATE", "memory 0", "memory 1"]
    PO = {o: (1250, 190 + o * 128) for o in range(6)}
    edges = ""
    for i, j, w, s in sorted(sig["in_hidden"], key=lambda e: e[3]):
        (x1, y1), (x2, y2) = pos[i], P1[j]
        edges += '<path d="M%.1f %.1f C %.1f %.1f, %.1f %.1f, %.1f %.1f" fill="none" stroke="%s" stroke-width="%.2f" stroke-opacity="%.2f"/>' % (x1, y1, x1 + 120, y1, x2 - 120, y2, x2, y2, GPU if w > 0 else CPU, 0.6 + 3.2 * s / smax, 0.25 + 0.5 * s / smax)
    for i, j, w, s in sorted(sig["h1_h2"][:20], key=lambda e: e[3]):
        (x1, y1), (x2, y2) = P1[i], P2[j]
        edges += line(x1, y1, x2, y2, GPU if w > 0 else CPU, 0.6 + 3.2 * s / smax, 0.25 + 0.5 * s / smax)
    for i, o, w, s in sorted(sig["hidden_out"], key=lambda e: e[3]):
        (x1, y1), (x2, y2) = P2[i], PO[o]
        hot = (i, o) == (3, 3)
        edges += line(x1, y1, x2 - 60, y2, LINE if hot else (GPU if w > 0 else CPU), (6 if hot else 0.6 + 3.2 * s / smax), 0.95 if hot else 0.25 + 0.5 * s / smax)
    b += edges
    for P, live, const, name in ((P1, live1, const1, "h1"), (P2, live2, const2, "h2")):
        x = P[0][0]
        b += text(x, hy0 - 26, "TRANSFORM " + name, 14, DIM, "middle", 700)
        for j, (px, py) in P.items():
            if j in const:
                b += '<circle cx="%.1f" cy="%.1f" r="5" fill="none" stroke="%s" stroke-width="1.5"/>' % (px, py, DIM)
            else:
                b += '<circle cx="%.1f" cy="%.1f" r="5.5" fill="%s" fill-opacity="%.2f"/>' % (px, py, INK, 1.0 if j in live else 0.45)
    b += '<circle cx="%.1f" cy="%.1f" r="10" fill="none" stroke="%s" stroke-width="3"/>' % (P2[3][0], P2[3][1], LINE)
    b += text(P2[3][0] - 16, P2[3][1] - 12, "h2[3]: the gate neuron", 13, LINE, "end", 700)
    # outputs
    b += text(1190, 150, "OUTPUTS", 14, DIM, weight=700)
    for o, (x, y) in PO.items():
        hot = o == 3
        b += box(x - 60, y - 22, 132, 44, LINE if hot else (GPU if o < 3 else VIOLET), PANEL, 8, 3 if hot else 2)
        b += text(x + 6, y + 6, outs[o], 16, LINE if hot else INK, "middle", 700)
    # the gate as a switch, and the action
    gx, gy2 = 1420, 330
    b += box(gx - 30, 160, 190, 120, DIM)
    b += para(gx - 18, 186, "the rules' answer: turn, speed, fire (inputs 32 to 34)", 13, 170)
    for k, yy in enumerate((190, 318, 446)):
        b += arrow(1322, yy, gx - 34, 572 + k * 22, GPU, 1.6, 0.6)
    b += text(1340, 512, "corrections", 13, DIM)
    b += box(gx - 30, 540, 190, 150, LINE)
    b += text(gx + 65, 572, "THE GATE", 15, LINE, "middle", 700)
    b += para(gx - 14, 598, "open when y3 > 0: action = rules + corrections. Shut: the rules exactly. Open on 6.8% of steps.", 13, 172)
    b += arrow(1322, 574, gx - 34, 640, LINE, 3)
    b += arrow(gx + 70, 284, gx + 70, 536, DIM, 2)
    b += box(gx - 30, 760, 190, 110, MAIN)
    b += text(gx + 70, 792, "THE TANK ACTS", 15, MAIN, "middle", 700)
    b += para(gx - 14, 818, "turn x π rad, speed x 4 tiles/s, fire if > 0 and loaded", 13, 172)
    b += arrow(gx + 70, 694, gx + 70, 756, MAIN, 2.5)
    # memory loop
    b += '<path d="M1322 830 C 1360 980, 600 1000, %d %d" fill="none" stroke="%s" stroke-width="2" stroke-dasharray="6 5"/>' % (pos[63][0] + 4, pos[63][1] + 6, VIOLET)
    b += text(820, 990, "memory: outputs 4 and 5 come back as inputs 62 and 63 on the next step", 13.5, VIOLET, "middle")
    b += para(40, 830, "A NET OF SWITCHES: 96% of hidden values sit beyond ±0.99. Hollow circles never change sign (biases in effect); bright ones are live switches. Lines: the 40 strongest senses to h1, 20 of h1 to h2, 20 of h2 to the outputs; blue +, coral −.", 14, 270, DIM)
    save("fig-net", W, H, b)


# ---- Fig. 15: what the net listens to -----------------------------------------------------------------------------

def fig_listen():
    d = json.load(open(os.path.join(OUT, "net.json")))
    ga = d["group_ablation"]["outputs"]
    names = {"rays.near": "rays: the nearest thing", "rules": "the rules' own answer", "body": "its own body and the enemy's", "pillbox": "the nearest pillbox",
             "rays.enemy": "rays: the enemy tank", "rays.pillbox": "rays: pillboxes", "arcs": "arcs: room to drive", "gun": "the gun", "memory": "memory", "route": "the route (the maze sense)"}
    rows = sorted(ga.items(), key=lambda kv: -kv[1]["mean_abs_dout_0to3"])
    W, H = 1600, 760
    b = title("What M0049 listens to", "Each group of senses held at its mean over 723 recorded duel steps: how much outputs 0 to 3 move, and how often the gate flips.")
    L, R, top = 420, 1100, 140
    for i, (k, v) in enumerate(rows):
        y = top + i * 52
        b += text(L - 14, y + 22, names.get(k, k), 17, INK, "end", 600)
        w = v["mean_abs_dout_0to3"] / 0.5 * (R - L)
        b += '<rect x="%d" y="%d" width="%.1f" height="30" rx="4" fill="%s"/>' % (L, y, w, LINE if k == "route" else GPU)
        b += text(L + w + 10, y + 21, "%.3f   gate flips %.1f%%" % (v["mean_abs_dout_0to3"], 100 * v["gate_flips"]), 15, INK)
    b += para(L, top + len(rows) * 52 + 30, "The route was added for the mazes on 6 November and is the sense the net uses least in a fight: its weights are exactly the size mutation alone would give them in 25,900 generations. These are duels, not mazes; the gauntlet's maze files are where the route should matter.", 15.5, 1100)
    save("fig-listen", W, H, b)


# ---- Fig. 4: the cycle, in a dataset's terms --------------------------------------------------------------------

def fig_cycle():
    """The Orrery Q process as any learning loop: a candidate change, read on fresh seeds until decided, read
    again on seeds nobody tuned on, kept, then proved against what stands. The CPU loop on the left (treadcore's
    dials), the GPU loop on the right (crucible's nets), the bridge between them."""
    W, H = 1600, 980
    b = title("The Orrery Q process: two learning loops and a bridge", "Left: treadcore's brain, a search over dials on the CPUs. Right: crucible's nets, evolution on the cards. Words in grey: the same step in a dataset's terms.")

    def loop(cx, cy, r, steps, col):
        o = '<circle cx="%d" cy="%d" r="%d" fill="none" stroke="%s" stroke-opacity="0.35" stroke-width="3"/>' % (cx, cy, r, col)
        n = len(steps)
        for i, (name, gen, num) in enumerate(steps):
            a = -math.pi / 2 + 2 * math.pi * i / n
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            a2 = -math.pi / 2 + 2 * math.pi * (i + 0.5) / n
            o += '<circle cx="%.1f" cy="%.1f" r="6" fill="%s"/>' % (cx + r * math.cos(a2), cy + r * math.sin(a2), col)
            o += box(x - 118, y - 40, 236, 80, col, PANEL, 10, 2)
            o += text(x, y - 14, name, 16, INK, "middle", 700)
            o += text(x, y + 6, gen, 13, DIM, "middle")
            o += text(x, y + 26, num, 13, col, "middle", 600)
        return o
    cpu = [("a candidate", "a hyperparameter to try", "120 asked on one set of defaults"), ("first read", "a validation batch", "150 seeds, ~5 min"),
           ("read on", "more batches until decided", "to 510 or 750 seeds"), ("held-out read", "the held-out set", "400 seeds no trial played"),
           ("promote", "keep the model", "tests, families, a commit"), ("the line's proof", "the final test, against what stands", "800 seeds a round, z 3"),
           ("main", "the new baseline", "every trial starts again from it")]
    gpu = [("a population", "2,048 nets of one lineage", "on boburner, calber, whitewolf"), ("a segment", "100 generations of training", "30 to 50 min on a card"),
           ("the exam", "validation against the ladder", "8 rungs x 2,048 duels"), ("the gauntlet", "unit tests with floors", "24 files x 256 runs"),
           ("election", "keep the model", "zg past the bar, or forced at 3 h"), ("the bridge", "the deployment test", "the real game, 192 seeds")]
    b += loop(425, 500, 275, cpu, CPU)
    b += loop(1235, 500, 250, gpu, GPU)
    b += text(425, 500 - 10, "CPU", 40, CPU, "middle", 700, SERIF)
    b += text(425, 500 + 26, "treadcore's dials", 16, DIM, "middle")
    b += text(1235, 500 - 10, "GPU", 40, GPU, "middle", 700, SERIF)
    b += text(1235, 500 + 26, "crucible's nets", 16, DIM, "middle")
    b += arrow(1235 - 250 * 0.866 - 122, 500 - 250 * 0.5 + 10, 425 + 275 * 0.78 + 122, 500 - 275 * 0.62 + 10, LINE, 3)
    b += text(1000, 150, "THE BRIDGE: a net the game takes", 15, LINE, "middle", 700)
    b += text(1000, 170, "ships as a style the CPU loop plays", 15, LINE, "middle", 600)
    b += para(40, 900, "One idea runs through both: a change is believed only on seeds it was not chosen on, and kept only if it beats what stands by more than the noise. The orrery's centre (the Mac) asks every question; the planets (the machines) only answer.", 16, 1500)
    save("fig-cycle", W, H, b)


# ---- Fig. 6: one CPU generation, job by job ------------------------------------------------------------------------

def hm(s):
    return time.mktime(time.strptime(s, "%Y-%m-%dT%H:%M:%S"))


def fig_chain():
    d = json.load(open(os.path.join(OUT, "trace-cpu.json")))
    jobs = [j for j in d["trial_chain"] + d["builds"] + d["proof"] if "started" in j]      # the merged held reads are records, not jobs
    t0, t1 = hm("2026-11-15T19:40:00"), hm("2026-11-15T22:50:00")
    W, H = 1600, 1000
    L, R = 260, 1560
    X = lambda t: L + (t - t0) / (t1 - t0) * (R - L)
    b = title("One CPU generation: w21532, ladder 0 → 3, from its first ask to main", "15 November 2026. A thin bar: queued, waiting for a lane. A thick bar: running, named by its lane. 44 jobs, 3 h 6 min.")
    groups = [("first read", lambda j: j["stage"] == "first"), ("read on ×4", lambda j: j["stage"] == "read"), ("held-out read 1", lambda j: j["id"].startswith("h1503")),
              ("held-out read 2", lambda j: j["id"].startswith("h1504")), ("held-out read 3", lambda j: j["id"].startswith("h1505")),
              ("families, gauntlet, promote", lambda j: j["stage"] in ("families", "other", "promote")), ("build 81e0df3 ×6", lambda j: j["id"].startswith("prep-")),
              ("proof round 1", lambda j: j["id"] in ["pv%04d" % k for k in range(499, 505)]), ("proof round 2", lambda j: j["id"] in ["pv%04d" % k for k in range(505, 511)]),
              ("proof round 3", lambda j: j["id"] in ["pv%04d" % k for k in range(511, 517)])]
    cols = {"first": GPU, "read": MAIN, "held": CPU, "families": LINE, "other": LINE, "promote": LINE, "build": VIOLET, "proof": RED}
    y = 140
    t = t0
    while t <= t1:
        b += line(X(t), 120, X(t), 820, FAINT, 1, 0.6)
        b += text(X(t), 112, time.strftime("%H:%M", time.localtime(t)), 13, DIM, "middle")
        t += 1800
    for name, f in groups:
        rows = [j for j in jobs if f(j)]
        sub = 1 if len(rows) <= 1 or name.startswith(("first", "read on", "families")) else min(6, len(rows))
        hh = 46 if sub > 1 else 30
        b += text(L - 14, y + hh / 2 + 5, name, 15, INK, "end", 600)
        for k, j in enumerate(sorted(rows, key=lambda j: j["started"])):
            lane = k % sub if sub > 1 else 0
            yy = y + lane * (hh / sub) if sub > 1 else y
            bh = hh / sub - 2 if sub > 1 else hh - 4
            q, st, en = hm(j["queued"]) if j.get("queued") else hm(j["started"]), hm(j["started"]), hm(j["ended"])
            col = cols.get(j["stage"], DIM if not j["id"].startswith("prep") else VIOLET)
            if j["id"].startswith("prep"):
                col = VIOLET
            b += '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" fill-opacity="0.22"/>' % (X(q), yy + bh * 0.35, max(1, X(st) - X(q)), bh * 0.3, col)
            b += '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" fill="%s"/>' % (X(st), yy, max(2, X(en) - X(st)), bh, col)
            if X(en) - X(st) > 52 and bh >= 12:
                b += text(X(st) + 4, yy + bh - 3 if bh < 20 else yy + bh / 2 + 5, j["lane"].replace("saskatchewan", "sask."), 11 if bh < 20 else 13, BG, weight=700)
            if j["id"] == "e22801":
                b += text(X(en) + 6, yy + bh / 2 + 5, "asked twice: 10.3 min on calber", 13, RED, weight=600)
        y += hh + 22
    marks = [("2026-11-15T20:20:27", "passed: z 2.92 on 510 seeds"), ("2026-11-15T21:00:41", "held out: z 3.13 on 1,128"), ("2026-11-15T21:07:42", "commit 81e0df3"), ("2026-11-15T22:47:05", "main")]
    for k, (ts, words) in enumerate(marks):
        x = X(hm(ts))
        b += line(x, 120, x, 830, LINE, 1.5, 0.8, "4 4")
        b += text(x + (-4 if k == 3 else 4), 846 + (k % 2) * 18, words, 13.5, LINE, "end" if k == 3 else "start", 600)
    # the budget
    cp = d["critical_path"]
    by = 900
    tot = cp["ask_to_main_min"]
    parts = [("running", cp["running_min"], MAIN), ("waiting for a lane", cp["queue_wait_min"], CPU), ("planner passes", cp["planner_gaps_min"] + cp["keeper_adding_pieces_min"], LINE),
             ("promotion to main: builds, three proof rounds", cp["promotion_to_main_min"], RED)]
    x = L
    for k, (name, m, col) in enumerate(parts):
        w = m / tot * (R - L)
        b += '<rect x="%.1f" y="%d" width="%.1f" height="28" fill="%s"/>' % (x, by, w - 2, col)
        b += line(x + 4, by + 30, x + 4, by + 40 + (k % 2) * 20, DIM, 1)
        b += text(x + 8, by + 50 + (k % 2) * 20, "%s %.0f min" % (name, m), 13.5, INK)
        x += w
    b += text(L - 14, by + 20, "where the time went", 15, INK, "end", 600)
    save("fig-chain", W, H, b)


# ---- Fig. 7: the funnel of the paths not taken -------------------------------------------------------------------

def fig_funnel():
    W, H = 1600, 760
    b = title("The paths not taken", "Left: the CPU generation of w21532 (defaults 2a1a1e9, 15 Nov 15:38 to 21:08). Right: the GPU window that made M0049, and the four days since.")
    cpu = [("trials asked", 120, "62 A/B versions, 40 far, 12 drawn from the fit, 3 carried, 3 read again"), ("played the very games of the defaults", 21, "a change the game never reaches: nothing to read"),
           ("read on past their first read", 36, "the keep bar: z 0.25 at 150 seeds, rising"), ("reached a held-out read", 8, "the sequential pass: z 2.1 at 510 seeds"),
           ("passed it, and promoted", 1, "w21532: z 3.13 on 1,128 held-out seeds")]
    gpu = [("segments examined in the window", 14, "19:05 to 22:06 on 15 Nov"), ("could not be elected", 4, "examined against a rung the game had just refused"),
           ("held every floor", 3, "boburner's 1756, 1757, 1758"), ("elected (forced at 3 h)", 1, "1756 as M0049, zg +1.99 under the bar 3.00"),
           ("taken by the game", 0, "−8.84 ± 1.22 a seat under the shipped M0030"), ("since: 316 segments, 206 GPU-hours", 0, "none holds the floors M0049 left")]

    def fun(x0, rows, col, top):
        o = ""
        for i, (name, n, why) in enumerate(rows):
            y = 150 + i * 92
            w = max(6, (n / top) ** 0.5 * 600)
            o += '<rect x="%.1f" y="%d" width="%.1f" height="40" rx="4" fill="%s" fill-opacity="%.2f"/>' % (x0, y, w, col, 0.9 if n else 0.25)
            o += text(x0 + w + 12, y + 28, "%d" % n, 22, INK, weight=700, family=SERIF)
            o += text(x0, y - 8, name, 15.5, INK, weight=600)
            o += text(x0 + 4, y + 62, why, 13.5, DIM)
        return o
    b += fun(40, cpu, CPU, 120.0)
    b += fun(830, gpu, GPU, 14.0)
    b += text(40, 720, "Bar length is the square root of the count, so the one that passed can still be seen.", 14, DIM)
    save("fig-funnel", W, H, b)


# ---- Fig. 8: is it getting better? -------------------------------------------------------------------------------

def fig_increase():
    W, H = 1600, 760
    b = title("Is it getting better? The two yardsticks", "Left: today's CPU defaults against main of 28 Oct, the same 2,000 seeds every day (plan/rating.json). Right: the GPU's gauntlet mean share by milestone (the maze home).")
    cpu = [("13 Nov", 3.87, 0.25), ("14 Nov", 7.83, 0.26), ("15 Nov", 7.52, 0.27), ("16 Nov", 8.18, 0.27), ("17 Nov", 8.13, 0.28), ("18 Nov", 8.22, 0.27)]
    L, R, top, bot = 110, 720, 160, 620
    Y = lambda v: bot - v / 10.0 * (bot - top)
    for v in range(0, 11, 2):
        b += line(L, Y(v), R, Y(v), FAINT, 1, 0.5)
        b += text(L - 10, Y(v) + 5, "+%d" % v, 13, DIM, "end")
    for i, (dname, v, se) in enumerate(cpu):
        x = L + 40 + i * 100
        b += '<rect x="%.1f" y="%.1f" width="60" height="%.1f" rx="4" fill="%s"/>' % (x, Y(v), bot - Y(v), CPU)
        b += line(x + 30, Y(v + 2 * se), x + 30, Y(v - 2 * se), INK, 2)
        b += text(x + 30, Y(v) - 22, "+%.2f" % v, 14, INK, "middle", 600)
        b += text(x + 30, bot + 22, dname, 13, DIM, "middle")
    b += text(L, top - 16, "points a seat over main of 28 Oct (± 2 errors)", 14, INK, weight=600)
    b += para(L, 680, "Up 4.35 points a seat in five days, then flat: the defaults have been 81e0df3 since 15 Nov 22:47, and the only generation since was orphaned.", 14, 620, DIM)
    gpu = [("M0020", 0.642), ("M0021", 0.738), ("M0022", 0.771), ("M0023", 0.779), ("M0024", 0.786), ("M0030", 0.801), ("M0032", 0.801), ("M0037", 0.807), ("M0045", 0.809), ("M0049", 0.810)]
    L2, R2 = 900, 1560
    Y2 = lambda v: bot - (v - 0.6) / 0.25 * (bot - top)
    for v in (0.60, 0.65, 0.70, 0.75, 0.80, 0.85):
        b += line(L2, Y2(v), R2, Y2(v), FAINT, 1, 0.5)
        b += text(L2 - 10, Y2(v) + 5, "%.2f" % v, 13, DIM, "end")
    pts = []
    for i, (m, v) in enumerate(gpu):
        x = L2 + 30 + i * 64
        pts.append("%.1f,%.1f" % (x, Y2(v)))
        shipped = m == "M0030"
        b += '<circle cx="%.1f" cy="%.1f" r="%d" fill="%s" stroke="%s" stroke-width="2"/>' % (x, Y2(v), 9 if shipped else 6, LINE if shipped else GPU, BG)
        b += text(x, bot + 22, m, 12, DIM, "middle")
    b = b.replace('<!--gpu-->', '')
    b += '<polyline points="%s" fill="none" stroke="%s" stroke-width="2"/>' % (" ".join(pts), GPU)
    for i, (m, v) in enumerate(gpu):
        x = L2 + 30 + i * 64
        b += '<circle cx="%.1f" cy="%.1f" r="%d" fill="%s" stroke="%s" stroke-width="2"/>' % (x, Y2(v), 9 if m == "M0030" else 6, LINE if m == "M0030" else GPU, BG)
    b += text(L2 + 30 + 5 * 64 + 14, Y2(0.801) + 30, "M0030: the last the game took", 13.5, LINE, weight=600)
    b += text(L2, top - 16, "the gauntlet's mean share, 24 files x 256 runs", 14, INK, weight=600)
    b += para(L2, 680, "Up from 0.64 to 0.80 in two days, then within 0.01 for eleven. The game has taken nothing since M0030 (10 Nov); every boburner milestone since was refused.", 14, 640, DIM)
    save("fig-increase", W, H, b)


# ---- Fig. 12: one GPU generation ---------------------------------------------------------------------------------

def fig_gpu():
    W, H = 1600, 700
    b = title("One GPU generation: M0049, from its queue to the game's refusal", "15 November 2026, the maze home. Segment x-boburner-cuda-1756 on boburner's GTX 1070 Ti.")
    t0, t1 = hm("2026-11-15T14:50:00"), hm("2026-11-15T23:10:00")
    L, R = 120, 1540
    X = lambda t: L + (t - t0) / (t1 - t0) * (R - L)
    t = hm("2026-11-15T15:00:00")
    while t <= t1:
        b += line(X(t), 150, X(t), 460, FAINT, 1, 0.6)
        b += text(X(t), 140, time.strftime("%H:%M", time.localtime(t)), 13, DIM, "middle")
        t += 3600
    segs = [("2026-11-15T15:00:58", "2026-11-15T19:01:54", "in the GPU queue: five segments ahead of it (ahead 6)", GPU, 0.25, 190),
            ("2026-11-15T19:01:54", "2026-11-15T19:51:23", "100 generations", GPU, 1.0, 190),
            ("2026-11-15T19:52:13", "2026-11-15T22:06:03", "the window's best: zg +1.99, every floor held, under the bar 3.00", LINE, 0.35, 270),
            ("2026-11-15T22:06:04", "2026-11-15T22:31:17", "footage 96/96", MAIN, 1.0, 350),
            ("2026-11-15T22:06:04", "2026-11-15T22:55:04", "the bridge: 192 seeds in the game", RED, 0.6, 410)]
    for a, z, words, col, op, y in segs:
        x1, x2 = X(hm(a)), X(hm(z))
        b += '<rect x="%.1f" y="%d" width="%.1f" height="34" rx="4" fill="%s" fill-opacity="%.2f"/>' % (x1, y, x2 - x1, col, op)
        b += text(x1 + 6 if x2 - x1 > 300 else x1, y + 23 if x2 - x1 > 300 else y - 8, words, 14, BG if (op > 0.9 and x2 - x1 > 300) else INK, weight=600)
    for ts, words, y in (("2026-11-15T19:52:13", "examined against M0032", 250), ("2026-11-15T22:06:03", "forced: 3.0 h without a generation", 330), ("2026-11-15T22:55:04", "refused: −8.84 ± 1.22 a seat", 470)):
        x = X(hm(ts))
        b += line(x, 160, x, 480, LINE, 1.5, 0.9, "4 4")
        b += text(x + (6 if x < 1300 else -6), y, words, 14, LINE, "start" if x < 1300 else "end", 700)
    b += para(L, 540, "Queued to refused: 7 h 54 min. In the queue 4 h 01 min; on the card 49.5 min; waiting as the window's best 2 h 14 min. The election raised every floor to M0049's own share less 1/16; the refusal did not lower them. C7 is now 0.18 and T3 0.918, and the standing top, M0032, scores T3 0.785: no segment since has met them.", 16, 1400)
    save("fig-gpu", W, H, b)


# ---- the close-ups ---------------------------------------------------------------------------------------------------
# name: (picture in docs/orreryq/live, (x, y, w, h) in its own pixels, [(number, x, y) in its own pixels, ...])
CROPS = {
    "fleet-head": ("3-fleet.png", (150, 62, 1450, 210), [(1, 885, 80), (2, 775, 121), (3, 1125, 195), (4, 1140, 241)]),
    "fleet-row": ("3-fleet.png", (150, 440, 1450, 90), []),
    "blame-head": ("3-blame.png", (150, 62, 1100, 50), []),
    "parade-head": ("3-parade.png", (150, 52, 820, 120), [(1, 278, 74), (2, 420, 74), (3, 563, 74), (4, 708, 74), (5, 852, 74)]),
    "lineup-top": ("3-lineup.png", (150, 125, 1450, 380), []),
    "keeper-difficulty": ("7-keeper.png", (150, 546, 1450, 52), []),
    "yardstick": ("4-generations-7.png", (150, 160, 900, 330), []),
    "gpu-margins": ("4-generations-4.png", (150, 162, 1450, 300), []),
    "hearth-top": ("1-heat-hearth.png", (150, 242, 1450, 380), []),
    "steps-tau": ("1-heat-steps.png", (150, 242, 1450, 300), []),
    "timeline-w21532": ("3-timeline-w21532.png", (150, 60, 1450, 600), []),
    "lineup-w21532": ("3-lineup-w21532-all.png", (150, 240, 1450, 300), []),
}


def crops(only=None):
    """Each close-up: the rectangle cut out, enlarged twice, the numbers ringed on it (numbers placed in the
    picture's own pixels, so a crop can be moved without moving them)."""
    for name, (src, (x, y, w, h), marks) in CROPS.items():
        if only and name not in only:
            continue
        k = 2.0 if w <= 900 else 1600.0 / w * 1.0 if w > 1600 else 1.1
        cw, ch = int(w * k), int(h * k)
        tmp = os.path.join(OUT, "crop-" + name + ".tmp.png")
        subprocess.run(["magick", os.path.join(OUT, "live", src), "-crop", "%dx%d+%d+%d" % (w, h, x, y), "+repage", "-filter", "Point" if k >= 2 else "Lanczos",
                        "-resize", "%dx%d!" % (cw, ch), tmp], check=True)
        body = '<image href="%s" xlink:href="%s" width="%d" height="%d"/>' % (os.path.basename(tmp), os.path.basename(tmp), cw, ch)
        for n, mx, my in marks:
            px, py = (mx - x) * k, (my - y) * k
            body += ('<circle cx="%.1f" cy="%.1f" r="15" fill="%s" fill-opacity="0.92" stroke="%s" stroke-width="3"/>' % (px, py, BG, LINE) +
                     text(px, py + 6, str(n), 16, LINE, "middle", 700))
        svg = '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="%d" height="%d" viewBox="0 0 %d %d">%s<rect x="1" y="1" width="%d" height="%d" fill="none" stroke="%s" stroke-width="2"/></svg>' % (
            cw, ch, cw, ch, body, cw - 2, ch - 2, LINE)
        p = os.path.join(OUT, "crop-" + name + ".svg")
        open(p, "w").write(svg)
        subprocess.run(["rsvg-convert", "-o", os.path.join(OUT, "crop-" + name + ".png"), p], check=True, cwd=OUT)
        os.remove(p)
        os.remove(tmp)
        print("crop-%s.png %dx%d from %s" % (name, cw, ch, src))


FIGS = {"cycle": fig_cycle, "chain": fig_chain, "funnel": fig_funnel, "increase": fig_increase, "gpu": fig_gpu, "crops": crops, "net": fig_net, "listen": fig_listen, "orrery": fig_orrery, "uml": fig_uml, "sequence": fig_sequence, "room": fig_room, "energy": fig_energy}

if __name__ == "__main__":
    want = [a for a in sys.argv[2:]] or list(FIGS)
    for k in want:
        FIGS[k]()
