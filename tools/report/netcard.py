#!/usr/bin/env python3
"""netcard.py QUEUE [HOME]  -- a card beside every GPU milestone: what it is, where it came from, what it uses, what it did.

Paul, 6 November: "What kind of information should we store about the net and weights we are training, something
we can store to increase information to use in the future." A milestone is 20 to 23 KB of floats and nothing else;
what the fleet learned about it lies in six places (the planner's ladder, elect.tsv, the bridge's reads, the
footage, the segment's log) or nowhere. The card gathers it beside the file, HOME/milestones/ID.card.json, and an
index HOME/cards.json:

  lineage    its parent (the milestone it had to beat), the segment, the island, the generation, when
  election   the weighed gauntlet z, the yardstick z, the bar, the shares, kept or refused
  shape      inputs, hidden, outputs, weights
  senses     the L2 norm of each group of inputs' first-layer columns (rays, body, rules, world, route, arcs,
             memory): what the net leans on. A group near the norm of mutation's drift is not used.
  moved      the same per group, of the difference from the milestone it had to beat (the ladder's "after"; not
             always its forebear: an island's population may come down another line, and then it moves far)
  game       the bridge's census of it as the Gladiator, if one was read
  footage    its tests' passes, if filmed
  training   (Paul, 6 November: "Net cards every pass") what made it: the build's flags, the segment's seed, the
             crucible commit the working copy was at when the segment started, the source's size, the task mix, the
             net and the rules as the segment's console says them
  gauntlet   each gauntlet file's share, the champion's own, as its segment read it

The planner writes them every ten minutes (netcard_watch).

The cards cost one read of each file; a refresh only writes the new ones.
"""
import array
import csv
import json
import math
import os
import re
import subprocess
import sys

CRUCIBLE = os.path.expanduser("~/code/treadcore/crucible")
TREADCORE = os.path.dirname(CRUCIBLE)

SHAPES = {2340: (35, 32, 4), 5236: (55, 48, 4), 5766: (64, 48, 6)}
GROUPS = [("rays", 0, 24), ("body", 24, 32), ("rules", 32, 35), ("world", 35, 55), ("route", 55, 59), ("arcs", 59, 62), ("memory", 62, 64)]


def weights(path):
    w = array.array("f")
    w.frombytes(open(path, "rb").read())
    return w


def groups(w):
    nin, h, nout = SHAPES[len(w)]
    out = {}
    for name, a, z in GROUPS:
        if z > nin:
            continue
        out[name] = round(math.sqrt(sum(w[j * nin + i] ** 2 for j in range(h) for i in range(a, z))), 3)
    return out


def moved(w, p):
    """Per group, the L2 norm of the change from the parent; a parent narrower is read as widened (new columns zero)."""
    nin, h, _ = SHAPES[len(w)]
    pin = SHAPES[len(p)][0]
    out = {}
    for name, a, z in GROUPS:
        if z > nin:
            continue
        s = 0.0
        for j in range(h):
            for i in range(a, z):
                pv = p[j * pin + i] if i < pin else 0.0
                s += (w[j * nin + i] - pv) ** 2
        out[name] = round(math.sqrt(s), 3)
    return out


_REFLOG = None


def main_at(when):
    """crucible's main at a time (YYYY-MM-DDTHH:MM:SS, local): the newest move at or before it. Until crucible
    joined treadcore (10 November 2026), from the reflog it kept as a repository of its own, saved as
    docs/main-reflog.tsv; after, from treadcore's commits that touched crucible/."""
    global _REFLOG
    if _REFLOG is None:
        _REFLOG = []
        kept = os.path.join(CRUCIBLE, "docs", "main-reflog.tsv")
        if os.path.exists(kept):
            for line in open(kept):
                if line.strip() and not line.startswith("#"):
                    t, h = line.rstrip("\n").split("\t")[:2]
                    _REFLOG.append((t, h))
        joined = max((t for t, _ in _REFLOG), default="")
        r = subprocess.run(["git", "-C", TREADCORE, "log", "--date=format-local:%Y-%m-%dT%H:%M:%S", "--format=%cd %h", "--", "crucible"],
                           capture_output=True, text=True)
        for line in r.stdout.splitlines():
            t, _, h = line.partition(" ")
            if t > joined:
                _REFLOG.append((t, h))
        _REFLOG.sort(reverse=True)
    before = [h for t, h in _REFLOG if t <= when]
    return before[0] if before else None


