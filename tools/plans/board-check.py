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
