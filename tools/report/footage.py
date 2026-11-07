#!/usr/bin/env python3
"""footage.py QUEUE make [--home HOME] [--only ID] [--runs N]  -- every new GPU generation, filmed at its tests
   footage.py QUEUE reel [--home HOME]                           -- the filmed generations, one after another
   footage.py QUEUE resheet [--home HOME]                        -- the sheets made again from their films, then the reel

Paul, 6 November: "we want to see just about every generation have a set of tests be monitored, then we take
those recordings and collect them to show generations of footage. We dont need to show old generations, just
the newly trained ones."

MAKE. For each milestone the GPU's home made itself (a carried one, from the home before, is old footage and
is skipped) that has no footage yet: on a GPU island, as the montage traces, crucible is built with the home's
flags and plays TESTS -- the routes N1 and N3, the mazes M0 to M3 with their pillboxes, the walled base B1,
the takeovers T1 and T2 -- RUNS runs each (`--trace-scen`). The traces come back; each is a film
(report/maze_film.py: the whole arena, the best run followed, the others its ghosts), every film sped to the
same length; the nine play at once on one sheet, three by three, under a card that names the generation and
its passes. Written to QUEUE/archive/footage/HOME/ID/ (the films, sheet.mp4, result.json) and the index.

REEL. Every filmed generation's sheet in order, oldest first: QUEUE/archive/footage/HOME/reel.mp4 and
orrery's output/treadcore-footage.mp4. The planner asks `make` then `reel` when the home makes a generation
(`footage_watch`).
"""
import importlib.util
import json
import os
import shlex
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = ["n1-the-s-maze-reach", "n3-the-at-maze-reach", "m0-one-bar", "m1-the-s-maze", "m2-the-5-maze",
         "m3-the-at-maze", "b1-breach-the-walled-base", "t1-take-a-pillbox", "t2-take-the-base"]
SHORT = {"n1": "N1 the S, the route", "n3": "N3 the @, the route", "m0": "M0 one bar", "m1": "M1 the S maze",
         "m2": "M2 the 5 maze", "m3": "M3 the @ maze", "b1": "B1 the walled base", "t1": "T1 take a pillbox", "t2": "T2 take the base"}
FRAMES = 180          # each test's film: twelve seconds at 15 frames a second, however long the run
TILE = (426, 240)     # a test on the sheet; three by three is 1278 x 720


