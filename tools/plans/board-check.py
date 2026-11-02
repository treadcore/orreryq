#!/usr/bin/env python3
"""board-check.py: the planner's board, ratchet and one-map rule, against what Paul asked on
1 November. Plain asserts, no queue touched:  python3 -I tools/plans/board-check.py"""
import importlib.util
import os
import tempfile
import time

s = importlib.util.spec_from_file_location("t", os.path.join(os.path.dirname(os.path.abspath(__file__)), "treadcore.py"))
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
P = m.Plan


def task(i, state="waiting", deps=(), dur=1.0):
    return {"id": i, "title": i, "state": state, "deps": list(deps), "dur_min": dur}


# The most dependents wins, and a blocked task outranks a healthy one with more.
t = P.board([task("a", "running", dur=5), task("b", deps=["a"]), task("c", "blocked", ["b"]), task("d", deps=["c"]), task("e", "not built"), task("f", deps=["e", "d"])])
by = {x["id"]: x for x in t}
assert by["a"]["dependents"] == 4 and by["c"]["dependents"] == 2 and by["e"]["dependents"] == 1
assert by["c"]["essential"] and sum(x["essential"] for x in t) == 1
# A task starts when what it waits on ends, in sequence.
assert by["b"]["start_min"] == by["a"]["end_min"] and by["c"]["start_min"] == by["b"]["end_min"]
# With nothing stuck, the open task most depend on is next.
t = P.board([task("a", "done"), task("b", "running", ["a"]), task("c", deps=["b"])])
assert {x["id"]: x for x in t}["b"]["essential"]


class Ratchet(P):
    """The ease alone: no queue, promotions given."""
    def __init__(self):
        self.state = {}
        self.got = []
    def promotions(self):
        return self.got


r, base = Ratchet(), time.time
assert r.ease() == P.START_EASE
for i in range(3):  # each generation harder
    r._ease = None
    r.got = [(time.time(), "r%d" % i, {})]
    e = r.ease()
assert abs(e - (P.START_EASE - 3 * P.HARDEN)) < 1e-9, e
# Four hours dry: easier; each hour after, easier again; never past the ceiling.
try:
    d = r.state["difficulty"]["since"]
    for hours, want in ((3.9, e), (4.0, e + P.EASE_STEP), (5.5, min(P.EASE_MAX, e + 2 * P.EASE_STEP)), (99, P.EASE_MAX)):
        time.time = lambda: d + hours * 3600
        r._ease = None
        got = r.ease()
        assert abs(got - want) < 1e-9, (hours, got, want)
finally:
    time.time = base

# A read of the generated map alone decides nothing; one of the whole game does.
with tempfile.TemporaryDirectory() as q:
    a, b = os.path.join(q, "one"), os.path.join(q, "all")
    os.makedirs(a), os.makedirs(b)
    open(os.path.join(a, "pooled.txt"), "w").write("every map   +9.00 +/- 1.00 over 55 seeds\ngenerated   +9.00 +/- 1.00 over 55 seeds\n")
    open(os.path.join(b, "pooled.txt"), "w").write("every map   +1.00 +/- 1.00 over 55 seeds\nnaval   +1.00 +/- 1.00 over 28 seeds\nindustry   +1.00 +/- 1.00 over 27 seeds\n")
    assert P.one_map(a) and not P.one_map(b)
    assert P.pool([a]) is None and P.pool([a, b])["every"][0] == 1.0

# A pass on the defaults a generation replaced is read once more; what passed on older ones, what
# is current and what was promoted are not; a read finishing later is still caught; never past the cap.
HOLD_Q = tempfile.mkdtemp()


class C(P):
    def __init__(self, ev):
        self.name, self.state, self.ev, self.got, self.flags, self.CARRY_MAX = "grove", {"adopt": []}, ev, [], [], 2
        self.q = HOLD_Q

    def auto(self):
        return True

    def promotions(self):
        return [(1.0, "r9", {"commit": "new", "status": "self-modified"})]

    def runs(self):
        return [{"id": "r9", "kind": "promote"}]

    def rstate(self, rid):
        return {"status": "self-modified", "candidate": "grove/w9"}

    def parent_of(self, c):
        return "old"

    def same_as(self, a, b):
        return a == b

    def evidence(self):
        return self.ev

    def short(self):
        return "new"

    def flag(self, *a, **k):
        self.flags.append(a)

    def adopt(self, text, what):
        self.state["adopt"].append({"text": text, "what": what})


