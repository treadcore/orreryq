#!/usr/bin/env python3
"""disk-report.py -- tools/disk-bench.py's results as charts and a conclusion matrix, for a lab report.

    python3 tools/disk-report.py fetch calber            copy calber's results to docs/calber-disks/data/
    python3 tools/disk-report.py draw calber             draw every chart into docs/calber-disks/
    python3 tools/disk-report.py summary calber          the matrix and the winners, in the terminal
    python3 tools/disk-report.py status [HOST...]        one JSON document for Orrery's Bench screen
    python3 tools/disk-report.py stage HOST inspect|run  copy the bench to HOST; print its command for the Sessions tile

Paul, 7 November 2026: "tools such that after running the bench mark next time we can use the data and make a
clear comparison, show trendlines, max speed, worse latency. and help us generate a conclusion matrix and show
us best options in Green", with every layout "super imposed on this graph", "for N disks, but our N is 6 today".

WHAT IT DRAWS, each an inline SVG figure a lab report pastes with !html(path) (tools/report/md.py), with a
tooltip on every mark:
    overlay.html     every layout on one chart: each measure as a multiple of one disk, log scale
    bars.html        each measure alone, the layouts ranked, the best starred
    latency.html     the worst latency: 99th percentile and the single slowest request, lower is better
    matrix.html      the conclusion matrix: every layout against every measure and three uses, the best green
    raw.html         each disk alone, no filesystem: is one weaker than the rest?
    barrage-*.html   block sizes, queue depths, the cache cliff, the file trees (when a barrage ran)
    trend.html       a measure across runs, with a least-squares line (when there are two runs or more)
and summary.json, the numbers the charts were drawn from.

COLOUR IS THE TECHNOLOGY, never the rank: mdadm blue, ZFS orange, btrfs aqua, one disk gray. Three hues are
the most that stay apart for every reader when all of them share a chart (the dataviz reference palette's
all-pairs cap), so a layout's variant is its line's dash and its marker's shape, and every line is named in a
legend. "Best" is the status colour good, green, always with a star: it is never a series colour.
"""
import glob
import html
import json
import math
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The first version's names, and this one's.
ALIAS = {"single-ext4": "single", "pair-md-ext4": "pair-md", "six-md10-xfs": "md10", "six-md10-ext4": "md10-ext4",
         "six-md0-xfs": "md0", "six-btrfs10": "btrfs10", "six-zfs-3x2": "zfs-3x2", "six-zfs-2x3": "zfs-2x3",
         "four-md10-2spare": "md10-4+2spare", "zfs-2x2-spare-l2arc": "zfs-2x2+spare+l2arc", "zfs-2x2-slog-l2arc": "zfs-2x2+slog+l2arc"}

# (key, side, field, label, unit, higher is better)
MEASURES = [
    ("seq-write", "write", "MBps", "seq write", "MB/s", True), ("seq-read", "read", "MBps", "seq read", "MB/s", True),
    ("butterfly", "write", "MBps", "two streams", "MB/s", True), ("write-read", "read", "MBps", "read-back", "MB/s", True),
    ("rand-read", "read", "iops", "4K reads", "IOPS", True), ("rand-write", "write", "iops", "4K writes", "IOPS", True),
    ("mixed", "read", "iops", "70/30 mix", "IOPS", True), ("sync-write", "write", "iops", "sync writes", "IOPS", True),
    ("create_s", None, None, "create 100k", "s", False), ("find_s", None, None, "find", "s", False),
    ("ls_lR_s", None, None, "ls -lR", "s", False), ("stat_sort_s", None, None, "stat + sort", "s", False),
    ("delete_s", None, None, "delete", "s", False),
]
USES = {
    "Blu-ray working disk": {"seq-write": 3, "seq-read": 3, "butterfly": 1, "create_s": 1, "find_s": 1, "ls_lR_s": 1, "stat_sort_s": 1},
    "swap": {"rand-read": 3, "rand-write": 3, "seq-write": 1, "seq-read": 1},
    "NFS share": {"sync-write": 3, "mixed": 2, "find_s": 1, "ls_lR_s": 1, "stat_sort_s": 1, "seq-read": 1, "seq-write": 1},
}

# Identity: hue by technology, dash and marker by variant.
TECH = {"md": "--s-md", "zfs": "--s-zfs", "btrfs": "--s-btrfs", "one": "--s-one"}
STYLE = """<style>
.viz-root { --surface: #fcfcfb; --t1: #0b0b0b; --t2: #52514e; --t3: #8a887f; --grid: #e4e2dc;
  --s-md: #2a78d6; --s-zfs: #eb6834; --s-btrfs: #1baf7a; --s-one: #6f6d66; --good: #0ca30c; --bad: #d03b3b;
  --good-bg: rgba(12,163,12,.16); --bad-bg: rgba(208,59,59,.13);
  background: var(--surface); color: var(--t1); border-radius: 6px; padding: 10px 12px; margin: 14px 0; overflow-x: auto; }
@media (prefers-color-scheme: dark) { :root:where(:not([data-theme="light"])) .viz-root {
  --surface: #1a1a19; --t1: #f0efec; --t2: #c3c2b7; --t3: #8f8d84; --grid: #33332f;
  --s-md: #3987e5; --s-zfs: #d95926; --s-btrfs: #199e70; --s-one: #a3a197; --good-bg: rgba(12,163,12,.28); --bad-bg: rgba(208,59,59,.25); } }
:root[data-theme="dark"] .viz-root { --surface: #1a1a19; --t1: #f0efec; --t2: #c3c2b7; --t3: #8f8d84; --grid: #33332f;
  --s-md: #3987e5; --s-zfs: #d95926; --s-btrfs: #199e70; --s-one: #a3a197; --good-bg: rgba(12,163,12,.28); --bad-bg: rgba(208,59,59,.25); }
.viz-root svg { display: block; width: 100%; height: auto; font: 11px ui-sans-serif, system-ui, -apple-system, sans-serif; }
.viz-root .t1 { fill: var(--t1); } .viz-root .t2 { fill: var(--t2); } .viz-root .t3 { fill: var(--t3); }
.viz-root .grid { stroke: var(--grid); stroke-width: 1; }
.viz-root .hit { fill: transparent; } .viz-root .hit:hover + .mk, .viz-root g.s:hover path { stroke-width: 3.5; }
.viz-root .cap { font: 12px ui-sans-serif, system-ui, sans-serif; color: var(--t2); margin: 4px 0 0; }
</style>"""


