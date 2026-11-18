#!/usr/bin/env python3
"""What the house loses: UA, the room's heat capacity and where it settles, from records that are
already kept. It reads; it commands nothing, and it does not need the controller scheduled.

    hearth-house.py QUEUE              fetch the airport's last week, rebuild the record, fit, say
    hearth-house.py QUEUE --no-fetch   the same from the outside air already kept
    hearth-house.py QUEUE --since H    only the last H hours (after the house's heating went off)
    hearth-house.py QUEUE --table      the record as well, an hour a line

THE THREE RECORDS, and who keeps each:
  the room     room.radXXXX.c in QUEUE/telemetry/MACHINE/DAY.log, every five seconds: radbeeper asks
               each Geiger counter its temperature and the fleet's collector reports it. radbeeper's
               own temp-SERIAL-YYYY-MM.tsv on the machine is the same reading and outlives a lost pull.
  the watts    the same logs: each machine's CPU counter and card, made watts at the wall by the
               model in tools/plans/power.json. A MODEL, NOT A METER, until a meter corrects a box.
  the outside  the airport's observations. The weather service keeps about a week of them, so this
               must run at least once a week or hours are lost; each run adds what is new to
               QUEUE/hearth/outside-history.tsv. The request carries nothing of this house.

THE BALANCE. One room, one lump of heat:

    C dT/dt = P + P0 - UA (T - To)

T the room, To the outside, P the fleet's watts, P0 every other watt the house gets (people, the
refrigerator, the sun, the rooms beyond the door), UA the watts lost for each degree the room
stands over the outside, C the joules that warm the room a degree. Divided by C it is a line in
three things that are all recorded:

    dT/dt = a P + b (T - To) + c        a = 1/C,  b = -UA/C,  c = P0/C

so least squares over the hours gives UA = -b/a, C = 1/a, P0 = c/a, the time constant tau = C/UA,
and the temperature the room settles at with the fleet at P watts and the outside at To:

    T_ss = To + (P + P0) / UA

WHAT EACH PART NEEDS. b wants the room's height over the outside to change, which the night and
the day do without being asked. a wants THE FLEET'S WATTS TO CHANGE: with P level, a P and c are
one constant and only two numbers come out, tau and the rise (P + P0)/UA. That rise is already the
steady temperature AT THE WATTS OF THOSE HOURS; UA in watts a degree, and so the steady temperature
at any other watts, waits for a step in the watts. This says which of the two it has.
"""
import glob
import json
import os
import sys
import time
import urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
BUCKET = 600           # seconds: the record's line
SLOPE_H = 2            # hours either side over which a slope is taken
WANT_HOURS = 48        # below this a fit is said and not believed
WANT_SPREAD_W = 80     # the watts must have stood at levels this far apart (standard deviation)
WANT_SPREAD_C = 1.5    # and the room's height over the outside this far
LEVEL_C_H = 0.08       # a room moving less than this in an hour is held still


def not_a_reading(v):
    """The counter's two answers that are not temperatures: 85.0 and minus nought."""
    return v == 85.0 or (v == 0.0)


def samples(q):
    """Every sample of every machine: (machine, {key: number})."""
    for d in sorted(glob.glob(os.path.join(q, "telemetry", "*"))):
        m = os.path.basename(d)
        for f in sorted(glob.glob(os.path.join(d, "*.log"))):
            for l in open(f, errors="replace"):
                s = {}
                for w in l.split():
                    k, _, v = w.partition("=")
                    try:
                        s[k] = float(v)
                    except ValueError:
                        pass
                if "t" in s:
                    yield m, s


