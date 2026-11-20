#!/usr/bin/env python3
"""crucible-lean-check: an island's training leans on the files it lost, and the standing top is a migrant (the
planner's task_leans, TASKS_SH and TOP_SH).

    python3 -I tools/plans/crucible-lean-check.py [PLANNER]      ends PASSED, or says which claim failed

On a scratch queue, a maze home with two CUDA islands, four gauntlet files and the floors of 19 November (C7 0.2148,
C8 0.8281, T2 0.9375, T3 0.7227). calber's last six champions score C7 0.000 (two older ones 0.30); whitewolf's
last six score 0.27 (two older ones 0.000). A planner pass (crucible_jobs, as the keeper's pass calls it) must
write calber a task list in which C7 is half the draws and whitewolf one that draws evenly, flag calber's once,
send each segment its island's list, and train on the folder that list makes. The segment's own commands are then
run in bash on a made-up island: the folder holds C7 three times and the others once, a list naming no file gives
every file once, and the standing top joins the migrants unless it is the net the game ships. Given an older
planner (PLANNER), the first claim shows its fault: every file once, so on 19 November C7 was one draw in 24.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "treadcore.py")
spec = importlib.util.spec_from_file_location("planner_under_check", SRC)
tc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tc)

FAILED = []
HOME = "crucible-world-hybrid-forest-nav"
TOP = "M0001-calber-cuda-g100"
FILES = {"c7-pillbox-outside-its-ring.toml": "C7 a pillbox from outside its ring", "c8-out-of-a-pillboxs-ring.toml": "C8 out of a pillbox's ring",
         "t2-take-the-base.toml": "T2 take the base", "t3-build-a-base.toml": "T3 build a base: take the ground and hold it"}
FLOORS = {"C7 a pillbox from outside its ring": 0.2148, "C8 out of a pillbox's ring": 0.8281, "T2 take the base": 0.9375,
          "T3 build a base: take the ground and hold it": 0.7227}


def claim(ok, words, more=""):
    print("%s  %s%s" % ("ok" if ok else "FAILED:", words, "" if ok else "   " + str(more)))
    if not ok:
        FAILED.append(words)


def gauntlet(path, c7):
    """A CUDA gauntlet's tsv, the champion and the standing top on the same runs; only C7 differs between islands."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("item\tbrain\tpassed\truns\tshare\tse\treaction_median\treaction_n\tfloor\tholds\n")
        for brain, mine in (("champion", c7), (TOP, 0.277)):
            for name in FILES.values():
                v = mine if name.startswith("C7") else 0.9 if name.startswith("C8") else 1.0 if name.startswith("T2") else 0.79
                f.write("%s\t%s\t%d\t256\t%.4f\t0.02\t0\t0\t-\t-\n" % (name, brain, round(v * 256), v))


