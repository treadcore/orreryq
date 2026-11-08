#!/usr/bin/env python3
"""boots.py -- after a power cut: what came back, and what came back different.

    tools/boots.py QUEUE check [--force] [--host NAME]   read each machine that booted since its record
    tools/boots.py QUEUE accept NAME                     a machine's changed boot is its normal now
    tools/boots.py QUEUE show                            the record (QUEUE/plan/boots.json)

THE MORNING OF 8 NOVEMBER, DONE BY HAND, IS THIS FILE'S SPECIFICATION. The power went at 21:02 and
came back at 05:49, and until 07:47 nothing ran, because the keeper did not start itself. Then it
was one ssh at a time: which machines answered; whether the GPU islands' saved state had reached the
disk (whitewolf's was saved five seconds before the cut, the timing that left calber's files empty on
7 November); whether the queue's own files read back; and why calber, whose BIOS needed clearing
again, came back with CSM on -- found only because its kernel logged a legacy MP table that Friday's
boot had not. Each of those is a read here, and the keeper asks for them: once when it starts, again
when a machine it could not reach answers, and every boots_s (600) besides (Paul: "The actions we are
doing after a power loss, should be done auto, with GUI buttons").

A MACHINE IS READ ONCE A BOOT. Its boot id says whether anything changed since the record, and only a
new boot (or --force) reads the firmware and the islands' files, 141 MB each. A boot is compared with
THE BOOT BEFORE IT on the same machine, not with a list of how each should be set: the record says
what was, and a change is a sentence ("CSM off -> on"), not a verdict. Kernel and system changes are
updates, shown and not flagged; firmware, the boot list, Secure Boot, CSM and the GPU are flagged, once
a boot, until Accept says the new boot is the machine's normal.

CSM IS READ AS THE LEGACY MP TABLE IN THE KERNEL'S LOG. On calber the table is there with CSM on and
absent with it off (Friday's F15 report, and this morning); another board may keep one either way,
which the comparison absorbs, because it compares a machine with itself.

NOT READ: the memory's speed (dmidecode needs root) and AC BACK (kept where Linux cannot see it). The
page names both, so nobody takes their absence for a pass.
"""
import fcntl
import json
import os
import re
import subprocess
import sys
import threading
import time

SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "ServerAliveInterval=15"]
# Flagged when they change between boots; the rest are shown.
FLAGGED = ("firmware", "board", "uefi", "csm", "secure_boot", "boot_entry", "boot_entries", "gpu")
NAMES = {"firmware": "firmware", "board": "board", "uefi": "UEFI", "csm": "CSM", "secure_boot": "Secure Boot",
         "boot_entry": "booted from", "boot_entries": "boot entries", "gpu": "GPU", "kernel": "kernel", "system": "system"}

