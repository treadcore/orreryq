#!/usr/bin/env python3
"""reopened.py QUEUE OUTDIR -- the figures, diagrams and numbers of *Old Decisions, Reopened*
(docs/reopened-lab-report.md): what each rule set aside on 13 November had cost and bought, read from
the queue (events.jsonl for the hours, plan/clone.json, plan/bridge.json, tuning.json, plan.json), and one
diagram a rule in checked.py's boxes: data, function, outcome. `--redraw OUTDIR` draws from data.json."""
import collections
import json
import math
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import checked as ck  # noqa: E402
import forward as fw  # noqa: E402
import outgrowing as og  # noqa: E402

SINCE = "2026-11-10"
KINDS = {"e": "reads on", "w": "first reads", "r:k": "the transform rotation", "h": "held-out reads", "pv": "the proof"}


def gather(q):
    sec, n = collections.Counter(), collections.Counter()
    with open(os.path.join(q, "events.jsonl")) as f:
        for line in f:
            if '"done"' not in line:
                continue
            e = json.loads(line)
            if e.get("event") != "done" or not (SINCE <= e["t"] < "2026-11-13T08:00") or e["host"].endswith("-cuda") or e["host"] == "mac":
                continue
            j = e["job"]
            k = re.match(r"[a-z]+", j).group(0)
            if k == "r":
                k = "r:" + (j.split("-")[1][:1] if "-" in j else "?")
            sec[k] += float(e.get("seconds") or 0)
            n[k] += 1
    tot = sum(sec.values())
    hours = [{"kind": KINDS.get(k, k), "jobs": n[k], "hours": v / 3600, "share": v / tot} for k, v in sec.most_common(5)]
    hours.append({"kind": "everything else", "jobs": sum(n.values()) - sum(h["jobs"] for h in hours), "hours": (tot - sum(h["hours"] * 3600 for h in hours)) / 3600,
                  "share": 1 - sum(h["share"] for h in hours)})
    clone = [{"n": c.get("n"), "diff": c.get("diff"), "se": c.get("se"), "holds": bool(c.get("holds"))}
             for c in (json.load(open(os.path.join(q, "plan", "clone.json"))).get("rounds") or []) if c.get("diff") is not None]
    reads = json.load(open(os.path.join(q, "plan", "bridge.json"))).get("reads") or []
    isles = []
    for isl in ("boburner", "calber", "whitewolf"):
        xs = [r for r in reads if isl in r.get("label", "") and r.get("diff") is not None]
        if xs:
            isles.append({"island": isl, "reads": [{"label": r["label"].split("-")[0], "diff": r["diff"], "se": r.get("se"), "holds": bool(r.get("holds"))} for r in xs],
                          "mean": statistics.mean(r["diff"] for r in xs), "held": sum(bool(r.get("holds")) for r in xs)})
    st = json.load(open(os.path.join(q, "plan", "state.json")))
    return {"since": SINCE, "hours": hours, "clone": clone, "isles": isles, "tuning": json.load(open(os.path.join(q, "tuning.json"))),
            "plan": {k: v for k, v in json.load(open(os.path.join(q, "plan.json"))).items() if k in ("rotation", "weights")},
            "proof": (st.get("proof") or {}).get("last"), "orphans": st.get("orphans") or [], "line": bool(st.get("local_line"))}


def fig_hours(F):
    H = F["hours"]
    W, rowh, x0, x1 = 960, 30, 230, 860
    sx = lambda v: x0 + v / 0.45 * (x1 - x0)
    b = ""
    for v in (0, 0.1, 0.2, 0.3, 0.4):
        b += fw.grid(sx(v), 14, sx(v), 20 + rowh * len(H)) + og.text(sx(v), 36 + rowh * len(H), "%d%%" % (v * 100), "dim num", "middle")
    for i, h in enumerate(H):
        y = 20 + i * rowh
        b += og.text(x0 - 10, y + 19, h["kind"], "", "end")
        cls = "bar3" if h["kind"] == "the transform rotation" else "bar2"
        b += og.titled('<rect x="%d" y="%d" width="%.1f" height="%d" rx="3" class="%s"/>' % (x0, y + 6, max(1.0, sx(h["share"]) - x0), rowh - 12, cls),
                       "%s: %d jobs, %.1f hours, %.1f%% of the CPU machines' job-hours" % (h["kind"], h["jobs"], h["hours"], 100 * h["share"]))
        b += og.text(sx(h["share"]) + 6, y + 19, "%.1f%%  %s jobs" % (100 * h["share"], "{:,}".format(h["jobs"])), "num")
    b += og.text((x0 + x1) / 2, 54 + rowh * len(H), "share of the CPU machines' job-hours, 10 to 13 November", "", "middle")
    return og.STYLE + og.svg(W, 66 + rowh * len(H), b, "Fig. 1: where the CPU machines' hours went, by the kind of job")


