#!/usr/bin/env python3
"""forward.py QUEUE OUTDIR -- the figures and numbers of *Always Forward* (docs/forward-lab-report.md): whether
the line's generations still gain, what each was worth once read again, why the bar lets through what it lets
through, and the gain that waited on a rule.

Everything is read from the queue and from git, nothing typed in. The generations, the proofs and main's moves
come from outgrowing.py's gather(), the same reading as *Outgrowing Yourself*. Every census the queue fetched
is read once more by treadcore's own scripts/ledger.py, into one table across every set of defaults (the
planner keeps only today's, and the fit's memory the last few): from it, each era's first reads give the
spread of the trials' true gains past their noise, the anchor trials give today's defaults against those
three generations back, the trials that passed their stages give their held-out reads, and the held-out
reads of recent days give each map's swing a seed. The trade rule's refusals are its own flags. The
simulation is the planner's own, tools/plans/difficulty-sim.py, given what is measured here.

Writes OUTDIR/data.json and one figure a file, fig-NAME.html, in outgrowing.py's style (inline SVG on the
page's colour variables; a mark's numbers in its <title>). The first figure carries the style sheet."""
import collections
import glob
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import outgrowing as og  # noqa: E402

SIM = os.path.join(os.path.dirname(HERE), "plans", "difficulty-sim.py")
# The report's four periods. Main last moved on 6 November; the anchors turned on the 10th.
PERIODS = (("28 Oct – 1 Nov", "20261028", "20261102"), ("2 – 5 Nov", "20261102", "20261106"),
           ("6 – 9 Nov", "20261106", "20261110"), ("10 – 13 Nov", "20261110", "20261114"))
TAUS = (0.10, 0.15, 0.20)


def jid_of(stamp):
    return stamp.split("-", 2)[-1] if stamp.count("-") >= 2 else ""


def kind_of(jid):
    m = re.match(r"[a-z]+", jid)
    return m.group(0) if m else ""


def pool(xs):
    """(d, se, seeds) of reads [(d, se, seeds)], inverse-variance."""
    w = [1 / s ** 2 for _, s, _ in xs]
    return sum(wi * d for wi, (d, _, _) in zip(w, xs)) / sum(w), 1 / math.sqrt(sum(w)), sum(n for _, _, n in xs)


def ledger_all(p):
    """Every census the queue fetched, one row each, on every set of defaults: the planner's own census_dirs()
    (a held-out read's pieces as the one census they make), one-map censuses left out as the planner leaves
    them, read by treadcore's ledger.py."""
    root = tempfile.mkdtemp(prefix="forward-")
    try:
        for d in p.census_dirs():
            if p.one_map(d):
                continue
            jid = d.rstrip("/").split(os.sep)[-2]
            os.symlink(d, os.path.join(root, "%s-%s" % (os.path.basename(d.rstrip("/")), jid)))
        out = subprocess.run([sys.executable, "-I", os.path.join(p.tc, "scripts", "ledger.py"), root], capture_output=True, text=True, check=True).stdout
    finally:
        shutil.rmtree(root, ignore_errors=True)
    lines = out.splitlines()
    head = lines[0].split("\t")
    rows = []
    for l in lines[1:]:
        r = dict(zip(head, l.split("\t")))
        try:
            r["dd"], r["ss"], r["n"] = float(r["d"]), float(r["se"]), int(r["seeds"])
        except (KeyError, ValueError):
            continue
        if r["ss"] <= 0:
            continue
        r["jid"] = jid_of(r["stamp"])
        r["kind"] = kind_of(r["jid"])
        r["c"] = r["commit"][:7]
        rows.append(r)
    return rows


