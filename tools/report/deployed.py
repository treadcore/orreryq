#!/usr/bin/env python3
"""deployed.py QUEUE OUTDIR -- the figures, diagrams and numbers of *The First Morning* (docs/deployed-lab-report.md):
the design of 13 November watched as it went live. The watch itself is tools/deploy-watch.py, run here and
kept; beside it, every planner pass of the day (when, how long, how long since the one before), the seeds
the CPU machines finished each hour, and the day's commits in both repositories. `--redraw OUTDIR` draws
from data.json."""
import collections
import importlib.util
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import checked as ck  # noqa: E402
import forward as fw  # noqa: E402
import outgrowing as og  # noqa: E402

DAY = "2026-11-13"


def gather(q):
    s = importlib.util.spec_from_file_location("deploy_watch", os.path.join(os.path.dirname(HERE), "deploy-watch.py"))
    dw = importlib.util.module_from_spec(s)
    s.loader.exec_module(dw)
    watch = dw.watch(q)
    ids = {f.split("-", 1)[1][:-5]: f for f in os.listdir(os.path.join(q, "done"))}
    passes, hours, marks = [], collections.Counter(), []
    prev = None
    with open(os.path.join(q, "events.jsonl")) as f:
        for line in f:
            if line[7:17] != DAY:
                continue
            e = json.loads(line)
            if e["event"] == "planned":
                t = og.ep(e["t"])
                passes.append({"t": e["t"], "seconds": e.get("seconds"), "gap": t - prev if prev else None, "added": e.get("added")})
                prev = t
            elif e["event"] == "done" and e.get("kind") in ("weights", "census") and not e["host"].endswith("-cuda"):
                try:
                    m = re.search(r"\bSEEDS=(\d+)", json.load(open(os.path.join(q, "done", ids[e["job"]])))["cmd"])
                except (KeyError, OSError, ValueError):
                    m = None
                if m:
                    hours[e["t"][11:13]] += int(m.group(1))
            elif e["event"] in ("keeper restarting", "handed over", "lane left", "machine removed"):
                marks.append({"t": e["t"], "what": e["event"], "why": e.get("why") or e.get("host") or ""})
    now_h = time.strftime("%H")
    git = lambda d, *a: subprocess.run(["git", "-C", d] + list(a), capture_output=True, text=True).stdout
    commits = []
    for name, d in (("orrery", os.path.dirname(os.path.dirname(HERE))), ("treadcore", os.path.expanduser("~/code/treadcore"))):
        for l in git(d, "log", "origin/main", "--since=%s 00:00" % DAY, "--format=%h\t%ad\t%s", "--date=format:%H:%M").splitlines():
            h, at, subj = l.split("\t", 2)
            commits.append({"repo": name, "sha": h, "at": at, "subject": subj[:110]})
    commits.sort(key=lambda c: c["at"])
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "watch": watch, "passes": passes, "seeds_hour": [[h, hours[h]] for h in sorted(hours) if h < now_h],
            "marks": marks, "commits": commits, "manifest": json.load(open(os.path.join(os.path.dirname(HERE), "plans", "deployed.json")))}


