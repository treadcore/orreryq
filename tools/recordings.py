#!/usr/bin/env python3
"""recordings.py QUEUE list | recipe RUN | prove RUN | drop RUN [--do] [--without-recipe] | sweep [--do] | keep RUN | unkeep RUN
| rerecord RUN [SEED0 ...] | read RUN SEED -- the behaviour-cloning recordings, kept only while something reads them, their
recipe kept for good.

Paul, 4 November: "can we have this feature not eat up my storage space, have it clean up when done ...
i'm arguing that maybe they should not be recorded and stored, but I like the idea of a mechanism to debug if
necessary." Answered: the old shards go with their recipe kept; a run's shards go once the job they were made
for is done; a run may be marked to keep for analysis; and one setting keeps them all.

A RECORDING IS A FUNCTION OF ITS BINARY AND ITS SEEDS. The census binary that recorded a shard, run again in a
checkout of the same commit with the same seeds and seconds, writes the same bytes -- deterministic per binary,
as the census is (LAB-REPORT-FLEET.md), and the thread count does not enter. Proved on 4 November for every
binary that made rec1200 and rec2400: one shard each re-recorded on calber, the Mac and columbia, six hashes
equal to the manifest's. So the shards are a cache, and the recipe is the record: 87.5 GB of shards against
about 20 MB of binaries.

THE RECIPE is archive/recordings/RUN/recipe.json: the commit, the seconds, and every shard -- its seeds, its
samples, its bytes, its sha256, and the sha256 of the binary that made it. Each binary is copied once, by its
hash, to archive/recordings/bin/SHA256 (a Mac's binary runs only on a Mac, a Linux one on Linux: the recipe
says which). A recipe is COMPLETE only when every shard is hashed, every binary is saved and its copy checked,
and ONE SHARD A BINARY HAS BEEN RE-RECORDED EQUAL. Nothing is dropped on a recipe that is not complete: a
binary that was rebuilt since, or a machine gone, is said, and the shards stay.

DROP removes a run's shards on the store, and nothing else: its folder keeps census-bin, wt and the manifest.
SWEEP is the default: a run is dropped when it is finished, no queued or running job names its shards, no
watch or round of the planner still waits on it, it is not marked to keep (QUEUE/recordings.json, "Keep for
analysis" on the Recordings page), and tuning.json keep_recordings is off. RERECORD makes shards again from the
recipe, on a machine that can run the binary, each checked against its hash before it is renamed into place.
"""
import array
import glob
import hashlib
import importlib.util
import json
import math
import os
import re
import shlex
import struct
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def _growth():
    # Loaded by path: the keeper runs these tools with python3 -I, which leaves the script's own
    # folder off sys.path.
    spec = importlib.util.spec_from_file_location("growth", os.path.join(HERE, "growth.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


G = _growth()
load, save, remote, finished, tuning = G.load, G.save, G.remote, G.finished, G.tuning

RUN_NAME = re.compile(r"^[\w.-]+$")
TC = os.path.expanduser("~/code/treadcore")
RECORD = ("cd %(wt)s && RECORD=%(out)s SEED0=%(s0)d SEEDS=%(n)d SECS=%(secs)d THREADS=%(threads)s nice -n 10 "
          "%(bin)s --ignored learn::harness::train --nocapture >/dev/null 2>&1")
# Braces, not a subshell: "$((" opens arithmetic in dash.
SHA = "{ sha256sum %s 2>/dev/null || shasum -a 256 %s; } | cut -c1-64"


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def adir(q, *a):
    return os.path.join(q, "archive", "recordings", *a)


def say_event(q, **kw):
    with open(os.path.join(q, "events.jsonl"), "a") as f:
        f.write(json.dumps(dict({"t": now(), "event": "recordings"}, **kw)) + "\n")


# ---- where things are ------------------------------------------------------------------------

def targets(q):
    """Every machine name the registry knows -> its ssh target; the Mac is None (run here)."""
    m = load(os.path.join(q, "machines.json"), {}) or {}
    reg = dict(m.items()) if isinstance(m, dict) else {x.get("name"): x for x in m}
    out = {"mac": None}
    for name, v in reg.items():
        t = v.get("target") if isinstance(v, dict) else v
        if t and t != "-" and re.match(r"^[\w.@-]+$", str(t)):
            out[name] = t
            out[name.replace("-cuda", "")] = out.get(name.replace("-cuda", ""), t)
    return out


def on(target, cmd, timeout=600):
    """A command on a machine (None: this Mac), in plain sh."""
    if target is None:
        return subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, timeout=timeout)
    return remote(target, cmd, timeout)


SCAN = (
    "for d in $HOME/fleet/*/shards; do [ -d \"$d\" ] || continue; r=$(dirname \"$d\"); "
    "n=$(ls \"$d\" | grep -c '[.]bin$'); kb=$(du -sk \"$d\" | cut -f1); f=$(ls \"$d\" | grep '[.]bin$' | head -1); "
    "h=-; [ -n \"$f\" ] && h=$(head -c 16 \"$d/$f\" | od -A n -t x1 | tr -d ' \\n'); "
    "m=0; [ -f \"$r/manifest.tsv\" ] && m=1; "
    "t=$( (stat -c %Y \"$d\" 2>/dev/null || stat -f %m \"$d\") ); "
    "echo \"R $(basename \"$r\") $n $kb $m $h $t\"; done"
)


def header(h):
    """(format, senses, heads, record bytes) from a shard's first 16 bytes, as hex."""
    try:
        b = bytes.fromhex(h)
    except ValueError:
        return None
    if len(b) < 16 or not b.startswith(b"TCBC"):
        return None
    fmt = b[:5].decode("ascii", "replace")
    senses, heads = int.from_bytes(b[8:12], "little"), int.from_bytes(b[12:16], "little")
    masks = 3 if fmt == "TCBC2" else 4
    return fmt, senses, heads, senses * 4 + heads + masks + 4


def scan(q):
    """Every run with a shards folder, on every machine the queue runs and on this Mac."""
    out = []
    lock = threading.Lock()

    def one(name, target):
        try:
            r = on(target, SCAN, timeout=60)
        except subprocess.TimeoutExpired:
            return
        for line in r.stdout.splitlines():
            p = line.split()
            if len(p) == 7 and p[0] == "R":
                hd = header(p[5]) if p[5] != "-" else None
                with lock:
                    out.append({"run": p[1], "host": name, "shards": int(p[2]), "bytes": int(p[3]) * 1024,
                                "manifest": p[4] == "1", "format": hd[0] if hd else None, "senses": hd[1] if hd else None,
                                "made": time.strftime("%Y-%m-%dT%H:%M", time.localtime(int(p[6]))) if p[6].isdigit() else None})

    ts = [threading.Thread(target=one, args=(n, t)) for n, t in [("mac", None)] + G.machines(q)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return sorted(out, key=lambda r: (r["host"], r["run"]))


def planner_runs(q):
    """Run name -> (run id, its state, its params), for the planner's record runs."""
    out = {}
    for f in glob.glob(os.path.join(q, "plan", "runs", "*", "state.json")):
        st = load(f, {}) or {}
        rid = os.path.basename(os.path.dirname(f))
        if st.get("run") and st.get("jobs") is not None:
            params = (load(os.path.join(q, "runs", rid + ".json"), {}) or {}).get("params") or {}
            out[st["run"]] = (rid, st, params)
    return out


def marks(q):
    return load(os.path.join(q, "recordings.json"), {}) or {}


def keep_all(q):
    return bool(int(tuning(q, "keep_recordings", 0) or 0))


def readers(q, name, rid=None):
    """Why a run's shards are still wanted, in words; none, and it may go."""
    why = []
    pat = "fleet/%s/shards" % name
    for sub in ("queue", "running"):
        for f in glob.glob(os.path.join(q, sub, "**", "*.json"), recursive=True):
            try:
                if pat in open(f).read():
                    why.append("%s %s reads it" % ("queued" if sub == "queue" else "running", os.path.basename(f)[:-5].split("-", 1)[-1]))
            except OSError:
                pass
    st = load(os.path.join(q, "plan", "state.json"), {}) or {}
    wd = st.get("width") or {}
    if wd.get("name") == name:
        why.append("the shape watch waits on it")
    net = (load(os.path.join(q, "plan.json"), {}) or {}).get("net") or {}
    rounds = net.get("rounds") or []
    left = rounds[int(st.get("round") or 0):]
    if any(r.get("run") == name for r in left) or (left and name == "rec1200"):
        why.append("a net round still to come trains or judges on it")
    if rid:
        rs = (load(os.path.join(q, "plan", "runs", rid, "state.json"), {}) or {})
        if rs.get("status") not in ("done", "failed"):
            why.append("its run %s is %s" % (rid, rs.get("status") or "new"))
    return why


# ---- the recipe ------------------------------------------------------------------------------

def recipe_path(q, name):
    return adir(q, name, "recipe.json")


def save_binary(q, sha, sources):
    """Copy a binary into the archive by its hash, from the first source that has it; True when the
    copy on the Mac hashes to sha."""
    dst = adir(q, "bin", sha)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst) and hashlib.sha256(open(dst, "rb").read()).hexdigest() == sha:
        return True
    for target, path in sources:
        tmp = dst + ".part"
        try:
            if target is None:
                r = subprocess.run(["cp", os.path.expanduser(path), tmp], capture_output=True, timeout=120)
            else:
                r = subprocess.run(["scp", "-q", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "%s:%s" % (target, path.replace("~/", "")), tmp],
                                   capture_output=True, timeout=300)
        except subprocess.TimeoutExpired:
            continue
        if r.returncode == 0 and os.path.exists(tmp) and hashlib.sha256(open(tmp, "rb").read()).hexdigest() == sha:
            os.chmod(tmp, 0o755)
            os.replace(tmp, dst)
            return True
        try:
            os.remove(tmp)
        except OSError:
            pass
    return False


def osname(q, sha):
    p = adir(q, "bin", sha)
    try:
        head = open(p, "rb").read(20)
    except OSError:
        return None
    if head[:4] == b"\x7fELF":
        return "linux-" + {0x3e: "x86_64", 0xb7: "aarch64"}.get(int.from_bytes(head[18:20], "little"), "elf")
    if head[:4] in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
        return "macos"
    return None


def recipe(q, name):
    """Write (or complete) a run's recipe; returns it."""
    if not RUN_NAME.match(name):
        raise SystemExit("not a run name: %r" % name)
    tg = targets(q)
    found = [r for r in scan(q) if r["run"] == name and r["shards"]]
    old = load(recipe_path(q, name), {}) or {}
    if not found and old.get("shards"):
        return old
    if not found:
        raise SystemExit("%s: no shards on any machine, and no recipe" % name)
    store = found[0]
    st_target = tg.get(store["host"])
    pr = planner_runs(q).get(name)
    rows, where = [], {}
    if store["manifest"]:
        # A fleet-record.sh run: its manifest beside the shards names every shard's binary.
        man = on(st_target, "cat $HOME/fleet/%s/manifest.tsv" % name, 60).stdout
        wt = on(st_target, "git -C $HOME/fleet/%s/wt rev-parse HEAD" % name, 30).stdout.strip()
        for line in man.splitlines():
            p = line.split("\t")
            if len(p) >= 8 and p[0].isdigit():
                rows.append({"seed0": int(p[2]), "seeds": int(p[3]), "samples": int(p[4]), "bytes": int(p[5]),
                             "sha256": p[6], "binary": p[7], "host": p[1]})
                where.setdefault(p[7], set()).add((p[1], "~/fleet/%s/census-bin" % name, "~/fleet/%s/wt" % name))
        commit, secs, source = wt, int(old.get("secs") or 600), "fleet-record"
        os.makedirs(adir(q, name), exist_ok=True)
        with open(adir(q, name, "manifest.tsv"), "w") as f:
            f.write(man)
    elif pr:
        # A planner's record run: a job a shard, each on its own machine's build of the run's commit.
        rid, st, params = pr
        short = st.get("commit") or ""
        commit = subprocess.run(["git", "-C", TC, "rev-parse", short], capture_output=True, text=True).stdout.strip() or short
        secs, per, end = int(params.get("secs", 600)), int(params.get("per", 12)), int(st.get("end") or 0)
        done = {}
        for f in glob.glob(os.path.join(q, "done", "**", "*.json"), recursive=True):
            j = re.sub(r"^\d+-", "", os.path.basename(f))[:-5]
            if j in st.get("jobs", []):
                done[j] = (load(f, {}) or {}).get("host")
        hashes = {}
        out = on(st_target, "cd $HOME/fleet/%s/shards && for f in *.bin; do echo \"$(wc -c < $f) $(%s)  $f\"; done" % (name, SHA % ("$f", "$f")), 900).stdout
        for line in out.split("\n"):
            p = line.split()
            if len(p) == 3:
                hashes[p[2][:-4]] = (int(p[0]), p[1])
        bins = {}
        for j, host in sorted(done.items()):
            s0 = int(j.rsplit("-", 1)[1])
            path = "~/fleet/q-grove/c/%s/census-bin" % short
            if (host, path) not in bins:
                r = on(tg.get(host), SHA % (path.replace("~", "$HOME"), path.replace("~", "$HOME")), 60) if host in tg else None
                bins[(host, path)] = (r.stdout.strip() if r and r.returncode == 0 else "") or None
            b = bins[(host, path)]
            size, sha = hashes.get(str(s0), (None, None))
            hd = header_of_store(store)
            rows.append({"seed0": s0, "seeds": min(per, end - s0) if end else per, "bytes": size, "sha256": sha, "binary": b, "host": host,
                         "samples": (size - 16) // hd if size and hd else None, "job": j})
            if b:
                where.setdefault(b, set()).add((host, path, "~/fleet/q-grove/c/%s/wt" % short))
        source = "planner %s" % rid
    else:
        raise SystemExit("%s: shards without a manifest or a planner run; nothing says what made them" % name)
    binaries = dict(old.get("binaries") or {})
    for sha, srcs in where.items():
        ok = save_binary(q, sha, [(tg.get(h), p) for h, p, _ in sorted(srcs) if h in tg])
        binaries[sha] = {"saved": ok, "os": osname(q, sha) if ok else None, "made_on": sorted({h for h, _, _ in srcs}),
                         "runs_at": sorted([h, p, w] for h, p, w in srcs)}
    doc = {"run": name, "source": source, "store": store["host"], "made": store["made"], "commit": commit, "secs": secs,
           "format": store["format"], "senses": store["senses"], "shards": rows, "binaries": binaries,
           "seeds": sum(r["seeds"] or 0 for r in rows), "samples": sum(r["samples"] or 0 for r in rows),
           "bytes": sum(r["bytes"] or 0 for r in rows), "proofs": old.get("proofs") or [], "dropped": old.get("dropped"),
           "written": now(),
           "how": "git -C ~/code/treadcore worktree add --detach WT COMMIT; cd WT && RECORD=OUT SEED0=S SEEDS=N SECS=%d THREADS=T "
                  "archive/recordings/bin/BINARY --ignored learn::harness::train --nocapture; the sha256 of OUT is the shard's" % secs}
    os.makedirs(adir(q, name), exist_ok=True)
    save(recipe_path(q, name), doc)
    return doc


def header_of_store(store):
    """A sample's bytes, from what the scan read of the store's first shard."""
    if not store.get("senses"):
        return None
    return store["senses"] * 4 + 7 + (3 if store.get("format") == "TCBC2" else 4) + 4


def complete(doc):
    """(complete, why not) for a recipe."""
    if not doc or not doc.get("shards"):
        return False, "no recipe"
    if any(not r.get("sha256") or not r.get("binary") for r in doc["shards"]):
        return False, "a shard without its hash or its binary's"
    bins = {r["binary"] for r in doc["shards"]}
    lost = [b[:12] for b in bins if not (doc["binaries"].get(b) or {}).get("saved")]
    if lost:
        return False, "binary %s not saved" % ", ".join(lost)
    proved = {p["binary"] for p in doc.get("proofs", []) if p.get("equal")}
    unproved = [b[:12] for b in bins if b not in proved]
    if unproved:
        return False, "binary %s not proved by a re-recording" % ", ".join(unproved)
    return True, ""


# ---- proof, drop, re-record ------------------------------------------------------------------

def prove(q, name):
    """One shard a binary re-recorded where that binary already sits beside its checkout, and its hash
    compared with the recipe's."""
    doc = load(recipe_path(q, name)) or recipe(q, name)
    tg = targets(q)
    proofs = [p for p in doc.get("proofs", []) if p.get("equal")]
    have = {p["binary"] for p in proofs}
    lock = threading.Lock()

    def one(sha):
        rows = [r for r in doc["shards"] if r["binary"] == sha]
        places = (doc["binaries"].get(sha) or {}).get("runs_at") or []
        for host, binp, wt in places:
            if host not in tg:
                continue
            row = next((r for r in rows if r["host"] == host), rows[0])
            out = "/tmp/recordings-proof-%s-%d.bin" % (name, row["seed0"])
            cmd = (("[ \"$(%s)\" = %s ] || { echo binary-differs; exit 3; }; " % (SHA % (binp.replace("~", "$HOME"), binp.replace("~", "$HOME")), sha))
                   + RECORD % {"wt": wt.replace("~", "$HOME"), "out": out, "s0": row["seed0"], "n": row["seeds"], "secs": doc["secs"], "threads": 4,
                               "bin": binp.replace("~", "$HOME")}
                   + "; " + SHA % (out, out) + "; rm -f " + out)
            t0 = time.time()
            try:
                r = on(tg[host], cmd, 1800)
            except subprocess.TimeoutExpired:
                continue
            got = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
            if "binary-differs" in r.stdout:
                continue
            with lock:
                proofs.append({"binary": sha, "seed0": row["seed0"], "host": host, "seconds": round(time.time() - t0),
                               "equal": got == row["sha256"], "got": got, "at": now()})
            return

    ts = [threading.Thread(target=one, args=(b,)) for b in sorted({r["binary"] for r in doc["shards"]}) if b not in have]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    doc["proofs"] = proofs
    save(recipe_path(q, name), doc)
    ok, why = complete(doc)
    print("%s: %s" % (name, "the recipe is complete" if ok else "not complete: " + why))
    return doc


def drop(q, name, do, without_recipe=False):
    doc = load(recipe_path(q, name), {}) or {}
    ok, why = complete(doc)
    if not ok and not without_recipe:
        print("%s: kept -- %s" % (name, why))
        return 0
    if not ok:
        # A person's word, not the sweep's (Paul, 4 November, of rot8 to rot23: "Delete them"): the
        # shards go though nothing can remake them, and the recipe says so, its hashes kept as the record.
        doc = doc or {"run": name, "shards": []}
        doc["unrecoverable"] = "dropped without a complete recipe (%s), by a person's word" % why
    tg = targets(q)
    found = [r for r in scan(q) if r["run"] == name and r["shards"]]
    if not found:
        print("%s: no shards on any machine" % name)
        return 0
    freed = 0
    for st in found:
        if st["host"] != doc["store"]:
            continue
        if not do:
            print("%s: would remove %d shards, %.1f GB, on %s" % (name, st["shards"], st["bytes"] / 1e9, st["host"]))
            return st["bytes"]
        r = on(tg.get(st["host"]), "rm -f $HOME/fleet/%s/shards/*.bin" % name, 300)
        if r.returncode == 0:
            freed += st["bytes"]
    doc["dropped"] = now()
    doc["dropped_bytes"] = freed
    save(recipe_path(q, name), doc)
    say_event(q, did="dropped", run=name, freed=freed)
    print("%s: %.1f GB of shards removed; the recipe stays in archive/recordings/%s" % (name, freed / 1e9, name))
    return freed


def sweep(q, do):
    """The default: every run nothing reads, not kept, recipe completed and proved, then dropped."""
    mk = marks(q).get("keep") or {}
    if keep_all(q):
        print("keep_recordings is on: every run is kept")
        return
    runs = planner_runs(q)
    for st in scan(q):
        if not st["shards"]:
            continue
        name = st["run"]
        rid = (runs.get(name) or (None,))[0]
        if name in mk:
            print("%s: kept for analysis (%s)" % (name, mk[name].get("at", "")))
            continue
        why = readers(q, name, rid)
        if why:
            # Its binaries saved now, while their builds stand: a promotion prunes old builds.
            if do and not load(recipe_path(q, name)):
                try:
                    recipe(q, name)
                except SystemExit as e:
                    print(e)
            print("%s: still wanted -- %s" % (name, "; ".join(why)))
            continue
        if not do:
            print("%s: would be dropped, %.1f GB, once its recipe is complete" % (name, st["bytes"] / 1e9))
            continue
        doc = load(recipe_path(q, name)) or recipe(q, name)
        if not complete(doc)[0]:
            doc = recipe(q, name)
            doc = prove(q, name)
        drop(q, name, True)
    listing(q)


def rerecord(q, name, seeds):
    """Shards made again from the recipe, where their binary already sits, each checked before it is
    named: a shard that does not hash as the recipe says is removed and said."""
    doc = load(recipe_path(q, name), {}) or {}
    if not doc:
        raise SystemExit("%s: no recipe" % name)
    tg = targets(q)
    store = tg.get(doc["store"])
    rows = [r for r in doc["shards"] if not seeds or r["seed0"] in seeds]
    said = []
    for row in rows:
        places = [(h, b, w) for h, b, w in (doc["binaries"].get(row["binary"]) or {}).get("runs_at", []) if h in tg]
        if not places:
            said.append("%d: no machine holds its binary beside a checkout" % row["seed0"])
            continue
        host, binp, wt = next((p for p in places if p[0] == row["host"]), places[0])
        part = "$HOME/fleet/%s/shards/%d.bin.part" % (name, row["seed0"])
        rec = RECORD % {"wt": wt.replace("~", "$HOME"), "out": "/tmp/rerecord-%s-%d.bin" % (name, row["seed0"]), "s0": row["seed0"],
                        "n": row["seeds"], "secs": doc["secs"], "threads": "$(nproc 2>/dev/null || sysctl -n hw.ncpu)", "bin": binp.replace("~", "$HOME")}
        tmp = "/tmp/rerecord-%s-%d.bin" % (name, row["seed0"])
        if tg.get(host) == store:
            cmd = "mkdir -p $HOME/fleet/%s/shards && %s && mv %s %s && %s" % (name, rec, tmp, part, SHA % (part, part))
            r = on(store, cmd, 3600)
        else:
            r1 = on(tg.get(host), rec, 3600)
            src = ("cat %s" % tmp) if tg.get(host) is None else "ssh %s %s" % (tg[host], shlex.quote("cat " + tmp))
            pipe = "%s | ssh %s %s" % (src, store, shlex.quote("mkdir -p ~/fleet/%s/shards && cat > %s && %s" % (name, part, SHA % (part, part))))
            r = subprocess.run(["sh", "-c", pipe], capture_output=True, text=True, timeout=3600) if r1.returncode == 0 else r1
            on(tg.get(host), "rm -f " + tmp, 60)
        got = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        if got == row["sha256"]:
            on(store, "mv %s $HOME/fleet/%s/shards/%d.bin" % (part, name, row["seed0"]), 60)
            said.append("%d: made on %s, equal" % (row["seed0"], host))
        else:
            on(store, "rm -f " + part, 60)
            said.append("%d: made on %s, DIFFERENT (%s), removed" % (row["seed0"], host, got[:12]))
    say_event(q, did="rerecorded", run=name, shards=len(rows), said=said[:20])
    print("\n".join(said) or "nothing asked")


# ---- the reader -----------------------------------------------------------------------------
#
# Paul chose "Shard reader in orrery" (4 November): open a shard, pick a seed and a tank, and step
# through its senses and the bot's choices. A TCBC2 or TCBC3 sample carries its seed but NOT ITS SEAT
# OR ITS TICK: the recorder writes, at each decision tick, the living seats in order. So a tank is
# followed by where it is -- the instruments' X and Y, the senses at AT_NAV -- each sample joined to
# the nearest tank not yet seen in this round, a round ending when the nearest is one already seen. A
# respawn far from where the tank died is a new track. It is a reconstruction and the page says so; a
# format with the seat and the tick in each sample would make it exact, and is not built.

EXTRACT = r"""
import struct, sys
f = open(sys.argv[1], 'rb'); seed = int(sys.argv[2])
h = f.read(16); senses, heads = struct.unpack('<II', h[8:16]); m = 3 if h[:5] == b'TCBC2' else 4
rec = senses * 4 + heads + m + 4
sys.stdout.buffer.write(h)
while True:
    b = f.read(rec * 4096)
    if not b: break
    for i in range(0, len(b) - rec + 1, rec):
        if struct.unpack_from('<I', b, i + rec - 4)[0] == seed:
            sys.stdout.buffer.write(b[i:i + rec])
"""


def sense_names(commit, n):
    """A name for each of n senses, from senses.rs at the recording's commit: the compass's sectors and
    channels, the instruments, the periscope, the shell and the air; the rest by group and index."""
    src = subprocess.run(["git", "-C", TC, "show", "%s:source/treadcore-brain/src/senses.rs" % commit], capture_output=True, text=True).stdout

    def enum(name):
        m = re.search(r"pub enum %s \{(.*?)\n\}" % name, src, re.S)
        return re.findall(r"^\s+([A-Z]\w*),?\s*$", m.group(1), re.M) if m else []

    def const(name, d):
        m = re.search(r"pub const %s: usize = ([^;]+);" % name, src)
        try:
            return int(eval(m.group(1), {"__builtins__": {}}, {})) if m else d
        except Exception:
            return d
    sectors, chans = const("SECTORS", 8), enum("Channel")
    names = ["s%d %s" % (k, c) for k in range(sectors) for c in (chans or ["ch%d" % i for i in range(const("CHANNELS", 11))])]
    names += ["body %d" % i for i in range(const("BODY", 12))]
    names += ["nav " + x for x in (enum("Nav") or ["%d" % i for i in range(6)])]
    names += ["contact " + x for x in (enum("Contact") or [])]
    names += ["hint %d" % i for i in range(const("HINTS", 9))]
    names += ["shell " + x for x in enum("ShellContact")] + ["air " + x for x in enum("AirContact")]
    names += ["econ %d" % i for i in range(max(0, n - len(names)))]
    return names[:n]


def read(q, name, seed):
    doc = load(recipe_path(q, name), {}) or {}
    tg = targets(q)
    found = [r for r in scan(q) if r["run"] == name and r["shards"]]
    row = next((r for r in doc.get("shards", []) if r["seed0"] <= seed < r["seed0"] + (r["seeds"] or 1)), None)
    if not row and found:
        # A run without a recipe: its shards are named by their first seed.
        out = on(tg.get(found[0]["host"]), "ls $HOME/fleet/%s/shards" % name, 60).stdout.split()
        s0s = sorted(int(f[:-4]) for f in out if f.endswith(".bin") and f[:-4].isdigit())
        s0 = max([x for x in s0s if x <= seed] or [None]) if s0s else None
        row = {"seed0": s0} if s0 is not None else None
    if not row:
        raise SystemExit("%s: no shard holds seed %d" % (name, seed))
    script = "python3 -c %s" % shlex.quote(EXTRACT)
    if found:
        store = tg.get(found[0]["host"])
        r = subprocess.run(["sh", "-c", "%s" % ("ssh -o BatchMode=yes %s %s" % (store, shlex.quote("%s $HOME/fleet/%s/shards/%d.bin %d" % (script, name, row["seed0"], seed))) if store else
                                                  "%s $HOME/fleet/%s/shards/%d.bin %d" % (script, name, row["seed0"], seed))], capture_output=True, timeout=600)
        where = "the store's shard"
    else:
        # Dropped: the shard made again from the recipe where its binary sits, read, and deleted.
        places = [(h, b, w) for h, b, w in (doc["binaries"].get(row["binary"]) or {}).get("runs_at", []) if h in tg]
        if not places:
            raise SystemExit("%s: its shards are dropped and no machine holds the binary to make them again" % name)
        host, binp, wt = next((p for p in places if p[0] == row["host"]), places[0])
        tmp = "/tmp/recordings-read-%s-%d.bin" % (name, row["seed0"])
        rec = RECORD % {"wt": wt.replace("~", "$HOME"), "out": tmp, "s0": row["seed0"], "n": row["seeds"], "secs": doc["secs"],
                        "threads": "$(nproc 2>/dev/null || sysctl -n hw.ncpu)", "bin": binp.replace("~", "$HOME")}
        cmd = "%s; %s %s %d; rm -f %s" % (rec, script, tmp, seed, tmp)
        t = tg.get(host)
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", t, cmd] if t else ["sh", "-c", cmd], capture_output=True, timeout=3600)
        where = "shard %d re-recorded on %s from the recipe, read, and deleted" % (row["seed0"], host)
    b = r.stdout
    if len(b) < 16 or not b.startswith(b"TCBC"):
        raise SystemExit("%s: the read failed: %s" % (name, r.stderr.decode(errors="replace")[-300:]))
    fmt = b[:5].decode()
    senses, heads = struct.unpack("<II", b[8:16])
    m = 3 if fmt == "TCBC2" else 4
    rec = senses * 4 + heads + m + 4
    n = (len(b) - 16) // rec
    at_nav = None
    names = sense_names(doc.get("commit") or "HEAD", senses)
    at_nav = next((i for i, x in enumerate(names) if x == "nav X"), 100)
    samples, xs = [], array.array("f")
    for i in range(n):
        o = 16 + i * rec
        xs.frombytes(b[o:o + senses * 4])
        lab = list(b[o + senses * 4:o + senses * 4 + heads])
        mk = list(b[o + senses * 4 + heads:o + senses * 4 + heads + m])
        samples.append([round(xs[i * senses + at_nav], 4), round(xs[i * senses + at_nav + 1], 4)] + lab + mk)
    tracks, last, used, rounds = [], [], set(), 1
    tr_of = []
    for i, smp in enumerate(samples):
        x, y = smp[0], smp[1]
        dist = lambda k: math.hypot(last[k][0] - x, last[k][1] - y)
        free = [k for k in range(len(tracks)) if k not in used]
        k = min(free, key=dist, default=None)
        if k is None or dist(k) > 0.03:
            seen = min(used, key=dist, default=None)
            if seen is not None and dist(seen) <= 0.03:
                used, rounds = set(), rounds + 1
                free = list(range(len(tracks)))
                k = min(free, key=dist)
            else:
                tracks.append([])
                last.append((x, y))
                k = len(tracks) - 1
        tracks[k].append(i)
        last[k] = (x, y)
        used.add(k)
        tr_of.append(k)
    base = os.path.join(q, "plan", "recordings-read")
    with open(base + ".bin.part", "wb") as f:
        xs.tofile(f)
    os.replace(base + ".bin.part", base + ".bin")
    save(base + ".json", {"run": name, "seed": seed, "format": fmt, "senses": senses, "heads": heads, "masks": m, "n": n,
                          "names": names, "samples": samples, "tracks": tracks, "rounds": rounds, "bin": base + ".bin",
                          "where": where, "at": now(),
                          "heads_are": ["drive", "gun", "lead", "mortar", "drone", "squad", "signal"][:heads]})
    say_event(q, did="read", run=name, seed=seed, samples=n)
    print("%s seed %d: %d samples, %d tanks followed over about %d ticks (%s)" % (name, seed, n, len(tracks), rounds, where))


# ---- the page --------------------------------------------------------------------------------

def listing(q):
    """plan/recordings.json, what orrery's Recordings page draws: every run on a machine or in the
    archive, its size, whether its recipe is complete, who still reads it, and its mark."""
    runs = {}
    mk = marks(q).get("keep") or {}
    pr = planner_runs(q)
    for st in scan(q):
        r = runs.setdefault(st["run"], {"run": st["run"]})
        if st["shards"] or "host" not in r:
            r.update({"host": st["host"], "shards_now": st["shards"], "bytes_now": st["bytes"], "made": st["made"],
                      "format": st["format"], "senses": st["senses"]})
    for f in glob.glob(adir(q, "*", "recipe.json")):
        d = load(f, {}) or {}
        r = runs.setdefault(d.get("run"), {"run": d.get("run"), "shards_now": 0, "bytes_now": 0})
        ok, why = complete(d)
        r.update({"recipe": "complete" if ok else why, "shards": len(d.get("shards") or []), "seeds": d.get("seeds"),
                  "samples": d.get("samples"), "bytes": d.get("bytes"), "commit": (d.get("commit") or "")[:7],
                  "dropped": d.get("dropped"), "proofs": len([p for p in d.get("proofs", []) if p.get("equal")]),
                  "binaries": len(d.get("binaries") or {}), "source": d.get("source")})
        rows = d.get("shards") or []
        if rows:
            r["seed_lo"] = min(x["seed0"] for x in rows)
            r["seed_hi"] = max(x["seed0"] + (x.get("seeds") or 1) - 1 for x in rows)
        r.setdefault("made", d.get("made"))
        r.setdefault("format", d.get("format"))
        r.setdefault("senses", d.get("senses"))
    for name, r in runs.items():
        rid = (pr.get(name) or (None,))[0]
        if rid and not r.get("commit"):
            r["commit"] = (pr[name][1].get("commit") or "")[:7]
        if rid and not r.get("seed_lo"):
            st_, params = pr[name][1], pr[name][2]
            lo = int(params.get("seed0") or 0)
            r["seed_lo"], r["seed_hi"] = lo, int(st_.get("end") or lo + int(params.get("count") or 1)) - 1
        r["readers"] = readers(q, name, rid) if r.get("shards_now") else []
        r["kept"] = name in mk
        r["state"] = ("kept for analysis" if r["kept"] else "kept: every recording is" if keep_all(q) and r.get("shards_now")
                      else "read now" if r["readers"] else "on the store" if r.get("shards_now") else "recipe only")
    doc = {"at": now(), "keep_all": keep_all(q), "runs": sorted(runs.values(), key=lambda r: r.get("made") or "", reverse=True),
           "bytes_now": sum(r.get("bytes_now") or 0 for r in runs.values()),
           "bytes_recipe": sum(os.path.getsize(f) for f in glob.glob(adir(q, "bin", "*"))) if os.path.isdir(adir(q, "bin")) else 0}
    os.makedirs(os.path.join(q, "plan"), exist_ok=True)
    save(os.path.join(q, "plan", "recordings.json"), doc)
    for r in doc["runs"]:
        print("%-10s %-18s %6.1f GB now  %s" % (r["run"], r["state"], (r.get("bytes_now") or 0) / 1e9, r.get("recipe") or "no recipe"))
    return doc


def mark(q, name, keep):
    if not RUN_NAME.match(name):
        raise SystemExit("not a run name: %r" % name)
    p = os.path.join(q, "recordings.json")
    m = marks(q)
    k = m.setdefault("keep", {})
    if keep:
        k[name] = {"at": now()}
    else:
        k.pop(name, None)
    save(p, m)
    say_event(q, did="keep" if keep else "unkeep", run=name)
    listing(q)


def main(a):
    if len(a) < 2:
        print(__doc__)
        sys.exit(2)
    q, cmd, rest = os.path.abspath(a[0]), a[1], a[2:]
    if cmd == "list":
        listing(q)
    elif cmd == "recipe" and rest:
        d = recipe(q, rest[0])
        print("%s: %d shards, %d binaries; %s" % (rest[0], len(d["shards"]), len(d["binaries"]), complete(d)[1] or "complete"))
    elif cmd == "prove" and rest:
        prove(q, rest[0])
    elif cmd == "drop" and rest:
        drop(q, rest[0], "--do" in rest, without_recipe="--without-recipe" in rest)
        listing(q)
    elif cmd == "sweep":
        sweep(q, "--do" in rest)
    elif cmd in ("keep", "unkeep") and rest:
        mark(q, rest[0], cmd == "keep")
    elif cmd == "read" and len(rest) >= 2 and rest[1].isdigit():
        read(q, rest[0], int(rest[1]))
    elif cmd == "rerecord" and rest:
        rerecord(q, rest[0], {int(s) for s in rest[1:] if s.isdigit()})
        listing(q)
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
