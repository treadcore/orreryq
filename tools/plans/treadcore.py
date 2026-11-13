#!/usr/bin/env python3
"""orrery's plan for treadcore: what the fleet does for it, decided here
(treadcore LAB-REPORT-BRAIN.md 112 to 114).

    python3 -I tools/plans/treadcore.py QDIR plan N     up to N new jobs, as JSON
    python3 -I tools/plans/treadcore.py QDIR collect    what the finished jobs found
    python3 -I tools/plans/treadcore.py QDIR judged ID  (on_done of a judge job)
    python3 -I tools/plans/treadcore.py QDIR families   the families' verdicts so far
    python3 -I tools/plans/treadcore.py QDIR sync       every machine's ledger, one table
    python3 -I tools/plans/treadcore.py QDIR chores     the housekeeping: what is stale, begun (the keeper, each minute)
    python3 -I tools/plans/treadcore.py QDIR now        do it now: sync, then promote or re-read

tools/fleet-queue.py is the engine (jobs, lanes, the keeper, stops); this
file is the plan it calls for treadcore. treadcore keeps only the work:
how one census plays (scripts/census.sh), the brain's tests, the ledger and
the fit (scripts/ledger.py, scripts/suggest.py), the trainer (tools/bc).
Everything that decides what runs where, and gathers what came back, is
here.

THE NEWEST COMMIT. plan.json's "commit" is a ref ("origin/main") or a hash.
A ref is read again at each top-up, after a fetch, so the fleet follows
what the coordinator pushed. Each host builds each commit once, in its own
folder (~/fleet/q-NAME/c/SHORT/: a worktree, the census binary, the
defaults); new jobs use the newest, and a job runs on the build it was
planned with. Before building, a host fast-forwards its own checkout
(~/code/treadcore) when it is clean and on main.

PUSH PERMISSION. A template's plan.json names the remote and branch a
promotion lands on ("push": {"remote": "origin", "branch": "main"}), and the
coordinator must be able to push there: Approve is a push. It is checked by
a dry-run push at each sync and before every promotion and approval
(plan/push.json; `push-check`); without it no promotion starts.

FOUR KINDS OF WORK share the one queue:

- weights: the scripted brain's named weights (weights.rs), a census trial
  each, picked by scripts/suggest.py from the ledger: the queue's own
  censuses and the fleet's history (plan.json "history"), only those read
  with the same weights.rs, the same seconds and map, 55 seeds or more. A
  trial past two errors above the defaults, no map past two below, is read
  twice on held-out seeds.
- families: a candidate's weights over every family of scenarios/families/,
  each held to its floor: the defaults, then candidates that passed both
  held-out reads (this queue's, then each converge run's, newest first);
  8 a job, side by side.
- net: the learned tank, a round trained on the GPU machine and judged by
  one census machine's census against the best. The official net changes
  only when Paul says.
- prepare: a host's build of a commit, before any of the above on it.

SYNC. `sync` reads every machine's own censuses with scripts/ledger.py ON
that machine (each row keeps its binary's hash), copies each machine's
converge runs' records (not their binaries), and joins every table with
the queues' ledgers into one (ledger.py --merge): build/ledger/fleet.tsv.
The keeper runs it on its own clock (config.json "sync"), so nothing is
gathered by hand.
"""
import base64
import contextlib
import csv
import math
import random
import shlex
import glob
import hashlib
import importlib.util
import json
import os
import re
import shutil
import statistics as st
import struct
import subprocess
import sys
import time

SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
# A fetched census's commit and its one-map verdict, read once a process (a pass): they do not change.
_COMMITS, _ONE_MAP = {}, {}
# Read once a process too: a census pooled (its files are fetched once and kept), and weights.rs's blob
# at a commit named by its hash (a commit is what it is; a branch's name is not memoised).
_POOLS, _BLOBS = {}, {}
# Whether a census dir holds trial.weights, for the dirs census-dirs.json keeps (a finished job's).
_TRIAL_W = {}


def has_trial(d):
    """trial.weights in a census dir: from census-dirs.json for a finished job's, else looked at."""
    if d in _TRIAL_W:
        return _TRIAL_W[d]
    return os.path.exists(os.path.join(d, "trial.weights"))


def keep_cache(p, v):
    """A cache's file, written under a name of this process's own and then put in place: two planners
    at once (a pass, and a button's command) each leave a whole file, the last one's, and neither dies
    on the other's rename (the keeper's flags of 8 November). A cache not kept is made again."""
    tmp = "%s.%d.tmp" % (p, os.getpid())
    try:
        with open(tmp, "w") as f:
            json.dump(v, f, separators=(",", ":"))
        os.replace(tmp, p)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


def cache_due(p, fresh, dropped):
    """Whether a cache's file is written now: something gone from it, fifty entries new, or ten
    minutes since it was. Its writing was a second and a half a pass, 11 MB for a job or two, and what
    is not written is only read again at the next pass."""
    try:
        aged = time.time() - os.stat(p).st_mtime > 600
    except OSError:
        aged = True
    return bool(dropped or fresh >= 50 or (fresh and aged))


def names_in(d):
    """The names in a directory that a glob's * gives (no dot names), and whether one of them is a
    directory; None when the directory is not there."""
    try:
        with os.scandir(d) as it:
            out, nested = [], False
            for e in it:
                if e.name.startswith("."):
                    continue
                out.append(e.name)
                nested = nested or e.is_dir()
            return out, nested
    except (FileNotFoundError, NotADirectoryError):
        return None


def load(p, default=None):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(p, v, compact=False):
    # The temp file is this process's own, as keep_cache's is. A pass and the sync both keep plan/push.json, and
    # with one shared name the second to rename found its file gone and the pass died (12 November, 01:16 and
    # 15:12, each in the second a sync ended). WORSE THAN THE CRASH, the two had opened one file to write: the
    # rename that won could put a mixture of both in place. Now each leaves a whole file, and the last one stands.
    tmp = "%s.%d.tmp" % (p, os.getpid())
    with open(tmp, "w") as f:
        # Compact for what a screen reads each minute and no person does: the Timeline's bins,
        # indented, are an array a line and more than doubled pipeline.json.
        json.dump(v, f, separators=(",", ":")) if compact else json.dump(v, f, indent=1)
    os.replace(tmp, p)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def env_file(p):
    out = {}
    try:
        for l in open(p):
            if "=" in l:
                k, v = l.rstrip("\n").split("=", 1)
                out[k] = v.strip("'\"")
    except OSError:
        pass
    return out


def parse_weights(text):
    """name = number lines of a weights file (caps and comments left out)."""
    out = {}
    for l in text.splitlines():
        l = l.split("#")[0].strip()
        m = re.match(r"^([a-z_][a-z0-9_]*)\s*=\s*([-+0-9.eE]+)$", l)
        if m:
            out[m.group(1)] = float(m.group(2))
    return out


def changed_vars(lines):
    """set-defaults.py's "name old -> new" lines as ticker vars; the
    Tactics::default() echo lines (and any old value that is an expression,
    DIRECT_RANGE - 1.0) are left out rather than read."""
    out = {}
    for l in lines:
        m = re.match(r"^([a-z_][a-z0-9_]*) ([-+0-9.eE]+) -> ([-+0-9.eE]+)$", l.strip())
        if m and not l.startswith(" "):
            out[m.group(1)] = {"value": float(m.group(3)), "offset": round(float(m.group(3)) - float(m.group(2)), 4)}
    return out


def short_moved(text, room=60):
    """A trial's weights for a job's title: whole names, "+N more" past the room."""
    parts = [l.split("#")[0].strip().replace(" = ", " ") for l in text.splitlines() if "=" in l.split("#")[0]]
    out = []
    for i, p in enumerate(parts):
        if len(", ".join(out + [p])) > room:
            return ", ".join(out) + ", +%d more" % (len(parts) - i)
        out.append(p)
    return ", ".join(out)


def github_web(url):
    """A remote's web page on GitHub, from any of the ways git spells it
    (git@github.com:o/r.git, ssh://git@ssh.github.com:443/o/r.git,
    https://github.com/o/r), or "" for a remote that is not GitHub."""
    m = re.search(r"github\.com[:/](?:\d+/)?([^/]+)/([^/]+?)(?:\.git)?/?$", url or "")
    return "https://github.com/%s/%s" % m.groups() if m else ""


def write_tsv(path, rows):
    if not rows:
        return False
    with open(path + ".tmp", "w") as f:
        w = csv.DictWriter(f, list(rows[0].keys()), delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    os.replace(path + ".tmp", path)
    return True


class Plan:
    def __init__(self, qdir):
        self.q = os.path.abspath(qdir)
        self.name = os.path.basename(self.q.rstrip("/"))
        self.cfg = load(os.path.join(self.q, "plan.json"), {})
        self._ranges = None
        self.qcfg = load(os.path.join(self.q, "config.json"), {})
        # treadcore's machines; a GPU machine's crucible lane (caps
        # ["cuda"], named NAME-cuda) is the same machine again, and builds
        # nothing of treadcore's.
        every = self.qcfg.get("hosts", [])
        # A machine a person set aside (paused, or the project off for it, on
        # the Machines page) is planned for like one that is not there: no build
        # waits for it and no promotion counts it. Its ledger still counts:
        # self.ledgers is every machine that has one, or a removal would shrink
        # fleet.tsv.
        self.ledgers = [h for h in every + self.qcfg.get("bench", []) if "cuda" not in h.get("caps", ["cpu"])]
        stopped = set(self.qcfg.get("paused_projects", []))
        self.paused_projects = stopped
        self.hosts = [h for h in every if "cpu" in h.get("caps", ["cpu"]) and not h.get("paused")
                      and "treadcore" not in stopped | set(h.get("off", []))]
        self.cuda = [h for h in every if "cuda" in h.get("caps", []) and not h.get("paused")
                     and "crucible" not in stopped | set(h.get("off", []))]
        self.tc = os.path.expanduser(self.cfg.get("project", "~/code/treadcore"))
        self.pd = os.path.join(self.q, "plan")
        os.makedirs(self.pd, exist_ok=True)
        self.state = load(os.path.join(self.pd, "state.json"), {})
        for k, v in (("weights_n", 0), ("gen", 0), ("held_n", 0), ("round", 0), ("held_read", []),
                     ("families_n", 0), ("families_queued", []), ("commits", {})):
            self.state.setdefault(k, v)
        self.home = "fleet/q-%s" % self.name  # under each host's $HOME
        self.tuned = {}
        self.apply_tuning()
        self._sha = None
        self._rsaves = {}
        self._newruns = []

    # ---- the values a person can move ------------------------------------------------------
    # Paul, 1 November: "set some values that we can adjust ... apply them to the run". The list,
    # with each one's range and default, is line.json, which orrery's Values page and the report
    # read too. What has been moved is QUEUE/tuning.json, written by `fleet-queue.py DIR tune`.
    # A MISSING OR BROKEN FILE IS THE DEFAULTS, NEVER A STOPPED PLAN, and a number is held to its
    # range here as well as at the button: the file can be edited by hand.
    def apply_tuning(self):
        table = load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "line.json"), {}) or {}
        self.line = table
        asked = load(os.path.join(self.q, "tuning.json"), {}) or {}
        asked = asked if isinstance(asked, dict) else {}
        for v in table.get("values", []):
            val = asked.get(v["key"], v["default"])
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                val = v["default"]
            val = max(v["min"], min(v["max"], val))
            if v["key"] in asked:
                self.tuned[v["key"]] = val
            if v.get("attr"):
                setattr(self, v["attr"], type(v["default"])(val))
            elif v["key"] == "held_seeds" and self.cfg.get("weights") and v["key"] in asked:
                self.cfg["weights"]["held_seeds"] = int(val)

    def flag(self, kind, text, key=None, progress=False):
        """A flag for a person (fleet-queue's flags/, the same form): raised once a key.
        progress=True: news, shown and never waiting for anyone (a candidate)."""
        d = os.path.join(self.q, "flags")
        os.makedirs(d, exist_ok=True)
        key = key or "%s:%s" % (kind, text)
        f = self.flag_keys().get(key)
        if f:
            j = load(f, {}) or {}
            if j.get("key") == key:
                # One raised before candidates were news: it becomes news.
                if progress and not j.get("progress"):
                    j["progress"] = True
                    save(f, j)
                return
        fid = "%d-%s" % (int(time.time() * 1000), kind)
        f = os.path.join(d, fid + ".json")
        save(f, {"id": fid, "t": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind, "text": text, "key": key,
                 "ack": None, "progress": bool(progress)})
        self._flag_keys[key] = f

    def flag_keys(self):
        """{key: file} of every flag, read once a pass. flag() read all 1,171 of them each time it was
        asked, 188 times a pass (8 November); a key raised stays raised, so once a pass is enough,
        and flag() adds what it raises."""
        if self.__dict__.get("_flag_keys") is None:
            keys = {}
            for f in sorted(glob.glob(os.path.join(self.q, "flags", "*.json"))):
                j = load(f, {}) or {}
                if isinstance(j, dict) and j.get("key") and j["key"] not in keys:
                    keys[j["key"]] = f
            self._flag_keys = keys
        return self._flag_keys

    def keep(self):
        for rid, r in self._newruns:
            save(os.path.join(self.q, "runs", rid + ".json"), r)
        self._newruns = []
        save(os.path.join(self.pd, "state.json"), self.state)
        for rid, st in self._rsaves.items():
            save(os.path.join(self.rdir(rid), "state.json"), st)
        self._rsaves = {}

    def ids(self, *subs):
        """The job ids in the queue's directories (queue, running, done, failed, stopped).

        A DIRECTORY IS LISTED AGAIN ONLY WHEN IT CHANGED (8 November). done/ held 38,704 jobs and was
        globbed 73 times a pass, 45 of them by prepared(), eleven of the pass's seconds. A flat
        directory's own time moves whenever a job is moved in or out, so its ids are kept with that
        time and are never older than the directory; one with directories in it (running/, a lane
        each) is read each time, as before."""
        out = set()
        memo = self.__dict__.setdefault("_ids", {})
        for sub in subs:
            d = os.path.join(self.q, sub)
            try:
                before = os.stat(d).st_mtime_ns
            except OSError:
                continue
            hit = memo.get(sub)
            if hit and hit[0] == before:
                out |= hit[1]
                continue
            listed = names_in(d)
            if listed is None:
                continue
            names, nested = listed
            if nested:
                out |= {re.sub(r"^\d+-", "", os.path.basename(f))[:-5]
                        for f in glob.glob(os.path.join(d, "**", "*.json"), recursive=True)}
                continue
            got = {re.sub(r"^\d+-", "", n)[:-5] for n in names if n.endswith(".json")}
            try:
                if os.stat(d).st_mtime_ns == before:
                    memo[sub] = (before, got)
            except OSError:
                pass
            out |= got
        return out

    # ---- the commit -----------------------------------------------------------------
    def weights_rs(self, commit):
        # Asked 300 times a pass, a git process each (8 November): a commit named by its hash, short
        # (run.env's seven) or whole, has one blob; a branch's name moves and is asked each time.
        whole = isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{7,40}", commit)
        if whole and commit in _BLOBS:
            return _BLOBS[commit]
        r = run(["git", "-C", self.tc, "rev-parse", "%s:source/treadcore-brain/src/weights.rs" % commit])
        blob = r.stdout.strip() if r.returncode == 0 else ""
        if whole and r.returncode == 0:
            _BLOBS[commit] = blob
        return blob

    def defaults_at(self, commit):
        """The weights! table's defaults at a commit: {name: number}, read
        from git, cached by weights.rs's blob."""
        blob = self.weights_rs(commit)
        if not blob:
            return {}
        # "tables_caps": the tables read before the switches were in them
        # would miss a promoted switch against a fresh one.
        self.state.pop("tables", None)
        cache = self.state.setdefault("tables_caps", {})
        if blob not in cache:
            text = run(["git", "-C", self.tc, "cat-file", "-p", blob]).stdout
            table = {}
            for m in re.finditer(r'^\s*[A-Z][A-Za-z0-9]*\s+"([a-z_0-9]+)"\s+(-?[0-9][0-9.eE+-]*)\s*,', text, re.M):
                table[m.group(1)] = float(m.group(2))
            # The switches, as 1 and 0: a promoted switch is new defaults.
            for m in re.finditer(r'^\s*[A-Z][A-Z0-9_]*\s+[0-9]+\s+"([a-z_0-9]+)"\s+(true|false)\s*,', text, re.M):
                table["caps:" + m.group(1)] = 1.0 if m.group(2) == "true" else 0.0
            cache[blob] = table
        return cache[blob]

    def sha(self):
        """The commit new jobs build: plan.json's ref, read after a fetch."""
        if self._sha:
            return self._sha
        ref = self.cfg.get("commit", "origin/main")
        run(["git", "-C", self.tc, "fetch", "-q", "origin"], timeout=120)
        r = run(["git", "-C", self.tc, "rev-parse", ref + "^{commit}"])
        if r.returncode != 0:
            raise SystemExit("cannot resolve %s in %s: %s" % (ref, self.tc, r.stderr.strip()))
        self._sha = r.stdout.strip()
        # Self-modified promotions not yet on main: the fleet builds the
        # local line, main with them on top.
        if ref == "origin/main":
            self._sha = self.build_tip(self._sha)
        line = self.local_line(self._sha) if ref == "origin/main" else None
        if line:
            self._sha = line
        c = self.state["commits"]
        if self._sha not in c:
            # Censuses read with the same weights.rs share one set of
            # defaults, so their rows can feed one fit.
            c[self._sha] = {"weights_rs": self.weights_rs(self._sha), "first_seen": time.strftime("%Y-%m-%dT%H:%M:%S")}
        return self._sha

    # NOTHING TO BUILD (1 November). Nine commits to main in a day, three of them reports, and each made
    # seven machines build, retired the search's queue and replayed the line, which also voids a proof
    # running at the time. These paths go into no census binary: the fleet stays on the last commit that
    # touched anything else, the line stays where it is, and land() puts the difference right on the
    # way to main. The two scripts run on this machine alone, from its checkout.
    NOT_BUILT = ("reports", "docs", "scripts/suggest.py", "scripts/ledger.py")

    def build_tip(self, tip):
        """The newest commit at or under tip that something a machine builds has changed in."""
        r = run(["git", "-C", self.tc, "log", "-1", "--format=%H", tip, "--", "."]
                + [":(exclude)%s" % p for p in self.NOT_BUILT] + [":(exclude,glob)*.md"])
        return r.stdout.strip() or tip

    def replay(self, own, onto):
        """Commits cherry-picked in order onto a commit, in a worktree: the new head, or "" if they do not apply."""
        w = os.path.join(self.pd, "line-replay")
        run(["git", "-C", self.tc, "worktree", "remove", "--force", w])
        run(["git", "-C", self.tc, "worktree", "prune"])
        r = run(["git", "-C", self.tc, "worktree", "add", "-q", "--detach", w, onto])
        for c in own:
            if r.returncode:
                break
            r = run(["git", "-C", w, "cherry-pick", "--allow-empty", c])
        new = run(["git", "-C", w, "rev-parse", "HEAD"]).stdout.strip() if r.returncode == 0 else ""
        if r.returncode:
            run(["git", "-C", w, "cherry-pick", "--abort"])
        run(["git", "-C", self.tc, "worktree", "remove", "--force", w])
        return new

    def land(self, commit):
        """A commit of the line onto main, by a push; the commit main now has. If main has moved since
        only by what no machine builds, the line's commits go on top of it first: what was read is what
        main then builds. If it has moved by anything else, that read is not of this main, and it stops."""
        remote, branch = self.push_target()
        run(["git", "-C", self.tc, "fetch", "-q", remote], timeout=120)
        tip = "%s/%s" % (remote, branch)
        if run(["git", "-C", self.tc, "merge-base", "--is-ancestor", tip, commit]).returncode != 0:
            real = self.build_tip(run(["git", "-C", self.tc, "rev-parse", tip]).stdout.strip())
            if run(["git", "-C", self.tc, "merge-base", "--is-ancestor", real, commit]).returncode != 0:
                raise SystemExit("main's source has moved since %s was read: it waits for its own proof" % commit[:7])
            own = run(["git", "-C", self.tc, "rev-list", "--reverse", "%s..%s" % (tip, commit)]).stdout.split()
            commit = self.replay(own, tip)
            if not commit:
                raise SystemExit("main moved by documents, and the line does not replay on it")
        r = run(["git", "-C", self.tc, "push", remote, "%s:refs/heads/%s" % (commit, branch)])
        if r.returncode != 0:
            raise SystemExit("the push failed: " + r.stderr[-300:])
        run(["git", "-C", self.tc, "fetch", "-q", remote])
        return commit

    def short(self, sha=None):
        return (sha or self.sha())[:7]

    def cdir(self):
        return "~/%s/c/%s" % (self.home, self.short())

    def trainer(self):
        """The GPU trainer at this commit, built by the job that runs it when the build lacks it: a
        minute of cargo the first time on that machine and commit, nothing after."""
        return ("[ -x %(c)s/treadcore-bc ] || ( [ -f ~/.cargo/env ] && . ~/.cargo/env; export PATH=$HOME/.cargo/bin:$PATH; "
                "cd %(c)s/wt/tools/bc && CARGO_TARGET_DIR=$HOME/code/treadcore/tools/bc/target cargo build -q --release && "
                "cp $HOME/code/treadcore/tools/bc/target/release/treadcore-bc %(c)s/treadcore-bc ) || { echo 'the trainer did not build'; exit 1; }\n") % {"c": self.cdir()}

    def prune_builds(self):
        """Each time main moves, the old commit builds on every machine go -- by growth.py's own purge,
        builds alone, in the background: the current, any a queued or running job names and the two
        newest stay (Paul, 4 November: "Prune after promotion"). A build is about 50 MB without the
        trainer, and a prepare makes one again in minutes if it is ever asked for."""
        short = self.short()
        if self.state.get("pruned_for") == short or not self.auto():
            return
        self.state["pruned_for"] = short
        tool = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "growth.py")
        subprocess.Popen([sys.executable, "-I", tool, self.q, "prune-builds"], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    def commits_log(self, n=40):
        """The line the fleet builds, newest first, each commit with the
        weights! defaults it changed (old, new), when the fleet first built
        it, and its page on GitHub (none for the local line's own commits,
        which are not there): plan/commits.json, for the console's Settings.
        A commit's changes never change, so each is read once (state)."""
        head = self.sha()
        remote, branch = self.push_target()
        web = github_web(run(["git", "-C", self.tc, "remote", "get-url", remote]).stdout.strip())
        local = set(run(["git", "-C", self.tc, "rev-list", "%s/%s..%s" % (remote, branch, head)]).stdout.split())
        r = run(["git", "-C", self.tc, "log", "--first-parent", "-n", str(n), "--format=%H%x09%P%x09%aI%x09%an%x09%s", head])
        seen = self.state.setdefault("commit_values", {})
        out = []
        for line in r.stdout.splitlines():
            parts = line.split("\t", 4)
            if len(parts) < 5:
                continue
            sha, parents, when, who, subject = parts
            if sha not in seen:
                parent = parents.split()[0] if parents else ""
                a, b = (self.defaults_at(parent) if parent else {}), self.defaults_at(sha)
                seen[sha] = [[k, a.get(k), b.get(k)] for k in sorted(set(a) | set(b)) if parent and a.get(k) != b.get(k)]
            out.append({"sha": sha, "short": sha[:7], "when": when[:19], "who": who, "subject": subject[:400],
                        "values": seen[sha], "built": (self.state["commits"].get(sha) or {}).get("first_seen"),
                        "local": sha in local, "url": "%s/commit/%s" % (web, sha) if web and sha not in local else ""})
        save(os.path.join(self.pd, "commits.json"), {"head": head, "branch": "%s/%s" % (remote, branch), "web": web,
                                                      "checked": time.strftime("%Y-%m-%dT%H:%M:%S"), "commits": out})

    # ---- preparing the hosts --------------------------------------------------------
    def prep_id(self, host):
        # A second lane on a machine ("build_of" in config.json, the keeper's builder()) has no build of
        # its own: the machine's first lane built it, and that build is the one asked after.
        of = next((h.get("build_of") for h in (getattr(self, "qcfg", None) or {}).get("hosts", []) if h.get("name") == host and h.get("build_of")), None)
        return "prep-%s-%s" % (of or host, self.short())

    def prepare_jobs(self):
        sha, short = self.sha(), self.short()
        jobs = []
        # A build still queued for a commit main has moved past is not
        # built: the newest carries everything the older did, and a
        # machine busy for hours would build each in turn (29 October:
        # calber held three, behind a school run). Moved to stopped/ as the
        # keeper claims a job, by a rename, so one it has begun is left.
        # BUT NOT ONE A QUEUED JOB WAITS ON (1 November). A census asked by hand is held to its commit and
        # is not retired with the search's jobs; with its build gone it could never start, and nothing
        # said so: r0093 and r0094 sat high in the queue for twenty minutes, behind no one.
        waited = {j.get("after_host", "").rsplit("-", 1)[-1] for j in self.queue_jobs() if j.get("kind") != "prepare" and j.get("after_host")}
        for f in glob.glob(os.path.join(self.q, "queue", "*.json")):
            j = load(f, {})
            if j.get("kind") == "prepare" and j.get("id", "").startswith("prep-") and not j["id"].endswith("-" + short) and j["id"].rsplit("-", 1)[-1] not in waited:
                try:
                    os.rename(f, os.path.join(self.q, "stopped", os.path.basename(f)))
                except OSError:
                    pass
        known = self.ids("queue", "running", "done", "failed", "stopped") - self.retry_failed_builds()
        for h in self.hosts:
            jid = self.prep_id(h["name"])
            if jid in known or h.get("build_of"):
                continue
            cmd = (
                "set -e; [ -f ~/.cargo/env ] && . ~/.cargo/env; export PATH=$HOME/.cargo/bin:$PATH\n"
                "C=%s; mkdir -p $C\n"
                "cd ~/code/treadcore && git fetch -q origin\n"
                # The host's own checkout follows main when nothing in it would be lost.
                "if [ \"$(git rev-parse --abbrev-ref HEAD)\" = main ] && git diff --quiet && git diff --cached --quiet; then\n"
                "  git merge -q --ff-only origin/main && echo \"checkout: main at $(git rev-parse --short HEAD)\" || echo 'checkout: not a fast-forward, left as it is'\n"
                "else echo \"checkout: $(git rev-parse --abbrev-ref HEAD), with changes or not main: left as it is\"; fi\n"
                "git worktree remove --force $C/wt 2>/dev/null || true; git worktree prune\n"
                # The local line's commits, when the commit is not on main yet.
                "[ -f $C/accepted.bundle ] && git fetch -q $C/accepted.bundle %s\n"
                "git worktree add -q --detach $C/wt %s\n"
                "cd $C/wt && export CARGO_TARGET_DIR=$HOME/fleet/target && . scripts/common.sh && census_bin $C >/dev/null\n"
                "CENSUS_DUMP=$C/defaults.toml CENSUS_SEEDS=0 $C/census-bin --ignored brain_census >/dev/null 2>&1\n"
                "echo \"census binary %s: $( (sha256sum $C/census-bin 2>/dev/null || shasum -a 256 $C/census-bin) | cut -c1-16)\"\n"
            ) % (self.cdir(), self.LINE, sha, short)
            # Ahead of the queue: every job on that machine waits on this one, and it took the last
            # machine 3 to 43 minutes to reach a build behind the search's own reads.
            job = {"id": jid, "kind": "prepare", "title": "build %s on %s" % (short, h["name"]),
                   "needs": "host:" + h["name"], "cmd": cmd, "timeout_s": 3600, "priority": "high"}
            if self.state.get("local_line"):
                job["send"] = [{"src": os.path.join(self.pd, "accepted.bundle"), "dst": "%s/accepted.bundle" % self.cdir()}]
                job["title"] += " (the local line: %d promotion(s) not on main)" % len(self.state["local_line"]["promotions"])
            # THE TRAINER IS NOT BUILT HERE. It was, on every GPU machine at every commit: 207 MB of a
            # 250 MB build, 72 of them on whitewolf, and only a net job runs it (Paul, 4 November:
            # "Trainer only when needed"). The net job builds it at its own commit: trainer().
            # Every machine brings back the defaults it built: after a
            # promotion, the proof that its values reached that machine.
            job["fetch"] = "%s/c/%s/defaults.toml" % (self.home, short)
            jobs.append(job)
        return jobs

    def retry_failed_builds(self):
        """A FAILED BUILD IS TRIED ONCE MORE (4 November). Nothing built a failed build's commit again,
        so a machine stood idle until main moved: at 20:10 every machine's build of f04f157 failed in a
        second on a bundle that did not hold it, and nothing asked again. A failed build of the commit
        the fleet builds goes to failed-retried/ and is asked again, once a machine and commit (a
        writer's pass only). The builds set aside, by id."""
        out = set()
        if not self.writer:
            return out
        retried = self.state.setdefault("prep_retried", {})
        failed = self.ids("failed")
        for h in self.hosts:
            jid = self.prep_id(h["name"])
            if jid in failed and jid not in retried:
                aside = os.path.join(self.q, "failed-retried")
                os.makedirs(aside, exist_ok=True)
                for f in glob.glob(os.path.join(self.q, "failed", "*-%s.json" % jid)):
                    os.rename(f, os.path.join(aside, os.path.basename(f)))
                retried[jid] = time.strftime("%Y-%m-%dT%H:%M:%S")
                out.add(jid)
        return out

    def prepared(self, host):
        return self.prep_id(host) in self.ids("done")

    def after_host(self):
        return "prep-{host}-%s" % self.short()

    # ---- the weights -----------------------------------------------------------------
    def census_cmd(self, trial_text, seeds, seed0, out_id):
        w = self.cfg["weights"]
        trial_text = self.ranged(trial_text)
        b = base64.b64encode(trial_text.encode()).decode()
        return (
            "set -e; [ -f ~/.cargo/env ] && . ~/.cargo/env; export PATH=$HOME/.cargo/bin:$PATH\n"
            # BSD paste will not read stdin unnamed: `paste -sd,` fails on a Mac, census_maps
            # keeps only `gen`, and MAP=all reads ONE map of eleven. macmini read so from the
            # day it joined, 470 first reads pooled as if they were the whole game (1 November).
            "paste() { command paste \"$@\" -; }; export -f paste\n"
            "Q=~/%s; C=%s; mkdir -p $Q/trials; echo %s | base64 -d > $Q/trials/%s.weights\n"
            "cd $C/wt && export CARGO_TARGET_DIR=$HOME/fleet/target\n"
            "TRIAL=$Q/trials/%s.weights CENSUS_MODELS=$Q/models CENSUS_PATCHES=$Q/patches SEEDS=%d SEED0=%d SECS=%d MAP=%s RESPAWNS=3 JOBS=$(nproc 2>/dev/null || sysctl -n hw.ncpu) CENSUS_BIN=$C/census-bin scripts/census.sh 2>&1 | tail -3\n"
            "d=$(ls -td build/census/*/ | head -1); s=$(basename $d)\n"
            "rm -rf $Q/out/%s; mkdir -p $Q/out/%s/$s; cp $d/*.txt $d/*.env $d/*.weights $d/g-*.log $Q/out/%s/$s/; rm -rf $d\n"
        ) % (self.home, self.cdir(), b, out_id, out_id, seeds, seed0, w["secs"], w["map"], out_id, out_id, out_id)

    def census_dirs(self):
        """Every fetched census of the queue: results/ID/fleet/q-NAME/out/ID/STAMP.

        READ ONCE A PASS. The planner is a fresh process each pass, and a fetched census does not
        change: 27,000 of them were globbed sixteen times a pass, 44 of its 105 seconds, once the
        keeper asked for passes sooner (5 November, the duty-cycle report's B)."""
        if self.__dict__.get("_census_dirs") is None:
            # A held-out read's pieces (hNNNN-pI) are read as the one census they make, never alone:
            # in the ledger as well they would count each seed twice.
            # A FINISHED JOB'S CENSUSES ARE KEPT BETWEEN PASSES (8 November): the glob looked through
            # 38,851 results three levels down each pass, seven of its seconds, for directories that
            # do not change once their job is done. The queue takes no id it has seen (Queue.add) and
            # nothing moves a job out of done/, so a job there never runs again; what it fetched is
            # kept in plan/census-dirs.json. Every other result (running, failed, a held-out read the
            # planner merges itself) is looked through each pass, as before. The same directories,
            # in the same order.
            # Each dir is kept with its commit (run.env), whether it holds trial.weights, and whether
            # it read only one map (one_map), all fetched with it: sequential() asked the first two of
            # 13,000 dirs each pass, five seconds, and remembered() the third of 29,500, nine.
            # (A planner without a plan directory, a test's, keeps nothing and looks through them all.)
            cache_f = os.path.join(self.pd, "census-dirs.json") if getattr(self, "pd", None) else None
            cache = (load(cache_f, {}) or {}) if cache_f else {}
            had = cache.get("dirs", {}) if cache.get("home") == self.home and cache.get("v") == 3 else {}
            done = self.ids("done") if cache_f else set()
            kept, found, fresh = {}, [], 0
            for jid in (names_in(os.path.join(self.q, "results")) or ([], False))[0]:
                if jid in had:
                    kept[jid] = had[jid]
                    for rel, commit, tw, om in had[jid]:
                        d = os.path.join(self.q, rel)
                        found.append(d)
                        if commit is not False:
                            _COMMITS[d] = commit
                        if om is not None:
                            _ONE_MAP[d] = om
                        _TRIAL_W[d] = tw
                    continue
                mine = []
                out = os.path.join(self.q, "results", jid, self.home, "out")
                for x in (names_in(out) or ([], False))[0]:
                    if not os.path.isdir(os.path.join(out, x)):
                        continue
                    for stamp in (names_in(os.path.join(out, x)) or ([], False))[0]:
                        if os.path.isdir(os.path.join(out, x, stamp)):
                            mine.append(os.path.join("results", jid, self.home, "out", x, stamp, ""))
                if jid in done:
                    entries = []
                    for rel in mine:
                        d = os.path.join(self.q, rel)
                        commit = Plan.census_commit(d)
                        Plan.one_map(d)
                        # False and None: run.env or pooled.txt could not be read, so nothing is kept
                        # of it and it is read as before.
                        entries.append([rel, commit if d in _COMMITS else False, os.path.exists(os.path.join(d, "trial.weights")),
                                        _ONE_MAP.get(d)])
                    kept[jid] = entries
                    fresh += 1
                found += [os.path.join(self.q, d) for d in mine]
            if cache_f and cache_due(cache_f, fresh, len(had) - (len(kept) - fresh)):
                keep_cache(cache_f, {"home": self.home, "v": 3, "dirs": kept})
            self._census_dirs = sorted(d for d in found if not re.search(r"-p\d+(r\d+)?$", d.rstrip("/").split(os.sep)[-2]))
        return list(self._census_dirs)

    def done_titles(self):
        """{job id: title} of every finished job, read once a pass: sequential() and held_pairs() each
        loaded all 27,000 of them, five and seven times a pass."""
        if self.__dict__.get("_done_titles") is None:
            out = {}
            d = os.path.join(self.q, "done")
            listed = names_in(d)
            if listed is None or listed[1] or not getattr(self, "pd", None):
                for f in glob.glob(os.path.join(d, "**", "*.json"), recursive=True):
                    j = load(f, {}) or {}
                    if j.get("id"):
                        out[j["id"]] = j.get("title", "")
            else:
                # KEPT BETWEEN PASSES (8 November): 38,704 files read each pass for an id and a title,
                # neither of which a finished job changes. Each file's pair is kept by its name, in
                # plan/done-titles.json, and only the names new since the last pass are read.
                cache_f = os.path.join(self.pd, "done-titles.json")
                cache = load(cache_f, {}) or {}
                kept, fresh = {}, 0
                for n in sorted(n for n in listed[0] if n.endswith(".json")):
                    hit = cache.get(n)
                    if hit is None:
                        j = load(os.path.join(d, n), {}) or {}
                        if not j.get("id"):
                            continue
                        hit = [j["id"], j.get("title", "")]
                        fresh += 1
                    kept[n] = hit
                    out[hit[0]] = hit[1]
                if cache_due(cache_f, fresh, len(cache) - (len(kept) - fresh)):
                    keep_cache(cache_f, kept)
            self._done_titles = out
        return self._done_titles

    def own_ledger(self):
        root = os.path.join(self.pd, "census")
        shutil.rmtree(root, ignore_errors=True)
        os.makedirs(root)
        for d in self.census_dirs():
            # Today's defaults only, as the history rows are: a census read
            # against the defaults before a promotion says nothing of a trial
            # against today's. suggest.py puts every row on today's log
            # scale, so the 182 rows read before w0034 was promoted (each
            # near +2, against the old defaults) went in as gains of the
            # weights that moved, and the fit's "best" chased them: read 309
            # times since, at -0.3 (29 October).
            if not self.same_defaults(self.census_commit(d)) or self.one_map(d):
                continue
            # The stamp, and the job: two hosts can finish in the same second.
            jid = d.rstrip("/").split(os.sep)[-2]
            os.symlink(d, os.path.join(root, "%s-%s" % (os.path.basename(d.rstrip("/")), jid)))
        out = os.path.join(self.pd, "ledger.tsv")
        with open(out, "w") as f:
            subprocess.run([sys.executable, "-I", os.path.join(self.tc, "scripts", "ledger.py"), root], stdout=f, check=True)
        return out

    # THE FIT REMEMBERS (Paul, 1 November: "continue. implimenting."). The fit read only today's defaults,
    # so each generation wiped it: of 42 hours of reads, it could use the last 0.4. The old reason stands,
    # that a read of a trial against old defaults is not a gain of that trial against today's: 182 rows
    # near +2 went in as gains of the weights that moved. But the read is still a true difference, between
    # the trial's value and the value of its day, and suggest.py can fit it as that (--memory). What
    # moved between then and now and is not in the trial cancels, if the score adds. It does not quite,
    # so an older read counts for less: its error grows MEMORY_TAU a seat for each doubling the defaults
    # have moved, and past MEMORY_DRIFT doublings, or across a game version, it is not used at all.
    MEMORY_TAU = 0.5
    MEMORY_DRIFT = 6.0

    def drift_from(self, commit):
        """{"old": the dials that differ, at their values then, "drift": doublings moved} of a commit's
        defaults from today's. None when its read cannot be used: other rules, or moved too far."""
        memo = self.__dict__.setdefault("_drift", {})
        if commit not in memo:
            memo[commit] = None
            if commit and not commit.endswith("+") and self.game_at(commit) == self.game_at(self.sha()):
                a, b = self.defaults_at(commit), self.defaults_at(self.sha())
                old, drift = {}, 0.0
                for k in set(a) & set(b):
                    if a[k] != b[k]:
                        old[k] = a[k]
                        drift += abs(math.log2(a[k] / b[k])) if a[k] > 0 and b[k] > 0 else 1.0
                if a and b and drift <= self.MEMORY_DRIFT:
                    memo[commit] = {"old": old, "drift": round(drift, 3)}
        return memo[commit]

    def remembered(self, ledger):
        """Today's ledger and the reads of earlier defaults, as one table for the fit, with
        plan/memory.json saying what each older commit's defaults were. Not plan/ledger.tsv itself,
        which others read as rows of today's."""
        root = os.path.join(self.pd, "census-memory")
        shutil.rmtree(root, ignore_errors=True)
        os.makedirs(root)
        mem = {}
        for d in self.census_dirs():
            c = self.census_commit(d)
            if self.same_defaults(c) or self.one_map(d):
                continue
            m = self.drift_from(c)
            if m:
                mem[c] = m
                jid = d.rstrip("/").split(os.sep)[-2]
                os.symlink(d, os.path.join(root, "%s-%s" % (os.path.basename(d.rstrip("/")), jid)))
        out = os.path.join(self.pd, "ledger-memory.tsv")
        older = run([sys.executable, "-I", os.path.join(self.tc, "scripts", "ledger.py"), root]).stdout.splitlines()
        with open(out, "w") as f:
            f.write(open(ledger).read())
            f.write("".join(l + "\n" for l in older[1:]))
        save(os.path.join(self.pd, "memory.json"), mem)
        self.state["memory"] = {"commits": len(mem), "rows": max(0, len(older) - 1)}
        return out

    def memory_args(self):
        try:
            if "--memory" not in open(os.path.join(self.tc, "scripts", "suggest.py")).read():
                return []
        except OSError:
            return []
        return ["--memory", os.path.join(self.pd, "memory.json"), "--tau", str(self.MEMORY_TAU)]

    def ranges(self):
        """{name: (min, max)} from the brain's RANGES: past these a number means nothing, or a
        person has ruled it, min = max, a decree. The brain holds to them whatever it is given;
        here the search stops asking for what it could not get."""
        if self._ranges is None:
            r = run(["git", "-C", self.tc, "show", "%s:source/treadcore-brain/RANGES" % self.sha()])
            self._ranges = {}
            for line in (r.stdout if r.returncode == 0 else "").splitlines():
                f = line.split("#")[0].split()
                if len(f) == 3:
                    self._ranges[f[0]] = (float(f[1]), float(f[2]))
        return self._ranges

    def decreed(self):
        return {k for k, (lo, hi) in self.ranges().items() if lo == hi}

    def ranged(self, text):
        """A trial's text with each number held to its range."""
        out = []
        for line in text.splitlines():
            k, eq, v = line.partition("=")
            r = self.ranges().get(k.strip())
            try:
                if eq and r and not line.lstrip().startswith("#"):
                    n = float(v.split("#")[0])
                    if not r[0] <= n <= r[1]:
                        line = "%s = %g" % (k.strip(), min(r[1], max(r[0], n)))
            except ValueError:
                pass
            out.append(line)
        return "\n".join(out) + "\n"

    def game_at(self, commit):
        """The game's rules at a commit, source/treadcore-sim/GAME_VERSION, bumped by hand when
        they change: the dials can stand still while the game moves under them (Paul's depots,
        30 October), and a read of the old game is no evidence about the new one."""
        # A commit named by its hash never changes: 195 of them asked a pass, two git runs each, so
        # what each said is kept in the state from pass to pass.
        games = self.state.setdefault("games", {})
        if commit and re.fullmatch(r"[0-9a-f]{7,40}", commit) and commit in games:
            return games[commit]
        r = run(["git", "-C", self.tc, "show", "%s:source/treadcore-sim/GAME_VERSION" % commit])
        game = r.stdout.strip() if r.returncode == 0 else ""
        # AND THE SCORE'S (LR 139; Paul, 4 November, of the score counting building and the base:
        # "Start anew"): source/treadcore-brain/SCORE_VERSION, absent before it, so a read of the old
        # score is no evidence about the new one, as a read of the old game is not.
        sv = run(["git", "-C", self.tc, "show", "%s:source/treadcore-brain/SCORE_VERSION" % commit])
        out = game + ("+score%s" % sv.stdout.strip() if sv.returncode == 0 and sv.stdout.strip() else "")
        if commit and re.fullmatch(r"[0-9a-f]{7,40}", commit) and r.returncode == 0:
            games[commit] = out
        return out

    def same_defaults(self, commit):
        """A row's commit read with today's defaults: every weight both
        commits have at the same default (a weight added since, at a default
        that plays as before, keeps the history; a promotion, which moves a
        default, starts anew). No '+' (uncommitted source)."""
        if not commit or commit.endswith("+"):
            return False
        memo = self.state.setdefault("same", {})
        key = "%s:%s" % (commit, self.short())
        if key not in memo:
            a, b = self.defaults_at(commit), self.defaults_at(self.sha())
            common = set(a) & set(b)
            memo[key] = bool(common) and all(a[k] == b[k] for k in common) and self.game_at(commit) == self.game_at(self.sha())
        return memo[key]

    def ledger(self):
        """The fit's input: the queue's own rows, and the fleet's history rows
        that share today's defaults and the queue's census settings."""
        own = self.own_ledger()
        hist = self.cfg.get("history")
        if not hist:
            return own
        w = self.cfg["weights"]
        path = os.path.join(self.tc, hist) if not os.path.isabs(hist) else hist
        try:
            src = list(csv.DictReader(open(path), delimiter="\t"))
        except OSError:
            src = []
        q_stamps = {r["stamp"] for r in csv.DictReader(open(own), delimiter="\t")}
        rows = []
        for r in src:
            try:
                ok = (r["stamp"] not in q_stamps and int(r["seeds"] or 0) >= w["seeds"] and str(r["secs"]) == str(w["secs"])
                      and r["map"] == w["map"] and self.same_defaults(r["commit"]))
            except ValueError:
                ok = False
            if ok:
                rows.append(r)
        self.state["history_rows"] = len(rows)
        if not rows:
            return own
        h = os.path.join(self.pd, "history.tsv")
        write_tsv(h, rows)
        out = os.path.join(self.pd, "ledger-all.tsv")
        with open(out, "w") as f:
            subprocess.run([sys.executable, "-I", os.path.join(self.tc, "scripts", "ledger.py"), "--merge", h, own], stdout=f, check=True)
        return out

    def defaults(self):
        # The census host's, or any machine's that built it: one flaky machine
        # must not stop the whole search.
        p = glob.glob(os.path.join(self.q, "results", self.prep_id(self.cfg["census_host"]), self.home, "c", self.short(), "defaults.toml"))
        p = p or sorted(glob.glob(os.path.join(self.q, "results", "prep-*-" + self.short(), self.home, "c", self.short(), "defaults.toml")))
        return p[0] if p else None

    @staticmethod
    def passes(d):
        ok, below = False, False
        try:
            lines = open(os.path.join(d, "pooled.txt")).read().splitlines()
        except OSError:
            return None
        for l in lines:
            m = re.match(r"^(\S+(?: map)?)\s+([-+][\d.]+) \+/- ([\d.]+)", l)
            if not m:
                continue
            dd, se = float(m.group(2)), float(m.group(3))
            if m.group(1) == "every map":
                ok = se > 0 and dd > 2 * se
            elif se > 0 and dd < -2 * se:
                below = True
        return ok and not below

    # LONG READS ON FAST MACHINES (1 November). macmini reads a seed in 1.4 s and columbia in 6.2, and a
    # held-out read fell to whichever lane came free: 9 minutes or 41, and a slow machine in a long read
    # is also the last to build a new commit, which held up the proof for up to 29 minutes. A machine's
    # "fast" cap in config.json says where they go; with none of those fit to take one, any machine does.
    LONG_ON_FAST = 1

    def long_needs(self):
        if not self.LONG_ON_FAST:
            return "cpu"
        for h in self.hosts:
            if "fast" in h.get("caps", []) and not h.get("paused"):
                lane = load(os.path.join(self.q, "lanes", h["name"] + ".json"), {}) or {}
                if lane.get("state") not in ("down", "unreachable", "paused"):
                    return "fast"
        return "cpu"

    def cpu_ready(self):
        return [h for h in self.hosts if "cpu" in h.get("caps", ["cpu"]) and self.prepared(h["name"])]

    def weight_jobs(self, n):
        w = self.cfg.get("weights")
        defaults = self.defaults() if w else None
        if not w or not defaults or not self.cpu_ready() or n <= 0:
            return []
        jobs = []
        seq = self.sequential()
        # Held-out reads first, for trials the sequential read passed.
        for jid, v in sorted(seq.items()):
            if v["status"] != "passed" or jid in self.state["held_read"]:
                continue
            trial = v["text"]
            # A GENERATION TAKES ONE READ (Paul, 1 November: pass about every half hour,
            # carry what is not proven). Proof is the line's own read against main
            # (line_proof), where the noise of many generations is read at once.
            for k in range(1):
                # What decides goes first: it got 3% of the lanes behind a queue seven hours long.
                jobs += self.held_read(jid, k + 1, trial, high=True)
            self.state["held_read"].append(jid)
        # A second read asked for before the rule above, for a first at zero or better.
        waiting = self.state.get("held_second", [])
        if waiting:
            pairs = self.held_pairs()
            for jid in list(waiting):
                ds = pairs.get(jid, [])
                if len(ds) != 1 or jid not in seq:
                    if len(ds) >= 2 or jid not in seq:
                        waiting.remove(jid)
                    continue
                first = self.pool(ds)
                waiting.remove(jid)
                if not first or first["every"][1] <= 0 or first["every"][0] < 0:
                    continue
                jobs += self.held_read(jid, 2, seq[jid]["text"], high=False)
        jobs += self.held_more_jobs(seq)
        # Then the reads on, the most promising first: a test begun is
        # finished before most new ones begin (Fishtest's way). A third of
        # the room is kept for new trials, so a backlog of reads on (the
        # 1,100 trials read before this rule, say) does not stop the search.
        room = n - len(jobs)
        jobs += self.read_on_jobs(seq, room - room // 3, w)
        # Then new trials from the fit.
        want = n - len(jobs)
        if want > 0:
            s = self.search(defaults)
            s["sequential"] = self.seq_counts(seq)
            s["difficulty"] = dict(self.state.get("difficulty", {}), last_promotion=(self.promotions() or [[None, None]])[-1][1])
            g = self.state["gen"]
            out = os.path.join(self.pd, "gen%d" % g)
            shutil.rmtree(out, ignore_errors=True)
            # Four times what is wanted: the trials already read are dropped
            # below, and the rest must still fill the generation.
            r = run([sys.executable, "-I", os.path.join(self.tc, "scripts", "suggest.py"), self.remembered(self.ledger()), defaults, out,
                     "--n", str(max(12, 4 * want)), "--seed", str(g), "--bound", str(s["bound"]), "--also-skip", ",".join(sorted(self.decreed()))]
                    + self.memory_args())
            if r.returncode != 0:
                raise SystemExit("suggest.py: " + r.stderr[-400:])
            self.state["gen"] += 1
            # A/B first: each switch flipped, each choice at each other
            # version, once a generation, a third of the room at most.
            ab = self.ab_trials(max(1, want // 3), out, s)
            # A stalled search took half of each generation for wide trials: 40% of the
            # lanes on 31 October, 843 trials and none past the first bars, where the
            # fit passed 21 of 514 and the A/B 4 of 17. One a generation keeps the door open.
            wide = self.wide_trials(1, out, g, defaults) if s["stalled"] else []
            far = self.far_trials(max(1, int(want * self.FAR_SHARE)), out, defaults)
            asked = self.region_trials(want, out)
            temper = self.temper_trials(max(1, int(want * self.TEMPER_SHARE)), out)
            fit = []
            try:
                fit = [os.path.join(out, l.split("\t")[0] + ".weights") for l in open(os.path.join(out, "plan.tsv")).read().splitlines()[1:]]
            except OSError:
                pass
            picked, now, far_seen, temper_seen = [], set(), [], []
            for f in asked + ab + temper + far + wide + fit:
                if len(picked) >= want:
                    break
                text = self.ranged(open(f).read())
                if os.path.basename(f).startswith("far-"):
                    far_seen.append(os.path.basename(f)[:-8])
                if os.path.basename(f).startswith("temper-"):
                    temper_seen.append(os.path.basename(f)[:-8])
                key = self.trial_key(text)
                # suggest.py's reads again are the sequential read's to make
                # (read_on_jobs, pooled with the first): not new trials.
                name = os.path.basename(f)
                if name.startswith("again-") or key in now:
                    continue
                now.add(key)
                # A trial once on today's defaults. suggest.py sees only what
                # has been read, so each generation, five minutes apart, asked
                # again for what was still queued: since w0300, 721 trials and
                # 310 different ones, one of them read 77 times (29 October).
                # The fit's best, which moves by a hair a generation: again
                # once there are 20 new reads to have moved it.
                if s["tried"].get(key) or (name.startswith("best") and s["reads"] < s.get("best_at", -99) + 20):
                    s["repeats"] = s.get("repeats", 0) + 1
                    continue
                s["tried"][key] = s["tried"].get(key, 0) + 1
                picked.append((f, text))
            if any(os.path.basename(f).startswith("best") for f, _ in picked):
                s["best_at"] = s["reads"]
            self.far_asked(far_seen)
            self.temper_asked(temper_seen)
            s["far_left"] = len((self.state.get("far") or {}).get("todo", []))
            self.search_note(s)
            for f, text in picked:
                jid = "w%04d" % self.state["weights_n"]
                seed0 = w["seed0"] + 10000 * self.state["weights_n"]
                self.state["weights_n"] += 1
                what = os.path.basename(f)[:-8]
                if what.startswith("far-"):
                    self.state["far"].setdefault("asked", {})[jid] = what
                if what.startswith("temper-"):
                    self.state["temper"].setdefault("asked", {})[jid] = what
                if what.startswith("region-"):
                    self.state.setdefault("regions", {}).setdefault(what.split("-")[1], {}).setdefault("jobs", {})[jid] = int(what.split("-")[2])
                moved = short_moved(text)
                jobs.append({"id": jid, "kind": "weights", "title": "%s: %s" % (what, moved or "the defaults"),
                             "needs": "cpu", "after_host": self.after_host(), "cmd": self.census_cmd(text, w["seeds"], seed0, jid),
                             "fetch": "%s/out/%s" % (self.home, jid), "timeout_s": 6 * 3600})
        return jobs

    # ---- the search's own memory -------------------------------------------------------
    # Trials on today's defaults past the last find (a trial past both its
    # held-out reads): the search widens. After w0034 was promoted the fit's
    # trials stayed at its tops, near what was read, and in 1,000 of them
    # none held out (29 October).
    STALL = 150

    @staticmethod
    def trial_key(text):
        """A trial's weights, three figures each: the fit's top moves by a
        hair as rows come in, and a hair is the same trial. Its caps line
        too, its names sorted: every switch's trial had the empty key."""
        canon = ";".join("%s=%.3g" % kv for kv in sorted(parse_weights(text).items()))
        stamp = re.search(r"^# A/B: model slot (\d+) \S+, sha (\w+)", text, re.M) or re.search(r"^# A/B: patch slot (\d+), sha (\w+)", text, re.M)
        if stamp:
            canon += ";slot%s=%s" % stamp.groups()
        caps = [l.split("=", 1)[1] for l in text.splitlines() if re.match(r"^\s*caps\s*=", l.split("#")[0])]
        if caps:
            canon += ";caps=" + ",".join(sorted(c.strip() for c in caps[-1].split("#")[0].split(",") if c.strip()))
        return hashlib.sha1(canon.encode()).hexdigest()[:12]

    def search(self, defaults):
        """{defaults, tried {key: times planned}, reads, last_find, since_find,
        stalled, bound}: what the search has asked on these defaults (a
        promotion starts it anew), seeded from every trial read, running or
        queued when they are first seen."""
        fp = hashlib.sha1(open(defaults, "rb").read()).hexdigest()[:12]
        s = self.state.get("search")
        trials = [(d, d.rstrip("/").split(os.sep)[-2]) for d in self.census_dirs()]
        trials = [(d, jid) for d, jid in trials if re.match(r"w\d+$", jid) and self.same_defaults(self.census_commit(d))]
        if not s or s.get("defaults") != fp:
            s = {"defaults": fp, "tried": {}, "repeats": 0}
            texts = [open(os.path.join(d, "trial.weights")).read() for d, _ in trials if os.path.exists(os.path.join(d, "trial.weights"))]
            for f in glob.glob(os.path.join(self.q, "queue", "w*.json")) + glob.glob(os.path.join(self.q, "running", "*", "w*.json")):
                m = re.search(r"echo (\S+) \| base64 -d", load(f, {}).get("cmd", ""))
                if m:
                    texts.append(base64.b64decode(m.group(1)).decode())
            for t in texts:
                k = self.trial_key(t)
                s["tried"][k] = s["tried"].get(k, 0) + 1
            self.state["search"] = s
        found = [int(jid[1:]) for jid, ds in self.held_pairs().items()
                 if self.held_pass(ds) and all(self.same_defaults(self.census_commit(d)) for d in ds)]
        last = max(found) if found else None
        since = len([1 for _, jid in trials if last is None or int(jid[1:]) > last])
        s.update({"reads": len(trials), "last_find": "w%04d" % last if last is not None else None,
                  "since_find": since, "stalled": since >= self.STALL})
        s["bound"] = 4 if s["stalled"] else 2
        # Where the widening began, so health can tell widened and still dry.
        if s["stalled"]:
            s.setdefault("widened_at", len(trials))
        else:
            s.pop("widened_at", None)
        return s

    def search_note(self, s):
        """plan/search.json, for fleet-queue.py health and the Settings page."""
        note = {k: v for k, v in s.items() if k != "tried"}
        note.update({"distinct": len(s["tried"]), "stall": self.STALL, "checked": time.strftime("%Y-%m-%dT%H:%M:%S")})
        save(os.path.join(self.pd, "search.json"), note)

    # ---- A/B: the brain's other versions ----------------------------------------------
    # Paul, 29 October: "more efficient A/B testing alternate functions such
    # that we can expand binary paths of brains using a or b". The brain
    # has two kinds of version: a capability (caps!, a bit: on or off) and a
    # choice (weights!, a doc saying "(choice: a | b | ...)", 0 as built).
    # Each generation every one is tried against the defaults, alone: the
    # switch flipped, the choice at each version it is not. A trial is a
    # trial: the sequential read decides it, the held-out reads confirm it,
    # and set-defaults.py promotes a caps line or a choice as it does a
    # number. suggest.py leaves them out, a fit across versions being a fit
    # across functions.
    def versions(self):
        """(caps {name: on}, choices {name: (default, [versions])}) from
        today's weights.rs."""
        blob = self.weights_rs(self.sha())
        text = run(["git", "-C", self.tc, "cat-file", "-p", blob]).stdout if blob else ""
        caps = {m.group(1): m.group(2) == "true"
                for m in re.finditer(r'^\s*[A-Z][A-Z0-9_]*\s+[0-9]+\s+"([a-z_0-9]+)"\s+(true|false)\s*,', text, re.M)}
        choices = {m.group(1): (float(m.group(2)), [v.strip() for v in m.group(3).split("|")])
                   for m in re.finditer(r'^\s*[A-Z][A-Za-z0-9]*\s+"([a-z_0-9]+)"\s+(-?[0-9.]+),\s*"[^"]*\(choice: ([^)]*)\)', text, re.M)}
        return caps, choices

    def ab_trials(self, n, out, s):
        """Up to n A/B trials not yet asked on today's defaults, written to
        out as ab-NAME-VERSION.weights; s's count of them kept for health."""
        caps, choices = self.versions()
        want = []
        fixed = self.decreed()
        for name, on in sorted(caps.items()):
            if name in fixed:
                continue
            want.append(("ab-%s-%s" % (name, "off" if on else "on"),
                         "# A/B: %s %s, the rest as the defaults\ncaps = baseline, %s%s\n" % (name, "off" if on else "on", "-" if on else "", name)))
        slots = {r["slot"]: r for r in self.models()}
        # A version that plays the very games of the defaults has nothing to say, and
        # asking again on each new set of defaults only spends the fleet (ladder 2).
        for j, v in self.sequential().items():
            if v.get("d") == 0 and v.get("se") == 0 and v.get("seeds", 0) >= 55:
                self.flag("ab", "%s plays the same games as the defaults: dead, or waiting on another setting" % v["text"].split("\n")[0][2:],
                          key="dead:%s" % self.trial_key(v["text"]))
        patches = os.path.join(self.q, "patches")
        for name, (dflt, vs) in sorted(choices.items()):
            lo, hi = self.ranges().get(name, (0, len(vs)))
            for i, v in enumerate(vs):
                if i == int(round(dflt)) or not lo <= i <= hi:
                    continue
                # A slot with no patch in it stops a census: asked for only when trained.
                # A whole named brain, a person's to choose (styles.rs): read one by hand
                # (`new census trial="bot_style = 3"`). Asked each generation it is seven lanes
                # of what is already known, and at a generation's bar one could replace the brain.
                if name == "bot_style":
                    continue
                if name == "patch":
                    f = os.path.join(patches, "%d.bin" % i)
                    if os.path.exists(f):
                        # Stamped with its file: a slot retrained is a new trial.
                        sha = hashlib.sha256(open(f, "rb").read()).hexdigest()[:12]
                        want.append(("ab-patch-%d" % i, "# A/B: patch slot %d, sha %s, against none\npatch = %d\n" % (i, sha, i)))
                    continue
                # Whole nets in place of the rules are retired from the search: every
                # slot read about -20 a seat. A transform over the rules replaces them.
                if name == "model" and self.cfg.get("models") is False:
                    continue
                if name == "model":
                    # A slot with a model in it, stamped with its file: a
                    # slot given a new model is a new trial.
                    if i not in slots:
                        continue
                    r = slots[i]
                    want.append(("ab-model-%d-%s" % (i, r["name"]), "# A/B: model slot %d %s, sha %s, against %s\nmodel = %d\n"
                                 % (i, r["name"], r["sha"], vs[int(round(dflt))], i)))
                    continue
                want.append(("ab-%s-%s" % (name, v), "# A/B: %s %s against %s\n%s = %d\n" % (name, v, vs[int(round(dflt))], name, i)))
        left = [(f, text) for f, text in want if not s["tried"].get(self.trial_key(text))]
        s["ab"] = {"versions": len(want), "left": len(left)}
        os.makedirs(out, exist_ok=True)
        files = []
        for f, text in left[:n]:
            p = os.path.join(out, f + ".weights")
            open(p, "w").write(text)
            files.append(p)
        return files

    # ---- model slots: a league of learned brains, 1 to 7 -------------------------------
    # Paul, 29 October: "we are training an AI brain, its output should be
    # fed back into a competing model, where we can have an enum of up to
    # 0-7 different alternate ai models. we can name the models as
    # generations progress." The brain's choice `model` (treadcore 37b6b65):
    # 0 the rules, k the net in slot k. The slots are this queue's:
    # models/k.bin, and models/models.tsv naming each by its generation
    # (gN-what, N counting up from the first seven, the nets in
    # treadcore's nets/). Each finished train or school run is the next
    # generation: an empty slot takes it, else the slot whose A/B read
    # against the rules is lowest, never the defaults' own. A slot's trial
    # is stamped with its file's hash, so a trial of the net it held
    # before is no evidence for the net it holds now. Each census sends
    # the slots it plays (model_sends).
    MODEL_SLOTS = 7

    def models_file(self):
        return os.path.join(self.q, "models", "models.tsv")

    def models(self):
        """[{slot, name, gen, source, sha}] of the filled slots."""
        try:
            lines = open(self.models_file()).read().splitlines()[1:]
        except OSError:
            return []
        out = []
        for l in lines:
            p = l.split("\t")
            if len(p) >= 5 and os.path.exists(os.path.join(self.q, "models", "%s.bin" % p[0])):
                out.append({"slot": int(p[0]), "name": p[1], "gen": int(p[2]), "source": p[3], "sha": p[4]})
        return out

    def model_put(self, rows, slot, name, gen, src):
        dst = os.path.join(self.q, "models", "%d.bin" % slot)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst + ".part")
        os.replace(dst + ".part", dst)
        sha = hashlib.sha256(open(dst, "rb").read()).hexdigest()[:12]
        rows = [r for r in rows if r["slot"] != slot] + [{"slot": slot, "name": name, "gen": gen, "source": src, "sha": sha}]
        with open(self.models_file() + ".part", "w") as f:
            f.write("slot\tname\tgeneration\tsource\tsha\n")
            for r in sorted(rows, key=lambda r: r["slot"]):
                f.write("%d\t%s\t%d\t%s\t%s\n" % (r["slot"], r["name"], r["gen"], r["source"], r["sha"]))
        os.replace(self.models_file() + ".part", self.models_file())
        self.flag("models", "model slot %d is %s (generation %d, from %s)" % (slot, name, gen, os.path.basename(src)),
                  key="model:%d:%s" % (slot, sha), progress=True)
        return rows

    def model_stale(self, text):
        """A trial of a slot's model that the slot no longer holds."""
        m = re.search(r"^# A/B: model slot (\d+) \S+, sha (\w+)", text, re.M)
        if not m:
            return False
        r = next((r for r in self.models() if r["slot"] == int(m.group(1))), None)
        return not r or r["sha"] != m.group(2)

    def best_slot(self):
        """The slot whose A/B reads strongest against the rules on today's defaults,
        its file still there; with none read, the newest generation. None: no slots."""
        rows = [r for r in self.models() if os.path.exists(r["source"])]
        if not rows:
            return None
        read = {}
        for v in self.sequential().values():
            m = re.search(r"^# A/B: model slot (\d+) ", v["text"], re.M)
            if m and v.get("d") is not None:
                read[int(m.group(1))] = v["d"]
        known = [r for r in rows if r["slot"] in read]
        if known:
            return max(known, key=lambda r: read[r["slot"]])
        return max(rows, key=lambda r: r["gen"])

    def models_update(self):
        rows = self.models()
        if not rows and not self.state.get("models_seeded"):
            # The first generation: the nets treadcore already has, newest first.
            nets = sorted(glob.glob(os.path.join(self.tc, "nets", "*.bin")), key=os.path.getmtime, reverse=True)[:self.MODEL_SLOTS]
            for k, f in enumerate(nets, 1):
                rows = self.model_put(rows, k, "g1-" + os.path.basename(f)[:-4], 1, f)
            self.state["models_seeded"] = True
        taken = self.state.setdefault("models_taken", [])
        for r in self.runs():
            rid, kind = r["id"], r["kind"]
            if kind not in ("train", "school") or rid in taken or self.rstate(rid).get("status") != "done":
                continue
            out = os.path.join(self.q, "results", "%s-%s" % (rid, kind), self.home, "out", "%s-%s" % (rid, kind))
            nets = glob.glob(os.path.join(out, "*.bin"))
            if kind == "school":
                # Its last round.
                nets = sorted(nets, key=lambda f: int(re.sub(r"\D", "", os.path.basename(f)) or 0))[-1:]
            else:
                nets = sorted(nets, key=os.path.getmtime)[-1:]
            if not nets:
                taken.append(rid)
                continue
            gen = max([x["gen"] for x in rows] or [0]) + 1
            free = [k for k in range(1, self.MODEL_SLOTS + 1) if k not in {x["slot"] for x in rows}]
            if free:
                slot = free[0]
            else:
                # The weakest against the rules, by its A/B read; a slot
                # not read yet is kept, and so is the defaults' own.
                own = int(self.defaults_at(self.sha()).get("model", 0))
                read = {}
                for v in self.sequential().values():
                    m = re.search(r"^# A/B: model slot (\d+) ", v["text"], re.M)
                    if m:
                        read[int(m.group(1))] = v["d"]
                scored = [(read[x["slot"]], x["slot"]) for x in rows if x["slot"] in read and x["slot"] != own]
                if not scored:
                    # It waits for the slots' reads: a run is never
                    # dropped for want of a slot.
                    continue
                slot = min(scored)[1]
            taken.append(rid)
            rows = self.model_put(rows, slot, "g%d-%s-%s" % (gen, rid, os.path.basename(nets[0])[:-4]), gen, nets[0])

    def model_sends(self, jobs):
        """Each census job gets the slots it plays: its trial's and the
        defaults' own."""
        own = int(self.defaults_at(self.sha()).get("model", 0))
        for j in jobs:
            m = re.search(r"echo (\S+) \| base64 -d > \$Q/trials/", j.get("cmd", ""))
            if j.get("kind") != "weights" or not m:
                continue
            w = parse_weights(base64.b64decode(m.group(1)).decode())
            if w.get("patch"):
                src = os.path.join(self.q, "patches", "%d.bin" % int(w["patch"]))
                if os.path.exists(src):
                    j.setdefault("send", []).append({"src": src, "dst": "~/%s/patches/%d.bin" % (self.home, int(w["patch"]))})
            k = w.get("model")
            for slot in {int(k) if k else 0, own} - {0}:
                src = os.path.join(self.q, "models", "%d.bin" % slot)
                if os.path.exists(src):
                    j.setdefault("send", []).append({"src": src, "dst": "~/%s/models/%d.bin" % (self.home, slot)})

    def unit_weights(self):
        """suggest.py's UNIT: weights from 0 to 1, which stop halfway to 1."""
        try:
            m = re.search(r"UNIT = set\('([^']*)'", open(os.path.join(self.tc, "scripts", "suggest.py")).read())
        except OSError:
            m = None
        return set(m.group(1).split()) if m else set()

    def wide_trials(self, n, out, g, defaults):
        """Trials past the fit's bound: three weights at a time, each a
        quarter to four times its default (at least 1.4 times either way),
        the weights the fit is least sure of the likelier. The fit's own
        trials sit at its curves' tops, within what has been read; when they
        stop finding, the room left is outside it."""
        dflt = parse_weights(open(defaults).read())
        try:
            rows = list(csv.DictReader(open(os.path.join(out, "curves.tsv")), delimiter="\t"))
        except OSError:
            return []
        pool = {r["weight"]: float(r["gain_se"]) + 0.1 for r in rows if dflt.get(r["weight"], 0) > 0}
        unit, rnd, files = self.unit_weights(), random.Random(1000003 * g + 7), []
        names = sorted(pool)
        for i in range(n):
            pick = set()
            while len(pick) < min(3, len(names)):
                pick.add(rnd.choices(names, weights=[pool[x] for x in names])[0])
            lines = []
            for w in sorted(pick):
                d = dflt[w]
                y = d * 2 ** (rnd.choice((-1, 1)) * rnd.uniform(0.5, 2.0))
                if w in unit and y > d:
                    y = min(y, d + (1 - d) / 2) if d < 1 else d
                if abs(y - d) > 1e-9:
                    lines.append("%s = %.6g" % (w, y))
            if lines:
                f = os.path.join(out, "wide-%d.weights" % i)
                with open(f, "w") as fh:
                    fh.write("# orrery: wide, past the fit's bound (the search stalled)\n" + "\n".join(lines) + "\n")
                files.append(f)
        return files

    # LOOK FAR (1 November). The fit's reach is one doubling, two when stalled. w_pos_fortify was promoted
    # at 6.0 under game 1 and stood at nearly four doublings from where it wanted to be under game 4,
    # and the fit could not reach it. So under each new game every dial is read alone at a quarter and at
    # four times today's value, a share of each generation until they are done. They are ordinary trials,
    # and go by the ordinary road: nothing is promoted because it was far.
    FAR_SHARE = 0.5   # half of each generation's new trials, since 13 November (0.25 before)
    # ONE DIAL AT A TIME, ROUND AFTER ROUND (Paul, 13 November: "can we adjust one parameter at a time ...
    # is there a way to make it more specific"). The fit's trials move three or four dials together:
    # 7,051 of 8,082 first reads since 6 November, their true gains spread 0.25 to 0.30 a seat, and
    # what passed held +0.06 and -0.02 on fresh seeds; nothing says which dial did what, and a good move
    # is read with two that cancel it. The 875 that moved one dial spread 1.15. The far read was the one
    # road that asks one dial alone, and it ran once a game. Now when a round is done the next begins on
    # the defaults of its day, a step nearer: four times, twice, then the root of two, and round those
    # two again for as long as the defaults keep moving. A round on defaults already read waits.
    FAR_STEPS = (4.0, 2.0, 1.41)

    def far_step(self, far):
        return self.FAR_STEPS[min(far.get("round", 0), len(self.FAR_STEPS) - 1)] if far.get("round", 0) < len(self.FAR_STEPS) else self.FAR_STEPS[1 + (far["round"] - 1) % 2]

    def far_trials(self, n, out, defaults):
        """Up to n trials of the far read still to do, written to out as far-NAME.lo/hi.weights."""
        game = self.game_at(self.sha())
        far = self.state.get("far")
        if not far or far.get("game") != game:
            dflt = parse_weights(open(defaults).read())
            _, choices = self.versions()
            skip = self.decreed() | set(choices) | {"bot_style", "patch", "model"}
            names = sorted(k for k, v in dflt.items() if v > 0 and k not in skip)
            far = self.state["far"] = {"game": game, "todo": ["%s.%s" % (k, e) for k in names for e in ("lo", "hi")], "asked": {}, "total": 2 * len(names),
                                       "round": 0, "on": hashlib.sha1(open(defaults).read().encode()).hexdigest()[:12]}
            self.flag("far", "game %s: each of %d dials to be read at a quarter and four times, %d trials" % (game, len(names), far["total"]),
                      key="far:%s" % game, progress=True)
        elif not far["todo"] and len(self.FAR_STEPS) > 1:
            on = hashlib.sha1(open(defaults).read().encode()).hexdigest()[:12]
            if far.get("round", 0) + 1 < len(self.FAR_STEPS) or on != far.get("on"):
                dflt = parse_weights(open(defaults).read())
                _, choices = self.versions()
                skip = self.decreed() | set(choices) | {"bot_style", "patch", "model"}
                names = sorted(k for k, v in dflt.items() if v > 0 and k not in skip)
                far.update({"todo": ["%s.%s" % (k, e) for k in names for e in ("lo", "hi")], "total": 2 * len(names), "round": far.get("round", 0) + 1, "on": on})
                self.flag("far", "one dial at a time, round %d: each of %d dials read alone at %.3g times today's value and at today's over %.3g, %d trials" % (
                    far["round"] + 1, len(names), self.far_step(far), self.far_step(far), far["total"]), key="far:%s:%d" % (game, far["round"]), progress=True)
        # A job retired by a generation before it ran was never read: it goes back.
        gone = self.ids("stopped")
        for jid, what in list(far.get("asked", {}).items()):
            if jid in gone:
                del far["asked"][jid]
                key = what[len("far-"):]
                if key not in far["todo"]:
                    far["todo"].insert(0, key)
        dflt, unit, files = parse_weights(open(defaults).read()), self.unit_weights(), []
        for key in far["todo"][:]:
            if len(files) >= n:
                break
            name, end = key.rsplit(".", 1)
            d = dflt.get(name, 0)
            step = self.far_step(far)
            y = d / step if end == "lo" else d * step
            if end == "hi" and name in unit:
                y = d + (1 - d) * min(0.5, (step - 1) / 2) if d < 1 else d
            lo, hi = self.ranges().get(name, (None, None))
            if lo is not None:
                y = min(hi, max(lo, y))
            if d <= 0 or abs(y - d) <= 1e-9 * max(d, 1):
                far["todo"].remove(key)
                continue
            f = os.path.join(out, "far-%s.weights" % key)
            with open(f, "w") as fh:
                fh.write("# orrery: far, under game %s: %s at %s today's\n%s = %.6g\n" % (
                    game, name, ("a quarter of" if end == "lo" else "four times") if step == 4 else ("1/%.3g of" % step if end == "lo" else "%.3g times" % step), name, y))
            files.append(f)
        return files

    def far_asked(self, names):
        far = self.state.get("far")
        for n in names:
            key = n[len("far-"):]
            if far and key in far["todo"]:
                far["todo"].remove(key)

    # THE TEMPERAMENT MATRIX, READ AGAIN AND AGAIN (Paul, 1 November: "connect biorhythems to the output
    # temperment"; "can these be setup in a way to achieve this in many generations in the future"). The
    # fit cannot read these twelve dials: they stand at 0, and it works on a log scale. So every
    # TEMPER_EVERY generations each entry is read each way alone, with the mood's older road shut, on the
    # sine wave, and goes by the ordinary road. Three reads of 400 seeds go with them, to fold: the waves
    # driving nothing, which are the same games and show chance; the mood as it stands; and the mood at full.
    TEMPER_SHARE = 0.15
    TEMPER_EVERY = 0   # off since 13 November: three rounds, 24 settings, 9,869 seeds, none past z 2 upward (12 before)
    TEMPER_STEP = 0.5
    TEMPER_ROWS = ("engage", "press", "retreat", "trigger")

    def temper_trials(self, n, out):
        """Up to n of the matrix's trials still to read, as temper-NAME.lo/hi.weights."""
        if not self.TEMPER_EVERY or "temper_engage_1" not in self.defaults_at(self.sha()):
            return []
        gens = len(self.promotions())
        tp = self.state.setdefault("temper", {"todo": [], "asked": {}, "at_gen": None, "rounds": 0})
        gone = self.ids("stopped")
        for jid, what in list(tp.get("asked", {}).items()):
            if jid in gone:
                del tp["asked"][jid]
                tp["todo"].insert(0, what[len("temper-"):])
        if not tp["todo"] and (tp.get("at_gen") is None or gens - tp["at_gen"] >= self.TEMPER_EVERY):
            tp.update({"at_gen": gens, "rounds": tp.get("rounds", 0) + 1,
                       "todo": ["temper_%s_%d.%s" % (r, i, e) for r in self.TEMPER_ROWS for i in (1, 2, 3) for e in ("lo", "hi")]})
            for name, text in (("bio-null", "bio = 1\nbio_amount = 0\n"), ("bio-mood", "bio = 1\n"), ("bio-full", "bio = 1\nbio_amount = 1\n")):
                self.new_run("census", {"trial": text, "name": name, "seeds": 400, "adopt": "no"}, "auto")
            self.flag("temper", "round %d of the temperament matrix: %d trials, and three reads to fold" % (tp["rounds"], len(tp["todo"])),
                      key="temper:%d" % tp["rounds"], progress=True)
        files = []
        for key in tp["todo"][:n]:
            name, end = key.rsplit(".", 1)
            f = os.path.join(out, "temper-%s.weights" % key)
            with open(f, "w") as fh:
                fh.write("# orrery: the temperament matrix\nbio = 1\nbio_amount = 0\n%s = %g\n" % (name, -self.TEMPER_STEP if end == "lo" else self.TEMPER_STEP))
            files.append(f)
        return files

    def temper_asked(self, names):
        tp = self.state.get("temper")
        for x in names:
            key = x[len("temper-"):]
            if tp and key in tp["todo"]:
                tp["todo"].remove(key)

    # THE WIDTH WATCH (Paul, 1 November: "do we need to expand its dimensions"; "in many generations in the
    # future"; "add the options in the settings page"). Whether a net has run out of room is a thing to
    # measure from time to time, and not to guess from a chart. Every WIDTH_EVERY generations: record
    # WIDTH_SEEDS seeds of today's brain, train the same data at each of WIDTHS, and read each on held-out
    # seeds. Past the bar it raises a flag for a person. IT CHANGES NO NET: a wider net needs a person's
    # yes, because the game ships this file, and copying better is not yet playing better.
    WIDTH_EVERY = 20
    WIDTH_SEEDS = 240
    WIDTH_BAR = 1.0
    # The shapes (the plan of 2 November, chapter 12): widths at two hidden layers, and one deeper.
    WIDTHS = ("32", "64", "128", "64x3")
    WIDTH_NOW = "64"

    def width_watch(self):
        """The watch's next step: jobs, if any are due."""
        wd = self.state.setdefault("width", {"history": [], "at_gen": None, "n": 0})
        gens = len(self.promotions())
        gpu = [h for h in self.hosts if "gpu" in h.get("caps", [])]
        if wd.get("job"):
            if wd["job"] not in self.ids("done", "failed", "stopped"):
                return []
            row = self.width_read(wd["job"], wd.get("run"))
            wd["history"].append(row)
            for k in ("job", "run", "name"):
                wd.pop(k, None)
            save(os.path.join(self.pd, "widths.json"), {"history": wd["history"], "widths": self.WIDTHS, "now": self.WIDTH_NOW})
            self.flag("width" if row.get("verdict") == "widen" else "width-read", row.get("said", ""), key="width:%d" % len(wd["history"]), progress=row.get("verdict") != "widen")
            return []
        if wd.get("run"):
            st = self.rstate(wd["run"])
            if st.get("status") != "done":
                return []
            if not gpu or not self.prepared(gpu[0]["name"]):
                return []
            jid = "width-%04d" % wd["n"]
            wd["job"] = jid
            # A SHAPE WATCH (the plan of 2 November, chapter 12): widths and depths alike, "64" two
            # hidden layers of 64 as ever, "64x3" three of them; tools/bc takes WIDTH and DEPTH.
            loop = "".join(
                "WIDTH=%d DEPTH=%d GPU_GB=1 BC_DEVICE=cuda %s/treadcore-bc ~/fleet/%s/shards $D/w%s.bin 12 32768 0.01 > $D/w%s.log 2>&1 || echo failed at %s\n"
                % (self.shape(s)[0], self.shape(s)[1], self.cdir(), wd["name"], s, s, s)
                for s in self.WIDTHS)
            return [{"id": jid, "kind": "net", "title": "the shape watch: the same data at %s" % ", ".join(str(w) for w in self.WIDTHS),
                     "needs": "host:" + gpu[0]["name"], "after": [self.prep_id(gpu[0]["name"])],
                     "cmd": "D=~/%s/out/%s; mkdir -p $D\n%s%sgrep -h 'drive\\|gun' $D/w*.log | tail -8\n" % (self.home, jid, self.trainer(), loop),
                     "fetch": "%s/out/%s" % (self.home, jid), "timeout_s": 4 * 3600}]
        # The count begins when the watch is first seen: "in the future", and nothing to measure today.
        if wd.get("at_gen") is None:
            wd["at_gen"] = gens
        if not self.WIDTH_EVERY or not gpu or gens - wd["at_gen"] < self.WIDTH_EVERY:
            return []
        wd["n"] += 1
        wd["at_gen"] = gens
        wd["name"] = "width%d" % wd["n"]
        wd["run"] = self.new_run("record", {"run": wd["name"], "count": self.WIDTH_SEEDS, "per": 12, "secs": 600, "seed0": 9200000 + 100000 * wd["n"]}, "auto")
        return []

    # THE GAUNTLET, NIGHTLY (the plan of 2 November, chapter 15): every single-decision file in
    # scenarios/gauntlet, for the rules, the untrained net and every net in nets/, on this Mac's checkout
    # of main, written to build/train/gauntlet.tsv, which Results, Gauntlet reads. Once each
    # GAUNTLET_EVERY_H hours; 0 turns it off. It ran on the Mac, the one machine with the checkout the
    # people read; with the Mac's lane set aside (3 November) it waited for nothing, so now it is a job
    # for any fast machine, run in the queue's own checkout of the commit, its record fetched back to
    # results/ where treadcore-view.py reads the newest (the Mac's own file beside it).
    GAUNTLET_EVERY_H = 24

    def gauntlet_watch(self):
        g = self.state.setdefault("gauntlet", {})
        if g.get("job"):
            if g["job"] not in self.ids("done", "failed", "stopped"):
                return []
            g["last_at"] = time.time()
            self.flag("gauntlet", "the gauntlet ran (%s): Results, Gauntlet has the record" % g["job"], key="gauntlet:%s" % g["job"], progress=True)
            g.pop("job", None)
            return []
        if not self.GAUNTLET_EVERY_H or time.time() - g.get("last_at", 0) < self.GAUNTLET_EVERY_H * 3600:
            return []
        jid = "gauntlet-%s" % time.strftime("%m%d-%H%M")
        g["job"] = jid
        return [self.gauntlet_job(jid)]

    def gauntlet_job(self, jid):
        """The gauntlet as a fleet job: the harness's GAUNTLET read in the queue's checkout, its tsv in
        the job's out directory, fetched back. Fast machines first, any CPU lane if none is free."""
        cmd = (
            "set -o pipefail; [ -f ~/.cargo/env ] && . ~/.cargo/env; export PATH=$HOME/.cargo/bin:$PATH\n"
            "Q=~/%s; C=%s; O=$Q/out/%s; mkdir -p $O\n"
            "cd $C/wt && GAUNTLET=1 GAUNTLET_RUNS=100 OUT=$O THREADS=${THREADS:-$(nproc 2>/dev/null || sysctl -n hw.ncpu)} "
            "$C/census-bin --ignored learn::harness::train --nocapture 2>&1 | tee $O/harness.log | tail -60\n"
        ) % (self.home, self.cdir(), jid)
        return {"id": jid, "kind": "gauntlet", "title": "the gauntlet: every single decision, the rules and every net, 100 seeds each",
                "needs": "fast", "or": "cpu", "after_host": self.after_host(), "cmd": cmd, "fetch": "%s/out/%s" % (self.home, jid), "timeout_s": 2 * 3600}

    @staticmethod
    def shape(s):
        """A shape's (width, depth) from "64" or "64x3"."""
        w, _, d = str(s).partition("x")
        return int(w), int(d or 2)

    def width_read(self, jid, run):
        """What a watch found: each shape's agreement on drive and gun, and whether one says widen or
        deepen past the bar; the shapes are read against the shape in use."""
        rows = {}
        for w in self.WIDTHS:
            got = {}
            for f in glob.glob(os.path.join(self.q, "results", jid, self.home, "out", jid, "w%s.log" % w)):
                for l in open(f, errors="replace"):
                    m = re.match(r"\s*(drive|gun)\s+([\d.]+)% \+/- ([\d.]+)", l)
                    if m:
                        got[m.group(1)] = (float(m.group(2)), float(m.group(3)))
            rows[str(w)] = got
        row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "gen": len(self.promotions()), "seeds": self.WIDTH_SEEDS, "job": jid, "rows": rows, "verdict": "no reading"}
        mean = lambda w: (rows.get(str(w), {}).get("drive", (None,))[0], rows.get(str(w), {}).get("gun", (None,))[0])
        a = mean(self.WIDTH_NOW)
        if None in a:
            row["said"] = "the shape watch %s read nothing for the shape in use: see its log" % jid
            return row
        # The best of the other shapes against the one in use; a tie keeps the smaller shape.
        best, gain = None, None
        for s in self.WIDTHS:
            b = mean(s)
            if str(s) == str(self.WIDTH_NOW) or None in b:
                continue
            g = ((b[0] - a[0]) + (b[1] - a[1])) / 2
            if gain is None or g > gain:
                best, gain = s, g
        if gain is None:
            row["said"] = "the shape watch %s read nothing: see its log" % jid
            return row
        row["gain"], row["best"] = round(gain, 2), str(best)
        row["verdict"] = "widen" if gain >= self.WIDTH_BAR else "stay"
        row["said"] = "the shape watch: %s against %s on held-out seeds, %+.2f points of agreement on drive and gun: %s" % (
            best, self.WIDTH_NOW, gain, "past the bar, a person should look" if gain >= self.WIDTH_BAR else "stay")
        return row

    # REGIONS (Paul, 1 November: "Selecting regions of operation with the terrain map"). A person draws a
    # box on a terrain, and tools/regions.py writes it to QUEUE/regions.json with how many trials to read
    # in it. They go ahead of the search, spaced evenly by a Halton sequence, on the log scale of each
    # dial, and go by the ordinary road: nothing is promoted because a person looked there.
    @staticmethod
    def halton(i, base):
        f, r = 1.0, 0.0
        i += 1
        while i:
            f /= base
            r += f * (i % base)
            i //= base
        return r

    def region_trials(self, n, out):
        """Up to n trials of what regions ask, as region-ID-I.weights. A job retired before it ran goes back."""
        regions = load(os.path.join(self.q, "regions.json"), {}) or {}
        state = self.state.setdefault("regions", {})
        gone, files = self.ids("stopped"), []
        for g in regions.get("regions", []) if isinstance(regions, dict) else []:
            mine = state.setdefault(g["id"], {"jobs": {}})
            for jid in [j for j in mine["jobs"] if j in gone]:
                del mine["jobs"][jid]
            held = set(mine["jobs"].values())
            for i in range(g.get("n", 0)):
                if len(files) >= n:
                    return files
                if i in held:
                    continue
                u, v = self.halton(i, 2), self.halton(i, 3)
                a = g["a0"] * (g["a1"] / g["a0"]) ** u
                b = g["b0"] * (g["b1"] / g["b0"]) ** v
                f = os.path.join(out, "region-%s-%d.weights" % (g["id"], i))
                with open(f, "w") as fh:
                    fh.write("# orrery: a person's region %s, over %s and %s\n%s = %.6g\n%s = %.6g\n" % (g["id"], g["a"], g["b"], g["a"], a, g["b"], b))
                files.append(f)
        return files

    # ---- the sequential read -----------------------------------------------------------
    # Fishtest's way, in seeds: a test begun is read on until it is decided,
    # pooled. At 55 seeds a census is good to +/-0.66 a seat (a seed swings
    # 4.9), so a trial truly +0.5 above passed 11 times in 100, and a trial
    # no better passed 2 in 100: of 1,000 trials after w0034 every one that
    # passed was noise, and each cost two held-out reads of 400 seeds. Each
    # stage: (seeds read by then, read on at z past, pass at z past). Against
    # one fixed read of 55, simulated with the measured noise and a fleet of
    # mostly no-better trials: 40% more real finds a seed, a quarter of the
    # false passes (29 October). The held-out reads still decide.
    # Since 29 October the stages grow by half, not double (Paul: "more like
    # 1.2x or 1.6x"), the read-on bar rising from 0.5 to 1.7 across them:
    # 55, 82, 124, 187, 275, 418 seeds. Simulated, 5% more gain a day.
    SEQ = ((1, 0.5, None), (1.5, 0.8, None), (2.25, 1.1, None), (3.4, 1.4, 2.6), (5, 1.7, 2.6), (7.6, None, 2.0))

    # The held-out reads decide together: pooled, 800 seeds, z past HELD_Z and
    # no map two errors under. Each read had to pass alone (d past two of its
    # errors, about +0.55), and a trial truly +0.6 did that both times one
    # time in three: w1198 (+0.67 +/- 0.19 pooled, z 3.5) and w1266 (+0.59 +/-
    # 0.16, z 3.7) each passed one read and were lost (29 October). A trial no
    # better reaches z 3 one time in 750, near the old rule's one in 2,000; a
    # trial +0.6 does six times in ten.
    HELD_Z = 3.0

    HELD_READS = 6
    HELD_ON_Z = 1.0

    def held_more_jobs(self, seq):
        """THE HELD-OUT READ IS READ ON (13 November). One read of 400 seeds is good to about 0.40 a seat, so at
        a bar of z 2.5 only a read of +1.0 passes, and a trial truly +0.3 passes four times in a hundred:
        "a generation takes one read" was the rule of a low bar. A held-out read that is promising and
        undecided (pooled z from HELD_ON_Z up to the bar) is read again on fresh seeds, pooled, up to
        HELD_READS reads in all: at 6, 2,400 seeds, good to 0.17. One read, as it was, at 1."""
        jobs, more = [], self.state.setdefault("held_more", {})
        if self.HELD_READS <= 1:
            return jobs
        pairs = self.held_pairs()
        for jid in list(self.state["held_read"])[-200:]:
            ds = pairs.get(jid, [])
            if jid not in seq or not ds or len(ds) < more.get(jid, 1) or len(ds) >= self.HELD_READS:
                continue
            p_ = self.pool(ds)
            if not p_ or p_["every"][1] <= 0:
                continue
            z_ = p_["every"][0] / p_["every"][1]
            if self.HELD_ON_Z <= z_ < self.HELD_Z - self.ease():
                more[jid] = len(ds) + 1
                jobs += self.held_read(jid, len(ds) + 1, seq[jid]["text"], high=True)
        return jobs


    def held_pass(self, ds):
        """True when a trial's held-out reads, pooled, pass: one is enough for a generation."""
        p = self.pool(ds) if ds else None
        return bool(p) and p["every"][1] > 0 and p["every"][0] / p["every"][1] >= self.HELD_Z - self.ease() and not p["below"]

    # ---- difficulty: a promotion about every PROMOTE_EVERY minutes ---------------------
    # Paul, 29 October: "something like a block height difficulty ... a
    # promotion every 20 minutes at average." Every bar (each stage's read
    # on and pass, the held-out reads' HELD_Z) is lowered by one ease, in
    # errors. difficulty-sim.py reads what each ease buys. The trials are a
    # bulk truly N(-0.35, 0.24) a seat and a few real finds (0.3% at +0.6):
    # the spread the held-out reads allow (first reads near z 2.3 held out
    # at -0.10 on average) and the finds the fleet made (two in a day at
    # ease 0). There, 5,250 seeds an hour: ease 0 a promotion each 16 hours,
    # +0.9 a day; 1 each 5 hours, 3% truly worse, +2.0; 1.5 each 4 hours, 7%
    # worse, +1.8; 2 each 2.3 hours, 18% worse, +1.9; 3 each 68 minutes,
    # half worse, +0.3; 4 each 36 minutes, the brain 3.7 a day poorer. One
    # in 20 minutes is past what the trials hold. The floor, 1.5, is the
    # one ease within a few tenths of the most gain under each spread the
    # data leaves open (0.24 with or without the finds, 0.30), and keeps the
    # truly worse to one in ten or fewer; 2, first chosen from a spread of
    # 0.30 alone, let one in five through under the measured one.
    # Paul, the same evening, the brain's tests set right and w1266
    # promoted: "lets try for a promotion every 2.5 hours." The pace of
    # ease 2 under the measured trials, so its floor: one promotion in
    # five may be truly worse there (one in fourteen at 1.5), and the
    # anchor reads are what stand against it.
    # Like a block's difficulty: no promotion in its time and the ease
    # rises a step each PROMOTE_EVERY more; a promotion sooner than its
    # time lowers it by half a step for each halving (one quick promotion
    # is as much luck as a sign). The anchor reads catch the worse
    # (anchor_trial). PROMOTE_EVERY is the floor's own pace, so the ease
    # rests below the floor rather than pinned to it; a faster fleet
    # promotes sooner at the same ease.
    PROMOTE_EVERY = 150
    # A RATCHET (Paul, 1 November: "pass every half hour or so. And each generation this could
    # continue to get more difficult, until we find nothing for 4 hours, then it gets easier
    # again"). Each generation the bars rise a step; four hours with no generation they fall,
    # and fall again each hour after, to the ceiling. Simulated on this game's own noise (a
    # seed swings 9.5 a seat, not the 4.9 above), 5,000 seeds an hour, one held read of 400:
    # 2.1 (the "10% easier" asked, held z 0.9) one in 56 minutes, 20% truly worse; 2.5 one in
    # 38, 28% worse; 2.75 one in 30, 34% worse; gain a day about +14 at all of them. So a
    # generation is carried, unproven, and only line_proof puts the line on main.
    # THE BAR STANDS AT z 2.5 (13 November, Always Forward): the ease began at 2.5 and could reach 2.75, a held-out
    # bar of z 0.25, and from 6 to 13 November ten generations passed it and were worth nothing together.
    START_EASE = 0.5
    EASE_MAX = 0.5
    HARDEN = 0.05         # each generation
    DRY_MIN = 240         # nothing for four hours
    EASE_STEP = 0.25      # then this, and again each DRY_AGAIN_MIN
    DRY_AGAIN_MIN = 60
    # Easing the read-on bars with the rest only spends lanes on what will be dropped: 38% of
    # them on 31 October. Kept within half an error: more gain a day at every ease simulated.
    KEEP_EASE = 0.5

    def promotions(self):
        """[(approved epoch, run id, state)] of the promotions on main, oldest first."""
        out = []
        for r in self.runs():
            if r["kind"] != "promote":
                continue
            st_ = self.rstate(r["id"])
            if st_.get("status") in ("approved", "self-modified") and st_.get("approved"):
                out.append((time.mktime(time.strptime(st_["approved"], "%Y-%m-%dT%H:%M:%S")), r["id"], st_))
        return sorted(out, key=lambda x: x[0])

    def ease(self):
        """The errors the pass bars are lowered by now (state difficulty): the ratchet."""
        if getattr(self, "_ease", None) is not None:
            return self._ease
        d = self.state.setdefault("difficulty", {})
        last = (self.promotions() or [None])[-1]
        now = time.time()
        if d.get("rule") != "ratchet":
            d.clear()
            d.update({"rule": "ratchet", "base": self.START_EASE, "since": now, "seen": last[1] if last else None, "generations": 0})
        # A value moved by hand moves the bar once; the ratchet goes on from there.
        tuned = getattr(self, "tuned", {})
        if "ease_now" in tuned and tuned["ease_now"] != d.get("asked"):
            d.update({"base": tuned["ease_now"], "asked": tuned["ease_now"]})
        if last and last[1] != d.get("seen"):
            base = d.get("ease", d["base"])
            d.update({"base": max(0.0, base - self.HARDEN), "since": now, "seen": last[1], "last_gap_min": round((now - d["since"]) / 60),
                      "generations": d.get("generations", 0) + 1})
        dry = (now - d["since"]) / 60
        steps = 0 if dry < self.DRY_MIN else 1 + int((dry - self.DRY_MIN) // self.DRY_AGAIN_MIN)
        self._ease = min(self.EASE_MAX, d["base"] + self.EASE_STEP * steps)
        d.update({"ease": round(self._ease, 3), "held_z": round(self.HELD_Z - self._ease, 3), "floor": self.EASE_MAX,
                  "dry_min": round(dry), "eases_at_min": self.DRY_MIN + (self.DRY_AGAIN_MIN * steps if steps else 0)})
        return self._ease

    ANCHOR = 0   # none since 13 November (3 before): the yardstick and a line coming off ask what it asked

    def anchor_trial(self):
        """Each promotion, once its machines build it, read against the
        defaults ANCHOR promotions back: those as a trial (its census and
        two held-out reads), the values each moved put back. Today's better,
        it fails; if not, it passes as any trial and promotes itself, the
        drift undone."""
        # ANCHOR 0: no anchor reads (13 November). The yardstick reads today against fixed days on fixed seeds,
        # and a line that fails its check comes off; the anchor was the one thing that asked either question.
        if not self.auto() or not self.ANCHOR:
            return
        done = self.state.setdefault("anchored", [])
        p = self.promotions()
        if not p or p[-1][1] in done or not p[-1][2].get("confirmed"):
            return
        back, old, caps = p[-self.ANCHOR:], {}, {}
        for _, _, st_ in back:
            for l in st_.get("changed", []):
                m = re.match(r"^([a-z_][a-z0-9_]*) ([-+0-9.eE]+) -> ([-+0-9.eE]+)$", l)
                if m and m.group(1) not in old:
                    old[m.group(1)] = m.group(2)
                # A switch a promotion flipped (set-defaults.py: "caps
                # name on -> off") is put back as well.
                m = re.match(r"^caps ([a-z_0-9]+) (on|off) -> (on|off)$", l)
                if m and m.group(1) not in caps:
                    caps[m.group(1)] = m.group(2) == "on"
        done.append(p[-1][1])
        if old or caps:
            text = "".join("%s = %s\n" % kv for kv in sorted(old.items()))
            if caps:
                text += "caps = baseline, %s\n" % ", ".join(("" if on else "-") + c for c, on in sorted(caps.items()))
            jid = self.adopt(text, "anchor: the defaults before %s" % back[0][1])
            self.state.setdefault("anchor_trials", []).append(jid)
            self.flag("anchor", "%s reads the defaults before %s against today's, after %s" % (jid, back[0][1], p[-1][1]),
                      key="anchor:%s" % p[-1][1], progress=True)

    # UNDOING TAKES EVIDENCE (1 November). A generation passes at a low bar on purpose, and an anchor read
    # at that bar will pass by chance about as often: w4845, the defaults three back, went on the line as
    # generation 5 on +0.38 +/- 0.51 and +0.18 +/- 0.58, and undid two generations on noise. A find may be
    # carried unproven, because the proof stands behind it. A retreat has nothing behind it, so an anchor
    # must clear the proof's own bar, whatever the ease.
    def held_by_a_person(self, text):
        """QUEUE/hold.json: {"dial": value}. A trial setting a dial to a held value does not promote or
        carry itself, whatever it reads: a change that passes the road and fails a rule set before the
        run waits for a person (1 November: w_pos_fortify 0.4). Its reads go on."""
        hold = load(os.path.join(self.q, "hold.json"), {}) or {}
        vals = parse_weights(text)
        return any(k in vals and abs(vals[k] - float(v)) < 1e-6 for k, v in hold.items())

    def anchor_short(self, name, v):
        """True for an anchor trial whose held-out reads have not reached HELD_Z."""
        if name.split("/", 1)[-1] not in self.state.get("anchor_trials", []):
            return False
        held = v.get("held") or []
        iw = sum(1 / h[1] ** 2 for h in held if h[1] > 0)
        return not iw or sum(h[0] / h[1] ** 2 for h in held if h[1] > 0) / math.sqrt(iw) < self.HELD_Z

    @staticmethod
    def pool(dirs):
        """The censuses of one trial pooled, by inverse variance: {"every":
        (d, se, seeds), "below": a map more than two errors under}. Once a process: the same reads
        are pooled by sequential() four times a pass, and by raise_found()."""
        key = tuple(dirs)
        if key not in _POOLS:
            _POOLS[key] = Plan._pool(dirs)
        return dict(_POOLS[key]) if _POOLS[key] is not None else None

    @staticmethod
    def _pool(dirs):
        every, maps = [], {}
        for d in dirs:
            if Plan.one_map(d):
                continue
            try:
                lines = open(os.path.join(d, "pooled.txt")).read().splitlines()
            except OSError:
                continue
            for l in lines:
                m = re.match(r"^(\S+(?: map)?)\s+([-+][\d.]+) \+/- ([\d.]+)(?: over\s+(\d+) seeds)?", l)
                if not m or float(m.group(3)) <= 0:
                    continue
                row = (float(m.group(2)), float(m.group(3)), int(m.group(4) or 0))
                (every.append(row) if m.group(1) == "every map" else maps.setdefault(m.group(1), []).append(row))

        def comb(rows):
            iw = sum(1 / se ** 2 for _, se, _ in rows)
            return sum(d / se ** 2 for d, se, _ in rows) / iw, 1 / math.sqrt(iw), sum(n for _, _, n in rows)
        if not every:
            return None
        rows = [comb(r) for r in maps.values()]
        return {"every": comb(every), "below": any(dd < -2 * se for dd, se, _ in rows), "above": any(dd > 2 * se for dd, se, _ in rows)}

    @staticmethod
    def one_map(d):
        """A census that read only the generated map: a Mac's, before census_cmd's paste.
        A map is not the game: such a read decides nothing."""
        if d in _ONE_MAP:
            return _ONE_MAP[d]
        try:
            rows = [l.split()[0] for l in open(os.path.join(d, "pooled.txt")) if " +/- " in l and not l.startswith("every map")]
        except OSError:
            return False
        _ONE_MAP[d] = rows == ["generated"]
        return _ONE_MAP[d]

    def sequential(self):
        """{trial: {status, d, se, seeds, z, stage, text}} for every trial on
        today's defaults: reading (a read of it queued or running), read on
        (its stage says more), passed, or dropped. Its reads are its own
        census and the jobs titled "read on N of TRIAL"."""
        title, inflight = {}, set()
        for i, t in self.done_titles().items():
            m = re.match(r"read on \d+ of (w\d+)", t)
            if m:
                title[i] = m.group(1)
        for f in glob.glob(os.path.join(self.q, "queue", "*.json")) + glob.glob(os.path.join(self.q, "running", "*", "*.json")):
            j = load(f, {})
            m = re.match(r"read on \d+ of (w\d+)", j.get("title", ""))
            if m or re.match(r"w\d+$", j.get("id", "")):
                inflight.add(m.group(1) if m else j["id"])
        reads = {}
        for d in self.census_dirs():
            jid = d.rstrip("/").split(os.sep)[-2]
            if re.match(r"w\d+$", jid):
                reads.setdefault(jid, []).insert(0, d)
            elif jid in title:
                reads.setdefault(title[jid], []).append(d)
        base = self.cfg["weights"]["seeds"]
        out = {}
        for jid, ds in reads.items():
            if not has_trial(ds[0]) or not self.same_defaults(self.census_commit(ds[0])):
                continue
            p = self.pool(ds)
            if not p:
                continue
            d, se, n = p["every"]
            z = d / se
            stage = max([i for i, s in enumerate(self.SEQ) if round(s[0] * base) <= n] or [0])
            _, keep, ok = self.SEQ[stage]
            e = self.ease()
            keep, ok = (None if keep is None else keep - min(e, self.KEEP_EASE)), (None if ok is None else ok - e)
            if jid in self.state["held_read"]:
                status = "passed"
            elif jid in inflight:
                status = "reading"
            elif ok is not None and z >= ok and not p["below"]:
                status = "passed"
            elif keep is None or z < keep:
                # A map under blocks a pass, not a read on: eleven maps at 55
                # seeds put one two errors under, by chance, a time in five.
                status = "dropped"
            else:
                status = "read on"
            text = open(os.path.join(ds[0], "trial.weights")).read()
            if self.model_stale(text):
                continue
            out[jid] = {"status": status, "d": d, "se": se, "seeds": n, "z": z, "stage": stage, "text": text}
        return out

    def read_on_jobs(self, seq, room, w):
        """The next stage's census for the trials that read on, highest z
        first: as many seeds again as read so far, on fresh seeds (300M up,
        clear of the trials', the held-out reads' and the rotation's)."""
        jobs = []
        for jid, v in sorted(seq.items(), key=lambda kv: -kv[1]["z"]):
            if len(jobs) >= room:
                break
            if v["status"] != "read on":
                continue
            base = w["seeds"]
            more = round(self.SEQ[v["stage"] + 1][0] * base) - v["seeds"]
            if more <= 0:
                continue
            k = self.state.get("read_on_n", 0)
            self.state["read_on_n"] = k + 1
            eid = "e%04d" % k
            # AHEAD OF NEW TRIALS (1 November). A winner took 49 minutes from its first read to its pass,
            # with 19 minutes of work in it. The rest was queue, ten minutes at each of its stages, behind
            # trials that had not yet shown anything. Whatever has shown something goes first.
            jobs.append({"id": eid, "kind": "weights",
                         "title": "read on %d of %s (%d seeds more, z %+.2f on %d)" % (v["stage"] + 2, jid, more, v["z"], v["seeds"]),
                         "needs": "cpu", "after_host": self.after_host(), "priority": "high",
                         "cmd": self.census_cmd(v["text"], more, 300000000 + 1000 * k, eid),
                         "fetch": "%s/out/%s" % (self.home, eid), "timeout_s": 6 * 3600})
        return jobs

    @staticmethod
    def seq_counts(seq):
        """For plan/search.json: how many trials at each status, and the
        seeds a decided trial took."""
        out = {}
        for v in seq.values():
            out[v["status"]] = out.get(v["status"], 0) + 1
        decided = [v["seeds"] for v in seq.values() if v["status"] in ("passed", "dropped")]
        out["seeds_a_decision"] = round(sum(decided) / len(decided)) if decided else None
        return out

    # ---- the families ------------------------------------------------------------------
    @staticmethod
    def weights_set(text):
        """A .weights file as SCENARIO_SET: name=value ... (comments dropped)."""
        out = []
        for l in text.splitlines():
            l = l.split("#")[0].strip()
            if "=" in l:
                k, v = (x.strip() for x in l.split("=", 1))
                # Words, split on spaces by the test: "baseline, -pings" is one.
                out.append("%s=%s" % (k, v.replace(", ", ",")))
        return " ".join(out)

    # THE HELD-OUT READ IN PIECES (the duty-cycle report's change C; Paul, 5 November: "build C"). A
    # held-out read was one job of 400 seeds, about twelve minutes on one machine, and a passing
    # trial needs two. It is asked as HELD_PIECES jobs of a quarter of the seeds each, on as many
    # machines, and made one census when all are back: every piece's per-seed logs in one folder,
    # pooled by treadcore's pool.sh (written for "a census split over jobs"). A seed plays the map of
    # its own number (n mod k), so the pieces play the very games the one job played, and the read is
    # the same to the digit, under the read's own id; everything that reads a held-out read reads it
    # as before.
    HELD_PIECES = 4

    def held_read(self, jid, k, text, high=True):
        """Trial jid's k-th held-out read: its id and seeds, and its pieces as jobs. A piece already
        asked (ahead of time, by the background job) is not asked again."""
        w = self.cfg["weights"]
        pre = self.state.setdefault("held_ahead", {}).pop(jid, None) if k == 1 else None
        if pre:
            hid, seed0 = pre["hid"], pre["seed0"]
        else:
            hid = "h%04d" % self.state["held_n"]
            seed0 = w["held_seed0"] + 200000 * self.state["held_n"]
            self.state["held_n"] += 1
        title = "held-out read %d of %s (%d seeds)" % (k, jid, w["held_seeds"])
        n = self.HELD_PIECES if self.HELD_PIECES > 1 and w["held_seeds"] % self.HELD_PIECES == 0 else 1
        if n == 1:
            job = {"id": hid, "kind": "weights", "title": title, "needs": self.long_needs(), "after_host": self.after_host(),
                   "cmd": self.census_cmd(text, w["held_seeds"], seed0, hid), "fetch": "%s/out/%s" % (self.home, hid), "timeout_s": 6 * 3600}
            if high:
                job["priority"] = "high"
            return [job]
        per = w["held_seeds"] // n
        rec = self.state.setdefault("held_split", {}).setdefault(hid, {
            "trial": jid, "k": k, "title": title, "seed0": seed0, "per": per, "n": n, "text": text,
            "slots": {}, "tries": {}, "asked": time.strftime("%Y-%m-%dT%H:%M:%S")})
        rec["k"], rec["title"], rec["high"] = k, title, high
        if rec.pop("ahead_only", None):
            # Asked for now: the pieces read ahead are its own, and those still queued go first.
            self.state.get("ahead", {}).pop(jid, None)
            self.raise_queued(set(rec["slots"].values()), high)
        jobs = []
        for i in range(1, n + 1):
            if str(i) in rec["slots"]:
                continue
            jobs.append(self.held_piece(hid, rec, i, high))
        return jobs

    def held_piece(self, hid, rec, i, high, background=False):
        """Piece i of a split held-out read: its quarter of the seeds, on any CPU machine."""
        tries = rec["tries"].get(str(i), 0)
        pid = "%s-p%d" % (hid, i) + ("" if tries == 0 else "r%d" % tries)
        rec["slots"][str(i)] = pid
        # To the fast machines while one is up, as a whole read was: a piece is as slow as its machine,
        # and the read as its slowest piece (5 November: macmini read 100 seeds in 2.0 minutes,
        # columbia in 10.1, and h0802 waited on columbia). The background job's go anywhere.
        job = {"id": pid, "kind": "weights", "needs": "cpu" if background else self.long_needs(), "after_host": self.after_host(),
               "title": "held-out piece %d of %d of read %d of %s (%d seeds)" % (i, rec["n"], rec["k"], rec["trial"], rec["per"]),
               "cmd": self.census_cmd(rec["text"], rec["per"], rec["seed0"] + (i - 1) * rec["per"], pid),
               "fetch": "%s/out/%s" % (self.home, pid), "timeout_s": 6 * 3600}
        if background:
            # The background job's: last in the queue, taken only by a machine with nothing else.
            job["priority"], job["background"] = "low", True
            job["title"] = job["title"].replace("held-out piece", "held-out piece ahead of time:", 1)
        elif high:
            job["priority"] = "high"
        return job

    def raise_queued(self, ids, high):
        """Queued background pieces become the read's own: no longer last, no longer background. The
        queue's file is renamed, as prepare_jobs sets builds aside; a lane that has just taken one
        keeps it as it is."""
        for f in glob.glob(os.path.join(self.q, "queue", "*.json")):
            seq_, _, rest = os.path.basename(f).partition("-")
            if rest[:-5] not in ids:
                continue
            j = load(f, {}) or {}
            j.pop("background", None)
            j["title"] = j.get("title", "").replace("held-out piece ahead of time:", "held-out piece", 1)
            if high:
                j["priority"] = "high"
            else:
                j.pop("priority", None)
            j["replan"] = True
            j["needs"] = self.long_needs()
            new = os.path.join(self.q, "queue", "%d-%s" % (int(time.time() * 1000) - (10 ** 11 if high else 0), rest))
            # Out of the lanes' sight first (they read *.json): a lane that has claimed it keeps it,
            # and the job is never in the queue twice.
            hold = f + ".raise"
            try:
                os.rename(f, hold)
            except OSError:
                continue
            save(new, j)
            os.remove(hold)

    def piece_dir(self, pid):
        ds = sorted(glob.glob(os.path.join(self.q, "results", pid, self.home, "out", pid, "*", "")))
        ds = [d for d in ds if os.path.exists(os.path.join(d, "pooled.txt"))]
        return ds[-1] if ds else None

    def same_class(self, c1, c2):
        """Two censuses' commits play the same defaults and the same game: their reads pool."""
        if not c1 or not c2 or c1.endswith("+") or c2.endswith("+"):
            return False
        if c1 == c2:
            return True
        a, b = self.defaults_at(c1), self.defaults_at(c2)
        common = set(a) & set(b)
        return bool(common) and all(a[k] == b[k] for k in common) and self.game_at(c1) == self.game_at(c2)

    def held_merge(self):
        """Each split held-out read whose pieces are all back, made one census (see HELD_PIECES).
        A piece that failed is asked again, twice at most; a piece read on other defaults than the
        newest of its read weighs nothing and is asked again (the newest decides, as the line's proof
        pools only one line against one main). Returns the pieces asked again."""
        if not self.writer:
            return []
        split = self.state.get("held_split", {})
        done, gone = self.ids("done"), self.ids("failed", "stopped")
        jobs = []
        for hid, rec in list(split.items()):
            if rec.get("ahead_only"):
                continue  # asked ahead of time, and its trial not (yet) asked for the read
            slots = {int(i): pid for i, pid in rec["slots"].items()}
            if len(slots) < rec["n"]:
                continue
            again = []
            for i, pid in sorted(slots.items()):
                if pid in gone:
                    again.append(i)
            dirs = {i: self.piece_dir(pid) for i, pid in slots.items() if pid in done}
            commits = {i: self.census_commit(d) for i, d in dirs.items() if d}
            if commits:
                newest = commits[max(commits, key=lambda i: os.path.getmtime(dirs[i]))]
                again += [i for i, c in commits.items() if not self.same_class(c, newest)]
            for i in sorted(set(again)):
                t = rec["tries"].get(str(i), 0) + 1
                if t > 2:
                    self.flag("held", "%s: piece %d of %s's held-out read failed three times; the read is dropped" % (hid, i, rec["trial"]),
                              key="held-dropped:%s" % hid)
                    del split[hid]
                    break
                rec["tries"][str(i)] = t
                jobs.append(self.held_piece(hid, rec, i, rec.get("high", True)))
            else:
                if again or len(dirs) < rec["n"] or not all(dirs.values()):
                    continue
                self.merge_pieces(hid, rec, [dirs[i] for i in sorted(dirs)])
                self.state.setdefault("held_merged", {})[hid] = rec["title"]
                del split[hid]
        return jobs

    def merge_pieces(self, hid, rec, dirs):
        """The pieces' per-seed logs in one folder under the read's id, run.env saying the whole read,
        and pool.sh's pooled.txt over all of them."""
        out = os.path.join(self.q, "results", hid, self.home, "out", hid, time.strftime("%Y%m%d-%H%M%S"))
        os.makedirs(out, exist_ok=True)
        for d in dirs:
            for f in glob.glob(os.path.join(d, "g-*.log")):
                shutil.copy2(f, out)
        first = dirs[0]
        for f in glob.glob(os.path.join(first, "*.weights")) + glob.glob(os.path.join(first, "*.env")):
            shutil.copy2(f, out)
        env = env_file(os.path.join(first, "run.env"))
        env.update({"SEEDS": str(rec["per"] * rec["n"]), "SEED0": str(rec["seed0"]), "HOST": "pieces",
                    "PIECES": ",".join(d.rstrip("/").split(os.sep)[-2] for d in dirs)})
        with open(os.path.join(out, "run.env"), "w") as f:
            f.write("".join("%s=%s\n" % (k_, shlex.quote(v)) for k_, v in env.items()))
        r = run(["bash", os.path.join(self.tc, "scripts", "pool.sh"), out])
        with open(os.path.join(out, "pooled.txt"), "w") as f:
            f.write(r.stdout)

    # THE BACKGROUND JOB (the duty-cycle report's section VII; Paul, 5 November: "then the background
    # job"). Held-out reads asked ahead of time, a piece at a time, at the lowest priority: a trial still
    # reading on, far enough and strong enough that its held-out read is likely (a trial with three
    # read-ons reaches one 28% of the time), gets the first pieces of its first held-out read before it
    # is asked for. If it is, the read is part done; if not, the pieces stay its evidence, kept for the
    # day it is asked. Each piece is stamped when it is asked (the trial, the commit, the game) and pools
    # only with its own read's pieces of the same defaults (held_merge), so a piece begun before a
    # promotion weighs nothing after it. Nothing waits on a background piece (graph_lint), and a
    # machine takes one only when nothing else is there for it (priority "low"; the keeper's low water
    # does not count them).
    AHEAD_Z = 1.5            # the trial's pooled z on its reads so far
    AHEAD_STAGE = 2          # read-ons it has had
    AHEAD_PER_DAY = 150      # pieces a day at most, about 5% of the CPU
    AHEAD_DAYS = 3           # a trial dropped or gone this long: its record goes, its pieces' results stay

    def ahead_jobs(self):
        if not self.writer or self.HELD_PIECES <= 1:
            return []
        w = self.cfg["weights"]
        now_ = time.time()
        log = [t for t in self.state.get("ahead_log", []) if t > now_ - 86400]
        queued = [j for j in self.queue_jobs() if j.get("background")]
        lanes = [h for h in self.hosts if not h.get("paused")]
        room = min(len(lanes) - len(queued), self.AHEAD_PER_DAY - len(log))
        ahead = self.state.setdefault("ahead", {})
        split = self.state.setdefault("held_split", {})
        seq = self.sequential()
        # Records of trials long dropped or gone: forgotten, their results kept.
        for jid in list(ahead):
            st_ = seq.get(jid, {}).get("status")
            if st_ in (None, "dropped") and now_ - ahead[jid]["at"] > self.AHEAD_DAYS * 86400:
                hid = ahead.pop(jid)["hid"]
                if split.get(hid, {}).get("ahead_only"):
                    del split[hid]
                self.state.get("held_ahead", {}).pop(jid, None)
        jobs = []
        if room <= 0:
            self.state["ahead_log"] = log
            return jobs
        asked = set(self.state["held_read"])
        cands = sorted(((v["z"], jid) for jid, v in seq.items()
                        if v["status"] in ("reading", "read on") and v["stage"] >= self.AHEAD_STAGE and v["z"] >= self.AHEAD_Z and jid not in asked),
                       reverse=True)
        for z, jid in cands:
            if room <= 0:
                break
            if jid not in ahead:
                hid = "h%04d" % self.state["held_n"]
                seed0 = w["held_seed0"] + 200000 * self.state["held_n"]
                self.state["held_n"] += 1
                n = self.HELD_PIECES if w["held_seeds"] % self.HELD_PIECES == 0 else 1
                if n == 1:
                    break
                ahead[jid] = {"hid": hid, "seed0": seed0, "at": now_}
                self.state.setdefault("held_ahead", {})[jid] = {"hid": hid, "seed0": seed0}
                split[hid] = {"trial": jid, "k": 1, "title": "held-out read 1 of %s (%d seeds)" % (jid, w["held_seeds"]), "seed0": seed0,
                              "per": w["held_seeds"] // n, "n": n, "text": seq[jid]["text"], "slots": {}, "tries": {}, "ahead_only": True,
                              "asked": time.strftime("%Y-%m-%dT%H:%M:%S"),
                              # The stamp: what this read is of, and on what, when it was asked.
                              "stamp": {"trial": self.trial_key(seq[jid]["text"]), "commit": self.sha()[:12], "game": self.game_at(self.sha()), "z": round(z, 2)}}
            rec = split.get(ahead[jid]["hid"])
            if not rec or not rec.get("ahead_only"):
                continue
            free = [i for i in range(1, rec["n"] + 1) if str(i) not in rec["slots"]]
            if not free:
                continue
            jobs.append(self.held_piece(ahead[jid]["hid"], rec, free[0], high=False, background=True))
            log.append(now_)
            room -= 1
        self.state["ahead_log"] = log
        return jobs

    def graph_lint(self, jobs):
        """NO CIRCULAR DEPENDENCIES (Paul, 5 November: "We want to prevent creating circular
        depdencies"). The queue's `after` edges with the new jobs' sort topologically, and no edge
        enters a background job: nothing may wait on work that may never be read. A new job that
        breaks either is not asked, and a flag says which."""
        known = {j.get("id"): j for j in self.queue_jobs()}
        for j in jobs:
            known[j.get("id")] = j
        background = {i for i, j in known.items() if j.get("background")}
        bad = set()
        for j in jobs:
            if any(a in background for a in j.get("after", [])):
                bad.add(j["id"])
        # A cycle: a walk that comes back to a job still on its own path.
        state = {}

        def walk(i, path):
            state[i] = 1
            for a in known.get(i, {}).get("after", []):
                if a not in known:
                    continue
                if state.get(a) == 1:
                    bad.update(path[path.index(a):] if a in path else [i])
                elif not state.get(a):
                    walk(a, path + [a])
            state[i] = 2
        for i in list(known):
            if not state.get(i):
                walk(i, [i])
        new = {j["id"] for j in jobs}
        if bad & new:
            self.flag("graph", "not asked, for they would wait on a background job or in a circle: %s" % ", ".join(sorted(bad & new)),
                      key="graph:%s" % ",".join(sorted(bad & new)))
        return [j for j in jobs if j["id"] not in bad]

    def held_pairs(self):
        """Each trial's held-out reads: {trial: [census dir, ...]}, from the jobs' titles."""
        title = {}
        for i, t in list(self.done_titles().items()) + list(self.state.get("held_merged", {}).items()):
            m = re.match(r"held-out read \d of (w\d+)", t)
            if m:
                title[i] = m.group(1)
        out = {}
        for d in self.census_dirs():
            hid = d.rstrip("/").split(os.sep)[-2]
            if hid in title:
                out.setdefault(title[hid], []).append(d)
        return out

    def family_candidates(self):
        """[(name, SCENARIO_SET)]: the defaults, this queue's candidates, then
        each converge run's CANDIDATE lines, newest generation first."""
        f = self.cfg.get("families") or {}
        out = [("defaults@%s" % self.short(), "")]
        if f.get("queue", True):
            # Today's candidates only: each generation asked every old one again.
            for jid, ds in sorted(self.held_pairs().items()):
                if self.held_pass(ds) and self.same_defaults(self.census_commit(ds[0])):
                    trial = glob.glob(os.path.join(self.q, "results", jid, self.home, "out", jid, "*", "trial.weights"))
                    if trial:
                        out.append(("%s/%s" % (self.name, jid), self.weights_set(open(trial[0]).read())))
        for run_dir in f.get("converge", []) if f.get("converge_each") else []:
            run_dir = os.path.join(self.tc, run_dir) if not os.path.isabs(run_dir) else run_dir
            rows = []
            try:
                lines = open(os.path.join(run_dir, "candidates.txt")).readlines()
            except OSError:
                lines = []
            for l in lines:
                m = re.match(r"^(gen(\d+)/\S+) .*CANDIDATE", l)
                if m and os.path.exists(os.path.join(run_dir, m.group(1) + ".weights")):
                    rows.append((int(m.group(2)), m.group(1)))
            for g, name in sorted(rows, key=lambda r: (-r[0], r[1])):
                text = open(os.path.join(run_dir, name + ".weights")).read()
                out.append(("%s/%s" % (os.path.basename(run_dir.rstrip("/")), name), self.weights_set(text)))
        return out

    def family_jobs(self, n):
        f = self.cfg.get("families")
        if not f or not self.cpu_ready() or n <= 0:
            return []
        # A read that crashed said nothing about the candidate: once more on each
        # new commit, which is the only thing that could have mended it.
        done = load(os.path.join(self.pd, "families.json"), {}) or {}
        retried = self.state.setdefault("families_retried", {})
        for name, v in done.items():
            if v.get("verdict") == "ERROR" and retried.get(name) != self.short() and name in self.state["families_queued"]:
                self.state["families_queued"].remove(name)
                retried[name] = self.short()
        todo = [c for c in self.family_candidates() if c[0] not in self.state["families_queued"]]
        batch = int(f.get("batch", 8))
        jobs = []
        while todo and len(jobs) < n:
            part, todo = todo[:batch], todo[batch:]
            fid = "f%04d" % self.state["families_n"]
            self.state["families_n"] += 1
            b = base64.b64encode(("\n".join("%s\t%s" % c for c in part) + "\n").encode()).decode()
            # The test fails when a family is under its floor: that is a
            # verdict, kept in the output, not a failed job (the breaker).
            cmd = (
                "set -e; Q=~/%s; C=%s; O=$Q/out/%s; rm -rf $O; mkdir -p $O; echo %s | base64 -d > $O/candidates.tsv\n"
                "N=$(nproc 2>/dev/null || sysctl -n hw.ncpu)\n"
                "i=0; while IFS=$'\\t' read -r name set; do\n"
                "  i=$((i+1)); ( printf '%%s\\n%%s\\n' \"$name\" \"$set\" > $O/$i.set\n"
                "    t0=$(date +%%s); FLOOR_GIVE=GIVE_NOW SCENARIO_SET=\"$set\" $C/census-bin --ignored every_family_holds_its_floor --nocapture > $O/$i.log 2>&1 && r=holds || r=UNDER\n"
                "    echo \"$r $(( $(date +%%s) - t0 ))\" > $O/$i.verdict ) &\n"
                "  while [ $(jobs -rp | wc -l) -ge $N ]; do sleep 2; done\n"
                "done < $O/candidates.tsv; wait\n"
                "for v in $O/*.verdict; do k=$(basename $v .verdict); echo \"$(cat $v) $(head -1 $O/$k.set)\"; done\n"
            ) % (self.home, self.cdir(), fid, b)
            cmd = cmd.replace("GIVE_NOW", "%g" % self.FLOOR_GIVE)
            jobs.append({"id": fid, "kind": "families", "title": "families: %s" % ", ".join(c[0] for c in part)[:110],
                         "needs": "cpu", "after_host": self.after_host(), "cmd": cmd,
                         "fetch": "%s/out/%s" % (self.home, fid), "timeout_s": 12 * 3600, "priority": "high",
                         "on_done": "python3 -I %s %s families" % (os.path.abspath(__file__), self.q)})
            self.state["families_queued"] += [c[0] for c in part]
        return jobs

    def families(self):
        """Every families verdict fetched so far, into plan/families.json."""
        out = {}
        for d in sorted(glob.glob(os.path.join(self.q, "results", "f*", self.home, "out", "f*", ""))):
            for sf in glob.glob(os.path.join(d, "*.set")):
                k = sf[:-4]
                name, _, sset = open(sf).read().partition("\n")
                try:
                    verdict, secs = open(k + ".verdict").read().split()
                except (OSError, ValueError):
                    continue
                fams = []
                for l in open(k + ".log", errors="replace"):
                    m = re.match(r"^family (\S+) \[.*\]: held (\d+) of (\d+), ([\d.]+)% \+/- ([\d.]+)%, floor (\S+), (.+) \(([\d.]+) s\)", l)
                    if m:
                        fams.append({"family": m.group(1)[:-5], "held": int(m.group(2)), "runs": int(m.group(3)),
                                     "pct": float(m.group(4)), "se": float(m.group(5)), "floor": m.group(6), "verdict": m.group(7)})
                # NO FAMILY READ IS NOT A FLOOR BROKEN. The test exits non-zero for
                # both, and a panic before the first family (w1442, w1592, w1656, a
                # switch's A/B each) was read as UNDER and could never be promoted.
                if verdict == "UNDER" and not fams:
                    verdict = "ERROR"
                out[name] = {"set": sset.strip(), "verdict": verdict, "seconds": int(secs), "families": fams,
                             "job": d.rstrip("/").split(os.sep)[-1]}
        save(os.path.join(self.pd, "families.json"), out)
        held = [k for k, v in out.items() if v["verdict"] == "holds"]
        print("families: %d candidates read, %d hold every floor" % (len(out), len(held)))
        return out

    # ---- the net ------------------------------------------------------------------------
    def best_net(self):
        start = (self.cfg.get("net") or {}).get("start", "bc2.bin")
        p = os.path.join(self.pd, "best.bin")
        if not os.path.exists(p):
            shutil.copy(os.path.join(self.tc, "nets", start), p)
            save(os.path.join(self.pd, "best.json"), {"name": start, "round": 0})
        return p

    def net_jobs(self):
        n = self.cfg.get("net")
        if not n or not n.get("rounds"):
            return []
        gpu = [h for h in self.hosts if "gpu" in h.get("caps", [])]
        if not gpu or not self.prepared(gpu[0]["name"]) or not self.prepared(self.cfg["census_host"]):
            return []
        r = self.state["round"]
        # One round at a time: the next only when this one is judged (or failed).
        if r > 0 and "judge-%03d" % r not in self.ids("done", "failed", "stopped"):
            return []
        rounds = n["rounds"]
        if r >= len(rounds):
            return []
        spec = rounds[r]
        r += 1
        self.state["round"] = r
        store_q = "~/" + self.home
        tid, jid = "train-%03d" % r, "judge-%03d" % r
        best = self.best_net()
        data = (
            "D=%s/rounds/%03d; rm -rf $D; mkdir -p $D/data\n"
            "for f in ~/fleet/%s/shards/*.bin; do s=$(basename $f .bin); [ $s -ge %d ] && [ $s -lt %d ] && ln -s $f $D/data/; done; true\n"
            "ln -s ~/bc/rec60.bin $D/data/9000000.bin\n"
            "for s in 9001140 9001164 9001188 9001212 9001236; do ln -s ~/fleet/rec1200/shards/$s.bin $D/data/; done\n"
        ) % (store_q, r, spec["run"], spec["lo"], spec["lo"] + spec["n"])
        train = {
            "id": tid, "kind": "net", "title": "round %d: train the best on %s seeds %d to %d" % (r, spec["run"], spec["lo"], spec["lo"] + spec["n"] - 1),
            "needs": "gpu", "after": [self.prep_id(gpu[0]["name"])],
            "send": [{"src": best, "dst": "%s/rounds/%03d.start.bin" % (store_q, r)}],
            "cmd": data + self.trainer() + "cd $D && HELD=9000054-9000059,9001140-9001259 START=%s/rounds/%03d.start.bin BC_DEVICE=cuda %s/treadcore-bc $D/data $D/cand.bin %s > $D/train.log 2>&1\n"
                   "grep -v 'DEINIT\\|^thread\\|^note\\|^$' $D/train.log | tail -14\n" % (store_q, r, self.cdir(), n["train_args"]),
            "fetch": "%s/rounds/%03d" % (self.home, r), "timeout_s": 4 * 3600,
        }
        c = n["census"]
        census_one = (
            "cd $C/wt && export CARGO_TARGET_DIR=$HOME/fleet/target\n"
            "SEEDS=%d SEED0=%d SECS=%d MAP=%s RESPAWNS=3 JOBS=$(nproc 2>/dev/null || sysctl -n hw.ncpu) CENSUS_NET=$Q/judge/%03d/%%s.bin CENSUS_BIN=$C/census-bin scripts/census.sh 2>&1 | tail -2\n"
            "d=$(ls -td build/census/*/ | head -1); mkdir -p $Q/judge/%03d/%%s; cp $d/*.txt $d/*.env $d/g-*.log $Q/judge/%03d/%%s/; rm -rf $d\n"
        ) % (c["seeds"], c["seed0"], c["secs"], c["map"], r, r, r)
        judge = {
            "id": jid, "kind": "net", "title": "round %d: judge the candidate against the best, a census each" % r,
            "needs": "host:" + self.cfg["census_host"], "after": [tid, self.prep_id(self.cfg["census_host"])],
            "send": [{"src": os.path.join(self.q, "results", tid, self.home, "rounds", "%03d" % r, "cand.bin"), "dst": "~/%s/judge/%03d/cand.bin" % (self.home, r)},
                     {"src": best, "dst": "~/%s/judge/%03d/best.bin" % (self.home, r)}],
            "cmd": "set -e; [ -f ~/.cargo/env ] && . ~/.cargo/env; export PATH=$HOME/.cargo/bin:$PATH; Q=~/%s; C=%s\n" % (self.home, self.cdir())
                   + (census_one % ("cand", "cand", "cand")) + (census_one % ("best", "best", "best")),
            "fetch": "%s/judge/%03d" % (self.home, r),
            "on_done": "python3 -I %s %s judged %s" % (os.path.abspath(__file__), self.q, jid),
            "timeout_s": 6 * 3600,
        }
        return [train, judge]

    def judged(self, jid):
        r = int(jid.split("-")[1])
        base = os.path.join(self.q, "results", jid, self.home, "judge", "%03d" % r)

        def seeds(who):
            out = {}
            for f in glob.glob(os.path.join(base, who, "g-*.log")):
                s0 = int(re.search(r"g-(\d+)", f).group(1))
                for l in open(f):
                    l = re.sub(r"\x1b\[[0-9;]*m", "", l)
                    if l.startswith("brain_census: difference"):
                        for i, v in enumerate(l.split("a seed:")[1].split()):
                            out[s0 + i] = float(v)
            return out

        a, b = seeds("cand"), seeds("best")
        k = sorted(set(a) & set(b))
        if len(k) < 2:
            print("judge %s: too few paired seeds (%d)" % (jid, len(k)))
            return
        d = [a[s] - b[s] for s in k]
        m, se = st.mean(d), st.stdev(d) / len(d) ** 0.5
        verdict = {"round": r, "seeds": len(k), "cand": st.mean(a[s] for s in k), "best": st.mean(b[s] for s in k),
                   "diff": m, "se": se, "better": m > 2 * se}
        tlog = os.path.join(self.q, "results", "train-%03d" % r, self.home, "rounds", "%03d" % r, "train.log")
        agree = {}
        try:
            text = open(tlog).read()
            part = text.split("seeds 9000054-9000059")[1] if "seeds 9000054-9000059" in text else ""
            for h in ("drive", "gun", "mortar", "drone", "lead"):
                mm = re.search(r"^\s+%s\s+([\d.]+)%%" % h, part, re.M)
                if mm:
                    agree[h] = float(mm.group(1))
        except OSError:
            pass
        verdict["held_out"] = agree
        save(os.path.join(self.pd, "round-%03d.json" % r), verdict)
        if verdict["better"]:
            cand = os.path.join(self.q, "results", "train-%03d" % r, self.home, "rounds", "%03d" % r, "cand.bin")
            shutil.copy(cand, os.path.join(self.pd, "best.bin"))
            save(os.path.join(self.pd, "best.json"), {"name": "round %d" % r, "round": r, "census_vs_previous": [m, se], "held_out": agree})
        print("judge %s: candidate less best %+.2f +/- %.2f over %d seeds: %s" % (jid, m, se, len(k), "the new best" if verdict["better"] else "the best stays"))

    # ---- sync: every machine's record, gathered ------------------------------------------
    def sync(self, only=None):
        """Each machine's ledger, read on it; each machine's converge records
        (no binaries); every table joined into build/ledger/fleet.tsv.
        ONLY: that machine alone (before it powers off), then the join."""
        out = os.path.join(self.tc, "build", "ledger")
        os.makedirs(out, exist_ok=True)
        aliases = self.qcfg.get("aliases", {})
        tables, lines = [], []
        active = {h["name"] for h in self.hosts}
        for h in self.ledgers:
            name, target = h["name"], h["target"]
            p = os.path.join(out, "%s.tsv" % name)
            if (only and name != only) or (not only and name not in active):
                if os.path.exists(p):
                    tables.append(p)
                continue
            cmd = "cd ~/code/treadcore 2>/dev/null && [ -d build/census ] && python3 -I scripts/ledger.py build/census || true"
            try:
                r = run(["bash", "-c", cmd] if target == "-" else SSH + [target, "bash -c %s" % json.dumps(cmd)], timeout=900)
                ok = r.returncode == 0
            except subprocess.TimeoutExpired:
                ok = False
            if ok:
                rows = list(csv.DictReader(r.stdout.splitlines(), delimiter="\t"))
                # One name a machine: run.env says what hostname(1) said,
                # which on a Mac changes with the network.
                for row in rows:
                    row["host"] = aliases.get(row["host"], row["host"])
                write_tsv(p, rows)
                lines.append("%s %d" % (name, len(rows)))
                # Its converge runs: the records the families and a person read.
                dst = os.path.join(self.tc, "build", "fleet-sync", name)
                if target == "-":
                    src = os.path.join(self.tc, "build", "converge")
                    if os.path.isdir(src):
                        os.makedirs(dst, exist_ok=True)
                        run(["rsync", "-a", "--exclude", "census-bin", src, dst + "/"], timeout=1800)
                elif run(SSH + [target, "test -d ~/code/treadcore/build/converge"], timeout=60).returncode == 0:
                    os.makedirs(dst, exist_ok=True)
                    run(["rsync", "-a", "--exclude", "census-bin", "-e", " ".join(SSH),
                         "%s:code/treadcore/build/converge" % target, dst + "/"], timeout=1800)
            else:
                lines.append("%s unreachable (its last table %s)" % (name, "kept" if os.path.exists(p) else "none"))
            if os.path.exists(p):
                tables.append(p)
        for q in sorted(glob.glob(os.path.join(self.tc, "build", "queue", "*", "plan", "ledger.tsv"))):
            name = q.split(os.sep)[-3]
            rows = list(csv.DictReader(open(q), delimiter="\t"))
            for row in rows:
                row["host"] = aliases.get(row["host"], row["host"])
            p = os.path.join(out, "queue-%s.tsv" % name)
            if write_tsv(p, rows):
                tables.append(p)
        fleet = os.path.join(out, "fleet.tsv")
        with open(fleet + ".tmp", "w") as f:
            subprocess.run([sys.executable, "-I", os.path.join(self.tc, "scripts", "ledger.py"), "--merge"] + tables, stdout=f, check=True)
        os.replace(fleet + ".tmp", fleet)
        by = {}
        for r in csv.DictReader(open(fleet), delimiter="\t"):
            by[r["host"]] = by.get(r["host"], 0) + 1
        ps = self.push_check() if not only else load(os.path.join(self.pd, "push.json"), {})
        summary = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "rows": sum(by.values()), "by_host": by, "hosts": lines, "push": ps}
        save(os.path.join(out, "sync.json"), summary)
        print("sync: fleet.tsv %d rows (%s); read: %s" % (summary["rows"], ", ".join("%s %d" % kv for kv in sorted(by.items())), "; ".join(lines)))


    # ---- runs: what a person asks for (fleet-queue.py Q new KIND k=v ...) -------------
    # A run is a request in Q/runs/RID.json ({"kind", "params"}); its state and
    # results are in plan/runs/RID/. The kinds are what treadcore's make
    # targets were (LR 114):
    #   census       one census: trial against base (TRIAL=, BASE= files or text)
    #   parts        each part off (scripts/parts.sh LIST=1), a census each
    #   switches     each switch alone (scripts/switches.sh LIST=1), a census each
    #   roundrobin   every ordered pair of profiles (scripts/roundrobin.sh LIST=1)
    #   spsa         SPSA over named weights, a step a census (scripts/spsa.sh's rule)
    #   tune         a (1 + lambda) evolution strategy, a child a census (tune.sh's rule)
    #   train, gauntlet, clips, school   the learning harness, one job on one host
    #   record       recordings for behaviour cloning, a shard a job, to the store
    #   families     every candidate's families read again
    #   promote      a candidate written into weights.rs on a branch, tested,
    #                its families read, committed and pushed as the branch;
    #                main moves only when Paul approves (approve RID)
    # Every census is one machine's; a run's censuses go to whichever is free.
    CENSUS_KINDS = ("census", "parts", "switches", "roundrobin")
    HARNESS_KINDS = ("train", "gauntlet", "clips", "school")

    def runs(self):
        out = []
        for f in sorted(glob.glob(os.path.join(self.q, "runs", "*.json"))):
            r = load(f)
            if r and r.get("kind"):
                r["id"] = os.path.basename(f)[:-5]
                out.append(r)
        return out

    def rdir(self, rid):
        d = os.path.join(self.pd, "runs", rid)
        os.makedirs(d, exist_ok=True)
        return d

    def rstate(self, rid):
        if rid in self._rsaves:
            return self._rsaves[rid]
        return load(os.path.join(self.rdir(rid), "state.json"), {"status": "new"})

    def rsave(self, rid, st):
        # Kept until the top-up succeeds (keep()): a run is never marked as
        # having jobs the keeper did not receive.
        self._rsaves[rid] = st
        # A run that ends, or waits for a person, is a flag.
        status = st.get("status")
        if status in ("done", "failed", "prepared"):
            text = {"done": "run %s finished" % rid, "failed": "run %s failed: %s" % (rid, st.get("why", "")),
                    "prepared": "promotion %s is prepared on %s: Paul Accepts it when auto mode is on and this machine can push; "
                                "otherwise it self-modifies (the local line)" % (rid, st.get("branch"))}[status]
            # News is progress (Paul, 28 October: "I'm going to always accept
            # them"); only a failure asks for a person. A prepared promotion
            # never waits: it is accepted or it self-modifies.
            asks = status == "failed"
            self.flag("run" if status != "prepared" else "approve", text, key="run:%s:%s" % (rid, status), progress=not asks)

    # ---- auto mode: the cycle closes itself ---------------------------------------------
    def auto(self):
        """Auto mode (config "auto", on unless false): a run's result gets its
        held-out reads, the strongest current candidate promotes itself, and a
        prepared promotion approves itself (Paul, 28 October: "Should self
        promote, unless we are not in AUTO mode. We should be in auto mode")."""
        return self.cfg.get("auto", True) is not False

    def new_run(self, kind, params, by, **extra):
        """A run file, as fleet-queue.py new writes one."""
        d = os.path.join(self.q, "runs")
        os.makedirs(d, exist_ok=True)
        n = 1 + max([int(f[1:5]) for f in os.listdir(d) if f[:1] == "r" and f[1:5].isdigit()] +
                    [int(r[1:]) for r, _ in self._newruns] or [0])
        rid = "r%04d" % n
        # Written by keep(), with the state: a pass that fails leaves no run
        # behind it (28 October: one did, and its state was not saved).
        self._newruns.append((rid, dict({"kind": kind, "params": params, "asked": time.strftime("%Y-%m-%dT%H:%M:%S"), "by": by}, **extra)))
        return rid

    def adopt(self, text, what):
        """A result (a run's weights) as a trial of the queue: its census and
        its two held-out reads, queued together. Passing both, it is a
        candidate like any other. Returns the trial's id."""
        self.state.setdefault("adopt", []).append({"text": text, "what": what})
        return "w%04d" % (self.state["weights_n"] + len(self.state["adopt"]) - 1)

    def adopt_runs(self):
        """Each finished spsa or tune run's result, adopted once (auto mode)."""
        if not self.auto() or not self.defaults():
            return
        done = self.state.setdefault("adopted", {})
        for r in self.runs():
            rid, kind = r["id"], r["kind"]
            st = self.rstate(rid)
            if kind not in ("spsa", "tune", "census") or rid in done or st.get("status") != "done":
                continue
            # A read to know, not to promote: `adopt=no`.
            if (r.get("params") or {}).get("adopt") == "no":
                done[rid] = None
                continue
            if kind == "census":
                # A census of a trial (the rotation's @best): adopted when it
                # passed, so its held-out reads follow.
                items = st.get("items", [])
                ds = glob.glob(os.path.join(self.q, "results", items[0]["job"], self.home, "out", items[0]["job"], "*", "")) if len(items) == 1 else []
                if not ds or not self.passes(ds[0]) or not os.path.exists(os.path.join(ds[0], "trial.weights")):
                    done[rid] = None
                    continue
                text = open(os.path.join(ds[0], "trial.weights")).read()
                # A NAMED STYLE IS A PERSON'S CHOICE, whatever it reads: adopted, it would replace
                # every bot's whole brain at a generation's bar (styles.rs).
                if "bot_style" in parse_weights(text):
                    done[rid] = None
                    continue
            else:
                f = os.path.join(self.rdir(rid), "theta.weights" if kind == "spsa" else "best.weights")
                text = open(f).read() if os.path.exists(f) else ""
            dflt = parse_weights(open(self.defaults()).read()) if self.defaults() else {}
            moved = {k: v for k, v in parse_weights(text).items() if k in dflt and abs(v - dflt[k]) > 1e-9}
            if not moved:
                done[rid] = None
                continue
            done[rid] = self.adopt(text, "%s %s" % (kind, rid))

    # One of each, in turn: the default work of auto mode beside the standing
    # search (Paul, 28 October: "Is there a do one of each on rotation method
    # that is the default choice? Can we have that."). Two lanes, a run
    # active in each: the brain's searches and measurements, and the
    # learned tank's (train and school can take days).
    ROTATION = {
        "brain": [["spsa", {}], ["tune", {}], ["census", {"trial": "@best", "name": "best"}],
                  ["parts", {}], ["switches", {}], ["roundrobin", {}], ["record", {}]],
        "net": [["gauntlet", {}], ["train", {}], ["school", {}]],
    }
    # Measurements that say nothing new on the same defaults: once each.
    ONCE_PER_DEFAULTS = ("parts", "switches", "roundrobin", "gauntlet")

    def rotate(self):
        if not self.auto() or self.cfg.get("rotation") is False:
            return
        rot = self.state.setdefault("rotation", {})
        runs = self.runs()
        lanes = self.cfg.get("rotation") if isinstance(self.cfg.get("rotation"), dict) else self.ROTATION
        for lane, kinds in lanes.items():
            if any(r.get("lane") == lane and self.rstate(r["id"]).get("status") in ("new", "running") for r in runs):
                continue
            i = rot.get(lane, 0)
            for step in range(len(kinds)):
                kind, params = kinds[(i + step) % len(kinds)]
                if kind in self.ONCE_PER_DEFAULTS and any(
                        r["kind"] == kind and self.rstate(r["id"]).get("status") in ("done", "running")
                        and self.same_defaults(self.rstate(r["id"]).get("commit")) for r in runs):
                    continue
                params = dict(params)
                cycle = rot.get("cycle", 0)
                rot["cycle"] = cycle + 1
                # Fresh seeds every time, clear of the trials' (20M), the
                # held-out reads' (60M up) and the recordings' (9.9M).
                if kind in ("spsa", "tune", "census", "patch"):
                    params["seed0"] = 500000000 + 1000000 * cycle
                if kind == "record":
                    nxt = rot.get("record_next", 9920000)
                    params.update({"seed0": nxt, "count": 48, "per": 12, "run": "rot%d" % cycle})
                    rot["record_next"] = nxt + 48
                rid = self.new_run(kind, params, "rotation", lane=lane)
                rot[lane] = (i + step + 1) % len(kinds)
                self.flag("rotation", "rotation (%s): %s asked a %s" % (lane, rid, kind), key="rotation:%s" % rid, progress=True)
                break

    def adopt_jobs(self):
        w = self.cfg.get("weights")
        if not w or not self.state.get("adopt") or not self.cpu_ready():
            return []
        jobs = []
        for a in self.state["adopt"]:
            jid = "w%04d" % self.state["weights_n"]
            self.state["weights_n"] += 1
            seed0 = w["seed0"] + 10000 * int(jid[1:])
            jobs.append({"id": jid, "kind": "weights", "title": "%s: %s" % (a["what"], short_moved(a["text"])),
                         "needs": "cpu", "after_host": self.after_host(), "cmd": self.census_cmd(a["text"], w["seeds"], seed0, jid),
                         "fetch": "%s/out/%s" % (self.home, jid), "timeout_s": 6 * 3600})
            # Its held-out reads at once, not after its own census passes:
            # a run's result was already chosen by a search.
            # A carried pass goes first, and takes the one read a generation takes.
            for k in range(a.get("reads", 2)):
                jobs += self.held_read(jid, k + 1, a["text"], high=bool(a.get("reads")))
            self.state["held_read"].append(jid)
        self.state["adopt"] = []
        return jobs

    @staticmethod
    def census_commit(d):
        if d in _COMMITS:
            return _COMMITS[d]
        c = None
        try:
            for l in open(os.path.join(d, "run.env")):
                if l.startswith("COMMIT="):
                    c = l.split("=", 1)[1].strip().strip("'")
                    break
        except OSError:
            return None
        _COMMITS[d] = c
        return c

    GENERATION_EVERY_MIN = 0   # since 13 November the line settling holds a generation; half an hour before

    # THE LINE SETTLES BEFORE IT GROWS (Paul, 13 November, on Always Forward: "it seems that we abandon a
    # block too frequently"). A generation on the line moved its head, and the proof's pool began again:
    # of 37 heads the proof read, 28 were left unproved, after a median 1.2 hours and 1,600 seeds, where
    # a true +0.25 against a seed's swing of 8.1 takes 9,400 to show at z 3. Four were left past z 2,
    # one (8017a71) at 2.92 over 13,600 seeds. So while the line's head has not been read SETTLE_SEEDS
    # seeds by its proof, no generation joins it: the proof goes first, SETTLE_JOBS reads at a time and
    # no hour between, and the head either goes to main or has been read enough to say it does not.
    # What passes meanwhile stays a candidate on the same defaults, and the strongest goes next. A
    # head whose proof cannot be asked (the line's values are main's) holds nothing past SETTLE_MAX_H.
    # 0 seeds: off, as it was.
    SETTLE_SEEDS = 9600
    SETTLE_JOBS = 6
    SETTLE_MAX_H = 8

    def settling(self):
        """What the line waits for before another generation, in words; None when nothing."""
        line = self.state.get("local_line")
        if not line or not self.SETTLE_SEEDS or not line.get("commit"):
            return None
        p = self.promotions()
        if p and time.time() - p[-1][0] > self.SETTLE_MAX_H * 3600:
            return None
        pf = self.state.get("proof") or {}
        last, head = pf.get("last") or {}, line["commit"]
        seeds = last.get("seeds", 0) if last.get("head") == head[:7] else 0
        # Read its seeds and neither proved nor refused (orphan): it is read on, to twice as many, then let go.
        undecided = seeds < 2 * self.SETTLE_SEEDS and last.get("se") and last["d"] + 2 * last["se"] >= self.MIN_GAIN
        if seeds >= self.SETTLE_SEEDS and not undecided:
            return None
        return "the line %s settles first: its proof has read %d of %d seeds%s" % (
            head[:7], seeds, self.SETTLE_SEEDS, ", %+.2f +/- %.2f so far" % (last["d"], last["se"]) if seeds else "")

    # A BLOCK THAT FAILS ITS CHECK COMES OFF (Paul, 13 November: "Remove a block that fails"). The proof and
    # the anchors read ten generations as worth nothing for a week and nothing acted on it: the line kept
    # them, the fleet built on them, and the search measured every trial against them. A line read its
    # SETTLE_SEEDS whose lead, with two errors added, is still under MIN_GAIN is not worth a generation
    # by its own proof: its promotions are marked orphaned, the branch goes back to main, and the fleet
    # builds main again. Nothing on main is touched and nothing is pushed. The trials are not forgotten:
    # each stays a candidate of its day, to be read again on main's defaults like any older one.
    def orphan(self, head, lead, se, seeds):
        line = self.state.get("local_line")
        if not line or line.get("commit") != head:
            return False
        remote, branch = self.push_target()
        main = run(["git", "-C", self.tc, "rev-parse", "%s/%s" % (remote, branch)]).stdout.strip()
        if not main:
            return False
        off = []
        for rid in line.get("promotions", []):
            st = self.rstate(rid)
            if st.get("status") == "self-modified":
                st.update({"status": "orphaned", "orphaned": time.strftime("%Y-%m-%dT%H:%M:%S"),
                           "detail": "orphaned: the line %s read %+.2f +/- %.2f over main in %d seeds, under the %.2f a generation is worth; it was at %s" % (
                               head[:7], lead, se, seeds, self.MIN_GAIN, st.get("commit", "")[:7])})
                self.rsave(rid, st)
                off.append(rid)
        run(["git", "-C", self.tc, "branch", "-f", self.LINE, main])
        self.state.pop("local_line", None)
        self.state["proof"] = {"last_at": time.time(), "orphaned": {"head": head, "lead": round(lead, 2), "se": round(se, 2), "seeds": seeds, "promotions": off}}
        self.state.setdefault("orphans", []).append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "head": head, "lead": round(lead, 2), "se": round(se, 2), "seeds": seeds, "promotions": off})
        self.state["families_queued"] = []
        self._sha = None
        # MAIN IS BUILT AGAIN, WHATEVER WAS BUILT BEFORE. Each time main moves the old builds are pruned, so
        # a build of main made before the line began may be gone from a machine while its job still reads
        # as done, and then nothing would ask for it and every job there would wait on nothing. The done
        # builds of the commit the fleet now builds are set aside and asked again: minutes, where a build stands.
        if getattr(self, "q", None):
            aside = os.path.join(self.q, "orphan-rebuilt")
            for f in glob.glob(os.path.join(self.q, "done", "*-prep-*-%s.json" % self.short())):
                os.makedirs(aside, exist_ok=True)
                os.rename(f, os.path.join(aside, os.path.basename(f)))
        self.flag("line", "the line %s came off: its proof read %+.2f +/- %.2f over main in %d seeds, and with two errors added that is under the %.2f a generation is worth; "
                  "%s orphaned, and the fleet builds main again" % (head[:7], lead, se, seeds, self.MIN_GAIN, ", ".join(off) or "nothing"), key="orphan:%s" % head[:12], progress=True)
        return True

    # Minutes a pause of auto promotion lasts before it goes on by itself (or less, if main moves).
    PAUSE_RESUME_MIN = 60

    def main_now(self):
        """main's commit as the remote has it, or "" when it cannot be read (no checkout, no config)."""
        try:
            remote, branch = self.push_target()
            return run(["git", "-C", self.tc, "rev-parse", "%s/%s" % (remote, branch)]).stdout.strip()
        except (AttributeError, OSError, subprocess.SubprocessError):
            return ""

    # LESS NOISE (Paul, 1 November: "can we get a little less noise promotions"). Of the day's thirteen
    # generations, nine were noise by any reading: a switch off at +0.10 and back on at +0.08, base_r 16 to
    # 32 to 8 to 6.15 in four steps, `bio` on at z 1.0. Two kinds of pass get through a bar in errors alone.
    # A CHANGE THAT BARELY PLAYS DIFFERENTLY HAS A TINY ERROR, so +0.08 +/- 0.04 clears any z and is worth
    # nothing: a gain must be MIN_GAIN points a seat. And A DIAL STILL MOVING IS NOT SETTLED: one moved in
    # the last SETTLE_GENS generations moves again only at full z 3, so no dial wanders on luck.
    MIN_GAIN = 0.25
    SETTLE_GENS = 0   # off since 13 November (2 before): the bar at z 2.5 and the line settling do its work

    def changed_from_line(self, text):
        """A trial's weights as "name old -> new" lines, against what the fleet builds now."""
        today, out = self.defaults_at(self.sha()), []
        for k, v in sorted(parse_weights(text).items()):
            if k in today and abs(today[k] - v) > 1e-9:
                out.append("%s %g -> %g" % (k, today[k], v))
        for l in text.splitlines():
            m = re.match(r"^\s*caps\s*=\s*(.*)$", l.split("#")[0])
            for c in (m.group(1).split(",") if m else []):
                c = c.strip()
                name = c.lstrip("+-")
                key = "caps:" + name
                if c and name != "baseline" and key in today and bool(today[key]) == c.startswith("-"):
                    out.append("caps %s %s -> %s" % (name, "on" if today[key] else "off", "off" if c.startswith("-") else "on"))
        return out

    def recently_moved(self):
        """The dials and switches the last SETTLE_GENS generations moved, by comparing each with its parent."""
        moved = set()
        if not self.SETTLE_GENS:
            return moved
        for _, _, st_ in self.promotions()[-self.SETTLE_GENS:]:
            c = st_.get("commit")
            parent = self.parent_of(c) if c else ""
            if parent:
                a, b = self.defaults_at(parent), self.defaults_at(c)
                moved |= {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
        return moved

    @staticmethod
    def trial_moves(text):
        """What a trial's weights set: its numbers, and the switches on its caps line."""
        out = set(parse_weights(text))
        for l in text.splitlines():
            m = re.match(r"^\s*caps\s*=\s*(.*)$", l.split("#")[0])
            if m:
                out |= {"caps:" + c.strip().lstrip("+-") for c in m.group(1).split(",") if c.strip() and c.strip() != "baseline"}
        return out

    def noise(self, name, v):
        """Why this candidate should not land, in words, or "". It stays a candidate, and a stronger read lifts it."""
        held = [h for h in (v.get("held") or []) if h and h[1] > 0]
        if not held:
            return ""
        iw = sum(1 / h[1] ** 2 for h in held)
        mean = sum(h[0] / h[1] ** 2 for h in held) / iw
        why = ""
        if mean < self.MIN_GAIN:
            why = "gains %+.2f, under the %.2f a seat that is worth a generation" % (mean, self.MIN_GAIN)
        else:
            again = self.trial_moves(v.get("weights", "")) & self.recently_moved()
            if again and mean * math.sqrt(iw) < self.HELD_Z:
                why = "moves %s again within %d generations, at z %.1f and not %.1f" % (", ".join(sorted(again)), self.SETTLE_GENS, mean * math.sqrt(iw), self.HELD_Z)
        if why:
            self.flag("noise", "%s waits: it %s" % (name, why), key="noise:%s" % name, progress=True)
        return why

    # WHAT THE SCORE DOES NOT WEIGH (Paul, 2 November). The night's search turned `cycle` off, and with it the
    # building fix, at +0.83 on the score: a generation had built 4 less a team and lost 0.38 a seat in fights, and
    # nothing read either. Against main the line had gained 1.46 and lost 0.41 of it all but the reward for going
    # forward. So a read that gives up building or fights past noise and past a floor waits for a person.
    # Past noise: two errors, seed by seed. The floors are values, so raising one lets a generation through.
    GIVE_BUILT = 0.10
    GIVE_ROAD = 0.10
    GIVE_KD = 0.10
    # THE TRADE RULE (Paul, 4 November: "what holds wait for a person. what step of a human is required.
    # automate this please"). A trade past its floor waited for a person: 51 candidates in three days, and
    # a line held half an hour that evening until Paul approved it. Since SCORE_VERSION 1 the score counts
    # building, so a read that gives up building and still clears the bar has already paid for it. A trade
    # up to TRADE_TIMES its floor (25% of building or road, 0.25 kills less deaths a seat) lands by itself,
    # said in a flag; past that it is refused by itself. Nothing waits.
    TRADE_TIMES = 2.5

    @staticmethod
    def trade_rule(items, times):
        """What is given up, judged: items are (words, mean, se, bar) with mean negative where the trial
        gives up; (words past the floor, the worst ratio of loss to floor, "within" or "past" or None)."""
        lost, worst = [], 0.0
        for words, mean, se, bar in items:
            if bar and mean < -bar and mean < -2 * se:
                lost.append(words)
                worst = max(worst, -mean / bar)
        if not lost:
            return [], 0.0, None
        return lost, worst, ("within" if worst <= times else "past")

    @staticmethod
    def side_read(d):
        """A census's trial less the rest in what the score does not weigh, from its logs, seed by
        seed as the score is pooled: {"built": (mean, se, seeds), "road": ..., "kd": ...}."""
        trial, rest = {}, {}
        for f in glob.glob(os.path.join(d, "g-*.log")):
            seed = None
            for l in open(f, errors="replace"):
                m = re.match(r"seed (\S+) on \S+: trial team \d", l)
                if m:
                    seed = m.group(1)
                    continue
                m = re.match(r"\s+team \d( \(trial\))?: score [-\d.]+, (.*)", l)
                if m and seed:
                    row = {k: float(v) for k, v in re.findall(r"(kills|deaths|built|road|ore|smelted|oil|supply) ([-\d.]+)", m.group(2))}
                    (trial if m.group(1) else rest).setdefault(seed, []).append(row)
        # Game 6 (treadcore LR 128) writes ore mined and shells smelted a team; read, not yet a floor.
        sides = {"built": lambda r: r.get("built", 0.0), "road": lambda r: r.get("road", 0.0),
                 "kd": lambda r: (r.get("kills", 0.0) - r.get("deaths", 0.0)) / 5.0,
                 "ore": lambda r: r.get("ore", 0.0), "smelted": lambda r: r.get("smelted", 0.0),
                 "oil": lambda r: r.get("oil", 0.0), "supply": lambda r: r.get("supply", 0.0)}
        out = {}
        for k, fn in sides.items():
            ds = [sum(map(fn, trial[x])) / len(trial[x]) - sum(map(fn, rest[x])) / len(rest[x]) for x in trial if rest.get(x)]
            if len(ds) >= 2:
                mean = sum(ds) / len(ds)
                out[k] = (mean, math.sqrt(sum((x - mean) ** 2 for x in ds) / (len(ds) - 1) / len(ds)), len(ds))
        # What the other teams build and lay a team, the level a share of it is measured against.
        for k in ("built", "road"):
            lv = [fn_r for x in rest.values() for fn_r in (sides[k](r) for r in x)]
            if lv:
                out[k + "_of"] = sum(lv) / len(lv)
        return out

    def gives_up(self, dirs, sign=1, detail=False):
        """What these reads, pooled, give up past noise and past a floor, in words. sign -1: the
        trial is what would be left behind, as in the proof, where main is the trial."""
        cache = self.state.setdefault("side_reads", {})
        reads = []
        for d in dirs or []:
            key = os.sep.join(d.rstrip(os.sep).split(os.sep)[-2:])
            if (key not in cache or "built_of" not in (cache.get(key) or {})) and os.path.exists(os.path.join(d, "pooled.txt")):
                cache[key] = self.side_read(d)
            reads.append(cache.get(key) or {})
        while len(cache) > 300:
            del cache[next(iter(cache))]
        out = []
        # BUILDING AND ROAD AS A SHARE OF WHAT THE OTHERS DO (Paul, 4 November: "ajust your floors, keep
        # what we got, maybe normalize some, but it should worke"). A team builds about 21 things on
        # the fleet's maps and lays about 8 of road, and far more on some maps than others; a floor of
        # one thing meant a twentieth on one map and nothing on another. GIVE_BUILT and GIVE_ROAD are
        # shares of the other teams' own (10%: the trades of 4 November ran 7 to 15% of building, and
        # the large ones are still held); kills less deaths stays a count a seat.
        for k, word, floor, share in (("built", "built a team", self.GIVE_BUILT, True), ("road", "road a team", self.GIVE_ROAD, True),
                                      ("kd", "kills less deaths a seat", self.GIVE_KD, False)):
            rows = [r[k] for r in reads if k in r and r[k][1] > 0]
            if rows:
                iw = sum(1 / x[1] ** 2 for x in rows)
                mean, se = sign * sum(x[0] / x[1] ** 2 for x in rows) / iw, 1 / math.sqrt(iw)
                level = [r[k + "_of"] for r in reads if r.get(k + "_of")] if share else []
                of = sum(level) / len(level) if level else None
                bar = floor * of if share and of else floor if not share else None
                out.append(("%s %+.2f +/- %.2f%s" % (word, mean, se, " (%.0f%% of the %.1f the others do)" % (-100 * mean / of, of) if share and of else ""), mean, se, bar))
        return out if detail else self.trade_rule(out, self.TRADE_TIMES)[0]

    # A TRADE IS WEIGHED AGAINST WHAT IT BUYS (Paul, 13 November: "we are fixing old training decisions.
    # adapt. just trial runs"). The limit was the same whatever was gained: 2.5 times a floor, so 0.25
    # kills less deaths a seat, for a gain of +0.3 and for one of +3.3 alike. w_smooth 0.525 gained +3.3
    # held out and gave up 0.47, and was refused thirteen times beside trials let through for giving up
    # 0.2 on a gain of 0.3. With TRADE_GAIN set, the limit stands as it was up to that gain a seat and
    # grows in proportion past it: at 1.0, a gain of +3.3 may give up 3.3 times what a gain of +1 may.
    # 0 is the rule as it was. A trial, to be read again when the fleet has shown what it lets through.
    TRADE_GAIN = 1.0
    _allow = 2.5

    def trade_allow(self, gain=None):
        """How many times its floor a trade may give up, for this gain a seat."""
        if not self.TRADE_GAIN or gain is None or gain <= self.TRADE_GAIN:
            return self.TRADE_TIMES
        return self.TRADE_TIMES * gain / self.TRADE_GAIN

    def trade(self, dirs, sign=1, gain=None):
        """gives_up, judged by the trade rule: (words, worst ratio to the floor, "within" | "past" | None)."""
        self._allow = self.trade_allow(gain)
        return self.trade_rule(self.gives_up(dirs, sign, detail=True), self._allow)

    def trades_away(self, name, v):
        """True for a candidate whose held-out reads give up building or fights past the trade rule's
        limit: it stays a candidate. Within the limit it goes on, and a flag says what it traded."""
        lost, worst, verdict = self.trade(v.get("held_dirs"), gain=v.get("held_mean"))
        if verdict == "within":
            self.flag("trade", "%s goes on by the trade rule: held out %+.2f, and it gives up %s, %.1f times its floor (the rule allows %.1f)" % (
                name, v.get("held_mean") or 0.0, ", ".join(lost), worst, self._allow), key="trade:%s" % name, progress=True)
        elif verdict == "past":
            self.flag("trade", "%s refused by the trade rule: held out %+.2f, but it gives up %s, %.1f times its floor (the rule allows %.1f)" % (
                name, v.get("held_mean") or 0.0, ", ".join(lost), worst, self._allow), key="trade:%s" % name, progress=True)
            # REFUSED, IT IS NOT ASKED AGAIN UNTIL THE RULE MOVES (13 November). w_smooth 0.525 was the strongest
            # older candidate on every set of defaults, so reread_older read it again each time, and each time
            # the rule refused it: 13 times, 11,382 seeds. What was refused is kept with the rule it was
            # refused under; a person moving the rule, or a hold, is what asks again.
            self.state.setdefault("refused", {})[self.refusal_key(v.get("weights", ""))] = [self.TRADE_TIMES, self.GIVE_BUILT, self.GIVE_ROAD, self.GIVE_KD, self.TRADE_GAIN]
        return verdict == "past"

    @staticmethod
    def refusal_key(text):
        return ";".join("%s=%.6g" % kv for kv in sorted(parse_weights(text).items()))

    def refused_still(self, text):
        """True for a trial the trade rule refused, while the rule stands as it stood then."""
        return (self.state.get("refused") or {}).get(self.refusal_key(text)) == [self.TRADE_TIMES, self.GIVE_BUILT, self.GIVE_ROAD, self.GIVE_KD, self.TRADE_GAIN]

    def batch(self, ev, name):
        """The strongest candidate's weights and, on top, each other current candidate that moves
        nothing it moves, strongest first: (text, names added). Together they have not been read:
        the tests and the families are run on the whole, and the proof stands behind it."""
        def parts(text):
            caps, rest = [], []
            for l in text.splitlines():
                bare = l.split("#")[0].strip()
                if re.match(r"^caps\s*=", bare):
                    caps += [c.strip() for c in bare.split("=", 1)[1].split(",") if c.strip() and c.strip() != "baseline"]
                elif bare:
                    rest.append(bare)
            return rest, caps

        def moves(rest, caps):
            return {l.split("=")[0].strip() for l in rest} | {c.lstrip("+-") for c in caps}
        rest, caps = parts(ev[name]["weights"])
        held, also = moves(rest, caps), []
        for k in sorted((k for k in ev if k != name), key=lambda k: -ev[k]["held_mean"]):
            r, c = parts(ev[k]["weights"])
            if moves(r, c) & held or not moves(r, c):
                continue
            held |= moves(r, c)
            rest, caps = rest + r, caps + c
            also.append(k)
        if not also:
            return ev[name]["weights"], []
        text = "# orrery: a batch: %s\n" % ", ".join([name] + also) + "\n".join(rest) + "\n"
        if caps:
            text += "caps = baseline, " + ", ".join(caps) + "\n"
        return text, also

    def auto_promote(self):
        """The strongest current candidate whose families hold, promoted: one
        promotion at a time, each candidate tried once."""
        if not self.auto():
            return
        autos = [r for r in self.runs() if r["kind"] == "promote" and r.get("by") == "auto"]
        for r in self.runs():
            if r["kind"] == "promote" and self.rstate(r["id"]).get("status") in ("new", "running", "prepared"):
                return
        # Two failed in a row: something every candidate trips on (a test, a
        # family). Auto mode waits for a person rather than trying them all.
        # Two that failed different tests failed on their own numbers (29
        # October: w1198 the square law, w1266 the capped castle), and two
        # that failed before main last moved may pass on it now: neither waits.
        last = [self.rstate(r["id"]) for r in autos[-2:]]
        # BUT TWO TRIES OF ONE CANDIDATE SAY ONLY THAT IT FAILS (1 November: w5525, on its own numbers, was
        # tried again because main moved, and stopped every other candidate behind it).
        if (len(last) == 2 and all(x.get("status") == "failed" for x in last) and last[0].get("candidate") != last[1].get("candidate")
                and self.same_failure([x.get("job") for x in last])):
            # BUT TWO BATCHES THAT CARRIED THE SAME RIDERS FAILED ON THOSE RIDERS (4 November: r0170 and
            # r0171 led by w7726 and w7616 both carried w8960, w8965 and w8815, one of them kite_turn 1.6,
            # and the kiting test failed in both; the line paused on one candidate's numbers). What they
            # share is set aside as the likely cause, and the line goes on; only two batches with nothing
            # in common pause it.
            batch = lambda r: {(r.get("params") or {}).get("candidate")} | set((r.get("params") or {}).get("with") or [])
            shared = (batch(autos[-2]) & batch(autos[-1])) - {None}
            if not shared:
                # THE PAUSE LIFTS ITSELF (Paul, 4 November: "automate this please"). It waited for a person
                # four times. Now it waits PAUSE_RESUME_MIN, or until main moves (a fix may have landed),
                # then sets the two candidates aside and goes on; their logs say what failed.
                pz = self.state.setdefault("auto_pause", {})
                after = autos[-1]["id"]
                main_now = self.main_now()
                if pz.get("after") != after:
                    pz.clear()
                    pz.update(after=after, at=time.time(), main=main_now)
                    self.flag("auto", "auto promotion paused: %s and %s failed in a row on different candidates; it goes on by itself in %d minutes, or when main moves, "
                              "with both set aside (their logs say what failed)" % (autos[-2]["id"], after, self.PAUSE_RESUME_MIN), key="paused:%s" % after, progress=True)
                    return
                if pz.get("resumed") != after:
                    if time.time() - pz.get("at", 0) < self.PAUSE_RESUME_MIN * 60 and main_now == pz.get("main"):
                        return
                    tried_ = self.state.setdefault("auto_tried", [])
                    pair = [x.get("candidate") for x in last if x.get("candidate")]
                    tried_.extend(c for c in pair if c not in tried_)
                    pz["resumed"] = after
                    self.flag("auto", "auto promotion goes on by itself after its pause (%s): %s set aside" % (
                        "main moved" if main_now != pz.get("main") else "%d minutes" % self.PAUSE_RESUME_MIN, ", ".join(pair) or "the two candidates"),
                        key="resumed:%s" % after, progress=True)
            tried_ = self.state.setdefault("auto_tried", [])
            aside = sorted(shared - set(tried_))
            if aside:
                tried_.extend(aside)
                self.flag("auto", "auto promotion goes on: %s and %s failed alike and both carried %s, set aside as the likely cause"
                          % (autos[-2]["id"], autos[-1]["id"], ", ".join(aside)), key="aside:%s" % autos[-1]["id"], progress=True)
        # ONE GENERATION A WINDOW (Paul, 1 November: half an hour). Faster than this, a generation lands
        # inside the reads of the last, and each one cost the proof, the builds and the fit's freshest
        # rows. What passes meanwhile waits, and goes together.
        p = self.promotions()
        if p and time.time() - p[-1][0] < self.GENERATION_EVERY_MIN * 60:
            return
        wait = self.settling()
        if wait:
            self.flag("line", wait + "; what passes meanwhile waits, and the strongest goes next", key="settling:%s" % self.state["local_line"]["commit"][:12], progress=True)
            return
        tried = self.state.setdefault("auto_tried", [])
        self.retry_after_main(autos, tried)
        # NOT A TRANSFORM, YET. The slot's file lives with the queue and the game has none:
        # promoted, `patch = k` would stop every game that starts. It waits for a person.
        ev = {k: v for k, v in self.evidence().items()
              if v.get("current") and v["families"] == "holds" and v["held_mean"] is not None and k not in tried
              and "patch" not in parse_weights(v["weights"]) and "bot_style" not in parse_weights(v["weights"])
              and not self.anchor_short(k, v) and not self.held_by_a_person(v["weights"]) and not self.noise(k, v) and not self.trades_away(k, v)
              and self.guard_holds(k)}
        if not ev:
            return
        name = max(ev, key=lambda k: ev[k]["held_mean"])
        tried.append(name)
        # Only the strongest counts as tried. Those riding with it, if the batch fails its tests, come
        # up again alone: and if it lands, the defaults have moved and they are not current any more.
        text, also = self.batch(ev, name)
        params = {"candidate": name}
        if also:
            params.update({"with": also, "weights": text, "name": name})
        rid = self.new_run("promote", params, "auto")
        self.flag("promote", "auto: %s asked to promote %s%s (held out %s)" % (
            rid, name, " with " + ", ".join(also) if also else "", " and ".join("%+.2f" % h[0] for h in ev[name]["held"])),
            key="auto:%s" % name, progress=True)

    # ---- older candidates, read again on today's defaults ----------------------------
    # Paul, 28 October: "why are some older, when it says promoted". A
    # candidate is read against the defaults of its day; a promotion changes
    # the defaults, and every other candidate is then evidence about a brain
    # that is no longer the game's. It may promote itself only when read
    # again on today's. With no current candidate, auto mode re-reads the
    # strongest older ones (REREAD a time): each a new trial with its census
    # and two held-out reads, on the newest commit.
    REREAD = 3

    def defaults_blob(self):
        return self.state["commits"].get(self.sha(), {}).get("weights_rs") or self.weights_rs(self.sha())

    # CARRY A PASS ACROSS A GENERATION (Paul, 1 November: "commit. push. impliment."; the whole-line
    # report, its largest gain left). Each generation threw away every read on the old defaults:
    # when r0069 landed, w4398 at z 0.83 and w4424 at z 1.07 were still being read and both passed,
    # on the defaults just overtaken. The faster generations come the more this costs, and at half
    # an hour hardly a trial could finish. So a trial that passed its held-out read on the defaults
    # the last generation replaced is read once more on the new ones, ahead of the search. Only one
    # step back, only a few: a read on old defaults says little about new ones as they drift, and a
    # read of 400 seeds is a lane for a quarter of an hour.
    CARRY_MAX = 3

    def parent_of(self, commit):
        return run(["git", "-C", self.tc, "rev-parse", commit + "^"]).stdout.strip()

    def same_as(self, a_commit, b_commit):
        """Two commits read the same defaults: same_defaults, between any two."""
        a, b = self.defaults_at(a_commit), self.defaults_at(b_commit)
        common = set(a) & set(b)
        return bool(common) and all(a[k] == b[k] for k in common) and self.game_at(a_commit) == self.game_at(b_commit)

    def carry_passes(self):
        """Returns what it carried. Called each plan, because a read still running when the
        generation landed finishes after it."""
        if not self.auto() or not self.CARRY_MAX:
            return []
        p = self.promotions()
        if not p:
            return []
        rid, st_ = p[-1][1], p[-1][2]
        carried = self.state.setdefault("carried", {})
        if carried.get("for") != rid:
            carried.clear()
            carried.update({"for": rid, "names": []})
        room = self.CARRY_MAX - len(carried["names"])
        commit = st_.get("self_modified_at") or st_.get("commit")
        if room <= 0 or not commit:
            return []
        parent = self.parent_of(commit)
        if not parent:
            return []
        promoted = {self.rstate(r["id"]).get("candidate") for r in self.runs()
                    if r["kind"] == "promote" and self.rstate(r["id"]).get("status") in ("approved", "self-modified")}
        for r in self.runs():
            if r["kind"] == "promote" and self.rstate(r["id"]).get("status") in ("approved", "self-modified"):
                promoted |= set((r.get("params") or {}).get("with", []))
        ev = self.evidence()
        out = []
        for k, v in sorted(ev.items(), key=lambda kv: -(kv[1].get("held_mean") or -99)):
            if len(out) >= room:
                break
            if not k.startswith(self.name + "/") or v.get("current") or k in promoted or k in carried["names"] or self.anchor_short(k, v):
                continue
            if "bot_style" in parse_weights(v["weights"]) or self.held_by_a_person(v["weights"]):
                continue
            if not v.get("commits") or not all(c and self.same_as(c, parent) for c in v["commits"]):
                continue
            self.adopt(v["weights"], "%s carried to %s" % (k.split("/", 1)[1], self.short()))
            self.state["adopt"][-1]["reads"] = 1
            carried["names"].append(k)
            out.append(k)
            self.flag("carry", "%s passed on the defaults %s replaced: read again on the new ones" % (k, rid), key="carry:%s:%s" % (k, rid), progress=True)
        return out

    def reread_older(self, force=False):
        """Queue the strongest older candidates again; returns their names."""
        if not force and not self.auto():
            return []
        ev = self.evidence()
        if not force and any(v.get("current") for v in ev.values()):
            return []
        # Once a generation is half an hour, reading three old trials each is a tenth of the
        # fleet on what was already passed by: only when nothing has been found for two hours.
        if not force and self.state.get("difficulty", {}).get("dry_min", 0) < 120:
            return []
        done = self.state.setdefault("reread", {})
        blob = self.defaults_blob()
        # One round a set of defaults, unless asked.
        if not force and any(b == blob for b in done.values()):
            return []
        # A promoted candidate is the defaults: read again it would be
        # measured against itself.
        promoted = {self.rstate(r["id"]).get("candidate") for r in self.runs()
                    if r["kind"] == "promote" and self.rstate(r["id"]).get("status") in ("approved", "self-modified")}
        older = sorted(((k, v) for k, v in ev.items() if k.startswith(self.name + "/") and not v.get("current")
                        and k not in promoted and v["held_mean"] is not None and done.get(k) != blob and not self.refused_still(v["weights"])),
                       key=lambda kv: -kv[1]["held_mean"])[:self.REREAD]
        for k, v in older:
            self.adopt(v["weights"], "%s again on %s" % (k.split("/", 1)[1], self.short()))
            done[k] = blob
            self.flag("reread", "%s read again on today's defaults (%s): it was read on older ones" % (k, self.short()),
                      key="reread:%s:%s" % (k, blob[:8]), progress=True)
        return [k for k, _ in older]

    def now(self):
        """Do it now (Paul, 28 October: "it has a do it now button to sync and
        push the values"): sync, then the strongest current candidate whose
        families hold is promoted (tests and families on a branch, then
        main); with none, the strongest older ones are read again."""
        self.sync()
        for r in self.runs():
            if r["kind"] == "promote" and self.rstate(r["id"]).get("status") in ("new", "running", "prepared"):
                print("a promotion is already under way: %s" % r["id"])
                return
        ev = {k: v for k, v in self.evidence().items() if v.get("current") and v["families"] == "holds" and v["held_mean"] is not None and "patch" not in parse_weights(v["weights"])}
        if ev:
            name = max(ev, key=lambda k: ev[k]["held_mean"])
            rid = self.new_run("promote", {"candidate": name}, "now")
            self.keep()
            print("%s: promoting %s (held out %s); in auto mode it is pushed to main when its tests and families pass"
                  % (rid, name, " and ".join("%+.2f" % h[0] for h in ev[name]["held"])))
            return
        names = self.reread_older(force=True)
        self.keep()
        print("no candidate on today's defaults (%s) to promote; read again: %s" % (self.short(), ", ".join(names) or "none left"))

    def propagation(self):
        """For each approved promotion: has each machine built a commit whose
        defaults carry the promoted values? Read from the defaults.toml each
        machine's build brought back; confirmed on all, it is progress."""
        for r in self.runs():
            rid = r["id"]
            if r["kind"] != "promote":
                continue
            st = self.rstate(rid)
            if st.get("status") not in ("approved", "self-modified") or st.get("confirmed"):
                continue
            want = {k: v["value"] for k, v in changed_vars(st.get("changed", [])).items()}
            # Every commit main has been at since the promotion (each carries
            # its values, unless a later promotion moved them): a machine is
            # confirmed by any finished build of one of them whose defaults
            # have the values, not only by its newest, which may still be
            # queued behind its work (28 October: two of seven read
            # "confirmed" while all seven had built them).
            since = st.get("approved", "")
            shorts = [st.get("commit", "")[:7]] + [c[:7] for c, v in self.state.get("commits", {}).items()
                                                   if v.get("first_seen", "") >= since and c[:7] != st.get("commit", "")[:7]]
            done, live, gone = self.ids("done"), self.ids("queue", "running"), self.ids("failed", "stopped")
            hosts = {}
            for h in self.hosts:
                name, ok, differs, building, failed = h["name"], None, None, None, None
                for short in shorts:
                    jid = "prep-%s-%s" % (name, short)
                    if jid in done:
                        f = glob.glob(os.path.join(self.q, "results", jid, self.home, "c", short, "defaults.toml"))
                        if not f:
                            continue
                        got = parse_weights(open(f[0]).read())
                        off = [k for k, v in want.items() if k not in got or abs(got[k] - v) > 1e-6 * max(1.0, abs(v))]
                        if off:
                            differs = differs or "differs at %s: %s" % (short, ", ".join(off))
                        else:
                            ok = ok or short
                    elif jid in live:
                        building = building or short
                    elif jid in gone:
                        failed = failed or short
                hosts[name] = ("confirmed at %s" % ok if ok else differs if differs else "building %s" % building if building
                               else "build of %s failed" % failed if failed else "waiting for its build")
            st["hosts"] = hosts
            ok = [n for n, v in hosts.items() if v.startswith("confirmed")]
            # "Self-modified" is a commit on the LOCAL LINE, not on main: main moves only when the line's
            # proof reads it past main (5 November: r0196, r0199 and r0201 said "on main at" while
            # origin/main still stood at r0186, and a person asked whether they were pushed).
            st["detail"] = "on %s at %s; values confirmed on %d of %d machines%s" % (
                "the line" if st.get("status") == "self-modified" else "main", st.get("commit", "")[:7], len(ok), len(hosts),
                "" if len(ok) == len(hosts) else " (" + "; ".join("%s: %s" % (n, v) for n, v in hosts.items() if n not in ok) + ")")
            if hosts and len(ok) == len(hosts):
                st["confirmed"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                self.flag("propagated", "promotion %s: %s's values confirmed on all %d machines (%s)" % (
                    rid, st.get("candidate"), len(hosts), ", ".join(sorted(hosts))), key="propagated:%s" % rid, progress=True)
            elif any(v.startswith("differs") or "failed" in v for v in hosts.values()):
                self.flag("propagated", "promotion %s: not every machine has its values: %s" % (rid, st["detail"]), key="propagation:%s:%s" % (rid, st["detail"]))
            self.rsave(rid, st)

    def text(self, v):
        """A weights parameter: a file under treadcore, or the text itself ("a = 1;b = 2")."""
        if not v:
            return ""
        if v == "@best":
            # The newest best the queue's search suggested.
            gens = sorted(glob.glob(os.path.join(self.pd, "gen*", "best.weights")), key=lambda f: int(re.search(r"gen(\d+)", f).group(1)))
            return open(gens[-1]).read() if gens else ""
        p = os.path.join(self.tc, v) if not os.path.isabs(v) else v
        if os.path.isfile(p):
            return open(p).read()
        return v.replace(";", "\n") + "\n"

    def census_job(self, jid, title, trial, base, seeds, seed0, secs, mp, respawns=3, net=None, host=None, env="", also=None):
        b1 = base64.b64encode(trial.encode()).decode()
        b2 = base64.b64encode(base.encode()).decode()
        net_env = env
        send = list(also or [])
        if net:
            send.append({"src": net, "dst": "~/%s/trials/%s.net" % (self.home, jid)})
            net_env += "CENSUS_NET=$Q/trials/%s.net " % jid
        cmd = (
            "set -e; [ -f ~/.cargo/env ] && . ~/.cargo/env; export PATH=$HOME/.cargo/bin:$PATH\n"
            # As census_cmd: BSD paste keeps a Mac on one map of eleven. Every read of a run on macmini
            # was of one map until this (1 November: Castle read -3.88 so, and the Duelist -25).
            "paste() { command paste \"$@\" -; }; export -f paste\n"
            "Q=~/%s; C=%s; mkdir -p $Q/trials\n"
            "echo %s | base64 -d > $Q/trials/%s.trial; echo %s | base64 -d > $Q/trials/%s.base\n"
            "cd $C/wt && export CARGO_TARGET_DIR=$HOME/fleet/target\n"
            "%s%s%sSEEDS=%d SEED0=%d SECS=%s MAP=%s RESPAWNS=%s JOBS=$(nproc 2>/dev/null || sysctl -n hw.ncpu) CENSUS_BIN=$C/census-bin scripts/census.sh 2>&1 | tail -3\n"
            "d=$(ls -td build/census/*/ | head -1); s=$(basename $d)\n"
            "rm -rf $Q/out/%s; mkdir -p $Q/out/%s/$s; cp $d/*.txt $d/*.env $d/*.weights $d/g-*.log $Q/out/%s/$s/ 2>/dev/null; rm -rf $d\n"
        ) % (self.home, self.cdir(), b1, jid, b2, jid,
             "TRIAL=$Q/trials/%s.trial " % jid if trial.strip() else "",
             "BASE=$Q/trials/%s.base " % jid if base.strip() else "", net_env,
             int(seeds), int(seed0), secs, mp, respawns, jid, jid, jid)
        j = {"id": jid, "kind": "census", "title": title, "needs": "host:" + host if host else "cpu",
             "after_host": self.after_host(), "cmd": cmd, "fetch": "%s/out/%s" % (self.home, jid), "timeout_s": 12 * 3600}
        if send:
            j["send"] = send
        return j

    def job_census(self, jid):
        """(d, se, verdict line, host) of a fetched census job, or None."""
        ds = glob.glob(os.path.join(self.q, "results", jid, self.home, "out", jid, "*", "pooled.txt"))
        if not ds:
            return None
        lines = open(ds[0]).read().splitlines()
        for l in lines:
            m = re.match(r"^every map\s+([-+][\d.]+) \+/- ([\d.]+) over\s+(\d+) seeds \((.*)\)", l)
            if m:
                envs = env_file(os.path.join(os.path.dirname(ds[0]), "run.env"))
                host = self.qcfg.get("aliases", {}).get(envs.get("HOST", ""), envs.get("HOST", ""))
                return float(m.group(1)), float(m.group(2)), m.group(4), host
        return None

    def list_items(self, kind, params):
        """The censuses of parts, switches or roundrobin, from treadcore's LIST=1."""
        env = dict(os.environ, LIST="1")
        for k, v in params.items():
            env[k.upper()] = str(v)
        r = run(["bash", os.path.join(self.tc, "scripts", "%s.sh" % kind)], env=env, cwd=self.tc, timeout=60)
        if r.returncode != 0:
            raise SystemExit("%s LIST=1: %s" % (kind, r.stderr[-300:]))
        settings, items = {}, []
        for l in r.stdout.splitlines():
            if l.startswith("#settings"):
                settings = dict(kv.split("=", 1) for kv in l.split()[1:])
            elif l.strip():
                name, trial, base = (l.split("\t") + ["", ""])[:3]
                items.append({"name": name, "trial": trial.replace(";", "\n") + "\n", "base": base.replace(";", "\n") + "\n"})
        return settings, items

    def run_jobs(self, n):
        # Runs advance whether or not a machine has built the newest commit:
        # a new job waits for its machine's build (after_host) by itself.
        jobs = []
        for r in self.runs():
            if len(jobs) >= n:
                break
            first = len(jobs)
            rid, kind, p = r["id"], r["kind"], r.get("params", {})
            st = self.rstate(rid)
            if st["status"] in ("done", "failed", "stopped", "approved", "self-modified", "rejected", "orphaned"):
                continue
            if kind in self.CENSUS_KINDS:
                jobs += self.census_run(rid, kind, p, st)
            elif kind == "spsa":
                jobs += self.spsa_run(rid, p, st)
            elif kind == "tune":
                jobs += self.tune_run(rid, p, st)
            elif kind == "patch":
                jobs += self.patch_run(rid, p, st)
            elif kind in self.HARNESS_KINDS:
                jobs += self.harness_run(rid, kind, p, st)
            elif kind == "record":
                jobs += self.record_run(rid, p, st, n - len(jobs))
            elif kind == "promote":
                jobs += self.promote_run(rid, p, st)
            elif kind == "families":
                # Every candidate's families read again (after a promotion,
                # say): the next top-ups queue them all.
                self.state["families_queued"] = []
                self.rsave(rid, {"status": "done", "detail": "every candidate queued again"})
            else:
                st.update({"status": "failed", "why": "no such kind %s" % kind})
                self.rsave(rid, st)
            # What a person asked for goes ahead of the standing search; the
            # rotation's runs share the fleet with it.
            if r.get("by") != "rotation":
                for j in jobs[first:]:
                    j["priority"] = "high"
        return jobs

    # census, parts, switches, roundrobin: a census an item, then a table.
    def census_run(self, rid, kind, p, st):
        if st["status"] == "new":
            if kind == "census":
                settings = {"SEEDS": p.get("seeds", 55), "SEED0": p.get("seed0", 0), "SECS": p.get("secs", 900),
                            "MAP": p.get("map", "all"), "RESPAWNS": p.get("respawns", 3)}
                items = [{"name": p.get("name", "trial"), "trial": self.text(p.get("trial", "")), "base": self.text(p.get("base", ""))}]
            else:
                settings, items = self.list_items(kind, {k: v for k, v in p.items() if k.upper() in
                                                         ("PARTS", "SWITCHES", "PROFILES", "SEEDS", "SEED0", "SECS", "MAP", "RESPAWNS")})
            st = {"status": "running", "settings": settings, "items": [], "commit": self.short()}
            jobs = []
            for i, it in enumerate(items):
                jid = "%s-%02d" % (rid, i)
                st["items"].append({"name": it["name"], "job": jid})
                jobs.append(self.census_job(jid, "%s %s: %s" % (kind, rid, it["name"]), it["trial"], it["base"],
                                            settings["SEEDS"], settings.get("SEED0", 0), settings["SECS"], settings["MAP"],
                                            settings.get("RESPAWNS", 3), net=p.get("net")))
            self.rsave(rid, st)
            return jobs
        # Running: the table, when every census is back.
        done = self.ids("done")
        gone = self.ids("failed", "stopped")
        rows, left = [], 0
        for it in st["items"]:
            c = self.job_census(it["job"]) if it["job"] in done else None
            if c:
                rows.append("%-28s %+8.2f %6.2f  %-22s %s" % (it["name"], c[0], c[1], c[2], c[3]))
            elif it["job"] in gone:
                rows.append("%-28s %8s %6s  %s" % (it["name"], "?", "?", "failed"))
            else:
                left += 1
        if left == 0:
            with open(os.path.join(self.rdir(rid), "table.txt"), "w") as f:
                f.write("%s %s at %s: %s\n" % (kind, rid, st.get("commit"), " ".join("%s=%s" % kv for kv in st["settings"].items())))
                f.write("%-28s %8s %6s  %-22s %s\n" % ("name", "diff", "se", "verdict", "machine"))
                f.write("\n".join(rows) + "\n")
            st["status"] = "done"
            self.rsave(rid, st)
        return []

    # SPSA (scripts/spsa.sh's rule, a step a census on one machine).
    def theta0(self, p):
        if p.get("start"):
            return parse_weights(self.text(p["start"]))
        return parse_weights(open(self.defaults()).read())

    def spsa_run(self, rid, p, st):
        tune = p.get("tune", "dodge_horizon dodge_margin dodge_clear").replace(",", " ").split()
        steps, seeds, seed0 = int(p.get("steps", 8)), int(p.get("seeds", 12)), int(p.get("seed0", 1000))
        A, C, maxstep, bound = float(p.get("a", 0.6)), float(p.get("c", 0.4)), float(p.get("maxstep", 0.5)), float(p.get("bound", 2))
        if st["status"] == "new":
            if not p.get("start") and not self.defaults():
                return []  # the census host has not built this commit yet
            th = self.theta0(p)
            for w in tune:
                if w not in th or th[w] <= 0:
                    st.update({"status": "failed", "why": "%s is not a positive weight" % w})
                    self.rsave(rid, st)
                    return []
            st = {"status": "running", "k": 0, "theta": {w: th[w] for w in tune}, "start": {w: th[w] for w in tune},
                  "steps": [], "pending": None, "commit": self.short()}
        if st.get("pending"):
            pend = st["pending"]
            if pend["job"] in self.ids("failed", "stopped"):
                st.update({"status": "failed", "why": "step %d's census failed" % pend["k"]})
                self.rsave(rid, st)
                return []
            c = self.job_census(pend["job"]) if pend["job"] in self.ids("done") else None
            if not c:
                return []
            d, se = c[0], c[1]
            k, ak, ck = pend["k"], pend["ak"], pend["ck"]
            row = {"k": k, "d": d, "se": se, "host": c[3]}
            for w in tune:
                sgn = pend["sign"][w]
                step = ak * d / (2 * ck * sgn)
                step = max(-maxstep, min(maxstep, step))
                x = st["theta"][w] * math.exp(step)
                if bound > 0:
                    x = max(st["start"][w] / bound, min(st["start"][w] * bound, x))
                st["theta"][w] = round(x, 4)
                row[w] = st["theta"][w]
            st["steps"].append(row)
            st["pending"] = None
            self.tick({"kind": "spsa", "run": rid, "step": k, "d": d, "se": se, "host": c[3],
                       "vars": {w: st["theta"][w] for w in tune}, "improved": False})
            write_tsv(os.path.join(self.rdir(rid), "steps.tsv"), st["steps"])
            with open(os.path.join(self.rdir(rid), "theta.weights"), "w") as f:
                f.write("".join("%s = %s\n" % kv for kv in st["theta"].items()))
        if st["k"] >= steps:
            st["status"] = "done"
            self.rsave(rid, st)
            return []
        k = st["k"] + 1
        ak, ck = A / (k + 1) ** 0.602, C / k ** 0.101
        rnd = random.Random("%s-%d" % (rid, k))
        sign = {w: rnd.choice((-1, 1)) for w in tune}
        plus = "".join("%s = %.4f\n" % (w, st["theta"][w] * math.exp(ck * sign[w])) for w in tune)
        minus = "".join("%s = %.4f\n" % (w, st["theta"][w] * math.exp(-ck * sign[w])) for w in tune)
        base_extra = self.text(p.get("start", "")) if p.get("start") else ""
        jid = "%s-k%02d" % (rid, k)
        st["k"] = k
        st["pending"] = {"k": k, "ak": ak, "ck": ck, "sign": sign, "job": jid}
        self.rsave(rid, st)
        return [self.census_job(jid, "spsa %s: step %d of %d" % (rid, k, steps), base_extra + plus, base_extra + minus,
                                seeds, seed0 + (k - 1) * seeds, p.get("secs", 900), p.get("map", "maps/naval.map"))]

    # ---- the transform: Algorhythm's last stage (treadcore patch.rs) ----------------------
    # SPSA, because a step costs two sides of one census however many numbers there are:
    # a transform is about 900 and a census is minutes. The sides are a patch each, played
    # on the same seeds. IT STARTS AT TODAY'S BRAIN: every correction 0 and the confidence
    # just past the gate, so the gate can close or open by what the senses say, and until a
    # correction grows the games are the rules' own (patch_gate_open_is_the_rules, read by
    # a census at exactly 0.00). A run takes up where the last left off. What it ends with
    # goes in a slot, and the fleet reads the slot as it reads any version: 55 seeds, the
    # read on, two held-out reads. A step's own number is far too noisy to judge it by.
    PATCH_INPUTS = 153  # senses 143, waves 3, the rules' answer 3, the best base 4
    PATCH_STEP = 3 * (PATCH_INPUTS + 3) + 3

    @staticmethod
    def patch_write(path, theta, depth):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".part", "wb") as f:
            f.write(b"TCP1" + struct.pack("<II", depth, Plan.PATCH_INPUTS) + struct.pack("<%df" % len(theta), *theta))
        os.rename(path + ".part", path)

    @staticmethod
    def patch_start(depth):
        theta = [0.0] * (Plan.PATCH_STEP * depth)
        # b[2] of the first step: tanh(0.6) = 0.54, past patch_confidence's 0.5.
        theta[Plan.PATCH_STEP - 1] = 0.6
        return theta

    def patch_install(self, rid, theta, depth):
        d = os.path.join(self.q, "patches")
        os.makedirs(d, exist_ok=True)
        files = {k: os.path.join(d, "%d.bin" % k) for k in range(1, 8)}
        free = [k for k, f in files.items() if not os.path.exists(f)]
        slot = free[0] if free else min(files, key=lambda k: os.path.getmtime(files[k]))
        self.patch_write(files[slot], theta, depth)
        save(os.path.join(d, "theta.json"), {"depth": depth, "theta": theta, "run": rid})
        self.flag("patch", "%s: a transform of %d steps is in slot %d; the fleet reads it next" % (rid, depth, slot),
                  key="patch:%s" % rid, progress=True)

    def patch_run(self, rid, p, st):
        depth, steps, seeds = int(p.get("depth", 2)), int(p.get("steps", 30)), int(p.get("seeds", 24))
        seed0 = int(p.get("seed0", 700000000))
        # A step well under the probe: at a = 0.05 every number moved its full 0.05 on one
        # census of 24 seeds, more than the probe itself, and a random 0.15 loses 11 a seat
        # (r0063, cancelled after a step). At these, a read of +2 moves each about 0.005.
        A, C, maxstep = float(p.get("a", 0.00025)), float(p.get("c", 0.03)), float(p.get("maxstep", 0.01))
        if st["status"] == "new":
            if not self.defaults():
                return []
            last = load(os.path.join(self.q, "patches", "theta.json"), {})
            theta = last["theta"] if last.get("depth") == depth else self.patch_start(depth)
            st = {"status": "running", "k": 0, "theta": theta, "steps": [], "pending": None, "commit": self.short()}
        if st.get("pending"):
            pend = st["pending"]
            if pend["job"] in self.ids("failed", "stopped"):
                st.update({"status": "failed", "why": "step %d's census failed" % pend["k"]})
                self.rsave(rid, st)
                return []
            c = self.job_census(pend["job"]) if pend["job"] in self.ids("done") else None
            if not c:
                return []
            d = c[0]
            rnd = random.Random("%s-%d" % (rid, pend["k"]))
            for i in range(len(st["theta"])):
                sign = rnd.choice((-1, 1))
                st["theta"][i] += max(-maxstep, min(maxstep, pend["ak"] * d / (2 * pend["ck"] * sign)))
            st["steps"].append({"k": pend["k"], "d": d, "se": c[1], "host": c[3]})
            st["pending"] = None
            self.tick({"kind": "patch", "run": rid, "step": pend["k"], "d": d, "se": c[1], "host": c[3], "vars": {}, "improved": False})
        if st["k"] >= steps:
            self.patch_install(rid, st["theta"], depth)
            st["status"] = "done"
            self.rsave(rid, st)
            return []
        k = st["k"] + 1
        ak, ck = A / (k + 1) ** 0.602, C / k ** 0.101
        rnd = random.Random("%s-%d" % (rid, k))
        signs = [rnd.choice((-1, 1)) for _ in st["theta"]]
        jid = "%s-k%02d" % (rid, k)
        also = []
        for slot, sg in ((1, 1), (2, -1)):
            f = os.path.join(self.rdir(rid), "k%02d" % k, "%d.bin" % slot)
            self.patch_write(f, [t + sg * ck * s for t, s in zip(st["theta"], signs)], depth)
            also.append({"src": f, "dst": "~/%s/trials/%s.patches/%d.bin" % (self.home, jid, slot)})
        st["k"] = k
        st["pending"] = {"k": k, "ak": ak, "ck": ck, "job": jid}
        self.rsave(rid, st)
        w = self.cfg.get("weights") or {}
        return [self.census_job(jid, "transform %s: step %d of %d" % (rid, k, steps), "patch = 1\n", "patch = 2\n", seeds,
                                seed0 + (k - 1) * seeds, p.get("secs", w.get("secs", 900)), p.get("map", w.get("map", "all")),
                                env="CENSUS_PATCHES=$Q/trials/%s.patches " % jid, also=also)]

    # A (1 + lambda) evolution strategy (scripts/tune.sh's rule), a
    # generation's children side by side, the best replacing the parent
    # only by beating it.
    def tune_run(self, rid, p, st):
        default_tune = "w_near w_wounded w_finish w_focus w_overkill w_in_range w_threat w_stick engage_odds press_odds w_exposure w_flank k_long c_boat swap_gap"
        tune = p.get("tune", default_tune).replace(",", " ").split()
        gens, lam, sigma = int(p.get("generations", 5)), int(p.get("lambda", 4)), float(p.get("sigma", 0.15))
        seeds, secs, mp = int(p.get("seeds", 2)), p.get("secs", 900), p.get("map", "all")
        # Its seeds: the same for every child of a run (a fair comparison),
        # new for each run (the rotation passes seed0).
        seed0 = int(p.get("seed0", 0))
        done, gone = self.ids("done"), self.ids("failed", "stopped")
        if st["status"] == "new":
            if not p.get("start") and not self.defaults():
                return []  # the census host has not built this commit yet
            th = self.theta0(p)
            parent = {w: th[w] for w in tune if w in th}
            jid = "%s-g00-parent" % rid
            st = {"status": "running", "g": 0, "parent": parent, "fit": None, "children": [jid], "kids": {jid: parent},
                  "log": [], "commit": self.short()}
            self.rsave(rid, st)
            return [self.census_job(jid, "tune %s: the parent" % rid, "".join("%s = %s\n" % kv for kv in parent.items()), "",
                                    seeds, seed0, secs, mp)]
        if any(j in gone for j in st["children"]):
            st.update({"status": "failed", "why": "a child's census failed"})
            self.rsave(rid, st)
            return []
        if not all(j in done for j in st["children"]):
            return []
        fits = {j: self.job_census(j) for j in st["children"]}
        for j, c in fits.items():
            if c is None:
                continue
            better = st["fit"] is not None and c[0] > st["fit"]
            if st["fit"] is None:
                st["fit"] = c[0]
            elif better:
                st["parent"], st["fit"] = st["kids"][j], c[0]
            st["log"].append({"g": st["g"], "job": j, "fit": c[0], "se": c[1], "host": c[3], "parent": better})
            if st["g"] > 0:
                self.tick({"kind": "tune", "run": rid, "job": j, "d": c[0], "se": c[1], "host": c[3],
                           "vars": st["kids"][j], "improved": better})
        write_tsv(os.path.join(self.rdir(rid), "children.tsv"), st["log"])
        with open(os.path.join(self.rdir(rid), "best.weights"), "w") as f:
            f.write("# tune %s: fitness %s\n" % (rid, st["fit"]) + "".join("%s = %s\n" % kv for kv in st["parent"].items()))
        if st["g"] >= gens:
            st["status"] = "done"
            self.rsave(rid, st)
            return []
        st["g"] += 1
        rnd = random.Random("%s-%d" % (rid, st["g"]))
        st["children"], st["kids"] = [], {}
        jobs = []
        for c in range(1, lam + 1):
            kid = {w: round(v * math.exp(sigma * rnd.gauss(0, 1)), 4) for w, v in st["parent"].items()}
            jid = "%s-g%02d-c%d" % (rid, st["g"], c)
            st["children"].append(jid)
            st["kids"][jid] = kid
            jobs.append(self.census_job(jid, "tune %s: generation %d child %d" % (rid, st["g"], c),
                                        "".join("%s = %s\n" % kv for kv in kid.items()), "", seeds, seed0, secs, mp))
        self.rsave(rid, st)
        return jobs

    # The learning harness (train, gauntlet, clips, school): one job.
    def harness_run(self, rid, kind, p, st):
        if st["status"] != "new":
            jid = st["job"]
            if jid in self.ids("done"):
                st["status"] = "done"
            elif jid in self.ids("failed", "stopped"):
                st["status"] = "failed"
            self.rsave(rid, st)
            return []
        jid = "%s-%s" % (rid, kind)
        # THE LEAGUE'S LOOP (docs/brains.md 6): a run nobody gave a start begins from
        # the strongest model the fleet has read, so generations build on each other
        # rather than each starting over. Asked once, so a run keeps its start.
        if kind in ("train", "school") and not p.get("start"):
            best = self.best_slot()
            if best:
                p = dict(p, start=best["source"])
                self.flag("league", "%s %s starts from slot %d, %s" % (kind, rid, best["slot"], best["name"]),
                          key="league:%s" % rid, progress=True)
        env = {"train": "", "gauntlet": "GAUNTLET=1 ", "clips": "CLIPS=1 ", "school": "SCHOOL=1 "}[kind]
        send = []
        for k in ("start", "check"):
            if p.get(k):
                src = os.path.join(self.tc, p[k]) if not os.path.isabs(p[k]) else p[k]
                send.append({"src": src, "dst": "~/%s/trials/%s.%s.bin" % (self.home, jid, k)})
                env += "%s=$Q/trials/%s.%s.bin " % (k.upper(), jid, k)
        # The harness's own names, where the Makefile renamed them.
        alias = {"gauntlet": {"runs": "GAUNTLET_RUNS"}}.get(kind, {})
        for k, v in p.items():
            if k not in ("start", "check", "host"):
                env += "%s=%s " % (alias.get(k, k.upper()), shlex.quote(str(v)))
        cmd = (
            "set -e; [ -f ~/.cargo/env ] && . ~/.cargo/env; export PATH=$HOME/.cargo/bin:$PATH\n"
            "Q=~/%s; C=%s; O=$Q/out/%s; mkdir -p $O $Q/trials\n"
            "cd $C/wt && %sOUT=$O THREADS=${THREADS:-$(nproc 2>/dev/null || sysctl -n hw.ncpu)} "
            "$C/census-bin --ignored learn::harness::train --nocapture 2>&1 | tee $O/harness.log | tail -20\n"
        ) % (self.home, self.cdir(), jid, env)
        job = {"id": jid, "kind": kind, "title": "%s %s" % (kind, rid), "needs": "host:%s" % p["host"] if p.get("host") else "cpu",
               "after_host": self.after_host(), "cmd": cmd, "fetch": "%s/out/%s" % (self.home, jid), "timeout_s": 72 * 3600}
        if send:
            job["send"] = send
        self.rsave(rid, {"status": "running", "job": jid, "commit": self.short()})
        return [job]

    # Recordings for behaviour cloning: a shard a job, streamed to the store.
    def record_run(self, rid, p, st, n):
        name = p.get("run", rid)
        seed0, count, per, secs = int(p.get("seed0", 9100000)), int(p.get("count", 120)), int(p.get("per", 12)), int(p.get("secs", 600))
        store = p.get("store", next((h["target"] for h in self.hosts if "gpu" in h.get("caps", [])), None))
        if not store:
            st.update({"status": "failed", "why": "no store: name one (store=user@host) or a gpu host"})
            self.rsave(rid, st)
            return []
        if st["status"] == "new":
            st = {"status": "running", "next": seed0, "end": seed0 + count, "jobs": [], "commit": self.short(), "store": store, "run": name}
        jobs = []
        while st["next"] < st["end"] and len(jobs) < max(1, n):
            s0, k = st["next"], min(per, st["end"] - st["next"])
            jid = "%s-%d" % (rid, s0)
            cmd = (
                "set -e -o pipefail; Q=~/%s; C=%s; mkdir -p $Q/out\n"
                "cd $C/wt && RECORD=$Q/out/%s.bin SEED0=%d SEEDS=%d SECS=%d THREADS=$(nproc 2>/dev/null || sysctl -n hw.ncpu) "
                "$C/census-bin --ignored learn::harness::train --nocapture 2>&1 | tail -4\n"
                "[ $(wc -c < $Q/out/%s.bin) -gt 16 ]\n"
            ) % (self.home, self.cdir(), jid, s0, k, secs, jid)
            jobs.append({"id": jid, "kind": "record", "title": "record %s: seeds %d to %d" % (name, s0, s0 + k - 1),
                         "needs": "cpu", "after_host": self.after_host(), "cmd": cmd, "timeout_s": 12 * 3600,
                         "deliver": {"src": "~/%s/out/%s.bin" % (self.home, jid), "to": store, "dst": "~/fleet/%s/shards/%d.bin" % (name, s0)}})
            st["jobs"].append(jid)
            st["next"] += k
        done, gone = self.ids("done"), self.ids("failed", "stopped")
        if st["next"] >= st["end"] and all(j in done or j in gone for j in st["jobs"]) and not jobs:
            st["status"] = "done"
            st["failed"] = [j for j in st["jobs"] if j in gone]
        self.rsave(rid, st)
        return jobs


    # ---- push permission: what a template must have for Approve to mean anything ----
    def push_target(self):
        p = self.cfg.get("push") or {}
        return p.get("remote", "origin"), p.get("branch", "main")

    def push_check(self):
        """Can this coordinator push the project's branch? A dry-run push of
        the remote's own head to it: it reaches the remote, proves the
        credentials, and changes nothing. Kept in plan/push.json."""
        remote, branch = self.push_target()
        url = run(["git", "-C", self.tc, "remote", "get-url", "--push", remote]).stdout.strip()
        run(["git", "-C", self.tc, "fetch", "-q", remote], timeout=120)
        head = run(["git", "-C", self.tc, "rev-parse", "%s/%s" % (remote, branch)]).stdout.strip()
        if not url or not head:
            ok, detail = False, "no remote %s with a branch %s in %s" % (remote, branch, self.tc)
        else:
            r = run(["git", "-C", self.tc, "push", "--dry-run", "--porcelain", remote, "%s:refs/heads/%s" % (head, branch)], timeout=120)
            ok = r.returncode == 0
            detail = "ok" if ok else (r.stderr.strip().splitlines() or ["refused"])[-1][:200]
        st = {"ok": ok, "remote": remote, "url": url, "branch": branch, "detail": detail, "checked": time.strftime("%Y-%m-%dT%H:%M:%S")}
        save(os.path.join(self.pd, "push.json"), st)
        if not ok:
            self.flag("push", "no push permission to %s %s: %s" % (url or remote, branch, detail), key="push:%s" % time.strftime("%Y-%m-%d"))
        return st

    # ---- promotion: a candidate prepared for treadcore, then accepted -----------
    # Paul, 28 October: "The process needs to be scripted without
    # intervention ... reword them to say Paul Accepts when auto promote is
    # on, and ssh credentials allow. Else they self modify, and have a flag
    # for please resolve this by commiting the weights and nets."
    #
    # A prepared promotion (its tests and families passed on a branch) is
    #   accepted:      auto mode on and this coordinator can push: Paul
    #                  Accepts, by his standing word; it is pushed to main and
    #                  tagged brain-RID;
    #   self-modified: otherwise: it goes onto the local line, a branch
    #                  orrery/accepted in this checkout (main and the
    #                  promotions not on it). The fleet builds the local line
    #                  (a git bundle sent with each build), so the work goes on
    #                  with the new values, and a flag asks Paul to resolve it:
    #                  commit the weights and nets to main. When main holds the
    #                  local line (Paul pushed it, or the credentials came back
    #                  and auto mode pushed it), the line ends.
    # Nothing waits for a person.
    LINE = "orrery/accepted"
    # A WRITER MOVES THE LINE; A READER SEES IT AS IT WAS KEPT (4 November). The line's branch and
    # its bundle are set in the same pass that saves the state naming the line's head. A reader
    # (analysis.py, the console's reports) used to replay the line too when main had moved, and
    # saved no state: at 20:09 it moved the branch and the bundle to a replay of its own, d821e7b,
    # forty seconds after the keeper's pass had kept f04f157, every machine was sent to build
    # f04f157 with a bundle that did not hold it, and all eight CPU lanes stood idle for an hour.
    # Only the commands that keep the state are writers (__main__).
    writer = False

    def evidence(self):
        """Every candidate with its weights and evidence: the census, the two
        held-out reads, and its families. {name: {...}}."""
        fam = load(os.path.join(self.pd, "families.json"), {})
        out = {}
        # This queue's: trials that passed both held-out reads.
        for jid, ds in self.held_pairs().items():
            if self.held_pass(ds):
                tw = glob.glob(os.path.join(self.q, "results", jid, self.home, "out", jid, "*", "trial.weights"))
                if tw and self.model_stale(open(tw[0]).read()):
                    continue
                c = self.job_census(jid)
                held = [self.job_census(d.rstrip("/").split(os.sep)[-2]) for d in ds]
                if tw and c and all(held):
                    # Current: its census and both reads ran on today's
                    # defaults. Only a current candidate may promote itself.
                    commits = [self.census_commit(os.path.dirname(tw[0]))] + [self.census_commit(d) for d in ds]
                    out["%s/%s" % (self.name, jid)] = {"weights": open(tw[0]).read(), "census": c[:2], "held": [h[:2] for h in held],
                                                       "commits": commits, "current": all(self.same_defaults(x) for x in commits), "held_dirs": ds}
        # Each converge run's: its progress lines.
        for run_dir in (self.cfg.get("families") or {}).get("converge", []):
            run_dir = os.path.join(self.tc, run_dir) if not os.path.isabs(run_dir) else run_dir
            stamp = os.path.basename(run_dir.rstrip("/"))
            try:
                lines = open(os.path.join(run_dir, "progress.txt")).read().splitlines()
            except OSError:
                continue
            census, held = {}, []
            for l in lines:
                m = re.match(r"^\S+ (gen\d+/\S+) every map\s+([-+][\d.]+) \+/- ([\d.]+)", l)
                if m:
                    census[m.group(1)] = (float(m.group(2)), float(m.group(3)))
                    held = []
                    continue
                m = re.match(r"^\S+\s+held out from \d+: every map\s+([-+][\d.]+) \+/- ([\d.]+)", l)
                if m:
                    held.append((float(m.group(1)), float(m.group(2))))
                    continue
                m = re.match(r"^\S+\s+(gen\d+/\S+): pass pass, CANDIDATE", l)
                if m and os.path.exists(os.path.join(run_dir, m.group(1) + ".weights")):
                    out["%s/%s" % (stamp, m.group(1))] = {"weights": open(os.path.join(run_dir, m.group(1) + ".weights")).read(),
                                                         "census": census.get(m.group(1)), "held": held[-2:]}
        for k, v in out.items():
            f = fam.get(k)
            v["families"] = f["verdict"] if f else "not read"
            v["held_mean"] = sum(h[0] for h in v["held"]) / len(v["held"]) if v["held"] else None
        return out

    def strongest(self):
        ev = {k: v for k, v in self.evidence().items() if v["families"] == "holds" and v["held_mean"] is not None}
        return max(ev.items(), key=lambda kv: kv[1]["held_mean"]) if ev else (None, None)

    def promote_run(self, rid, p, st):
        # ORPHANED IS AN END (13 November, 09:27). The first line to come off was back within a minute: its ten
        # promotions, marked orphaned, read here as runs not yet finished, and each was prepared and put
        # on the line again, one every seven seconds. A status this did not know was work to do.
        if st["status"] in ("prepared", "approved", "self-modified", "rejected", "orphaned"):
            return []
        if st["status"] == "new":
            # Without push permission the promotion still runs: it is
            # prepared here and self-modifies (the local line).
            can_push = self.push_check()["ok"]
            name = p.get("candidate", "@strongest")
            if name == "@strongest":
                name, ev = self.strongest()
            else:
                ev = self.evidence().get(name)
            if p.get("with"):
                # A batch: the strongest one's evidence, and the whole of the weights.
                ev = dict(ev, weights=p["weights"]) if ev else ev
            elif p.get("weights"):
                name, ev = p.get("name", "weights"), {"weights": self.text(p["weights"]), "census": None, "held": [], "families": "not read"}
            if not ev:
                self.rsave(rid, {"status": "failed", "why": "no candidate %s with evidence (families held, two held-out reads)" % name})
                return []
            if ev.get("families") == "UNDER":
                self.rsave(rid, {"status": "failed", "why": "%s falls under a family floor" % name})
                return []
            # What would change, read against the coordinator's checkout of main.
            tmp = os.path.join(self.rdir(rid), "promote.weights")
            open(tmp, "w").write(ev["weights"])
            r = run([sys.executable, "-I", os.path.join(self.tc, "scripts", "set-defaults.py"), tmp, "--check"], cwd=self.tc)
            if r.returncode != 0:
                self.rsave(rid, {"status": "failed", "candidate": name, "why": r.stderr.strip()[-200:]})
                return []
            # Against the line, not the coordinator's checkout of main: that said "no change" for a switch
            # flipped back, and "base_r 16 -> 8" for a step from 32.
            changed = self.changed_from_line(ev["weights"]) or r.stdout.strip().splitlines()
            fmt = lambda c: "%+.2f +/- %.2f" % tuple(c) if c else "?"
            msg = ("promote %s as the brain's defaults -- %s; census %s, held out %s; families %s; prepared by orrery (queue %s, run %s), "
                   "%s\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n") % (
                name, "; ".join(changed) or "no change", fmt(ev.get("census")), " and ".join(fmt(h) for h in ev.get("held", [])) or "?",
                ev.get("families"), self.name, rid,
                "Paul Accepts: orrery's auto mode, with push permission (Paul, 28 October)" if self.auto() and can_push
                else "self-modified: on orrery's local line %s until it is committed to main" % self.LINE)
            jid = "%s-promote" % rid
            branch = "promote/%s-%s" % (self.name, rid)
            b1 = base64.b64encode(ev["weights"].encode()).decode()
            b2 = base64.b64encode(msg.encode()).decode()
            # The commit comes back as a git bundle in the job's out directory and is fetched into
            # this checkout when the job is done (below), so the machine that tests it needs no
            # push permission and no local line: any CPU lane with ~/code/treadcore (every node has
            # one, from fleet-node.sh or copal-node.sh). Until 3 November this pinned the Mac, and
            # a promotion waited for nothing whenever the Mac's lane was set aside (Paul: "there
            # still is something stranded ... create an acknowledge which passes it on to the queue").
            host = p.get("host")
            # It is tested on what the fleet runs: the local line, if there is one.
            fetch_line, base, send = self.promote_base(rid)
            who = self.author()
            out = "~/%s/out/%s" % (self.home, jid)
            cmd = (
                "set -e -o pipefail; [ -f ~/.cargo/env ] && . ~/.cargo/env; export PATH=$HOME/.cargo/bin:/opt/homebrew/bin:$PATH\n"
                "T=~/code/treadcore; W=~/%s/promote/%s; B=%s; O=%s; mkdir -p $O\n"
                "cd $T && git fetch -q origin\n%s"
                "git worktree remove --force $W 2>/dev/null || true; git worktree prune; git branch -D $B 2>/dev/null || true\n"
                "git worktree add -q -b $B $W %s\n"
                "cd $W && echo %s | base64 -d > $O/promote.weights && python3 -I scripts/set-defaults.py $O/promote.weights | tee $O/changed.txt\n"
                # Its own target folder: two worktrees in one share the test
                # binary's file name, and cargo can call another's fresh (LR 117).
                "export CARGO_TARGET_DIR=$W/target\n"
                "cargo test -q -p treadcore-brain --release > $O/tests.txt 2>&1 || { tail -30 $O/tests.txt; echo 'the tests failed: not committed'; exit 1; }\n"
                "grep 'test result' $O/tests.txt\n"
                "FLOOR_GIVE=GIVE_NOW cargo test -q -p treadcore-brain --release -- --ignored every_family_holds_its_floor --nocapture > $O/families-full.txt 2>&1 || { grep -E '^family|panicked|under' $O/families-full.txt; echo 'a family fell under its floor: not committed'; exit 1; }\n"
                "grep -E '^family' $O/families-full.txt > $O/families.txt; cat $O/families.txt\n"
                # THE GAUNTLET'S FLOORS (treadcore LR 143): the batch's defaults on the rules, every file on
                # its floor, or nothing is committed. A commit without GAUNTLET_BRAINS skips it.
                "if grep -q GAUNTLET_BRAINS source/treadcore-brain/src/learn.rs; then\n"
                "  GAUNTLET=1 GAUNTLET_RUNS=100 GAUNTLET_BRAINS=scripted OUT=$O THREADS=$(nproc 2>/dev/null || sysctl -n hw.ncpu) cargo test -q -p treadcore-brain --release --lib -- --ignored learn::harness::train --nocapture > $O/gauntlet.txt 2>&1 || true\n"
                "  python3 -I -c \"import glob,re,sys; f={}; [f.__setitem__(re.search(r'^name\\\\s*=\\\\s*\\\\\\\"([^\\\\\\\"]+)', t, re.M).group(1), float(re.search(r'^floor\\\\s*=\\\\s*([\\\\d.]+)', t, re.M).group(1))) for t in (open(p).read() for p in glob.glob('scenarios/gauntlet/*.toml')) if re.search(r'^floor', t, re.M)]; u=[l.split(chr(9))[0] for l in open(sys.argv[1]).read().splitlines()[1:] if l.split(chr(9))[1]=='scripted' and float(l.split(chr(9))[4]) < f.get(l.split(chr(9))[0], 0) - GIVE_NOW]; print('gauntlet: holds' if not u else 'gauntlet under its floor: ' + '; '.join(u)); sys.exit(1 if u else 0)\" $O/gauntlet.tsv || { echo 'a gauntlet under its floor: not committed'; exit 1; }\n"
                "fi\n"
                # The floors, read together where the commit can (treadcore LR 158): a small drop passes and
                # its floor moves down in the scenario file; a collapse stops the promotion with nothing written.
                "if [ -f scripts/floors.py ]; then python3 -I scripts/floors.py --give GIVE_NOW --write $O/families.txt $O/gauntlet.tsv > $O/floors.txt 2>&1 || { cat $O/floors.txt; echo 'a floor collapsed: not committed'; exit 1; }; cat $O/floors.txt; git add scenarios/families scenarios/gauntlet; fi\n"
                # Both files set-defaults.py writes: weights.rs alone left
                # Tactics::default() behind, and main failed its tests from
                # dc3df01 until d7e8c09 (29 October).
                # The author is the coordinator's, given: a machine whose git knows no one (calber, 5
                # November: "Author identity unknown") would refuse the commit after every test passed.
                "git add source/treadcore-brain/src/weights.rs source/treadcore-brain/src/tactics.rs && echo %s | base64 -d > $O/msg.txt && git -c user.name=%s -c user.email=%s commit -q -F $O/msg.txt\n"
                "git bundle create -q $O/promote.bundle %s..$B && echo 'the commit travels back as promote.bundle'\n"
                "git rev-parse HEAD > $O/commit.txt; echo \"prepared $(cat $O/commit.txt) on $B\"\n"
            ) % (self.home, rid, branch, out, fetch_line, base, b1, b2, shlex.quote(who[0]), shlex.quote(who[1]), base)
            cmd = cmd.replace("GIVE_NOW", "%g" % self.FLOOR_GIVE)
            st = {"status": "running", "job": jid, "candidate": name, "branch": branch, "changed": changed, "can_push": can_push,
                  "evidence": {k: ev.get(k) for k in ("census", "held", "families")}}
            self.rsave(rid, st)
            job = {"id": jid, "kind": "promote", "title": "promote %s: tests and families on a branch" % name,
                   "needs": "host:" + host if host else "cpu", "cmd": cmd, "fetch": "%s/out/%s" % (self.home, jid), "timeout_s": 4 * 3600}
            if host:
                job["or"] = "cpu"
            if send:
                job["send"] = send
            return [job]
        # Running: the branch is prepared when the job is done, and its commit is fetched from the
        # bundle into this checkout, where approve pushes it from.
        if st["job"] in self.ids("done"):
            c = glob.glob(os.path.join(self.q, "results", st["job"], self.home, "out", st["job"], "commit.txt"))
            st["commit"] = open(c[0]).read().strip() if c else ""
            b = glob.glob(os.path.join(self.q, "results", st["job"], self.home, "out", st["job"], "promote.bundle"))
            if b and st["commit"]:
                # A worktree here that holds the branch refuses the fetch, -f or not: a promotion that
                # once ran on the Mac left one, and r0156's commit never came home (3 November: auto
                # promotion paused a night on it). Its work is the bundle's now, so it goes first.
                self.free_branch(st["branch"])
                r = run(["git", "-C", self.tc, "fetch", "-q", b[0], "%s:refs/heads/%s" % (st["branch"], st["branch"])])
                if r.returncode != 0:
                    run(["git", "-C", self.tc, "fetch", "-q", "-f", b[0], "%s:refs/heads/%s" % (st["branch"], st["branch"])])
                got = run(["git", "-C", self.tc, "rev-parse", "-q", "--verify", "refs/heads/%s" % st["branch"]]).stdout.strip()
                if got != st["commit"]:
                    st["status"] = "failed"
                    st["detail"] = "%s: prepared on its machine as %s, but the bundle did not fetch here (%s)" % (st["branch"], st["commit"][:7], (r.stderr or "").strip()[-160:])
                    self.rsave(rid, st)
                    self.flag("promote", st["detail"], key="promote-bundle:%s" % rid)
                    return []
            elif st["commit"] and run(["git", "-C", self.tc, "cat-file", "-e", st["commit"]]).returncode != 0:
                st["commit"] = ""
                st["status"] = "failed"
                st["detail"] = "%s: prepared on its machine, but no bundle came back to fetch the commit from" % st["branch"]
                self.rsave(rid, st)
                self.flag("promote", st["detail"], key="promote-bundle:%s" % rid)
                return []
            st["status"] = "prepared"
            st["detail"] = "%s: prepared (%s)" % (st["branch"], st["commit"][:7])
            self.rsave(rid, st)
            accept = self.auto() and self.push_check()["ok"]
            # Only what is proven goes to main: a generation is carried on the line.
            held = (st.get("evidence") or {}).get("held") or []
            proven = (len(held) >= 2 and sum(1 / h[1] ** 2 for h in held) > 0
                      and sum(h[0] / h[1] ** 2 for h in held) / math.sqrt(sum(1 / h[1] ** 2 for h in held)) >= self.HELD_Z
                      and not self.state.get("local_line"))
            try:
                if accept and proven:
                    self._approve(rid)
                elif accept:
                    self.self_modify(rid, because="a generation, carried unproven until the line reads past main")
                else:
                    self.self_modify(rid)
                st = self.rstate(rid)
            except SystemExit as e:
                # main moved under it, or the replay failed: the local line
                # takes it instead, so the values are not lost.
                why = str(e).splitlines()[0]
                try:
                    self.self_modify(rid, because="Paul Accepts failed (%s)" % why)
                    st = self.rstate(rid)
                except SystemExit as e2:
                    st["status"] = "failed"
                    st["why"] = "accepting: %s; self-modifying: %s" % (why, str(e2).splitlines()[0])
            self.tick({"kind": "promote", "run": rid, "host": "mac", "improved": True, "d": None, "se": None,
                       "vars": changed_vars(st["changed"])})
        elif st["job"] in self.ids("failed", "stopped"):
            st["status"] = "failed"
            st["why"] = self.promote_failure(st["job"])
        self.rsave(rid, st)
        return []

    def author(self):
        """The name and address the coordinator's treadcore checkout commits as: a promotion is
        committed in the same name on whichever machine runs it."""
        name = run(["git", "-C", self.tc, "config", "user.name"]).stdout.strip() or "orrery"
        mail = run(["git", "-C", self.tc, "config", "user.email"]).stdout.strip() or "orrery@localhost"
        return name, mail

    def promote_base(self, rid):
        """What a promotion job builds on, on whichever machine takes it: (the shell line that brings
        the local line there, the commit to branch from, the files sent with the job).

        THE LINE IS A BRANCH ONLY HERE. Every build fetches the line's commits from its bundle, but
        under no name, so on any other machine `orrery/accepted` names nothing: on 5 November, 00:15,
        the night's one promotion (r0182, grove/w10040, held out +0.69) went to macmini and died in a
        second on `fatal: invalid reference: orrery/accepted`. The job now takes the bundle with it
        and names the line by its commit, which is the same on every machine."""
        line = self.state.get("local_line")
        if not line:
            return "", "origin/main", []
        dst = "~/%s/promote/%s.bundle" % (self.home, rid)
        return ("git fetch -q %s %s\n" % (dst, self.LINE), line["commit"],
                [{"src": os.path.join(self.pd, "accepted.bundle"), "dst": dst}])

    def retry_after_main(self, autos, tried):
        """A candidate whose auto promotion failed at the brain's tests is
        tried once more when main has moved since: the test may have been
        the fault (29 October: grove/w1266 failed a castle test that pinned
        post_spacing without saying so, treadcore 9032026). Once a main
        commit, so a candidate that fails on its own numbers is not tried
        over and over."""
        # What a machine builds moved, not a report: a test cannot have been mended by a page.
        r = run(["git", "-C", self.tc, "log", "-1", "--format=%ct %H", self.build_tip(run(["git", "-C", self.tc, "rev-parse", "origin/main"]).stdout.strip())])
        try:
            when, sha = r.stdout.split()
            when = int(when)
        except ValueError:
            return
        done = self.state.setdefault("retried", {})
        faults = self.state.setdefault("job_faults", {})
        for a in autos:
            st_ = self.rstate(a["id"])
            # A promotion that failed at its first step (the writer) saved no candidate: its request says.
            name = st_.get("candidate") or (a.get("params") or {}).get("candidate")
            # NOT THE CANDIDATE'S FAULT: its promotion died before its numbers were judged (r0182, a git
            # error on macmini, 5 November). It is tried again at once, once: a fault that repeats is
            # the machine's or the line's, and two in a row pause auto promotion as any two failures do.
            if (st_.get("status") == "failed" and name in tried and st_.get("job") in self.ids("failed")
                    and not any(self.rstate(b["id"]).get("candidate") == name for b in autos[autos.index(a) + 1:])):
                why = self.promote_failure(st_["job"])
                if why.startswith(self.JOB_FAULT) and name not in faults:
                    if why != st_.get("why"):
                        st_["why"] = why
                        self.rsave(a["id"], st_)
                    tried.remove(name)
                    faults[name] = a["id"]
                    self.flag("auto", "%s is tried again: its promotion %s failed before it was judged (%s)" % (name, a["id"], why),
                              key="fault-retry:%s:%s" % (name, a["id"]), progress=True)
                    continue
            # Its tests failed, or the writer could not write it (set-defaults.py: 5 November, w10839's
            # `wing_leash`, whose default was a constant's name): main moving may have mended either.
            why = st_.get("why", "")
            if st_.get("status") != "failed" or name not in tried or done.get(name) == sha or not (
                    "tests failed" in why or "nothing written" in why):
                continue
            # Only its newest try counts.
            if any(self.rstate(b["id"]).get("candidate") == name for b in autos[autos.index(a) + 1:]):
                continue
            try:
                # The writer fails before a job is asked: then the run's own record says when.
                failed = os.path.getmtime(os.path.join(self.q, "logs", st_["job"] + ".log")) if st_.get("job") else \
                    os.path.getmtime(os.path.join(self.rdir(a["id"]), "state.json"))
            except (OSError, KeyError):
                continue
            if when > failed:
                tried.remove(name)
                done[name] = sha
                self.flag("auto", "%s is tried again: %s (%s), and main has moved since (%s)" % (
                    name, "its tests failed" if "tests failed" in why else "it could not be written", a["id"], sha[:7]),
                          key="retry:%s:%s" % (name, sha[:7]), progress=True)

    def promote_worktrees(self):
        """(path, branch) of every worktree of this checkout that a promotion job made here."""
        out, path = [], None
        for line in run(["git", "-C", self.tc, "worktree", "list", "--porcelain"]).stdout.splitlines():
            if line.startswith("worktree "):
                path = line[9:]
            elif line.startswith("branch refs/heads/") and path and "/%s/promote/" % self.home in path:
                out.append((path, line[18:]))
        return out

    def free_branch(self, branch):
        """No worktree here holds this branch: a promotion's own, which its commit has outlived."""
        for path, b in self.promote_worktrees():
            if b == branch:
                run(["git", "-C", self.tc, "worktree", "remove", "--force", path])
        run(["git", "-C", self.tc, "worktree", "prune"])

    def clear_promote_worktrees(self):
        """THE MAC'S PROMOTION WORKTREES GO WHEN THEIR RUNS DO. A promotion builds its branch in
        ~/fleet/q-NAME/promote/RID on whatever machine takes it, and one that ran here left its
        worktree behind: 39 by 4 November, 3.3 GB, one of them holding r0156's branch so its commit
        could not come home. The branch stays (removing a worktree keeps it); a run still in flight
        keeps its worktree."""
        live = {r["id"] for r in self.runs() if r["kind"] == "promote" and self.rstate(r["id"]).get("status") in ("new", "running")}
        for path, b in self.promote_worktrees():
            if os.path.basename(path) not in live:
                run(["git", "-C", self.tc, "worktree", "remove", "--force", path])
        run(["git", "-C", self.tc, "worktree", "prune"])

    def same_failure(self, jobs):
        """True when two failed promotions failed alike, on today's main:
        their tests share a failure (or neither failed at the tests), and
        main has no commit since the later."""
        logs = []
        for jid in jobs:
            try:
                f = os.path.join(self.q, "logs", jid + ".log")
                logs.append((open(f).read(), os.path.getmtime(f)))
            except (OSError, TypeError):
                return True
        tests = [self.failed_tests(l) for l, _ in logs]
        if all(tests) and not (tests[0] & tests[1]):
            return False
        r = run(["git", "-C", self.tc, "log", "-1", "--format=%ct", "origin/main"])
        try:
            return int(r.stdout.strip()) < max(m for _, m in logs)
        except ValueError:
            return True

    @staticmethod
    def failed_tests(log):
        """The tests cargo names under its last "failures:", a set."""
        return {n.strip() for b in re.findall(r"^failures:\n((?:    \S+\n)+)", log, re.M) for n in b.splitlines()}

    # A promotion that failed before its candidate was judged: the machine, git, a send.
    JOB_FAULT = "the promotion job failed"

    def promote_failure(self, jid):
        """Which step of a promotion failed, read from its log: the brain's
        tests (and the first that failed), a family under its floor, or the
        job itself."""
        try:
            log = open(os.path.join(self.q, "logs", jid + ".log")).read()
        except OSError:
            log = ""
        # THE VERDICT IS A LINE OF ITS OWN. The log begins with the job's command, which holds every
        # verdict's words: r0182 died on a git error and was read as "the brain's tests failed".
        if re.search(r"^the tests failed: not committed$", log, re.M):
            names = sorted(self.failed_tests(log))
            return "the brain's tests failed%s: see logs/%s.log" % (" (%s)" % ", ".join(names) if names else "", jid)
        if re.search(r"^a family fell under its floor: not committed$", log, re.M):
            m = re.search(r"^family (\S+).*under", log, re.M)
            return "a family fell under its floor%s: see logs/%s.log" % (" (%s)" % m.group(1) if m else "", jid)
        if re.search(r"^a gauntlet under its floor: not committed$", log, re.M):
            m = re.search(r"^gauntlet under its floor: (.*)$", log, re.M)
            return "a gauntlet fell under its floor%s: see logs/%s.log" % (" (%s)" % m.group(1) if m else "", jid)
        if re.search(r"^a floor collapsed: not committed$", log, re.M):
            m = re.search(r"^(?:family|gauntlet) (\S+): .* is a collapse", log, re.M)
            return "a floor collapsed%s: see logs/%s.log" % (" (%s)" % m.group(1) if m else "", jid)
        m = re.search(r"^((?:fatal|error)(?:\[\w+\])?: .*)$", log, re.M)
        return "%s%s: see logs/%s.log" % (self.JOB_FAULT, " (%s)" % m.group(1)[:160] if m else "", jid)

    def approve(self, rid):
        """Paul's word, by hand: a prepared or self-modified promotion is
        pushed to main, so the fleet trains on it at its next top-up."""
        st = self._approve(rid)
        self.keep()
        print("%s approved: main is %s; the fleet builds it at its next top-up" % (rid, st["commit"][:7]))

    def _approve(self, rid):
        st = self.rstate(rid)
        if st.get("status") == "self-modified":
            # By hand: the local line goes to main, this one with it.
            self.resolve()
            return self.rstate(rid)
        if st.get("status") != "prepared" or not st.get("commit"):
            raise SystemExit("%s is not a prepared promotion (%s)" % (rid, st.get("status")))
        remote, branch = self.push_target()
        r = run(["git", "-C", self.tc, "push", remote, "%s:refs/heads/%s" % (st["commit"], branch)])
        if r.returncode != 0:
            # main moved while it was tested. If nothing under source/ moved
            # (records, reports, docs), what was tested is what main would
            # build: the promotion commit is replayed on main and pushed.
            # Otherwise it must be tested again.
            run(["git", "-C", self.tc, "fetch", "-q", remote])
            tip = "%s/%s" % (remote, branch)
            base = run(["git", "-C", self.tc, "merge-base", st["commit"], tip]).stdout.strip()
            moved = run(["git", "-C", self.tc, "diff", "--quiet", base, tip, "--", "source/"]).returncode != 0
            if not base or moved:
                raise SystemExit("main's brain source has moved since it was prepared: ask for the promotion again\n" + r.stderr[-300:])
            w = os.path.join(self.rdir(rid), "replay")
            run(["git", "-C", self.tc, "worktree", "remove", "--force", w])
            run(["git", "-C", self.tc, "worktree", "prune"])
            r = run(["git", "-C", self.tc, "worktree", "add", "-q", "--detach", w, tip])
            r = r if r.returncode else run(["git", "-C", w, "cherry-pick", "--allow-empty", st["commit"]])
            new = run(["git", "-C", w, "rev-parse", "HEAD"]).stdout.strip() if r.returncode == 0 else ""
            r = r if r.returncode else run(["git", "-C", self.tc, "push", remote, "%s:refs/heads/%s" % (new, branch)])
            run(["git", "-C", self.tc, "worktree", "remove", "--force", w])
            if r.returncode != 0:
                raise SystemExit("main moved, and replaying the promotion on it failed\n" + r.stderr[-300:])
            st["tested"] = st["commit"]
            st["commit"] = new
        run(["git", "-C", self.tc, "fetch", "-q", remote])
        self.push_check()
        st["status"] = "approved"
        st["accepted"] = "Paul Accepts (auto mode)" if self.auto() else "Paul approved"
        st["detail"] = "%s: on main at %s" % (st["accepted"], st["commit"][:7])
        st["approved"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        # A micro version (Paul, 28 October: "essentially creating micro
        # versions of this git submission. its part of the program"): an
        # annotated tag brain-RID on the promotion's commit, pushed with it.
        # Never v*: a v tag starts the packages workflow, a release only Paul
        # asks for.
        tag = self.micro_tag(rid, st)
        if tag:
            st["tag"] = tag
            st["detail"] += ", tagged %s" % tag
        self.rsave(rid, st)
        # Every candidate's families again, on the new defaults; and the
        # commit is read anew, so this pass's prep jobs build it everywhere.
        self.state["families_queued"] = []
        self._sha = None
        self.flag("promote", "promotion %s: %s: %s is main at %s; every machine builds it next" % (
            rid, st["accepted"], st.get("candidate"), st["commit"][:7]), key="approved:%s" % rid, progress=True)
        return st

    def self_modify(self, rid, because=None):
        """A prepared promotion onto the local line (LINE): main and the
        promotions not on it. The fleet builds it; a flag asks Paul to
        commit the weights and nets."""
        st = self.rstate(rid)
        remote, branch = self.push_target()
        run(["git", "-C", self.tc, "fetch", "-q", remote], timeout=120)
        tip = "%s/%s" % (remote, branch)
        line = self.state.get("local_line")
        base = self.LINE if line else tip
        w = os.path.join(self.rdir(rid), "line")
        run(["git", "-C", self.tc, "worktree", "remove", "--force", w])
        run(["git", "-C", self.tc, "worktree", "prune"])
        r = run(["git", "-C", self.tc, "worktree", "add", "-q", "--detach", w, base])
        # The prepared commit was made on what the fleet ran then; on the
        # line as it is now, it is replayed (cherry-picked) when needed.
        same = run(["git", "-C", self.tc, "merge-base", "--is-ancestor", base, st["commit"]]).returncode == 0
        r = r if r.returncode else run(["git", "-C", w, "merge", "-q", "--ff-only", st["commit"]] if same
                                        else ["git", "-C", w, "cherry-pick", "--allow-empty", st["commit"]])
        new = run(["git", "-C", w, "rev-parse", "HEAD"]).stdout.strip() if r.returncode == 0 else ""
        run(["git", "-C", self.tc, "worktree", "remove", "--force", w])
        if not new:
            raise SystemExit("the promotion does not apply on the local line: " + (r.stderr or r.stdout)[-300:])
        run(["git", "-C", self.tc, "branch", "-f", self.LINE, new])
        line = line or {"promotions": []}
        line["promotions"].append(rid)
        line["commit"] = new
        line["since"] = line.get("since") or time.strftime("%Y-%m-%dT%H:%M:%S")
        self.state["local_line"] = line
        self.bundle()
        st["status"] = "self-modified"
        st["tested"] = st["commit"]
        st["commit"] = new
        st["approved"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        why = because or ("auto mode is off" if not self.auto() else "no push permission (%s)" % self.push_check()["detail"])
        st["detail"] = "self-modified onto %s at %s (%s): the fleet builds it; main does not have it yet" % (self.LINE, new[:7], why)
        self.rsave(rid, st)
        self.state["families_queued"] = []
        self._sha = None
        self.resolve_flag()
        return st

    def local_line(self, main_sha, by="committed to main by Paul"):
        """The local line's head while main lacks it, else None. When main
        holds every promotion on it, the line ends; when main moved on
        without it, the line is replayed on main."""
        line = self.state.get("local_line")
        if not line:
            return None
        head = line.get("commit", "")
        if not self.writer:
            # As kept: on main, nothing to build of it; else its head, replayed or not.
            return None if run(["git", "-C", self.tc, "merge-base", "--is-ancestor", head, main_sha]).returncode == 0 else head
        if run(["git", "-C", self.tc, "merge-base", "--is-ancestor", head, main_sha]).returncode == 0:
            # Resolved: Paul committed the weights (or pushed the line).
            for rid in line["promotions"]:
                st = self.rstate(rid)
                if st.get("status") == "self-modified":
                    st["status"] = "approved"
                    st["accepted"] = by
                    st["self_modified_at"] = st.get("commit", "")
                    st["commit"] = head
                    st["detail"] = "%s: on main at %s (self-modified at %s before)" % (by, head[:7], st["self_modified_at"][:7])
                    self.rsave(rid, st)
            self.state.pop("local_line", None)
            self.flag("resolve", "the local line is on main (%s): resolved" % main_sha[:7], key="resolved:%s" % head[:12], progress=True)
            return None
        if run(["git", "-C", self.tc, "merge-base", "--is-ancestor", main_sha, head]).returncode == 0:
            self.heal_line(head)
            return head
        # main moved on: the line's own commits again, on top of it.
        own = run(["git", "-C", self.tc, "rev-list", "--reverse", "%s..%s" % (main_sha, head)]).stdout.split()
        new = self.replay(own, main_sha)
        if not new:
            self.flag("resolve", "main moved and the local line %s does not replay on it: please resolve this by committing the weights and nets by hand"
                      % head[:7], key="replay:%s:%s" % (head[:12], main_sha[:12]))
            return head
        run(["git", "-C", self.tc, "branch", "-f", self.LINE, new])
        line["commit"] = new
        self.state["local_line"] = line
        self.bundle()
        return new

    def heal_line(self, head):
        """THE STATE IS THE LINE'S TRUTH, its branch and bundle follow it (4 November). A branch or a
        bundle that names another commit than the state's head is set back to it, and said."""
        f = os.path.join(self.pd, "accepted.bundle")
        branch = run(["git", "-C", self.tc, "rev-parse", "--verify", "-q", self.LINE]).stdout.strip()
        heads = run(["git", "-C", self.tc, "bundle", "list-heads", f]).stdout.split() if os.path.exists(f) else []
        if branch == head and head in heads:
            return
        run(["git", "-C", self.tc, "branch", "-f", self.LINE, head])
        self.bundle()
        self.flag("line", "the line's branch was %s and its bundle held %s, while the line is %s: both set to %s" % (
            branch[:7] or "none", ", ".join(h[:7] for h in heads if len(h) == 40) or "nothing", head[:7], head[:7]),
            key="healed:%s:%s" % (head[:12], branch[:12]), progress=True)

    def bundle(self):
        """The local line's own commits as a git bundle (plan/accepted.bundle),
        sent with each build so every machine has them without GitHub."""
        remote, branch = self.push_target()
        f = os.path.join(self.pd, "accepted.bundle")
        r = run(["git", "-C", self.tc, "bundle", "create", f + ".part", self.LINE, "^%s/%s" % (remote, branch)])
        if r.returncode == 0:
            os.replace(f + ".part", f)

    def pending_nets(self):
        """Nets not committed: files in the checkout's nets/ git does not
        track, and the net rounds' best when it is a new one."""
        out = []
        r = run(["git", "-C", self.tc, "ls-files", "--others", "--exclude-standard", "nets"])
        out += [l.strip() for l in r.stdout.splitlines() if l.strip().endswith(".bin")]
        best = load(os.path.join(self.pd, "best.json"), {}) or {}
        if best.get("round"):
            out.append("plan/best.bin (%s)" % best.get("name"))
        return out

    def resolve_flag(self):
        """Paul, 28 October: "have a flag for please resovle this by
        commiting the weights and nets". Raised while the local line lacks
        main, naming what to commit."""
        line = self.state.get("local_line")
        # In auto mode the line is how generations are carried, and line_proof takes it to main.
        if not line or (self.auto() and self.push_check()["ok"]):
            return
        nets = self.pending_nets()
        remote, branch = self.push_target()
        self.flag("resolve", "please resolve this by committing the weights and nets: %d promotion(s) (%s) are on %s at %s, not on %s/%s%s. "
                  "From a machine that can push: git push %s %s:%s, or fleet-queue.py %s resolve" % (
                      len(line["promotions"]), ", ".join(line["promotions"]), self.LINE, line["commit"][:7], remote, branch,
                      "; nets not committed: " + ", ".join(nets) if nets else "", remote, self.LINE, branch, self.q),
                  key="resolve:%s" % line["commit"][:12])

    def resolve(self, upto=None, carried=None):
        """The local line to main, when this coordinator can push; or only as far as `upto`, the
        commit a proof read, and the first `carried` generations with it."""
        line = self.state.get("local_line")
        if not line:
            print("no local line: main has every promotion")
            return
        ps = self.push_check()
        if not ps["ok"]:
            raise SystemExit("no push permission (%s): push %s from a machine that can" % (ps["detail"], self.LINE))
        remote, branch = self.push_target()
        main = run(["git", "-C", self.tc, "rev-parse", "%s/%s" % (remote, branch)]).stdout.strip()
        head = self.local_line(self.build_tip(main))
        if not head:
            return
        if upto and upto != head:
            landed = self.land(upto)
            if landed != upto:
                # Replayed on main's documents: what stood above it goes on top, under new hashes.
                rest = run(["git", "-C", self.tc, "rev-list", "--reverse", "%s..%s" % (upto, head)]).stdout.split()
                top = self.replay(rest, landed)
                if not top:
                    self.flag("resolve", "%s is on main at %s, and what stood above it does not replay: please resolve this by hand" % (upto[:7], landed[:7]),
                              key="replay:%s" % landed[:12])
                    return
                run(["git", "-C", self.tc, "branch", "-f", self.LINE, top])
                line["commit"] = top
                self.bundle()
            upto = landed
            n = len(line["promotions"]) if carried is None else min(carried, len(line["promotions"]))
            for rid in line["promotions"][:n]:
                st = self.rstate(rid)
                if st.get("status") == "self-modified":
                    st.update({"status": "approved", "accepted": "the line's proof", "self_modified_at": st.get("commit", ""), "commit": upto,
                               "detail": "on main at %s, by the line's proof" % upto[:7]})
                    self.rsave(rid, st)
            line["promotions"] = line["promotions"][n:]
            self._sha = None
            print("the line is main as far as %s; %d generation(s) still carried" % (upto[:7], len(line["promotions"])))
            return
        landed = self.land(head)
        if landed != head:
            run(["git", "-C", self.tc, "branch", "-f", self.LINE, landed])
            line["commit"] = head = landed
        self.local_line(head, by="Paul Accepts (auto mode)" if self.auto() else "Paul approved")
        for rid in line["promotions"]:
            st = self.rstate(rid)
            tag = self.micro_tag(rid, st)
            if tag:
                st["tag"] = tag
                st["detail"] += ", tagged %s" % tag
                self.rsave(rid, st)
        self._sha = None
        print("the local line is main at %s" % head[:7])

    def micro_tag(self, rid, st):
        tag = "brain-%s" % rid
        remote, _ = self.push_target()
        changed = [c.strip() for c in st.get("changed", []) if not c.strip().startswith("Tactics::default()")]
        ev = st.get("evidence", {})
        held = " and ".join("%+.2f" % h[0] for h in ev.get("held", []))
        msg = "%s: %s as the brain's defaults\n\n%s\n\nheld out %s; families %s; queue %s, run %s, %s" % (
            tag, st.get("candidate"), "\n".join(changed), held, ev.get("families", "?"), self.name, rid, time.strftime("%Y-%m-%dT%H:%M:%S"))
        if run(["git", "-C", self.tc, "rev-parse", "-q", "--verify", "refs/tags/" + tag]).returncode != 0:
            if run(["git", "-C", self.tc, "tag", "-a", tag, "-m", msg, st["commit"]]).returncode != 0:
                return ""
        r = run(["git", "-C", self.tc, "push", "-q", remote, "refs/tags/%s" % tag])
        return tag if r.returncode == 0 else ""

    def runs_status(self):
        out = []
        for r in self.runs():
            st = self.rstate(r["id"])
            what = {"census": lambda: "%d censuses" % len(st.get("items", [])),
                    "spsa": lambda: "step %s" % st.get("k"), "tune": lambda: "generation %s, fitness %s" % (st.get("g"), st.get("fit")),
                    "record": lambda: "next seed %s of %s" % (st.get("next"), st.get("end"))}
            k = r["kind"] if r["kind"] in what else "census" if r["kind"] in self.CENSUS_KINDS else None
            detail = st.get("detail") or (what[k]() if k and st.get("status") != "new" else "")
            if r["kind"] == "promote" and st.get("candidate") and st.get("status") == "running":
                detail = "%s: tests and families on %s" % (st["candidate"], st.get("branch"))
            out.append({"id": r["id"], "kind": r["kind"], "status": st.get("status"), "why": st.get("why", ""),
                        "detail": detail, "params": r.get("params", {}), "by": r.get("by", ""),
                        "candidate": st.get("candidate", ""), "hosts": st.get("hosts", {})})
        return out

    # ---- the ticker: every finished census, each coefficient it moved ----------------
    def tick(self, e):
        e.setdefault("t", time.strftime("%Y-%m-%dT%H:%M:%S"))
        with open(os.path.join(self.pd, "ticker.jsonl"), "a") as f:
            f.write(json.dumps(e) + "\n")

    def ticker_scan(self):
        """A ticker line for each weights census not yet ticked: each variable
        it moved, the value, the offset from the default, the difference and
        which machine read it; "improved" past two errors with no map below."""
        seen = set(self.state.setdefault("ticked", []))
        dflt = parse_weights(open(self.defaults()).read()) if self.defaults() else {}
        for d in self.census_dirs():
            jid = d.rstrip("/").split(os.sep)[-2]
            if jid in seen or not jid[:1] in ("w", "h"):
                continue
            c = self.job_census(jid)
            if not c:
                continue
            try:
                vars_ = parse_weights(open(os.path.join(d, "trial.weights")).read())
            except OSError:
                vars_ = {}
            self.tick({"kind": "weights", "job": jid, "d": c[0], "se": c[1], "host": c[3], "improved": bool(self.passes(d)),
                       "vars": {k: {"value": v, "offset": round(v - dflt[k], 4) if k in dflt else None} for k, v in vars_.items()}})
            self.state["ticked"].append(jid)

    # ---- the keeper's calls ---------------------------------------------------------------
    def candidate_states(self):
        """plan/candidates.json: each of this queue's candidates, current (its
        census and both reads on today's defaults, so it may promote itself)
        or on older defaults, with the commit it was read at. The Candidates
        page marks each line with it."""
        out = {}
        for k, v in self.evidence().items():
            if k.startswith(self.name + "/"):
                out[k.split("/", 1)[1]] = {"current": bool(v.get("current")), "commit": (v.get("commits") or [None])[0]}
        save(os.path.join(self.pd, "candidates.json"), out)

    def raise_found(self):
        """Flags for what the fleet found: a trial past both held-out reads,
        and a candidate under a family's floor."""
        keys = self.flag_keys()
        for jid, ds in self.held_pairs().items():
            # Raised already, and as news: flag() would do nothing, so nothing is read for it. Every
            # trial that ever passed was read again each pass, 14 of its seconds (8 November).
            f = keys.get("candidate:%s" % jid)
            if f and (load(f, {}) or {}).get("progress"):
                continue
            if self.held_pass(ds):
                c = self.job_census(jid)
                held = [self.job_census(d.rstrip("/").split(os.sep)[-2]) for d in ds]
                tw = glob.glob(os.path.join(self.q, "results", jid, self.home, "out", jid, "*", "trial.weights"))
                what = short_moved(open(tw[0]).read()) if tw else jid
                self.flag("candidate", "%s passed both held-out reads (%s): %s" % (jid, ", ".join("%+.2f" % h[0] for h in held if h), what), key="candidate:%s" % jid, progress=True)
        fam = load(os.path.join(self.pd, "families.json"), {}) or {}
        for name, v in fam.items():
            if v.get("verdict") == "UNDER":
                # REFUSED, AND RIGHTLY: IT IS NOT A PERSON'S TO ACKNOWLEDGE (Paul, 13 November: "explain that they
                # are correctly rejected because of their performance, perhaps we need a way to filter"). A
                # candidate under a family's floor has been refused by the rule that exists to refuse it, and
                # nothing waits on anyone: it is said once, with the family and the count, as progress.
                low = ["%s held %s of %s (floor %s)" % (x["family"].replace("-", " "), x.get("held"), x.get("runs"), x.get("floor"))
                       for x in v.get("families", []) if x.get("verdict") == "UNDER"]
                self.flag("families", "%s is refused, as it should be: %s" % (name, "; ".join(low) or "a family under its floor"), key="under:%s" % name, progress=True)
            elif v.get("verdict") == "ERROR":
                self.flag("families", "%s: its families could not run; read again on the next commit" % name, key="error:%s:%s" % (name, self.short()))

    # ---- crucible: the second job, on the GPU lanes ----------------------------------------
    # Paul, 28 October: "i want to see a button to add more gpu CUDA to the
    # mix, add crucible." Each GPU machine given a crucible lane (machines.py
    # cuda-lanes) is an island: its own population, trained a segment at a
    # time (plan.json "crucible": gens, pop, eps), its state kept on the
    # machine between segments. Each segment sends back its champion and its
    # generations, and takes the other islands' newest champions into its
    # hall of fame. The source is sent with every segment and built when it
    # changed, so the islands run what this Mac has.
    #
    # The ladder (Paul, 28 October: "islands' own past champions ...
    # battling known milestones in the past is a good idea"; "when they find
    # good values at the same time, how do we keep consistent generations
    # with keeping data"). Every segment's champion is kept
    # (crucible/champions/, a line in crucible/lineage.tsv). A champion
    # becomes the fleet's next milestone, M(n+1), only when its exam was
    # against M(n), the newest one, and it beat M(n) by more than two
    # standard errors (wins less losses), without losing to the ladder on
    # balance. When two islands qualify in the same pass, the larger margin
    # (in standard errors) becomes M(n+1); the other is kept, and meets
    # M(n+1) in its next segment. So the milestones are one line of
    # generations, each beating the one before, whichever card found it, and
    # nothing a card found is lost. The ladder and the imports are slot
    # files the keeper reads when it dispatches a segment, so a segment
    # queued six ahead still meets the newest milestones.
    LADDER_SLOTS = 8

    def crucible_dir(self, *a, home=None):
        return os.path.join(self.q, home or self.crucible_home(), *a)

    def crucible_home(self):
        """Hybrid islands apart from plain: their nets differ in size, so neither's
        state, ladder or champions load in the other, and the plain ones stay as they were.
        World islands (Paul, 3 November: "the rules of this world, can we apply them to the
        simulation expand the matrix dimensions. to the crucible") apart again: the game's rules
        in the arena and twenty more senses, so crucible-world and crucible-world-hybrid."""
        c = self.cfg.get("crucible") or {}
        # The trees (6 November): a forest arena is a home of its own again, begun from the world's.
        return ("crucible" + ("-world" if c.get("world") else "") + ("-hybrid" if c.get("hybrid") else "")
                + ("-forest" if c.get("world") and c.get("forest") else "")
                # The maze (6 November): the route sense, the arcs and the memory; 64 inputs, so a home apart.
                + ("-nav" if c.get("world") and c.get("forest") and c.get("nav") else ""))

    def crucible_parent(self, home):
        """The home a world home's islands begin from: the same kind without the world. Crucible
        widens a loaded net into the bigger layout with zeros where it had nothing, so the
        population carries everything it learned and meets the world's senses from nothing."""
        if home.endswith("-nav"):
            return home[:-len("-nav")]
        if self.gpu_home(home):
            return home[:-len("-forest")]
        return home.replace("-world", "") if "-world" in home else None

    def ladder_state(self, home=None):
        """A home's ladder in the planner's state. Plain and hybrid share the old key, as they always
        have; a world home has its own, so a milestone is never a file of another home."""
        home = home or self.crucible_home()
        key = "crucible_ladder" if home in ("crucible", "crucible-hybrid") else "crucible_ladder:" + home
        lad = self.state.get(key)
        if lad is None:
            lad = self.state[key] = {"milestones": [], "began": time.strftime("%Y-%m-%dT%H:%M:%S")}
            parent = self.crucible_parent(home)
            # A new world home begins with its parent's milestones as its first rungs, copied in
            # (widened by crucible when a segment loads them): the world islands meet the best the
            # old arena made, and a world champion must beat the newest of them to be the next.
            if parent:
                for m in self.ladder_state(parent).get("milestones", []):
                    src = self.crucible_dir("milestones", m["id"] + ".bin", home=parent)
                    if os.path.exists(src):
                        os.makedirs(self.crucible_dir("milestones", home=home), exist_ok=True)
                        shutil.copyfile(src, self.crucible_dir("milestones", m["id"] + ".bin", home=home))
                        lad["milestones"].append(dict(m, carried=parent))
        return lad

    # THE GAME'S VERDICT COMES BACK TO THE CARDS (Paul, 13 November: "fix the milestone process to be more
    # adaptive and cyclical ... reincorporate the adjustments found back into the loop"). The card elected
    # and the game credited, and there it ended: boburner's island made fourteen milestones that the game
    # read at -4.7 to -8.75 a seat under the shipped one, each stood as the newest rung every island's
    # next champion was examined against, and each was sent to the other two islands as a migrant. Now a
    # milestone the game refuses (read under the shipped Gladiator by two errors) is marked so, and three
    # things follow. It is no rung: the ladder the segments are sent leaves it out, and the newest
    # standing milestone is the one to beat. Its island's champions are no migrants while its last
    # GAME_REFUSED reads were all refused. And the net the game ships goes to every island as a
    # migrant each segment, so what the game credited is what the cards grow from.
    GAME_REFUSED = 3

    @staticmethod
    def standing(ms):
        """The milestones the game has not refused, oldest first."""
        return [m for m in ms if not (m.get("game") or {}).get("refused")]

    def ladder_top(self, lad):
        st = self.standing(lad.get("milestones") or [])
        return st[-1]["id"] if st else None

    def game_says(self, cur, home):
        """A bridge read, written on its milestone: what the game made of it."""
        lad = self.ladder_state(home)
        for m in lad.get("milestones", []):
            if m["id"] == cur.get("label") and cur.get("diff") is not None:
                refused = cur["diff"] < -2 * cur["se"]
                was = (m.get("game") or {}).get("refused")
                m["game"] = {"diff": cur["diff"], "se": cur["se"], "refused": refused, "credited": bool(cur.get("holds")), "read": cur.get("read")}
                if refused and not was:
                    self.flag("crucible", "%s is refused by the game (%+.2f +/- %.2f a seat under the shipped Gladiator): it is no rung of the ladder, and the newest standing is %s" % (
                        m["id"], cur["diff"], cur["se"], self.ladder_top(lad)), key="game-refused:%s" % m["id"], progress=True)
                return refused != was
        return False

    def island_refused(self, island, home):
        """True while an island's last GAME_REFUSED milestones the game read were all refused."""
        read = [m for m in self.ladder_state(home).get("milestones", []) if m.get("island") == island and m.get("game")]
        return len(read) >= self.GAME_REFUSED and all(m["game"].get("refused") for m in read[-self.GAME_REFUSED:])

    def ladder_rungs(self, ms):
        """At most LADDER_SLOTS milestones, oldest first: the newest half,
        and the older ones spread evenly. Only those the game has not refused."""
        ms = self.standing(ms)
        n = self.LADDER_SLOTS
        if len(ms) <= n:
            return list(ms)
        new = ms[-(n // 2):]
        old = ms[:-(n // 2)]
        k = n - len(new)
        return [old[round(i * (len(old) - 1) / max(1, k - 1))] for i in range(k)] + new

    def ladder_write(self, home=None):
        """The slot files and ladder.txt (slot, milestone) the segments are sent."""
        home = home or self.crucible_home()
        lad = self.ladder_state(home)
        d = self.crucible_dir("ladder", home=home)
        os.makedirs(d, exist_ok=True)
        rungs = self.ladder_rungs(lad["milestones"])
        lines = []
        for i in range(self.LADDER_SLOTS):
            dst = os.path.join(d, "slot-%d.bin" % i)
            if i < len(rungs):
                shutil.copyfile(self.crucible_dir("milestones", rungs[i]["id"] + ".bin", home=home), dst + ".part")
                lines.append("slot-%d.bin\t%s" % (i, rungs[i]["id"]))
            else:
                open(dst + ".part", "wb").close()
            os.replace(dst + ".part", dst)
        with open(os.path.join(d, "ladder.txt.part"), "w") as f:
            f.write("".join(l + "\n" for l in lines))
        os.replace(os.path.join(d, "ladder.txt.part"), os.path.join(d, "ladder.txt"))

    def crucible_exam(self, name, jid, home=None):
        """A finished segment's champion kept, its exam read: a row for the lineage, in the home
        the segment ran in (a segment queued before the home changed belongs to the old one)."""
        out = os.path.join(self.q, "results", jid, self.home, "out", jid)
        champ = os.path.join(out, "champ.bin")
        if not os.path.exists(champ):
            return None
        os.makedirs(self.crucible_dir("champions", home=home), exist_ok=True)
        os.makedirs(self.crucible_dir("latest", home=home), exist_ok=True)
        shutil.copyfile(champ, self.crucible_dir("champions", jid + ".bin", home=home))
        shutil.copyfile(champ, self.crucible_dir("latest", name + ".bin.part", home=home))
        os.replace(self.crucible_dir("latest", name + ".bin.part", home=home), self.crucible_dir("latest", name + ".bin", home=home))
        gen, last_yard = 0, None
        try:
            rows = open(os.path.join(out, "gens.tsv")).read().splitlines()[1:]
            gen = int(rows[-1].split("\t")[0]) + 1 if rows else 0
            ys = [float(r.split("\t")[7]) for r in rows if len(r.split("\t")) > 9 and float(r.split("\t")[7]) >= 0]
            last_yard = ys[-1] if ys else None
        except (OSError, ValueError):
            pass
        exam = []
        try:
            for line in open(os.path.join(out, "exam.tsv")).read().splitlines()[1:]:
                o, w, d, l, n = line.split("\t")
                # THE EXAM NAMES A RUNG BY ITS FILE, M0001-...-g200.bin; THE LADDER BY ITS ID, without
                # the .bin. Compared as they came, no champion was ever examined against "the newest"
                # and the ladder stayed at its first milestone in both homes, 28 October to 3 November.
                o = o[:-4] if o.endswith(".bin") else o
                exam.append((o, float(w), float(d), float(l), int(n)))
        except (OSError, ValueError):
            pass
        # The newest milestone's own read of the yardstick on the same seeds: not a rung.
        yref = [e for e in exam if e[0].startswith("yardstick@")]
        exam = [e for e in exam if not e[0].startswith("yardstick@")]
        row = {"job": jid, "island": name, "gen": gen, "yard": None, "against": None, "w": None, "d": None, "l": None,
               "margin_se": None, "ladder_mean": None, "result": "kept"}
        rungs = [e for e in exam if e[0] != "yardstick"]
        # A segment from before the exam: its last yardstick read instead.
        row["yard"] = last_yard
        if yref:
            row["yard_ref"] = {"of": yref[0][0][len("yardstick@"):], "w": yref[0][1], "n": yref[0][4]}
        g = self.gauntlet_read(os.path.join(out, "gauntlet.tsv"))
        if g:
            row["gauntlet"] = g
        for e in exam:
            if e[0] == "yardstick":
                row["yard"] = e[1]
        if rungs:
            o, w, d, l, n = rungs[-1]
            se = math.sqrt(max(1e-9, (w + l - (w - l) ** 2) / n))
            row.update({"against": o, "w": w, "d": d, "l": l, "margin_se": (w - l) / se,
                        "ladder_mean": sum(r[1] - r[3] for r in rungs) / len(rungs)})
        return row

    def crucible_ladder(self, fresh):
        """Finished segments, all islands at once, each home apart: each kept, and the
        milestone rule applied in order of margin."""
        homes = self.state.setdefault("crucible_homes", {})
        by = {}
        for n, j in fresh:
            by.setdefault(homes.pop(j, None) or self.segment_home(j), []).append((n, j))
        for home, these in sorted(by.items()):
            self.crucible_ladder_home(these, home)
        home = self.crucible_home()
        if self.gpu_home(home):
            lad = self.ladder_state(home)
            top = self.ladder_top(lad)
            if top and self.gpu_force(lad, home, top):
                self.ladder_write(home)
        if not by:
            self.ladder_write()

    def segment_home(self, jid):
        """The home a segment ran in, said by its own console (the state file it saved): a segment
        queued before segments were booked. Taking the configured home instead filed three hybrid
        segments under crucible-world-hybrid on 3 November, the night the home changed."""
        try:
            txt = open(os.path.join(self.q, "results", jid, self.home, "out", jid, "console.txt")).read()
            m = re.search(r"saved \S*/(crucible[\w-]*)/island\.state", txt)
            if m:
                return m.group(1)
        except OSError:
            pass
        return self.crucible_home()

    def crucible_ladder_home(self, fresh, home):
        lad = self.ladder_state(home)
        rows = [r for r in (self.crucible_exam(n, j, home=home) for n, j in fresh) if r]
        top = self.ladder_top(lad)
        # Strongest first: the margin over the newest milestone; with no
        # milestone yet, the yardstick's wins.
        # A forest home weighs the gauntlet's step first; the others, the margin head to head.
        if self.gpu_home(home):
            for r in rows:
                st = self.gpu_step(r, lad, top) if top and r.get("against") == top else None
                r["_zg"] = st["zg"] if st else -1e9
            rows.sort(key=lambda r: (-r["_zg"], r["island"]))
        else:
            rows.sort(key=lambda r: (-(r["margin_se"] if r["margin_se"] is not None else -1e9), -(r["yard"] or 0), r["island"]))
        os.makedirs(self.crucible_dir("milestones", home=home), exist_ok=True)
        for r in rows:
            if top is None:
                ok = r is rows[0]
                why = "the first milestone (yardstick %.3f)" % (r["yard"] or 0)
            elif r["against"] != top:
                ok, why = False, "%s, not the newest %s: meets it next segment" % (
                    "examined against %s" % r["against"] if r["against"] else "no exam against the ladder", top)
            else:
                ok = r["margin_se"] > 2 and r["ladder_mean"] >= 0
                why = "beat %s by %.1f se, ladder %+.3f" % (top, r["margin_se"], r["ladder_mean"])
                st = self.gpu_step(r, lad, top) if self.gpu_home(home) else None
                if st:
                    bar, dry = self.gpu_bar(lad)
                    # Held: every floor, or only small trades paid for by a step well over the bar.
                    held = st["holds"] or self.gpu_trade_ok(st, bar)
                    st["holds"] = held
                    r["step"] = dict(st, bar=round(bar, 2))
                    better = st["zg"] >= bar or st["zy"] >= bar
                    # HEAD TO HEAD STILL ELECTS, BUT NOT AGAINST THE GAUNTLET (Paul, 6 November: "Require the gauntlet
                    # too"): M0017 and M0020 came in two se ahead head to head with the weighed gauntlet at -2.09 and
                    # -4.11 z, below the generations they replaced.
                    ok = held and st["guard"] and (better or (ok and st["zg"] >= 0))
                    why = "the gauntlet %+.2f z (weighed by difficulty), the yardstick %+.2f z, head to head %+.1f se, against the bar %.2f%s%s%s" % (
                        st["zg"], st["zy"], r["margin_se"], bar,
                        "; traded: " + "; ".join((st["traded"] + st["missed"])[:3]) if st["short"] and held else "",
                        "" if held else "; under its floors: " + "; ".join((st["missed"] + st["traded"])[:3]) + (
                            " (the step does not pay for it, or the total did not rise)"),
                        "" if st["guard"] else "; worse on the yardstick")
                    # The window's best that went no way backwards (or traded small for a large step): the
                    # candidate a forced election takes.
                    if held and st["guard"] and st["zg"] > 0 and (not lad.get("best") or st["zg"] > lad["best"]["zg"]):
                        lad["best"] = {"job": r["job"], "island": r["island"], "gen": r["gen"], "zg": st["zg"], "zy": st["zy"], "against": top,
                                       "margin_se": r["margin_se"], "share": (r["gauntlet"]["share"].get("champion") or {}), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            if ok:
                mid = "M%04d-%s-g%d" % (len(lad["milestones"]) + 1, r["island"], r["gen"])
                shutil.copyfile(self.crucible_dir("champions", r["job"] + ".bin", home=home), self.crucible_dir("milestones", mid + ".bin", home=home))
                lad["milestones"].append({"id": mid, "job": r["job"], "island": r["island"], "gen": r["gen"],
                                          "after": top, "margin_se": r["margin_se"], "made": time.strftime("%Y-%m-%dT%H:%M:%S")})
                r["result"] = "milestone %s: %s" % (mid, why)
                top = mid
                if self.gpu_home(home):
                    self.gpu_elected(lad, r)
                self.flag("crucible", "crucible: %s is milestone %s (%s)" % (r["job"], mid, why), key="milestone:%s" % mid, progress=True)
            else:
                r["result"] = "kept: %s" % why
            r.pop("_zg", None)
            new = not os.path.exists(self.crucible_dir("lineage.tsv", home=home))
            with open(self.crucible_dir("lineage.tsv", home=home), "a") as f:
                if new:
                    f.write("time\tjob\tisland\tgen\tyard_win\tagainst\twin\tdraw\tloss\tmargin_se\tladder_mean\tresult\n")
                fm = lambda x: "-" if x is None else ("%.4f" % x if isinstance(x, float) else str(x))
                f.write("\t".join([time.strftime("%Y-%m-%dT%H:%M:%S"), r["job"], r["island"], str(r["gen"])] +
                                  [fm(r[k]) for k in ("yard", "against", "w", "d", "l", "margin_se", "ladder_mean")] + [r["result"]]) + "\n")
            # The GPU's elections, a row a segment: what Results, Generations draws.
            if r.get("step"):
                st, sh = r["step"], (r.get("gauntlet") or {}).get("share") or {}
                ep = self.crucible_dir("elect.tsv", home=home)
                first = not os.path.exists(ep)
                with open(ep, "a") as f:
                    if first:
                        f.write("time\tjob\tisland\tgen\tagainst\tzg\tzy\tbar\tholds\tguard\tmargin_se\tchampion_share\tagainst_share\tresult\n")
                    mean = lambda d: "%.4f" % (sum(d.values()) / len(d)) if d else "-"
                    f.write("\t".join([time.strftime("%Y-%m-%dT%H:%M:%S"), r["job"], r["island"], str(r["gen"]), str(r.get("against")), "%.2f" % st["zg"],
                                        "%.2f" % st["zy"], "%.2f" % st["bar"], "yes" if st["holds"] else "no", "yes" if st["guard"] else "no",
                                        fm(r.get("margin_se")), mean(sh.get("champion") or {}), mean(sh.get(r.get("against")) or {}), r["result"]]) + "\n")
        self.ladder_write(home)
    def crucible_src(self):
        return os.path.expanduser(self.cfg.get("crucible", {}).get("source", "~/code/treadcore/crucible"))

    # ---- the gauntlet's floors guard a promotion (treadcore LR 143) --------------------------------
    # Paul, 4 November: "adjust the floors to be what we have now as sucess, so we can create
    # generations from here forwards", and asked whether the floors should guard every promotion: "Yes,
    # a guard on promotions". Each candidate that has passed its reads and its families is read on the
    # gauntlet as the rules with its dials (GAUNTLET_WEIGHTS, the rules alone: a minute), at the fleet's
    # commit; auto promotion takes only one whose rules stand on every file's floor. The floors are
    # today's success, so a generation can only go forward. The promotion job reads the gauntlet again
    # on the batch it commits, beside the tests and the families.
    GUARD_RUNS = 100

    def guard_ready(self):
        if not getattr(self, "tc", None):
            return False
        src = run(["git", "-C", self.tc, "show", "%s:source/treadcore-brain/src/learn.rs" % self.sha()]).stdout
        return "GAUNTLET_WEIGHTS" in src

    # A SMALL DROP PASSES AND MOVES ITS FLOOR; A COLLAPSE DOES NOT (Paul, 13 November: "adapting the tests to
    # just pass with current numbers. Then we can progress forward"; asked, "pass on a small drop"). A
    # floor was a wall: seven candidates in a week waited on the gauntlet's G20 at 58% against 60%. A
    # family or a gauntlet file under its floor by no more than FLOOR_GIVE (a share) holds; at the
    # promotion treadcore's scripts/floors.py moves that floor down to what the new brain scored, and the
    # commit carries it. Under by more is a collapse and refuses, as a-raid-on-the-held-ground did at 0
    # of 400. 0: every floor a wall, as it was.
    FLOOR_GIVE = 0.05

    def guard_verdict(self, tsv):
        """(holds, the files under their floors) of a gauntlet read's tsv, the rules' rows."""
        floors, under = self.gauntlet_floors(), []
        for line in open(tsv).read().splitlines()[1:]:
            p = line.split("\t")
            if len(p) >= 5 and p[1] == "scripted" and p[0] in floors and float(p[4]) < floors[p[0]] - self.FLOOR_GIVE:
                under.append("%s %.0f%% under %.0f%%" % (p[0].split(" ")[0], 100 * float(p[4]), 100 * floors[p[0]]))
        return not under, under

    def guard_holds(self, name):
        """True when the gauntlet's floors let this candidate through: read at today's commit and every
        file on its floor, or no guard at this commit yet."""
        if not getattr(self, "_guard_ready", None):
            self._guard_ready = (self.guard_ready(),)
        if not self._guard_ready[0]:
            return True
        r = (self.state.get("guard") or {}).get("reads", {}).get(name) or {}
        return r.get("commit") == self.short() and r.get("verdict") == "holds"

    def guard_jobs(self, n):
        g = self.state.setdefault("guard", {"n": 0, "reads": {}})
        if n <= 0 or not self.guard_ready():
            return []
        done, gone = self.ids("done"), self.ids("failed", "stopped")
        for name, r in g["reads"].items():
            if r.get("verdict") is None and r.get("job") in done | gone:
                tsv = glob.glob(os.path.join(self.q, "results", r["job"], self.home, "out", r["job"], "gauntlet.tsv"))
                if tsv:
                    ok, under = self.guard_verdict(tsv[0])
                    r.update({"verdict": "holds" if ok else "under", "under": under})
                    if not ok:
                        self.flag("guard", "%s waits: its dials put the rules under the gauntlet's floor on %s" % (name, "; ".join(under)),
                                  key="guard:%s:%s" % (name, self.short()), progress=True)
                else:
                    r["verdict"] = "failed"
        pending = [k for k, r in g["reads"].items() if r.get("verdict") is None]
        ev = self.evidence()
        todo = sorted((k for k, v in ev.items() if v.get("current") and v.get("families") == "holds" and v.get("held_mean") is not None
                       and (g["reads"].get(k) or {}).get("commit") != self.short()), key=lambda k: -ev[k]["held_mean"])
        jobs = []
        for k in todo[:max(0, n - len(pending))]:
            g["n"] += 1
            jid = "gx%04d" % g["n"]
            b = base64.b64encode(ev[k]["weights"].encode()).decode()
            cmd = (
                "set -o pipefail; Q=~/%s; C=%s; O=$Q/out/%s; rm -rf $O; mkdir -p $O; echo %s | base64 -d > $O/trial.weights\n"
                "cd $C/wt && GAUNTLET=1 GAUNTLET_RUNS=%d GAUNTLET_BRAINS=scripted GAUNTLET_WEIGHTS=$O/trial.weights OUT=$O "
                "THREADS=${THREADS:-$(nproc 2>/dev/null || sysctl -n hw.ncpu)} $C/census-bin --ignored learn::harness::train --nocapture > $O/harness.log 2>&1; "
                "grep '^gauntlet: G' $O/harness.log | tail -40\n"
            ) % (self.home, self.cdir(), jid, b, self.GUARD_RUNS)
            jobs.append({"id": jid, "kind": "gauntlet", "title": "the gauntlet's floors: %s's dials on the rules" % k, "needs": "fast", "or": "cpu",
                         "after_host": self.after_host(), "cmd": cmd, "fetch": "%s/out/%s" % (self.home, jid), "timeout_s": 2 * 3600, "priority": "high"})
            g["reads"][k] = {"commit": self.short(), "job": jid, "verdict": None}
        return jobs

    # ---- the bridge: crucible's world champions read in the game (LR 138) ----------------------
    # Paul, 4 November: "Incorporate GPU as a growth step in the pipeline", and of the Duelist, "yes do
    # step 2, the duelist with world senses". Each new milestone of the world islands is read IN THE
    # GAME as the Gladiator, style 17, against the champion the game ships, on the same fresh seeds and
    # one fast machine: the candidate by GLADIATOR=file (treadcore styles.rs), the shipped one as it is.
    # A candidate that reads better by more than two errors of the difference ships: by itself in auto
    # mode with the push allowed, as a promotion does (Paul, 4 November: "Ship itself in auto mode"),
    # else on a person's press (`fleet-queue.py QUEUE bridge ship LABEL`). The game carries its
    # champion in its binary, so shipping is a commit to treadcore, tested on a worktree of main.
    # 192, not 48 (6 November): the first read of a forest generation, M0016, took 85 s a census and read
    # -1.35 +/- 1.79 a seat -- an error as large as any step a generation makes. Four times the seeds halve
    # it, for about six minutes of one machine a GPU generation.
    BRIDGE_SEEDS = 192
    BRIDGE_SEED0 = 80000000

    # ---- the GPU's generations: the gauntlet, its floors and the bar (6 November) -------------------
    # Paul: "fix the promotion to generations via the GPU ... we want incremental improvement. I'm not
    # observing increments, the hand pick generations need to be automatic and frequent"; "can the
    # scalars adjust when they detect diminishing returns, and have a good method of still electing the
    # best"; "make a better designed fitness and make it match difficulty projection".
    # THE OLD RULE COULD NOT SEE A STEP: a champion had to beat the newest milestone head to head by two
    # errors, and M0015 had become a net that draws 99.6% of its duels, so in 50 hours and 811 exams none
    # did. A forest home elects on what can move: the CUDA gauntlet (crucible --gauntlet, treadcore's
    # gauntlet's files and words), read for the champion and the newest milestone on the same runs, each
    # file weighed by how hard it is -- 1 for one the milestone never passes, 0.25 for one it always
    # does -- so a step on a hard file counts four times a step on an easy one; and the yardstick, the
    # fixed opponent, read for both on the same seeds. A champion is a generation when it holds every
    # floor (today's success: the newest generation's share less two errors, raised by each one), is not
    # worse on the yardstick by two errors, and is better by THE BAR on the weighed gauntlet or the
    # yardstick (or by the old rule, head to head). The bar follows the line's difficulty projection
    # (ease(): harder after each generation, easier when dry): GPU_BAR_START, +GPU_TIGHTEN after a
    # generation up to GPU_BAR_MAX, -GPU_EASE for every GPU_DRY_H hours dry down to GPU_BAR_MIN. And when
    # GPU_FORCE_H hours pass with none, or a person asks (`fleet-queue.py QUEUE crucible elect`), the best
    # candidate of the window -- the highest weighed step that held every floor and the guard -- is
    # elected: the best is still chosen when the returns diminish, and never one that went backwards.
    GPU_BAR_START, GPU_BAR_MIN, GPU_BAR_MAX = 2.0, 1.0, 3.0
    GPU_TIGHTEN, GPU_EASE, GPU_DRY_H, GPU_FORCE_H = 0.25, 0.25, 1.0, 3.0
    # SMALL TRADES (Paul, 6 November, asked whether a gain on a hard file may pay for a small loss on an
    # easy one, after boburner's champion built a base 56 times in 256 where none had, and lost 31 runs of
    # getting out of a pillbox's ring: "Allow small trades"). A file may fall below its floor by up to two
    # more of the largest errors its share can have (1/sqrt(n), 0.0625 at 256 runs) when the weighed step
    # is over the bar by GPU_TRADE_OVER; further below, or with a smaller step, the floor holds as before.
    GPU_TRADE_OVER = 2.0

    @staticmethod
    def gauntlet_read(path):
        """A CUDA gauntlet's tsv: each brain's shares by file, and the paired counts against the first."""
        try:
            rows = [l.split("\t") for l in open(path).read().splitlines()[1:]]
        except OSError:
            return None
        out = {"share": {}, "se": {}, "runs": {}, "paired": None, "items": {}}
        for r in rows:
            if len(r) < 8:
                continue
            if r[0] == "PAIRED":
                out["paired"] = {"pair": r[1], "b": int(r[2]), "c": int(r[3]), "d": float(r[4]), "se": float(r[5]), "n": int(r[7])}
            elif r[0] == "PAIRED-ITEM":
                out["items"][r[9] if len(r) > 9 else ""] = {"b": int(r[2]), "c": int(r[3]), "runs": int(r[7])}
            else:
                out["share"].setdefault(r[1], {})[r[0]] = float(r[4])
                out["se"].setdefault(r[1], {})[r[0]] = float(r[5])
                out["runs"][r[0]] = int(r[3])
        return out if out["share"] else None

    def gpu_bar(self, lad):
        """The bar now: the last one set, eased for every GPU_DRY_H hours since the newest generation."""
        made = [m for m in lad.get("milestones", []) if m.get("made") and not m.get("carried")]
        since = (made[-1]["made"] if made else lad.get("began")) or time.strftime("%Y-%m-%dT%H:%M:%S")
        dry = max(0.0, (time.time() - time.mktime(time.strptime(since[:19], "%Y-%m-%dT%H:%M:%S"))) / 3600.0)
        bar = lad.get("bar", self.GPU_BAR_START)
        return max(self.GPU_BAR_MIN, bar - self.GPU_EASE * int(dry / self.GPU_DRY_H)), dry

    @staticmethod
    def gpu_home(home):
        """A home that elects on the CUDA gauntlet: the forest's, and the maze's that grows from it."""
        return home.endswith("-forest") or home.endswith("-forest-nav")

    @staticmethod
    def gpu_floor(share, runs):
        """TODAY'S SUCCESS LESS TWO OF THE LARGEST ERRORS A SHARE OF `runs` CAN HAVE (0.5/sqrt(n)): a
        file passed 256 times of 256 has no binomial error, and its floor at share less two errors was
        1.00, which one unlucky run would break (M0016's C1 and C2, 6 November; the CPU's G25 the same
        day). Less 1/sqrt(n) -- 0.0625 at 256 runs -- is the same for every file and never 1."""
        return round(max(0.0, share - 1.0 / math.sqrt(max(1, runs))), 4)

    def gpu_floors_rebuilt(self, lad, home):
        """Floors under the first rule, rebuilt from the newest forest generation's own gauntlet."""
        lad["floor_rule"] = 2
        made = [m for m in lad.get("milestones", []) if not m.get("carried") and m.get("job")]
        lad["floors"] = {}
        if made:
            j = made[-1]["job"]
            g = self.gauntlet_read(os.path.join(self.q, "results", j, self.home, "out", j, "gauntlet.tsv"))
            for k, v in ((g or {}).get("share") or {}).get("champion", {}).items():
                lad["floors"][k] = self.gpu_floor(v, (g.get("runs") or {}).get(k, 256))

    def gpu_step(self, r, lad, top):
        """(holds, guard, z of the weighed gauntlet, z of the yardstick, the floors it missed): a forest
        champion against the newest generation, both read on the same runs."""
        g = r.get("gauntlet") or {}
        shares = g.get("share") or {}
        me, ref = shares.get("champion"), shares.get(top)
        if not me or not ref:
            return None
        if lad.get("floor_rule") != 2:
            self.gpu_floors_rebuilt(lad, self.crucible_home())
        floors = lad.setdefault("floors", {})
        if not floors:
            # TODAY'S SUCCESS, the first time: the newest generation's share less 1/sqrt(n) (gpu_floor).
            for k, v in ref.items():
                floors[k] = self.gpu_floor(v, (g.get("runs") or {}).get(k, 256))
        runs = g.get("runs") or {}
        margin = lambda k: 1.0 / math.sqrt(max(1, runs.get(k, 256)))
        under = [k for k, f in floors.items() if me.get(k, 0.0) < f - 1e-9]
        # How far under, in margins (1/sqrt(n)): the trade a step may pay for (gpu_trade_ok).
        short = {k: (floors[k] - me.get(k, 0.0)) / margin(k) for k in under}
        traded = ["%s %.2f < %.2f" % (k, me.get(k, 0.0), floors[k]) for k in under if short[k] <= 1.0 + 1e-9]
        missed = ["%s %.2f < %.2f" % (k, me.get(k, 0.0), floors[k]) for k in under if short[k] > 1.0 + 1e-9]
        total = sum(c["b"] - c["c"] for c in (g.get("items") or {}).values())
        num = var = 0.0
        for k, c in (g.get("items") or {}).items():
            n = max(1, c["runs"])
            wgt = 0.25 + 0.75 * (1.0 - ref.get(k, 0.0))
            num += wgt * (c["b"] - c["c"]) / n
            # McNemar's variance, the discordant runs under no difference (b + c), not the plug-in one: when
            # every discordant run of a file goes one way (an enemy behind, 0% to 100%) the plug-in variance
            # is zero and the z infinite -- the first forest generation read +166 z (6 November).
            var += wgt * wgt * (c["b"] + c["c"]) / (n * n)
        zg = num / math.sqrt(var) if var > 0 else 0.0
        zy, guard = 0.0, True
        yr = r.get("yard_ref") or {}
        if r.get("yard") is not None and yr.get("of") == top and yr.get("n"):
            a, b, n = r["yard"], yr["w"], yr["n"]
            se = math.sqrt(max(1e-9, a * (1 - a) / n + b * (1 - b) / n))
            zy = (a - b) / se
            guard = zy >= -2.0
        return {"holds": not missed and not traded, "guard": guard, "zg": round(zg, 2), "zy": round(zy, 2), "missed": missed, "traded": traded,
                "short": {k: round(v, 2) for k, v in short.items()}, "total": total, "step": round(num, 4)}

    def gpu_trade_ok(self, st, bar):
        """THE TOTAL SCORE (Paul, 6 November: "spending time on one type of goal will reduce its metrics in
        other things. We need a total score consideration, if things are vastly better, then we can allow a
        differing of goal priorities as long as we have improvement"). A step over the bar by GPU_TRADE_OVER
        may pay for a file one margin (1/sqrt(n)) under its floor; by twice that, two margins; by three times
        or more, three. And the total -- every file's runs gained less lost, unweighed -- must still rise."""
        if not st["short"]:
            return True
        allow = min(3.0, (st["zg"] - bar) / self.GPU_TRADE_OVER) if st["zg"] > bar else 0.0
        return allow >= 1.0 and all(v <= allow + 1e-9 for v in st["short"].values()) and st["total"] > 0

    def gpu_elected(self, lad, r):
        """After a GPU generation, the projection's step: the bar a notch harder, every floor raised to the
        new generation's own success less two errors, and the window's best begun again."""
        bar, _ = self.gpu_bar(lad)
        lad["bar"] = round(min(self.GPU_BAR_MAX, bar + self.GPU_TIGHTEN), 2)
        g = r.get("gauntlet") or {}
        me, runs = (g.get("share") or {}).get("champion") or {}, g.get("runs") or {}
        fl = lad.setdefault("floors", {})
        # TODAY'S SUCCESS IS THE NEW GENERATION'S: its own share less 1/sqrt(n) on every file. A file it
        # traded comes down to where it stands, so its heirs are not held to a skill it gave up; every other
        # floor rises with it.
        for k, v in me.items():
            fl[k] = self.gpu_floor(v, runs.get(k, 256))
        lad["best"] = None

    def gpu_force(self, lad, home, top):
        """THE FORCED ELECTION: GPU_FORCE_H hours with no generation, or a person's `crucible elect`
        (plan/crucible-elect): the window's best candidate -- the largest weighed step on the gauntlet
        among those that held every floor and were no worse on the yardstick -- is the next generation."""
        ask = os.path.join(self.pd, "crucible-elect")
        bar, dry = self.gpu_bar(lad)
        asked = os.path.exists(ask)
        b = lad.get("best")
        if not (asked or dry >= self.GPU_FORCE_H) or not b or b.get("against") != top:
            if asked and not b:
                self.flag("crucible", "an election was asked, and no candidate in the window has held every floor with a step forward: it waits for one",
                          key="elect-wait:%s" % top)
            return None
        src = self.crucible_dir("champions", b["job"] + ".bin", home=home)
        if not os.path.exists(src):
            lad["best"] = None
            return None
        mid = "M%04d-%s-g%d" % (len(lad["milestones"]) + 1, b["island"], b["gen"])
        shutil.copyfile(src, self.crucible_dir("milestones", mid + ".bin", home=home))
        why = "elected (%s): the window's best, the gauntlet %+.2f z weighed, the yardstick %+.2f z, every floor held" % (
            "asked" if asked else "%.1f h without a generation" % dry, b["zg"], b["zy"])
        lad["milestones"].append({"id": mid, "job": b["job"], "island": b["island"], "gen": b["gen"], "after": top, "margin_se": b.get("margin_se"),
                                  "made": time.strftime("%Y-%m-%dT%H:%M:%S"), "elected": True, "zg": b["zg"], "zy": b["zy"]})
        self.gpu_elected(lad, {"gauntlet": {"share": {"champion": b.get("share") or {}}, "runs": {}}})
        if asked:
            os.remove(ask)
        self.flag("crucible", "crucible: %s is milestone %s, %s" % (b["job"], mid, why), key="milestone:%s" % mid, progress=True)
        return mid

    def bridge_ready(self):
        """Does the fleet's commit play a Gladiator that GLADIATOR can swap -- and, for the maze's 64-input
        nets, one that computes the maze's senses (the route, the arcs, the memory) as the card does?"""
        src = run(["git", "-C", self.tc, "show", "%s:source/treadcore-brain/src/styles.rs" % self.sha()]).stdout
        if self.crucible_home().endswith("-nav") and "fn nav_senses" not in src:
            return False
        return "fn gladiator_file" in src

    def shipped_gladiator(self, home):
        """The milestone the fleet's commit ships as the Gladiator, found by its bytes."""
        b = subprocess.run(["git", "-C", self.tc, "show", "%s:nets/gladiator.bin" % self.sha()], capture_output=True).stdout
        if not b:
            return None
        h = hashlib.sha256(b).hexdigest()
        for f in sorted(glob.glob(os.path.join(self.crucible_dir("milestones", home=home), "M*.bin"))):
            with open(f, "rb") as fh:
                if hashlib.sha256(fh.read()).hexdigest() == h:
                    return os.path.basename(f)[:-4]
        return "a champion of no milestone here (%s)" % h[:12]

    def bridge_jobs(self):
        br = self.state.setdefault("bridge", {"reads": [], "n": 0})
        home = self.crucible_home()
        out = []
        if "world" not in home:
            br["note"] = "the islands are not world islands: nothing to read as the Gladiator"
        elif not self.bridge_ready():
            br["note"] = "the fleet's commit has no Gladiator to swap: treadcore's LR 138 is not on main"
        else:
            br["shipped"] = self.shipped_gladiator(home)
            if not br.get("said") and br.get("reads"):
                # The reads made before the verdict came back to the cards, written on their milestones once.
                if any([self.game_says(r, home) for r in br["reads"]]):
                    self.ladder_write(home)
                br["said"] = True
            done, gone = self.ids("done"), self.ids("failed", "stopped")
            cur = br.get("current")
            if cur and all(j in done | gone for j in cur["jobs"]):
                c, sh = self.job_census(cur["jobs"][0]), self.job_census(cur["jobs"][1])
                if c and sh:
                    diff, se = c[0] - sh[0], math.hypot(c[1], sh[1])
                    cur.update({"cand": [c[0], c[1]], "ship": [sh[0], sh[1]], "diff": round(diff, 3), "se": round(se, 3),
                                "holds": diff > 2 * se, "credited": diff > 2 * se, "on": c[3], "read": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                # Against the rules: the census of the Gladiator's team is read against the
                                # defaults, so its own number says how far the net stands from replacing the brain.
                                "vs_rules": [round(c[0], 3), round(c[1], 3), round(c[0] / c[1], 2) if c[1] else 0.0]})
                    # REPLACE THE BRAIN, OVER TIME (Paul, 6 November): the day a GPU generation reads past the
                    # rules themselves at the proof's z, a person is told; moving the default brain is Paul's.
                    if c[1] and c[0] / c[1] >= self.HELD_Z:
                        self.flag("bridge", "%s reads %+.2f +/- %.2f a seat past the rules themselves (z %.1f, %d seeds): a GPU net could replace the brain; "
                                  "the default brain is moved only when Paul says" % (cur["label"], c[0], c[1], c[0] / c[1], cur["seeds"]),
                                  key="replace-brain:%s" % cur["label"])
                    # IN AUTO MODE IT SHIPS ITSELF (Paul, 4 November: "Ship itself in auto mode"), as a
                    # promotion does when the push is allowed; otherwise it waits for the press.
                    auto = diff > 2 * se and self.auto() and self.push_check()["ok"]
                    if auto:
                        tool = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bridge.py")
                        subprocess.Popen(["sh", "-c", '"$0" -I "$@" > "$LOG" 2>&1', sys.executable, tool, self.q, "ship", cur["label"]],
                                         env=dict(os.environ, LOG=os.path.join(self.pd, "bridge-ship.log")),
                                         stdin=subprocess.DEVNULL, start_new_session=True)
                        cur["shipping"] = "by itself, auto mode"
                    self.flag("bridge", "bridge %d: %s reads %+.2f +/- %.2f a seat as the Gladiator over the shipped %s (%d seeds on %s): %s" % (
                        cur["n"], cur["label"], diff, se, cur["shipped"], cur["seeds"], c[3],
                        "shipping itself (auto mode): plan/bridge-ship.log says how it went" if auto
                        else "SHIP IT -- fleet-queue.py QUEUE bridge ship %s, or Ship on Results, Growth" % cur["label"] if diff > 2 * se
                        else "not better outside two errors; the shipped one stays"),
                        key="bridge:%d" % cur["n"], progress=diff <= 2 * se or auto)
                else:
                    cur.update({"holds": None, "why": "a census of the pair failed", "read": time.strftime("%Y-%m-%dT%H:%M:%S")})
                if self.game_says(cur, home):
                    self.ladder_write(home)
                br["reads"] = (br.get("reads") or [])[-30:] + [cur]
                br["current"] = cur = None
            if not cur:
                ms = sorted(glob.glob(os.path.join(self.crucible_dir("milestones", home=home), "M*.bin")))
                label = os.path.basename(ms[-1])[:-4] if ms else None
                read = {r.get("label") for r in br.get("reads", [])}
                # THE CARD ELECTS, THE GAME CREDITS (Paul, 6 November): every GPU generation is read in the
                # game, the oldest unread after the shipped one first, so each one is credited or not.
                names = [os.path.basename(m)[:-4] for m in ms]
                after = names[names.index(br.get("shipped")) + 1:] if br.get("shipped") in names else names[-1:]
                unread = [n for n in after if n not in read]
                if unread:
                    label = unread[0]
                    ms = [m for m in ms if os.path.basename(m)[:-4] == label]
                fast = [h["name"] for h in self.hosts if "fast" in h.get("caps", [])] or [h["name"] for h in self.hosts if "cpu" in h.get("caps", [])]
                if label and label != br.get("shipped") and label not in read and fast:
                    n = br["n"] = br.get("n", 0) + 1
                    seed0 = self.BRIDGE_SEED0 + 1000 * n
                    jc, js = "bridge-%03d-c" % n, "bridge-%03d-s" % n
                    out = [self.census_job(jc, "bridge %d: %s as the Gladiator" % (n, label), "bot_style = 17\n", "", self.BRIDGE_SEEDS, seed0, 900, "all",
                                           host=fast[0], env="GLADIATOR=$Q/trials/%s.champ " % jc,
                                           also=[{"src": ms[-1], "dst": "~/%s/trials/%s.champ" % (self.home, jc)}]),
                           self.census_job(js, "bridge %d: the shipped Gladiator, %s, on the same seeds" % (n, br.get("shipped")), "bot_style = 17\n", "",
                                           self.BRIDGE_SEEDS, seed0, 900, "all", host=fast[0])]
                    br["current"] = {"n": n, "label": label, "shipped": br.get("shipped"), "jobs": [jc, js], "seed0": seed0,
                                     "seeds": self.BRIDGE_SEEDS, "host": fast[0], "asked": time.strftime("%Y-%m-%dT%H:%M:%S")}
            br["note"] = ("reading %s against the shipped %s on %s" % (br["current"]["label"], br.get("shipped"), br["current"]["host"]) if br.get("current")
                          else "the game ships %s as the Gladiator; every milestone since has been read" % br.get("shipped"))
        save(os.path.join(self.pd, "bridge.json"), {k: v for k, v in br.items()} | {"home": home, "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        return out

    # ---- the montage, by itself (Paul, 4 November: "Every 5 new milestones") ----------------------
    MONTAGE_EVERY = 5
    # ---- and the trailer (Paul, 6 November: "every 2 line generations") ----------------------------
    # THE WORLD LADDER STOOD STILL FOR TWO DAYS: M0015 at 05:42 on 4 November, and no exam since beat it
    # by the two errors a milestone takes, so the film every 5 milestones never came, while the line
    # committed w10839, w11139, w11352 and w12042. The game's own brain was moving and nothing filmed it
    # unless asked. So a second watch, on the line: every TRAILER_EVERY generations committed (on the
    # line or on main) since the last film that told the line, a trailer -- the short film of those
    # generations, not the whole montage again, whose world chapters would be the same twelve each time
    # the ladder stands. 0 leaves it to the button.
    TRAILER_EVERY = 2

    @staticmethod
    def run_no(rid):
        m = re.match(r"r(\d+)$", rid or "")
        return int(m.group(1)) if m else -1

    @staticmethod
    def line_filmed(q):
        """The newest line generation a film has told, a montage's line act or a trailer: its run id, or
        None. A montage made before 6 November has no line_last in the index; its summary's act says it."""
        best = None
        for kind in ("montages", "trailers"):
            films = (load(os.path.join(q, "archive", kind, "index.json"), {}) or {}).get(kind) or []
            if not films:
                continue
            rid = films[-1].get("line_last")
            if not rid and films[-1].get("n"):
                s = load(os.path.join(q, "archive", kind, "%04d" % films[-1]["n"], "summary.json"), {}) or {}
                gens = (s.get("line") or {}).get("gens") or []
                rid = gens[-1]["run"] if gens else None
            if rid and Plan.run_no(rid) > Plan.run_no(best):
                best = rid
        return best

    def line_won(self):
        """The line's generations, oldest first: every promotion that was committed, on the line or on main."""
        return [r["id"] for r in self.runs() if r["kind"] == "promote" and self.rstate(r["id"]).get("status") in ("approved", "self-modified")]

    def montage_watch(self):
        """A film when the world ladder has gained MONTAGE_EVERY milestones since the last one: tools/
        montage.py make in the background, as the Montage page's button does. Else a trailer when the line
        has committed TRAILER_EVERY generations since the last film told it: montage.py trailer. One film
        at a time -- both trace on the same GPU folder -- and one asked an hour."""
        lock = os.path.join(self.pd, "montage.lock")
        busy = os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 3 * 3600
        if busy or time.time() - self.state.get("montage_asked", 0) < 3600:
            return
        tool = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "montage.py")
        ask = lambda verb: subprocess.Popen([sys.executable, "-I", tool, self.q, verb], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL, start_new_session=True)
        n = int(self.MONTAGE_EVERY)
        home = self.crucible_home()
        if n > 0 and "world" in home:
            idx = load(os.path.join(self.q, "archive", "montages", "index.json"), {}) or {}
            films = idx.get("montages") or []
            last = films[-1].get("last") if films else None
            ms = [os.path.basename(f)[:-4] for f in sorted(glob.glob(os.path.join(self.crucible_dir("milestones", home=home), "M*.bin")))]
            new = ms[ms.index(last) + 1:] if last in ms else ms
            if len(new) >= n:
                self.state["montage_asked"] = time.time()
                ask("make")
                self.flag("montage", "montage asked: %d new milestones since %s (%s to %s); Results, Montage follows it" % (
                    len(new), last or "the start", new[0], new[-1]), key="montage-asked:%s" % new[-1], progress=True)
                return
        e = int(self.TRAILER_EVERY)
        if e > 0:
            told = self.line_filmed(self.q)
            new = [r for r in self.line_won() if self.run_no(r) > self.run_no(told)]
            if len(new) >= e:
                self.state["montage_asked"] = time.time()
                ask("trailer")
                self.flag("montage", "trailer asked: %d line generations since %s (%s); Results, Videos will list it" % (
                    len(new), told or "the start", ", ".join(new)), key="trailer-asked:%s" % new[-1], progress=True)

    # ---- every generation on film (Paul, 6 November: "we want to see just about every generation have a set
    # of tests be monitored, then we take those recordings and collect them to show generations of footage.
    # We dont need to show old generations, just the newly trained ones.") -------------------------------
    FOOTAGE_EVERY_S = 1200

    def footage_watch(self):
        """When the GPU's home has a generation of its own (not one carried from the home before) with no
        footage: tools/report/footage.py make, then reel, in the background -- its tests traced on an island
        and filmed, the generations' sheets joined. One at a time (footage.lock), asked at most every
        FOOTAGE_EVERY_S; the output in footage.log beside the lock."""
        home = self.crucible_home()
        if "-forest" not in home:
            return
        lock = os.path.join(self.pd, "footage.lock")
        if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 3 * 3600:
            return
        if time.time() - self.state.get("footage_asked", 0) < self.FOOTAGE_EVERY_S:
            return
        made = [m["id"] for m in self.ladder_state(home).get("milestones", []) if m.get("made") and not m.get("carried")]
        idx = load(os.path.join(self.q, "archive", "footage", home, "index.json"), {}) or {}
        done = {g.get("id") for g in idx.get("generations", [])}
        todo = [m for m in made if m not in done]
        if not todo:
            return
        self.state["footage_asked"] = time.time()
        tool = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "report", "footage.py")
        py, q = shlex.quote(sys.executable), shlex.quote(self.q)
        sh = "touch {l}; {py} -I {t} {q} make --home {h} && {py} -I {t} {q} reel --home {h}; rm -f {l}".format(
            l=shlex.quote(lock), py=py, t=shlex.quote(tool), q=q, h=shlex.quote(home))
        with open(os.path.join(self.pd, "footage.log"), "a") as log:
            subprocess.Popen(["sh", "-c", sh], stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        self.flag("footage", "footage asked: %d new generation(s) of %s (%s); archive/footage/%s, and output/treadcore-footage.mp4" % (
            len(todo), home, ", ".join(todo), home), key="footage-asked:%s" % todo[-1], progress=True)

    # ---- a card beside every GPU generation (Paul, 6 November: "Net cards every pass") ----------------
    NETCARD_EVERY_S = 600

    def netcard_watch(self):
        """Every NETCARD_EVERY_S, tools/report/netcard.py in the background: a card beside each milestone of every
        GPU home (its lineage, election, senses, what it moved, its training and gauntlet, the game's read, its
        footage), and HOME/cards.json; a card unchanged is not written again."""
        if time.time() - self.state.get("netcards_asked", 0) < self.NETCARD_EVERY_S:
            return
        self.state["netcards_asked"] = time.time()
        tool = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "report", "netcard.py")
        subprocess.Popen([sys.executable, "-I", tool, self.q], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    # ---- the census's maps, kept in a history (Paul, 6 November: "how much worse is it to do them all. and keep
    # a history and a passrate") ------------------------------------------------------------------------
    MAP_EVERY_S = 6 * 3600

    def map_watch(self):
        """Every MAP_EVERY_S, tools/report/seed_sense.py in the background appends a line to plan/maps-history.jsonl:
        each census map's agreement with the verdict, a seed's spread, its telling and its pass rate, over every census
        and over those since the line before."""
        hist = os.path.join(self.pd, "maps-history.jsonl")
        if os.path.exists(hist) and time.time() - os.path.getmtime(hist) < self.MAP_EVERY_S:
            return
        if time.time() - self.state.get("maps_asked", 0) < self.MAP_EVERY_S:
            return
        self.state["maps_asked"] = time.time()
        tool = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "report", "seed_sense.py")
        subprocess.Popen([sys.executable, "-I", tool, self.q, "--history", hist], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    # ---- the clone: the rules cloned again on the GPU each time they move (Paul's step 3) -------
    # Paul, 4 November, of the GPU as a growth step: "GPU trainer as a stage", the net "Re-clone the
    # rules", judged by "Census + gauntlets". The Scholar (style 6) is a net that learned by imitating the
    # scripted brain, and the scripted brain moves with every promotion; a clone of last week's rules
    # imitates a brain the game no longer plays. So when main moves (at most once in CLONE_EVERY_H
    # hours), a round: RECORD the rules at the new commit (a record run, CLONE_SEEDS matches, shards to the
    # GPU store), TRAIN a clone from scratch on the card (the fast setting of LR 107), JUDGE it against
    # the shipped Scholar -- a census of each as the whole trial team on the same seeds and one machine,
    # better by two errors of the paired difference, AND the gauntlet with both, where no file the
    # Scholar meets falls under its floor and none drops by two errors -- and SHIP it into
    # nets/scholar.bin, by itself in auto mode with the push allowed, else on a press. The recording is
    # read once, by the train job; the recordings sweep drops its shards after, the recipe kept.
    CLONE_SEEDS = 120
    CLONE_JUDGE_SEEDS = 48
    CLONE_SEED0 = 9700000
    CLONE_JUDGE_SEED0 = 81000000
    CLONE_EVERY_H = 0   # off since 13 November: fifteen rounds, no clone shipped (12 before)

    def shipped_scholar(self):
        """The file style 6 plays at the fleet's commit, by styles.rs: "bc2.bin" until a clone ships."""
        src = run(["git", "-C", self.tc, "show", "%s:source/treadcore-brain/src/styles.rs" % self.sha()]).stdout
        m = re.search(r'name: "Scholar".*?nets/([\w.-]+\.bin)', src)
        return m.group(1) if m else None

    def gauntlet_floors(self):
        """{gauntlet's name: its floor} from scenarios/gauntlet at the fleet's commit."""
        out = {}
        ls = run(["git", "-C", self.tc, "ls-tree", "--name-only", "%s:scenarios/gauntlet" % self.sha()]).stdout.split()
        for f in ls:
            if not f.endswith(".toml"):
                continue
            t = run(["git", "-C", self.tc, "show", "%s:scenarios/gauntlet/%s" % (self.sha(), f)]).stdout
            n, fl = re.search(r'^name\s*=\s*"([^"]+)"', t, re.M), re.search(r"^floor\s*=\s*([\d.]+)", t, re.M)
            if n and fl:
                out[n.group(1)] = float(fl.group(1))
        return out

    def clone_jobs(self):
        cl = self.state.setdefault("clone", {"n": 0, "rounds": []})
        every = float(self.CLONE_EVERY_H)
        gpu = [h for h in self.hosts if "gpu" in h.get("caps", [])]
        fast = [h["name"] for h in self.hosts if "fast" in h.get("caps", [])] or [h["name"] for h in self.hosts if "cpu" in h.get("caps", [])]
        scholar = self.shipped_scholar()
        cur = cl.get("current")
        jobs = []
        done, gone = self.ids("done"), self.ids("failed", "stopped")
        if not cur:
            due = (self.auto() and every > 0 and gpu and fast and scholar and cl.get("for") != self.short()
                   and time.time() - cl.get("at", 0) >= every * 3600)
            if due:
                n = cl["n"] = cl.get("n", 0) + 1
                name = "clone%d" % n
                rid = self.new_run("record", {"run": name, "count": self.CLONE_SEEDS, "per": 12, "secs": 600, "seed0": self.CLONE_SEED0 + 1000 * n}, "clone")
                cl.update({"for": self.short(), "at": time.time()})
                cl["current"] = cur = {"n": n, "name": name, "record": rid, "commit": self.short(), "scholar": scholar, "step": "record",
                                       "asked": time.strftime("%Y-%m-%dT%H:%M:%S")}
            cl["note"] = ("the next round when main moves past %s and %g h have passed" % (cl.get("for"), every) if cl.get("for")
                          else "the first round at the next plan in auto mode")
        elif cur["step"] == "record":
            rs = self.rstate(cur["record"])
            if rs.get("status") == "failed":
                cur.update({"step": "failed", "why": "the recording failed"})
            elif rs.get("status") == "done" and gpu and self.prepared(gpu[0]["name"]):
                jid = "clone-%03d-train" % cur["n"]
                cmd = ("D=~/%s/out/%s; mkdir -p $D\n%s"
                       "GPU_GB=2 BC_DEVICE=cuda %s/treadcore-bc ~/fleet/%s/shards $D/cand.bin 12 32768 0.01 > $D/train.log 2>&1 || echo 'the training failed'\n"
                       "grep -v 'DEINIT\\|^thread\\|^note\\|^$' $D/train.log | tail -12\n") % (self.home, jid, self.trainer(), self.cdir(), cur["name"])
                jobs.append({"id": jid, "kind": "net", "title": "clone %d: the rules at %s cloned on the card" % (cur["n"], cur["commit"]),
                             "needs": "host:" + gpu[0]["name"], "after": [self.prep_id(gpu[0]["name"])], "cmd": cmd,
                             "fetch": "%s/out/%s" % (self.home, jid), "timeout_s": 4 * 3600})
                cur.update({"step": "train", "train": jid})
        elif cur["step"] == "train" and cur["train"] in done | gone:
            cand = glob.glob(os.path.join(self.q, "results", cur["train"], self.home, "out", cur["train"], "cand.bin"))
            if not cand:
                cur.update({"step": "failed", "why": "the training wrote no net"})
            else:
                n, seed0, host = cur["n"], self.CLONE_JUDGE_SEED0 + 1000 * cur["n"], fast[0]
                jc, js, jg = "clone-%03d-c" % n, "clone-%03d-s" % n, "clone-%03d-g" % n
                # ONE SEAT BESIDE THE RULES (Paul, 4 November: "One seat beside the rules"): the clone on
                # the team's last seat, its leader and guard the rules (bot_mix one), as a net would play
                # in a real side; a whole team of nets loses forty a seat for want of building and crews,
                # and that gap drowned the first round's difference. It needs SCHOLAR (treadcore LR 140);
                # a commit without it is judged as a whole team, and the round says so.
                one = "fn scholar_file" in run(["git", "-C", self.tc, "show", "%s:source/treadcore-brain/src/styles.rs" % self.sha()]).stdout
                cur["judged_as"] = "one seat beside the rules" if one else "a whole team of nets (no SCHOLAR at this commit)"
                if one:
                    trial = "bot_style = 6\nbot_mix = one\n"
                    jobs += [self.census_job(jc, "clone %d: the new clone on one seat beside the rules" % n, trial, "", self.CLONE_JUDGE_SEEDS, seed0, 900, "all",
                                             host=host, env="SCHOLAR=$Q/trials/%s.net " % jc, also=[{"src": cand[0], "dst": "~/%s/trials/%s.net" % (self.home, jc)}]),
                             self.census_job(js, "clone %d: the shipped Scholar on one seat, the same seeds" % n, trial, "", self.CLONE_JUDGE_SEEDS,
                                             seed0, 900, "all", host=host)]
                else:
                    jobs += [self.census_job(jc, "clone %d: the new clone as the whole trial team" % n, "", "", self.CLONE_JUDGE_SEEDS, seed0, 900, "all",
                                             net=cand[0], host=host),
                             self.census_job(js, "clone %d: the shipped Scholar (%s), the same seeds" % (n, cur["scholar"]), "", "", self.CLONE_JUDGE_SEEDS,
                                             seed0, 900, "all", host=host, env="CENSUS_NET=$C/wt/nets/%s " % cur["scholar"])]
                g = self.gauntlet_job(jg)
                g["send"] = [{"src": cand[0], "dst": "~/%s/trials/%s.bin" % (self.home, jg)}]
                g["cmd"] = g["cmd"].replace("cd $C/wt && GAUNTLET=1", "cp $Q/trials/%s.bin $C/wt/nets/%s.bin; cd $C/wt && GAUNTLET_NETS=%s,%s GAUNTLET=1"
                                            % (jg, jg, cur["scholar"][:-4], jg)) + "rm -f $C/wt/nets/%s.bin\n" % jg
                g["title"] = "clone %d: the gauntlet, the new clone beside the shipped Scholar" % n
                jobs.append(g)
                cur.update({"step": "judge", "cand": cand[0], "jobs": [jc, js, jg], "seed0": seed0, "host": host})
        elif cur["step"] == "judge" and all(j in done | gone for j in cur["jobs"]):
            c, sh = self.job_census(cur["jobs"][0]), self.job_census(cur["jobs"][1])
            tsv = glob.glob(os.path.join(self.q, "results", cur["jobs"][2], self.home, "out", cur["jobs"][2], "gauntlet.tsv"))
            if not (c and sh and tsv):
                cur.update({"step": "failed", "why": "a judge's job failed"})
            else:
                diff, se = c[0] - sh[0], math.hypot(c[1], sh[1])
                rows = {}
                for line in open(tsv[0]).read().splitlines()[1:]:
                    p = line.split("\t")
                    if len(p) >= 6:
                        rows.setdefault(p[0], {})[p[1]] = (float(p[4]), float(p[5]))
                floors, worse = self.gauntlet_floors(), []
                cn, sn = cur["jobs"][2], cur["scholar"][:-4]
                for item, b in sorted(rows.items()):
                    if cn not in b or sn not in b:
                        continue
                    (pc, ec), (ps, es) = b[cn], b[sn]
                    fl = floors.get(item)
                    if pc < ps - 2 * math.hypot(ec, es):
                        worse.append("%s %.0f%% for %.0f%%" % (item, 100 * pc, 100 * ps))
                    elif fl is not None and ps >= fl > pc:
                        worse.append("%s under its floor %.0f%% (%.0f%% for %.0f%%)" % (item, 100 * fl, 100 * pc, 100 * ps))
                holds = diff > 2 * se and not worse
                cur.update({"step": "judged", "cand_read": [c[0], c[1]], "ship_read": [sh[0], sh[1]], "diff": round(diff, 3), "se": round(se, 3),
                            "gauntlet_worse": worse, "holds": holds, "read": time.strftime("%Y-%m-%dT%H:%M:%S")})
                auto = holds and self.auto() and self.push_check()["ok"]
                if auto:
                    tool = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bridge.py")
                    subprocess.Popen(["sh", "-c", '"$0" -I "$@" > "$LOG" 2>&1', sys.executable, tool, self.q, "ship-clone", str(cur["n"])],
                                     env=dict(os.environ, LOG=os.path.join(self.pd, "clone-ship.log")), stdin=subprocess.DEVNULL, start_new_session=True)
                    cur["shipping"] = "by itself, auto mode"
                self.flag("clone", "clone %d (the rules at %s, judged as %s): %+.2f +/- %.2f a seat over the shipped Scholar on %d seeds%s: %s" % (
                    cur["n"], cur["commit"], cur.get("judged_as", "a whole team"), diff, se, self.CLONE_JUDGE_SEEDS,
                    "; the gauntlet worse on " + "; ".join(worse) if worse else "; the gauntlet holds",
                    "shipping itself (auto mode)" if auto else "SHIP IT -- fleet-queue.py QUEUE bridge ship-clone %d" % cur["n"] if holds
                    else "not shipped"), key="clone:%d" % cur["n"], progress=not holds or auto)
        if cur and cur.get("step") in ("judged", "failed"):
            cl["rounds"] = (cl.get("rounds") or [])[-30:] + [cur]
            cl["current"] = cur = None
        if cur:
            cl["note"] = "clone %d: %s (the rules at %s)" % (cur["n"], {"record": "recording %d matches" % self.CLONE_SEEDS, "train": "training on the card",
                                                                         "judge": "judged: two censuses and the gauntlet on %s" % cur.get("host")}.get(cur["step"], cur["step"]), cur["commit"])
        save(os.path.join(self.pd, "clone.json"), {k: v for k, v in cl.items()} | {"scholar": scholar, "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        return jobs

    # THE WORLD'S RULES ARE THE GAME'S (Paul, 4 November: "the GPU build always looks like the perfect
    # world in treadcore"). Read from treadcore-sim's rules.rs at the fleet's commit, each under
    # crucible's own name, seconds for ticks, and passed to make one variable each (R_VMAX=4.0f): the
    # .flags stamp holds them, so a rule that moves rebuilds every island at its next segment, and a
    # flag says what moved. A rule rules.rs no longer has is left at crucible's own number, and said.
    WORLD_RULES = (("CONCEAL_RANGE", "CONCEAL_RANGE", False), ("VMAX", "TANK_SPEED", False), ("ACCEL", "TANK_ACCEL", False), ("BRAKE", "TANK_BRAKE", False),
                   ("TURN", "TANK_TURN", False), ("GUN_RANGE", "DIRECT_RANGE", False), ("SSPEED", "SHELL_SPEED_DIRECT", False),
                   ("RELOAD", "RELOAD_TICKS", True), ("HP", "TANK_ARMOR", False), ("DAMAGE", "DIRECT_DAMAGE", False),
                   ("HIT_R", "DIRECT_HIT_RADIUS", False), ("SHELLS", "TANK_SHELLS", False), ("VISION", "TANK_VISION", False),
                   ("PB_RANGE", "PILLBOX_RANGE", False), ("PB_DAMAGE", "PILLBOX_DAMAGE", False),
                   ("PB_RELOAD", "PILLBOX_RELOAD_TICKS", True), ("PB_HEALTH", "PILLBOX_HEALTH", False))

    def world_rules(self):
        """{crucible name: value} from rules.rs at the fleet's commit, and the names it lacked."""
        sha = self.sha()
        src = run(["git", "-C", self.tc, "show", "%s:source/treadcore-sim/src/rules.rs" % sha]).stdout
        lib = run(["git", "-C", self.tc, "show", "%s:source/treadcore-sim/src/lib.rs" % sha]).stdout
        m = re.search(r"pub const TICK_HZ: \w+ = (\d+);", lib)
        hz = int(m.group(1)) if m else 20
        out, lost = {}, []
        for name, rust, ticks in self.WORLD_RULES:
            m = re.search(r"pub const %s: \w+ = ([^;]+);" % rust, src)
            expr = re.sub(r"\bas \w+", "", m.group(1)).replace("TICK_HZ", str(hz)).replace("_", "") if m else ""
            if not m or not re.match(r"^[\d.\s*+/()-]+$", expr):
                lost.append(rust)
                continue
            v = float(eval(expr, {"__builtins__": {}}, {}))
            out[name] = v / hz if ticks else v
        # THE SAME SCORE (6 November): the game's scoring constants as crucible's weights, in kills.
        sc = {k: re.search(r"pub const %s: \w+ = (\d+);" % k, src) for k in ("SCORE_KILL", "SCORE_CAPTURE", "SCORE_HOLD")}
        if all(sc.values()) and float(sc["SCORE_KILL"].group(1)) > 0:
            kill = float(sc["SCORE_KILL"].group(1))
            out["SCORE_CAPTURE_W"] = float(sc["SCORE_CAPTURE"].group(1)) / kill
            out["SCORE_HOLD_W"] = float(sc["SCORE_HOLD"].group(1)) / kill
        return out, lost

    def world_flags(self):
        """The rules as make variables, recorded, and a flag when they moved since the last segment."""
        if getattr(self, "_world_flags", None) is not None:
            return self._world_flags
        rules, lost = self.world_rules()
        if not rules:
            self._world_flags = ""
            return ""
        old = self.state.get("crucible_rules") or {}
        moved = ["%s %g -> %g" % (k, old["rules"][k], v) for k, v in sorted(rules.items()) if k in (old.get("rules") or {}) and old["rules"][k] != v]
        if moved:
            moves = self.state.setdefault("rules_moves", [])
            moves.append({"at": time.time(), "text": "the islands' rules at %s: %s" % (self.short(), ", ".join(moved))})
            del moves[:-50]
        if moved or lost and not old.get("lost"):
            self.flag("crucible", "the world islands now play treadcore's rules at %s: %s%s" % (
                self.short(), ", ".join(moved) or "nothing moved", "; not in rules.rs, left at crucible's own: %s" % ", ".join(lost) if lost else ""),
                key="crucible-rules:%s" % self.short())
        self.state["crucible_rules"] = {"commit": self.short(), "rules": rules, "lost": lost,
                                        "flags": " ".join("R_%s=%sf" % (k, repr(float(v))) for k, v in sorted(rules.items()))}
        self._world_flags = self.state["crucible_rules"]["flags"]
        return self._world_flags

    def crucible_jobs(self):
        src = self.crucible_src()
        if not self.cuda or not os.path.exists(os.path.join(src, "src", "crucible.cu")):
            return []
        opt = dict({"gens": 50, "pop": 2048, "eps": 128, "yard": 10, "ahead": 6, "lad": 0.2, "draw": -1.0}, **self.cfg.get("crucible", {}))
        if not os.path.exists(self.crucible_dir("ladder", "ladder.txt")):
            self.ladder_write()
        cr = self.state.setdefault("crucible", {})
        done, failed, stopped = self.ids("done"), self.ids("failed"), self.ids("stopped")
        # Each island keeps `ahead` segments queued, each after the one
        # before (its state file is the last one's), so the GPU lane is not
        # left idle between the keeper's plans.
        fresh = []
        for h in self.cuda:
            isl = cr.setdefault(h["name"], {"seg": 0, "last": None, "failures": 0, "gens": 0})
            isl.setdefault("queued", [isl["job"]] if isl.get("job") else [])
            isl.setdefault("next", isl["seg"] + len(isl["queued"]))
            isl.pop("job", None)
            live = []
            for j in isl["queued"]:
                if j in done:
                    isl.update({"seg": isl["seg"] + 1, "last": j, "failures": 0, "gens": isl["gens"] + opt["gens"]})
                    fresh.append((h["name"], j))
                elif j in failed:
                    isl["failures"] += 1
                    isl["failed_at"] = time.time()
                # A PERSON STOPPING A SEGMENT IS NOT A FAULT IN IT. Counted as one, the stop of
                # 30 October disabled all three islands for good, and the GPUs idled for two days.
                elif j not in stopped:
                    live.append(j)
            isl["queued"] = live
            # Three in a row rests an island for half an hour, and never for good: most of these
            # are a machine's ssh refusing a file, or a machine off, not the program.
            if isl["failures"] >= 3 and time.time() - isl.get("failed_at", 0) > 1800:
                isl["failures"] = 0
            if isl["failures"] >= 3:
                self.flag("crucible", "crucible on %s failed three segments in a row: it rests half an hour; see its logs" % h["name"], key="crucible:%s:%d" % (h["name"], isl["seg"]))
        self.crucible_ladder(fresh)
        jobs = []
        for h in self.cuda:
            name, isl = h["name"], cr[h["name"]]
            if isl["failures"] >= 3:
                continue
            while len(isl["queued"]) < opt["ahead"]:
                jid = "x-%s-%04d" % (name, isl["next"])
                isl["next"] += 1
                kind = self.crucible_home()
                home = "%s/%s" % (self.home, kind)
                # The segment is booked to the home it runs in, so its champion and exam go there
                # even when the home changes while it waits in the queue.
                self.state.setdefault("crucible_homes", {})[jid] = kind
                c = self.cfg.get("crucible") or {}
                # The build's flags. A world net is wider in its hidden layers too (H 48: 55 inputs
                # and two nets of 48 still fit a Pascal card's 48 KB of shared memory).
                flag = ("HYBRID=1 " if c.get("hybrid") else "") + ("WORLD=1 " if c.get("world") else "") + ("FOREST=1 " if c.get("world") and c.get("forest") else "")
                flag += "NAV=1 " if c.get("world") and c.get("forest") and c.get("nav") else ""
                hw = int(c.get("h") or (48 if c.get("world") else 32))
                flag += "H=%d " % hw if hw != 32 else ""
                if c.get("world"):
                    flag += self.world_flags() + " "
                parent = self.crucible_parent(kind)
                send = [{"src": os.path.join(src, f), "dst": "~/%s/%s" % (home, f)} for f in ("src/crucible.cu", "Makefile")]
                # Read when the keeper dispatches it: the other islands'
                # newest champions, and the ladder as it is then.
                imports = []
                for o in cr:
                    champ = self.crucible_dir("latest", o + ".bin")
                    if o != name and os.path.exists(champ) and not self.island_refused(o, kind):
                        send.append({"src": champ, "dst": "~/%s/in/%s.bin" % (home, o)})
                        imports.append("$H/in/%s.bin" % o)
                # What the game ships, to every island: the one net the game has credited.
                shipped = (self.state.get("bridge") or {}).get("shipped") or ""
                game = self.crucible_dir("milestones", shipped + ".bin", home=kind)
                if shipped and os.path.exists(game):
                    send.append({"src": game, "dst": "~/%s/in/game.bin" % home})
                    imports.append("$H/in/game.bin")
                send += [{"src": self.crucible_dir("ladder", f), "dst": "~/%s/ladder/%s" % (home, f)}
                         for f in ["slot-%d.bin" % i for i in range(self.LADDER_SLOTS)] + ["ladder.txt"]]
                forest = bool(c.get("world") and c.get("forest"))
                if forest:
                    # The CUDA gauntlet's files: the test each segment's champion sits, and its training's tasks.
                    send += [{"src": f, "dst": "~/%s/gauntlet/%s" % (home, os.path.basename(f))} for f in sorted(glob.glob(os.path.join(src, "gauntlet", "*.toml")))]
                seed = 1000 + 97 * (sum(map(ord, name)) % 1000)
                cmd = (
                    "set -e; H=~/%s; O=~/%s/out/%s; mkdir -p $O $H/in\n"
                    # make rebuilds when the source changes, not when the flags do: a stamp of them does.
                    "cd $H && F='FLAGS_NOW'; [ \"$(cat .flags 2>/dev/null)\" = \"$F\" ] || { rm -f crucible; echo \"$F\" > .flags; }\n"
                    "make -s FLAGS_NOW NVCC=${NVCC:-/usr/local/cuda/bin/nvcc} >/dev/null 2>&1 || make FLAGS_NOW NVCC=${NVCC:-/usr/local/cuda/bin/nvcc}\n"
                    "L=''; if [ -f $H/island.state ]; then L=\"--load $H/island.state\"; elif [ -n 'PARENT_NOW' ] && [ -f ~/PARENT_NOW/island.state ]; then L=\"--load $(echo ~/PARENT_NOW/island.state)\"; fi\n"
                    # Double quotes: the imports are $H/in/NAME.bin, and in single quotes $H never
                    # expanded -- every import since 28 October was "not a champion of this net".
                    "I=\"%s\"\n"
                    # The milestones by name, oldest first, from their slots.
                    "rm -rf $H/rungs; mkdir -p $H/rungs; R=''\n"
                    "while IFS=\"$(printf '\\t')\" read -r s m; do if [ -n \"$m\" ]; then cp $H/ladder/$s $H/rungs/$m.bin; R=\"$R${R:+,}$H/rungs/$m.bin\"; fi; done < $H/ladder/ladder.txt\n"
                    "./crucible --pop %d --eps %d --gens %d --yard %d --seed %d --lad %s --draw %s $L ${I:+--import $I} ${R:+--ladder $R} "
                    "--save $H/island.state --export $O/champ.bin --out $O/gens.tsv --exam $O/exam.tsv GAUNTLET_NOW2>&1 | tee $O/console.txt | grep '^#'\n"
                ) % (home, self.home, jid, ",".join(imports), opt["pop"], opt["eps"], opt["gens"], opt["yard"], seed, opt["lad"], opt["draw"])
                # The newest rung is the gauntlet's reference: the champion and it, on the same runs.
                cmd = cmd.replace("GAUNTLET_NOW", (
                    "--tasks $H/gauntlet --task-p %s --gauntlet $H/gauntlet --gauntlet-runs %d --gauntlet-out $O/gauntlet.tsv ${R:+--gauntlet-ref ${R##*,}} " % (
                        opt.get("task_p", 0.25), int(opt.get("gauntlet_runs", 256)))) if forest else "")
                cmd = cmd.replace("FLAGS_NOW ", flag).replace("'FLAGS_NOW'", "'%s'" % flag.strip())
                cmd = cmd.replace("PARENT_NOW", "%s/%s" % (self.home, parent) if parent else "")
                job = {"id": jid, "kind": "crucible", "title": "crucible island %s, segment %d" % (name, isl["next"] - 1),
                       "needs": "host:" + name, "cmd": cmd, "send": send, "fetch": "%s/out/%s" % (self.home, jid), "timeout_s": 4 * 3600}
                if isl["queued"]:
                    job["after"] = [isl["queued"][-1]]
                jobs.append(job)
                isl["queued"].append(jid)
        self.crucible_view()
        return jobs

    def crucible_view(self):
        """plan/crucible.json for orrery's Projects view: each island's
        segments, generations, last yardstick and speed, from its results."""
        out = {}
        # EACH SEGMENT'S ROWS ARE SUMMED UP ONCE (8 November): every pass read every segment any
        # island ever ran, 1.1 million rows, seven of its seconds, for a maximum, a speed and two
        # curves' last forty points. A segment's gens.tsv is fetched once; its summary is kept in
        # plan/crucible-rows.json by the file's size and time, and read again if either moves.
        cache_f = os.path.join(self.pd, "crucible-rows.json")
        cache = load(cache_f, {}) or {}
        kept, fresh = {}, 0
        names = sorted((names_in(os.path.join(self.q, "results")) or ([], False))[0])
        for name, isl in self.state.get("crucible", {}).items():
            gens, msteps, yard, ladder = [], [], [], []
            for jid in (n for n in names if n.startswith("x-%s-" % name)):
                f = os.path.join(self.q, "results", jid, self.home, "out", jid, "gens.tsv")
                try:
                    st = os.stat(f)
                except OSError:
                    continue
                hit = cache.get(f)
                if not hit or hit[0] != st.st_size or hit[1] != st.st_mtime_ns:
                    rows = []
                    try:
                        for line in open(f).read().splitlines()[1:]:
                            r = line.split("\t")
                            # A ROW A CUT LEFT AS ZEROS IS ONE ROW, NOT THE PLANNER (8 November).
                            # calber's x-calber-cuda-3345 ran again after the cut and wrote on after
                            # the 116 bytes the cut kept from its disk; every pass from 08:46 to 09:23
                            # died on that row, and for forty minutes nothing was planned. A row whose
                            # numbers do not read is passed over.
                            try:
                                int(r[0])
                                [float(r[i]) for i in (4, 7, 10, 11) if i < len(r)]
                            except ValueError:
                                continue
                            rows.append(r)
                    except OSError:
                        continue
                    hit = [st.st_size, st.st_mtime_ns,
                           max([int(r[0]) + 1 for r in rows]) if rows else None,
                           max([float(r[4]) / 1e6 for r in rows]) if rows else None,
                           [(int(r[0]) + 1, float(r[7])) for r in rows if len(r) > 9 and float(r[7]) >= 0][-40:],
                           [(int(r[0]) + 1, float(r[10]), float(r[11])) for r in rows
                            if len(r) > 11 and float(r[10]) > -1.5 and not (r[10] == r[11] == "-1.0000")][-40:]]
                    fresh += 1
                kept[f] = hit
                if hit[2] is not None:
                    gens.append(hit[2])
                    msteps.append(hit[3])
                yard += [tuple(y) for y in hit[4]]
                ladder += [tuple(x) for x in hit[5]]
            out[name] = {"segments": isl["seg"], "running": (isl.get("queued") or [""])[0], "failures": isl["failures"],
                         "generations": max(gens or [0]),
                         "yard": yard[-1] if yard else None, "yard_curve": yard[-40:], "ladder_curve": ladder[-40:],
                         "msteps": max(msteps or [0])}
        if cache_due(cache_f, fresh, len(cache) - (len(kept) - fresh)):
            keep_cache(cache_f, kept)
        lad = self.ladder_state().get("milestones", [])
        lineage = []
        try:
            lines = open(self.crucible_dir("lineage.tsv")).read().splitlines()
            head = lines[0].split("\t")
            lineage = [dict(zip(head, l.split("\t"))) for l in lines[1:]][-30:]
        except (OSError, IndexError):
            pass
        out["_ladder"] = {"milestones": lad, "rungs": [m["id"] for m in self.ladder_rungs(lad)], "lineage": lineage,
                          "kept": len(glob.glob(self.crucible_dir("champions", "*.bin")))}
        save(os.path.join(self.pd, "crucible.json"), out)

    def plan(self, n):
        # treadcore paused: no promotion, no build, no search; crucible goes on.
        if "treadcore" in self.paused_projects:
            jobs = self.crucible_jobs()
            self.keep()
            print(json.dumps(jobs))
            return
        # The held-out reads whose pieces are all back, made one census each before anything reads them.
        again = self.held_merge()
        self.raise_found()
        # The local line: to main when auto mode is on and the credentials
        # allow (Paul Accepts); else its flag stays up.
        if self.state.get("local_line"):
            self.resolve_flag()
        # Auto mode: results adopted, the strongest candidate promoted, a
        # prepared promotion approved (inside run_jobs). A promotion moves
        # main, so the builds are asked for after it.
        self.adopt_runs()
        self.models_update()
        self.candidate_states()
        self.auto_promote()
        self.retire_stale()
        self.anchor_trial()
        try:
            self.carry_passes()
        except Exception as e:  # a read saved is a gain; a plan lost is not worth one
            print("carry: %s" % e, file=sys.stderr)
        self.reread_older()
        self.rotate()
        jobs = self.net_jobs()
        # What a person asked for comes before the standing search.
        jobs += self.run_jobs(n)
        jobs += again
        jobs = self.prepare_jobs() + jobs
        self.prune_builds()
        try:
            self.clear_promote_worktrees()
        except Exception as e:  # a worktree left is space, not a fault
            print("promote worktrees: %s" % e, file=sys.stderr)
        self.propagation()
        jobs += self.adopt_jobs()
        jobs += self.line_proof()
        jobs += self.rating()
        self.watching()
        jobs += self.width_watch()
        jobs += self.gauntlet_watch()
        self.ticker_scan()
        try:
            self.commits_log()
        except Exception as e:  # the log is for reading; planning goes on
            print("commits: %s" % e, file=sys.stderr)
        # The CPU lanes' share: three queued jobs a CPU machine (the keeper
        # running since 12:28 plans at its half-hourly sync, and a census
        # takes 15 minutes: two a lane between syncs, and one spare). The
        # keeper asks only when its queue is low, and crucible's segments
        # (queued six ahead) and builds waiting behind a long job keep it
        # from looking low: counted against treadcore's share, they left
        # three CPU lanes idle (28 October, 20:40). So the GPU lanes' jobs
        # take none of it, and the share is topped up whatever n says.
        # BUT NEVER PAST FOUR A MACHINE. The keeper asks each minute while a lane is starved, and
        # max(n, ...) answered each time: with the GPU islands off their lanes starved for two
        # days and the queue reached 1,915 jobs, seven hours deep, a held-out read at its back.
        # The queue's order is first come, so depth is how long a finding waits.
        cpu_queued = len([j for j in self.ids("queue") if not j.startswith("x-")])
        want = max(0, self.QUEUE_PER_MACHINE * len(self.hosts) - cpu_queued)
        # The families first, a share of the queue: a candidate waits on them.
        jobs += self.family_jobs(max(0, (want - len(jobs) + 1) // 2))
        try:
            jobs += self.guard_jobs(2)
        except Exception as e:  # a read missed is asked again at the next plan
            print("guard: %s" % e, file=sys.stderr)
        jobs += self.weight_jobs(max(0, want - len(jobs)))
        # The GPU lanes' own work: it takes no treadcore lane.
        jobs += self.crucible_jobs()
        try:
            self.montage_watch()
        except Exception as e:  # a film missed is asked again at the next plan
            print("montage: %s" % e, file=sys.stderr)
        try:
            self.footage_watch()
        except Exception as e:  # footage missed is asked again at the next plan
            print("footage: %s" % e, file=sys.stderr)
        try:
            self.map_watch()
        except Exception as e:  # a line missed is written at the next plan
            print("maps: %s" % e, file=sys.stderr)
        try:
            self.netcard_watch()
        except Exception as e:  # cards missed are written at the next plan
            print("netcards: %s" % e, file=sys.stderr)
        # The rules cloned on the card each time they move (Paul's step 3).
        try:
            jobs += self.clone_jobs()
        except Exception as e:  # a round missed is asked again at the next plan
            print("clone: %s" % e, file=sys.stderr)
        # Their champions read in the game (the bridge, LR 138): two censuses a new world milestone.
        try:
            jobs += self.bridge_jobs()
        except Exception as e:  # a read missed is asked again at the next plan
            print("bridge: %s" % e, file=sys.stderr)
        # The difficulty each plan, whether or not the search was asked.
        note = load(os.path.join(self.pd, "search.json"), {})
        if note:
            self.ease()
            note["difficulty"] = dict(self.state.get("difficulty", {}), last_promotion=(self.promotions() or [[None, None]])[-1][1])
            save(os.path.join(self.pd, "search.json"), note)
        jobs += self.ahead_jobs()
        jobs = self.graph_lint(jobs)
        self.chain_marks(jobs)
        self.model_sends(jobs)
        try:
            self.pipeline_view(jobs)
        except Exception as e:  # the board is for reading; planning goes on
            print("pipeline: %s" % e, file=sys.stderr)
        self.archive_generations()
        self.keep()
        print(json.dumps(jobs))

    @staticmethod
    def chain_marks(jobs):
        """CHAINS ADVANCE WHEN THEY RETURN (the duty-cycle report's change B; Paul, 5 November: "build
        A, then B"). A transform's step and a held-out read are links of a chain whose next link only
        the planner asks for, and it passed each five minutes: a transform's step waited 3.2 minutes for
        the pass and 2.6 in the queue to do 1.8 of work, and thirty of them took 3.8 hours. Such a job
        carries `replan`, and the keeper asks the planner soon after it returns; a transform's step also
        goes ahead of the search's new trials (a held-out read already does). The trials' read-ons are
        left to the pass: a pass each of their 1,500 returns a day would be most of the Mac's core."""
        for j in jobs:
            i = j.get("id", "")
            if re.match(r"r\d+-k\d+$", i) and j.get("title", "").startswith("transform "):
                j["replan"] = True
                j["priority"] = "high"
            elif re.match(r"h\d+(-p\d+(r\d+)?)?$", i) and not j.get("background"):
                # A held-out read, or a piece of one: the last piece back makes the read.
                j["replan"] = True
        return jobs

    # ---- one line of generations --------------------------------------------------------
    # Paul, 1 November: "always progress forward and carry the weights, and restart with new
    # configuration when it resets run". A generation that passes its read joins the line, and
    # the fleet builds the line, so what was found is never searched for again. What the fleet
    # was asked on the old generation's defaults is no use on the new one.
    PROOF_EVERY_MIN = 60
    QUEUE_PER_MACHINE = 4

    def retire_stale(self):
        """Queued searches built for defaults that are no longer today's go to stopped/."""
        here = "/c/%s;" % self.short()
        for f in glob.glob(os.path.join(self.q, "queue", "*.json")):
            j = load(f, {}) or {}
            cmd = j.get("cmd", "")
            if j.get("kind") != "weights" or here in cmd or not re.match(r"[weh]\d+$", j.get("id", "")):
                continue
            m = re.search(r"/c/(\w+);", cmd)
            if m and not self.same_defaults(m.group(1)):
                try:
                    os.rename(f, os.path.join(self.q, "stopped", os.path.basename(f)))
                except OSError:
                    pass

    def line_proof(self):
        """Main's values read as a trial against the line, 800 seeds a read, every read of one line
        against one main pooled. The line past main by HELD_Z, and no map to main's side by two
        errors: the line goes to main. A generation's noise is in that read and cannot pass it by
        luck, one time in 750."""
        line = self.state.get("local_line")
        w = self.cfg.get("weights")
        if not line or not w or not self.auto() or not self.cpu_ready():
            return []
        pf = self.state.setdefault("proof", {})
        known = self.ids("done", "failed", "stopped")
        if pf.get("jobs"):
            if not all(j in known for j in pf["jobs"]):
                return []
            head, jobs, carried, main_then = pf.get("head"), pf["jobs"], pf.get("n"), pf.get("main")
            # POOLED WHILE THE QUESTION STANDS (Paul, 4 November: "yes pool the reads"). A proof inside
            # the noise was read again an hour later on fresh seeds and judged alone: r0179's line read
            # -0.23 +/- 0.22 at 19:54, and the next hour would have asked the same question anew, 17
            # machine-minutes each time, and each time given a line that changes nothing a new one in
            # 750 to pass by luck. Now the reads of one line against one main are one read: each proof
            # adds its seeds to those before it, the error narrows as they grow, and a commit on either
            # side (a generation on the line, a commit to main) starts the pool again, because a commit
            # can change the game. A proof made before the pool knew its main pools with nothing.
            before = pf.get("pooled") or {}
            # KEYED ON WHAT THE GAME IS, NOT ON THE COMMITS (Outgrowing Yourself, recommendation 4; Paul,
            # 6 November: "The polling technique was a good idea"): a push to main replays the line and
            # gives it a new head, and a report pushed to main restarted the pool -- 6 of the 26 heads the
            # proof read had the same generations as the head before. The question is main's game against
            # the line's: the source trees of both. A report, a doc or a film changes neither and the pool
            # goes on; a change to the game's code changes one and the pool starts again, as it should.
            key = pf.get("key")
            # A pool from before the key (or a proof asked without one) is matched the old way, by head and
            # main, so the reads it holds are not thrown away at the change.
            same = bool(main_then) and ((key and before.get("key") == key) or
                                        ((not key or not before.get("key")) and before.get("head") == head and before.get("main") == main_then))
            reads = ((before.get("jobs") or []) if same else []) + jobs

            def found(js):
                return [d for j in js for d in glob.glob(os.path.join(self.q, "results", j, self.home, "out", j, "*", ""))]
            ds = found(reads)
            p = self.pool(ds) if len(found(jobs)) == len(jobs) else None
            self.state["proof"] = pf = {"last_at": time.time(), "pooled": {"head": head, "main": main_then, "key": key, "jobs": reads}}
            if p and p["every"][1] > 0:
                d, se, n_ = p["every"]
                pf["last"] = {"head": head[:7], "d": round(-d, 2), "se": round(se, 2), "z": round(-d / se, 2), "seeds": n_, "reads": len(reads) // 2}
                # THE COMMIT IT READ, NOT THE LINE'S HEAD NOW (1 November). A proof takes a quarter of an
                # hour, and at this pace a generation lands inside it: 94a99be read z 4.82 past main and
                # went nowhere, because two more had landed. So what was proved goes on main, and what
                # came after waits for its own proof. Only if it is still on the line: a commit to main
                # replays the line under new hashes, and then this read is of no commit that remains.
                on_line = head and run(["git", "-C", self.tc, "merge-base", "--is-ancestor", head, line.get("commit", "")]).returncode == 0
                lost, worst, verdict = self.trade(ds, sign=-1, gain=-d) if -d / se >= self.HELD_Z and not p["above"] and on_line else ([], 0.0, None)
                if verdict == "past":
                    # Refused by itself: the line stays the fleet's working line, and the next proof reads it
                    # again with whatever has landed on it since.
                    self.flag("trade", "the line %s reads %+.2f past main but gives up %s, %.1f times its floor: refused by the trade rule (it allows %.1f); "
                              "the fleet works on from the line and the next proof reads it again" % (head[:7], -d, ", ".join(lost), worst, self._allow),
                              key="trade-line:%s" % head[:12], progress=True)
                elif -d / se >= self.HELD_Z and not p["above"] and on_line:
                    if verdict == "within":
                        self.flag("trade", "the line %s goes to main by the trade rule: %+.2f past main, and it gives up %s, %.1f times its floor (the rule allows %.1f)" % (
                            head[:7], -d, ", ".join(lost), worst, self._allow), key="trade-line:%s" % head[:12], progress=True)
                    try:
                        with contextlib.redirect_stdout(sys.stderr):
                            self.resolve(upto=head, carried=carried)
                        self.flag("promote", "the line %s proved past main: %+.2f +/- %.2f over %d seeds; it is main now" % (head[:7], -d, se, n_),
                                  key="proved:%s" % head[:12], progress=True)
                    except SystemExit as e:
                        print("resolve: %s" % e, file=sys.stderr)
                    return []
                if self.SETTLE_SEEDS and n_ >= self.SETTLE_SEEDS and -d + 2 * se < self.MIN_GAIN and self.orphan(head, -d, se, n_):
                    return []
                if d / se >= 2:
                    self.flag("line", "the line %s reads %+.2f +/- %.2f against main over %d seeds: under it; the anchor reads should undo it" % (head[:7], -d, se, n_),
                              key="line-under:%s" % head[:12])
        # A head still settling is read at once and more at a time: nothing may join the line until it is.
        settling = bool(self.settling())
        if (not settling and time.time() - pf.get("last_at", 0) < self.PROOF_EVERY_MIN * 60) or self._built_everywhere() is False:
            return []
        remote, branch = self.push_target()
        main = run(["git", "-C", self.tc, "rev-parse", "%s/%s" % (remote, branch)]).stdout.strip()
        a, b = self.defaults_at(main), self.defaults_at(line["commit"])
        vals = {k: a.get(k) for k in set(a) | set(b) if a.get(k) != b.get(k)}
        lines = ["%s = %s" % (k, v) for k, v in sorted(vals.items()) if not k.startswith("caps:") and v is not None]
        caps = [("" if vals[k] in (1, 1.0, "1") else "-") + k[5:] for k in sorted(vals) if k.startswith("caps:")]
        if caps:
            lines.append("caps = baseline, " + ", ".join(caps))
        if not lines:
            return []
        text = "# the line's proof: main's values, read as a trial against the line\n" + "\n".join(lines) + "\n"
        jobs = []
        pooled = pf.get("pooled") or {}
        key = [self.src_tree(line["commit"]), self.src_tree(main)]
        key = key if all(key) else None
        nth = len(pooled.get("jobs") or []) // 2 + 1 if ((key and pooled.get("key") == key) or (pooled.get("head"), pooled.get("main")) == (line["commit"], main)) else 1
        for k in range(self.SETTLE_JOBS if settling else 2):
            n_ = self.state["proof_n"] = self.state.get("proof_n", 0) + 1
            jid = "pv%04d" % n_
            jobs.append({"id": jid, "kind": "weights", "title": "proof %d of the line %s against main (%d seeds%s)" % (
                         k + 1, line["commit"][:7], w["held_seeds"], ", read %d, pooled" % nth if nth > 1 else ""),
                         "needs": self.long_needs(), "after_host": self.after_host(), "cmd": self.census_cmd(text, w["held_seeds"], 700000000 + 200000 * n_, jid),
                         "fetch": "%s/out/%s" % (self.home, jid), "timeout_s": 6 * 3600, "priority": "high"})
        pf.update({"jobs": [j["id"] for j in jobs], "head": line["commit"], "main": main, "key": key, "n": len(line.get("promotions", []))})
        return jobs

    # THE FIXED YARDSTICK (Paul, 13 November: "The fixed yardstick"; Always Forward, step 4). Every read the
    # line makes is of a child against its parent, and a chain of those cannot say whether the brain is
    # stronger than it was a week ago: from 6 to 13 November ten generations each beat their parent on
    # their day and together beat nothing. So once a day today's defaults are read against main as it
    # stood on fixed days, each as a trial of its values on today's game, RATING_SEEDS seeds, AND THE
    # SAME SEEDS EVERY DAY, so a day's difference is the brain's and not the draw's. plan/rating.json
    # keeps every row. It decides nothing and promotes nothing: it is the record that only moves when
    # strength does, and where a generation that beats its parent and loses to its grandparent shows.
    # A dial the old main did not have stays at today's value: it is today's code with that day's numbers.
    RATING_EVERY_H = 24
    RATING_SEEDS = 2000
    RATING_BRAINS = (("28 Oct", "dc3df01"), ("2 Nov", "da7e1da"), ("6 Nov", "63f2667"))

    def rating(self):
        w = self.cfg.get("weights")
        if not w or not self.RATING_SEEDS or not self.auto() or not self.cpu_ready():
            return []
        rt = self.state.setdefault("rating", {})
        f = os.path.join(self.pd, "rating.json")
        rnd = rt.get("round")
        if rnd:
            known = self.ids("done", "failed", "stopped")
            if not all(j in known for b in rnd["brains"] for j in b["jobs"]):
                return []
            doc = load(f, {}) or {}
            rows, said = doc.setdefault("rows", []), []
            for b in rnd["brains"]:
                ds = [d for j in b["jobs"] for d in glob.glob(os.path.join(self.q, "results", j, self.home, "out", j, "*", ""))]
                p = self.pool(ds) if ds else None
                if p and p["every"][1] > 0:
                    d, se, n_ = p["every"]
                    rows.append({"at": rnd["at"], "today": rnd["today"][:7], "against": b["sha"][:7], "label": b["label"],
                                 "lead": round(-d, 3), "se": round(se, 3), "seeds": n_, "dials": b.get("dials")})
                    said.append("%+.2f +/- %.2f over main of %s" % (-d, se, b["label"]))
            save(f, doc)
            rt.update({"round": None, "last_at": time.time()})
            if said:
                self.flag("rating", "the yardstick, %s at %s: today's defaults read %s" % (rnd["at"][:10], rnd["today"][:7], "; ".join(said)),
                          key="rating:%s" % rnd["at"], progress=True)
            return []
        if time.time() - rt.get("last_at", 0) < self.RATING_EVERY_H * 3600 or self._built_everywhere() is False:
            return []
        today = self.sha()
        now_, per = self.defaults_at(today), w["held_seeds"]
        brains, jobs = [], []
        for bi, (label, ref) in enumerate(self.RATING_BRAINS):
            old = run(["git", "-C", self.tc, "rev-parse", "--verify", "-q", ref + "^{commit}"]).stdout.strip()
            then = self.defaults_at(old) if old else {}
            vals = {k: v for k, v in then.items() if k in now_ and now_[k] != v}
            lines = ["%s = %s" % (k, v) for k, v in sorted(vals.items()) if not k.startswith("caps:")]
            caps = [("" if vals[k] in (1, 1.0) else "-") + k[5:] for k in sorted(vals) if k.startswith("caps:")]
            if caps:
                lines.append("caps = baseline, " + ", ".join(caps))
            if not lines:
                continue
            text = "# the yardstick: main's values of %s (%s), read as a trial against today's\n" % (label, old[:7]) + "\n".join(lines) + "\n"
            ids = []
            for i in range(max(1, self.RATING_SEEDS // per)):
                n_ = self.state["rating_n"] = self.state.get("rating_n", 0) + 1
                jid = "rt%04d" % n_
                # The same seeds each day, each brain and piece its own block of them.
                jobs.append({"id": jid, "kind": "weights", "title": "the yardstick: main of %s (%s) against today's %s, piece %d (%d seeds)" % (label, old[:7], today[:7], i + 1, per),
                             "needs": self.long_needs(), "after_host": self.after_host(), "cmd": self.census_cmd(text, per, 800000000 + 1000000 * bi + 10000 * i, jid),
                             "fetch": "%s/out/%s" % (self.home, jid), "timeout_s": 6 * 3600})
                ids.append(jid)
            brains.append({"label": label, "sha": old, "jobs": ids, "dials": len(vals)})
        if brains:
            rt["round"] = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "today": today, "brains": brains}
        else:
            rt["last_at"] = time.time()
        return jobs

    # THE WATCH, BY ITSELF (Paul, 13 November, of The First Morning's first open item: "the watch is run by
    # hand ... a BAD is seen only by whoever runs it"). Every WATCH_EVERY_MIN the planner reads
    # tools/deploy-watch.py's checks, keeps them in plan/deploy-watch.json for a page to draw, and
    # raises a flag for each that reads BAD: a mechanism doing what it must not is a person's to see,
    # the same hour, on the Flags page. A LOOK is kept and not flagged. It moves nothing.
    WATCH_EVERY_MIN = 10

    def watching(self):
        if not self.WATCH_EVERY_MIN or time.time() - self.state.get("watched_at", 0) < self.WATCH_EVERY_MIN * 60:
            return
        self.state["watched_at"] = time.time()
        try:
            sp = importlib.util.spec_from_file_location("deploy_watch", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "deploy-watch.py"))
            dw = importlib.util.module_from_spec(sp)
            sp.loader.exec_module(dw)
            doc = dw.watch(self.q)
        except Exception as e:  # the watch is for reading; planning goes on
            print("watch: %r" % e, file=sys.stderr)
            return
        save(os.path.join(self.pd, "deploy-watch.json"), doc)
        for c in doc["checks"]:
            if c["level"] == "BAD":
                self.flag("watch", "the watch reads BAD on %s: %s" % (c["name"], c["words"]), key="watch:%s:%s" % (c["name"], time.strftime("%Y-%m-%d %H")))

    def src_tree(self, commit):
        """The tree of the game's source at a commit: what a proof's question is about."""
        return run(["git", "-C", self.tc, "rev-parse", "%s:source" % commit]).stdout.strip() or None

    # ---- the board: one process, one screen ------------------------------------------------
    # Paul, 1 November: "a single coherent process ... like a gantt chart, showing dependency,
    # machine name, and expected duration, and their sequence with arrows ... Agile Kanban ...
    # the one with most dependencies denoted as next essential". plan/pipeline.json is the whole
    # document; orrery's Pipeline view draws it and decides nothing. Durations are the medians
    # the fleet measured, never a hope, and a task nobody has built says "not built".
    @staticmethod
    def board(tasks, generation=None):
        """Tasks in, with dependents, a schedule from now, and next essential. Each task: id,
        title, state (done, running, ready, waiting, blocked, not built), deps, dur_min,
        elapsed_min. A blocked task outranks a healthy one; among them, most dependents wins."""
        by = {x["id"]: x for x in tasks}
        kids = {x["id"]: [] for x in tasks}
        for x in tasks:
            for d in x["deps"]:
                kids[d].append(x["id"])

        def down(i, seen):
            for k in kids[i]:
                if k not in seen:
                    seen.add(k)
                    down(k, seen)
            return seen
        order, seen = [], set()

        def visit(i):
            if i not in seen:
                seen.add(i)
                for d in by[i]["deps"]:
                    visit(d)
                order.append(i)
        for x in tasks:
            visit(x["id"])
        for i in order:
            x = by[i]
            x["dependents"] = len([k for k in down(i, set()) if by[k]["state"] != "done"])
            start = max([by[d]["end_min"] for d in x["deps"]] or [0.0])
            dur = float(x.get("dur_min") or 0)
            if x["state"] == "done":
                x["start_min"], x["end_min"] = 0.0, 0.0
            elif x["state"] == "running":
                x["start_min"] = -float(x.get("elapsed_min") or 0)
                x["end_min"] = max(start, 0.0) + max(dur - float(x.get("elapsed_min") or 0), dur * 0.1)
            else:
                x["start_min"], x["end_min"] = start, start + dur
            x["essential"] = False
        open_ = [x for x in tasks if x["state"] != "done"]
        stuck = [x for x in open_ if x["state"] in ("blocked", "not built")] or open_
        if stuck:
            max(stuck, key=lambda x: (x["dependents"], -tasks.index(x)))["essential"] = True
        return tasks

    def pipeline_view(self, new_jobs=()):
        since = time.time() - 86400
        secs, last, recent = {}, {}, []
        for f in glob.glob(os.path.join(self.q, "done", "*.json")):
            if os.path.getmtime(f) < since:
                continue
            j = load(f, {}) or {}
            recent.append(j)
            k = self.task_of(j)
            if k:
                secs.setdefault(k, []).append(j.get("seconds", 0))
                last[k] = max(last.get(k, ""), j.get("ended", ""))
        med = lambda k, d: (st.median(secs[k]) / 60.0 if secs.get(k) else d)
        lanes = {}
        for f in glob.glob(os.path.join(self.q, "lanes", "*.json")):
            l = load(f, {}) or {}
            lanes[os.path.basename(f)[:-5]] = l
        names = {h["name"] for h in self.qcfg.get("hosts", [])}
        live = {n: l for n, l in lanes.items() if n in names}
        cpu = sorted(h["name"] for h in self.hosts)
        cpu_up = [n for n in cpu if live.get(n, {}).get("state") not in ("unreachable", "stopped", "removed", None)]
        n_up = max(1, len(cpu_up))
        queued, on = {}, {}
        for j in self.queue_jobs():
            k = self.task_of(j)
            if k:
                queued.setdefault(k, []).append(j)
        for n, l in live.items():
            if l.get("job"):
                k = self.task_of(l)
                if k:
                    on.setdefault(k, []).append((n, l))
        d = dict(self.state.get("difficulty", {}))
        line = self.state.get("local_line") or {}
        proof = self.state.get("proof") or {}
        short = self.short()
        built = [h for h in self.hosts if self.prepared(h["name"])]
        promote_lane = "mac" in names

        def state(k, deps_done=True, blocked=None):
            if blocked:
                return "blocked"
            if on.get(k):
                return "running"
            if queued.get(k) or deps_done:
                return "ready" if deps_done else "waiting"
            return "waiting"

        def machines(k, dflt):
            return sorted({n for n, _ in on.get(k, [])}) or dflt

        def elapsed(k):
            return max([(time.time() - l.get("since", time.time())) / 60 for _, l in on.get(k, [])] or [0])

        down = sorted(n for n in cpu if n not in cpu_up)
        # A CANDIDATE THAT PASSED AND WAS STOPPED BY A TEST IS THE LINE STOPPED, however busy every
        # lane looks: the search goes on and nothing is carried. It says so where a person looks.
        autos = [r for r in self.runs() if r["kind"] == "promote"]
        stopped_by = None
        if autos:
            last_run = self.rstate(autos[-1]["id"])
            if last_run.get("status") == "failed":
                stopped_by = "%s stopped %s: %s" % (autos[-1]["id"], (autos[-1].get("params") or {}).get("candidate", ""), (last_run.get("why") or "")[:100])
        tasks = [
            {"id": "build", "title": "Build the generation", "track": "brain", "deps": [], "state": "done" if len(built) == len(self.hosts) else state("build"),
             "machines": [h["name"] for h in self.hosts if not self.prepared(h["name"])] or cpu, "dur_min": med("build", 1.0), "elapsed_min": elapsed("build"),
             "note": "%s on %d of %d machines" % (short, len(built), len(self.hosts))},
            {"id": "search", "title": "Trials: the fit and the A/B", "track": "brain", "deps": ["build"], "state": state("search"), "machines": machines("search", cpu),
             "dur_min": med("search", 3.0) * (1 + len(queued.get("search", [])) / n_up), "elapsed_min": elapsed("search"),
             "note": "%d queued, %d running" % (len(queued.get("search", [])), len(on.get("search", [])))},
            {"id": "read", "title": "Read on until decided", "track": "brain", "deps": ["search"], "state": state("read"), "machines": machines("read", cpu),
             "dur_min": med("read", 2.0) * (1 + len(queued.get("read", [])) / n_up), "elapsed_min": elapsed("read"),
             "note": "%d queued, %d running" % (len(queued.get("read", [])), len(on.get("read", [])))},
            {"id": "held", "title": "Held-out read, 400 seeds", "track": "brain", "deps": ["read"], "state": state("held", bool(queued.get("held"))), "machines": machines("held", cpu),
             "dur_min": med("held", 15.0), "elapsed_min": elapsed("held"), "note": "passes at z %.2f; %d waiting" % (d.get("held_z", 0), len(queued.get("held", [])))},
            {"id": "families", "title": "Families hold their floors", "track": "brain", "deps": ["held"], "state": state("families", bool(queued.get("families"))), "machines": machines("families", cpu),
             "dur_min": med("families", 10.0), "elapsed_min": elapsed("families"), "note": "%d waiting" % len(queued.get("families", []))},
            {"id": "promote", "title": "Tests, then carried on the line", "track": "brain", "deps": ["families"],
             "state": state("promote", bool(queued.get("promote")), stopped_by if not on.get("promote") and not queued.get("promote") else None if promote_lane or not queued.get("promote") else "no lane"),
             "machines": ["mac"], "dur_min": med("promote", 2.0), "elapsed_min": elapsed("promote"),
             "note": stopped_by or ("no lane can take it: the Mac's is off" if queued.get("promote") and not promote_lane else "generation %d this run" % d.get("generations", 0))},
            {"id": "proof", "title": "The line read against main", "track": "brain", "deps": ["promote"], "state": state("proof", bool(line)), "machines": machines("proof", cpu),
             "dur_min": 2 * med("proof", med("held", 15.0)) / min(2, n_up), "elapsed_min": elapsed("proof"),
             "note": ("%d generation(s) on the line, last read %s" % (len(line.get("promotions", [])), json.dumps(proof.get("last")) if proof.get("last") else "not yet")) if line else "main has every generation"},
            {"id": "main", "title": "Main: the game's brain", "track": "brain", "deps": ["proof"], "state": "waiting" if line else "done", "machines": ["mac"], "dur_min": 1.0,
             "note": "z %.1f past main to go on it" % self.HELD_Z},
            {"id": "transform", "title": "Transform: learned override", "track": "transform", "deps": ["build"], "state": state("transform", True), "machines": machines("transform", cpu),
             "dur_min": med("transform", 3.0) * 100, "elapsed_min": elapsed("transform"), "note": "SPSA over 942 numbers, a census a step"},
            {"id": "slot", "title": "The game reads a transform", "track": "transform", "deps": ["transform"], "state": "done", "machines": [], "dur_min": 0,
             "note": "built: styles.rs ships slot 1, as style 5, Overrider; a person chooses it on the menu"},
            {"id": "islands", "title": "GPU islands: crucible", "track": "gpu", "deps": [], "state": state("islands", True), "machines": sorted(h["name"] for h in self.cuda),
             "dur_min": med("islands", 1.0) * 6, "elapsed_min": elapsed("islands"), "note": "its own arena, senses and net"},
            {"id": "bridge", "title": "Bridge: crucible into treadcore", "track": "gpu", "deps": ["islands"],
             "state": "running" if (self.state.get("bridge") or {}).get("current") else "done",
             "machines": [(self.state.get("bridge") or {}).get("current", {}).get("host")] if (self.state.get("bridge") or {}).get("current") else [],
             "dur_min": 2 * med("read", 15.0),
             "note": (self.state.get("bridge") or {}).get("note") or "a world champion reads in the game as style 17, Gladiator; style 7 keeps the hybrid"},
            {"id": "clone", "title": "The rules cloned on the card", "track": "gpu", "deps": ["build"],
             "state": "running" if (self.state.get("clone") or {}).get("current") else "done", "machines": [h["name"] for h in self.hosts if "gpu" in h.get("caps", [])][:1],
             "dur_min": 3 * med("read", 15.0), "note": (self.state.get("clone") or {}).get("note") or "a fresh clone of the rules each time main moves, judged against the Scholar"},
            {"id": "brain", "title": "One brain in treadcore", "track": "brain", "deps": ["main", "slot", "bridge", "clone"], "state": "waiting", "machines": [], "dur_min": 0, "note": "rules, dials and learned parts, chosen by name: bot styles 0 to 7"},
        ]
        self.board(tasks)
        doc = {"checked": time.strftime("%Y-%m-%dT%H:%M:%S"), "commit": short, "difficulty": d, "tasks": tasks, "down": down,
               "line": {"promotions": len(line.get("promotions", [])), "commit": (line.get("commit") or "")[:7]}, "proof": proof.get("last")}
        # Each is for reading, and each alone may fail: the board above must still be written.
        for name, part in (("values", self.values_view), ("flow", lambda: self.flow_view(recent)), ("timeline", lambda: self.timeline_view(recent, live)),
                           ("queued", lambda: self.queued_view(live)), ("traces", lambda: self.trace_view(recent)),
                           ("blame", lambda: self.blame_view(live, doc.get("timeline") or {}, recent)),
                           # The dials a person holds (hold.json): the Values page shows them with a Release.
                           ("held", lambda: load(os.path.join(self.q, "hold.json"), {}) or {})):
            try:
                doc[name] = part()
            except Exception as e:
                print("pipeline %s: %s" % (name, e), file=sys.stderr)
        save(os.path.join(self.pd, "pipeline.json"), doc, compact=True)

    @staticmethod
    def stage_of(i, title=""):
        """Which stage of line.json a job is, by its id and title. The GPU's, the builds' and
        the runs' each have a shape; a job nothing names is `other`, and says so."""
        if i.startswith("prep-"):
            return "build"
        if i.startswith("x-"):
            return "islands"
        if i.startswith("pv"):
            return "proof"
        if re.match(r"f\d+$", i):
            return "families"
        if i.endswith("-promote"):
            return "promote"
        if re.match(r"r\d+-k\d+", i):
            return "transform"
        if re.match(r"h\d+(-p\d+(r\d+)?)?$", i):
            return "held"
        if re.match(r"e\d+$", i):
            return "read"
        if re.match(r"w\d+$", i):
            return "anchor" if title.startswith("anchor") else "first"
        return "other"

    def archive_generations(self):
        """A generation's record is written when it is made, not when someone remembers: a promotion
        since the last look runs fleet-archive's snapshot, which is a fraction of a second of text."""
        try:
            done = [r for r in self.runs() if r["kind"] == "promote" and self.rstate(r["id"]).get("status") in ("approved", "self-modified", "failed")]
            if len(done) != self.state.get("archived"):
                tool = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fleet-archive.py")
                if run([sys.executable, tool, self.q, "snapshot"]).returncode == 0:
                    self.state["archived"] = len(done)
        except Exception as e:  # the record is for keeping; planning goes on
            print("archive: %s" % e, file=sys.stderr)

    def values_view(self):
        """Each value of line.json as the run has it now: its number and whether a person moved it."""
        d = self.state.get("difficulty", {})
        out = []
        for v in self.line.get("values", []):
            if v["key"] == "ease_now":
                now_ = d.get("base", v["default"])
            elif v["key"] == "held_seeds":
                now_ = (self.cfg.get("weights") or {}).get("held_seeds", v["default"])
            elif v.get("attr"):
                now_ = getattr(self, v["attr"], v["default"])
            else:
                # A value another tool reads (growth.py's size_warn_gb): tuning.json's, or its default.
                # Read by name, it stopped this page's whole table from 4 November (getattr of None).
                now_ = self.tuned.get(v["key"], v["default"])
            out.append({"key": v["key"], "value": round(now_, 3), "moved": v["key"] in self.tuned})
        return out

    def flow_view(self, recent):
        """Per stage, the last day and the moment: jobs finished, machine-hours, waiting, running."""
        out = {}
        for j in recent:
            k = self.stage_of(j.get("id", ""), j.get("title", ""))
            r = out.setdefault(k, {"jobs": 0, "hours": 0.0, "queued": 0, "running": 0})
            r["jobs"] += 1
            r["hours"] += (j.get("seconds") or 0) / 3600.0
        for j in self.queue_jobs():
            out.setdefault(self.stage_of(j.get("id", ""), j.get("title", "")), {"jobs": 0, "hours": 0.0, "queued": 0, "running": 0})["queued"] += 1
        for f in glob.glob(os.path.join(self.q, "running", "*", "*.json")):
            j = load(f, {}) or {}
            out.setdefault(self.stage_of(j.get("id", ""), j.get("title", "")), {"jobs": 0, "hours": 0.0, "queued": 0, "running": 0})["running"] += 1
        for r in out.values():
            r["hours"] = round(r["hours"], 1)
        return out

    TIMELINE_H = 6

    def timeline_view(self, recent, live):
        """Each lane: what it did (from the event log, measured), what it does, and what it would
        do next: the queue dealt to the lanes in its own order at the medians of the last day. THE
        RIGHT SIDE IS A FORECAST AND SAYS SO: no job is assigned until a lane is free to take it."""
        now_, since = time.time(), time.time() - self.TIMELINE_H * 3600
        path = os.path.join(self.q, "events.jsonl")
        with open(path, "rb") as f:
            f.seek(max(0, os.path.getsize(path) - 3000000))
            lines = f.read().split(b"\n")[1:]
        parse = lambda t: time.mktime(time.strptime(t, "%Y-%m-%dT%H:%M:%S"))
        titles = {j.get("id"): j.get("title", "") for j in recent}
        bars, open_ = {}, {}
        # Busy minutes by stage, each job as measured (the bars below merge what touches).
        busy = {}
        # And each job alone, with the chain it is a link of, for the page to follow one through, and
        # the job it follows where the titles cannot say (a bridge read after its milestone's segment).
        each, extra = {}, self.chain_extra()
        link = lambda job, title: list(extra[job]) if job in extra else [self.chain_of(job, title), ""]
        for l in lines:
            try:
                e = json.loads(l)
            except ValueError:
                continue
            ev, job = e.get("event"), e.get("job")
            if ev == "planned" and e.get("seconds"):
                t1 = parse(e["t"])
                if t1 >= since:
                    t0 = t1 - float(e["seconds"])
                    bars.setdefault("orchestrator", []).append([round((max(t0, since) - now_) / 60, 1), round((t1 - now_) / 60, 1), "plan", 1])
                    by = busy.setdefault("orchestrator", {})
                    by["plan"] = round(by.get("plan", 0.0) + (t1 - max(t0, since)) / 60, 1)
                continue
            if not job:
                continue
            if ev == "started":
                open_[job] = (parse(e["t"]), e.get("host"))
            elif ev in ("done", "failed", "stopped", "requeued") and job in open_:
                t0, host = open_.pop(job)
                t1 = parse(e["t"])
                if t1 >= since and host:
                    k = self.stage_of(job, titles.get(job, ""))
                    bars.setdefault(host, []).append([round((max(t0, since) - now_) / 60, 1), round((t1 - now_) / 60, 1), k, 1 if ev == "done" else 0])
                    each.setdefault(host, []).append([round((max(t0, since) - now_) / 60, 2), round((t1 - now_) / 60, 2), k, 1 if ev == "done" else 0,
                                                      job] + link(job, titles.get(job, "")))
                    by = busy.setdefault(host, {})
                    by[k] = round(by.get(k, 0.0) + (t1 - max(t0, since)) / 60, 1)
        med = {}
        for j in recent:
            med.setdefault(self.stage_of(j.get("id", ""), j.get("title", "")), []).append((j.get("seconds") or 0) / 60.0)
        dur = lambda k: st.median(med[k]) if med.get(k) else 5.0
        hosts, free, future = [h["name"] for h in self.qcfg.get("hosts", [])], {}, {}
        for n in hosts:
            l = live.get(n, {})
            free[n] = None if l.get("state") in ("unreachable", "stopped", "removed", None) else 0.0
            if l.get("job"):
                k = self.stage_of(l["job"], l.get("title", ""))
                gone = (now_ - l.get("since", now_)) / 60
                left = max(dur(k) - gone, dur(k) * 0.1)
                bars.setdefault(n, []).append([round(-gone, 1), 0.0, k, 2])
                each.setdefault(n, []).append([round(-min(gone, self.TIMELINE_H * 60), 2), 0.0, k, 2, l["job"]] + link(l["job"], l.get("title", "")))
                future.setdefault(n, []).append([0.0, round(left, 1), k])
                free[n] = left
                by = busy.setdefault(n, {})
                by[k] = round(by.get(k, 0.0) + min(gone, self.TIMELINE_H * 60), 1)
        cpu = [h["name"] for h in self.qcfg.get("hosts", []) if "cpu" in h.get("caps", ["cpu"]) and free.get(h["name"]) is not None]
        dealt, dealt_at = {}, {}
        for j in self.queue_jobs():
            need = j.get("needs") or "cpu"
            pool = [need[5:]] if need.startswith("host:") else cpu if need == "cpu" else [n for n in hosts if free.get(n) is not None and need in next(h.get("caps", []) for h in self.qcfg["hosts"] if h["name"] == n)]
            pool = [n for n in pool if free.get(n) is not None]
            if not pool:
                continue
            n = min(pool, key=lambda x: free[x])
            k = self.stage_of(j.get("id", ""), j.get("title", ""))
            future.setdefault(n, []).append([round(free[n], 1), round(free[n] + dur(k), 1), k])
            dealt_at[j.get("id", "")] = [round(free[n], 1), round(free[n] + dur(k), 1)]
            free[n] += dur(k)
            dealt[j.get("id", "")] = n
        # Every milestone of three months: the page shows those its zoom reaches.
        marks = self.timeline_marks(now_)
        d = self.state.get("difficulty", {})
        if d.get("eases_at_min") is not None and d.get("dry_min") is not None:
            marks.append({"at": round(d["eases_at_min"] - d["dry_min"], 1), "kind": "eases", "text": "easier"})
        pf = self.state.get("proof") or {}
        if self.state.get("local_line") and pf.get("last_at") and not pf.get("jobs"):
            marks.append({"at": round(max(0.0, (pf["last_at"] + self.PROOF_EVERY_MIN * 60 - now_) / 60), 1), "kind": "proof", "text": "proof"})
        lanes = []
        for n in hosts:
            lanes.append({"host": n, "up": free.get(n) is not None, "past": self.merge_bars(bars.get(n, [])), "next": future.get(n, [])[:12],
                          "jobs": sorted(each.get(n, []))})
        # The Orchestrator's own row: Orrery's planner passes, on the Mac the keeper runs on.
        lanes.append({"host": "orchestrator", "up": True, "past": self.merge_bars(bars.get("orchestrator", [])), "next": [], "jobs": []})
        hosts = hosts + ["orchestrator"]
        seg_min = {n: round(st.median([j[1] - j[0] for j in each.get(n, []) if j[2] == "islands" and j[3] == 1]), 1)
                   for n in hosts if any(j[2] == "islands" and j[3] == 1 for j in each.get(n, []))}
        # Its own clock: every minute on the page is from this moment, not the pass's start.
        bins = self.timeline_bins()
        try:
            P = power_mod()
            pm = P.model()
            power = (P, pm, P.calib(pm, P.samples(self.q, now_ - 3 * 86400)))
        except Exception as e:
            print("power: %s" % e, file=sys.stderr)
            power = None
        zoom = self.zoom_view(bins, hosts, now_, power)
        out = {"past_h": self.TIMELINE_H, "at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now_)), "lanes": lanes, "marks": marks, "busy": busy, "dealt": dealt, "dealt_at": dealt_at,
               "zoom": zoom, "cuda": self.cuda_return(now_, seg_min)}
        try:
            out["chains"] = self.chain_meta(lanes, dealt, dealt_at, now_)
        except Exception as e:
            print("chains: %s" % e, file=sys.stderr)
        try:
            out["parade"] = self.parade_view(bins, now_)
        except Exception as e:
            print("parade: %s" % e, file=sys.stderr)
        if power:
            try:
                out["power"] = self.power_view(now_, zoom, bins, live, hosts)
                # Each job's watt-hours, its lane's watts busy for the minutes it ran.
                for l in lanes:
                    bw = out["power"]["lane_busy_w"].get(l["host"]) or 0
                    for j in l["jobs"]:
                        j.append(round(bw * (j[1] - j[0]) / 60, 1))
            except Exception as e:
                print("power: %s" % e, file=sys.stderr)
        return out

    # ---- the Timeline zoomed out (Paul, 5 November: "maybe we can zoom timeline in and out.
    # months, weeks, days, day, hours, hour"), its milestones, and when the GPU hands anything on --
    # The hour and the six hours are drawn from each job; a day and more from bins of the event log,
    # each bin the share of its time a machine spent in each stage.
    BIN_FINE_S, BIN_COARSE_S, BIN_FINE_DAYS = 300, 3600, 14
    # (name, hours shown, seconds a bin, which bins it is made of)
    ZOOMS = (("day", 24, 300, "fine"), ("days", 7 * 24, 1800, "fine"), ("weeks", 28 * 24, 7200, "coarse"), ("months", 91 * 24, 21600, "coarse"))

    def timeline_bins(self):
        """Busy seconds by machine, stage and bin, read on from where the last pass stopped in the
        event log (plan/timeline-bins.json): five-minute bins for two weeks, hours for always. Time
        a job failed, stopped or was sent back is `failed`, whatever its stage, as the hours draw it."""
        path, keep = os.path.join(self.q, "events.jsonl"), os.path.join(self.pd, "timeline-bins.json")
        c = load(keep, {}) or {}
        try:
            size = os.path.getsize(path)
        except OSError:
            return c
        if c.get("v") != 5 or c.get("offset", 0) > size:
            c = {"v": 5, "offset": 0, "open": {}, "fine": {}, "coarse": {}, "first": None, "energy": {}, "down": {}, "tally": {}}
        # EACH JOB'S ENERGY AS IT IS HANDED OFF (Paul, 5 November: "have each computer report its power
        # estimate participation ... as it hands it off"): its lane's watts while busy (power.py: a CPU
        # lane its box's rest and CPU at the use measured, a GPU lane its card as measured) for the
        # time it ran, added to its day and lane: [jobs, watt-hours].
        try:
            P = power_mod()
            pm = P.model()
            cal = P.calib(pm, P.samples(self.q, time.time() - 3 * 86400))
            busy_w = lambda lane: P.lane_watts(pm, cal, lane, 1.0)
        except Exception:  # the bins are for drawing; watts are an extra
            busy_w = lambda lane: None
        with open(path, "rb") as f:
            f.seek(c["offset"])
            data = f.read()
        whole = data.rfind(b"\n") + 1
        parse = lambda t: time.mktime(time.strptime(t, "%Y-%m-%dT%H:%M:%S"))

        def add(host, k, t0, t1):
            for name, w in (("fine", self.BIN_FINE_S), ("coarse", self.BIN_COARSE_S)):
                lane, b = c[name].setdefault(host, {}), int(t0 // w)
                while b * w < t1:
                    part = min(t1, (b + 1) * w) - max(t0, b * w)
                    if part > 0:
                        cell = lane.setdefault(str(b), {})
                        cell[k] = round(cell.get(k, 0) + part, 1)
                    b += 1
        for l in data[:whole].split(b"\n"):
            if b'"job"' not in l and b'"host"' not in l and b'"planne' not in l:
                continue
            try:
                e = json.loads(l)
                t = parse(e["t"])
            except (ValueError, KeyError):
                continue
            c["first"] = c.get("first") or t
            ev, job = e.get("event"), e.get("job")
            # A MACHINE OFF DRAWS NOTHING: from the keeper finding it unreachable or powering it off,
            # until it is back or starts a job, its time is `~off` (not a stage; the watts leave it out).
            # THE ORCHESTRATOR (Paul, 5 November: "count them as Orchestrator of Orrery"): each planner
            # pass the keeper logs with its seconds is the orchestrator's lane busy planning; a pass
            # that failed is counted not done.
            if ev == "planned" and e.get("seconds"):
                add("orchestrator", "plan", t - float(e["seconds"]), t)
                w = busy_w("orchestrator")
                tl_ = c["tally"].setdefault(time.strftime("%Y-%m-%d", time.localtime(t)), {}).setdefault("orchestrator", {}).setdefault("plan", [0, 0, 0.0, 0.0])
                tl_[0] += 1
                tl_[2] = round(tl_[2] + float(e["seconds"]), 1)
                tl_[3] = round(tl_[3] + (w or 0) * float(e["seconds"]) / 3600, 1)
            elif ev == "planner failed":
                c["tally"].setdefault(time.strftime("%Y-%m-%d", time.localtime(t)), {}).setdefault("orchestrator", {}).setdefault("plan", [0, 0, 0.0, 0.0])[1] += 1
            if ev in ("host unreachable", "powered off") and e.get("host"):
                c["down"].setdefault(e["host"], t)
            elif ev in ("host back", "started") and e.get("host") in c["down"]:
                add(e["host"], "~off", c["down"].pop(e["host"]), t)
            if ev == "started" and e.get("host") and job:
                c["open"][job] = [t, e["host"]]
            elif ev in ("done", "failed", "stopped", "requeued") and job in c["open"]:
                t0, host = c["open"].pop(job)
                add(host, self.stage_of(job) if ev == "done" else "failed", t0, t)
                w = busy_w(host)
                d_ = time.strftime("%Y-%m-%d", time.localtime(t))
                if w:
                    day = c["energy"].setdefault(d_, {}).setdefault(host, [0, 0.0])
                    day[0] += 1
                    day[1] = round(day[1] + w * (t - t0) / 3600, 1)
                # THE HIT PARADE'S TALLY (Paul, 5 November: "keep the statistic in a chart ... a success
                # counter matrix wall"): a day, a machine, a kind of job: [done, not done (failed, stopped
                # or sent back), seconds, watt-hours], kept as long as the bins' hours.
                tl_ = c["tally"].setdefault(d_, {}).setdefault(host, {}).setdefault(self.stage_of(job), [0, 0, 0.0, 0.0])
                tl_[0 if ev == "done" else 1] += 1
                tl_[2] = round(tl_[2] + t - t0, 1)
                tl_[3] = round(tl_[3] + (w or 0) * (t - t0) / 3600, 1)
        c["offset"] += whole
        now_ = time.time()
        old = int((now_ - self.BIN_FINE_DAYS * 86400) // self.BIN_FINE_S)
        for lane in c["fine"].values():
            for k in [k for k in lane if int(k) < old]:
                del lane[k]
        for d in sorted(c["energy"])[:-120]:
            del c["energy"][d]
        # A start with no end for two days was lost with its keeper; it is not still running.
        c["open"] = {j: v for j, v in c["open"].items() if now_ - v[0] < 2 * 86400}
        save(keep, c, compact=True)
        return c

    @staticmethod
    def zoom_ticks(name, lo, hi):
        """Where the axis is marked, minutes from now, and what it says: a day by its clock, the
        longer ones by their midnights, labelled as often as they have room."""
        out, lt = [], time.localtime(lo)
        day0 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
        step = 3 * 3600 if name == "day" else 86400
        t = day0
        while t <= hi:
            if t >= lo:
                d = time.localtime(t)
                if name == "day":
                    say = "%s %d" % (time.strftime("%b", d), d.tm_mday) if d.tm_hour == 0 else time.strftime("%H:%M", d)
                elif name == "days":
                    say = "%s %d" % (time.strftime("%b", d), d.tm_mday)
                elif name == "weeks":
                    say = "%s %d" % (time.strftime("%b", d), d.tm_mday) if d.tm_wday == 0 else ""
                else:
                    say = time.strftime("%b", d) if d.tm_mday == 1 else ""
                if name != "months" or d.tm_mday == 1 or d.tm_wday == 0:
                    out.append([round((t - hi) / 60, 1), say])
            # Midnight to midnight by the calendar: a day of 23 or 25 hours keeps them at midnight.
            nxt = time.localtime(t + step + 7200)
            t = time.mktime((nxt.tm_year, nxt.tm_mon, nxt.tm_mday, 0, 0, 0, 0, 0, -1)) if step == 86400 else t + step
        return out

    def zoom_view(self, bins, hosts, now_, power=None):
        """Each zoom: its bins, a lane a machine, each bin [index, stage, percent, stage, percent ...]
        busiest first; bins on the local clock, so a day's begin at midnight. What runs now counts
        to now. With `power` (power.py, its model and calibration), each lane's watts at the wall in
        each bin as well: its watts busy for the share of the bin it was busy, idle for the rest;
        none before the event log begins, where nothing is known."""
        out, off = [], time.localtime(now_).tm_gmtoff
        for name, span_h, w, src in self.ZOOMS:
            nb = int(span_h * 3600 // w)
            lo = ((now_ + off) // w) * w - off - (nb - 1) * w
            unit = self.BIN_FINE_S if src == "fine" else self.BIN_COARSE_S
            lanes, watts, off_of = [], {}, {}
            # Boxes before their GPU lanes, so a GPU lane knows when its box was off.
            for h in sorted(hosts, key=lambda x: bool(power) and power[0].box_of(power[1], x) != x):
                acc = {}
                for k, cell in ((bins.get(src) or {}).get(h) or {}).items():
                    i = int((int(k) * unit - lo) // w)
                    if 0 <= i < nb:
                        a = acc.setdefault(i, {})
                        for stage, sec in cell.items():
                            a[stage] = a.get(stage, 0) + sec
                for host_, t0 in (bins.get("down") or {}).items():
                    if host_ == h:
                        t = max(t0, lo)
                        while t < now_:
                            i = int((t - lo) // w)
                            e_ = min(now_, lo + (i + 1) * w)
                            if 0 <= i < nb:
                                a = acc.setdefault(i, {})
                                a["~off"] = a.get("~off", 0) + e_ - t
                            t = e_
                for j, (t0, host) in (bins.get("open") or {}).items():
                    if host == h:
                        t = max(t0, lo)
                        while t < now_:
                            i = int((t - lo) // w)
                            e_ = min(now_, lo + (i + 1) * w)
                            if 0 <= i < nb:
                                a = acc.setdefault(i, {})
                                a[self.stage_of(j)] = a.get(self.stage_of(j), 0) + e_ - t
                            t = e_
                rows = []
                for i in sorted(acc):
                    row = [i]
                    for stage, sec in sorted(acc[i].items(), key=lambda kv: -kv[1]):
                        if stage.startswith("~"):
                            continue
                        pct = int(round(100.0 * sec / w))
                        if pct >= 1:
                            row += [stage, min(pct, 100)]
                    if len(row) > 1:
                        rows.append(row)
                lanes.append({"host": h, "bins": rows})
                if power:
                    P, pm, cal = power
                    first_t = bins.get("first") or lo
                    row_w = []
                    for i in range(nb):
                        t0 = lo + i * w
                        if t0 + w <= first_t:
                            row_w.append(None)
                            continue
                        span = max(1.0, min(w, now_ - t0))
                        cell = acc.get(i) or {}
                        off = cell.get("~off", 0) / span
                        if h != P.box_of(pm, h):  # a GPU lane is off when its box is
                            off = max(off, off_of.get((P.box_of(pm, h), i), 0.0))
                        else:
                            off_of[(h, i)] = off
                        busy = sum(v for k, v in cell.items() if not k.startswith("~")) / span
                        lw = P.lane_watts(pm, cal, h, busy)
                        row_w.append(None if lw is None else int(round(lw * max(0.0, 1.0 - min(1.0, off)))))
                    if any(x is not None for x in row_w):
                        watts[h] = row_w
            first = bins.get("first")
            out.append({"name": name, "span_h": span_h, "bin_min": w / 60, "from_min": round((lo - now_) / 60, 1), "lanes": lanes,
                        "begins_min": round((first - now_) / 60, 1) if first else None, "ticks": self.zoom_ticks(name, lo, now_),
                        "shifts": self.clock_shifts(lo, now_), "watts": watts})
        return out

    def parade_view(self, bins, now_):
        """THE HIT PARADE: the tally of every job handed off, a machine by a kind, over today, the last
        seven days and everything the event log holds; each window with the hours it covers, so a
        count is also a rate; and a row a day for the history."""
        tally, first = bins.get("tally") or {}, bins.get("first") or now_
        lt = time.localtime(now_)
        midnight = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
        week0 = time.mktime(time.localtime(midnight - 6 * 86400)[:3] + (0, 0, 0, 0, 0, -1))

        def window(keys, since):
            out = {}
            for d in keys:
                for h, kinds in tally[d].items():
                    for k, v in kinds.items():
                        a = out.setdefault(h, {}).setdefault(k, [0, 0, 0.0, 0.0])
                        for i in range(4):
                            a[i] += v[i]
            return {"hours": round((now_ - max(since, first)) / 3600, 2),
                    "cells": {h: {k: [v[0], v[1], round(v[2] / 60, 1), round(v[3], 1)] for k, v in ks.items()} for h, ks in out.items()}}
        days = sorted(tally)
        today = time.strftime("%Y-%m-%d", lt)
        return {"today": window([d for d in days if d == today], midnight),
                "week": window([d for d in days if d >= time.strftime("%Y-%m-%d", time.localtime(week0))], week0),
                "all": window(days, first),
                "since": time.strftime("%Y-%m-%d %H:%M", time.localtime(first)),
                "days": [[d, sum(v[0] for ks in tally[d].values() for v in ks.values()), sum(v[1] for ks in tally[d].values() for v in ks.values()),
                          round(sum(v[3] for ks in tally[d].values() for v in ks.values()), 1)] for d in days]}

    def chain_meta(self, lanes, dealt, dealt_at, now_):
        """THE CHAINS PAGE (Paul, 5 November: "rearranges each chain into its own gantt chart ... this
        would unscramble the net trace of arrows to have each dead end and each success clearly
        shown"). For every chain with a job in the six hours or in the queue: its kind; how it ended
        or where it stands, `good` True a success, False a dead end, None still going; that in words;
        and its queued jobs as the forecast deals them, [start, end, stage, id, machine]."""
        jobs = {}
        for l in lanes:
            for j in l["jobs"]:
                jobs.setdefault(j[5], []).append((j, l["host"]))
        nxt, extra = {}, self.chain_extra()
        for j in self.queue_jobs():
            jid = j.get("id", "")
            ch = extra[jid][0] if jid in extra else self.chain_of(jid, j.get("title", ""))
            at = dealt_at.get(jid) or [None, None]
            nxt.setdefault(ch, []).append([at[0], at[1], self.stage_of(jid, j.get("title", "")), jid, dealt.get(jid, "")])
        cand, kinds = {}, {}
        for r in self.runs():
            kinds[r["id"]] = r["kind"]
            if r["kind"] == "promote":
                c = ((r.get("params") or {}).get("candidate") or "").split("/")[-1]
                if c:
                    cand.setdefault(c, []).append(r["id"])
        on_main = set(re.findall(r"promote grove/(w\d+)", run(["git", "-C", self.tc, "log", "origin/main", "--first-parent",
                                                                 "--since=%d" % int(now_ - 14 * 86400), "--format=%s"]).stdout))
        current = {k for k, v in (load(os.path.join(self.pd, "candidates.json"), {}) or {}).items() if (v or {}).get("current")}
        rounds = {("clone-%03d" % r.get("n", 0)): r for r in ((self.state.get("clone") or {}).get("rounds") or [])}
        out = {}
        for ch in set(jobs) | set(nxt):
            js = jobs.get(ch, [])
            going_now = any(j[3] == 2 for j, _ in js) or ch in nxt
            last = max(js, key=lambda x: x[0][1])[0] if js else None
            fail = sorted({h for j, h in js if j[3] == 0})
            kind, good, say = "other", None, ""
            if re.match(r"w\d+$", ch):
                kind = "trial"
                states = [(rid, self.rstate(rid)) for rid in cand.get(ch, [])]
                won = [rid for rid, s_ in states if s_.get("status") in ("approved", "self-modified")]
                lost = [(rid, s_) for rid, s_ in states if s_.get("status") == "failed"]
                asked = [rid for rid, s_ in states if s_.get("status") in ("new", "running", "prepared")]
                if ch in on_main:
                    good, say = True, "promoted%s, and on main" % (" as " + won[-1] if won else "")
                elif won:
                    good, say = True, "promoted as %s: on the line" % won[-1]
                elif asked:
                    say = "its promotion, %s, is asked" % asked[-1]
                elif going_now:
                    held = any(x[2] == "held" for x in nxt.get(ch, [])) or any(j[2] == "held" and j[3] == 2 for j, _ in js)
                    say = "reading: its held-out read" if held else "reading on"
                elif lost:
                    good, say = False, "dead end: its promotion %s failed%s" % (lost[-1][0], (": " + lost[-1][1]["why"][:90]) if lost[-1][1].get("why") else "")
                elif ch in current:
                    say = "a candidate: its held-out reads passed, and it waits its promotion"
                elif last and last[2] == "held":
                    good, say = False, "dead end: its held-out read did not pass"
                else:
                    good, say = False, "dead end: dropped after %d read%s" % (len(js), "" if len(js) == 1 else "s")
            elif re.match(r"r\d+$", ch):
                kind = kinds.get(ch, "run")
                st_ = self.rstate(ch).get("status", "")
                good = True if st_ in ("done", "approved", "self-modified") else False if st_ == "failed" else None
                say = "%s, %s" % (kind, st_ or "running")
            elif ch.startswith("build "):
                kind = "build"
                good = None if going_now else (False if fail else True)
                say = ("failed on " + ", ".join(fail)) if fail else "built on %d machine%s" % (len({h for _, h in js}), "" if len({h for _, h in js}) == 1 else "s")
            elif ch.startswith("island "):
                kind, say = "island", "segments, each after the one before"
            elif ch.startswith("line "):
                kind, say = "proof", "the line read against main"
            elif ch.startswith("clone-"):
                kind = "clone"
                r = rounds.get(ch) or {}
                good = None if r.get("holds") is None else bool(r["holds"])
                say = "shipped as the Scholar" if good else ("not shipped: %+.2f against the shipped one" % r["diff"] if r.get("diff") is not None else "a clone round")
            else:
                say = self.stage_of(ch)
            if good is None and not going_now and kind not in ("island",) and not say:
                say = "done"
            out[ch] = {"kind": kind, "good": good, "say": say, "next": nxt.get(ch, [])[:8]}
        return out

    def power_view(self, now_, zoom, bins, live, hosts):
        """THE FLEET'S WATTS AND THEIR COST (Paul, 5 November). Each lane's watts at the wall now (the
        last sample's CPU use and GPU draw, if under a quarter hour old; its model busy or idle as it
        is, if not), the fleet's now and at full tilt, the last day's kilowatt-hours from the day's
        bins, the jobs' own energy as each was handed off (today, by lane), and the price at
        power_usd_kwh. Each box's model, measured or assumed, for the page to say."""
        P = power_mod()
        pm = P.model()
        smp = P.samples(self.q, now_ - 3 * 86400)
        cal = P.calib(pm, smp)
        rate = P.rate(self.q, pm)
        last = {}
        for x in smp:
            last[x["box"]] = x
        lanes_now = {}
        for h in hosts:
            box = P.box_of(pm, h)
            b = (pm.get("boxes") or {}).get(box)
            if not b:
                continue
            x = last.get(box) if last.get(box) and now_ - last[box]["t"] < 900 and last[box].get("ok") else None
            busy = (live.get(h) or {}).get("state") in P.BUSY or bool((live.get(h) or {}).get("job"))
            if h == "orchestrator":
                cores = sum((x.get("orch") or {}).values()) / 100 if x and x.get("orch") is not None else None
                lanes_now[h] = round(cores * P.per_core(pm, box) if cores is not None else P.lane_watts(pm, cal, h, 0.5), 1)
            elif x and h == box and x.get("cpu") is not None:
                # The machine the keeper runs on: its job lane less Orrery's own, which is the orchestrator's.
                th = max(1, b.get("threads", 8))
                lanes_now[h] = round(P.watts(pm, box, max(0.0, x["cpu"] - sum((x.get("orch") or {}).values()) / 100 / th), 0.0)["wall"])
            elif x and h != box and x.get("gpu_w"):
                lanes_now[h] = round(sum(x["gpu_w"]) / P.eff(pm, box))
            else:
                lanes_now[h] = round(P.lane_watts(pm, cal, h, 1.0 if busy else 0.0))
        day = next((z for z in zoom if z["name"] == "day"), None)
        kwh = sum(v for row in ((day or {}).get("watts") or {}).values() for v in row if v) * (day["bin_min"] / 60) / 1000 if day else 0.0
        today = (bins.get("energy") or {}).get(time.strftime("%Y-%m-%d", time.localtime(now_)), {})
        full = {box: round(P.full_tilt(pm, cal, box)) for box in (pm.get("boxes") or {})}
        boxes = []
        for box, b in (pm.get("boxes") or {}).items():
            c = cal.get(box) or {}
            boxes.append({"box": box, "cpu": b.get("cpu", ""), "gpu": b.get("gpu", ""), "full_w": full[box],
                          "now_w": sum(v for h, v in lanes_now.items() if P.box_of(pm, h) == box),
                          "busy_util": c.get("busy_util"), "gpu_busy_w": c.get("gpu_busy_w") if b.get("gpu") else None,
                          "samples": c.get("measured", {}), "why": b.get("why", "")})
        # The Orchestrator: Orrery's own processes on the Mac, by part, as the last sample read them, and
        # today's planner passes.
        ob = (pm.get("orchestrator") or {}).get("box", "mac")
        xo = last.get(ob) or {}
        plans = ((bins.get("tally") or {}).get(time.strftime("%Y-%m-%d", time.localtime(now_)), {}).get("orchestrator") or {}).get("plan") or [0, 0, 0.0, 0.0]
        orch = {"by": xo.get("orch") or {}, "cores": round(sum((xo.get("orch") or {}).values()) / 100, 2), "watts": lanes_now.get("orchestrator"),
                "steady_cores": (cal.get("orchestrator") or {}).get("steady_cores"), "samples": (cal.get("orchestrator") or {}).get("measured", 0),
                "passes_today": plans[0], "failed_today": plans[1], "pass_s": round(plans[2] / plans[0], 1) if plans[0] else None,
                "wh_today": plans[3], "box": ob}
        return {"rate": rate, "lanes_now": lanes_now, "fleet_now_w": sum(lanes_now.values()), "fleet_full_w": sum(full.values()), "orchestrator": orch,
                "kwh_24h": round(kwh, 2), "usd_24h": round(kwh * rate, 2), "usd_30d": round(kwh * rate * 30, 2),
                "jobs_today": {h: [n, round(wh, 1)] for h, (n, wh) in today.items()}, "boxes": boxes,
                "sampled": time.strftime("%H:%M", time.localtime(max((x["t"] for x in smp), default=0))) if smp else "",
                "lane_busy_w": {h: round(P.lane_watts(pm, cal, h, 1.0) or 0, 1) for h in hosts}}

    @staticmethod
    def clock_shifts(lo, now_):
        """[minutes from now, minutes the clock read more before it than now]: each change of summer
        time in the span, so the page's dates of a time before one read the clock that was on the
        wall then (the event log begins 09:34 on 28 October, summer time, not 08:34)."""
        out, off_now, t = [], time.localtime(now_).tm_gmtoff, lo
        prev = time.localtime(lo).tm_gmtoff
        while t < now_:
            t2 = min(now_, t + 3600)
            o = time.localtime(t2).tm_gmtoff
            if o != prev:
                a, b = t, t2
                while b - a > 60:
                    mid = (a + b) / 2
                    a, b = (mid, b) if time.localtime(mid).tm_gmtoff == prev else (a, mid)
                out.append([round((b - now_) / 60, 1), (prev - off_now) // 60])
                prev = o
            t = t2
        return out

    def timeline_marks(self, now_):
        """The milestones of three months, each where it happened, minutes from now: a generation
        on the line, the line on main, a candidate the tests stopped, the game's rules moving, a
        GPU island's milestone, a net shipped into the game, and the islands taking new rules."""
        lo, marks = now_ - 91 * 86400, []
        def mark(t, kind, text):
            if t >= lo:
                lt = time.localtime(t)
                marks.append({"at": round((t - now_) / 60, 1), "kind": kind, "text": text,
                              "when": "%s %d %s" % (time.strftime("%b", lt), lt.tm_mday, time.strftime("%H:%M", lt))})
        cand = {r["id"]: ((r.get("params") or {}).get("candidate") or "").split("/")[-1] for r in self.runs() if r["kind"] == "promote"}
        for t, rid, st_ in self.promotions():
            mark(t, "generation", ("%s %s" % (rid, cand.get(rid, ""))).strip())
        for r in self.runs():
            if r["kind"] == "promote" and self.rstate(r["id"]).get("status") == "failed":
                try:
                    mark(os.path.getmtime(os.path.join(self.q, "logs", r["id"] + "-promote.log")), "failed", ("%s %s" % (r["id"], cand.get(r["id"], ""))).strip())
                except OSError:
                    pass
        # Main, the game's rules and the nets shipped, from treadcore's main as it went.
        log = run(["git", "-C", self.tc, "log", "origin/main", "--first-parent", "--since=%d" % int(lo), "--format=%ct %h %s"]).stdout.splitlines()
        landed = {}
        for l in log:
            p = l.split(" ", 2)
            if len(p) == 3 and p[2].startswith("promote grove/"):
                landed.setdefault(int(p[0]), []).append(p[2].split()[1].split("/")[-1])
        for t, ws in landed.items():
            mark(t, "main", "main: " + ", ".join(sorted(ws)))
        games = run(["git", "-C", self.tc, "log", "origin/main", "--first-parent", "--since=%d" % int(lo), "--format=%ct %h", "--",
                     "source/treadcore-sim/GAME_VERSION", "source/treadcore-brain/SCORE_VERSION"]).stdout.split()
        for t, sha in zip(games[0::2], games[1::2]):
            mark(int(t), "game", "game " + (self.game_at(sha) or "?"))
        ships = run(["git", "-C", self.tc, "log", "origin/main", "--since=%d" % int(lo), "--format=@%ct %h", "--name-only", "--",
                     "nets/gladiator.bin", "nets/scholar.bin"]).stdout
        for part in ships.split("@")[1:]:
            w = part.split()
            if len(w) >= 3:
                mark(int(w[0]), "ship", "into the game: " + ", ".join({"nets/gladiator.bin": "Gladiator", "nets/scholar.bin": "Scholar"}.get(x, x) for x in w[2:]))
        home = self.crucible_home()
        for m in self.ladder_state(home).get("milestones", []) if self.cuda else []:
            try:
                mark(time.mktime(time.strptime(m["made"], "%Y-%m-%dT%H:%M:%S")), "milestone", m["id"])
            except (KeyError, ValueError):
                pass
        # The islands read treadcore's rules at each segment (world_flags); the first world segment
        # is when they began to, and each move since is kept in the state.
        if self.cuda and "world" in home:
            try:
                with open(self.crucible_dir("lineage.tsv", home=home)) as f:
                    f.readline()
                    first = f.readline().split("\t")[0]
                mark(time.mktime(time.strptime(first, "%Y-%m-%dT%H:%M:%S")), "rules", "the islands play treadcore's rules")
            except (OSError, ValueError):
                pass
        for r in self.state.get("rules_moves") or []:
            mark(r["at"], "rules", r["text"])
        return sorted(marks, key=lambda m: m["at"])

    def cuda_return(self, now_, seg_min=None):
        """When a GPU island next gives the game anything. Its segments go to the ladder each ten
        minutes or so, but the game sees a net only when one beats the newest milestone by two
        errors (crucible_ladder_home), and then only by the bridge's read on a CPU machine and a
        ship. So, a GPU lane: the milestone to beat, how near its exams of the last six hours came,
        the climb of their median over the last day, and the hours until it would cross at that
        climb. A GUESS FROM A TREND, said as one; none when the median does not climb."""
        home = self.crucible_home()
        lad = self.ladder_state(home).get("milestones", [])
        top = lad[-1] if lad else None
        rows = []
        try:
            import csv
            with open(self.crucible_dir("lineage.tsv", home=home)) as f:
                rows = [r for r in csv.DictReader(f, delimiter="\t") if r.get("margin_se") not in (None, "-", "")]
        except OSError:
            pass
        parse = lambda t: time.mktime(time.strptime(t, "%Y-%m-%dT%H:%M:%S"))
        out = {}
        for h in self.cuda:
            mine = [(parse(r["time"]), float(r["margin_se"])) for r in rows if r["island"] == h["name"] and top and r["against"] == top["id"]]
            last6 = [m for t, m in mine if t >= now_ - 6 * 3600]
            hours = {}
            for t, m in mine:
                if t >= now_ - 24 * 3600:
                    hours.setdefault(int((t - now_) // 3600), []).append(m)
            pts = [(k + 0.5, st.median(v)) for k, v in sorted(hours.items())]
            slope = None
            if len(pts) >= 6:
                mx, my = st.mean(p[0] for p in pts), st.mean(p[1] for p in pts)
                vx = sum((p[0] - mx) ** 2 for p in pts)
                slope = sum((p[0] - mx) * (p[1] - my) for p in pts) / vx * 24 if vx else None
            med = st.median(last6) if last6 else None
            eta = (2.0 - med) / slope * 24 if slope and slope > 0 and med is not None and med < 2 else None
            out[h["name"]] = {"top": top["id"] if top else "", "top_made": top.get("made", "") if top else "", "segments": len(mine),
                              "best": round(max(last6), 1) if last6 else None, "median": round(med, 1) if med is not None else None,
                              "per_day": round(slope, 1) if slope is not None else None, "eta_h": round(eta, 1) if eta is not None else None,
                              "seg_min": (seg_min or {}).get(h["name"])}
        return out

    def chain_extra(self):
        """Links the titles cannot say: a bridge read is the island's, after the segment that made
        the milestone it reads, so the island's chain runs on to the CPU machine that reads it."""
        made = {m["id"]: m.get("job") for m in self.ladder_state(self.crucible_home()).get("milestones", [])} if self.cuda else {}
        br = self.state.get("bridge") or {}
        out = {}
        for r in (br.get("reads") or []) + ([br["current"]] if br.get("current") else []):
            seg = made.get(r.get("label"))
            m = re.match(r"M\d+-(.+)-g\d+$", r.get("label") or "")
            if m:
                for j in r.get("jobs") or []:
                    out[j] = ("island " + m.group(1), seg or "")
        return out

    # The backup: the small reads a free lane takes from the queue when its own line has nothing for
    # it, each returned whole (its seeds pooled with every other read of its question).
    RETURNABLE = ("first", "read", "held", "proof", "anchor", "transform", "islands")

    def blame_view(self, live, tl, recent):
        """THE ROUND TABLE (Paul, 5 November: "a blame tab ... the computers point at each other
        saying who they are waiting on. On their other hand, shows their backup help, where it can
        reach out back to the queue to assist in small jobs of improvement, piecemeal in returnable
        increments"). What a queued job waits on, named by what holds it:

          turn     its machine, busy (the GPU islands keep six segments ahead on purpose);
          build    its machine's build of the newest commit;
          after    a job another machine runs: the only arrow between two machines;
          planner  a run whose last job came back and whose next is not asked yet, until the
                   planner's next pass (each plan_s, or sooner when the queue runs low).

        A queued job belongs to the machine the Timeline's forecast deals it to. Each machine's
        help is the share of its busy time on the small returnable reads; the handoffs are the
        measured minutes between one job of a chain coming back and the next one starting."""
        now_ = time.time()
        busy, dealt = tl.get("busy", {}), tl.get("dealt", {})
        win = float(tl.get("past_h", self.TIMELINE_H)) * 60
        done = self.ids("done")
        running = {l["job"]: n for n, l in live.items() if l.get("job")}
        nodes = []
        for h in self.qcfg.get("hosts", []):
            n, l = h["name"], live.get(h["name"], {})
            b = busy.get(n, {})
            tot = sum(b.values())
            gpu = "cpu" not in h.get("caps", ["cpu"]) and bool({"gpu", "cuda"} & set(h.get("caps", [])))
            nodes.append({"host": n, "gpu": gpu, "state": l.get("state") or "unknown", "job": l.get("job") or "",
                          "stage": self.stage_of(l["job"], l.get("title", "")) if l.get("job") else "",
                          "for_min": round((now_ - l.get("since", now_)) / 60, 1),
                          "busy_pct": round(100 * min(tot, win) / win, 1),
                          "help_pct": round(100 * sum(v for k, v in b.items() if k in self.RETURNABLE) / tot, 1) if tot else 0.0,
                          "by_stage": [[k, v] for k, v in sorted(b.items(), key=lambda kv: -kv[1])],
                          "backup": "its own island's next segment: a population lives on its card" if gpu
                          else "the standing search: a first read, 55 seeds, about 3 minutes, returned whole"})
        # EACH MACHINE'S QUEUE (Paul, 5 November: "a filtered job queue for each machine ... show the
        # job dependency on hover"): what it runs, then what the forecast deals it in turn, each
        # with the job it waits on and where that job is: its build, a job another machine has, or
        # simply the one ahead of it on this machine.
        at_ = tl.get("dealt_at", {})
        queues = {h["name"]: [] for h in self.qcfg.get("hosts", [])}
        for n, l in live.items():
            if l.get("job") and n in queues:
                queues[n].append({"id": l["job"], "title": l.get("title", ""), "stage": self.stage_of(l["job"], l.get("title", "")), "state": "running",
                                  "wait": "", "on": "", "on_host": "", "start_min": -round((now_ - l.get("since", now_)) / 60, 1), "end_min": None, "high": False})
        unplaced = []
        # The Orchestrator at the table too: Orrery's planner, busy the share of the hours it planned.
        ob_ = busy.get("orchestrator", {})
        nodes.append({"host": "orchestrator", "gpu": False, "state": "planning", "job": "", "stage": "plan", "for_min": 0.0,
                      "busy_pct": round(100 * min(sum(ob_.values()), win) / win, 1), "help_pct": 0.0,
                      "by_stage": [[k, v] for k, v in ob_.items()],
                      "backup": "none: it is the table's own planner, Orrery on the Mac, asking for every job the others run"})
        waits = {}
        for j in self.queue_jobs():
            jid, a = j.get("id", ""), dealt.get(j.get("id", ""))
            row = {"id": jid, "title": j.get("title", ""), "stage": self.stage_of(jid, j.get("title", "")), "state": "queued",
                   "high": j.get("priority") == "high", "start_min": (at_.get(jid) or [None])[0], "end_min": (at_.get(jid) or [None, None])[1]}
            if not a:
                pend = [x for x in j.get("after", []) if x not in done]
                row.update({"wait": "no machine", "on": pend[0] if pend else "", "on_host": running.get(pend[0], "") if pend else "",
                            "needs": j.get("needs") or "cpu"})
                unplaced.append(row)
                continue
            ah = j["after_host"].format(host=a) if j.get("after_host") else ""
            pend = [x for x in j.get("after", []) if x not in done]
            if ah and ah not in done:
                b, kind, on = a, "build", ah
            elif pend:
                b, kind, on = running.get(pend[0]) or dealt.get(pend[0]) or a, "after", pend[0]
            else:
                b, kind, on = a, "turn", ""
            if b == a and kind == "after":
                kind = "turn"
            ahead = queues.get(a) or []
            if kind == "turn" and not on and ahead:
                on = ahead[-1]["id"]
            row.update({"wait": kind, "on": on, "on_host": b})
            if a in queues and len(queues[a]) < 30:
                queues[a].append(row)
            waits.setdefault((a, b, kind), []).append(jid)
        edges = [{"from": a, "to": b, "kind": k, "n": len(js), "jobs": js[:8]} for (a, b, k), js in sorted(waits.items())]
        asked = {j.get("id", "") for j in self.queue_jobs()} | set(running)
        planner = []
        for r in self.runs():
            if self.rstate(r["id"]).get("status") != "running" or any(x.startswith(r["id"] + "-") for x in asked):
                continue
            mine = [j for j in recent if str(j.get("id", "")).startswith(r["id"] + "-") and j.get("ended")]
            if not mine:
                continue
            last = max(mine, key=lambda j: j["ended"])
            planner.append({"run": r["id"], "kind": r["kind"], "host": last.get("host", ""), "job": last["id"],
                            "for_min": round((now_ - time.mktime(time.strptime(last["ended"], "%Y-%m-%dT%H:%M:%S"))) / 60, 1)})
        return {"nodes": nodes, "edges": edges, "planner": planner, "handoffs": self.handoffs(recent),
                "queued": len(self.queue_jobs()), "plan_s": self.qcfg.get("plan_s", 300), "queues": queues, "unplaced": unplaced[:30]}

    def handoffs(self, recent):
        """The minutes a chain waits between its own jobs, over the last day: from one coming back to
        the next being asked (the planner's pass) and from asked to started (the queue). The transform's
        steps are one chain; a trial's first read, read-ons and held-out reads are another."""
        asked, cut = {}, time.time() * 1000 - 5e10
        for f in glob.glob(os.path.join(self.q, "done", "*.json")):
            seq, _, rest = os.path.basename(f).partition("-")
            try:
                v = int(seq)
            except ValueError:
                continue
            # A high-priority job's name is 10^11 ms earlier, so it sorts first; a background one's later.
            asked[rest[:-5]] = (v + 10 ** 11 if v < cut else v - 10 ** 11 if v > time.time() * 1000 + 5e10 else v) / 1000.0
        parse = lambda t: time.mktime(time.strptime(t, "%Y-%m-%dT%H:%M:%S"))
        jobs = {}
        for j in recent:
            i = str(j.get("id", ""))
            if j.get("ended") and i in asked:
                end = parse(j["ended"])
                jobs[i] = (asked[i], end - float(j.get("seconds") or 0), end, j.get("title", ""))
        chains = {"transform": {}, "trials": {}}
        for i, (q, s0, e, title) in jobs.items():
            m = re.match(r"(r\d+)-k(\d+)$", i)
            if m:
                chains["transform"].setdefault(m.group(1), []).append(i)
            m = re.search(r"of (w\d+)", title) if re.match(r"[eh]\d+$", i) else None
            if m or re.match(r"w\d+$", i):
                chains["trials"].setdefault(m.group(1) if m else i, []).append(i)
        out = {}
        for name, cs in chains.items():
            plan_m, queue_m, work_m = [], [], []
            for ids in cs.values():
                ids.sort(key=lambda i: jobs[i][1])
                for a, b in zip(ids, ids[1:]):
                    # Two asked together (held-out reads in pairs) are not a handoff.
                    if jobs[b][0] < jobs[a][2]:
                        continue
                    plan_m.append((jobs[b][0] - jobs[a][2]) / 60)
                    queue_m.append(max(0.0, jobs[b][1] - jobs[b][0]) / 60)
                    work_m.append((jobs[b][2] - jobs[b][1]) / 60)
            if plan_m:
                out[name] = {"n": len(plan_m), "planner_min": round(st.median(plan_m), 1), "queue_min": round(st.median(queue_m), 1),
                             "work_min": round(st.median(work_m), 1)}
        return out

    @staticmethod
    def chain_of(i, title=""):
        """What a job is a link of, for the Timeline to follow: a trial's first read, read-ons,
        held-out reads and their pieces, its gauntlet read and its promotion are the trial's
        (wNNNN); a run's jobs, a transform's steps among them, are the run's; a GPU island's
        segments are the island's; a commit's builds are the commit's; a proof is its line's."""
        m = re.search(r"(?:read on \d+|held-out read \d+|held-out piece(?: ahead of time:)? \d+ of \d+ of read \d+) of (w\d+)", title)
        if m:
            return m.group(1)
        m = re.search(r"grove/(w\d+)", title) if re.match(r"(gx\d+|r\d+-promote|f\d+)$", i) else None
        if m:
            return m.group(1)
        if re.match(r"w\d+$", i):
            return i
        m = re.match(r"(r\d+)-", i)
        if m:
            return m.group(1)
        m = re.match(r"(clone-\d+)-", i)
        if m:
            return m.group(1)
        m = re.match(r"prep-.+-([0-9a-f]{7})$", i)
        if m:
            return "build " + m.group(1)
        m = re.match(r"x-(.+)-\d+$", i)
        if m:
            return "island " + m.group(1)
        m = re.search(r"the line ([0-9a-f]{7})", title)
        if m and i.startswith("pv"):
            return "line " + m.group(1)
        return i

    @staticmethod
    def merge_bars(rows):
        """A lane's bars in time order, touching ones of a stage as one: a second-long gap is not
        worth a rectangle, and a day of 90-second jobs would be thousands."""
        out = []
        for a, b, k, ok in sorted(rows):
            if out and out[-1][2] == k and a - out[-1][1] < 1.0 and out[-1][3] == ok:
                out[-1][1] = b
            else:
                out.append([a, b, k, ok])
        return out

    def queued_view(self, live):
        """What runs and what waits, each with why it is here. The reason is the stage's in
        line.json; a held-out read adds the bar it must pass, which only the planner knows."""
        why = {s["id"]: s["queued"] for s in self.line.get("stages", [])}
        d = self.state.get("difficulty", {})

        def row(j, state, host="", age=0.0):
            i, title = j.get("job") or j.get("id") or "", j.get("title") or ""
            k = self.stage_of(i, title)
            text = why.get(k) or "A run someone asked for: it goes before the standing search."
            if "carried to" in title:
                text = "A pass the last generation overtook: read again on the new baseline, not thrown away."
            if k == "held":
                text = "%s Passes at z %.2f." % (text, d.get("held_z", 0))
            return {"id": i, "stage": k, "title": title, "state": state, "host": host, "age_min": round(age, 1), "high": j.get("priority") == "high", "why": text}
        out = [row(l, "running", n, (time.time() - l.get("since", time.time())) / 60) for n, l in sorted(live.items()) if l.get("job")]
        out += [row(j, "queued", (j.get("needs") or "")[5:] if (j.get("needs") or "").startswith("host:") else "") for j in self.queue_jobs()[:60]]
        return out

    def trace_view(self, recent):
        """The last trials that got as far as a held-out read, each followed through the line:
        every read with its machine and time, the pooled z after it, and how it ended. This is
        the visualizer's data: one trial's numbers, moving, from question to commit or to nothing."""
        steps = {}
        # A held-out read made of pieces has no finished job of its own: its merged census stands in.
        recent = list(recent)
        for hid, title in self.state.get("held_merged", {}).items():
            d = self.piece_dir(hid)
            if d and time.time() - os.path.getmtime(d) < 86400:
                recent.append({"id": hid, "title": title, "host": "%d machines" % self.HELD_PIECES,
                               "ended": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(d)))})
        for j in recent:
            title, i = j.get("title", ""), j.get("id", "")
            m = re.match(r"(read on \d+|held-out read \d+) of (w\d+)", title)
            if m:
                steps.setdefault(m.group(2), []).append(j)
            elif re.match(r"w\d+$", i):
                steps.setdefault(i, []).append(j)
        held = [t for t, js in steps.items() if any(x.get("title", "").startswith("held-out") for x in js)]
        ended = {}
        for r in self.runs():
            cand = (r.get("params") or {}).get("candidate", "")
            if r["kind"] == "promote" and cand.startswith(self.name + "/"):
                st_ = self.rstate(r["id"])
                ended[cand.split("/", 1)[1]] = {"run": r["id"], "status": st_.get("status", ""), "why": (st_.get("why") or "")[:90], "changed": st_.get("changed", [])[:4]}
        out = []
        for t in sorted(held, key=lambda x: max(j.get("ended", "") for j in steps[x]), reverse=True)[:8]:
            rows, dirs, text = [], [], ""
            for j in sorted(steps[t], key=lambda x: (0 if x["id"] == t else 1, x.get("ended", ""))):
                ds = glob.glob(os.path.join(self.q, "results", j["id"], self.home, "out", j["id"], "*", ""))
                if not ds:
                    continue
                dirs += ds
                one, all_ = self.pool(ds), self.pool(dirs)
                try:
                    text = text or open(os.path.join(ds[0], "trial.weights")).read()
                except OSError:
                    pass
                if not one or not all_:
                    continue
                d, se, n = one["every"]
                pd_, pse, pn = all_["every"]
                k = self.stage_of(j["id"], j.get("title", ""))
                # A held-out read decides alone: its own z, not the pool's.
                z = d / se if k == "held" and se else pd_ / pse if pse else 0.0
                rows.append({"stage": k, "job": j["id"], "host": j.get("host", ""), "ended": j.get("ended", "")[11:16], "seeds": n, "d": round(d, 2), "se": round(se, 2), "z": round(z, 2)})
            note = next((l[1:].strip() for l in text.splitlines() if l.startswith("#")), "")
            moved = "; ".join(l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#"))
            out.append({"trial": t, "note": note[:70], "moved": moved[:110], "reads": rows, "ended": ended.get(t, {})})
        return out

    def queue_jobs(self):
        return [load(f, {}) or {} for f in sorted(glob.glob(os.path.join(self.q, "queue", "*.json")))]

    @staticmethod
    def task_of(j):
        """Which task on the board a job or a lane's job is."""
        i, title = j.get("job") or j.get("id") or "", j.get("title") or ""
        if i.startswith("prep-"):
            return "build"
        if i.startswith("x-"):
            return "islands"
        if i.startswith("pv"):
            return "proof"
        if re.match(r"f\d+$", i):
            return "families"
        if i.endswith("-promote"):
            return "promote"
        if re.match(r"r\d+-k\d+", i):
            return "transform"
        if title.startswith("held-out"):
            return "held"
        if title.startswith("read on"):
            return "read"
        if re.match(r"w\d+$", i):
            return "search"
        return None

    def _built_everywhere(self):
        return all(self.prepared(h["name"]) for h in self.hosts if h["name"] not in ("jaguaribe",)) if self.hosts else False

    def collect(self):
        rows = []
        for d in self.census_dirs():
            jid = d.rstrip("/").split(os.sep)[-2]
            p = self.passes(d)
            trial = ""
            try:
                trial = "; ".join(l.split("#")[0].strip() for l in open(os.path.join(d, "trial.weights")) if "=" in l.split("#")[0])
            except OSError:
                pass
            every = ""
            try:
                every = next(l for l in open(os.path.join(d, "pooled.txt")) if l.startswith("every map")).strip()
            except (OSError, StopIteration):
                pass
            rows.append({"job": jid, "trial": trial, "every_map": every, "passes": p})
        rounds = [load(f) for f in sorted(glob.glob(os.path.join(self.pd, "round-*.json")))]
        summary = {"weights": rows, "rounds": rounds, "best": load(os.path.join(self.pd, "best.json")), "families": self.families()}
        save(os.path.join(self.pd, "summary.json"), summary)
        passed = [r["job"] for r in rows if r["passes"]]
        print("collected: %d weight censuses (%d past two errors); %d net rounds judged" % (len(rows), len(passed), len(rounds)))


_POWER = None


def power_mod():
    """tools/power.py, the fleet's watts: its model and its samples (loaded once a process)."""
    global _POWER
    if _POWER is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("orrery_power", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "power.py"))
        _POWER = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_POWER)
    return _POWER


def chores(qdir, tools=None):
    """THE HOUSEKEEPING IS THE KEEPER'S (the lab report of 4 November, "Fifty-Four Idle Minutes",
    change C). The Results and Analysis pages' documents and the recordings' sweep were begun by
    the window (treadcore-view.py, every few seconds while it is open): with it closed the pages went
    stale and the sweep that keeps the disks from filling waited, and opening it began everything
    stale in the same few seconds. The keeper asks this each minute (`PLANNER chores`), window or
    none; what is stale is begun in the background, each behind its own lock, and nothing here waits
    for it. The same clocks as the window kept: analysis each 10 minutes, nets and growth each 5,
    the recordings' list each half hour and their sweep each 6 hours. Prints what it began."""
    tools = tools or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pd = os.path.join(qdir, "plan")
    began = []

    def age(f):
        return time.time() - os.path.getmtime(f) if os.path.exists(f) else 1e9

    def begin(name, argv, then_rm=None):
        if then_rm:
            argv = ["sh", "-c", '"$@"; rm -f "$RM"', "sh"] + argv
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                         env=dict(os.environ, RM=then_rm) if then_rm else None)
        began.append(name)

    # (the document, how old it may be, its lock, how long a lock holds, the tool and its verb)
    for doc, every, hold, tool, verb in (("analysis.json", 600, 300, "analysis.py", []),
                                         ("nets.json", 300, 120, "nets.py", ["refresh"]),
                                         ("growth.json", 300, 600, "growth.py", ["refresh"]),
                                         # The fleet's watts (Paul, 5 November): each box's CPU use and GPU draw.
                                         ("power-samples.jsonl", 300, 120, "power.py", ["sample"])):
        f = os.path.join(pd, doc)
        lock = f + ".lock"
        if age(f) > every and age(lock) > hold:
            open(lock, "w").close()
            begin(tool[:-3], [sys.executable, "-I", os.path.join(tools, tool), qdir] + verb)
    # The recordings: the list each half hour (an ssh to every machine), the SWEEP each six hours (a
    # run's shards go once nothing reads them and their recipe is proved: Paul's default, 4 November).
    # One at a time: both ssh to every machine.
    f = os.path.join(pd, "recordings.json")
    turns = ((["list"], 1800, f, f + ".lock.run"), (["sweep", "--do"], 6 * 3600, f + ".sweep", f + ".sweep.run"))
    busy = any(age(run_) < 3600 for _, _, _, run_ in turns)
    for verb, every, stamp, run_ in turns:
        if age(stamp) > every and not busy:
            open(run_, "w").close()
            if verb[0] == "sweep":
                open(stamp, "w").close()
            begin("recordings " + verb[0], [sys.executable, "-I", os.path.join(tools, "recordings.py"), qdir] + verb, then_rm=run_)
            break
    # THE NIGHTLY PACK (Paul, 6 November: "the queue is too big ... is it all needed right now?", then
    # "Nightly, by the keeper"): the game logs of finished census reads past a day, packed into
    # archive/packs and proved before they go (growth.py pack-logs). Between 03:00 and 06:00, once a
    # night; a night missed (the Mac asleep, the keeper down) is made up once 36 hours have passed. The
    # growth page's refresh is held off while it runs, both writing plan/growth.json.
    f = os.path.join(pd, "pack-logs.stamp")
    run_ = f + ".run"
    hour = time.localtime().tm_hour
    if (3 <= hour < 6 and age(f) > 20 * 3600 or age(f) > 36 * 3600) and age(run_) > 3 * 3600:
        open(run_, "w").close()
        open(f, "w").close()
        open(os.path.join(pd, "growth.json.lock"), "w").close()
        begin("pack-logs", [sys.executable, "-I", os.path.join(tools, "growth.py"), qdir, "pack-logs"], then_rm=run_)
    return began


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    if sys.argv[2] == "chores":
        # Before the plan is read: a minute's clock wants nothing of it.
        began = chores(sys.argv[1])
        print("began " + ", ".join(began) if began else "nothing stale")
        sys.exit(0)
    p = Plan(sys.argv[1])
    cmd = sys.argv[2]
    p.writer = cmd in ("plan", "now", "approve", "resolve", "why", "tag", "adopt", "orphan")
    if cmd == "plan":
        # A pass measured on request: plan/profile-next there, the next pass runs under cProfile and
        # writes what it spent its time on to plan/profile.txt (the duty-cycle report's passes took
        # 80 to 106 seconds once the keeper asked for them sooner).
        flag = os.path.join(p.pd, "profile-next")
        if os.path.exists(flag):
            import cProfile
            import io
            import pstats
            os.remove(flag)
            prof = cProfile.Profile()
            prof.runcall(p.plan, int(sys.argv[3]) if len(sys.argv) > 3 else 4)
            out = io.StringIO()
            pstats.Stats(prof, stream=out).sort_stats("cumulative").print_stats(45)
            open(os.path.join(p.pd, "profile.txt"), "w").write(out.getvalue())
        else:
            p.plan(int(sys.argv[3]) if len(sys.argv) > 3 else 4)
    elif cmd == "collect":
        p.collect()
    elif cmd == "families":
        p.families()
    elif cmd == "judged":
        p.judged(sys.argv[3])
    elif cmd == "sync":
        p.sync(sys.argv[3] if len(sys.argv) > 3 else None)
        # A plan after every sync, whatever the queue's length: a keeper
        # plans when its queue runs low or runs/ changes, and a prepared
        # promotion or a finished rotation run would otherwise wait for the
        # queue to drain. A file made and removed in runs/ is a change.
        poke = os.path.join(p.q, "runs", ".sync-poke")
        open(poke, "w").close()
        os.remove(poke)
    elif cmd == "why":
        # why RID: a failed promotion's reason, read again from its log.
        st = p.rstate(sys.argv[3])
        if st.get("status") == "failed" and st.get("job"):
            st["why"] = p.promote_failure(st["job"])
            p.rsave(sys.argv[3], st)
            p.keep()
        print(st.get("why", st.get("status")))
    elif cmd == "orphan":
        # orphan: the line taken off again on the read that took it off before, when it carries the same
        # promotions and nothing else (13 November: the first orphaned line was rebuilt by a fault, not read anew).
        line, last = p.state.get("local_line"), (p.state.get("orphans") or [None])[-1]
        if not line or not last or line.get("promotions") != last.get("promotions"):
            sys.exit("no line that the last orphaning read: nothing done")
        print("off" if p.orphan(line["commit"], last["lead"], last["se"], last["seeds"]) else "not taken off")
        p.keep()
    elif cmd == "resolve":
        # resolve: the local line (self-modified promotions) pushed to main.
        p.resolve()
        p.keep()
    elif cmd == "tag":
        # tag RID: an approved promotion's micro version, made now (for one
        # approved before tags were made).
        st = p.rstate(sys.argv[3])
        if st.get("status") != "approved":
            sys.exit("%s is not an approved promotion" % sys.argv[3])
        tag = p.micro_tag(sys.argv[3], st)
        if tag:
            st["tag"] = tag
            p.rsave(sys.argv[3], st)
            p.keep()
        print(tag or "not tagged")
    elif cmd == "now":
        p.now()
        poke = os.path.join(p.q, "runs", ".sync-poke")
        open(poke, "w").close()
        os.remove(poke)
    elif cmd == "runs":
        print(json.dumps(p.runs_status(), indent=1))
    elif cmd == "approve":
        p.approve(sys.argv[3])
    elif cmd == "adopt":
        # adopt FILE WHAT: a weights file as a trial with its two held-out
        # reads, queued at the next top-up.
        jid = p.adopt(open(sys.argv[3]).read(), " ".join(sys.argv[4:]) or os.path.basename(sys.argv[3]))
        p.keep()
        print("%s: queued with its two held-out reads at the next top-up" % jid)
    elif cmd == "push-check":
        st = p.push_check()
        print("push to %s %s: %s" % (st["url"] or st["remote"], st["branch"], "ok" if st["ok"] else "NO: " + st["detail"]))
        sys.exit(0 if st["ok"] else 1)
    elif cmd == "evidence":
        ev = p.evidence()
        for k, v in sorted(ev.items(), key=lambda kv: -(kv[1]["held_mean"] or -99)):
            print("%-58s held %s  families %-9s %s" % (k, " ".join("%+.2f" % h[0] for h in v["held"]), v["families"],
                                                      "current" if v.get("current") else "older defaults"))
    else:
        sys.exit(__doc__)