def fig_passes(F):
    """Fig. 1: every planner pass of the day: when, and how long since the pass before."""
    P = [p for p in F["passes"] if p["gap"] is not None and p["t"][11:13] >= "06"]
    W, H, x0, x1, y0, y1 = 960, 360, 80, 900, 290, 30
    t0, t1 = og.ep(P[0]["t"]), og.ep(P[-1]["t"])
    sx = lambda t: x0 + (t - t0) / (t1 - t0) * (x1 - x0)
    hi = 420.0
    sy = lambda v: y0 - min(v, hi) / hi * (y0 - y1)
    b = ""
    for v in (0, 60, 120, 180, 240, 300, 360, 420):
        b += fw.grid(x0, sy(v), x1, sy(v), "axis" if v == 0 else "grid") + og.text(x0 - 8, sy(v) + 4, "%d s" % v, "dim num", "end")
    h = int(P[0]["t"][11:13]) + 1
    while True:
        t = og.ep("%sT%02d:00:00" % (DAY, h))
        if t > t1:
            break
        b += fw.grid(sx(t), y0, sx(t), y0 + 5, "axis") + og.text(sx(t), y0 + 18, "%02d:00" % h, "dim num", "middle")
        h += 1
    for label, at, y in (("07:39 the keeper takes the new code", "07:39:52", 44), ("09:26 the line comes off", "09:26:31", 44), ("09:27 it is put back; 09:33 off again", "09:27:43", 62)):
        x = sx(og.ep("%sT%s" % (DAY, at)))
        b += fw.grid(x, y1, x, y0, "thr") + og.text(x - 6, y, label, "dim", "end")
    for p in P:
        big = p["gap"] > 180
        el = '<circle cx="%.1f" cy="%.1f" r="%d" class="%s"/>' % (sx(og.ep(p["t"])), sy(p["gap"]), 5 if big else 3, "f2" if big else "f1")
        b += og.titled(el, "%s: %.0f s since the pass before; the pass took %.0f s and added %s job(s)" % (p["t"][11:19], p["gap"], p["seconds"] or 0, p["added"]))
    b += fw.ylabel(20, y0, y1, "seconds since the pass before")
    b += '<circle cx="96" cy="%d" r="3" class="f1"/>' % (H - 14) + og.text(108, H - 10, "a planner pass")
    b += '<circle cx="300" cy="%d" r="5" class="f2"/>' % (H - 14) + og.text(312, H - 10, "more than three minutes after the one before")
    return og.STYLE + og.svg(W, H, b, "Fig. 1: every planner pass of 13 November from 06:00, by the wait since the pass before")


def fig_seeds(F):
    """Fig. 2: seeds the CPU machines finished each hour of the day."""
    S = F["seeds_hour"]
    W, H, x0, x1, y0, y1 = 960, 320, 80, 900, 250, 30
    hi = max(v for _, v in S) * 1.15
    sy = lambda v: y0 - v / hi * (y0 - y1)
    b = ""
    for v in range(0, int(hi), 2000):
        b += fw.grid(x0, sy(v), x1, sy(v), "axis" if v == 0 else "grid") + og.text(x0 - 8, sy(v) + 4, "{:,}".format(v), "dim num", "end")
    gw = (x1 - x0) / len(S)
    for i, (h, v) in enumerate(S):
        x = x0 + i * gw + 4
        new = h >= "08"
        b += og.titled('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" class="%s"/>' % (x, sy(v), gw - 8, max(1.0, y0 - sy(v)), "bar3" if new else "bar2"),
                       "%s:00 to %s:59: %s seeds finished on the CPU machines" % (h, h, "{:,}".format(v)))
        b += og.text(x + (gw - 8) / 2, y0 + 16, h, "dim num", "middle")
        b += og.text(x + (gw - 8) / 2, sy(v) - 5, "%.1fk" % (v / 1000), "num", "middle")
    b += og.text((x0 + x1) / 2, y0 + 36, "hour of 13 November", "", "middle")
    b += fw.ylabel(20, y0, y1, "census seeds finished")
    b += '<rect x="90" y="%d" width="14" height="12" rx="2" class="bar2"/>' % (H - 22) + og.text(110, H - 12, "before the new design")
    b += '<rect x="330" y="%d" width="14" height="12" rx="2" class="bar3"/>' % (H - 22) + og.text(350, H - 12, "after 07:39: a second lane, larger reads, the line checked twice")
    return og.svg(W, H, b, "Fig. 2: census seeds finished each hour of 13 November")


def dia_deploy():
    f = ck.Flow(0, 0, "Diagram 1: how a change reaches the running fleet")
    f.N("c", 20, 20, 180, "data", "a commit, pushed", ["orrery main; checks", "run before it"])
    f.N("k", 250, 10, 200, "fn", "the keeper", ["fleet-queue.py changed on", "disk: hands its jobs over", "and starts again, same pid"])
    f.N("p", 250, 120, 200, "fn", "the planner", ["treadcore.py is a new", "process each pass: live", "at the next, a minute on"])
    f.N("v", 250, 220, 200, "data", "a value", ["tuning.json, plan.json,", "config.json: read each pass"])
    f.A("c", "k").A("c", "p")
    f.N("f", 510, 110, 190, "out", "the fleet", ["11 CPU and 2 GPU lanes", "take what the plan asks"])
    f.A("k", "f").A("p", "f").A("v", "p")
    f.N("g", 510, 220, 190, "data", "treadcore main", ["a game commit: every", "machine builds it first"])
    f.A("g", "f")
    f.N("w", 760, 110, 180, "fn", "deploy-watch.py", ["reads what happened,", "a line a mechanism"])
    f.A("f", "w", "records")
    return f.key().svg()