def scratch(shipped="M0000-calber-cuda-g50"):
    q = tempfile.mkdtemp(prefix="crucible-lean-")
    src = os.path.join(q, "src-crucible")
    os.makedirs(os.path.join(src, "src"))
    os.makedirs(os.path.join(src, "gauntlet"))
    open(os.path.join(src, "src", "crucible.cu"), "w").close()
    open(os.path.join(src, "Makefile"), "w").close()
    for f, name in FILES.items():
        open(os.path.join(src, "gauntlet", f), "w").write('# a file\nname = "%s"\nseconds = 12\n' % name)
    json.dump({"crucible": {"world": True, "hybrid": True, "forest": True, "nav": True, "task_p": 0.5, "source": src}}, open(os.path.join(q, "plan.json"), "w"))
    json.dump({"hosts": [{"name": "calber-cuda", "caps": ["cuda"], "target": "-"}, {"name": "whitewolf-cuda", "caps": ["cuda"], "target": "-"}]},
              open(os.path.join(q, "config.json"), "w"))
    P = tc.Plan(q)
    P.flags = []
    P.flag = lambda kind, text, key=None, progress=False: (P.flags.append(text) if key not in P.__dict__.setdefault("_keys", set()) else None,
                                                         P._keys.add(key))
    P.world_flags = lambda: ""
    os.makedirs(P.crucible_dir("milestones", home=HOME))
    for m in ("M0000-calber-cuda-g50", TOP):
        open(P.crucible_dir("milestones", m + ".bin", home=HOME), "wb").close()
    lad = P.ladder_state(HOME)
    lad["milestones"] = [{"id": "M0000-calber-cuda-g50", "job": "x-calber-cuda-1", "island": "calber-cuda", "gen": 50, "made": "2026-11-09T07:40:00"},
                         {"id": TOP, "job": "x-calber-cuda-2", "island": "calber-cuda", "gen": 100, "made": "2026-11-10T07:40:00", "game": {"refused": False}}]
    lad["floor_rule"], lad["floors"], lad["floors_from"] = 2, dict(FLOORS), TOP
    P.state["bridge"] = {"shipped": shipped}
    rows = ["time\tjob\tisland\tgen\tyard_win\tagainst\twin\tdraw\tloss\tmargin_se\tladder_mean\tresult"]
    for isl, shares in (("calber-cuda", [0.30, 0.30, 0, 0, 0, 0, 0, 0]), ("whitewolf-cuda", [0, 0, 0.27, 0.27, 0.27, 0.27, 0.27, 0.27])):
        for i, c7 in enumerate(shares):
            j = "x-%s-%d" % (isl, 10 + i)
            gauntlet(os.path.join(q, "results", j, P.home, "out", j, "gauntlet.tsv"), c7)
            rows.append("2026-11-1%dT10:00:00\t%s\t%s\t%d\t0.65\t%s\t0.1\t0.8\t0.1\t0.5\t0.1\tkept" % (2 + i, j, isl, 200 + i, TOP))
    open(P.crucible_dir("lineage.tsv", home=HOME), "w").write("\n".join(rows) + "\n")
    return q, P, lad


def listed(P, island):
    try:
        return dict((l.split("\t")[0], int(l.split("\t")[1])) for l in open(P.crucible_dir("tasks", island + ".txt", home=HOME)).read().splitlines())
    except (OSError, IndexError, ValueError):
        return None


def island_run(job, tasks_txt, q):
    """The segment's lines from its rungs to its tasks folder, run in bash on a made-up island: (migrants, the folder)."""
    lines = job["cmd"].split("\n")
    a = next(i for i, l in enumerate(lines) if l.startswith("I="))
    b = next(i for i, l in enumerate(lines) if l.startswith("./crucible"))
    H = tempfile.mkdtemp(prefix="island-", dir=q)
    os.makedirs(os.path.join(H, "ladder"))
    os.makedirs(os.path.join(H, "in"))
    shutil.copytree(os.path.join(P.crucible_src(), "gauntlet"), os.path.join(H, "gauntlet"))
    open(os.path.join(H, "ladder", "slot-0.bin"), "wb").close()
    open(os.path.join(H, "ladder", "slot-1.bin"), "wb").close()
    open(os.path.join(H, "ladder", "ladder.txt"), "w").write("slot-0.bin\tM0000-calber-cuda-g50\nslot-1.bin\t%s\n" % TOP)
    if tasks_txt is not None:
        open(os.path.join(H, "in", "tasks.txt"), "w").write(tasks_txt)
    script = "set -e; H=%s\n%s\necho \"$I\"\n" % (H, "\n".join(lines[a:b]))
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    folder = sorted(os.listdir(os.path.join(H, "tasks"))) if os.path.isdir(os.path.join(H, "tasks")) else []
    return out.stdout.strip().splitlines()[-1] if out.stdout.strip() else out.stderr, folder


# ---- a pass: calber lost C7 in its last six, whitewolf has it in its last six
q, P, lad = scratch()
jobs = P.crucible_jobs()
cal, ww = listed(P, "calber-cuda"), listed(P, "whitewolf-cuda")
claim(cal is not None and cal.get("c7-pillbox-outside-its-ring.toml") == 3 and sum(cal.values()) == 6,
      "calber's last six champions miss C7's floor (0.000 < 0.2148): its list draws C7 three times in six, half the draws", cal)
