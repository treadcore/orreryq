#!/usr/bin/env python3
"""job-speed.py QDIR HOST BEFORE_FROM BEFORE_TO AFTER_FROM [AFTER_TO] -- how fast a machine does the
queue's own work before a change and after it, against the rest of the fleet over the same hours.

    python3 tools/job-speed.py ~/code/treadcore/build/queue/grove calber \\
        2026-11-06T07:27 2026-11-07T07:27 2026-11-07T08:36 2026-11-07T09:30

THE MEASURE is seconds a seed: every census and weights job records its seeds (SEEDS=) and its
seconds, and on 900-second games a seed is a fixed amount of play. Medians, because a job's seeds play
different maps. The job mix changes by the hour, and that moves every machine together, so a
machine's change is read against the fleet's median change in the same two windows: below 1.0, the
machine got faster than the fleet did. The same build (the census binary, c/SHA) is compared alone
too, because a new build can change the work.

Paul, 7 November, before changing calber's memory: "can you profile speeds". tools/ram-bench.sh is
the bench on a machine out of the queue; this is the day's work, back in it.
"""
import glob
import json
import os
import re
import statistics as st
import sys
from datetime import datetime


def jobs(qdir, start, end):
    rows = []
    for p in glob.glob(os.path.join(qdir, "done", "*.json")):
        try:
            j = json.load(open(p))
        except (OSError, ValueError):
            continue
        if j.get("kind") not in ("weights", "census") or not j.get("ended") or j.get("rc") not in (0, None):
            continue
        cmd = j.get("cmd", "")
        seeds, secs, build = re.search(r"\bSEEDS=(\d+)", cmd), re.search(r"\bSECS=(\d+)", cmd), re.search(r"/c/([0-9a-f]{7})", cmd)
        if not seeds or not secs or secs.group(1) != "900":
            continue
        ended = datetime.fromisoformat(j["ended"])
        if start <= ended < end:
            rows.append({"host": j["host"], "spd": j["seconds"] / int(seeds.group(1)), "build": build.group(1) if build else "?"})
    return rows


def main(argv):
    if len(argv) < 5:
        sys.exit(__doc__)
    qdir, host = argv[0], argv[1]
    t = [datetime.fromisoformat(x) for x in argv[2:6]] + ([datetime.now()] if len(argv) < 6 else [])
    before, after = jobs(qdir, t[0], t[1]), jobs(qdir, t[2], t[3])
    print("seconds a seed, 900 s games, medians; before %s to %s, after %s to %s" % tuple(x.strftime("%m-%d %H:%M") for x in t))
    print("%-14s %6s %8s %6s %8s %8s" % ("machine", "jobs", "before", "jobs", "after", "after/before"))
    ratio = {}
    for h in sorted({r["host"] for r in before} | {r["host"] for r in after}):
        b = [r["spd"] for r in before if r["host"] == h]
        a = [r["spd"] for r in after if r["host"] == h]
        if len(b) < 5 or len(a) < 5:
            continue
        ratio[h] = st.median(a) / st.median(b)
        print("%-14s %6d %8.2f %6d %8.2f %8.3f%s" % (h, len(b), st.median(b), len(a), st.median(a), ratio[h], "   <-" if h == host else ""))
    others = [v for k, v in ratio.items() if k != host]
    if host in ratio and others:
        print("%s against the fleet's median change (%.3f): %.3f" % (host, st.median(others), ratio[host] / st.median(others)))
    for build in sorted({r["build"] for r in after if r["host"] == host}):
        b = [r["spd"] for r in before if r["host"] == host and r["build"] == build]
        a = [r["spd"] for r in after if r["host"] == host and r["build"] == build]
        if b and a:
            print("%s on the same build %s: %.2f (%d jobs) then %.2f (%d jobs): %.3f" % (host, build, st.median(b), len(b), st.median(a), len(a), st.median(a) / st.median(b)))
    if host not in ratio:
        print("%s has fewer than 5 jobs in a window: wait for more" % host)


if __name__ == "__main__":
    main(sys.argv[1:])
