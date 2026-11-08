#!/usr/bin/env python3
"""ssd_film: the SSD report as a forty-second film, drawn from the report's own numbers.

    python3 tools/report/ssd_film.py film [OUT.mp4]      every frame, then the film (docs/calber-disks/film.mp4)
    python3 tools/report/ssd_film.py still T OUT.png     the frame at T seconds, to look at one

The film and the report are one argument in two media: the film's numbers are read from
docs/calber-disks/summary.json and docs/network/data, the same files the report's figures are drawn from,
and each scene names the report section it is.

EVERY FRAME IS A FUNCTION OF ITS TIME. Nothing accumulates from frame to frame: the thirteen layouts are
thirteen boxes whose place, size, colour and words are keyframed, and a frame interpolates between the two
keyframes around it with an easing curve. So a box can be a card, then a row of a list, then a bar of one
chart and a bar of the next, and the eye follows it the whole way -- the tween is the explanation. A camera,
keyframed the same way, does the zooms. Frames are SVG, rasterised by librsvg eight at a time, joined by
FFmpeg. Plain Python; no package.
"""

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SUMMARY = os.path.join(ROOT, "docs", "calber-disks", "summary.json")
NETDATA = os.path.join(ROOT, "docs", "network", "data", "nfs")
W, H, FPS, LENGTH = 1920, 1080, 30, 40.0

BG, INK, DIM, FAINT, GRID = "#0e1013", "#ece9e1", "#9a978d", "#5b5952", "#24262b"
TECH = {"md": "#3987e5", "zfs": "#e2662f", "btrfs": "#1fa97a", "one": "#a3a197"}
WIN, AMBER = "#2ec95c", "#f2b33d"
SANS, MONO, SERIF = "Avenir Next", "Menlo", "Iowan Old Style"

NAMES = {"single": "one disk", "pair-md": "md mirror of 2", "pair-zfs": "ZFS mirror of 2", "pair-btrfs": "btrfs mirror of 2",
         "md10": "md RAID10 · xfs", "md10-ext4": "md RAID10 · ext4", "md0": "md RAID0 · xfs", "md10-4+2spare": "md RAID10, 2 spares",
         "btrfs10": "btrfs RAID10", "zfs-3x2": "ZFS 3 mirrors of 2", "zfs-2x3": "ZFS 2 mirrors of 3",
         "zfs-2x2+spare+l2arc": "ZFS 2×2 + spare + cache", "zfs-2x2+slog+l2arc": "ZFS 2×2 + log + cache"}
ORDER = ["single", "pair-md", "pair-zfs", "pair-btrfs", "md10", "md10-ext4", "md0", "md10-4+2spare", "btrfs10",
         "zfs-3x2", "zfs-2x3", "zfs-2x2+spare+l2arc", "zfs-2x2+slog+l2arc"]


def tech(n):
    return "one" if n == "single" else "zfs" if "zfs" in n else "btrfs" if "btrfs" in n else "md"


# ---- easing and tweening ---------------------------------------------------------------------------------

def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def smooth(p):          # the in-and-out every move uses: slow away, slow arrival
    p = clamp(p)
    return p * p * p * (p * (p * 6 - 15) + 10)


def back(p, s=1.6):     # a little overshoot, for things that arrive
    p = clamp(p) - 1
    return p * p * ((s + 1) * p + s) + 1


def seg(t, a, b, ease=smooth):
    return ease((t - a) / (b - a)) if b > a else float(t >= b)


def lerp(a, b, p):
    return a + (b - a) * p


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(c1, c2, p):
    a, b = hexrgb(c1), hexrgb(c2)
    return "#%02x%02x%02x" % tuple(int(round(lerp(x, y, clamp(p)))) for x, y in zip(a, b))


class Track:
    """A value keyframed in time; between two keys it moves on the easing curve, outside them it holds."""

    def __init__(self, keys):
        self.keys = sorted(keys, key=lambda k: k[0])

    def at(self, t):
        ks = self.keys
        if t <= ks[0][0]:
            return ks[0][1]
        for (t0, v0), (t1, v1) in zip(ks, ks[1:]):
            if t <= t1:
                p = smooth((t - t0) / (t1 - t0)) if t1 > t0 else 1.0
                if isinstance(v0, str) and v0.startswith("#"):
                    return mix(v0, v1, p)
                if isinstance(v0, (int, float)) and isinstance(v1, (int, float)):
                    return lerp(v0, v1, p)
                return v1 if p >= 0.5 else v0
        return ks[-1][1]


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=34, fill=INK, anchor="start", weight=400, family=SANS, opacity=1.0, extra=""):
    if opacity <= 0.003:
        return ""
    return ('<text x="%.1f" y="%.1f" font-family="%s" font-size="%.1f" font-weight="%d" fill="%s" fill-opacity="%.3f" '
            'text-anchor="%s"%s>%s</text>') % (x, y, family, size, weight, fill, clamp(opacity), anchor, extra, esc(s))