def tech(name):
    if name in ("single", "raw"):   # the bare disk is one disk too: gray in the lines and in their legend
        return "one"
    for t in ("zfs", "btrfs"):
        if t in name:
            return t
    return "md"


def dash(name):
    if name.startswith("pair") or name == "single":
        return "6 4"
    if "spare" in name or "slog" in name or "l2arc" in name:
        return "2 3"
    return ""


MARKERS = ["circle", "square", "diamond", "triangle"]


def marker(name, x, y, color, r=4.5):
    variants = [n for n in ORDER if tech(n) == tech(name)]
    shape = MARKERS[variants.index(name) % len(MARKERS)] if name in variants else "circle"
    s = 'stroke="var(--surface)" stroke-width="2" fill="var(%s)"' % color
    if shape == "circle":
        return '<circle cx="%.1f" cy="%.1f" r="%.1f" %s/>' % (x, y, r, s)
    if shape == "square":
        return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="1" %s/>' % (x - r, y - r, 2 * r, 2 * r, s)
    if shape == "diamond":
        return '<path d="M%.1f %.1fL%.1f %.1fL%.1f %.1fL%.1f %.1fZ" %s/>' % (x, y - r - 1, x + r + 1, y, x, y + r + 1, x - r - 1, y, s)
    return '<path d="M%.1f %.1fL%.1f %.1fL%.1f %.1fZ" %s/>' % (x, y - r - 1, x + r + 1, y + r, x - r - 1, y + r, s)


ORDER = []   # every layout, in a fixed order: the legend's, the matrix's


def esc(s):
    return html.escape(str(s), quote=True)


def fmt(v, unit):
    if v is None:
        return "-"
    if unit == "s":
        return "%.2f s" % v
    return "{:,.0f} {}".format(v, unit)


# ---- loading --------------------------------------------------------------------------------------

