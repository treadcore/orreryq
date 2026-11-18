#!/usr/bin/env python3
"""The room's answer to a step in the fleet's watts, read beside every disk and CPU that was recording.
It reads; it commands nothing.

    hearth-response.py QUEUE [OUTDIR]     the numbers, and three pictures in OUTDIR (docs/hearth-response)

Run `hearth-house.py QUEUE` first: it keeps the outside air this reads.

WHAT IT WORKS OUT
  the step        the largest lasting change in the fleet's watts: when, from what, to what, and which
                  machines made it.
  the turn        the room's slope before and after, its lowest point, and how long after the step it
                  began to rise.
  the fit         C dT/dt = P + P0 - UA (T - To), with the room SIMULATED from the recorded watts and
                  outside and laid over the probes, and the four numbers moved until the two agree
                  (an output-error fit: it does not difference a probe that reads in tenths). The
                  probes ride on saskatchewan, so what they read is the room plus cs degrees for each
                  watt saskatchewan draws; cs is fitted with the rest. Then the same fit with UA held
                  at each of a row of values, which shows how much of UA the record decides.
  the parts       every machine's disks, NVMe drives and CPU, as their change over the night and over
                  the step, beside the change in that machine's own watts: a part in a machine whose
                  watts held still moved because the room did.
  the stepped     the CPUs and disks of the machines that made the step: how fast each answered.
"""
import glob
import importlib.util
import json
import math
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
_s = importlib.util.spec_from_file_location("hearth_house", os.path.join(HERE, "hearth-house.py"))
house = importlib.util.module_from_spec(_s)
_s.loader.exec_module(house)

B = 600
BG, INK, DIM, FAINT, PANEL = "#0e1013", "#ece9e1", "#9a978d", "#4a4944", "#15181d"
GREEN, ORANGE, BLUE, YELLOW, RED, VIOLET = "#83c167", "#ff8c5a", "#58c4dd", "#f7d96f", "#fc6255", "#b9a6e8"
SANS = "Avenir Next, Helvetica Neue, Helvetica, Arial, sans-serif"


def kind(k):
    h = k.split(".")[0].split("_")[0]
    if k.startswith("room.") and k.endswith(".c"):
        return "room"
    if h in ("coretemp", "k10temp", "zenpower"):
        return "cpu"
    if h == "drivetemp" or k.startswith("disk."):
        return "disk"
    if h == "nvme" and k.endswith("Composite"):
        return "nvme"
    return None