def appear(t, a, b, fade=0.45):
    """Opacity of a thing shown from a to b: in over `fade` seconds, out over the same."""
    return min(seg(t, a, a + fade), 1 - seg(t, b - fade, b))


# ---- the data ----------------------------------------------------------------------------------------------

def load():
    s = json.load(open(SUMMARY))
    L = s["layouts"]
    d = {
        "find": {n: L[n].get("find_s") for n in ORDER},
        "rand": {n: L[n].get("rand-read") for n in ORDER},
        "score": {n: s["scores"]["Blu-ray working disk"].get(n) for n in ORDER},
        "swap": s["scores"]["swap"],
        "winners": s["winners"],
    }
    # the share's numbers, from the network report's own data
    runs = {}
    if os.path.isdir(NETDATA):
        for f in sorted(os.listdir(NETDATA)):
            if f.endswith(".json") and "-run-" in f:
                r = json.load(open(os.path.join(NETDATA, f)))
                runs[r["label"]] = r
    def tree(lab, key):
        r = runs.get(lab)
        return ((r or {}).get("tests", {}).get("tree", {}).get(key) or {}).get("per_s")
    def big(lab, key):
        r = runs.get(lab)
        return ((r or {}).get("tests", {}).get(key) or {}).get("MBps")
    d["share"] = {"local_make": tree("calber-local", "make") or 40700, "linux_make": tree("xinanjiang-nfs-sync", "make") or 147,
                  "mac_make": tree("mac-nfs-sync-default", "make") or 39, "local_read": big("calber-local", "seqR") or 1851,
                  "wire": big("xinanjiang-nfs-sync", "seqR") or 117, "linux_async": tree("xinanjiang-nfs-async", "make") or 803}
    return d


# ---- the thirteen boxes ---------------------------------------------------------------------------------------

# Where each box stands in each state. A state is (x, y, w, h); words and colour are keyed alongside.
GRID = {}
for i, n in enumerate(ORDER):
    r, c = divmod(i, 5)
    cols = 5 if r < 2 else 3
    x0 = (W - (cols * 330 + (cols - 1) * 26)) / 2
    GRID[n] = (x0 + c * 356, 250 + r * 196, 330, 164)

LIST = {n: (90, 168 + i * 62, 430, 50) for i, n in enumerate(ORDER)}

BAR_X, BAR_W, ROW, TOP = 640, 1060, 62, 168


def bars(values, lower_better=False, top=None):
    ranked = sorted((n for n in ORDER if values.get(n) is not None), key=lambda n: values[n], reverse=not lower_better)
    top = top or max(values[n] for n in ranked)
    out = {}
    for i, n in enumerate(ranked):
        out[n] = (BAR_X, TOP + i * ROW, max(6.0, BAR_W * values[n] / top), 46)
    return out, ranked


