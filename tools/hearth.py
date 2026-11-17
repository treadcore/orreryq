#!/usr/bin/env python3
"""hearth.py QUEUE ... -- the fleet as the house's heater, held to a temperature.

Paul, 16 November: "add the concept of thermal probes ... sets a dynamic heat target, which scales
back like a PID controller, which sets the CPU core throttling, until it shuts down systems. If the
house is cold, we can boot, but systems should unschedule and stop accepting new queue jobs while we
reduce total wattage, appropriate to maintaining steady heat. You can also have a WOL type effect to
turn systems back on. We can see about also creating a 'start a new computer to reach your target
temperature'."

    hearth.py QUEUE probes                         every probe: its place, its role, its newest reading, its age
    hearth.py QUEUE probe KEY place "the office"   name where a probe is
    hearth.py QUEUE probe KEY role room|outside|intake|exhaust|other
    hearth.py QUEUE target 21.0                    the temperature to hold, degrees C
    hearth.py QUEUE mode off|advise|act            advise (the default) computes and says; act does
    hearth.py QUEUE set KEY VALUE                  a gain or a rule (`set` alone lists them, with units)
    hearth.py QUEUE station KSEA                   which weather station's observation is the outside
    hearth.py QUEUE machine NAME keep on|off | mac AA:BB:.. | broadcast ADDR | port N
                                  | busy_w W | idle_w W | order N      (QUEUE/hearth/machines.json)
    hearth.py QUEUE outside                        fetch the outside temperature now (the airport's observation)
    hearth.py QUEUE fit-ua                         estimate the house's watts a degree from the record; adopts nothing
    hearth.py QUEUE step                           one pass of the controller: QUEUE/hearth/plan.json
    hearth.py QUEUE status                         one screen, and nothing changed
    hearth.py QUEUE wake NAME                      send the wake-on-LAN packet for one machine
    hearth.py QUEUE learn-macs                     read each machine's address over ssh (read-only)

A PROBE IS A KEY IN A MACHINE'S TELEMETRY THAT IS A TEMPERATURE OF AIR. `room.NAME.c` is found by
itself and taken for a room until told otherwise; any other key is a probe once `probe KEY role ...`
names it. A probe older than stale_s, absent from its machine's newest line, reading the 85.0 a
GMC-320 gives before its thermometer has a reading, or outside 0 to 50 is NOT A TEMPERATURE: it is
shown with the reason and never averaged. No fresh room probe, no control.

THE LAW. e = target - T, in degrees, T the mean of the fresh `room` probes. Inside the deadband e is
taken as nothing; outside it, as its excess over the band. The fleet's watts wanted are

    wanted = UA x (target - outside) + bias + kp x e + integral(ki x e dt) - kd x dT/dt

The first term is the feedforward (Paul, 16 November: "use wattage and use external temperature, our
current configuration is at seatac airport temp"): a house loses heat in proportion to how far it is
above the outside, so a colder outside asks for more watts before the room has moved. UA, watts a
degree, is the house's loss as the fleet sees it, and IT IS UNKNOWN UNTIL SET: unknown, or with no
fresh outside reading, the feedforward is nothing, the law is the rest alone, and the plan says
which. The outside is a probe of role `outside` at the house if one is fresh, else the latest
observation of the airport station (state.json's outside_station, KSEA; the US National Weather
Service, asked at most every twenty minutes; older than two hours it is not a temperature).
bias is what makes the controller begin where the fleet is: the watts the fleet drew when it began,
less the feedforward at that moment; it is moved by the feedforward's size whenever the feedforward
comes or goes, so losing the outside reading does not move the watts wanted. kp is in
watts a degree, ki in watts a degree an hour, kd in watts for a degree an hour of the room's own
slope (off: 0). wanted is held between what the ladder can shed down to and what it can add up to,
and THE INTEGRAL DOES NOT GROW WHILE THE OUTPUT IS AT A LIMIT AND THE ERROR PUSHES IT FURTHER.

THE ROOM'S OWN TIME CONSTANT IS NOT MEASURED (docs/hearth-lab-report.md, VIII: the house's step test
is not run), SO THE DEFAULTS ARE SLOW ON PURPOSE. kp 300 W/C: four degrees of error asks for the
whole fleet, about 1.2 kW. ki 25 W/C/h: an integral time of twelve hours, longer than any tau a
house of this size is likely to have, so the integral trims and does not drive. kd 0: the probe
steps in tenths and is read each five minutes; a derivative of that is noise. And whatever the law
asks, the ladder moves one rung a pass, no two changes within gap_s (15 min), none to one machine
within dwell_s (30 min).

THE LADDER, least drastic first. To shed: a machine's CPU lanes take nothing new (the queue's
pause; the job in hand finishes); then its card's lane; then, with all its lanes held and nothing in
hand, the machine is powered off. To add: the lanes held are resumed, newest held first; a machine
powered off is woken last. A rung is priced in watts from what the machine draws now
(plan/thermal.json) against its idle (tools/plans/power.json, an estimate, or this file's override),
and is taken only when taking it leaves the fleet nearer what is wanted than leaving it.

NEVER: a machine marked keep; this Mac; a machine any of whose lanes a person paused, or that is
restarting or leaving; a machine on the bench; more than one machine in a pass. A machine that
carries a room probe is never powered off. A machine with no address recorded is never powered off,
because nothing could wake it. Power-off and wake are a second switch (`set power on`), off by
default: `act` alone pauses and resumes.

WHAT ACT RUNS. Pause and resume are the queue's own commands, as a subprocess (fleet-queue.py QUEUE
machine NAME pause|resume); no queue file is written here. The queue has no power-off for one
machine (shutdown-now is the whole fleet), so that rung sends the machine's own power-off rule from
config.json over ssh, as the keeper's shutdown sends it, and only with `power on`. The queue pauses
a machine's lanes all together or a card's lane alone, so "the CPU lanes alone" is two commands:
pause NAME, then resume NAME-cuda.

State is QUEUE/hearth/: probes.json, machines.json, state.json, plan.json, log.jsonl (what was
done), record.tsv (each pass: time, room, outside, watts, watts wanted), outside.tsv. Nothing
outside it is written. HEARTH_QUEUE and HEARTH_SSH name stand-in commands, HEARTH_OUTSIDE_URL a
stand-in observation and HEARTH_NOW a clock, for tools/hearth-check.sh.
"""
import json
import math
import os
import shlex
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ControlMaster=no", "-o", "ControlPath=none"]
ROLES = ("room", "outside", "intake", "exhaust", "other")
NO_READING_C = 85.0  # a GMC-320 before its thermometer has a reading (hearth report, 16 November)
MODES = ("off", "advise", "act")

# name: (default, unit, what it is)
SETTINGS = {
    "kp": (300.0, "W/C", "watts wanted for a degree of error"),
    "ki": (25.0, "W/C/h", "watts added each hour a degree of error stands"),
    "kd": (0.0, "W per C/h", "watts taken off for the room's own rise of a degree an hour (0: off)"),
    "deadband": (0.3, "C", "an error inside this is no error"),
    "dwell": (1800.0, "s", "the least time between two changes to one machine"),
    "gap": (900.0, "s", "the least time between two changes to the fleet"),
    "stale": (600.0, "s", "a probe older than this is not a temperature"),
    "watts_stale": (900.0, "s", "the fleet's watts older than this are not known"),
    "settle": (600.0, "s", "how long a change is counted as not yet in the watts read"),
    "wake_wait": (1200.0, "s", "how long a woken machine is waited for"),
    "ua": (None, "W/C", "the house's loss as the fleet sees it, watts for a degree inside over outside (unknown: no feedforward)"),
    "outside_stale": (7200.0, "s", "an outside observation older than this is not a temperature"),
    "outside_every": (1200.0, "s", "the least time between two fetches of the outside observation"),
    "floor": (0.0, "W", "the fleet's watts are never asked below this"),
    "power": ("off", "on|off", "whether act may power a machine off and wake it"),
}


