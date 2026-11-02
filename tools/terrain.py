#!/usr/bin/env python3
"""terrain.py QUEUE -- a terrain for each dataset the fleet holds, with its local maxima, and whether
any work stands on each. plan/terrain/DATASET.json, and an index in analysis.py's document.

    every      each census of game now: points a seat over today's defaults, every map
    map-NAME   the same reads, on that map alone
    kd         the same reads, kills less deaths a seat, from the census logs
    nofwd      the same reads, the score less what going forward pays (w_pos_fortify's lesson)
    crucible   a champion net per point: two main directions of its weights, its ladder score
    hybrid     the same, for the hybrid islands

Paul, 1 November: "Selecting regions of operation with the terrain map can be visually confirmed that
data is working on all maximas." So a peak here carries one of three words:

    read       110 seeds or more stand within a kernel of it: their mean says if it holds
    reading    fewer, and a job queued or running there
    bare       nothing is working on it

A READ COUNTS ONLY WHERE IT MOVED ONE OF THE TWO DIALS. A trial of some third dial says nothing of
these two, and sits on them at whatever the day's defaults were: counted, it drew cliffs of nothing
and "covered" peaks that no one had looked at. A read's height is its gain plus how far its day's
defaults stood from today's, by a small fit of the dials that have moved. That fit is an estimate, as
is the whole surface: where few reads stand it shrinks to zero rather than invent a peak.
"""
import glob
import json
import math
import os
import random
import re
import statistics
import struct
import subprocess
import sys
import time

TC = os.path.expanduser(os.environ.get("TREADCORE", "~/code/treadcore"))
RS = "source/treadcore-brain/src/weights.rs"
N = 30
TAU = 0.5  # the fit's own: points of error a doubling of drift (tools/plans/line.json, memory_tau)
READ_SEEDS = 110
MAP_SEEDS = 8
PAIRS = 8


