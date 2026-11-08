#!/usr/bin/env python3
"""disk-bench.py -- a machine's spare disks: what is on them, and which layout of them is fastest, for any
number of disks, on Ubuntu or Alpine. Paul, 7 November 2026, of calber's six SATA SSDs: "a swap disk or working
disk for Blu Ray Writer. So lots of directory path listings, and sorting files type activity is expected", and,
an hour into the first run: "more verbose output ... with screen graphs and entertaining comparisons", "for N
disks, but our N is 6 today", "a barrage of tests to get an idea of how to make this the fastest".

RUN IT ON THE MACHINE, AS ROOT. Orrery and this session hold no root on a machine: a person types sudo there,
and that is the safeguard the format commands need (tools/storage.py stages its root scripts the same way).

    sudo python3 disk-bench.py candidates                  disks that look spare: unmounted, not the system's
    sudo python3 disk-bench.py inspect                     read only: SMART, and what each disk holds
    python3 disk-bench.py layouts                          the layouts for this machine's N disks
    sudo python3 disk-bench.py run --erase all             every layout, the quick suite (about 4 min each)
    sudo python3 disk-bench.py run --erase md10 zfs-2x3    some of them
    sudo python3 disk-bench.py barrage --erase raw single md10   the deep tests (about 8 min each)
    sudo python3 disk-bench.py barrage --erase zfs-3x2@16k zfs-3x2@1m   a ZFS layout at a record size
    sudo python3 disk-bench.py run --erase md10@nobitmap md10@bigbitmap  an mdadm layout without its bitmap
    sudo python3 disk-bench.py run --erase --repeat 3 md10 md0       each layout three times: the spread of a measure
    --settle N   seconds of quiet after the disks are discarded, before measuring (30 by default)
    --only sweeps   the barrage's parts to run: cliff, sweeps, trees (a comma list; all three by default)
    python3 disk-bench.py report                           bars in the terminal, from every run so far
    sudo python3 disk-bench.py serve --erase md10-ext4 [--async]   build it and share it over NFS, until:
    sudo python3 disk-bench.py export sync|async            switch the share's mode, the data kept
    sudo python3 disk-bench.py unserve                     stop sharing; the disks blank

Detached, so a dropped SSH session does not stop it: `sudo systemd-run --unit=disk-bench --collect python3 …`
on Ubuntu, `sudo setsid nohup python3 … >/dev/null 2>&1 &` on Alpine. Follow it with `tail -f results/LOG`,
which carries the live bars. tools/disk-report.py turns any number of runs into charts and a conclusion matrix.

WHICH DISKS: the serials in disks.txt beside this script, one a line, NEVER device names: a name can move
between boots, and the machine's own disks must never be touched. A run refuses unless every serial is found,
each is a whole disk of the same size, none is mounted or holds the system or swap, and --erase is given. The
disks are taken in disks.txt's order and the last ones serve as spares, logs and caches: put the weakest last.
The disks end blank.

THE QUICK SUITE, each measure about 20 s, on an 8 GiB file, direct I/O, incompressible data:
    seq-write, seq-read       1 MiB, queue 32                   a disc image written, and read to the burner
    butterfly                 two 1 MiB writers at once, one from the file's start and one from its middle
    write-read                2 GiB written, then read back and checked (crc32c)
    rand-read                 4 KiB, 8 threads x queue 16       many threads reading
    rand-write, mixed         4 KiB, 4 threads (mixed: 70% reads)
    sync-write                4 KiB, fsync after each, one thread: what an NFS client does
    metadata                  100,000 files of 4 KiB in 1,000 directories: create, then with the caches emptied
                              a listing (find), ls -lR, every size read and sorted, and delete
The order is fixed and every layout starts from discarded flash, so the layouts are comparable. These drives
slow down once their fast (SLC) write cache is full, so the first write measure runs on an empty cache and the
later ones on a full one; the barrage measures where that happens.

THE BARRAGE (barrage LAYOUT...; "raw" is one bare disk, no filesystem):
    cache cliff   75 s of 1 MiB sequential writes, the speed every second: where the fast cache ends, in GB
    block sizes   4K 16K 64K 256K 1M, sequential and random, reads and writes, queue 32, 6 s each
    queue depth   4 KiB random reads at queue 1 2 4 8 16 32 64, one thread, 6 s each
    file trees    100,000 x 4 KiB, 300,000 empty files, and 256 x 16 MiB: create, then cold: find, find -name
                  (a filename search), ls -lR, du, stat and sort by size and by name, grep -r (a linear search
                  through every byte), a copy of the big-file tree, and delete

Results: results/runs/STAMP/LAYOUT.json and run.json (the machine, its disks' SMART before and after).
"""
import glob
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(BASE, "results")
MNT = "/mnt/bench"
STAMP = time.strftime("%Y%m%d-%H%M%S")
RUN = os.path.join(RES, "runs", STAMP)
ALPINE = os.path.exists("/etc/alpine-release")
NEED = {"fio": "fio", "lsblk": "util-linux", "wipefs": "util-linux", "blkdiscard": "util-linux", "smartctl": "smartmontools",
        "mdadm": "mdadm", "mkfs.ext4": "e2fsprogs", "mkfs.xfs": "xfsprogs", "mkfs.btrfs": "btrfs-progs"}
ZFS_PKG = "zfs" if ALPINE else "zfsutils-linux"


# ---- plumbing -------------------------------------------------------------------------------------

def sh(cmd, check=True):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError("%s\n%s%s" % (cmd, r.stdout[-2000:], r.stderr[-2000:]))
    return r.stdout


def log(*a):
    line = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    os.makedirs(RES, exist_ok=True)
    with open(os.path.join(RES, "LOG"), "a") as f:
        f.write(line + "\n")


