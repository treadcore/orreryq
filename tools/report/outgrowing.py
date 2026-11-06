#!/usr/bin/env python3
"""outgrowing.py QUEUE OUTDIR -- the figures and numbers of *Outgrowing Yourself* (docs/outgrowing-lab-report.md):
what the GPU hands the game, how a generation's gain is claimed and how much of it main keeps, how long a
generation takes from its question to main, and what the card-hours cost.

Everything is read from the queue's own records and from git, nothing typed in: the planner's runs and their
states (imported, as montage.py does), events.jsonl (every job's start, end and seconds), the proof jobs'
census logs pooled by the planner's own pool(), the world home's ladder, lineage.tsv and growth.tsv, the
planner's energy tally (plan/timeline-bins.json), and treadcore's git -- its log, and the coordinator's reflog
of origin/main, which is the only record of WHEN main moved: a proof that passes fast-forwards main to the
line, and the commits keep the dates they were made on the line.

Writes OUTDIR/data.json and one figure a file, fig-NAME.html: inline SVG drawn on the report page's own
colour variables, so a figure follows the page into dark mode. A mark's numbers are in its <title>."""
import collections
import glob
import html
import importlib.util
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TC = os.path.expanduser("~/code/treadcore")
HOME = "crucible-world-hybrid"


def ep(s):
    return time.mktime(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))


def git(*a):
    return subprocess.run(["git", "-C", TC] + list(a), capture_output=True, text=True).stdout


def planner(q):
    s = importlib.util.spec_from_file_location("orrery_plan", os.path.join(os.path.dirname(HERE), "plans", "treadcore.py"))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m, m.Plan(q)


# ---- the numbers -------------------------------------------------------------------------------

