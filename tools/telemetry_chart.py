"""telemetry.py's fits (see tools/telemetry.py).

THE CHART is tools/heat_page.py's: this file keeps what it shares with it (which channel is a
temperature, the palette) and the fits.

THE FIT is the first-order step response, T(t) = T_end + (T_start - T_end) * exp(-(t - t0) / tau):
a channel after its driver (the CPUs' use for a CPU or board channel, the card's watts for the card)
stepped and then held. tau is found by search, T_end and T_start by least squares at each tau. A
second, slower exponential is added where it cuts the error by more than half: a CPU's own silicon
answers in seconds and its cooler, or its loop, in minutes, and one tau cannot be both. A fit is only
as good as its window: the report says how many tau the hold lasted, and a hold under three tau gives
a T_end that is a projection, not a measurement.
"""
import html
import json
import math
import os
import time

import telemetry

SERIES_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SERIES_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9", "#e66767"]


def is_temp(k):
    if k.startswith("rad.") or k in ("up", "t"):
        return False
    return k == "gpu.c" or (("." in k) and not k.startswith(("w.", "gpu.")) and not any(x in k for x in (".fan", ".pwm", ".power"))
                            ) or k.startswith(("nic.", "disk.")) or (k.startswith("ipmi.") and "RPM" not in k and "FAN" not in k.upper())


def thin(rows, n=700):
    """At most n rows, each the mean of its bucket: a day at 5 seconds is 17,280."""
    if len(rows) <= n:
        return rows
    size = len(rows) / n
    out = []
    for i in range(n):
        b = rows[int(i * size):int((i + 1) * size)]
        keys = set().union(*b)
        out.append({k: sum(r[k] for r in b if k in r) / max(1, sum(1 for r in b if k in r)) for k in keys})
    return out


# ---- the fit -------------------------------------------------------------------------

def mean(v):
    return sum(v) / len(v)


def median(v):
    v = sorted(v)
    return v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2


def steps(rows, key, jump, hold_s=240, look_s=45):
    """Where `key` stepped by at least `jump` and then held: (index, before, after, end index). Before
    and after are the MEDIANS of look_s each side, so the two sides differ only once most of the far
    side is past the step (a mean differs as soon as a few samples are, and a search begun there
    runs past the step itself: columbia's Pause, 15 November, was missed so). The index is then the
    first sample at the new level. The hold ends where the driver leaves the new level by half a
    jump, or the data ends."""
    out, i, n = [], 0, len(rows)
    t = [r["t"] for r in rows]
    v = [r.get(key) for r in rows]
    while i < n:
        a = [v[j] for j in range(i, -1, -1) if t[i] - t[j] <= look_s and v[j] is not None]
        b = [v[j] for j in range(i + 1, n) if t[j] - t[i] <= look_s and v[j] is not None]
        if len(a) >= 3 and len(b) >= 3 and abs(median(b) - median(a)) >= jump:
            before, after = median(a), median(b)
            while i + 1 < n and (v[i] is None or abs(v[i] - after) >= jump / 2):
                i += 1
            end = i + 1
            while end < n and (v[end] is None or abs(v[end] - after) < jump / 2 or
                               abs(mean([x for x in v[end:end + 6] if x is not None] or [after]) - after) < jump / 2):
                end += 1
            if t[min(end, n - 1)] - t[i] >= hold_s:
                out.append((i, before, after, min(end, n - 1)))
            i = max(end, i + 1)
        else:
            i += 1
    return out


def fit_one(ts, ys, taus):
    """Least squares of y = a + b * exp(-t / tau) at each tau: (rms, tau, a, b)."""
    best = None
    n = len(ts)
    for tau in taus:
        e = [math.exp(-x / tau) for x in ts]
        se, see, sy, sey = sum(e), sum(x * x for x in e), sum(ys), sum(x * y for x, y in zip(e, ys))
        den = n * see - se * se
        if abs(den) < 1e-12:
            continue
        b = (n * sey - se * sy) / den
        a = (sy - b * se) / n
        rms = math.sqrt(sum((a + b * x - y) ** 2 for x, y in zip(e, ys)) / n)
        if best is None or rms < best[0]:
            best = (rms, tau, a, b)
    return best


