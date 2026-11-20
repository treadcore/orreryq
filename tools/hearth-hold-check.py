#!/usr/bin/env python3
"""hearth-hold-check: the hold, the controller's second law (tools/hearth_regulator.py), proved on a made-up
fleet. No machine is asked anything: the queue's command and the power orders are stand-ins that write down
what they were told, the room's probes and the fleet's watts are numbers handed in, and the law's memory is
a scratch directory.

    python3 tools/hearth-hold-check.py          ends PASSED, or says which claim failed

The made-up fleet has the real machines' names, so the real power model and the real order of preference
apply: saskatchewan carries the probes; calber, whitewolf and boburner have cards; bosporus and jaguaribe
are the two that spend most energy on a job; calber and bosporus are known to wake by the packet.
"""
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hearth as H  # noqa: E402
import hearth_regulator as R  # noqa: E402

FAILED = []
TOLD = []


def claim(ok, words, more=""):
    print("%s  %s%s" % ("ok" if ok else "FAILED:", words, "" if ok else "   " + str(more)))
    if not ok:
        FAILED.append(words)


H.run_queue = lambda q, *a: (TOLD.append(("queue",) + a), (True, "done"))[1]
H.power_order = lambda q, name, what: (TOLD.append(("power", name, what)), 0)[1]

WOL = {"calber": True, "bosporus": True}
CARDS = ("calber", "whitewolf", "boburner")
WATTS = {"saskatchewan": 125, "calber": 260, "whitewolf": 200, "boburner": 205, "bosporus": 230, "jaguaribe": 240, "columbia": 15}


def fleet(paused=(), off=(), bench=()):
    ms = {}
    for name, w in WATTS.items():
        lanes = [{"name": name, "caps": ["cpu"], "paused": name in paused}]
        cards = [{"name": name + "-cuda", "caps": ["cuda"], "lane_of": name, "paused": name + "-cuda" in paused}] if name in CARDS else []
        gone = name in off or name in bench
        ms[name] = {"name": name, "cpu": [] if gone else lanes, "card": [] if gone else cards, "bench": gone, "target": "user@" + name,
                    "poweroff": "doas -n /sbin/poweroff", "special": "", "wall_w": None if name in off else w, "fresh": name not in off,
                    "cpu_w": None, "gpu_w": None, "box": {}, "mine": {}, "in_hand": []}
    return ms


def scratch(target=26.7, held=(), offed=(), spare=("bosporus", "jaguaribe"), since=10000.0, slope=0.0, room=26.7, wol=WOL, orders=None):
    q = tempfile.mkdtemp(prefix="hold-check-")
    os.makedirs(os.path.join(q, "hearth"))
    t = time.time()
    if orders:
        json.dump({n: dict(o, t=t - o["ago"], done=t - o["ago"] + 1200) for n, o in orders.items()}, open(H.hp(q, "power.json"), "w"))
    json.dump({n: {"mac": "02:00:00:00:00:%02x" % i, "wol": wol.get(n)} for i, n in enumerate(WATTS)}, open(H.hp(q, "machines.json"), "w"))
    json.dump({"wh_a_job": {"columbia": 3.3, "saskatchewan": 8.7, "boburner": 11.3, "calber": 18.7, "whitewolf": 22.3, "jaguaribe": 37.6, "bosporus": 46.4}},
              open(H.hp(q, "energy.json"), "w"))
    # An hour of looks behind this one, on the slope asked for, and each probe at its usual place.
    rows = [[t - 3600 + i * 300, room - slope * (3600 - i * 300) / 3600] for i in range(12)]
    devs = [[t - 3600 + i * 300, {"room.a.c": 0.3, "room.b.c": -0.3}] for i in range(12)]
    hist = [[t - 3600 + i * 300, {"room.a.c": rows[i][1] + 0.3, "room.b.c": rows[i][1] - 0.3}] for i in range(12)]
    json.dump({"held": list(held), "offed": list(offed), "spare": list(spare), "last_change_t": t - since, "rows": rows, "pdevs": devs, "phist": hist},
              open(H.hp(q, "hold.json"), "w"))
    st = {"mode": "act", "target_c": target, "set": {"power": "on", "ceiling": 27.2}, "held": {}}
    return q, st, t