def gather(q):
    m, p = planner(q)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    # Every promotion and what it claimed.
    runs = [r for r in p.runs() if r["kind"] == "promote"]
    proms = []
    for r in runs:
        st = p.rstate(r["id"])
        ev = st.get("evidence") or {}
        held = (ev.get("held") or [None])[-1]
        proms.append({"run": r["id"], "asked": r.get("asked"), "by": r.get("by"), "status": st.get("status"),
                      "trial": ((r.get("params") or {}).get("candidate") or "").split("/")[-1] or None,
                      "committed": st.get("approved"), "commit": (st.get("commit") or "")[:7], "census": ev.get("census"),
                      "held": held, "changed": st.get("changed") or [], "why": st.get("why", "")})
    gens = [x for x in proms if x["status"] in ("approved", "self-modified")]
    # The first job each trial ran: its first read began.
    want = {g["trial"] for g in gens if g["trial"]}
    first, hours, kinds, segs = {}, collections.defaultdict(lambda: [0.0, 0.0]), collections.Counter(), collections.defaultdict(list)
    with open(os.path.join(q, "events.jsonl")) as f:
        for line in f:
            if '"started"' in line:
                e = json.loads(line)
                t = e.get("job", "").split("-")[0]
                if t in want and t not in first:
                    first[t] = e["t"]
            elif '"done"' in line:
                e = json.loads(line)
                if e.get("event") != "done":
                    continue
                s = float(e.get("seconds") or 0)
                gpu = e.get("host", "").endswith("-cuda")
                hours[e["t"][:10]][0 if gpu else 1] += s / 3600
                kinds[("GPU" if gpu else "CPU", e.get("kind", ""))] += s / 3600
                if gpu:
                    segs[e["host"]].append((e["t"], s))
    # When main moved: the coordinator's reflog of origin/main, each push's promotions new to it.
    ents = []
    for l in git("reflog", "show", "refs/remotes/origin/main", "--date=format:%Y-%m-%dT%H:%M:%S", "--format=%gd\t%H").splitlines():
        d, h = l.split("\t")
        ents.append((d.split("@{")[1].rstrip("}"), h))
    ents.sort()
    moves, prev, on_main = [], set(), {}
    for at, h in ents:
        have = {s.split()[1].split("/")[1] for s in git("log", h, "--since=2026-10-27", "--format=%s").splitlines() if s.startswith("promote grove/")}
        new = have - prev
        if new:
            moves.append({"at": at, "sha": h[:7], "trials": sorted(new)})
            for t in new:
                on_main.setdefault(t, at)
        prev = have
    for g in gens:
        g["first"] = first.get(g["trial"])
        g["main"] = on_main.get(g["trial"])
    # The proofs: each job's census pooled as the planner pools it; its d is main's values over the line's,
    # so the line's lead is -d.
    proofs = []
    for f in sorted(glob.glob(os.path.join(q, "done", "*-pv*.json")), key=lambda f: f.split("-pv")[1]):
        j = json.load(open(f))
        ds = glob.glob(os.path.join(q, "results", j["id"], p.home, "out", j["id"], "*", ""))
        one = p.pool(ds) if ds else None
        mm = re.search(r"the line (\w+) against", j.get("title", ""))
        if one and mm:
            d, se, n = one["every"]
            proofs.append({"id": j["id"], "ended": j.get("ended", ""), "head": mm.group(1), "lead": -d, "se": se, "n": n})
    heads = collections.OrderedDict()
    for r in proofs:
        heads.setdefault(r["head"], []).append(r)
    # A head's generations: the promotions in its own history, less those main had when the proof read it.
    # (By time alone, a generation committed after the head was cut was counted on it.)
    by_trial = {g["trial"]: g for g in gens if g["trial"]}
    pairs = []
    for h, rs in heads.items():
        t0 = min(r["ended"] for r in rs)
        had = {t for mv in moves if mv["at"] <= t0 for t in mv["trials"]}
        mine = [x.split()[1].split("/")[1] for x in git("log", h, "--since=2026-10-27", "--format=%s").splitlines() if x.startswith("promote grove/")]
        on = sorted((by_trial[t] for t in set(mine) - had if t in by_trial), key=lambda g: g["run"])
        w = [1 / r["se"] ** 2 for r in rs]
        lead = sum(wi * r["lead"] for wi, r in zip(w, rs)) / sum(w)
        se = 1 / math.sqrt(sum(w))
        pairs.append({"head": h, "t0": t0, "t1": max(r["ended"] for r in rs), "reads": len(rs), "seeds": sum(r["n"] for r in rs),
                      "lead": lead, "se": se, "z": lead / se, "claimed": sum(g["held"][0] for g in on if g.get("held")),
                      "gens": [g["run"] for g in on], "unclaimed": [g["run"] for g in on if not g.get("held")]})
    moved_by = []
    for mv in moves:
        cands = [x for x in pairs if x["z"] >= 3 and x["t1"] <= mv["at"]]
        if cands and mv["at"] >= "2026-11-01T08:00":
            best = max(cands, key=lambda x: x["t1"])
            if best not in moved_by:
                moved_by.append(best)
                best["moved_main"] = mv["at"]
    # The world ladder: milestones, every exam against the newest, the yardstick.
    st = json.load(open(os.path.join(q, "plan", "state.json")))
    ms = (st.get("crucible_ladder:" + HOME) or {}).get("milestones", [])
    lineage = []
    with open(os.path.join(q, HOME, "lineage.tsv")) as f:
        head = f.readline().rstrip("\n").split("\t")
        for line in f:
            r = dict(zip(head, line.rstrip("\n").split("\t")))
            try:
                lineage.append({"t": r["time"], "island": r["island"], "gen": int(r["gen"]), "against": r["against"], "margin": float(r["margin_se"]), "result": r["result"]})
            except (KeyError, ValueError):
                pass
    growth = []
    with open(os.path.join(q, HOME, "growth.tsv")) as f:
        head = f.readline().rstrip("\n").split("\t")
        for line in f:
            r = dict(zip(head, line.rstrip("\n").split("\t")))
            try:
                growth.append({"t": r["time"], "island": r["island"], "gen": int(r["gen"]), "yard": float(r["yard"]), "pill_taken": float(r["pill_taken"]),
                               "hit_rate": float(r["hit_rate"]), "gens": int(r["gens"])})
            except (KeyError, ValueError):
                pass
    # Energy: the planner's tally, Wh a lane a day.
    bins = json.load(open(os.path.join(q, "plan", "timeline-bins.json")))
    energy = {d: [sum(v[1] for h, v in lanes.items() if h.endswith("-cuda")) / 1000, sum(v[1] for h, v in lanes.items() if not h.endswith("-cuda")) / 1000]
              for d, lanes in bins.get("energy", {}).items()}
    rate = json.load(open(os.path.join(os.path.dirname(HERE), "plans", "power.json"))).get("rate_usd_kwh", 0.17)
    # What the GPU's nets put into the game: every commit on main that changed a shipped net file.
    ships = []
    for l in git("log", "origin/main", "--format=%h\t%ad\t%s", "--date=format:%Y-%m-%dT%H:%M:%S", "--", "nets/gladiator.bin", "nets/scholar.bin").splitlines():
        h, at, subj = l.split("\t", 2)
        files = git("show", "--name-only", "--format=", h).split()
        ships.append({"sha": h, "at": at, "subject": subj, "files": [x for x in files if x.startswith("nets/")]})
    # The game's own changes that reset what a seat's score means: GAME_VERSION and SCORE_VERSION.
    versions = []
    for l in git("log", "origin/main", "--since=2026-10-27", "--format=%h\t%ad\t%s", "--date=format:%Y-%m-%dT%H:%M:%S").splitlines():
        h, at, subj = l.split("\t", 2)
        mg = re.match(r"^Game (\d+)", subj)
        if mg:
            versions.append({"at": at, "what": "game %s" % mg.group(1), "sha": h})
        elif "score versioned" in subj or "SCORE_VERSION" in subj:
            versions.append({"at": at, "what": "score 1", "sha": h})
    versions.sort(key=lambda v: v["at"])
    clone = (json.load(open(os.path.join(q, "plan", "clone.json"))) if os.path.exists(os.path.join(q, "plan", "clone.json")) else {}).get("rounds") or []
    bridge = json.load(open(os.path.join(q, "plan", "bridge.json"))) if os.path.exists(os.path.join(q, "plan", "bridge.json")) else {}
    seg_min = {h: {"all": statistics.median(s for _, s in v) / 60, "world": statistics.median([s for t, s in v if t >= "2026-11-04"] or [0]) / 60, "n": len(v)} for h, v in segs.items()}
    return {"now": now, "promotions": proms, "gens": gens, "moves": moves, "proofs": proofs, "pairs": pairs, "moved_by": moved_by, "milestones": ms, "lineage": lineage,
            "growth": growth, "hours": dict(hours), "kinds": {"%s %s" % k: v for k, v in kinds.items()}, "energy": energy, "rate": rate,
            "ships": ships, "versions": versions, "clone": clone, "bridge_reads": len(bridge.get("reads") or []), "segments": seg_min, "line": st.get("local_line") or {}, "proof_last": (st.get("proof") or {}).get("last")}


# ---- the drawing -------------------------------------------------------------------------------

