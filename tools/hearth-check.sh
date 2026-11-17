#!/bin/sh
# The hearth controller (tools/hearth.py; Paul, 16 November: "sets a dynamic heat target, which scales
# back like a PID controller ... until it shuts down systems ... a WOL type effect to turn systems back
# on"), against a queue directory made here and three stand-ins: a recorder in place of fleet-queue.py
# (it pauses and resumes lanes in the scratch config.json as the queue does, and writes down what it
# was told), a recorder in place of ssh (a power-off is a file), and a socket on this machine in place
# of the network (a wake packet is read back, byte for byte), and a file in place of the weather
# service's observation. The clock is HEARTH_NOW. No keeper is
# started, no machine is spoken to, and the live queue's config.json is looked at before and after.
# Each line is a claim; the first false one ends it.
#
#     sh tools/hearth-check.sh [LIVE_QUEUE]
set -eu
T=$(cd "$(dirname "$0")" && pwd)
LIVE=${1:-$HOME/code/treadcore/build/queue/grove}
Q=$(mktemp -d)/grove
mkdir -p "$Q"
cat > "$Q/../queue-stand-in.py" <<'E'
import json, os, sys
q, verb, name, how = sys.argv[1:5]
open(os.path.join(q, "calls.log"), "a").write("%s %s %s %s\n" % (os.environ.get("HEARTH_NOW", "?"), verb, name, how))
if os.path.exists(os.path.join(q, "fail-next")):
    os.remove(os.path.join(q, "fail-next"))
    sys.exit("the stand-in was told to fail")
assert verb == "machine" and how in ("pause", "resume"), sys.argv
p = os.path.join(q, "config.json")
cfg = json.load(open(p))
for h in cfg["hosts"]:
    if name in (h["name"], h.get("lane_of")):
        if how == "pause":
            h["paused"] = True
        else:
            h.pop("paused", None)
json.dump(cfg, open(p, "w"))
E
cat > "$Q/../ssh-stand-in.sh" <<E
#!/bin/sh
echo "\${HEARTH_NOW:-?} \$1 \$2" >> "$Q/ssh.log"
: > "$Q/off-\${1#user@scratch-}"
E
HEARTH_QUEUE="python3 $Q/../queue-stand-in.py" HEARTH_SSH="sh $Q/../ssh-stand-in.sh" HEARTH_OUTSIDE_URL="file://$Q/../ksea.json" \
exec python3 - "$T" "$Q" "$LIVE" <<'E'
import json, math, os, shutil, socket, subprocess, sys, time
from datetime import datetime, timezone
T, Q, LIVE = sys.argv[1:4]
sys.path.insert(0, T)
import hearth

live = os.path.join(LIVE, "config.json")
live_before = os.stat(live).st_mtime_ns if os.path.exists(live) else None
live_hearth = os.path.join(LIVE, "hearth")
live_hearth_before = sorted((f, os.stat(os.path.join(live_hearth, f)).st_mtime_ns) for f in os.listdir(live_hearth)) if os.path.isdir(live_hearth) else None


def claim(ok, text, detail=""):
    if not ok:
        print("FAILED: %s %s" % (text, detail))
        sys.exit(1)
    print("ok  " + text)


BOXES = json.load(open(os.path.join(T, "plans", "power.json")))["boxes"]
NOW = [1.8e9]
MAC = {"calber": "02:00:00:00:00:0a", "whitewolf": "02:00:00:00:00:0b", "boburner": "02:00:00:00:00:0c"}
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", 0))
sock.setblocking(False)
PORT = sock.getsockname()[1]
packets = []
OUT = [None]  # the outside, as the stand-in observation says it; None: no observation to fetch
KSEA = os.path.join(os.path.dirname(Q), "ksea.json")


def cli(*a):
    r = subprocess.run([sys.executable, os.path.join(T, "hearth.py"), Q] + [str(x) for x in a], capture_output=True, text=True,
                       env=dict(os.environ, HEARTH_NOW=str(NOW[0])))
    return r.returncode, r.stdout + r.stderr


def config():
    return json.load(open(os.path.join(Q, "config.json")))


