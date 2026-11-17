#!/usr/bin/env python3
"""fleet-probes.py QUEUE look|status|install|serve [MACHINE...] -- the fleet's Geiger counters, as room probes.

Paul, 16 November: "add the concept of thermal probes. allow orrery copal fleet machines to look and
install rad beeper if the usb tty device is a GMC 300, 500, 600, or anything matching the spec of"
GQ-RFC1201.

A PROBE is a thermometer that reads a room and not a part. The only ones the fleet has are inside
GQ Geiger counters: a GMC-320 from firmware 3.01 answers <GETTEMP>>, radbeeper asks it and logs the
answer, and the five-second collector (fleet-telemetry.sh) reports the newest as room.radXXXX.c. A
GMC-300, 500 or 600 is found and served for its counts and gives no temperature.

THE WORK IS DONE ON THE MACHINE by tools/fleet-probes.sh, as the user, no root. This copies it to
~/.fleet-queue/fleet-probes.sh over one connection a machine, of its own (as telemetry.py's pull
does: never the shared one the jobs ride), runs the verb and prints the fleet's table.

  look [MACHINE...]     every USB serial device and what its USB identity says; no port is opened
  status [MACHINE...]   a line a counter: counts a minute, temperature and its age, who serves it
  install MACHINE...    radbeeper built by cargo into ~/.cargo/bin where it is absent or does not
                        log temperature; where cargo is absent it says so and stops
  serve MACHINE...      start `radbeeper service` as the user for a counter nothing serves; it does
                        not survive a reboot (the boot service is root's: fleet-radbeeper-root.sh)

look and status change nothing on a machine but this script's own copy, and both write
QUEUE/hearth/counters.json: each machine, each port, its USB identity, and for a counter its model,
firmware, whether it has the thermometer, who serves it and the telemetry key of its temperature.
install and serve change a machine, so they want the machines named.
"""
import json
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import telemetry  # noqa: E402  (machines(), and the connection a pull makes)

SCRIPT = os.path.join(HERE, "fleet-probes.sh")
REMOTE = r'''
[ -r /proc/stat ] || { echo "@@none"; exit 0; }
mkdir -p ~/.fleet-queue && cd ~/.fleet-queue || exit 1
cat > .fp.new <<'FLEET_PROBES_EOF'
%(script)s
FLEET_PROBES_EOF
mv .fp.new fleet-probes.sh
%(verbs)s
echo "@@end"
'''
WAIT = {"look": 120, "status": 120, "install": 3600, "serve": 300}


def run_one(name, target, verbs, wait, said):
    script = REMOTE % {"script": open(SCRIPT).read().rstrip("\n"),
                       "verbs": "\n".join('echo "@@verb %s"; sh fleet-probes.sh %s' % (v, v) for v in verbs)}
    try:
        r = subprocess.run(telemetry.SSH + [target, "sh -s"], input=script.encode(), capture_output=True, timeout=wait)
    except (subprocess.TimeoutExpired, OSError) as e:
        said[name] = {"error": type(e).__name__}
        return
    out = r.stdout.decode("utf-8", "replace").splitlines()
    if "@@none" in out:
        said[name] = {"none": "not Linux: not looked at"}
        return
    if r.returncode != 0 or "@@end" not in out:
        said[name] = {"error": (r.stderr.decode("utf-8", "replace").strip().splitlines() or ["rc %d" % r.returncode])[-1][:160]}
        return
    rows, verb = [], None
    for line in out:
        if line.startswith("@@verb "):
            verb = line.split()[1]
        elif line.startswith("kind="):
            d = dict(kv.partition("=")[::2] for kv in line.split("\t"))
            d["verb"] = verb
            rows.append(d)
    said[name] = {"rows": rows}


def run(q, verbs, only, wait):
    ms = {n: t for n, t in telemetry.machines(q).items() if not only or n in only}
    for n in sorted(only - set(ms)):
        print("%-14s not a machine of this queue" % n)
    said, ts = {}, []
    for n, t in ms.items():
        ts.append(threading.Thread(target=run_one, args=(n, t, verbs, wait, said)))
        ts[-1].start()
    for t in ts:
        t.join()
    return said