def fit_two(ts, ys, taus):
    """y = a + b * exp(-t / fast) + c * exp(-t / slow), fast < slow: (rms, fast, slow, a, b, c)."""
    best = None
    n = len(ts)
    es = {tau: [math.exp(-x / tau) for x in ts] for tau in taus}
    for i, f in enumerate(taus):
        for s in taus[i + 1:]:
            if s < 3 * f:
                continue
            e1, e2 = es[f], es[s]
            # Normal equations, three unknowns.
            m = [[n, sum(e1), sum(e2)], [sum(e1), sum(x * x for x in e1), sum(x * y for x, y in zip(e1, e2))],
                 [sum(e2), sum(x * y for x, y in zip(e1, e2)), sum(x * x for x in e2)]]
            r = [sum(ys), sum(x * y for x, y in zip(e1, ys)), sum(x * y for x, y in zip(e2, ys))]
            sol = solve3(m, r)
            if sol is None:
                continue
            a, b, c = sol
            if b * c < 0:  # both parts must move the same way: a step, not a wiggle
                continue
            rms = math.sqrt(sum((a + b * x + c * z - y) ** 2 for x, z, y in zip(e1, e2, ys)) / n)
            if best is None or rms < best[0]:
                best = (rms, f, s, a, b, c)
    return best


def solve3(m, r):
    m = [row[:] + [x] for row, x in zip(m, r)]
    for i in range(3):
        p = max(range(i, 3), key=lambda k: abs(m[k][i]))
        if abs(m[p][i]) < 1e-12:
            return None
        m[i], m[p] = m[p], m[i]
        for k in range(3):
            if k != i:
                f = m[k][i] / m[i][i]
                m[k] = [x - f * y for x, y in zip(m[k], m[i])]
    return [m[i][3] / m[i][i] for i in range(3)]


