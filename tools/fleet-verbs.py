#!/usr/bin/env python3
"""fleet-verbs.py -- the console's verbs that run one of the queue's tools: nets, growth, recordings, bridge,
montage, videos, and every verb added after them. fleet-queue.py hands it any verb it does not know itself:

    fleet-queue.py QUEUE VERB ...   ->   VERBS[VERB](queue, argv)

WHY A FILE OF ITS OWN (Paul, 4 November: "look into making blockages minimized"). The keeper restarts when
fleet-queue.py changes on disk, and a restart sends every running job back to the queue: in two days seven
restarts threw away 71 jobs, 6.7 machine-hours, and most of them were for a new button's verb, which the
keeper never runs. A verb here is read fresh each time a page asks for it; changing one restarts nothing.
A verb that changes what the keeper does (start, stop, machine, project, add) stays in fleet-queue.py.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def delegate(q, tool, args):
    """Run a tool of the queue's with the queue first, and pass on what it says and its exit."""
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, tool), q.d] + args, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    sys.exit(r.returncode)


def background(argv, **kw):
    subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, **kw)


def nets(q, argv):
    # The register of the learned nets and its vault (tools/nets.py): refresh, capture, promote, demote,
    # expire, note, forget. Delegated whole, so the Nets page's buttons are one verb each.
    delegate(q, "nets.py", argv[2:])


def growth(q, argv):
    # crucible's generations sampled, the sizes the fleet's generations fill, and the purge
    # (tools/growth.py): refresh, sizes, purge [--do].
    delegate(q, "growth.py", argv[2:])


def recordings(q, argv):
    # The behaviour-cloning recordings (tools/recordings.py): list, recipe, prove, drop [--do], sweep [--do],
    # keep, unkeep, rerecord, read. The verbs that take minutes go to the background, and the page sees their
    # result when the list is written again.
    tool = os.path.join(HERE, "recordings.py")
    if argv[2:3] and argv[2] in ("sweep", "rerecord", "prove", "read", "recipe"):
        background(["sh", "-c", '"$0" -I "$@"; "$0" -I "$1" "$2" list >/dev/null 2>&1', sys.executable, tool, q.d] + argv[2:])
        print("recordings %s: begun in the background" % argv[2])
        sys.exit(0)
    delegate(q, "recordings.py", argv[2:])


def bridge(q, argv):
    # A world milestone shipped as the game's Gladiator, or a clone as the Scholar (tools/bridge.py). Ship
    # tests, commits and pushes on a worktree of origin/main, minutes: in the background, logged.
    if argv[2:3] in (["ship"], ["ship-clone"]) and argv[3:4]:
        log = os.path.join(q.d, "plan", "bridge-ship.log" if argv[2] == "ship" else "clone-ship.log")
        subprocess.Popen(["sh", "-c", '"$0" -I "$@" > "$LOG" 2>&1', sys.executable, os.path.join(HERE, "bridge.py"), q.d] + argv[2:4],
                         env=dict(os.environ, LOG=log), stdin=subprocess.DEVNULL, start_new_session=True)
        print("bridge %s %s: begun; plan/%s says how it went" % (argv[2], argv[3], os.path.basename(log)))
        sys.exit(0)
    delegate(q, "bridge.py", argv[2:])


def montage(q, argv):
    # The generations since the last film, as a film (tools/montage.py). make goes to the background, and the
    # Montage page follows plan/montage.json; open N plays film N in this machine's own player. trailer is the
    # line's short film (the newest generations committed and one champion's duel), plan/trailer.json its state.
    if argv[2:3] in (["make"], ["trailer"]):
        background([sys.executable, "-I", os.path.join(HERE, "montage.py"), q.d] + argv[2:])
        print("%s: begun; %s" % (argv[2], "the Montage page follows it" if argv[2] == "make" else "plan/trailer.json follows it"))
        sys.exit(0)
    if argv[2:3] == ["open"] and argv[3:4] and argv[3].isdigit():
        mp4 = os.path.join(q.d, "archive", "montages", "%04d" % int(argv[3]), "montage.mp4")
        if not os.path.exists(mp4):
            print("no film %s" % argv[3])
            sys.exit(1)
        background(["open" if sys.platform == "darwin" else "xdg-open", mp4])
        print("playing %s" % mp4)
        sys.exit(0)
    delegate(q, "montage.py", argv[2:])