def now():
    return float(os.environ.get("HEARTH_NOW") or time.time())


def load(p, default=None):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def hp(q, *a):
    return os.path.join(q, "hearth", *a)


def save(q, name, doc):
    os.makedirs(hp(q), exist_ok=True)
    with open(hp(q, name + ".tmp"), "w") as f:
        json.dump(doc, f, indent=1)
    os.replace(hp(q, name + ".tmp"), hp(q, name))


def state(q):
    st = load(hp(q, "state.json"), {}) or {}
    st.setdefault("mode", "advise")
    st.setdefault("target_c", None)
    st.setdefault("outside_station", "KSEA")
    st.setdefault("set", {})
    st.setdefault("held", {})      # machine -> {"cpu"|"card"|"off": {"t", "w"}}: what this controller did
    st.setdefault("added", {})     # machine -> {"t", "w"}: a resume not yet in the watts read
    st.setdefault("changed", {})   # machine -> when it was last changed (the dwell)
    st.setdefault("integral_w", 0.0)
    st.setdefault("bias_w", None)
    return st


def setting(st, k):
    return st["set"].get(k, SETTINGS[k][0])


def f_of(c):
    return c * 9 / 5 + 32


def ago(s):
    s = int(s)
    return "%d s" % s if s < 120 else "%d min" % (s // 60) if s < 7200 else "%.1f h" % (s / 3600)


def parse(line):
    d = {}
    for kv in line.split():
        k, _, v = kv.partition("=")
        try:
            d[k] = float(v)
        except ValueError:
            pass
    return d


WINDOW_S = 300
JUMP_C = 3.0  # more than this in five minutes is not a room changing: it is a probe misreading


def not_a_reading(v):
    """85.0 and -0.0: what a GMC-320 says with no reading (saskatchewan's record of 16 November
    has -0.0 seven times between readings of 26)."""
    return v == NO_READING_C or (v == 0 and math.copysign(1, v) < 0)


def median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2


def last_samples(q):
    """Each machine's last five minutes of telemetry, oldest first: machine -> [{key: value}]."""
    out = {}
    base = os.path.join(q, "telemetry")
    for m in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        logs = sorted(f for f in os.listdir(os.path.join(base, m)) if f.endswith(".log"))
        for f in reversed(logs[-2:]):
            p = os.path.join(base, m, f)
            with open(p, "rb") as fh:
                fh.seek(max(0, os.path.getsize(p) - 400000))
                rows = [parse(l) for l in fh.read().decode("utf-8", "replace").split("\n")[:-1] if l.startswith("t=")]
            rows = [r for r in rows if "t" in r]
            if rows:
                out[m] = [r for r in rows if r["t"] > rows[-1]["t"] - WINDOW_S]
                break
    return out


# ---------------------------------------------------------------------------------------- probes

def probes(q, st, t, samples=None, write=True):
    """The registry with each probe's reading. A probe is `ok` only when it is a temperature."""
    samples = last_samples(q) if samples is None else samples
    reg = load(hp(q, "probes.json"), {}) or {}
    new = False
    for m, rows in samples.items():
        for k in rows[-1]:
            if k.startswith("room.") and k.endswith(".c") and k not in reg:
                reg[k] = {"machine": m, "place": "", "role": "room", "found": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t))}
                new = True
    if new and write:
        save(q, "probes.json", reg)
    out = []
    for k in sorted(reg):
        p = dict(reg[k], key=k)
        rows = samples.get(p.get("machine"), [])
        p["c"], p["age_s"], p["ok"], p["why"] = None, None, False, ""
        if p.get("source") == "nws":
            o = last_outside(q, p.get("station"))
            if o is None:
                p["why"] = "missing: no observation fetched yet (`outside`)"
            else:
                p["c"], p["age_s"] = o[1], round(t - o[2])
                if p["age_s"] > setting(st, "outside_stale"):
                    p["why"] = "stale: observed %s ago" % ago(p["age_s"])
                elif not -50 <= o[1] <= 55:
                    p["why"] = "outside -50 to 55: not taken for air"
                else:
                    p["ok"] = True
        elif not rows:
            p["why"] = "missing: %s has no telemetry" % p.get("machine")
        elif k not in rows[-1]:
            p["age_s"] = round(t - rows[-1]["t"])
            p["why"] = "missing: %s's newest line does not carry it" % p.get("machine")
        else:
            # ONE SAMPLE IS NOT THE TEMPERATURE: the median of the window's readings, with what is
            # known to be no reading thrown out first.
            good = [r[k] for r in rows if k in r and not not_a_reading(r[k])]
            p["age_s"] = round(t - rows[-1]["t"])
            lo, hi = (0, 50) if p["role"] == "room" else (-50, 55)
            was = (st.get("probe_last") or {}).get(k)
            if not good:
                p["c"] = rows[-1][k]
                p["why"] = "%s is what a counter says when its thermometer has no reading" % ("85.0" if p["c"] == NO_READING_C else "-0.0")
            else:
                p["c"] = round(median(good), 2)
                if p["age_s"] > setting(st, "stale"):
                    p["why"] = "stale: read %s ago" % ago(p["age_s"])
                elif not lo <= p["c"] <= hi:
                    p["why"] = "outside %d to %d: not taken for air" % (lo, hi)
                elif was and abs(p["c"] - was["c"]) > JUMP_C * max(1.0, (t - was["t"]) / 300.0):
                    p["why"] = "suspect: it jumped %+.1f in %s (from %.1f), more than %g degrees in five minutes" % (
                        p["c"] - was["c"], ago(t - was["t"]), was["c"], JUMP_C)
                else:
                    p["ok"] = True
        out.append(p)
    return out


def controlled(ps):
    """(the mean of the fresh room probes or None, the probes it is the mean of)."""
    used = [p for p in ps if p["role"] == "room" and p["ok"]]
    return (sum(p["c"] for p in used) / len(used) if used else None), used


def outside_of(ps):
    """(the outside temperature or None, the probes it is from, why not). A probe at the house
    comes before the airport's."""
    fresh = [p for p in ps if p["role"] == "outside" and p["ok"]]
    used = [p for p in fresh if p.get("source") != "nws"] or fresh
    if used:
        return sum(p["c"] for p in used) / len(used), used, ""
    return None, [], "no fresh outside probe: %s" % ("; ".join("%s %s" % (p["key"], p["why"]) for p in ps if p["role"] == "outside") or "none is known (`outside` fetches the airport's)")


def last_outside(q, station):
    """The newest line of outside.tsv for a station: (fetched, degrees C, observed), epoch seconds."""
    try:
        lines = open(hp(q, "outside.tsv")).read().splitlines()
    except OSError:
        return None
    for l in reversed(lines):
        w = l.split("\t")
        if len(w) >= 5 and w[4] == station:
            try:
                return float(w[0]), float(w[1]), float(w[2])
            except ValueError:
                pass
    return None