# One script, every machine: key=value lines. ONLY_ID=1 stops after the boot's id; ISLANDS=1 reads the
# crucible homes' island.state (QNAME is the queue's name, the remote home fleet/q-QNAME).
SCRIPT = r'''
k() { printf '%s=%s\n' "$1" "$2"; }
if [ "$(uname)" = Darwin ]; then
  b=$(sysctl -n kern.boottime | sed 's/^{ sec = \([0-9]*\).*/\1/')
  k os mac; k boot_id "$b"; k booted "$b"; k kernel "$(uname -r)"; k system "macOS $(sw_vers -productVersion)"
  exit 0
fi
k os linux
k boot_id "$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)"
k booted "$(awk '/^btime/ {print $2}' /proc/stat)"
k kernel "$(uname -r)"
k system "$(. /etc/os-release 2>/dev/null; echo "$PRETTY_NAME")"
[ "$ONLY_ID" = 1 ] && exit 0
k firmware "$(cat /sys/class/dmi/id/bios_version 2>/dev/null) $(cat /sys/class/dmi/id/bios_date 2>/dev/null)"
k board "$(cat /sys/class/dmi/id/board_vendor 2>/dev/null) $(cat /sys/class/dmi/id/board_name 2>/dev/null)"
[ -d /sys/firmware/efi ] && k uefi yes || k uefi no
if journalctl -k -b 0 -q --no-pager 2>/dev/null | head -50 | grep -q 'Linux version'; then
  journalctl -k -b 0 -q --no-pager 2>/dev/null | grep -q 'found SMP MP-table' && k csm on || k csm off
elif dmesg 2>/dev/null | head -5 | grep -q 'Linux version'; then
  dmesg 2>/dev/null | grep -q 'found SMP MP-table' && k csm on || k csm off
fi
case "$(mokutil --sb-state 2>/dev/null | head -1)" in
  *enabled*) k secure_boot on ;;
  *disabled*) k secure_boot off ;;
esac
if command -v efibootmgr >/dev/null 2>&1; then
  e=$(efibootmgr 2>/dev/null)
  cur=$(printf '%s\n' "$e" | sed -n 's/^BootCurrent: //p')
  k boot_entries "$(printf '%s\n' "$e" | grep -c '^Boot[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]')"
  [ -n "$cur" ] && k boot_entry "$(printf '%s\n' "$e" | awk -v c="Boot$cur" 'index($0, c) == 1 { sub(/^Boot[0-9A-Fa-f]+\*? ?/, ""); split($0, a, "\t"); print a[1]; exit }')"
fi
command -v systemd-analyze >/dev/null 2>&1 && k timing "$(systemd-analyze 2>/dev/null | head -1)"
command -v nvidia-smi >/dev/null 2>&1 && k gpu "$(nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>&1 | head -4 | tr '\n' ';' | sed 's/;$//')"
if [ "$ISLANDS" = 1 ] && command -v python3 >/dev/null 2>&1; then
  for f in "$HOME"/fleet/q-"$QNAME"/*/island.state; do
    [ -f "$f" ] || continue
    printf 'island=%s\n' "$(python3 -c '
import json, os, struct, sys
f = sys.argv[1]; z = n = 0; Z = bytes(4096)
with open(f, "rb") as h:
    head = h.read(20); h.seek(0)
    while True:
        b = h.read(4096)
        if not b: break
        n += 1; z += b == Z[:len(b)]
ok = head[:4] == b"3urc" and len(head) >= 20
print(json.dumps({"path": f, "bytes": os.path.getsize(f), "mtime": int(os.path.getmtime(f)), "blocks": n, "zero": z, "magic": ok, "gen": struct.unpack("<I", head[16:20])[0] if ok else None}))
' "$f")"
  done
fi
'''


def now_iso(t=None):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t if t is not None else time.time()))