def record(q, said):
    """QUEUE/hearth/counters.json: what each machine has, kept for one that did not answer this time."""
    doc = os.path.join(q, "hearth", "counters.json")
    prev = telemetry.load(doc, {}) or {}
    machines = prev.get("machines", {})
    for name, s in said.items():
        if "rows" not in s:
            m = machines.setdefault(name, {})
            m["said"] = s.get("error") or s.get("none")
            m["asked"] = time.time()
            continue
        head = next((r for r in s["rows"] if r["kind"] == "machine"), {})
        seen = {r.get("port"): r for r in s["rows"] if r["kind"] == "counter"}
        by_serial = {r.get("serial"): r for r in s["rows"] if r["kind"] == "counter" and r.get("serial")}
        ports = []
        for r in (r for r in s["rows"] if r["kind"] == "port"):
            c = by_serial.get(r.get("serial")) or seen.get(r["port"]) or {}
            therm = r.get("thermometer") or c.get("thermometer")
            ports.append({
                "machine": name, "port": r["port"], "usb": r.get("usb"), "product": r.get("product"),
                "driver": r.get("driver"), "counter": r.get("counter"), "held": r.get("held"),
                "serial": r.get("serial") or None, "model": r.get("model") or c.get("model") or None,
                "firmware": r.get("firmware") or c.get("firmware") or None,
                "thermometer": {"yes": True, "no": False}.get(therm),
                "served_by": c.get("served_by") or (r.get("by") if r.get("held") != "no" else None),
                "logs": c.get("logs") or r.get("logs") or None,
                "key": c.get("key") or None,
                "cpm_300": num(c.get("cpm_300")), "temp_c": num(c.get("temp_c")), "temp_age": num(c.get("temp_age")),
            })
        machines[name] = {
            "asked": time.time(), "said": None, "os": head.get("os"),
            "radbeeper": None if head.get("radbeeper") in (None, "none") else head["radbeeper"],
            "version": head.get("version") or None, "logs_temperature": head.get("logs_temperature") == "yes",
            "cargo": head.get("cargo") != "none", "boot_service": head.get("boot_service"),
            "in_dialout": head.get("in_dialout") == "yes", "ports": ports,
        }
    out = {"_t": time.time(), "machines": machines,
           "counters": [p for n in sorted(machines) for p in machines[n].get("ports", []) if p.get("serial")]}
    os.makedirs(os.path.dirname(doc), exist_ok=True)
    with open(doc + ".tmp", "w") as f:
        json.dump(out, f, indent=1)
    os.replace(doc + ".tmp", doc)
    return doc


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def table(rows, heads):
    rows = [[str(c) if c not in (None, "") else "-" for c in r] for r in rows]
    w = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(heads)]
    for r in [heads] + rows:
        print("  ".join(c.ljust(w[i]) for i, c in enumerate(r)).rstrip())


def why(s):
    """A machine that gave no rows, in few words: the whole error is in counters.json."""
    e = s.get("error") or s.get("none") or ""
    return "does not answer (%s)" % ("no such name" if "not resolve" in e else e[:40]) if s.get("error") else e


def show_look(said):
    rows = []
    for n in sorted(said):
        s = said[n]
        if "rows" not in s:
            rows.append([n, why(s)] + [""] * 7)
            continue
        head = next((r for r in s["rows"] if r["kind"] == "machine"), {})
        rb = "no" if head.get("radbeeper") == "none" else "%s%s" % (head.get("version", "?"), "" if head.get("logs_temperature") == "yes" else " (no temperature)")
        build = "cargo" if head.get("cargo") != "none" else "no cargo"
        ports = [r for r in s["rows"] if r["kind"] == "port" and r["verb"] == "look"]
        if not ports:
            rows.append([n, "none", "", "", "", "", "", rb, build])
        for r in ports:
            what = "%s Re %s" % (r["model"], r["firmware"]) if r.get("model") else ("could be one" if r["counter"] == "possible" else "no: never opened")
            rows.append([n, r["port"], r.get("usb"), r.get("product"), what,
                         {"yes": "yes", "no": "no"}.get(r.get("thermometer"), ""),
                         r.get("by") if r["held"] != "no" else "nothing", rb, build])
    table(rows, ["machine", "port", "usb", "product", "counter", "thermometer", "held by", "radbeeper", "build"])


def show_status(said):
    rows = []
    for n in sorted(said):
        s = said[n]
        if "rows" not in s:
            rows.append([n, why(s)] + [""] * 7)
            continue
        cs = [r for r in s["rows"] if r["kind"] == "counter"]
        if not cs:
            rows.append([n, "no counter"] + [""] * 7)
        for r in cs:
            temp = "%s C, %s s old" % (r["temp_c"], r.get("temp_age", "?")) if r.get("temp_c") else ("none: no thermometer" if r.get("thermometer") == "no" else "")
            rows.append([n, r.get("serial") or "not asked", ("%s Re %s" % (r["model"], r["firmware"])) if r.get("model") else "",
                         r.get("port"), r.get("cpm"), r.get("cpm_300"), temp, r.get("key"), r.get("served_by")])
    table(rows, ["machine", "serial", "model", "port", "cpm", "cpm 5 min", "temperature", "telemetry key", "served by"])


def show_verb(said, verb):
    for n in sorted(said):
        s = said[n]
        if "rows" not in s:
            print("%-14s %s" % (n, s.get("error") or s.get("none")))
            continue
        for r in (r for r in s["rows"] if r["kind"] == verb):
            first = " ".join("%s=%s" % (k, r[k]) for k in ("port", "ports", "did", "radbeeper", "version", "logs_temperature", "missing", "needs_group", "pid") if r.get(k))
            print("%-14s %s" % (n, first))
            if r.get("note"):
                print("%-14s   %s" % ("", r["note"]))


def main(argv):
    if len(argv) < 3 or argv[2] not in WAIT:
        print(__doc__)
        return 2
    q, verb, only = os.path.abspath(argv[1]), argv[2], set(argv[3:])
    if verb in ("install", "serve"):
        if not only:
            print("%s changes a machine: name the machines" % verb)
            return 2
        show_verb(run(q, [verb], only, WAIT[verb]), verb)
        print()
    said = run(q, ["look", "status"], only, WAIT["look"])
    (show_status if verb == "status" else show_look)(said)
    print("\nwritten: %s" % record(q, said))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
