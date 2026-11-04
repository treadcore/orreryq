#!/usr/bin/env python3
"""What the fleet is training, as one JSON document (LAB-REPORT-BRAIN.md 109).

    python3 -I tools/plans/treadcore-view.py [--fleet grove] [--queue QDIR]

(Moved from treadcore's scripts/fleet-view.py, treadcore LR 113: orrery holds
the orchestration. TREADCORE= names the checkout, ~/code/treadcore by default.)

orrery's Training view draws this (`--jobs-cmd`). It reads, every time:

- the fleet's machines: the static list of the Copal fleet
  (~/.copal/fleets/NAME/nodes), and this Mac, the coordinator; each asked over
  ssh, in parallel and with a short timeout, for its cores, load, memory and
  GPU;
- what each is doing: the lanes of the newest recording run
  (tools/plans/treadcore-jobs.py), and the loop's state (build/fleet-train);
- the net being trained: the loop's best (build/fleet-train/best.bin, else
  nets/bc2.bin) read from its Net::save form, its weight matrices shrunk to
  at most 48 x 48 cells for drawing;
- how good it is: build/fleet-train/best.json (held-out agreement by head,
  the census), with bc1 and the official net beside it.
"""
import glob
import json
import os
import re
import struct
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

TC = os.path.expanduser(os.environ.get("TREADCORE", "~/code/treadcore"))
FT = os.environ.get("FT_DIR", os.path.join(TC, "build", "fleet-train"))
FLEET = sys.argv[sys.argv.index("--fleet") + 1] if "--fleet" in sys.argv else "grove"
# --queue QDIR: an orrery fleet-queue (tools/fleet-queue.py) and its planner's
# summary, so the view shows the queue and what each machine runs in it.
QDIR = sys.argv[sys.argv.index("--queue") + 1] if "--queue" in sys.argv else ""
QUEUE_PY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fleet-queue.py")
STORE = os.environ.get("STORE", "user@calber").split("@")[-1]
CENSUS = os.environ.get("CENSUS_HOST", "user@columbia").split("@")[-1]
HEADS = [("drive", 10), ("gun", 9), ("lead", 3), ("mortar", 9), ("drone", 5), ("squad", 7), ("signal", 4)]

PROBE = ("echo cores=$(nproc 2>/dev/null || sysctl -n hw.ncpu); "
         "echo load=$(cut -d' ' -f1 /proc/loadavg 2>/dev/null || sysctl -n vm.loadavg | awk '{print $2}'); "
         "free -m 2>/dev/null | awk '/Mem:/ {print \"mem_mb=\" $2; print \"avail_mb=\" $7}'; "
         "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | sed 's/^/gpu=/'")


def read(path, default=""):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def probe(addr):
    cmd = ["bash", "-c", PROBE] if addr == "local" else \
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3", "-o", "ControlMaster=auto", "-o", "ControlPath=/tmp/orrery-view-%r@%h-%p", "-o", "ControlPersist=120", addr, PROBE]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=6).stdout
    except (subprocess.TimeoutExpired, OSError):
        return {"up": False}
    d = {"up": bool(out.strip())}
    for line in out.splitlines():
        k, _, v = line.partition("=")
        if k in ("cores", "mem_mb", "avail_mb"):
            d[k] = int(v) if v.strip().isdigit() else None
        elif k == "load":
            try:
                d[k] = float(v)
            except ValueError:
                pass
        elif k == "gpu" and v.strip():
            p = [x.strip() for x in v.split(",")]
            if len(p) == 4:
                d["gpu"] = {"name": p[0].replace("NVIDIA GeForce ", ""), "busy_pct": int(p[1]),
                            "mem_mb": int(p[2]), "mem_total_mb": int(p[3])}
    return d