# progress.json beside the results: what a run is doing now, for Orrery's Bench screen (and anyone's tail).
# Rewritten whole at each step, through a temporary file, so a reader never sees half of it.
PROGRESS = {}


def progress(**kw):
    PROGRESS.update(kw)
    PROGRESS["updated"] = time.time()
    done = PROGRESS.get("done", [])
    plan = PROGRESS.get("plan", [])
    if done and plan:
        each = (time.time() - PROGRESS["started"]) / len(done)
        PROGRESS["eta"] = time.time() + each * (len(plan) - len(done))
    elif plan:
        PROGRESS["eta"] = time.time() + (9 if PROGRESS.get("kind") == "barrage" else 4) * 60 * len(plan)
    os.makedirs(RES, exist_ok=True)
    tmp = os.path.join(RES, ".progress.json")
    with open(tmp, "w") as f:
        json.dump(PROGRESS, f)
    os.replace(tmp, os.path.join(RES, "progress.json"))


def save(name, obj):
    os.makedirs(RUN, exist_ok=True)
    with open(os.path.join(RUN, name + ".json"), "w") as f:
        json.dump(obj, f, indent=1)


def tools_or_exit():
    missing = sorted({pkg for t, pkg in NEED.items() if not shutil.which(t)})
    if missing:
        sys.exit("missing tools: %s %s" % ("apk add" if ALPINE else "apt install -y", " ".join(missing)))


# ---- the disks: by serial only --------------------------------------------------------------------

def serials():
    p = os.path.join(BASE, "disks.txt")
    if not os.path.exists(p):
        sys.exit("no disks.txt beside the script: write the serials of the disks it may erase, one a line "
                 "(`sudo python3 %s candidates` lists the likely ones)" % sys.argv[0])
    return [l.split("#")[0].strip() for l in open(p) if l.split("#")[0].strip()]


def blockdevs():
    return json.loads(sh("lsblk -J -b -o NAME,SERIAL,TYPE,TRAN,SIZE,MODEL,FSTYPE,LABEL,MOUNTPOINTS"))["blockdevices"]


def system_disks():
    """The disks holding anything mounted, or swap: never ours."""
    keep = set()
    devs = blockdevs()
    for d in devs:
        stack = [d]
        while stack:
            p = stack.pop()
            if [m for m in (p.get("mountpoints") or []) if m]:
                keep.add(d["name"])
            stack.extend(p.get("children", []))
    for line in open("/proc/swaps").read().splitlines()[1:]:
        dev = line.split()[0]
        for d in devs:
            if dev.startswith("/dev/" + d["name"]):
                keep.add(d["name"])
    return keep


def disks():
    want = serials()
    found = {d.get("serial"): d for d in blockdevs() if d.get("serial") in want}
    missing = [s for s in want if s not in found]
    if missing:
        sys.exit("refusing: disks with serial %s not found" % ", ".join(missing))
    sysd = system_disks()
    sizes = set()
    for s in want:
        d = found[s]
        if d["type"] != "disk":
            sys.exit("refusing: %s (%s) is not a whole disk" % (d["name"], s))
        if d["name"] in sysd:
            sys.exit("refusing: /dev/%s (%s) is mounted, holds the system or swap" % (d["name"], s))
        sizes.add(d["size"])
    if len(sizes) != 1:
        sys.exit("refusing: the disks are not all the same size")
    return ["/dev/" + found[s]["name"] for s in want]


def candidates(as_json=False):
    sysd = system_disks()
    if as_json:
        rows = []
        for d in blockdevs():
            if d["type"] == "disk" and d["name"] not in sysd and int(d["size"]) > 1e9:
                fs = sorted({x for x in [d.get("fstype")] + [c.get("fstype") for c in d.get("children", [])] if x})
                rows.append({"serial": d.get("serial"), "dev": d["name"], "GB": round(int(d["size"]) / 1e9), "tran": d.get("tran"),
                             "model": (d.get("model") or "").strip(), "holds": fs})
        print(json.dumps({"host": socket.gethostname(), "spare": rows, "chosen": serials() if os.path.exists(os.path.join(BASE, "disks.txt")) else []}))
        return
    print("disks that look spare (not mounted, not the system's, not swap); put the ones to bench in disks.txt:")
    for d in blockdevs():
        if d["type"] == "disk" and d["name"] not in sysd and int(d["size"]) > 1e9:
            fs = ",".join(sorted({x for x in [d.get("fstype")] + [c.get("fstype") for c in d.get("children", [])] if x}))
            print("  %-16s %-8s %6.0f GB  %-4s %-22s holds: %s" % (d.get("serial"), d["name"], int(d["size"]) / 1e9,
                  d.get("tran") or "", (d.get("model") or "").strip(), fs or "nothing a filesystem tool recognises"))


# ---- layouts, for N disks -------------------------------------------------------------------------

