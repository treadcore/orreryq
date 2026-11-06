#!/usr/bin/env python3
"""power.py QUEUE sample|show -- what the fleet draws at the wall, and what it costs.

Paul, 5 November: "use the assessment of CPU power, and general Gold Efficiency Power Supplies, use
GPU power and CPU estimates, perhaps there is a sensor ... a general guess at full tilt CPU cause
things like macmini is minimal watts where the 48Core server CPU is power hungry ... have each
computer report its power estimate participation to the graph as it hands it off ... a general
cost per kWh."

THE MODEL is tools/plans/power.json: each box's CPU at idle and at full tilt, the rest of the box
(board, memory, disks, fans), its GPU's idle and its limit, and its supply's efficiency. A box's
watts at the wall = (rest + CPU idle + CPU use x (CPU full - CPU idle) + GPU) / efficiency.

WHAT IS MEASURED: the CPU's use and the GPU's draw, each five minutes (`sample`, one of the keeper's
chores): two reads of /proc/stat two seconds apart, nvidia-smi's power.draw, top's CPU line on the
Mac. WHAT IS NOT: the CPU's own power. Five boxes have an energy counter (RAPL) and all five keep
it for root; the two Xeon servers have none; no box has a meter at the wall. So a CPU's watts are
its model's at the use measured, and say so.

A lane's part (`lane_watts`): a CPU lane carries its box's rest and CPU, a GPU lane its card, so
the parts of a box add up to the box and each job is charged its own lane's watts while it ran.

  sample   one reading of every box, appended to plan/power-samples.jsonl (a week kept)
  show     each box: its model, its last reading, its watts now and at full tilt
"""
import json
import os
import re
import statistics as st
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "plans", "power.json")
KEEP_DAYS = 7
# Fewer samples than this and the model's guess stands: one two-second read can land in a job's last
# seeds, where a 24-thread server ran 9% busy (jaguaribe, 14:20 on 5 November).
MIN_SAMPLES = 6
BUSY = ("running", "delivering", "fetching", "sending")
# ORRERY'S OWN PROCESSES, the Orchestrator (Paul, 5 November: "show the process of Orrery and its
# orchestration scripts, count them as Orchestrator of Orrery"), on the machine the keeper runs on:
# the first pattern a command matches names it.
ORCH = (("planner", re.compile(r"plans/treadcore\.py")),
        ("keeper", re.compile(r"fleet-queue\.py")),
        ("console", re.compile(r"Orrery\.app|/orrery --gui|/orrery --operator")),
        ("chores", re.compile(r"/orrery/tools/[\w-]+\.py|treadcore-view\.py")),
        ("ssh", re.compile(r"^(ssh|scp|rsync)[ :]")))
# One command for every box: the Mac's top, or Linux's /proc/stat twice and the GPU's draw.
PROBE = ('if [ "$(uname)" = Darwin ]; then top -l 2 -n 0 -s 2 | grep "CPU usage" | tail -1; else '
         'head -1 /proc/stat; sleep 2; head -1 /proc/stat; '
         'command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=power.draw,utilization.gpu --format=csv,noheader,nounits; fi')


def load(p, default=None):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def model():
    return load(MODEL, {}) or {}


def rate(q, m=None):
    """$ a kWh: tuning.json's power_usd_kwh (Settings, Long run), or the model's guess."""
    m = m or model()
    t = load(os.path.join(q, "tuning.json"), {}) or {}
    return float(t.get("power_usd_kwh", m.get("rate_usd_kwh", 0.17)))


def box_of(m, lane):
    return (m.get("lanes") or {}).get(lane, lane)


def orch_of(ps_out, me=None):
    """{part: % of one core} of Orrery's own processes, from `ps -Ao pid=,pcpu=,command=`; the
    sampler's own process (`me`) left out, or it would count itself reading."""
    out = {}
    for line in ps_out.splitlines():
        p = line.strip().split(None, 2)
        if len(p) != 3 or p[0] == str(me):
            continue
        try:
            pct = float(p[1])
        except ValueError:
            continue
        for name, rx in ORCH:
            if rx.search(p[2]):
                out[name] = round(out.get(name, 0.0) + pct, 1)
                break
    return out


def per_core(m, box):
    """A box's watts at the wall for one busy core of its CPU."""
    b = (m.get("boxes") or {}).get(box) or {}
    return (b.get("cpu_full_w", 0) - b.get("cpu_idle_w", 0)) / max(1, b.get("threads", 8)) / eff(m, box)


def eff(m, box):
    return float((m.get("boxes") or {}).get(box, {}).get("eff", (m.get("gold") or {}).get("eff", 0.88)))


def watts(m, box, cpu_util, gpu_w=0.0):
    """A box's watts at the wall at a CPU use (0 to 1) and a GPU draw (watts at the card)."""
    b = (m.get("boxes") or {}).get(box)
    if not b:
        return None
    cpu = b["cpu_idle_w"] + max(0.0, min(1.0, cpu_util)) * (b["cpu_full_w"] - b["cpu_idle_w"])
    dc = b["rest_w"] + cpu + (gpu_w or 0.0)
    return {"cpu": round(cpu, 1), "gpu": round(gpu_w or 0.0, 1), "rest": b["rest_w"], "dc": round(dc, 1), "wall": round(dc / eff(m, box), 1)}


