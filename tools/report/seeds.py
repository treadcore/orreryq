#!/usr/bin/env python3
"""seeds.py QUEUE OUTDIR [FROM] -- the numbers and figures of *Where the Seeds Went* (docs/seeds-lab-report.md):
every trial since wFROM (17000) with its reads pooled stage by stage, by what proposed it and by what its
first read said; the line's proof map by map; the bridge's reads as one read each. The numbers are the
queue's own. `--redraw OUTDIR` draws from data.json."""
import collections
import glob
import json
import math
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import forward as fw  # noqa: E402
import outgrowing as og  # noqa: E402

BUCKETS = ((-9, -1), (-1, -.5), (-.5, 0), (0, .25), (.25, .5), (.5, .75), (.75, 1), (1, 1.5), (1.5, 2), (2, 9))
KINDS = (("sample", "the fit's samples, three or four dials"), ("wide", "wide trials, a stalled search's"), ("ab", "a switch or a choice flipped"),
         ("far", "one dial alone, far"), ("best", "the fit's best"))


def gather(q, lo=17000):
    m, p = og.planner(q)
    title = dict(p.done_titles())
    on = {}
    for i, t in title.items():
        mm = re.match(r"read on (\d+) of (w\d+)", t)
        if mm:
            on[i] = (mm.group(2), int(mm.group(1)))
    reads = collections.defaultdict(list)
    for d in p.census_dirs():
        jid = d.rstrip("/").split(os.sep)[-2]
        if re.match(r"w\d+$", jid):
            reads[jid].append((1, d))
        elif jid in on:
            reads[on[jid][0]].append((on[jid][1], d))
    cand = set()
    for f in glob.glob(os.path.join(q, "flags", "*-candidate.json")):
        try:
            mm = re.match(r"(w\d+) passed both", json.load(open(f))["text"])
        except (ValueError, KeyError, OSError):
            mm = None
        if mm:
            cand.add(mm.group(1))
    rows = []
    for jid, ds in reads.items():
        ds = sorted(ds)
        if int(jid[1:]) < lo or ds[0][0] != 1:
            continue
        first, last = p.pool([ds[0][1]]), p.pool([d for _, d in ds])
        if not first or not last or first["every"][1] <= 0:
            continue
        t = title.get(jid) or ""
        k = re.match(r"([a-z]+)[-:]", t)
        rows.append({"job": jid, "kind": k.group(1) if k else "other", "n0": first["every"][2], "z0": first["every"][0] / first["every"][1],
                     "d0": first["every"][0], "seeds": last["every"][2], "reads": len(ds), "held": jid in p.state.get("held_read", {}), "cand": jid in cand})
    old = [r for r in rows if r["n0"] < 100]
    kinds = []
    for k, words in KINDS:
        z = [r["z0"] for r in rows if r["kind"] == k]
        if len(z) < 2:
            continue
        kinds.append({"kind": k, "words": words, "n": len(z), "seeds": sum(r["seeds"] for r in rows if r["kind"] == k), "mean": statistics.mean(z), "sd": statistics.pstdev(z),
                      "se_mean": 1 / math.sqrt(len(z)), "over2": sum(x > 2 for x in z), "under2": sum(x < -2 for x in z), "null2": 0.02275 * len(z),
                      "held": sum(r["held"] for r in rows if r["kind"] == k), "cand": sum(r["cand"] for r in rows if r["kind"] == k)})
    noise = [r["z0"] for r in rows if r["kind"] in ("sample", "wide")]
    hist = [sum(1 for x in noise if a <= x < a + 0.5) for a in [i / 2 for i in range(-8, 8)]]
    buckets = []
    for a, b in BUCKETS:
        r = [x for x in old if a <= x["z0"] < b]
        buckets.append({"lo": a, "hi": b, "n": len(r), "on": sum(x["reads"] > 1 for x in r), "after": sum(x["seeds"] - x["n0"] for x in r),
                        "held": sum(x["held"] for x in r), "cand": sum(x["cand"] for x in r)})
    pf = p.state.get("proof") or {}
    ds = [d for j in (pf.get("pooled") or {}).get("jobs") or [] for d in glob.glob(os.path.join(q, "results", j, p.home, "out", j, "*", ""))]
    pp = p.pool(ds) if ds else None
    maps = sorted(({"map": k, "d": -d, "se": se} for k, (d, se) in (pp or {}).get("maps", {}).items()), key=lambda x: -x["d"])
    br = p.state.get("bridge") or {}
    return {"from": lo, "trials": len(rows), "old": {"n": len(old), "seeds": sum(r["seeds"] for r in old), "first": sum(r["n0"] for r in old),
                                                     "held": sum(r["held"] for r in old), "cand": sum(r["cand"] for r in old)},
            "cand_first_z": sorted(round(r["z0"], 2) for r in old if r["cand"]), "kinds": kinds, "hist": hist, "noise_n": len(noise), "buckets": buckets,
            "proof": {"last": pf.get("last"), "maps": maps}, "shipped": br.get("shipped"),
            "bridge": [{k: r.get(k) for k in ("n", "label", "shipped", "seeds", "diff", "se", "kind", "credited", "read")} for r in br.get("reads") or []]}


