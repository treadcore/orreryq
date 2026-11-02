#!/usr/bin/env python3
"""analysis.py QUEUE -- what the Algorhythm page's analysis tabs draw, into
QUEUE/plan/analysis.json. Slow by the standard of a poll (a minute of plain Python), so
treadcore-view.py starts it in the background when the file is old and never waits for it.

    terrains   each dataset's surface and local maxima, and what works on them: tools/terrain.py
    spectrum   each champion's singular values over its generations: a net's spectrogram
    dials      each dial at each promotion, in doublings
    matrices   a net's layers: norms, ranks, sparsity, the end-to-end linear map
    senses     how hard the net listens to each input, laid out as the tank has them
    fleet      how many trials stand at each step of the road to main

EVERY SURFACE HERE IS AN ESTIMATE, AND SAYS HOW MUCH DATA STANDS UNDER EACH POINT. A trial
moves several dials at once and the fleet never sampled a grid, so a terrain is a kernel
average with the other dials left to average out: a map of where reads have been good, not
a measurement of a slice. Where few reads stand, it shrinks to zero rather than invent a peak.
"""
import glob
import json
import math
import os
import re
import struct
import subprocess
import sys
import time

TC = os.path.expanduser(os.environ.get("TREADCORE", "~/code/treadcore"))
QUEUE = ""  # set by main
RS = "source/treadcore-brain/src/weights.rs"
GROUPS = [("compass", 88), ("body", 12), ("nav", 6), ("contacts", 18), ("hints", 9), ("shells", 5), ("air", 5)]
HEADS = [("drive", 10), ("gun", 11), ("lead", 3), ("mortar", 11), ("drone", 5), ("squad", 4), ("signal", 3)]
CHANNELS = ["hostile tank", "allied tank", "hostile pillbox", "neutral pillbox", "our pillbox", "depot to take",
            "our depot", "shell coming", "ground", "cover", "call"]


def git(*a):
    r = subprocess.run(["git", "-C", TC] + list(a), capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def weights_at(commit, cache={}):
    if commit not in cache:
        cache[commit] = {n: float(v) for n, v in re.findall(r'^\s*[A-Z][A-Za-z0-9]*\s+"([a-z_0-9]+)"\s+(-?[0-9.]+),', git("show", "%s:%s" % (commit, RS)), re.M)}
    return cache[commit]


# ---- terrain ----------------------------------------------------------------------------------
# tools/terrain.py. What was here read fleet.tsv, whose rows of game 4 carry no commit, and a ledger
# stopped on 28 October: 109 reads of 2,659, and heights set by the gains promotions had claimed.


def promotions():
    """[(commit, held gain)] oldest first, from the commits the fleet's promotions made."""
    out = []
    for line in reversed(git("log", "--grep=^promote ", "--format=%h %s").splitlines()):
        m = re.search(r"held out ([-+][\d.]+)(?: and ([-+][\d.]+))?", line)
        gain = (float(m.group(1)) + float(m.group(2) or m.group(1))) / 2 if m else 0.0
        out.append((line.split()[0], gain))
    return out


# ---- matrices ---------------------------------------------------------------------------------
def singular_values(rows):
    """Cyclic Jacobi on the smaller of A'A and AA': no numpy on this Mac (tools run with
    python3 -I). The smaller, since a 47 by 64 layer has 47 singular values; and to convergence,
    since five sweeps left the zeros of A'A at 0.08, and a layer of 47 outputs read rank 48."""
    if len(rows) < len(rows[0]):
        rows = [list(c) for c in zip(*rows)]
    n = len(rows[0])
    a = [[sum(r[i] * r[j] for r in rows) for j in range(n)] for i in range(n)]
    size = sum(a[i][i] for i in range(n)) or 1.0
    for _ in range(40):
        if sum(a[p][q] ** 2 for p in range(n - 1) for q in range(p + 1, n)) < (1e-13 * size) ** 2:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                if abs(a[p][q]) < 1e-9:
                    continue
                th = (a[q][q] - a[p][p]) / (2 * a[p][q])
                t = (1 if th >= 0 else -1) / (abs(th) + math.sqrt(th * th + 1))
                c = 1 / math.sqrt(t * t + 1)
                s = t * c
                for k in range(n):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p], a[k][q] = c * akp - s * akq, s * akp + c * akq
                for k in range(n):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k], a[q][k] = c * apk - s * aqk, s * apk + c * aqk
    return sorted((math.sqrt(max(0.0, a[i][i])) for i in range(n)), reverse=True)