def build(d):
    """The keyframes: every box's place, colour, words, and the camera's, over the whole film."""
    find_pos, find_rank = bars(d["find"], lower_better=True)
    rand_pos, rand_rank = bars(d["rand"])
    score_pos, score_rank = bars(d["score"])
    win = d["winners"]["Blu-ray working disk"]
    boxes = {}
    for i, n in enumerate(ORDER):
        pop = 4.9 + i * 0.17                        # the cards arrive one after another
        sweep = 11.9 + i * 0.32                     # the suite runs down the list
        # Each move leaves a beat after the box before it (a lag, as 3Blue1Brown's animations peel objects off
        # one by one): thirteen boxes moving at once pile up mid-flight, and staggered they read as a procession.
        g0 = 10.75 + i * 0.05                                   # card to list, in list order
        b0 = 16.55 + find_rank.index(n) * 0.05                  # list to bars, in the bars' order
        r0 = 22.25 + rand_rank.index(n) * 0.035                 # one chart to the next, in the new order
        s0 = 25.85 + score_rank.index(n) * 0.035                # after the last chart's header and values have gone
        k = lambda key: [(pop, GRID[n][key]), (g0, GRID[n][key]), (g0 + 0.8, LIST[n][key]), (b0, LIST[n][key]),
                         (b0 + 0.9, find_pos[n][key]), (r0, find_pos[n][key]), (r0 + 0.85, rand_pos[n][key]),
                         (s0, rand_pos[n][key]), (s0 + 0.85, score_pos[n][key])]
        col = TECH[tech(n)]
        boxes[n] = {
            "x": Track(k(0)), "y": Track(k(1)), "w": Track(k(2)), "h": Track(k(3)),
            "pop": pop, "sweep": sweep,
            "card": Track([(pop, 1.0), (g0, 1.0), (g0 + 0.45, 0.0)]),        # the diagram inside a card
            "barness": Track([(b0, 0.0), (b0 + 0.9, 1.0)]),                   # 0: a box with its name in it; 1: a bar, name beside
            "fill": Track([(pop, col), (27.2, col)] + ([(28.0, WIN)] if n == win else [(28.0, col)])),
            "alpha": Track([(pop, 1.0), (27.2, 1.0), (28.0, 1.0 if n == win else 0.28), (31.2, 1.0 if n == win else 0.28),
                            (32.0, 0.0)]),
        }
    camera = Track([(0, (W / 2, H / 2, 1.0)), (7.6, (W / 2, H / 2, 1.0)), (10.9, (W / 2, H / 2 + 6, 1.045)),
                    (11.9, (W / 2, H / 2, 1.0)), (19.2, (W / 2, H / 2, 1.0)), (20.2, (806, 262, 2.35)),
                    (21.5, (806, 262, 2.35)), (22.4, (W / 2, H / 2, 1.0))])
    return boxes, camera, {"find": find_rank, "rand": rand_rank, "score": score_rank}


def cam_at(camera, t):
    ks = camera.keys
    if t <= ks[0][0]:
        return ks[0][1]
    for (t0, v0), (t1, v1) in zip(ks, ks[1:]):
        if t <= t1:
            p = smooth((t - t0) / (t1 - t0))
            # zoom in log space: a camera that doubles in equal time feels even, not lurching
            s = math.exp(lerp(math.log(v0[2]), math.log(v1[2]), p))
            return (lerp(v0[0], v1[0], p), lerp(v0[1], v1[1], p), s)
    return ks[-1][1]


# ---- what each box draws ---------------------------------------------------------------------------------------

LAYOUT_DIAGRAM = {
    # disks used (index 0..5), how they are joined: ("mirror", [..]) groups, "stripe" over the groups, extras
    "single": {"groups": [[0]], "stripe": False},
    "pair-md": {"groups": [[4, 5]], "stripe": False},
    "pair-zfs": {"groups": [[0, 1]], "stripe": False},
    "pair-btrfs": {"groups": [[2, 3]], "stripe": False},
    "md10": {"groups": [[0, 1], [2, 3], [4, 5]], "stripe": True},
    "md10-ext4": {"groups": [[0, 1], [2, 3], [4, 5]], "stripe": True},
    "md0": {"groups": [[0], [1], [2], [3], [4], [5]], "stripe": True},
    "md10-4+2spare": {"groups": [[0, 1], [2, 3]], "stripe": True, "spare": [4, 5]},
    "btrfs10": {"groups": [[0, 1], [2, 3], [4, 5]], "stripe": True},
    "zfs-3x2": {"groups": [[0, 1], [2, 3], [4, 5]], "stripe": True},
    "zfs-2x3": {"groups": [[0, 1, 2], [3, 4, 5]], "stripe": True},
    "zfs-2x2+spare+l2arc": {"groups": [[0, 1], [2, 3]], "stripe": True, "spare": [4], "cache": [5]},
    "zfs-2x2+slog+l2arc": {"groups": [[0, 1], [2, 3]], "stripe": True, "log": [4], "cache": [5]},
}


