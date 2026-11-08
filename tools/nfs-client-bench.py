#!/usr/bin/env python3
"""nfs-client-bench: measure a share from the machine that uses it, beside the disks under it.

disk-bench.py measures calber's disks from inside calber. A share is used from another machine, through the
wire and that machine's NFS client, so it is measured there -- the same tests on the share from the Mac, from
the VM inside the Mac, and on calber's own mount of the same disks, so each column says what the wire and the
client cost. The Blu-ray working disk is the use: a disc's worth of large files written and read back, and the
tree work around it -- many files made, listed with their sizes, sorted, moved into folders, read, removed.

    python3 nfs-client-bench.py net HOST [--label L]              the wire: iperf3 each way, and the ping
    python3 nfs-client-bench.py run DIR [--label L] [--quick]     fio and the tree tests inside DIR
    python3 nfs-client-bench.py show [FILE.json ...]              every result so far, side by side

net needs `iperf3 -s` running on HOST. run writes about 4 GB inside DIR (1 GB with --quick) and removes it,
also when stopped. Results go to ~/.cache/orrery-bench/nfs/LABEL-STAMP.json. Needs python3 and fio (iperf3 for
net); no root -- mounting the share is the one root step, and it is not this script's.
"""

import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time

OUT = os.path.expanduser("~/.cache/orrery-bench/nfs")
MAC = platform.system() == "Darwin"
# 1 GbE carries about 117 MB/s of payload. A share that reads faster than that was not read over the wire:
# the client answered from its own memory, and the number measures that memory, not the share.
WIRE = 125.0


