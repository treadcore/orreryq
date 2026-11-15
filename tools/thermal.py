"""thermal.py: the fleet's heat as an energy balance, from the telemetry (tools/telemetry.py model).

Paul, 15 November: "start analysis of heat capacity, of expected fin temperature, and current heat
air extraction. Maybe even a unified estimation of heat difference for heat flow, resulting from the
ambient air temperature shared constant. The end goal of this is to find something like a PID
controller to control the ambient air temperature. Through conservation of energy analysis screens."

WHAT GOES IN COMES OUT. Every watt a machine draws at the wall leaves it as heat into the room, so
the fleet's heat is its watts: tools/plans/power.json's model at the CPUs' use measured (or the CPU's
own counter, w.package-0, once root's reader gives it), the card's watts measured, the rest of the
box, over the supply's efficiency.

A PART IS R AND C. Heated at P watts in air at T_air it settles at T_air + R x P and gets there
with tau = R x C. A step the queue made (telemetry_chart.fits) gives tau and where the part settled;
the step's watts give R = (degrees moved) / (watts moved), and C = tau / R, joules a degree: the
metal and water there is to heat. Where a step wanted two exponentials the fast one is the silicon
to its cooler and the slow one the cooler to the air, and THE FIN is then what the die reads less
the fast part's share: T_fin = T_die - R_fast x P. T_zero = T_settled - R x P is what the part would
read at no watts: the air it sits in, inside its case.

THE ROOM is the same equation one size up: C_room dT/dt = (the fleet's watts) - (T_room - T_out) /
R_room. Nothing in the fleet measures T_room. What is recorded in its place is the coldest reading
any machine gives (never an ACPI zone: those are constants), which the room is no warmer than. A
controller that holds the room needs that reading to be a thermometer in the room; until there is
one this is a bound, and is called one.

The document is QUEUE/plan/thermal.json, written after each pull; Orrery's Heat page draws it.
"""
import json
import os
import time

import telemetry
import telemetry_chart

HERE = os.path.dirname(os.path.abspath(__file__))
HOURS = 6
POINTS = 240
AIR_J_M3_C = 1.2 * 1005  # a cubic metre of air, a degree


def cpu_keys(keys):
    """The CPU's channels: its package sensors, or, on a CPU that has none, every core's."""
    mine = sorted(k for k in keys if k.split("_")[0] in ("coretemp", "k10temp", "zenpower"))
    return [k for k in mine if "Package" in k or "Tctl" in k] or mine


def watts(box, s):
    """(cpu, card, wall) watts of one sample, by the model; None where the box is not in power.json."""
    if not box:
        return None
    busy = s.get("busy")
    if busy is None:
        return None
    cpu = s.get("w.package-0")
    if cpu is not None and "w.package-1" in s:
        cpu += s["w.package-1"]
    if cpu is None:
        cpu = box.get("cpu_idle_w", 0) + busy * (box.get("cpu_full_w", 0) - box.get("cpu_idle_w", 0))
    card = s.get("gpu.w", 0.0)
    return cpu, card, (box.get("rest_w", 0) + cpu + card) / box.get("eff", 0.88)


def bucket(rows, n):
    if len(rows) <= n:
        return [[r] for r in rows]
    size = len(rows) / n
    return [rows[int(i * size):int((i + 1) * size)] for i in range(n)]