def fresh():
    """A scratch fleet under the real machines' names (so tools/plans/power.json prices them) and
    made-up addresses: three with a card, saskatchewan carrying the probe, columbia to be kept,
    jaguaribe paused by a person, bosporus on the bench and off, this Mac."""
    for f in os.listdir(Q):
        p = os.path.join(Q, f)
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    hosts = []
    for n in ("calber", "whitewolf", "boburner"):
        hosts.append({"name": n, "target": "user@scratch-" + n, "caps": ["cpu", "gpu"], "poweroff": "echo off-" + n})
        hosts.append({"name": n + "-cuda", "target": "user@scratch-" + n, "caps": ["cuda"], "lane_of": n})
    for n in ("saskatchewan", "columbia", "jaguaribe"):
        hosts.append({"name": n, "target": "user@scratch-" + n, "caps": ["cpu"], "poweroff": "echo off-" + n})
    hosts[-1]["paused"] = True
    hosts.append({"name": "mac", "target": "-", "caps": ["own"]})
    json.dump({"hosts": hosts, "bench": [{"name": "bosporus", "target": "user@scratch-bosporus", "caps": ["cpu"], "paused": True}]},
              open(os.path.join(Q, "config.json"), "w"))
    os.makedirs(os.path.join(Q, "plan"))
    os.makedirs(os.path.join(Q, "telemetry", "saskatchewan"))
    del packets[:]
    OUT[0] = None
    if os.path.exists(KSEA):
        os.remove(KSEA)
    cli("machine", "columbia", "keep", "on")
    for n, mac in MAC.items():
        cli("machine", n, "mac", mac)
        cli("machine", n, "broadcast", "127.0.0.1")
        cli("machine", n, "port", PORT)
    cli("machine", "saskatchewan", "mac", "02:00:00:00:00:0d")


def watts():
    """What the scratch fleet draws, from its config: a lane not paused works, a machine with an
    off file draws nothing."""
    out = []
    cfg = config()
    for n in ("calber", "whitewolf", "boburner", "saskatchewan", "columbia", "jaguaribe"):
        if os.path.exists(os.path.join(Q, "off-" + n)):
            continue
        b = BOXES[n]
        ls = {h["name"]: not h.get("paused") for h in cfg["hosts"] if n in (h["name"], h.get("lane_of"))}
        cpu = b["cpu_full_w"] * 0.9 if ls.get(n) else b["cpu_idle_w"]
        gpu = (b["gpu_limit_w"] * 0.6 if ls.get(n + "-cuda") else b["gpu_idle_w"]) if "gpu" in b else 0.0
        out.append({"name": n, "age_s": 5, "cpu_w": cpu, "gpu_w": gpu, "wall_w": round((b["rest_w"] + cpu + gpu) / b["eff"])})
    return out


def observe(c, age=600):
    json.dump({"properties": {"temperature": {"value": c}, "timestamp": datetime.fromtimestamp(NOW[0] - age, timezone.utc).isoformat()}}, open(KSEA, "w"))


def say(*rooms):
    """Lines of telemetry five seconds apart, the last one now."""
    with open(os.path.join(Q, "telemetry", "saskatchewan", "20270101.log"), "a") as f:
        for i, c in enumerate(rooms):
            f.write("t=%d busy=0.9 room.radC2EA.c=%s\n" % (NOW[0] - 5 * (len(rooms) - 1 - i), c))


def world(room, probe_age=5, extra=""):
    if OUT[0] is not None:
        observe(OUT[0])
    ms = watts()
    json.dump({"t": NOW[0], "machines": ms}, open(os.path.join(Q, "plan", "thermal.json"), "w"))
    if room is not None:
        with open(os.path.join(Q, "telemetry", "saskatchewan", "20270101.log"), "a") as f:
            f.write("t=%d busy=0.9 room.radC2EA.c=%.1f%s\n" % (NOW[0] - probe_age, room, extra))
    return sum(m["wall_w"] for m in ms)


def hear():
    """A wake packet read off the socket switches its machine on."""
    while True:
        try:
            data = sock.recv(200)
        except BlockingIOError:
            return
        packets.append(data)
        for n, mac in MAC.items():
            if bytes.fromhex(mac.replace(":", "")) * 16 == data[6:] and os.path.exists(os.path.join(Q, "off-" + n)):
                os.remove(os.path.join(Q, "off-" + n))