def look(room_a, room_b, ms, act=True, out=8.0, was=None, **kw):
    """One look with the two probes reading room_a and room_b; `was` is where the room stood over the hour before, where that is not their mean."""
    del TOLD[:]
    q, st, t = scratch(room=(room_a + room_b) / 2 if was is None else was, **kw)
    if "power" in kw.get("settings", {}):
        st["set"].update(kw["settings"])
    ps = [{"key": "room.a.c", "role": "room", "ok": True, "c": room_a, "machine": "saskatchewan"},
          {"key": "room.b.c", "role": "room", "ok": True, "c": room_b, "machine": "saskatchewan"}]
    plan = {"outside_c": out, "now_w": float(sum(m["wall_w"] or 0 for m in ms.values()))}
    said = []
    R.look(H, q, st, t, {}, ms, ps, plan, said, act)
    told = list(TOLD)
    shutil.rmtree(q)
    return told, plan, said


def scratch_kw(**kw):
    return kw


# ---- the band
told, plan, said = look(27.0, 26.4, fleet())
claim(told == [] and plan["would"] is None, "on its target with no slope, nothing is done", told)

# ---- too warm: the machine that spends most on a job, and has no card, goes first, and goes whole
told, plan, said = look(27.3, 26.7, fleet())
claim(told == [("power", "bosporus", "off")], "too warm (27.0): bosporus, no card, 46 Wh a job, known to wake, is switched off whole", told)
told, plan, said = look(27.3, 26.7, fleet(), wol={})
claim(len(told) == 1 and told[0][:2] == ("queue", "machine") and told[0][3] == "pause" and told[0][2] in ("bosporus", "jaguaribe"),
      "with no machine known to wake, the step is a lane of a machine without a card taking nothing new, and no machine is powered off", told)
claim(not any(x[0] == "power" for x in told), "a machine not known to wake is never powered off", told)

# ---- the machine that carries the probes
for ms in (fleet(), fleet(off=("bosporus", "jaguaribe", "columbia", "calber", "whitewolf", "boburner"))):
    told, plan, said = look(27.9, 27.5, ms, wol={"saskatchewan": True})
    claim(not any("saskatchewan" in str(x) for x in told), "the machine that carries the probes is neither paused nor powered off, at 27.7 with %d machines on" % sum(1 for m in ms.values() if m["fresh"]), told)

# ---- too cold: a card's lane comes back first; then a card machine is woken before a Supermicro
told, plan, said = look(26.5, 25.9, fleet(paused=("bosporus", "whitewolf-cuda", "columbia")), held=("bosporus", "whitewolf-cuda", "columbia"))
claim(told == [("queue", "machine", "whitewolf-cuda", "resume")], "too cold (26.2) with three lanes held: the card's lane works again first", told)
told, plan, said = look(26.5, 25.9, fleet(off=("calber", "bosporus")), offed=("calber", "bosporus"))
claim(told == [("power", "calber", "on")], "too cold with calber and bosporus off: calber, which has a card, is woken first", told)
told, plan, said = look(26.5, 25.9, fleet(off=("jaguaribe",)))
claim(told == [] and any("SWITCH ON JAGUARIBE" in s for s in said), "too cold, every lane working, and the one machine off is not known to wake: a person is asked, and no packet is sent", (told, said[:3]))

# ---- a machine that did not answer its packet is not asked again for three hours (19 November)
deaf = {"calber": {"what": "on", "ok": False, "ago": 1500, "state": "it did not answer in 20 min"}}
told, plan, said = look(26.5, 25.9, fleet(off=("calber",), paused=("whitewolf-cuda", "whitewolf")), held=("whitewolf-cuda", "whitewolf"), offed=("calber",), orders=deaf)
claim(told == [("queue", "machine", "whitewolf-cuda", "resume")], "too cold, calber off and deaf to its last packet 25 min ago: a lane this law held works again, and calber is not sent another", told)
claim(any("calber did not answer" in s for s in said), "and the log says why calber was passed over", said[:4])
told, plan, said = look(26.5, 25.9, fleet(off=("calber",)), offed=("calber",), orders={"calber": dict(deaf["calber"], ago=4 * 3600)})
claim(told == [("power", "calber", "on")], "four hours after its last packet failed, calber is tried again", told)
told, plan, said = look(26.5, 25.9, fleet(off=("calber",)), offed=("calber",), orders={"calber": {"what": "on", "ok": True, "ago": 1500}})
claim(told == [("power", "calber", "on")], "a packet that was answered last time is no reason to wait", told)