def fetch_outside(q, st, t):
    """The station's latest observation, appended to outside.tsv and made a probe. (degrees C or
    None, what to say). THE REQUEST CARRIES NOTHING OF THIS HOUSE: a generic client name, no more.
    A fetch that fails is said and is nothing worse: the last observation ages until it is stale."""
    station = st.get("outside_station") or "KSEA"
    url = os.environ.get("HEARTH_OUTSIDE_URL") or "https://api.weather.gov/stations/%s/observations/latest" % station
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "orrery-hearth", "Accept": "application/geo+json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            pr = json.load(r)["properties"]
        c, stamp = pr["temperature"]["value"], pr["timestamp"]
        if c is None:
            return None, "%s's latest observation carries no temperature" % station
        c, obs = float(c), datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
    except Exception as e:  # the network, the JSON, the shape: none of them is this controller's to fix
        return None, "the fetch of %s failed: %s" % (station, str(e)[:120] or type(e).__name__)
    os.makedirs(hp(q), exist_ok=True)
    with open(hp(q, "outside.tsv"), "a") as f:
        f.write("%d\t%.1f\t%d\t%s\t%s\n" % (t, c, obs, stamp, station))
    key = "outside.%s.c" % station.lower()
    reg = load(hp(q, "probes.json"), {}) or {}
    if key not in reg:
        reg[key] = {"machine": "", "place": "SeaTac airport (KSEA)" if station == "KSEA" else pr.get("stationName") or station,
                    "role": "outside", "source": "nws", "station": station}
        save(q, "probes.json", reg)
    return c, "%s: %.1f C (%.1f F), observed %s ago (%s)" % (station, c, f_of(c), ago(max(0, t - obs)), stamp)


def print_probes(ps):
    if not ps:
        print("no probe: no room.NAME.c in any machine's telemetry, and none named")
    for p in ps:
        print("  %-22s %-8s %-14s %-20s %s" % (
            p["key"], p["role"], p.get("machine") or ("the weather service" if p.get("source") == "nws" else "?"), p.get("place") or "(no place named)",
            "%.1f C (%.1f F), %s %s ago" % (p["c"], f_of(p["c"]), "observed" if p.get("source") == "nws" else "read", ago(p["age_s"])) if p["ok"] else
            "NOT A TEMPERATURE: %s%s" % (p["why"], " (it said %.1f)" % p["c"] if p["c"] is not None and p["why"].startswith(("stale", "suspect")) else "")))


# ----------------------------------------------------------------------------------------- fleet

def fleet(q, st, t):
    """Each machine as the ladder sees it: its lanes, who paused them, what is in hand, its watts."""
    cfg = load(os.path.join(q, "config.json"), {}) or {}
    th = load(os.path.join(q, "plan", "thermal.json"), {}) or {}
    boxes = (load(os.path.join(HERE, "plans", "power.json"), {}) or {}).get("boxes", {})
    mine = load(hp(q, "machines.json"), {}) or {}
    th_age = t - th.get("t", 0)
    ms = {}

    def row(name):
        return ms.setdefault(name, {"name": name, "cpu": [], "card": [], "bench": False, "target": "", "poweroff": None,
                                    "special": "", "wall_w": None, "cpu_w": None, "gpu_w": None, "fresh": False,
                                    "box": boxes.get(name) or {}, "mine": mine.get(name) or {}, "in_hand": []})
    for where in ("hosts", "bench"):
        for h in cfg.get(where, []):
            m = row(h.get("lane_of", h["name"]))
            if where == "bench":
                m["bench"] = True
                continue
            m["card" if "cuda" in h.get("caps", []) else "cpu"].append(h)
            if not h.get("lane_of"):
                m["target"], m["poweroff"] = h.get("target", ""), h.get("poweroff")
            for k in ("restarting", "leaving"):
                if h.get(k):
                    m["special"] = k
            d = os.path.join(q, "running", h["name"])
            if os.path.isdir(d) and any(f.endswith(".json") for f in os.listdir(d)):
                m["in_hand"].append(h["name"])
    for x in th.get("machines", []):
        m = row(x["name"])
        if not m["cpu"] and not m["card"] and not m["bench"]:
            m["bench"] = True  # read, and not in the queue: it heats the room all the same
        # Fresh as thermal.py counts it: read within ten minutes of the model being made.
        if x.get("wall_w") is not None and (x.get("age_s") or 0) < 600 and th_age <= setting(st, "watts_stale"):
            m.update(fresh=True, wall_w=x["wall_w"], cpu_w=x.get("cpu_w"), gpu_w=x.get("gpu_w"), age_s=round(th_age + (x.get("age_s") or 0)))
    return cfg, ms, th_age


def eff(m):
    return m["box"].get("eff", 0.88)


def price(m, kind):
    """(watts at the wall this rung is worth, where the figure is from)."""
    o, b = m["mine"], m["box"]
    card_w = None
    if m["card"]:
        card_w = max(0.0, ((m["gpu_w"] or 0) - b.get("gpu_idle_w", 10)) / eff(m)) if m["gpu_w"] is not None else None
    if kind == "card":
        return (card_w, "the card's watts read now, less its idle (an estimate)") if card_w is not None else (None, "its card's watts are not read")
    if kind == "cpu":
        if "busy_w" in o and "idle_w" in o:
            return max(0.0, o["busy_w"] - o["idle_w"] - (card_w or 0)), "the override in hearth/machines.json"
        if m["cpu_w"] is not None and b:
            return max(0.0, (m["cpu_w"] - b.get("cpu_idle_w", 0)) / eff(m)), "the CPU's watts read now, less its idle (an estimate)"
        return None, "its watts are not read"
    # off, or wake: what it draws doing nothing
    if "idle_w" in o:
        return float(o["idle_w"]), "the override in hearth/machines.json"
    if b:
        return (b.get("rest_w", 0) + b.get("cpu_idle_w", 0) + (b.get("gpu_idle_w", 0) if "gpu" in b else 0)) / eff(m), "an estimate (tools/plans/power.json)"
    return None, "no figure for it idle"


def busy_estimate(m):
    """What a machine not now working would draw at work: an estimate, for the suggestion only."""
    o, b = m["mine"], m["box"]
    if "busy_w" in o:
        return float(o["busy_w"])
    if b:
        return (b.get("rest_w", 0) + b.get("cpu_full_w", 0) * 0.9 + b.get("gpu_limit_w", 0) * 0.6) / eff(m)
    return None