def tick(room, minutes=5, **kw):
    NOW[0] += minutes * 60
    os.environ["HEARTH_NOW"] = str(NOW[0])
    hear()
    world(room, **kw)
    plan = hearth.step(Q)
    time.sleep(0.01)
    hear()
    return plan


def calls():
    p = os.path.join(Q, "calls.log")
    return [l.split() for l in open(p)] if os.path.exists(p) else []


def acted():
    p = os.path.join(Q, "hearth", "log.jsonl")
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


# ---- the packet
pkt = hearth.magic_packet("AA:bb:0c-0D.0e:0F")
claim(len(pkt) == 102 and pkt[:6] == b"\xff" * 6 and pkt[6:] == bytes([0xaa, 0xbb, 0x0c, 0x0d, 0x0e, 0x0f]) * 16,
      "a wake packet is 102 bytes: six of FF, then the address sixteen times")
try:
    hearth.magic_packet("aa:bb:cc")
    claim(False, "an address that is not six bytes is refused")
except ValueError:
    claim(True, "an address that is not six bytes is refused")
fresh()
rc, out = cli("wake", "calber")
time.sleep(0.05)
hear()
claim(rc == 0 and len(packets) == 3 and all(p == hearth.magic_packet(MAC["calber"]) for p in packets),
      "`wake calber` sends that packet three times, read back off a socket on this machine", out)
rc, out = cli("wake", "columbia")
claim(rc != 0 and "no address" in out, "`wake` for a machine with no address recorded sends nothing and says so")

# ---- probes
fresh()
world(26.0, extra=" room.rad7F7E.c=85.0 out.porch.c=9.5")
rc, out = cli("probes")
reg = json.load(open(os.path.join(Q, "hearth", "probes.json")))
claim(set(reg) == {"room.radC2EA.c", "room.rad7F7E.c"} and all(p["role"] == "room" and p["machine"] == "saskatchewan" for p in reg.values()),
      "a room.NAME.c key in a machine's telemetry is found by itself and taken for a room probe")
claim("NOT A TEMPERATURE" in out.split("room.rad7F7E.c")[1].split("\n")[0], "a counter answering 85.0 is not a temperature")
cli("probe", "out.porch.c", "role", "outside")
cli("probe", "out.porch.c", "place", "the porch")
rc, out = cli("probes")
claim("the porch" in out and "9.5 C (49.1 F)" in out, "a key is made a probe by naming its role, and is given a place")
cli("target", "21")
plan = tick(26.0, extra=" room.rad7F7E.c=85.0 out.porch.c=9.5")
claim(plan["temp_c"] == 26.0 and plan["temp_from"] == ["room.radC2EA.c"], "the controlled temperature is the mean of the fresh room probes only: not the 85.0, not the outside probe")
rc, out = cli("target", "70")
claim(rc != 0, "a target of 70 is refused as a slip for Fahrenheit")

# ---- one sample is not the temperature
fresh()
cli("target", "21")
cli("mode", "advise")
plan = tick(26.0)
NOW[0] += 300
os.environ["HEARTH_NOW"] = str(NOW[0])
world(None)
say(26.0, 26.1, 26.0, "-0.0")
plan = hearth.step(Q)
claim(plan["temp_c"] == 26.0 and plan["temp_from"] == ["room.radC2EA.c"], "a -0.0 as the newest sample changes nothing: the probe is the median of its last five minutes, less what is no reading")
NOW[0] += 300
os.environ["HEARTH_NOW"] = str(NOW[0])
world(None)
say(26.0, 26.0, 61.5, 26.1, 26.0)
plan = hearth.step(Q)
claim(plan["temp_c"] == 26.0, "a single wild sample (61.5 among four of 26) changes nothing")
NOW[0] += 300
os.environ["HEARTH_NOW"] = str(NOW[0])
world(None)
say(31.0, 31.0, 31.1, 31.0, 31.0)
plan = hearth.step(Q)
why = [p["why"] for p in plan["probes"] if p["key"] == "room.radC2EA.c"][0]
claim(plan["temp_c"] is None and why.startswith("suspect: it jumped +5.0") and "suspect" in plan["stopped"] and plan.get("would") is None,
      "a probe whose median jumped five degrees in five minutes is suspect for that pass: named with the reason, and with no other room probe nothing is planned")