def say(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def save(kind, label, where, tests, extra=None):
    os.makedirs(OUT, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    rec = {"kind": kind, "label": label, "host": socket.gethostname(), "os": platform.platform(), "where": where,
           "stamp": stamp, "tests": tests}
    rec.update(extra or {})
    path = os.path.join(OUT, "%s-%s-%s.json" % (label, kind, stamp))
    with open(path, "w") as f:
        json.dump(rec, f, indent=1)
    say("saved", path)
    return path


# ---- the wire -------------------------------------------------------------------------------------------

def ping(host):
    for args in (["-c", "20", "-i", "0.2"], ["-c", "10"]):
        p = subprocess.run(["ping", "-q"] + args + [host], capture_output=True, text=True)
        m = re.search(r"= ([\d.]+)/([\d.]+)/([\d.]+)", p.stdout)
        if m:
            return {"min_ms": float(m.group(1)), "avg_ms": float(m.group(2)), "max_ms": float(m.group(3))}
    return None


def net(host, label):
    if not shutil.which("iperf3"):
        sys.exit("iperf3 is not installed here")
    tests = {"ping": ping(host)}
    for way, extra in (("up", []), ("down", ["-R"])):
        p = subprocess.run(["iperf3", "-c", host, "-t", "10", "-J"] + extra, capture_output=True, text=True, timeout=90)
        try:
            j = json.loads(p.stdout)
            end = j["end"]
            tests[way] = {"MBps": round(end["sum_received"]["bits_per_second"] / 8e6, 1),
                          "retransmits": end["sum_sent"].get("retransmits")}
        except (ValueError, KeyError):
            sys.exit("iperf3 to %s failed (is `iperf3 -s` running there?): %s" % (host, (p.stdout + p.stderr).strip()[-300:]))
        say("%-4s %6.1f MB/s  (%s retransmits)" % (way, tests[way]["MBps"], tests[way]["retransmits"]))
    if tests["ping"]:
        say("ping %.3f ms average, %.3f worst" % (tests["ping"]["avg_ms"], tests["ping"]["max_ms"]))
    return save("net", label, host, tests)


# ---- what DIR is ------------------------------------------------------------------------------------------

def mount_of(path):
    """The mount DIR lives on, with the options the kernel took -- what was asked for at mount time is not
    always what was granted (a client clamps rsize to what it and the server allow)."""
    path = os.path.realpath(path)
    if MAC:
        best = None
        for line in subprocess.run(["mount"], capture_output=True, text=True).stdout.splitlines():
            m = re.match(r"(.+?) on (.+?) \((.+)\)$", line)
            if m and (path == m.group(2) or path.startswith(m.group(2).rstrip("/") + "/")):
                if best is None or len(m.group(2)) > len(best["at"]):
                    best = {"source": m.group(1), "at": m.group(2), "type": m.group(3).split(",")[0].strip(),
                            "options": m.group(3)}
        if best and best["type"] == "nfs":
            p = subprocess.run(["nfsstat", "-m", best["at"]], capture_output=True, text=True)
            best["granted"] = " ".join(p.stdout.split())[-600:]
        return best
    best = None
    with open("/proc/self/mounts") as f:
        for line in f:
            src, at, typ, opts = line.split()[:4]
            at = at.replace("\\040", " ")
            if path == at or path.startswith(at.rstrip("/") + "/"):
                if best is None or len(at) > len(best["at"]):
                    best = {"source": src, "at": at, "type": typ, "options": opts}
    return best


# ---- fio: the large files ---------------------------------------------------------------------------------

def engine():
    # Linux's asynchronous engine where it is built in, the POSIX one on the Mac; psync with a queue of one
    # everywhere else, which reads the depth tests as one thread and says so in the result.
    p = subprocess.run(["fio", "--enghelp"], capture_output=True, text=True)
    have = p.stdout.split()
    for e in (["posixaio"] if MAC else ["libaio", "io_uring", "posixaio"]):
        if e in have:
            return e
    return "psync"


def fio(name, work, args, quiet=False):
    cmd = ["fio", "--name=" + name, "--directory=" + work, "--filename=seq.dat", "--direct=1",
           "--ioengine=" + ENGINE, "--output-format=json"] + args
    p = subprocess.run(cmd, capture_output=True, text=True)
    try:
        j = json.loads(p.stdout[p.stdout.index("{"):])
    except ValueError:
        raise RuntimeError("fio %s: %s" % (name, (p.stderr or p.stdout).strip()[-300:]))
    job = j["jobs"][0]
    side = job["write"] if job["write"]["io_bytes"] > job["read"]["io_bytes"] else job["read"]
    pct = side.get("clat_ns", {}).get("percentile", {})
    r = {"MBps": round(side["bw"] * 1024 / 1e6, 1), "IOPS": round(side["iops"]),
         "p50_ms": round(pct.get("50.000000", 0) / 1e6, 3), "p99_ms": round(pct.get("99.000000", 0) / 1e6, 3)}
    sync = job.get("sync", {}).get("lat_ns", {})
    if sync.get("mean"):
        r["fsync_ms"] = round(sync["mean"] / 1e6, 3)
    return r


def large(work, size, quick):
    run = "8" if quick else "15"
    gb = int(size.rstrip("G"))
    quarter = "%dM" % (gb * 1024 // 4)
    plan = [
        # The disc's worth, written once front to back: it also lays the file out for the tests after it.
        ("seqW", "sequential write 1M", ["--rw=write", "--bs=1M", "--iodepth=8", "--size=" + size]),
        ("seqR", "sequential read 1M", ["--rw=read", "--bs=1M", "--iodepth=8", "--size=" + size, "--runtime=" + run]),
        ("seqR4", "4 readers 1M", ["--rw=read", "--bs=1M", "--iodepth=4", "--numjobs=4", "--size=" + quarter,
                                   "--offset_increment=" + quarter, "--group_reporting", "--runtime=" + run]),
        ("randR", "random read 4K, queue 16", ["--rw=randread", "--bs=4k", "--iodepth=16", "--size=" + size,
                                               "--time_based", "--runtime=" + run, "--ramp_time=2"]),
        ("randW", "random write 4K, queue 16", ["--rw=randwrite", "--bs=4k", "--iodepth=16", "--size=" + size,
                                                "--time_based", "--runtime=" + run, "--ramp_time=2"]),
        # One 4K write and its fsync at a time: what a program that saves its work and waits pays per save.
        # This is where a sync share and an async one part.
        ("syncW", "4K write + fsync, one at a time", ["--rw=write", "--bs=4k", "--iodepth=1", "--fsync=1",
                                                      "--size=256M", "--time_based", "--runtime=" + run]),
    ]
    out = {}
    for key, words, args in plan:
        r = fio(key, work, args)
        out[key] = r
        tail = ("  fsync %.2f ms" % r["fsync_ms"]) if "fsync_ms" in r else ""
        say("%-6s %-34s %8.1f MB/s %8d IOPS  p99 %.2f ms%s" % (key, words, r["MBps"], r["IOPS"], r["p99_ms"], tail))
    return out


# ---- the tree: many small files ---------------------------------------------------------------------------

def walk(root, extra=None):
    """What `ls -lR` or a file manager sorting by size does: every name, and every name's size and time.
    A Mac on an NFSv3 share writes a hidden ._NAME beside each file, an AppleDouble holding the extended
    attributes the protocol cannot (macOS tags every file a program makes with one). They are stat'ed like
    any file -- that is their cost -- but counted apart, in extra, so the tree's own count still checks."""
    rows = []
    stack = [root]
    while stack:
        d = stack.pop()
        with os.scandir(d) as it:
            for e in it:
                st = e.stat(follow_symlinks=False)
                if e.is_dir(follow_symlinks=False):
                    stack.append(e.path)
                elif e.name.startswith("._"):
                    if extra is not None:
                        extra.append(e.path)
                else:
                    rows.append((e.path, st.st_size, st.st_mtime))
    return rows


MAKE_BUDGET = 60.0   # seconds; a slow share makes a smaller tree, not a longer test


def tree(work, dirs, per):
    """The tree is as large as a minute of making allows, up to dirs x per files: on a share that makes 41
    files a second (the Mac's first sync run, 7 November) the full 10,000 took four minutes to make and as
    long again for every step after it. Each step's rate is per file, so a smaller tree still compares."""
    root = os.path.join(work, "tree")
    blob = os.urandom(4096)
    made = [0]
    out = {}

    def timed(key, words, fn):
        t = time.time()
        fn()
        dt = time.time() - t
        n = made[0]
        out[key] = {"s": round(dt, 2), "per_s": round(n / dt) if dt else None}
        say("%-6s %-34s %8.2f s  %8d files/s" % (key, words % n if "%d" in words else words, dt, out[key]["per_s"] or 0))

    def make():
        t0 = time.time()
        for d in range(dirs):
            os.makedirs(os.path.join(root, "d%03d" % d))
        # One file into every folder in turn, so a tree the minute cuts short is still as wide.
        for i in range(per):
            for d in range(dirs):
                with open(os.path.join(root, "d%03d" % d, "f%05d.bin" % i), "wb") as f:
                    f.write(blob)
                made[0] += 1
            if time.time() - t0 > MAKE_BUDGET:
                return

    rows = []
    companions = []

    def listing():
        companions[:] = []
        rows[:] = walk(root, companions)
        if len(rows) != made[0]:
            raise RuntimeError("listed %d files of %d" % (len(rows), made[0]))

    def sort():
        for key in (lambda r: r[0], lambda r: (-r[1], r[0]), lambda r: r[2]):
            sorted(rows, key=key)

    def move():
        # Into twenty folders by turn, the way a disc's files are gathered from where they were made.
        for b in range(20):
            os.makedirs(os.path.join(root, "sorted", "b%02d" % b))
        for i, (path, _, _) in enumerate(sorted(rows)):
            os.rename(path, os.path.join(root, "sorted", "b%02d" % (i % 20), "%06d.bin" % i))

    def read():
        for path, _, _ in walk(os.path.join(root, "sorted")):
            with open(path, "rb") as f:
                f.read()

    def remove():
        # A Mac removes a file's ._ companion itself when the file goes, so a companion listed a moment ago may
        # be gone by its turn (the Mac's first full run, 7 November): a name already gone is not a failure.
        def gone(fn, path, exc):
            if not isinstance(exc[1], FileNotFoundError):
                raise exc[1]
        shutil.rmtree(root, onerror=gone)

    timed("make", "make %%d 4K files in %d folders" % dirs, make)
    out["files"] = made[0]
    timed("list", "list them with sizes (ls -lR)", listing)
    out["companions"] = len(companions)
    if companions:
        say("       %d hidden ._ companions beside them, made by this machine's NFS client" % len(companions))
    timed("list2", "list them again (the client's cache)", listing)
    timed("sort", "sort by name, size, time (no disk)", sort)
    timed("move", "move each into one of 20 folders", move)
    timed("read", "read every file", read)
    timed("remove", "remove them all", remove)
    return out


def run(path, label, quick):
    global ENGINE
    if not shutil.which("fio"):
        sys.exit("fio is not installed here")
    if not os.path.isdir(path):
        sys.exit("no folder %s (is the share mounted?)" % path)
    where = mount_of(path)
    if label is None:
        label = "%s-%s" % (socket.gethostname().split(".")[0], (where or {}).get("type", "disk"))
    ENGINE = engine()
    work = os.path.join(path, "nfs-bench-%s-%d" % (socket.gethostname().split(".")[0], os.getpid()))
    os.makedirs(work)
    say("%s: %s on %s (%s), fio engine %s" % (label, path, (where or {}).get("source", "?"), (where or {}).get("type", "?"), ENGINE))
    try:
        tests = large(work, "1G" if quick else "4G", quick)
        tests["tree"] = tree(work, 10, 100) if quick else tree(work, 40, 250)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return save("run", label, path, tests, {"mount": where, "engine": ENGINE, "quick": quick})


# ---- side by side -----------------------------------------------------------------------------------------

ROWS = [("net", "up", "MBps", "wire, this machine to the server", "MB/s"),
        ("net", "down", "MBps", "wire, server to this machine", "MB/s"),
        ("net", "ping", "avg_ms", "ping", "ms"),
        ("run", "seqW", "MBps", "sequential write 1M", "MB/s"),
        ("run", "seqR", "MBps", "sequential read 1M", "MB/s"),
        ("run", "seqR4", "MBps", "4 readers 1M", "MB/s"),
        ("run", "randR", "IOPS", "random read 4K, queue 16", "IOPS"),
        ("run", "randW", "IOPS", "random write 4K, queue 16", "IOPS"),
        ("run", "syncW", "IOPS", "4K write + fsync, one at a time", "IOPS"),
        ("tree", "make", "per_s", "make small files", "files/s"),
        ("tree", "list", "per_s", "list with sizes", "files/s"),
        ("tree", "list2", "per_s", "list again", "files/s"),
        ("tree", "move", "per_s", "move into folders", "files/s"),
        ("tree", "read", "per_s", "read every file", "files/s"),
        ("tree", "remove", "per_s", "remove them all", "files/s")]


def load(files):
    if not files:
        files = sorted(os.path.join(OUT, f) for f in os.listdir(OUT) if f.endswith(".json")) if os.path.isdir(OUT) else []
    latest = {}
    for f in files:
        rec = json.load(open(f))
        latest[(rec["label"], rec["kind"])] = rec   # sorted by stamp within a label: the last one stands
    return latest


def show(files):
    latest = load(files)
    labels = sorted({lab for lab, _ in latest}, key=lambda s: (not s.endswith("local"), s))
    if not labels:
        sys.exit("no results yet in " + OUT)
    w = max(12, max(len(s) for s in labels) + 1)
    print("%-34s %-8s" % ("", "") + "".join("%*s" % (w, s) for s in labels))
    for kind, key, field, words, unit in ROWS:
        cells, any_ = [], False
        for lab in labels:
            rec = latest.get((lab, "net" if kind == "net" else "run"))
            v = None
            if rec:
                t = rec["tests"].get("tree", {}) if kind == "tree" else rec["tests"]
                v = (t.get(key) or {}).get(field)
            mark = ""
            if v is not None and unit == "MB/s" and kind == "run" and (rec.get("mount") or {}).get("type", "").startswith("nfs") and v > WIRE:
                mark = "*"
            cells.append("%*s" % (w, "-" if v is None else ("%.3g" % v if unit == "ms" else "{:,}".format(round(v))) + mark))
            any_ = any_ or v is not None
        if any_:
            print("%-34s %-8s" % (words, unit) + "".join(cells))
    print("\n* faster than 1 GbE can carry: the client answered from its own memory, not the share")


def main(a):
    if not a or a[0] in ("-h", "--help"):
        sys.exit(__doc__)
    label = a[a.index("--label") + 1] if "--label" in a else None
    pos = [x for i, x in enumerate(a[1:], 1) if not x.startswith("--") and a[i - 1] != "--label"]
    if a[0] == "net" and pos:
        return net(pos[0], label or socket.gethostname().split(".")[0])
    if a[0] == "run" and pos:
        return run(pos[0], label, "--quick" in a)
    if a[0] == "show":
        return show(pos)
    sys.exit(__doc__)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        sys.exit("stopped")
