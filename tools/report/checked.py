#!/usr/bin/env python3
"""checked.py QUEUE OUTDIR -- the figures and numbers of *Every Block Checked* (docs/checked-lab-report.md):
how often a proof was left before it could say anything, what a trial's spread is by how many dials it
moves, and where "a raid on the held ground" falls as w_pos_defend comes down.

Read from the queue as forward.py reads it (every census once more through treadcore's ledger.py; the
proofs from outgrowing.py's gather()), and from OUTDIR/cliff.tsv, the family's sweep as it was run on
saskatchewan on 13 November (`scenario_many`, 400 runs a value; the command is in the report). `--redraw
OUTDIR` draws again from OUTDIR/data.json. Figures in outgrowing.py's style; the first carries the sheet."""
import collections
import json
import math
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import forward as fw  # noqa: E402
import outgrowing as og  # noqa: E402

SINCE = "20261106"


def dials(trial):
    """How many dials and switches a trial's text moves."""
    parts = [x.strip() for x in re.split(r"[;\n]", trial) if "=" in x]
    n = len([x for x in parts if not x.startswith("caps")])
    return n + sum(len([c for c in x.split("=", 1)[1].split(",") if c.strip() and c.strip() != "baseline"]) for x in parts if x.startswith("caps"))


def gather(q, out):
    D = og.gather(q)
    m, p = og.planner(q)
    rows = fw.ledger_all(p)
    mv = D["moves"][-1]["at"] if D["moves"] else ""
    heads = [{"head": x["head"], "t0": x["t0"], "t1": x["t1"], "reads": x["reads"], "seeds": x["seeds"], "lead": x["lead"], "se": x["se"], "z": x["z"],
              "passed": x["z"] >= 3, "hours": (og.ep(x["t1"]) - og.ep(x["t0"])) / 3600, "gens": x["gens"]} for x in D["pairs"]]
    first = collections.defaultdict(list)
    tr = collections.defaultdict(lambda: {"held": [], "n": 0})
    for r in rows:
        if r["stamp"] < SINCE or not r["base"].startswith("caps=baseline"):
            continue
        n = min(dials(r["trial"]), 5)
        if n == 0:
            continue
        if r["kind"] == "w":
            first[n].append((r["dd"], r["ss"]))
        if r["kind"] == "h" and "-p" not in r["jid"]:
            k = (r["c"], r["trial"])
            tr[k]["held"].append(r["dd"])
            tr[k]["n"] = n
    by = []
    for n in sorted(first):
        ds = [d for d, _ in first[n]]
        ms = statistics.mean(s * s for _, s in first[n])
        hs = [statistics.mean(v["held"]) for v in tr.values() if v["n"] == n and v["held"]]
        by.append({"dials": n, "first": len(ds), "mean": statistics.mean(ds), "tau": math.sqrt(max(0.0, statistics.pvariance(ds) - ms)),
                   "held": len(hs), "held_mean": statistics.mean(hs) if hs else None})
    cliff = []
    with open(os.path.join(out, "cliff.tsv")) as f:
        f.readline()
        for l in f:
            v, held, runs = l.split("\t")
            cliff.append({"v": float(v), "held": int(held), "runs": int(runs)})
    st = json.load(open(os.path.join(q, "plan", "state.json")))
    rating = (json.load(open(os.path.join(q, "plan", "rating.json"))) if os.path.exists(os.path.join(q, "plan", "rating.json")) else {}).get("rows", [])
    return {"now": D["now"], "moved": mv, "heads": heads, "by_dials": by, "cliff": cliff, "orphans": st.get("orphans") or [], "rating": rating,
            "proof": (st.get("proof") or {}).get("last"), "line": st.get("local_line"), "far": {k: (st.get("far") or {}).get(k) for k in ("round", "total")},
            "refused": len(st.get("refused") or {})}


