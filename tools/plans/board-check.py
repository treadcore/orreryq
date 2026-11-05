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
    """The line's git, for real; what it reports, kept here. A writer: it plays the keeper's pass."""
    LINE = "orrery/accepted"
    writer = True
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

# A READER REPLAYS NOTHING, AND THE STATE IS THE LINE'S TRUTH (4 November). Main moved: analysis.py's
# planner sees the line as kept and leaves the branch alone; the keeper's pass replays it; a branch
# moved behind the state's back is set back on the next pass, and said.
root, tc, pd, base = fresh()
g = Git(tc, pd)
head = line_of(tc, g, base, "r1")
moved = commit(tc, "source/game", "x", "the game moved")
git(tc, "push", "-q", "origin", "main")
rd = Git(tc, pd)
rd.writer, rd.state = False, json.loads(json.dumps(g.state))
assert rd.sha() == head and git(tc, "rev-parse", g.LINE) == head, "a reader moves nothing"
new = g.sha()
assert new != head and git(tc, "rev-parse", g.LINE) == new, "the writer replays"
git(tc, "branch", "-f", g.LINE, moved)
said = len(g.flags)
g._sha = None
assert g.sha() == new and git(tc, "rev-parse", g.LINE) == new, "set back to the state's head"
assert any("set to %s" % new[:7] in f for f in g.flags[said:]), g.flags[said:]
_sh.rmtree(root)


class Builds(P):
    """A failed build, asked again once."""
    def __init__(self, q):
        self.q, self.state, self.hosts = q, {}, [{"name": "a"}, {"name": "b"}]
    def short(self, sha=None):
        return "abc1234"


bq = tempfile.mkdtemp()
os.makedirs(os.path.join(bq, "failed"))
json.dump({"id": "prep-a-abc1234"}, open(os.path.join(bq, "failed", "17-prep-a-abc1234.json"), "w"))
json.dump({"id": "prep-a-0ld0000"}, open(os.path.join(bq, "failed", "16-prep-a-0ld0000.json"), "w"))
bw = Builds(bq)
assert bw.retry_failed_builds() == set(), "a reader asks nothing again"
bw.writer = True
assert bw.retry_failed_builds() == {"prep-a-abc1234"} and "prep-a-abc1234" not in bw.ids("failed"), "this commit's failed build, set aside"
assert "prep-a-0ld0000" in bw.ids("failed"), "an older commit's is left"
json.dump({"id": "prep-a-abc1234"}, open(os.path.join(bq, "failed", "18-prep-a-abc1234.json"), "w"))
assert bw.retry_failed_builds() == set() and "prep-a-abc1234" in bw.ids("failed"), "once a machine and commit"
_sh.rmtree(bq)
print("the line as kept, set back, and a failed build asked again: every check holds")

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

# ---- A region: its trials inside it, on the log scale, none twice, and a retired one back.
class Regions(P):
    def __init__(self, q):
        self.q, self.state, self.stopped = q, {}, set()
    def ids(self, *a):
        return self.stopped


root = tempfile.mkdtemp()
g = {"id": "g1", "a": "w_a", "b": "w_b", "a0": 1.0, "a1": 4.0, "b0": 0.1, "b1": 0.2, "n": 4}
json.dump({"regions": [g]}, open(os.path.join(root, "regions.json"), "w"))
r = Regions(root)
got = r.region_trials(10, root)
assert len(got) == 4 and os.path.basename(got[0]) == "region-g1-0.weights"
vals = [m.parse_weights(open(f).read()) for f in got]
assert all(1 <= v["w_a"] <= 4 and 0.1 <= v["w_b"] <= 0.2 for v in vals) and len({v["w_a"] for v in vals}) == 4
assert abs(vals[0]["w_a"] - 2.0) < 1e-3, "halfway on the log scale"
assert len(r.region_trials(2, root)) == 2, "never more than asked for at once"
r.state["regions"]["g1"]["jobs"] = {"w1": 0, "w2": 1, "w3": 2, "w4": 3}
assert r.region_trials(10, root) == []
r.stopped = {"w2"}
assert [os.path.basename(f) for f in r.region_trials(10, root)] == ["region-g1-1.weights"]
_sh.rmtree(root)

print("regions: every check holds")

# ---- The temperament matrix's rounds, and the width watch's steps.
class Temper(P):
    def __init__(self, gens):
        self.state, self.gens, self.gone, self.flags, self.runs_asked = {}, gens, set(), [], []
    def promotions(self):
        return [None] * self.gens
    def ids(self, *a):
        return self.gone
    def flag(self, kind, text, key=None, progress=False):
        self.flags.append(text)
    def new_run(self, kind, params, by):
        self.runs_asked.append((kind, params))
        return "r9"
    def sha(self):
        return "now"
    def defaults_at(self, c):
        return {"temper_engage_1": 0.0}


root = tempfile.mkdtemp()
t = Temper(0)
files = t.temper_trials(4, root)
assert len(files) == 4 and len(t.state["temper"]["todo"]) == 24, "twelve entries, each way"
text = open(files[0]).read()
v = m.parse_weights(text)
assert v["bio"] == 1 and v["bio_amount"] == 0 and v["temper_engage_1"] == -0.5, text
assert [r[1]["name"] for r in t.runs_asked] == ["bio-null", "bio-mood", "bio-full"] and all(r[1]["adopt"] == "no" and r[1]["seeds"] == 400 for r in t.runs_asked)
t.temper_asked([os.path.basename(f)[:-8] for f in files])
assert len(t.state["temper"]["todo"]) == 20
t.state["temper"]["asked"]["w1"] = os.path.basename(files[0])[:-8]
t.gone = {"w1"}
assert os.path.basename(t.temper_trials(1, root)[0]) == os.path.basename(files[0]), "retired before it ran: it goes back"
t.gone = set()
t.state["temper"]["todo"] = []
n_runs = len(t.runs_asked)
assert t.temper_trials(4, root) == [] and len(t.runs_asked) == n_runs, "a round done: not again until its time"
t.gens = t.TEMPER_EVERY
assert len(t.temper_trials(4, root)) == 4 and t.state["temper"]["rounds"] == 2
off = Temper(0)
off.TEMPER_EVERY = 0
assert off.temper_trials(4, root) == [] and not off.runs_asked

