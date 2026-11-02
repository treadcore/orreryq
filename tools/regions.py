#!/usr/bin/env python3
"""regions.py QUEUE add A A0 A1 B B0 B1 [N] | cover DATASET PAIR | cover-all | clear [ID] | status

Paul, 1 November: "Selecting regions of operation with the terrain map". A region is a box over two
dials, in their real values, and a number of trials to read inside it: QUEUE/regions.json, which the
planner takes ahead of its own search and sends by the ordinary road. Nothing here promotes anything,
and a read in a region is judged like any other. Apart from fleet-queue.py, as fleet-tune.py is, so
that asking restarts no keeper.
"""
import json
import os
import sys
import time

N_DEFAULT, COVER_N, MOST = 6, 3, 40


def load(q):
    try:
        return json.load(open(os.path.join(q, "regions.json"))).get("regions", [])
    except (OSError, ValueError):
        return []


def save(q, regions):
    tmp = os.path.join(q, ".regions.tmp")
    with open(tmp, "w") as f:
        json.dump({"regions": regions}, f, indent=1)
    os.replace(tmp, os.path.join(q, "regions.json"))
    # So the terrains are worked out again at the next poll, and a person sees what they asked for.
    try:
        os.utime(os.path.join(q, "plan", "analysis.json"), (0, 0))
    except OSError:
        pass


def new_id(regions):
    used = [int(g["id"][1:]) for g in regions if g.get("id", "g0")[1:].isdigit()]
    return "g%d" % (max(used + [0]) + 1)


def add(q, regions, a, a0, a1, b, b0, b1, n):
    a0, a1, b0, b1 = float(a0), float(a1), float(b0), float(b1)
    if a0 <= 0 or b0 <= 0 or a1 < a0 or b1 < b0:
        raise SystemExit("a region is two ranges above zero: %s %s to %s, %s %s to %s" % (a, a0, a1, b, b0, b1))
    if not 1 <= n <= MOST:
        raise SystemExit("between 1 and %d trials" % MOST)
    g = {"id": new_id(regions), "a": a, "b": b, "a0": a0, "a1": a1, "b0": b0, "b1": b1, "n": n, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    regions.append(g)
    return g


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    q, what = argv[0], argv[1]
    regions = load(q)
    if what == "add":
        a, a0, a1, b, b0, b1 = argv[2:8]
        g = add(q, regions, a, a0, a1, b, b0, b1, int(argv[8]) if len(argv) > 8 else N_DEFAULT)
        save(q, regions)
        print("region %s: %d trials over %s and %s" % (g["id"], g["n"], a, b))
    elif what == "cover":
        # Three trials tight on each maximum nothing works on, in one pair of one dataset.
        doc = json.load(open(os.path.join(q, "plan", "terrain", argv[2] + ".json")))
        if not doc.get("can_send"):
            raise SystemExit("%s has no dials to read: its maxima are for the islands" % doc.get("label"))
        p = doc["pairs"][int(argv[3])]
        done = 0
        for k in p["peaks"]:
            if k["word"] == "bare":
                r = p["h"] / 2
                add(q, regions, p["a"], p["today"][0] * 2 ** (k["x"] - r), p["today"][0] * 2 ** (k["x"] + r),
                    p["b"], p["today"][1] * 2 ** (k["y"] - r), p["today"][1] * 2 ** (k["y"] + r), COVER_N)
                done += 1
        save(q, regions)
        print("%d maxima without work: %d trials asked" % (done, done * COVER_N))
    elif what == "cover-all":
        # Every dataset's bare maxima, each place once: the same ground on two maps is one trial's read.
        import glob
        seen, done = set(), 0
        for f in sorted(glob.glob(os.path.join(q, "plan", "terrain", "*.json"))):
            if f.endswith("parts-cache.json"):
                continue
            doc = json.load(open(f))
            if not doc.get("can_send"):
                continue
            for p in doc["pairs"]:
                for k in p["peaks"]:
                    place = (p["a"], p["b"], round(k["x"] / p["h"]), round(k["y"] / p["h"]))
                    if k["word"] != "bare" or place in seen or done * COVER_N >= MOST * 3:
                        continue
                    seen.add(place)
                    r = p["h"] / 2
                    add(q, regions, p["a"], p["today"][0] * 2 ** (k["x"] - r), p["today"][0] * 2 ** (k["x"] + r),
                        p["b"], p["today"][1] * 2 ** (k["y"] - r), p["today"][1] * 2 ** (k["y"] + r), COVER_N)
                    done += 1
        save(q, regions)
        print("%d places with nothing on them: %d trials asked" % (done, done * COVER_N))
    elif what == "clear":
        keep = [g for g in regions if len(argv) > 2 and g.get("id") != argv[2]]
        save(q, keep)
        print("%d regions left" % len(keep))
    elif what == "status":
        print(json.dumps(regions, indent=1))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