def git(*a):
    r = subprocess.run(["git", "-C", TC] + list(a), capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def weights_at(commit, cache={}):
    if commit not in cache:
        cache[commit] = {n: float(v) for n, v in re.findall(r'^\s*[A-Z][A-Za-z0-9]*\s+"([a-z_0-9]+)"\s+(-?[0-9.]+),', git("show", "%s:%s" % (commit, RS)), re.M)}
    return cache[commit]


def game_at(commit, cache={}):
    if commit not in cache:
        cache[commit] = git("show", commit + ":source/treadcore-sim/GAME_VERSION").strip()
    return cache[commit]


def parse(text):
    """A weights file's numbers, and whether it has a caps line."""
    out, caps = {}, False
    for l in text.splitlines():
        l = l.split("#")[0].strip()
        if re.match(r"^caps\s*=", l):
            caps = caps or "-" in l or "+" in l
            continue
        m = re.match(r"^([a-z_][a-z0-9_]*)\s*=\s*([-+0-9.eE]+)$", l)
        if m:
            out[m.group(1)] = float(m.group(2))
    return out, caps


def read(path):
    try:
        return open(path, errors="replace").read()
    except OSError:
        return None


def censuses(q):
    """Every census of dials the queue fetched: its reading, whole and by map. What it could not use,
    counted by why, so the screen can say so."""
    rows, why = [], {}

    def drop(k):
        why[k] = why.get(k, 0) + 1
    for d in glob.glob(os.path.join(q, "results", "*", "*", "*", "out", "*", "*", "")):
        jid = d.rstrip("/").split(os.sep)[-2]
        if not re.match(r"[weh]\d+$|r\d+-\d+$", jid):
            continue
        pooled, tw, bw, env = read(d + "pooled.txt"), read(d + "trial.weights"), read(d + "base.weights"), read(d + "run.env")
        if not pooled or tw is None or bw is None or not env:
            drop("not finished")
            continue
        m = re.search(r"^COMMIT='?(\w+)", env, re.M)
        whole = re.search(r"^every map\s+([-+][\d.]+) \+/- ([\d.]+) over\s+(\d+)", pooled, re.M)
        if not m or not whole or float(whole.group(2)) <= 0:
            drop("no reading")
            continue
        trial, tcaps = parse(tw)
        base, bcaps = parse(bw)
        if tcaps or bcaps:
            drop("a switch, not a dial")
            continue
        if not trial or {"patch", "model", "bot_style"} & set(trial):
            drop("a whole brain, not a dial")
            continue
        # A map's reading needs seeds of its own. A census of 27 seeds has two or three a map, and an
        # error from two seeds is a coin: one such read of europe, +15.50 +/- 0.25, made a mountain.
        got = re.findall(r"^(\S+)\s+([-+][\d.]+) \+/- ([\d.]+) over\s+(\d+)", pooled, re.M)
        count = sum(1 for g in got if g[0] != "every")
        maps = {n: (float(a), float(b)) for n, a, b, k in got if n != "every" and int(k) >= MAP_SEEDS and float(b) > 0}
        if count < 5:
            drop("one map")
            continue
        rows.append({"job": jid, "dir": d, "commit": m.group(1), "trial": trial, "base": base, "d": float(whole.group(1)),
                     "se": float(whole.group(2)), "seeds": int(whole.group(3)), "maps": maps})
    return rows, why


def solve(a, b):
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        if abs(m[c][c]) < 1e-12:
            continue
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                if f:
                    for k in range(c, n + 1):
                        m[r][k] -= f * m[c][k]
    return [m[i][n] / m[i][i] if abs(m[i][i]) > 1e-12 else 0.0 for i in range(n)]


def heights(rows, today, score):
    """{id(row): gain over today's defaults}, by how far its day's defaults stood from today's."""
    moved = {}
    for r in rows:
        for k, v in r["then"].items():
            if k in today and today[k] > 0 and v > 0 and v != today[k]:
                moved.setdefault(k, set()).add(v)
    names = sorted(moved)
    col = {w: i for i, w in enumerate(names)}
    k = 2 * len(names)
    A, B = [[0.0] * k for _ in range(k)], [0.0] * k
    for r in rows:
        got = score(r)
        if not got:
            continue
        f = {}
        for w, v in r["trial"].items():
            then = r["then"].get(w, 0)
            if w in col and v > 0 and then > 0:
                x, u = math.log2(v / today[w]), math.log2(then / today[w])
                f[2 * col[w]], f[2 * col[w] + 1] = x - u, x * x - u * u
        if f:
            iw = 1.0 / max(got[1], 0.05) ** 2
            for i, fi in f.items():
                B[i] += iw * fi * got[0]
                for j, fj in f.items():
                    A[i][j] += iw * fi * fj
    for i in range(k):
        A[i][i] += 1.0
    beta = solve(A, B) if k else []
    out = {}
    for r in rows:
        got = score(r)
        if not got:
            continue
        lift = 0.0
        for w, v in r["then"].items():
            if w in col and v > 0:
                x = math.log2(v / today[w])
                lift += beta[2 * col[w]] * x + beta[2 * col[w] + 1] * x * x
        out[id(r)] = got[0] + lift
    return out


def convolve(grid, sx, sy):
    """A Gaussian over a grid, one axis at a time: thirty squared cells for each of thousands of
    reads, sixteen datasets, six pairs, would be most of a minute of plain Python."""
    def kernel(s):
        r = max(1, int(3 * s))
        return [(i, math.exp(-i * i / (2 * s * s))) for i in range(-r, r + 1)]
    n = len(grid)
    kx, ky = kernel(sx), kernel(sy)
    a = [[0.0] * n for _ in range(n)]
    for y in range(n):
        for x in range(n):
            v = grid[y][x]
            if v:
                for i, k in kx:
                    if 0 <= x + i < n:
                        a[y][x + i] += v * k
    b = [[0.0] * n for _ in range(n)]
    for y in range(n):
        for x in range(n):
            v = a[y][x]
            if v:
                for i, k in ky:
                    if 0 <= y + i < n:
                        b[y + i][x] += v * k
    return b


def surface(pts, ax, ay, h):
    """pts: (x, y, height, weight). The kernel average, shrunk where little stands, and its support."""
    (ax0, ax1), (ay0, ay1) = ax, ay
    sw, swd = [[0.0] * N for _ in range(N)], [[0.0] * N for _ in range(N)]
    for x, y, d, w in pts:
        ix, iy = round((x - ax0) / (ax1 - ax0) * (N - 1)), round((y - ay0) / (ay1 - ay0) * (N - 1))
        if 0 <= ix < N and 0 <= iy < N:
            sw[iy][ix] += w
            swd[iy][ix] += w * d
    sx, sy = max(0.5, h / (ax1 - ax0) * (N - 1)), max(0.5, h / (ay1 - ay0) * (N - 1))
    s0, s1 = convolve(sw, sx, sy), convolve(swd, sx, sy)
    z = [[round(s1[j][i] / (s0[j][i] + 2.0), 3) for i in range(N)] for j in range(N)]
    return z, [[round(s0[j][i], 1) for i in range(N)] for j in range(N)]


def maxima(z, sup):
    """Ground higher than its neighbours, standing on reads, and rising from something: a shrunk
    surface is nearly level where little was read, and level ground has a peak at every ripple."""
    found = []
    seen = [z[j][i] for j in range(N) for i in range(N) if sup[j][i] >= 2.0]
    rise = max(0.02, 0.03 * (max(seen) - min(seen))) if seen else 0.05
    for iy in range(N):
        for ix in range(N):
            v = z[iy][ix]
            # The rim of a deep pit is a local maximum of nothing anyone would want.
            if seen and v < max(seen) - 0.5 * (max(seen) - min(seen)):
                continue
            if sup[iy][ix] < 2.0 or not all(v >= z[iy + dy][ix + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if 0 <= iy + dy < N and 0 <= ix + dx < N):
                continue
            # Falling away on both sides of some line through it. A ridge does; the shelf at a pit's
            # edge does not, being high beside the pit and level beside the rest. Off the map counts as
            # falling away: a hill at the end of what was read is still a hill.
            def falls(dx, dy):
                x, y = ix + dx, iy + dy
                return not (0 <= x < N and 0 <= y < N) or v - z[y][x] >= rise
            if any(falls(3 * dx, 3 * dy) and falls(-3 * dx, -3 * dy) for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1))):
                found.append((ix, iy, v))
    found.sort(key=lambda p: -p[2])
    kept = []
    for p in found:
        if all(max(abs(p[0] - q[0]), abs(p[1] - q[1])) > 2 for q in kept):
            kept.append(p)
    return kept[:6]