# The series' colours: blue the GPU, orange the line and its CPUs, aqua main. Light steps deepened for the
# report's tan paper (#fce2ab), validated with the dataviz skill's validator (all pairs: CVD 7.7 protan, in
# the band that needs direct labels, which every series here has); dark steps are its reference palette's,
# validated against #181818 (CVD 9.4).
STYLE = """<style>
.ogv { --s1: #1c5cab; --s2: #c04a1c; --s3: #0f7a55; --s1f: #1c5cab33; --s2f: #c04a1c30; --s3f: #0f7a5533; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .ogv { --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s1f: #3987e540; --s2f: #d9592638; --s3f: #199e7040; } }
:root[data-theme="dark"] .ogv { --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s1f: #3987e540; --s2f: #d9592638; --s3f: #199e7040; }
.ogv { margin: 1.2em 0 .4em; }
.ogv svg { display: block; width: 100%; height: auto; overflow: visible; }
.ogv text { font-family: var(--cond); fill: var(--ink); font-size: 12px; }
.ogv .dim { fill: var(--dim); }
.ogv .num { font-family: var(--mono); font-size: 11px; }
.ogv .ttl { font-weight: 600; font-size: 13px; }
.ogv .grid { stroke: var(--line); stroke-width: 1; }
.ogv .axis { stroke: var(--dim); stroke-width: 1; }
.ogv .box { fill: var(--tile); stroke: var(--line); stroke-width: 1.5; }
.ogv .gpu { fill: var(--s1f); stroke: var(--s1); stroke-width: 2; }
.ogv .cpu { fill: var(--s2f); stroke: var(--s2); stroke-width: 2; }
.ogv .main { fill: var(--s3f); stroke: var(--s3); stroke-width: 2; }
.ogv .wire { fill: none; stroke: var(--dim); stroke-width: 1.5; }
.ogv .wire-gpu { fill: none; stroke: var(--s1); stroke-width: 2; }
.ogv .wire-cpu { fill: none; stroke: var(--s2); stroke-width: 2; }
.ogv .wire-main { fill: none; stroke: var(--s3); stroke-width: 2; }
.ogv .no { fill: none; stroke: var(--dim); stroke-width: 1.5; stroke-dasharray: 5 4; }
.ogv .f1 { fill: var(--s1); } .ogv .f2 { fill: var(--s2); } .ogv .f3 { fill: var(--s3); }
.ogv .l1 { stroke: var(--s1); stroke-width: 2; fill: none; } .ogv .l2 { stroke: var(--s2); stroke-width: 2; fill: none; } .ogv .l3 { stroke: var(--s3); stroke-width: 2; fill: none; }
.ogv .bar2 { fill: var(--s2); } .ogv .bar3 { fill: var(--s3f); stroke: var(--s3); stroke-width: 1.5; }
.ogv .wait { fill: none; stroke: var(--s3); stroke-width: 1.5; stroke-dasharray: 3 3; }
.ogv .thr { stroke: var(--ink); stroke-width: 1.5; stroke-dasharray: 6 4; }
.ogv .hollow { fill: var(--base); stroke-width: 2; }
.ogv rect.hit:hover, .ogv circle:hover { stroke: var(--ink); stroke-width: 2.5; }
</style>"""


def esc(s):
    return html.escape(str(s), quote=True)


def svg(w, h, body, label):
    return '<div class="ogv"><svg viewBox="0 0 %d %d" role="img" aria-label="%s">%s</svg></div>' % (w, h, esc(label), body)


def text(x, y, s, cls="", anchor="start", size=None):
    st = ' style="font-size:%dpx"' % size if size else ""
    return '<text x="%.1f" y="%.1f" text-anchor="%s" class="%s"%s>%s</text>' % (x, y, anchor, cls, st, esc(s))


def titled(el, tip):
    """A mark with its numbers as a hover title."""
    return el.replace("/>", "><title>%s</title></%s>" % (esc(tip), el.split()[0][1:]), 1)


def arrow(x1, y1, x2, y2, cls, bend=0):
    """A wire from (x1,y1) to (x2,y2) with its head, as one path and one polygon."""
    if bend:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        d = "M%.1f,%.1f Q%.1f,%.1f %.1f,%.1f" % (x1, y1, mx + bend, my - abs(bend), x2, y2)
        ang = math.atan2(y2 - (my - abs(bend)), x2 - (mx + bend))
    else:
        d = "M%.1f,%.1f L%.1f,%.1f" % (x1, y1, x2, y2)
        ang = math.atan2(y2 - y1, x2 - x1)
    hx, hy = x2, y2
    a1, a2 = ang + math.pi * 0.85, ang - math.pi * 0.85
    head = "%.1f,%.1f %.1f,%.1f %.1f,%.1f" % (hx, hy, hx + 8 * math.cos(a1), hy + 8 * math.sin(a1), hx + 8 * math.cos(a2), hy + 8 * math.sin(a2))
    col = {"wire-gpu": "var(--s1)", "wire-cpu": "var(--s2)", "wire-main": "var(--s3)"}.get(cls, "var(--dim)")
    return '<path d="%s" class="%s"/><polygon points="%s" style="fill:%s"/>' % (d, cls, head, col)


def node(x, y, w, h, cls, title, lines):
    out = '<rect x="%d" y="%d" width="%d" height="%d" rx="6" class="%s"/>' % (x, y, w, h, cls)
    out += text(x + 10, y + 18, title, "ttl")
    for i, l in enumerate(lines):
        out += text(x + 10, y + 34 + i * 14, l, "dim num")
    return out