plan = tick(31.0)
claim(plan["temp_c"] == 31.0 and not plan.get("stopped"), "and is taken again at the next pass if it stays where it went")

# ---- the outside, and the feedforward
fresh()
cli("target", "21")
cli("mode", "advise")
rc, out = cli("outside")
claim(rc != 0 and "failed" in out, "a fetch of the outside that fails is said, by `outside`")
plan = tick(21.0, minutes=25)
claim(plan["wanted_w"] and plan["outside_c"] is None and plan["feedforward_w"] == 0 and any("outside: the fetch" in s for s in plan["said"]),
      "and is not fatal to a pass: the plan is made, with no outside and no feedforward")
OUT[0] = 10.0
NOW[0] += 1500
observe(10.0)
rc, out = cli("outside")
reg = json.load(open(os.path.join(Q, "hearth", "probes.json")))
claim(rc == 0 and reg["outside.ksea.c"]["role"] == "outside" and reg["outside.ksea.c"]["place"] == "SeaTac airport (KSEA)"
      and open(os.path.join(Q, "hearth", "outside.tsv")).read().count("\n") == 1,
      "`outside` fetches the station's observation, logs it to outside.tsv and makes it a probe of role outside", out)
plan = tick(21.0)
claim(plan["outside_c"] == 10.0 and plan["ua_w_per_c"] is None and plan["feedforward_w"] == 0 and "UA is unknown" in plan["feedforward_why"],
      "with UA unknown there is no feedforward, and the plan says that is why")
cli("set", "ua", "80")
plan = tick(21.0)
base = plan["unclamped_w"]
claim(plan["feedforward_w"] == 880 and plan["correction_w"] == base - 880 and base == plan["expected_w"],
      "with UA 80 W/C and the outside at 10 the feedforward is 880 W, and the controller still begins where the fleet is")
OUT[0] = 5.0
plan = tick(21.0, minutes=25)
claim(plan["temp_c"] == 21.0 and plan["outside_c"] == 5.0 and plan["unclamped_w"] - base == 400 and plan["feedforward_w"] == 1280,
      "the outside five degrees colder: the watts the law asks rise by UA x 5 = 400 W before the room has moved at all")
OUT[0] = None  # the observation is no longer renewed: it ages
plan = tick(21.0, minutes=150)
claim(plan["outside_c"] is None and plan["feedforward_w"] == 0 and "stale" in plan["feedforward_why"] and plan["unclamped_w"] - base == 400,
      "the observation three hours old: the feedforward is nothing, the plan says the outside is stale, and the watts wanted do not move for it")
rec = open(os.path.join(Q, "hearth", "record.tsv")).read().splitlines()
claim(len(rec) == 5 and rec[-1].split("\t")[2] == "" and rec[-2].split("\t")[2] == "5.0", "each pass is a line of record.tsv: time, room, outside, watts")
rc, out = cli("fit-ua")
claim(rc != 0 and "not enough" in out, "fit-ua on five passes says there is not enough, and adopts nothing")

# ---- off, advise
fresh()
cli("target", "21")
rc, out = cli("mode", "advise")
claim(json.load(open(os.path.join(Q, "hearth", "state.json")))["mode"] == "advise", "the mode is advise unless set")
cli("mode", "off")
before = open(os.path.join(Q, "config.json")).read()
for _ in range(3):
    tick(26.0)
claim(not os.path.exists(os.path.join(Q, "hearth", "plan.json")) and not calls() and open(os.path.join(Q, "config.json")).read() == before,
      "off: three passes over a room five degrees warm write no plan and run nothing")
cli("mode", "advise")
for _ in range(6):
    plan = tick(26.0)
claim(plan["would"] and plan["would"]["rung"] == "boburner:cpu" and plan["did"] is None, "advise: a warm room is planned (the first rung is the cheapest machine's CPU lanes)")
claim(not calls() and not acted() and open(os.path.join(Q, "config.json")).read() == before and not os.path.exists(os.path.join(Q, "ssh.log")),
      "advise: six passes run nothing: no queue command, no ssh, the config as it was")
