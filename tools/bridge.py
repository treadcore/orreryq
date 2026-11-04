#!/usr/bin/env python3
"""bridge.py QUEUE status | ship LABEL | ship-clone N -- a world milestone of crucible's islands shipped as the game's
Gladiator (treadcore style 17, nets/gladiator.bin).

Paul, 4 November: "yes do step 2, the duelist with world senses". The planner reads each new milestone in
the game against the shipped one (treadcore.py, bridge_jobs: two censuses on the same seeds, the candidate by
GLADIATOR=file) and ships the one that reads better by more than two errors. SHIPPING IS A COMMIT TO
TREADCORE, because the game carries its champion in its binary: in auto mode with the push allowed the
planner runs this verb itself, as a promotion commits itself (Paul, 4 November: "Ship itself in auto mode");
otherwise it is a person's press, this verb or Ship on Results, Growth. It never touches the Mac's checkout of treadcore, where a session's work may lie
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


def ship_file(q, src, dest, row, message, edit=None, dry=False):
    """A file into treadcore's nets/ on a worktree of origin/main: its row in nets/styles.tsv, the styles
    tests, a commit, a push; `edit(wt)` may change the source first (the clone's first ship points style 6
    at its file). The Mac's own checkout is never touched."""
    git("fetch", "-q", "origin", "main")
    wt = os.path.join(q, "plan", "ship-worktree")
    subprocess.run(["git", "-C", TC, "worktree", "remove", "--force", wt], capture_output=True)
    shutil.rmtree(wt, ignore_errors=True)
    git("worktree", "add", "-q", "--detach", wt, "origin/main")
    try:
        if edit:
            edit(wt)
        shutil.copy(src, os.path.join(wt, "nets", dest))
        tsv = os.path.join(wt, "nets", "styles.tsv")
        rows = [l for l in open(tsv).read().splitlines() if not l.startswith("nets/%s\t" % dest)]
        rows.append(row)
        with open(tsv, "w") as f:
            f.write("\n".join(rows) + "\n")
        env = dict(os.environ, CARGO_TARGET_DIR=os.path.join(TC, "target"))
        t = subprocess.run(["cargo", "test", "-q", "-p", "treadcore-brain", "--release", "--lib", "styles"], cwd=wt, env=env,
                           capture_output=True, text=True, timeout=3600)
        if t.returncode != 0:
            raise SystemExit("the styles tests failed: %s" % (t.stdout + t.stderr)[-600:])
        git("add", "-A", "nets/%s" % dest, "nets/styles.tsv", "source/treadcore-brain/src/styles.rs", cwd=wt)
        if dry:
            print("dry: the tests pass; would commit:\n%s\n%s" % (git("diff", "--cached", "--stat", cwd=wt), message))
            return None
        git("commit", "-q", "-m", message, cwd=wt)
        sha = git("rev-parse", "--short", "HEAD", cwd=wt)
        git("push", "-q", "origin", "HEAD:refs/heads/main", cwd=wt)
    finally:
        subprocess.run(["git", "-C", TC, "worktree", "remove", "--force", wt], capture_output=True)
        shutil.rmtree(wt, ignore_errors=True)
    return sha


def event(q, **kw):
    with open(os.path.join(q, "events.jsonl"), "a") as f:
        f.write(json.dumps(dict({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": "bridge"}, **kw)) + "\n")


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

    def has_gladiator(wt):
        if "fn gladiator_file" not in open(os.path.join(wt, "source", "treadcore-brain", "src", "styles.rs")).read():
            raise SystemExit("main has no Gladiator yet (treadcore LR 138): nothing to ship into")
    sha = ship_file(q, src, "gladiator.bin",
                    "nets/gladiator.bin\t17 Gladiator\tcrucible world milestone %s, shipped %s by orrery's bridge\t%s; 5,236 floats, 55-48-48-4" % (label, time.strftime("%d %B %Y"), said),
                    "Gladiator: %s ships as style 17, crucible's world champion in every fight\n\n%s.\nShipped by orrery's bridge (tools/bridge.py ship), from QUEUE/%s/milestones." % (label, said[0].upper() + said[1:], home),
                    edit=has_gladiator)
    event(q, did="shipped", label=label, commit=sha)
    print("%s shipped as the Gladiator at %s, pushed to main; the fleet builds it next" % (label, sha))


def ship_clone(q, n):
    """Clone round n's net into nets/scholar.bin, style 6's file: the first such ship also points style 6
    at it (until then style 6 is nets/bc2.bin), in the same commit and under the same tests."""
    cl = load(os.path.join(q, "plan", "clone.json"), {}) or {}
    r = next((x for x in reversed(cl.get("rounds", [])) if x.get("n") == n), None)
    if not r or not r.get("cand") or not os.path.exists(r["cand"]):
        raise SystemExit("clone %d: no judged round with its net here" % n)
    said = ("read %+.2f +/- %.2f a seat over the shipped Scholar (%s) on the same seeds; the gauntlet %s" % (
        r["diff"], r["se"], r.get("scholar"), "worse on " + "; ".join(r["gauntlet_worse"]) if r.get("gauntlet_worse") else "holds")
        if r.get("diff") is not None else "not judged")

    def point_style_6(wt):
        p = os.path.join(wt, "source", "treadcore-brain", "src", "styles.rs")
        s = open(p).read()
        s2 = re.sub(r'(name: "Scholar".*?nets/)[\w.-]+\.bin', r"\1scholar.bin", s, count=1)
        if s2 != s:
            open(p, "w").write(s2)
    sha = ship_file(q, r["cand"], "scholar.bin",
                    "nets/scholar.bin\t6 Scholar\tthe rules at %s cloned on the GPU (orrery clone %d), shipped %s\t%s" % (r.get("commit"), n, time.strftime("%d %B %Y"), said),
                    "Scholar: clone %d of the rules at %s ships as style 6\n\n%s.\nCloned and judged by orrery's clone stage (tools/bridge.py ship-clone)." % (n, r.get("commit"), said[0].upper() + said[1:]),
                    edit=point_style_6)
    event(q, did="clone shipped", n=n, commit=sha)
    print("clone %d shipped as the Scholar at %s, pushed to main" % (n, sha))


def main(a):
    if len(a) < 2:
        print(__doc__)
        sys.exit(2)
    q, cmd = os.path.abspath(a[0]), a[1]
    if cmd == "status":
        print(json.dumps(load(os.path.join(q, "plan", "bridge.json"), {}), indent=1))
    elif cmd == "ship" and len(a) > 2:
        ship(q, a[2])
    elif cmd == "ship-clone" and len(a) > 2 and a[2].isdigit():
        ship_clone(q, int(a[2]))
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
