#!/usr/bin/env python3
"""net-report: the share-and-wire lab report's data and figures, from what was measured.

    python3 net-report.py fetch      every machine's NFS results, and this Mac's network results, into docs/network/data
    python3 net-report.py draw       the map and the charts into docs/network/
    python3 net-report.py table      the report's tables, as Markdown, on stdout

The map is drawn from the measures, not by hand, so a machine added later is placed by its own numbers: its link
speed from the inventory, its rate alone from the star, and any link it shares from the fan-in tests. What the
measures cannot see -- whether the core is one switch or several joined at 10 GbE -- the map draws as one box and
says so in its caption.
"""

import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs", "network")
DATA = os.path.join(DOCS, "data")
NET = os.path.expanduser("~/.cache/orrery-bench/net")
NFS = os.path.expanduser("~/.cache/orrery-bench/nfs")
CLIENTS = {"calber": "~/.cache/orrery-bench/nfs/", "user@192.168.8.121": "~/.cache/orrery-bench/nfs/",
           "user@192.168.8.217": "~/.cache/orrery-bench/nfs/", "user@192.168.64.39": "~/.cache/orrery-bench/nfs/"}

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module  # noqa: E402
DR = import_module("disk-report")      # its figure style, so the two reports' charts read as one set
STYLE, esc = DR.STYLE, DR.esc


def fetch():
    os.makedirs(os.path.join(DATA, "nfs"), exist_ok=True)
    os.makedirs(os.path.join(DATA, "net"), exist_ok=True)
    for f in os.listdir(NFS) if os.path.isdir(NFS) else []:
        shutil.copy2(os.path.join(NFS, f), os.path.join(DATA, "nfs", f))
    for f in os.listdir(NET) if os.path.isdir(NET) else []:
        shutil.copy2(os.path.join(NET, f), os.path.join(DATA, "net", f))
    for host, path in CLIENTS.items():
        # A machine away is skipped: its results come with the next fetch.
        subprocess.run(["rsync", "-a", "-e", "ssh -o BatchMode=yes -o ConnectTimeout=6", "%s:%s" % (host, path),
                        os.path.join(DATA, "nfs") + "/"], capture_output=True)
    n = len(os.listdir(os.path.join(DATA, "nfs"))), len(os.listdir(os.path.join(DATA, "net")))
    print("docs/network/data: %d NFS results, %d network results" % n)


def load(kind_dir, prefix=None):
    d = os.path.join(DATA, kind_dir)
    out = []
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if f.endswith(".json") and (prefix is None or f.startswith(prefix)):
            out.append(json.load(open(os.path.join(d, f))))
    return out


def latest(kind):
    r = load("net", kind + "-")
    return r[-1] if r else None


# ---- the map ------------------------------------------------------------------------------------------------

