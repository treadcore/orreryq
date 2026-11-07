#!/usr/bin/env python3
"""seed_sense.py QUEUE [OUT.json] -- which maps of the census tell a candidate's verdict soonest.

Paul, 6 November: "is there a way to find a sensitivity analysis to its seed such that we can disqualify certain
changes quicker to focus and increase success rate of changes and perturbations." Every census of the line's
search plays fresh seeds (SEED0 is the job's number times 10,000), so no seed is played twice and a seed's own
telling power cannot be read from what is stored. Its maps are the same eleven every time, so a MAP's can: for
every census in QUEUE/results (pooled.txt: every map, and each map, as mean +/- se over n seeds), the correlation,
over candidates, between the map's mean and the mean of the other maps (leave one out), and the noise a seed of
it carries (se x sqrt(n)). A map that agrees with the rest and is quiet tells the verdict in fewer seeds; played
first, it lets a sequential census stop a loser sooner.
"""
import glob
import json
import math
import os
import re
import sys
import time

LINE = re.compile(r"^(\S[\S ]*?)\s+([+-]?\d+\.\d+) \+/- (\d+\.\d+) over\s+(\d+) seeds")


def read(q, since=0.0):
    """Every census's pooled rows: [{map: (mean, se, n)}], those written after `since` (a time) only if given."""
    rows = []
    for p in glob.glob(os.path.join(q, "results", "w*", "fleet", "*", "out", "*", "*", "pooled.txt")):
        if since and os.path.getmtime(p) <= since:
            continue
        d = {}
        for line in open(p):
            m = LINE.match(line.strip())
            if m:
                d[m.group(1).strip()] = (float(m.group(2)), float(m.group(3)), int(m.group(4)))
        if "every map" in d and len(d) > 3:
            rows.append(d)
    return rows


def maps_of(rows, least=20):
    """Each map: its agreement with the other maps (leave one out), a seed's spread, its telling, and its PASS RATE
    (Paul, 6 November: "keep a history and a passrate"): the share of censuses whose trial beat the defaults there."""
    out = []
    for mp in sorted({k for r in rows for k in r if k != "every map"}):
        xs, ys, noise, wins = [], [], [], 0
        for r in rows:
            if mp not in r:
                continue
            mean, se, n = r["every map"]
            mm, ms, mn = r[mp]
            wins += mm > 0
            if n - mn < 4:
                continue
            xs.append(mm)
            ys.append((mean * n - mm * mn) / (n - mn))
            noise.append(ms * math.sqrt(mn))
        if len(xs) < least:
            continue
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        vx, vy = sum((x - mx) ** 2 for x in xs), sum((y - my) ** 2 for y in ys)
        r = cov / math.sqrt(vx * vy) if vx > 0 and vy > 0 else 0.0
        sd = sorted(noise)[len(noise) // 2]
        out.append({"map": mp, "censuses": len(xs), "agreement": round(r, 3), "seed_sd": round(sd, 2),
                    "telling": round(r / sd * 10, 3) if sd else 0, "pass_rate": round(wins / max(1, len(xs)), 3)})
    out.sort(key=lambda o: -o["telling"])
    return out


def main(a):
    """seed_sense.py QUEUE [OUT.json] [--history FILE]: --history appends a line -- the time, every census so far
    and the censuses since the line before, each map's telling and pass rate, and the share of censuses that
    passed overall (the trial over the defaults on every map)."""
    q = a[0]
    hist = a[a.index("--history") + 1] if "--history" in a else None
    rest = [x for i, x in enumerate(a[1:], 1) if x != "--history" and (i == 0 or a[i - 1] != "--history")]
    rows = read(q)
    out = maps_of(rows)
    for o in out:
        print("%-22s %5d censuses  agrees with the rest %+.3f  a seed's sd %6.2f  telling %.3f  pass rate %.3f" % (
            o["map"], o["censuses"], o["agreement"], o["seed_sd"], o["telling"], o["pass_rate"]))
    print("%d censuses read" % len(rows))
    if rest:
        json.dump({"censuses": len(rows), "maps": out}, open(rest[0], "w"), indent=1)
    if hist:
        last = 0.0
        if os.path.exists(hist):
            lines = [l for l in open(hist) if l.strip()]
            if lines:
                last = json.loads(lines[-1]).get("t", 0.0)
        recent = read(q, last) if last else rows
        line = {"t": time.time(), "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "censuses": len(rows),
                "passed": round(sum(1 for r in rows if r["every map"][0] > 0) / max(1, len(rows)), 3), "maps": out,
                "since_last": {"censuses": len(recent), "passed": round(sum(1 for r in recent if r["every map"][0] > 0) / max(1, len(recent)), 3),
                               "maps": maps_of(recent, least=5)}}
        with open(hist, "a") as f:
            f.write(json.dumps(line) + "\n")
        print("history: %s (%d censuses since the line before)" % (hist, len(recent)))


if __name__ == "__main__":
    main(sys.argv[1:])