def ladder(q, st, t, cfg, ms, ps):
    """Both sides of the ladder, in order, each rung with its state. `open` is the only state a
    rung can be taken in; `wait` is a rung that will open by itself and holds the more drastic
    kinds behind it; `after` is a rung that opens once another has been taken."""
    probe_hosts = {p.get("machine") for p in ps if p["role"] == "room"}
    power = setting(st, "power") == "on"
    dwell = setting(st, "dwell")
    shed, add = [], []

    def never(m):
        if m["mine"].get("keep"):
            return "keep"
        if m["target"] == "-":
            return "keep: this Mac runs the keeper"
        if m["bench"]:
            return "on the bench: a person removed it"
        if m["special"]:
            return "by hand: it is %s" % m["special"]
        held = st["held"].get(m["name"], {})
        for kind in ("cpu", "card"):
            if m[kind] and all(h.get("paused") for h in m[kind]) and kind not in held:
                return "by hand: a person paused its %s" % ("lanes" if kind == "cpu" else "card's lane")
        if any(h.get("paused") for h in m["cpu"] + m["card"]) and not held:
            return "by hand: a person paused one of its lanes"
        return ""

    def dwelling(m):
        left = dwell - (t - st["changed"].get(m["name"], 0))
        return "wait: changed %s ago, %s of its dwell left" % (ago(dwell - left), ago(left)) if left > 0 else ""

    for name in sorted(ms):
        m = ms[name]
        held = st["held"].get(name, {})
        no = never(m)
        off = "off" in held
        for kind in ("cpu", "card"):
            if not m[kind]:
                continue
            what = "its CPU lanes take nothing new" if kind == "cpu" else "its card's lane takes nothing new"
            if kind in held:
                # The other side: what was shed can be added.
                r = {"id": "%s:%s" % (name, kind), "side": "add", "kind": "resume", "machine": name,
                     "what": "its %s work again" % ("CPU lanes" if kind == "cpu" else "card's lane"),
                     "watts": held[kind].get("w"), "from": "what it was worth when it was shed", "at": held[kind]["t"]}
                r["state"] = no or ("after: it is powered off, and is woken first" if off else dwelling(m) or "open")
                add.append(r)
                continue
            w, src = price(m, kind)
            r = {"id": "%s:%s" % (name, kind), "side": "shed", "kind": kind, "machine": name, "what": what, "watts": w, "from": src}
            r["state"] = (no or ("absent: %s" % src if w is None else "")
                          or ("wait: its CPU lanes go first" if kind == "card" and m["cpu"] and "cpu" not in held else "")
                          or dwelling(m) or "open")
            shed.append(r)
        if not m["cpu"] and not m["card"]:
            continue
        w, src = price(m, "off")
        if off:
            o = held["off"]
            r = {"id": name + ":off", "side": "add", "kind": "wake", "machine": name, "what": "it is woken (wake-on-LAN)",
                 "watts": o.get("w"), "from": "what it drew idle when it was powered off", "at": o["t"]}
            r["state"] = (no or ("not allowed: power is off (`set power on`)" if not power else "")
                          or ("absent: no address recorded" if not m["mine"].get("mac") else "")
                          or ("wait: woken %s ago, not yet answering" % ago(t - o["woke"]) if o.get("woke") else "")
                          or dwelling(m) or "open")
            add.append(r)
        else:
            all_held = all(k in held for k in ("cpu", "card") if m[k])
            r = {"id": name + ":off", "side": "shed", "kind": "off", "machine": name, "what": "it is powered off", "watts": w, "from": src}
            r["state"] = (no or ("keep: it carries a room probe" if name in probe_hosts else "")
                          or ("absent: no power-off rule in config.json" if not m["poweroff"] else "")
                          or ("absent: no address recorded, so nothing could wake it (learn-macs)" if not m["mine"].get("mac") else "")
                          or ("absent: %s" % src if w is None else "")
                          or ("not allowed: power is off (`set power on`)" if not power else "")
                          or ("wait: its lanes go first" if not all_held else "")
                          or ("wait: %s still in hand" % ", ".join(m["in_hand"]) if m["in_hand"] else "")
                          or ("absent: it is not read, so it may be off already" if not m["fresh"] else "")
                          or dwelling(m) or "open")
            shed.append(r)
    kinds = {"cpu": 0, "card": 1, "off": 2, "resume": 0, "wake": 1}
    shed.sort(key=lambda r: (kinds[r["kind"]], ms[r["machine"]]["mine"].get("order", 0), r["watts"] if r["watts"] is not None else 0, r["machine"]))
    add.sort(key=lambda r: (kinds[r["kind"]], -r["at"], r["machine"]))
    return shed, add


def can(r):
    """A rung the ladder can still reach: now, or in its turn."""
    return r["state"] == "open" or r["state"].startswith(("wait", "after"))


def first_open(rungs):
    """The next rung in ladder order, or why there is none. A rung that waits holds every more
    drastic kind behind it: the ladder is climbed in order."""
    waits = None
    for r in rungs:
        if r["state"] == "open":
            if waits and waits["kind"] != r["kind"]:
                return None, "%s (%s)" % (waits["id"], waits["state"])
            return r, ""
        if r["state"].startswith("wait") and waits is None:
            waits = r
    return None, ("%s (%s)" % (waits["id"], waits["state"]) if waits else "")


# ------------------------------------------------------------------------------------ the doing

def run_queue(q, *args):
    """The queue's own command, as a subprocess. (ok, what it said)."""
    cmd = shlex.split(os.environ["HEARTH_QUEUE"]) if os.environ.get("HEARTH_QUEUE") else [sys.executable, os.path.join(HERE, "fleet-queue.py")]
    try:
        r = subprocess.run(cmd + [q] + list(args), capture_output=True, text=True, timeout=120)
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, repr(e)
    return r.returncode == 0, ((r.stdout or "") + (r.stderr or "")).strip()[-300:]


def run_ssh(target, script, timeout=60):
    cmd = shlex.split(os.environ["HEARTH_SSH"]) if os.environ.get("HEARTH_SSH") else SSH
    try:
        r = subprocess.run(cmd + [target, script], capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError) as e:
        return 255, repr(e)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def magic_packet(mac):
    """Six bytes of FF, then the address sixteen times: 102 bytes."""
    hexes = mac.replace(":", "").replace("-", "").replace(".", "")
    if len(hexes) != 12:
        raise ValueError("not a hardware address: %r" % mac)
    return b"\xff" * 6 + bytes.fromhex(hexes) * 16


def send_wake(rec):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        pkt = magic_packet(rec["mac"])
        for _ in range(3):
            s.sendto(pkt, (rec.get("broadcast", "255.255.255.255"), int(rec.get("port", 9))))
    finally:
        s.close()


def commands(m, r, st):
    """What a rung is, as the commands it would run, in order."""
    name = m["name"]
    held = st["held"].get(name, {})
    cards = [h["name"] for h in m["card"]]
    if r["kind"] == "cpu":
        return [["queue", "machine", name, "pause"]] + [["queue", "machine", c, "resume"] for c in cards if "card" not in held]
    if r["kind"] == "card":
        return [["queue", "machine", c, "pause"] for c in cards]
    if r["kind"] == "off":
        return [["ssh", m["target"], "nohup sh -c 'sleep 2; %s' >/dev/null 2>&1 &" % m["poweroff"]]]
    if r["kind"] == "wake":
        return [["wake", name]]
    if r["id"].endswith(":card"):
        return [["queue", "machine", c, "resume"] for c in cards]
    # The CPU lanes back: resume is every lane of the machine, so a card still held is paused again.
    return [["queue", "machine", name, "resume"]] + [["queue", "machine", c, "pause"] for c in cards if "card" in held]


def words(c):
    return ("fleet-queue.py QUEUE " + " ".join(c[1:])) if c[0] == "queue" else ("ssh %s '%s'" % (c[1], c[2].split("; ")[-1].split("'")[0])) if c[0] == "ssh" else "the wake packet to " + c[1]