def machines(run, qd=None):
    nodes = []
    for line in read(os.path.expanduser(f"~/.copal/fleets/{FLEET}/nodes")).splitlines():
        line = line.split("#")[0].split()
        if len(line) >= 2:
            nodes.append((line[0], line[1]))
    nodes.append(("this Mac", "local"))
    with ThreadPoolExecutor(len(nodes)) as ex:
        found = list(ex.map(lambda n: probe(n[1] if n[1] == "local" else "user@" + n[1]), nodes))
    out = []
    for (name, addr), p in zip(nodes, found):
        roles = []
        if addr == STORE:
            roles.append("trains on the GPU")
        if addr == CENSUS:
            roles.append("runs the census")
        if addr == "local":
            roles.append("coordinates")
        lanes = {l["host"] for l in (run or {}).get("lanes", [])} | {l["host"] for l in (qd or {}).get("lanes", [])}
        if name in lanes or (addr == "local" and "mac" in lanes):
            roles.insert(0, "records matches")
        elif addr != "local":
            roles.append("not in this recording run")
        out.append({"name": name, "address": "" if addr == "local" else addr, "roles": roles, **p})
    return out


def ticker(n=40):
    """The newest coefficients the fleet changed, a line a variable, and the
    two Found Improvement leaderboards: by variable, and by machine."""
    out, by_var, by_host = [], {}, {}
    try:
        lines = open(os.path.join(QDIR, "plan", "ticker.jsonl")).read().splitlines()
    except OSError:
        lines = []
    for l in lines:
        try:
            e = json.loads(l)
        except ValueError:
            continue
        host = e.get("host") or "?"
        h = by_host.setdefault(host, [0, 0])
        h[0] += 1
        if e.get("improved"):
            h[1] += 1
        for var, v in (e.get("vars") or {}).items():
            value, offset = (v.get("value"), v.get("offset")) if isinstance(v, dict) else (v, None)
            if e.get("improved"):
                by_var[var] = by_var.get(var, 0) + 1
            out.append({"t": e.get("t", "")[11:19], "kind": e.get("kind", ""), "var": var, "value": value, "offset": offset,
                        "d": e.get("d"), "se": e.get("se"), "host": host, "improved": bool(e.get("improved"))})
    return {"ticker": out[-n:],
            "lead_vars": sorted(by_var.items(), key=lambda kv: -kv[1])[:10],
            "lead_hosts": sorted(([k, v[0], v[1]] for k, v in by_host.items()), key=lambda r: (-r[2], -r[1]))}


def runs():
    """The runs a person asked for, and where each is (the planner's `runs`)."""
    try:
        cfg = json.load(open(os.path.join(QDIR, "config.json")))
        out = subprocess.run(["bash", "-c", cfg["planner"] + " runs"], capture_output=True, text=True, timeout=30).stdout
        return json.loads(out)
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        return []


def queue():
    if not QDIR or not os.path.exists(os.path.join(QDIR, "config.json")):
        return None
    try:
        out = subprocess.run([sys.executable, QUEUE_PY, QDIR, "status", "--json"], capture_output=True, text=True, timeout=20).stdout
        q = json.loads(out)
    except (subprocess.TimeoutExpired, ValueError):
        return None
    q["name"] = os.path.basename(os.path.abspath(QDIR))
    q.update(ticker())
    q["runs"] = runs()
    # Each candidate: current, or on older defaults (the planner's).
    try:
        q["candidate_state"] = json.load(open(os.path.join(QDIR, "plan", "candidates.json")))
    except (OSError, ValueError):
        q["candidate_state"] = {}
    # crucible's islands (plan/crucible.json, the planner's): the Projects view.
    try:
        q["crucible"] = json.load(open(os.path.join(QDIR, "plan", "crucible.json")))
    except (OSError, ValueError):
        q["crucible"] = {}
    try:
        q["push"] = json.load(open(os.path.join(QDIR, "plan", "push.json")))
    except (OSError, ValueError):
        q["push"] = None
    # The line the fleet builds, each commit's changed defaults (the
    # planner's, each plan): the Settings view's Commits page.
    try:
        q["commits"] = json.load(open(os.path.join(QDIR, "plan", "commits.json")))
    except (OSError, ValueError):
        q["commits"] = {}
    s = read(os.path.join(QDIR, "plan", "summary.json"))
    if s:
        try:
            q["summary"] = json.loads(s)
        except ValueError:
            pass
    return q