def sim(mu, tau, sd, rate, queue=None):
    """The planner's simulation, each ease: [ease, minutes a promotion or None, true gain each, % truly worse,
    gain a day]; and the inputs it states."""
    cmd = [sys.executable, SIM] + ([queue] if queue else ["--mu", "%.3f" % mu, "--tau", "%.3f" % tau, "--sd", "%.2f" % sd, "--rate", "%d" % rate])
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    said = next((l for l in out.splitlines() if l.startswith("trials N(")), "")
    pts = []
    for l in out.splitlines():
        m = re.match(r"^\s*([\d.]+)\s+(never|(\d+) min)\s+([+-][\d.]+)\s+(\d+)%\s+([+-][\d.]+)", l)
        if m:
            pts.append([float(m.group(1)), int(m.group(3)) if m.group(3) else None, float(m.group(4)), int(m.group(5)), float(m.group(6))])
    return {"said": said, "points": pts}


def gather(q):
    D = og.gather(q)
    m, p = og.planner(q)
    st = json.load(open(os.path.join(q, "plan", "state.json")))
    first_seen = {k[:7]: v.get("first_seen", "") for k, v in st.get("commits", {}).items()}
    rows = ledger_all(p)
    by_trial = collections.defaultdict(list)
    first = {}
    for r in rows:
        by_trial[(r["c"], r["trial"], r["base"])].append(r)
        if r["kind"] == "w":
            first.setdefault(r["jid"], r)

    # Each set of defaults: its trials' first reads (55 seeds, against the defaults), and what their spread holds
    # past their own noise: tau^2 = var(d) - mean(se^2). And a seed's swing, se times the root of the seeds.
    eras = []
    fr = collections.defaultdict(list)
    for r in rows:
        if r["kind"] == "w" and r["base"].startswith("caps=baseline"):
            fr[r["c"]].append(r)
    for c, rs in fr.items():
        if len(rs) < 40:
            continue
        ds = [r["dd"] for r in rs]
        ms = statistics.mean(r["ss"] ** 2 for r in rs)
        eras.append({"commit": c, "first_seen": first_seen.get(c) or "", "t0": min(r["stamp"] for r in rs)[:13], "n": len(rs),
                     "mu": statistics.mean(ds), "sd": statistics.pstdev(ds), "noise": math.sqrt(ms),
                     "tau": math.sqrt(max(0.0, statistics.pvariance(ds) - ms)), "swing": statistics.median(r["ss"] * math.sqrt(r["n"]) for r in rs)})
    eras.sort(key=lambda e: e["t0"])

    # The anchors: the defaults three promotions back, read as a trial against today's. Their own flags say
    # which promotions they stand between.
    between = {}
    for f in glob.glob(os.path.join(q, "flags", "*-anchor.json")):
        try:
            mm = re.match(r"(w\d+) reads the defaults before (r\d+) against today's, after (r\d+)", json.load(open(f))["text"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if mm:
            between[mm.group(1)] = (mm.group(2), mm.group(3))
    # When each ran, by the keeper's clock: a census's stamp is its machine's, and some keep UTC.
    ended = {}
    for f in os.listdir(os.path.join(q, "done")):
        if f.endswith(".json") and "-w" in f:
            ended[f.split("-", 1)[1][:-5]] = f
    anchors = []
    for a in st.get("anchor_trials", []):
        f = first.get(a)
        if not f:
            continue
        rs = by_trial[(f["c"], f["trial"], f["base"])]
        d, se, n = pool([(r["dd"], r["ss"], r["n"]) for r in rs])
        b = between.get(a, ("?", "?"))
        try:
            at = json.load(open(os.path.join(q, "done", ended[a])))["ended"][:16]
        except (KeyError, OSError, ValueError):
            at = time.strftime("%Y-%m-%dT%H:%M", time.strptime(f["stamp"][:13], "%Y%m%d-%H%M"))
        anchors.append({"anchor": a, "before": b[0], "after": b[1], "on": f["c"], "at": at, "reads": len(rs), "seeds": n,
                        "d": d, "se": se, "z": d / se, "trial": f["trial"]})

    # The trials that passed their stages: what their stage reads said, and what their held-out reads said
    # on seeds no stage had seen. Only the defaults' own trials (base caps=baseline); a trial is its text on
    # its commit. Simple means across trials: a switch that changes nothing reads 0 with an error near 0,
    # and in an inverse-variance pool it would outweigh all the rest.
    tr = collections.defaultdict(lambda: {"seq": [], "held": [], "day": ""})
    for r in rows:
        if not r["base"].startswith("caps=baseline"):
            continue
        k = (r["c"], r["trial"])
        if r["kind"] in ("w", "e"):
            tr[k]["seq"].append((r["dd"], r["ss"], r["n"]))
            tr[k]["day"] = max(tr[k]["day"], r["stamp"][:8])
        elif r["kind"] == "h" and "-p" not in r["jid"]:
            tr[k]["held"].append((r["dd"], r["ss"], r["n"]))
    selected = []
    for name, a, b in PERIODS:
        xs = [(pool(v["seq"]), pool(v["held"])) for v in tr.values() if v["seq"] and v["held"] and a <= v["day"] < b]
        if not xs:
            continue
        sm = statistics.mean(x[0][0] for x in xs)
        hm = statistics.mean(x[1][0] for x in xs)
        mx = sm
        sxx = sum((x[0][0] - mx) ** 2 for x in xs)
        sxy = sum((x[0][0] - mx) * (x[1][0] - hm) for x in xs)
        selected.append({"period": name, "n": len(xs), "seq": sm, "held": hm, "held_se": statistics.pstdev([x[1][0] for x in xs]) / math.sqrt(len(xs)),
                         "kept": hm / sm if sm else None, "slope": sxy / sxx if sxx else None,
                         "seq_seeds": statistics.median(x[0][2] for x in xs), "held_seeds": statistics.median(x[1][2] for x in xs)})

    # A seed's swing on each map, from the held-out reads and proofs since main last moved (100 to 400 seeds,
    # each map about a thirteenth of them): the map's se, times the root of its seeds.
    since = D["moves"][-1]["at"].replace("-", "").replace("T", "-").replace(":", "")[:13] if D["moves"] else "20261106"
    var = collections.defaultdict(list)
    for r in rows:
        if r["kind"] not in ("h", "pv") or "-p" in r["jid"] or r["stamp"] < since[:8]:
            continue
        maps = [x.split(":") for x in r["maps"].split("|") if x.count(":") == 2]
        for name, d, se in maps:
            if float(se) > 0:
                var[name].append(float(se) ** 2 * r["n"] / len(maps))
    maps = sorted(({"map": k, "reads": len(v), "swing": math.sqrt(statistics.median(v))} for k, v in var.items() if len(v) >= 50), key=lambda x: -x["swing"])
    vs = [x["swing"] ** 2 for x in maps]
    weigh = {"equal": sum(vs) / len(vs), "inverse": len(vs) / sum(1 / v for v in vs)} if vs else {}
    if weigh:
        weigh["saved"] = 1 - weigh["inverse"] / weigh["equal"]

    # Seeds a day, by the job's kind, the last full days.
    days = collections.defaultdict(collections.Counter)
    for r in rows:
        days[r["stamp"][:8]][r["kind"]] += r["n"]
    today = time.strftime("%Y%m%d")
    full = sorted(d for d in days if d < today)[-7:]
    seeds_day = {d: dict(days[d]) for d in full}
    per_day = statistics.mean(sum(days[d].values()) for d in full) if full else 0
    search_day = statistics.mean(sum(days[d][k] for k in ("w", "e", "h")) for d in full) if full else 0

    # The trade rule's refusals, from its flags: when, the trial, its held-out gain and what it gave up.
    smooth_text = {r["jid"] for r in rows if r["kind"] == "w" and re.fullmatch(r"w_smooth=0\.525", r["trial"].replace(" ", ""))}
    refusals = []
    for f in sorted(glob.glob(os.path.join(q, "flags", "*-trade.json"))):
        try:
            j = json.load(open(f))
        except (OSError, ValueError):
            continue
        mm = re.match(r"grove/(w\d+) refused by the trade rule: held out ([-+][\d.]+), but it gives up (.+?) ([-+]?[\d.]+) \+/- ([\d.]+), ([\d.]+) times its floor", j.get("text", ""))
        if mm:
            t = int(os.path.basename(f).split("-")[0]) / 1000
            refusals.append({"trial": mm.group(1), "at": time.strftime("%Y-%m-%dT%H:%M", time.localtime(t)), "held": float(mm.group(2)),
                             "what": mm.group(3), "lost": float(mm.group(4)), "lost_se": float(mm.group(5)), "times": float(mm.group(6)),
                             "smooth": mm.group(1) in smooth_text})
    refusals.sort(key=lambda x: x["at"])
    smooth_seeds = collections.Counter()
    for r in rows:
        if re.fullmatch(r"w_smooth=0\.525", r["trial"].replace(" ", "")):
            smooth_seeds[r["kind"]] += r["n"]

    # The families' verdicts on the candidates that passed both held-out reads and were set aside.
    fam = json.load(open(os.path.join(q, "plan", "families.json"))) if os.path.exists(os.path.join(q, "plan", "families.json")) else {}
    under = []
    for k, v in fam.items():
        if isinstance(v, dict) and v.get("verdict") == "UNDER" and k.startswith("grove/w"):
            for x in v.get("families", []):
                if x.get("verdict") == "UNDER":
                    under.append({"trial": k.split("/")[1], "set": v.get("set"), "family": x["family"], "held": x.get("held"), "runs": x.get("runs"), "floor": x.get("floor")})

    # The simulation: the planner's own, with what is measured here, and with what it measures for itself.
    latest = max(eras, key=lambda e: e["n"] if e["t0"] >= since[:8] else 0) if eras else None
    mu = latest["mu"] if latest else -0.15
    sd = latest["swing"] if latest else 8.0
    rate = search_day / 24
    sims = {"%.2f" % t: sim(mu, t, sd, rate) for t in TAUS}
    sims["own"] = sim(0, 0, 0, 0, queue=q)

    # What the line truly gained a day since main last moved: its best-read head's proof, over the days between.
    measured = None
    if D["moves"]:
        mv = D["moves"][-1]["at"]
        heads = [x for x in D["pairs"] if x["t0"] >= mv]
        if heads:
            h = max(heads, key=lambda x: x["seeds"])
            days = (og.ep(h["t1"]) - og.ep(mv)) / 86400
            measured = {"head": h["head"], "lead": h["lead"], "se": h["se"], "seeds": h["seeds"], "days": days, "a_day": h["lead"] / days, "se_day": h["se"] / days,
                        "gens": h["gens"], "claimed": h["claimed"]}
    search = json.load(open(os.path.join(q, "plan", "search.json"))) if os.path.exists(os.path.join(q, "plan", "search.json")) else {}
    return {"measured": measured, "now": D["now"], "gens": D["gens"], "moves": D["moves"], "pairs": D["pairs"], "line": D["line"], "proof_last": D["proof_last"],
            "eras": eras, "anchors": anchors, "selected": selected, "maps": maps, "weigh": weigh, "seeds_day": seeds_day, "per_day": per_day,
            "search_day": search_day, "refusals": refusals, "smooth_seeds": dict(smooth_seeds), "under": under, "sims": sims,
            "sim_in": {"mu": mu, "sd": sd, "rate": rate, "era": latest["commit"] if latest else None}, "search": search,
            "hold": json.load(open(os.path.join(q, "hold.json"))) if os.path.exists(os.path.join(q, "hold.json")) else {}}


# ---- the drawing -------------------------------------------------------------------------------

grid = lambda x1, y1, x2, y2, cls="grid": '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" class="%s"/>' % (x1, y1, x2, y2, cls)


def yaxis(x0, x1, sy, lo, hi, step, fmt="%+g"):
    b, v = "", lo
    while v <= hi + 1e-9:
        b += grid(x0, sy(v), x1, sy(v), "axis" if abs(v) < 1e-9 else "grid") + og.text(x0 - 8, sy(v) + 4, "0" if abs(v) < 1e-9 else fmt % v, "dim num", "end")
        v += step
    return b


def ylabel(x, y0, y1, words):
    return '<text transform="translate(%d,%d) rotate(-90)" text-anchor="middle">%s</text>' % (x, (y0 + y1) // 2, og.esc(words))


def fig_anchors(F):
    """Fig. 1: every anchor read, the defaults three generations back against today's, ± 1 se."""
    W, H = 960, 430
    x0, x1, y0, y1 = 80, 930, 370, 30
    A = F["anchors"]
    ts = [og.ep(a["at"] + ":00") for a in A]
    t0, t1 = min(ts) - 6 * 3600, max(ts) + 6 * 3600
    lo, hi = -4.0, 1.5
    sy = lambda v: y0 - (v - lo) / (hi - lo) * (y0 - y1)
    b = yaxis(x0, x1, sy, lo, hi, 1.0)
    tb, sx = og.time_axis(x0, x1, t0, t1, y1, y0)
    b += tb
    b += og.text(x1 - 4, sy(1.2), "the defaults three back read better", "dim", "end")
    b += og.text(x1 - 4, sy(-3.7), "today's defaults read better", "dim", "end")
    mv = F["moves"][-1]["at"] if F["moves"] else None
    if mv:
        x = sx(og.ep(mv))
        b += grid(x, y1, x, y0, "thr") + og.text(x + 6, y1 + 14, "main's last move, %s" % time.strftime("%-d %b %H:%M", time.localtime(og.ep(mv))), "num")
    for a, t in zip(A, ts):
        x = sx(t)
        b += grid(x, sy(a["d"] - a["se"]), x, sy(a["d"] + a["se"]), "l2")
        strong = abs(a["z"]) >= 2
        el = '<circle cx="%.1f" cy="%.1f" r="5" class="%s"%s/>' % (x, sy(a["d"]), "f2" if strong else "hollow", "" if strong else ' style="stroke:var(--s2)"')
        b += og.titled(el, "%s, %s: the defaults before %s read against today's (after %s): %+.2f ± %.2f a seat over %d seeds, z %.1f" % (
            a["anchor"], a["at"].replace("T", " "), a["before"], a["after"], a["d"], a["se"], a["seeds"], a["z"]))
    b += ylabel(20, y0, y1, "the defaults three back, less today's (a seat, ± 1 se)")
    b += '<circle cx="96" cy="%d" r="5" class="f2"/>' % (H - 22) + og.text(108, H - 18, "two errors or more from even")
    b += '<circle cx="330" cy="%d" r="5" class="hollow" style="stroke:var(--s2)"/>' % (H - 22) + og.text(342, H - 18, "within two errors")
    return og.STYLE + og.svg(W, H, b, "Fig. 1: every anchor read, the defaults three generations back against today's")


def fig_line(F):
    """Fig. 2: the line since main's last move: what its generations claimed, summed, and what the proof read."""
    W, H = 960, 430
    x0, x1, y0, y1 = 80, 800, 370, 30
    mv = F["moves"][-1]["at"]
    P = [p for p in F["pairs"] if p["t0"] >= mv]
    t0, t1 = og.ep(mv) - 3 * 3600, max(og.ep(p["t1"]) for p in P) + 6 * 3600
    lo, hi = -1.0, 7.0
    sy = lambda v: y0 - (v - lo) / (hi - lo) * (y0 - y1)
    b = yaxis(x0, x1, sy, lo, hi, 1.0)
    tb, sx = og.time_axis(x0, x1, t0, t1, y1, y0)
    b += tb
    # The claim, a step at each generation's commit.
    gens = sorted((g for g in F["gens"] if g.get("committed") and g["committed"] >= mv and g.get("held")), key=lambda g: g["committed"])
    pts, c = [(sx(og.ep(mv)), sy(0))], 0.0
    for g in gens:
        x = sx(og.ep(g["committed"]))
        pts.append((x, sy(c)))
        c += g["held"][0]
        pts.append((x, sy(c)))
        b += og.titled('<circle cx="%.1f" cy="%.1f" r="4" class="f2"/>' % (x, sy(c)), "%s, %s (%s): held out %+.2f; the line's claim now %+.2f" % (
            g["run"], g["committed"][:16], g["trial"], g["held"][0], c))
    pts.append((sx(t1), sy(c)))
    b += '<polyline points="%s" class="l2"/>' % " ".join("%.1f,%.1f" % p for p in pts)
    b += og.text(sx(t1) + 6, sy(c) + 4, "claimed %+.2f" % c, "num")
    for p in P:
        x = sx((og.ep(p["t0"]) + og.ep(p["t1"])) / 2)
        b += grid(x, sy(p["lead"] - p["se"]), x, sy(p["lead"] + p["se"]), "l3")
        b += og.titled('<circle cx="%.1f" cy="%.1f" r="5" class="f3"/>' % (x, sy(p["lead"])), "proof of %s, %s to %s: the line over main %+.2f ± %.2f over %d seeds (z %.1f); generations on it %s" % (
            p["head"], p["t0"][5:16], p["t1"][5:16], p["lead"], p["se"], p["seeds"], p["z"], ", ".join(p["gens"])))
    last = P[-1]
    b += og.text(sx(t1) + 6, sy(last["lead"]) + 4, "proven %+.2f" % last["lead"], "num")
    b += ylabel(20, y0, y1, "a seat over main")
    b += '<line x1="90" y1="%d" x2="120" y2="%d" class="l2"/>' % (H - 22, H - 22) + og.text(128, H - 18, "claimed: the line's generations' held-out reads, summed")
    b += '<circle cx="560" cy="%d" r="5" class="f3"/>' % (H - 22) + og.text(572, H - 18, "proven: the proof's read of the line over main (± 1 se)")
    return og.svg(W, H, b, "Fig. 2: the line since main's last move, claimed and proven")


def fig_kept(F):
    """Fig. 3: the trials that passed their stages: their stage reads and their held-out reads, by period."""
    W, H = 960, 380
    x0, x1, y0, y1 = 80, 930, 300, 30
    S = F["selected"]
    lo, hi = 0.0, 0.8
    sy = lambda v: y0 - (v - lo) / (hi - lo) * (y0 - y1)
    b = yaxis(x0, x1, sy, lo, hi, 0.2, "%+.1f")
    gw = (x1 - x0) / len(S)
    bw = 46
    for i, s in enumerate(S):
        cx = x0 + gw * (i + 0.5)
        for j, (v, cls, words) in enumerate(((s["seq"], "bar2", "their stage reads"), (s["held"], "bar3", "their held-out reads"))):
            x = cx - bw - 2 + j * (bw + 4)
            el = '<rect x="%.1f" y="%.1f" width="%d" height="%.1f" rx="3" class="%s"/>' % (x, sy(v), bw, max(1.0, sy(0) - sy(v)), cls)
            b += og.titled(el, "%s: %d trials; %s %+.2f a seat (median %d seeds)" % (s["period"], s["n"], words, v, s["seq_seeds"] if j == 0 else s["held_seeds"]))
            b += og.text(x + bw / 2, sy(v) - 6, "%+.2f" % v, "num", "middle")
        b += og.text(cx, y0 + 18, s["period"], "", "middle")
        b += og.text(cx, y0 + 34, "%d trials; kept %.2f" % (s["n"], s["kept"]), "dim num", "middle")
    b += ylabel(20, y0, y1, "mean gain a seat")
    b += '<rect x="90" y="%d" width="14" height="12" rx="2" class="bar2"/>' % (H - 30) + og.text(110, H - 20, "the reads that passed them through their stages")
    b += '<rect x="470" y="%d" width="14" height="12" rx="2" class="bar3"/>' % (H - 30) + og.text(490, H - 20, "their held-out reads, on seeds no stage saw")
    return og.svg(W, H, b, "Fig. 3: what the trials that passed their stages read, and what they read again")


def fig_maps(F):
    """Fig. 4: a seed's swing on each map."""
    M = F["maps"]
    W, rowh = 960, 24
    H = 60 + rowh * len(M)
    x0, x1 = 170, 860
    hi = math.ceil(max(m["swing"] for m in M) / 2) * 2
    sx = lambda v: x0 + v / hi * (x1 - x0)
    b = ""
    for v in range(0, hi + 1, 2):
        b += grid(sx(v), 20, sx(v), 26 + rowh * len(M)) + og.text(sx(v), 40 + rowh * len(M), str(v), "dim num", "middle")
    for i, m in enumerate(M):
        y = 26 + i * rowh
        b += og.text(x0 - 8, y + 15, m["map"], "", "end")
        el = '<rect x="%d" y="%d" width="%.1f" height="%d" rx="3" class="bar2"/>' % (x0, y + 4, sx(m["swing"]) - x0, rowh - 8)
        b += og.titled(el, "%s: a seed swings %.2f a seat (median over %d reads)" % (m["map"], m["swing"], m["reads"]))
        b += og.text(sx(m["swing"]) + 6, y + 15, "%.1f" % m["swing"], "num")
    b += og.text((x0 + x1) / 2, 56 + rowh * len(M), "a seed's swing, a seat (the map's error times the root of its seeds)", "", "middle")
    return og.svg(W, H + 10, b, "Fig. 4: a seed's swing on each map")


def fig_sim(F):
    """Fig. 5: the gain a day the planner's simulation promises at today's ease, model by model, against the gain
    the proof measured since main last moved. Every normal model rises as the bar falls; the bars here are
    at 1.5, where the ratchet has stood."""
    W = 960
    S = F["sims"]
    rows = []
    own = next((p for p in S["own"]["points"] if abs(p[0] - 1.5) < 1e-6), None)
    if own:
        mm = re.search(r"N\([^)]*\)", S["own"]["said"])
        rows.append(("the simulator's own reading, %s" % (mm.group(0) if mm else "its own"), own, "bar2"))
    for t in sorted(TAUS, reverse=True):
        p = next((p for p in S["%.2f" % t]["points"] if abs(p[0] - 1.5) < 1e-6), None)
        if p:
            rows.append(("spread %.2f, measured mean and swing" % t, p, "bar2"))
    m = F["measured"]
    rowh, x0, x1 = 40, 330, 900
    H = 70 + rowh * (len(rows) + 1)
    hi = math.ceil(max([r[1][4] for r in rows] + [1]))
    lo = -1.0
    sx = lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)
    b = ""
    for v in range(int(lo), hi + 1):
        b += grid(sx(v), 16, sx(v), 22 + rowh * (len(rows) + 1), "axis" if v == 0 else "grid") + og.text(sx(v), 40 + rowh * (len(rows) + 1), "%+d" % v if v else "0", "dim num", "middle")
    for i, (words, p, cls) in enumerate(rows):
        y = 22 + i * rowh
        b += og.text(x0 - 10, y + 22, words, "", "end")
        el = '<rect x="%.1f" y="%d" width="%.1f" height="%d" rx="3" class="%s"/>' % (sx(0), y + 8, max(1.0, sx(p[4]) - sx(0)), rowh - 16, cls)
        b += og.titled(el, "%s at ease 1.5: a promotion every %s, each truly %+.2f, %d%% truly worse: %+.2f a seat a day" % (words, "%d min" % p[1] if p[1] else "never", p[2], p[3], p[4]))
        b += og.text(sx(p[4]) + 6, y + 23, "%+.1f" % p[4], "num")
    y = 22 + len(rows) * rowh
    b += og.text(x0 - 10, y + 22, "measured: the proof, since main's last move", "ttl", "end")
    b += grid(sx(m["a_day"] - m["se_day"]), y + 20, sx(m["a_day"] + m["se_day"]), y + 20, "l3")
    b += og.titled('<circle cx="%.1f" cy="%d" r="7" class="f3"/>' % (sx(m["a_day"]), y + 20), "the line %s over main %+.2f ± %.2f over %d seeds, %.1f days after main's last move: %+.3f ± %.3f a seat a day" % (
        m["head"], m["lead"], m["se"], m["seeds"], m["days"], m["a_day"], m["se_day"]))
    b += og.text(sx(m["a_day"]) + 14, y + 25, "%+.3f ± %.3f" % (m["a_day"], m["se_day"]), "num")
    b += og.text((x0 + x1) / 2, 58 + rowh * (len(rows) + 1), "true gain a day at an ease of 1.5, a seat", "", "middle")
    return og.svg(W, H, b, "Fig. 5: the gain a day each model promises at today's ease, and the gain measured")


def fig_smooth(F):
    """Fig. 6: w_smooth = 0.525, each time the trade rule refused it: its held-out gain, and the fights it gave up."""
    R = [r for r in F["refusals"] if r["smooth"]]
    W, H = 960, 400
    x0, x1, y0, y1 = 80, 860, 330, 30
    ts = [og.ep(r["at"] + ":00") for r in R]
    t0, t1 = min(ts) - 8 * 3600, max(ts) + 8 * 3600
    lo, hi = -2.0, 5.0
    sy = lambda v: y0 - (v - lo) / (hi - lo) * (y0 - y1)
    b = yaxis(x0, x1, sy, lo, hi, 1.0)
    tb, sx = og.time_axis(x0, x1, t0, t1, y1, y0)
    b += tb
    for r, t in zip(R, ts):
        x = sx(t)
        b += og.titled('<circle cx="%.1f" cy="%.1f" r="6" class="f3"/>' % (x, sy(r["held"])), "%s, %s: held out %+.2f a seat on the score" % (r["trial"], r["at"], r["held"]))
        b += grid(x, sy(r["lost"] - r["lost_se"]), x, sy(r["lost"] + r["lost_se"]), "l2")
        b += og.titled('<circle cx="%.1f" cy="%.1f" r="6" class="f2"/>' % (x, sy(r["lost"])), "%s, %s: %s %+.2f ± %.2f, %.1f times its floor (the rule allows 2.5)" % (
            r["trial"], r["at"], r["what"], r["lost"], r["lost_se"], r["times"]))
    b += grid(x0, sy(-0.25), x1, sy(-0.25), "thr") + og.text(x1 - 4, sy(-0.25) + 52, "the dashed line: the trade rule's limit, 2.5 times the 0.10 floor", "dim", "end")
    b += ylabel(20, y0, y1, "a seat")
    b += '<circle cx="96" cy="%d" r="6" class="f3"/>' % (H - 22) + og.text(108, H - 18, "the score, held out")
    b += '<circle cx="300" cy="%d" r="6" class="f2"/>' % (H - 22) + og.text(312, H - 18, "kills less deaths given up (± 1 se)")
    return og.svg(W, H, b, "Fig. 6: w_smooth 0.525, refused by the trade rule each time it was read")


def main(a):
    """QUEUE OUTDIR reads the queue; --redraw OUTDIR draws the figures again from OUTDIR/data.json."""
    if a[0] == "--redraw":
        out = os.path.abspath(a[1])
        F = json.load(open(os.path.join(out, "data.json")))
    else:
        q, out = os.path.abspath(a[0]), os.path.abspath(a[1])
        os.makedirs(out, exist_ok=True)
        F = gather(q)
        json.dump(F, open(os.path.join(out, "data.json"), "w"), indent=1, default=str)
    figs = {"anchors": fig_anchors(F), "line": fig_line(F), "kept": fig_kept(F), "maps": fig_maps(F), "sim": fig_sim(F), "smooth": fig_smooth(F)}
    for k, v in figs.items():
        with open(os.path.join(out, "fig-%s.html" % k), "w") as f:
            f.write(v + "\n")
    print("wrote %s: %d figures; %d eras, %d anchors, %d trade refusals (%d of w_smooth), %d maps" % (
        out, len(figs), len(F["eras"]), len(F["anchors"]), len(F["refusals"]), len([r for r in F["refusals"] if r["smooth"]]), len(F["maps"])))


if __name__ == "__main__":
    main(sys.argv[1:])
