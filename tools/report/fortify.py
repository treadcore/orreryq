#!/usr/bin/env python3
"""fortify.py QUEUE RUN...: what a census's gain is made of, seed by seed, from its logs: docs/fortify-lab-report.md's
tables. For each seed, trial team less the others, then mean and error over seeds, as pool.sh does for the score itself."""
import collections, glob, math, os, re, statistics as st, sys

SEATS = 5.0
Q = os.path.abspath(sys.argv[1])


def seeds_of(run):
    """{seed: {metric: [trial values], ...}, ...}: a match's team lines, per seed; also the map."""
    trial, base, mapn = collections.defaultdict(lambda: collections.defaultdict(list)), collections.defaultdict(lambda: collections.defaultdict(list)), {}
    rung, post = collections.Counter(), collections.defaultdict(int)
    for f in glob.glob(os.path.join(Q, "results", run, "**", "g-*.log"), recursive=True):
        seed, kept = None, {}
        for l in open(f, errors="replace"):
            m = re.match(r"seed (\S+) on (\S+): trial team (\d)", l)
            if m:
                seed = m.group(1)
                mapn[seed] = m.group(2)
                continue
            if not seed:
                continue
            m = re.match(r"\s+rewards of team (\d)( \(trial\))?: (.*)", l)
            if m:
                kept = dict((k.strip(), float(v)) for k, v in re.findall(r"([a-z ]+) (\d+)", m.group(3)))
                continue
            m = re.match(r"\s+team (\d)( \(trial\))?: score ([-\d.]+), (.*)", l)
            if m:
                row = dict(kept)
                kept = {}
                row["score"] = float(m.group(3))
                b = m.group(4)
                for k, v in re.findall(r"(kills|deaths|revives|built|road|bridge|held|rewards) ([-\d.]+)", b):
                    row[k] = float(v)
                for k, v in re.findall(r"(direct hits|pillbox damage|defends) ([-\d.]+)", b):
                    row[k] = float(v)
                g = re.search(r"pillboxes taken (\d+) neutral (\d+) hostile", b)
                if g:
                    row["taken"] = float(g.group(1)) + float(g.group(2))
                (trial if m.group(2) else base)[seed]["rows"].append(row)
                continue
            if "seat-seconds a rung" in l:
                for k, v in re.findall(r"([a-z ]+) (\d+)(?:,|$)", l.split(":", 1)[1]):
                    rung[k.strip()] += int(v)
            m = re.search(r"postures \[(\d+), (\d+), (\d+), (\d+), (\d+)\]", l)
            if m:
                for name, v in zip(("economy", "fortify", "connect", "expand", "defend"), m.groups()):
                    post[name] += int(v)
    return trial, base, mapn, rung, post


def stat(trial, base, fn, only=None):
    d = []
    for s in trial:
        if only and only != "*" and s not in only:
            continue
        a = [fn(r) for r in trial[s]["rows"]]
        b = [fn(r) for r in base[s]["rows"]]
        if a and b:
            d.append(st.mean(a) - st.mean(b))
    if len(d) < 2:
        return (float("nan"), 0.0, len(d))
    return (st.mean(d), st.stdev(d) / math.sqrt(len(d)), len(d))


METRICS = [
    ("The score", lambda r: r.get("score", 0)),
    ("The score without going forward", lambda r: r.get("score", 0) - (0.25 * r.get("advanced", 0) + r.get("towed", 0) + 3 * r.get("stages", 0)) / SEATS),
    ("All the rewards", lambda r: r.get("rewards", 0)),
    ("Kills less deaths, a seat", lambda r: (r.get("kills", 0) - r.get("deaths", 0)) / SEATS),
    ("Kills, team", lambda r: r.get("kills", 0)),
    ("Deaths, team", lambda r: r.get("deaths", 0)),
    ("Direct hits, team", lambda r: r.get("direct hits", 0)),
    ("Pillbox damage, team", lambda r: r.get("pillbox damage", 0)),
    ("Pillboxes taken, team", lambda r: r.get("taken", 0)),
    ("Ground held", lambda r: r.get("held", 0)),
    ("Built, team", lambda r: r.get("built", 0)),
    ("Road, team", lambda r: r.get("road", 0)),
    ("Tiles advanced, team", lambda r: r.get("advanced", 0)),
    ("Advance stages, team", lambda r: r.get("stages", 0)),
    ("Rotations, team", lambda r: r.get("rotations", 0)),
    ("Castle-seconds, team", lambda r: r.get("castle", 0)),
]


def table(run):
    trial, base, mapn, rung, post = seeds_of(run)
    out = ["| Measure | Trial less the rest | z |", "| --- | --- | --- |"]
    for name, fn in METRICS:
        d, se, n = stat(trial, base, fn)
        if d != d or (name.startswith(("Tiles", "Advance", "Rotations", "Castle", "The score without")) and all(abs(r.get("advanced", 0)) == 0 for s in trial for r in trial[s]["rows"])):
            continue
        out.append("| %s | %+.2f +/- %.2f | %+.1f |" % (name, d, se, d / se if se else 0))
    return "\n".join(out), len(trial), rung, post, trial, base, mapn


for run in sys.argv[2:]:
    t, n, rung, post, trial, base, mapn = table(run)
    print("###", run, n, "seeds")
    print(t)
    tot = sum(rung.values()) or 1
    print("rungs", {k: round(100 * v / tot) for k, v in rung.items()})
    tp = sum(post.values()) or 1
    print("postures", {k: round(100 * v / tp) for k, v in post.items()})
    maps = collections.defaultdict(set)
    for s, m in mapn.items():
        maps[m].add(s)
    print("score without going forward, by map:", {m: "%+.1f" % stat(trial, base, METRICS[1][1], ss)[0] for m, ss in sorted(maps.items())})
