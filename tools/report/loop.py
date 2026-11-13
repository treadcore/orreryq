#!/usr/bin/env python3
"""loop.py QUEUE OUTDIR -- the diagrams and numbers of *The Loop Closed* (docs/loop-lab-report.md): the learning
process as it stands after 13 November, with the game's verdict coming back to the cards, floors that give,
and what more CUDA cards would and would not speed. The numbers are the queue's: the ladder and what the game
refused, the bridge's reads by island, the yardstick's rows, the first reads of w_smooth's parts, the watch.
`--redraw OUTDIR` draws from data.json."""
import glob
import importlib.util
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import checked as ck  # noqa: E402
import forward as fw  # noqa: E402
import outgrowing as og  # noqa: E402


def gather(q):
    m, p = og.planner(q)
    st = json.load(open(os.path.join(q, "plan", "state.json")))
    key = [k for k in st if k.startswith("crucible_ladder:")][-1]
    ms = st[key]["milestones"]
    isles = {}
    for x in ms:
        i = isles.setdefault(x.get("island") or "?", {"made": 0, "read": 0, "refused": 0, "credited": 0, "diffs": []})
        i["made"] += 1
        g = x.get("game")
        if g:
            i["read"] += 1
            i["refused"] += bool(g.get("refused"))
            i["credited"] += bool(g.get("credited"))
            i["diffs"].append(g["diff"])
    for i in isles.values():
        i["mean"] = statistics.mean(i["diffs"]) if i["diffs"] else None
    made = sorted(x["made"] for x in ms if x.get("made") and not x.get("carried"))
    days = (og.ep(made[-1]) - og.ep(made[0])) / 86400 if len(made) > 1 else 0
    parts = []
    for jid, name in (("w20032", "the turret's confirmation"), ("w20033", "the stance's advance scalar"), ("w20034", "resupply by the doctrine alone"),
                      ("w20035", "the rung's confirmation"), ("w20026", "all of w_smooth 0.525")):
        c = p.job_census(jid)
        ds = glob.glob(os.path.join(q, "results", jid, p.home, "out", jid, "*", ""))
        side = p.side_read(ds[0]) if ds else {}
        held = [p.job_census(d.rstrip("/").split(os.sep)[-2]) for d in p.held_pairs().get(jid, [])]
        parts.append({"job": jid, "name": name, "census": [c[0], c[1]] if c else None, "kd": list(side["kd"][:2]) if side and side.get("kd") else None,
                      "held": [[h[0], h[1]] for h in held if h]})
    s = importlib.util.spec_from_file_location("deploy_watch", os.path.join(os.path.dirname(HERE), "deploy-watch.py"))
    dw = importlib.util.module_from_spec(s)
    s.loader.exec_module(dw)
    return {"home": key.split(":", 1)[1], "milestones": len(ms), "standing_top": p.ladder_top(st[key]), "isles": isles, "ladder_days": days, "made": len(made),
            "rating": (json.load(open(os.path.join(q, "plan", "rating.json"))) if os.path.exists(os.path.join(q, "plan", "rating.json")) else {}).get("rows") or [],
            "parts": parts, "watch": dw.watch(q), "shipped": (st.get("bridge") or {}).get("shipped")}


def dia_loop():
    f = ck.Flow(0, 0, "Diagram 1: the learning process, both loops, with what comes back")
    f.T(20, 14, "THE GAME'S OWN BRAIN, on the CPU machines", "ttl")
    f.N("fit", 20, 26, 190, "fn", "the search", ["the fit's trials; one dial", "at a time; the A/B versions"])
    f.N("read", 260, 26, 190, "fn", "the reads", ["stages from 150 seeds;", "held out, read on to six"])
    f.N("gate", 500, 26, 200, "fn", "the gates", ["gain 0.25; floors that give;", "a trade by its gain"])
    f.N("line", 750, 26, 190, "data", "the line", ["one block at a time,", "settling: 9,600 seeds"])
    f.A("fit", "read").A("read", "gate").A("gate", "line")
    f.N("main", 750, 136, 190, "out", "main", ["proved at z 3: pushed"])
    f.N("off", 500, 136, 200, "out", "orphaned", ["refused: off the line;", "its trial is a candidate still"])
    f.A("line", "main", "proved").A("line", "off", "refused")
    f.A("off", "read", "read again", dash=True)
    f.N("yard", 750, 226, 190, "fn", "the yardstick", ["main today against main", "of three fixed days"])
    f.A("main", "yard", dash=True)
    f.T(20, 308, "THE NETS, on the cards", "ttl")
    f.N("isl", 20, 320, 190, "fn", "the islands, a card each", ["2,048 nets, 100 generations", "a segment, in the arena"])
    f.N("ms", 260, 320, 190, "data", "a milestone", ["elected on the card:", "the gauntlet, the ladder"])
    f.N("br", 500, 320, 200, "fn", "the bridge", ["read in the game as the", "Gladiator: 2 x 192 seeds"])
    f.A("isl", "ms").A("ms", "br")
    f.N("ref", 750, 320, 190, "out", "refused by the game", ["NEW: no rung; its island", "sends no migrants"])
    f.A("br", "ref", "refused")
    f.N("ship", 500, 440, 200, "out", "shipped", ["past two errors:", "nets/gladiator.bin on main"])
    f.A("br", "ship", "credited")
    f.N("mig", 260, 440, 190, "data", "migrants, each segment", ["NEW: the shipped net; the", "standing islands' champions"])
    f.A("ship", "mig", dash=True)
    f.A("mig", "isl")
    return f.key().svg()


