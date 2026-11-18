"""hearth_regulator: the hold, as the controller's own law. Not a program: tools/hearth.py's pass calls
`look` when its law is `hold` (`hearth.py QUEUE set law hold`), every five minutes after the telemetry
is pulled, and in act it carries out what `look` decides.

Paul, 17 November: "update the implementation of orrery. stop using the script. switch to orrery
controlling. Prefer GPU computers, Prefer Energy Calculations. Prefer keeping temp around 80, under 81F."
The script was tools/hearth-hold.py, a morning's work in a terminal; what it learned that day is here,
and the script is gone.

WHAT IT HOLDS. The target is the controller's (the Hearth panel's). Inside a band of 0.25 C either side
nothing is changed. THE CEILING (`set ceiling C`, half a degree over the target unless set: 80 F and
81 F) is not to be stood above: within 0.05 C of it and not falling, heat is shed at once, without
waiting out the dwell, and the largest step is taken.

THE BUDGET, in watts, is an energy calculation and not a gain:

    watts to move = -( UA x (room - target)  +  C x the room's slope )

the first term what the walls lose more or less of at the target than now, the second what the room is
storing or giving up as it moves. C is 4.2 MJ/C, measured by the step of 17 November. UA is 120 W/C, the
middle of what that day's record allows, until `set ua` says better. The slope is a line through the
last hour's looks. The budget is held within 600 W either way: a probe that reads in tenths cannot
justify more.

A MACHINE THAT IS ON COMPUTES. A machine that answers and is not in the queue is put in it, or, if the
room wants watts taken away, switched off.

WHICH MACHINE. Two preferences, in this order:
  1. GPU MACHINES ARE KEPT. Heat is shed from a machine without a card before one with, and from a CPU
     lane before a card's lane; heat is added the other way about.
  2. WORK FOR THE JOULE. Among equals, the machine that spends the most energy on a job goes first and
     comes back last (QUEUE/hearth/energy.json, written by tools/hearth-energy.py from the record: the
     CPU side's watt-hours for each job finished). The two Supermicros spend four to five times
     saskatchewan's, by the power model.
The first in that order whose watts are no more than twice the budget, or no more than 250 W, is taken
(a whole machine that spends its energy badly is a better step than a lane of one that spends it well);
if every one is larger, the smallest.

HOW. A machine KNOWN TO WAKE BY THE PACKET (hearth/machines.json, `wol`) is shed whole: it finishes its
task, leaves the queue and is powered off, and is woken and put back when heat is wanted; that needs the
power switch on (`set power on`). Any other machine is shed by a lane taking nothing new, since only a
person could bring it back. Never the machine that carries the room's probes (its lanes may pause),
never this Mac, never a lane a person paused, never a machine a person removed that this law did not
switch off itself (except the spares named in hearth/hold.json).

FORTY MINUTES BETWEEN CHANGES: the room answers about an hour late. Fifteen when the budget is 400 W or
more, ten at the ceiling.

ONE PROBE'S SPIKE IS LEFT OUT. Each probe has a usual place about the mean of them all; one that moves
0.4 C in a quarter of an hour while the others move less than half of that, and stands 0.3 C from its
usual place, is left out for as long as it stands there and no longer than an hour.

Its memory is QUEUE/hearth/hold.json (what it holds paused, what it switched off, the probes' usual
places, when it last changed anything), its record hold.tsv (a line a look), its words hold.log, and
steady.tsv, a line for each two hours the room did not move (within 0.35 C, no slope) with nothing changed: the fleet's
watts against the room's height over the outside, which is the house's loss being measured.
"""
import contextlib
import io
import math
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
NEVER = ("mac",)
BAND_C, DWELL_S, URGENT_GAP_S, STEADY_S = 0.25, 2400.0, 600.0, 7200.0
# How near the ceiling counts as at it. It was 0.15: with the target at 26.7, the band's top at 26.95 and the
# ceiling at 27.2, that left a tenth of a degree in which the order of preference applied at all, and on the
# morning of 18 November the first machine shed was calber, a card machine, "at the ceiling" at 27.05.
CEILING_NEAR_C = 0.05
AHEAD_SLOPE, AHEAD_H = 0.15, 0.75     # act on where the room will be in three quarters of an hour, if it is moving this fast
HASTE_W, HASTE_S = 400.0, 900.0       # a budget this large does not wait forty minutes for its next step: fifteen
UA_W_C, C_MJ_C, BUDGET_MAX_W = 120.0, 4.2, 600.0