def fig_maps(D):
    """Fig. 1: the proof, a map at a time."""
    M = D["proof"]["maps"]
    W, rowh = 960, 26
    x0, x1 = 190, 900
    lo, hi = -4, 12
    sx = lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)
    b = ""
    for v in range(lo, hi + 1, 2):
        b += fw.grid(sx(v), 14, sx(v), 22 + rowh * len(M), "axis" if v == 0 else "grid") + og.text(sx(v), 38 + rowh * len(M), "0" if v == 0 else "%+d" % v, "dim num", "middle")
    for i, m in enumerate(M):
        y = 20 + i * rowh
        b += og.text(x0 - 8, y + 16, m["map"], "", "end")
        a, c = sorted((sx(0), sx(m["d"])))
        el = '<rect x="%.1f" y="%d" width="%.1f" height="%d" rx="3" class="%s hit"/>' % (a, y + 5, max(1.0, c - a), rowh - 10, "bar2" if m["d"] < 0 else "f3")
        b += og.titled(el, "%s: the line reads %+.2f +/- %.2f a seat over main (%+.1f errors)" % (m["map"], m["d"], m["se"], m["d"] / m["se"]))
        b += '<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" class="axis"/>' % (sx(m["d"] - 2 * m["se"]), y + 13, sx(m["d"] + 2 * m["se"]), y + 13)
        b += og.text(sx(m["d"] + 2 * m["se"]) + 6 if m["d"] >= 0 else sx(m["d"] - 2 * m["se"]) - 6, y + 17, "%+.2f" % m["d"], "num", "start" if m["d"] >= 0 else "end")
    b += og.text((x0 + x1) / 2, 56 + rowh * len(M), "the line over main, a seat; the whisker is two errors either side", "", "middle")
    return og.svg(W, 66 + rowh * len(M), b, "Fig. 1: the proof of w_smooth 0.525, a map at a time")