def cand(commit="old", mean=1.0, current=False):
    return {"weights": "a = 1\n", "commits": [commit, commit], "current": current, "held_mean": mean}


ev = {"grove/w1": cand(mean=0.5), "grove/w2": cand(mean=1.5), "grove/w3": cand(commit="older"), "grove/w4": cand(commit="new", current=True), "grove/w9": cand(), "run/gen1": cand()}
c = C(ev)
assert c.carry_passes() == ["grove/w2", "grove/w1"], "strongest first, only the one step back"
assert all(x["reads"] == 1 for x in c.state["adopt"]) and "carried to" in c.state["adopt"][0]["what"]
assert c.carry_passes() == [], "once"
ev["grove/w5"] = cand()
assert c.carry_passes() == [], "the cap holds"
c = C({"grove/w1": cand()})
c.CARRY_MAX = 0
assert c.carry_passes() == [], "0 is off"
c = C({"grove/w1": cand()})
c.state["carried"] = {"for": "r8", "names": ["grove/w1"]}
assert c.carry_passes() == ["grove/w1"], "a new generation is a new count"

# A retreat takes the proof's bar; a find, the generation's.
c = C({})
c.state["anchor_trials"] = ["w5"]
assert c.anchor_short("grove/w5", {"held": [[0.38, 0.51], [0.18, 0.58]]}), "w4845's reads do not undo a generation"
assert not c.anchor_short("grove/w5", {"held": [[2.0, 0.4], [2.0, 0.4]]}), "z 7 does"
assert not c.anchor_short("grove/w6", {"held": [[0.38, 0.51]]}), "only an anchor is held to it"

# What a person holds does not promote or carry itself, whatever it reads; anything else does.
c = C({"grove/w1": cand()})
assert not c.held_by_a_person("w_pos_fortify = 0.4\n"), "no file, no hold"
open(os.path.join(HOLD_Q, "hold.json"), "w").write('{"w_pos_fortify": 0.4}')
assert c.held_by_a_person("w_pos_fortify = 0.4\nw_near = 2\n")
assert not c.held_by_a_person("w_pos_fortify = 1.5\n")
os.remove(os.path.join(HOLD_Q, "hold.json"))

print("board-check: every check holds")


# ---- The line and documents, against real git: a remote, a clone, and no fleet.
import json
import subprocess
import shutil as _sh


def git(d, *a):
    return subprocess.run(["git", "-C", d, *a], capture_output=True, text=True, check=True).stdout.strip()


