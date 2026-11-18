#!/usr/bin/env python3
"""The joules each machine put into the room, and what it did for them. It reads; it commands nothing.

    hearth-energy.py QUEUE [--from "2026-11-16 15:00"] [--to "2026-11-17 16:00"]

Paul, 17 November: "that is why I want to calculate Joules of energy added to the room. Efficiency wise,
the supermicro boards use the most WATTS."

EVERY WATT A MACHINE DRAWS AT THE WALL ENDS AS HEAT IN THE ROOM, so the energy added is the wall watts
summed over the time: a watt for a second is a joule, 3.6 MJ is a kilowatt-hour. For each machine, over
the stretch asked for (by default from when the house's own heating went off, 16 November 15:00):

  hours on      for how much of the stretch it was reporting
  mean W        its watts at the wall while on
  MJ, kWh       the energy, and its share of the fleet's
  CPU W         the wall watts less the card's share: what the CPU side cost
  cores busy    the mean number of its threads at work
  W a core      CPU-side watts for each busy thread: the lower, the more work for the heat
  jobs, Wh a job   CPU jobs of the queue finished there, and the CPU-side energy each cost. Jobs differ in
                size, so this is rough; it is fair between machines only because the queue deals them alike.

THE WATTS ARE A MODEL OF EACH BOX (tools/plans/power.json) except where the CPU has an energy counter the
collector may read (w.package-0) and the card reports its own draw. THE TWO SUPERMICROS HAVE NO COUNTER:
their watts are an idle figure plus a share for how busy they are, from the parts' ratings. So their row
is what the model says and not what a meter says, and it is marked. A plug-in meter for an hour corrects
power.json and this with it.

Then the room's own account: the energy the fleet put in, what the room kept (C times its change), and
so what left through the walls.
"""
import importlib.util
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
_s = importlib.util.spec_from_file_location("hearth_house", os.path.join(HERE, "hearth-house.py"))
house = importlib.util.module_from_spec(_s)
_s.loader.exec_module(house)

C_MJ = 4.2          # the room's heat capacity, MJ/C: the step of 17 November (docs/hearth-response-lab-report.md)
USD_KWH = 0.17      # power.json's rate: the US average, until Paul sets his own


def stamp(word):
    return time.mktime(time.strptime(word, "%Y-%m-%d %H:%M"))