def samples(q, since=0.0):
    out = []
    try:
        with open(os.path.join(q, "plan", "power-samples.jsonl")) as f:
            for line in f:
                try:
                    s = json.loads(line)
                except ValueError:
                    continue
                if s.get("t", 0) >= since:
                    out.append(s)
    except OSError:
        pass
    return out


def calib(m, smp):
    """Each box as measured: its CPU's use while its lane runs a job and while it does not, and its
    card's draw while its GPU lane runs a segment and while it does not; the model's guesses where
    fewer than MIN_SAMPLES say."""
    out = {}
    gpu_lane = {box: lane for lane, box in (m.get("lanes") or {}).items()}
    threads = lambda b: max(1, b.get("threads", 8))
    for box, b in (m.get("boxes") or {}).items():
        mine = [s for s in smp if s.get("box") == box]
        # The machine the keeper runs on: its job lane's use is the machine's less Orrery's own.
        use = lambda s: max(0.0, s["cpu"] - sum((s.get("orch") or {}).values()) / 100 / threads(b))
        busy = [use(s) for s in mine if s.get("cpu") is not None and (s.get("busy") or {}).get(box)]
        idle = [use(s) for s in mine if s.get("cpu") is not None and not (s.get("busy") or {}).get(box)]
        gl = gpu_lane.get(box)
        gb = [sum(s["gpu_w"]) for s in mine if gl and s.get("gpu_w") and (s.get("busy") or {}).get(gl)]
        gi = [sum(s["gpu_w"]) for s in mine if gl and s.get("gpu_w") and not (s.get("busy") or {}).get(gl)]
        enough = lambda v: len(v) >= MIN_SAMPLES
        out[box] = {"busy_util": round(st.mean(busy), 3) if enough(busy) else b.get("busy_util", m.get("busy_util", 0.9)),
                    "idle_util": round(st.mean(idle), 3) if enough(idle) else m.get("idle_util", 0.03),
                    "gpu_busy_w": round(st.median(gb), 1) if enough(gb) else round(b.get("gpu_limit_w", 0) * m.get("gpu_busy_share", 0.6), 1),
                    "gpu_idle_w": round(st.median(gi), 1) if enough(gi) else b.get("gpu_idle_w", 0),
                    "measured": {"cpu": len(busy) + len(idle), "gpu": len(gb) + len(gi)}}
    o = m.get("orchestrator") or {}
    steady = [(sum(s["orch"].values()) - s["orch"].get("planner", 0)) / 100 for s in smp if s.get("orch")]
    out["orchestrator"] = {"steady_cores": round(st.mean(steady), 3) if enough(steady) else o.get("steady_cores", 0.3), "measured": len(steady)}
    return out


def lane_watts(m, cal, lane, busy):
    """A lane's part of its box at the wall, busy that share of the time (0 to 1): a CPU lane its
    box's rest and CPU, a GPU lane its card. None for a lane the model has no box for."""
    busy = max(0.0, min(1.0, busy))
    if lane == "orchestrator":
        # A planner pass is one core while it runs; the console, keeper, chores and ssh the rest.
        o = m.get("orchestrator") or {}
        return (busy + (cal.get("orchestrator") or {}).get("steady_cores", o.get("steady_cores", 0.3))) * per_core(m, o.get("box", "mac"))
    box = box_of(m, lane)
    b = (m.get("boxes") or {}).get(box)
    if not b:
        return None
    c = cal.get(box) or {}
    if lane != box:
        return (busy * c.get("gpu_busy_w", 0) + (1 - busy) * c.get("gpu_idle_w", 0)) / eff(m, box)
    util = busy * c.get("busy_util", 0.9) + (1 - busy) * c.get("idle_util", 0.03)
    return (b["rest_w"] + b["cpu_idle_w"] + util * (b["cpu_full_w"] - b["cpu_idle_w"])) / eff(m, box)


def full_tilt(m, cal, box):
    """A box's watts at the wall at full tilt: every core busy, its card at its measured draw."""
    gpu = sum((cal.get(box) or {}).get("gpu_busy_w", 0) for l, b in (m.get("lanes") or {}).items() if b == box and l != "orchestrator")
    w = watts(m, box, 1.0, gpu)
    return w["wall"] if w else 0.0


def parse(out):
    """(CPU use 0 to 1 or None, [GPU watts], [GPU use %]) from the probe's output."""
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    cpu, gw, gu = None, [], []
    stat = [l for l in lines if l.startswith("cpu ")]
    if len(stat) >= 2:
        a, b = ([int(x) for x in s.split()[1:9]] for s in stat[:2])
        dt, di = sum(b) - sum(a), (b[3] + b[4]) - (a[3] + a[4])
        cpu = round(1 - di / dt, 3) if dt > 0 else None
    for l in lines:
        if l.startswith("CPU usage"):
            try:
                cpu = round(1 - float(l.rsplit(",", 1)[1].split("%")[0]) / 100, 3)
            except (ValueError, IndexError):
                pass
        elif "," in l and not l.startswith("cpu"):
            p = [x.strip() for x in l.split(",")]
            try:
                gw.append(float(p[0]))
                gu.append(float(p[1]))
            except (ValueError, IndexError):
                pass
    return cpu, gw, gu