def commit(d, path, text, msg):
    f = os.path.join(d, path)
    os.makedirs(os.path.dirname(f), exist_ok=True)
    open(f, "w").write(text)
    git(d, "add", path)
    git(d, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", msg)
    return git(d, "rev-parse", "HEAD")


class Git(P):
    """The line's git, for real; what it reports, kept here."""
    LINE = "orrery/accepted"
    def __init__(self, tc, pd):
        self.tc, self.pd, self.cfg, self._sha = tc, pd, {}, None
        self.state = {"commits": {}}
        self.flags, self.st = [], {}
    def push_target(self):
        return "origin", "main"
    def push_check(self):
        return {"ok": True, "detail": ""}
    def flag(self, kind, text, key=None, progress=False):
        self.flags.append(text)
    def rstate(self, rid):
        return self.st.setdefault(rid, {"status": "self-modified", "commit": "x"})
    def rsave(self, rid, st):
        self.st[rid] = st
    def micro_tag(self, rid, st):
        return None
    def auto(self):
        return True
    def bundle(self):
        pass


def fresh():
    root = tempfile.mkdtemp()
    remote, tc, pd = os.path.join(root, "r.git"), os.path.join(root, "tc"), os.path.join(root, "plan")
    os.makedirs(pd)
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", remote], check=True)
    subprocess.run(["git", "clone", "-q", remote, tc], capture_output=True, check=True)
    git(tc, "checkout", "-q", "-b", "main")
    base = commit(tc, "source/treadcore-brain/src/weights.rs", "a\n", "code")
    git(tc, "push", "-q", "origin", "main")
    return root, tc, pd, base


def line_of(tc, plan, on, *names):
    git(tc, "checkout", "-q", "--detach", on)
    head = on
    for i, n in enumerate(names):
        head = commit(tc, "source/g%d" % i, n, n)
    git(tc, "branch", "-f", plan.LINE, head)
    git(tc, "checkout", "-q", "main")
    plan.state["local_line"] = {"commit": head, "promotions": list(names), "since": "x"}
    return head


root, tc, pd, base = fresh()
g = Git(tc, pd)
head = line_of(tc, g, base, "r1", "r2")
mid = git(tc, "rev-parse", head + "^")
# A report on main: nothing to build, the line where it was, a proof of it still of it.
doc = commit(tc, "reports/a.html", "x", "a report")
commit(tc, "docs/b.md", "x", "a document")
commit(tc, "NOTES.md", "x", "a note")
commit(tc, "scripts/suggest.py", "x", "the fit")
git(tc, "push", "-q", "origin", "main")
assert g.build_tip(git(tc, "rev-parse", "main")) == base
assert g.sha() == head and g.state["local_line"]["commit"] == head
# A proof of the middle of the line lands it on main's documents, and what stood above follows.
g.resolve(upto=mid, carried=1)
tip = git(tc, "rev-parse", "origin/main")
assert tip != mid and git(tc, "rev-parse", "origin/main~1") != base, "on top of the documents"
assert subprocess.run(["git", "-C", tc, "merge-base", "--is-ancestor", doc, tip]).returncode == 0
assert git(tc, "show", "origin/main:source/g0") == "r1"
assert subprocess.run(["git", "-C", tc, "cat-file", "-e", "origin/main:source/g1"]).returncode != 0, "r2 has no proof yet"
assert g.state["local_line"]["promotions"] == ["r2"] and g.st["r1"]["status"] == "approved" and g.st["r1"]["commit"] == tip
top = g.state["local_line"]["commit"]
assert git(tc, "show", top + ":source/g1") == "r2" and git(tc, "rev-parse", top + "^") == tip
g._sha = None
assert g.sha() == top, "what is left stands on main, with no second replay"
# All of it: the line ends.
commit_doc = git(tc, "fetch", "-q", "origin")
git(tc, "merge", "-q", "--ff-only", "origin/main")
commit(tc, "reports/c.html", "x", "another report")
git(tc, "push", "-q", "origin", "main")
g._sha = None
g.resolve()
assert git(tc, "show", "origin/main:source/g1") == "r2" and git(tc, "show", "origin/main:reports/c.html") == "x"
assert not g.state.get("local_line"), "the line is main"
_sh.rmtree(root)

# Source moved on main: a read of the old one lands nowhere, and the line replays.
root, tc, pd, base = fresh()
g = Git(tc, pd)
head = line_of(tc, g, base, "r1", "r2")
mid = git(tc, "rev-parse", head + "^")
moved = commit(tc, "source/game", "x", "the game moved")
git(tc, "push", "-q", "origin", "main")
try:
    g.land(mid)
    raise AssertionError("landed on moved source")
except SystemExit as e:
    assert "source has moved" in str(e)
assert git(tc, "rev-parse", "origin/main") == moved
new = g.sha()
assert new != head and git(tc, "rev-parse", new + "~2") == moved
_sh.rmtree(root)

# ---- A batch: the strongest, and what moves nothing it moves.
b = P.__new__(P)
ev = {"a": {"weights": "# x\nw_a = 1\nw_b = 2\n", "held_mean": 3.0}, "b": {"weights": "w_c = 3\n", "held_mean": 2.0},
      "c": {"weights": "w_a = 9\n", "held_mean": 1.5}, "d": {"weights": "# A/B\ncaps = baseline, -escort\n", "held_mean": 1.0},
      "e": {"weights": "caps = baseline, -escort, -dodge\n", "held_mean": 0.5}, "f": {"weights": "w_a = 1\ncaps = baseline, -bridges\n", "held_mean": 0.2}}
text, also = b.batch(ev, "a")
assert also == ["b", "d"], also
assert m.parse_weights(text) == {"w_a": 1.0, "w_b": 2.0, "w_c": 3.0} and "caps = baseline, -escort\n" in text
assert b.batch({"a": ev["a"]}, "a") == (ev["a"]["weights"], [])

# ---- The window: what passes inside half an hour waits.
class Window(P):
    def __init__(self, got):
        self.state, self.got, self.asked = {}, got, []
    def auto(self):
        return True
    def runs(self):
        return []
    def promotions(self):
        return self.got
    def retry_after_main(self, autos, tried):
        pass
    def evidence(self):
        return {"grove/w1": {"current": True, "families": "holds", "held_mean": 1.0, "held": [(1.0, 0.1)], "weights": "w_a = 1\n"}}
    def anchor_short(self, k, v):
        return False
    def held_by_a_person(self, w):
        return False
    def new_run(self, kind, params, by):
        self.asked.append(params)
        return "r1"
    def flag(self, *a, **k):
        pass


w = Window([(time.time() - 60, "r0", {})])
w.auto_promote()
assert not w.asked, "inside the window"
w = Window([(time.time() - 31 * 60, "r0", {})])
w.auto_promote()
assert w.asked == [{"candidate": "grove/w1"}], w.asked

# ---- How far the defaults have moved, and what the fit may use.
class Drift(P):
    def __init__(self, tables, games):
        self.tables, self.games, self.state = tables, games, {}
    def sha(self):
        return "now"
    def defaults_at(self, c):
        return self.tables[c]
    def game_at(self, c):
        return self.games[c]


d = Drift({"now": {"a": 4.0, "b": 1.0, "on": 1.0}, "old": {"a": 2.0, "b": 1.0, "on": 0.0}, "far": {"a": 400.0, "b": 1.0, "on": 1.0}, "game": {"a": 4.0, "b": 1.0, "on": 1.0}},
          {"now": "4", "old": "4", "far": "4", "game": "3"})
assert d.drift_from("old") == {"old": {"a": 2.0, "on": 0.0}, "drift": 2.0}, "a doubling, and a switch counted as one"
assert d.drift_from("far") is None and d.drift_from("game") is None and d.drift_from("x+") is None

# ---- The far read: a quarter and four times, each dial once, and a retired one comes back.
class Far(P):
    def __init__(self):
        self.state, self.flags, self._ranges = {}, [], {"w_kept": (2.0, 2.0), "w_held": (0.5, 8.0)}
        self.stopped = set()
    def game_at(self, c):
        return "4"
    def sha(self):
        return "now"
    def versions(self):
        return {}, {"bio": (0.0, ["off", "sine"])}
    def unit_weights(self):
        return {"share"}
    def ids(self, *a):
        return self.stopped
    def flag(self, kind, text, key=None, progress=False):
        self.flags.append(text)


root = tempfile.mkdtemp()
dfile = os.path.join(root, "d")
open(dfile, "w").write("w_a = 2\nw_held = 2\nw_kept = 2\nzero = 0\nbio = 1\nshare = 0.5\nfull = 1\n")
f = Far()
files = f.far_trials(100, root, dfile)
said = {os.path.basename(x)[4:-8]: open(x).read().splitlines()[-1] for x in files}
assert said["w_a.lo"] == "w_a = 0.5" and said["w_a.hi"] == "w_a = 8" and said["share.hi"] == "share = 0.75"
assert said["w_held.lo"] == "w_held = 0.5" and said["w_held.hi"] == "w_held = 8"
assert "zero.lo" not in said and "bio.lo" not in said and "w_kept.lo" not in said, "nothing at 0, no choice, no decree"
assert f.flags and f.state["far"]["total"] == 8
two = f.far_trials(2, root, dfile)
assert len(two) == 2
f.far_asked([os.path.basename(x)[:-8] for x in two])
assert os.path.basename(two[0])[4:-8] not in f.state["far"]["todo"]
f.state["far"]["asked"]["w9"] = os.path.basename(two[0])[:-8]
f.stopped = {"w9"}
assert os.path.basename(f.far_trials(1, root, dfile)[0]) == os.path.basename(two[0]), "retired before it ran: it goes back, first"
left = len(f.state["far"]["todo"])
f.far_trials(1, root, dfile)
assert len(f.state["far"]["todo"]) == left and not f.state["far"]["asked"]
_sh.rmtree(root)

print("the line, batches, the window, memory and the far read: every check holds")