class Width(Temper):
    home = "fleet"
    def __init__(self, gens, q):
        super().__init__(gens)
        self.q, self.pd, self.st, self.done = q, q, {}, set()
        self.hosts = [{"name": "calber", "target": "u@c", "caps": ["cpu", "gpu"]}]
    def rstate(self, rid):
        return self.st.get(rid, {})
    def prepared(self, host):
        return True
    def prep_id(self, host):
        return "prep-" + host
    def cdir(self):
        return "~/c"
    def ids(self, *a):
        return self.done


w = Width(50, root)
w.WIDTH_EVERY = 0
assert w.width_watch() == [] and not w.runs_asked, "0 is never"
w.WIDTH_EVERY = 20
w.gens = 55
assert w.width_watch() == [] and not w.runs_asked, "the count began when the watch was first seen"
w.gens = 70
assert w.width_watch() == [] and w.runs_asked[0][0] == "record" and w.runs_asked[0][1]["count"] == 240
assert w.width_watch() == [], "waits for its recording"
w.st["r9"] = {"status": "done"}
job = w.width_watch()
assert len(job) == 1 and job[0]["id"] == "width-0001" and all("WIDTH=%d " % x in job[0]["cmd"] for x in (32, 64, 128)) and "~/fleet/width1/shards" in job[0]["cmd"]
assert w.width_watch() == [], "waits for its training"
d = os.path.join(root, "results", "width-0001", "fleet", "out", "width-0001")
os.makedirs(d)
for x, (a, b) in {32: (60.0, 55.0), 64: (66.0, 62.0), 128: (68.0, 63.5)}.items():
    open(os.path.join(d, "w%d.log" % x), "w").write("  drive    %.1f%% +/- 0.1  (always label 3:  40.0%%)  of 100\n  gun      %.1f%% +/- 0.1  (always label 0:  40.0%%)  of 100\n" % (a, b))
w.done = {"width-0001"}
assert w.width_watch() == []
row = w.state["width"]["history"][0]
assert row["verdict"] == "widen" and row["gain"] == 1.75 and row["rows"]["128"]["drive"][0] == 68.0, row
assert "past the bar" in w.flags[-1] and os.path.exists(os.path.join(root, "widths.json"))
assert not w.state["width"].get("run") and not w.state["width"].get("job")
assert w.width_watch() == [] and len(w.runs_asked) == 1, "not again for twenty generations"
w.gens += 20
w.width_watch()
assert len(w.runs_asked) == 2 and w.runs_asked[1][1]["run"] == "width2" and w.runs_asked[1][1]["seed0"] != w.runs_asked[0][1]["seed0"]
_sh.rmtree(root)

print("the temperament's rounds and the width watch: every check holds")

# ---- Long reads go to fast machines, and to any machine if none of those is fit.
class Long(P):
    def __init__(self, q, hosts):
        self.q, self.hosts = q, hosts


root = tempfile.mkdtemp()
os.makedirs(os.path.join(root, "lanes"))
h = [{"name": "a", "caps": ["cpu", "fast"]}, {"name": "b", "caps": ["cpu"]}]
l = Long(root, h)
assert l.long_needs() == "fast"
l.LONG_ON_FAST = 0
assert l.long_needs() == "cpu", "off"
l = Long(root, [{"name": "b", "caps": ["cpu"]}])
assert l.long_needs() == "cpu", "no machine marked"
l = Long(root, [{"name": "a", "caps": ["cpu", "fast"], "paused": True}])
assert l.long_needs() == "cpu", "the only one set aside"
json.dump({"state": "down"}, open(os.path.join(root, "lanes", "a.json"), "w"))
l = Long(root, [{"name": "a", "caps": ["cpu", "fast"]}])
assert l.long_needs() == "cpu", "the only one down"
_sh.rmtree(root)
print("long reads: every check holds")

# ---- Less noise: a floor on the gain, a dial that has just moved, and what a commit says it changed.
class Noise(P):
    HELD_Z = 3.0
    def __init__(self):
        self.state, self.flags = {}, []
    def flag(self, kind, text, key=None, progress=False):
        self.flags.append(text)
    def promotions(self):
        return [(0, "r1", {"commit": "c1"}), (0, "r2", {"commit": "c2"})]
    def parent_of(self, c):
        return c + "^"
    def defaults_at(self, c):
        return {"c1^": {"a": 1.0, "caps:escort": 1.0}, "c1": {"a": 2.0, "caps:escort": 1.0}, "c2^": {"a": 2.0, "caps:escort": 1.0}, "c2": {"a": 2.0, "caps:escort": 0.0}, "now": {"a": 2.0, "caps:escort": 0.0, "b": 5.0}}[c]
    def sha(self):
        return "now"


n = Noise()
assert n.recently_moved() == {"a", "caps:escort"}
# Today's: escort back on at +0.08 +/- 0.04, z 2.0.
assert "under the 0.25" in n.noise("x", {"held": [(0.08, 0.04)], "weights": "caps = baseline, escort\n"})
# A real gain on a dial at rest.
assert n.noise("x", {"held": [(1.34, 0.63)], "weights": "b = 3\n"}) == ""
# A real gain on a dial still moving, under z 3, and over it.
assert "moves a again" in n.noise("x", {"held": [(0.55, 0.5)], "weights": "a = 8\n"})
assert n.noise("x", {"held": [(2.0, 0.5)], "weights": "a = 8\n"}) == ""
assert "moves caps:escort again" in n.noise("x", {"held": [(1.0, 0.5)], "weights": "caps = baseline, escort\n"}), "a switch counts"
# Two reads pool.
assert n.noise("x", {"held": [(0.3, 0.2), (0.3, 0.2)], "weights": "b = 3\n"}) == ""
assert n.noise("x", {"held": [], "weights": "b = 3\n"}) == ""
n.MIN_GAIN, n.SETTLE_GENS = 0, 0
assert n.noise("x", {"held": [(0.08, 0.04)], "weights": "a = 8\n"}) == "", "both off, as it was"
assert n.changed_from_line("a = 8\nb = 5\ncaps = baseline, escort\n") == ["a 2 -> 8", "caps escort off -> on"], "against the line, and only what moves"
assert n.changed_from_line("a = 2\ncaps = baseline, -escort\n") == []
assert m.changed_vars(["a 2 -> 8"])["a"]["value"] == 8.0