def diagram(n, x, y, w, col, a):
    """Six small disks under a card's name: the ones in use filled, mirrors tied below, a stripe drawn over."""
    if a <= 0.01:
        return ""
    spec = LAYOUT_DIAGRAM[n]
    dw, gap = 34, 12
    x0 = x + (w - (6 * dw + 5 * gap)) / 2
    out = []
    used = {i for g in spec["groups"] for i in g}
    roles = {}
    for key, word in (("spare", "S"), ("cache", "C"), ("log", "L")):
        for i in spec.get(key, []):
            roles[i] = word
    for i in range(6):
        dx = x0 + i * (dw + gap)
        if i in used:
            out.append('<rect x="%.1f" y="%.1f" width="%d" height="44" rx="6" fill="%s" fill-opacity="%.2f"/>' % (dx, y, dw, col, 0.9 * a))
        elif i in roles:
            out.append('<rect x="%.1f" y="%.1f" width="%d" height="44" rx="6" fill="none" stroke="%s" stroke-width="2" stroke-dasharray="5 4" stroke-opacity="%.2f"/>'
                       % (dx, y, dw, col, a))
            out.append(text(dx + dw / 2, y + 29, roles[i], 18, col, "middle", 600, opacity=a))
        else:
            out.append('<rect x="%.1f" y="%.1f" width="%d" height="44" rx="6" fill="none" stroke="%s" stroke-width="1.5" stroke-opacity="%.2f"/>'
                       % (dx, y, dw, FAINT, 0.7 * a))
    for g in spec["groups"]:
        if len(g) > 1:              # a mirror: its disks tied underneath
            a0 = x0 + g[0] * (dw + gap) + dw / 2
            a1 = x0 + g[-1] * (dw + gap) + dw / 2
            out.append('<path d="M%.1f %.1f v10 H%.1f v-10" fill="none" stroke="%s" stroke-width="2.5" stroke-opacity="%.2f"/>'
                       % (a0, y + 50, a1, INK, 0.75 * a))
    if spec["stripe"]:              # a stripe: one bar across every group
        g0, g1 = spec["groups"][0][0], spec["groups"][-1][-1]
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="5" rx="2.5" fill="%s" fill-opacity="%.2f"/>'
                   % (x0 + g0 * (dw + gap), y - 13, (g1 - g0) * (dw + gap) + dw, INK, 0.75 * a))
    return "".join(out)


def value_words(stage, n, d):
    if stage == "find":
        return "%.2f s" % d["find"][n]
    if stage == "rand":
        return "{:,}".format(int(d["rand"][n]))
    if stage == "score":
        return "%.2f×" % d["score"][n]
    return ""


def box(t, n, b, d):
    x, y, w, h = b["x"].at(t), b["y"].at(t), b["w"].at(t), b["h"].at(t)
    if t < b["pop"]:
        return ""
    grow = back((t - b["pop"]) / 0.55)
    a = b["alpha"].at(t)
    if a <= 0.01:
        return ""
    col = b["fill"].at(t)
    bar = b["barness"].at(t)
    card = b["card"].at(t)
    cx, cy = x + w / 2, y + h / 2
    out = ['<g opacity="%.3f" transform="translate(%.1f %.1f) scale(%.4f) translate(%.1f %.1f)">' % (a, cx, cy, grow, -cx, -cy)]
    # the body: a card's outline and tint, turning into a solid bar
    fill_op = lerp(0.13, 0.95, bar)
    out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-width="%.1f" stroke-opacity="%.3f"/>'
               % (x, y, w, h, lerp(12, 6, bar), col, fill_op, col, 2.0, 1 - bar))
    if n == d["winners"]["Blu-ray working disk"] and t > 27.4:
        g = seg(t, 27.4, 28.4) * (0.75 + 0.25 * math.sin((t - 27.4) * 4.0))
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="8" fill="none" stroke="%s" stroke-width="10" stroke-opacity="%.3f" filter="url(#glow)"/>'
                   % (x - 3, y - 3, w + 6, h + 6, WIN, 0.55 * g))
    # the name: inside a card or a list row, beside a bar
    name = NAMES[n]
    inside, beside = clamp(1 - bar * 2.5), clamp(bar * 2.5 - 1.5)     # one name at a time, never two
    # A bar's name dims while its bar is on the move and returns as it lands: in a re-sort the bars cross, and
    # names crossing at full strength are what clutters, not the bars.
    moving = clamp(abs(b["y"].at(t + 0.06) - b["y"].at(t - 0.06)) / 24.0)
    beside *= 1 - 0.7 * moving
    if inside > 0.001:
        size = lerp(30, 26, 1 - card)
        ny = y + (36 if card > 0.5 else h / 2 + 9)
        out.append(text(x + (w / 2 if card > 0.5 else 18), ny, name, size, INK, "middle" if card > 0.5 else "start", 600, opacity=inside))
    if beside > 0.001:
        out.append(text(BAR_X - 18, y + h / 2 + 9, name, 26, INK, "end", 600, opacity=beside))
    out.append(diagram(n, x, y + 78, w, col, card))
    # the bar's value, crossfading as the chart changes under it
    # each chart's values arrive once its bars have landed, and leave before the bars move again
    for stage, t0, t1 in (("find", 17.9, 22.5), ("rand", 23.25, 25.75), ("score", 26.95, 40.0)):
        op = appear(t, t0, t1, 0.4) * bar
        if op > 0.01:
            out.append(text(x + w + 14, y + h / 2 + 10, value_words(stage, n, d), 26, INK, "start", 500, MONO, op))
    out.append("</g>")
    return "".join(out)