def judge(near, seeds, jobs):
    """The three words, and for a read peak what its reads say."""
    if seeds >= READ_SEEDS:
        iw = sum(1 / se ** 2 for _, se in near)
        mean = sum(d / se ** 2 for d, se in near) / iw
        err = 1 / math.sqrt(iw)
        says = "holds" if mean > 2 * err else "falls" if mean < -2 * err else "unsure"
        return "read", round(mean, 2), round(err, 2), says
    return ("reading" if jobs else "bare"), None, None, ""


def queued_trials(q):
    """(state, {dial: value}) of each dial census queued or running."""
    out = []
    for state, pat in (("queued", "queue/*.json"), ("running", "running/*/*.json")):
        for f in glob.glob(os.path.join(q, pat)):
            try:
                j = json.load(open(f))
            except (OSError, ValueError):
                continue
            m = re.search(r"echo (\S+) \| base64 -d", j.get("cmd", ""))
            if j.get("kind") != "weights" or not m or not re.match(r"[weh]\d+$", j.get("id", "")):
                continue
            try:
                import base64
                trial, caps = parse(base64.b64decode(m.group(1)).decode())
            except ValueError:
                continue
            if trial and not caps:
                out.append((state, trial))
    return out


def regions_of(q):
    try:
        return json.load(open(os.path.join(q, "regions.json"))).get("regions", [])
    except (OSError, ValueError):
        return []


