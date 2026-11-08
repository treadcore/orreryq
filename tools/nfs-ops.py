#!/usr/bin/env python3
"""nfs-ops: what one file costs a share, counted at the server rather than reasoned.

    python3 nfs-ops.py CLIENT DIR [--files N] [--label L]

CLIENT is `mac` (this machine) or an ssh target; DIR is the share's mount on it. N small files (200) are made,
moved and removed in DIR, and around each step the server's own counters are read: its NFS operations
(/proc/net/rpc/nfsd: NFSv3 procedures, NFSv4 operations) and the flushes each of its disks completed (the
kernel's per-disk flush count). Each step's counts are divided by N. Run it when nothing else uses the share:
the counters are the server's, not this client's. No root anywhere. Results go to
~/.cache/orrery-bench/nfs/LABEL-ops-STAMP.json beside the client bench's.
"""

import json
import os
import subprocess
import sys
import time

SERVER = "calber"
DISKS = ["sda", "sdb", "sdc", "sdd", "sde", "sdf"]
OUT = os.path.expanduser("~/.cache/orrery-bench/nfs")
V3 = ("null getattr setattr lookup access readlink read write create mkdir symlink mknod remove rmdir rename link "
      "readdir readdirplus fsstat fsinfo pathconf commit").split()
V4 = {3: "access", 4: "close", 5: "commit", 6: "create", 9: "getattr", 10: "getfh", 15: "lookup", 18: "open",
      22: "putfh", 25: "read", 26: "readdir", 28: "remove", 29: "rename", 31: "restorefh", 32: "savefh",
      34: "setattr", 38: "write", 53: "sequence", 72: "getxattr", 73: "setxattr", 74: "listxattrs"}
# The operations that change the disks; on a sync share each is answered only once on stable storage.
CHANGING = {"setattr", "write", "create", "mkdir", "remove", "rmdir", "rename", "commit", "open", "close",
            "setxattr", "link", "symlink"}

COUNTERS = r'''
import json
v3, v4 = [], []
for line in open("/proc/net/rpc/nfsd"):
    w = line.split()
    if w[0] == "proc3":
        v3 = [int(x) for x in w[2:]]
    if w[0] == "proc4ops":
        v4 = [int(x) for x in w[2:]]
fl = {}
for d in %r:
    f = open("/sys/block/%%s/stat" %% d).read().split()
    fl[d] = int(f[15]) if len(f) > 15 else None   # the 16th field: flush requests completed (Linux 5.5 on)
print(json.dumps({"v3": v3, "v4": v4, "flush": fl}))
''' % (DISKS,)

ACT = r'''
import os, sys, time
step, base, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
blob = os.urandom(4096)
t = time.time()
if step == "make":
    os.makedirs(os.path.join(base, "a"))
    os.makedirs(os.path.join(base, "b"))
    for i in range(n):
        with open(os.path.join(base, "a", "f%05d.bin" % i), "wb") as f:
            f.write(blob)
elif step == "move":
    for i in range(n):
        os.rename(os.path.join(base, "a", "f%05d.bin" % i), os.path.join(base, "b", "f%05d.bin" % i))
elif step == "remove":
    for i in range(n):
        os.remove(os.path.join(base, "b", "f%05d.bin" % i))
    for d in os.listdir(base):            # what the client's own companions left behind
        p = os.path.join(base, d)
        for x in os.listdir(p) if os.path.isdir(p) else []:
            try:
                os.remove(os.path.join(p, x))
            except FileNotFoundError:
                pass
        try:
            os.rmdir(p)
        except (FileNotFoundError, OSError):
            pass
    os.rmdir(base)
print(round(time.time() - t, 3))
'''


def run(where, code, args=()):
    cmd = (["python3", "-"] if where in (None, "mac") else ["ssh", "-o", "BatchMode=yes", where, "python3", "-"]) + [str(a) for a in args]
    p = subprocess.run(cmd, input=code, capture_output=True, text=True, timeout=600)
    if p.returncode:
        raise SystemExit("%s: %s" % (where, (p.stderr or p.stdout).strip()[-300:]))
    return p.stdout.strip()


def diff(a, b, n):
    ops = {}
    for i, name in enumerate(V3):
        if i < len(a["v3"]) and b["v3"][i] - a["v3"][i]:
            ops["v3 " + name] = round((b["v3"][i] - a["v3"][i]) / n, 2)
    for i in range(min(len(a["v4"]), len(b["v4"]))):
        if b["v4"][i] - a["v4"][i]:
            ops["v4 " + V4.get(i, "op%d" % i)] = round((b["v4"][i] - a["v4"][i]) / n, 2)
    fl = sum((b["flush"][d] or 0) - (a["flush"][d] or 0) for d in DISKS)
    return ops, round(fl / n, 2)


def main(a):
    if len(a) < 2:
        sys.exit(__doc__)
    client, base = a[0], a[1]
    n = int(a[a.index("--files") + 1]) if "--files" in a else 200
    label = a[a.index("--label") + 1] if "--label" in a else client.split("@")[-1]
    work = os.path.join(base, "nfs-ops-%d" % int(time.time()))
    steps = {}
    for step in ("make", "move", "remove"):
        before = json.loads(run(SERVER, COUNTERS))
        secs = float(run(client, ACT, (step, work, n)))
        time.sleep(1.0)        # the server's last replies and flushes land in its counters
        after = json.loads(run(SERVER, COUNTERS))
        ops, flushes = diff(before, after, n)
        changing = round(sum(v for k, v in ops.items() if k.split()[1] in CHANGING), 2)
        steps[step] = {"secs": secs, "per_s": round(n / secs, 1), "ops_per_file": ops, "changing_per_file": changing,
                       "disk_flushes_per_file": flushes}
        print("%-7s %6.1f files/s  %5.2f changing ops a file  %5.2f disk flushes a file   %s"
              % (step, n / secs, changing, flushes, "  ".join("%s %g" % (k, v) for k, v in sorted(ops.items(), key=lambda kv: -kv[1]))))
    os.makedirs(OUT, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(OUT, "%s-ops-%s.json" % (label, stamp))
    with open(path, "w") as f:
        json.dump({"kind": "ops", "label": label, "client": client, "files": n, "stamp": stamp, "steps": steps}, f, indent=1)
    print("saved", path)


if __name__ == "__main__":
    main(sys.argv[1:])