claim(cal is not None and all(v == 1 for k, v in cal.items() if not k.startswith("c7")), "and every other file once", cal)
claim(ww is not None and set(ww.values()) == {1} and len(ww) == 4,
      "whitewolf's last six hold every floor (C7 0.27; the two older at 0.000 are past the six read): every file once", ww)
claim(len([x for x in P.flags if "calber-cuda's training leans" in x and "C7 0.000 under its floor 0.215" in x and "3 of every 6" in x]) == 1
      and not any("whitewolf" in x for x in P.flags), "a flag says calber leans on C7, its share and floor, and none for whitewolf", P.flags)
n = len(P.flags)
P.crucible_jobs()
claim(len(P.flags) == n, "the next pass raises nothing more", P.flags[n:])
cj = next((j for j in jobs if j["id"].startswith("x-calber-cuda")), None)
claim(cj is not None and any(s["src"].endswith("tasks/calber-cuda.txt") and s["dst"].endswith("/in/tasks.txt") for s in cj["send"])
      and "--tasks $H/tasks " in cj["cmd"] and "--gauntlet $H/gauntlet " in cj["cmd"],
      "calber's segment is sent its list as in/tasks.txt and trains on $H/tasks; its exam still sits $H/gauntlet", cj and (cj["send"][-3:], cj["cmd"][-400:]))

# ---- the segment's own commands on a made-up island
tp = P.crucible_dir("tasks", "calber-cuda.txt", home=HOME)
I, folder = island_run(cj, open(tp).read() if os.path.exists(tp) else None, q)
claim(len(folder) == 6 and len([f for f in folder if f.startswith("c7-")]) == 3, "its tasks folder holds C7 three times and each other file once (crucible draws evenly from the folder)", folder)
claim(I.split(",")[-1].endswith("/rungs/%s.bin" % TOP) and "$H/in/game.bin" in cj["cmd"],
      "the standing top (the ladder's newest rung, %s) joins the migrants beside the shipped net" % TOP, I)
I2, folder2 = island_run(cj, "gone.toml\t5\n", q)
claim(len(folder2) == 4, "a list naming no file of the gauntlet: every file once", folder2)
I3, folder3 = island_run(cj, None, q)
claim(len(folder3) == 4, "no list at all: every file once", folder3)
shutil.rmtree(q)

# ---- the standing top is the shipped net: not sent twice
q, P, lad = scratch(shipped=TOP)
jobs = P.crucible_jobs()
cj = next(j for j in jobs if j["id"].startswith("x-calber-cuda"))
I, _ = island_run(cj, None, q)
claim(not I.endswith("/rungs/%s.bin" % TOP) and "game.bin" in I, "when the game ships the standing top it is a migrant once, as game.bin", I)
shutil.rmtree(q)

# ---- calber has C7 back: it draws evenly again
q, P, lad = scratch()
P.crucible_jobs()
rows = open(P.crucible_dir("lineage.tsv", home=HOME)).read()
for i in range(6):
    j = "x-calber-cuda-%d" % (30 + i)
    gauntlet(os.path.join(q, "results", j, P.home, "out", j, "gauntlet.tsv"), 0.25)
    rows += "2026-11-19T1%d:00:00\t%s\tcalber-cuda\t%d\t0.65\t%s\t0.1\t0.8\t0.1\t0.5\t0.1\tkept\n" % (i, j, 300 + i, TOP)
open(P.crucible_dir("lineage.tsv", home=HOME), "w").write(rows)
P.crucible_jobs()
cal = listed(P, "calber-cuda")
claim(cal is not None and set(cal.values()) == {1} and any("calber-cuda's champions hold every floor again" in x for x in P.flags),
      "six champions at C7 0.25 later, calber's list draws evenly and a flag says so", (cal, P.flags))
shutil.rmtree(q)

print("\nFAILED: %d claim(s)" % len(FAILED) if FAILED else "\nPASSED")
sys.exit(1 if FAILED else 0)