# ---- the scenes' other things ------------------------------------------------------------------------------------

def disk_icon(x, y, w, h, p, label_op):
    """A disk drawn on: its outline traced, then filled, then labelled."""
    perim = 2 * (w + h)
    out = ['<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="10" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-width="3" '
           'stroke-dasharray="%.1f %.1f" stroke-dashoffset="%.1f"/>' % (x, y, w, h, TECH["md"], 0.18 * seg(p, 0.6, 1.0, lambda q: q),
                                                                        INK, perim, perim, perim * (1 - clamp(p / 0.7)))]
    for k in range(3):   # the label's lines, as on a real drive
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="4" rx="2" fill="%s" fill-opacity="%.3f"/>'
                   % (x + 22, y + 40 + k * 16, (w - 44) * (1 - k * 0.25), INK, 0.35 * seg(p, 0.7, 1.0)))
    out.append(text(x + w / 2, y + h + 44, "480 GB", 28, DIM, "middle", 500, MONO, label_op))
    return "".join(out)


def title_scene(t, d):
    out = []
    op = 1 - seg(t, 4.0, 4.7)
    if op <= 0:
        return ""
    reveal = seg(t, 0.2, 1.5)
    out.append('<clipPath id="tclip"><rect x="0" y="0" width="%.1f" height="%d"/></clipPath>' % (260 + 1400 * reveal, H))
    out.append('<g clip-path="url(#tclip)">%s</g>' % text(W / 2, 330, "Six cheap SSDs", 104, INK, "middle", 400, SERIF, op))
    for i in range(6):
        p = seg(t, 0.7 + i * 0.16, 1.9 + i * 0.16, lambda q: q)
        x = W / 2 - 3 * 220 + i * 220 + 20
        y = 470 + 30 * (1 - smooth(p))
        out.append('<g opacity="%.3f">%s</g>' % (op * clamp(p * 3), disk_icon(x, y, 180, 150, p, seg(t, 1.9 + i * 0.1, 2.5 + i * 0.1))))
    out.append(text(W / 2, 800, "and thirteen ways to join them", 46, INK, "middle", 400, SERIF, op * seg(t, 2.4, 3.1)))
    out.append(text(W / 2, 870, "calber · 7 November 2026 · a working disk for a Blu-ray writer", 26, DIM, "middle", 500, SANS, op * seg(t, 2.8, 3.5)))
    return "".join(out)


def header(t, words, a, b, sub=None):
    op = appear(t, a, b, 0.5)
    if op <= 0:
        return ""
    dy = 18 * (1 - seg(t, a, a + 0.6))
    out = text(90, 104 + dy, words, 56, INK, "start", 400, SERIF, op)
    if sub:
        out += text(92, 146 + dy, sub, 26, DIM, "start", 500, SANS, op * seg(t, a + 0.3, a + 0.9))
    return out


def legend(t, a, b):
    op = appear(t, a, b)
    if op <= 0:
        return ""
    out = []
    x = W - 90
    for word, key in (("one disk", "one"), ("btrfs", "btrfs"), ("ZFS", "zfs"), ("mdadm", "md")):
        wd = 22 + len(word) * 15
        x -= wd + 30
        out.append('<rect x="%.1f" y="88" width="18" height="18" rx="4" fill="%s" fill-opacity="%.3f"/>' % (x, TECH[key], op))
        out.append(text(x + 28, 104, word, 24, DIM, "start", 500, SANS, op))
    return "".join(out)


def caption(t, words, a, b, y=1010):
    op = appear(t, a, b, 0.5)
    return text(W / 2, y, words, 30, DIM, "middle", 500, SANS, op) if op > 0 else ""


SUITE = ["8 GB written, then read back", "two streams at once", "4K blocks at random, queue 32",
         "writes that must reach the disk", "100,000 files: make · find · ls -lR · sort · delete"]