# ---- a lane a person paused is not the law's to resume
told, plan, said = look(26.5, 25.9, fleet(paused=("boburner",)))
claim(not any("boburner" in str(x) for x in told), "a lane a person paused is not resumed", told)

# ---- the pace
told, plan, said = look(27.3, 26.7, fleet(), since=1200.0)
claim(told == [], "too warm, and a change was made twenty minutes ago with a small budget: it waits", told)
told, plan, said = look(27.3, 26.7, fleet(), since=1200.0, slope=0.5)
claim(len(told) == 1, "the same with the room rising half a degree an hour (a budget over 400 W): fifteen minutes is enough", (told, plan.get("budget")))

# ---- the ceiling
told, plan, said = look(27.5, 26.9, fleet(), since=700.0, slope=0.6)
claim(told == [("power", "bosporus", "off")], "at the ceiling (27.2) and rising, twelve minutes after a change: the largest step among the machines without a card, bosporus whole", told)
told, plan, said = look(27.5, 26.9, fleet(off=("bosporus", "jaguaribe")), since=700.0, slope=0.6, offed=("bosporus",))
claim(told == [("power", "calber", "off")], "the same with both Supermicros already off: calber whole, though it has a card", told)
told, plan, said = look(27.5, 26.9, fleet(), since=300.0, slope=0.6)
claim(told == [], "at the ceiling five minutes after a change: it waits out ten", told)

# ---- one probe's spike
told, plan, said = look(27.0, 27.4, fleet(), was=26.7)          # probe b a degree over its usual place, probe a where it was
claim(abs(plan["budget"]["room_c"] - 26.7) < 0.06 and any("spike" in s for s in said), "a probe that jumps a degree by itself is left out: the room is still read as 26.7", (plan["budget"]["room_c"], said[:2]))
told, plan, said = look(27.1, 27.9, fleet(), since=700.0, was=26.8)
claim(len(told) == 1, "but for the ceiling the hotter reading is believed: with the plain mean at 27.5, heat is shed", (told, plan["budget"]["room_c"]))

# ---- where the room is heading
told, plan, said = look(27.1, 26.5, fleet(paused=("whitewolf-cuda",)), held=("whitewolf-cuda",), slope=-0.5)
claim(told == [("queue", "machine", "whitewolf-cuda", "resume")], "inside the band (26.8) and falling 0.5 C an hour: heat is added now, not at the band's foot", (told, said[:2]))
told, plan, said = look(26.9, 26.3, fleet(), slope=0.5)
claim(len(told) == 1 and told[0][0] == "power" and told[0][2] == "off", "inside the band (26.6) and rising 0.5 C an hour: heat is shed now", (told, said[:2]))
told, plan, said = look(27.0, 26.4, fleet(), slope=0.1)
claim(told == [], "inside the band and drifting a tenth of a degree an hour: nothing", told)

# ---- a machine that is on computes
told, plan, said = look(27.0, 26.4, fleet(bench=("bosporus",)))
claim(told == [("queue", "machine", "bosporus", "add")], "a spare that answers and is not in the queue is put in it", told)
told, plan, said = look(27.3, 26.7, fleet(bench=("bosporus",)), slope=0.2)
claim(told == [("power", "bosporus", "off")], "the same with the room too warm and rising: it is switched off instead", told)

# ---- advise
told, plan, said = look(27.3, 26.7, fleet(), act=False)
claim(told == [] and plan["would"] and "bosporus" in plan["would"]["what"] and any("WOULD" in s for s in said), "not in act: it says what it would do and does nothing", (told, plan["would"]))