def shared_groups(star):
    """Machines that halve each other sending to one hub sit behind one link. Two senders share when their sum is
    no more than one link's worth (10% over their faster self) and each kept under 70% of its rate alone."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            x = parent[x]
        return x
    for r in load("net", "fanin-"):
        s = [x for x in r["senders"] if r["Mbps"].get(x)]
        if len(s) != 2:
            continue
        a, b = s
        va, vb = r["Mbps"][a], r["Mbps"][b]
        alone_a, alone_b = star.get(a) or va, star.get(b) or vb
        if va + vb <= 1.1 * max(alone_a, alone_b) and va < 0.7 * alone_a and vb < 0.7 * alone_b:
            parent[find(a)] = find(b)
    groups = {}
    for x in parent:
        groups.setdefault(find(x), set()).add(x)
    return [g for g in groups.values() if len(g) > 1]


def speed_of(inv, name):
    for r in inv["hosts"].get(name, {}).get("links", []):
        if r["state"] == "up" and not r["wireless"] and r.get("speed"):
            return r["speed"]
    return None


def ip_of(inv, name):
    for r in inv["hosts"].get(name, {}).get("links", []):
        if r["state"] == "up" and not r["wireless"] and r.get("ip"):
            return r["ip"]
    return ""


def topology():
    inv, st = latest("inventory"), latest("star")
    if not inv:
        return None
    star = st["Mbps"] if st else {}
    hub = st["hub"] if st else None
    fan = [r for r in load("net", "fanin-") if len(r["senders"]) > 2]
    together = max(fan, key=lambda r: (len(r["senders"]), r.get("at", 0))) if fan else None   # the newest of the widest
    groups = shared_groups(star)
    behind = {x for g in groups for x in g}
    names = [n for n in inv["hosts"] if n != "vm" and "error" not in inv["hosts"][n]]
    fast = [n for n in names if (speed_of(inv, n) or 0) >= 10000]
    slow = [n for n in names if n not in fast and n not in behind]
    W = 960
    H = 500
    out = ['<svg viewBox="0 0 %d %d" role="img" aria-label="The home network, inferred from measures">' % (W, H),
           '<text x="0" y="14" class="t1" font-weight="600">The home network, as the measures show it</text>']

    def wire(x1, y1, x2, y2, speed):
        wdt = 4.5 if (speed or 0) >= 10000 else 2 if (speed or 0) >= 1000 else 1.2
        col = "var(--s-md)" if (speed or 0) >= 10000 else "var(--bad)" if (speed or 0) < 1000 else "var(--s-one)"
        dash = ' stroke-dasharray="4 3"' if (speed or 0) < 1000 else ""
        return '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="%s"%s/>' % (x1, y1, x2, y2, col, wdt, dash)

    def node(x, y, name, sub, sub2, w=108, sub3=None):
        h = 59 if sub3 else 46
        return ('<rect x="%d" y="%d" width="%d" height="%d" rx="5" fill="var(--surface)" stroke="var(--t3)"/>'
                '<text x="%d" y="%d" class="t1" text-anchor="middle" font-weight="600">%s</text>'
                '<text x="%d" y="%d" class="t2" text-anchor="middle">%s</text>'
                '<text x="%d" y="%d" class="t3" text-anchor="middle">%s</text>') % (
            x - w // 2, y, w, h, x, y + 14, esc(name), x, y + 27, esc(sub), x, y + 40, esc(sub2)) + (
            '<text x="%d" y="%d" class="t3" text-anchor="middle">%s</text>' % (x, y + 53, esc(sub3)) if sub3 else "")

    def rate(n):
        v = star.get(n)
        return ("%s Mb/s to %s" % ("{:,.0f}".format(v), hub)) if v else ("the hub" if n == hub else "")

    def words(sp):
        return "10 GbE" if sp and sp >= 10000 else "1 GbE" if sp and sp >= 1000 else ("%s Mb/s" % sp if sp else "?")
    # the core
    cx0, cx1, cy = 40, W - 40, 190
    out.append('<rect x="%d" y="%d" width="%d" height="40" rx="6" fill="var(--grid)" stroke="var(--t3)"/>' % (cx0, cy, cx1 - cx0))
    carried = sum(v for v in together["Mbps"].values() if v) if together else None
    out.append('<text x="%d" y="%d" class="t1" text-anchor="middle" font-weight="600">switching core: 10 GbE and 1 GbE ports</text>' % (W // 2, cy + 17))
    out.append('<text x="%d" y="%d" class="t2" text-anchor="middle">%s</text>' % (
        W // 2, cy + 32, ("carried %s Mb/s from %d machines at once: one switch, or switches joined at 10 GbE" % ("{:,.0f}".format(carried), len(together["senders"]))) if carried else "one switch, or switches joined at 10 GbE"))
    # the router, and the 10 GbE machines, above
    top = ["router"] + fast
    xs = [W // 2 - (len(top) - 1) * 80 + i * 160 for i in range(len(top))]
    for x, n in zip(xs, top):
        if n == "router":
            out.append(wire(x, 116, x, cy, 1000))
            out.append(node(x, 70, "router", "GL.iNet 192.168.8.1", "to the internet", 130))
        else:
            sp = speed_of(inv, n)
            out.append(wire(x, 116, x, cy, sp))
            out.append(node(x, 70, n, "%s · %s" % (words(sp), ip_of(inv, n)), rate(n), 140))
    # The 1 GbE machines below in two staggered rows; a shared link's machines take the last two slots, under a
    # small switch of their own, on a third row so their boxes clear the second.
    glen = max(2, len(groups[0])) if groups else 0
    nslots = len(slow) + glen
    step = (W - 80) / max(1, nslots)
    for i, n in enumerate(slow):
        x = int(40 + step * (i + 0.5))
        sp = speed_of(inv, n)
        y = 290 if i % 2 == 0 else 362
        out.append(wire(x, cy + 40, x, y, sp))
        if n == "mac":
            vm = star.get("vm")
            out.append(node(x, y, "this Mac", "%s · %s" % (words(sp), ip_of(inv, n)), rate(n), 152,
                            ("its VM, by NAT: %s Mb/s" % "{:,.0f}".format(vm)) if vm else "its VM, by NAT"))
        else:
            out.append(node(x, y, n, "%s · %s" % (words(sp), ip_of(inv, n)), rate(n), 118))
    for gi, g in enumerate(groups[:1]):
        g = sorted(g)
        x = int(40 + step * (len(slow) + glen / 2))
        out.append(wire(x, cy + 40, x, 300, 1000))
        out.append('<rect x="%d" y="300" width="150" height="30" rx="5" fill="var(--grid)" stroke="var(--t3)"/>' % (x - 75))
        out.append('<text x="%d" y="314" class="t1" text-anchor="middle" font-weight="600">small switch</text>' % x)
        out.append('<text x="%d" y="326" class="t2" text-anchor="middle">one 1 GbE link up, shared</text>' % x)
        for j, m in enumerate(g):
            gx = min(W - 62, max(62, int(x + (j - (len(g) - 1) / 2) * 128)))
            # down from the switch, across, and down to the machine: an elbow, so every link meets the switch
            sp = speed_of(inv, m)
            wdt = 2 if (sp or 0) >= 1000 else 1.2
            colr = "var(--s-one)" if (sp or 0) >= 1000 else "var(--bad)"
            out.append('<path d="M%d 330 V392 H%d V430" fill="none" stroke="%s" stroke-width="%s"/>' % (x, gx, colr, wdt))
            out.append(node(gx, 430, m, "%s · %s" % (words(speed_of(inv, m)), ip_of(inv, m)), rate(m), 122))
    out.append("</svg>")
    cap = ("Drawn from the measures. A line's weight is its link's speed: blue 10 GbE, gray 1 GbE, red dashed slower. "
           "Under each machine, its rate alone to %s. Machines that halved each other sending at once are drawn behind "
           "a switch of their own; the core may be one switch or several joined at 10 GbE, which no rate here can tell apart." % hub)
    return DR.figure("".join(out), cap)


SHOWN = {"mac": "this Mac", "vm": "its VM (NAT)"}


def star_chart():
    st, inv = latest("star"), latest("inventory")
    if not st:
        return None
    rows = sorted(((n, v) for n, v in st["Mbps"].items() if v), key=lambda r: -r[1])
    W, L, R, T = 880, 120, 90, 30
    H = T + 26 * len(rows) + 40
    top = max(v for _, v in rows)
    import math
    lo, hi = 1.5, math.log10(top) + 0.05      # log: 100 Mb/s and 10 GbE on one chart
    X = lambda v: L + (math.log10(v) - lo) / (hi - lo) * (W - L - R)
    out = ['<svg viewBox="0 0 %d %d" role="img" aria-label="Each machine alone to %s">' % (W, H, esc(st["hub"])),
           '<text x="0" y="14" class="t1" font-weight="600">Each machine alone to %s, one TCP stream</text>' % esc(st["hub"])]
    for v in (100, 1000, 10000):
        if v <= 10 ** hi:
            out.append('<line class="grid" x1="%.1f" x2="%.1f" y1="%d" y2="%d"/><text x="%.1f" y="%d" class="t3" text-anchor="middle">%s Mb/s</text>'
                       % (X(v), X(v), T, H - 30, X(v), H - 14, "{:,}".format(v)))
    for i, (n, v) in enumerate(rows):
        y = T + 8 + i * 26
        sp = speed_of(inv, n) if inv else None
        col = "var(--s-md)" if v > 2000 else "var(--bad)" if v < 500 else "var(--s-one)"
        out.append('<text x="%d" y="%d" class="t2" text-anchor="end">%s</text>' % (L - 8, y + 12, esc(SHOWN.get(n, n))))
        out.append('<rect x="%d" y="%d" width="%.1f" height="16" rx="3" fill="%s"><title>%s: %s Mb/s (link %s)</title></rect>'
                   % (L, y, max(2, X(v) - L), col, esc(n), "{:,.1f}".format(v), sp or "?"))
        note = (" · its link runs at %s Mb/s" % sp) if sp and sp < 1000 else ""
        out.append('<text x="%.1f" y="%d" class="t1">%s<tspan class="t2">%s</tspan></text>' % (X(v) + 6, y + 12, "{:,.0f}".format(v), esc(note)))
    out.append("</svg>")
    return DR.figure("".join(out), "Mb/s received by %s from each machine in turn, five seconds each, on a log scale. "
                     "A 1 GbE link carries at most 941 Mb/s of TCP, a 10 GbE link 9,410, a 100 Mb/s link 94." % st["hub"])


SYNC_PAIRS = [("the Mac", "mac-nfs-sync-default", "mac-nfs-async"), ("the VM", "vm-nfs-sync", "vm-nfs-async"),
              ("nasser", "nasser-nfs-sync", "nasser-nfs-async"), ("xinanjiang", "xinanjiang-nfs-sync", "xinanjiang-nfs-async")]
ASYNC_MEASURES = [("make", "per_s", "files made"), ("move", "per_s", "files moved"), ("remove", "per_s", "files removed"),
                  ("randW", "IOPS", "4K random writes"), ("syncW", "IOPS", "4K write + fsync")]


def value(r, key, field):
    t = r["tests"].get("tree", {}) if key in ("make", "list", "list2", "move", "read", "remove") else r["tests"]
    return (t.get(key) or {}).get(field)


def async_chart():
    """Each client's sync rate and async rate on one line per measure: the line is what async buys. calber's own
    rate is marked on each measure for scale; it is the ceiling a share is measured against."""
    runs = {}
    for r in load("nfs"):
        if r["kind"] == "run":
            runs[r["label"]] = r
    rows = []
    for key, field, words in ASYNC_MEASURES:
        local = value(runs["calber-local"], key, field) if "calber-local" in runs else None
        for who, sl, al in SYNC_PAIRS:
            if sl in runs and al in runs:
                rows.append((words, who, value(runs[sl], key, field), value(runs[al], key, field), local))
    if not rows:
        return None
    import math
    vals = [v for r in rows for v in r[2:] if v]
    lo, hi = math.floor(math.log10(min(vals))), math.ceil(math.log10(max(vals)))
    W, L, R, T, RH = 880, 210, 30, 44, 20
    groups = []
    for r in rows:
        if not groups or groups[-1] != r[0]:
            groups.append(r[0])
    H = T + RH * len(rows) + 14 * len(groups) + 40
    X = lambda v: L + (math.log10(v) - lo) / (hi - lo) * (W - L - R)
    out = ['<svg viewBox="0 0 %d %d" role="img" aria-label="What async buys each client">' % (W, H),
           '<text x="0" y="14" class="t1" font-weight="600">What an async share buys each client, per second, log scale</text>']
    # legend: two states and the reference
    out.append('<circle cx="%d" cy="30" r="4.5" fill="var(--s-one)"/><text x="%d" y="34" class="t2">sync</text>' % (L, L + 9))
    out.append('<circle cx="%d" cy="30" r="4.5" fill="var(--s-md)"/><text x="%d" y="34" class="t2">async</text>' % (L + 60, L + 69))
    out.append('<path d="M%d 25 l4 5 l-4 5 l-4 -5 z" fill="none" stroke="var(--t2)" stroke-width="1.5"/><text x="%d" y="34" class="t2">calber on its own disks</text>' % (L + 130, L + 139))
    for e in range(lo, hi + 1):
        x = X(10 ** e)
        out.append('<line class="grid" x1="%.1f" x2="%.1f" y1="%d" y2="%d"/><text x="%.1f" y="%d" class="t3" text-anchor="middle">%s</text>'
                   % (x, x, T, H - 30, x, H - 14, "{:,}".format(10 ** e)))
    y, last = T, None
    for words, who, sv, av, local in rows:
        if words != last:
            y += 14
            out.append('<text x="0" y="%d" class="t1" font-weight="600">%s</text>' % (y + 10, esc(words)))
            if local:
                out.append('<path d="M%.1f %d l4 5 l-4 5 l-4 -5 z" fill="none" stroke="var(--t2)" stroke-width="1.5"><title>calber itself: %s</title></path>'
                           % (X(local), y + 1, "{:,.0f}".format(local)))
            last = words
        cy = y + RH // 2 + 2
        out.append('<text x="%d" y="%d" class="t2" text-anchor="end">%s</text>' % (L - 10, cy + 4, esc(who)))
        if sv and av:
            out.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="var(--t3)" stroke-width="2"/>' % (X(sv), X(av), cy, cy))
        for v, col, state in ((sv, "var(--s-one)", "sync"), (av, "var(--s-md)", "async")):
            if v:
                out.append('<circle cx="%.1f" cy="%d" r="5" fill="%s" stroke="var(--surface)" stroke-width="2"><title>%s, %s, %s: %s a second</title></circle>'
                           % (X(v), cy, col, esc(who), esc(words), state, "{:,.0f}".format(v)))
        if sv and av:
            out.append('<text x="%.1f" y="%d" class="t3">%s</text>' % (max(X(sv), X(av)) + 9, cy + 4, "%.1f×" % (av / sv)))
        y += RH
    out.append("</svg>")
    return DR.figure("".join(out), "Each client's rate on the sync share (gray) and the async share (blue), the same mount, one run each; "
                     "the multiple is async over sync. The Mac's sync rate is its default 32K mount's. The diamond is calber on its own "
                     "disks: the ceiling a share is measured against.")


def draw():
    os.makedirs(DOCS, exist_ok=True)
    made = []
    for name, html in (("topology.html", topology()), ("star.html", star_chart()), ("async.html", async_chart())):
        if html:
            with open(os.path.join(DOCS, name), "w") as f:
                f.write(html)
            made.append(name)
    print("drew", ", ".join(made) or "nothing (fetch first)")


# ---- tables -----------------------------------------------------------------------------------------------

COLS = [("seqW", "MBps", "Seq W MB/s"), ("seqR", "MBps", "Seq R MB/s"), ("randR", "IOPS", "4K reads/s"),
        ("randW", "IOPS", "4K writes/s"), ("syncW", "IOPS", "Write+fsync/s"), ("make", "per_s", "Make files/s"),
        ("list", "per_s", "List files/s"), ("move", "per_s", "Move files/s"), ("read", "per_s", "Read files/s"),
        ("remove", "per_s", "Remove files/s")]


def table():
    runs = {}
    for r in load("nfs"):
        if r["kind"] == "run":
            runs[r["label"]] = r     # sorted by stamp: the last of each label stands
    print("| Client | Mount | " + " | ".join(c[2] for c in COLS) + " |")
    print("| --- | --- | " + " | ".join("---" for _ in COLS) + " |")
    order = sorted(runs, key=lambda s: (not s.startswith("calber"), s))
    for lab in order:
        r = runs[lab]
        m = r.get("mount") or {}
        opts = m.get("granted") or m.get("options") or ""
        size = ""
        for k in ("rsize=",):
            if k in opts:
                size = opts.split(k)[1].split(",")[0].split()[0]
        mount = (m.get("type", "?") + ((" r/w %sK" % (int(size) // 1024)) if size.isdigit() else "")) if m else "?"
        cells = []
        for key, field, _ in COLS:
            t = r["tests"].get("tree", {}) if key in ("make", "list", "move", "read", "remove") else r["tests"]
            v = (t.get(key) or {}).get(field)
            cells.append("-" if v is None else "{:,.0f}".format(v) if v >= 10 else "%.1f" % v)
        print("| %s%s | %s | %s |" % (lab, " (quick)" if r.get("quick") else "", mount, " | ".join(cells)))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["fetch"]:
        fetch()
    elif a[:1] == ["draw"]:
        draw()
    elif a[:1] == ["table"]:
        table()
    else:
        sys.exit(__doc__)