def suite_scene(t, d, boxes):
    op = appear(t, 11.9, 16.9)
    if op <= 0:
        return ""
    out = []
    x0, y0 = 660, 250
    k = int(clamp((t - 11.9) / 0.32, 0, 12.999))     # which layout the suite is on
    cur = ORDER[k]
    for i, s in enumerate(SUITE):
        y = y0 + i * 132
        # each station lights as the run passes through it, every layout in turn
        phase = ((t - 11.9) / 0.32) % 1.0
        lit = 1.0 if int(phase * 5) == i and t < 16.1 else 0.0
        box_a = op * seg(t, 12.0 + i * 0.12, 12.5 + i * 0.12)
        out.append('<rect x="%d" y="%d" width="1060" height="96" rx="14" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-width="2" stroke-opacity="%.3f"/>'
                   % (x0, y, TECH[tech(cur)], 0.08 + 0.22 * lit, FAINT if not lit else TECH[tech(cur)], box_a))
        out.append(text(x0 + 40, y + 60, s, 34, INK, "start", 500, SANS, box_a))
        if i < len(SUITE) - 1:
            out.append('<path d="M%d %d v28" stroke="%s" stroke-width="3" stroke-opacity="%.3f"/>' % (x0 + 60, y + 98, FAINT, box_a))
    # the cursor down the list: the layout being measured
    b = boxes[cur]
    if t < 16.1:
        out.append('<path d="M%.1f %.1f l22 -14 v28 z" fill="%s" fill-opacity="%.3f"/>' % (LIST[cur][0] + LIST[cur][2] + 16, LIST[cur][1] + 25 - 0, INK, op))
    return "".join(out)


def find_callout(t, d, ranks):
    op = appear(t, 19.5, 21.7, 0.35)
    if op <= 0:
        return ""
    # the three fastest are the three on ext4: tag them, and say it beside them, inside the camera's frame
    y0 = TOP + 3 * ROW - 8
    out = ['<path d="M%d %d h560" stroke="%s" stroke-width="2" stroke-dasharray="6 5" stroke-opacity="%.3f"/>' % (BAR_X - 200, y0, WIN, op)]
    for i in range(3):
        out.append(text(BAR_X + 172, TOP + i * ROW + 32, "ext4", 24, WIN, "start", 700, SANS, op))
    out.append(text(BAR_X + 246, TOP + 30, "0.04–0.05 s on ext4", 21, INK, "start", 600, SANS, op))
    out.append(text(BAR_X + 246, TOP + ROW + 30, "0.26–1.26 s on xfs, ZFS, btrfs", 21, DIM, "start", 500, SANS, op))
    return "".join(out)


def zfs_callout(t, d):
    op = appear(t, 23.2, 25.6, 0.4)
    if op <= 0:
        return ""
    x, y = 1180, 820
    out = [text(x, y - 70, "Why ZFS sinks: it reads a whole record", 28, INK, "start", 600, SANS, op),
           text(x, y - 36, "128K", 22, DIM, "start", 500, MONO, op)]
    full = 560
    out.append('<rect x="%d" y="%d" width="%d" height="40" rx="6" fill="%s" fill-opacity="%.3f"/>' % (x, y - 20, full, TECH["zfs"], 0.35 * op))
    sliver = full * 4 / 128
    pulse = 0.6 + 0.4 * math.sin((t - 23.2) * 6)
    out.append('<rect x="%.1f" y="%d" width="%.1f" height="40" rx="3" fill="%s" fill-opacity="%.3f"/>' % (x + 220, y - 20, sliver, INK, op * pulse))
    out.append(text(x + 220 + sliver / 2, y + 52, "the 4K asked for", 20, INK, "middle", 500, SANS, op))
    out.append(text(x, y + 92, "a 4K read costs 128K: 32 times the work", 22, DIM, "start", 500, SANS, op))
    return "".join(out)


def score_extras(t, d):
    out = []
    op = appear(t, 26.0, 31.4)
    if op > 0:
        x1 = BAR_X + BAR_W * 1.0 / max(v for v in d["score"].values() if v)
        out.append('<path d="M%.1f %d V%d" stroke="%s" stroke-width="2" stroke-dasharray="7 6" stroke-opacity="%.3f"/>' % (x1, TOP - 20, TOP + 13 * ROW, INK, 0.6 * op))
        out.append(text(x1, TOP - 30, "one disk = 1×", 22, DIM, "middle", 500, SANS, op))
    # three verdicts arrive
    verdicts = [("Blu-ray working disk", NAMES[d["winners"]["Blu-ray working disk"]], "%.2f×" % d["score"][d["winners"]["Blu-ray working disk"]], WIN),
                ("swap", NAMES[d["winners"]["swap"]], "%.2f×" % d["swap"][d["winners"]["swap"]], TECH["md"]),
                ("NFS share", NAMES[d["winners"]["NFS share"]], "the wire decides", AMBER)]
    for i, (use, who, num, col) in enumerate(verdicts):
        a = appear(t, 28.6 + i * 0.35, 31.6, 0.4)
        if a <= 0:
            continue
        x = 1290
        y = 600 + i * 120 + 26 * (1 - seg(t, 28.6 + i * 0.35, 29.2 + i * 0.35))
        out.append('<rect x="%d" y="%.1f" width="540" height="100" rx="12" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-width="2" stroke-opacity="%.3f"/>'
                   % (x, y, BG, 0.92 * a, col, a))
        out.append(text(x + 24, y + 36, use, 22, DIM, "start", 600, SANS, a))
        out.append(text(x + 516, y + 36, num, 24, col, "end", 600, MONO, a))
        out.append(text(x + 24, y + 78, who, 30, INK, "start", 600, SANS, a))
    return "".join(out)