def fig_roads():
    """Fig. 1: the roads from a computation to main, each gate with its condition as the code has it."""
    W, H = 960, 660
    b = ""
    b += text(20, 22, "GPU  (three CUDA cards)", "ttl")
    b += text(20, 38, "crucible islands: 100 generations a segment, 9-13 min", "dim")
    b += text(560, 22, "CPU FLEET  (treadcore census)", "ttl")
    b += text(560, 38, "ten machines; the scripted brain's ~300 dials", "dim")
    # the Gladiator road
    b += node(20, 56, 250, 66, "gpu", "1  Segment champion", ["exam: 2,048 duels against each", "of up to 8 rungs of the ladder"])
    b += node(20, 146, 250, 66, "gpu", "2  Milestone", ["over the newest: margin > 2 se,", "and the ladder's mean >= 0"])
    b += arrow(145, 122, 145, 144, "wire-gpu")
    b += node(20, 236, 250, 80, "gpu", "3  Bridge read (Gladiator)", ["newest milestone only, as style 17;", "2 censuses x 48 seeds, all maps;", "diff > 2 se (errors unpaired)"])
    b += arrow(145, 212, 145, 234, "wire-gpu")
    b += node(290, 236, 250, 80, "gpu", "Clone round (Scholar)", ["12 h and a new line head: record", "120 games (CPU), train on calber,", "judge: 48 seeds and the gauntlet"])
    b += node(20, 344, 250, 66, "gpu", "4  Ship a net file", ["bridge.py: auto mode, push ok;", "styles tests, push to main"])
    b += arrow(145, 316, 145, 342, "wire-gpu")
    b += arrow(380, 316, 272, 362, "wire-gpu")
    b += text(20, 432, "Shipped by this road so far: nothing.", "ttl")
    b += text(20, 448, "0 bridge reads (no milestone after the code landed);", "dim")
    b += text(20, 462, "4 clone rounds, each read under the Scholar it would replace.", "dim")
    b += text(20, 476, "The one GPU net on main, M0015 as the Gladiator,", "dim")
    b += text(20, 490, "was committed by hand (21fdfbd, 4 Nov 10:31).", "dim")
    # the line
    stages = [("Trial", ["a few dials drawn by suggest.py", "from the fit of every census"]),
              ("First read, read-ons", ["55 seeds, on to ~190 while it", "stays over the eased bar"]),
              ("Held-out read", ["400 seeds no search has seen,", "4 x 100 pooled; z over the bar"]),
              ("Families, gauntlet, tests", ["9 families, 22 gauntlets and", "168 tests at their floors"]),
              ("The line (committed)", ["orrery/accepted: every machine", "builds it, reads trials against it"])]
    y = 56
    for k, (t, ls) in enumerate(stages):
        b += node(560, y, 270, 62, "cpu", t, ls)
        if k:
            b += arrow(695, y - 20, 695, y - 2, "wire-cpu")
        y += 82
    b += node(560, 506, 270, 80, "main", "main (pushed)", ["the hourly proof: main's values as a", "trial against the line, 800 seeds,", "pooled; z >= 3 and the trade rule"])
    b += arrow(695, 446, 695, 504, "wire-main")
    b += arrow(272, 380, 558, 540, "wire-gpu")
    b += text(330, 520, "a net file goes straight to main:", "dim")
    b += text(330, 534, "no held-out read, no proof", "dim")
    # what does not travel
    b += '<path d="M272,180 C420,180 440,128 558,128" class="no"/>'
    b += text(330, 200, "no wire: no GPU number", "dim")
    b += text(330, 214, "reaches the line's dials", "dim")
    b += node(846, 506, 104, 80, "box", "The game", ["fleet: dials", "17: Gladiator", "6: Scholar"])
    b += arrow(830, 546, 844, 546, "wire")
    b += text(20, 640, "Blue: the GPU's road. Orange: the line. Green: main. Dashed: a connection that does not exist. Styles 17 and 6 play only when a person picks them.", "dim")
    return svg(W, H, b, "Fig. 1: the roads from the GPU and from the CPU census to treadcore main")


def time_axis(x0, x1, t0, t1, y_top, y_bot, every_h=24, fmt="%-d %b"):
    """Day ticks across a time span: returns (body, x_of)."""
    sx = lambda t: x0 + (t - t0) / (t1 - t0) * (x1 - x0)
    b = ""
    # A day at a time by the calendar, not by 86,400 s: the clocks fell back on 1 November, and adding seconds
    # put every later tick at 23:00 under the next day's name.
    lt = time.localtime(t0)
    k = 0
    while True:
        day = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday + k, 0, 0, 0, 0, 0, -1))
        k += 1
        if day > t1:
            break
        if day >= t0:
            x = sx(day)
            b += '<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" class="grid"/>' % (x, y_top, x, y_bot)
            b += text(x + 3, y_bot + 14, time.strftime(fmt, time.localtime(day)), "dim num")
    return b, sx


def fig_lanes(D):
    """Fig. 2: nine days in lanes -- milestones, shipped nets, the game's versions, line commits, main moves."""
    W, H = 960, 300
    t0, t1 = ep("2026-10-28T00:00:00"), ep(D["now"])
    x0, x1 = 150, 940
    ax, sx = time_axis(x0, x1, t0, t1, 30, 250)
    b = ax
    lanes = [("GPU milestones", 50), ("GPU nets to main", 90), ("Game / score version", 130), ("Line commits", 170), ("Main moves", 210)]
    for name, y in lanes:
        b += text(10, y + 4, name, "dim")
        b += '<line x1="%d" y1="%d" x2="%d" y2="%d" class="grid" style="stroke-dasharray:2 3"/>' % (x0, y, x1, y)
    for mm in D["milestones"]:
        if mm.get("made"):
            t = ep(mm["made"])
            if t >= t0:
                b += titled('<circle cx="%.1f" cy="50" r="5" class="f1"/>' % sx(t), "%s at %s, %.1f se over %s" % (mm["id"], mm["made"][5:16], mm.get("margin_se") or 0, mm.get("after")))
    for s in D["ships"]:
        t = ep(s["at"])
        if t >= t0:
            b += titled('<rect x="%.1f" y="74" width="12" height="14" rx="3" class="f1"/>' % (sx(t) - 6), "%s %s: %s" % (s["sha"], s["at"][5:16], s["subject"][:120]))
    for c in D["clone"]:
        if c.get("asked"):
            el = '<rect x="%.1f" y="93" width="12" height="14" rx="3" class="hollow" style="stroke:var(--s1)"/>' % (sx(ep(c["asked"])) - 6)
            b += titled(el, "clone round %s, asked %s: clone %+.2f vs the Scholar %+.2f, %+.2f ± %.2f; %s" % (
                c.get("n"), c["asked"][5:16], (c.get("cand_read") or [0])[0], (c.get("ship_read") or [0])[0], c.get("diff") or 0, c.get("se") or 0, "shipped" if c.get("holds") else "not shipped"))
    for v in D["versions"]:
        t = ep(v["at"])
        b += titled('<rect x="%.1f" y="122" width="4" height="16" class="f2" style="fill:var(--dim)"/>' % (sx(t) - 2), "%s at %s (%s)" % (v["what"], v["at"][5:16], v["sha"]))
    lab = {}
    for v in D["versions"]:
        k = round(sx(ep(v["at"])) / 40)
        lab.setdefault(k, []).append(v["what"].replace("game ", "g").replace("score 1", "s1"))
    for k, ws in lab.items():
        b += text(k * 40 + 6, 145, ",".join(ws), "dim num")
    for g in D["gens"]:
        if g["committed"]:
            hand = g["by"] not in ("auto",)
            b += titled('<circle cx="%.1f" cy="170" r="5" class="%s"/>' % (sx(ep(g["committed"])), "hollow" if hand else "f2") + "", "%s %s committed %s; held out %s" % (
                g["run"], g["trial"] or "(by hand)", g["committed"][5:16], "%+.2f ± %.2f" % tuple(g["held"]) if g.get("held") else "-")).replace('class="hollow"', 'class="hollow" style="stroke:var(--s2)"')
    for mv in D["moves"]:
        b += titled('<rect x="%.1f" y="202" width="10" height="16" rx="2" class="f3"/>' % (sx(ep(mv["at"])) - 5), "main moved %s to %s: %s" % (mv["at"][5:16], mv["sha"], ", ".join(mv["trials"])))
    # the waiting line
    if D["line"].get("promotions"):
        first = min(ep(g["committed"]) for g in D["gens"] if g["status"] == "self-modified")
        b += '<line x1="%.1f" y1="230" x2="%.1f" y2="230" class="wait"/>' % (sx(first), x1)
        b += text(x1, 244, "the line waits for its proof", "dim", "end")
    b += text(10, 290, "Filled square: a GPU net on main (by hand). Hollow squares: clone rounds, none shipped. Hollow dots: generations committed by hand. Hover a mark.", "dim")
    return svg(W, H, b, "Fig. 2: nine days of milestones, shipped nets, game versions, line commits and main moves")