claim(json.load(open(os.path.join(Q, "hearth", "plan.json")))["wanted_w"] == plan["wanted_w"], "the plan is written to hearth/plan.json")

# ---- act: a warm room is shed
fresh()
cli("target", "21")
cli("set", "gap", "300")
cli("mode", "act")
full = world(26.0)
per_pass = []
for _ in range(24):
    n = len(calls())
    plan = tick(26.0)
    per_pass.append(len(acted()))
log = acted()
order = [a["rung"] for a in log]
claim(order == ["boburner:cpu", "whitewolf:cpu", "calber:cpu", "saskatchewan:cpu", "boburner:card", "whitewolf:card", "calber:card"],
      "act, power off: a warm room sheds every CPU lane first, cheapest first, then every card's lane, and stops there", str(order))
claim(all(b - a <= 1 for a, b in zip([0] + per_pass, per_pass)), "never more than one rung in a pass")
claim([c[2:] for c in calls()][:2] == [["boburner", "pause"], ["boburner-cuda", "resume"]],
      "a machine's CPU lanes alone are two of the queue's commands: pause NAME, resume NAME-cuda")
last = {}
ok = True
for a in log:
    m = a["rung"].split(":")[0]
    ok = ok and a["t"] - last.get(m, 0) >= 1800
    last[m] = a["t"]
claim(ok, "no machine is changed twice within its dwell of 30 minutes (the gap was set to 5)")
claim(not os.path.exists(os.path.join(Q, "ssh.log")) and any(r["id"] == "calber:off" and r["state"].startswith("not allowed") for r in plan["ladder"]),
      "with power off no machine is powered off: the rung says it is not allowed")
cfg = config()
paused = {h["name"] for h in cfg["hosts"] if h.get("paused")}
claim(paused == {"boburner", "boburner-cuda", "whitewolf", "whitewolf-cuda", "calber", "calber-cuda", "saskatchewan", "jaguaribe"},
      "what is paused is what was shed, and jaguaribe, which a person paused")

# ---- act: power off
cli("set", "power", "on")
os.makedirs(os.path.join(Q, "running", "whitewolf-cuda"))
open(os.path.join(Q, "running", "whitewolf-cuda", "1-x.json"), "w").write("{}")
for _ in range(8):
    plan = tick(26.0)
claim([a["rung"] for a in acted()[7:]] == ["calber:off", "boburner:off"] and any(r["id"] == "whitewolf:off" and "in hand" in r["state"] for r in plan["ladder"]),
      "with power on the machines whose lanes are all held are powered off, and one with a job in hand is not", str([a["rung"] for a in acted()[7:]]))
os.remove(os.path.join(Q, "running", "whitewolf-cuda", "1-x.json"))
for _ in range(8):
    plan = tick(26.0)
claim([a["rung"] for a in acted()[7:]] == ["calber:off", "boburner:off", "whitewolf:off"], "once its job in hand has ended it is powered off too")
ssh = open(os.path.join(Q, "ssh.log")).read()
claim(ssh.count("\n") == 3 and "echo off-calber" in ssh, "a power-off is the machine's own rule from config.json, sent once each")
st = {r["id"]: r["state"] for r in plan["ladder"]}
claim(st["saskatchewan:off"].startswith("keep: it carries a room probe") and "saskatchewan" not in ssh, "the machine that carries the room probe is never powered off")
claim(st["columbia:cpu"] == "keep" and st["columbia:off"] == "keep" and not any("columbia" in " ".join(c) for c in calls()) and "columbia" not in ssh,
      "a machine marked keep is never shed: not paused, not powered off")
claim(st["jaguaribe:cpu"].startswith("by hand") and not any("jaguaribe" in " ".join(c) for c in calls()) and "jaguaribe" not in ssh,
      "a machine a person paused is never touched")
claim(not any(r["machine"] in ("bosporus", "mac") and r["state"] == "open" for r in plan["ladder"]) and "bosporus" not in ssh,
      "a machine on the bench, and this Mac, are never touched")
low = world(26.0)
claim(plan["now_w"] == low and low < full / 3, "the scratch fleet fell from %d W to %d W" % (full, low))