def segment_facts(q, job, started):
    """What a segment's own records say of the net it made: its log, its console, its gauntlet."""
    out = {}
    log = os.path.join(q, "logs", job + ".log")
    if os.path.exists(log):
        txt = open(log, errors="replace").read()
        m = re.search(r"make -s ([^;>]*?) NVCC=", txt)
        out["flags"] = m.group(1).strip() if m else None
        m = re.search(r"--seed (\d+)", txt)
        out["seed"] = int(m.group(1)) if m else None
        m = re.search(r"crucible\.cu -> \S+ \((\d+) bytes", txt)
        out["source_bytes"] = int(m.group(1)) if m else None
    od = os.path.join(q, "results", job, "fleet", os.path.basename(q.rstrip("/")) and "q-" + os.path.basename(q.rstrip("/")), "out", job)
    con = os.path.join(od, "console.txt")
    if os.path.exists(con):
        for line in open(con, errors="replace"):
            for key, pre in (("net", "# net "), ("rules", "# rules: "), ("tasks", "# tasks: ")):
                if line.startswith(pre) and key not in out:
                    out[key] = line[len(pre):].strip()
    if started:
        # Where main WAS when the segment started: the reflog says when the working copy moved, which a commit's own
        # date does not (a branch fast-forwarded in the evening carries the afternoon's dates).
        out["crucible_commit"] = main_at(started)
    shares = None
    g = os.path.join(od, "gauntlet.tsv")
    if os.path.exists(g):
        shares = {}
        for row in csv.reader(open(g), delimiter="\t"):
            if len(row) > 4 and row[1] == "champion":
                try:
                    shares[row[0]] = float(row[4])
                except ValueError:
                    pass
    return out, shares


def main(a):
    if not a:
        print(__doc__)
        sys.exit(2)
    q = os.path.abspath(a[0])
    st = json.load(open(os.path.join(q, "plan", "state.json")))
    homes = [a[1]] if len(a) > 1 else [k.split(":", 1)[1] for k in st if k.startswith("crucible_ladder:")]
    bridge = {}
    bp = os.path.join(q, "plan", "bridge.json")
    if os.path.exists(bp):
        for r in json.load(open(bp)).get("reads") or []:
            if r.get("label"):
                bridge[r["label"]] = {k: r.get(k) for k in ("diff", "se", "holds", "vs_rules", "read")}
    started = {}
    ev = os.path.join(q, "events.jsonl")
    if os.path.exists(ev):
        for line in open(ev, errors="replace"):
            if '"started"' in line and '"crucible"' in line:
                try:
                    e = json.loads(line)
                    started[e["job"]] = e["t"]
                except (ValueError, KeyError):
                    pass
    for home in homes:
        hd = os.path.join(q, home)
        lad = st.get("crucible_ladder:" + home) or {}
        elect = {}
        ep = os.path.join(hd, "elect.tsv")
        if os.path.exists(ep):
            for row in csv.DictReader(open(ep), delimiter="\t"):
                res = row.get("result") or ""
                if res.startswith("milestone "):
                    elect[res.split()[1].rstrip(":")] = {k: row.get(k) for k in ("zg", "zy", "bar", "champion_share", "against_share", "margin_se", "time")}
        fp = os.path.join(q, "archive", "footage", home, "index.json")
        foot = {g["id"]: {"passed": g["passed"], "runs": g["runs"], "tests": {k: v["passed"] for k, v in g["results"].items()}}
                for g in (json.load(open(fp))["generations"] if os.path.exists(fp) else [])}
        cards, new = [], 0
        for m in lad.get("milestones", []):
            path = os.path.join(hd, "milestones", m["id"] + ".bin")
            if not os.path.exists(path):
                continue
            card_path = os.path.join(hd, "milestones", m["id"] + ".card.json")
            w = weights(path)
            if len(w) not in SHAPES:
                continue
            nin, h, nout = SHAPES[len(w)]
            parent = m.get("after")
            pp = os.path.join(hd, "milestones", (parent or "") + ".bin")
            card = {"id": m["id"], "home": home, "made": m.get("made"), "carried": bool(m.get("carried")), "parent": parent,
                    "segment": m.get("job"), "island": m.get("island"), "generation": m.get("gen"), "margin_se": m.get("margin_se"),
                    "election": elect.get(m["id"]), "shape": {"inputs": nin, "hidden": h, "outputs": nout, "weights": len(w)},
                    "senses": groups(w), "moved": moved(w, weights(pp)) if parent and os.path.exists(pp) and len(weights(pp)) in SHAPES else None,
                    "game": bridge.get(m["id"]), "footage": foot.get(m["id"])}
            if m.get("job") and not m.get("carried"):
                card["training"], card["gauntlet"] = segment_facts(q, m["job"], started.get(m["job"]))
            old = json.load(open(card_path)) if os.path.exists(card_path) else None
            if old != card:
                json.dump(card, open(card_path, "w"), indent=1)
                new += 1
            cards.append(card)
        json.dump({"home": home, "cards": cards}, open(os.path.join(hd, "cards.json"), "w"), indent=1)
        print("%s: %d cards, %d written" % (home, len(cards), new))


if __name__ == "__main__":
    main(sys.argv[1:])