def pair_doc(a, b, rows, tall, today, jobs, regions, se_of=None):
    """One pair's surface, its maxima and what works on them. rows that moved neither dial do not count."""
    se_of = se_of or (lambda r: r["se"])
    pts, marks = [], []
    for r in rows:
        if id(r) not in tall or not (a in r["trial"] or b in r["trial"]):
            continue
        va, vb = r["vals"].get(a, 0), r["vals"].get(b, 0)
        if va > 0 and vb > 0:
            x, y = math.log2(va / today[a]), math.log2(vb / today[b])
            se = se_of(r)
            pts.append((x, y, tall[id(r)], 1 / (se ** 2 + 0.25 + (TAU * r["drift"]) ** 2)))
            marks.append((x, y, tall[id(r)], math.hypot(se, TAU * r["drift"]), r["seeds"]))
    if len(pts) < 8:
        return None
    # Today's defaults are the one point known exactly: no gain over themselves.
    pts.append((0.0, 0.0, 0.0, 4.0))
    lo = lambda i: max(-2.5, min(min(p[i] for p in pts) - 0.1, -0.25))
    hi = lambda i: min(2.5, max(max(p[i] for p in pts) + 0.1, 0.25))
    ax, ay = (lo(0), hi(0)), (lo(1), hi(1))
    h = max(0.15, max(ax[1] - ax[0], ay[1] - ay[0]) / 10)
    z, sup = surface(pts, ax, ay, h)
    at = []
    for state, t in jobs:
        if a in t or b in t:
            va, vb = t.get(a, today[a]), t.get(b, today[b])
            if va > 0 and vb > 0:
                at.append((math.log2(va / today[a]), math.log2(vb / today[b]), state))
    peaks = []
    for ix, iy, v in maxima(z, sup):
        x, y = ax[0] + (ax[1] - ax[0]) * ix / (N - 1), ay[0] + (ay[1] - ay[0]) * iy / (N - 1)
        near = [(m[2], max(m[3], 0.05)) for m in marks if math.hypot(m[0] - x, m[1] - y) <= h]
        seeds = sum(m[4] for m in marks if math.hypot(m[0] - x, m[1] - y) <= h)
        working = sum(1 for j in at if math.hypot(j[0] - x, j[1] - y) <= h)
        # A rise with no read within a kernel of it is the far edge of someone else's hill.
        if not near:
            continue
        word, mean, err, says = judge(near, seeds, working)
        peaks.append({"ix": ix, "iy": iy, "z": v, "support": sup[iy][ix], "x": round(x, 3), "y": round(y, 3), "a": round(today[a] * 2 ** x, 4), "b": round(today[b] * 2 ** y, 4),
                      "word": word, "reads": len(near), "seeds": seeds, "jobs": working, "mean": mean, "err": err, "says": says})
    keep = sorted(marks, key=lambda m: m[3])[:1000]
    regs = [dict(g, x0=round(math.log2(g["a0"] / today[a]), 3), x1=round(math.log2(g["a1"] / today[a]), 3), y0=round(math.log2(g["b0"] / today[b]), 3), y1=round(math.log2(g["b1"] / today[b]), 3))
            for g in regions if g.get("a") == a and g.get("b") == b]
    return {"a": a, "b": b, "ax": [round(ax[0], 3), round(ax[1], 3)], "ay": [round(ay[0], 3), round(ay[1], 3)], "h": round(h, 3), "today": [today[a], today[b]],
            "reads": len(pts), "z": z, "support": sup, "peaks": peaks, "dots": [[round(m[0], 2), round(m[1], 2), round(m[2], 1)] for m in keep],
            "jobs": [[round(j[0], 2), round(j[1], 2), j[2]] for j in at], "regions": regs, "log": True}