def do(q, st, t, m, r):
    """Carry one rung out. The first command that fails ends it: nothing is retried in this pass."""
    name = m["name"]
    held = st["held"].setdefault(name, {})
    ran = []
    ok = True
    before = dict(held)
    for c in commands(m, r, st):
        if c[0] == "queue":
            good, said = run_queue(q, *c[1:])
            # What the queue was told is what is held, command by command, so a half-done rung is
            # recorded as it stands: a pause of every lane that was not followed by the card's
            # resume leaves the card held too, and the ladder then knows to give it back.
            for kind in (("cpu", "card") if c[2] == name else ("card",)) if good else ():
                if not m[kind]:
                    continue
                if c[3] == "resume":
                    held.pop(kind, None)
                elif kind not in held:
                    held[kind] = before.get(kind) or {"t": t, "w": round((r["watts"] if kind == r["kind"] else price(m, kind)[0]) or 0, 1)}
        elif c[0] == "ssh":
            rc, said = run_ssh(c[1], c[2])
            good = rc in (0, 255)  # the connection drops as the machine goes down
            if good:
                held["off"] = {"t": t, "w": round(r["watts"] or 0, 1)}
        else:
            try:
                send_wake(m["mine"])
                good, said = True, "sent to %s port %s" % (m["mine"].get("broadcast", "255.255.255.255"), m["mine"].get("port", 9))
                held["off"]["woke"] = t
            except (OSError, ValueError) as e:
                good, said = False, repr(e)
        ran.append({"cmd": words(c), "ok": good, "said": said})
        if not good:
            ok = False
            break
    if ok and r["kind"] == "resume":
        st["added"][name] = {"t": t, "w": r["watts"] or 0}
    if not held:
        st["held"].pop(name, None)
    st["changed"][name] = t
    st["last_action_t"] = t
    rec = {"t": t, "at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t)), "rung": r["id"], "side": r["side"],
           "what": "%s: %s" % (name, r["what"]), "watts": r["watts"], "ok": ok, "ran": ran}
    st["last_action"] = rec
    os.makedirs(hp(q), exist_ok=True)
    with open(hp(q, "log.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


# ----------------------------------------------------------------------------------- one pass

def slope_c_h(q, used, t):
    """The room's own slope over the last half hour, degrees an hour (for kd)."""
    pts = []
    for p in used:
        d = os.path.join(q, "telemetry", p["machine"])
        for f in sorted(x for x in os.listdir(d) if x.endswith(".log"))[-2:]:
            for line in open(os.path.join(d, f)):
                s = parse(line)
                if p["key"] in s and t - 1800 <= s.get("t", 0) <= t and not not_a_reading(s[p["key"]]):
                    pts.append((s["t"], s[p["key"]]))
    if len(pts) < 10 or max(x for x, _ in pts) - min(x for x, _ in pts) < 900:
        return 0.0
    mx, my = sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts)
    den = sum((x - mx) ** 2 for x, _ in pts)
    return sum((x - mx) * (y - my) for x, y in pts) / den * 3600 if den else 0.0


def reconcile(st, t, ms, said):
    """What this controller holds, against what the queue says now. A person's hand wins."""
    for name in list(st["held"]):
        m, held = ms.get(name), st["held"][name]
        if m is None or m["bench"] or not (m["cpu"] or m["card"]):
            said.append("%s left the queue by a person's hand: it is no longer this controller's" % name)
            del st["held"][name]
            st["changed"][name] = t
            continue
        for kind in ("cpu", "card"):
            if kind in held and not all(h.get("paused") for h in m[kind]):
                said.append("%s's %s were resumed by a person: no longer held here" % (name, "CPU lanes" if kind == "cpu" else "card's lane"))
                del held[kind]
                st["changed"][name] = t
        o = held.get("off")
        if o and o.get("woke"):
            if m["fresh"] and m.get("age_s", 1e9) < t - o["woke"]:
                said.append("%s answers again, %s after it was woken" % (name, ago(t - o["woke"])))
                del held["off"]
                st["changed"][name] = t
            elif t - o["woke"] > setting(st, "wake_wait"):
                said.append("%s was woken %s ago and does not answer: wake-on-LAN may be off in its BIOS; it will be tried again after its dwell" % (name, ago(t - o["woke"])))
                o.pop("woke")
                st["changed"][name] = t
        elif o and m["fresh"] and t - o["t"] > setting(st, "settle") and m.get("age_s", 1e9) < t - o["t"] - 120:
            said.append("%s was sent its power-off %s ago and still answers: it is taken as on" % (name, ago(t - o["t"])))
            del held["off"]
            st["changed"][name] = t
        if not held:
            del st["held"][name]


def step(q, dry=False):
    """One pass. Returns the plan; unless dry, writes plan.json and state.json, and in act does
    at most one rung."""
    st = state(q)
    t = now()
    plan = {"t": t, "made": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t)), "mode": st["mode"], "target_c": st["target_c"]}
    # EVERY KEY IS THERE IN EVERY PLAN, null where a pass did not get that far: Orrery's Heat panel
    # reads this file, and a key that comes and goes is a panel that breaks on a stale probe.
    for k in ("temp_c", "outside_c", "outside_age_s", "ua_w_per_c", "now_w", "expected_w", "error_c", "error_past_deadband_c",
              "terms", "gains", "feedforward_w", "correction_w", "unclamped_w", "floor_w", "max_w", "wanted_w", "integral_held",
              "diff_w", "would", "did", "shortfall"):
        plan[k] = None
    for k in ("temp_from", "outside_from", "probes", "ladder", "read", "not_read", "pending"):
        plan[k] = []
    for k in ("stopped", "feedforward_why", "clamped", "why_not"):
        plan[k] = ""
    said = plan["said"] = []
    if st["mode"] == "off":
        said.append("off: nothing is read, planned or done")
        return plan
    if not dry and t - st.get("outside_tried_t", 0) >= setting(st, "outside_every"):
        st["outside_tried_t"] = t
        c, word = fetch_outside(q, st, t)
        if c is None:
            said.append("outside: " + word)
    ps = probes(q, st, t, write=not dry)
    temp, used = controlled(ps)
    # What each probe said this pass, for the next pass's look at a jump. A suspect reading is kept
    # too: one that stays where it jumped to is taken at the next pass.
    st["probe_last"] = {p["key"]: {"t": t, "c": p["c"]} for p in ps if p.get("source") != "nws" and p["c"] is not None
                        and (p["ok"] or p["why"].startswith("suspect"))}
    out_c, out_used, out_why = outside_of(ps)
    plan["outside_c"] = round(out_c, 1) if out_c is not None else None
    plan["outside_age_s"] = max(p["age_s"] for p in out_used) if out_used else None
    plan["outside_from"] = [p["key"] for p in out_used]
    plan["ua_w_per_c"] = setting(st, "ua")
    cfg, ms, th_age = fleet(q, st, t)
    reconcile(st, t, ms, said)
    shed, add = ladder(q, st, t, cfg, ms, ps)
    plan["probes"] = [{k: p.get(k) for k in ("key", "role", "machine", "place", "c", "age_s", "ok", "why")} for p in ps]
    plan["temp_c"] = round(temp, 2) if temp is not None else None
    plan["temp_from"] = [p["key"] for p in used]
    plan["ladder"] = shed + add
    for r in plan["ladder"]:
        r["watts"] = round(r["watts"], 1) if r["watts"] is not None else None

    # The watts now, and what is on its way into them.
    fresh = [m for m in ms.values() if m["fresh"]]
    now_w = float(sum(m["wall_w"] for m in fresh)) if fresh and th_age <= setting(st, "watts_stale") else None
    pending = []
    settle = setting(st, "settle")
    for name, held in st["held"].items():
        m = ms[name]
        for kind in ("cpu", "card"):
            lanes = {h["name"] for h in m[kind]}
            if kind in held and "off" not in held and (lanes & set(m["in_hand"]) or t - held[kind]["t"] < settle):
                pending.append({"rung": "%s:%s" % (name, kind), "w": -held[kind]["w"],
                                "why": "the job in hand still runs" if lanes & set(m["in_hand"]) else "shed %s ago" % ago(t - held[kind]["t"])})
        o = held.get("off")
        if o and not o.get("woke") and m["fresh"]:
            pending.append({"rung": name + ":off", "w": -o["w"], "why": "sent its power-off %s ago, still read" % ago(t - o["t"])})
        if o and o.get("woke"):
            pending.append({"rung": name + ":off", "w": o["w"], "why": "woken %s ago" % ago(t - o["woke"])})
    for name in list(st["added"]):
        a = st["added"][name]
        if t - a["t"] < settle:
            pending.append({"rung": name + ":resume", "w": a["w"], "why": "resumed %s ago" % ago(t - a["t"])})
        else:
            del st["added"][name]
    plan["now_w"] = round(now_w) if now_w is not None else None
    plan["read"] = sorted(m["name"] for m in fresh)
    plan["not_read"] = sorted(m["name"] for m in ms.values() if not m["fresh"])
    plan["pending"] = pending
    expected = now_w + sum(p["w"] for p in pending) if now_w is not None else None
    plan["expected_w"] = round(expected) if expected is not None else None
    if not dry:
        with open(hp(q, "record.tsv"), "a") as f:
            f.write("%d\t%s\t%s\t%s\n" % (t, "%.2f" % temp if temp is not None else "", "%.1f" % out_c if out_c is not None else "",
                                           "%d" % now_w if now_w is not None else ""))

    stop = ("no target is set (`target 21.0`)" if st["target_c"] is None else
            "no fresh room probe: %s" % ("; ".join("%s %s" % (p["key"], p["why"]) for p in ps if p["role"] == "room") or "none is known") if temp is None else
            "the fleet's watts are not known: plan/thermal.json is %s old" % ago(th_age) if now_w is None else "")
    if stop:
        # NOT A TEMPERATURE, NOT A PLAN. The integral stands where it was; the clock is let go so
        # the gap is not integrated when the reading returns.
        plan["stopped"] = stop
        said.append("nothing is planned and nothing is done: " + stop)
        st.pop("last_step_t", None)
        if not dry:
            save(q, "plan.json", plan)
            save(q, "state.json", st)
        return plan

    kp, ki, kd, db = (setting(st, k) for k in ("kp", "ki", "kd", "deadband"))
    e = st["target_c"] - temp
    e_db = 0.0 if abs(e) <= db else e - db * (1 if e > 0 else -1)
    ua = setting(st, "ua")
    ff_on = ua is not None and out_c is not None
    ff = ua * (st["target_c"] - out_c) if ff_on else 0.0
    ff_why = "" if ff_on else "UA is unknown (`fit-ua`, then `set ua N`)" if ua is None else out_why
    if st["bias_w"] is None:
        st["bias_w"], st["integral_w"] = expected - ff, 0.0
    elif ff_on != st.get("ff_on", False):
        # The feedforward came or went: the bias takes its size up, so the watts wanted do not move.
        st["bias_w"] += st.get("feedforward_w", 0.0) - ff
    st["ff_on"], st["feedforward_w"] = ff_on, ff
    lo = max(setting(st, "floor"), expected - sum(r["watts"] or 0 for r in shed if can(r)))
    hi = max(lo, expected + sum(r["watts"] or 0 for r in add if can(r)))
    dt_h = min(t - st["last_step_t"], 900.0) / 3600 if st.get("last_step_t") else 0.0
    p_w = kp * e_db
    d_w = -kd * slope_c_h(q, used, t) if kd else 0.0
    i_w = st["integral_w"] + ki * e_db * dt_h
    raw = ff + st["bias_w"] + p_w + i_w + d_w
    wound = (raw > hi and e_db > 0) or (raw < lo and e_db < 0)
    if wound:
        i_w = st["integral_w"]  # at a limit, pushed further: the integral stands
        raw = ff + st["bias_w"] + p_w + i_w + d_w
    wanted = min(hi, max(lo, raw))
    st["integral_w"], st["last_step_t"] = i_w, t
    plan.update(error_c=round(e, 2), error_past_deadband_c=round(e_db, 2),
                terms={"bias_w": round(st["bias_w"]), "p_w": round(p_w), "i_w": round(i_w, 1), "d_w": round(d_w, 1)},
                gains={"kp_w_c": kp, "ki_w_c_h": ki, "kd_w_per_c_h": kd, "deadband_c": db},
                feedforward_w=round(ff), feedforward_why=ff_why, correction_w=round(raw - ff),
                unclamped_w=round(raw), floor_w=round(lo), max_w=round(hi), wanted_w=round(wanted),
                clamped="at the most the fleet can give" if raw > hi else "at the least it can shed to" if raw < lo else "",
                integral_held=wound)
    diff = wanted - expected
    plan["diff_w"] = round(diff)

    said.append("the room is %.1f C (%.1f F), the mean of %s; the target is %.1f C (%.1f F); the error is %+.1f" % (
        temp, f_of(temp), ", ".join(p["key"] for p in used), st["target_c"], f_of(st["target_c"]), e))
    said.append("outside %s; %s" % (
        "%.1f C (%.1f F) by %s, %s old" % (out_c, f_of(out_c), ", ".join(plan["outside_from"]), ago(plan["outside_age_s"])) if out_c is not None else "is not known",
        "feedforward %d W = UA %g W/C x %.1f degrees under the target" % (ff, ua, st["target_c"] - out_c) if ff_on else "no feedforward: " + ff_why))
    said.append("the fleet draws %d W (%s read%s)%s; wanted %d W (%sbias %d, P %+d, I %+d%s)%s" % (
        now_w, ", ".join(plan["read"]), "; not read and not counted: " + ", ".join(plan["not_read"]) if plan["not_read"] else "",
        "; %+d W on its way (%s)" % (sum(p["w"] for p in pending), "; ".join("%s %s" % (p["rung"], p["why"]) for p in pending)) if pending else "",
        wanted, "feedforward %d, " % ff if ff_on else "", st["bias_w"], p_w, i_w, ", D %+d" % d_w if kd else "",
        ", held %s (the law alone asks %d W; the integral stands)" % (plan["clamped"], raw) if plan["clamped"] else ""))

    # The one rung, if any.
    side = shed if diff < 0 else add
    r, held_by = first_open(side)
    gap_left = setting(st, "gap") - (t - st.get("last_action_t", 0))
    would = None
    if abs(e) <= db and abs(diff) < 1:
        why = "inside the deadband of %.1f: nothing to do" % db
    elif r is None:
        why = ("nothing on the ladder to %s" % ("shed" if diff < 0 else "add")) + (": it waits on %s" % held_by if held_by else "")
    elif (diff < 0) != (e < 0):
        # NO RUNG AGAINST THE ROOM. Heat is not added to a room over its target nor shed from one
        # under it, whatever the watts say: without this the fleet sat on the deadband's edge
        # shedding a rung and giving it back a dwell later, for days (the check's room found it).
        why = "the law asks %+d W, and the room is %s its target: no rung is taken against the room" % (diff, "over" if e < 0 else "under")
    elif abs(diff) < (r["watts"] or 0) / 2:
        why = "the next rung (%s, %d W) is more than twice the %d W asked: taking it would leave the fleet further from what is wanted" % (r["id"], r["watts"], abs(diff))
    elif gap_left > 0:
        why = "the next rung is %s (%d W); the last change was %s ago, and the fleet is given %s between changes" % (
            r["id"], r["watts"] or 0, ago(setting(st, "gap") - gap_left), ago(setting(st, "gap")))
    else:
        why = ""
        would = {"rung": r["id"], "side": r["side"], "what": "%s: %s" % (r["machine"], r["what"]), "watts": r["watts"], "from": r["from"],
                 "cmds": [words(c) for c in commands(ms[r["machine"]], r, st)]}
    plan["would"], plan["why_not"] = would, why
    if would:
        said.append("%s %d W: %s, about %d W (%s)" % ("to shed" if diff < 0 else "to add", abs(diff), would["what"], would["watts"] or 0, would["from"]))
        for c in would["cmds"]:
            said.append("    " + c)
    else:
        said.append("no change: " + why)

    # Every rung used and the room still cold: say what is short, and which machine would cover it.
    if raw > hi and e > db and not any(can(x) for x in add):
        short = raw - hi
        spare = sorted(((busy_estimate(m), m["name"], "on the bench: Add brings it back" if m["fresh"] else "on the bench and not read: it is off or away; switch it on, then Add")
                        for m in ms.values() if m["bench"] and busy_estimate(m)), reverse=True)
        cover = [x for x in spare if x[0] >= short]
        pick = [min(cover)] if cover else spare
        plan["shortfall"] = {"w": round(short), "would_cover": [{"machine": n, "about_w": round(w), "how": how} for w, n, how in pick],
                             "covers": bool(cover) or sum(w for w, _, _ in pick) >= short}
        said.append("every rung is used and the room is %.1f under its target: the fleet is %d W short of what the law asks. %s" % (
            e, short, ("Starting %s would cover it" if plan["shortfall"]["covers"] else "Starting %s would not cover it") % " and ".join(
                "%s (about %d W at work, an estimate; %s)" % (n, w, how) for w, n, how in pick) if pick else "No machine on the bench is known that would cover it"))

    plan["did"] = None
    if st["mode"] == "act" and would and not dry:
        rec = do(q, st, t, ms[r["machine"]], r)
        plan["did"] = rec
        said.append("done: " + rec["what"] if rec["ok"] else "FAILED, and not tried again in this pass: %s (%s)" % (rec["what"], rec["ran"][-1]["said"][:200]))
    elif would:
        said.append("advise: nothing was done" if st["mode"] == "advise" else "a look only: nothing was done")
    if not dry:
        save(q, "plan.json", plan)
        save(q, "state.json", st)
    return plan