def fits(q, name, hours):
    """Every step of this machine in the window, each channel that answered it."""
    rows = telemetry.series(q, name, hours)
    if len(rows) < 60:
        return []
    keys = set().union(*rows)
    taus = [2 * 1.18 ** i for i in range(48)]  # 2 s to 80 min, for the two-part search
    fine = [2 * 1.05 ** i for i in range(150)]  # the same span in steps of 5%, for the one
    out = []
    for driver, jump, unit, follow in (("busy", 0.4, "of the CPUs", lambda k: is_temp(k) and k != "gpu.c"),
                                       ("gpu.w", 40.0, "W at the card", lambda k: k == "gpu.c")):
        if driver not in keys:
            continue
        for i, before, after, end in steps(rows, driver, jump):
            seg = rows[i:end + 1]
            hold = seg[-1]["t"] - seg[0]["t"]
            for k in sorted(x for x in keys if follow(x)):
                pts = [(r["t"] - seg[0]["t"], r[k]) for r in seg if k in r]
                if len(pts) < 30 or max(p[1] for p in pts) - min(p[1] for p in pts) < 3:
                    continue
                ts, ys = [p[0] for p in pts], [p[1] for p in pts]
                one = fit_one(ts, ys, [t for t in fine if t <= hold])
                # A fit that leaves a quarter of the channel's own swing unexplained is not a step response.
                # Nor is one whose best tau is the longest tried: the channel was still on its way, and
                # the hold says nothing of where it ends.
                # And the step must be seen above the channel's own noise, in whole seconds of it.
                two = fit_two(ts, ys, [t for t in taus if t <= hold])
                good_one = (one is not None and one[0] <= 0.25 * (max(ys) - min(ys)) and one[1] < 0.9 * hold
                            and abs(one[3]) >= 3 and abs(one[3]) >= 4 * one[0] and one[1] >= 5)
                good_two = (two is not None and one is not None and two[0] < 0.5 * one[0] and two[2] < 0.9 * hold
                            and abs(two[4] + two[5]) >= 3 and abs(two[4] + two[5]) >= 4 * two[0])
                if not (good_one or good_two):
                    continue
                rec = {"machine": name, "channel": k, "driver": driver, "unit": unit, "at": seg[0]["t"], "from": round(before, 2),
                       "to": round(after, 2), "hold_s": round(hold), "start_c": round(ys[0], 1), "last_c": round(mean(ys[-6:]), 1),
                       "tau_s": round(one[1], 1), "end_c": round(one[2], 1), "rms_c": round(one[0], 2), "taus_held": round(hold / one[1], 1)}
                if good_two:
                    rec.update(fast_s=round(two[1], 1), slow_s=round(two[2], 1), fast_c=round(two[4], 1), slow_c=round(two[5], 1),
                               end2_c=round(two[3], 1), rms2_c=round(two[0], 2), taus_held=round(hold / two[2], 1))
                out.append(rec)
    # SWITCHED ON: the first sample after ten minutes of none (a boot, the collector started by the
    # next pull) is a step too, from off to whatever the machine then does, held while the CPUs' use
    # stays within 0.4 of where it began. Off for hours, it starts at the room's temperature.
    starts = [i for i in range(len(rows)) if i == 0 or rows[i]["t"] - rows[i - 1]["t"] >= 600]
    first_ever = min((f for f in os.listdir(os.path.join(q, "telemetry", name)) if f.endswith(".log")), default="")
    for i in starts:
        if i == 0 and not (first_ever and abs(os.path.getmtime(os.path.join(q, "telemetry", name, first_ever)) - 0) and
                           rows[0]["t"] - time.time() > -hours * 3600 + 120):
            continue  # the window's own first row, not a start
        base = mean([r["busy"] for r in rows[i:i + 12] if "busy" in r] or [0])
        # A boot, not the collector's own start: up under a quarter hour (or, in the first day's lines,
        # which had no `up`, a machine that began idle).
        if not (rows[i]["up"] < 900 if "up" in rows[i] else base < 0.2):
            continue
        end = i
        while end + 1 < len(rows) and rows[end + 1]["t"] - rows[end]["t"] < 600 and abs(rows[end + 1].get("busy", base) - base) < 0.4:
            end += 1
        seg = rows[i:end + 1]
        hold = seg[-1]["t"] - seg[0]["t"]
        if hold < 240:
            continue
        for k in sorted(x for x in keys if is_temp(x)):
            pts = [(r["t"] - seg[0]["t"], r[k]) for r in seg if k in r]
            if len(pts) < 30 or max(p[1] for p in pts) - min(p[1] for p in pts) < 2:
                continue
            ts, ys = [p[0] for p in pts], [p[1] for p in pts]
            one = fit_one(ts, ys, [t for t in fine if t <= hold])
            if one is None or one[0] > 0.25 * (max(ys) - min(ys)) or one[1] >= 0.9 * hold or abs(one[3]) < 3 or abs(one[3]) < 4 * one[0]:
                continue
            out.append({"machine": name, "channel": k, "driver": "power", "unit": "switched on", "at": seg[0]["t"], "from": 0, "to": round(base, 2),
                        "hold_s": round(hold), "start_c": round(ys[0], 1), "last_c": round(mean(ys[-6:]), 1), "tau_s": round(one[1], 1),
                        "end_c": round(one[2], 1), "rms_c": round(one[0], 2), "taus_held": round(hold / one[1], 1)})
    return out


def fit(q, args):
    names = [a for a in args if not a.replace(".", "").isdigit()] or sorted(telemetry.machines(q))
    hours = next((float(a) for a in args if a.replace(".", "").isdigit()), 6.0)
    every = []
    for name in names:
        every += fits(q, name, hours)
    doc = os.path.join(q, "plan", "telemetry-fits.json")
    with open(doc, "w") as f:
        json.dump({"t": time.time(), "hours": hours, "fits": every}, f, indent=1)
    if not every:
        print("no step held four minutes in the last %g hours: pause a machine, let it settle, resume it" % hours)
        return 0
    print("%-13s %-26s %-22s %6s  %-18s %7s %7s %6s  %s" % ("machine", "channel", "step", "held", "tau", "from C", "ends C", "rms", "taus held"))
    for r in every:
        step = ("switched on, CPUs %g" % r["to"] if r["driver"] == "power" else
                "%s %g -> %g" % ("CPUs" if r["driver"] == "busy" else "card W", r["from"], r["to"]))
        tau = "%.0f s + %.0f s" % (r["fast_s"], r["slow_s"]) if "slow_s" in r else "%.0f s" % r["tau_s"]
        print("%-13s %-26s %-22s %5ds  %-18s %7.1f %7.1f %6.2f  %s%s" % (
            r["machine"], r["channel"], step, r["hold_s"], tau, r["start_c"], r.get("end2_c", r["end_c"]), r.get("rms2_c", r["rms_c"]),
            r["taus_held"], "" if r["taus_held"] >= 3 else "  (under 3: the end is a projection)"))
    print("kept: %s" % doc)
    return 0