def dia_floor():
    f = ck.Flow(0, 0, "Diagram 2: a floor that gives")
    f.N("c", 20, 70, 180, "data", "a brain's score on a file", ["a family, or a gauntlet", "file: a share of runs held"])
    f.N("t", 260, 70, 200, "fn", "floors.py / FLOOR_GIVE", ["against the file's floor,", "with a give of 0.05"])
    f.A("c", "t")
    f.N("a", 520, 10, 250, "out", "on its floor", ["holds; nothing moves"])
    f.N("b", 520, 80, 250, "out", "under by no more than the give", ["passes; the floor moves down to", "what it scored, in the commit"])
    f.N("d", 520, 170, 250, "out", "under by more: a collapse", ["refused, nothing written: a raid", "on the held ground at 0 of 400"])
    f.A("t", "a").A("t", "b").A("t", "d")
    f.N("n", 20, 170, 440, "note", "what it changes", ["G20 at 58% of 60% stopped seven candidates in a week: it passes now,", "and G20's floor becomes 0.57. A floor only moves down here; up is a person's."])
    return f.key().svg()


def dia_gpu():
    f = ck.Flow(0, 0, "Diagram 3: what more CUDA cards speed, and what they do not")
    f.N("n", 20, 20, 190, "data", "N cards", ["an island each; today 3"])
    f.N("p", 270, 10, 230, "fn", "proposals: x N", ["champions an hour and milestones", "a day rise with the cards"])
    f.N("d", 270, 90, 230, "fn", "breadth: N lineages", ["each island its own population;", "the game's net seeds them all"])
    f.N("w", 270, 170, 230, "fn", "the wait for a credited net", ["1 - (1 - p)^N a day, p a card's chance:", "about 2.7 days at 3 cards, 1.7 at 6"])
    f.A("n", "p").A("n", "d").A("n", "w")
    f.N("b", 560, 10, 220, "fn", "the bridge: x N reads", ["384 seeds a milestone: at 6 cards", "about 2% of the CPU fleet"])
    f.A("p", "b")
    f.N("g", 560, 170, 220, "out", "a better Gladiator, sooner", ["only if the arena rewards", "what the game does"])
    f.A("w", "g").A("b", "g")
    f.N("x", 20, 270, 480, "note", "what a card does not speed", ["The dials of the game's own brain are read in whole games on the CPUs:", "178,000 seeds a day whatever the cards. A card reads no census.", "And the arena agreed with the game at -0.40 over 22 milestones:", "more cards make more of what the arena likes."])
    f.N("y", 560, 270, 220, "note", "so, before the fourth card", ["mend the exam; keep the", "game's verdict coming back"])
    return f.key().svg()


def dia_flags():
    f = ck.Flow(0, 0, "Diagram 4: a flag that wants a person, and one that does not")
    f.N("e", 20, 70, 170, "data", "something happened", ["the planner or the", "keeper raises a flag"])
    f.N("q", 240, 70, 200, "fn", "does anything wait", ["on a person?"])
    f.A("e", "q")
    f.N("p", 500, 10, 280, "out", "progress: said once, no Acknowledge", ["a candidate passed; a generation landed;", "NEW: a candidate refused by a family's floor;", "NEW: a milestone refused by the game"])
    f.N("a", 500, 130, 280, "out", "attention: on the page until acknowledged", ["a machine that cannot be reached; a failed", "promotion; NEW: the watch reading BAD"])
    f.A("q", "p", "no").A("q", "a", "yes")
    f.N("x", 20, 190, 420, "note", "13 November", ["Seven of 23 flags were families doing their work. One flag file was", "not JSON, and Acknowledge all died on it before reaching any other."])
    return f.key().svg()


DIAGRAMS = {"loop": dia_loop, "floor": dia_floor, "gpu": dia_gpu, "flags": dia_flags}


def main(a):
    if a[0] == "--redraw":
        out = os.path.abspath(a[1])
    else:
        q, out = os.path.abspath(a[0]), os.path.abspath(a[1])
        os.makedirs(out, exist_ok=True)
        json.dump(gather(q), open(os.path.join(out, "data.json"), "w"), indent=1, default=str)
    first = True
    for k, fn in DIAGRAMS.items():
        open(os.path.join(out, "dia-%s.html" % k), "w").write((og.STYLE if first else "") + fn() + "\n")
        first = False
    print("wrote %s: %d diagrams" % (out, len(DIAGRAMS)))


if __name__ == "__main__":
    main(sys.argv[1:])