def videos(q, argv):
    # Results, Videos: a film in orrery's output folder opened in this machine's own player, or shown in its
    # file browser. NAME is a file's name in that folder and nothing else: no path reaches here.
    out = os.environ.get("ORRERY_OUTPUT") or os.path.join(os.path.dirname(HERE), "output")
    verb, name = (argv[2:3] or [""])[0], (argv[3:4] or [""])[0]
    path = os.path.join(out, name)
    if verb not in ("open", "show") or not re.match(r"^[\w.-]+\.mp4$", name) or not os.path.isfile(path):
        print("videos open|show NAME: NAME an .mp4 in %s" % out)
        sys.exit(2)
    mac = sys.platform == "darwin"
    background((["open", path] if verb == "open" else ["open", "-R", path]) if mac else ["xdg-open", path if verb == "open" else out])
    print("%s %s" % ("playing" if verb == "open" else "showing", path))
    sys.exit(0)


def crucible(q, argv):
    # `crucible elect`: the forest home elects the window's best at the planner's next pass (the planner's
    # gpu_force reads plan/crucible-elect and removes it): the best candidate since the last GPU generation
    # that held every floor and the yardstick and stepped forward on the weighed gauntlet. Nothing else.
    if argv[2:3] != ["elect"]:
        print("crucible elect: the forest home elects its window's best at the next pass")
        sys.exit(2)
    open(os.path.join(q.d, "plan", "crucible-elect"), "w").close()
    print("crucible elect: asked; the next planner pass elects the window's best, if one held every floor")
    sys.exit(0)


def forget(q, argv):
    # `forget NAME`: a machine on the bench leaves every record the console reads -- the bench in config.json,
    # machines.json, storage.json and the Fleet chapter's orchestrate.json -- so its row is gone, not "Removed".
    # ONLY FROM THE BENCH: a machine still in the queue is removed first, so that its job in hand finishes and
    # nothing pinned to it is stranded (Paul, 6 November, of nasser and xinanjiang: "Forget them"). A return is
    # a fresh Join on the Machines screen.
    import json
    name = argv[2] if len(argv) > 2 else ""
    if not name:
        print("forget NAME: a removed machine leaves the fleet's records")
        sys.exit(2)
    path = os.path.join(q.d, "config.json")
    cfg = json.load(open(path))
    if any(name in (h["name"], h.get("lane_of")) for h in cfg["hosts"]):
        print("%s is in the queue: remove it first, then forget it" % name)
        sys.exit(1)
    gone = []

    def rewrite(file, change):
        f = os.path.join(q.d, file)
        try:
            d = json.load(open(f))
        except (OSError, ValueError):
            return
        if change(d):
            tmp = os.path.join(q.d, "." + file + ".tmp")
            with open(tmp, "w") as out:
                json.dump(d, out, indent=1)
            os.replace(tmp, f)
            gone.append(file)

    def bench(d):
        keep = [h for h in d.get("bench", []) if name not in (h["name"], h.get("lane_of"))]
        hit = len(keep) != len(d.get("bench", []))
        d["bench"] = keep
        return hit

    def by_key(d):
        return d.pop(name, None) is not None

    def fleet(d):
        keep = [m for m in d.get("machines", []) if m.get("name") != name]
        hit = len(keep) != len(d.get("machines", []))
        d["machines"] = keep
        return hit

    rewrite("config.json", bench)
    rewrite("machines.json", by_key)
    rewrite("storage.json", by_key)
    rewrite("orchestrate.json", fleet)
    if not gone:
        print("%s is in none of the fleet's records" % name)
        sys.exit(1)
    q.event("machine forgotten", host=name)
    print("%s forgotten: %s; a return is a fresh Join" % (name, ", ".join(gone)))
    sys.exit(0)


def boots(q, argv):
    # After a power cut (tools/boots.py): check [--force] [--host NAME], accept NAME, show. The keeper
    # asks for a check by itself; Check now and Accept on Settings, After a cut, are these.
    delegate(q, "boots.py", argv[2:])


VERBS = {"boots": boots, "nets": nets, "growth": growth, "recordings": recordings, "bridge": bridge, "montage": montage, "videos": videos, "crucible": crucible, "forget": forget}
