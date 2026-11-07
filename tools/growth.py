#!/usr/bin/env python3
"""growth.py QUEUE refresh [--sizes] | sizes | purge [--keep-days N] [--do] | prune-builds | pack-logs [--keep-days N]
-- crucible's generations
sampled, and the disks the fleet's generations fill.

Paul, 3 November: "the rules and simulation of generations, we want to sample its growth in an
inspector as well. also, place a purge button, and give warnings when sizes get above 20GB."

THE SAMPLE. Each island segment (fifty or a hundred generations on one card) leaves its champion
and its numbers in results/x-ISLAND-NNNN/. `refresh` reads every segment not yet sampled and
writes ONE ROW A SEGMENT to HOME/growth.tsv beside the home's lineage: the generation reached,
best and mean fitness, the yardstick and the ladder, the exam, the speed, and the champion's own
matrices -- each layer's Frobenius norm and STABLE RANK (|W|_F^2 / sigma_max^2: how many
directions the layer really uses), the share of near-zero weights, and the share of the first
layer's weight that listens to the rules (hybrid) and to the world's senses (world). The record
is append-only and small (a few hundred bytes a segment), so it outlives a purge of the raw
segments: the growth is kept, the bulk is not. plan/growth.json is what orrery's Growth page
draws; its inspector reads a sample under the pointer.

THE SIZES. `sizes` measures every place the generations fill: the queue on the Mac (by kind),
treadcore's build/ outside it, and each machine's ~/fleet (over ssh, as the user, read only),
each part named with what it holds and whether it is rebuilt on demand. A place over the limit
(tuning.json `size_warn_gb`, 20 by default) is a warning on the page and a flag on the Flags
page, raised again at each ten gigabytes more, so a disk that keeps filling keeps saying so.

THE PURGE. `purge` LISTS; `purge --do` REMOVES. Three things go, and only these:
    old commit builds on every machine (QUEUE/c/SHORT: a checkout and its binaries, about 250 MB
        each), except the fleet's current commit, any commit a queued or running job names, and
        the two newest -- a prepare job rebuilds one in minutes if it is ever asked for again;
    finished jobs' out directories on the machines, older than the keep, whose results the
        Mac already fetched (the Mac's copy is the record);
    the GAME LOGS (g-*.log) of finished census reads (w, e, h, f) older than the keep, on the
        Mac, PACKED FIRST into archive/packs in fleet-archive's own form (PACK-NNN.tar.xz, rows
        in MANIFEST.tsv with their sha256), and the new pack read back against its rows before a
        file is removed. The reading itself -- pooled.txt, trial.weights, base.weights, run.env --
        stays, so the terrain, the temperament matrix and the planner read exactly what they did.
THE NIGHTLY PACK. `pack-logs` is the purge's third item alone, done without a press: the game logs of
finished census reads past PACK_KEEP_DAYS (1; tuning.json pack_keep_days), packed and proved as above.
The planner's chores begin it once a night (Paul, 6 November, of 17.65 GB of game logs in a 20.6 GB
queue: "the queue is too big ... is it all needed right now?"; then "Pack all but 1 day" and "Nightly,
by the keeper"). Nothing reads a game log past a day: the ledger, the terrain, the temperament and the
seed reads take pooled.txt and the weights; the logs serve the live work of hours -- held-out pieces
merged, a candidate's side reads, a training round's judge.
NOT PURGED, said rather than done: training recordings (*/shards: recordings.py drops a run's
shards once nothing reads them, its recipe proved and kept -- not this purge's business), a
run's results (r*, train-*, gauntlet-*: the reports read their logs), crucible's populations and
champions, the vault, and anything younger than the keep.
"""
import glob
import hashlib
import io
import json
import lzma
import math
import os
import re
import shlex
import struct
import subprocess
import sys
import tarfile
import threading
import time

SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8"]
LIMIT_GB = 20.0
KEEP_DAYS = 3
PACK_KEEP_DAYS = 1
KEEP_NEWEST_BUILDS = 2
# The net kinds crucible builds, as (inputs, outputs): plain, hybrid (the rules' three answers in,
# a confidence out), and each with the world's twenty senses. A champion file is NW floats with no
# header, so its kind is the one whose layout gives a whole hidden width.
KINDS = ((32, 3), (35, 4), (52, 3), (55, 4))
FIELDS = ["gen", "best", "mean", "yard", "ladder", "exam", "exam_yard", "msteps", "srank1", "srank2", "srank3",
          "fro1", "fro2", "fro3", "near0", "rules", "world", "pill_taken", "pill_killed", "shots", "hit_rate",
          "time", "job", "island", "dims", "gens"]
CENSUS = re.compile(r"^[wehf]\d+$")