def fig_heads(F):
    """Fig. 1: every line head the proof read: the seeds it was read before it passed or was left, and its z then."""
    W, H = 960, 430
    x0, x1, y0, y1 = 80, 900, 360, 30
    lx = lambda v: x0 + (math.log10(v) - math.log10(500)) / (math.log10(40000) - math.log10(500)) * (x1 - x0)
    lo, hi = -3.0, 7.0
    sy = lambda v: y0 - (v - lo) / (hi - lo) * (y0 - y1)
    b = fw.yaxis(x0, x1, sy, lo, hi, 1.0)
    for v in (800, 1600, 3200, 6400, 12800, 25600):
        b += fw.grid(lx(v), y1, lx(v), y0) + og.text(lx(v), y0 + 16, "{:,}".format(v), "dim num", "middle")
    b += fw.grid(x0, sy(3), x1, sy(3), "thr") + og.text(x0 + 6, sy(3) - 12, "the proof's bar, z 3", "dim")
    b += fw.grid(lx(9400), y1, lx(9400), y0, "thr") + og.text(lx(9400) + 6, y1 + 12, "9,400 seeds: a true +0.25 shows at z 3", "dim")
    for h in F["heads"]:
        cls = "f3" if h["passed"] else "hollow"
        el = '<circle cx="%.1f" cy="%.1f" r="5" class="%s"%s/>' % (lx(max(500, h["seeds"])), sy(max(lo, min(hi, h["z"]))), cls, "" if h["passed"] else ' style="stroke:var(--s2)"')
        b += og.titled(el, "line %s, %s: read %d times, %d seeds in %.1f h; %+.2f ± %.2f over main, z %.2f; %s" % (
            h["head"], h["t0"][5:16], h["reads"], h["seeds"], h["hours"], h["lead"], h["se"], h["z"], "passed, main moved" if h["passed"] else "left when the head moved"))
    b += og.text((x0 + x1) / 2, y0 + 36, "seeds the proof read of the head (log scale)", "", "middle")
    b += fw.ylabel(20, y0, y1, "z of the line over main, when it passed or was left")
    b += '<circle cx="96" cy="%d" r="5" class="f3"/>' % (H - 18) + og.text(108, H - 14, "passed: the line went to main")
    b += '<circle cx="360" cy="%d" r="5" class="hollow" style="stroke:var(--s2)"/>' % (H - 18) + og.text(372, H - 14, "left: a generation moved the head, and the pool began again")
    return og.STYLE + og.svg(W, H, b, "Fig. 1: every line head the proof read, its seeds and its z when it passed or was left")


def fig_dials(F):
    """Fig. 2: the spread of the trials' true gains, by how many dials a trial moves."""
    B = F["by_dials"]
    W, H = 960, 330
    x0, x1, y0, y1 = 80, 900, 250, 30
    hi = math.ceil(max(x["tau"] for x in B) * 5) / 5
    sy = lambda v: y0 - v / hi * (y0 - y1)
    b = fw.yaxis(x0, x1, sy, 0, hi, 0.2, "%.1f")
    gw = (x1 - x0) / len(B)
    for i, x in enumerate(B):
        cx = x0 + gw * (i + 0.5)
        el = '<rect x="%.1f" y="%.1f" width="70" height="%.1f" rx="3" class="bar2"/>' % (cx - 35, sy(x["tau"]), max(1.0, sy(0) - sy(x["tau"])))
        b += og.titled(el, "%s dial(s): %d first reads, mean %+.2f, spread past noise %.2f; %d read held out, mean %s" % (
            "%d+" % x["dials"] if x["dials"] == 5 else x["dials"], x["first"], x["mean"], x["tau"], x["held"], "%+.2f" % x["held_mean"] if x["held_mean"] is not None else "none"))
        b += og.text(cx, sy(x["tau"]) - 6, "%.2f" % x["tau"], "num", "middle")
        b += og.text(cx, y0 + 18, "%s moved" % ("5 or more" if x["dials"] == 5 else x["dials"]), "", "middle")
        b += og.text(cx, y0 + 34, "{:,} trials".format(x["first"]), "dim num", "middle")
    b += fw.ylabel(20, y0, y1, "spread of true gains, a seat")
    return og.svg(W, H, b, "Fig. 2: the spread of the trials' true gains by how many dials a trial moves")


