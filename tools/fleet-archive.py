#!/usr/bin/env python3
"""fleet-archive.py QUEUE snapshot|list|verify|pack -- the training record, kept.

Paul, 1 November: "I want to store all this training information. Github or maybe burned
compressed media. I want snapshots and generations."

TWO THINGS, BECAUSE THEY ARE DIFFERENT SIZES AND DIFFERENT USES:

    A GENERATION is small text: what the brain became and the evidence for it. One a promotion.
    It diffs, so it belongs in git. `snapshot` writes one for every promotion not yet recorded:
    QUEUE/archive/generations/NNNN-rXXXX/ with the values changed, the evidence, the test log's
    verdict, the families, the commit, and the settings the run had (tuning.json, plan.json).

    A SNAPSHOT is everything else, raw: results, logs, the GPU champions, the ledgers. Gigabytes
    of logs that compress ten to one and that nobody greps until the day they must. `pack` writes
    QUEUE/archive/packs/PACK-NNN.tar.xz of what no earlier pack holds, cut to fit one disc, and
    MANIFEST.tsv says which file went in which pack, with its sha256, so a disc can be checked
    alone, decades on, with nothing but sha256sum and tar.

NOTHING IS DELETED AND NOTHING IS SENT. Moving these to GitHub or burning them is a person's act:
see docs/whole-line-lab-report.md. `verify` reads every pack back against its manifest.
"""
import hashlib
import io
import json
import lzma
import os
import shutil
import sys
import tarfile
import time

# A disc's use, leaving room for the filesystem: BD-R 25 GB, and M-DISC BD-R at the same size.
DISC_BYTES = {"bd25": 23 * 10 ** 9, "bd50": 46 * 10 ** 9, "dvd": 4 * 10 ** 9}
# What a snapshot holds, relative to the queue. plan/ is the ledgers and the fit's inputs.
RAW = ("results", "logs", "done", "failed", "stopped", "crucible", "crucible-hybrid", "models", "patches", "plan", "flags", "runs")
LOOSE = ("events.jsonl", "config.json", "plan.json", "tuning.json", "keeper.log")


def load(p, default=None):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def promotions(q):
    """[(run id, its run file, its state)] of every promotion asked for, oldest first."""
    out = []
    runs = os.path.join(q, "runs")
    for fn in sorted(os.listdir(runs)):
        r = load(os.path.join(runs, fn), {}) or {}
        if r.get("kind") == "promote":
            rid = fn[:-5]
            out.append((rid, r, load(os.path.join(q, "plan", "runs", rid, "state.json"), {}) or {}))
    return out


def snapshot(q):
    """A generation for each promotion that became one, and a line for each that failed: a
    failure is half of what a record is for."""
    home = os.path.join(q, "archive", "generations")
    os.makedirs(home, exist_ok=True)
    families = load(os.path.join(q, "plan", "families.json"), {}) or {}
    n, wrote = 0, 0
    rows = []
    for rid, r, st in promotions(q):
        ok = st.get("status") in ("approved", "self-modified")
        name = (r.get("params") or {}).get("candidate", "")
        rows.append({"run": rid, "asked": r.get("asked"), "candidate": name, "status": st.get("status"), "why": st.get("why", ""), "commit": st.get("commit", ""), "changed": st.get("changed", [])})
        if not ok:
            continue
        n += 1
        d = os.path.join(home, "%04d-%s" % (n, rid))
        if os.path.isdir(d):
            continue
        os.makedirs(d)
        wrote += 1
        rec = {"generation": n, "run": rid, "candidate": name, "asked": r.get("asked"), "by": r.get("by"), "approved": st.get("approved"),
               "confirmed": st.get("confirmed"), "status": st.get("status"), "commit": st.get("commit"), "changed": st.get("changed", []),
               "evidence": st.get("evidence"), "families": (families.get(name) or {}).get("families", []), "written": time.strftime("%Y-%m-%dT%H:%M:%S")}
        with open(os.path.join(d, "generation.json"), "w") as f:
            json.dump(rec, f, indent=1, sort_keys=True)
            f.write("\n")
        src = os.path.join(q, "plan", "runs", rid, "promote.weights")
        if os.path.exists(src):
            shutil.copy(src, os.path.join(d, "promote.weights"))
    with open(os.path.join(q, "archive", "generations.json"), "w") as f:
        json.dump(rows, f, indent=1)
        f.write("\n")
    # What the run's settings and the search's ledgers are now: small, and they diff.
    now_ = os.path.join(q, "archive", "now")
    os.makedirs(now_, exist_ok=True)
    for rel in ("tuning.json", "plan.json", "plan/ledger-all.tsv", "plan/history.tsv", "plan/pipeline.json", "crucible-hybrid/lineage.tsv"):
        p = os.path.join(q, rel)
        if os.path.exists(p):
            shutil.copy(p, os.path.join(now_, rel.replace("/", "-")))
    print("%d generations recorded, %d new; %d promotions asked in all" % (n, wrote, len(rows)))