def fig_clone(F):
    C = F["clone"]
    W, H, x0, x1, y0, y1 = 960, 330, 80, 900, 270, 30
    lo, hi = -12.0, 8.0
    sy = lambda v: y0 - (v - lo) / (hi - lo) * (y0 - y1)
    sx = lambda i: x0 + (i + 0.5) * (x1 - x0) / len(C)
    b = fw.yaxis(x0, x1, sy, lo, hi, 4.0)
    for i, c in enumerate(C):
        b += fw.grid(sx(i), sy(c["diff"] - 2 * c["se"]), sx(i), sy(c["diff"] + 2 * c["se"]), "l1")
        b += og.titled('<circle cx="%.1f" cy="%.1f" r="5" class="f1"/>' % (sx(i), sy(c["diff"])), "clone %d: %+.2f ± %.2f a seat over the shipped Scholar; shipping wants more than two errors" % (c["n"], c["diff"], c["se"]))
        b += og.text(sx(i), y0 + 16, str(c["n"]), "dim num", "middle")
    b += og.text((x0 + x1) / 2, y0 + 36, "clone round", "", "middle")
    b += fw.ylabel(20, y0, y1, "the clone less the Scholar, a seat (± 2 se)")
    return og.svg(W, H, b, "Fig. 2: every clone round, the clone less the Scholar it would replace")


def fig_isles(F):
    I = F["isles"]
    W, H, x0, x1, y0, y1 = 960, 320, 80, 900, 260, 30
    lo, hi = -10.0, 4.0
    sy = lambda v: y0 - (v - lo) / (hi - lo) * (y0 - y1)
    b = fw.yaxis(x0, x1, sy, lo, hi, 2.0)
    n = sum(len(i["reads"]) for i in I) + len(I)
    k = 0
    for ii, isl in enumerate(I):
        cls = ("f2", "f1", "f3")[ii % 3]
        start = k
        for r in isl["reads"]:
            x = x0 + (k + 1) * (x1 - x0) / (n + 1)
            el = '<circle cx="%.1f" cy="%.1f" r="5" class="%s"/>' % (x, sy(r["diff"]), cls)
            if r["holds"]:
                el = el.replace('r="5"', 'r="8"')
            b += og.titled(el, "%s of %s: %+.2f ± %.2f a seat as the Gladiator over the shipped one%s" % (r["label"], isl["island"], r["diff"], r["se"] or 0, "; shipped" if r["holds"] else ""))
            k += 1
        xm = x0 + ((start + k + 1) / 2) * (x1 - x0) / (n + 1)
        b += og.text(xm, y0 + 18, "%s: %d reads, mean %+.2f, %d shipped" % (isl["island"], len(isl["reads"]), isl["mean"], isl["held"]), "", "middle")
        k += 1
    b += fw.ylabel(20, y0, y1, "over the shipped one, a seat")
    return og.svg(W, H, b, "Fig. 3: every milestone read in the game, by the island that made it")


def dia_rotation():
    f = ck.Flow(0, 0, "Diagram 2: the transform rotation")
    f.N("rot", 20, 20, 170, "fn", "rotate()", ["plan.json rotation:", "the transform lane"])
    f.N("run", 240, 20, 170, "data", "a patch run, rNNNN", ["jobs rNNNN-kNN: censuses", "of a transform's steps"])
    f.N("slot", 460, 20, 170, "data", "patches/k.bin", ["a transform of 2 steps", "in slot 1 to 7"])
    f.N("cand", 680, 20, 170, "fn", "auto_promote()", ["\"patch\" in the weights:", "not a transform, yet"])
    f.A("rot", "run").A("run", "slot").A("slot", "cand", "read")
    f.N("dead", 680, 130, 170, "out", "never promoted", ["the game has no file", "for a slot"])
    f.A("cand", "dead")
    f.N("cost", 240, 130, 170, "note", "9.7% of CPU hours", ["1,496 jobs in three days"])
    f.N("off", 20, 130, 170, "out", "rotation: false", ["plan.json; the lane", "asks nothing"])
    f.A("rot", "off", "13 Nov")
    return f.key().svg()