# ---- the power switch
del TOLD[:]
q, st, t = scratch(room=27.0)
st["set"]["power"] = "off"
ps = [{"key": "room.a.c", "role": "room", "ok": True, "c": 27.3, "machine": "saskatchewan"}, {"key": "room.b.c", "role": "room", "ok": True, "c": 26.7, "machine": "saskatchewan"}]
plan = {"outside_c": 8.0, "now_w": 1200.0}
R.look(H, q, st, t, {}, fleet(), ps, plan, [], True)
shutil.rmtree(q)
claim(TOLD and not any(x[0] == "power" for x in TOLD), "with the power switch off, too warm is a lane taking nothing new and no machine is powered off", TOLD)

# ---- no probe, no watts
del TOLD[:]
q, st, t = scratch()
plan = {"outside_c": 8.0, "now_w": 1200.0}
R.look(H, q, st, t, {}, fleet(), [], plan, [], True)
claim(TOLD == [], "with no fresh room probe nothing is done", TOLD)
shutil.rmtree(q)

# ---- the budget's arithmetic, against the report's two worked cases
told, plan, said = look(26.3, 25.7, fleet(), slope=-0.07)
claim(abs(plan["budget"]["w"] - 166) <= 6, "the budget of 06:37 on 18 November (room 26.00, falling 0.07 C an hour) is +166 W within rounding: %d" % plan["budget"]["w"])
told, plan, said = look(27.4, 26.8, fleet(), slope=0.69, since=100.0)
claim(plan["budget"]["w"] == -600, "the budget of 18:37 on 17 November (room 27.10, rising 0.69) is -853 W, held at -600: %d" % plan["budget"]["w"])

# ---- the house's loss from the steady stretches
rows = [[0, 7200, 26.0, 26.0 - d, d, 125.0 * d - 1200.0] for d in (14.0, 16.5, 19.0, 21.0)]
fit = R.steady_fit(rows)
claim(fit is not None and abs(fit[0] - 125) < 0.5 and abs(fit[1] - 1200) < 5 and fit[2] == 4, "four steady stretches on the line P = 125 (T - To) - 1200 give UA 125 W/C and an other heat of 1200 W", fit)
claim(R.steady_fit(rows[:2]) is None and R.steady_fit([rows[0], rows[0], rows[0]]) is None, "two stretches, or three at one height over the weather, give no line")
looks = [(i * 600.0, 4.0 if i < 60 else 10.0) for i in range(120)]       # ten hours at 4 C, then ten at 10 C
claim(4.0 < R.lagged(looks, 60 * 600.0 + 3600) < 5.0 and 7.5 < R.lagged(looks, 119 * 600.0) < 9.0,
      "the weather the room has felt lags the weather: an hour after it turned from 4 to 10 C it is still under 5; ten hours after, between 7.5 and 9",
      (R.lagged(looks, 60 * 600.0 + 3600), R.lagged(looks, 119 * 600.0)))

# ---- the probes warming are not the room (18 November, 15:07: saskatchewan restarted, its counters came back
# cold and climbed; read as the room rising four degrees an hour, it switched calber off with the room under target)
told, plan, said = look(25.1, 24.5, fleet(), slope=4.14)
claim(told == [] and any("taken as the probes warming" in s for s in said),
      "a room under its target whose probes climb 4.1 C an hour, faster than the fleet's watts could warm it, sheds nothing", (told, said[:3]))
told, plan, said = look(26.9, 26.3, fleet(), slope=0.5)
claim(len(told) == 1 and not any("probes warming" in s for s in said), "a rise of half a degree an hour, which the heat can make, is still believed and acted on", (told, said[:2]))


# ---- full tilt (18 November: "code a button for the heat that goes full tilt. essentially setting temp to max")
def full(ms, lanes, orders=None, dry=False, wol=WOL):
    """One full-tilt pass on a scratch queue; `lanes` is {lane: seconds before full tilt began that it changed}
    (negative: after)."""
    del TOLD[:]
    q, st, t = scratch(wol=wol)
    st.update(mode="full", full_from=t - 600, before_full="act")
    os.makedirs(os.path.join(q, "lanes"))
    json.dump({"hosts": [{"name": n, "target": "user@" + n} for n in WATTS]}, open(os.path.join(q, "config.json"), "w"))
    for lane, before in lanes.items():
        json.dump({"host": lane, "state": "paused", "since": t - 600 - before}, open(os.path.join(q, "lanes", lane + ".json"), "w"))
    if orders:
        json.dump({n: dict(o, t=t - o.pop("ago")) for n, o in orders.items()}, open(H.hp(q, "power.json"), "w"))
    plan, said = {"temp_c": 25.5}, []
    H.full_tilt(q, st, t, ms, plan, said, dry)
    told = list(TOLD)
    shutil.rmtree(q)
    return told, plan, said