def wall(box, s):
    """Watts at the wall of one sample, as tools/thermal.py counts them."""
    busy = s.get("busy")
    if not box or busy is None:
        return None
    cpu = s.get("w.package-0")
    if cpu is not None and "w.package-1" in s:
        cpu += s["w.package-1"]
    if cpu is None:
        cpu = box.get("cpu_idle_w", 0) + busy * (box.get("cpu_full_w", 0) - box.get("cpu_idle_w", 0))
    return (box.get("rest_w", 0) + cpu + s.get("gpu.w", 0.0)) / box.get("eff", 0.88)


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def outside(q, station, fetch):
    """{observed epoch: degrees C}, the kept history with the airport's last week added."""
    path = os.path.join(q, "hearth", "outside-history.tsv")
    obs, said = {}, ""
    try:
        for l in open(path):
            w = l.split("\t")
            if len(w) >= 3 and w[2].strip() == station:
                obs[int(w[0])] = float(w[1])
    except OSError:
        pass
    had = len(obs)
    if fetch:
        try:
            req = urllib.request.Request("https://api.weather.gov/stations/%s/observations?limit=500" % station,
                                         headers={"User-Agent": "orrery-hearth", "Accept": "application/geo+json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                for f in json.load(r)["features"]:
                    p = f["properties"]
                    c = (p.get("temperature") or {}).get("value")
                    if c is not None:
                        obs[int(datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00")).timestamp())] = float(c)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path + ".new", "w") as f:
                for t in sorted(obs):
                    f.write("%d\t%.1f\t%s\n" % (t, obs[t], station))
            os.replace(path + ".new", path)
        except Exception as e:
            said = "the fetch of %s failed (%s); using what was kept" % (station, str(e)[:100] or type(e).__name__)
    return obs, had, said


def at(series, t, reach):
    """A series' value at t, on the line between its neighbours; None where the nearer is beyond reach."""
    ts = series["t"]
    if not ts:
        return None
    lo, hi = 0, len(ts)
    while lo < hi:
        mid = (lo + hi) // 2
        if ts[mid] < t:
            lo = mid + 1
        else:
            hi = mid
    if lo == 0:
        return series["v"][0] if ts[0] - t <= reach else None
    if lo == len(ts):
        return series["v"][-1] if t - ts[-1] <= reach else None
    a, b = ts[lo - 1], ts[lo]
    if min(t - a, b - t) > reach:
        return None
    return series["v"][lo - 1] + (series["v"][lo] - series["v"][lo - 1]) * (t - a) / (b - a)


def record(q, obs):
    """The record, a line each ten minutes: [t, room, outside, watts, machines reporting, probes]."""
    boxes = (json.load(open(os.path.join(HERE, "plans", "power.json"))) or {}).get("boxes", {})
    room, watts = {}, {}
    for m, s in samples(q):
        b = int(s["t"] // BUCKET)
        w = wall(boxes.get(m), s)
        if w is not None:
            watts.setdefault(b, {}).setdefault(m, []).append(w)
        for k, v in s.items():
            if k.startswith("room.") and k.endswith(".c") and not not_a_reading(v):
                room.setdefault(b, {}).setdefault(k, []).append(v)
    out = {"t": sorted(obs), "v": [obs[t] for t in sorted(obs)]}
    # The room is the mean of its probes, and two probes do not read alike: a line with one of
    # them missing would step the mean by their difference. So the probes that are in at least
    # four lines of five are the room's, and a line without all of them is left out.
    seen = {}
    for ps in room.values():
        for k in ps:
            seen[k] = seen.get(k, 0) + 1
    steady = {k for k, n in seen.items() if n >= 0.8 * max(seen.values())} if seen else set()
    rows = []
    for b in sorted(room):
        t = b * BUCKET + BUCKET // 2
        if not steady <= set(room[b]):
            continue
        probes = {k: median(v) for k, v in room[b].items() if k in steady}
        o = at(out, t, 2 * 3600)
        ws = watts.get(b, {})
        if o is None or not ws:
            continue
        rows.append([t, sum(probes.values()) / len(probes), o, sum(sum(v) / len(v) for v in ws.values()), len(ws), probes])
    return rows


def solve(A, y):
    """Least squares by the normal equations: the coefficients, or None where they do not stand apart."""
    n = len(A[0])
    M = [[sum(r[i] * r[j] for r in A) for j in range(n)] + [sum(r[i] * v for r, v in zip(A, y))] for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda k: abs(M[k][i]))
        if abs(M[p][i]) < 1e-12:
            return None
        M[i], M[p] = M[p], M[i]
        for k in range(n):
            if k != i:
                f = M[k][i] / M[i][i]
                M[k] = [x - f * z for x, z in zip(M[k], M[i])]
    return [M[i][n] / M[i][i] for i in range(n)]


def sd(xs):
    m = sum(xs) / len(xs)
    return (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5


def hourly(rows):
    """The record an hour a line: (t, room, outside, watts), only whole hours."""
    by = {}
    for r in rows:
        by.setdefault(int(r[0] // 3600), []).append(r)
    return [(h * 3600 + 1800, median([r[1] for r in v]), sum(r[2] for r in v) / len(v), sum(r[3] for r in v) / len(v))
            for h, v in sorted(by.items()) if len(v) >= 4]


def slopes(hs):
    """(room, room over outside, watts, degrees an hour) at each hour that has SLOPE_H hours either side."""
    by = {int(h[0] // 3600): h for h in hs}
    pts = []
    for k, h in sorted(by.items()):
        a, b = by.get(k - SLOPE_H), by.get(k + SLOPE_H)
        if a and b and all(k + d in by for d in range(-SLOPE_H, SLOPE_H + 1)):
            mid = [by[k + d] for d in range(-SLOPE_H, SLOPE_H + 1)]
            pts.append((h[0], sum(x[1] for x in mid) / len(mid), sum(x[1] - x[2] for x in mid) / len(mid),
                        sum(x[3] for x in mid) / len(mid), (b[1] - a[1]) / (2 * SLOPE_H)))
    return pts


def fit(pts, name):
    """Say what the hours in pts give. Returns the fit as a dict."""
    doc = {"hours": len(pts)}
    if len(pts) < 6:
        print("%s: %d hours with a slope; too few to fit anything" % (name, len(pts)))
        return doc
    over, w, dT = [p[2] for p in pts], [p[3] for p in pts], [p[4] for p in pts]
    sw, so = sd(w), sd(over)
    doc.update(watts_mean=sum(w) / len(w), watts_sd=sw, over_mean=sum(over) / len(over), over_sd=so)
    print("%s: %d hours. Fleet %.0f W (standing %.0f W apart); the room %.1f C over the outside (standing %.1f C apart)" % (
        name, len(pts), doc["watts_mean"], sw, doc["over_mean"], so))
    # Two numbers, which need only the outside to move: dT/dt = k - (T - To)/tau, rise = k tau.
    two = solve([[1.0, o] for o in over], dT)
    if two and two[1] < 0:
        tau = -1 / two[1]
        rise = two[0] * tau
        doc.update(tau_h=tau, rise_c=rise)
        print("    with the watts taken as level: tau = %.0f hours, and the room settles %.1f C over the outside at %.0f W" % (tau, rise, doc["watts_mean"]))
        print("    (P + P0)/UA = %.1f C, so UA = (%.0f + P0)/%.1f: at least %.0f W/C, and more by P0/%.1f" % (rise, doc["watts_mean"], rise, doc["watts_mean"] / rise, rise))
    else:
        print("    with the watts taken as level: no fit (the room did not move toward a level in these hours)")
    # Three, which need the watts to have moved as well.
    three = solve([[x, o, 1.0] for x, o in zip(w, over)], dT)
    if three and three[0] > 0 and three[1] < 0:
        a, b, c = three
        ua, cap, p0 = -b / a, 3600 / a, c / a
        doc.update(ua_w_c=ua, c_j_c=cap, p0_w=p0, tau3_h=cap / ua / 3600)
        ok = len(pts) >= WANT_HOURS and sw >= WANT_SPREAD_W and so >= WANT_SPREAD_C
        doc["believed"] = ok
        print("    with the watts' own movement: UA = %.0f W/C, C = %.1f MJ/C, P0 = %.0f W, tau = %.0f hours%s" % (
            ua, cap / 1e6, p0, cap / ua / 3600, "" if ok else "   NOT TO BE BELIEVED YET:"))
        if not ok:
            print("        " + "; ".join(x for x in (
                "%d hours where %d are wanted" % (len(pts), WANT_HOURS) if len(pts) < WANT_HOURS else "",
                "the watts stood only %.0f W apart where %d are wanted: a step in the fleet's watts is what gives UA" % (sw, WANT_SPREAD_W) if sw < WANT_SPREAD_W else "",
                "the room's height over the outside stood only %.1f C apart where %.1f are wanted" % (so, WANT_SPREAD_C) if so < WANT_SPREAD_C else "") if x))
    else:
        print("    with the watts' own movement: no fit yet (the watts and the constant do not stand apart, or the signs are wrong)")
    # THE ROOM HELD STILL (Paul, 17 November: "try to maintain 80, and calculate the outside temperature
    # delta"). In an hour in which the room does not move, what goes in goes out: P + P0 = UA (T - To).
    # So each level hour is a point, the fleet's watts against the degrees the room stands over the
    # outside, and as the outside moves through a day and a night the points lie on a line:
    #     P = UA x (T - To) - P0
    # whose slope is UA and whose foot is the house's other heat. It needs no slope of a probe that
    # reads in tenths, and no step: holding the room is the experiment.
    level = [(o, x) for o, x, d in zip(over, w, dT) if abs(d) <= LEVEL_C_H]
    doc["level_hours"] = len(level)
    if level:
        lo, lw = [p[0] for p in level], [p[1] for p in level]
        print("    held still (within %.2f C an hour): %d hours; the room %.1f to %.1f C over the outside on %.0f to %.0f W; %.0f W for each degree of that, P0 left out" % (
            LEVEL_C_H, len(level), min(lo), max(lo), min(lw), max(lw), sum(lw) / sum(lo)))
        line = solve([[o, -1.0] for o in lo], lw) if len(level) >= 6 and sd(lo) >= 0.7 else None
        if line and line[0] > 0:
            doc.update(held_ua=line[0], held_p0=line[1])
            print("    the line through them: P = %.0f x (T - To) - %.0f, so UA = %.0f W/C and P0 = %.0f W%s" % (
                line[0], line[1], line[0], line[1], "" if len(level) >= 24 else "   (fewer than 24 level hours: a first look)"))
        else:
            print("    no line through them yet: it wants six level hours with the room's height over the outside standing 0.7 C apart")
    return doc


def main(argv):
    if len(argv) < 2 or argv[1].startswith("-"):
        print(__doc__)
        return 2
    q = argv[1]
    since = float(argv[argv.index("--since") + 1]) if "--since" in argv else None
    st = {}
    try:
        st = json.load(open(os.path.join(q, "hearth", "state.json")))
    except (OSError, ValueError):
        pass
    station = st.get("outside_station") or "KSEA"
    obs, had, said = outside(q, station, "--no-fetch" not in argv)
    if said:
        print(said)
    rows = record(q, obs)
    if since is not None:
        rows = [r for r in rows if r[0] >= time.time() - since * 3600]
    if not rows:
        print("no line has the room, the outside and the watts together")
        return 1
    with open(os.path.join(q, "hearth", "house.tsv"), "w") as f:
        f.write("#t\troom_c\toutside_c\tfleet_w\tmachines\n")
        for r in rows:
            f.write("%d\t%.2f\t%.1f\t%.0f\t%d\n" % tuple(r[:5]))
    hs = hourly(rows)
    stamp = lambda t: time.strftime("%d %b %H:%M", time.localtime(t))
    print("the record: %s to %s, %.1f hours, %d lines; outside from %s, %d observations kept (%d before this run)" % (
        stamp(rows[0][0]), stamp(rows[-1][0]), (rows[-1][0] - rows[0][0]) / 3600, len(rows), station, len(obs), had))
    probes = sorted({k for r in rows for k in r[5]})
    print("room probes: %s" % ", ".join("%s (now %.1f C)" % (k, [r[5][k] for r in rows if k in r[5]][-1]) for k in probes))
    if "--table" in argv:
        print("  hour          room  outside  over   fleet W")
        for h in hs:
            print("  %s  %5.2f  %5.1f  %5.1f  %6.0f" % (stamp(h[0]), h[1], h[2], h[1] - h[2], h[3]))
    # What can be said from one line of the record: the sign of the slope bounds UA.
    last = hs[-3:] if len(hs) >= 3 else hs
    if len(last) >= 2:
        slope = (last[-1][1] - last[0][1]) / ((last[-1][0] - last[0][0]) / 3600)
        over, w = last[-1][1] - last[-1][2], last[-1][3]
        if over > 1:
            print("now: the room %.1f C, %.1f C over the outside, the fleet %.0f W, the room moving %+.2f C an hour" % (last[-1][1], over, w, slope))
            if slope < -0.05:
                print("    it is cooling, so the loss is more than the heat: UA x %.1f > %.0f + P0, and UA is MORE than %.0f W/C" % (over, w, w / over))
            elif slope > 0.05:
                print("    it is warming, so the heat is more than the loss: UA x %.1f < %.0f + P0" % (over, w))
            else:
                print("    it is level, so the loss is the heat: UA = (%.0f + P0)/%.1f, which is %.0f W/C and more by P0/%.1f" % (w, over, w / over, over))
    pts = slopes(hs)
    doc = {"t": time.time(), "from": rows[0][0], "to": rows[-1][0], "all": fit(pts, "every hour")}
    night = [p for p in pts if time.localtime(p[0]).tm_hour >= 22 or time.localtime(p[0]).tm_hour < 6]
    doc["night"] = fit(night, "22:00 to 06:00 only (no sun, the house asleep)")
    with open(os.path.join(q, "hearth", "house.json"), "w") as f:
        json.dump(doc, f, indent=1)
    best = doc["night"] if doc["night"].get("believed") else doc["all"] if doc["all"].get("believed") else None
    if best:
        print("to use it:    hearth.py QUEUE set ua %d" % round(best["ua_w_c"]))
        o = rows[-1][2]
        for p in (0, 250, 500, 750, 1000, 1250):
            print("    the fleet at %4d W, the outside at %.0f C: the room settles at %.1f C" % (p, o, o + (p + best["p0_w"]) / best["ua_w_c"]))
    else:
        print("nothing is adopted. UA waits for the hours and for a step in the fleet's watts; see docs/hearth-measure-plan.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