def dia_clone():
    f = ck.Flow(0, 0, "Diagram 3: a clone round")
    f.N("due", 20, 20, 170, "fn", "clone_jobs()", ["CLONE_EVERY_H 12, and", "a new line head"])
    f.N("rec", 240, 20, 150, "data", "record", ["120 games of the", "rules, ten CPU jobs"])
    f.N("train", 440, 20, 150, "fn", "train", ["behaviour cloning", "on calber's card"])
    f.N("judge", 640, 20, 170, "fn", "judge", ["48 seeds, one seat;", "past two errors?"])
    f.A("due", "rec").A("rec", "train").A("train", "judge")
    f.N("ship", 640, 130, 170, "out", "nets/scholar.bin", ["shipped: 0 of 15"])
    f.A("judge", "ship")
    f.N("off", 20, 130, 170, "out", "clone_every_h 0", ["no round is due"])
    f.A("due", "off", "13 Nov")
    return f.key().svg()


def dia_island():
    f = ck.Flow(0, 0, "Diagram 4: three islands and the bridge")
    f.N("bo", 20, 10, 190, "data", "boburner's island", ["14 milestones read:", "mean -6.78, none shipped"])
    f.N("ca", 20, 90, 190, "data", "calber's island", ["8 read: mean +0.17,", "one shipped (M0030)"])
    f.N("wh", 20, 170, 190, "data", "whitewolf's island", ["no milestone read"])
    f.N("br", 290, 90, 190, "fn", "bridge_jobs()", ["the newest milestone in", "the game, as the Gladiator"])
    f.A("bo", "br").A("ca", "br").A("wh", "br")
    f.N("ship", 560, 90, 180, "out", "nets/gladiator.bin", ["past two errors: shipped"])
    f.A("br", "ship")
    f.N("off", 290, 10, 190, "out", "assign ... crucible off", ["boburner-cuda takes no", "crucible; its card rests"])
    f.A("bo", "off", "13 Nov")
    return f.key().svg()


def dia_settle_gens():
    f = ck.Flow(0, 0, "Diagram 5: a dial moved again")
    f.N("cand", 20, 20, 180, "data", "a candidate", ["moves beta; beta moved", "one generation ago"])
    f.N("noise", 250, 20, 190, "fn", "noise()  SETTLE_GENS 2", ["a dial moved in the last", "two generations wants z 3"])
    f.A("cand", "noise")
    f.N("wait", 500, 20, 170, "out", "waits", ["\"moves beta again\"", "twice in the week"])
    f.A("noise", "wait")
    f.N("now", 250, 130, 190, "fn", "what does its work now", ["held-out bar z 2.5;", "settling(): one block,", "checked, before the next"])
    f.N("off", 500, 130, 170, "out", "settle_gens 0", ["the rule asks nothing"])
    f.A("noise", "now").A("now", "off")
    return f.key().svg()


def dia_anchor():
    f = ck.Flow(0, 0, "Diagram 6: the anchor, and what replaced it")
    f.N("p", 20, 20, 170, "data", "a promotion", ["its values confirmed", "on every machine"])
    f.N("a", 240, 20, 190, "fn", "anchor_trial()  ANCHOR 3", ["the defaults three back,", "as a trial: 855 seeds"])
    f.A("p", "a")
    f.N("q", 480, 20, 190, "note", "is today better than", ["three generations ago?"])
    f.A("a", "q")
    f.N("y", 240, 130, 190, "fn", "rating()", ["today against three fixed", "mains, the same seeds daily"])
    f.N("o", 480, 130, 190, "fn", "orphan()", ["a line that fails its", "check comes off"])
    f.A("q", "y", dash=True).A("q", "o", dash=True)
    f.N("off", 730, 20, 150, "out", "anchor 0", ["no anchor reads"])
    f.A("q", "off")
    return f.key().svg()


def dia_hold():
    f = ck.Flow(0, 0, "Diagram 7: a hold")
    f.N("h", 20, 20, 190, "data", "hold.json", ["w_pos_fortify: 0.4", "1 November, game 4"])
    f.N("f", 270, 20, 200, "fn", "held_by_a_person()", ["a trial setting the dial", "to that value never", "promotes; its reads go on"])
    f.A("h", "f")
    f.N("now", 530, 20, 190, "note", "since then", ["game 9; the default has", "moved to 0.0249"])
    f.A("f", "now")
    f.N("off", 530, 130, 190, "out", "hold ... off", ["hold.json is empty"])
    f.A("now", "off")
    return f.key().svg()


def dia_trade():
    f = ck.Flow(0, 0, "Diagram 8: a trade weighed against what it buys")
    f.N("c", 20, 60, 190, "data", "held-out reads", ["gain a seat (held_mean)", "kills less deaths given up"])
    f.N("a", 270, 20, 220, "fn", "trade_allow(gain)", ["TRADE_TIMES 2.5 up to", "TRADE_GAIN 1.0; then", "2.5 x gain / 1.0"])
    f.N("g", 270, 130, 220, "fn", "gives_up()", ["the loss, in floors of 0.10,", "where past two errors"])
    f.A("c", "a").A("c", "g")
    f.N("r", 550, 70, 180, "fn", "trade_rule()", ["loss in floors against", "the allowance"])
    f.A("a", "r").A("g", "r")
    f.N("in", 790, 10, 190, "out", "within: it goes on", ["+3.3 gives up 0.47:", "4.7 floors of 8.25"])
    f.N("out", 790, 130, 190, "out", "past: refused, kept", ["+1.0 gives up 0.47:", "4.7 floors of 2.5"])
    f.A("r", "in").A("r", "out")
    return f.key().svg()