def cliff_of(per):
    """The GB written before the fast write cache ran out: the first second, after the speed's peak, from
    which it stays under 60% of the early speed for three seconds running. The first second is fio
    ramping up, not the cache: a plain "first second under 60%" read the ramp as the cliff (7 November)."""
    if len(per) < 5:
        return None
    head = sorted(per[1:11])[len(per[1:11]) // 2]
    total, peaked = 0.0, False
    for i, v in enumerate(per):
        if v >= head * 0.9:
            peaked = True
        if peaked and i + 3 <= len(per) and all(x < head * 0.6 for x in per[i:i + 3]):
            return round(total, 1)
        total += v / 1000
    return None

def load(host):
    data = os.path.join(ROOT, "docs", "%s-disks" % host, "data")
    runs = []
    for d in sorted(glob.glob(os.path.join(data, "runs", "*"))) + ([data] if glob.glob(os.path.join(data, "*.json")) else []):
        run = {"stamp": os.path.basename(d) if d != data else "v1", "suite": {}, "barrage": {}, "raw": None, "meta": {}}
        for p in glob.glob(os.path.join(d, "*.json")):
            j = json.load(open(p))
            b = os.path.basename(p)[:-5]
            if b == "run":
                run["meta"] = j
            elif b == "raw-each":
                run["raw"] = j["raw"]
            elif b.startswith("barrage-"):
                run["barrage"][j["layout"]] = j
            elif "suite" in j:
                # Repeated trials (layout#k) are kept apart here and folded to medians by table().
                run["suite"][j.get("trial") or ALIAS.get(j["layout"], j["layout"])] = j
        if run["stamp"] == "v1":
            ats = [j.get("at", "") for j in run["suite"].values() if j.get("at")]
            run["stamp"] = "v1-" + (min(ats)[:10] if ats else "")
        runs.append(run)
    return runs


def value(suite, key, side, field):
    if side is None:
        return suite.get("metadata", {}).get(key)
    return suite.get(key, {}).get(side, {}).get(field)


def table(run):
    """{layout: {measure: value}} for one run's quick suite. Repeated trials (layout#k) fold to their median,
    and their spread is kept as spread[layout][measure] = (lowest, highest, trials)."""
    trials = {}
    for name, j in run["suite"].items():
        row = {m[0]: value(j["suite"], m[0], m[1], m[2]) for m in MEASURES}
        for k in ("rand-read", "rand-write", "seq-write"):
            side = "read" if k == "rand-read" else "write"
            row["p99:" + k] = j["suite"].get(k, {}).get(side, {}).get("p99_us")
            row["max:" + k] = j["suite"].get(k, {}).get(side, {}).get("max_us")
        trials.setdefault(name.partition("#")[0], []).append(row)
    t = {}
    for name, rows in trials.items():
        t[name] = {}
        for k in rows[0]:
            vals = sorted(r[k] for r in rows if r.get(k) is not None)
            t[name][k] = vals[len(vals) // 2] if vals else None
            if len(vals) > 1:
                SPREAD.setdefault(name, {})[k] = (vals[0], vals[-1], len(vals))
    return t


SPREAD = {}


def ratio(t, name, key, higher):
    base, v = t.get("single", {}).get(key), t[name].get(key)
    if not base or not v:
        return None
    return v / base if higher else base / v


def capacity(name, n, gb):
    """Usable GB and the disks a layout can lose for certain."""
    k = n - 2 if ("+2spare" in name or "+spare" in name or "+slog" in name) else n
    if name == "single":
        return gb, 0
    if name.startswith("pair"):
        return gb, 1
    if name == "md0":
        return gb * n, 0
    if "x3" in name:
        return gb * n / 3, 2
    return gb * k / 2, 1


# ---- the figures ----------------------------------------------------------------------------------

def figure(svg, caption, width=880):
    return '%s<div class="viz-root">%s<p class="cap">%s</p></div>\n' % (STYLE, svg, esc(caption))


def legend(names, x, y, cols=4, colw=210):
    out = []
    for i, n in enumerate(names):
        cx, cy = x + (i % cols) * colw, y + (i // cols) * 18
        c = TECH[tech(n)]
        out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="var(%s)" stroke-width="2" stroke-dasharray="%s"/>' % (cx, cy, cx + 22, cy, c, dash(n)))
        out.append(marker(n, cx + 11, cy, c, 3.5))
        out.append('<text x="%d" y="%d" class="t2">%s</text>' % (cx + 28, cy + 4, esc(n)))
    return "".join(out)


def overlay(t, n):
    names = [x for x in ORDER if x in t]
    rows = (len(names) + 3) // 4
    W, L, R, T, B = 880, 60, 20, 30, 70 + 18 * rows
    H = 320 + B
    xs = [m for m in MEASURES if any(ratio(t, nm, m[0], m[5]) for nm in names)]
    lo, hi = -2, 3   # log2 of the multiple: 0.25x to 8x
    for nm in names:
        for m in xs:
            r = ratio(t, nm, m[0], m[5])
            if r:
                lo, hi = min(lo, math.floor(math.log2(r))), max(hi, math.ceil(math.log2(r)))
    X = lambda i: L + i * (W - L - R) / max(1, len(xs) - 1)
    Y = lambda r: T + (hi - math.log2(r)) / (hi - lo) * (H - T - B)
    out = ['<svg viewBox="0 0 %d %d" role="img" aria-label="every layout as a multiple of one disk">' % (W, H)]
    for e in range(lo, hi + 1):
        y = Y(2 ** e)
        out.append('<line class="grid" x1="%d" x2="%d" y1="%.1f" y2="%.1f"%s/>' % (L, W - R, y, y, ' stroke-dasharray="0"' if e else ''))
        out.append('<text x="%d" y="%.1f" class="t3" text-anchor="end">%s</text>' % (L - 6, y + 4, ("%gx" % 2 ** e)))
    y1 = Y(1)
    out.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="var(--t3)" stroke-width="1.5"/>' % (L, W - R, y1, y1))
    out.append('<text x="%d" y="%.1f" class="t2">one disk</text>' % (W - R - 50, y1 - 5))
    for i, m in enumerate(xs):
        out.append('<text x="%.1f" y="%d" class="t2" text-anchor="middle">%s</text>' % (X(i), H - B + 18, esc(m[3])))
        out.append('<text x="%.1f" y="%d" class="t3" text-anchor="middle">%s</text>' % (X(i), H - B + 31, "faster" if m[5] else "quicker"))
    for nm in names:
        c = TECH[tech(nm)]
        pts = [(X(i), Y(ratio(t, nm, m[0], m[5])), m) for i, m in enumerate(xs) if ratio(t, nm, m[0], m[5])]
        if not pts:
            continue
        d = "M" + " L".join("%.1f %.1f" % (x, y) for x, y, _ in pts)
        out.append('<g class="s"><path d="%s" fill="none" stroke="var(%s)" stroke-width="2" stroke-dasharray="%s" stroke-linejoin="round"><title>%s</title></path>' % (d, c, dash(nm), esc(nm)))
        for x, y, m in pts:
            r = ratio(t, nm, m[0], m[5])
            out.append('<circle class="hit" cx="%.1f" cy="%.1f" r="9"><title>%s, %s: %s (%.2fx one disk)</title></circle>%s' % (
                x, y, esc(nm), esc(m[3]), esc(fmt(t[nm][m[0]], m[4])), r, marker(nm, x, y, c)))
        out.append("</g>")
    out.append(legend(names, L, H - B + 58))
    out.append("</svg>")
    return figure("".join(out), "Every layout on one chart. Each measure is a multiple of one disk on its own (log scale; above the line is "
                  "better, for times too: they are inverted). Colour is the technology: mdadm blue, ZFS orange, btrfs aqua; dashes mark the "
                  "pairs and dots the layouts with spares, logs or caches. Hover a point for its value.")


def bars(t):
    names = [x for x in ORDER if x in t]
    ms = [m for m in MEASURES if any(t[nm].get(m[0]) for nm in names)]
    cols, pw, ph = 2, 430, 22 + 17 * len(names)
    W, H = cols * pw + 20, ((len(ms) + cols - 1) // cols) * (ph + 26) + 10
    out = ['<svg viewBox="0 0 %d %d" role="img" aria-label="each measure, the layouts ranked">' % (W, H)]
    for k, m in enumerate(ms):
        ox, oy = (k % cols) * (pw + 20), (k // cols) * (ph + 26) + 16
        vals = [(nm, t[nm].get(m[0])) for nm in names if t[nm].get(m[0])]
        best = max(v for _, v in vals) if m[5] else min(v for _, v in vals)
        top = max(v for _, v in vals)
        vals.sort(key=lambda kv: -kv[1] if m[5] else kv[1])
        out.append('<text x="%d" y="%d" class="t1" font-weight="600">%s (%s%s)</text>' % (ox, oy, esc(m[3]), esc(m[4]), ", lower is better" if not m[5] else ""))
        for i, (nm, v) in enumerate(vals):
            y = oy + 8 + i * 17
            w = max(2, (pw - 210) * v / top)
            out.append('<text x="%d" y="%d" class="t2" text-anchor="end">%s</text>' % (ox + 128, y + 11, esc(nm)))
            sp = SPREAD.get(nm, {}).get(m[0])
            tip = "%s, %s: %s%s" % (nm, m[3], fmt(v, m[4]), ", median of %d trials, %s to %s" % (sp[2], fmt(sp[0], m[4]), fmt(sp[1], m[4])) if sp else "")
            out.append('<rect x="%d" y="%d" width="%.1f" height="12" rx="3" fill="var(%s)"><title>%s</title></rect>' % (ox + 134, y + 1, w, TECH[tech(nm)], esc(tip)))
            if sp:   # the spread of repeated trials: a whisker from the lowest to the highest
                a_, b_ = (pw - 210) * sp[0] / top, (pw - 210) * sp[1] / top
                out.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="var(--t1)" stroke-width="1.5"/>' % (ox + 134 + a_, ox + 134 + b_, y + 7, y + 7))
            star = v == best
            out.append('<text x="%.1f" y="%d" class="%s"%s>%s%s</text>' % (ox + 140 + w, y + 11, "t1" if star else "t3",
                       ' fill="var(--good)" font-weight="700"' if star else "", esc(fmt(v, m[4])), "  ★ best" if star else ""))
    out.append("</svg>")
    return figure("".join(out), "Each measure alone, the layouts ranked best first. The bar's colour is the technology; the best carries a green star.")


def latency(t):
    names = [x for x in ORDER if x in t]
    keys = [("rand-read", "4K reads"), ("rand-write", "4K writes"), ("seq-write", "seq writes")]
    pw, ph = 285, 22 + 17 * len(names)
    W, H = 3 * pw + 20, 2 * (ph + 30) + 10
    out = ['<svg viewBox="0 0 %d %d" role="img" aria-label="worst latency per layout">' % (W, H)]
    for row, (kind, word) in enumerate((("p99", "99th percentile"), ("max", "slowest single request"))):
        for col, (k, lab) in enumerate(keys):
            ox, oy = col * (pw + 10), row * (ph + 30) + 16
            vals = [(nm, t[nm].get("%s:%s" % (kind, k))) for nm in names if t[nm].get("%s:%s" % (kind, k))]
            if not vals:
                continue
            top = max(v for _, v in vals)
            worst = top
            out.append('<text x="%d" y="%d" class="t1" font-weight="600">%s, %s</text>' % (ox, oy, esc(lab), esc(word)))
            for i, (nm, v) in enumerate(sorted(vals, key=lambda kv: kv[1])):
                y = oy + 8 + i * 17
                w = max(2, (pw - 175) * math.log10(max(v, 1)) / math.log10(max(top, 10)))
                out.append('<text x="%d" y="%d" class="t2" text-anchor="end">%s</text>' % (ox + 108, y + 11, esc(nm)))
                out.append('<rect x="%d" y="%d" width="%.1f" height="12" rx="3" fill="var(%s)"><title>%s: %s</title></rect>' % (ox + 112, y + 1, w, TECH[tech(nm)], esc(nm), esc(us(v))))
                bad = v == worst
                out.append('<text x="%.1f" y="%d" class="t3"%s>%s%s</text>' % (ox + 116 + w, y + 11, ' fill="var(--bad)" font-weight="700"' if bad else "", esc(us(v)), " ▲ worst" if bad else ""))
    out.append("</svg>")
    return figure("".join(out), "The worst latency, lower is better (log scale): the 99th percentile, and the single slowest request of each run. The worst carries a red triangle.")


def us(v):
    return "%.0f µs" % v if v < 1000 else ("%.1f ms" % (v / 1000) if v < 1e6 else "%.2f s" % (v / 1e6))


def score(t, nm, weights):
    num = den = 0.0
    for k, w in weights.items():
        m = next(x for x in MEASURES if x[0] == k)
        r = ratio(t, nm, k, m[5])
        if r:
            num += w * math.log(r)
            den += w
    return math.exp(num / den) if den else None


def matrix(t, n, gb):
    names = [x for x in ORDER if x in t]
    cols = [m for m in MEASURES if any(t[nm].get(m[0]) for nm in names)]
    uses = list(USES)
    cw, uw, rh, L = 64, 100, 22, 150
    W = L + len(cols) * cw + 2 * 70 + len(uses) * uw + 10
    H = 70 + rh * len(names) + 60
    # Wider than a column: it scrolls sideways rather than shrinking its text below reading size.
    out = ['<svg viewBox="0 0 %d %d" style="min-width:%dpx" role="img" aria-label="the conclusion matrix">' % (W, H, W)]
    heads = [(m[3], m[4]) for m in cols] + [("usable", "GB"), ("can lose", "disks")] + [(u, "x one disk") for u in uses]
    xs = []
    x = L
    for i, (h, u) in enumerate(heads):
        w = uw if i >= len(cols) + 2 else (70 if i >= len(cols) else cw)
        xs.append((x, w))
        out.append('<text transform="translate(%.1f,62) rotate(-35)" class="t2">%s</text>' % (x + w / 2 - 4, esc(h)))
        x += w
    scores = {u: {nm: score(t, nm, USES[u]) for nm in names} for u in uses}
    for r, nm in enumerate(names):
        y = 70 + r * rh
        out.append('<text x="%d" y="%d" class="t1" text-anchor="end">%s</text>' % (L - 8, y + 15, esc(nm)))
        out.append(marker(nm, 8, y + 11, TECH[tech(nm)], 3.5))
        cells = []
        for m in cols:
            v = t[nm].get(m[0])
            vals = [t[o].get(m[0]) for o in names if t[o].get(m[0])]
            best = (max(vals) if m[5] else min(vals)) if vals else None
            rel = (v / best if m[5] else best / v) if v and best else 0
            cells.append((fmt(v, m[4]).split(" ")[0] if v else "-", rel, "%s, %s: %s" % (nm, m[3], fmt(v, m[4]))))
        cap, lose = capacity(nm, n, gb)
        cells.append(("%.0f" % cap, None, "%s: %.0f GB usable" % (nm, cap)))
        cells.append(("%d" % lose, None, "%s: can lose %d disk(s) for certain" % (nm, lose)))
        for u in uses:
            s = scores[u][nm]
            ok = not (u == "NFS share" and lose == 0)
            best = max(v for o, v in scores[u].items() if v and not (u == "NFS share" and capacity(o, n, gb)[1] == 0))
            rel = (s / best) if s and ok else 0
            cells.append(("%.2f" % s if s else "-", rel if ok else -1, "%s, %s: %.2fx one disk%s" % (nm, u, s or 0, "" if ok else ", no redundancy")))
        for (txt, rel, tip), (cx, w) in zip(cells, xs):
            fill, mark = "transparent", ""
            if rel is not None:
                if rel >= 0.999:
                    fill, mark = "var(--good-bg)", "★"
                elif rel >= 0.9:
                    fill = "var(--good-bg)"
                elif rel == -1:
                    fill, mark = "var(--bad-bg)", "✗"
                elif 0 < rel <= 0.5:
                    fill, mark = "var(--bad-bg)", "▼"
            out.append('<rect x="%.1f" y="%d" width="%d" height="%d" rx="3" fill="%s" stroke="var(--surface)" stroke-width="2"><title>%s</title></rect>' % (cx, y, w, rh, fill, esc(tip)))
            out.append('<text x="%.1f" y="%d" text-anchor="middle" class="%s"%s>%s%s</text>' % (cx + w / 2, y + 15, "t1" if mark == "★" else "t2",
                       ' font-weight="700"' if mark == "★" else "", esc(txt), (" " + mark) if mark else ""))
    ly = 70 + rh * len(names) + 26
    out.append('<rect x="%d" y="%d" width="14" height="12" rx="3" fill="var(--good-bg)"/><text x="%d" y="%d" class="t2">★ the best, or within 10%% of it</text>' % (L, ly, L + 20, ly + 10))
    out.append('<rect x="%d" y="%d" width="14" height="12" rx="3" fill="var(--bad-bg)"/><text x="%d" y="%d" class="t2">▼ half the best or worse;  ✗ no redundancy, so not for a share</text>' % (L + 250, ly, L + 270, ly + 10))
    out.append("</svg>")
    winners = {u: max((v, nm) for nm, v in scores[u].items() if v and not (u == "NFS share" and capacity(nm, n, gb)[1] == 0))[1] for u in uses}
    return figure("".join(out), "The conclusion matrix. Each measure's cell is green within 10% of the best (starred); the three uses are weighted "
                  "geometric means of the multiples of one disk, a share requiring a layout that survives a lost disk. Best for each use: "
                  + "; ".join("%s, %s" % (u, w) for u, w in winners.items()) + "."), winners, scores


def raw(run):
    r = run["raw"]
    rows = [(k, v) for k, v in sorted(r.items())]
    W, H = 880, 40 + 3 * (22 + 17 * len(rows))
    out = ['<svg viewBox="0 0 %d %d" role="img" aria-label="each disk alone">' % (W, H)]
    for g, (key, side, field, lab, unit) in enumerate((("seq-write", "write", "MBps", "sequential write", "MB/s"),
                                                       ("seq-read", "read", "MBps", "sequential read (fresh flash)", "MB/s"),
                                                       ("rand-read", "read", "iops", "4K reads", "IOPS"))):
        oy = 16 + g * (22 + 17 * len(rows))
        vals = [(k, v[key][side][field]) for k, v in rows]
        top = max(x for _, x in vals)
        out.append('<text x="0" y="%d" class="t1" font-weight="600">%s (%s)</text>' % (oy, esc(lab), unit))
        for i, (k, v) in enumerate(vals):
            y = oy + 8 + i * 17
            w = (W - 260) * v / top
            out.append('<text x="96" y="%d" class="t2" text-anchor="end">%s %s</text>' % (y + 11, esc(k), esc(r[k]["dev"].replace("/dev/", ""))))
            out.append('<rect x="102" y="%d" width="%.1f" height="12" rx="3" fill="var(--s-one)"><title>%s: %s</title></rect>' % (y + 1, w, esc(k), esc(fmt(v, unit))))
            out.append('<text x="%.1f" y="%d" class="t3">%s</text>' % (108 + w, y + 11, esc(fmt(v, unit))))
    out.append("</svg>")
    return figure("".join(out), "Each disk alone, raw, no filesystem. A weak disk would stand out; none does.")


def lines_chart(series, xlabels, ylab, title, caption, logy=False):
    """series: [(name, [y or None per x])]. One panel, a line per layout."""
    W, H, L, R, T, B = 880, 330, 70, 20, 28, 90
    vals = [v for _, ys in series for v in ys if v]
    if not vals:
        return ""
    lo, hi = (math.log10(min(vals)), math.log10(max(vals))) if logy else (0, max(vals) * 1.08)
    if logy:
        lo, hi = math.floor(lo), math.ceil(hi)
    X = lambda i: L + i * (W - L - R) / max(1, len(xlabels) - 1)
    Y = lambda v: T + (hi - (math.log10(v) if logy else v)) / (hi - lo) * (H - T - B)
    out = ['<svg viewBox="0 0 %d %d" role="img" aria-label="%s">' % (W, H, esc(title)),
           '<text x="0" y="14" class="t1" font-weight="600">%s</text>' % esc(title)]
    ticks = [10 ** e for e in range(int(lo), int(hi) + 1)] if logy else [hi * k / 4 for k in range(5)]
    for v in ticks:
        y = Y(v)
        out.append('<line class="grid" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/><text x="%d" y="%.1f" class="t3" text-anchor="end">%s</text>' % (L, W - R, y, y, L - 6, y + 4, "{:,.0f}".format(v)))
    out.append('<text transform="translate(14,%d) rotate(-90)" class="t3" text-anchor="middle">%s</text>' % ((T + H - B) // 2, esc(ylab)))
    for i, xl in enumerate(xlabels):
        out.append('<text x="%.1f" y="%d" class="t2" text-anchor="middle">%s</text>' % (X(i), H - B + 18, esc(xl)))
    for nm, ys in series:
        c = TECH[tech(nm)]
        pts = [(X(i), Y(v), v, xlabels[i]) for i, v in enumerate(ys) if v]
        if len(pts) > 1:
            out.append('<path d="M%s" fill="none" stroke="var(%s)" stroke-width="2" stroke-dasharray="%s"/>' % (" L".join("%.1f %.1f" % (x, y) for x, y, _, _ in pts), c, dash(nm)))
        for x, y, v, xl in pts:
            out.append('<circle class="hit" cx="%.1f" cy="%.1f" r="9"><title>%s at %s: %s</title></circle>%s' % (x, y, esc(nm), esc(xl), "{:,.0f}".format(v), marker(nm, x, y, c, 3.5)))
    out.append(legend([nm for nm, _ in series], L, H - B + 44))
    out.append("</svg>")
    return figure("".join(out), caption)


def merged_barrage(runs):
    """Each layout's barrage parts from the newest run that has them. A sweep counts only if its region was
    written whole first ("filled", or a bare disk): the first barrage's filesystem read sweeps read holes,
    zeros a filesystem returns without a disk, and are left out (7 November)."""
    out = {}
    for r in runs:
        for nm, j in r["barrage"].items():
            o = out.setdefault(nm, {"layout": nm})
            if j.get("cliff"):
                o["cliff"] = j["cliff"]
            sw = j.get("sweeps")
            if sw and (sw.get("filled") or nm == "raw"):
                o["sweeps"] = sw
            if j.get("trees"):
                o["trees"] = j["trees"]
    return out


def barrage_figures(run, outdir):
    b = run["barrage"]
    if not b:
        return []
    names = [n for n in ["raw"] + ORDER if n in b] + sorted(n for n in b if n != "raw" and n not in ORDER)
    made = []
    sizes = ["4k", "16k", "64k", "256k", "1M"]
    swept = [n for n in names if b[n].get("sweeps")]
    for rw, word in (("write", "sequential writes"), ("read", "sequential reads"), ("randwrite", "random writes"), ("randread", "random reads")):
        series = [(n, [b[n]["sweeps"]["block"].get(s, {}).get(rw, {}).get("MBps") for s in sizes]) for n in swept]
        made.append(("barrage-block-%s.html" % rw, lines_chart(series, sizes, "MB/s", "Block size against speed: %s, queue 32" % word,
                     "MB/s at each block size. Small blocks are bound by operations a second, large ones by the SATA link (about 550 MB/s a disk).")))
    depths = ["1", "2", "4", "8", "16", "32", "64"]
    series = [(n, [b[n]["sweeps"]["depth"].get(q, {}).get("iops") for q in depths]) for n in swept]
    made.append(("barrage-depth.html", lines_chart(series, depths, "IOPS", "Queue depth against 4K random reads, one thread",
                 "How many requests in flight it takes to reach full speed. At queue 1 the number is the drive's own latency.", logy=True)))
    cliffed = [n for n in names if b[n].get("cliff")]
    longest = max([len(b[n]["cliff"]["MBps_each_second"]) for n in cliffed] or [1])
    xl = [str(i) for i in range(1, longest + 1)]
    series = [(n, b[n]["cliff"]["MBps_each_second"] + [None] * (longest - len(b[n]["cliff"]["MBps_each_second"]))) for n in cliffed]
    made.append(("barrage-cliff.html", lines_chart(series, [x if int(x) % 10 == 0 or x == "1" else "" for x in xl], "MB/s", "The cache cliff: 75 s of sequential writes, a point a second",
                 "Where each layout's fast (SLC) write cache runs out: "
                 + "; ".join("%s after %s GB" % (n, cliff_of(b[n]["cliff"]["MBps_each_second"])) for n in cliffed) + ".")))
    ops = ["create_s", "find_s", "find_name_s", "ls_lR_s", "du_s", "sort_size_s", "sort_name_s", "grep_s", "copy_s", "delete_s"]
    for tree_name in ("100k x 4K", "300k empty", "256 x 16M"):
        tn = [n for n in names if n in b and "trees" in b[n] and tree_name in b[n]["trees"]]
        if not tn:
            continue
        series = [(n, [b[n]["trees"][tree_name].get(o) for o in ops]) for n in tn]
        made.append(("barrage-tree-%s.html" % tree_name.replace(" ", "").lower(), lines_chart(series, [o[:-2].replace("_", " ") for o in ops], "seconds",
                     "File tree %s: each operation, cold caches" % tree_name, "Seconds for each operation on the tree, lower is better; grep -r reads every byte, a linear search.", logy=True)))
    for fname, body in made:
        if body:
            open(os.path.join(outdir, fname), "w").write(body)
    return [f for f, body in made if body]


def trend(runs, outdir):
    """A measure across runs, one panel a measure, a least-squares line a layout."""
    if len([r for r in runs if r["suite"]]) < 2:
        open(os.path.join(outdir, "trend.html"), "w").write(figure("<svg viewBox='0 0 880 40'><text x='0' y='24' class='t3'>One run so far: a trend needs two. "
                                                                   "Run the bench again and draw again.</text></svg>", "Trends across runs."))
        return
    stamps = [r["stamp"] for r in runs if r["suite"]]
    tabs = [table(r) for r in runs if r["suite"]]
    body = []
    for m in MEASURES[:8]:
        series = []
        for nm in ORDER:
            ys = [tb.get(nm, {}).get(m[0]) for tb in tabs]
            if sum(1 for y in ys if y) >= 2:
                series.append((nm, ys))
        body.append(lines_chart(series, stamps, m[4], "%s across runs" % m[3], "Each run's value; a straight line is fitted per layout in summary.json."))
    open(os.path.join(outdir, "trend.html"), "w").write("".join(body))


# ---- commands -------------------------------------------------------------------------------------

def fetch(host):
    dest = os.path.join(ROOT, "docs", "%s-disks" % host, "data")
    os.makedirs(dest, exist_ok=True)
    subprocess.run("rsync -a --exclude LOG.old %s:fleet/disk-bench/results/ %s/" % (host, dest), shell=True, check=True)
    print("copied %s's results to %s" % (host, os.path.relpath(dest, ROOT)))


PREF = ["single", "pair-md", "pair-zfs", "pair-btrfs", "md10", "md10-ext4", "md0", "md10-4+2spare", "zfs-3x2", "zfs-2x3",
        "zfs-2x2+spare+l2arc", "zfs-2x2+slog+l2arc", "btrfs10"]


def compute(host, only=None):
    """A machine's quick-suite results as one table, repeated trials as medians. `only`, a run's stamp,
    keeps that run alone. MEASUREMENTS ARE COMPARED WITHIN A RUN: the first run measured every layout
    straight after the last (its writes came in at half what a 30 s pause gives, 7 November), the second
    measured four finalists after a pause, so a finalist of the second against the first run's one disk would
    flatter it. Without `only`, the run that measured the most layouts is the table."""
    global ORDER
    runs = load(host)
    if not runs:
        return None
    SPREAD.clear()
    quick = {}
    with_suite = [r for r in runs if r["suite"]]
    if only:
        pick = [r for r in with_suite if r["stamp"] == only]
    else:
        pick = sorted(with_suite, key=lambda r: len({k.partition("#")[0] for k in r["suite"]}))[-1:] if with_suite else []
    for r in pick:
        stamps = {}
        for nm, j in r["suite"].items():
            base = nm.partition("#")[0]
            # A newer run's trials of a layout replace an older run's, rather than mixing with them.
            if base not in stamps:
                for old in [k for k in quick if k.partition("#")[0] == base]:
                    del quick[old]
                stamps[base] = True
            quick[nm] = j
    t = table({"suite": quick})
    meta = next((r["meta"] for r in reversed(runs) if r["meta"]), {})
    n = len(meta.get("serials", [])) or 6
    gb = 480
    ORDER = [x for x in PREF if x in t] + sorted(x for x in t if x not in PREF)
    return {"runs": runs, "t": t, "n": n, "gb": gb, "meta": meta, "stamp": pick[0]["stamp"] if pick else None,
            "others": [r["stamp"] for r in with_suite if not pick or r["stamp"] != pick[0]["stamp"]]}


def draw(host):
    c = compute(host)
    if not c:
        sys.exit("no results: python3 tools/disk-report.py fetch %s" % host)
    runs, t, n, gb = c["runs"], c["t"], c["n"], c["gb"]
    outdir = os.path.join(ROOT, "docs", "%s-disks" % host)
    open(os.path.join(outdir, "overlay.html"), "w").write(overlay(t, n))
    open(os.path.join(outdir, "bars.html"), "w").write(bars(t))
    open(os.path.join(outdir, "latency.html"), "w").write(latency(t))
    mx, winners, scores = matrix(t, n, gb)
    open(os.path.join(outdir, "matrix.html"), "w").write(mx)
    rawrun = next((r for r in reversed(runs) if r["raw"]), None)
    if rawrun:
        open(os.path.join(outdir, "raw.html"), "w").write(raw(rawrun))
    made = barrage_figures({"barrage": merged_barrage(runs)}, outdir)
    # Every other run with a quick suite: its layouts ranked against each other, repeated trials as medians
    # with their spread, in a figure of its own (finalists-STAMP.html). Never folded into the first table.
    for other in c["others"]:
        oc = compute(host, other)
        if oc and oc["t"]:
            body = bars(oc["t"]).replace("Each measure alone, the layouts ranked best first.",
                                         "Run %s alone: its layouts ranked against each other, medians of repeated trials with whiskers for their spread." % other)
            open(os.path.join(outdir, "finalists-%s.html" % other), "w").write(body)
            made.append("finalists-%s.html" % other)
    c = compute(host)
    trend(runs, outdir)
    summary = {"layouts": t, "winners": winners, "scores": scores, "runs": [r["stamp"] for r in runs], "disks": n, "disk_GB": gb,
               "capacity": {nm: capacity(nm, n, gb) for nm in t}, "barrage_figures": made}
    json.dump(summary, open(os.path.join(outdir, "summary.json"), "w"), indent=1)
    print("drew %d figures into %s; best: %s" % (6 + len(made), os.path.relpath(outdir, ROOT), "; ".join("%s: %s" % kv for kv in winners.items())))


# ---- for Orrery ----------------------------------------------------------------------------------
CACHE = os.path.expanduser("~/.cache/orrery-bench")


def remote(host, cmd, timeout=20):
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", host, cmd], capture_output=True, text=True, timeout=timeout)
    return r.stdout if r.returncode == 0 else None


def machine_status(host):
    """One machine for the Bench screen: its run now, its spare disks, and the table every chart draws from.
    The results are fetched every 30 s while a run is live and every 10 min otherwise; the run's progress is
    read each time, cheaply (one cat over the fleet's shared ssh connection)."""
    import fcntl
    out = {"host": host, "error": ""}
    cdir = os.path.join(CACHE, host)
    os.makedirs(cdir, exist_ok=True)
    try:
        text = remote(host, "cat ~/fleet/disk-bench/results/progress.json 2>/dev/null || true", 10)
        out["progress"] = json.loads(text) if text and text.strip() else {}
    except (subprocess.TimeoutExpired, ValueError):
        out["progress"], out["error"] = {}, "cannot read %s's progress" % host
    stamp = os.path.join(cdir, "fetched")
    age = time.time() - (os.path.getmtime(stamp) if os.path.exists(stamp) else 0)
    live = out["progress"].get("state") == "running"
    done = len(out["progress"].get("done", []))
    last_done = int(open(os.path.join(cdir, "done")).read() or 0) if os.path.exists(os.path.join(cdir, "done")) else -1
    if age > 600 or (live and age > 30) or done != last_done:
        with open(os.path.join(cdir, "lock"), "w") as lk:
            try:
                fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
                dest = os.path.join(ROOT, "docs", "%s-disks" % host, "data")
                os.makedirs(dest, exist_ok=True)
                subprocess.run(["rsync", "-a", "--exclude", "LOG", "--exclude", "progress.json", "--exclude", ".progress.json",
                                "%s:fleet/disk-bench/results/" % host, dest + "/"], capture_output=True, timeout=60)
                open(stamp, "w").close()
                open(os.path.join(cdir, "done"), "w").write(str(done))
            except (BlockingIOError, subprocess.TimeoutExpired):
                pass
    spare = os.path.join(cdir, "spare.json")
    if not os.path.exists(spare) or time.time() - os.path.getmtime(spare) > 600:
        try:
            text = remote(host, "python3 ~/fleet/disk-bench/disk-bench.py candidates --json 2>/dev/null")
            if text and text.strip().startswith("{"):
                open(spare, "w").write(text)
        except subprocess.TimeoutExpired:
            pass
    sp = json.load(open(spare)) if os.path.exists(spare) else {}
    out["spare"], out["chosen"] = sp.get("spare", []), sp.get("chosen", [])
    c = compute(host)
    if c:
        t, n, gb = c["t"], c["n"], c["gb"]
        names = [x for x in ORDER if x in t]
        ms = [m for m in MEASURES if any(t[nm].get(m[0]) for nm in names)]
        best = {}
        for m in ms:
            vals = [(t[nm][m[0]], nm) for nm in names if t[nm].get(m[0])]
            best[m[0]] = (max(vals) if m[5] else min(vals))[1]
        scores = {u: {nm: score(t, nm, USES[u]) for nm in names} for u in USES}
        winners = {u: max((v, nm) for nm, v in scores[u].items() if v and not (u == "NFS share" and capacity(nm, n, gb)[1] == 0))[1] for u in USES}
        cliffs = []
        for nm, b in merged_barrage(c["runs"]).items():
            cl = b.get("cliff")
            if cl:
                cliffs.append({"layout": nm, "MBps": cl.get("MBps_each_second", []), "cliff_GB": cliff_of(cl.get("MBps_each_second", []))})
        out["summary"] = {
            "disks": n, "disk_GB": gb, "runs": [r["stamp"] for r in c["runs"]],
            "measures": [{"key": m[0], "label": m[3], "unit": m[4], "higher": m[5]} for m in ms],
            "layouts": [{"name": nm, "tech": tech(nm), "values": [t[nm].get(m[0]) for m in ms],
                         "ratios": [ratio(t, nm, m[0], m[5]) for m in ms],
                         "spread": [list(SPREAD.get(nm, {}).get(m[0], ())) or None for m in ms],
                         "usable_GB": capacity(nm, n, gb)[0], "can_lose": capacity(nm, n, gb)[1],
                         "scores": {u: scores[u][nm] for u in USES}} for nm in names],
            "best": best, "winners": [{"use": u, "layout": w, "score": scores[u][w]} for u, w in winners.items()],
            "cliffs": cliffs,
        }
    return out


def status(hosts):
    if not hosts:
        hosts = sorted(d[:-6] for d in os.listdir(os.path.join(ROOT, "docs")) if d.endswith("-disks") and os.path.isdir(os.path.join(ROOT, "docs", d)))
    print(json.dumps({"at": time.time(), "machines": [machine_status(h) for h in hosts]}))


def stage(host, what):
    """Copy the bench to a machine and hand back its command for the machine's Sessions tile, where a person
    types the sudo password. `inspect` reads only; `run` erases the disks in disks.txt and measures every
    layout. Orrery holds no root: this is the only way the bench starts from it."""
    if what not in ("inspect", "run"):
        sys.exit("stage HOST inspect|run")
    src = os.path.join(ROOT, "tools", "disk-bench.py")
    subprocess.run(["ssh", "-o", "BatchMode=yes", host, "mkdir -p ~/fleet/disk-bench"], check=True, capture_output=True)
    subprocess.run(["scp", "-q", src, "%s:fleet/disk-bench/disk-bench.py" % host], check=True)
    if not remote(host, "test -s ~/fleet/disk-bench/disks.txt && echo yes"):
        print(json.dumps({"error": "%s has no ~/fleet/disk-bench/disks.txt: write the serials of the disks it may erase there first "
                                   "(`python3 ~/fleet/disk-bench/disk-bench.py candidates` lists them)" % host}))
        return
    cmd = ("sudo python3 ~/fleet/disk-bench/disk-bench.py inspect" if what == "inspect" else
           "sudo systemd-run --unit=disk-bench-%s --collect python3 /home/user/fleet/disk-bench/disk-bench.py run --erase all" % time.strftime("%H%M"))
    print(json.dumps({"machine": host, "target": host, "command": cmd,
                      "what": "the bench, %s" % ("read only: what the disks hold" if what == "inspect" else "every layout, erasing the disks")}))


def summary(host):
    p = os.path.join(ROOT, "docs", "%s-disks" % host, "summary.json")
    s = json.load(open(p))
    for u, w in s["winners"].items():
        print("%-22s %s (%.2fx one disk)" % (u, w, s["scores"][u][w]))


def main(a):
    if a and a[0] == "status":
        return status(a[1:])
    if a and a[0] == "stage" and len(a) == 3:
        return stage(a[1], a[2])
    if len(a) < 2 or a[0] not in ("fetch", "draw", "summary"):
        sys.exit(__doc__)
    {"fetch": fetch, "draw": draw, "summary": summary}[a[0]](a[1])


if __name__ == "__main__":
    main(sys.argv[1:])
