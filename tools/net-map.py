#!/usr/bin/env python3
"""net-map: the home network measured from inside it -- every machine's links, and what each path carries.

The switches cannot be asked: they are unmanaged, they have no address, they send nothing. What can be measured is
what they do. A machine's own link says its speed; one stream between two machines says what the path between them
carries; and several machines sending to one at once say what they share -- two senders that each keep their full
rate reach the receiver by separate links, two that halve each other sit behind one. From those the switches and the
links between them are inferred, and the inference is said to be one.

    python3 net-map.py inventory                       every machine's wired links: speed, driver, address
    python3 net-map.py pair A B [--secs S] [--streams N]   A sends to B for S seconds (5): one path, one way
    python3 net-map.py star HUB [--secs S]             every machine to HUB, one at a time
    python3 net-map.py fanin HUB A B ... [--secs S]    A, B ... send to HUB at once: what they share
    python3 net-map.py show                            every measure so far

Runs from the Mac. Each machine is reached by ssh and runs python3 from stdin: nothing is installed, no root. The
receiver listens on TCP 5299 for the test alone. The Mac and the VM send but do not receive (the Mac's firewall
asks; the VM sits behind the Mac's NAT). Results go to ~/.cache/orrery-bench/net/.
"""

import json
import os
import socket
import subprocess
import sys
import threading
import time

OUT = os.path.expanduser("~/.cache/orrery-bench/net")
PORT = 5299

# name: (how to reach it by ssh, or None for this Mac; can it receive). Addresses come from the inventory.
HOSTS = {
    "mac": (None, False),
    "calber": ("calber", True),
    "whitewolf": ("whitewolf", True),
    "boburner": ("boburner", True),
    "saskatchewan": ("saskatchewan", True),
    "jaguaribe": ("jaguaribe", True),
    "bosporus": ("bosporus", True),
    "columbia": ("columbia", True),
    "nasser": ("user@192.168.8.121", True),
    "xinanjiang": ("user@192.168.8.217", True),
    "vm": ("user@192.168.64.39", False),
}

# ---- the code each machine runs, sent over ssh's stdin -------------------------------------------------------

LINKS = r'''
import json, os, socket, subprocess
rows = []
for n in sorted(os.listdir("/sys/class/net")):
    p = "/sys/class/net/" + n
    if n == "lo" or not os.path.exists(p + "/device"):
        continue
    def rd(f):
        try:   # a link that is down answers its speed with EINVAL, not a number
            return open(p + "/" + f).read().strip()
        except OSError:
            return ""
    try:
        speed = int(rd("speed"))
    except ValueError:
        speed = None
    drv = ""
    for line in rd("device/uevent").splitlines():
        if line.startswith("DRIVER="):
            drv = line[7:]
    addr = subprocess.run(["ip", "-4", "-o", "addr", "show", n], capture_output=True, text=True).stdout.split()
    ip = addr[addr.index("inet") + 1].split("/")[0] if "inet" in addr else ""
    rows.append({"if": n, "speed": speed if speed and speed > 0 else None, "state": rd("operstate"), "mac": rd("address"),
                 "driver": drv, "ip": ip, "wireless": os.path.exists(p + "/wireless")})
print(json.dumps({"host": socket.gethostname(), "links": rows}))
'''

# The receiver: counts each sender's bytes every tenth of a second; the rate is taken over the stretch when every
# sender was sending, the first and last second left out, so senders that start a little apart still compare.
SINK = r'''
import json, socket, sys, threading, time
port, secs, expect = int(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("", port)); srv.listen(64); srv.settimeout(secs + 20)
count, first, lock = {}, {}, threading.Lock()
def take(c, peer):
    buf = bytearray(4 << 20); mv = memoryview(buf)
    while True:
        n = c.recv_into(mv)
        if not n:
            break
        with lock:
            if peer not in first:
                first[peer] = time.time()
            count[peer] = count.get(peer, 0) + n
print("ready", flush=True)
threads, deadline = [], time.time() + secs + 20
while len(threads) < expect and time.time() < deadline:
    try:
        c, a = srv.accept()
    except socket.timeout:
        break
    t = threading.Thread(target=take, args=(c, a[0]), daemon=True); t.start(); threads.append(t)
samples = []
end = time.time() + secs + 3
while time.time() < end:
    with lock:
        samples.append((time.time(), dict(count)))
    if not any(t.is_alive() for t in threads):
        break
    time.sleep(0.1)
with lock:
    samples.append((time.time(), dict(count)))
t0 = max(first.values()) + 1.0 if first else 0
t1 = min(t for t, c in samples if all(c.get(p) == samples[-1][1].get(p) for p in first)) - 1.0 if first else 0
# Between two real samples, their own times: a count read from a sample taken before the window's start, set
# against the window's length, overstated a 1 GbE path at 962 Mb/s, past the 941 TCP can carry (7 November).
inside = [(ts, c) for ts, c in samples if t0 <= ts <= t1]
rates, span = {}, 0.0
if len(inside) >= 2:
    (a_t, a_c), (b_t, b_c) = inside[0], inside[-1]
    span = b_t - a_t
    rates = {p: round((b_c.get(p, 0) - a_c.get(p, 0)) * 8 / 1e6 / span, 1) for p in first}
print(json.dumps({"window_s": round(span, 2), "Mbps": rates, "bytes": count}), flush=True)
'''