def walk_raw(q):
    for top in RAW:
        base = os.path.join(q, top)
        for root, dirs, files in os.walk(base):
            dirs.sort()
            for fn in sorted(files):
                yield os.path.relpath(os.path.join(root, fn), q)
    for fn in LOOSE:
        if os.path.exists(os.path.join(q, fn)):
            yield fn


def manifest(q):
    p = os.path.join(q, "archive", "packs", "MANIFEST.tsv")
    out = {}
    if os.path.exists(p):
        for l in open(p):
            pack, digest, size, rel = l.rstrip("\n").split("\t", 3)
            out[rel] = (pack, digest, int(size))
    return p, out


def pack(q, disc="bd25", limit_files=None):
    """What has changed since the last pack, into new packs that each fit one disc. Compressed
    size is unknown until written, so a pack closes at the disc's size of compressed output as
    counted by a writer in the middle; the check after it is a person's `verify`."""
    home = os.path.join(q, "archive", "packs")
    os.makedirs(home, exist_ok=True)
    mpath, have = manifest(q)
    todo = []
    for rel in walk_raw(q):
        p = os.path.join(q, rel)
        try:
            st = os.stat(p)
        except OSError:
            continue
        known = have.get(rel)
        # Same size and older than the pack holding it: a finished job's files do not change.
        if known and known[2] == st.st_size:
            continue
        todo.append(rel)
    if limit_files:
        todo = todo[:limit_files]
    if not todo:
        print("nothing new to pack")
        return
    nums = [int(f[5:8]) for f in os.listdir(home) if f.startswith("PACK-") and f.endswith(".tar.xz")]
    n = max(nums, default=0) + 1
    limit, i, raw = DISC_BYTES[disc], 0, 0
    t0 = time.time()
    while i < len(todo):
        name = "PACK-%03d.tar.xz" % n
        path = os.path.join(home, name)
        tmp = path + ".part"
        rows = []
        with lzma.open(tmp, "wb", preset=6) as xz, tarfile.open(fileobj=xz, mode="w") as tar:
            while i < len(todo) and os.path.getsize(tmp) < limit * 0.95:
                rel = todo[i]
                i += 1
                p = os.path.join(q, rel)
                # Read once, so that what is hashed is what is packed: the keeper may rewrite
                # plan/state.json between a look and a copy.
                try:
                    ti = tar.gettarinfo(p, arcname=rel)
                    with open(p, "rb") as f:
                        data = f.read()
                except OSError:
                    continue
                ti.size = size = len(data)
                digest = hashlib.sha256(data).hexdigest()
                tar.addfile(ti, io.BytesIO(data))
                rows.append("%s\t%s\t%d\t%s\n" % (name, digest, size, rel))
                raw += size
        os.replace(tmp, path)
        with open(mpath, "a") as m:
            m.writelines(rows)
        print("%s: %d files, %.0f MB on disc" % (name, len(rows), os.path.getsize(path) / 1e6))
        n += 1
    print("%.0f MB of raw record in %.0f s" % (raw / 1e6, time.time() - t0))


def verify(q):
    """Every file of every pack, read back from the pack and hashed against the manifest."""
    home = os.path.join(q, "archive", "packs")
    _, have = manifest(q)
    by = {}
    for rel, (pk, digest, size) in have.items():
        by.setdefault(pk, {})[rel] = digest
    bad = 0
    for pk in sorted(by):
        seen = 0
        with tarfile.open(os.path.join(home, pk), "r:xz") as tar:
            for m in tar:
                if not m.isfile() or m.name not in by[pk]:
                    continue
                h = hashlib.sha256()
                f = tar.extractfile(m)
                for b in iter(lambda: f.read(1 << 20), b""):
                    h.update(b)
                seen += 1
                if h.hexdigest() != by[pk][m.name]:
                    bad += 1
                    print("BAD %s %s" % (pk, m.name))
        print("%s: %d files read back" % (pk, seen))
    print("%d files differ" % bad)
    sys.exit(1 if bad else 0)


def listing(q):
    rows = load(os.path.join(q, "archive", "generations.json"), []) or []
    for r in rows:
        print("%-6s %-16s %-14s %-14s %s" % (r["run"], (r.get("asked") or "")[:16], r.get("candidate", "")[:14], r.get("status"), (r.get("changed") or [""])[0][:44]))
    home = os.path.join(q, "archive", "packs")
    if os.path.isdir(home):
        for f in sorted(os.listdir(home)):
            print("%s %.1f MB" % (f, os.path.getsize(os.path.join(home, f)) / 1e6))


def main(a):
    if len(a) < 2:
        sys.exit(__doc__)
    q, cmd = os.path.abspath(a[0]), a[1]
    if cmd == "snapshot":
        snapshot(q)
    elif cmd == "pack":
        pack(q, a[2] if len(a) > 2 else "bd25")
    elif cmd == "verify":
        verify(q)
    elif cmd == "list":
        listing(q)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