def fig_cliff(F):
    """Fig. 3: the family's runs held, as w_pos_defend comes down."""
    C = sorted(F["cliff"], key=lambda c: c["v"])
    W, H = 960, 360
    x0, x1, y0, y1 = 80, 900, 290, 30
    sx = lambda v: x0 + (v - 0.35) / (0.78 - 0.35) * (x1 - x0)
    sy = lambda v: y0 - v / 400 * (y0 - y1)
    b = ""
    for v in (0, 100, 200, 300, 400):
        b += fw.grid(x0, sy(v), x1, sy(v), "axis" if v == 0 else "grid") + og.text(x0 - 8, sy(v) + 4, str(v), "dim num", "end")
    for v in (0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75):
        b += fw.grid(sx(v), y0, sx(v), y0 + 5, "axis") + og.text(sx(v), y0 + 18, "%.2f" % v, "dim num", "middle")
    b += fw.grid(x0, sy(380), x1, sy(380), "thr") + og.text(x0 + 6, sy(380) + 16, "the family's floor, 95%", "dim")
    b += '<polyline points="%s" class="l2"/>' % " ".join("%.1f,%.1f" % (sx(c["v"]), sy(c["held"])) for c in C)
    for c in C:
        b += og.titled('<circle cx="%.1f" cy="%.1f" r="5" class="f2"/>' % (sx(c["v"]), sy(c["held"])), "w_pos_defend %.3g: held %d of %d" % (c["v"], c["held"], c["runs"]))
    b += og.text(sx(0.75) + 8, sy(400) + 4, "0.75, the default: 400", "num")
    b += og.text(sx(0.74) - 8, sy(56) - 8, "0.74: 56", "num", "end")
    b += og.text((x0 + x1) / 2, y0 + 38, "w_pos_defend", "", "middle")
    b += fw.ylabel(20, y0, y1, "runs held, of 400")
    return og.svg(W, H, b, "Fig. 3: a raid on the held ground, runs held as w_pos_defend comes down")


# ---- the diagrams: what each section talks about, as boxes and arrows ---------------------------
# Three kinds of box, said in each diagram's key and by each box's own first line: data (what is kept, and
# where), a function (the code that acts, by its name), an outcome (where a thing ends up).

class Flow:
    """Boxes placed by hand and arrows between them: N(name, x, y, w, kind, title, lines) and A(a, b, label)."""
    KIND = {"data": "gpu", "fn": "cpu", "out": "main", "note": "box"}

    SX = 1.2  # the hand-set columns, spread: room between boxes for an arrow's word

    def __init__(self, w, h, label):
        self.label, self.b, self.n = label, "", {}

    def N(self, name, x, y, w, kind, title, lines=()):
        x = 20 + (x - 20) * self.SX
        # A box is as wide as its words: the title in the condensed face, the lines in the mono.
        w = max(w, 24 + 6.5 * len(title), 24 + 6.7 * max([len(l) for l in lines] or [0]))
        h = 26 + 14 * len(lines) + (4 if lines else 0)
        self.n[name] = (x, y, w, h)
        self.b += og.node(x, y, w, h, self.KIND[kind], title, list(lines))
        return self

    def A(self, a, b, label="", bend=0, dash=False, dy=0):
        ax, ay, aw, ah = self.n[a]
        bx, by, bw, bh = self.n[b]
        if bx >= ax + aw:  # to the right
            x1, y1, x2, y2 = ax + aw, ay + ah / 2, bx - 2, by + bh / 2
        elif bx + bw <= ax:  # to the left
            x1, y1, x2, y2 = ax, ay + ah / 2, bx + bw + 2, by + bh / 2
        elif by >= ay + ah:  # below
            x1, y1, x2, y2 = ax + aw / 2, ay + ah, bx + bw / 2, by - 2
        else:  # above
            x1, y1, x2, y2 = ax + aw / 2, ay, bx + bw / 2, by + bh + 2
        el = og.arrow(x1, y1, x2, y2, "wire", bend)
        if dash:
            el = el.replace('class="wire"', 'class="no"')
        self.b += el
        if label:
            horizontal = abs(x2 - x1) >= abs(y2 - y1)
            self.b += og.text((x1 + x2) / 2 + (0 if horizontal else 6), (y1 + y2) / 2 + (-6 if horizontal else 4) + dy, label, "dim", "middle" if horizontal else "start")
        return self

    def T(self, x, y, words, cls="dim", anchor="start"):
        self.b += og.text(20 + (x - 20) * self.SX, y, words, cls, anchor)
        self.n["_t%d" % len(self.n)] = (20 + (x - 20) * self.SX, y - 12, 6.2 * len(words), 14)
        return self

    def key(self):
        self.h = max(y + h for _, y, _, h in self.n.values()) + 44
        self.w = max(960, max(x + w for x, _, w, _ in self.n.values()) + 20)
        y = self.h - 14
        for i, (cls, words) in enumerate((("gpu", "data: what is kept, and where"), ("cpu", "a function, by its name in the code"), ("main", "an outcome"))):
            x = 20 + i * 320
            self.b += '<rect x="%d" y="%d" width="16" height="12" rx="2" class="%s"/>' % (x, y - 10, cls) + og.text(x + 22, y, words)
        return self

    def svg(self):
        return og.svg(self.w, self.h, self.b, self.label)