# ---- act: a cold room adds back
n0 = len(acted())
for _ in range(120):
    plan = tick(16.0)
back = [a["rung"] for a in acted()[n0:]]
claim(back[0] == "saskatchewan:cpu", "a cold room first resumes the lanes held on a machine that is up", str(back))
ok = True
up = set()
for r in back:
    m, k = r.split(":")
    if k == "off":
        ok = ok and not up  # nothing left to resume on a machine that is up
        up.add(m)
    else:
        ok = ok and (m in up or m == "saskatchewan")
        if k == "cpu":
            up.discard(m)
claim(ok and back == ["saskatchewan:cpu", "whitewolf:off", "whitewolf:card", "whitewolf:cpu", "boburner:off", "boburner:card", "boburner:cpu", "calber:off", "calber:card", "calber:cpu"],
      "a machine is woken only when nothing is left to resume, the last powered off first; then its card's lane, then its CPU lanes", str(back))
claim(len(packets) == 9 and {p for p in packets} == {hearth.magic_packet(m) for m in MAC.values()},
      "each wake was the right 102 bytes for its machine, read back off the socket")
paused = {h["name"] for h in config()["hosts"] if h.get("paused")}
st = json.load(open(os.path.join(Q, "hearth", "state.json")))
claim(paused == {"jaguaribe"} and not st["held"] and world(16.0) == full, "everything shed is given back, nothing is held, and jaguaribe is still paused by its person")

# ---- every rung used, and still cold
claim(plan["clamped"] and plan["shortfall"]["would_cover"][0]["machine"] == "bosporus" and plan["would"] is None,
      "every rung used and the room still cold: the plan says how many watts short, and names bosporus on the bench (%d W short; about %d W)" % (
          plan["shortfall"]["w"], plan["shortfall"]["would_cover"][0]["about_w"]))

# ---- anti-windup
fresh()
cli("target", "21")
cli("mode", "act")
for _ in range(100):
    plan = tick(16.0)
st = json.load(open(os.path.join(Q, "hearth", "state.json")))
claim(st["integral_w"] == 0 and plan["integral_held"] and plan["wanted_w"] == plan["max_w"] and plan["unclamped_w"] - plan["max_w"] == round(300 * 4.7),
      "anti-windup: eight hours five degrees cold with nothing to add, and the integral has not grown (0 W; unbounded it would be %d W)" % (25 * 4.7 * 100 / 12))
tick(18.5)
tick(21.0)
plan = tick(21.6)
claim(plan["did"] and plan["did"]["rung"] == "boburner:cpu", "so the first pass the room is over its deadband sheds at once, with no integral to unwind first")

# ---- a person's hand, a failure, a stale probe
fresh()
cli("target", "21")
cli("mode", "act")
tick(26.0)
tick(26.0, minutes=20)
claim([a["rung"] for a in acted()] == ["boburner:cpu", "whitewolf:cpu"], "two rungs shed")
subprocess.run(["python3", os.path.join(Q, "..", "queue-stand-in.py"), Q, "machine", "boburner", "resume"], check=True)
n = len(calls())
plan = tick(26.0, minutes=20)
st = json.load(open(os.path.join(Q, "hearth", "state.json")))
claim("boburner" not in st["held"] and any("resumed by a person" in s for s in plan["said"]) and plan["did"]["rung"] == "calber:cpu",
      "a lane a person resumed is no longer held here, and is not shed again inside its dwell")
open(os.path.join(Q, "fail-next"), "w").close()
n = len(calls())
plan = tick(26.0, minutes=20)
claim(plan["did"] and not plan["did"]["ok"] and len(calls()) == n + 1, "a queue command that fails is recorded as failed and not tried again in the pass")
n = len(calls())
plan = tick(26.0, probe_age=1500)
claim(plan.get("stopped", "").startswith("no fresh room probe") and plan.get("would") is None and len(calls()) == n,
      "a probe 25 minutes old is not a temperature: act plans nothing and does nothing")