def choose_dials(rows, today, q):
    """The dials the most reads moved, and those the fit now thinks most of: the first are where a map
    has something on it, and the second are the question (w_pos_fortify, read less than twenty others,
    was the find of the day)."""
    count = {}
    for r in rows:
        for k, v in r["trial"].items():
            if today.get(k, 0) > 0 and v > 0 and v != r["then"].get(k):
                count[k] = count.get(k, 0) + 1
    wanted = []
    gens = sorted(glob.glob(os.path.join(q, "plan", "gen*", "curves.tsv")), key=os.path.getmtime)
    if gens:
        try:
            lines = open(gens[-1]).read().splitlines()
            head = lines[0].split("\t")
            curves = [dict(zip(head, l.split("\t"))) for l in lines[1:]]
            curves = [c for c in curves if float(c["gain"]) > 0.05 and count.get(c["weight"], 0) >= 8]
            wanted = [c["weight"] for c in sorted(curves, key=lambda c: -float(c["gain"]))[:3]]
        except (OSError, ValueError, KeyError, IndexError):
            wanted = []
    read = [k for k, _ in sorted(count.items(), key=lambda kv: (-kv[1], kv[0])) if k not in wanted]
    top = wanted + read[:6 - len(wanted)]
    return [(top[i], top[j]) for i in range(len(top)) for j in range(i + 1, len(top))][:PAIRS]


def parts_of(q, rows):
    """{job: {kd, nofwd}: (d, se)}, from the census logs, kept: the logs of a census never change, and
    reading them all takes minutes. Only logs since the census named each reward can say."""
    os.makedirs(os.path.join(q, "plan", "terrain"), exist_ok=True)
    cache_file = os.path.join(q, "plan", "terrain", "parts-cache.json")
    try:
        cache = json.load(open(cache_file))
    except (OSError, ValueError):
        cache = {}
    t0 = time.time()
    for r in rows:
        if r["job"] in cache or time.time() - t0 > 240:
            continue
        cache[r["job"]] = census_parts(r["dir"])
    tmp = cache_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cache, f)
    os.replace(tmp, cache_file)
    return cache


def census_parts(d):
    """Trial team less the others, a seed at a time, as pool.sh does the score."""
    seeds = {}
    for f in glob.glob(d + "g-*.log"):
        seed, kept = None, {}
        for l in open(f, errors="replace"):
            m = re.match(r"seed (\S+) on (\S+): trial team (\d)", l)
            if m:
                seed = m.group(1)
                continue
            m = re.match(r"\s+rewards of team (\d)( \(trial\))?: (.*)", l)
            if m:
                kept = {k.strip(): float(v) for k, v in re.findall(r"([a-z ]+) (\d+)", m.group(3))}
                continue
            m = re.match(r"\s+team (\d)( \(trial\))?: score ([-\d.]+), (.*)", l)
            if m and seed:
                row = dict(kept, score=float(m.group(3)))
                kept = {}
                for k, v in re.findall(r"(kills|deaths) ([-\d.]+)", m.group(4)):
                    row[k] = float(v)
                seeds.setdefault(seed, {"t": [], "o": []})["t" if m.group(2) else "o"].append(row)
    if not seeds:
        return {}

    def of(fn):
        out = []
        for s in seeds.values():
            if s["t"] and s["o"]:
                out.append(statistics.mean(fn(x) for x in s["t"]) - statistics.mean(fn(x) for x in s["o"]))
        if len(out) < 8:
            return None
        return [round(statistics.mean(out), 3), round(statistics.stdev(out) / math.sqrt(len(out)), 3)]
    rows = [x for s in seeds.values() for x in s["t"]]
    return {"kd": of(lambda x: (x.get("kills", 0) - x.get("deaths", 0)) / 5.0) if any("kills" in x for x in rows) else None,
            # What going forward pays: docs/fortify-lab-report.md's reading, tools/report/fortify.py's formula.
            "nofwd": of(lambda x: x["score"] - (0.25 * x.get("advanced", 0) + x.get("towed", 0) + 3 * x.get("stages", 0)) / 5.0) if any("advanced" in x for x in rows) else None}


def write(q, name, doc):
    d = os.path.join(q, "plan", "terrain")
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, ".%s.tmp" % name)
    with open(tmp, "w") as f:
        json.dump(doc, f)
    os.replace(tmp, os.path.join(d, name + ".json"))


def summary(doc):
    words = [p["word"] for pair in doc["pairs"] for p in pair["peaks"]]
    return {"pairs": len(doc["pairs"]), "reads": max([p["reads"] for p in doc["pairs"]] or [0]), "peaks": len(words),
            "read": words.count("read"), "reading": words.count("reading"), "bare": words.count("bare")}