SOURCE = r'''
import os, socket, sys, time
host, port, secs, start, streams = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5])
for i in range(streams - 1):
    if os.fork() == 0:
        break
time.sleep(max(0, start - time.time()))
s = socket.create_connection((host, port), timeout=10)
buf = memoryview(bytes(4 << 20)); end = time.time() + secs
while time.time() < end:
    s.sendall(buf)
s.close()
'''


def remote(name, code, args=(), timeout=120, popen=False):
    via = HOSTS[name][0]
    cmd = (["python3", "-"] if via is None else ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", via, "python3", "-"]) + [str(a) for a in args]
    if popen:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        p.stdin.write(code)
        p.stdin.close()
        return p
    p = subprocess.run(cmd, input=code, capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError("%s: %s" % (name, (p.stderr or p.stdout).strip()[-300:]))
    return p.stdout


def save(kind, rec):
    os.makedirs(OUT, exist_ok=True)
    rec.update(kind=kind, stamp=time.strftime("%Y%m%d-%H%M%S"), at=time.time())
    path = os.path.join(OUT, "%s-%s.json" % (kind, rec["stamp"]))
    with open(path, "w") as f:
        json.dump(rec, f, indent=1)
    return path


def say(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ---- inventory ----------------------------------------------------------------------------------------------

def mac_links():
    rows = []
    for ifname in ("en0", "en1"):
        p = subprocess.run(["ifconfig", ifname], capture_output=True, text=True).stdout
        if not p:
            continue
        ip = mac = media = ""
        for line in p.splitlines():
            w = line.split()
            if w and w[0] == "inet":
                ip = w[1]
            if w and w[0] == "ether":
                mac = w[1]
            if "media:" in line:
                media = line.split("media:")[1].strip()
        speed = 1000 if "1000base" in media else 10000 if "10Gbase" in media else 100 if "100base" in media else None
        rows.append({"if": ifname, "speed": speed, "state": "up" if "status: active" in p else "down", "mac": mac,
                     "driver": "Wi-Fi" if ifname == "en1" else "Ethernet", "ip": ip, "wireless": ifname == "en1", "media": media})
    return {"host": socket.gethostname(), "links": rows}


def inventory():
    found = {}
    for name in HOSTS:
        try:
            found[name] = mac_links() if name == "mac" else json.loads(remote(name, LINKS, timeout=30))
        except Exception as e:   # one machine away does not stop the map: it is listed as unreached
            found[name] = {"error": str(e)[:200]}
        rows = found[name].get("links", [])
        up = [r for r in rows if r["state"] == "up" and not r["wireless"]]
        say("%-13s %s" % (name, "; ".join("%s %s Mb/s %s %s" % (r["if"], r["speed"], r["driver"], r["ip"]) for r in up)
                          or found[name].get("error", "no wired link up")))
    return save("inventory", {"hosts": found})


def address(name):
    inv = latest("inventory")
    if inv:
        for r in inv["hosts"].get(name, {}).get("links", []):
            if r["state"] == "up" and r["ip"] and not r["wireless"] and r["ip"].startswith("192.168.8."):
                return r["ip"]
    raise SystemExit("no address for %s: run inventory first" % name)


# ---- moving bytes ---------------------------------------------------------------------------------------------

def flow(hub, senders, secs, streams=1):
    """senders send to hub at once; the hub's view of each one's rate, in Mb/s."""
    if not HOSTS[hub][1]:
        raise SystemExit("%s cannot receive (the Mac's firewall; the VM's NAT)" % hub)
    total = len(senders) * streams
    sink = remote(hub, SINK, (PORT, secs, total), popen=True)
    line = sink.stdout.readline()
    if not line.startswith("ready"):
        sink.kill()
        raise RuntimeError("%s did not listen: %s" % (hub, line + sink.stderr.read()[-300:]))
    start = time.time() + 2.5
    ip = address(hub)
    procs = [remote(s, SOURCE, (ip, PORT, secs, start, streams), popen=True) for s in senders]
    for p in procs:
        p.wait(timeout=secs + 60)
    out = sink.stdout.read()   # its stdin is already closed: communicate() would try to flush it
    sink.wait(timeout=secs + 40)
    res = json.loads(out.strip().splitlines()[-1])
    by_ip = {}
    for name in senders:
        try:
            by_ip[sender_ip(name, hub)] = name
        except SystemExit:
            pass
    rates = {by_ip.get(p, p): v for p, v in res["Mbps"].items()}
    return rates, res["window_s"]


def sender_ip(name, hub):
    # The Mac and the VM reach the hub from the Mac's wired address: the VM through its NAT.
    if name in ("mac", "vm"):
        return mac_links()["links"][0]["ip"]
    return address(name)


def pair(a, b, secs, streams):
    rates, win = flow(b, [a], secs, streams)
    v = list(rates.values())[0] if rates else None
    say("%s -> %s: %s Mb/s over %.1f s%s" % (a, b, v, win, (" (%d streams)" % streams) if streams > 1 else ""))
    return save("pair", {"from": a, "to": b, "secs": secs, "streams": streams, "Mbps": v, "window_s": win})


def star(hub, secs):
    rows = {}
    for name in HOSTS:
        if name == hub:
            continue
        try:
            rates, win = flow(hub, [name], secs)
            rows[name] = list(rates.values())[0] if rates else None
        except Exception as e:
            rows[name] = None
            say("%s: %s" % (name, str(e)[:160]))
            continue
        say("%-13s -> %s: %8.1f Mb/s" % (name, hub, rows[name] or 0))
    return save("star", {"hub": hub, "secs": secs, "Mbps": rows})


def fanin(hub, senders, secs):
    rates, win = flow(hub, senders, secs)
    for n in senders:
        say("%-13s -> %s: %8.1f Mb/s" % (n, hub, rates.get(n) or 0))
    say("together: %.1f Mb/s over %.1f s" % (sum(v for v in rates.values() if v), win))
    return save("fanin", {"hub": hub, "senders": senders, "secs": secs, "Mbps": rates, "window_s": win})


# ---- show ----------------------------------------------------------------------------------------------------

def records(kind=None):
    if not os.path.isdir(OUT):
        return []
    out = []
    for f in sorted(os.listdir(OUT)):
        if f.endswith(".json") and (kind is None or f.startswith(kind + "-")):
            out.append(json.load(open(os.path.join(OUT, f))))
    return out


def latest(kind):
    r = records(kind)
    return r[-1] if r else None


def show():
    inv = latest("inventory")
    if inv:
        print("links (wired, up):")
        for name, h in inv["hosts"].items():
            up = [r for r in h.get("links", []) if r["state"] == "up" and not r["wireless"]]
            print("  %-13s %s" % (name, "; ".join("%s %s Mb/s (%s) %s" % (r["if"], r["speed"], r["driver"], r["ip"]) for r in up) or h.get("error", "-")))
    for r in records():
        if r["kind"] == "pair":
            print("pair   %s -> %s: %s Mb/s%s" % (r["from"], r["to"], r["Mbps"], " x%d" % r["streams"] if r["streams"] > 1 else ""))
        elif r["kind"] == "star":
            print("star   to %s: %s" % (r["hub"], ", ".join("%s %s" % (k, v) for k, v in r["Mbps"].items())))
        elif r["kind"] == "fanin":
            tot = sum(v for v in r["Mbps"].values() if v)
            print("fanin  to %s: %s = %.0f Mb/s" % (r["hub"], ", ".join("%s %s" % (k, v) for k, v in r["Mbps"].items()), tot))


def main(a):
    if not a or a[0] in ("-h", "--help"):
        sys.exit(__doc__)
    secs = float(a[a.index("--secs") + 1]) if "--secs" in a else 5.0
    streams = int(a[a.index("--streams") + 1]) if "--streams" in a else 1
    pos = [x for i, x in enumerate(a[1:], 1) if not x.startswith("--") and a[i - 1] not in ("--secs", "--streams")]
    for n in pos:
        if n not in HOSTS:
            sys.exit("no machine %s; known: %s" % (n, " ".join(HOSTS)))
    if a[0] == "inventory":
        return inventory()
    if a[0] == "pair" and len(pos) == 2:
        return pair(pos[0], pos[1], secs, streams)
    if a[0] == "star" and len(pos) == 1:
        return star(pos[0], secs)
    if a[0] == "fanin" and len(pos) >= 2:
        return fanin(pos[0], pos[1:], secs)
    if a[0] == "show":
        return show()
    sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