def wire_scene(t, d):
    op = appear(t, 31.9, 37.9)
    if op <= 0:
        return ""
    s = d["share"]
    out = []
    # calber's array, then the funnel into one 1 GbE wire, then the clients
    ax, ay = 140, 330
    out.append('<rect x="%d" y="%d" width="420" height="230" rx="16" fill="%s" fill-opacity="%.3f" stroke="%s" stroke-width="3" stroke-opacity="%.3f"/>'
               % (ax, ay, WIN, 0.16 * op, WIN, op))
    out.append(text(ax + 210, ay + 62, "calber", 30, DIM, "middle", 600, SANS, op))
    out.append(text(ax + 210, ay + 112, NAMES[d["winners"]["Blu-ray working disk"]], 34, INK, "middle", 600, SANS, op))
    out.append(text(ax + 210, ay + 178, "{:,.0f} MB/s".format(s["local_read"]), 40, WIN, "middle", 600, MONO, op))
    # the pipe narrows: the tween of its width is the point
    narrow = seg(t, 32.6, 34.0)
    wide, thin = 200, 200 * s["wire"] / s["local_read"]
    x0, x1, x2 = ax + 420, 900, 1500
    hw = lerp(wide, thin, narrow) / 2
    cy = ay + 115
    out.append('<path d="M%d %.1f H%d C%d %.1f %d %.1f %d %.1f H%d" fill="none" stroke="%s" stroke-width="2.5" stroke-opacity="%.3f"/>'
               % (x0, cy - wide / 2, x1, x1 + 60, cy - wide / 2, x1 + 60, cy - hw, x1 + 120, cy - hw, x2, DIM, op))
    out.append('<path d="M%d %.1f H%d C%d %.1f %d %.1f %d %.1f H%d" fill="none" stroke="%s" stroke-width="2.5" stroke-opacity="%.3f"/>'
               % (x0, cy + wide / 2, x1, x1 + 60, cy + wide / 2, x1 + 60, cy + hw, x1 + 120, cy + hw, x2, DIM, op))
    # the data, flowing: dots that keep their place in the stream, so they pack where it narrows
    for i in range(46):
        u = ((t - 31.9) * 0.42 + i / 46.0) % 1.0
        px = lerp(x0, x2, u)
        lane = ((i * 37) % 11) / 10.0 - 0.5
        half = wide / 2 if px < x1 else (hw if px > x1 + 120 else lerp(wide / 2, hw, smooth((px - x1) / 120)))
        out.append('<circle cx="%.1f" cy="%.1f" r="4.5" fill="%s" fill-opacity="%.3f"/>' % (px, cy + lane * 2 * max(half - 8, 1), INK, 0.75 * op))
    out.append(text(x1 + 300, cy - 70, "1 GbE: {:,.0f} MB/s".format(s["wire"]), 34, AMBER, "middle", 600, MONO, op * seg(t, 33.4, 34.0)))
    out.append(text(x1 + 300, cy + 90, "every client, large files", 24, DIM, "middle", 500, SANS, op * seg(t, 33.6, 34.2)))
    for i, who in enumerate(["the Mac", "the VM", "nasser", "xinanjiang"]):
        out.append(text(x2 + 40, cy - 66 + i * 44, who, 28, INK, "start", 500, SANS, op * seg(t, 33.0 + i * 0.1, 33.6 + i * 0.1)))
    # small files, on a log scale: the share's real cost
    b = appear(t, 34.6, 37.9, 0.4)
    if b > 0:
        rows = [("calber, on its own disks", s["local_make"], WIN), ("a Linux client, async share", s["linux_async"], TECH["md"]),
                ("a Linux client, sync share", s["linux_make"], mix(TECH["md"], BG, 0.45)), ("the Mac, sync share", s["mac_make"], AMBER)]
        out.append(text(140, 690, "Small files made a second", 30, INK, "start", 600, SANS, b))
        for i, (who, v, col) in enumerate(rows):
            y = 716 + i * 62
            grow = seg(t, 34.8 + i * 0.2, 35.8 + i * 0.2)
            wd = 1100 * math.log10(v) / math.log10(s["local_make"]) * grow
            out.append(text(540, y + 34, who, 24, DIM, "end", 500, SANS, b))
            out.append('<rect x="560" y="%d" width="%.1f" height="42" rx="6" fill="%s" fill-opacity="%.3f"/>' % (y, wd, col, 0.9 * b))
            out.append(text(574 + wd, y + 31, "{:,.0f}".format(v * grow), 26, INK, "start", 600, MONO, b))
        out.append(text(560, 1000, "log scale · sync: each change waits for 8 disk flushes · async answers first, and a crash can lose the last seconds",
                        21, FAINT, "start", 500, SANS, b))
    return "".join(out)