def model(q):
    boxes = (telemetry.load(os.path.join(HERE, "plans", "power.json"), {}) or {}).get("boxes", {})
    limits = telemetry.load(os.path.join(q, "temps.json"), {}) or {}
    cfg = telemetry.load(os.path.join(q, "config.json"), {}) or {}
    in_queue = {h.get("lane_of", h["name"]) for h in cfg.get("hosts", [])}
    now = time.time()
    t0 = now - HOURS * 3600
    # The window begins where the record does, while the record is younger than the window.
    firsts = []
    for name in telemetry.machines(q):
        d = os.path.join(q, "telemetry", name)
        for f in sorted(x for x in os.listdir(d) if x.endswith(".log"))[:1] if os.path.isdir(d) else []:
            with open(os.path.join(d, f)) as fh:
                firsts.append(telemetry.parse(fh.readline()).get("t", now))
    if firsts and min(firsts) > t0:
        t0 = min(firsts)
    edges = [t0 + (now - t0) * i / POINTS for i in range(POINTS + 1)]
    fleet_w = [0.0] * POINTS
    fleet_n = [0] * POINTS
    cold = [None] * POINTS
    cold_now = None
    machines = []
    for name in sorted(telemetry.machines(q)):
        rows = telemetry.series(q, name, HOURS)
        if len(rows) < 3:
            continue
        keys = set().union(*rows)
        box = boxes.get(name)
        ck = cpu_keys(keys)
        temps = sorted(k for k in keys if telemetry_chart.is_temp(k) and not k.startswith("acpitz"))
        ser = {"cpu": [None] * POINTS, "gpu": [None] * POINTS, "w": [None] * POINTS}
        i = 0
        acc = [[] for _ in range(POINTS)]
        for r in rows:
            while i < POINTS - 1 and r["t"] >= edges[i + 1]:
                i += 1
            acc[i].append(r)
        for i, b in enumerate(acc):
            if not b:
                continue
            c = [max(r[k] for k in ck if k in r) for r in b if any(k in r for k in ck)]
            if c:
                ser["cpu"][i] = round(sum(c) / len(c), 1)
            g = [r["gpu.c"] for r in b if "gpu.c" in r]
            if g:
                ser["gpu"][i] = round(sum(g) / len(g), 1)
            w = [x[2] for x in (watts(box, r) for r in b) if x]
            if w:
                ser["w"][i] = round(sum(w) / len(w))
                fleet_w[i] += sum(w) / len(w)
                fleet_n[i] += 1
            lo = min(((r[k], k) for r in b for k in temps if k in r and r[k] > 5), default=None)
            if lo and (cold[i] is None or lo[0] < cold[i]):
                cold[i] = lo[0]
        last = rows[-1]
        # Above 5: an input with nothing on it reads -39 (jaguaribe's w83627dhg temp2).
        lo = min(((last[k], k) for k in temps if k in last and last[k] > 5), default=None)
        if lo and now - last["t"] < 600 and (cold_now is None or lo[0] < cold_now[0]):
            cold_now = (lo[0], name, lo[1])
        w_now = watts(box, last)
        lim = limits.get(name, {})
        cpu_now = max((last[k] for k in ck if k in last), default=None)
        # The steps, and what each says of the part.
        parts = []
        for f in telemetry_chart.fits(q, name, 24):
            main = f["channel"] in ck or f["channel"] == "gpu.c"
            dp = None
            if f["driver"] == "busy" and box:
                dp = (f["to"] - f["from"]) * (box.get("cpu_full_w", 0) - box.get("cpu_idle_w", 0))
            elif f["driver"] == "gpu.w":
                dp = f["to"] - f["from"]
            rec = {"channel": f["channel"], "main": main, "step": ("switched on" if f["driver"] == "power" else
                   "%s %g to %g" % ("CPUs" if f["driver"] == "busy" else "card W", f["from"], f["to"])),
                   "at": f["at"], "tau_s": f.get("slow_s", f["tau_s"]), "end_c": f.get("end2_c", f["end_c"]), "start_c": f["start_c"],
                   "taus_held": f["taus_held"], "rms_c": f.get("rms2_c", f["rms_c"])}
            if "slow_s" in f:
                rec["fast_s"] = f["fast_s"]
            if dp and abs(dp) >= 5:
                dT = rec["end_c"] - f["start_c"]
                r_total = dT / dp
                if r_total > 0:
                    rec["dp_w"] = round(dp, 1)
                    rec["r_c_w"] = round(r_total, 3)
                    rec["c_j_c"] = round(rec["tau_s"] / r_total)
                    p_after = (f["to"] if f["driver"] == "gpu.w" else box.get("cpu_idle_w", 0) + f["to"] * (box.get("cpu_full_w", 0) - box.get("cpu_idle_w", 0)))
                    rec["zero_c"] = round(rec["end_c"] - r_total * p_after, 1)
                    if "slow_s" in f:
                        # The fast part's degrees a watt: the silicon to its cooler.
                        rec["r_fast_c_w"] = round(abs(f["fast_c"] / dp), 3)
                        rec["r_slow_c_w"] = round(abs(f["slow_c"] / dp), 3)
                        rec["c_j_c"] = round(f["slow_s"] / rec["r_slow_c_w"]) if rec["r_slow_c_w"] else None
            parts.append(rec)
        # What the newest good fit of the CPU and of the card says of now: where each settles at the
        # watts it draws now, and the fin under the die.
        say = {}
        for what, chan, p_now in (("cpu", ck, w_now[0] if w_now else None), ("gpu", ["gpu.c"], w_now[1] if w_now else None)):
            good = [p for p in parts if p["channel"] in chan and "r_c_w" in p and p["taus_held"] >= 3]
            if good and p_now is not None:
                g = max(good, key=lambda p: p["at"])
                d = {"tau_s": g["tau_s"], "r_c_w": g["r_c_w"], "c_j_c": g["c_j_c"], "zero_c": g["zero_c"],
                     "settles_c": round(g["zero_c"] + g["r_c_w"] * p_now, 1), "five_tau_s": round(5 * g["tau_s"])}
                t_now = cpu_now if what == "cpu" else last.get("gpu.c")
                if "r_fast_c_w" in g and t_now is not None:
                    d["fin_c"] = round(t_now - g["r_fast_c_w"] * p_now, 1)
                    d["fast_s"] = g.get("fast_s")
                say[what] = d
        wall = w_now[2] if w_now else None
        machines.append({
            "name": name, "in_queue": name in in_queue, "age_s": round(now - last["t"]),
            "cpu_c": cpu_now, "cpu_hot": lim.get("cpu_hot"), "gpu_c": last.get("gpu.c"), "gpu_hot": lim.get("gpu_hot") if "gpu.c" in last else None,
            "busy": last.get("busy"), "cpu_w": round(w_now[0], 1) if w_now else None, "gpu_w": round(w_now[1], 1) if w_now else None,
            "wall_w": round(wall) if wall is not None else None, "watts_from": "the CPU's counter" if "w.package-0" in last else "the model at the use measured",
            # Air to carry its heat off at a ten-degree rise through the case, cubic metres an hour.
            "air_m3h": round(wall / (AIR_J_M3_C * 10) * 3600, 1) if wall is not None else None,
            "model": say, "fits": sorted(parts, key=lambda p: (not p["main"], -p["at"]))[:12], "series": ser,
            "channels": [[k, last[k]] for k in temps if k in last],
            "fans": [[k, last[k]] for k in sorted(keys) if (".fan" in k or "Fan" in k) and k != "gpu.fan" and k in last and last[k] > 0]})
    heat = [round(fleet_w[i]) if fleet_n[i] else None for i in range(POINTS)]
    wall_now = sum(m["wall_w"] or 0 for m in machines if m["age_s"] < 600)
    doc = {"t": now, "made": time.strftime("%Y-%m-%dT%H:%M:%S"), "hours": round((now - t0) / 3600, 1), "t0": t0,
           "fleet": {"heat_w": round(wall_now), "machines": sum(1 for m in machines if m["age_s"] < 600 and m["wall_w"] is not None),
                     "air_m3h": round(wall_now / (AIR_J_M3_C * 10) * 3600), "btu_h": round(wall_now * 3.412),
                     "coldest_c": cold_now[0] if cold_now else None, "coldest_from": "%s %s" % (cold_now[1], cold_now[2]) if cold_now else None,
                     "series": {"w": heat, "coldest": cold}},
           "machines": machines}
    out = os.path.join(q, "plan", "thermal.json")
    with open(out + ".tmp", "w") as f:
        json.dump(doc, f)
    os.replace(out + ".tmp", out)
    return doc


def main(q, args):
    doc = model(q)
    fl = doc["fleet"]
    print("the fleet's heat now: %d W from %d machines (%d BTU/h); %d m3/h of air carries it at a ten-degree rise" % (
        fl["heat_w"], fl["machines"], fl["btu_h"], fl["air_m3h"]))
    if fl["coldest_c"] is not None:
        print("the room is no warmer than %.1f C (%s): the coldest reading in the fleet, not a thermometer in the room" % (fl["coldest_c"], fl["coldest_from"]))
    for m in doc["machines"]:
        print("%-13s %s W at the wall  CPU %s  card %s" % (m["name"], m["wall_w"], m["cpu_c"], m["gpu_c"]))
        for what, d in m["model"].items():
            print("    %s: tau %.0f s (5 tau %d s), %.3f C/W, %d J/C, air at the part %.1f C, settles at %.1f C at the watts now%s" % (
                what, d["tau_s"], d["five_tau_s"], d["r_c_w"], d["c_j_c"], d["zero_c"], d["settles_c"],
                ", the fin %.1f C" % d["fin_c"] if "fin_c" in d else ""))
    return 0