NOW[0] += 3600
os.environ["HEARTH_NOW"] = str(NOW[0])
world(None)
plan = hearth.step(Q)
claim(plan.get("stopped") and len(calls()) == n, "nor with no reading at all for an hour")
os.remove(os.path.join(Q, "plan", "thermal.json"))
NOW[0] += 300
os.environ["HEARTH_NOW"] = str(NOW[0])
with open(os.path.join(Q, "telemetry", "saskatchewan", "20270101.log"), "a") as f:
    f.write("t=%d room.radC2EA.c=26.0\n" % NOW[0])
plan = hearth.step(Q)
claim("watts are not known" in plan.get("stopped", "") and len(calls()) == n, "nor with a fresh probe and the fleet's watts unknown")


# ---- a room
def room(tau_h, hours=72, start=24.0, t_out=14.0, r_c_w=0.008, ua=None, swing=0.0):
    """C dT/dt = P - (T - T_out) / R, stepped each five minutes, P the scratch fleet's watts.
    R 0.008 C/W: the fleet's %d W would hold it 9.8 degrees over the outside; 21 wants 875 W."""
    fresh()
    cli("target", "21")
    cli("set", "power", "on")
    if ua:
        cli("set", "ua", ua)
    cli("mode", "act")
    temp, trace = start, []
    for i in range(hours * 12):
        out = t_out + swing * math.sin(2 * math.pi * i / 288)
        OUT[0] = round(out, 1)
        plan = tick(round(temp, 1))
        p = world(None)
        temp += (300 / (tau_h * 3600)) * (out + r_c_w * p - temp)
        trace.append((temp, p))
    return trace, acted()


def judge(trace, log):
    tail = [x for x, _ in trace[-24 * 12:]]
    late = [a for a in log if a["t"] > NOW[0] - 24 * 3600]
    per_m = {}
    for a in log:
        per_m.setdefault(a["rung"].split(":")[0], []).append(a["t"])
    dwell_ok = all(b - a >= 1800 for ts in per_m.values() for a, b in zip(ts, ts[1:]))
    return max(abs(x - 21) for x in tail), max(tail) - min(tail), len(late), dwell_ok and all(a["ok"] for a in log), sum(p for _, p in trace[-288:]) / 288


for tau in (6, 24):
    trace, log = room(tau)
    worst, swing, late, good, mean = judge(trace, log)
    claim(worst <= 1.0 and swing <= 1.2 and late <= 12 and good,
          "a room of tau %d h (first order, R 0.008 C/W, outside 14, begun at 24 with the fleet at %d W, all of it): over the third day it stays within %.2f of 21, swings %.2f, on %d changes that day (%d in three days), mean %d W"
          % (tau, full, worst, swing, late, len(log), mean),
          "worst %.2f swing %.2f late %d all %d" % (worst, swing, late, len(log)))
    if tau == 6:
        rc, out = cli("fit-ua")
        ua = int(out.split("set ua ")[1]) if "set ua " in out else 0
        claim(rc == 0 and abs(ua - 125) <= 13 and "ua" not in json.load(open(os.path.join(Q, "hearth", "state.json")))["set"],
              "fit-ua on that record finds the room's 1/R = 125 W/C within a tenth (%d W/C, %s) and does not adopt it" % (ua, out.split("; ")[1].split("\n")[0]), out)

res = {}
for ua in (None, 125):
    trace, log = room(6, ua=ua, swing=4.0)
    res[ua] = judge(trace, log)
(w0, s0, l0, g0, _), (w1, s1, l1, g1, _) = res[None], res[125]
claim(g0 and g1 and w1 <= 1.0 and w1 <= w0,
      "the outside swinging 10 to 18 over a day, tau 6 h: with UA 125 the room's third day stays within %.2f of 21 (swing %.2f, %d changes); without the feedforward, within %.2f (swing %.2f, %d changes)"
      % (w1, s1, l1, w0, s0, l0), str(res))

# ---- the live queue
if live_before is not None:
    claim(os.stat(live).st_mtime_ns == live_before, "the live queue's config.json was not written (%s)" % live)
    after = sorted((f, os.stat(os.path.join(live_hearth, f)).st_mtime_ns) for f in os.listdir(live_hearth)) if os.path.isdir(live_hearth) else None
    claim(after == live_hearth_before, "nor anything in its hearth directory")
else:
    print("--  no live queue at %s to look at" % LIVE)
shutil.rmtree(os.path.dirname(Q))
print("PASSED")
E