class Paused(Window):
    def __init__(self, cands):
        super().__init__([])
        self.cands = cands
    def runs(self):
        return [{"id": "r%d" % i, "kind": "promote", "by": "auto"} for i in range(len(self.cands))]
    def rstate(self, rid):
        return {"status": "failed", "candidate": self.cands[int(rid[1:])], "job": rid}
    def same_failure(self, jobs):
        return True
    def noise(self, k, v):
        return ""


w = Paused(["grove/w9", "grove/w9"])
w.auto_promote()
assert w.asked == [{"candidate": "grove/w1"}], "one candidate failing twice stops no other"
w = Paused(["grove/w8", "grove/w9"])
w.auto_promote()
assert not w.asked, "two candidates failing alike: something all trip on, and auto promotion pauses"
w.auto_promote()
assert not w.asked, "the pause holds until its time is up"
w.state["auto_pause"]["at"] -= w.PAUSE_RESUME_MIN * 60 + 1
w.auto_promote()
assert w.asked == [{"candidate": "grove/w1"}] and {"grove/w8", "grove/w9"} <= set(w.state["auto_tried"]), \
    "after PAUSE_RESUME_MIN it goes on by itself, the two that failed set aside (Paul, 4 November: automate this)"

print("less noise: every check holds")

# ---- what the score does not weigh: a read that gives up building or fights waits for a person ----
class Sides(P):
    def __init__(self):
        self.state, self.flags = {}, []
    def flag(self, kind, text, key=None, progress=False):
        self.flags.append((kind, text))


JOBS = iter(range(10 ** 6))


def census(rows):
    """A census directory from {seed: ((trial built, road, kills, deaths), (rest built, road, kills, deaths))}."""
    d = tempfile.mkdtemp() + "/w%d/20261102-000000/" % next(JOBS)  # the cache knows a read by its job and stamp
    os.makedirs(d)
    open(d + "pooled.txt", "w").write("every map +1.00 +/- 0.10 over 3 seeds\n")
    for seed, (a, b) in rows.items():
        line = "  team %d%s: score 10.0, kills %g, deaths %g, revives 1, built %g, road %g, bridge 0\n"
        with open(d + "g-%s.log" % seed, "w") as f:
            f.write("seed %s on atlantic: trial team 1\n" % seed)
            f.write(line % (0, "", b[2], b[3], b[0], b[1]))
            f.write(line % (1, " (trial)", a[2], a[3], a[0], a[1]))
    return d


LOSES = {s_: ((16 + s_ * 0.1, 6, 17, 18), (20, 6, 17, 18)) for s_ in range(6)}
FIGHTS = {s_: ((20, 6, 17 - s_ * 0.2, 19), (20, 6, 17, 17)) for s_ in range(6)}
FLAT = {s_: ((20 + (-1) ** s_, 6, 17, 17), (20, 6, 17, 17)) for s_ in range(6)}
d_ = Sides.side_read(census(LOSES))
assert abs(d_["built"][0] + 3.75) < 1e-6 and d_["built"][2] == 6 and d_["road"][0] == 0, d_
sd = Sides()
assert [w_.split(" +/-")[0] for w_ in sd.gives_up([census(LOSES)])] == ["built a team -3.75"], "building lost past noise and floor"
assert sd.gives_up([census(FIGHTS)])[0].startswith("kills less deaths a seat"), "fights lost"
assert sd.gives_up([census(FLAT)]) == [], "noise gives up nothing"
assert sd.gives_up(None) == [] and sd.gives_up([tempfile.mkdtemp() + "/"]) == [], "no logs, nothing known, nothing held"
assert sd.gives_up([census({s_: (b_, a_) for s_, (a_, b_) in LOSES.items()})], sign=-1), "the proof's trial is main: a sign"
assert sd.gives_up([census(LOSES)], sign=-1) == [], "the line that builds more gives up nothing"
sd.GIVE_BUILT = 99.0
assert sd.gives_up([census(LOSES)]) == [], "a floor raised on Values lets it through"
sd = Sides()
# LOSES gives up 3.75 of the others' 20, 1.9 times the 10% floor: within the trade rule (2.5), it goes on,
# and a flag says what it traded. HALVES gives up half, 5 times: refused by itself. Neither waits.
assert not sd.trades_away("grove/w1", {"held_dirs": [census(LOSES)], "held_mean": 1.0}) and sd.flags[0][0] == "trade" and "goes on by the trade rule" in sd.flags[0][1]
HALVES = {s_: ((10 + s_ * 0.1, 6, 17, 18), (20, 6, 17, 18)) for s_ in range(6)}
assert sd.trades_away("grove/w3", {"held_dirs": [census(HALVES)], "held_mean": 1.0}) and "refused by the trade rule" in sd.flags[-1][1]
assert not sd.trades_away("grove/w2", {"held_dirs": [census(FLAT)], "held_mean": 1.0})
assert not sd.trades_away("gen3/x", {"held_mean": 1.0}), "a converge run's candidate has no logs here"


class Trades(Window):
    def __init__(self):
        super().__init__([])
    def trades_away(self, k, v):
        return True
    def noise(self, k, v):
        return ""


w = Trades()
w.auto_promote()
assert not w.asked, "a candidate that trades away waits, and asks no promotion"

print("what the score does not weigh: every check holds")