def dia_road():
    f = Flow(960, 470, "Diagram 1: the road of a promotion, with the three gates built on 13 November")
    f.N("fit", 20, 20, 170, "fn", "suggest.py / far_trials", ["draws a trial: dials", "moved from the defaults"])
    f.N("seq", 230, 20, 170, "fn", "sequential()  SEQ", ["55 to 418 seeds, staged;", "read on, pass or drop"])
    f.N("held", 440, 20, 170, "fn", "held_pass()  HELD_Z", ["400 fresh seeds;", "z 3 less the ease: 2.5"])
    f.N("cand", 650, 20, 170, "data", "a candidate", ["plan/candidates.json", "its held-out reads"])
    f.A("fit", "seq", "trial").A("seq", "held", "passed").A("held", "cand", "passed")
    f.N("gates", 650, 130, 170, "fn", "auto_promote()", ["noise(): MIN_GAIN 0.25", "families hold", "trades_away(): the rule"])
    f.A("cand", "gates")
    f.N("refused", 860, 130, 90, "data", "refused", ["state", "kept"])
    f.A("gates", "refused", "past")
    f.N("settle", 440, 130, 170, "fn", "settling()  NEW", ["the head read 9,600", "seeds? if not: wait"])
    f.A("gates", "settle", "strongest")
    f.N("line", 230, 130, 170, "data", "the line", ["branch orrery/accepted", "state local_line"])
    f.A("settle", "line", "self_modify()")
    f.N("proof", 230, 250, 170, "fn", "line_proof()", ["main's values against", "the line's, pooled;", "six reads while settling"])
    f.A("line", "proof")
    f.A("proof", "settle", "seeds read", bend=30, dash=True)
    f.N("main", 20, 250, 170, "out", "main", ["resolve(): z 3 and", "no map against: pushed"])
    f.A("proof", "main", "proved")
    f.N("orph", 440, 250, 170, "out", "orphaned  NEW", ["orphan(): lead + 2 se", "under 0.25: off the line,", "the fleet back on main"])
    f.A("proof", "orph", "refused")
    f.N("on", 230, 370, 170, "note", "undecided", ["read on to 19,200", "seeds, then let go"])
    f.A("proof", "on")
    f.N("yard", 650, 250, 300, "fn", "rating()  NEW: the fixed yardstick", ["today's defaults against main of 28 Oct,", "2 Nov and 6 Nov, the same seeds each day", "-> plan/rating.json; decides nothing"])
    f.T(650, 365, "It stands beside the road, not on it:", "dim").T(650, 381, "it says whether the road went anywhere.", "dim")
    return f.key().svg()