def layer_stats(rows):
    sv = singular_values(rows)
    flat = [v for r in rows for v in r]
    fro = math.sqrt(sum(v * v for v in flat))
    mx = max(abs(v) for v in flat) or 1.0
    return {"rows": len(rows), "cols": len(rows[0]), "fro": round(fro, 2), "spectral": round(sv[0], 2),
            "stable_rank": round(fro * fro / (sv[0] * sv[0] or 1), 2),
            "effective_rank": sum(1 for s in sv if s > 0.01 * sv[0]),
            "sparsity": round(sum(1 for v in flat if abs(v) < 0.01 * mx) / len(flat), 3),
            "sv": [round(s, 3) for s in sv]}


def read_net(path):
    b = open(path, "rb").read()
    k = struct.unpack_from("<I", b, 8)[0]
    sizes = list(struct.unpack_from("<%dI" % k, b, 12))
    off, layers = 12 + 4 * k, []
    for a, o in zip(sizes, sizes[1:]):
        w = struct.unpack_from("<%df" % (a * o), b, off)
        off += 4 * a * o + 4 * o
        layers.append([list(w[r * a:(r + 1) * a]) for r in range(o)])
    return sizes, layers


def matmul(a, b):
    cols = list(zip(*b))
    return [[sum(x * y for x, y in zip(r, c)) for c in cols] for r in a]


def net_analysis(path):
    sizes, layers = read_net(path)
    end = matmul(layers[2], matmul(layers[1], layers[0]))
    g, at = [], 0
    for name, n in GROUPS:
        g.append((name, at, at + n))
        at += n
    h, at = [], 0
    for name, n in HEADS:
        h.append((name, at, at + n))
        at += n
    grid = [[round(sum(abs(end[r][c]) for r in range(r0, r1) for c in range(c0, c1)) / ((r1 - r0) * (c1 - c0)), 3)
             for _, c0, c1 in g] for _, r0, r1 in h] if len(end[0]) == 143 and len(end) == 47 else []
    listen = [round(math.sqrt(sum(r[c] ** 2 for r in layers[0])), 3) for c in range(sizes[0])]
    return {"name": os.path.basename(path), "sizes": sizes, "layers": [layer_stats(l) for l in layers],
            "end_grid": grid, "inputs": [x[0] for x in g], "outputs": [x[0] for x in h], "listen": listen}