def layouts(n):
    L = {"single": ("ext4", 1)}
    if n >= 2:
        L.update({"pair-zfs": ("zfs-pair", 2), "pair-btrfs": ("btrfs-pair", 2), "pair-md": ("md1", 2)})
    if n >= 3:
        L.update({"md10": ("md10-xfs", n), "md10-ext4": ("md10-ext4", n), "md0": ("md0-xfs", n), "btrfs10": ("btrfs10", n)})
    if n >= 4 and n % 2 == 0:
        L["zfs-%dx2" % (n // 2)] = ("zfs-mirrors", 2)
    if n >= 6 and n % 3 == 0:
        L["zfs-%dx3" % (n // 3)] = ("zfs-mirrors", 3)
    if n >= 6 and (n - 2) % 2 == 0:
        L["md10-%d+2spare" % (n - 2)] = ("md10-spares", n - 2)
        L["zfs-%dx2+spare+l2arc" % ((n - 2) // 2)] = ("zfs-spare-cache", n - 2)
        L["zfs-%dx2+slog+l2arc" % ((n - 2) // 2)] = ("zfs-log-cache", n - 2)
    return L


def teardown(ds):
    sh("umount %s" % MNT, check=False)
    if shutil.which("zpool"):
        sh("zpool destroy -f bench", check=False)
    for md in glob.glob("/dev/md/bench*") + glob.glob("/dev/md12[0-9]"):
        sh("mdadm --stop %s" % md, check=False)
    for d in ds:
        sh("mdadm --zero-superblock %s" % d, check=False)
        sh("wipefs -a -q %s" % d, check=False)


def settle():
    sh("udevadm settle", check=False)


SETTLE = 30   # seconds of quiet after the disks are discarded: --settle N


def fresh(devs):
    for d in devs:
        sh("wipefs -a -q %s" % d, check=False)
        sh("blkdiscard -f %s" % d, check=False)
    settle()
    # Cheap flash keeps working after a layout is torn down: it moves what was written into its slow cells
    # and reclaims the discarded ones. Measured straight away, the next layout's writes share the disks with
    # that (7 November: RAID10 of four, xfs, wrote 624 MB/s and RAID10 of six, xfs, 219). A pause lets it end.
    if SETTLE:
        time.sleep(SETTLE)


BITMAP = ""   # "", "none" or a chunk: set by a layout's @nobitmap or @bigbitmap
# Tuning of an mdadm layout, from its @options joined by "+" (Paul, 7 November: "test different block sizes,
# and different format options within the md10-ext"):
#   chunk=64k|128k|256k|512k|1m   the stripe unit (512k by default)
#   layout=n2|f2|o2               RAID10's copies: near (default), far (reads like RAID0, writes seek), offset
#   journal=off                   ext4 without a journal: the fastest metadata, no crash safety
#   writeback                     ext4 data=writeback: metadata journalled, data not ordered before it
#   commit=N                      ext4 commits every N seconds (5 by default)
#   inode=N                       ext4 bytes per inode (16384 by default): more inodes for many small files
MDOPT = {}


def md(level, devs, spares=()):
    extra = " --chunk=%s" % MDOPT.get("chunk", "512K").upper() if level in ("0", "10") else ""
    # mdadm gives an array over 100 GB an internal write-intent bitmap. @nobitmap drops it (a crash then costs
    # a full resync); @bigbitmap keeps it with 128 MiB chunks. The second run (7 November) found it costs
    # nothing measurable here: the first run's slow writes were the drives' own background work.
    if BITMAP == "none":
        extra += " --bitmap=none"
    elif BITMAP:
        extra += " --bitmap=internal --bitmap-chunk=%s" % BITMAP
    extra += " --layout=%s" % MDOPT.get("layout", "n2") if level == "10" else ""
    sp = " --spare-devices=%d" % len(spares) if spares else ""
    sh("mdadm --create /dev/md/bench --run --assume-clean --metadata=1.2 --level=%s --raid-devices=%d%s%s %s %s"
       % (level, len(devs), sp, extra, " ".join(devs), " ".join(spares)))
    settle()
    return "/dev/md/bench"


def mkfs(kind, dev):
    mopts = "noatime"
    if kind == "ext4":
        extra = ""
        if MDOPT.get("journal") == "off":
            extra += " -O ^has_journal"
        if MDOPT.get("inode"):
            extra += " -i %s" % MDOPT["inode"]
        sh("mkfs.ext4 -F -q -E lazy_itable_init=0,lazy_journal_init=0%s %s" % (extra, dev))
        if "writeback" in MDOPT:
            mopts += ",data=writeback"
        if MDOPT.get("commit"):
            mopts += ",commit=%s" % MDOPT["commit"]
    else:
        sh("mkfs.xfs -f -q %s" % dev)
    os.makedirs(MNT, exist_ok=True)
    sh("mount -o %s %s %s" % (mopts, dev, MNT))


def zfs(vdevs, extra=""):
    if not shutil.which("zpool"):
        raise RuntimeError("zpool is not installed: %s %s" % ("apk add" if ALPINE else "apt install -y", ZFS_PKG))
    sh("zpool create -f -o ashift=12 -O compression=off -O atime=off -O primarycache=metadata -m %s bench %s %s"
       % (MNT, " ".join("mirror " + " ".join(v) for v in vdevs), extra))


def btrfs(profile, devs):
    sh("mkfs.btrfs -f -q -L bench -d %s -m %s %s" % (profile, profile, " ".join(devs)))
    os.makedirs(MNT, exist_ok=True)
    sh("mount -o noatime,ssd,discard=async %s %s" % (devs[0], MNT))


def build(name, ds):
    # "zfs-3x2@16k": a ZFS layout with that record size. ZFS reads and checksums whole records, 128K by default,
    # so a 4K random read costs a 128K one: the record size is the block size a ZFS layout really has.
    global BITMAP, MDOPT
    name, _, rs = name.partition("@")
    kind, k = layouts(len(ds))[name]
    BITMAP, MDOPT = "", {}
    if kind.startswith("md"):
        for tok in (t for t in rs.split("+") if t):
            if tok in ("nobitmap", "bigbitmap"):
                BITMAP = {"nobitmap": "none", "bigbitmap": "128M"}[tok]
            else:
                key, _, val = tok.partition("=")
                MDOPT[key] = val
        rs = ""
    if kind == "ext4":
        used = ds[:1]
        fresh(used)
        mkfs("ext4", used[0])
    elif kind == "zfs-pair":
        used = ds[0:2]
        fresh(used)
        zfs([used])
    elif kind == "btrfs-pair":
        used = ds[2:4] if len(ds) >= 4 else ds[0:2]
        fresh(used)
        btrfs("raid1", used)
    elif kind == "md1":
        used = ds[4:6] if len(ds) >= 6 else ds[0:2]
        fresh(used)
        mkfs("ext4", md("1", used))
    elif kind in ("md10-xfs", "md10-ext4", "md0-xfs"):
        used = ds
        fresh(used)
        mkfs("ext4" if kind.endswith("ext4") else "xfs", md("0" if kind.startswith("md0") else "10", used))
    elif kind == "btrfs10":
        used = ds
        fresh(used)
        btrfs("raid10", used)
    elif kind == "zfs-mirrors":
        used = ds
        fresh(used)
        zfs([ds[i:i + k] for i in range(0, len(ds), k)])
    elif kind == "md10-spares":
        used = ds
        fresh(used)
        mkfs("xfs", md("10", ds[:k], spares=ds[k:]))
    elif kind in ("zfs-spare-cache", "zfs-log-cache"):
        used = ds
        fresh(used)
        first = "spare" if kind == "zfs-spare-cache" else "log"
        zfs([ds[i:i + 2] for i in range(0, k, 2)], "%s %s cache %s" % (first, ds[k], ds[k + 1]))
    else:
        raise RuntimeError("no layout " + name)
    if rs:
        if not kind.startswith("zfs"):
            raise RuntimeError("@record size is for ZFS layouts")
        sh("zfs set recordsize=%s bench" % rs)
    return used


# ---- the screen: bars and comparisons --------------------------------------------------------------

SPARK = "▁▂▃▄▅▆▇█"
BASELINE = {}   # the single disk's numbers in this run, for "x one disk"
BEST = {}       # the best so far in this run, for the bars


def bar(v, top, width=28):
    n = 0 if not top else max(1, int(round(width * v / top)))
    return "█" * n + "·" * (width - n)


def spark(vals):
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    return "".join(SPARK[int((v - lo) / (hi - lo + 1e-9) * 7)] for v in vals)


# Each measure, how to read it, and a comparison a person can feel. Higher is better.
MEASURES = [
    ("seq-write", "write", "MBps", "MB/s", lambda v: "a 25 GB Blu-ray image in %.0f s" % (25000 / v)),
    ("seq-read", "read", "MBps", "MB/s", lambda v: "feeds %.0f burners at 12x, 54 MB/s each" % (v / 54)),
    ("butterfly", "write", "MBps", "MB/s", lambda v: "two streams, %.0f MB/s each" % (v / 2)),
    ("write-read", "read", "MBps", "MB/s", lambda v: "the read-back, checked"),
    ("rand-read", "read", "iops", "IOPS", lambda v: "%.0f spinning disks' worth, at 150 each" % (v / 150)),
    ("rand-write", "write", "iops", "IOPS", lambda v: "small writes a second"),
    ("mixed", "read", "iops", "IOPS", lambda v: "reads, while 30% writes go on"),
    ("sync-write", "write", "iops", "IOPS", lambda v: "%.1f ms an fsync" % (1000 / v if v else 0)),
]
META = [
    ("create_s", "create 100k", lambda v: "%.0f files a second" % (100000 / v if v else 0)),
    ("find_s", "find", lambda v: "a blink is 0.1 s"),
    ("ls_lR_s", "ls -lR", lambda v: "%.0f files listed a second" % (100000 / v if v else 0)),
    ("stat_sort_s", "stat+sort", lambda v: "every size read, then sorted"),
    ("delete_s", "delete", lambda v: "%.0f files a second" % (100000 / v if v else 0)),
]


def show(name, s):
    for key, side, field, unit, say in MEASURES:
        v = s.get(key, {}).get(side, {}).get(field)
        if not v:
            continue
        BEST[key] = max(BEST.get(key, 0), v)
        base = BASELINE.get(key)
        log("  %-11s %s %8.0f %-4s%s  %s" % (key, bar(v, BEST[key]), v, unit,
            "  x%.2f one disk" % (v / base) if base else "", say(v)))
    m = s.get("metadata", {})
    for key, label, say in META:
        v = m.get(key)
        if not v:
            continue
        BEST[key] = min(BEST.get(key, 1e9), v)
        base = BASELINE.get(key)
        log("  %-11s %s %8.2f s   %s  %s" % (label, bar(BEST[key], v), v, "x%.2f one disk" % (base / v) if base else "", say(v)))
    if name == "single":
        for key, side, field, *_ in MEASURES:
            if s.get(key, {}).get(side, {}).get(field):
                BASELINE[key] = s[key][side][field]
        for key, *_ in META:
            if m.get(key):
                BASELINE[key] = m[key]


def leaders():
    rows = {}
    for p in glob.glob(os.path.join(RUN, "*.json")):
        j = json.load(open(p))
        if "suite" in j:
            rows[j["layout"]] = j["suite"]
    if len(rows) >= 2:
        log("  leading so far: " + "; ".join("%s %s" % (key, max(rows, key=lambda n: rows[n].get(key, {}).get(side, {}).get(field, 0)))
                                             for key, side, field, *_ in MEASURES))


# ---- the measures ---------------------------------------------------------------------------------

FIO = "--ioengine=libaio --direct=1 --refill_buffers --randrepeat=0 --group_reporting --output-format=json"


def fio(target, name, args, secs=20, ramp=3):
    if PROGRESS:
        progress(step=name)
    timed_ = "--time_based --runtime=%d --ramp_time=%d" % (secs, ramp) if secs else ""
    return parse(sh("fio --name=%s --filename=%s %s %s %s" % (name, target, FIO, timed_, args)))


def parse(out):
    j = json.loads(out[out.index("{"):])["jobs"][0]
    r = {}
    for k in ("read", "write"):
        if j[k]["io_bytes"]:
            c = j[k].get("clat_ns", {})
            r[k] = {"MBps": round(j[k]["bw_bytes"] / 1e6, 1), "iops": round(j[k]["iops"]), "mean_us": round(c.get("mean", 0) / 1000, 1),
                    "p99_us": round(c.get("percentile", {}).get("99.000000", 0) / 1000, 1), "max_us": round(c.get("max", 0) / 1000, 1)}
    r["secs"] = round(j.get("job_runtime", 0) / 1000, 1)
    return r


def dropcaches(zpool):
    os.sync()
    if zpool:
        sh("zpool export bench && zpool import -d %s bench" % ("/dev/disk/by-id" if os.path.isdir("/dev/disk/by-id") else "/dev"))
    with open("/proc/sys/vm/drop_caches", "w") as f:
        f.write("3\n")


def timed(fn):
    t = time.time()
    fn()
    return round(time.time() - t, 2)


def tree(root, dirs, per, size):
    blob = os.urandom(size) if size else b""
    for i in range(dirs):
        d = os.path.join(root, "d%05d" % i)
        os.makedirs(d)
        for k in range(per):
            with open(os.path.join(d, "f%05d.dat" % k), "wb") as f:
                if size:
                    f.write(blob)
    os.sync()


def walk_sort(root, by):
    rows = []
    for dp, dn, fn in os.walk(root):
        for x in fn:
            p = os.path.join(dp, x)
            rows.append((os.lstat(p).st_size, p) if by == "size" else (p, 0))
    rows.sort()
    return len(rows)


def metadata(zpool):
    progress(step="file tree")
    root = os.path.join(MNT, "tree")
    r = {"create_s": timed(lambda: tree(root, 1000, 100, 4096))}
    dropcaches(zpool)
    r["find_s"] = timed(lambda: sh("find %s -type f | wc -l" % root))
    dropcaches(zpool)
    r["ls_lR_s"] = timed(lambda: sh("ls -lR %s > /dev/null" % root))
    dropcaches(zpool)
    r["stat_sort_s"] = timed(lambda: walk_sort(root, "size"))
    r["delete_s"] = timed(lambda: (shutil.rmtree(root), os.sync()))
    return r


def suite(zpool):
    f = os.path.join(MNT, "fio.dat")
    r = {"seq-write": fio(f, "seqw", "--rw=write --bs=1M --iodepth=32 --size=8G"),
         "seq-read": fio(f, "seqr", "--rw=read --bs=1M --iodepth=32 --size=8G")}
    r["butterfly"] = parse(sh("fio %s --time_based --runtime=20 --ramp_time=3 --filename=%s --size=4G --rw=write --bs=1M "
                              "--iodepth=16 --name=front --offset=0 --name=back --offset=4G" % (FIO, f)))
    r["write-read"] = fio(os.path.join(MNT, "verify.dat"), "wr", "--rw=write --bs=1M --iodepth=16 --size=2G --verify=crc32c --do_verify=1", secs=0)
    r["rand-read"] = fio(f, "rr", "--rw=randread --bs=4k --iodepth=16 --numjobs=8 --size=8G")
    r["rand-write"] = fio(f, "rw", "--rw=randwrite --bs=4k --iodepth=32 --numjobs=4 --size=8G")
    r["mixed"] = fio(f, "mx", "--rw=randrw --rwmixread=70 --bs=4k --iodepth=16 --numjobs=4 --size=8G")
    r["sync-write"] = fio(os.path.join(MNT, "sync.dat"), "sw", "--rw=write --bs=4k --iodepth=1 --numjobs=1 --fsync=1 --size=1G", secs=15)
    for x in glob.glob(os.path.join(MNT, "*.dat")):
        os.remove(x)
    r["metadata"] = metadata(zpool)
    return r


# ---- the barrage ----------------------------------------------------------------------------------

SIZES = ["4k", "16k", "64k", "256k", "1M"]
DEPTHS = [1, 2, 4, 8, 16, 32, 64]


def cliff_of(per):
    """The GB written before the fast write cache ran out: the first second, after the speed's peak, from
    which it stays under 60% of the early speed for three seconds running. The first second is fio
    ramping up, not the cache: a plain "first second under 60%" read the ramp as the cliff (7 November)."""
    if len(per) < 5:
        return None
    head = sorted(per[1:11])[len(per[1:11]) // 2]
    total, peaked = 0.0, False
    for i, v in enumerate(per):
        if v >= head * 0.9:
            peaked = True
        if peaked and i + 3 <= len(per) and all(x < head * 0.6 for x in per[i:i + 3]):
            return round(total, 1)
        total += v / 1000
    return None

def cache_cliff(target, secs=75):
    """1 MiB sequential writes for secs, the speed each second: where the fast write cache ends."""
    progress(step="cache cliff")
    os.makedirs(RUN, exist_ok=True)
    logp = os.path.join(RUN, "cliff")
    sh("fio --name=cliff --filename=%s %s --rw=write --bs=1M --iodepth=32 --time_based --runtime=%d --write_bw_log=%s "
       "--log_avg_msec=1000 %s" % (target, FIO, secs, logp, "" if target.startswith("/dev/") else "--size=60G"))
    per = []
    for p in sorted(glob.glob(logp + "_bw*.log")):
        for line in open(p):
            f = [x.strip() for x in line.split(",")]
            if len(f) >= 2 and f[1].isdigit():
                per.append(round(int(f[1]) * 1024 / 1e6, 1))
        os.remove(p)
    cliff = cliff_of(per)
    res = {"MBps_each_second": per, "cliff_GB": cliff, "start_MBps": per[0] if per else None,
           "after_MBps": round(sum(per[-15:]) / max(1, len(per[-15:])), 1) if per else None}
    log("  cache cliff %s" % spark(per))
    log("  starts at %s MB/s, under 60%% of that after %s GB, then %s MB/s" % (res["start_MBps"], cliff, res["after_MBps"]))
    return res


def sweeps(target, size_arg):
    r = {"block": {}, "depth": {}}
    for bs in SIZES:
        row = {}
        for rw in ("write", "read", "randwrite", "randread"):
            res = fio(target, "b", "--rw=%s --bs=%s --iodepth=32 %s" % (rw, bs, size_arg), secs=6, ramp=1)
            side = "write" if "write" in rw else "read"
            row[rw] = {k: res[side][k] for k in ("MBps", "iops", "p99_us", "max_us")}
        r["block"][bs] = row
        log("  block %-4s seqW %5.0f  seqR %5.0f  randW %5.0f  randR %5.0f MB/s" % (
            bs, row["write"]["MBps"], row["read"]["MBps"], row["randwrite"]["MBps"], row["randread"]["MBps"]))
    for q in DEPTHS:
        res = fio(target, "q", "--rw=randread --bs=4k --iodepth=%d %s" % (q, size_arg), secs=6, ramp=1)
        r["depth"][str(q)] = {k: res["read"][k] for k in ("iops", "mean_us", "p99_us")}
    iops = [r["depth"][str(q)]["iops"] for q in DEPTHS]
    log("  queue 1..64, 4K reads %s  %s IOPS" % (spark(iops), " ".join(str(x) for x in iops)))
    return r


def trees(zpool):
    progress(step="file trees")
    root = os.path.join(MNT, "trees")
    out = {}
    for label, dirs, per, size in (("100k x 4K", 1000, 100, 4096), ("300k empty", 3000, 100, 0), ("256 x 16M", 16, 16, 16 << 20)):
        t = os.path.join(root, label.replace(" ", ""))
        r = {"create_s": timed(lambda: tree(t, dirs, per, size))}
        for key, cmd in (("find_s", "find %s -type f | wc -l"), ("find_name_s", "find %s -name '*77*' | wc -l"),
                         ("ls_lR_s", "ls -lR %s > /dev/null"), ("du_s", "du -s %s")):
            dropcaches(zpool)
            r[key] = timed(lambda: sh(cmd % t))
        dropcaches(zpool)
        r["sort_size_s"] = timed(lambda: walk_sort(t, "size"))
        dropcaches(zpool)
        r["sort_name_s"] = timed(lambda: walk_sort(t, "name"))
        if size:
            dropcaches(zpool)
            r["grep_s"] = timed(lambda: sh("grep -r -c needle-that-is-not-there %s > /dev/null" % t, check=False))
        if size >= 1 << 20:
            dropcaches(zpool)
            r["copy_s"] = timed(lambda: (sh("cp -r %s %s.copy" % (t, t)), os.sync()))
            shutil.rmtree(t + ".copy")
        r["delete_s"] = timed(lambda: (shutil.rmtree(t), os.sync()))
        out[label] = r
        log("  tree %-10s create %6.2f  find %5.2f  -name %5.2f  ls -lR %5.2f  du %5.2f  sort %5.2f%s%s s" % (
            label, r["create_s"], r["find_s"], r["find_name_s"], r["ls_lR_s"], r["du_s"], r["sort_size_s"],
            "  grep -r %.2f" % r["grep_s"] if "grep_s" in r else "", "  copy %.2f" % r["copy_s"] if "copy_s" in r else ""))
    shutil.rmtree(root, ignore_errors=True)
    return out


ONLY = ("cliff", "sweeps", "trees")   # --only sweeps (or a comma list): the barrage's parts to run


def fill(target, size="8G"):
    """Write the sweep's region whole before reading it. A file written only for a timed test is mostly holes,
    and a filesystem answers a read of a hole with zeros and no disk at all: the first barrage (7 November)
    read RAID10 at 5.2 GB/s, past six SATA links and the chipset's. On a bare disk it replaces discarded flash,
    which a controller also answers without reading anything."""
    progress(step="filling %s" % size)
    fio(target, "fill", "--rw=write --bs=1M --iodepth=32 --size=%s" % size, secs=0)


def barrage(name, ds):
    if name == "raw":
        d = ds[0]
        fresh([d])
        log("  one bare disk, %s, no filesystem" % d)
        res = {"layout": "raw", "disks": [d]}
        if "cliff" in ONLY:
            res["cliff"] = cache_cliff(d)
            fresh([d])
        if "sweeps" in ONLY:
            fill(d)
            res["sweeps"] = sweeps(d, "--size=8G")
        return res
    used = build(name, ds)
    zp = name.startswith("zfs") or name.startswith("pair-zfs")
    f = os.path.join(MNT, "fio.dat")
    res = {"layout": name, "disks": used}
    if "cliff" in ONLY:
        res["cliff"] = cache_cliff(f)
        os.remove(f)
    if "sweeps" in ONLY:
        fill(f)
        res["sweeps"] = sweeps(f, "--size=8G")
        res["sweeps"]["filled"] = True
        os.remove(f)
    if "trees" in ONLY:
        res["trees"] = trees(zp)
    return res


# ---- runs -----------------------------------------------------------------------------------------

WATCH = {"170": "bad blocks late/early", "218": "CRC errors", "192": "unsafe shutdowns", "241": "GiB written", "231": "life left %"}


def health(ds, when):
    out = {}
    for i, d in enumerate(ds, 1):
        vals = {}
        for line in sh("smartctl -A %s" % d, check=False).splitlines():
            f = line.split()
            if f and f[0] in WATCH:
                vals[WATCH[f[0]]] = " ".join(f[9:])
        out[d] = vals
        log("health %s disk%d %s: %s" % (when, i, d, "; ".join("%s %s" % kv for kv in vals.items())))
    return out


def machine(ds):
    model = next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")), "")
    mem = int(open("/proc/meminfo").read().split()[1]) // 1024 // 1024
    return {"host": socket.gethostname(), "kernel": platform.release(), "cpu": model, "cores": os.cpu_count(), "mem_GiB": mem,
            "os": "alpine" if ALPINE else "ubuntu/debian", "disks": ds, "serials": serials(), "stamp": STAMP,
            "zfs": sh("zfs version 2>/dev/null | tr '\\n' ' '", check=False).strip()}


def raw_each(ds):
    r, top = {}, 0
    for i, d in enumerate(ds, 1):
        fresh([d])
        row = {"dev": d, "seq-write": fio(d, "w", "--rw=write --bs=1M --iodepth=32", secs=10),
               "seq-read": fio(d, "r", "--rw=read --bs=1M --iodepth=32", secs=10),
               "rand-read": fio(d, "rr", "--rw=randread --bs=4k --iodepth=32 --numjobs=4", secs=10)}
        r["disk%d" % i] = row
        top = max(top, row["seq-write"]["write"]["MBps"])
        log("raw disk%d %s: write %s MB/s, read %s MB/s, 4K read %s IOPS  %s" % (i, d, row["seq-write"]["write"]["MBps"],
            row["seq-read"]["read"]["MBps"], row["rand-read"]["read"]["iops"], bar(row["seq-write"]["write"]["MBps"], top, 20)))
    return r


EXPORTS = "/etc/exports.d/disk-bench.exports"


def ours():
    """What a cancelled run of this bench can leave: its NFS export, its mount, its pool, its array, all named
    bench. Taken apart before the disks are checked, so a stop never blocks the next run; nothing else is touched."""
    if os.path.exists(EXPORTS):
        os.remove(EXPORTS)
        sh("exportfs -ra", check=False)
    for m in (MNT, "/mnt/bench-inspect"):
        sh("umount %s" % m, check=False)
    if shutil.which("zpool"):
        sh("zpool destroy -f bench", check=False)
    for md in glob.glob("/dev/md/bench*"):
        sh("mdadm --stop %s" % md, check=False)


def run(names, kind, repeat=1):
    tools_or_exit()
    # A stop (systemctl stop, or Ctrl-C) ends the run through its finally: the layout is taken apart.
    import signal
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    ours()
    ds = disks()
    meta = machine(ds)
    log("=== %s %s on %s: %d disks %s" % (kind, STAMP, meta["host"], len(ds), " ".join(ds)))
    meta["health_before"] = health(ds, "before")
    save("run", meta)
    teardown(ds)
    names = [n if repeat == 1 else "%s#%d" % (n, k) for k in range(1, repeat + 1) for n in names]
    progress(state="running", kind=kind, stamp=STAMP, host=meta["host"], disks=len(ds), plan=names, done=[], failed=[],
             started=time.time(), current=None, step=None)
    for tagged in names:
        name = tagged.partition("#")[0]
        log("=== %s" % tagged)
        progress(current=tagged, step="build", layout_started=time.time())
        t0 = time.time()
        try:
            if kind == "barrage":
                res, fname = barrage(name, ds), "barrage-" + tagged
            elif name == "raw-each":
                res, fname = {"layout": name, "raw": raw_each(ds)}, tagged
            else:
                used = build(name, ds)
                log("built on", " ".join(used))
                res = {"layout": name, "trial": tagged, "disks": used, "suite": suite(name.startswith("zfs") or name.startswith("pair-zfs"))}
                show(name, res["suite"])
                fname = tagged
            res["settle_s"] = SETTLE
            res["minutes"] = round((time.time() - t0) / 60, 1)
            save(fname, res)
            log("%s done in %.1f min" % (tagged, res["minutes"]))
            progress(done=PROGRESS["done"] + [tagged], last=fname)
            if kind == "run":
                leaders()
        except KeyboardInterrupt:
            log("%s STOPPED by a person; taking it apart" % tagged)
            teardown(ds)
            progress(state="stopped", current=None, step=None)
            log("stopped; the disks are blank")
            sys.exit(1)
        except Exception as e:
            log("%s FAILED: %s" % (tagged, str(e)[:600]))
            progress(done=PROGRESS["done"] + [tagged], failed=PROGRESS["failed"] + [tagged])
        finally:
            teardown(ds)
    meta["health_after"] = health(ds, "after")
    save("run", meta)
    progress(state="done", current=None, step=None, eta=time.time())
    log("all done; the disks are blank. Then: python3 %s report" % os.path.join(BASE, "disk-bench.py"))


# ---- report (no root) -----------------------------------------------------------------------------

def report():
    sets = sorted(glob.glob(os.path.join(RES, "runs", "*"))) + ([RES] if glob.glob(os.path.join(RES, "*.json")) else [])
    for r in sets:
        rows = {}
        for p in glob.glob(os.path.join(r, "*.json")):
            j = json.load(open(p))
            if "suite" in j:
                rows[j["layout"]] = j["suite"]
        if not rows:
            continue
        print("\n== %s" % ("first version, results/" if r == RES else os.path.basename(r)))
        for key, side, field, unit, _ in MEASURES:
            vals = {n: s.get(key, {}).get(side, {}).get(field) for n, s in rows.items()}
            vals = {n: v for n, v in vals.items() if v}
            if vals:
                top = max(vals.values())
                print("%s (%s)" % (key, unit))
                for n, v in sorted(vals.items(), key=lambda kv: -kv[1]):
                    print("  %-26s %s %8.0f%s" % (n, bar(v, top), v, "  <- best" if v == top else ""))


def inspect():
    ds = disks()
    out = []
    for i, d in enumerate(ds, 1):
        out.append("=== disk %d: %s" % (i, d))
        out.append(sh("smartctl -H -i -A %s" % d, check=False))
    os.makedirs("/mnt/bench-inspect", exist_ok=True)
    for d in ds:
        fs = sh("lsblk -n -o FSTYPE %s" % d, check=False).split()
        if fs and subprocess.run("mount -o ro %s /mnt/bench-inspect" % d, shell=True, capture_output=True).returncode == 0:
            try:
                out.append("=== %s (%s), mounted read-only" % (d, fs[0]))
                out.append(sh("df -h /mnt/bench-inspect; ls -la /mnt/bench-inspect", check=False))
                out.append("files: " + sh("find /mnt/bench-inspect -xdev -type f | wc -l", check=False))
            finally:
                sh("umount /mnt/bench-inspect", check=False)
    os.makedirs(RES, exist_ok=True)
    with open(os.path.join(RES, "inspect.txt"), "w") as f:
        f.write("\n".join(out))
    print("\n".join(out))


def serve(name, mode):
    """Build a layout and share it over NFS, to measure it from another machine (tools/nfs-client-bench.py).
    It stays until `unserve`. sync (the default) answers a write only once it is on the disks; async answers
    at once, faster, and a server crash can lose what it had not written."""
    tools_or_exit()
    if not shutil.which("exportfs"):
        sys.exit("the NFS server is not installed: %s nfs-kernel-server" % ("apk add nfs-utils; rc-service nfs start" if ALPINE else "apt install -y"))
    ours()
    ds = disks()
    used = build(name, ds)
    os.chmod(MNT, 0o1777)
    export(mode, name)
    log("serving %s over NFS (%s) from %s:%s on %s; stop with: sudo python3 %s unserve" % (name, mode, socket.gethostname(), MNT, " ".join(used), os.path.join(BASE, "disk-bench.py")))


def export(mode, name=None):
    """Share MNT on the home network, sync or async; run again with the other word to switch, the data kept.
    insecure lets a client mount from an ordinary port (the Mac's mount_nfs does without resvport); the share
    is the bench's blank disks, for the home subnet only."""
    if not os.path.ismount(MNT):
        sys.exit("nothing to share: %s is not mounted (serve builds it)" % MNT)
    os.makedirs(os.path.dirname(EXPORTS), exist_ok=True)
    with open(EXPORTS, "w") as f:
        f.write("%s 192.168.8.0/24(rw,%s,insecure,no_subtree_check,no_root_squash,fsid=77)\n" % (MNT, mode))
    if not ALPINE:
        sh("systemctl start nfs-server", check=False)
    sh("exportfs -ra")
    if name is None:
        try:
            name = (json.load(open(os.path.join(RES, "progress.json"))).get("current") or "").split(" (")[0] or "?"
        except (OSError, ValueError):
            name = "?"
    progress(state="serving", kind="serve", current="%s (NFS, %s)" % (name, mode), step=None, plan=[], done=[], failed=[], started=time.time())
    log("NFS export of %s is %s" % (MNT, mode))


def unserve():
    ours()
    ds = disks()
    teardown(ds)
    progress(state="done", kind="serve", current=None, step=None, plan=[], done=[], failed=[], started=time.time())
    log("NFS share stopped; the disks are blank")


def main(a):
    if not a:
        sys.exit(__doc__)
    cmd = a[0]
    if cmd == "report":
        return report()
    if cmd == "layouts":
        n = len(serials())
        print("%d disks:" % n)
        for k, v in layouts(n).items():
            print("  %-26s %s" % (k, v[0]))
        return
    if cmd == "candidates":
        # Reading lsblk needs no root: Orrery's probe asks this, as the user, to list a machine's spare disks.
        return candidates("--json" in a)
    if os.geteuid() != 0:
        sys.exit("run it as root: sudo python3 %s %s" % (sys.argv[0], " ".join(a)))
    if cmd == "inspect":
        return inspect()
    if cmd == "serve" and len(a) >= 2:
        if "--erase" not in a:
            sys.exit("refusing: serve builds the layout, erasing the disks in disks.txt. Add --erase")
        name = [x for x in a[1:] if not x.startswith("--")][0]
        return serve(name, "async" if "--async" in a else "sync")
    if cmd == "unserve":
        return unserve()
    if cmd == "export" and len(a) == 2 and a[1] in ("sync", "async"):
        return export(a[1])
    if cmd in ("run", "barrage"):
        global SETTLE
        repeat = 1
        global ONLY
        for flag in ("--repeat", "--settle", "--only"):
            if flag in a:
                i = a.index(flag)
                if flag == "--only":
                    ONLY = tuple(x for x in a[i + 1].split(",") if x in ("cliff", "sweeps", "trees"))
                else:
                    v = int(a[i + 1])
                    if flag == "--repeat":
                        repeat = max(1, v)
                    else:
                        SETTLE = max(0, v)
                del a[i:i + 2]
        if "--erase" not in a:
            sys.exit("refusing: %s erases the disks in disks.txt. Inspect first, then add --erase" % cmd)
        names = [x for x in a[1:] if x != "--erase"]
        allowed = (["raw"] if cmd == "barrage" else ["raw-each"]) + list(layouts(len(serials())))
        names = allowed if names == ["all"] else names
        sizes = ("4k", "8k", "16k", "32k", "64k", "128k", "256k", "512k", "1m")

        def ok(x):
            base, _, opt = x.partition("@")
            if base not in allowed:
                return False
            if not opt:
                return True
            kind = layouts(len(serials()))[base][0]
            if kind.startswith("zfs"):
                return opt.lower() in sizes
            import re as _re
            pat = _re.compile(r"^(nobitmap|bigbitmap|writeback|journal=off|chunk=(64k|128k|256k|512k|1m)|layout=(n2|f2|o2)|commit=\d+|inode=\d+)$")
            return kind.startswith("md") and all(pat.match(t) for t in opt.split("+"))
        bad = [x for x in names if not ok(x)]
        if bad or not names:
            sys.exit("layouts: all, or any of " + ", ".join(allowed))
        return run(names, cmd, repeat)
    sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
