#!/usr/bin/env python3
"""telemetry.py QUEUE pull|show|chart|fit -- each machine's temperatures, brought back to the queue.

Paul, 15 November: "calculate a Tau, or a time constant ... model how reactive in the time constant
to the step function of turning a system on fully on and off ... Show all the temperatures on a
graphs chart plots over time, many plots overlaid ... Collect the information about these systems,
setting up a system in orrery to receive telemetry back ... But first we need to collect the data."

THE COLLECTOR is tools/fleet-telemetry.sh, on each Linux machine, as the user, no root: one line of
key=value every 5 seconds (the CPUs' use and clock, every temperature the kernel has, fans and watts
where a chip tells, the card). `pull` is one connection a machine, of its own (never the shared one
the jobs ride): the collector is put there if it is absent or older than this repository's, started
if it is not running (after a boot, say), and the lines written since the last pull come back to
QUEUE/telemetry/MACHINE/YYYYMMDD.log. The keeper's housekeeping asks every five minutes.

  pull [MACHINE...]   bring the new lines back; plan/telemetry.json says what each machine last read
  show                each machine's last sample, every channel
  chart [HOURS] [OUT.html]   the heat page (heat_page.py): the fleet's watts, a row a machine by its CPU, opened on a click (default 72 hours; made at every pull)
  model               the energy balance (thermal.py): each machine's watts, each fitted part's R, C
                      and where it settles, the fleet's heat; plan/thermal.json, for Orrery's Heat page
  fit [MACHINE] [HOURS]      first-order fits (a time constant and the level it settles at) to the
                      steps the queue made: a channel after the CPUs' use or the card's watts changed
"""
import json
import math
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
COLLECTOR = os.path.join(HERE, "fleet-telemetry.sh")
EVERY = 5
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ControlMaster=no", "-o", "ControlPath=none"]

REMOTE = r'''
[ -r /proc/stat ] || { echo "@@none"; exit 0; }
mkdir -p ~/.fleet-queue/telemetry && cd ~/.fleet-queue || exit 1
cat > .ft.new <<'FLEET_TELEMETRY_EOF'
%(script)s
FLEET_TELEMETRY_EOF
if ! cmp -s .ft.new fleet-telemetry.sh; then
    # Stopped by the new one: it waits for every old copy to be gone before the next is started.
    sh .ft.new stop >/dev/null 2>&1
    mv .ft.new fleet-telemetry.sh; echo "@@new"
else rm -f .ft.new; fi
if ! sh fleet-telemetry.sh status | grep -q '^running'; then
    if command -v setsid >/dev/null; then setsid sh fleet-telemetry.sh run %(every)d >/dev/null 2>&1 < /dev/null &
    else nohup sh fleet-telemetry.sh run %(every)d >/dev/null 2>&1 < /dev/null & fi
    echo "@@started"
fi
HAVE=" %(have)s "
cd telemetry || exit 1
for f in *.log; do
    [ -f "$f" ] || continue
    off=0
    case "$HAVE" in *" $f:"*) off=${HAVE#* $f:}; off=${off%%%% *} ;; esac
    size=$(wc -c < "$f")
    if [ "$size" -gt "$off" ]; then echo "@@file $f"; tail -c +$((off + 1)) "$f"; echo; fi
done
echo "@@end"
'''


def load(p, default=None):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def machines(q):
    """name -> target, each machine once: the queue's, the bench's; not this Mac."""
    cfg = load(os.path.join(q, "config.json"), {})
    out = {}
    for h in cfg.get("hosts", []) + cfg.get("bench", []):
        if h.get("target", "-") != "-":
            out.setdefault(h.get("lane_of", h["name"]), h["target"])
    return out


def parse(line):
    d = {}
    for kv in line.split():
        k, _, v = kv.partition("=")
        try:
            d[k] = float(v)
        except ValueError:
            pass
    return d


