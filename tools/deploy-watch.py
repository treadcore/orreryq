#!/usr/bin/env python3
"""deploy-watch.py QUEUE [--since ISO] [--json] -- is the design of 13 November doing what it was built to do?

One line a mechanism, each "ok", "LOOK" (not wrong, not yet seen, or wants a person) or "BAD" (it is doing
what it must not), read from the queue's own records and nothing else: the planner's state, its plan
files, the events, the run states, the flags. It moves nothing. Written after the first line to come off
was put back within a minute by a fault the checks had not asked about (13 November, 09:27): a mechanism
proved in a check is not yet a mechanism seen working, and this is where the second is read.

    python3 tools/deploy-watch.py ~/code/treadcore/build/queue/grove
    python3 tools/deploy-watch.py QUEUE --json > plan/deploy-watch.json     for a page or a report

--since is when the design went live (default 2026-11-13T07:39:00, the keeper's handover to the first of it)."""
import collections
import glob
import json
import os
import re
import statistics
import subprocess
import sys
import time

SINCE = "2026-11-13T07:39:00"


def load(p, d=None):
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return d


def ep(s):
    return time.mktime(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))


def watch(q, since=SINCE):
    out = []
    say = lambda level, name, words, **more: out.append(dict({"level": level, "name": name, "words": words}, **more))
    st = load(os.path.join(q, "plan", "state.json"), {})
    now = time.time()
    events = []
    with open(os.path.join(q, "events.jsonl")) as f:
        for line in f:
            if line[7:26] < since:  # {"t": "2026-..." : the stamp begins at the eighth character
                continue
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
    # 1. the planner's passes: how long, how far apart, any failed
    plans = [e for e in events if e["event"] == "planned"]
    fails = [e for e in events if e["event"] == "planner failed"]
    recent = [e for e in plans if now - ep(e["t"]) < 1800]
    gaps = [ep(b["t"]) - ep(a["t"]) for a, b in zip(recent, recent[1:])]
    if fails:
        say("BAD", "planner", "%d pass(es) failed since %s; the last at %s" % (len(fails), since[11:16], fails[-1]["t"][11:16]))
    elif not recent:
        say("BAD", "planner", "no pass in the last half hour")
    else:
        worst = max(gaps or [0])
        # A pass is asked when the queue runs low, a chain's step comes back or a lane starves, and at the
        # latest each plan_s (300): with reads of 150 and 400 seeds the queue drains slowly and four or five
        # minutes between passes is the keeper not needing one. Past seven it is the keeper held.
        say("LOOK" if worst > 420 else "ok", "planner", "%d passes in the last half hour, a median %.0f s each, the longest wait between two %.0f s" % (
            len(recent), statistics.median(e["seconds"] for e in recent), worst), passes=len(recent), worst_gap=worst)
    # 2. jobs that failed
    failed = [e for e in events if e["event"] == "failed"]
    say("LOOK" if failed else "ok", "jobs", "%d job(s) failed since %s%s" % (len(failed), since[11:16], ": " + ", ".join(e["job"] for e in failed[-4:]) if failed else ""))
    # 3. the line: none, settling, or carried; and no orphan back on it
    line = st.get("local_line")
    orphans = st.get("orphans") or []
    off = {r for o in orphans for r in o.get("promotions", [])}
    back = sorted(off & set((line or {}).get("promotions", [])))
    statuses = {r: (load(os.path.join(q, "plan", "runs", r, "state.json"), {}) or {}).get("status") for r in off}
    undone = sorted(r for r, s in statuses.items() if s != "orphaned")
    if back or undone:
        say("BAD", "orphans", "orphaned and on the line again or no longer marked: %s" % ", ".join(back or undone))
    else:
        say("ok", "orphans", "%d line(s) came off, %d promotion(s) orphaned, none back%s" % (
            len(orphans), len(off), "; the last at %s, %+.2f +/- %.2f in %d seeds" % (orphans[-1]["at"][11:16], orphans[-1]["lead"], orphans[-1]["se"], orphans[-1]["seeds"]) if orphans else ""))
    last = (st.get("proof") or {}).get("last") or {}
    if not line:
        say("ok", "line", "no line: the fleet builds main, and the next generation will be the first to settle")
    else:
        seeds = last.get("seeds", 0) if last.get("head") == line["commit"][:7] else 0
        age = (now - ep(line["since"])) / 3600 if line.get("since") else 0
        say("LOOK" if age > 24 else "ok", "line", "%d generation(s) on the line %s for %.1f h; its proof has read %d seeds%s" % (
            len(line["promotions"]), line["commit"][:7], age, seeds, ", %+.2f +/- %.2f" % (last["d"], last["se"]) if seeds else ""))
    # 4. the first read's size, from the newest trials asked
    seeds = []
    for f in sorted(glob.glob(os.path.join(q, "queue", "*-w*.json")) + glob.glob(os.path.join(q, "running", "*", "*-w*.json")), key=os.path.getmtime)[-20:]:
        m = re.search(r"\bSEEDS=(\d+)", (load(f, {}) or {}).get("cmd", ""))
        if m:
            seeds.append(int(m.group(1)))
    want = ((load(os.path.join(q, "plan.json"), {}) or {}).get("weights") or {}).get("seeds")
    if seeds:
        say("ok" if all(s == want for s in seeds) else "LOOK", "first read", "the newest %d trials are asked at %s seeds (plan.json says %s)" % (len(seeds), "/".join(str(s) for s in sorted(set(seeds))), want))
    else:
        say("LOOK", "first read", "no new trial in the queue to read its size from")
    # 5. one dial at a time
    far = st.get("far") or {}
    say("ok" if far.get("round") else "LOOK", "one dial", "round %d: %d of %d trials still to ask" % ((far.get("round") or 0) + 1, len(far.get("todo") or []), far.get("total") or 0))
    # 6. the held-out read, read on
    more = st.get("held_more") or {}
    say("ok" if more else "LOOK", "held-out", "%d trial(s) read on past their first held-out read%s" % (len(more), ": " + ", ".join("%s to read %d" % kv for kv in sorted(more.items())[-4:]) if more else " (none has been promising and undecided yet)"))
    # 7. the trade rule
    went, refused = [], []
    for f in glob.glob(os.path.join(q, "flags", "*-trade.json")):
        if int(os.path.basename(f).split("-")[0]) / 1000 >= ep(since):
            t = (load(f, {}) or {}).get("text", "")
            (went if "goes on" in t or "goes to main" in t else refused).append(t)
    say("LOOK" if went else "ok", "trade", "%d trade(s) let through and %d refused since %s; %d refusal(s) kept%s" % (
        len(went), len(refused), since[11:16], len(st.get("refused") or {}), ": " + went[-1][:150] if went else ""))
    # 8. the yardstick
    rows = (load(os.path.join(q, "plan", "rating.json"), {}) or {}).get("rows") or []
    rnd = (st.get("rating") or {}).get("round")
    if rows:
        newest = rows[-1]["at"]
        day = [r for r in rows if r["at"] == newest]
        say("ok" if now - ep(newest) < 36 * 3600 else "LOOK", "yardstick", "%s, today's %s: %s" % (newest[:16].replace("T", " "), day[0]["today"], "; ".join("%+.2f +/- %.2f over main of %s" % (r["lead"], r["se"], r["label"]) for r in day)), rows=len(rows))
    elif rnd:
        jobs = [j for b in rnd["brains"] for j in b["jobs"]]
        done = len([j for j in jobs if glob.glob(os.path.join(q, "done", "*-%s.json" % j))])
        say("LOOK", "yardstick", "no day read yet: the first round, asked %s, has %d of %d reads back" % (rnd["at"][11:16], done, len(jobs)))
    else:
        say("LOOK", "yardstick", "no day read and no round asked")
    # 9. what was set aside stays aside
    runs = collections.Counter()
    for f in glob.glob(os.path.join(q, "runs", "r*.json")):
        if os.path.getmtime(f) >= ep(since) + 5400:  # an hour and a half after: the switches were thrown through the morning
            r = load(f, {}) or {}
            runs[(r.get("kind"), r.get("by"))] += 1
    again = {k: v for k, v in runs.items() if k[1] in ("rotation", "clone") or k[0] in ("patch",)}
    anchors = len(glob.glob(os.path.join(q, "flags", "*-anchor.json"))) and len([f for f in glob.glob(os.path.join(q, "flags", "*-anchor.json")) if int(os.path.basename(f).split("-")[0]) / 1000 >= ep(since) + 5400])
    say("BAD" if again or anchors else "ok", "set aside", "since %s: %s" % (time.strftime("%H:%M", time.localtime(ep(since) + 5400)),
        ", ".join("%d %s run(s) by %s" % (v, k[0], k[1]) for k, v in again.items()) + (" %d anchor read(s)" % anchors if anchors else "") if again or anchors else "no rotation run, no clone round, no anchor read"))
    # 10. the split, read
    titles = collections.Counter()
    for d in ("queue", "done"):
        for f in glob.glob(os.path.join(q, d, "*-w*.json")):
            if os.path.getmtime(f) >= ep(since):
                t = (load(f, {}) or {}).get("title", "")
                m = re.search(r"smooth_(turret|stance|supply|rung)", t)
                if m:
                    titles[(m.group(1), d)] += 1
    parts = sorted({k[0] for k in titles})
    say("ok" if len(parts) == 4 else "LOOK", "w_smooth's parts", ("asked: %s (%d read)" % (", ".join(parts), sum(v for k, v in titles.items() if k[1] == "done")) if parts else "no trial of a part asked yet: the A/B trials reach them in their turn"))
    # 12. the cards' ladder: what the game refused, the one to beat, which islands send no migrants
    for key in [k for k in st if k.startswith("crucible_ladder:")][-1:]:
        ms = st[key].get("milestones") or []
        ref = [m for m in ms if (m.get("game") or {}).get("refused")]
        stand = [m for m in ms if not (m.get("game") or {}).get("refused")]
        isles = collections.defaultdict(list)
        for m in ms:
            if m.get("game"):
                isles[m.get("island")].append(m["game"].get("refused"))
        quiet = sorted(i for i, v in isles.items() if len(v) >= 3 and all(v[-3:]))
        say("ok" if stand else "BAD", "ladder", "%d milestone(s), %d refused by the game; the one to beat is %s%s" % (
            len(ms), len(ref), stand[-1]["id"] if stand else "none", "; no migrants from %s" % ", ".join(quiet) if quiet else ""))
    # 13. floors moved by a small drop, since the design went live
    moved = []
    for f in glob.glob(os.path.join(q, "logs", "r*-promote.log")):
        if os.path.getmtime(f) >= ep(since):
            moved += re.findall(r"^(?:family|gauntlet) (\S+): .* its floor moves to ([\d.]+)$", open(f, errors="replace").read(), re.M)
    say("LOOK" if moved else "ok", "floors", "%d floor(s) moved down by a small drop since %s%s" % (len(moved), since[11:16], ": " + ", ".join("%s to %s" % m for m in moved[-4:]) if moved else ""))
    # 11. the fleet's pace: census jobs finished in the last hour
    last_h = len([e for e in events if e["event"] == "done" and e.get("kind") in ("weights", "census") and now - ep(e["t"]) < 3600])
    say("ok" if last_h else "BAD", "pace", "%d census jobs finished in the last hour (each is larger than before: a first read is %s seeds)" % (last_h, want))
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "since": since, "checks": out,
            "worst": "BAD" if any(c["level"] == "BAD" for c in out) else "LOOK" if any(c["level"] == "LOOK" for c in out) else "ok"}


def main(a):
    q = os.path.abspath(a[0])
    since = a[a.index("--since") + 1] if "--since" in a else SINCE
    doc = watch(q, since)
    if "--json" in a:
        print(json.dumps(doc, indent=1))
        return
    for c in doc["checks"]:
        print("%-4s %-16s %s" % (c["level"], c["name"], c["words"]))
    print("%s overall, read %s" % (doc["worst"], doc["at"][11:16]))


if __name__ == "__main__":
    main(sys.argv[1:])