def load(p, default=None):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(p, doc):
    tmp = p + ".part"
    with open(tmp, "w") as f:
        json.dump(doc, f)
    os.replace(tmp, p)


def tuning(q, key, default):
    v = (load(os.path.join(q, "tuning.json"), {}) or {}).get(key)
    return default if v is None else v


def num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ---- the sample ------------------------------------------------------------------------------

def dims_of(nw):
    """(inputs, hidden, outputs) of a champion of `nw` weights, or None: NW = nin*H + H + H*H + H
    + H*nout + nout, a quadratic in H."""
    for nin, nout in KINDS:
        b = nin + 2 + nout
        disc = b * b + 4 * (nw - nout)
        r = math.isqrt(disc)
        if r * r == disc and (r - b) % 2 == 0 and r > b:
            return (nin, (r - b) // 2, nout)
    return None


def layers(w, nin, h, nout):
    """The three matrices, rows a unit's inputs, as crucible lays them out (W1[j*NIN+i])."""
    i = 0

    def take(rows, cols):
        nonlocal i
        m = [w[i + r * cols:i + (r + 1) * cols] for r in range(rows)]
        i += rows * cols
        return m
    W1 = take(h, nin)
    i += h
    W2 = take(h, h)
    i += h
    W3 = take(nout, h)
    return W1, W2, W3


def top_singular(m, iters=14):
    """The largest singular value, by power iteration on M^T M: enough for a stable rank."""
    cols = len(m[0])
    v = [1.0 / math.sqrt(cols)] * cols
    s = 0.0
    for _ in range(iters):
        u = [sum(a * b for a, b in zip(row, v)) for row in m]
        z = [0.0] * cols
        for row, ur in zip(m, u):
            for k, a in enumerate(row):
                z[k] += a * ur
        nz = math.sqrt(sum(x * x for x in z)) or 1e-30
        v = [x / nz for x in z]
        s = math.sqrt(nz)
    return s


def champion_stats(path):
    try:
        raw = open(path, "rb").read()
    except OSError:
        return None
    nw = len(raw) // 4
    d = dims_of(nw)
    if not d:
        return None
    w = struct.unpack("<%df" % nw, raw[:nw * 4])
    nin, h, nout = d
    out = {"dims": "%d-%d-%d-%d" % (nin, h, h, nout)}
    big = max(abs(x) for x in w) or 1.0
    # Near zero: under 2% of the net's largest weight -- a weight the net could lose unnoticed.
    out["near0"] = sum(1 for x in w if abs(x) < 0.02 * big) / nw
    for k, m in enumerate(layers(w, nin, h, nout), 1):
        fro2 = sum(x * x for row in m for x in row)
        smax = top_singular(m)
        out["fro%d" % k] = math.sqrt(fro2)
        out["srank%d" % k] = fro2 / (smax * smax) if smax > 0 else None
    W1 = layers(w, nin, h, nout)[0]
    col = [sum(abs(W1[j][i]) for j in range(h)) for i in range(nin)]
    total = sum(col) or 1.0
    hybrid = nin in (35, 55)
    base = 35 if hybrid else 32
    out["rules"] = sum(col[32:35]) / total if hybrid else None
    out["world"] = sum(col[base:]) / total if nin in (52, 55) else None
    return out


def segment_home(console):
    m = re.search(r"saved (\S+)/island\.state", console) or re.search(r"resumed (\S+)/island\.state", console)
    return os.path.basename(m.group(1)) if m else None


def sample_segment(q, gens_path):
    out_dir = os.path.dirname(gens_path)
    jid = os.path.basename(out_dir)
    champ = os.path.join(out_dir, "champ.bin")
    if not os.path.exists(champ):
        return None, None  # not finished: sampled when it is
    try:
        lines = open(gens_path).read().splitlines()
    except OSError:
        return None, None
    if len(lines) < 2:
        return None, None
    head = lines[0].split("\t")
    rows = [dict(zip(head, l.split("\t"))) for l in lines[1:] if l.strip()]
    console = ""
    try:
        console = open(os.path.join(out_dir, "console.txt")).read()
    except OSError:
        pass
    st = champion_stats(champ) or {}
    home = segment_home(console) or {"35": "crucible-hybrid", "52": "crucible-world", "55": "crucible-world-hybrid"}.get(st.get("dims", "32").split("-")[0], "crucible")
    last = rows[-1]
    yard = [num(r.get("yard_win")) for r in rows if (num(r.get("yard_win")) or -1) >= 0]
    lad = [num(r.get("ladder_score")) for r in rows if (num(r.get("ladder_score")) or -9) > -1.5]
    sps = [num(r.get("steps_per_s")) for r in rows if num(r.get("steps_per_s"))]

    def mean_of(k):
        v = [num(r.get(k)) for r in rows if num(r.get(k)) is not None]
        return sum(v) / len(v) if v else None
    exam, exam_yard = None, None
    try:
        ex = [l.split("\t") for l in open(os.path.join(out_dir, "exam.tsv")).read().splitlines()[1:] if l.strip()]
        ms = [num(r[1]) - num(r[3]) for r in ex if r[0] != "yardstick" and num(r[1]) is not None and num(r[3]) is not None]
        exam = sum(ms) / len(ms) if ms else None
        exam_yard = next((num(r[1]) for r in ex if r[0] == "yardstick"), None)
    except (OSError, IndexError, TypeError):
        pass
    island = jid[2:].rsplit("-", 1)[0]
    rec = {"gen": int(num(last.get("gen")) or 0) + 1, "best": num(last.get("best")), "mean": num(last.get("mean")),
           "yard": yard[-1] if yard else None, "ladder": lad[-1] if lad else None, "exam": exam, "exam_yard": exam_yard,
           "msteps": sum(sps) / len(sps) / 1e6 if sps else None,
           "pill_taken": mean_of("pill_taken"), "pill_killed": mean_of("pill_killed"), "shots": mean_of("shots"), "hit_rate": mean_of("hit_rate"),
           "time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(gens_path))), "job": jid, "island": island, "gens": len(rows)}
    for k in ("srank1", "srank2", "srank3", "fro1", "fro2", "fro3", "near0", "rules", "world", "dims"):
        rec[k] = st.get(k)
    return home, rec


def record_path(q, home):
    return os.path.join(q, home, "growth.tsv")


def read_record(q, home):
    p = record_path(q, home)
    rows = []
    try:
        lines = open(p).read().splitlines()
    except OSError:
        return rows
    head = lines[0].split("\t") if lines else FIELDS
    for l in lines[1:]:
        r = dict(zip(head, l.split("\t")))
        for k in FIELDS:
            if k in ("time", "job", "island", "dims"):
                r[k] = r.get(k) or ""
            elif k in ("gen", "gens"):
                r[k] = int(num(r.get(k)) or 0)
            else:
                r[k] = num(r.get(k))
        rows.append(r)
    return rows


def fmt(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        return "%.5g" % v
    return str(v)


def sample(q):
    """Every finished segment not yet in its home's record, appended. Returns the count."""
    homes = [os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(q, "crucible*", "lineage.tsv"))]
    seen = set()
    for h in set(homes) | {"crucible", "crucible-hybrid"}:
        seen |= {r["job"] for r in read_record(q, h)}
    new = {}
    for gp in sorted(glob.glob(os.path.join(q, "results", "x-*", "*", "*", "out", "x-*", "gens.tsv"))):
        jid = os.path.basename(os.path.dirname(gp))
        if jid in seen:
            continue
        home, rec = sample_segment(q, gp)
        if rec:
            new.setdefault(home, []).append(rec)
    n = 0
    for home, recs in new.items():
        os.makedirs(os.path.join(q, home), exist_ok=True)
        p = record_path(q, home)
        fresh = not os.path.exists(p) or os.path.getsize(p) == 0
        recs.sort(key=lambda r: (r["island"], r["gen"]))
        with open(p, "a") as f:
            if fresh:
                f.write("\t".join(FIELDS) + "\n")
            for r in recs:
                f.write("\t".join(fmt(r.get(k)) for k in FIELDS) + "\n")
        n += len(recs)
    return n


def growth_doc(q):
    """The homes, each island's samples thinned to at most 480 points (every one kept at the ends)."""
    out = []
    for p in sorted(glob.glob(os.path.join(q, "crucible*", "growth.tsv"))):
        home = os.path.basename(os.path.dirname(p))
        rows = read_record(q, home)
        if not rows:
            continue
        islands = {}
        for r in rows:
            islands.setdefault(r["island"], []).append(r)
        isl = []
        for name, rs in sorted(islands.items()):
            rs.sort(key=lambda r: r["gen"])
            step = max(1, math.ceil(len(rs) / 480))
            keep = rs[::step]
            if keep[-1] is not rs[-1]:
                keep.append(rs[-1])
            isl.append({"island": name, "count": len(rs), "first": rs[0]["time"], "last": rs[-1]["time"],
                        "samples": [[r.get(k) for k in FIELDS] for r in keep]})
        dims = sorted({r["dims"] for r in rows if r["dims"]})
        out.append({"home": home, "dims": dims, "segments": len(rows), "islands": isl, "newest": max(r["time"] for r in rows)})
    # The home sampled last first: the page opens on the islands running now, not the retired.
    out.sort(key=lambda h: h["newest"], reverse=True)
    return {"fields": FIELDS, "homes": out}


# ---- the sizes -------------------------------------------------------------------------------

# What each part of ~/fleet holds, by the last components of its path: (pattern, what, rebuilt).
PARTS = [
    (r"q-[^/]+/c$", "commit builds: a checkout and its binaries a commit", True),
    (r"q-[^/]+/out$", "jobs' outputs, fetched to the Mac when each finished", True),
    (r"q-[^/]+/promote$", "promotion worktrees", True),
    (r"q-[^/]+/crucible[^/]*$", "an island's population and hall of fame", False),
    (r"q-[^/]+/trials$", "trials' weights files", True),
    (r"(rec|rot|width)\w*/shards$", "training recordings: dropped once read, re-recorded from the recipe", False),
    (r"(rec|rot|width)\w*$", "a training recording's folder: its binary, checkout and manifest", False),
    (r"target$|target/release$", "the lane's cargo build cache", True),
]


def what_of(path):
    for pat, what, rebuilt in PARTS:
        if re.search(pat, path):
            return what, rebuilt
    return "", None


def du_lines(text):
    out = []
    for l in text.splitlines():
        m = re.match(r"^(\d+)\s+(.+)$", l.strip())
        if m:
            out.append((int(m.group(1)) * 1024, m.group(2)))
    return out


REMOTE_DU = (
    "du -sk ~/fleet 2>/dev/null; for d in ~/fleet/* ~/fleet/q-*/* ~/fleet/rec*/*; do [ -d \"$d\" ] && du -sk \"$d\" 2>/dev/null; done; "
    "echo DF $(df -Pk ~ | tail -1)"
)


def machines(q):
    """(name, target) once a target, for the queue's lanes only (config.json's hosts: a machine
    the registry remembers but the queue no longer runs is not dialled); the -cuda lanes share
    their machine's disk, so a target is asked once."""
    m = load(os.path.join(q, "machines.json"), {}) or {}
    reg = dict(m.items()) if isinstance(m, dict) else {x.get("name"): x for x in m}
    lanes = [h.get("name") for h in (load(os.path.join(q, "config.json"), {}) or {}).get("hosts", [])]
    seen, out = set(), []
    for name in lanes:
        v = reg.get(name)
        t = v.get("target") if isinstance(v, dict) else v
        if not t or name == "mac" or t in seen or not re.match(r"^[\w.@-]+$", str(t)):
            continue
        seen.add(t)
        out.append((name.replace("-cuda", ""), t))
    return out


def remote(target, cmd, timeout):
    """A command on a machine, in plain sh whatever its login shell: zsh (macmini's) aborts the
    whole line on a glob that matches nothing, and ~/fleet/rec*/* matches nothing there."""
    return subprocess.run(SSH + [target, "sh -c %s" % shlex.quote(cmd)], capture_output=True, text=True, timeout=timeout)


def place_from(name, where, lines, disk, limit):
    total = next((b for b, p in lines if p.rstrip("/").endswith("/fleet")), sum(b for b, p in lines))
    home = next((p for b, p in lines if p.rstrip("/").endswith("/fleet")), "~/fleet")
    parts = []
    for b, p in lines:
        if p.rstrip("/").endswith("/fleet") or b < 50 * 1024 * 1024:
            continue
        rel = p.split("/fleet/", 1)[-1]
        # A q-*/ folder is itself the sum of its parts below: skip it, list the parts.
        if re.match(r"^q-[^/]+$", rel) or re.match(r"^rec\d+$", rel) and any(x[1].startswith(p + "/") for x in lines):
            continue
        what, rebuilt = what_of(rel)
        parts.append({"path": rel, "bytes": b, "what": what, "rebuilt": rebuilt})
    parts.sort(key=lambda x: -x["bytes"])
    return {"place": name, "where": where, "path": home, "bytes": total, "over": total > limit * 1e9, "parts": parts[:12], "disk": disk}


def sizes(q):
    limit = float(tuning(q, "size_warn_gb", LIMIT_GB))
    places = []
    # The Mac: the queue by part, results by kind, and treadcore's build outside the queue.
    qb = du_lines(subprocess.run(["du", "-sk", q], capture_output=True, text=True).stdout)
    qtotal = qb[0][0] if qb else 0
    sub = du_lines(subprocess.run("du -sk %s/* 2>/dev/null" % shlex.quote(q), shell=True, capture_output=True, text=True).stdout)
    # du's own depth, not a shell glob: 21,000 result folders overflow the argument list.
    res = [x for x in du_lines(subprocess.run(["du", "-k", "-d", "1", os.path.join(q, "results")], capture_output=True, text=True).stdout)
           if x[1].rstrip("/") != os.path.join(q, "results")]
    kinds = {}
    for b, p in res:
        j = os.path.basename(p)
        k = ("crucible segments (x-)" if j.startswith("x-") else "first reads (w)" if re.match(r"w\d", j) else "read-ons (e)" if re.match(r"e\d", j)
             else "held-out reads (h)" if re.match(r"h\d", j) else "families (f)" if re.match(r"f\d", j) else "runs (r)" if re.match(r"r\d", j)
             else "builds and promotions (prep, p)" if j.startswith(("prep-", "p")) else "other")
        kinds[k] = kinds.get(k, 0) + b
    parts = [{"path": "results: " + k, "bytes": b, "what": "the game logs are the bulk; packed before a purge" if k.endswith(("(w)", "(e)", "(h)", "(f)")) else "", "rebuilt": False}
             for k, b in sorted(kinds.items(), key=lambda x: -x[1])]
    parts += [{"path": os.path.basename(p), "bytes": b, "what": "", "rebuilt": False} for b, p in sub if os.path.basename(p) != "results" and b >= 50 * 1024 * 1024]
    parts.sort(key=lambda x: -x["bytes"])
    st = os.statvfs(q)
    disk = {"size": st.f_blocks * st.f_frsize, "free": st.f_bavail * st.f_frsize}
    places.append({"place": "mac", "where": "the queue", "path": q, "bytes": qtotal, "over": qtotal > limit * 1e9, "parts": parts[:12], "disk": disk})
    build = os.path.dirname(os.path.dirname(q))
    if os.path.basename(build) == "build":
        bb = du_lines(subprocess.run(["du", "-sk", build], capture_output=True, text=True).stdout)
        outside = (bb[0][0] if bb else 0) - qtotal
        places.append({"place": "mac", "where": "treadcore build/, outside the queue", "path": build, "bytes": outside, "over": outside > limit * 1e9,
                       "parts": [], "disk": disk})
    lane = os.path.expanduser("~/fleet")
    if os.path.isdir(lane):
        lines = du_lines(subprocess.run("du -sk %s 2>/dev/null; for d in %s/* %s/q-*/*; do [ -d \"$d\" ] && du -sk \"$d\" 2>/dev/null; done" % ((shlex.quote(lane),) * 3),
                                        shell=True, capture_output=True, text=True).stdout)
        places.append(place_from("mac", "the Mac's lane", lines, disk, limit))
    # The machines, at once: a machine that does not answer in a minute is said, not waited for.
    got = {}

    def one(name, target):
        try:
            r = remote(target, REMOTE_DU, 120)
            got[name] = (r.stdout, r.stderr.strip().splitlines()[-1] if r.returncode and r.stderr.strip() else "")
        except subprocess.TimeoutExpired:
            got[name] = ("", "no answer in two minutes")
    ts = [threading.Thread(target=one, args=mt) for mt in machines(q)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    for name, target in machines(q):
        text, err = got.get(name, ("", "not asked"))
        lines = du_lines(text)
        m = re.search(r"^DF \S+ (\d+) (\d+) (\d+)", text, re.M)
        disk = {"size": int(m.group(1)) * 1024, "free": int(m.group(3)) * 1024} if m else None
        if not lines:
            places.append({"place": name, "where": "~/fleet", "path": "~/fleet", "bytes": None, "over": False, "parts": [], "disk": disk, "error": err or "no ~/fleet"})
            continue
        places.append(place_from(name, "~/fleet", lines, disk, limit))
    warnings = []
    for p in places:
        if p.get("over"):
            big = ", ".join("%s %.1f GB" % (x["path"], x["bytes"] / 1e9) for x in p["parts"][:3])
            warnings.append("%s: %s holds %.1f GB, over the %.0f GB limit%s" % (p["place"], p["where"], p["bytes"] / 1e9, limit, (": " + big) if big else ""))
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "limit_gb": limit, "places": places, "warnings": warnings}


def raise_flags(q, sz):
    """A flag a place over the limit, once a ten gigabytes: the Flags page's form (fleet-queue's)."""
    d = os.path.join(q, "flags")
    os.makedirs(d, exist_ok=True)
    keys = set()
    for f in glob.glob(os.path.join(d, "*.json")):
        keys.add((load(f, {}) or {}).get("key"))
    for p in sz["places"]:
        if not p.get("over"):
            continue
        band = int(p["bytes"] / 1e9 // 10 * 10)
        key = "size:%s:%s:%d" % (p["place"], p["where"], band)
        if key in keys:
            continue
        fid = "%d-size" % int(time.time() * 1000)
        text = "%s: %s holds %.1f GB, over the %.0f GB limit; the Growth page lists what a purge would free" % (p["place"], p["where"], p["bytes"] / 1e9, sz["limit_gb"])
        save(os.path.join(d, fid + ".json"), {"id": fid, "t": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": "size", "text": text, "key": key, "ack": None, "progress": False})
        time.sleep(0.002)


# ---- the purge -------------------------------------------------------------------------------

def finished(q):
    """Job ids in done/, failed/ and stopped/, as the planner reads them (MILLIS-ID.json)."""
    out = set()
    for sub in ("done", "failed", "stopped"):
        for f in glob.glob(os.path.join(q, sub, "**", "*.json"), recursive=True):
            out.add(re.sub(r"^\d+-", "", os.path.basename(f))[:-5])
    return out


def named_commits(q):
    """Commits the fleet still needs built: the one it builds now, the local line's, and any a
    queued or running job's text names (a census on an older build reads its own)."""
    keep = set()
    pipe = load(os.path.join(q, "plan", "pipeline.json"), {}) or {}
    if pipe.get("commit"):
        keep.add(pipe["commit"][:7])
    st = load(os.path.join(q, "plan", "state.json"), {}) or {}
    line = (st.get("local_line") or {}).get("commit") or ""
    if line:
        keep.add(line[:7])
    text = ""
    for sub in ("queue", "running"):
        for f in glob.glob(os.path.join(q, sub, "*.json")):
            try:
                text += open(f).read()
            except OSError:
                pass
    keep |= set(re.findall(r"/c/([0-9a-f]{7})\b", text)) | set(re.findall(r"prep-[\w-]+-([0-9a-f]{7})\b", text))
    # A recording still on its store whose recipe is not complete: its build holds the binary that
    # made it, and without that binary its shards cannot be dropped (recordings.py).
    for r in (load(os.path.join(q, "plan", "recordings.json"), {}) or {}).get("runs", []):
        if r.get("shards_now") and r.get("recipe") != "complete" and re.match(r"^[0-9a-f]{7}$", r.get("commit") or ""):
            keep.add(r["commit"])
    return keep


REMOTE_LIST = (
    "for d in $(ls -td ~/fleet/q-*/c/* 2>/dev/null); do echo \"C $(du -sk \"$d\" | cut -f1) $d\"; done; "
    "for d in $(find ~/fleet/q-*/out -mindepth 1 -maxdepth 1 -type d -mtime +%d 2>/dev/null); do echo \"O $(du -sk \"$d\" | cut -f1) $d\"; done"
)


def plan_purge(q, keep_days, kinds=None):
    keep_c = named_commits(q)
    done = finished(q)
    items, kept = [], []
    kinds = kinds or {"logs", "builds", "outs"}
    # The Mac's census logs: finished reads older than the keep.
    cutoff = time.time() - keep_days * 86400
    logs, lbytes = [], 0
    for jid in (os.listdir(os.path.join(q, "results")) if "logs" in kinds else []):
        if not CENSUS.match(jid) or jid not in done:
            continue
        d = os.path.join(q, "results", jid)
        try:
            if os.path.getmtime(d) > cutoff:
                continue
        except OSError:
            continue
        for f in glob.glob(os.path.join(d, "*", "*", "out", jid, "*", "g-*.log")):
            try:
                lbytes += os.path.getsize(f)
            except OSError:
                continue
            logs.append(os.path.relpath(f, q))
    items.append({"place": "mac", "kind": "logs", "what": "game logs of finished census reads older than %d days, packed first; the readings stay" % keep_days,
                  "count": len(logs), "bytes": lbytes, "paths": logs})
    # The machines' builds and outputs, and the Mac's own lane.
    targets = [("mac", None)] + machines(q)
    got = {}

    def one(name, target):
        cmd = REMOTE_LIST % keep_days
        try:
            if target is None:
                r = subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, timeout=300)
            else:
                r = remote(target, cmd, 300)
            got[name] = r.stdout
        except subprocess.TimeoutExpired:
            got[name] = ""
    ts = [threading.Thread(target=one, args=mt) for mt in targets]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    for name, target in targets:
        builds, bb, kb = [], 0, 0
        outs, ob = [], 0
        newest = 0
        for l in got.get(name, "").splitlines():
            m = re.match(r"^([CO]) (\d+) (\S+)$", l)
            if not m:
                continue
            kind, kb_, path = m.group(1), int(m.group(2)) * 1024, m.group(3)
            if kind == "C":
                short = os.path.basename(path)
                if not re.match(r"^[0-9a-f]{7}$", short) or not re.search(r"/fleet/q-[\w-]+/c/[0-9a-f]{7}$", path):
                    continue
                # ls -t: newest first. The newest two stay, and every commit still named.
                if short in keep_c or newest < KEEP_NEWEST_BUILDS:
                    newest += short not in keep_c
                    kb += kb_
                    continue
                builds.append(path)
                bb += kb_
            else:
                jid = os.path.basename(path)
                if jid not in done or not os.path.isdir(os.path.join(q, "results", jid)) or not re.search(r"/fleet/q-[\w-]+/out/[\w.-]+$", path):
                    continue
                outs.append(path)
                ob += kb_
        if builds:
            items.append({"place": name, "kind": "builds", "target": target, "what": "%d old commit builds (rebuilt on demand); the current, the named and the two newest stay" % len(builds),
                          "count": len(builds), "bytes": bb, "paths": builds})
        if outs:
            items.append({"place": name, "kind": "outs", "target": target, "what": "finished jobs' outputs older than %d days, already fetched to the Mac" % keep_days,
                          "count": len(outs), "bytes": ob, "paths": outs})
    sz = (load(os.path.join(q, "plan", "growth.json"), {}) or {}).get("sizes") or {}
    for p in sz.get("places", []):
        for part in p.get("parts", []):
            if part.get("rebuilt") is False and part["bytes"] >= 1e9 and re.match(r"(rec|rot|width)\w*", part["path"]):
                kept.append({"place": p["place"], "what": "%s: %s" % (part["path"], part["what"]), "bytes": part["bytes"], "why": "recordings.py drops it once nothing reads it, keeping its recipe (Recordings page)"})
    items = [i for i in items if i["count"] and i["kind"] in kinds]
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "keep_days": keep_days, "bytes": sum(i["bytes"] for i in items),
            "items": items, "kept": kept, "commits_kept": sorted(keep_c)}


def archive_tool():
    import importlib.util
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fleet-archive.py")
    spec = importlib.util.spec_from_file_location("fleet_archive", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def pack_logs(q, rels):
    """The logs into a new pack, fleet-archive's form, then the pack read back against its rows.
    Returns the rels proven held. xz preset 1, not the disc's 6: a purge waits on this, and logs
    of text compress about tenfold at either."""
    fa = archive_tool()
    mpath, have = fa.manifest(q)
    todo = []
    held = []
    for rel in rels:
        try:
            size = os.path.getsize(os.path.join(q, rel))
        except OSError:
            continue
        k = have.get(rel)
        if k and k[2] == size:
            held.append(rel)  # an earlier pack holds it already
        else:
            todo.append(rel)
    home = os.path.join(q, "archive", "packs")
    os.makedirs(home, exist_ok=True)
    limit = fa.DISC_BYTES["bd25"]
    i = 0
    while i < len(todo):
        nums = [int(f[5:8]) for f in os.listdir(home) if f.startswith("PACK-") and f.endswith(".tar.xz")]
        name = "PACK-%03d.tar.xz" % (max(nums, default=0) + 1)
        path = os.path.join(home, name)
        tmp = path + ".part"
        rows = {}
        with lzma.open(tmp, "wb", preset=1) as xz, tarfile.open(fileobj=xz, mode="w") as tar:
            while i < len(todo) and os.path.getsize(tmp) < limit * 0.95:
                rel = todo[i]
                i += 1
                p = os.path.join(q, rel)
                try:
                    ti = tar.gettarinfo(p, arcname=rel)
                    with open(p, "rb") as f:
                        data = f.read()
                except OSError:
                    continue
                ti.size = len(data)
                rows[rel] = (hashlib.sha256(data).hexdigest(), len(data))
                tar.addfile(ti, io.BytesIO(data))
        # READ BACK BEFORE ANYTHING IS REMOVED: every member's bytes against the row written for it.
        ok = set()
        with tarfile.open(tmp, "r:xz") as tar:
            for ti in tar:
                f = tar.extractfile(ti)
                if f is None:
                    continue
                data = f.read()
                r = rows.get(ti.name)
                if r and hashlib.sha256(data).hexdigest() == r[0] and len(data) == r[1]:
                    ok.add(ti.name)
        os.replace(tmp, path)
        with open(mpath, "a") as m:
            m.writelines("%s\t%s\t%d\t%s\n" % (name, rows[rel][0], rows[rel][1], rel) for rel in rows)
        held += sorted(ok)
        print("%s: %d logs, %.0f MB on disc, %d read back whole" % (name, len(rows), os.path.getsize(path) / 1e6, len(ok)))
    return held


def purge(q, keep_days, do, kinds=None, by=None):
    gp = os.path.join(q, "plan", "growth.json")
    doc = load(gp, {}) or {}
    plan = plan_purge(q, keep_days, kinds)
    if not do:
        doc["purge"] = {k: v for k, v in plan.items()}
        doc["purge"]["items"] = [{k: v for k, v in i.items() if k != "paths"} for i in plan["items"]]
        doc["purge"]["state"] = "listed"
        save(gp, doc)
        print("a purge would free %.1f GB: %s; press again to do it" % (plan["bytes"] / 1e9, "; ".join("%s %s %.1f GB" % (i["place"], i["kind"], i["bytes"] / 1e9) for i in plan["items"]) or "nothing"))
        return
    freed, said = 0, []
    for it in plan["items"]:
        if it["kind"] == "logs":
            held = set(pack_logs(q, it["paths"]))
            n = b = 0
            for rel in it["paths"]:
                if rel not in held:
                    continue
                p = os.path.join(q, rel)
                try:
                    b += os.path.getsize(p)
                    os.remove(p)
                    n += 1
                except OSError:
                    pass
            freed += b
            said.append("mac: %d logs packed and removed, %.1f GB" % (n, b / 1e9))
            continue
        paths = [p for p in it["paths"] if re.search(r"/fleet/q-[\w-]+/(c/[0-9a-f]{7}|out/[\w.-]+)$", p)]
        if not paths:
            continue
        cmd = "rm -rf -- %s" % " ".join(shlex.quote(p) for p in paths)
        if it["kind"] == "builds":
            # The checkouts were worktrees of the machine's treadcore: git forgets the missing ones.
            cmd += "; git -C ~/code/treadcore worktree prune 2>/dev/null; true"
        try:
            if it.get("target"):
                r = remote(it["target"], cmd, 900)
            else:
                r = subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, timeout=900)
            ok = r.returncode == 0
        except subprocess.TimeoutExpired:
            ok = False
        if ok:
            freed += it["bytes"]
        said.append("%s: %s %s" % (it["place"], it["kind"], "%.1f GB removed" % (it["bytes"] / 1e9) if ok else "failed"))
    doc = load(gp, {}) or {}
    doc["purge"] = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "state": "done", "keep_days": keep_days, "bytes": freed, "items": [], "kept": plan["kept"], "did": said, "by": by or "the Purge button"}
    save(gp, doc)
    with open(os.path.join(q, "events.jsonl"), "a") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": "purge", "freed": freed, "did": said, "by": by or "the Purge button"}) + "\n")
    refresh(q, measure=True)
    print("purged %.1f GB: %s" % (freed / 1e9, "; ".join(said) or "nothing"))


# ---- the document ----------------------------------------------------------------------------

def refresh(q, measure=False):
    os.makedirs(os.path.join(q, "plan"), exist_ok=True)
    gp = os.path.join(q, "plan", "growth.json")
    lock = gp + ".lock"
    open(lock, "w").close()
    try:
        n = sample(q)
        old = load(gp, {}) or {}
        doc = growth_doc(q)
        doc["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        doc["limit_gb"] = float(tuning(q, "size_warn_gb", LIMIT_GB))
        doc["keep_days"] = int(tuning(q, "purge_keep_days", KEEP_DAYS))
        sz = old.get("sizes")
        # The sizes every half hour, or when asked: they change by gigabytes a day, and each
        # measure is a minute of ssh to every machine.
        age = time.time() - time.mktime(time.strptime(sz["at"], "%Y-%m-%dT%H:%M:%S")) if sz and sz.get("at") else 1e9
        if measure or age > 1800:
            sz = sizes(q)
            raise_flags(q, sz)
        doc["sizes"] = sz
        if old.get("purge"):
            doc["purge"] = old["purge"]
        save(gp, doc)
        print("growth: %d new segment%s sampled; %s" % (n, "" if n == 1 else "s",
              "%d warning%s over %.0f GB" % (len(sz["warnings"]), "" if len(sz["warnings"]) == 1 else "s", sz["limit_gb"]) if sz else "sizes not measured"))
    finally:
        try:
            os.remove(lock)
        except OSError:
            pass


def main(a):
    if len(a) < 2:
        print(__doc__)
        sys.exit(2)
    q, cmd = os.path.abspath(a[0]), a[1]
    rest = a[2:]
    if cmd == "refresh":
        refresh(q, measure="--sizes" in rest)
    elif cmd == "sizes":
        refresh(q, measure=True)
    elif cmd == "purge":
        keep = int(tuning(q, "purge_keep_days", KEEP_DAYS))
        if "--keep-days" in rest:
            keep = int(rest[rest.index("--keep-days") + 1])
        purge(q, max(1, keep), "--do" in rest)
    elif cmd == "pack-logs":
        keep = int(tuning(q, "pack_keep_days", PACK_KEEP_DAYS))
        if "--keep-days" in rest:
            keep = int(rest[rest.index("--keep-days") + 1])
        purge(q, max(1, keep), True, kinds={"logs"}, by="the nightly pack: game logs past %d day%s" % (max(1, keep), "" if keep <= 1 else "s"))
    elif cmd == "prune-builds":
        # The planner's, each time main moves: old commit builds alone, no press.
        purge(q, int(tuning(q, "purge_keep_days", KEEP_DAYS)), True, kinds={"builds"}, by="main moved: builds pruned")
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
