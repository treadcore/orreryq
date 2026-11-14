#!/usr/bin/env python3
"""battles.py QUEUE [OUT.json] [--duels N] [--seed S] [--labels M0001,M0015,...] -- the recordings a film reenacts.

Paul, 13 November: "taking the data and the generations of the recording showing the bots and their traces, in a
multidimensional battle decision best of montage background, behind the blocks and animations ... This could be 3d
assets that run from the recording files. design it in the easy way, simply."

The recording is crucible's own trace (`--trace`, tools/montage.py's): each champion named plays N duels in ONE
arena from ONE start, the dice choosing each duel's opponent, and every step of every duel is written, both tanks,
their shells, the pillboxes. One generation's N duels from one start are the "multidimensional decision": the same
moment, taken N ways. This asks a GPU island for that trace of a few generations (the first champion, the net the
game shipped for a week, the net it ships now, the newest standing), and keeps what a reenactment needs, small:

  arena          its size, pillars, pillboxes, groves, walls
  generations[]  label, generation, won/lost/drawn, and
    ghosts       the champion's path in every duel, a point each second: the fan of what it might have done
    best[]       its best duels (won, by score; then the rest), every step: both tanks' place, heading and
                 armour, both shells, the pillboxes' health, and what each shell did that step

docs/process/battles.json by default: a megabyte or two, read by tools/report/process_blend_film.py.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import montage as mt  # noqa: E402

LABELS = ("M0001", "M0015", "M0030", "M0032")
BEST = 4


def opt(a, name, default):
    if name in a:
        i = a.index(name)
        v = a[i + 1]
        del a[i:i + 2]
        return v
    return default


def main(a):
    duels, seed, labels = int(opt(a, "--duels", 48)), int(opt(a, "--seed", 11)), opt(a, "--labels", ",".join(LABELS)).split(",")
    q = os.path.abspath(a[0])
    out = a[1] if len(a) > 1 else os.path.join(os.path.dirname(os.path.dirname(HERE)), "docs", "process", "battles.json")
    homename, cfg = mt.home_of(q)
    hd = os.path.join(q, homename)
    _, opps, ms = mt.choose(q, hd, None, 6)
    chapters = [m for m in ms if m["name"] in labels]
    for c in chapters:
        c["facts"] = mt.facts_of(hd, c["island"], c["gen"])
    work = tempfile.mkdtemp(prefix="battles-")
    tpath, tracer, lines = mt.trace(q, chapters, opps, cfg, duels, seed, None, work)
    tr = mt.Trace(tpath)
    R = mt.TREC
    gens = []
    for ci, (c, ch) in enumerate(zip(chapters, tr.champs)):
        order = sorted(range(tr.nd), key=lambda d: (ch["outcome"][d] != 1, -ch["fit"][d]))
        ghosts = []
        for d in range(tr.nd):
            n = ch["lasted"][d]
            ghosts.append([[round(v, 1) for v in tr.at(ci, d, t)[:2]] for t in list(range(0, n, 10)) + [n - 1]])
        best = []
        for d in order[:BEST]:
            n = ch["lasted"][d]
            opp = tr.opp_of[d]
            best.append({"duel": d, "outcome": ch["outcome"][d], "fit": round(ch["fit"][d], 2), "steps": n,
                         "against": opps[opp]["name"] if 0 <= opp < len(opps) else "a sparring partner",
                         "rec": [[round(v, 2) for v in tr.at(ci, d, t)] for t in range(n)]})
        gens.append({"label": c["label"], "name": c["name"], "island": c["island"], "gen": c["gen"],
                     "won": sum(1 for o in ch["outcome"] if o == 1), "lost": sum(1 for o in ch["outcome"] if o == -1), "drawn": sum(1 for o in ch["outcome"] if o == 0),
                     "ghosts": ghosts, "best": best})
    data = {"traced_on": tracer, "duels": tr.nd, "seed": seed, "dt": tr.dt, "arena": tr.arena, "hp": tr.hp, "pb_hp": tr.pb_hp, "gun": tr.gun, "pb_range": tr.pb_range,
            "pillars": [[round(v, 2) for v in p] for p in tr.pillars], "boxes": [[round(v, 2) for v in p] for p in tr.boxes],
            "groves": [[round(v, 2) for v in p] for p in tr.groves], "walls": [[round(v, 2) for v in p] for p in tr.walls],
            "fields": "x y heading armour shell_x shell_y shell_life (the champion), the same seven (its opponent), the pillboxes' health, shell_did champion, shell_did opponent, pillbox hits on each",
            "generations": gens}
    json.dump(data, open(out, "w"), separators=(",", ":"))
    print("%s: %d generations, %d duels each on %s, %d reenacted; %.1f MB" % (out, len(gens), tr.nd, tracer, sum(len(g["best"]) for g in gens), os.path.getsize(out) / 1e6))
    for g in gens:
        print("  %s  generation %s  won %d lost %d drawn %d" % (g["label"], format(g["gen"], ","), g["won"], g["lost"], g["drawn"]))


if __name__ == "__main__":
    main(sys.argv[1:])