def end_scene(t, d):
    op = seg(t, 37.9, 38.6)
    if op <= 0:
        return ""
    w = NAMES[d["winners"]["Blu-ray working disk"]]
    out = [text(W / 2, 380, w, 96, WIN, "middle", 400, SERIF, op),
           text(W / 2, 470, "1.44 TB · survives a lost disk · finds 100,000 files in 0.04 s", 32, INK, "middle", 500, SANS, op * seg(t, 38.2, 38.8)),
           text(W / 2, 530, "large files over the share · small work at home", 32, DIM, "middle", 500, SANS, op * seg(t, 38.4, 39.0)),
           text(W / 2, 700, "Lab reports: Six Cheap SSDs, Thirteen Ways · The Share and the Wire", 26, FAINT, "middle", 500, SANS, op * seg(t, 38.7, 39.3))]
    return "".join(out)


DEFS = ('<defs><filter id="glow" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="9"/></filter></defs>')


def frame(t, d, boxes, camera, ranks):
    cx, cy, s = cam_at(camera, t)
    world = []
    world.append(title_scene(t, d))
    world.append(header(t, "The opponents", 4.6, 11.4, "the same six disks, built thirteen ways"))
    world.append(legend(t, 4.8, 11.4))
    world.append(caption(t, "each one built, measured with the same suite, and erased", 7.4, 11.4))
    world.append(header(t, "The test", 11.9, 16.9, "fifty minutes, every layout in turn; then the finalists again"))
    world.append(suite_scene(t, d, boxes))
    world.append(header(t, "Find 100,000 files", 17.0, 22.4, "seconds, cold cache · shorter is better"))
    world.append(header(t, "4K blocks read at random", 22.6, 25.8, "a second · longer is better"))
    world.append(header(t, "The selection: a Blu-ray working disk", 26.0, 31.6, "listing, sorting, reads, writes, and a lost disk survived · × one disk"))
    world.append(header(t, "Then the wire", 31.9, 37.9, "the winner shared over NFS, measured from four machines"))
    world.append(find_callout(t, d, ranks))
    world.append(zfs_callout(t, d))
    world.append(score_extras(t, d))
    for n in ORDER:
        world.append(box(t, n, boxes[n], d))
    world.append(wire_scene(t, d))
    world.append(end_scene(t, d))
    body = "".join(world)
    tr = "translate(%.2f %.2f) scale(%.5f) translate(%.2f %.2f)" % (W / 2, H / 2, s, -cx, -cy)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">%s'
            '<rect width="%d" height="%d" fill="%s"/><g transform="%s">%s</g></svg>') % (W, H, W, H, DEFS, W, H, BG, tr, body)


def render(svg, png):
    subprocess.run(["rsvg-convert", "-w", str(W), "-h", str(H), "-o", png], input=svg.encode(), check=True)


def main(a):
    d = load()
    boxes, camera, ranks = build(d)
    if a[:1] == ["still"] and len(a) == 3:
        render(frame(float(a[1]), d, boxes, camera, ranks), a[2])
        print(a[2])
        return
    if a[:1] == ["film"]:
        out = a[1] if len(a) > 1 else os.path.join(ROOT, "docs", "calber-disks", "film.mp4")
        tmp = tempfile.mkdtemp(prefix="ssd-film-")
        n = int(LENGTH * FPS)
        def one(i):
            render(frame(i / FPS, d, boxes, camera, ranks), os.path.join(tmp, "f%05d.png" % i))
        with ThreadPoolExecutor(os.cpu_count() or 4) as ex:
            list(ex.map(one, range(n)))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(tmp, "f%05d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "slow", "-movflags", "+faststart", out], check=True)
        poster = os.path.splitext(out)[0] + "-poster.png"
        shutil.copy(os.path.join(tmp, "f%05d.png" % int(29.6 * FPS)), poster)
        shutil.rmtree(tmp)
        print("%s: %d frames, %.0f s; poster %s" % (out, n, LENGTH, poster))
        return
    sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