def dia_lane():
    f = Flow(960, 260, "Diagram 2: a second lane on one machine")
    f.N("cfg", 20, 20, 250, "data", "config.json: two host entries", ["saskatchewan", "saskatchewan-2  build_of: saskatchewan"])
    f.N("lane1", 330, 10, 200, "fn", "lane()  the first", ["takes a job; its census", "runs on every core"])
    f.N("lane2", 330, 100, 200, "fn", "lane()  the second", ["takes another job into", "the gaps and the tails"])
    f.A("cfg", "lane1").A("cfg", "lane2")
    f.N("ready", 590, 100, 180, "fn", "ready() / builder()", ["asks after the build of", "build_of, not its own"])
    f.A("lane2", "ready")
    f.N("prep", 590, 10, 180, "data", "prep-saskatchewan-SHA", ["the one build, in done/"])
    f.A("lane1", "prep", "built").A("ready", "prep")
    f.N("rate", 810, 55, 140, "out", "seeds an hour", ["1,810 -> 2,700", "load 7-10 -> 19"])
    f.A("ready", "rate")
    f.N("plan", 20, 130, 250, "fn", "prep_id()  the planner", ["asks no build of a lane", "that has build_of"])
    f.A("plan", "cfg")
    return f.key().svg()


def dia_settle():
    f = Flow(960, 300, "Diagram 3: the line settles before it grows")
    f.N("cand", 20, 20, 190, "data", "candidates, passed", ["wait on the same defaults;", "the strongest goes next"])
    f.N("auto", 260, 20, 180, "fn", "auto_promote()", ["asks settling() before", "any generation"])
    f.A("cand", "auto")
    f.N("set", 490, 20, 200, "fn", "settling()", ["proof.last.seeds of this", "head < SETTLE_SEEDS 9,600?"])
    f.A("auto", "set")
    f.N("hold", 740, 20, 200, "out", "held: no generation", ["flag: the line HEAD", "settles first"])
    f.A("set", "hold", "yes")
    f.N("go", 490, 130, 200, "out", "self_modify()", ["the strongest candidate", "joins the line"])
    f.A("set", "go", "no")
    f.N("proof", 740, 130, 200, "fn", "line_proof()", ["no hour between rounds;", "SETTLE_JOBS 6 x 400 seeds"])
    f.A("hold", "proof")
    f.N("pool", 740, 230, 200, "data", "state proof.pooled", ["every read of this head", "against this main"])
    f.A("proof", "pool")
    f.A("pool", "set", "seeds", dash=True, bend=-40)
    f.T(20, 150, "Before: 28 of 37 heads were left after a", "dim").T(20, 166, "median 1,600 seeds; 9,400 are needed", "dim").T(20, 182, "to show a true +0.25 at z 3.", "dim")
    return f.key().svg()


def dia_orphan():
    f = Flow(960, 300, "Diagram 4: the three outcomes of a line's check")
    f.N("pool", 20, 110, 200, "data", "the pooled proof", ["lead, se, seeds of the", "line's head over main"])
    f.N("proved", 300, 10, 230, "fn", "z >= 3, no map against", ["resolve(upto=head)"])
    f.N("refused", 300, 110, 230, "fn", "seeds >= 9,600 and", ["lead + 2 se < MIN_GAIN 0.25:", "orphan(head, lead, se, seeds)"])
    f.N("open", 300, 220, 230, "fn", "neither", ["settling() holds on,", "to 19,200 seeds"])
    f.A("pool", "proved").A("pool", "refused").A("pool", "open")
    f.N("main", 620, 10, 320, "out", "main moves", ["the line's commits pushed; its runs approved"])
    f.A("proved", "main")
    f.N("off", 620, 90, 320, "out", "the block comes off", ["runs' status: orphaned (state orphans)", "branch orrery/accepted = origin/main", "state local_line gone: the fleet builds main", "main untouched; nothing pushed"])
    f.A("refused", "off")
    f.N("go", 620, 220, 320, "out", "let go, unproved", ["a generation may join; hourly proofs go on"])
    f.A("open", "go")
    return f.key().svg()