def dial_datasets(q):
    rows, why = censuses(q)
    state = {}
    try:
        state = json.load(open(os.path.join(q, "plan", "state.json")))
    except (OSError, ValueError):
        pass
    head = (state.get("local_line") or {}).get("commit") or "origin/main"
    today, game = weights_at(head), game_at(head)
    good = []
    for r in rows:
        then = weights_at(r["commit"])
        if not then:
            why["commit gone"] = why.get("commit gone", 0) + 1
            continue
        if game_at(r["commit"]) != game:
            why["another game"] = why.get("another game", 0) + 1
            continue
        r["then"] = dict(then, **r["base"])
        r["vals"] = dict(r["then"], **r["trial"])
        r["drift"] = sum(abs(math.log2(r["then"][k] / today[k])) if r["then"][k] > 0 and today[k] > 0 else 1.0
                         for k in r["then"] if k in today and r["then"][k] != today[k])
        good.append(r)
    pairs = choose_dials(good, today, q)
    jobs = queued_trials(q)
    regions = regions_of(q)
    parts = parts_of(q, good)
    names = sorted({m for r in good for m in r["maps"]})
    sets = [("every", "Every map", "reads", lambda r: (r["d"], r["se"]), "points a seat")]
    sets += [("map-" + m, m, "maps", (lambda m: lambda r: r["maps"].get(m))(m), "points a seat on " + m) for m in names]
    sets.append(("kd", "Kills less deaths", "parts", lambda r: parts.get(r["job"], {}).get("kd"), "kills less deaths a seat"))
    sets.append(("nofwd", "Less forward pay", "parts", lambda r: parts.get(r["job"], {}).get("nofwd"), "points a seat, less what going forward pays"))
    out = []
    for key, label, group, score, unit in sets:
        tall = heights(good, today, score)
        doc = {"id": key, "label": label, "unit": unit, "group": group, "can_send": True, "pairs": []}
        for a, b in pairs:
            p = pair_doc(a, b, good, tall, today, jobs, regions, lambda r: score(r)[1])
            if p:
                doc["pairs"].append(p)
        write(q, key, doc)
        out.append(dict(summary(doc), id=key, label=label, group=group))
    return out, {"used": len(good), "seen": len(rows) + sum(why.values()) - why.get("commit gone", 0) - why.get("another game", 0), "left_out": why}