def targets(q, m):
    """Each box of the model the fleet knows: where to ssh, and its lanes."""
    cfg = load(os.path.join(q, "config.json"), {}) or {}
    out = {}
    for h in cfg.get("hosts", []):
        box = box_of(m, h["name"])
        if box in (m.get("boxes") or {}):
            out.setdefault(box, {"target": None, "lanes": []})["lanes"].append(h["name"])
            if h["name"] == box:
                out[box]["target"] = h.get("target")
    # The machine the keeper runs on is sampled whether or not it has a lane: the Orchestrator is on it.
    o = (m.get("orchestrator") or {}).get("box")
    if o in (m.get("boxes") or {}):
        out.setdefault(o, {"target": "-", "lanes": []})
        out[o]["target"] = out[o]["target"] or "-"
        if "orchestrator" not in out[o]["lanes"]:
            out[o]["lanes"].append("orchestrator")
    return {b: v for b, v in out.items() if v["target"]}


def sample(q):
    m = model()
    now = time.time()
    got = {}

    orch = {}

    def one(box, target):
        try:
            if target == "-":
                # This machine: and Orrery's own processes on it, the Orchestrator.
                r = subprocess.run(["bash", "-c", PROBE], capture_output=True, text=True, timeout=30)
                ps = subprocess.run(["ps", "-Ao", "pid=,pcpu=,command="], capture_output=True, text=True, timeout=10)
                orch[box] = orch_of(ps.stdout, os.getpid())
            else:
                r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6", target, PROBE],
                                   capture_output=True, text=True, timeout=30)
            got[box] = parse(r.stdout)
        except (subprocess.TimeoutExpired, OSError):
            got[box] = None
    ts = targets(q, m)
    th = [threading.Thread(target=one, args=(b, v["target"])) for b, v in ts.items()]
    for t in th:
        t.start()
    for t in th:
        t.join()
    rows = []
    for box, v in sorted(ts.items()):
        busy = {}
        for lane in v["lanes"]:
            ln = load(os.path.join(q, "lanes", lane + ".json"), {}) or {}
            busy[lane] = ln.get("state") in BUSY or bool(ln.get("job"))
        cpu, gw, gu = got.get(box) or (None, [], [])
        row = {"t": round(now, 1), "box": box, "cpu": cpu, "gpu_w": gw, "gpu_util": gu, "busy": busy, "ok": got.get(box) is not None}
        if box in orch:
            row["orch"] = orch[box]
            # The Orchestrator is busy while a planner pass runs.
            busy["orchestrator"] = orch[box].get("planner", 0) >= 50
        rows.append(row)
    path = os.path.join(q, "plan", "power-samples.jsonl")
    with open(path, "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    # A week kept: the file is rewritten when it passes 3 MB.
    if os.path.getsize(path) > 3_000_000:
        keep = samples(q, now - KEEP_DAYS * 86400)
        with open(path + ".tmp", "w") as f:
            for r in keep:
                f.write(json.dumps(r) + "\n")
        os.replace(path + ".tmp", path)
    return rows


def show(q):
    m = model()
    smp = samples(q, time.time() - 3 * 86400)
    cal = calib(m, smp)
    last = {}
    for s in smp:
        last[s["box"]] = s
    r = rate(q, m)
    print("%-13s %-44s %6s %7s %8s %9s  %s" % ("box", "cpu", "use", "gpu W", "wall W", "full W", "measured"))
    tot = 0.0
    for box, b in m.get("boxes", {}).items():
        s = last.get(box) or {}
        w = watts(m, box, s.get("cpu") if s.get("cpu") is not None else cal[box]["idle_util"], sum(s.get("gpu_w") or []))
        tot += w["wall"]
        print("%-13s %-44s %6s %7s %8.0f %9.0f  %s" % (box, b["cpu"][:44], "%.0f%%" % (100 * s["cpu"]) if s.get("cpu") is not None else "-",
                                                    "%.0f" % sum(s["gpu_w"]) if s.get("gpu_w") else "-", w["wall"], full_tilt(m, cal, box),
                                                    "%d cpu, %d gpu samples" % (cal[box]["measured"]["cpu"], cal[box]["measured"]["gpu"])))
    print("fleet now %.0f W at the wall: %.1f kWh a day, $%.2f a day at $%.3f/kWh" % (tot, tot * 24 / 1000, tot * 24 / 1000 * r, r))


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[2] not in ("sample", "show"):
        sys.exit(__doc__)
    if sys.argv[2] == "sample":
        for row in sample(sys.argv[1]):
            print(json.dumps(row))
    else:
        show(sys.argv[1])