def fig_noise(D):
    """Fig. 2: the first reads of the sample and wide trials, beside what no effect at all reads."""
    H, n = D["hist"], D["noise_n"]
    W, Ht = 960, 300
    x0, x1, y0, y1 = 70, 920, 24, 240
    cdf = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
    exp = [n * (cdf(a + 0.5) - cdf(a)) for a in [i / 2 for i in range(-8, 8)]]
    top = math.ceil(max(H + exp) / 100) * 100
    sy = lambda v: y1 - v / top * (y1 - y0)
    bw = (x1 - x0) / len(H)
    b = fw.yaxis(x0, x1, sy, 0, top, top / 5, "%d")
    for i, (h, e) in enumerate(zip(H, exp)):
        a = -4 + i / 2
        el = '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" class="f1 hit"/>' % (x0 + i * bw + 2, sy(h), bw - 4, y1 - sy(h))
        b += og.titled(el, "z %+.1f to %+.1f: %d trials read so; no effect at all gives %.0f" % (a, a + 0.5, h, e))
        b += '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" class="thr"/>' % (x0 + i * bw, sy(e), x0 + (i + 1) * bw, sy(e))
        if i % 2 == 0:
            b += og.text(x0 + i * bw, y1 + 18, "%+d" % a if a else "0", "dim num", "middle")
    b += og.text(x1, y1 + 18, "+4", "dim num", "middle")
    b += og.text((x0 + x1) / 2, y1 + 42, "the first read, in its own errors (z)", "", "middle") + fw.ylabel(22, y0, y1, "trials")
    b += '<rect x="%d" y="%d" width="14" height="10" rx="2" class="f1"/>' % (x1 - 330, y0) + og.text(x1 - 310, y0 + 10, "%s sample and wide trials" % format(n, ","))
    b += '<line x1="%d" y1="%d" x2="%d" y2="%d" class="thr"/>' % (x1 - 330, y0 + 24, x1 - 316, y0 + 24) + og.text(x1 - 310, y0 + 28, "the same number of trials that do nothing")
    return og.svg(W, Ht, b, "Fig. 2: the first reads of the sample and wide trials against no effect at all")


def fig_first(D):
    """Fig. 3: the seeds read after the first read, by what the first read said, and the candidates that came of them."""
    B = [x for x in D["buckets"] if x["lo"] >= 0]
    W, Ht = 960, 300
    x0, x1, y0, y1 = 80, 920, 30, 236
    top = math.ceil(max(x["after"] for x in B) / 10000) * 10000
    sy = lambda v: y1 - v / top * (y1 - y0)
    bw = (x1 - x0) / len(B)
    b = fw.yaxis(x0, x1, sy, 0, top, top / 5, "%d")
    for i, x in enumerate(B):
        el = '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" class="%s hit"/>' % (x0 + i * bw + 14, sy(x["after"]), bw - 28, y1 - sy(x["after"]), "bar2" if not x["cand"] else "f1")
        b += og.titled(el, "first read z %.2f to %s: %d trials, %d read on, %s seeds after the first read, %d reached the held-out reads, %d candidates" % (
            x["lo"], "%.2f" % x["hi"] if x["hi"] < 9 else "up", x["n"], x["on"], format(x["after"], ","), x["held"], x["cand"]))
        b += og.text(x0 + (i + .5) * bw, sy(x["after"]) - 6, "%d candidate%s" % (x["cand"], "" if x["cand"] == 1 else "s"), "num", "middle")
        b += og.text(x0 + (i + .5) * bw, y1 + 18, "%.2f to %s" % (x["lo"], "%.2f" % x["hi"] if x["hi"] < 9 else "up"), "dim num", "middle")
    b += og.text((x0 + x1) / 2, y1 + 42, "what the first read said (z); under 0 a trial was dropped at once", "", "middle") + fw.ylabel(22, y0, y1, "seeds read after the first read")
    return og.svg(W, Ht, b, "Fig. 3: seeds read after the first read, by the first read, with the candidates that came of them")


FIGS = {"maps": fig_maps, "noise": fig_noise, "first": fig_first}


def main(a):
    if a[0] == "--redraw":
        out = os.path.abspath(a[1])
    else:
        q, out = os.path.abspath(a[0]), os.path.abspath(a[1])
        os.makedirs(out, exist_ok=True)
        json.dump(gather(q, int(a[2]) if len(a) > 2 else 17000), open(os.path.join(out, "data.json"), "w"), indent=1, default=str)
    D = json.load(open(os.path.join(out, "data.json")))
    first = True
    for k, fn in FIGS.items():
        open(os.path.join(out, "fig-%s.html" % k), "w").write((og.STYLE if first else "") + fn(D) + "\n")
        first = False
    print("wrote %s: %d figures" % (out, len(FIGS)))


if __name__ == "__main__":
    main(sys.argv[1:])