# ------------------------------------------------------------------------------------- commands

def status(q):
    st = state(q)
    t = now()
    print("mode %s%s; target %s" % (st["mode"], "" if st["mode"] != "act" else ", power %s" % setting(st, "power"),
                                    "%.1f C (%.1f F)" % (st["target_c"], f_of(st["target_c"])) if st["target_c"] is not None else "not set"))
    print("probes:")
    print_probes(probes(q, st, t, write=False))
    if st["mode"] == "off":
        print("off: nothing is read, planned or done")
    else:
        plan = step(q, dry=True)
        for line in plan["said"]:
            print(line)
        print("the ladder:")
        for r in plan.get("ladder", []):
            print("  %-5s %-20s %6s  %-34s %s" % (r["side"], r["id"], "%d W" % r["watts"] if r["watts"] is not None else "?", r["what"], r["state"]))
    a = st.get("last_action")
    print("the last action: %s" % ("%s, %s ago (%s)%s" % (a["what"], ago(t - a["t"]), a["at"], "" if a["ok"] else ", which FAILED") if a else "none, ever"))
    return 0


def learn_macs(q):
    cfg = load(os.path.join(q, "config.json"), {}) or {}
    mine = load(hp(q, "machines.json"), {}) or {}
    script = ("if command -v ip >/dev/null 2>&1; then dev=$(ip -o route get 1.1.1.1 2>/dev/null | sed -n 's/.* dev \\([^ ]*\\).*/\\1/p');"
              " echo dev $dev; echo mac $(cat /sys/class/net/$dev/address);"
              " ip -o -4 addr show dev $dev | sed -n 's/.* brd \\([0-9.]*\\).*/brd \\1/p' | head -1;"
              " else dev=$(route -n get default | awk '/interface/{print $2}'); echo dev $dev;"
              " ifconfig $dev | awk '$1 == \"ether\" {print \"mac \" $2} /broadcast/{print \"brd \" $NF}'; fi")
    seen = set()
    for h in cfg.get("hosts", []) + cfg.get("bench", []):
        name = h.get("lane_of", h["name"])
        if name in seen or h.get("target", "-") == "-":
            continue
        seen.add(name)
        rc, out = run_ssh(h["target"], script, timeout=30)
        got = {}
        for l in out.splitlines():
            w = l.split()
            if len(w) == 2 and w[0] in ("dev", "mac", "brd"):
                got[w[0]] = w[1]
        try:
            magic_packet(got.get("mac", ""))
        except ValueError:
            got.pop("mac", None)
        if rc != 0 or "mac" not in got:
            print("%-14s not read: %s" % (name, (out.splitlines() or ["rc %d" % rc])[-1][:120]))
            continue
        rec = mine.setdefault(name, {})
        rec.update(mac=got["mac"].lower(), dev=got.get("dev", ""))
        if "brd" in got:
            rec["broadcast"] = got["brd"]
        print("%-14s %s on %s, broadcast %s" % (name, rec["mac"], rec["dev"], rec.get("broadcast", "(not told: 255.255.255.255)")))
    save(q, "machines.json", mine)
    return 0