def pull_one(q, name, target, said):
    d = os.path.join(q, "telemetry", name)
    os.makedirs(d, exist_ok=True)
    # A line cut short by a pull that died is cut back to its last whole line first.
    have = []
    for f in sorted(os.listdir(d))[-3:]:
        if f.endswith(".log"):
            p = os.path.join(d, f)
            data = open(p, "rb").read()
            if data and not data.endswith(b"\n"):
                data = data[:data.rfind(b"\n") + 1]
                open(p, "wb").write(data)
            have.append("%s:%d" % (f, len(data)))
    script = REMOTE % {"script": open(COLLECTOR).read().rstrip("\n"), "every": EVERY, "have": " ".join(have)}
    try:
        r = subprocess.run(SSH + [target, "bash -s"], input=script.encode(), capture_output=True, timeout=120)
    except (subprocess.TimeoutExpired, OSError) as e:
        said[name] = {"error": type(e).__name__}
        return
    out = r.stdout.decode("utf-8", "replace").splitlines()
    if r.returncode != 0 or "@@end" not in out and "@@none" not in out:
        said[name] = {"error": (r.stderr.decode("utf-8", "replace").strip().splitlines() or ["rc %d" % r.returncode])[-1][:160]}
        return
    if "@@none" in out:
        said[name] = {"none": "not Linux: no collector"}
        return
    got, f, last = 0, None, None
    for line in out:
        if line.startswith("@@file "):
            if f:
                f.close()
            f = open(os.path.join(d, line.split()[1]), "a")
        elif line.startswith("@@"):
            continue
        elif f and line.startswith("t="):
            f.write(line + "\n")
            got += 1
            last = line
    if f:
        f.close()
    if last is None:
        files = sorted(x for x in os.listdir(d) if x.endswith(".log"))
        if files:
            lines = open(os.path.join(d, files[-1])).read().splitlines()
            last = lines[-1] if lines else None
    said[name] = {"lines": got, "new": "@@new" in out, "started": "@@started" in out, "last": parse(last) if last else None}


def pull(q, only):
    ms = {n: t for n, t in machines(q).items() if not only or n in only}
    said, ts = {}, []
    for n, t in ms.items():
        ts.append(threading.Thread(target=pull_one, args=(q, n, t, said)))
        ts[-1].start()
    for t in ts:
        t.join()
    doc = os.path.join(q, "plan", "telemetry.json")
    prev = load(doc, {}) or {}
    for n, s in said.items():
        if s.get("error") and prev.get(n, {}).get("last"):
            s["last"] = prev[n]["last"]
    prev.update(said)
    prev["_t"] = time.time()
    os.makedirs(os.path.dirname(doc), exist_ok=True)
    with open(doc + ".tmp", "w") as f:
        json.dump(prev, f)
    os.replace(doc + ".tmp", doc)
    for n in sorted(said):
        s = said[n]
        print("%-14s %s" % (n, s.get("error") or s.get("none") or "%d lines%s%s" % (
            s["lines"], ", the collector put there" if s["new"] else "", ", started" if s["started"] else "")))


def series(q, name, hours):
    """A machine's samples of the last `hours`, oldest first."""
    d = os.path.join(q, "telemetry", name)
    since = time.time() - hours * 3600
    out = []
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if f.endswith(".log") and os.path.getmtime(os.path.join(d, f)) >= since:
            for line in open(os.path.join(d, f)):
                s = parse(line)
                if s.get("t", 0) >= since:
                    out.append(s)
    return out


def show(q):
    doc = load(os.path.join(q, "plan", "telemetry.json"), {}) or {}
    for n in sorted(k for k in doc if not k.startswith("_")):
        s = doc[n]
        last = s.get("last")
        if not last:
            print("%-14s %s" % (n, s.get("error") or s.get("none") or "nothing yet"))
            continue
        print("%-14s read %d s ago%s" % (n, time.time() - last["t"], "  (last pull: %s)" % s["error"] if s.get("error") else ""))
        keys = [k for k in last if k != "t"]
        for i in range(0, len(keys), 4):
            print("    " + "  ".join("%-26s" % ("%s %g" % (k, last[k])) for k in keys[i:i + 4]))


def main(argv):
    if len(argv) < 3 or argv[2] not in ("pull", "show", "chart", "fit", "model"):
        print(__doc__)
        return 2
    q = os.path.abspath(argv[1])
    if argv[2] == "pull":
        pull(q, set(argv[3:]))
        # The energy balance Orrery's Heat page draws (thermal.py), and the page of it (heat_page.py,
        # which runs the model first), from what is now here.
        try:
            import heat_page
            heat_page.page(q, [])
        except Exception as e:  # a pull's lines are kept whatever the model makes of them
            print("the model failed: %r" % e)
    elif argv[2] == "model":
        import thermal
        return thermal.main(q, argv[3:])
    elif argv[2] == "show":
        show(q)
    elif argv[2] == "chart":
        import heat_page
        return heat_page.page(q, argv[3:])
    else:
        import telemetry_chart
        return telemetry_chart.fit(q, argv[3:])
    return 0


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    sys.exit(main(sys.argv))