# THE TRADE RULE (Paul, 4 November: "automate this please"). Under its floor nothing is traded; past the
# floor but inside two errors it is noise; past the floor and within TRADE_TIMES of it the trade goes on;
# past that it is refused. 1 refuses every trade past its floor.
tr = P.trade_rule
assert tr([("built a team -2.51", -2.51, 0.23, 1.87)], 2.5)[2] == "within", "r0178's: 13% of 18.7 against a 10% floor, 1.3 times"
assert abs(tr([("built a team -2.51", -2.51, 0.23, 1.87)], 2.5)[1] - 2.51 / 1.87) < 1e-9, "the worst ratio of loss to floor"
assert tr([("built a team -6.0", -6.0, 0.3, 1.87)], 2.5)[2] == "past", "a third of what the others build: refused"
assert tr([("built a team -1.0", -1.0, 0.3, 1.87)], 2.5) == ([], 0.0, None), "under the floor: nothing traded"
assert tr([("built a team -2.5", -2.5, 1.5, 1.87)], 2.5)[2] is None, "past the floor, inside two errors: noise"
assert tr([("kills less deaths a seat -0.2", -0.2, 0.05, 0.1)], 2.5)[2] == "within" and tr([("kills less deaths a seat -0.3", -0.3, 0.05, 0.1)], 2.5)[2] == "past", "fights, a count a seat"
assert tr([("built a team -2.51", -2.51, 0.23, 1.87)], 1.0)[2] == "past", "TRADE_TIMES 1 refuses every trade past its floor"
assert tr([("built", -2.0, 0.2, 1.87), ("road", -3.0, 0.2, 0.8)], 2.5)[2] == "past", "the worst of them decides"
assert tr([("built", -2.0, 0.2, None)], 2.5)[2] is None, "no floor known: nothing judged"
print("the trade rule: ok")

# POOLED WHILE THE QUESTION STANDS (Paul, 4 November: "yes pool the reads"). Each proof of one line
# against one main adds its seeds to those before: two proofs each inside the noise (z 2.1) pool past
# HELD_Z (z 3.0) and the line goes to main; a new commit on the line starts the pool again.
pr_root = tempfile.mkdtemp()
pr_tc = os.path.join(pr_root, "tc")
os.makedirs(pr_tc)
for c in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "main"]):
    subprocess.run(["git", "-C", pr_tc, "-c", "user.name=t", "-c", "user.email=t@t"] + c, check=True)