ms = fleet(paused=("columbia", "whitewolf-cuda", "boburner"), bench=("calber",), off=("bosporus", "jaguaribe"))
ms["mac"] = {"name": "mac", "cpu": [{"name": "mac", "caps": ["own"], "paused": True}], "card": [], "bench": False, "target": "-", "special": "",
             "fresh": True, "wall_w": 24, "in_hand": []}
told, plan, said = full(ms, {"columbia": 3600, "whitewolf-cuda": 3600, "boburner": -300, "mac": 3600})
claim(sorted(told) == sorted([("queue", "machine", "columbia", "resume"), ("queue", "machine", "whitewolf-cuda", "resume"),
                              ("queue", "machine", "calber", "add"), ("power", "bosporus", "on")]),
      "full tilt: lanes paused before it work again, a machine on the bench that answers is put in the queue, one known to wake is woken", told)
claim(not any("boburner" in str(x) for x in told), "a lane a person paused after full tilt began is left paused", told)
claim(not any("mac" == x[2] for x in told if len(x) > 2), "this Mac's own lane is never touched", told)
claim(not any("jaguaribe" in str(x) for x in told) and any("JAGUARIBE" in w.upper() and "SWITCH IT ON" in w for w in said),
      "a machine off and not known to wake is not sent a packet: a person is asked to switch it on", said)
claim(not any(x[0] == "power" and x[2] == "off" for x in told) and not any(len(x) > 3 and x[3] in ("pause", "finish", "remove") for x in told),
      "full tilt sheds nothing and powers nothing off", told)

told, plan, said = full(fleet(paused=("whitewolf", "whitewolf-cuda")), {"whitewolf": 3600, "whitewolf-cuda": -60})
claim(told == [("queue", "machine", "whitewolf", "resume"), ("queue", "machine", "whitewolf-cuda", "pause")],
      "the queue's resume of a machine resumes its card too: a card lane a person paused after full tilt began is paused again", told)

told, plan, said = full(fleet(), {})
claim(told == [] and any("everything that can compute is computing" in w for w in said), "with everything working, a pass does nothing", (told, said))

told, plan, said = full(fleet(off=("bosporus",), bench=()), {}, orders={"bosporus": {"what": "on", "ago": 120}})
claim(told == [], "a machine whose packet went two minutes ago is not sent another", told)
told, plan, said = full(fleet(off=("bosporus",)), {}, orders={"bosporus": {"what": "on", "ago": 300, "done": 1, "ok": False, "state": "it did not answer"}})
claim(told == [], "one that did not answer a packet sent since full tilt began is not sent another within the hour", told)

# A new power order over an old finished one is in flight (18 November: the old order's `done` stood on the
# new one, and full tilt sent jaguaribe a packet every pass).
_q = tempfile.mkdtemp(prefix="hold-check-")
os.makedirs(os.path.join(_q, "hearth"))
H.power_note(_q, "jaguaribe", what="on", t=100.0, state="it answered", ok=True, done=200.0)
H.power_note(_q, "jaguaribe", what="on", t=1000.0, state="the wake packet was sent", ok=None)
_o = json.load(open(H.hp(_q, "power.json")))["jaguaribe"]
shutil.rmtree(_q)
claim("done" not in _o and _o["t"] == 1000.0, "a new power order starts a new record: an earlier order's finish does not stand on it", _o)

told, plan, said = full(fleet(paused=("columbia",), off=("bosporus",)), {"columbia": 3600}, dry=True)
claim(told == [] and any(w.startswith("would:") for w in plan["full"]["did"]), "a dry pass says what it would do and does nothing", (told, plan["full"]))

print("\n%s" % ("PASSED" if not FAILED else "FAILED: %d claim(s)" % len(FAILED)))
sys.exit(1 if FAILED else 0)