def dia_refusal():
    f = Flow(960, 230, "Diagram 5: a refusal is kept")
    f.N("cand", 20, 20, 200, "data", "a candidate's held-out reads", ["score, built, road,", "kills less deaths"])
    f.N("trade", 270, 20, 200, "fn", "trades_away()", ["gives up > TRADE_TIMES 2.5", "x its floor: past"])
    f.A("cand", "trade")
    f.N("ref", 520, 20, 200, "data", "state refused", ["refusal_key(weights) ->", "the rule as it stood"])
    f.A("trade", "ref", "past")
    f.N("re", 520, 130, 200, "fn", "reread_older()", ["the strongest older", "candidates, read again"])
    f.N("still", 270, 130, 200, "fn", "refused_still()", ["the rule unmoved?", "then not asked"])
    f.A("re", "still").A("still", "ref", dash=True)
    f.N("skip", 770, 130, 170, "out", "passed over", ["until a person moves", "the rule or a floor"])
    f.A("re", "skip")
    f.T(770, 40, "w_smooth 0.525: 13 refusals,", "dim").T(770, 56, "56 censuses, 11,382 seeds", "dim")
    return f.key().svg()


def dia_far():
    f = Flow(960, 270, "Diagram 6: one dial at a time, round after round")
    f.N("def", 20, 20, 180, "data", "today's defaults", ["defaults.toml", "128 dials above 0"])
    f.N("far", 250, 20, 200, "fn", "far_trials()", ["each dial alone, at", "value x step and / step"])
    f.A("def", "far")
    f.N("files", 500, 20, 200, "data", "far-NAME.lo / .hi", ["one dial a trial;", "FAR_SHARE of new trials"])
    f.A("far", "files")
    f.N("road", 750, 20, 190, "out", "the ordinary road", ["stages, held-out, gates:", "nothing passes for being far"])
    f.A("files", "road")
    f.N("r1", 250, 150, 110, "note", "round 1", ["step 4"])
    f.N("r2", 400, 150, 110, "note", "round 2", ["step 2"])
    f.N("r3", 550, 150, 110, "note", "round 3", ["step 1.41"])
    f.N("r4", 700, 150, 240, "note", "then 2 and 1.41 again", ["only when the defaults have moved"])
    f.A("r1", "r2").A("r2", "r3").A("r3", "r4")
    f.A("r1", "far", "FAR_STEPS")
    f.T(20, 150, "The fit's trials move 3 or 4 dials:", "dim").T(20, 166, "spread 0.25 to 0.30 a seat.", "dim").T(20, 182, "One dial alone: 1.15.", "dim")
    return f.key().svg()


def dia_auction():
    f = Flow(960, 300, "Diagram 7: the posture auction, and the tie at 0.75")
    f.N("raid", 20, 20, 200, "data", "a raider on held ground", ["board.incursion > 0", "x w_defend_ground 3.0"])
    f.N("score", 270, 20, 200, "fn", "scores", ["defend = base_threat / 0.5", "clamped: 1.0"])
    f.A("raid", "score")
    f.N("vd", 520, 20, 200, "data", "value(Defend)", ["w_pos_defend x 1.0", "= 0.75"])
    f.A("score", "vd")
    f.N("build", 20, 150, 200, "data", "a base half built", ["slots and castle left"])
    f.N("s2", 270, 150, 200, "fn", "scores", ["the building posture's", "share still to do"])
    f.A("build", "s2")
    f.N("vb", 520, 150, 200, "data", "value(building)", ["weight x score", "= 0.75 in this family"])
    f.A("s2", "vb")
    f.N("pick", 770, 85, 170, "fn", "the best, ties to", ["the ladder's order:", "Defend first"])
    f.A("vd", "pick").A("vb", "pick")
    f.N("out", 770, 200, 170, "out", "0.75: Defend, 400/400", ["0.74: building, 56/400"])
    f.A("pick", "out")
    return f.key().svg()