PR_MAIN = subprocess.run(["git", "-C", pr_tc, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
subprocess.run(["git", "-C", pr_tc, "update-ref", "refs/remotes/origin/main", PR_MAIN], check=True)
subprocess.run(["git", "-C", pr_tc, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "line"], check=True)
PR_LINE = subprocess.run(["git", "-C", pr_tc, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


class Proof(P):
    PROOF_EVERY_MIN = 60
    def __init__(self):
        self.q, self.tc, self.home = pr_root, pr_tc, "fleet/q-grove"
        self.cfg = {"weights": {"held_seeds": 400}}
        self.state = {"local_line": {"commit": PR_LINE, "promotions": ["r1"]}}
        self.flags, self.resolved, self.finished = [], [], set()
    def flag(self, kind, text, key=None, progress=False):
        self.flags.append((kind, text))
    def cpu_ready(self):
        return True
    def ids(self, *states):
        return self.finished
    def _built_everywhere(self):
        return True
    def push_target(self):
        return "origin", "main"
    def defaults_at(self, c):
        return {"a": 1.0} if c == PR_MAIN else {"a": 2.0}
    def census_cmd(self, text, seeds, seed0, jid):
        return "true"
    def long_needs(self):
        return "cpu"
    def after_host(self):
        return None
    def resolve(self, upto=None, carried=None):
        self.resolved.append(upto)
    def read(self, jobs, d="-1.00", se="0.665"):
        """Each job's census, the line ahead of main by 1 a seat: the pair reads z 2.13 alone."""
        for j in jobs:
            o = os.path.join(self.q, "results", j, self.home, "out", j, "20261104-200000")
            os.makedirs(o)
            open(os.path.join(o, "pooled.txt"), "w").write("every map   %s +/- %s over 400 seeds\n" % (d, se))
            self.finished.add(j)


pv = Proof()
first = pv.line_proof()
assert [j["id"] for j in first] == ["pv0001", "pv0002"] and pv.state["proof"]["main"] == PR_MAIN, "a proof knows the main it reads against"
pv.read(["pv0001", "pv0002"])
assert pv.line_proof() == [] and not pv.resolved, "one proof inside the noise: no landing"
assert pv.state["proof"]["last"]["z"] == 2.13 and pv.state["proof"]["last"]["reads"] == 1, pv.state["proof"]
pv.state["proof"]["last_at"] = 0
second = pv.line_proof()
assert [j["id"] for j in second] == ["pv0003", "pv0004"] and "read 2, pooled" in second[0]["title"], second[0]["title"]
pv.read(["pv0003", "pv0004"])
pv.line_proof()
assert pv.state["proof"]["last"]["reads"] == 2 and pv.state["proof"]["last"]["seeds"] == 1600, pv.state["proof"]
assert pv.state["proof"]["last"]["z"] >= 3.0 and pv.resolved == [PR_LINE], "two proofs pooled pass where neither did"
# A generation lands on the line: its first proof pools with nothing.
subprocess.run(["git", "-C", pr_tc, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "g2"], check=True)
PR_LINE2 = subprocess.run(["git", "-C", pr_tc, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
pv.state["local_line"]["commit"], pv.state["proof"]["last_at"], pv.resolved = PR_LINE2, 0, []
third = pv.line_proof()
assert "pooled" not in third[0]["title"], third[0]["title"]
pv.read([j["id"] for j in third])
pv.line_proof()
assert pv.state["proof"]["pooled"]["jobs"] == ["pv0005", "pv0006"] and pv.state["proof"]["last"]["z"] == 2.13 and not pv.resolved, "a new commit starts the pool"
# A proof begun before the pool knew its main (today's pv0049 and pv0050) pools with nothing.
pv.state["proof"] = {"jobs": ["pv0005", "pv0006"], "head": PR_LINE2, "n": 1, "pooled": {"head": PR_LINE2, "main": None, "jobs": ["pv0001"]}}
pv.line_proof()
assert pv.state["proof"]["pooled"]["jobs"] == ["pv0005", "pv0006"], "no main known, no pool"
_sh.rmtree(pr_root)
print("the line's proof, pooled: every check holds")

# A PROMOTION ON THE LINE, ON A MACHINE THAT HAS NO LINE (5 November, r0182: macmini, `fatal: invalid
# reference: orrery/accepted`). The Mac holds the line as a branch; the machine has main and nothing
# else. The job takes the bundle, names the line by its commit, and its commit comes home.
pb_root = tempfile.mkdtemp()
pb_remote, pb_tc, pb_mc, pb_pd = (os.path.join(pb_root, n) for n in ("r.git", "tc", "mc", "plan"))
os.makedirs(pb_pd)
subprocess.run(["git", "init", "-q", "--bare", "-b", "main", pb_remote], check=True)
subprocess.run(["git", "clone", "-q", pb_remote, pb_tc], capture_output=True, check=True)
git(pb_tc, "checkout", "-q", "-b", "main")
commit(pb_tc, "source/treadcore-brain/src/weights.rs", "a\n", "code")
git(pb_tc, "push", "-q", "origin", "main")
subprocess.run(["git", "clone", "-q", pb_remote, pb_mc], capture_output=True, check=True)


class Promo(P):
    LINE = "orrery/accepted"
    def __init__(self, line):
        self.q, self.tc, self.pd, self.home = pb_root, pb_tc, pb_pd, "fleet/q-grove"
        self.state = {"local_line": {"commit": line, "promotions": ["r1"]}} if line else {}


assert Promo(None).promote_base("r9") == ("", "origin/main", []), "no line: main, as everywhere"
pb_head = line_of(pb_tc, Promo(None), git(pb_tc, "rev-parse", "main"), "r1")
git(pb_tc, "bundle", "create", "-q", os.path.join(pb_pd, "accepted.bundle"), "orrery/accepted", "^origin/main")
fetch_line, pb_base, pb_send = Promo(pb_head).promote_base("r9")
assert pb_base == pb_head and pb_send[0]["src"] == os.path.join(pb_pd, "accepted.bundle") and pb_send[0]["dst"].startswith("~/")
home = os.path.join(pb_root, "home")
os.makedirs(home)
sh = lambda c: subprocess.run(["bash", "-c", c], cwd=pb_mc, capture_output=True, text=True, env=dict(os.environ, HOME=home))
r = sh("git worktree add -q -b promote/old ../old orrery/accepted")
assert r.returncode != 0 and "invalid reference: orrery/accepted" in r.stderr, "the machine has no line by name: the night's fault"
dst = pb_send[0]["dst"]
r = sh("mkdir -p $(dirname %s) && cat %s > %s" % (dst, pb_send[0]["src"], dst))
assert r.returncode == 0, r.stderr
r = sh("set -e; git fetch -q origin\n%sgit worktree add -q -b promote/x ../wt %s\ncd ../wt && echo b > source/treadcore-brain/src/weights.rs\n"
       "git -c user.name=t -c user.email=t@t commit -q -am promoted\ngit bundle create -q %s/promote.bundle %s..promote/x"
       % (fetch_line, pb_base, pb_root, pb_base))
assert r.returncode == 0, r.stderr
git(pb_tc, "fetch", "-q", os.path.join(pb_root, "promote.bundle"), "promote/x:refs/heads/promote/x")
assert git(pb_tc, "rev-parse", "promote/x^") == pb_head, "built on the line, and home again"
_sh.rmtree(pb_root)

# THE VERDICT IS A LINE OF ITS OWN: the command at the log's head holds every verdict's words.
fq = tempfile.mkdtemp()
os.makedirs(os.path.join(fq, "logs"))
CMD = ("$ set -e -o pipefail\ngit worktree add -q -b $B $W orrery/accepted\ncargo test || { echo 'the tests failed: not committed'; exit 1; }\n"
       "cargo test families || { echo 'a family fell under its floor: not committed'; exit 1; }\n")
open(os.path.join(fq, "logs", "r1-promote.log"), "w").write(CMD + "fatal: invalid reference: orrery/accepted\n[1]+  Exit 128  ( set -e; echo 'the tests failed: not committed' )\n")
open(os.path.join(fq, "logs", "r2-promote.log"), "w").write(CMD + "test weights::x ... FAILED\nthe tests failed: not committed\n")
open(os.path.join(fq, "logs", "r3-promote.log"), "w").write(CMD + "family raid 0.41 under 0.50\na family fell under its floor: not committed\n")
fp = P.__new__(P)
fp.q = fq
assert fp.promote_failure("r1-promote") == "the promotion job failed (fatal: invalid reference: orrery/accepted): see logs/r1-promote.log"
assert fp.promote_failure("r2-promote").startswith("the brain's tests failed")
assert fp.promote_failure("r3-promote").startswith("a family fell under its floor (raid)")
_sh.rmtree(fq)


# Not the candidate's fault: tried again at once, once.
class Fault(Window):
    def __init__(self, why):
        super().__init__([])
        self.state["auto_tried"] = ["grove/w1"]
        self.why, self.saved, self.flags, self.q = why, {}, [], "/nonexistent"
    def runs(self):
        return [{"id": "r1", "kind": "promote", "by": "auto"}]
    def rstate(self, rid):
        return self.saved.get(rid) or {"status": "failed", "candidate": "grove/w1", "job": "r1-promote", "why": "the brain's tests failed: see logs"}
    def rsave(self, rid, st):
        self.saved[rid] = st
    def ids(self, *subs):
        return {"r1-promote"} if "failed" in subs else set()
    def promote_failure(self, jid):
        return self.why
    def flag(self, kind, text, key=None, progress=False):
        self.flags.append(text)
    def noise(self, k, v):
        return ""
    def trades_away(self, k, v):
        return False
    def guard_holds(self, k):
        return True
    retry_after_main = P.retry_after_main
    def build_tip(self, sha):
        return sha


f_ = Fault("the promotion job failed (fatal: invalid reference: orrery/accepted): see logs/r1-promote.log")
f_.tc = os.path.dirname(os.path.abspath(__file__))
f_.auto_promote()
assert f_.asked == [{"candidate": "grove/w1"}] and "before it was judged" in f_.flags[0], (f_.asked, f_.flags)
assert f_.saved["r1"]["why"].startswith("the promotion job failed"), "the record says what happened"
f_.asked = []
f_.state["auto_tried"].append("grove/w1")
f_.auto_promote()
assert not f_.asked, "once: a fault that repeats is the machine's"
f_ = Fault("the brain's tests failed: see logs/r1-promote.log")
f_.tc = os.path.dirname(os.path.abspath(__file__))
f_.auto_promote()
assert not f_.asked, "its own tests: it waits for main to move, as before"
print("a promotion on the line from any machine, its verdict read, a fault tried again once: every check holds")

# THE HOUSEKEEPING IS THE KEEPER'S (change C): what is stale is begun, each behind its lock, and a
# minute later nothing is begun twice; the recordings' list and sweep one at a time, the sweep each
# six hours. The tools here are stand-ins that write what they were asked.
cq = tempfile.mkdtemp()
ct = os.path.join(cq, "tools")
os.makedirs(os.path.join(cq, "plan"))
os.makedirs(ct)
for t in ("analysis.py", "nets.py", "growth.py", "recordings.py"):
    open(os.path.join(ct, t), "w").write("import sys, time\ntime.sleep(0.5)\nopen(sys.argv[1] + '/asked', 'a').write(' '.join(['%s'] + sys.argv[2:]) + '\\n')\n" % t[:-3])
asked = lambda: sorted(open(os.path.join(cq, "asked")).read().splitlines()) if os.path.exists(os.path.join(cq, "asked")) else []
wait = lambda n: [time.sleep(0.05) for _ in range(100) if len(asked()) < n]
assert m.chores(cq, ct) == ["analysis", "nets", "growth", "recordings list"]
assert m.chores(cq, ct) == [], "behind their locks: nothing begun twice, the list's while it runs"
wait(4)
assert asked() == ["analysis", "growth refresh", "nets refresh", "recordings list"], asked()
for doc in ("analysis.json", "nets.json", "growth.json", "recordings.json"):
    open(os.path.join(cq, "plan", doc), "w").write("{}")
time.sleep(0.3)
assert not os.path.exists(os.path.join(cq, "plan", "recordings.json.lock.run")), "the list's mark goes when it ends"
assert m.chores(cq, ct) == ["recordings sweep"], "fresh documents; the sweep's turn"
wait(5)
assert "recordings sweep --do" in asked() and os.path.exists(os.path.join(cq, "plan", "recordings.json.sweep"))
time.sleep(0.3)
assert m.chores(cq, ct) == [], "the sweep, once in six hours"
_sh.rmtree(cq)
print("the housekeeping, the keeper's: every check holds")

# THE ROUND TABLE (Paul, 5 November: "a blame tab"). A queued job belongs to the machine the forecast
# deals it to, and waits on its turn there, its build there, or a job another machine runs; a run
# whose last job came back and whose next is not asked is handed back to the planner.
class Table(P):
    TIMELINE_H = 6
    def __init__(self):
        self.q, self.qcfg = tempfile.mkdtemp(), {"hosts": [{"name": "a", "caps": ["cpu"]}, {"name": "b", "caps": ["cpu"]}, {"name": "a-cuda", "caps": ["cuda"]}], "plan_s": 300}
        self.state = {}
    def ids(self, *subs):
        return {"prep-b-c1", "x-1"} if "done" in subs else set()
    def queue_jobs(self):
        return [{"id": "x-3", "needs": "host:a-cuda", "after": ["x-2"]}, {"id": "w1", "needs": "cpu", "after_host": "prep-{host}-c2"},
                {"id": "h1", "needs": "cpu", "after": ["e1"]}, {"id": "w2", "needs": "cpu"}]
    def runs(self):
        return [{"id": "r7", "kind": "patch"}, {"id": "r8", "kind": "census"}]
    def rstate(self, rid):
        return {"status": "running"}


tb = Table()
live = {"a": {"job": "e1", "state": "running", "since": time.time() - 60}, "b": {"state": "idle"}, "a-cuda": {"job": "x-2", "state": "running"}}
tl = {"past_h": 6, "busy": {"a": {"first": 300.0, "other": 54.0}, "a-cuda": {"islands": 360.0}}, "dealt": {"x-3": "a-cuda", "w1": "a", "h1": "b", "w2": "b"}}
recent = [{"id": "r7-k03", "host": "b", "ended": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - 120)), "seconds": 90}]
bl = tb.blame_view(live, tl, recent)
kinds = {(e["from"], e["to"], e["kind"]): e["jobs"] for e in bl["edges"]}
assert kinds == {("a-cuda", "a-cuda", "turn"): ["x-3"], ("a", "a", "build"): ["w1"], ("b", "a", "after"): ["h1"], ("b", "b", "turn"): ["w2"]}, kinds
assert [h["run"] for h in bl["planner"]] == ["r7"] and bl["planner"][0]["host"] == "b", "r7's step came back from b; r8 has nothing back yet"
seat = {s_["host"]: s_ for s_ in bl["nodes"]}
assert seat["a"]["busy_pct"] == 98.3 and seat["a"]["help_pct"] == 84.7 and seat["a-cuda"]["gpu"] and seat["a-cuda"]["help_pct"] == 100.0
assert not seat["b"]["gpu"] and seat["b"]["busy_pct"] == 0.0
_sh.rmtree(tb.q)
print("the round table: every check holds")

# CHAINS ADVANCE WHEN THEY RETURN (change B): a transform's step and a held-out read carry `replan`; the
# step goes ahead of new trials; a first read, a read-on and a GPU segment are left to the pass.
cm = P.chain_marks([{"id": "r0187-k17", "title": "transform r0187: step 17 of 30"}, {"id": "h0812", "title": "held-out read 1 of w10900 (400 seeds)", "priority": "high"},
                    {"id": "e9400", "title": "read on 2 of w10901"}, {"id": "w10902", "title": "trial"}, {"id": "x-calber-cuda-3110"},
                    {"id": "r0183-k02", "title": "spsa r0183: step 2 of 30"}])
assert [bool(j.get("replan")) for j in cm] == [True, True, False, False, False, False], cm
assert cm[0]["priority"] == "high" and cm[1]["priority"] == "high" and "priority" not in cm[2]
print("chains advance when they return: every check holds")

# THE HELD-OUT READ IN PIECES (change C) AND THE BACKGROUND JOB. A read is four jobs of a hundred seeds on
# any CPU machine, made one census when all are back; a piece that failed is asked again, twice at most;
# a piece on other defaults than the newest weighs nothing and is asked again. The background job asks
# pieces of likely trials' first reads ahead of time, last in the queue, within its budget; the read,
# asked later, takes them as its own. Nothing waits on a background job, and nothing waits in a circle.
import glob
import re
TC_DIR = os.path.expanduser(os.environ.get("TREADCORE", "~/code/treadcore"))


class Held(P):
    LINE = "orrery/accepted"
    def __init__(self, q):
        self.q, self.home, self.tc, self.writer = q, "fleet/q-grove", TC_DIR, True
        self.cfg = {"weights": {"held_seeds": 400, "held_seed0": 60000000, "seeds": 55, "secs": 900, "map": "all"}}
        self.state = {"held_n": 7, "held_read": []}
        self.flags, self.done, self.gone, self.seq, self.queued = [], set(), set(), {}, []
        self.hosts = [{"name": n} for n in ("a", "b", "c")]
        self.commit_of = {}
    def ids(self, *subs):
        return (self.done if "done" in subs else set()) | (self.gone if ("failed" in subs or "stopped" in subs) else set())
    def flag(self, kind, text, key=None, progress=False):
        self.flags.append(text)
    def short(self, sha=None):
        return "abc1234"
    def sha(self):
        return "abc1234abc1234"
    def census_cmd(self, text, seeds, seed0, out_id):
        return "census %d from %d as %s" % (seeds, seed0, out_id)
    def census_commit(self, d):
        return self.commit_of.get(d.rstrip("/").split(os.sep)[-2], "abc1234")
    def same_class(self, c1, c2):
        return c1 == c2
    def game_at(self, c):
        return "8+score1"
    def sequential(self):
        return self.seq
    def queue_jobs(self):
        return self.queued


def piece_result(q, pid, seeds):
    d = os.path.join(q, "results", pid, "fleet/q-grove/out", pid, "20261105-120000")
    os.makedirs(d)
    # The census's own lines: each seed's difference, as pool.sh reads them.
    open(os.path.join(d, "g-%d.log" % seeds[0]), "w").write("brain_census: difference a seat, a seed: %s\n" % " ".join("%.1f" % ((s % 7) - 3) for s in seeds))
    open(os.path.join(d, "run.env"), "w").write("SEEDS=%d\nSEED0=%d\nCOMMIT=abc1234\nHOST=a\n" % (len(seeds), seeds[0]))
    open(os.path.join(d, "trial.weights"), "w").write("w_a = 1\n")
    open(os.path.join(d, "pooled.txt"), "w").write("every map +0.00 +/- 0.10 over %d seeds (a piece)\n" % len(seeds))


hq = tempfile.mkdtemp()
hp = Held(hq)
js = hp.held_read("w0042", 1, "w_a = 1\n", high=True)
assert [j["id"] for j in js] == ["h0007-p1", "h0007-p2", "h0007-p3", "h0007-p4"], [j["id"] for j in js]
assert [j["cmd"] for j in js][2] == "census 100 from 60001400200 as h0007-p3".replace("60001400200", str(60000000 + 200000 * 7 + 200))
assert all(j["needs"] == "cpu" and j["priority"] == "high" and not re.match(r"held-out read \d of", j["title"]) for j in js), js[0]
assert hp.state["held_n"] == 8 and hp.state["held_split"]["h0007"]["seed0"] == 61400000
for i, j in enumerate(js):
    hp.done.add(j["id"])
    piece_result(hq, j["id"], list(range(61400000 + 100 * i, 61400000 + 100 * i + 100)))
# One failed: asked again as r1, and nothing merged yet.
hp.done.discard("h0007-p3")
hp.gone.add("h0007-p3")
again = hp.held_merge()
assert [j["id"] for j in again] == ["h0007-p3r1"] and "h0007" in hp.state["held_split"], again
hp.done.add("h0007-p3r1")
piece_result(hq, "h0007-p3r1", list(range(61400200, 61400300)))
# One on other defaults than the newest: it weighs nothing, and is asked again.
hp.commit_of["h0007-p1"] = "0ld0000"
again = hp.held_merge()
assert [j["id"] for j in again] == ["h0007-p1r1"], again
hp.done.add("h0007-p1r1")
piece_result(hq, "h0007-p1r1", list(range(61400000, 61400100)))
assert hp.held_merge() == [] and "h0007" not in hp.state["held_split"] and hp.state["held_merged"]["h0007"].startswith("held-out read 1 of w0042")
merged = glob.glob(os.path.join(hq, "results/h0007/fleet/q-grove/out/h0007/*/"))[0]
assert len(glob.glob(merged + "g-*.log")) == 4 and "SEEDS=400" in open(merged + "run.env").read() and "SEED0=61400000" in open(merged + "run.env").read()
if os.path.exists(os.path.join(TC_DIR, "scripts", "pool.sh")):
    assert open(merged + "pooled.txt").read().startswith("every map") and " over 400 seeds" in open(merged + "pooled.txt").read(), open(merged + "pooled.txt").read()
assert hp.held_pairs() == {"w0042": [merged]}, hp.held_pairs()
assert [d.split("/out/")[1].split("/")[0] for d in hp.census_dirs()] == ["h0007"], "the pieces are not reads of their own"
# Three failures of one piece drop the read, and say so.
js2 = hp.held_read("w0043", 2, "w_b = 2\n", high=False)
assert all("priority" not in j for j in js2)
for t in range(3):
    hp.gone.add(hp.state["held_split"]["h0008"]["slots"]["2"])
    hp.held_merge()
assert "h0008" not in hp.state["held_split"] and any("failed three times" in f for f in hp.flags)

# The background job: the likely trials, strongest first, one piece a free lane, within the day's budget.
hp.seq = {"w0050": {"status": "read on", "stage": 3, "z": 2.4, "text": "w_c = 3\n"}, "w0051": {"status": "read on", "stage": 1, "z": 2.9, "text": "x"},
          "w0052": {"status": "read on", "stage": 2, "z": 1.2, "text": "x"}, "w0053": {"status": "reading", "stage": 2, "z": 1.7, "text": "w_d = 4\n"},
          "w0054": {"status": "dropped", "stage": 4, "z": 3.0, "text": "x"}}
bg = hp.ahead_jobs()
assert [(j["id"], j["priority"], j["background"]) for j in bg] == [("h0009-p1", "low", True), ("h0010-p1", "low", True)], bg
assert all(j["title"].startswith("held-out piece ahead of time:") for j in bg)
assert hp.state["held_ahead"]["w0050"]["hid"] == "h0009" and hp.state["held_split"]["h0009"]["stamp"]["commit"] == "abc1234abc12"
hp.queued = [dict(j) for j in bg]
more = hp.ahead_jobs()
assert [j["id"] for j in more] == ["h0009-p2"], "one queued a lane at most: three lanes, two queued, the strongest trial's next piece"
hp.AHEAD_PER_DAY = len(hp.state["ahead_log"])
hp.queued = []
assert hp.ahead_jobs() == [], "the day's budget spent"
# w0050 is asked for its read: it takes the reserved id and seeds, asks only the pieces not read ahead,
# and its queued piece goes first.
os.makedirs(os.path.join(hq, "queue"), exist_ok=True)
qf = os.path.join(hq, "queue", "%d-h0009-p1.json" % (int(time.time() * 1000) + 10 ** 11))
json.dump(bg[0], open(qf, "w"))
js3 = hp.held_read("w0050", 1, "w_c = 3\n", high=True)
assert [j["id"] for j in js3] == ["h0009-p3", "h0009-p4"] and "ahead_only" not in hp.state["held_split"]["h0009"], js3
raised = glob.glob(os.path.join(hq, "queue", "*-h0009-p1.json"))
assert len(raised) == 1 and int(os.path.basename(raised[0]).split("-")[0]) < time.time() * 1000, "raised ahead of the standing work"
rj = json.load(open(raised[0]))
assert rj["priority"] == "high" and "background" not in rj and rj["title"].startswith("held-out piece 1 of 4")
# Nothing waits on a background job, nor in a circle.
hp.queued = [{"id": "bgx", "background": True}, {"id": "c1", "after": ["c2"]}, {"id": "c2", "after": ["c3"]}]
kept = hp.graph_lint([{"id": "n1", "after": ["bgx"]}, {"id": "c3", "after": ["c1"]}, {"id": "n2", "after": ["c1"]}])
assert [j["id"] for j in kept] == ["n2"], kept
assert any("background job or in a circle" in f for f in hp.flags)
cm = P.chain_marks([{"id": "h0012-p2", "title": "held-out piece 2 of 4 of read 1 of w1"}, {"id": "h0013-p1", "background": True, "title": "x"}])
assert cm[0].get("replan") and not cm[1].get("replan")
_sh.rmtree(hq)
print("the held-out read in pieces, and the background job: every check holds")

# THE WRITER'S FAILURE TRIED AGAIN (5 November, w10839: set-defaults.py could not write `wing_leash`,
# whose default was a constant's name, and no job was ever asked): once main has moved since, as a
# failed test is. And a held-out piece goes to the fast machines while one is up.
wq = tempfile.mkdtemp()


class Writer(Fault):
    def __init__(self):
        super().__init__("")
        self.q = wq
    def rdir(self, rid):
        return os.path.join(wq, "runs", rid)
    def runs(self):
        return [{"id": "r1", "kind": "promote", "by": "auto", "params": {"candidate": "grove/w1"}}]
    def rstate(self, rid):
        # As r0193 saved it: no candidate, the writer's words.
        return {"status": "failed", "why": "no such weight in weights.rs: wing_leash (nothing written)"}


os.makedirs(os.path.join(wq, "runs", "r1"))
st_file = os.path.join(wq, "runs", "r1", "state.json")
open(st_file, "w").write("{}")
os.utime(st_file, (1, 1))  # failed long before the commit main is at now
wr = Writer()
wr.tc = os.path.dirname(os.path.abspath(__file__))
wr.auto_promote()
assert wr.asked == [{"candidate": "grove/w1"}] and any("could not be written" in f for f in wr.flags), (wr.asked, wr.flags)
_sh.rmtree(wq)


class Fast(Held):
    LONG_ON_FAST = True
    def __init__(self, q):
        super().__init__(q)
        self.hosts = [{"name": "slow", "caps": ["cpu"]}, {"name": "quick", "caps": ["cpu", "fast"]}]


fq_ = tempfile.mkdtemp()
fp = Fast(fq_)
pieces = fp.held_read("w0060", 1, "w_e = 5\n")
assert {j["needs"] for j in pieces} == {"fast"}, [j["needs"] for j in pieces]
fp.seq = {"w0061": {"status": "read on", "stage": 3, "z": 2.0, "text": "w_f = 6\n"}}
assert [j["needs"] for j in fp.ahead_jobs()] == ["cpu"], "the background job's go anywhere"
_sh.rmtree(fq_)
print("the writer's failure tried again, and pieces to the fast machines: every check holds")

# FOLLOW A CHAIN (the Timeline, 5 November): each job names the chain it is a link of, so a block
# hovered on the page lights every other link wherever it ran.
links = [("w10839", "trial"), ("e9400", "read on 2 of w10839 (300 seeds more, z +1.10 on 55)"),
         ("h0812", "held-out read 1 of w10839 (400 seeds)"), ("h0812-p2", "held-out piece 2 of 4 of read 1 of w10839 (100 seeds)"),
         ("h0813-p1", "held-out piece ahead of time: 1 of 4 of read 1 of w10839 (100 seeds)"),
         ("r0196-promote", "promote grove/w10839: tests and families on a branch"),
         ("r0187-k17", "transform r0187: step 17 of 30"), ("clone-003-train", ""), ("prep-boburner-2180ded", ""),
         ("x-calber-cuda-3110", ""), ("pv0070", "the line 0724007 against main"), ("f0251", "families: kite, castle")]
got = [P.chain_of(i, t) for i, t in links]
assert got == ["w10839"] * 6 + ["r0187", "clone-003", "build 2180ded", "island calber-cuda", "line 0724007", "f0251"], got
print("following a chain: every check holds")