def dia_held():
    f = ck.Flow(0, 0, "Diagram 9: the held-out read, read on")
    f.N("p", 20, 20, 180, "data", "a trial past its stages", ["one held-out read:", "400 seeds, good to 0.40"])
    f.N("m", 250, 20, 200, "fn", "held_more_jobs()", ["pooled z from HELD_ON_Z", "1.0 up to the bar 2.5?"])
    f.A("p", "m")
    f.N("again", 510, 20, 190, "fn", "held_read(k + 1)", ["400 fresh seeds, pooled;", "up to HELD_READS 6"])
    f.A("m", "again", "yes")
    f.T(510, 100, "each read is pooled with those before it", "dim")
    f.N("pass", 250, 140, 200, "out", "past the bar: a candidate", ["at six reads, good to 0.17:", "+0.45 can pass"])
    f.N("drop", 510, 140, 190, "out", "under 1.0: not read on", ["as it was"])
    f.A("m", "pass").A("m", "drop")
    return f.key().svg()


def dia_stage():
    f = ck.Flow(0, 0, "Diagram 10: the stages, at today's swing")
    f.N("d", 20, 20, 190, "data", "a seed's swing", ["4.9 a seat on 29 October;", "8.1 on 13 November"])
    f.N("s", 270, 20, 210, "fn", "sequential()  SEQ", ["stages at 1, 1.5, 2.25, 3.4,", "5 and 7.6 times the first read"])
    f.A("d", "s")
    f.N("b", 540, 20, 200, "data", "plan.json weights.seeds", ["55 -> 150: (8.1 / 4.9)^2", "= 2.7 times the seeds"])
    f.A("b", "s")
    f.N("o", 270, 140, 210, "out", "stages of 150 to 1,140", ["the same z for the same", "gain as the design meant"])
    f.A("s", "o")
    f.N("c", 540, 140, 200, "note", "the cost", ["about 390 trials a day", "where there were 1,070"])
    return f.key().svg()


def dia_map():
    f = ck.Flow(0, 0, "Diagram 1: the gates of 13 November, kept, changed and set aside")
    rows = (("kept", "out", ("families hold their floors", "the gauntlet's guard", "the proof: z 3 over main", "MIN_GAIN 0.25 a seat")),
            ("changed", "fn", ("held-out bar: z 1.5 -> 2.5", "held-out reads: 1 -> up to 6", "first read: 55 -> 150 seeds", "trade limit: fixed -> by the gain")),
            ("set aside", "note", ("a dial moved again wants z 3", "the anchor reads", "the hold on w_pos_fortify 0.4", "the transform rotation", "the clone rounds", "boburner's island")),
            ("new", "data", ("the line settles: 9,600 seeds", "a block that fails comes off", "a refusal is kept", "one dial at a time, in rounds", "the fixed yardstick")))
    for i, (name, kind, items) in enumerate(rows):
        f.N("c%d" % i, 20 + i * 232, 20, 215, kind, name, items)
    return f.key().svg()


DIAGRAMS = {"map": dia_map, "rotation": dia_rotation, "clone": dia_clone, "island": dia_island, "settle-gens": dia_settle_gens, "anchor": dia_anchor,
            "hold": dia_hold, "trade": dia_trade, "held": dia_held, "stage": dia_stage}


def main(a):
    if a[0] == "--redraw":
        out = os.path.abspath(a[1])
        F = json.load(open(os.path.join(out, "data.json")))
    else:
        q, out = os.path.abspath(a[0]), os.path.abspath(a[1])
        os.makedirs(out, exist_ok=True)
        F = gather(q)
        json.dump(F, open(os.path.join(out, "data.json"), "w"), indent=1, default=str)
    for k, v in {"hours": fig_hours(F), "clone": fig_clone(F), "isles": fig_isles(F)}.items():
        open(os.path.join(out, "fig-%s.html" % k), "w").write(v + "\n")
    for k, fn in DIAGRAMS.items():
        open(os.path.join(out, "dia-%s.html" % k), "w").write(fn() + "\n")
    print("wrote %s: 3 figures, %d diagrams; %d clone rounds, %d islands" % (out, len(DIAGRAMS), len(F["clone"]), len(F["isles"])))


if __name__ == "__main__":
    main(sys.argv[1:])
