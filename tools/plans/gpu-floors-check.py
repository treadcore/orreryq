#!/usr/bin/env python3
"""gpu-floors-check: a milestone the game refuses takes its floors with it (the planner's gpu_floors_unrefused).

    python3 -I tools/plans/gpu-floors-check.py [PLANNER]      ends PASSED, or says which claim failed

On a scratch queue, a maze home whose ladder is M0001 (standing) and M0002 (elected after it, its floors in
force, then refused by the game), and segments examined against M0001 whose gauntlet reads give M0001's share
beside each champion. A planner pass (crucible_ladder, as the keeper's pass calls it) must set the floors to
M0001's measured share less 1/sqrt(256) and say so in a flag; a standing milestone's floors must stay; a top
no segment has met falls back to its own share when elected; and the floors the next election sets are
written down as that milestone's. Given an older planner (PLANNER) the first claim shows its fault: the
floors of 15 November's refused M0049 stood for four days and no segment could meet them.
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "treadcore.py")
spec = importlib.util.spec_from_file_location("planner_under_check", SRC)
tc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tc)

FAILED = []
HOME = "crucible-world-hybrid-forest-nav"
FILES = ["C7 a pillbox from outside its ring", "T3 build a base: take and hold", "T2 take the base"]


def claim(ok, words, more=""):
    print("%s  %s%s" % ("ok" if ok else "FAILED:", words, "" if ok else "   " + str(more)))
    if not ok:
        FAILED.append(words)


def gauntlet(path, champ, ref_name, ref):
    """A CUDA gauntlet's tsv as crucible writes it: a row a file a brain (file, brain, passed, runs, share, se, ...)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("file\tbrain\tpassed\truns\tshare\tse\tx\ty\n")
        for name, shares in (("champion", champ), (ref_name, ref)):
            for k, v in zip(FILES, shares):
                f.write("%s\t%s\t%d\t256\t%.4f\t0.02\t0\t0\n" % (k, name, round(v * 256), v))


def scratch(refused=True, with_reads=True):
    q = tempfile.mkdtemp(prefix="gpu-floors-")
    json.dump({"crucible": {"world": True, "hybrid": True, "forest": True, "nav": True}}, open(os.path.join(q, "plan.json"), "w"))
    json.dump({"hosts": []}, open(os.path.join(q, "config.json"), "w"))
    P = tc.Plan(q)
    P.flags = []
    P.flag = lambda kind, text, key=None, progress=False: P.flags.append(text)
    os.makedirs(P.crucible_dir("milestones", home=HOME))
    for m in ("M0001-calber-cuda-g100", "M0002-boburner-cuda-g200"):
        open(P.crucible_dir("milestones", m + ".bin", home=HOME), "wb").close()
    lad = P.ladder_state(HOME)
    lad["milestones"] = [
        {"id": "M0001-calber-cuda-g100", "job": "x-calber-cuda-1", "island": "calber-cuda", "gen": 100, "made": "2026-11-10T07:40:00", "game": {"refused": False}},
        {"id": "M0002-boburner-cuda-g200", "job": "x-boburner-cuda-2", "island": "boburner-cuda", "gen": 200, "made": "2026-11-15T22:06:00", "elected": True,
         "game": {"refused": refused}}]
    lad["floor_rule"] = 2
    lad["floors"] = {FILES[0]: 0.18, FILES[1]: 0.918, FILES[2]: 0.9375}      # M0002's, as its election left them
    lad["best"] = None
    # M0001's own share when it was elected, and three segments since read beside it.
    gauntlet(os.path.join(q, "results", "x-calber-cuda-1", P.home, "out", "x-calber-cuda-1", "gauntlet.tsv"), [0.30, 0.80, 1.0], "M0000", [0.2, 0.7, 1.0])
    rows = ["time\tjob\tisland\tgen\tyard_win\tagainst\twin\tdraw\tloss\tmargin_se\tladder_mean\tresult"]
    if with_reads:
        for i, (c7, t3) in enumerate(((0.27, 0.78), (0.28, 0.79), (0.29, 0.785))):
            j = "x-whitewolf-cuda-%d" % (10 + i)
            gauntlet(os.path.join(q, "results", j, P.home, "out", j, "gauntlet.tsv"), [0.0, 0.82, 1.0], "M0001-calber-cuda-g100", [c7, t3, 1.0])
            rows.append("2026-11-1%dT10:00:00\t%s\twhitewolf-cuda\t%d\t0.65\tM0001-calber-cuda-g100\t0.1\t0.8\t0.1\t0.5\t0.1\tkept" % (6 + i, j, 300 + i))
    open(P.crucible_dir("lineage.tsv", home=HOME), "w").write("\n".join(rows) + "\n")
    return q, P, lad


# ---- a pass after the game refused the milestone whose election set the floors
q, P, lad = scratch()
P.crucible_ladder([])
f = lad["floors"]
want = {FILES[0]: round(0.28 - 0.0625, 4), FILES[1]: round(0.785 - 0.0625, 4), FILES[2]: 0.9375}
claim(all(abs(f.get(k, -1) - v) < 1e-4 for k, v in want.items()),
      "a pass after M0002 was refused: the floors are M0001's, its mean share beside three champions less 1/16 (C7 0.18 to 0.2175, T3 0.918 to 0.7225)", f)
claim(lad.get("floors_from") == "M0001-calber-cuda-g100", "and they are written down as M0001's", lad.get("floors_from"))
claim(any("M0002-boburner-cuda-g200 was refused" in x and "C7" in x and "T3" in x for x in P.flags), "a flag says which milestone was refused and which floors moved", P.flags)
n = len(P.flags)
P.crucible_ladder([])
claim(len(P.flags) == n and lad["floors"] == f, "the next pass changes nothing more", (P.flags[n:], lad["floors"]))
shutil.rmtree(q)

# ---- a standing milestone's floors stand
q, P, lad = scratch(refused=False)
P.crucible_ladder([])
claim(lad["floors"][FILES[1]] == 0.918 and not P.flags, "a milestone the game has not refused keeps its floors (T3 stays 0.918)", (lad["floors"], P.flags))
shutil.rmtree(q)

# ---- a top no segment has met yet: its own share when it was elected
q, P, lad = scratch(with_reads=False)
P.crucible_ladder([])
claim(abs(lad["floors"][FILES[1]] - (0.80 - 0.0625)) < 1e-4 and any("its own share when it was elected" in x for x in P.flags),
      "with no segment examined against M0001, its own share at its election is used (T3 0.7375)", (lad["floors"], P.flags))
shutil.rmtree(q)

# ---- the next election writes its floors down as its own
q, P, lad = scratch(refused=False)
P.gpu_elected(lad, {"gauntlet": {"share": {"champion": {FILES[0]: 0.5, FILES[1]: 0.9, FILES[2]: 1.0}}, "runs": {}}}, "M0003-calber-cuda-g300")
claim(lad.get("floors_from") == "M0003-calber-cuda-g300" and abs(lad["floors"][FILES[0]] - 0.4375) < 1e-4, "an election writes the floors down as its milestone's", lad)
shutil.rmtree(q)

print("\nFAILED: %d claim(s)" % len(FAILED) if FAILED else "\nPASSED")
sys.exit(1 if FAILED else 0)