def fig_turnaround(D):
    """Fig. 3: each generation from its first read to its commit (left) and from its commit to main (right)."""
    gens = [g for g in D["gens"] if g["committed"]]
    W = 960
    row = 17
    H = 70 + row * len(gens) + 40
    x0, xc, x1 = 190, 520, 940
    left_h, right_h = 36.0, 24.0
    sl = lambda h: xc - min(h, left_h) / left_h * (xc - x0)
    sr = lambda h: xc + min(h, right_h) / right_h * (x1 - xc)
    b = text(xc - 8, 22, "first read → commit (hours before)", "ttl", "end")
    b += text(xc + 8, 22, "commit → main (hours after)", "ttl")
    for hh in (0, 6, 12, 24, 36):
        x = sl(hh)
        b += '<line x1="%.1f" y1="34" x2="%.1f" y2="%d" class="grid"/>' % (x, x, H - 34) + text(x, H - 20, "%d" % hh, "dim num", "middle")
    for hh in (6, 12, 18, 24):
        x = sr(hh)
        b += '<line x1="%.1f" y1="34" x2="%.1f" y2="%d" class="grid"/>' % (x, x, H - 34) + text(x, H - 20, "%d" % hh, "dim num", "middle")
    b += '<line x1="%d" y1="30" x2="%d" y2="%d" class="axis"/>' % (xc, xc, H - 30)
    now = ep(D["now"])
    for i, g in enumerate(gens):
        y = 44 + i * row
        b += text(10, y + 11, "%s %s" % (g["run"], g["trial"] or "by hand"), "num")
        if g.get("first"):
            h = (ep(g["committed"]) - ep(g["first"])) / 3600
            x = sl(h)
            b += titled('<rect x="%.1f" y="%d" width="%.1f" height="12" rx="3" class="bar2 hit"/>' % (x, y + 1, xc - x), "%s: first read %s, committed %s, %.1f h" % (
                g["trial"], g["first"][5:16], g["committed"][5:16], h))
            if h > left_h:
                b += text(x0 + 4, y + 11, "%.0f h ‹" % h, "num")
        if g.get("main"):
            h = (ep(g["main"]) - ep(g["committed"])) / 3600
            if h > 0.05:
                b += titled('<rect x="%d" y="%d" width="%.1f" height="12" rx="3" class="bar3 hit"/>' % (xc, y + 1, sr(h) - xc), "%s: committed %s, on main %s, %.1f h" % (
                    g["trial"], g["committed"][5:16], g["main"][5:16], h))
            else:
                b += text(xc + 6, y + 11, "straight to main", "dim num")
        elif g["status"] == "self-modified":
            h = (now - ep(g["committed"])) / 3600
            b += titled('<rect x="%d" y="%d" width="%.1f" height="12" rx="3" class="wait hit"/>' % (xc, y + 1, sr(h) - xc), "%s: on the line since %s, %.1f h, waiting for the proof" % (
                g["trial"], g["committed"][5:16], h))
            b += text(sr(h) + 6, y + 11, "waiting, %.0f h" % h, "dim num")
        else:
            b += text(xc + 6, y + 11, "by hand, with its batch", "dim num")
    b += text(10, H - 4, "Orange: the fleet's work on the question. Green: the commit waiting for main. Dashed: still waiting. Hover a bar for its times.", "dim")
    return svg(W, H, b, "Fig. 3: turnaround of every committed generation")