def newest_run():
    d = os.path.join(TC, "build", "fleet")
    try:
        runs = [os.path.join(d, r) for r in os.listdir(d) if os.path.isdir(os.path.join(d, r, "queue"))]
    except OSError:
        return None
    runs = [r for r in runs if not os.path.basename(r).startswith("rehearse")]
    if not runs:
        return None
    r = max(runs, key=lambda r: os.path.getmtime(os.path.join(r, "manifest.tsv")) if os.path.exists(os.path.join(r, "manifest.tsv")) else 0)
    try:
        out = subprocess.run([sys.executable, "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "treadcore-jobs.py"), r],
                             capture_output=True, text=True, timeout=10).stdout
        return json.loads(out)["runs"][0]
    except (subprocess.TimeoutExpired, ValueError, KeyError, IndexError):
        return None


def loop():
    rnd = read(os.path.join(FT, "round"), "0")
    stages = []
    events = []
    try:
        with open(os.path.join(FT, "events.jsonl")) as f:
            events = [json.loads(l) for l in f if l.strip()]
    except OSError:
        pass
    now = {}
    for e in events:
        if str(e.get("round")) == rnd and e.get("stage") not in ("round", "loop"):
            now[e["stage"]] = e["event"]
    for s in ("record", "train", "judge"):
        stages.append({"stage": s, "state": now.get(s, "")})
    return {"round": int(rnd) if rnd.isdigit() else 0, "stages": stages, "best": read(os.path.join(FT, "best")),
            "stopping": os.path.exists(os.path.join(FT, "STOP")),
            # A round is running when its last round-event is "started".
            "running": next((e.get("event") == "started" for e in reversed(events) if e.get("stage") == "round"), False)}


def shrink(w, rows, cols, cap=48):
    """A rows x cols matrix (row-major) as at most cap x cap cells, each the
    mean of the weights it covers."""
    r2, c2 = min(rows, cap), min(cols, cap)
    out = []
    for i in range(r2):
        r0, r1 = i * rows // r2, max(i * rows // r2 + 1, (i + 1) * rows // r2)
        row = []
        for j in range(c2):
            c0, c1 = j * cols // c2, max(j * cols // c2 + 1, (j + 1) * cols // c2)
            vals = [w[a * cols + b] for a in range(r0, r1) for b in range(c0, c1)]
            row.append(round(sum(vals) / len(vals), 4))
        out.append(row)
    return out


def net():
    path = os.path.join(FT, "best.bin")
    name = read(os.path.join(FT, "best"), "").split(" ")[0] or "bc2"
    if not os.path.exists(path):
        path = os.path.join(TC, "nets", "bc2.bin")
    try:
        b = open(path, "rb").read()
    except OSError:
        return None
    if b[:8] != b"TCNET1\0\0":
        return None
    k = struct.unpack_from("<I", b, 8)[0]
    sizes = list(struct.unpack_from(f"<{k}I", b, 12))
    off = 12 + 4 * k
    layers = []
    for a, o in zip(sizes, sizes[1:]):
        w = struct.unpack_from(f"<{a * o}f", b, off)
        off += 4 * a * o
        off += 4 * o  # biases, not drawn
        m = max(abs(x) for x in w) or 1.0
        # Whole, not shrunk: orrery draws a matrix large when it is clicked.
        layers.append({"inputs": a, "outputs": o, "max_abs": round(m, 4), "cells": shrink(w, o, a, cap=1000)})
    # What the 143 inputs are, by group (senses.rs: SECTORS * CHANNELS, BODY,
    # NAV, CONTACTS, HINTS, SHELL, AIR), and the 47 outputs by head.
    groups, at = [], 0
    for g, n in [("compass", 8 * 11), ("body", 12), ("navigation", 6), ("contacts", 18),
                 ("hints", 9), ("shells", 5), ("air", 5)]:
        groups.append({"name": g, "from": at, "to": at + n - 1})
        at += n
    heads, at = [], 0
    for h, n in HEADS:
        heads.append({"name": h, "from": at, "to": at + n - 1})
        at += n
    return {"name": name, "file": os.path.relpath(path, TC), "sizes": sizes,
            "input_groups": groups if sizes and sizes[0] == 143 else [],
            "output_groups": heads if sizes and sizes[-1] == 47 else [],
            "parameters": sum(a * o + o for a, o in zip(sizes, sizes[1:])),
            "heads": [{"name": n, "choices": c} for n, c in HEADS], "layers": layers}


# The commit before the fleet's first promotion: where training began.
FIRST_PROMOTION = "dc3df01"


def algorhythm():
    """The brain as a patch: its switches, its dials and how far training has moved
    each from where the fleet found it, the transforms in their slots."""
    import glob, re
    rs = "source/treadcore-brain/src/weights.rs"
    def parse(text):
        return re.findall(r'^\s*[A-Z][A-Za-z0-9]*\s+"([a-z_0-9]+)"\s+(-?[0-9.]+),\s*"([^"]*)"', text, re.M)
    text = read(os.path.join(TC, rs))
    # Before the fleet's first promotion: where training began.
    r = subprocess.run(["git", "-C", TC, "show", "%s~1:" % FIRST_PROMOTION + rs], capture_output=True, text=True)
    factory = {n: float(v) for n, v, _ in parse(r.stdout)} if r.returncode == 0 else {}
    switches, dials = [], []
    for name, v, doc in parse(text):
        m = re.search(r"\(choice: ([^)]*)\)", doc)
        if m:
            switches.append({"name": name, "value": int(round(float(v))), "versions": [x.strip() for x in m.group(1).split("|")]})
        else:
            dials.append({"name": name, "value": float(v), "factory": factory.get(name, float(v))})
    caps = re.findall(r'^\s*[A-Z_]+ [0-9]+ "([a-z_]+)" (true|false),', text, re.M)
    patches = []
    pdir = os.path.join(QDIR, "patches") if QDIR else ""
    for f in sorted(glob.glob(os.path.join(pdir, "*.bin"))) if pdir else []:
        b = open(f, "rb").read()
        if b[:4] != b"TCP1":
            continue
        steps, inputs = struct.unpack_from("<II", b, 4)
        off, cols, cells = 12, inputs + 3, []
        for _ in range(steps):
            w = struct.unpack_from(f"<{3 * cols}f", b, off)
            off += 4 * (3 * cols + 3)
            cells.append(shrink(w, 3, cols, cap=320))
        patches.append({"slot": os.path.basename(f)[:-4], "inputs": inputs, "steps": cells})
    return {"switches": switches, "dials": dials, "caps": [{"name": n, "on": o == "true"} for n, o in caps], "patches": patches}


def nets():
    """nets.py's register of the learned nets, and a fresh one begun in the background when it is
    older than five minutes: a refresh is a few seconds, and the Nets page redraws from the file."""
    if not QDIR:
        return None
    f = os.path.join(QDIR, "plan", "nets.json")
    age = time.time() - os.path.getmtime(f) if os.path.exists(f) else 1e9
    lock = f + ".lock"
    if age > 300 and not (os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 120):
        open(lock, "w").close()
        tool = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nets.py")
        subprocess.Popen([sys.executable, "-I", tool, QDIR, "refresh"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        return json.loads(read(f))
    except ValueError:
        return None


def growth():
    """growth.py's document: crucible's samples, the sizes and the purge's list. A fresh one begun
    in the background when it is older than five minutes (the sizes inside it re-measure only each
    half hour: that is a minute of ssh to every machine)."""
    if not QDIR:
        return None
    f = os.path.join(QDIR, "plan", "growth.json")
    age = time.time() - os.path.getmtime(f) if os.path.exists(f) else 1e9
    lock = f + ".lock"
    if age > 300 and not (os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 600):
        open(lock, "w").close()
        tool = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "growth.py")
        subprocess.Popen([sys.executable, "-I", tool, QDIR, "refresh"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        return json.loads(read(f))
    except ValueError:
        return None


def analysis():
    """analysis.py's document, and a fresh one begun in the background when it is old: it
    takes a minute, and this runs every few seconds."""
    if not QDIR:
        return None
    f = os.path.join(QDIR, "plan", "analysis.json")
    age = time.time() - os.path.getmtime(f) if os.path.exists(f) else 1e9
    lock = f + ".lock"
    if age > 600 and not (os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 300):
        open(lock, "w").close()
        tool = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "analysis.py")
        subprocess.Popen([sys.executable, "-I", tool, QDIR], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        return json.loads(read(f))
    except ValueError:
        return None


def long_run():
    """The Settings page's Long run: what repeats over many generations, and what it last found."""
    if not QDIR:
        return None
    out = {}
    try:
        out["values"] = json.loads(read(os.path.join(QDIR, "plan", "pipeline.json"))).get("values", [])
    except ValueError:
        out["values"] = []
    try:
        st = json.loads(read(os.path.join(QDIR, "plan", "state.json")))
    except ValueError:
        return out
    far, tp, wd = st.get("far") or {}, st.get("temper") or {}, st.get("width") or {}
    gens = len([1 for f in glob.glob(os.path.join(QDIR, "runs", "*.json")) if '"promote"' in read(f)])
    out["far"] = {"game": far.get("game", ""), "left": len(far.get("todo", [])), "total": far.get("total", 0)}
    out["memory"] = st.get("memory") or {}
    out["temper"] = {"rounds": tp.get("rounds", 0), "left": len(tp.get("todo", [])), "at_gen": tp.get("at_gen")}
    hist = wd.get("history", [])
    out["width"] = {"tests": len(hist), "last": hist[-1] if hist else None, "running": bool(wd.get("run") or wd.get("job")), "at_gen": wd.get("at_gen")}
    return out


def quality():
    q = read(os.path.join(FT, "best.json"))
    if q:
        try:
            return json.loads(q)
        except ValueError:
            pass
    # Until the loop has promoted a net: bc2, as LR 108 read it.
    return {
        "net": "bc2",
        "held_out": {"drive": 66.6, "gun": 62.7, "mortar": 89.9, "drone": 96.8, "lead": 99.8},
        "bc1": {"drive": 65.5, "gun": 64.2, "mortar": 89.3, "drone": 96.7, "lead": 99.8},
        "commonest": {"drive": 36.5, "gun": 37.9, "mortar": 87.7, "drone": 94.0, "lead": 99.8},
        "census": {"best": -19.76, "best_se": 0.39, "official": -20.33, "official_se": 0.27,
                   "vs_official": 0.57, "vs_official_se": 0.37},
        "source": "LAB-REPORT-BRAIN.md section 108",
    }


def ranges():
    """The brain's RANGES as rows for a Settings page (the plan of 2 November, chapter 14): name, min,
    max, today's default, whether a decree (min = max), the comment, and the kind the file's sections
    name. Read from the checkout, so what the fleet compiles in is what the page shows."""
    rows, kind, defaults = [], "", {}
    try:
        src = read(os.path.join(TC, "source", "treadcore-brain", "src", "weights.rs"))
        for m in re.finditer(r'^\s+[A-Z][A-Za-z0-9]+ "([a-z_0-9]+)" ([-0-9.eE]+|crate::commander::[A-Z_]+),', src, re.M):
            defaults[m.group(1)] = m.group(2)
        for l in read(os.path.join(TC, "source", "treadcore-brain", "RANGES")).splitlines():
            bare, _, note = l.partition("#")
            if not bare.strip():
                if note.strip() and not bare.strip():
                    kind = note.strip().rstrip(".").split(":")[0][:40]
                continue
            f = bare.split()
            if len(f) == 3:
                rows.append({"name": f[0], "min": float(f[1]), "max": float(f[2]), "decree": f[1] == f[2], "why": note.strip(),
                             "kind": kind, "default": defaults.get(f[0], "")})
    except (OSError, ValueError):
        return rows
    return rows


def personas():
    """The roster of styles.rs (the eight styles and the eight personas of 2 November) for a Results
    page: slot, name, what it plays, the dials its profile sets over today's defaults, and its last
    census read in this queue (a run named persona-NAME, or a trial `bot_style = K`), pooled line."""
    out = []
    try:
        src = read(os.path.join(TC, "source", "treadcore-brain", "src", "styles.rs"))
    except OSError:
        return out
    for m in re.finditer(r'Style \{ slot: (\d+), name: "([^"]+)", about: "([^"]+)", kind: Kind::(\w+)\((?:include_str!\("[./]*profiles/([^"]+)"\))?', src):
        slot, name, about, kind, profile = int(m.group(1)), m.group(2), m.group(3), m.group(4), m.group(5)
        dials = []
        if profile:
            for l in read(os.path.join(TC, "profiles", profile)).splitlines():
                bare = l.split("#")[0].strip()
                if "=" in bare:
                    k, _, v = bare.partition("=")
                    dials.append("%s %s" % (k.strip(), v.strip()))
        out.append({"slot": slot, "name": name, "about": about, "kind": kind.lower(), "dials": dials, "read": None})
    if not QDIR:
        return out
    # The newest read of each slot: a run whose trial sets bot_style, by its results' pooled line.
    for f in sorted(glob.glob(os.path.join(QDIR, "runs", "*.json"))):
        try:
            r = json.loads(read(f))
        except ValueError:
            continue
        trial = (r.get("params") or {}).get("trial", "")
        mm = re.match(r"\s*bot_style\s*=\s*(\d+)", trial)
        if not mm:
            continue
        rid = os.path.basename(f)[:-5]
        for p in glob.glob(os.path.join(QDIR, "results", rid + "*", "*", "*", "out", rid + "*", "*", "pooled.txt")):
            line = read(p).splitlines()[:1]
            ml = re.match(r"every map\s+([-+][\d.]+) \+/- ([\d.]+) over\s+(\d+) seeds", line[0]) if line else None
            if ml:
                for x in out:
                    if x["slot"] == int(mm.group(1)):
                        x["read"] = {"d": float(ml.group(1)), "se": float(ml.group(2)), "seeds": int(ml.group(3)), "run": rid}
    return out


def gauntlet():
    """The gauntlet's last record (build/train/gauntlet.tsv, written by `make gauntlet` or the nightly
    job): a row an item, a column a brain, the share passed with its error and the reaction's median;
    the floor from each gauntlet file, so a cell under it can be red (the plan, chapter 15)."""
    # The newest record wherever it was written: `make gauntlet` on this Mac (two places, by the
    # directory cargo ran in), or a fleet machine's gauntlet job, fetched back under results/.
    paths = [os.path.join(TC, "build", "train", "gauntlet.tsv"), os.path.join(TC, "source", "treadcore-brain", "build", "train", "gauntlet.tsv")]
    if QDIR:
        paths += glob.glob(os.path.join(QDIR, "results", "gauntlet-*", "*", "*", "out", "gauntlet-*", "gauntlet.tsv"))
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        return None
    path = max(paths, key=os.path.getmtime)
    lines = read(path).splitlines()
    if len(lines) < 2:
        return None
    floors = {}
    for f in glob.glob(os.path.join(TC, "scenarios", "gauntlet", "*.toml")):
        name, floor = "", None
        for l in read(f).splitlines():
            m = re.match(r'\s*name\s*=\s*"([^"]+)"', l)
            if m:
                name = m.group(1)
            m = re.match(r"\s*floor\s*=\s*([\d.]+)", l)
            if m:
                floor = float(m.group(1))
        if name:
            floors[name] = floor
    head = lines[0].split("\t")
    rows, brains = [], []
    for l in lines[1:]:
        f = dict(zip(head, l.split("\t")))
        try:
            rows.append({"item": f["item"], "brain": f["brain"], "share": float(f["share"]), "se": float(f["se"]), "runs": int(f["runs"]),
                         "reaction": f.get("reaction_median", ""), "floor": floors.get(f["item"])})
        except (KeyError, ValueError):
            continue
        if f["brain"] not in brains:
            brains.append(f["brain"])
    items = []
    for r in rows:
        if r["item"] not in items:
            items.append(r["item"])
    return {"at": time.strftime("%Y-%m-%dT%H:%M", time.localtime(os.path.getmtime(path))), "source": path, "brains": brains, "items": items, "rows": rows}


if __name__ == "__main__":
    run = newest_run()
    qd = queue()
    doc = {"fleet": FLEET, "queue": qd, "project": "treadcore", "at": time.strftime("%H:%M:%S"),
           "machines": machines(run, qd), "run": run, "loop": loop(), "net": net(), "algorhythm": algorhythm(), "analysis": analysis(), "long_run": long_run(), "quality": quality(),
           "ranges": ranges(), "personas": personas(), "gauntlet": gauntlet(), "nets": nets(), "growth": growth(),
           "held": (lambda p: (lambda t: json.loads(t) if t.strip() else {})(read(p)))(os.path.join(QDIR, "hold.json")) if QDIR else {}}
    print(json.dumps(doc))