def load_mod(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def gpu_home(q):
    """The GPU's home now, as the planner names it (crucible.nav, .forest, .world), from plan.json."""
    c = (json.load(open(os.path.join(q, "plan.json"))).get("crucible") or {})
    home = "crucible" + ("-world" if c.get("world") else "") + ("-hybrid" if c.get("hybrid") else "")
    home += "-forest" if c.get("world") and c.get("forest") else ""
    home += "-nav" if c.get("world") and c.get("forest") and c.get("nav") else ""
    return home, c


def new_generations(q, home):
    """The home's own milestones, oldest first: (id, path, made). The planner's ladder (plan/state.json,
    crucible_ladder:HOME) marks the ones copied in from the home before as carried; those are left out."""
    st = json.load(open(os.path.join(q, "plan", "state.json")))
    key = "crucible_ladder" if home in ("crucible", "crucible-hybrid") else "crucible_ladder:" + home
    out = []
    for m in (st.get(key) or {}).get("milestones", []):
        path = os.path.join(q, home, "milestones", m["id"] + ".bin")
        if m.get("carried") or not m.get("made") or not os.path.exists(path):
            continue
        out.append((m["id"], path, m["made"]))
    return out


def trace_on_island(q, mt, c, mid, path, runs, work):
    """The tests' traces for one milestone, run on whichever GPU island answers: {test: local trace path}."""
    home = "fleet/q-%s/footage" % os.path.basename(q.rstrip("/"))
    # The home's own build, from its name: a forest home's nets are filmed as they were trained, not under the
    # maze build's errand.
    hn = os.path.basename(path.split("/milestones/")[0]) if "/milestones/" in path else ""
    flags = ("HYBRID=1 " if "-hybrid" in hn or c.get("hybrid") else "") + ("WORLD=1 " if "-world" in hn or c.get("world") else "")
    flags += "FOREST=1 " if "-forest" in hn else ""
    flags += "NAV=1 " if hn.endswith("-nav") else ""
    flags += "H=%d" % int(c.get("h") or 48)
    rules = ((mt.load(os.path.join(q, "plan", "state.json"), {}) or {}).get("crucible_rules") or {}).get("flags") or ""
    flags = (flags.strip() + " " + rules).strip()
    gdir = os.path.join(mt.CRUCIBLE, "gauntlet")
    for name, target in mt.gpu_hosts(q):
        r = mt.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", target, "mkdir -p ~/%s/src ~/%s/gauntlet && rm -f ~/%s/t-*.bin" % (home, home, home)], 60)
        if r.returncode != 0:
            continue
        ok = all(mt.run(cmd, 300).returncode == 0 for cmd in (
            ["scp", "-q", "-o", "BatchMode=yes", os.path.join(mt.CRUCIBLE, "src", "crucible.cu"), "%s:%s/src/" % (target, home)],
            ["scp", "-q", "-o", "BatchMode=yes", os.path.join(mt.CRUCIBLE, "Makefile"), "%s:%s/" % (target, home)],
            ["scp", "-q", "-o", "BatchMode=yes"] + [os.path.join(gdir, t + ".toml") for t in TESTS] + ["%s:%s/gauntlet/" % (target, home)],
            ["scp", "-q", "-o", "BatchMode=yes", path, "%s:%s/m.bin" % (target, home)]))
        if not ok:
            continue
        loop = "; ".join("./crucible --trace t-%s.bin --trace-scen gauntlet/%s.toml --champions m.bin --trace-duels %d | grep '^# trace'" % (t[:2], t, runs) for t in TESTS)
        cmd = ("set -e; cd ~/%(h)s; F='%(f)s'; [ \"$(cat .flags 2>/dev/null)\" = \"$F\" ] || { rm -f crucible; echo \"$F\" > .flags; }; "
               "make -s %(f)s NVCC=${NVCC:-/usr/local/cuda/bin/nvcc} >/dev/null 2>&1 || make %(f)s NVCC=${NVCC:-/usr/local/cuda/bin/nvcc}; %(l)s") % {"h": home, "f": flags, "l": loop}
        r = mt.run(["ssh", "-o", "BatchMode=yes", target, "sh -c %s" % shlex.quote(cmd)], 3600)
        if r.returncode != 0:
            print("footage: the trace on %s failed: %s" % (name, (r.stderr or r.stdout).strip()[-300:]))
            continue
        got = {}
        for t in TESTS:
            out = os.path.join(work, "t-%s.bin" % t[:2])
            if mt.run(["scp", "-q", "-o", "BatchMode=yes", "%s:%s/t-%s.bin" % (target, home, t[:2]), out], 600).returncode == 0:
                got[t[:2]] = out
        mt.run(["ssh", "-o", "BatchMode=yes", target, "rm -f ~/%s/t-*.bin ~/%s/m.bin" % (home, home)], 60)
        return got, name
    raise RuntimeError("no GPU island could trace the footage")


def sheet(mt, films, results, out, title):
    """The nine films three by three, each padded to the longest, a card over the top."""
    order = [t[:2] for t in TESTS]
    ins, parts = [], []
    for i, k in enumerate(order):
        ins += ["-i", films[k]]
        parts.append("[%d:v]scale=%d:%d,tpad=stop_mode=clone:stop_duration=15[v%d]" % (i, TILE[0], TILE[1], i))
    layout = "|".join("%d_%d" % ((i % 3) * TILE[0], (i // 3) * TILE[1]) for i in range(len(order)))
    card = out[:-4] + "-card.png"
    mt.label_png(card, title, 18, font=mt.FONT_B, pad=10)
    ins += ["-loop", "1", "-i", card]
    # The card in a strip of its own above the nine, so no test's caption is under it.
    fc = ";".join(parts) + ";" + "".join("[v%d]" % i for i in range(len(order))) + (
        "xstack=inputs=%d:layout=%s[g];[g]pad=iw:ih+48:0:48:color=0x0b0f0c[gp];[gp][%d:v]overlay=(W-w)/2:2:shortest=1[o]" % (len(order), layout, len(order)))
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + ins + ["-filter_complex", fc, "-map", "[o]", "-t", "%.1f" % (FRAMES / 15.0 + 1.0),
                        "-c:v", "libx264", "-preset", "slow", "-crf", "30", "-pix_fmt", "yuv420p", "-r", "15", "-g", "150", "-movflags", "+faststart", out],
                       capture_output=True, text=True)
    os.remove(card)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg sheet: %s" % r.stderr[-300:])


def make(q, home=None, only=None, runs=8):
    mt = load_mod("montage", os.path.join(os.path.dirname(HERE), "montage.py"))
    mf = load_mod("maze_film", os.path.join(HERE, "maze_film.py"))
    h, c = gpu_home(q)
    home = home or h
    base = os.path.join(q, "archive", "footage", home)
    os.makedirs(base, exist_ok=True)
    idx_path = os.path.join(base, "index.json")
    idx = json.load(open(idx_path)) if os.path.exists(idx_path) else {"home": home, "generations": []}
    done = {g["id"] for g in idx["generations"]}
    gens = [g for g in new_generations(q, home) if (only is None or g[0] == only) and g[0] not in done]
    if only and not gens and os.path.exists(only):
        gens = [(os.path.basename(only)[:-4], os.path.abspath(only), time.strftime("%Y-%m-%dT%H:%M"))]
    for mid, path, made in gens:
        work = os.path.join(base, mid)
        os.makedirs(work, exist_ok=True)
        traces, host = trace_on_island(q, mt, c, mid, path, runs, work)
        films, results = {}, {}
        for k, tp in traces.items():
            tr = mt.Trace(tp)
            steps = max(tr.champs[0]["lasted"])
            every = max(1, -(-steps // FRAMES))
            r = mf.film(tp, os.path.join(work, "%s.mp4" % k), every, SHORT.get(k, k) + " · " + mid, stills=False, m=mt)
            films[k], results[k] = os.path.join(work, "%s.mp4" % k), {"passed": r["passed"], "runs": r["runs"]}
            os.remove(tp)
        passed = sum(v["passed"] for v in results.values())
        runs_all = sum(v["runs"] for v in results.values())
        title = "%s  ·  made %s  ·  %d of %d test runs passed" % (mid, made.replace("T", " ")[:16], passed, runs_all)
        sheet(mt, films, results, os.path.join(work, "sheet.mp4"), title)
        res = {"id": mid, "made": made, "host": host, "results": results, "passed": passed, "runs": runs_all, "filmed": time.strftime("%Y-%m-%dT%H:%M:%S")}
        json.dump(res, open(os.path.join(work, "result.json"), "w"), indent=1)
        idx["generations"].append(res)
        json.dump(idx, open(idx_path, "w"), indent=1)
        print("footage %s: %d of %d test runs passed, on %s" % (mid, passed, runs_all, host))
    return idx


def reel(q, home=None):
    mt = load_mod("montage", os.path.join(os.path.dirname(HERE), "montage.py"))
    home = home or gpu_home(q)[0]
    base = os.path.join(q, "archive", "footage", home)
    idx = json.load(open(os.path.join(base, "index.json")))
    sheets = [os.path.join(base, g["id"], "sheet.mp4") for g in idx["generations"] if os.path.exists(os.path.join(base, g["id"], "sheet.mp4"))]
    if not sheets:
        raise SystemExit("no footage yet")
    lst = os.path.join(base, "reel.txt")
    open(lst, "w").write("".join("file '%s'\n" % s for s in sheets))
    out = os.path.join(base, "reel.mp4")
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", out], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg reel: %s" % r.stderr[-300:])
    os.makedirs(mt.OUTPUT, exist_ok=True)
    subprocess.run(["cp", out, os.path.join(mt.OUTPUT, "treadcore-footage.mp4")])
    print("reel: %d generations, %s (%d KB)" % (len(sheets), out, os.path.getsize(out) // 1024))


def resheet(q, home=None):
    """Every filmed generation's sheet made again from its films (a new layout, no new traces), then the reel."""
    mt = load_mod("montage", os.path.join(os.path.dirname(HERE), "montage.py"))
    home = home or gpu_home(q)[0]
    base = os.path.join(q, "archive", "footage", home)
    idx = json.load(open(os.path.join(base, "index.json")))
    for g in idx["generations"]:
        work = os.path.join(base, g["id"])
        films = {t[:2]: os.path.join(work, "%s.mp4" % t[:2]) for t in TESTS}
        title = "%s  \u00b7  made %s  \u00b7  %d of %d test runs passed" % (g["id"], g["made"].replace("T", " ")[:16], g["passed"], g["runs"])
        sheet(mt, films, g["results"], os.path.join(work, "sheet.mp4"), title)
    reel(q, home)


def main(a):
    if len(a) < 2 or a[1] not in ("make", "reel", "resheet"):
        print(__doc__)
        sys.exit(2)
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    if a[1] == "make":
        make(a[0], opt("--home"), opt("--only"), int(opt("--runs", 8)))
    elif a[1] == "resheet":
        resheet(a[0], opt("--home"))
    else:
        reel(a[0], opt("--home"))


if __name__ == "__main__":
    main(sys.argv[1:])