def load(q, since):
    """{machine: {bucket: {"W": watts, "kind:key": degrees}}}, ten-minute means; and the raw CPU means
    of each machine a minute a point."""
    boxes = (json.load(open(os.path.join(HERE, "plans", "power.json"))) or {}).get("boxes", {})
    acc, fine = {}, {}
    for m, s in house.samples(q):
        if s["t"] < since:
            continue
        a = acc.setdefault(m, {}).setdefault(int(s["t"] // B), {})
        w = house.wall(boxes.get(m), s)
        if w is not None:
            x = a.setdefault("W", [0, 0])
            x[0] += w
            x[1] += 1
        cpus = []
        for k, v in s.items():
            kd = kind(k)
            if kd and not (kd == "room" and house.not_a_reading(v)):
                x = a.setdefault(kd + ":" + k, [0, 0])
                x[0] += v
                x[1] += 1
                if kd == "cpu":
                    cpus.append(v)
        if cpus:
            x = fine.setdefault(m, {}).setdefault(int(s["t"] // 60), [0, 0, 0])
            x[0] += sum(cpus) / len(cpus)
            x[1] += 1
            x[2] += s.get("busy", 0)
    data = {m: {b: {k: v[0] / v[1] for k, v in a.items()} for b, a in bs.items()} for m, bs in acc.items()}
    fine = {m: {b: (v[0] / v[1], v[2] / v[1]) for b, v in bs.items()} for m, bs in fine.items()}
    return data, fine


KEEP = {}


def group(data, m, kd, b):
    """The mean of a machine's channels of one kind in one bucket, or None. ALWAYS THE SAME CHANNELS:
    those in at least nine buckets of ten. A drive that stops answering for an hour would otherwise
    move the mean by what it alone read, and a bucket without one of them is left out."""
    if (m, kd) not in KEEP:
        n = {}
        for a in data.get(m, {}).values():
            for k in a:
                if k.startswith(kd + ":"):
                    n[k] = n.get(k, 0) + 1
        KEEP[(m, kd)] = sorted(k for k, c in n.items() if c >= 0.9 * max(n.values())) if n else []
    ks, a = KEEP[(m, kd)], data.get(m, {}).get(b, {})
    return sum(a[k] for k in ks) / len(ks) if ks and all(k in a for k in ks) else None


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def slope(ts, vs):
    """Least-squares slope of vs against ts (per unit of ts)."""
    n = len(ts)
    mt, mv = sum(ts) / n, sum(vs) / n
    den = sum((t - mt) ** 2 for t in ts)
    return sum((t - mt) * (v - mv) for t, v in zip(ts, vs)) / den if den else 0.0


def corr(a, b):
    n = len(a)
    if n < 6:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    sa, sb = sum((x - ma) ** 2 for x in a), sum((x - mb) ** 2 for x in b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(sa * sb) if sa > 0 and sb > 0 else None


def nelder(f, x0, steps, iters=900):
    """Nelder and Mead's simplex, enough for four numbers."""
    n = len(x0)
    pts = [list(x0)] + [[x0[j] + (steps[j] if j == i else 0) for j in range(n)] for i in range(n)]
    val = [f(p) for p in pts]
    for _ in range(iters):
        order = sorted(range(n + 1), key=lambda i: val[i])
        pts, val = [pts[i] for i in order], [val[i] for i in order]
        cen = [sum(p[j] for p in pts[:-1]) / n for j in range(n)]
        ref = [cen[j] + (cen[j] - pts[-1][j]) for j in range(n)]
        fr = f(ref)
        if fr < val[0]:
            ex = [cen[j] + 2 * (cen[j] - pts[-1][j]) for j in range(n)]
            fe = f(ex)
            pts[-1], val[-1] = (ex, fe) if fe < fr else (ref, fr)
        elif fr < val[-2]:
            pts[-1], val[-1] = ref, fr
        else:
            con = [cen[j] + 0.5 * (pts[-1][j] - cen[j]) for j in range(n)]
            fc = f(con)
            if fc < val[-1]:
                pts[-1], val[-1] = con, fc
            else:
                pts = [pts[0]] + [[pts[0][j] + 0.5 * (p[j] - pts[0][j]) for j in range(n)] for p in pts[1:]]
                val = [val[0]] + [f(p) for p in pts[1:]]
    i = min(range(n + 1), key=lambda i: val[i])
    return pts[i], val[i]


def simulate(rec, tau_h, ua, p0, cs, ref_s):
    """The probes as the balance says they should read: the room from the watts and the outside,
    begun where the record begins, plus cs degrees for each watt saskatchewan draws over ref_s."""
    x = rec[0]["room"] - cs * (rec[0]["Ps"] - ref_s)
    out = []
    for i, r in enumerate(rec):
        if i:
            dt_h = (r["t"] - rec[i - 1]["t"]) / 3600
            prev = rec[i - 1]
            settle = prev["To"] + (prev["P"] + p0) / ua
            x = settle + (x - settle) * math.exp(-dt_h / tau_h)
        out.append(x + cs * (r["Ps"] - ref_s))
    return out


def fit(rec, ref_s, ua_fixed=None, with_cs=True):
    def cost(p):
        tau_h, ua, p0, cs = p[0], (ua_fixed if ua_fixed else p[1]), p[2], (p[3] if with_cs else 0.0)
        if tau_h < 0.3 or ua < 5 or cs < 0 or p0 < -500:
            return 1e9
        sim = simulate(rec, tau_h, ua, p0, cs, ref_s)
        return sum((a - r["room"]) ** 2 for a, r in zip(sim, rec))
    best = None
    for tau0 in (6.0, 15.0, 40.0):
        for ua0 in ((ua_fixed,) if ua_fixed else (50.0, 100.0, 200.0)):
            p, v = nelder(cost, [tau0, ua0, 300.0, 0.003], [tau0 * 0.3, ua0 * 0.3, 200.0, 0.002])
            if best is None or v < best[1]:
                best = (p, v)
    p, v = best
    return {"tau_h": p[0], "ua": ua_fixed if ua_fixed else p[1], "p0": p[2], "cs": p[3] if with_cs else 0.0,
            "rms": math.sqrt(v / len(rec))}


# ---- the pictures -------------------------------------------------------------------------------

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


def text(x, y, s, size=15, col=INK, anchor="start", weight=400):
    return '<text x="%.1f" y="%.1f" font-family="%s" font-size="%d" fill="%s" text-anchor="%s" font-weight="%d">%s</text>' % (
        x, y, SANS, size, col, anchor, weight, esc(s))


def nice(lo, hi, n=5):
    span = (hi - lo) or 1.0
    step = 10 ** math.floor(math.log10(span / n))
    for m in (1, 2, 2.5, 5, 10):
        if span / (step * m) <= n:
            step *= m
            break
    a = math.floor(lo / step) * step
    ticks = []
    while a <= hi + step * 0.001:
        if a >= lo - step * 0.001:
            ticks.append(a)
        a += step
    return ticks


def panel(x, y, w, h, t0, t1, series, title, unit, marks=(), ylim=None, fmt="%.1f"):
    """One plot: series is [(name, colour, [(t, v)], dashed)]. Every line is named at its right end."""
    vs = [v for _, _, pts, _ in series for _, v in pts]
    lo, hi = ylim or (min(vs), max(vs))
    pad = (hi - lo) * 0.08 or 0.5
    lo, hi = (lo - pad, hi + pad) if not ylim else (lo, hi)
    X = lambda t: x + (t - t0) / (t1 - t0) * w
    Y = lambda v: y + h - (v - lo) / (hi - lo) * h
    b = '<rect x="%d" y="%d" width="%d" height="%d" fill="%s" rx="6"/>' % (x - 62, y - 34, w + 62 + 190, h + 62, PANEL)
    b += text(x - 50, y - 12, title, 15, DIM, weight=700)
    for v in nice(lo, hi):
        b += '<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="%s" stroke-width="1"/>' % (x, x + w, Y(v), Y(v), FAINT)
        b += text(x - 8, Y(v) + 5, (fmt % v) + unit, 13, DIM, "end")
    h0 = int(t0 // 3600) * 3600
    every = 1 if (t1 - t0) < 8 * 3600 else 2 if (t1 - t0) < 30 * 3600 else 4
    t = h0
    while t <= t1:
        lt = time.localtime(t)
        if t >= t0 and lt.tm_hour % every == 0:
            b += '<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="%s" stroke-width="1"/>' % (X(t), X(t), y + h, y + h + 5, DIM)
            b += text(X(t), y + h + 20, "%02d:00" % lt.tm_hour, 12, DIM, "middle")
        t += 3600
    for mt, words in marks:
        if t0 <= mt <= t1:
            b += '<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="%s" stroke-width="1" stroke-dasharray="4 4"/>' % (X(mt), X(mt), y, y + h, DIM)
            if words:
                b += text(X(mt) + 5, y + 13, words, 12, DIM)
    ends = []
    for name, col, pts, dashed in series:
        if not pts:
            continue
        d = " ".join("%s%.1f %.1f" % ("M" if i == 0 else "L", X(t), Y(v)) for i, (t, v) in enumerate(pts))
        b += '<path d="%s" fill="none" stroke="%s" stroke-width="2" stroke-linejoin="round"%s/>' % (d, col, ' stroke-dasharray="7 5"' if dashed else "")
        ends.append([Y(pts[-1][1]), name, col, X(pts[-1][0])])
    ends.sort()
    for i in range(1, len(ends)):                      # labels a line apart
        if ends[i][0] - ends[i - 1][0] < 17:
            ends[i][0] = ends[i - 1][0] + 17
    for yy, name, col, xx in ends:
        b += '<circle cx="%.1f" cy="%.1f" r="3" fill="%s"/>' % (xx, yy, col) + text(xx + 9, yy + 5, name, 13, INK)
    return b


def picture(path, w, h, title, sub, body):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d"><rect width="%d" height="%d" fill="%s"/>%s%s%s</svg>'
           % (w, h, w, h, w, h, BG, text(40, 46, title, 24, INK, weight=700), text(40, 72, sub, 15, DIM), body))
    subprocess.run(["rsvg-convert", "-w", str(w * 2), "-h", str(h * 2), "-o", path], input=svg.encode(), check=True)


# ---- the work -----------------------------------------------------------------------------------

def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    q = argv[1]
    outdir = argv[2] if len(argv) > 2 else os.path.join(HERE, "..", "docs", "hearth-response")
    os.makedirs(outdir, exist_ok=True)
    stamp = lambda t: time.strftime("%d %b %H:%M", time.localtime(t))
    hm = lambda t: time.strftime("%H:%M", time.localtime(t))
    obs, _, _ = house.outside(q, "KSEA", False)
    out = {"t": sorted(obs), "v": [obs[t] for t in sorted(obs)]}
    data, fine = load(q, time.time() - 4 * 86400)
    sk = "saskatchewan"
    probes = sorted({k for a in data.get(sk, {}).values() for k in a if k.startswith("room:")})
    rec = []
    for b in sorted(data.get(sk, {})):
        a = data[sk][b]
        if not all(k in a for k in probes) or not probes:
            continue
        t = b * B + B // 2
        to = house.at(out, t, 2 * 3600)
        if to is None:
            continue
        per = {m: data[m][b]["W"] for m in data if b in data[m] and "W" in data[m][b]}
        rec.append({"b": b, "t": t, "room": sum(a[k] for k in probes) / len(probes), "probes": [a[k] for k in probes],
                    "To": to, "P": sum(per.values()), "Ps": per.get(sk, 0.0), "per": per})
    if len(rec) < 30:
        print("too little of the room is recorded")
        return 1
    print("the record: %s to %s, %d lines of ten minutes; probes %s" % (stamp(rec[0]["t"]), stamp(rec[-1]["t"]), len(rec), ", ".join(p[5:] for p in probes)))

    # ---- the step: the boundary with the largest lasting change in the watts
    best = None
    for i in range(12, len(rec) - 9):
        before, after = mean([r["P"] for r in rec[i - 12:i]]), mean([r["P"] for r in rec[i + 3:]])
        if best is None or abs(after - before) > abs(best[1] - best[0]):
            best = (before, after, i)
    p_before, p_after, si = best
    # It began where the watts first left the level before it.
    while si > 1 and abs(rec[si - 1]["P"] - p_before) > 0.15 * abs(p_after - p_before):
        si -= 1
    t_step = rec[si]["t"] - B // 2
    made = sorted(((mean([r["per"].get(m, 0) for r in rec[si + 3:]]) - mean([r["per"].get(m, 0) for r in rec[si - 12:si]]), m) for m in data), reverse=True)
    print("\nTHE STEP: the fleet went from %.0f W to %.0f W, %+.0f W, beginning about %s" % (p_before, p_after, p_after - p_before, stamp(t_step)))
    print("    made by: " + ", ".join("%s %+.0f W" % (m, d) for d, m in made if abs(d) >= 15))

    # ---- the turn
    pre = [r for r in rec if t_step - 4 * 3600 <= r["t"] < t_step]
    low = min(rec[si - 3:], key=lambda r: r["room"])
    post = [r for r in rec if r["t"] >= max(low["t"], rec[-1]["t"] - 2 * 3600)]
    s_pre = slope([r["t"] / 3600 for r in pre], [r["room"] for r in pre])
    s_post = slope([r["t"] / 3600 for r in post], [r["room"] for r in post]) if len(post) >= 4 else 0.0
    rose = next((r for i, r in enumerate(rec) if r["t"] > low["t"] and r["room"] >= low["room"] + 0.1
                 and all(x["room"] >= low["room"] + 0.1 for x in rec[i:i + 3])), None)
    print("\nTHE TURN: in the four hours before, the room moved %+.2f C an hour; lowest %.2f C at %s; over %s to %s it moved %+.2f C an hour" % (
        s_pre, low["room"], hm(low["t"]), hm(post[0]["t"]), hm(post[-1]["t"]), s_post))
    if rose:
        print("    it stood 0.1 C over its lowest, and stayed there, from %s: %.0f minutes after the step began" % (hm(rose["t"]), (rose["t"] - t_step) / 60))
    d_out = mean([r["To"] for r in post]) - mean([r["To"] for r in pre])
    c_slope = (p_after - p_before) / ((s_post - s_pre) / 3600) if s_post > s_pre else None
    if c_slope:
        print("    the slope changed %+.2f C an hour for %+.0f W: C = %.1f MJ/C if nothing else had moved (the outside moved %+.1f C)" % (
            s_post - s_pre, p_after - p_before, c_slope / 1e6, d_out))

    # ---- the fit
    ref_s = min(r["Ps"] for r in rec)
    whole = fit(rec, ref_s)
    plain = fit(rec, ref_s, with_cs=False)
    say = lambda f: "UA %.0f W/C, tau %.1f h, C %.1f MJ/C, P0 %.0f W, cs %.4f C/W; the probes missed by %.3f C (rms)" % (
        f["ua"], f["tau_h"], f["tau_h"] * 3600 * f["ua"] / 1e6, f["p0"], f["cs"], f["rms"])
    print("\nTHE FIT, the room simulated from the watts and the outside:")
    print("    " + say(whole))
    print("    without saskatchewan's own heat on the probes: " + say(plain))
    prof = []
    for ua in (40, 60, 80, 100, 125, 150, 200, 300):
        f = fit(rec, ref_s, ua_fixed=float(ua))
        prof.append(f)
        print("    UA held at %3d: tau %5.1f h, C %5.1f MJ/C, P0 %5.0f W, rms %.3f C" % (ua, f["tau_h"], f["tau_h"] * 3600 * ua / 1e6, f["p0"], f["rms"]))
    okay = [f for f in prof if f["rms"] <= whole["rms"] * 1.15]
    if okay:
        print("    within 15%% of the best miss: UA from %d to %d W/C; C from %.1f to %.1f MJ/C" % (
            min(f["ua"] for f in okay), max(f["ua"] for f in okay),
            min(f["tau_h"] * 3600 * f["ua"] / 1e6 for f in okay), max(f["tau_h"] * 3600 * f["ua"] / 1e6 for f in okay)))
    now = rec[-1]
    print("    by the best fit the room settles at %.1f C with the fleet at %.0f W and the outside at %.1f C" % (
        now["To"] + (p_after + whole["p0"]) / whole["ua"], p_after, now["To"]))
    # Fitted on what came before the step alone, and asked what the step would do.
    early = fit(rec[:si], ref_s)
    sim_e = simulate(rec, early["tau_h"], early["ua"], early["p0"], early["cs"], ref_s)
    miss = math.sqrt(mean([(a - r["room"]) ** 2 for a, r in zip(sim_e[si:], rec[si:])]))
    print("    fitted on the hours before the step only (%s), then run through it: it misses the hours after by %.2f C (rms)" % (say(early), miss))

    # ---- the parts
    t_load = next((r["t"] for i, r in enumerate(rec) if i > 6 and r["Ps"] - rec[i - 3]["Ps"] > 40 and r["t"] < t_step), None)
    n0 = (t_load + 1800) if t_load else rec[0]["t"]
    wins = {"night": (n0, t_step - 1800), "step": (t_step - 1800, rec[-1]["t"])}
    rows = []
    print("\nTHE PARTS. Change from the first hour to the last of each stretch; night %s to %s, step %s to %s" % (
        hm(wins["night"][0]), hm(wins["night"][1]), hm(wins["step"][0]), hm(wins["step"][1])))
    edge = lambda f, a, b: (mean([f(r) for r in rec if a <= r["t"] < a + 3600]), mean([f(r) for r in rec if b - 3600 < r["t"] <= b]))
    room_d = {w: (lambda e: e[1] - e[0])(edge(lambda r: r["room"], a, b)) for w, (a, b) in wins.items()}
    print("    %-28s  night %+.2f C            step %+.2f C" % ("the room (the two probes)", room_d["night"], room_d["step"]))
    for m in sorted(data):
        for kd, name in (("disk", "disks"), ("nvme", "NVMe"), ("cpu", "CPU")):
            group(data, m, kd, 0)
            n = len(KEEP[(m, kd)])
            if not n:
                continue
            row = {"machine": m, "kind": name, "n": n}
            for w, (a, b) in wins.items():
                e = edge(lambda r: group(data, m, kd, r["b"]), a, b)
                ew = edge(lambda r: r["per"].get(m), a, b)
                inwin = [(r["room"], group(data, m, kd, r["b"])) for r in rec if a <= r["t"] <= b]
                inwin = [(x, y) for x, y in inwin if y is not None]
                row[w] = None if None in e else e[1] - e[0]
                row[w + "_w"] = None if None in ew else ew[1] - ew[0]
                row[w + "_r"] = corr([x for x, _ in inwin], [y for _, y in inwin])
            rows.append(row)
            f = lambda v, s="%+.2f": (s % v) if v is not None else "  -  "
            print("    %-13s %-5s x%-2d       night %s C (r %s, its watts %s)   step %s C (r %s, its watts %s)" % (
                m, name, n, f(row["night"]), f(row["night_r"]), f(row["night_w"], "%+.0f"), f(row["step"]), f(row["step_r"]), f(row["step_w"], "%+.0f")))

    # ---- the machines that made the step: how fast their CPUs and disks answered
    stepped = [m for d, m in made if d >= 60]
    resp = {}
    print("\nTHE MACHINES THAT MADE THE STEP")
    for m in stepped:
        mins = sorted(b for b in fine.get(m, {}) if b * 60 >= t_step - 3600)
        work = next((b for b in mins if fine[m][b][1] > 0.5), None)
        if work is None:
            continue
        idle = mean([fine[m][b][0] for b in mins if work - 6 <= b < work - 1])
        full = mean([fine[m][b][0] for b in mins if work + 15 <= b < work + 30])
        if idle is None or full is None:
            continue
        t63 = next((b for b in mins if b >= work and fine[m][b][0] >= idle + 0.632 * (full - idle)), None)
        disks = [(r["t"], group(data, m, "disk", r["b"])) for r in rec if r["t"] >= t_step - 1800]
        disks = [(t, v) for t, v in disks if v is not None]
        resp[m] = {"work": work * 60, "idle": idle, "full": full, "t63_min": (t63 - work) if t63 else None}
        line = "    %-11s work began %s; CPU %.0f C to %.0f C, 63%% of it within %s" % (
            m, hm(work * 60), idle, full, ("%d min" % (t63 - work + 1)) if t63 is not None else "?")
        if len(disks) >= 6:
            ts, vs = [(t - disks[0][0]) / 3600 for t, _ in disks], [v for _, v in disks]
            bestd = None
            for tau in [x / 4 for x in range(1, 81)]:        # 0.25 h to 20 h
                e = [1 - math.exp(-t / tau) for t in ts]
                co = house.solve([[1.0, x] for x in e], vs)
                if co:
                    sse = sum((co[0] + co[1] * x - v) ** 2 for x, v in zip(e, vs))
                    if bestd is None or sse < bestd[0]:
                        bestd = (sse, tau, co)
            if bestd:
                _, tau, co = bestd
                span = ts[-1]
                resp[m].update(disk_from=vs[0], disk_now=vs[-1], disk_tau_h=tau, disk_to=co[0] + co[1], disk_span_h=span)
                line += "; disks %.1f C to %.1f C in %.1f h, heading for %.1f C with a lag of %.1f h%s" % (
                    vs[0], vs[-1], span, co[0] + co[1], tau, "" if span >= 1.5 * tau else " (the record is shorter than that lag: a guess)")
        print(line)

    # ---- the pictures
    t0, t1 = rec[0]["t"], rec[-1]["t"]
    marks = [(t_load, "saskatchewan takes work")] if t_load else []
    marks += [(t_step, "the step")]
    simw = simulate(rec, whole["tau_h"], whole["ua"], whole["p0"], whole["cs"], ref_s)
    W, x0, pw = 1180, 110, 840
    body = panel(x0, 130, pw, 150, t0, t1, [("the fleet", YELLOW, [(r["t"], r["P"]) for r in rec], False),
                                             ("saskatchewan", ORANGE, [(r["t"], r["Ps"]) for r in rec], False)],
                 "WATTS AT THE WALL (A MODEL OF EACH BOX)", " W", marks, fmt="%.0f")
    body += panel(x0, 350, pw, 220, t0, t1, [("probe " + probes[0][-6:-2], BLUE, [(r["t"], r["probes"][0]) for r in rec], False),
                                             ("probe " + probes[1][-6:-2], GREEN, [(r["t"], r["probes"][1]) for r in rec], False),
                                             ("the fit", INK, [(r["t"], v) for r, v in zip(rec, simw)], True)],
                  "THE ROOM, BY ITS TWO PROBES, AND THE BALANCE FITTED TO THEIR MEAN", "°", [(m[0], "") for m in marks])
    body += panel(x0, 640, pw, 110, t0, t1, [("SeaTac", VIOLET, [(r["t"], r["To"]) for r in rec], False)], "OUTSIDE", "°", [(m[0], "") for m in marks])
    picture(os.path.join(outdir, "step.png"), W, 800, "The room turns: a step of %+.0f W at %s" % (p_after - p_before, hm(t_step)),
            "%s to %s. Ten-minute means. The dashed line is C dT/dt = P + P0 - UA (T - To) run from the recorded watts and outside." % (stamp(t0), stamp(t1)), body)

    rel = lambda f: [(r["t"], f(r) - base) for r in rec if f(r) is not None] if (base := mean([f(r) for r in rec if t_step - 3600 <= r["t"] < t_step and f(r) is not None])) is not None else []
    cand = [("the room", INK, rel(lambda r: r["room"]))]
    cols = [BLUE, GREEN, ORANGE, YELLOW, VIOLET, RED]
    for row in sorted(rows, key=lambda r: -(r["night_r"] or -1)):
        if row["kind"] in ("disks", "NVMe") and row["machine"] not in stepped and row["night"] is not None and row["night_r"] is not None:
            kd = "disk" if row["kind"] == "disks" else "nvme"
            m = row["machine"]
            cand.append(("%s %s" % (m, row["kind"]), cols[(len(cand) - 1) % len(cols)], rel(lambda r, m=m, kd=kd: group(data, m, kd, r["b"]))))
    body = panel(x0, 130, pw, 420, t0, t1, [(n, c, p, False) for n, c, p in cand[:6]],
                 "DEGREES ABOVE OR BELOW EACH ONE'S OWN LEVEL IN THE HOUR BEFORE THE STEP", "°", marks, fmt="%+.1f")
    picture(os.path.join(outdir, "disks.png"), W, 620, "Disks beside the room",
            "Drives in machines that did not make the step, each as its change from the hour before it. A drive reads in whole degrees; these are means of several.", body)

    if stepped:
        ta = t_step - 3600
        ser, ser2 = [], []
        for i, m in enumerate(stepped[:3]):
            ser.append((m + " CPU", cols[i], [(b * 60, v[0]) for b, v in sorted(fine.get(m, {}).items()) if b * 60 >= ta], False))
            ser2.append((m + " disks", cols[i], [(r["t"], group(data, m, "disk", r["b"])) for r in rec if r["t"] >= ta and group(data, m, "disk", r["b"]) is not None], False))
        ser2.append(("the room", INK, [(r["t"], r["room"]) for r in rec if r["t"] >= ta], False))
        body = panel(x0, 130, pw, 230, ta, t1, ser, "THE CPUS OF THE MACHINES THAT MADE THE STEP, A MINUTE A POINT", "°", [(t_step, "the step")], fmt="%.0f")
        body += panel(x0, 430, pw, 230, ta, t1, [s for s in ser2 if s[2]], "THEIR DISKS, AND THE ROOM, TEN MINUTES A POINT", "°", [(t_step, "")], fmt="%.0f")
        picture(os.path.join(outdir, "stepped.png"), W, 710, "Three clocks: the CPU in a minute, the disks in hours, the room in a day",
                "The machines switched on and given work, from an hour before the step.", body)

    doc = {"made": time.time(), "from": t0, "to": t1, "step": {"t": t_step, "before_w": p_before, "after_w": p_after,
                                                               "made": [[m, d] for d, m in made if abs(d) >= 15]},
           "turn": {"slope_before": s_pre, "slope_after": s_post, "low_c": low["room"], "low_t": low["t"], "rose_t": rose["t"] if rose else None,
                    "c_from_slope": c_slope, "outside_moved": d_out},
           "fit": whole, "fit_plain": plain, "fit_before_step": early, "miss_after": miss, "profile": prof, "parts": rows, "stepped": resp, "room": room_d}
    with open(os.path.join(outdir, "response.json"), "w") as f:
        json.dump(doc, f, indent=1)
    print("\npictures and response.json: %s" % os.path.abspath(outdir))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