def slope_of(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else 0.0


def without_spikes(hs, t, vals, mean, note):
    """The room with a probe that has jumped by itself left out (the module's account says when)."""
    hist, devs, out = hs.setdefault("phist", []), hs.setdefault("pdevs", []), hs.setdefault("spiking", {})
    hist.append([t, dict(vals)])
    del hist[:-60]
    usual = {}
    for k in vals:
        d = sorted(x[k] for tt, x in devs if k in x and t - tt < 4 * 3600)
        if len(d) >= 6:
            usual[k] = d[len(d) // 2]
    if len(vals) < 2 or len(usual) < len(vals):
        devs.append([t, {k: v - mean for k, v in vals.items()}])
        del devs[:-60]
        return mean
    old = next((x for tt, x in hist if 600 <= t - tt <= 1500), None)
    moved = {k: abs(vals[k] - old[k]) for k in vals if old and k in old}
    for k in vals:
        rest = [j for j in vals if j != k]
        others = [moved[j] for j in moved if j != k]
        away = abs(vals[k] - usual[k] - sum(vals[j] - usual[j] for j in rest) / len(rest)) > 0.3
        if k not in out and away and k in moved and moved[k] >= 0.4 and others and max(others) < moved[k] / 2:
            out[k] = t
            note("probe %s moved %.1f C in a quarter of an hour and the other did not: taken as a spike of its own and left out of the room" % (k[5:-2], moved[k]))
    good = [k for k in vals if k not in out] or list(vals)
    est = sum(vals[k] - usual[k] for k in good) / len(good)
    for k in list(out):
        if k not in vals or abs(vals[k] - usual[k] - est) <= 0.3:
            note("probe %s is back at its usual place: it is counted again" % k[5:-2])
            del out[k]
        elif t - out[k] > 3600:
            note("probe %s has stood away from its usual place for an hour: it is believed, and its place is learned again" % k[5:-2])
            del out[k]
            devs[:] = []
    if not out:
        devs.append([t, {k: v - mean for k, v in vals.items()}])
        del devs[:-60]
        return mean
    return est


def seed(H, q, hs, used):
    """Each probe's usual place, from the last hours of the telemetry: a law just switched on knows a spike."""
    byt = {}
    for p in used:
        try:
            lines = open(os.path.join(q, "telemetry", p["machine"], time.strftime("%Y%m%d.log", time.gmtime()))).read().splitlines()[-2900:]
        except (OSError, KeyError):
            continue
        for l in lines[::60]:
            d = H.parse(l)
            if p["key"] in d and "t" in d and not H.not_a_reading(d[p["key"]]):
                byt.setdefault(int(d["t"] // 300), {})[p["key"]] = d[p["key"]]
    for b in sorted(byt)[:-1]:
        if len(byt[b]) >= 2:
            without_spikes(hs, b * 300.0, byt[b], sum(byt[b].values()) / len(byt[b]), lambda w: None)


def lagged(looks, t, tau_h=9.7):
    """THE WEATHER THE ROOM HAS FELT. A room with a time constant of ten hours does not stand against the
    weather of this minute but against the weather of the last half day, the newest hours counting most.
    Two stretches of the night of 17 November had the same watts and the same room while the weather went
    from 4.3 to 7.0 C between them: taken at the minute, they said the house lost 58 and then 68 W a
    degree. So the weather for a steady stretch is its mean over the hours before, each weighted
    exp(-age / tau), tau the room's own (C / UA, 9.7 h at the figure in use). `looks` is (t, weather)."""
    num = den = 0.0
    for tt, o in looks:
        if tt <= t and t - tt < 4 * tau_h * 3600:
            w = math.exp(-(t - tt) / (tau_h * 3600))
            num, den = num + w * o, den + w
    return num / den if den else None


def weather_looks(H, q):
    out = []
    try:
        for l in open(H.hp(q, "hold.tsv")):
            w = l.split("\t")
            if l[:1].isdigit() and len(w) >= 3 and w[2]:
                out.append((float(w[0]), float(w[2])))
    except (OSError, ValueError):
        pass
    return out


def steady_rows(H, q):
    """steady.tsv as rows: [from, to, room, outside, over, watts]."""
    rows = []
    try:
        for l in open(H.hp(q, "steady.tsv")):
            w = l.split("\t")
            if len(w) >= 6:
                rows.append([float(x) for x in w[:6]])
    except (OSError, ValueError):
        pass
    return rows


def steady_fit(rows):
    """THE HOUSE'S LOSS FROM THE STRETCHES THE ROOM STOOD STILL. In a room that is not moving what goes in
    goes out, P + P0 = UA (T - To), so each stretch is a point, the fleet's watts against the room's height
    over the weather, and as the weather moves the points lie on the line P = UA (T - To) - P0. Its slope
    is UA and its foot the other heat. (UA, P0, how many stretches, how far apart their heights stand), or
    None with fewer than three stretches or less than 2 C between the lowest and the highest."""
    if len(rows) < 3:
        return None
    over, w = [r[4] for r in rows], [r[5] for r in rows]
    spread = max(over) - min(over)
    if spread < 2.0:
        return None
    ua = slope_of(over, w)
    p0 = ua * sum(over) / len(over) - sum(w) / len(w)
    return ua, p0, len(rows), spread


def backfill(H, q):
    """Read hold.tsv again for stretches the room stood still and nothing was changed, and write the ones
    steady.tsv does not have. For the hours before 18 November, when a stretch was counted only inside
    the target's band. Returns how many were added."""
    looks, changes = [], []
    try:
        for l in open(H.hp(q, "hold.tsv")):
            if l.startswith("# 20"):
                try:
                    changes.append(time.mktime(time.strptime(l[2:21], "%Y-%m-%dT%H:%M:%S")))
                except ValueError:
                    pass
            elif l[:1].isdigit():
                w = l.rstrip("\n").split("\t")
                if len(w) >= 5 and w[2]:
                    looks.append((float(w[0]), float(w[1]), float(w[2]), float(w[4])))
    except OSError:
        return 0
    have = {int(r[0]) for r in steady_rows(H, q)}
    added, i = 0, 0
    while i < len(looks):
        j = i
        while j < len(looks) and looks[j][0] - looks[i][0] < STEADY_S:
            j += 1
        if j >= len(looks):
            break
        span = looks[i:j + 1]
        t0, t1 = span[0][0], span[-1][0]
        rooms, watts = [r[1] for r in span], [r[3] for r in span]
        still = (max(rooms) - min(rooms) <= 0.35 and abs(slope_of([r[0] / 3600 for r in span], rooms)) <= 0.1
                 and len(span) >= 12 and max(b[0] - a[0] for a, b in zip(span, span[1:])) <= 1500
                 and not any(t0 - 1800 <= c <= t1 for c in changes)
                 and max(watts) - min(watts) <= 0.35 * (sum(watts) / len(watts)))      # the watts level too: a change made shows as a step in them
        if still and int(t0) not in have:
            rm, p = sum(rooms) / len(span), sum(watts) / len(span)
            o = lagged([(r[0], r[2]) for r in looks], (t0 + t1) / 2) or sum(r[2] for r in span) / len(span)
            with open(H.hp(q, "steady.tsv"), "a") as f:
                f.write("%d\t%d\t%.2f\t%.1f\t%.2f\t%.0f\n" % (t0, t1, rm, o, rm - o, p))
            added += 1
            i = j + 1
        else:
            i += 1 if not still else j - i + 1
    return added


def look(H, q, st, t, cfg, ms, ps, plan, said, act):
    """One look. Fills the plan's `hold`, `would`, `wanted_w`, `diff_w` and `budget`, says what it sees first
    in `said`, and, where `act`, does the one thing it decided."""
    hs = H.load(H.hp(q, "hold.json"), {}) or {}
    for k, v in (("held", []), ("offed", []), ("spare", []), ("last_change_t", 0), ("rows", []), ("steady_from", None), ("asked", {})):
        hs.setdefault(k, v)
    words = []

    def note(w):
        words.append(w)

    def done():
        hs["beat"], hs["pid"], hs["by"] = t, None, "the controller's own law, at every pass"
        H.save(q, "hold.json", hs)
        stamp = time.strftime("%H:%M:%S", time.localtime(t))
        with open(H.hp(q, "hold.log"), "a") as f:
            for w in words:
                f.write("%s  %s\n" % (stamp, w))
        said[0:0] = ["the hold: " + w for w in words] + ["(below, the ladder's law, for comparison: it does not act while the law is hold)"]
        if plan.get("would") is None and words:
            plan["why_not"] = "by the hold: " + words[-1] if len(words) > 1 else "by the hold: inside the band, or nothing it may take"
        plan["hold"] = {"running": bool(act), "by": hs["by"], "beat_age_s": 0, "auto": True, "held": hs["held"], "spare": spares(), "last": "%s  %s" % (stamp, words[-1]) if words else "",
                        "steady": steady_n(), "pid": None}

    def steady_n():
        try:
            return sum(1 for l in open(H.hp(q, "steady.tsv")) if l.strip())
        except OSError:
            return 0

    def spares():
        return list(dict.fromkeys(hs["spare"] + hs["offed"]))

    used = [p for p in ps if p["role"] == "room" and p["ok"]]
    if not used or plan.get("now_w") is None:
        note("nothing is changed: %s" % ("no room probe is fresh" if not used else "the fleet's watts are not known"))
        plan["would"] = None
        return done()
    vals = {p["key"]: p["c"] for p in used}
    if not hs.get("pdevs"):
        seed(H, q, hs, used)
    plain = sum(vals.values()) / len(vals)
    room = without_spikes(hs, t, vals, plain, note)
    out_c, watts, tgt = plan.get("outside_c"), plan["now_w"], st["target_c"]
    ceiling = H.setting(st, "ceiling") or tgt + 0.5
    hs["rows"].append([t, round(room, 3)])
    hs["rows"] = [r for r in hs["rows"] if t - r[0] < 3 * 3600]
    hour = [r for r in hs["rows"] if t - r[0] <= 3900]
    slope = slope_of([r[0] / 3600 for r in hour], [r[1] for r in hour]) if len(hour) >= 4 and hour[-1][0] - hour[0][0] >= 1200 else 0.0
    # UA: what a person set; else the line through the steady stretches, once there are four of them standing
    # 3 C apart and it is a house's figure; else the figure in use.
    fit = steady_fit(steady_rows(H, q))
    if st["set"].get("ua"):
        ua, ua_from = st["set"]["ua"], "set by a person"
    elif fit and fit[2] >= 4 and fit[3] >= 3.0 and 40 <= fit[0] <= 400:
        ua, ua_from = fit[0], "%d steady stretches, %.1f C apart" % (fit[2], fit[3])
    else:
        ua, ua_from = UA_W_C, "a figure in use, not a measurement"
    c_j = C_MJ_C * 1e6
    need = max(-BUDGET_MAX_W, min(BUDGET_MAX_W, -(ua * (room - tgt) + c_j * slope / 3600)))
    new = not os.path.exists(H.hp(q, "hold.tsv"))
    with open(H.hp(q, "hold.tsv"), "a") as f:
        if new:
            f.write("#t\troom_c\toutside_c\tover_c\tfleet_w\ttarget_c\n")
        f.write("%d\t%.2f\t%s\t%s\t%.0f\t%.2f\n" % (t, room, "%.1f" % out_c if out_c is not None else "", "%.2f" % (room - out_c) if out_c is not None else "", watts, tgt))
    f_of = H.f_of
    since = t - hs["last_change_t"]
    note("room %.2f C (%.1f F), target %.1f F, ceiling %.1f F; outside %s, over it by %s; fleet %.0f W; the room moving %+.2f C an hour; budget %+.0f W" % (
        room, f_of(room), f_of(tgt), f_of(ceiling), "%.1f C" % out_c if out_c is not None else "?", "%.1f C" % (room - out_c) if out_c is not None else "?", watts, slope, need))
    plan.update(budget={"w": round(need), "ua_w_c": ua, "c_mj_c": C_MJ_C, "slope_c_h": round(slope, 3), "room_c": round(room, 2), "ceiling_c": ceiling,
                        "ua_from": ua_from, "ua_measured": not ua_from.startswith("a figure"),
                        "fit": {"ua_w_c": round(fit[0]), "p0_w": round(fit[1]), "stretches": fit[2], "spread_c": round(fit[3], 1)} if fit else None,
                        "trend": [r[1] for r in hs["rows"]]},      # the room over the last three hours, for the Diagram panel's strip
                wanted_w=round(watts + need), diff_w=round(need), temp_c=round(room, 2))

    # ---- what there is to take
    power = H.setting(st, "power") == "on"
    mine = H.load(H.hp(q, "machines.json"), {}) or {}
    orders = H.load(H.hp(q, "power.json"), {}) or {}
    flying = {n for n, o in orders.items() if not o.get("done") and t - o.get("t", 0) < 1800}
    carriers = {p.get("machine") for p in ps if p["role"] == "room"}
    energy = (H.load(H.hp(q, "energy.json"), {}) or {}).get("wh_a_job", {})
    boxes = (H.load(os.path.join(HERE, "plans", "power.json"), {}) or {}).get("boxes", {})
    wakes = lambda n: mine.get(n, {}).get("wol") is True
    has_card = lambda n: bool((ms.get(n) or {}).get("card")) or "gpu" in boxes.get(n, {})
    # The energy a job costs there; a machine with no record is taken as its box's rating for each thread, which keeps the order of ages.
    spend = lambda n: energy.get(n) or (boxes.get(n, {}).get("cpu_full_w", 100) / 3.0)
    full = lambda n: (lambda b: (b.get("rest_w", 0) + b.get("cpu_full_w", 0) * 0.9 + b.get("gpu_limit_w", 0) * 0.6) / b.get("eff", 0.88))(boxes.get(n, {})) or 200.0

    def lane_w(m, h):
        b = boxes.get(m["name"], {})
        if "cuda" in h.get("caps", []):
            return (b.get("gpu_limit_w", 0) * 0.6) / b.get("eff", 0.88)
        return (b.get("cpu_full_w", 0) - b.get("cpu_idle_w", 0)) * 0.9 / max(1, len(m["cpu"])) / b.get("eff", 0.88)

    shed, add = [], []
    for name, m in ms.items():
        lanes = m["cpu"] + m["card"]
        if name in NEVER or m["target"] == "-" or m["special"] or name in flying:
            continue
        whole = wakes(name) and power and name not in carriers and m["poweroff"] and mine.get(name, {}).get("mac")
        if lanes and not m["bench"]:
            running = [h for h in lanes if not h.get("paused")]
            if whole and running and m["fresh"] and m["wall_w"] is not None and not any(h.get("paused") and h["name"] not in hs["held"] for h in lanes):
                shed.append({"do": "off", "name": name, "w": m["wall_w"], "key": (has_card(name), False, -spend(name)),
                             "what": "%s finishes its task and is switched off (it wakes by the packet)" % name})
            # THE MACHINE THAT CARRIES THE PROBES IS LEFT WORKING. Its own heat is part of what the probes
            # read: paused, its corner cools, the probes read low, and heat is added somewhere the probes
            # are not (the evening of 17 November: saskatchewan paused, two machines woken elsewhere, the
            # probes at 79.5 F and Paul saying "it got hot").
            elif not whole and name not in carriers and m["fresh"] and m["wall_w"] is not None:      # a machine whose watts are not read is no heat this law can count
                for h in running:
                    w = lane_w(m, h)
                    if w >= 10:
                        card = "cuda" in h.get("caps", [])
                        shed.append({"do": "pause", "name": h["name"], "w": w, "key": (has_card(name), card, -spend(name)),
                                     "what": "%s takes nothing new" % h["name"]})
            for h in lanes:
                if h.get("paused") and h["name"] in hs["held"]:
                    card = "cuda" in h.get("caps", [])
                    add.append({"do": "resume", "name": h["name"], "w": lane_w(m, h), "key": (not has_card(name), not card, spend(name)),
                                "what": "%s takes work again" % h["name"]})
        elif name in spares():
            if m["fresh"]:
                # On, and not computing.
                add.append({"do": "add", "name": name, "w": max(20.0, full(name) - (m["wall_w"] or 0)), "key": (not has_card(name), False, spend(name)), "idle": True,
                            "what": "%s is on and not in the queue; a machine that is on computes: it is put in the queue" % name})
                if whole:
                    shed.append({"do": "off", "name": name, "w": m["wall_w"] or 100.0, "key": (False, False, -1e9), "idle": True,
                                 "what": "%s is on and idle: it is switched off (it wakes by the packet)" % name})
            elif wakes(name) and power and mine.get(name, {}).get("mac"):
                add.append({"do": "wake", "name": name, "w": full(name), "key": (not has_card(name), False, spend(name)),
                            "what": "%s is woken, and computes as soon as it is up%s" % (name, " (it took %s last time)" % H.ago(mine[name]["boot_s"]) if mine.get(name, {}).get("boot_s") else "")})
    hs["held"] = [l for l in hs["held"] if any(h["name"] == l and h.get("paused") for m in ms.values() for h in m["cpu"] + m["card"])]

    def pick(opts, want, biggest=False):
        """The step for a budget: the first in the order of preference that is no more than twice it (or
        250 W); failing that the smallest.
        AT THE CEILING the preference gives way: the largest that is no more than twice the budget,
        whatever machine it is on (17 November, 18:22 to 18:37: asked for 600 W, the order of preference
        gave an idle machine's 143 W and then one lane's 73 W, and the room went through 81 F)."""
        opts = sorted(opts, key=lambda o: o["key"])
        under = [o for o in opts if o["w"] <= max(2.0 * want, 350.0)]      # 350: the largest single machine at work is a step that may be taken
        if not opts:
            return None
        if biggest:
            # The largest, but among the machines without a card first where one of them is a real step
            # (150 W or more): the card machines are kept even at the ceiling while something else will do.
            plain = [o for o in under if not o["key"][0] and o["w"] >= 150.0]
            return max(plain or under, key=lambda o: o["w"]) if under else min(opts, key=lambda o: o["w"])
        # THE ORDER OF PREFERENCE IS KEPT, whatever the size: a large budget is met by the shorter wait
        # between steps, not by reaching past a card's lane for a machine that spends its energy badly
        # (21:47 on 17 November: asked for 415 W, it woke bosporus, 249 W, over four paused lanes of the
        # card machines that were each too small to be "a fair share").
        return under[0] if under else min(opts, key=lambda o: o["w"])

    # FOR THE CEILING A PROBE LEFT OUT IS STILL BELIEVED: if it is a spike, a lane is paused for nothing and
    # given back; if it is the room (18:37 on 17 November it was), the ceiling is kept.
    urgent = max(room, plain) >= ceiling - CEILING_NEAR_C and slope > -0.05
    choice, why = None, ""
    idle = [o for o in add + shed if o.get("idle")]
    if urgent and since >= URGENT_GAP_S:
        choice, why = pick(shed, max(-need, 250.0), biggest=True), "AT THE CEILING and not falling"
    elif since < (HASTE_S if abs(need) >= HASTE_W else DWELL_S):
        note("%d min since the last change; it waits %d more%s" % (since / 60, ((HASTE_S if abs(need) >= HASTE_W else DWELL_S) - since) / 60, " (AT THE CEILING: it waits %d min only)" % ((URGENT_GAP_S - since) / 60) if urgent else ""))
    elif idle and (need > -100 or any(o["do"] == "off" for o in idle)):
        # A machine on and idle is settled before anything else: to work if the room has room for it, off if not.
        choice = next((o for o in idle if o["do"] == ("add" if need > -100 else "off")), None)
        why = "a machine that is on computes"
    elif room >= tgt + BAND_C and slope > -0.1:
        choice, why = pick(shed, -need), "too warm and not falling"
    # WHERE THE ROOM IS HEADING. The room answers an hour late, so a law that waits for it to leave the band
    # has already lost that hour (the night of 17 November: it fell a third of a degree an hour for an hour
    # in plain sight, and heat was added only at the band's foot; it reached 78.1 F). If the slope is clear,
    # 0.15 C an hour or more, and carries the room out of the band within three quarters of an hour, the step
    # is taken now.
    elif slope >= AHEAD_SLOPE and room + slope * AHEAD_H >= tgt + BAND_C:
        choice, why = pick(shed, -need), "heading over the band (%.2f C in %d min at %+.2f C an hour)" % (room + slope * AHEAD_H, AHEAD_H * 60, slope)
    elif room <= tgt - BAND_C and slope < 0.1:
        choice, why = pick(add, need), "too cold and not rising"
    elif slope <= -AHEAD_SLOPE and room + slope * AHEAD_H <= tgt - BAND_C:
        choice, why = pick(add, need), "heading under the band (%.2f C in %d min at %+.2f C an hour)" % (room + slope * AHEAD_H, AHEAD_H * 60, slope)
    if why.startswith("too cold") or why.startswith("heading under"):
        if choice is None and room <= tgt - BAND_C:
            cold = [n for n in spares() if not (ms.get(n) or {}).get("fresh") and n not in flying]
            note("too cold, and nothing is left that this law may add." + (" SWITCH ON %s: it is put to work when it answers" % cold[0].upper() if cold else " The fleet has no more to give"))
    plan["would"] = None
    if choice is not None:
        cmds = {"pause": "fleet-queue.py QUEUE machine %s pause", "resume": "fleet-queue.py QUEUE machine %s resume", "add": "fleet-queue.py QUEUE machine %s add",
                "off": "hearth.py QUEUE power-off %s", "wake": "hearth.py QUEUE power-on %s"}[choice["do"]] % choice["name"]
        plan["would"] = {"what": choice["what"], "watts": round(choice["w"]), "cmds": [cmds], "why": why}
        if not act:
            note("%s, %.0f W to %s: it WOULD: %s (about %.0f W). Not in act: nothing is done" % (why, abs(need), "shed" if choice in shed else "add", choice["what"], choice["w"]))
        else:
            ok, heard = carry(H, q, choice)
            note("%s, %.0f W to %s: %s (about %.0f W)%s" % (why, abs(need), "shed" if choice in shed else "add", choice["what"], choice["w"], "" if ok else ". IT FAILED: " + heard[-160:]))
            if ok:
                hs["last_change_t"], hs["steady_from"] = t, None
                if choice["do"] == "pause":
                    hs["held"].append(choice["name"])
                elif choice["do"] == "resume":
                    hs["held"] = [l for l in hs["held"] if l != choice["name"]]
                elif choice["do"] == "off" and choice["name"] not in hs["offed"]:
                    hs["offed"].append(choice["name"])
            st["last_action"] = {"what": choice["what"], "t": t, "at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t)), "ok": ok}
            st["last_action_t"] = t
            plan["did"] = dict(st["last_action"], ran=[{"cmd": cmds, "ok": ok, "said": heard[-300:]}])

    # ---- a stretch standing still: the house's loss being measured
    # Standing still is the room not moving, wherever it stands: the night of 17 November it stood five
    # hours at 26.0 C with every machine on, 0.7 under its target, and under the first rule (inside the
    # band) none of it was written down.
    if flying:
        hs["steady_from"] = None
    elif hs["steady_from"] is None:
        hs["steady_from"] = max(t, hs["last_change_t"] + 1800)
    elif t - hs["steady_from"] >= STEADY_S and out_c is not None:
        span = [r for r in hs["rows"] if r[0] >= hs["steady_from"]]
        if len(span) >= 6 and abs(slope_of([r[0] / 3600 for r in span], [r[1] for r in span])) <= 0.1 and max(r[1] for r in span) - min(r[1] for r in span) <= 0.35:
            rm = sum(r[1] for r in span) / len(span)
            felt = lagged(weather_looks(H, q), (span[0][0] + span[-1][0]) / 2) or out_c       # the weather the room has felt, not this minute's
            with open(H.hp(q, "steady.tsv"), "a") as f:
                f.write("%d\t%d\t%.2f\t%.1f\t%.2f\t%.0f\n" % (span[0][0], span[-1][0], rm, felt, rm - felt, watts))
            out_c = felt
            note("STEADY: the room stood at %.2f C for %.1f h on about %.0f W, %.1f C over the outside: %.0f W for each degree, the house's other heat left out (steady.tsv)" % (
                rm, (span[-1][0] - span[0][0]) / 3600, watts, rm - out_c, watts / (rm - out_c)))
        hs["steady_from"] = t
    # The energy each machine spends on a job, kept fresh for the order above: made again when it is half a day old.
    try:
        age = t - os.path.getmtime(H.hp(q, "energy.json"))
    except OSError:
        age = 1e9
    if age > 12 * 3600 and act:
        subprocess.Popen([sys.executable, os.path.join(HERE, "hearth-energy.py"), q, "--from", time.strftime("%Y-%m-%d %H:%M", time.localtime(t - 2 * 86400))],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    done()


def carry(H, q, choice):
    """Do the one thing. (whether it was taken, what was said.)"""
    if choice["do"] == "add":
        return H.run_queue(q, "machine", choice["name"], "add")
    if choice["do"] in ("pause", "resume"):
        # THE QUEUE'S PAUSE OF A MACHINE'S FIRST LANE IS A PAUSE OF THE MACHINE: `machine saskatchewan
        # pause` pauses saskatchewan-2 and a card's lane with it, and resume resumes them all. This law's
        # step is one lane, so the others are put back as they were.
        cfg = H.load(os.path.join(q, "config.json"), {}) or {}
        was = {h["name"]: bool(h.get("paused")) for h in cfg.get("hosts", []) if h.get("lane_of") == choice["name"]}
        ok, heard = H.run_queue(q, "machine", choice["name"], choice["do"])
        for lane, paused in was.items():
            if ok and paused != (choice["do"] == "pause"):
                H.run_queue(q, "machine", lane, "pause" if paused else "resume")
        return ok, heard
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = H.power_order(q, choice["name"], "off" if choice["do"] == "off" else "on")
        return rc == 0, buf.getvalue().strip()
    except SystemExit as e:          # the order was refused, and says why
        return False, str(e)
