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

LINE = re.compile(r"^(\S[\S ]*?)\s+([+-]?\d+\.\d+) \+/- (\d+\.\d+) over\s+(\d+) seeds")


def main(a):
    q = a[0]
    rows = []
    for p in glob.glob(os.path.join(q, "results", "w*", "fleet", "*", "out", "*", "*", "pooled.txt")):
        d = {}
        for line in open(p):
            m = LINE.match(line.strip())
            if m:
                d[m.group(1).strip()] = (float(m.group(2)), float(m.group(3)), int(m.group(4)))
        if "every map" in d and len(d) > 3:
            rows.append(d)
    maps = sorted({k for r in rows for k in r if k != "every map"})
    out = []
    for mp in maps:
        xs, ys, noise = [], [], []
        for r in rows:
            if mp not in r:
                continue
            mean, se, n = r["every map"]
            mm, ms, mn = r[mp]
            if n - mn < 4:
                continue
            rest = (mean * n - mm * mn) / (n - mn)
            xs.append(mm)
            ys.append(rest)
            noise.append(ms * math.sqrt(mn))
        if len(xs) < 20:
            continue
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        vx, vy = sum((x - mx) ** 2 for x in xs), sum((y - my) ** 2 for y in ys)
        r = cov / math.sqrt(vx * vy) if vx > 0 and vy > 0 else 0.0
        sd = sorted(noise)[len(noise) // 2]
        out.append({"map": mp, "censuses": len(xs), "agreement": round(r, 3), "seed_sd": round(sd, 2), "telling": round(r / sd * 10, 3) if sd else 0})
    out.sort(key=lambda o: -o["telling"])
    for o in out:
        print("%-22s %5d censuses  agrees with the rest %+.3f  a seed's sd %6.2f  telling %.3f" % (o["map"], o["censuses"], o["agreement"], o["seed_sd"], o["telling"]))
    print("%d censuses read" % len(rows))
    if len(a) > 1:
        json.dump({"censuses": len(rows), "maps": out}, open(a[1], "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