def main(argv):
    if len(argv) < 2 or argv[1].startswith("-"):
        print(__doc__)
        return 2
    q = argv[1]
    t0 = stamp(argv[argv.index("--from") + 1]) if "--from" in argv else stamp("2026-11-16 15:00")
    t1 = stamp(argv[argv.index("--to") + 1]) if "--to" in argv else time.time()
    boxes = (json.load(open(os.path.join(HERE, "plans", "power.json"))) or {}).get("boxes", {})
    reg = json.load(open(os.path.join(q, "machines.json")))
    m = {}
    room = []
    last = {}
    for name, s in house.samples(q):
        t = s["t"]
        if not t0 <= t <= t1:
            continue
        for k, v in s.items():
            if k.startswith("room.") and k.endswith(".c") and not house.not_a_reading(v):
                room.append((t, k, v))
        box = boxes.get(name)
        w = house.wall(box, s)
        if w is None:
            continue
        dt = min(t - last.get(name, t - 5), 30)      # a sample stands for the time since the one before, a gap for no more than 30 s
        last[name] = t
        a = m.setdefault(name, {"s": 0.0, "j": 0.0, "card_j": 0.0, "busy_s": 0.0, "meter": "w.package-0" in s})
        card = s.get("gpu.w", 0.0) / box.get("eff", 0.88)
        a["s"] += dt
        a["j"] += w * dt
        a["card_j"] += card * dt
        a["busy_s"] += s.get("busy", 0.0) * dt
    jobs = {}
    for l in open(os.path.join(q, "events.jsonl")):
        if '"event": "done"' not in l:
            continue
        try:
            e = json.loads(l)
            t = time.mktime(time.strptime(e["t"], "%Y-%m-%dT%H:%M:%S"))
        except (ValueError, KeyError):
            continue
        host = e.get("host", "")
        if t0 <= t <= t1 and not host.endswith("-cuda"):
            name = host[:-2] if host.endswith("-2") else host
            j = jobs.setdefault(name, [0, 0.0])
            j[0] += 1
            j[1] += e.get("seconds", 0.0)
    total = sum(a["j"] for a in m.values())
    hours = (t1 - t0) / 3600
    print("from %s to %s, %.1f hours" % (time.strftime("%d %b %H:%M", time.localtime(t0)), time.strftime("%d %b %H:%M", time.localtime(t1)), hours))
    print("%-13s %8s %7s %7s %6s %6s %7s %10s %8s %6s %9s  %s" % ("machine", "hours on", "mean W", "MJ", "kWh", "share", "CPU W", "cores busy", "W a core", "jobs", "Wh a job", "its watts are"))
    rows = []
    for name, a in sorted(m.items(), key=lambda kv: -kv[1]["j"]):
        h = a["s"] / 3600
        if h < 0.05:
            continue
        cores = float(((reg.get(name) or {}).get("facts") or {}).get("cpus") or 0)
        cpu_j = a["j"] - a["card_j"]
        busy = a["busy_s"] / a["s"] * cores
        n, _ = jobs.get(name, (0, 0.0))
        rows.append((name, cpu_j / a["s"] / busy if busy > 0.2 else None))
        print("%-13s %8.1f %7.0f %7.1f %6.2f %5.0f%% %7.0f %10.1f %8s %6d %9s  %s" % (
            name, h, a["j"] / a["s"], a["j"] / 1e6, a["j"] / 3.6e6, 100 * a["j"] / total, cpu_j / a["s"], busy,
            "%.1f" % (cpu_j / a["s"] / busy) if busy > 0.2 else "-", n, "%.1f" % (cpu_j / 3600 / n) if n else "-",
            "the CPU's counter, the card's own" if a["meter"] else "A MODEL: no counter"))
    print("%-13s %8s %7.0f %7.1f %6.2f   100%%   (about $%.2f at %.0f cents a kWh)" % ("the fleet", "", total / (t1 - t0), total / 1e6, total / 3.6e6, total / 3.6e6 * USD_KWH, USD_KWH * 100))
    # For the hold's order of machines (tools/hearth_regulator.py): the CPU side's watt-hours for each job finished.
    whj = {name: (a["j"] - a["card_j"]) / 3600 / jobs[name][0] for name, a in m.items() if jobs.get(name, (0,))[0] >= 5}
    os.makedirs(os.path.join(q, "hearth"), exist_ok=True)
    with open(os.path.join(q, "hearth", "energy.json.tmp"), "w") as f:
        json.dump({"made": time.time(), "from": t0, "to": t1, "wh_a_job": {k: round(v, 2) for k, v in whj.items()},
                   "mj": {name: round(a["j"] / 1e6, 2) for name, a in m.items()}}, f, indent=1)
    os.replace(os.path.join(q, "hearth", "energy.json.tmp"), os.path.join(q, "hearth", "energy.json"))
    best = sorted((w, n) for n, w in rows if w is not None)
    if len(best) >= 2:
        print("\nwork for the heat, CPU-side watts a busy thread: " + ", ".join("%s %.1f" % (n, w) for w, n in best))
        print("    %s gives a thread of work for the fewest watts and %s for the most: %.1f times as many" % (best[0][1], best[-1][1], best[-1][0] / best[0][0]))
    # ---- the room's own account
    by = {}
    for t, k, v in room:
        by.setdefault(k, []).append((t, v))
    ends = []
    for k, pts in by.items():
        pts.sort()
        a = [v for t, v in pts if t - pts[0][0] <= 1800]
        b = [v for t, v in pts if pts[-1][0] - t <= 1800]
        if pts[-1][0] - pts[0][0] > 0.8 * (t1 - t0):
            ends.append((house.median(a), house.median(b)))
    if ends:
        r0, r1 = sum(e[0] for e in ends) / len(ends), sum(e[1] for e in ends) / len(ends)
        kept = C_MJ * (r1 - r0)
        print("\nthe room's account: the fleet put in %.1f MJ. The room went from %.2f C to %.2f C, which at %.1f MJ a degree is %+.1f MJ kept." % (total / 1e6, r0, r1, C_MJ, kept))
        print("    so %.1f MJ left through the walls, less whatever the house's other heat (people, appliances, sun) added: a mean of %.0f W lost that the fleet paid for" % (
            total / 1e6 - kept, (total / 1e6 - kept) * 1e6 / (t1 - t0)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