def secs(iso):
    try:
        return time.mktime(time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return 0.0


def load(p, d=None):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def save(p, doc):
    tmp = "%s.%d.tmp" % (p, os.getpid())
    with open(tmp, "w") as f:
        json.dump(doc, f, indent=1)
    os.replace(tmp, p)


def machines_of(qdir):
    """The machines in the queue's config, one a box: calber and calber-cuda are lanes of one
    machine (one target), and a lane's name is not the machine's. The Mac is "-": read here."""
    cfg = load(os.path.join(qdir, "config.json"), {}) or {}
    out = {}
    for h in cfg.get("hosts", []):
        target = h.get("target", "-")
        name = h.get("lane_of") or h["name"]
        m = next((m for m in out.values() if m["target"] == target), None)
        if m is None:
            m = out.setdefault(name, {"name": name, "target": target, "lanes": [], "cuda": False})
        m["lanes"].append(h["name"])
        m["cuda"] = m["cuda"] or "cuda" in h.get("caps", [])
    return list(out.values())


def read(m, qname, only_id, timeout):
    """Run the script on a machine: (facts, islands) or None when it cannot be reached."""
    env = "QNAME=%s; ONLY_ID=%d; ISLANDS=%d\n" % (qname, 1 if only_id else 0, 1 if m["cuda"] and not only_id else 0)
    argv = ["sh", "-s"] if m["target"] in ("-", "") else SSH + [m["target"], "sh -s"]
    try:
        r = subprocess.run(argv, input=env + SCRIPT, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    facts, islands = {}, []
    for line in r.stdout.splitlines():
        k, _, v = line.partition("=")
        if k == "island":
            try:
                islands.append(json.loads(v))
            except ValueError:
                pass
        elif k:
            facts[k] = v.strip()
    if not facts.get("boot_id"):
        return None
    return facts, islands


def timing(text):
    """systemd-analyze's first line as seconds a stage: firmware, loader, kernel, initrd, userspace."""
    out = {}
    head = (text or "").split("=")[0]
    for mins, secs, unit, stage in re.findall(r"(?:(\d+)min )?([\d.]+)(ms|s) \((\w+)\)", head):
        out[stage] = round(int(mins or 0) * 60 + float(secs) / (1000 if unit == "ms" else 1), 1)
    return out


def changes(before, after):
    """[key, was, now] for each fact the two boots both read and read differently."""
    out = []
    for k in FLAGGED + ("kernel", "system"):
        a, b = (before or {}).get(k), (after or {}).get(k)
        if a is not None and b is not None and a != b:
            out.append([k, a, b])
    return out


def island_harm(i):
    """What is wrong with a saved island, or None. A cut inside the disk's write-back window leaves
    the file empty or its blocks zero (calber, 7 November: names and times on disk, no data)."""
    # The header's magic is not asked for: the first homes (crucible, crucible-hybrid) saved in a
    # format from before it, and a file without it is older, not damaged.
    if not i.get("bytes"):
        return "is empty"
    if i.get("zero"):
        return "has %d zeroed blocks of %d" % (i["zero"], i.get("blocks", 0))
    return None


def flag(qdir, kind, text, key):
    """A flag for a person, in the keeper's form (flags/SEQ-KIND.json), once a key."""
    d = os.path.join(qdir, "flags")
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        if f.endswith(".json") and (load(os.path.join(d, f), {}) or {}).get("key") == key:
            return
    seq = int(time.time() * 1000)
    while os.path.exists(os.path.join(d, "%d-%s.json" % (seq, kind))):
        seq += 1
    fid = "%d-%s" % (seq, kind)
    tmp = os.path.join(d, ".%s.%d.tmp" % (fid, os.getpid()))
    with open(tmp, "w") as f:
        json.dump({"id": fid, "t": now_iso(), "kind": kind, "text": text, "key": key, "ack": None, "progress": False}, f)
    os.rename(tmp, os.path.join(d, fid + ".json"))


def acked(qdir, key):
    """Was the flag of this key acknowledged (Flags page, or Accept)?"""
    d = os.path.join(qdir, "flags")
    for f in os.listdir(d) if os.path.isdir(d) else []:
        j = load(os.path.join(d, f), {}) or {} if f.endswith(".json") else {}
        if j.get("key") == key:
            return bool(j.get("ack"))
    return False


def ack(qdir, key, by):
    d = os.path.join(qdir, "flags")
    for f in os.listdir(d) if os.path.isdir(d) else []:
        p = os.path.join(d, f)
        j = load(p, {}) or {}
        if f.endswith(".json") and j.get("key") == key and not j.get("ack"):
            j["ack"] = {"by": by, "t": now_iso()}
            save(p, j)


def queue_files(qdir):
    """The Mac's side of a cut: every JSON the keeper and the planner keep, read back."""
    bad, n = [], 0
    for sub in ("", "plan", "lanes"):
        d = os.path.join(qdir, sub)
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if not f.endswith(".json"):
                continue
            n += 1
            try:
                with open(os.path.join(d, f)) as h:
                    json.load(h)
            except (OSError, ValueError):
                bad.append(os.path.join(sub, f))
    return {"read": n, "bad": bad}


def the_cut(qdir):
    """The last cut: QUEUE/cut.json, which a keeper writes when it starts after one that never ended
    (its keeper.pid left behind). A cut from before that file is found once in the events: the
    jobs a dead keeper left were requeued just before the next keeper started."""
    cut = load(os.path.join(qdir, "cut.json"))
    if cut and "jobs" not in cut:
        back = secs(cut.get("keeper_back"))
        ids = []
        try:
            with open(os.path.join(qdir, "events.jsonl")) as f:
                for line in f:
                    if '"requeued"' in line and "died" in line:
                        e = json.loads(line)
                        if abs(secs(e.get("t")) - back) <= 10:
                            ids.append(e.get("job"))
        except (OSError, ValueError):
            pass
        cut["jobs"] = ids
        save(os.path.join(qdir, "cut.json"), cut)
    if cut:
        return cut
    last, quiet, back, n, ids = None, None, None, 0, []
    try:
        with open(os.path.join(qdir, "events.jsonl")) as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("event") == "requeued" and "died" in (e.get("why") or ""):
                    if back is None or n == 0:
                        quiet, n, ids = last, 0, []
                    n += 1
                    ids.append(e.get("job"))
                    back = "pending"
                    continue
                if e.get("event") == "keeper started" and back == "pending":
                    # A keeper stopped from outside and started again at once left the same
                    # requeues; a cut is a quiet of minutes at least.
                    if quiet and secs(e["t"]) - secs(quiet) > 300:
                        cut = {"quiet_since": quiet, "keeper_back": e["t"], "requeued": n, "jobs": ids, "source": "events"}
                    back, n = e["t"], 0
                last = e.get("t")
    except OSError:
        return None
    if cut:
        save(os.path.join(qdir, "cut.json"), cut)
    return cut


def cut_jobs(qdir, cut):
    """THE JOBS A CUT INTERRUPTED, READ AGAIN WHEN THEY COME BACK. A job the cut stopped runs again
    under its own id, and what it writes on top of may keep the zeros the cut left on its machine's
    disk: x-calber-cuda-3345 appended to a gens.tsv whose last 116 bytes never got there, and from
    08:46 on 8 November every planner pass died on that row. Each such job's text results (and its
    log) are read for zero bytes once it is done; a file with them is named, with where."""
    out = []
    for jid in (cut or {}).get("jobs") or []:
        if not jid:
            continue
        d = os.path.join(qdir, "results", jid)
        done = os.path.exists(os.path.join(qdir, "done")) and any(f.endswith("-%s.json" % jid) for f in os.listdir(os.path.join(qdir, "done")))
        files = [os.path.join(qdir, "logs", jid + ".log")]
        for root, _, names in os.walk(d):
            files += [os.path.join(root, n) for n in names if n.endswith((".tsv", ".txt", ".log", ".json", ".csv", ".env"))]
        bad = []
        for f in files:
            try:
                with open(f, "rb") as h:
                    b = h.read()
            except OSError:
                continue
            z = b.count(b"\0")
            if z:
                bad.append({"file": os.path.relpath(f, qdir), "zero": z, "at": b.find(b"\0"), "line": b[:b.find(b"\0")].count(b"\n") + 1})
        out.append({"job": jid, "done": done, "bad": bad})
    return out


def summary(rec, qdir):
    """The health line: [level, text] -- bad for a damaged island or unreadable queue file, warn for a
    machine back different and not accepted, ok otherwise."""
    bad, look, read = [], [], []
    for name, m in sorted(rec["machines"].items()):
        b = m.get("boot") or {}
        for i in b.get("islands", []):
            harm = island_harm(i)
            if harm:
                bad.append("%s's %s %s" % (name, os.path.basename(os.path.dirname(i["path"])), harm))
        flagged = [c for c in b.get("changed", []) if c[0] in FLAGGED]
        if flagged and m.get("accepted") != b.get("id"):
            look.append("%s came back different (%s)" % (name, ", ".join("%s %s -> %s" % (NAMES[c[0]], c[1], c[2]) for c in flagged)))
        if b:
            read.append(name)
    zeros = ["%s, run again after the cut, carries %d zero bytes in %s (line %d)" % (j["job"], b["zero"], os.path.basename(b["file"]), b["line"])
             for j in rec.get("cut_jobs") or [] for b in j.get("bad", []) if not acked(qdir, "cut:%s:%s" % (j["job"], b["file"]))]
    qf = rec.get("queue_files") or {}
    if qf.get("bad"):
        bad.append("the queue's %s does not read back" % ", ".join(qf["bad"]))
    if bad:
        return ["bad", "; ".join(bad)]
    if look or zeros:
        return ["warn", "; ".join(([("; ".join(look) + ": Accept on Settings, After a cut, once it is meant")] if look else []) + zeros)]
    cut = rec.get("cut") or {}
    tail = "; the last cut: quiet from %s, the keeper back %s" % ((cut.get("quiet_since") or "?")[5:16].replace("T", " "), (cut.get("keeper_back") or "?")[5:16].replace("T", " ")) if cut else ""
    return ["ok", "%d machines read since their boots, nothing back different%s" % (len(read), tail)]


def check(qdir, force=False, only=None):
    plan = os.path.join(qdir, "plan")
    os.makedirs(plan, exist_ok=True)
    lock = open(os.path.join(plan, ".boots.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("a check is already running")
        return 0
    path = os.path.join(plan, "boots.json")
    rec = load(path, {}) or {}
    rec.setdefault("machines", {})
    qname = os.path.basename(os.path.abspath(qdir).rstrip("/"))
    ms = [m for m in machines_of(qdir) if not only or m["name"] == only]
    ids, full = {}, {}

    def pass_one(m):
        ids[m["name"]] = read(m, qname, True, 30)
    ts = [threading.Thread(target=pass_one, args=(m,)) for m in ms]
    [t.start() for t in ts]
    [t.join() for t in ts]
    again = [m for m in ms if ids.get(m["name"]) and (force or ((rec["machines"].get(m["name"]) or {}).get("boot") or {}).get("id") != ids[m["name"]][0]["boot_id"])]

    def pass_two(m):
        full[m["name"]] = read(m, qname, False, 240)
    ts = [threading.Thread(target=pass_two, args=(m,)) for m in again]
    [t.start() for t in ts]
    [t.join() for t in ts]

    t = now_iso()
    said = []
    for m in ms:
        r = rec["machines"].setdefault(m["name"], {})
        r.update(target=m["target"], lanes=m["lanes"])
        got = ids.get(m["name"])
        if not got:
            r["reach"] = False
            r.setdefault("dark_since", t)
            said.append("%s dark" % m["name"])
            continue
        r["reach"] = True
        r.pop("dark_since", None)
        r["seen"] = t
        if m["name"] not in full or not full[m["name"]]:
            continue
        facts, islands = full[m["name"]]
        booted = int(facts.pop("booted", "0") or 0)
        boot = {"id": facts.pop("boot_id"), "booted": booted, "booted_at": now_iso(booted) if booted else None, "timing": timing(facts.pop("timing", "")),
                "facts": {k: v for k, v in facts.items() if k != "os"}, "islands": islands, "read": t}
        old = r.get("boot")
        if old and old.get("id") != boot["id"]:
            r["before"] = {k: old.get(k) for k in ("id", "booted", "booted_at", "timing", "facts")}
            r.pop("accepted", None)
        before = r.get("before")
        boot["changed"] = changes((before or {}).get("facts"), boot["facts"]) if before else []
        r["boot"] = boot
        when = now_iso(boot["booted"])[5:16].replace("T", " ")
        flagged = [c for c in boot["changed"] if c[0] in FLAGGED]
        if flagged and r.get("accepted") != boot["id"]:
            flag(qdir, "boot", "%s came back different after its boot at %s: %s" % (m["name"], when, ", ".join("%s %s -> %s" % (NAMES[c[0]], c[1], c[2]) for c in flagged)),
                 "boot:%s:%s" % (m["name"], boot["id"]))
        for i in islands:
            harm = island_harm(i)
            if harm:
                flag(qdir, "island", "%s's island %s %s: its last save did not reach the disk; the segment that loads it starts from a damaged state"
                     % (m["name"], os.path.basename(os.path.dirname(i["path"])), harm), "island:%s:%s:%s" % (m["name"], boot["id"], i["path"]))
        said.append("%s read (booted %s)" % (m["name"], when))
    rec["checked"] = t
    rec["queue_files"] = queue_files(qdir)
    rec["cut"] = the_cut(qdir)
    # When the Mac itself came back, if it did inside the quiet: the keeper can only start after it.
    mac = next((r for r in rec["machines"].values() if r.get("target") in ("-", "")), None)
    booted = ((mac or {}).get("boot") or {}).get("booted")
    if rec["cut"] and booted and secs(rec["cut"].get("quiet_since")) < booted < secs(rec["cut"].get("keeper_back")) + 60:
        rec["cut"]["mac_booted"] = now_iso(booted)
    # The first machine up after the quiet: when the power came back, as near as the fleet can say
    # (8 November: the Mac mini restarts by itself and was up at 04:48; the rest waited for a hand
    # at 05:49, and the keeper for 07:47).
    if rec["cut"]:
        quiet = secs(rec["cut"].get("quiet_since"))
        ups = sorted(((r.get("boot") or {}).get("booted") or 0, n) for n, r in rec["machines"].items())
        ups = [(b, n) for b, n in ups if b > quiet]
        if ups:
            rec["cut"]["first_up"] = {"at": now_iso(ups[0][0]), "machine": ups[0][1]}
    rec["cut_jobs"] = cut_jobs(qdir, rec["cut"])
    for j in rec["cut_jobs"]:
        for b in j["bad"]:
            flag(qdir, "cut", "%s ran again after the cut and %s carries %d zero bytes from line %d: what the cut kept from its machine's disk. The planner and growth.py pass such a row over; the file is left as it is"
                 % (j["job"], b["file"], b["zero"], b["line"]), "cut:%s:%s" % (j["job"], b["file"]))
    rec["health"] = summary(rec, qdir)
    save(path, rec)
    print("; ".join(said) or "nothing to read")
    return 0


def accept(qdir, name):
    path = os.path.join(qdir, "plan", "boots.json")
    rec = load(path, {}) or {}
    m = (rec.get("machines") or {}).get(name)
    if not m or not m.get("boot"):
        sys.exit("%s has no boot on record" % name)
    m["accepted"] = m["boot"]["id"]
    ack(qdir, "boot:%s:%s" % (name, m["boot"]["id"]), "operator")
    rec["health"] = summary(rec, qdir)
    save(path, rec)
    print("%s: this boot is its normal now; its next boot is compared with it" % name)
    return 0


def main(a):
    if len(a) < 2:
        sys.exit(__doc__)
    qdir, cmd = a[0], a[1]
    if cmd == "check":
        only = a[a.index("--host") + 1] if "--host" in a else None
        return check(qdir, "--force" in a, only)
    if cmd == "accept" and len(a) > 2:
        return accept(qdir, a[2])
    if cmd == "show":
        print(json.dumps(load(os.path.join(qdir, "plan", "boots.json"), {}), indent=1))
        return 0
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