def dia_smooth():
    f = Flow(960, 300, "Diagram 8: w_smooth, one number, split into its parts")
    f.N("w", 20, 110, 170, "data", "w_smooth", ["default 0.05", "0.525: +3.3 score,", "-0.47 kills less deaths"])
    f.N("blend", 250, 10, 220, "fn", "smooth() / smooth_alpha()", ["the move's desire vector and", "the retreat thresholds: a blend"])
    f.A("w", "blend")
    f.N("on", 250, 130, 220, "fn", "smooth_on()", ["> 0.5: four behaviours", "at once, as before"])
    f.A("w", "on")
    f.N("part", 250, 230, 220, "fn", "smooth_part(W)  NEW", ["0 with_w_smooth | 1 off | 2 on"])
    f.A("on", "part")
    ys = (10, 80, 150, 220)
    for i, (k, what) in enumerate((("smooth_turret", "the turret's confirmation"), ("smooth_stance", "the stance's advance scalar"), ("smooth_supply", "resupply by the doctrine alone"), ("smooth_rung", "the rung's confirmation"))):
        f.N(k, 540, ys[i], 200, "data", k, [what])
        f.A("part", k)
    f.N("ab", 800, 110, 150, "out", "ab_trials()", ["reads each part", "on, by itself"])
    for k in ("smooth_turret", "smooth_stance", "smooth_supply", "smooth_rung"):
        f.A(k, "ab")
    return f.key().svg()


def dia_yard():
    f = Flow(960, 270, "Diagram 9: the fixed yardstick")
    for i, (d, c) in enumerate((("28 Oct", "dc3df01"), ("2 Nov", "da7e1da"), ("6 Nov", "63f2667"))):
        f.N("m%d" % i, 20, 10 + i * 66, 170, "data", "main of %s" % d, [c + ": its values"])
    f.N("rate", 250, 60, 200, "fn", "rating()", ["each as a trial against", "today's defaults; once a day"])
    for i in range(3):
        f.A("m%d" % i, "rate")
    f.N("jobs", 500, 60, 190, "data", "jobs rtNNNN", ["5 x 400 seeds a brain;", "THE SAME SEEDS each day"])
    f.A("rate", "jobs")
    f.N("pool", 500, 170, 190, "fn", "pool()", ["today's lead, its error"])
    f.A("jobs", "pool")
    f.N("rows", 740, 60, 200, "data", "plan/rating.json", ["at, today, against,", "lead, se, seeds"])
    f.A("pool", "rows")
    f.N("out", 740, 170, 200, "out", "a flag a day", ["promotes nothing;", "moves only if strength does"])
    f.A("rows", "out")
    f.N("today", 250, 170, 200, "data", "today's defaults", ["the line's head, or main"])
    f.A("today", "rate")
    return f.key().svg()


DIAGRAMS = {"road": dia_road, "lane": dia_lane, "settle": dia_settle, "orphan": dia_orphan, "refusal": dia_refusal, "far": dia_far,
            "auction": dia_auction, "smooth": dia_smooth, "yard": dia_yard}


def main(a):
    if a[0] == "--redraw":
        out = os.path.abspath(a[1])
        F = json.load(open(os.path.join(out, "data.json")))
    else:
        q, out = os.path.abspath(a[0]), os.path.abspath(a[1])
        F = gather(q, out)
        json.dump(F, open(os.path.join(out, "data.json"), "w"), indent=1, default=str)
    for k, v in {"heads": fig_heads(F), "dials": fig_dials(F), "cliff": fig_cliff(F)}.items():
        with open(os.path.join(out, "fig-%s.html" % k), "w") as f:
            f.write(v + "\n")
    for k, fn in DIAGRAMS.items():
        with open(os.path.join(out, "dia-%s.html" % k), "w") as f:
            f.write(fn() + "\n")
    print("wrote %s: 3 figures; %d heads, %d dial groups, %d cliff points, %d orphans, %d rating rows" % (out, len(F["heads"]), len(F["by_dials"]), len(F["cliff"]), len(F["orphans"]), len(F["rating"])))


if __name__ == "__main__":
    main(sys.argv[1:])