def fig_claims(D):
    """Fig. 4: what the line's generations claimed (the sum of their held-out reads) against what the proof
    read of the line over main."""
    W, H = 960, 470
    x0, x1, y0, y1 = 80, 600, 420, 30
    vmin, vmax = -1.0, 6.0
    sx = lambda v: x0 + (v - vmin) / (vmax - vmin) * (x1 - x0)
    sy = lambda v: y0 - (v - vmin) / (vmax - vmin) * (y0 - y1)
    b = ""
    for v in range(-1, 7):
        b += '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" class="grid"/>' % (x0, sy(v), x1, sy(v)) + text(x0 - 8, sy(v) + 4, "%+d" % v if v else "0", "dim num", "end")
        b += '<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" class="grid"/>' % (sx(v), y0, sx(v), y1) + text(sx(v), y0 + 16, "%+d" % v if v else "0", "dim num", "middle")
    b += '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" class="thr"/>' % (sx(-1), sy(-1), sx(6), sy(6))
    b += text(sx(4.6), sy(5.0), "kept all it claimed", "dim", "end")
    b += text((x0 + x1) / 2, y0 + 36, "claimed: the sum of the held-out reads of the generations on the line", "", "middle")
    b += '<text transform="translate(18,%d) rotate(-90)" text-anchor="middle">proven: the line read over main (± 1 se)</text>' % ((y0 + y1) // 2)
    for pr in D["pairs"]:
        if not pr["gens"]:
            continue
        x, y = sx(pr["claimed"]), sy(pr["lead"])
        passed = pr["z"] >= 3
        b += '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" class="%s"/>' % (x, sy(pr["lead"] - pr["se"]), x, sy(pr["lead"] + pr["se"]), "l3" if passed else "l2")
        cls = "f3" if passed else "hollow"
        tip = "line %s, %s-%s: %s; claimed %+.2f, proven %+.2f ± %.2f over %d seeds (z %.1f)%s" % (
            pr["head"], pr["t0"][5:16], pr["t1"][11:16], ", ".join(pr["gens"]), pr["claimed"], pr["lead"], pr["se"], pr["seeds"], pr["z"], "; passed, main moved" if passed else "")
        el = '<circle cx="%.1f" cy="%.1f" r="6" class="%s"%s/>' % (x, y, cls, "" if passed else ' style="stroke:var(--s2)"')
        b += titled(el, tip)
    # the current line, labelled
    cur = D["pairs"][-1]
    b += '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" class="axis"/>' % (sx(cur["claimed"]), sy(cur["lead"]) + 8, sx(cur["claimed"]) + 30, sy(-0.55))
    b += text(sx(cur["claimed"]) + 32, sy(-0.6), "the line now, %s: %s" % (cur["head"], ", ".join(cur["gens"])), "num")
    # legend
    b += '<circle cx="640" cy="60" r="6" class="f3"/>' + text(654, 64, "a line head the proof passed (z ≥ 3)")
    b += '<circle cx="640" cy="86" r="6" class="hollow" style="stroke:var(--s2)"/>' + text(654, 90, "a line head the proof read and did not pass")
    b += text(630, 130, "Points under the dashed line kept less than", "dim")
    b += text(630, 146, "their generations claimed. When main moved,", "dim")
    mv = D["moved_by"]
    b += text(630, 162, "the %d lines it took had claimed %+.2f in all;" % (len(mv), sum(p["claimed"] for p in mv)), "dim")
    b += text(630, 178, "the proofs that passed them read %+.2f." % sum(p["lead"] for p in mv), "dim")
    b += text(630, 210, "One head can be read many times: each push to", "dim")
    b += text(630, 226, "main (a report, a fix) replays the line, gives it", "dim")
    b += text(630, 242, "a new head, and starts its proof's pool again.", "dim")
    return svg(W, H, b, "Fig. 4: claimed against proven for every line head the proof read")


def fig_ladder(D):
    """Fig. 5: (a) each milestone's margin over the one before; (b) since M0015, the best and median exam
    against it an hour; (c) the yardstick a half-day."""
    W, H = 960, 600
    b = ""
    ms = [m for m in D["milestones"] if m.get("after")]
    # (a)
    b += text(20, 20, "(a) Each milestone's margin over the one before it, in standard errors (dashed: the bar, 2)", "ttl")
    ax0, ax1, ay0, ay1 = 60, 940, 170, 34
    top = 55.0
    sy = lambda v: ay0 - v / top * (ay0 - ay1)
    for v in (0, 10, 20, 30, 40, 50):
        b += '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" class="grid"/>' % (ax0, sy(v), ax1, sy(v)) + text(ax0 - 6, sy(v) + 4, "%d" % v, "dim num", "end")
    bw = (ax1 - ax0) / len(ms)
    for i, m in enumerate(ms):
        v = m.get("margin_se") or 0
        x = ax0 + i * bw + 3
        b += titled('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" class="f1 hit"/>' % (x, sy(v), bw - 6, ay0 - sy(v)), "%s, made %s: %.1f se over %s" % (m["id"], (m.get("made") or "")[5:16], v, m.get("after")))
        b += text(x + (bw - 6) / 2, sy(v) - 4, "%.1f" % v, "num", "middle")
        b += text(x + (bw - 6) / 2, ay0 + 14, m["id"][:5], "dim num", "middle")
    b += '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" class="thr"/>' % (ax0, sy(2), ax1, sy(2))
    # (b)
    b += text(20, 222, "(b) Since M0015: the exams against it, best (solid) and median (dotted) of each hour, in se (dashed: the bar, +2)", "ttl")
    bx0, bx1, by0, by1 = 60, 940, 420, 236
    last = ms[-1]["id"] if ms else None
    ex = [r for r in D["lineage"] if last and r["against"].startswith(last)]
    hours = collections.defaultdict(list)
    for r in ex:
        hours[r["t"][:13]].append(r["margin"])
    ks = sorted(hours)
    t0, t1 = ep(ks[0] + ":00:00"), ep(D["now"])
    lo, hi = -50.0, 5.0
    syb = lambda v: by0 - (max(lo, min(hi, v)) - lo) / (hi - lo) * (by0 - by1)
    for v in (-50, -40, -30, -20, -10, 0):
        b += '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" class="grid"/>' % (bx0, syb(v), bx1, syb(v)) + text(bx0 - 6, syb(v) + 4, "%d" % v, "dim num", "end")
    axb, sxb = time_axis(bx0, bx1, t0, t1, by1, by0)
    b += axb
    best = " ".join("%.1f,%.1f" % (sxb(ep(k + ":30:00")), syb(max(hours[k]))) for k in ks)
    med = " ".join("%.1f,%.1f" % (sxb(ep(k + ":30:00")), syb(statistics.median(hours[k]))) for k in ks)
    b += '<polyline points="%s" class="l1"/>' % best
    b += '<polyline points="%s" class="l1" style="stroke-dasharray:4 3;opacity:.7"/>' % med
    for k in ks:
        b += titled('<circle cx="%.1f" cy="%.1f" r="3" class="f1"/>' % (sxb(ep(k + ":30:00")), syb(max(hours[k]))), "%s:00, %d exams: best %+.1f, median %+.1f se" % (
            k[5:], len(hours[k]), max(hours[k]), statistics.median(hours[k])))
    b += '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" class="thr"/>' % (bx0, syb(2), bx1, syb(2))
    kl = ks[-1]
    b += text(sxb(ep(kl + ":30:00")) - 4, syb(max(hours[kl])) - 8, "best", "num", "end")
    b += text(sxb(ep(kl + ":30:00")) - 4, syb(statistics.median(hours[kl])) + 16, "median", "num", "end")
    # (c)
    b += text(20, 470, "(c) The yardstick: the share of duels won against crucible's fixed opponent, median of each half-day, all islands", "ttl")
    cx0, cx1, cy0, cy1 = 60, 940, 580, 486
    half = collections.defaultdict(list)
    for r in D["growth"]:
        half[r["t"][:10] + ("a" if r["t"][11:13] < "12" else "p")].append(r["yard"])
    hk = [k for k in sorted(half) if len(half[k]) >= 20]
    lo2, hi2 = 0.70, 0.74
    syc = lambda v: cy0 - (v - lo2) / (hi2 - lo2) * (cy0 - cy1)
    for v in (0.70, 0.72, 0.74):
        b += '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" class="grid"/>' % (cx0, syc(v), cx1, syc(v)) + text(cx0 - 6, syc(v) + 4, "%.2f" % v, "dim num", "end")
    cx0 += 0
    cx0 += 40
    cx1 -= 30
    step = (cx1 - cx0) / max(1, len(hk) - 1)
    pts = []
    for i, k in enumerate(hk):
        v = statistics.median(half[k])
        x = cx0 + i * step
        pts.append("%.1f,%.1f" % (x, syc(v)))
        b += titled('<circle cx="%.1f" cy="%.1f" r="4" class="f1"/>' % (x, syc(v)), "%s %s: median %.3f over %d segments" % (k[5:10], "morning" if k.endswith("a") else "afternoon", v, len(half[k])))
        b += text(x, cy0 + 14, "%s %s" % (k[8:10] + " Nov", "am" if k.endswith("a") else "pm"), "dim num", "middle")
        b += text(x, syc(v) - 8, "%.3f" % v, "num", "middle")
    b += '<polyline points="%s" class="l1"/>' % " ".join(pts)
    return svg(W, H, b, "Fig. 5: the world ladder's milestones, the exams since the last, and the yardstick")


def fig_hours(D):
    """Fig. 6: job-hours a day, the GPU's cards and the CPU machines, with each day's kWh."""
    W, H = 960, 330
    days = sorted(D["hours"])
    x0, x1, y0, y1 = 60, 940, 250, 40
    top = 200.0
    sy = lambda v: y0 - v / top * (y0 - y1)
    b = ""
    for v in (0, 50, 100, 150, 200):
        b += '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" class="grid"/>' % (x0, sy(v), x1, sy(v)) + text(x0 - 6, sy(v) + 4, "%d h" % v, "dim num", "end")
    gw = (x1 - x0) / len(days)
    bw = (gw - 18) / 2
    for i, d in enumerate(days):
        g, c = D["hours"][d]
        e = D["energy"].get(d, [0, 0])
        x = x0 + i * gw + 9
        b += titled('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" class="f1 hit"/>' % (x, sy(g), bw, y0 - sy(g)), "%s: GPU %.1f card-hours, %.1f kWh" % (d, g, e[0]))
        b += titled('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" class="f2 hit"/>' % (x + bw + 2, sy(c), bw, y0 - sy(c)), "%s: CPU %.1f machine-hours, %.1f kWh" % (d, c, e[1]))
        b += text(x + bw / 2, sy(g) - 4, "%.0f" % g, "num", "middle")
        b += text(x + bw * 1.5 + 2, sy(c) - 4, "%.0f" % c, "num", "middle")
        b += text(x + bw, y0 + 16, time.strftime("%-d %b", time.strptime(d, "%Y-%m-%d")), "dim num", "middle")
        b += text(x + bw, y0 + 32, "%.1f kWh" % (e[0] + e[1]), "dim num", "middle")
    b += '<rect x="640" y="12" width="12" height="12" rx="2" class="f1"/>' + text(658, 22, "GPU card-hours (3 cards: 72 a day at most)")
    b += '<rect x="640" y="30" width="12" height="12" rx="2" class="f2"/>' + text(658, 40, "CPU machine-hours")
    b += text(10, 320, "Job-hours from events.jsonl (a job's seconds on its machine); kWh from the planner's energy tally. 31 Oct: the fleet was shut down.", "dim")
    return svg(W, H, b, "Fig. 6: job-hours a day on the GPU and the CPU machines")


# ---- the view: Results, Generations (orrery src/generations.rs) ----------------------------------

def view(q, out):
    """The same numbers as the report's, live, for orrery's Generations page: written to `out` (the queue's
    plan/generations.json), which treadcore-view.py hands the app. The report's figures, tab by tab, and
    the forest home's elections, its bar and floors, and the window's best candidate."""
    D = gather(q)
    ep_ = lambda x: ep(x) if x else None
    m, p = planner(q)
    st = json.load(open(os.path.join(q, "plan", "state.json")))
    homes = {}
    for key in [k for k in st if k.startswith("crucible_ladder:")]:
        home = key.split(":", 1)[1]
        lad = st[key]
        el = []
        try:
            with open(os.path.join(q, home, "elect.tsv")) as f:
                head = f.readline().rstrip("\n").split("\t")
                for line in f:
                    el.append(dict(zip(head, line.rstrip("\n").split("\t"))))
        except OSError:
            pass
        bar, dry = (m.Plan.gpu_bar(p, lad) if hasattr(m.Plan, "gpu_bar") else (None, None))
        gl = sorted(glob.glob(os.path.join(q, "results", "x-*", p.home, "out", "x-*", "gauntlet.tsv")), key=os.path.getmtime)
        latest = None
        for g in reversed(gl):
            jid = g.split("/out/")[1].split("/")[0]
            if (st.get("crucible_homes") or {}).get(jid, home) == home or home.endswith("-forest"):
                latest = {"job": jid, "read": m.Plan.gauntlet_read(g)} if hasattr(m.Plan, "gauntlet_read") else None
                break
        # The game's read of each, from the bridge: credited when it beat the shipped Gladiator.
        br = json.load(open(os.path.join(q, "plan", "bridge.json"))) if os.path.exists(os.path.join(q, "plan", "bridge.json")) else {}
        game = {r.get("label"): {"diff": r.get("diff"), "se": r.get("se"), "credited": bool(r.get("holds")), "vs_rules": r.get("vs_rules") or
                                 ([r["cand"][0], r["cand"][1], round(r["cand"][0] / r["cand"][1], 2)] if r.get("cand") and r["cand"][1] else None), "read": r.get("read")}
                for r in (br.get("reads") or []) if r.get("label")}
        homes[home] = {"milestones": [{"id": x["id"], "made": x.get("made"), "margin": x.get("margin_se"), "carried": bool(x.get("carried")),
                                       "elected": bool(x.get("elected")), "zg": x.get("zg"), "zy": x.get("zy"), "game": game.get(x["id"])}
                                      for x in lad.get("milestones", [])],
                       "bridge_now": (br.get("current") or {}).get("label"),
                       "bar": bar, "dry_h": dry, "floors": lad.get("floors") or {}, "best": lad.get("best"), "began": lad.get("began"),
                       "elections": el[-400:], "latest": latest if home.endswith("-forest") else None}
    last = None
    for mm in D["milestones"]:
        last = mm["id"]
    hours = collections.defaultdict(list)
    for r in D["lineage"]:
        if last and r["against"].startswith(last):
            hours[r["t"][:13]].append(r["margin"])
    half = collections.defaultdict(list)
    for r in D["growth"]:
        half[r["t"][:10] + ("a" if r["t"][11:13] < "12" else "p")].append(r["yard"])
    gens = [{"run": g["run"], "trial": g["trial"], "by": g["by"], "status": g["status"], "first": g.get("first"), "committed": g["committed"],
             "main": g.get("main"), "held": g.get("held"), "census": g.get("census"), "changed": g.get("changed")} for g in D["gens"]]
    gh = sum(v[0] for v in D["hours"].values()); ch = sum(v[1] for v in D["hours"].values())
    ge = sum(v[0] for v in D["energy"].values()); ce = sum(v[1] for v in D["energy"].values())
    fh = homes.get("crucible-world-hybrid-forest") or {}
    bought = {"gpu": [["milestones", len([x for x in D["milestones"] if not x.get("carried")])],
                      ["forest generations", len([x for x in fh.get("milestones", []) if not x.get("carried")])],
                      ["nets on main", len(D["ships"])], ["clone rounds", len(D["clone"])],
                      ["clone rounds shipped", len([c for c in D["clone"] if c.get("holds")])]],
              "cpu": [["generations committed", len(D["gens"])], ["main moves", len(D["moves"])],
                      ["proven since score 1", round(sum(x["lead"] for x in D["moved_by"] if x["t0"] >= "2026-11-04T13:00"), 2)]]}
    doc = {"at": D["now"], "gens": gens, "moves": D["moves"], "pairs": D["pairs"], "moved_by": [x["head"] for x in D["moved_by"]],
           "milestones": [{"id": x["id"], "made": x.get("made"), "margin": x.get("margin_se"), "carried": bool(x.get("carried"))} for x in D["milestones"]],
           "exams": [[k, max(v), statistics.median(v), len(v)] for k, v in sorted(hours.items())],
           "yard": [[k, statistics.median(v), len(v)] for k, v in sorted(half.items()) if len(v) >= 10],
           "hours": [[d, v[0], v[1], (D["energy"].get(d) or [0, 0])[0], (D["energy"].get(d) or [0, 0])[1]] for d, v in sorted(D["hours"].items())],
           "totals": {"gpu_h": gh, "cpu_h": ch, "gpu_kwh": ge, "cpu_kwh": ce, "rate": D["rate"]}, "bought": bought,
           "ships": D["ships"], "clone": [{"n": c.get("n"), "asked": c.get("asked"), "diff": c.get("diff"), "se": c.get("se"), "holds": c.get("holds")} for c in D["clone"]],
           "versions": D["versions"], "homes": homes, "proof": D.get("proof_last"), "line": D["line"]}
    tmp = out + ".part"
    with open(tmp, "w") as f:
        json.dump(doc, f, default=str)
    os.replace(tmp, out)
    print("wrote %s" % out)


def main(a):
    if len(a) >= 3 and a[1] == "--view":
        view(os.path.abspath(a[0]), os.path.abspath(a[2]))
        return
    q, out = os.path.abspath(a[0]), os.path.abspath(a[1])
    os.makedirs(out, exist_ok=True)
    D = gather(q)
    json.dump(D, open(os.path.join(out, "data.json"), "w"), indent=1, default=str)
    figs = {"roads": STYLE + fig_roads(), "lanes": fig_lanes(D), "turnaround": fig_turnaround(D), "claims": fig_claims(D), "ladder": fig_ladder(D), "hours": fig_hours(D)}
    for k, v in figs.items():
        with open(os.path.join(out, "fig-%s.html" % k), "w") as f:
            f.write(v + "\n")
    print("wrote %s: %d figures, data.json (%d generations, %d proofs, %d heads, %d milestones)" % (out, len(figs), len(D["gens"]), len(D["proofs"]), len(D["pairs"]), len(D["milestones"])))


if __name__ == "__main__":
    main(sys.argv[1:])