def dia_incident():
    f = ck.Flow(0, 0, "Diagram 2: the line that came back")
    f.N("a", 20, 20, 170, "fn", "09:26 orphan()", ["ten runs marked", "orphaned; line off"])
    f.N("b", 240, 20, 190, "data", "run states", ["status: orphaned,", "a word the run loop", "did not know"])
    f.A("a", "b")
    f.N("c", 480, 20, 190, "fn", "09:27 promote_run()", ["not prepared, approved,", "self-modified or rejected:", "so, work to do"])
    f.A("b", "c")
    f.N("d", 720, 20, 190, "out", "the line again", ["ten promotions back in", "62 s, on the new main"])
    f.A("c", "d")
    f.N("e", 20, 150, 170, "fn", "the fix, 79aea74", ["orphaned ends a run,", "in both places"])
    f.N("g", 240, 150, 190, "fn", "the verb orphan", ["the same promotions, the", "read that took them off"])
    f.N("h", 480, 150, 190, "out", "09:33 off again", ["still off two passes", "and an hour later"])
    f.A("e", "g").A("g", "h")
    f.N("i", 720, 150, 190, "note", "the cost", ["main built twice over;", "passes six minutes apart", "for a quarter of an hour"])
    return f.key().svg()


def dia_watch():
    f = ck.Flow(0, 0, "Diagram 3: what the watch reads, and what each level means")
    f.N("s", 20, 20, 190, "data", "plan/state.json", ["local_line, orphans, proof,", "far, held_more, refused,", "rating"])
    f.N("e", 20, 120, 190, "data", "events.jsonl", ["planned, failed, done,", "planner failed"])
    f.N("r", 20, 210, 190, "data", "runs, flags, queue", ["run states; trade flags;", "the newest trials' seeds"])
    f.N("w", 280, 110, 190, "fn", "watch()", ["twelve checks, each one", "mechanism of the design"])
    f.A("s", "w").A("e", "w").A("r", "w")
    f.N("ok", 540, 20, 240, "out", "ok", ["seen doing what it was built for"])
    f.N("look", 540, 110, 240, "out", "LOOK", ["not yet seen, or a person's to judge:", "a trade let through, a slow pass"])
    f.N("bad", 540, 210, 240, "out", "BAD", ["doing what it must not: an orphan", "back on the line, a pass failed,", "something set aside running again"])
    f.A("w", "ok").A("w", "look").A("w", "bad")
    return f.key().svg()


DIAGRAMS = {"deploy": dia_deploy, "incident": dia_incident, "watch": dia_watch}


def main(a):
    if a[0] == "--redraw":
        out = os.path.abspath(a[1])
        F = json.load(open(os.path.join(out, "data.json")))
    else:
        q, out = os.path.abspath(a[0]), os.path.abspath(a[1])
        os.makedirs(out, exist_ok=True)
        F = gather(q)
        json.dump(F, open(os.path.join(out, "data.json"), "w"), indent=1, default=str)
    for k, v in {"passes": fig_passes(F), "seeds": fig_seeds(F)}.items():
        open(os.path.join(out, "fig-%s.html" % k), "w").write(v + "\n")
    for k, fn in DIAGRAMS.items():
        open(os.path.join(out, "dia-%s.html" % k), "w").write(fn() + "\n")
    print("wrote %s: 2 figures, 3 diagrams; %d passes, %d commits; the watch reads %s" % (out, len(F["passes"]), len(F["commits"]), F["watch"]["worst"]))


if __name__ == "__main__":
    main(sys.argv[1:])
