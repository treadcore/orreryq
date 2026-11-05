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
    # Montage page follows plan/montage.json; open N plays film N in this machine's own player.
    if argv[2:3] == ["make"]:
        background([sys.executable, "-I", os.path.join(HERE, "montage.py"), q.d] + argv[2:])
        print("montage: begun; the Montage page follows it")
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


VERBS = {"nets": nets, "growth": growth, "recordings": recordings, "bridge": bridge, "montage": montage, "videos": videos}