# ---- growth ---------------------------------------------------------------------------------
def champion_spectrum(files, nin, nout, H=32, n=48):
    """The middle layer's singular values, a column a champion, oldest at the left."""
    if len(files) < 3:
        return None
    pick = [files[round(i * (len(files) - 1) / (min(n, len(files)) - 1))] for i in range(min(n, len(files)))]
    cols, norms, drift, first = [], [], [], None
    for f in pick:
        b = open(f, "rb").read()
        w = struct.unpack("<%df" % (len(b) // 4), b)
        start = nin * H + H
        rows = [list(w[start + r * H:start + (r + 1) * H]) for r in range(H)]
        cols.append([round(s, 3) for s in singular_values(rows)])
        norms.append(round(math.sqrt(sum(v * v for v in w)), 2))
        first = first or w
        drift.append(round(math.sqrt(sum((x - y) ** 2 for x, y in zip(w, first))), 2))
    return {"champions": len(files), "shown": len(pick), "columns": cols, "norm": norms, "drift": drift}


def by_time(d):
    return sorted(glob.glob(os.path.join(d, "*.bin")), key=os.path.getmtime)


def dial_history():
    commits = [c for c, _ in promotions()]
    if not commits:
        return None
    first = weights_at(commits[0] + "~1")
    steps = [weights_at(c) for c in commits]
    keys = [k for k in first if first[k] > 0 and any(s.get(k, first[k]) > 0 and abs(math.log2(s.get(k, first[k]) / first[k])) > 0.01 for s in steps)]
    keys.sort(key=lambda k: -max(abs(math.log2(s.get(k, first[k]) / first[k])) if s.get(k, first[k]) > 0 else 0 for s in steps))
    return {"commits": commits, "dials": keys[:36],
            "cells": [[round(math.log2(s.get(k, first[k]) / first[k]), 3) if s.get(k, first[k]) > 0 else 0 for s in steps] for k in keys[:36]]}


def number_limits():
    """RANGES at HEAD: the decrees, min = max, and how many numbers have a limit at all."""
    decrees, limited = [], 0
    for line in git("show", "HEAD:source/treadcore-brain/RANGES").splitlines():
        f = line.split("#")[0].split()
        if len(f) == 3:
            limited += 1
            if f[1] == f[2]:
                decrees.append("%s = %s" % (f[0], f[1]))
    return {"decrees": decrees, "limited": limited}


def fleet_counts(q):
    tools = os.path.dirname(os.path.abspath(__file__))
    import collections
    import importlib.util
    s = importlib.util.spec_from_file_location("tp", os.path.join(tools, "plans", "treadcore.py"))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    p = m.Plan(q)
    seq = p.sequential()
    c = collections.Counter(v["status"] for v in seq.values())
    ev = p.evidence()
    runs = [r for r in p.runs() if r["kind"] == "patch"]
    st = p.rstate(runs[-1]["id"]) if runs else {}
    cr = p.state.get("crucible", {})
    return {"reading": c.get("reading", 0), "read_on": c.get("read on", 0), "dropped": c.get("dropped", 0), "passed": c.get("passed", 0),
            "held_waiting": len(p.state.get("held_second", [])), "candidates": sum(1 for v in ev.values() if v.get("current")),
            "promotions": len(p.promotions()), "transform_step": st.get("k", 0), "transform_of": 30,
            "islands": len([v for v in cr.values() if isinstance(v, dict)]), "segments": sum(v.get("seg", 0) for v in cr.values() if isinstance(v, dict)),
            "milestones": len(p.state.get("crucible_ladder", {}).get("milestones", [])),
            "patches": len(glob.glob(os.path.join(q, "patches", "*.bin")))}


def main(q):
    global QUEUE
    QUEUE = q
    t0 = time.time()
    out = {"at": time.strftime("%H:%M"), "reads": 0, "dials": dial_history(), "channels": CHANNELS,
           "spectrum": {"plain": champion_spectrum(by_time(os.path.join(q, "crucible", "champions")), 32, 3),
                        "hybrid": champion_spectrum(by_time(os.path.join(q, "crucible-hybrid", "champions")), 35, 4)}}
    for name in ("bc2",):
        p = os.path.join(TC, "nets", name + ".bin")
        if os.path.exists(p):
            out["net"] = net_analysis(p)
    # Each dataset's terrain is a file of its own, read when it is chosen: this document is read every few seconds.
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import terrain as terrains
        out["terrains"] = terrains.index(q)
        out["reads"] = out["terrains"]["reads"]["used"]
    except Exception as e:
        out["terrains"] = {"error": str(e)[:300], "datasets": []}
    try:
        import temperament
        out["temper"] = temperament.read(q)
        out["temper"]["dials"] = {k: v for k, v in weights_at("orrery/accepted").items() if k.startswith("temper_") or k in ("bio", "bio_amount", "bio_period")}
    except Exception as e:
        out["temper"] = {"error": str(e)[:300], "groups": []}
    try:
        out["fleet"] = fleet_counts(q)
        out["limits"] = number_limits()
    except Exception as e:
        out["fleet"] = {"error": str(e)[:200]}
    out["seconds"] = round(time.time() - t0, 1)
    tmp = os.path.join(q, "plan", ".analysis.tmp")
    with open(tmp, "w") as f:
        json.dump(out, f)
    os.rename(tmp, os.path.join(q, "plan", "analysis.json"))
    print("analysis: %d reads, %d terrains, %.0f s" % (out["reads"], len(out["terrains"].get("datasets", [])), out["seconds"]))


if __name__ == "__main__":
    main(sys.argv[1])