def fit_ua(q, st):
    """UA from the record, where the room held still. In a room that is neither warming nor
    cooling what goes in goes out: watts = UA x (room - outside). So over each three hours in which
    the room moved less than 0.3 degrees, UA is about the mean watts over the mean difference.
    THE FLEET IS NOT THE HOUSE'S ONLY HEAT (people, sun, whatever else heats it), so this is watts
    of fleet a degree with everything else as it was. Nothing is adopted."""
    rows = []
    try:
        for l in open(hp(q, "record.tsv")):
            w = l.rstrip("\n").split("\t")
            if len(w) >= 4 and w[1] and w[2] and w[3]:
                rows.append(tuple(float(x) for x in w[:4]))
    except OSError:
        pass
    all_h = (rows[-1][0] - rows[0][0]) / 3600 if rows else 0.0
    fits, i = [], 0
    while i < len(rows):
        j = i
        while j < len(rows) and rows[j][0] < rows[i][0] + 3 * 3600:
            j += 1
        win = rows[i:j]
        i = j
        room = [r[1] for r in win]
        gaps = max([b[0] - a[0] for a, b in zip(win, win[1:])] or [1e9])
        over = sum(r[1] - r[2] for r in win) / len(win)
        if win[-1][0] - win[0][0] >= 2.5 * 3600 and gaps <= 1800 and max(room) - min(room) < 0.3 and over >= 3:
            fits.append(sum(r[3] for r in win) / len(win) / over)
    print("the record: %d passes (lines) with the room, the outside and the watts all read, over %.1f hours; %d steady three-hour stretches (%d hours)" % (
        len(rows), all_h, len(fits), 3 * len(fits)))
    if len(fits) < 4:
        print("not enough to fit UA: it wants at least twelve hours in which the room held within 0.3 degrees and stood three degrees over the outside%s" % (
            "; what there is says %s W/C" % ", ".join("%d" % x for x in fits) if fits else ""))
        return 1
    fits.sort()
    mid = fits[len(fits) // 2] if len(fits) % 2 else (fits[len(fits) // 2 - 1] + fits[len(fits) // 2]) / 2
    print("UA is about %d W/C (the median; from %d to %d across the stretches)" % (mid, fits[0], fits[-1]))
    print("that is watts of FLEET for a degree, with the house's other heat as it was in those hours; it is not adopted. To use it:")
    print("    hearth.py QUEUE set ua %d" % mid)
    return 0


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    q, cmd, a = os.path.abspath(argv[1]), argv[2], argv[3:]
    if not os.path.isfile(os.path.join(q, "config.json")):
        sys.exit("%s is not a queue: it has no config.json" % q)
    st = state(q)
    if cmd == "probes" and not a:
        print_probes(probes(q, st, now()))
    elif cmd == "probe" and len(a) == 3 and a[1] in ("place", "role", "machine"):
        if a[1] == "role" and a[2] not in ROLES:
            sys.exit("a role is one of: " + ", ".join(ROLES))
        probes(q, st, now())
        reg = load(hp(q, "probes.json"), {}) or {}
        if a[0] not in reg:
            if a[1] != "role":
                sys.exit("%s is not a probe yet: give it a role first (probe %s role outside)" % (a[0], a[0]))
            who = [m for m, rows in last_samples(q).items() if a[0] in rows[-1]]
            reg[a[0]] = {"machine": who[0] if who else "", "place": "", "role": a[2]}
            if not who:
                print("no machine's newest line carries %s: name its machine (probe %s machine NAME)" % (a[0], a[0]))
        reg[a[0]][a[1]] = a[2]
        save(q, "probes.json", reg)
        print_probes([p for p in probes(q, st, now()) if p["key"] == a[0]])
    elif cmd == "target" and len(a) == 1:
        try:
            c = float(a[0])
        except ValueError:
            sys.exit("target is degrees C: target 21.0")
        if not 5 <= c <= 35:
            sys.exit("a target is between 5 and 35 C; %.1f was taken for a slip (or for Fahrenheit: %.1f F is %.1f C)" % (c, c, (c - 32) * 5 / 9))
        st["target_c"] = c
        save(q, "state.json", st)
        print("the target is %.1f C (%.1f F)" % (c, f_of(c)))
    elif cmd == "mode" and len(a) == 1 and a[0] in MODES:
        if a[0] != st["mode"]:
            # A change of mode begins the law again where the fleet is: no integral carried from a
            # time nothing was done on it.
            st.update(mode=a[0], integral_w=0.0, bias_w=None)
            st.pop("last_step_t", None)
            save(q, "state.json", st)
        print({"off": "off: step reads nothing and does nothing",
               "advise": "advise: step computes and says, and changes nothing",
               "act": "act: step does at most one rung a pass, through the queue's own commands%s" % (
                   "" if setting(st, "power") == "on" else "; power-off and wake stay off until `set power on`")}[a[0]])
        if st.get("held"):
            print("still held from before, and given back only by act or by hand: " + ", ".join("%s (%s)" % (m, ", ".join(h)) for m, h in st["held"].items()))
    elif cmd == "set" and not a:
        for k, (d, unit, what) in SETTINGS.items():
            print("  %-13s %-8s %-10s %s%s" % (k, "unknown" if setting(st, k) is None else setting(st, k), unit, what, "" if setting(st, k) == d else " (default %s)" % d))
    elif cmd == "set" and len(a) == 2 and a[0] in SETTINGS:
        if a[0] == "power":
            if a[1] not in ("on", "off"):
                sys.exit("power is on or off")
            v = a[1]
        else:
            try:
                v = float(a[1])
            except ValueError:
                sys.exit("%s is a number of %s" % (a[0], SETTINGS[a[0]][1]))
            if v < 0:
                sys.exit("%s is not negative" % a[0])
        st["set"][a[0]] = v
        if a[0] == "ua":
            st.update(bias_w=None, integral_w=0.0)  # the law begins again where the fleet is
        save(q, "state.json", st)
        print("%s is %s %s: %s" % (a[0], v, SETTINGS[a[0]][1], SETTINGS[a[0]][2]))
    elif cmd == "machine" and len(a) == 3 and a[1] in ("keep", "mac", "broadcast", "port", "busy_w", "idle_w", "order"):
        mine = load(hp(q, "machines.json"), {}) or {}
        rec = mine.setdefault(a[0], {})
        if a[1] == "keep":
            if a[2] not in ("on", "off"):
                sys.exit("keep is on or off")
            rec["keep"] = a[2] == "on"
        elif a[1] == "mac":
            magic_packet(a[2])
            rec["mac"] = a[2].lower()
        elif a[1] == "broadcast":
            rec["broadcast"] = a[2]
        else:
            rec[a[1]] = float(a[2]) if a[1] != "port" else int(a[2])
        save(q, "machines.json", mine)
        print("%s: %s" % (a[0], json.dumps(rec)))
    elif cmd == "set" and a == ["ua", "unknown"]:
        st["set"].pop("ua", None)
        st.update(bias_w=None, integral_w=0.0)
        save(q, "state.json", st)
        print("UA is unknown: no feedforward")
    elif cmd == "station" and len(a) == 1 and a[0].isalnum():
        st["outside_station"] = a[0].upper()
        st.pop("outside_tried_t", None)
        save(q, "state.json", st)
        print("the outside is station %s's observation, fetched at the next step or by `outside`" % st["outside_station"])
    elif cmd == "outside" and not a:
        c, word = fetch_outside(q, st, now())
        st["outside_tried_t"] = now()
        save(q, "state.json", st)
        print(word)
        return 0 if c is not None else 1
    elif cmd == "fit-ua" and not a:
        return fit_ua(q, st)
    elif cmd == "step" and not a:
        for line in step(q)["said"]:
            print(line)
    elif cmd == "status" and not a:
        return status(q)
    elif cmd == "wake" and len(a) == 1:
        rec = (load(hp(q, "machines.json"), {}) or {}).get(a[0], {})
        if not rec.get("mac"):
            sys.exit("%s has no address recorded: learn-macs while it is on, or machine %s mac AA:BB:CC:DD:EE:FF" % (a[0], a[0]))
        send_wake(rec)
        print("the wake packet for %s (%s) went to %s port %s, three times; whether it wakes is its BIOS's to say" % (
            a[0], rec["mac"], rec.get("broadcast", "255.255.255.255"), rec.get("port", 9)))
    elif cmd == "learn-macs" and not a:
        return learn_macs(q)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
