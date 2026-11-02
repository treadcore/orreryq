#!/usr/bin/env python3
"""temperament.py QUEUE -- what tanks do at each wave's high against its low, from the census logs.

A census with waves on prints, for each seed and each of the three waves, what the trial team did in
each of eight bins of that wave's phase. Here each trial becomes a grid, waves by behaviours: the rate
in the wave's upper half less the rate in its lower half, seed by seed, with its error. On a sine or
square wave the first four bins are where the wave is above zero.

THE WAVES DRIVING NOTHING ARE THE CONTROL. With bio on and bio_amount 0 and no matrix, the games are the
same games as with no waves at all, so that grid is what chance looks like. Whatever its cells read, a
real trial must read more. And this says only that a wave reaches behaviour: only a census says it wins.
"""
import glob
import json
import math
import os
import re
import statistics
import sys

METRICS = [("fight", "In a fight", "% of seconds", lambda c, h: rate(c, "fight", "secs", h, 100)),
           ("press", "Pressing", "% of fights", lambda c, h: rate(c, "press", "fight", h, 100)),
           ("mass", "Massing", "% of fights", lambda c, h: rate(c, "mass", "fight", h, 100)),
           ("shells", "Shells", "a minute", lambda c, h: rate(c, "shells", "secs", h, 60)),
           ("kills", "Kills", "per 100 min", lambda c, h: rate(c, "kills", "secs", h, 6000)),
           ("deaths", "Deaths", "per 100 min", lambda c, h: rate(c, "deaths", "secs", h, 6000))]
WAVES = ["60 s", "73 s", "86 s"]
SHAPES = {1, 3}  # A saw or a triangle is not above zero in its first half.


def rate(cols, top, under, half, scale):
    """top per under, in the bins of this half; None where nothing was under it."""
    a, b = sum(cols[top][i] for i in half), sum(cols[under][i] for i in half)
    return scale * a / b if b else None


def label_of(trial):
    """What a trial is, for the grid's name, or None if the waves were not sine or square or it moved more."""
    if int(trial.get("bio", 0)) not in SHAPES:
        return None
    temper = {k: v for k, v in trial.items() if k.startswith("temper_") and v}
    other = set(trial) - {"bio", "bio_amount"} - set(temper)
    if other:
        return None
    if temper:
        return "matrix: " + ", ".join("%s %+g" % kv for kv in sorted(temper.items()))
    amount = trial.get("bio_amount")
    if amount == 0:
        return "the waves driving nothing"
    if amount is None:
        return "the mood as it stands"
    return "the mood at %g" % amount


def parse_weights(text):
    out = {}
    for l in text.splitlines():
        m = re.match(r"^([a-z_][a-z0-9_]*)\s*=\s*([-+0-9.eE]+)$", l.split("#")[0].strip())
        if m:
            out[m.group(1)] = float(m.group(2))
    return out


def plays(d):
    """Each seed's three waves' columns, from a census's logs."""
    for f in glob.glob(d + "g-*.log"):
        got = {}
        for l in open(f, errors="replace"):
            m = re.match(r"\s+bio folded wave (\d): (.*)", l)
            if not m:
                continue
            got[int(m.group(1))] = {c.split(" ")[0]: [int(x) for x in c.split(" ")[1].split(",")] for c in m.group(2).split("; ")}
            if len(got) == 3:
                yield got
                got = {}


def read(q):
    groups = {}
    for tf in glob.glob(os.path.join(q, "results", "*", "*", "*", "out", "*", "*", "trial.weights")):
        try:
            trial = parse_weights(open(tf).read())
        except OSError:
            continue
        if "bio" not in trial:
            continue
        label = label_of(trial)
        if not label:
            continue
        g = groups.setdefault(label, [])
        for p in plays(os.path.dirname(tf) + os.sep):
            g.append(p)
    out = []
    for label, ps in groups.items():
        if len(ps) < 8:
            continue
        cells, secs, fights = [], 0, 0
        for w in range(3):
            row = []
            for key, name, unit, fn in METRICS:
                ds = []
                for p in ps:
                    high, low = fn(p[w], range(0, 4)), fn(p[w], range(4, 8))
                    if high is not None and low is not None:
                        ds.append(high - low)
                if len(ds) >= 8:
                    row.append({"d": round(statistics.mean(ds), 3), "se": round(statistics.stdev(ds) / math.sqrt(len(ds)), 3), "n": len(ds)})
                else:
                    row.append({"d": 0, "se": 0, "n": len(ds)})
            cells.append(row)
        for p in ps:
            secs += sum(p[0]["secs"])
            fights += sum(p[0]["fight"])
        out.append({"label": label, "plays": len(ps), "fight_share": round(100 * fights / max(secs, 1), 2), "cells": cells})
    order = lambda g: (0 if "nothing" in g["label"] else 1 if "mood" in g["label"] else 2, g["label"])
    out.sort(key=order)
    return {"waves": WAVES, "metrics": [{"key": m[0], "name": m[1], "unit": m[2]} for m in METRICS], "groups": out}


if __name__ == "__main__":
    print(json.dumps(read(os.path.abspath(sys.argv[1])))[:1500])