def crucible_dataset(q, sub, key, label):
    """Champions as points: weights are thousands of numbers, so the map is their two main directions,
    from a sample of them. Height, the score it had on the ladder. A live island is the work on it."""
    root = os.path.join(q, sub)
    rows = []
    try:
        lines = open(os.path.join(root, "lineage.tsv"), errors="replace").read().splitlines()
    except OSError:
        return None
    head = lines[0].split("\t") if lines else []
    for l in lines[1:]:
        r = dict(zip(head, l.split("\t")))
        f = os.path.join(root, "champions", r.get("job", "") + ".bin")
        try:
            m = float(r.get("ladder_mean", ""))
        except ValueError:
            continue
        if os.path.exists(f):
            rows.append((f, m, r.get("island", "")))
    if len(rows) < 20:
        return None
    size = os.path.getsize(rows[0][0])
    rows = [x for x in rows if os.path.getsize(x[0]) == size]
    n = size // 4
    rnd = random.Random(7)
    picks = sorted(rnd.sample(range(n), min(400, n)))

    def vec(path):
        w = struct.unpack("<%df" % n, open(path, "rb").read())
        return [w[i] for i in picks]
    sample = [vec(x[0]) for x in (rnd.sample(rows, 250) if len(rows) > 250 else rows)]
    mean = [sum(c) / len(sample) for c in zip(*sample)]
    centred = [[a - b for a, b in zip(v, mean)] for v in sample]

    def direction(against):
        p = [rnd.gauss(0, 1) for _ in picks]
        for _ in range(25):
            scores = [sum(a * b for a, b in zip(v, p)) for v in centred]
            q2 = [sum(s * v[i] for s, v in zip(scores, centred)) for i in range(len(picks))]
            for g in against:
                dot = sum(a * b for a, b in zip(q2, g))
                q2 = [a - dot * b for a, b in zip(q2, g)]
            size_ = math.sqrt(sum(a * a for a in q2)) or 1.0
            p = [a / size_ for a in q2]
        return p
    d1 = direction([])
    d2 = direction([d1])

    def place(path):
        v = vec(path)
        c = [a - b for a, b in zip(v, mean)]
        return sum(a * b for a, b in zip(c, d1)), sum(a * b for a, b in zip(c, d2))
    # Most of a plain ladder is draws, so a mean margin is near zero and small: in hundredths, to be seen.
    pts = []
    for f, m, _ in rows:
        x, y = place(f)
        pts.append((x, y, m * 100, 1.0))
    xs, ys = sorted(p[0] for p in pts), sorted(p[1] for p in pts)
    pad = lambda v: (v[1] - v[0]) * 0.05 or 1.0
    ax = (xs[max(0, len(xs) // 50)] - pad((xs[0], xs[-1])), xs[-1 - len(xs) // 50] + pad((xs[0], xs[-1])))
    ay = (ys[max(0, len(ys) // 50)] - pad((ys[0], ys[-1])), ys[-1 - len(ys) // 50] + pad((ys[0], ys[-1])))
    # Narrow: the lineages are tracks a long way apart, and a wide kernel draws one hill of nothing between them.
    h = max(ax[1] - ax[0], ay[1] - ay[0]) / 28
    z, sup = surface(pts, ax, ay, h)
    islands = []
    for f in glob.glob(os.path.join(root, "latest", "*.bin")):
        if os.path.getsize(f) == size:
            x, y = place(f)
            islands.append((x, y, os.path.basename(f)[:-4]))
    peaks = []
    for ix, iy, v in maxima(z, sup):
        x, y = ax[0] + (ax[1] - ax[0]) * ix / (N - 1), ay[0] + (ay[1] - ay[0]) * iy / (N - 1)
        near = sum(1 for p in pts if math.hypot(p[0] - x, p[1] - y) <= h)
        if not near:
            continue
        # A bare hilltop is an island that moved on from it, and a wide one covers a whole lineage.
        on = [g[2] for g in islands if math.hypot(g[0] - x, g[1] - y) <= 2 * h]
        peaks.append({"ix": ix, "iy": iy, "z": v, "support": sup[iy][ix], "x": round(x, 3), "y": round(y, 3), "a": round(x, 2), "b": round(y, 2),
                      "word": "reading" if on else "bare", "reads": near, "seeds": 0, "jobs": len(on), "mean": None, "err": None, "says": ", ".join(on)})
    pair = {"a": "direction 1", "b": "direction 2", "ax": [round(ax[0], 3), round(ax[1], 3)], "ay": [round(ay[0], 3), round(ay[1], 3)], "h": round(h, 3), "today": [0, 0],
            "reads": len(pts), "z": z, "support": sup, "peaks": peaks, "dots": [[round(p[0], 2), round(p[1], 2), round(p[2], 1)] for p in pts[-600:]],
            "jobs": [[round(g[0], 2), round(g[1], 2), "running"] for g in islands], "regions": [], "log": False, "ring": [round(islands[0][0], 3), round(islands[0][1], 3)] if islands else None}
    doc = {"id": key, "label": label, "unit": "ladder margin, in hundredths", "group": "nets", "can_send": False, "pairs": [pair]}
    write(q, key, doc)
    return dict(summary(doc), id=key, label=label, group="nets")


def index(q):
    t0 = time.time()
    data, reads = dial_datasets(q)
    for sub, key, label in (("crucible", "crucible", "Crucible nets"), ("crucible-hybrid", "hybrid", "Hybrid nets")):
        try:
            got = crucible_dataset(q, sub, key, label)
        except (OSError, ValueError, struct.error) as e:
            print("terrain: %s: %s" % (key, e), file=sys.stderr)
            got = None
        if got:
            data.append(got)
    return {"dir": os.path.join(q, "plan", "terrain"), "datasets": data, "reads": reads, "seconds": round(time.time() - t0, 1)}


if __name__ == "__main__":
    print(json.dumps(index(os.path.abspath(sys.argv[1]))))
