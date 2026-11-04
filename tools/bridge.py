#!/usr/bin/env python3
"""bridge.py QUEUE status | ship LABEL -- a world milestone of crucible's islands shipped as the game's
Gladiator (treadcore style 17, nets/gladiator.bin).

Paul, 4 November: "yes do step 2, the duelist with world senses". The planner reads each new milestone in
the game against the shipped one (treadcore.py, bridge_jobs: two censuses on the same seeds, the candidate by
GLADIATOR=file) and flags the one that reads better by more than two errors. SHIPPING IS A COMMIT TO
TREADCORE, because the game carries its champion in its binary, so it is a person's press: this verb, or Ship
on Results, Growth. It never touches the Mac's checkout of treadcore, where a session's work may lie
uncommitted: it adds a worktree of origin/main, puts the milestone in nets/gladiator.bin and its row in
nets/styles.tsv, runs the styles tests there, commits, pushes to main, and removes the worktree. The fleet
builds the new commit as it builds every commit of main.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time

TC = os.path.expanduser("~/code/treadcore")
WORLD_BYTES = 5236 * 4


def load(p, d=None):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def git(*a, cwd=TC, check=True):
    r = subprocess.run(["git", "-C", cwd] + list(a), capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit("git %s: %s" % (" ".join(a), (r.stderr or r.stdout).strip()[-400:]))
    return r.stdout.strip()


def ship(q, label):
    if not re.match(r"^M\d{4}-[\w-]+-g\d+$", label):
        raise SystemExit("not a milestone's name: %r" % label)
    br = load(os.path.join(q, "plan", "bridge.json"), {}) or {}
    home = br.get("home") or "crucible-world-hybrid"
    src = os.path.join(q, home, "milestones", label + ".bin")
    if not os.path.exists(src) or os.path.getsize(src) != WORLD_BYTES:
        raise SystemExit("%s: no world champion of %d bytes in %s/milestones" % (label, WORLD_BYTES, home))
    read = next((r for r in reversed(br.get("reads", [])) if r.get("label") == label), None)
    said = ("read %+.2f +/- %.2f a seat over the shipped %s on %d seeds (bridge %d, %s)" % (read["diff"], read["se"], read["shipped"], read["seeds"], read["n"], read.get("on"))
            if read and read.get("diff") is not None else "not read by the bridge: shipped by hand")
    git("fetch", "-q", "origin", "main")
    wt = os.path.join(q, "plan", "bridge-ship")
    subprocess.run(["git", "-C", TC, "worktree", "remove", "--force", wt], capture_output=True)
    shutil.rmtree(wt, ignore_errors=True)
    git("worktree", "add", "-q", "--detach", wt, "origin/main")
    try:
        if "fn gladiator_file" not in open(os.path.join(wt, "source", "treadcore-brain", "src", "styles.rs")).read():
            raise SystemExit("main has no Gladiator yet (treadcore LR 138): nothing to ship into")
        shutil.copy(src, os.path.join(wt, "nets", "gladiator.bin"))
        tsv = os.path.join(wt, "nets", "styles.tsv")
        rows = [l for l in open(tsv).read().splitlines() if not l.startswith("nets/gladiator.bin\t")]
        rows.append("nets/gladiator.bin\t17 Gladiator\tcrucible world milestone %s, shipped %s by orrery's bridge\t%s; 5,236 floats, 55-48-48-4"
                    % (label, time.strftime("%d %B %Y"), said))
        with open(tsv, "w") as f:
            f.write("\n".join(rows) + "\n")
        env = dict(os.environ, CARGO_TARGET_DIR=os.path.join(TC, "target"))
        t = subprocess.run(["cargo", "test", "-q", "-p", "treadcore-brain", "--release", "--lib", "styles"], cwd=wt, env=env,
                           capture_output=True, text=True, timeout=3600)
        if t.returncode != 0:
            raise SystemExit("the styles tests failed with %s: %s" % (label, (t.stdout + t.stderr)[-600:]))
        git("add", "nets/gladiator.bin", "nets/styles.tsv", cwd=wt)
        git("commit", "-q", "-m", "Gladiator: %s ships as style 17, crucible's world champion in every fight\n\n%s.\nPressed on orrery's bridge (tools/bridge.py ship), from QUEUE/%s/milestones." % (label, said[0].upper() + said[1:], home), cwd=wt)
        sha = git("rev-parse", "--short", "HEAD", cwd=wt)
        git("push", "-q", "origin", "HEAD:refs/heads/main", cwd=wt)
    finally:
        subprocess.run(["git", "-C", TC, "worktree", "remove", "--force", wt], capture_output=True)
        shutil.rmtree(wt, ignore_errors=True)
    with open(os.path.join(q, "events.jsonl"), "a") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": "bridge", "did": "shipped", "label": label, "commit": sha}) + "\n")
    print("%s shipped as the Gladiator at %s, pushed to main; the fleet builds it next" % (label, sha))


def main(a):
    if len(a) < 2:
        print(__doc__)
        sys.exit(2)
    q, cmd = os.path.abspath(a[0]), a[1]
    if cmd == "status":
        print(json.dumps(load(os.path.join(q, "plan", "bridge.json"), {}), indent=1))
    elif cmd == "ship" and len(a) > 2:
        ship(q, a[2])
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
