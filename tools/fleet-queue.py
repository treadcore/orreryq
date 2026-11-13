#!/usr/bin/env python3
"""fleet-queue: the fleet as one computer -- a queue of jobs, a lane a machine,
a keeper that keeps it all running, and two ways to stop.

    tools/fleet-queue.py DIR start           the keeper, in the foreground
    tools/fleet-queue.py DIR ensure          start the keeper in the background
                                             unless it is already running
    tools/fleet-queue.py DIR stop-adding     the queue drains; what runs finishes;
                                             then the results are collected and
                                             the keeper ends
    tools/fleet-queue.py DIR autostart       the console opening: the keeper starts unless a person
                                             stopped it (a stop, a shutdown, a finished drain)
    tools/fleet-queue.py DIR resume-adding
    tools/fleet-queue.py DIR resume          THE QUEUE GOES AGAIN, whatever stopped it: adding is
                                             on, a shutdown's and a stop's switches are off, and
                                             the keeper starts unless it is running
    tools/fleet-queue.py DIR machine NAME pause|finish|stop|resume|remove|add|restart [now]
                                             one machine, all its lanes. pause: the job in hand
                                             finishes, nothing new starts. finish: the same, and
                                             when its jobs in hand end it leaves the queue for the
                                             bench by itself (a GPU island keeps its segment).
                                             stop: the job in hand goes back on the queue now,
                                             nothing new starts. resume: it takes work again.
                                             remove: the job in hand goes back on the queue now
                                             and it leaves the queue at once, kept on the bench.
                                             add: from the bench, or from machines.json
    tools/fleet-queue.py DIR assign NAME PROJECT on|off
                                             one machine takes that project's jobs, or does not
    tools/fleet-queue.py DIR project NAME pause|stop|resume
                                             one project, every machine: pause and stop as above
    tools/fleet-queue.py DIR stop-now        stop every running job now, collect
                                             the results there are, end
    tools/fleet-queue.py DIR shutdown-now    SHUT THE FLEET DOWN: add nothing,
                                             start nothing; each machine finishes
                                             the job in hand, its results and its
                                             ledger come back, then it powers off;
                                             a report says who finished what
    tools/fleet-queue.py DIR sync            gather every machine's record now
    tools/fleet-queue.py DIR new KIND [k=v ...]
                                             ask the planner for a run (a census,
                                             parts, switches, spsa, train ...):
                                             DIR/runs/RID.json; the planner turns
                                             it into jobs at its next top-up
    tools/fleet-queue.py DIR runs            the runs asked for, and where each is
    tools/fleet-queue.py DIR cancel RID      a run takes no more jobs; its queued
                                             jobs leave the queue
    tools/fleet-queue.py DIR stop-job ID     one job, and nothing else: queued, it leaves
                                             the queue; running, it is stopped on its
                                             machine at the keeper's next beat, and its
                                             lane goes on to the next job
    tools/fleet-queue.py DIR approve RID     a prepared promotion becomes main
    tools/fleet-queue.py DIR push-check      can this machine push the project's branch?
    tools/fleet-queue.py DIR flags [--all] [--brief]
                                             what needs attention: the flags not yet
                                             acknowledged (--all: every one)
    tools/fleet-queue.py DIR ack ID|all [--by NAME]
                                             mark a flag (or all) acknowledged
    tools/fleet-queue.py DIR now            do it now: sync, then promote the strongest
                                             current candidate (pushed in auto mode), or
                                             re-read the older ones on today's defaults
    tools/fleet-queue.py DIR status [--json]
    tools/fleet-queue.py DIR health         is it running as it should: the keeper, its code,
                                             its planning and syncing, the lanes, the jobs waiting
    tools/fleet-queue.py DIR plan-now        the keeper asks the planner for work at its next beat
    tools/fleet-queue.py DIR restart         the keeper restarts on the code on disk; the jobs
                                             running carry on, handed over to the new keeper
    tools/fleet-queue.py DIR add JOB.json    put a job on the queue by hand

DIR/config.json says who works and who plans:

    {"hosts": [{"name": "calber", "target": "user@192.168.8.181", "caps": ["cpu", "gpu"]},
               {"name": "mac", "target": "-", "caps": ["cpu"], "nice": 19}],
     "planner": "python3 -I /path/to/project/scripts/fleet-plan.py DIR",
     "low_water": 6, "poll_s": 10, "max_failures_in_a_row": 5, "sync_s": 1800}

A host may also say how it powers off for shutdown-now ("poweroff": "doas -n
/sbin/poweroff"); one that does not is left running and the report says so.
The keeper runs `PLANNER sync` every sync_s seconds (and at the end), so
every machine's record is gathered without anyone asking, and `PLANNER
chores` every chores_s (60): the project's housekeeping, what is stale begun
in the background, whether or not a window is open.

The planner is asked when the jobs a CPU lane could take fall under
low_water (the GPU islands' own queue does not count), each plan_s, for
a lane idle with nothing it can start, and replan_after_s (15) after a
job marked "replan" comes back: a chain's step, whose next only the
planner can ask for. A pass holds the keeper's beat; health calls the loop
stuck after heartbeat_s (60, or 6 poll_s) with no beat, unless a planner pass
began since the last beat.

CPU lanes idle idle_flag_s (900) with nothing they can start raise a flag
saying why, as far as the keeper can see: a build failed (its first error
line), builds or jobs not done, or nothing queued that fits.

The planner is the project's: `PLANNER plan N` prints a JSON list of up to N
new jobs, and `PLANNER collect` gathers what the finished jobs found. The
queue knows nothing about what a job is for. A job:

    {"id": "w0042", "kind": "weights", "title": "census of w_near at 1.4",
     "needs": "cpu" | "gpu" | "host:NAME",
     "after": ["r0007", ...],          jobs that must be done first
     "after_host": "prep-{host}",      a job that must be done on the host that
                                       takes this one (its build, say)
     "cmd": "bash, run on the host from $HOME",
     "send": [{"src": "a file here", "dst": "a path on the host"}], before the cmd
     "fetch": "a path under $HOME, copied back into DIR/results/ID/",
     "deliver": {"src": "path on the host", "to": "user@store", "dst": "path on the store"},
     "on_done": "a command run here, after, with JOB_ID and RESULT_DIR set",
     "replan": true,                   the planner is asked soon after it comes back
     "priority": "high" | "low",       ahead of the standing work, or after it (the background job)
     "timeout_s": 7200}

Everything is a file a person can read: queue/, running/HOST/, done/, failed/,
stopped/ (a job each, its JSON), logs/ID.log, results/ID/, lanes/HOST.json
(what each lane is doing), events.jsonl, and the switches STOP_ADDING and
STOP_NOW (and SHUTDOWN), flags/ (what needs a person's attention, each
acknowledged or not), keeper.json (the keeper: pid, start, last plan, last and
next sync, the caffeinate holding a Mac awake). A job is claimed by renaming its file, so two lanes never run one
job. A remote job runs in its own process group, its pid kept on the host,
so `stop-now` can stop all of it.
"""
import glob
import re
import hashlib
import json
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from base64 import b64encode

SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=30"]


def now():
    return time.time()


class Queue:
    def __init__(self, d):
        self.d = os.path.abspath(d)
        for sub in ("queue", "running", "done", "failed", "stopped", "logs", "results", "lanes", "stop-job", "send-back"):
            os.makedirs(os.path.join(self.d, sub), exist_ok=True)
        self.lock = threading.Lock()
        self.flag_lock = threading.Lock()
        self.restarting = False
        # When the checks after a cut are asked for next (tools/boots.py): soon after a host comes back.
        self.boots_at = None
        # When a chain's step came back (a job with `replan`): the planner is asked then, not at its
        # next pass. The earliest asked, so a burst of returns is one pass (change B).
        self.replan_at = None
        # THE HANDOVER (Paul, 4 November: "build A"). A keeper that restarts itself keeps its jobs:
        # it re-executes in place, its children (the ssh of each running job) are still its children,
        # and the new keeper waits on them and finishes each job as any job finishes. From the moment
        # a handover begins nothing reaps a child (hand_lock), so a job that ends inside it is still
        # there, with its exit code, for the new keeper to read.
        self.hand_lock = threading.Lock()
        self.handing = False
        self.parked = set()
        self.started = {}
        self.adopt = {}

    # ---- files ---------------------------------------------------------
    def p(self, *a):
        return os.path.join(self.d, *a)

    def config(self):
        with open(self.p("config.json")) as f:
            return json.load(f)

    def event(self, what, **kw):
        line = json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": what, **kw})
        with self.lock, open(self.p("events.jsonl"), "a") as f:
            f.write(line + "\n")

    def jobs_in(self, sub):
        out = []
        base = self.p(sub)
        for root, _, files in os.walk(base):
            for fn in sorted(files):
                if fn.endswith(".json"):
                    try:
                        with open(os.path.join(root, fn)) as f:
                            j = json.load(f)
                        j["_file"] = os.path.join(root, fn)
                        out.append(j)
                    except (OSError, ValueError):
                        pass
        return out

    def ids_in(self, sub):
        return {j["id"] for j in self.jobs_in(sub)}

    def known(self):
        return set().union(*(self.ids_in(s) for s in ("queue", "running", "done", "failed", "stopped")))

    def add(self, job):
        if not job.get("id") or any(c in job["id"] for c in "/ ."):
            raise ValueError("a job needs an id of letters, digits, - and _")
        if job["id"] in self.known():
            return False
        # The file name orders the queue: the planner's order, kept. A job
        # marked "priority": "high" (what a person asked for) goes ahead of
        # the standing work: its number is set back a few years. One marked
        # "low" (the background job's) goes after it: set forward as far.
        seq = int(now() * 1000) - {"high": 10 ** 11, "low": -10 ** 11}.get(job.get("priority"), 0)
        tmp = self.p("queue", ".%s.tmp" % job["id"])
        with open(tmp, "w") as f:
            json.dump(job, f, indent=1)
        os.rename(tmp, self.p("queue", "%d-%s.json" % (seq, job["id"])))
        return True

    def flag(self, name):
        return os.path.exists(self.p(name))

    def unpin(self, jid, by):
        """A queued job's needs host:X becomes its "or" need, or cpu: whoever fits takes it."""
        for j in self.jobs_in("queue"):
            if j["id"] == jid and j.get("needs", "").startswith("host:"):
                was = j["needs"]
                j["needs"] = j.pop("or", None) or "cpu"
                j["moved_from"] = was[5:]
                path = j.pop("_file")
                with open(path + ".tmp", "w") as f:
                    json.dump(j, f, indent=1)
                os.replace(path + ".tmp", path)
                self.event("job unpinned", job=jid, was=was, needs=j["needs"], by=by)
                return True
        return False

    def notice(self, kind, text, key=None, progress=False):
        """Raise a flag: something a person (or the agent working with them)
        should look at. One a key: a key already flagged is not raised again.
        flags/SEQ-KIND.json, until acknowledged (ack). A progress record
        (progress=True: a candidate found, say) is news, not a question: it
        is shown (progress()) and never waits for anyone."""
        d = self.p("flags")
        os.makedirs(d, exist_ok=True)
        key = key or "%s:%s" % (kind, text)
        # LANES THAT LOSE THEIR HOSTS TOGETHER RAISE THEIR FLAGS IN ONE MILLISECOND. A power cut takes
        # calber and calber-cuda (one box, two lanes) and the small switch's machines at the same
        # instant; their lanes time out on the same beat and arrive here at once. Named by the clock
        # alone, two flags were one name: both wrote the same .tmp, the first rename took it, the
        # second raised FileNotFoundError, and that lane's thread died -- calber's CPU lane on 7
        # November and again on 8 November. The beat starts a dead lane again (07:49:28, a minute
        # on), so what was lost was the flag and the minute; a lane that died holding a job would
        # lose more. So the look for the key and the write are one step under a lock (apart, two
        # lanes with one key could both find none), the number steps past any name already taken,
        # and the .tmp is the thread's own.
        with self.flag_lock:
            for f in os.listdir(d):
                try:
                    if json.load(open(os.path.join(d, f))).get("key") == key:
                        return False
                except (OSError, ValueError):
                    pass
            seq = int(now() * 1000)
            while os.path.exists(os.path.join(d, "%d-%s.json" % (seq, kind))):
                seq += 1
            fid = "%d-%s" % (seq, kind)
            tmp = os.path.join(d, ".%s.%d-%d.tmp" % (fid, os.getpid(), threading.get_ident()))
            with open(tmp, "w") as f:
                json.dump({"id": fid, "t": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind, "text": text, "key": key, "ack": None,
                           "progress": bool(progress)}, f)
            os.rename(tmp, os.path.join(d, fid + ".json"))
        self.event("flag", kind=kind, text=text)
        return True

    def flags(self, every=False):
        out = []
        for f in sorted(glob.glob(self.p("flags", "*.json"))):
            try:
                j = json.load(open(f))
            except (OSError, ValueError):
                continue
            if every or not (j.get("ack") or j.get("progress")):
                out.append(j)
        return out

    def progress(self):
        """The progress records, oldest first: what the fleet has found."""
        out = []
        for f in sorted(glob.glob(self.p("flags", "*.json"))):
            try:
                j = json.load(open(f))
            except (OSError, ValueError):
                continue
            if j.get("progress"):
                out.append(j)
        return out

    def ack(self, fid, by):
        n = 0
        for f in sorted(glob.glob(self.p("flags", "*.json"))):
            # ONE FLAG THAT CANNOT BE READ DOES NOT STOP THE REST (13 November). A flag written twice over in
            # the cut of 8 November was not JSON, and Acknowledge all died on it with "Extra data: line 1
            # column 193" before it reached any other: 23 flags stood unacknowledged behind one bad file.
            # flags() and progress() had always passed over such a file; this did not.
            try:
                j = json.load(open(f))
            except (OSError, ValueError):
                continue
            if not j.get("ack") and not j.get("progress") and (fid == "all" or j["id"] == fid):
                j["ack"] = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "by": by}
                with open(f + ".tmp", "w") as out:
                    json.dump(j, out)
                os.replace(f + ".tmp", f)
                n += 1
                # Acknowledging a stranded job passes it on: the pin to its machine comes off and
                # any lane that fits takes it (Paul, 3 November: "create an acknowledge which
                # passes it on to the queue").
                if j.get("kind") == "stranded" and not by.startswith("the keeper"):
                    self.unpin((j.get("key") or "")[len("stranded:"):], by)
        if n:
            self.event("acknowledged", flag=fid, by=by, count=n)
        return n


# ---- running a job on a host --------------------------------------------------

def remote(target, script, timeout=None, stdin=None, capture=True):
    """Run `script` under bash on the host (or here for "-"), sent as base64 so
    no quoting is read twice, whatever the host's login shell."""
    b = b64encode(script.encode()).decode()
    cmd = ["bash", "-c", script] if target == "-" else SSH + [target, 'exec bash -c "$(echo %s | base64 -d)"' % b]
    # ssh's own failure, 255, three times over half a minute before it is believed: the Copal
    # machines reset a connection now and then (154 "unreachable" and 81 failed jobs in two days
    # on saskatchewan, while it answered every other ssh), and one reset lost a finished read.
    for attempt in range(3):
        r = subprocess.run(cmd, input=stdin, capture_output=capture, text=stdin is None or isinstance(stdin, str),
                           timeout=timeout)
        if r.returncode != 255 or target == "-" or attempt == 2:
            return r
        time.sleep(15)


class Child:
    """A job's process: its Popen, or, adopted across a restart, its pid alone. THE POPEN IS KEPT
    while the job runs: one let go is reaped by subprocess on its own, and its code is lost."""
    def __init__(self, p=None, pid=None):
        self.p, self.pid = p, p.pid if p else pid

    def poll(self):
        """The exit code; None while it runs; "gone" if it is not this process's child."""
        if self.p:
            return self.p.poll()
        try:
            done, status = os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:
            return "gone"
        return os.waitstatus_to_exitcode(status) if done else None

    def reap(self):
        if self.p:
            return self.p.wait()
        try:
            return os.waitstatus_to_exitcode(os.waitpid(self.pid, 0)[1])
        except ChildProcessError:
            return "gone"

    def terminate(self):
        try:
            os.kill(self.pid, signal.SIGTERM)
        except OSError:
            pass

    def kill(self):
        try:
            os.kill(self.pid, signal.SIGKILL)
        except OSError:
            pass


CPU_STEPS = (1, 2, 4, 8, 16, 32, 64, 128)


def limiter(host):
    """THE CPU LIMITER (Paul, 5 November: "a CPU limiter where we use 2^n CPUs, so 1, 2, 4, 8 ...
    I don't want it to be stressed"). A host's "cpus" in config.json, a power of two, is the number
    of CPUs its jobs are told the machine has: every job asks `nproc` (or, on a Mac, `sysctl -n
    hw.ncpu`) how many seeds or threads to run at once, so both answer the limit, for the job and
    every shell under it; cargo, rayon and OpenMP are told the same, and THREADS where a job reads it.
    A host's "background", on a Mac, runs the job at the background policy (taskpolicy -b): the
    efficiency cores and the lowest priority, so a person at the machine does not feel it."""
    out = ""
    n = host.get("cpus")
    if n in CPU_STEPS:
        out += ("nproc() { echo %d; }; export -f nproc\n"
                "sysctl() { if [ \"$*\" = \"-n hw.ncpu\" ]; then echo %d; else command sysctl \"$@\"; fi; }; export -f sysctl\n"
                "export CARGO_BUILD_JOBS=%d RAYON_NUM_THREADS=%d OMP_NUM_THREADS=%d THREADS=%d\n") % ((n,) * 6)
    if host.get("background"):
        out += "command -v taskpolicy >/dev/null && taskpolicy -b -p $$ >/dev/null 2>&1\n"
    return out


def run_job(q, host, job, log, t0=None, adopted=None):
    """The job's command, in its own process group on the host, its pid kept
    in ~/.fleet-queue/ID.pid so stop-now can stop the whole group. Its exit code;
    "gone" when an adopted job turns out not to be this process's child."""
    jid = job["id"]
    body = job["cmd"]
    t0 = t0 or now()
    deadline = t0 + job.get("timeout_s", 4 * 3600)
    # A host's "nice" (config.json) lowers the whole job, its children too.
    nice = "renice -n %d -p $$ >/dev/null 2>&1\n" % host["nice"] if host.get("nice") else ""
    wrapper = nice + limiter(host) + (
        "mkdir -p ~/.fleet-queue; cd ~; set -m\n"
        "( %s ) &\n"
        "echo $! > ~/.fleet-queue/%s.pid\n"
        "wait $!; rc=$?; rm -f ~/.fleet-queue/%s.pid; exit $rc\n"
    ) % (body, jid, jid)
    b = b64encode(wrapper.encode()).decode()
    cmd = ["bash", "-c", wrapper] if host["target"] == "-" else SSH + [host["target"], 'exec bash -c "$(echo %s | base64 -d)"' % b]
    with open(log, "a") as out:
        if adopted:
            out.write("-- the keeper restarted at %s; the job ran on (pid %d)\n" % (time.strftime("%H:%M:%S"), adopted))
            out.flush()
            child = Child(pid=adopted)
        else:
            out.write("$ %s\n" % job.get("cmd", "")[:2000])
            out.flush()
            child = Child(p=subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, start_new_session=True))
        q.procs[jid] = (child, host)
        q.started[jid] = (t0, job["_file"], host["name"])
        try:
            while True:
                with q.hand_lock:
                    if q.handing:
                        # Handed over: this thread ends with the exec, the job runs on.
                        q.parked.add(host["name"])
                        rc = "parked"
                    else:
                        rc = child.poll()
                if rc == "parked":
                    while True:
                        time.sleep(60)
                if rc is not None:
                    return rc
                if now() > deadline:
                    stop_remote(host, jid)
                    child.kill()
                    child.reap()
                    out.write("timed out after %s s\n" % job.get("timeout_s", 4 * 3600))
                    return 124
                time.sleep(1)
        finally:
            q.procs.pop(jid, None)
            q.started.pop(jid, None)


def stop_asked(q, jid):
    """`stop-job ID` asked for this one."""
    return os.path.exists(q.p("stop-job", jid))


def sent_back(q, jid):
    """A machine or a project was stopped: this job runs again, somewhere, later."""
    return os.path.exists(q.p("send-back", jid))


def stop_remote(host, jid):
    script = "f=~/.fleet-queue/%s.pid; [ -f $f ] && kill -TERM -$(cat $f) 2>/dev/null; sleep 2; [ -f $f ] && kill -KILL -$(cat $f) 2>/dev/null; rm -f $f; true" % jid
    try:
        remote(host["target"], script, timeout=30)
    except (subprocess.TimeoutExpired, OSError):
        pass


def send(q, host, job, log):
    """Files from here to the host, before the job runs."""
    for f in job.get("send", []):
        src, dst = os.path.expanduser(f["src"]), f["dst"]
        with open(src, "rb") as data:
            body = data.read()
        r = remote(host["target"], "mkdir -p $(dirname %s) && cat > %s" % (dst, dst), timeout=600, stdin=body)
        with open(log, "a") as out:
            out.write("sent %s -> %s (%d bytes, %s)\n" % (src, dst, len(body), "ok" if r.returncode == 0 else "FAILED"))
        if r.returncode != 0:
            return False
    return True


def fetch(q, host, job, log):
    """A path under the host's $HOME, copied into results/ID/ with tar."""
    rel = job["fetch"]
    dest = q.p("results", job["id"])
    os.makedirs(dest, exist_ok=True)
    src = "tar -C ~ -cf - %s" % shlex.quote(rel)
    # A finished read is the dearest thing on the wire: a reset here cost the whole census.
    for attempt in range(4):
        a = subprocess.Popen(["bash", "-c", src] if host["target"] == "-" else SSH + [host["target"], src], stdout=subprocess.PIPE)
        b = subprocess.run(["tar", "-C", dest, "-xf", "-"], stdin=a.stdout, capture_output=True)
        a.wait()
        ok = a.returncode == 0 and b.returncode == 0
        with open(log, "a") as out:
            out.write("fetched %s -> %s (%s)\n" % (rel, dest, "ok" if ok else "FAILED"))
        if ok or a.returncode != 255:
            return ok
        time.sleep(15)
    return False


def deliver(q, host, job, log):
    """A file from the host to the store, hashed as it passes (read once),
    written as .part, its hash read again on the store, then renamed."""
    d = job["deliver"]
    src, to, dst = d["src"], d["to"], d["dst"]
    h = hashlib.sha256()
    n = 0
    if host["target"] == to:
        r = remote(to, "sha256sum %s | cut -c1-64; mkdir -p $(dirname %s); mv %s %s" % (src, dst, src, dst), timeout=600)
        ok = r.returncode == 0
        with open(log, "a") as out:
            out.write("delivered in place on the store: %s (%s)\n" % (dst, "ok" if ok else "FAILED"))
        return ok
    reader = (subprocess.Popen(["bash", "-c", "cat %s" % src], stdout=subprocess.PIPE) if host["target"] == "-"
              else subprocess.Popen(SSH + [host["target"], "cat %s" % src], stdout=subprocess.PIPE))
    writer = subprocess.Popen(SSH + [to, "mkdir -p $(dirname %s) && cat > %s.part" % (dst, dst)], stdin=subprocess.PIPE)
    while True:
        chunk = reader.stdout.read(1 << 20)
        if not chunk:
            break
        h.update(chunk)
        n += len(chunk)
        writer.stdin.write(chunk)
    writer.stdin.close()
    reader.wait()
    writer.wait()
    there = remote(to, "sha256sum %s.part | cut -c1-64" % dst, timeout=600).stdout.strip()
    ok = reader.returncode == 0 and writer.returncode == 0 and there == h.hexdigest()
    with open(log, "a") as out:
        out.write("delivered %d bytes to %s:%s, sha256 %s %s\n" % (n, to, dst, h.hexdigest()[:16], "ok" if ok else "DIFFERS: %s" % there[:16]))
    if ok:
        remote(to, "mv %s.part %s" % (dst, dst), timeout=60)
        remote(host["target"], "rm -f %s" % src, timeout=60)
    return ok


# ---- a lane -------------------------------------------------------------------

def projects_of(cfg):
    """The projects sharing the queue, in order: {name: {"caps": the lane's capability
    it runs on, "kinds": its jobs' kinds}}. The one without kinds takes every other
    kind. The queue still knows nothing of what a job is for: only whose it is."""
    return cfg.get("projects") or {"jobs": {"caps": "cpu"}}


def project_of(cfg, job):
    ps = projects_of(cfg)
    for name, p in ps.items():
        if job.get("kind") in p.get("kinds", ()):
            return name
    return next((n for n, p in ps.items() if not p.get("kinds")), next(iter(ps)))


def working(cfg, h):
    """A lane's record as it stands now: what it refuses, by machine and by project.
    The record a lane was started with goes stale; this is read at each pick."""
    return dict(h, _cfg=cfg, _refuse=set(h.get("off", ())) | set(cfg.get("paused_projects", ())))


def fits(host, job):
    if host.get("_refuse") and project_of(host["_cfg"], job) in host["_refuse"]:
        return False
    need = job.get("needs", "cpu")
    if need.startswith("host:"):
        return need[5:] == host["name"]
    return need in host.get("caps", ["cpu"])


def builder(host):
    """The name a host's builds are done under. A SECOND LANE ON ONE MACHINE (Paul, 13 November: "yes
    build 1 and 2") is a host entry of its own, the same target, with "build_of" naming the machine's
    first: a census splits its seeds over every core and is as long as its slowest share, so between
    jobs and in each job's tail most of the cores stand idle (saskatchewan, a minute sampled each five
    seconds: 3, 2, 0, 0, 0, 8, 6, 4, 4, 17, 17, 17 census processes on 24 threads). A second lane takes
    its own job into those gaps. It builds nothing: what the first lane built on that machine is its build."""
    return host.get("build_of", host["name"])


def ready(host, job, done):
    """The host could start the job now: it fits, and what it waits for
    (its jobs, and its build on this host) is done."""
    ah = job.get("after_host")
    if ah and ah.format(host=builder(host)) not in done:
        return False
    return fits(host, job) and all(a in done for a in job.get("after", []))


def lane_file(q, name):
    try:
        with open(q.p("lanes", name + ".json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def rehome(q, cfg):
    """A queued job pinned to a machine (needs host:X) that is paused or no longer in the queue
    waits for nothing that will come. Paul, 3 November: "when a machine is paused or removed the
    queue not started on that item should move to another machine queue." A job that says where
    else it may run ("or": a need, "fast" or "cpu") is rewritten to that and taken by the next
    lane that fits; one that cannot move (a promotion wants the Mac's checkout and its push) is
    flagged once, with the way out. Nothing running is touched: that is the lane's job in hand."""
    active = {h["name"] for h in cfg["hosts"] if not h.get("paused")}
    moved = 0
    stranded = set()
    for j in q.jobs_in("queue"):
        need = j.get("needs", "cpu")
        if not need.startswith("host:") or need[5:] in active:
            continue
        host = need[5:]
        if j.get("or"):
            j["needs"] = j.pop("or")
            j["moved_from"] = host
            path = j.pop("_file")
            tmp = path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(j, f, indent=1)
            os.replace(tmp, path)
            q.event("job moved", job=j["id"], was=host, needs=j["needs"])
            moved += 1
        else:
            stranded.add(j["id"])
            q.notice("stranded", "%s waits for %s, which is %s: Resume or Add it on the Queue's Fleet page; acknowledge this to let any machine take it; or cancel the job" % (
                j["id"], host, "paused" if any(h["name"] == host for h in cfg["hosts"]) else "not in the queue"), key="stranded:" + j["id"])
    # A stranded flag answers itself once the job is no longer stranded (its machine is back, it
    # moved, it ran, or it was cancelled): a flag that outlives its cause is what Paul saw on 3
    # November after Add, Resume and Stop, and it said nothing true any more.
    for f in glob.glob(q.p("flags", "*-stranded.json")):
        try:
            fl = json.load(open(f))
        except (OSError, ValueError):
            continue
        jid = (fl.get("key") or "")[len("stranded:"):]
        if not fl.get("ack") and jid and jid not in stranded:
            q.ack(fl["id"], "the keeper: no longer stranded")
    return moved


def starved(q, cfg, idle_s=None):
    """The lanes idle at least idle_s with nothing queued they could start.

    THE QUEUE'S LENGTH IS NOT THE QUESTION. On 28 October it held eleven jobs
    and five CPU lanes sat idle: five were builds for whitewolf, waiting
    behind its six-hour school job, and six were crucible's segments, queued
    ahead for the GPU lanes. Eleven is above the low-water mark, so the
    keeper never asked for more. A lane with nothing it can start is the
    question, whatever else is queued."""
    idle_s = cfg.get("starve_idle_s", 30) if idle_s is None else idle_s
    jobs = q.jobs_in("queue")
    done = q.ids_in("done")
    out = []
    for h in cfg["hosts"]:
        l = lane_file(q, h["name"])
        h = working(cfg, h)
        # A lane for one kind of job (the Mac's, promotions alone) is not hungry: nothing the
        # planner could add would feed it, and asking each minute is how a queue grew to 1,915.
        if not {"cpu", "gpu", "cuda"} & set(h.get("caps", ["cpu"])):
            continue
        if l.get("state") == "idle" and now() - l.get("since", now()) >= idle_s and not any(ready(h, j, done) for j in jobs):
            out.append(h["name"])
    return out


def first_error(q, jid):
    """The first line of a job's last run that says what went wrong: a `fatal:` or `error:` line
    (git, cargo), else the last line it wrote. A log keeps every run of its job, each begun with the
    job's command, which is skipped."""
    try:
        log = open(q.p("logs", jid + ".log"), errors="replace").read()
    except OSError:
        return "no log"
    for j in q.jobs_in("failed"):
        if j["id"] == jid and j.get("cmd"):
            head = "$ %s\n" % j["cmd"][:2000]
            at = log.rfind(head)
            if at >= 0:
                log = log[at + len(head):]
            break
    m = re.search(r"^((?:fatal|error)(?:\[\w+\])?: .*)$", log, re.M)
    if m:
        return m.group(1)[:200]
    said = [l for l in log.splitlines() if l.strip() and not l.startswith("[") and not l.startswith("$ ")]
    return said[-1][:200] if said else "nothing said"


def idle_reason(q, cfg, names, info=None):
    """WHY THESE LANES HAVE NOTHING THEY CAN START, as far as the keeper can see (the lab report of
    4 November, "Fifty-Four Idle Minutes", change D). That night five CPU lanes stood idle 54 minutes
    under a full queue, every job behind a build that had failed with `fatal: invalid reference`,
    and nothing said so until a person looked. In order: a build that failed (with its first error
    line), a build not done, a job waited on not done, nothing queued that fits."""
    jobs = q.jobs_in("queue")
    done, failed = q.ids_in("done"), q.ids_in("failed")
    by = {h["name"]: working(cfg, h) for h in cfg["hosts"]}
    broken, building, waiting, empty = {}, {}, {}, []
    for n in names:
        mine = [j for j in jobs if n in by and fits(by[n], j)]
        if not mine:
            empty.append(n)
            continue
        for j in mine:
            b = j.get("after_host", "").format(host=builder(by[n])) if j.get("after_host") else None
            if b and b in failed:
                broken[n] = b
                break
            if b and b not in done:
                building[n] = b
                break
            pend = [a for a in j.get("after", []) if a not in done]
            if pend:
                waiting[n] = pend[0]
                break
    parts = []
    if broken:
        first = sorted(broken.values())[0]
        parts.append("the build failed on %d machine%s (%s): %s (logs/%s.log)" % (
            len(broken), "" if len(broken) == 1 else "s", ", ".join(sorted(broken)), first_error(q, first), first))
    if building:
        parts.append("waiting on builds not done: %s" % ", ".join("%s (%s)" % (b, n) for n, b in sorted(building.items())))
    if waiting:
        parts.append("waiting on jobs not done: %s" % ", ".join("%s (%s)" % (b, n) for n, b in sorted(waiting.items())))
    if empty:
        info = info or {}
        asked = (info.get("last_plan") or "")[11:16]
        parts.append("nothing queued fits %s (%d queued); the planner was last asked at %s and added %s" % (
            ", ".join(empty), len(jobs), asked or "?", info.get("last_plan_added", "?")))
    return "; ".join(parts)


def idle_lanes(q, cfg, idle_s=None):
    """CPU lanes idle idle_s (idle_flag_s, 900) with nothing they can start, and since when the first
    of them: the CPU lanes are where the planner keeps work, so one idle a quarter hour is a fault."""
    idle_s = cfg.get("idle_flag_s", 900) if idle_s is None else idle_s
    if not idle_s:
        return [], None
    caps = {h["name"]: h.get("caps", ["cpu"]) for h in cfg["hosts"]}
    names = [n for n in starved(q, cfg, idle_s=idle_s) if "cpu" in caps.get(n, [])]
    since = min((lane_file(q, n).get("since", now()) for n in names), default=None)
    return names, since


def cpu_queued(cfg, jobs):
    """The queued jobs a CPU machine could take: what the low water counts (the duty-cycle report's
    change A; Paul, 5 November: "build A"). The GPU islands keep six segments a card queued on purpose;
    counted with the rest they held the queue over low_water for good, so the planner was asked only
    each plan_s, and a CPU machine whose queue ran dry stood about a minute until the starved path
    asked for it: the CPU's last two percent. None when no CPU machine is at work."""
    cpu = [working(cfg, h) for h in cfg["hosts"] if "cpu" in h.get("caps", ["cpu"]) and not h.get("paused")]
    if not cpu:
        return None
    # The background job's pieces are not work the planner keeps up: counted, they would stand in
    # for it, and the lanes would take them while the line's own work waited for a pass.
    return sum(1 for j in jobs if j.get("priority") != "low" and any(fits(h, j) for h in cpu))


def breaker_stop(q):
    """STOP_ADDING is up, and the breaker put it there (it writes "breaker" in it; a person's press leaves
    it empty)."""
    try:
        with open(q.p("STOP_ADDING")) as f:
            return f.read().startswith("breaker")
    except OSError:
        return False


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def code_id():
    """This file's identity: what a keeper runs, against what is on disk."""
    try:
        with open(os.path.abspath(__file__), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:12]
    except OSError:
        return None


def lane(q, host, alive):
    name = host["name"]
    os.makedirs(q.p("running", name), exist_ok=True)

    said = {}

    def say(state, job=None, since=None):
        # "since" is when the lane came to this state: an idle lane says
        # idle every three seconds, and an hour of it must read as an hour.
        # An adopted job keeps the time it began.
        jid = job and job["id"]
        if said.get("state") != state or said.get("job") != jid:
            said.update(state=state, job=jid, since=since or now())
        tmp = q.p("lanes", ".%s.tmp" % name)
        with open(tmp, "w") as f:
            json.dump({"host": name, "state": state, "job": jid, "kind": job and job.get("kind"),
                       "title": job and job.get("title"), "since": said["since"]}, f)
        os.rename(tmp, q.p("lanes", name + ".json"))

    # A job the keeper before this one handed over: this lane finishes it before it takes another.
    handed = q.adopt.pop(name, None)
    if handed:
        try:
            j = dict(json.load(open(handed["file"])), _file=handed["file"])
            work(q, host, j, say, adopted=handed)
        except Exception as e:  # the job fails; the lane goes on
            q.event("lane error", host=name, job=handed.get("id"), detail=repr(e)[:300])
            try:
                os.rename(handed["file"], q.p("failed", os.path.basename(handed["file"])))
            except OSError:
                pass
    say("idle")
    while alive.is_set() and not q.flag("STOP_NOW"):
        if q.flag("SHUTDOWN"):
            power_off(q, host, say)
            return
        # A host taken out of config.json leaves: its lane ends after the job
        # in hand, so a host can be removed while the queue runs.
        cfg = q.config()
        me = next((h for h in cfg["hosts"] if h["name"] == name), None)
        if me is None:
            q.event("lane left", host=name, why="not in config.json")
            say("removed")
            return
        host = working(cfg, me)
        # PAUSED COMES BEFORE REACHABLE. A machine a person has set aside is not a
        # machine that is down: it raises no flag, and it may well be off.
        if me.get("paused"):
            say("paused")
            time.sleep(3)
            continue
        # A host that cannot be reached waits, probed each minute, and takes
        # nothing: a machine that is down must not fail the queue's jobs.
        if not reachable(host):
            q.event("host unreachable", host=name)
            q.notice("host", "%s cannot be reached: its lane waits" % name, key="host:%s:%s" % (name, time.strftime("%Y-%m-%d %H")))
            say("unreachable")
            def waiting():
                r = next((h for h in q.config()["hosts"] if h["name"] == name), None)
                return r is not None and not r.get("paused")
            while alive.is_set() and not q.flag("STOP_NOW") and waiting() and not reachable(host):
                for _ in range(20):
                    if not alive.is_set() or q.flag("STOP_NOW") or not waiting():
                        break
                    time.sleep(3)
            if waiting():
                q.event("host back", host=name)
                # A machine back from dark may be back from a boot: read it soon.
                q.boots_at = q.boots_at or now() + 20
            continue
        done, failed = q.ids_in("done"), q.ids_in("failed") | q.ids_in("stopped")
        picked = None
        for j in q.jobs_in("queue"):
            if not fits(host, j):
                continue
            after = j.get("after", [])
            if any(a in failed for a in after):
                # It cannot run: say so, and why.
                try:
                    os.rename(j["_file"], q.p("failed", os.path.basename(j["_file"])))
                    q.event("failed", job=j["id"], why="a job it waited for failed")
                except OSError:
                    pass
                continue
            if ready(host, j, done):
                try:
                    claimed = q.p("running", name, os.path.basename(j["_file"]))
                    os.rename(j["_file"], claimed)
                    j["_file"] = claimed
                    picked = j
                    break
                except OSError:
                    continue  # another lane took it
        if not picked:
            say("idle")
            time.sleep(3)
            continue
        try:
            work(q, host, picked, say)
            if q.flag("SHUTDOWN"):
                power_off(q, host, say)
                return
        except Exception as e:  # the job fails; the lane goes on
            q.event("lane error", host=name, job=picked["id"], detail=repr(e)[:300])
            try:
                os.rename(picked["_file"], q.p("failed", os.path.basename(picked["_file"])))
            except OSError:
                pass
    say("stopped")


def power_off(q, host, say):
    """Shutdown: the host's record comes back (PLANNER sync HOST), then it
    powers off by its own command; the lane ends. What it did is reported."""
    name = host["name"]
    planner = q.config().get("planner")
    if planner and reachable(host):
        say("reporting")
        r = subprocess.run(["bash", "-c", "%s sync %s" % (planner, name)], capture_output=True, text=True, timeout=1800)
        q.event("reported", host=name, detail=(r.stdout or r.stderr)[-300:])
    cmd = host.get("poweroff")
    if not cmd:
        q.event("left running", host=name, why="no poweroff in config.json")
        say("left running")
        return
    if not reachable(host):
        q.event("powered off", host=name, detail="already unreachable")
        say("off")
        return
    # The connection drops as the machine goes down: ssh's 255 is expected.
    try:
        r = remote(host["target"], "nohup sh -c 'sleep 2; %s' >/dev/null 2>&1 &" % cmd, timeout=60)
        ok = r.returncode in (0, 255)
        detail = (r.stderr or "").strip()[-200:]
    except subprocess.TimeoutExpired:
        ok, detail = True, "the connection hung as it went down"
    time.sleep(10)
    if ok and not reachable(host):
        q.event("powered off", host=name)
        say("off")
    else:
        q.event("poweroff failed", host=name, detail=detail or "it still answers")
        say("poweroff failed")


def reachable(host):
    """ssh answers (always, for this machine)."""
    if host["target"] == "-":
        return True
    try:
        return remote(host["target"], "true", timeout=30).returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def work(q, host, j, say, adopted=None):
    name = host["name"]
    if True:
        log = q.p("logs", j["id"] + ".log")
        if adopted:
            # Handed over by the keeper before this one: it ran on through the restart.
            t0 = adopted["t0"]
            say("running", j, since=t0)
            q.event("adopted", job=j["id"], host=name, pid=adopted["pid"])
            rc = run_job(q, host, j, log, t0, adopted=adopted["pid"])
            if rc == "gone":
                with open(log, "a") as out:
                    out.write("the keeper restarted and the job's process was not its own to wait on: the job goes back on the queue\n")
                os.rename(j["_file"], q.p("queue", os.path.basename(j["_file"])))
                q.event("requeued", job=j["id"], host=name, why="the keeper restarted and could not take it up")
                return
        else:
            say("running", j)
            q.event("started", job=j["id"], host=name, kind=j.get("kind"))
            t0 = now()
            rc = 1
            if send(q, host, j, log) and not stop_asked(q, j["id"]) and not sent_back(q, j["id"]):
                rc = run_job(q, host, j, log, t0)
        ok = rc == 0
        if ok and j.get("deliver"):
            say("delivering", j)
            ok = deliver(q, host, j, log)
        if ok and j.get("fetch"):
            say("fetching", j)
            ok = fetch(q, host, j, log)
        back = sent_back(q, j["id"])
        if back:
            try:
                os.remove(q.p("send-back", j["id"]))
            except OSError:
                pass
        if (q.flag("STOP_NOW") or stop_asked(q, j["id"])) and not ok:
            dest = "stopped"
        elif back and not ok:
            # Not the job's fault, and not the end of it: stopped/ would read as
            # a failure to whatever waits on it (a crucible island counts three).
            with open(log, "a") as out:
                out.write("stopped by a person setting this machine or project aside: the job goes back on the queue\n")
            os.rename(j["_file"], q.p("queue", os.path.basename(j["_file"])))
            q.event("requeued", job=j["id"], host=name, why="sent back")
            return
        elif q.restarting and not ok:
            # The keeper restarts for new code: what it cut short runs again.
            with open(log, "a") as out:
                out.write("the keeper restarted for new code: the job goes back on the queue\n")
            os.rename(j["_file"], q.p("queue", os.path.basename(j["_file"])))
            q.event("requeued", job=j["id"], host=name, why="the keeper restarted for new code")
            return
        elif not ok and rc == 255 and j.get("ssh_tries", 0) < 3:
            # ssh's own failure: not the job's fault, whether or not the host answers a moment
            # later. It goes back on the queue for any host, its log kept, three times at most.
            with open(log, "a") as out:
                out.write("ssh failed (255): the job goes back on the queue\n")
            j2 = {k: v for k, v in j.items() if k != "_file"}
            j2["ssh_tries"] = j.get("ssh_tries", 0) + 1
            with open(j["_file"], "w") as f:
                json.dump(j2, f, indent=1)
            os.rename(j["_file"], q.p("queue", os.path.basename(j["_file"])))
            q.event("requeued", job=j["id"], host=name, why="host unreachable")
            return
        else:
            dest = "done" if ok else "failed"
        j2 = {k: v for k, v in j.items() if k != "_file"}
        j2.update({"host": name, "rc": rc, "seconds": round(now() - t0, 1), "ended": time.strftime("%Y-%m-%dT%H:%M:%S")})
        with open(j["_file"], "w") as f:
            json.dump(j2, f, indent=1)
        os.rename(j["_file"], q.p(dest, os.path.basename(j["_file"])))
        q.event(dest, job=j["id"], host=name, kind=j.get("kind"), seconds=j2["seconds"])
        if j.get("replan"):
            # A chain's step came back: its next is asked soon, not at the planner's next pass
            # (change B). A few seconds' grace gathers the returns of a burst into one pass.
            at = now() + q.config().get("replan_after_s", 15)
            q.replan_at = at if q.replan_at is None else min(q.replan_at, at)
        try:
            os.remove(q.p("stop-job", j["id"]))
        except OSError:
            pass
        # The breaker: failures in a row, any host, any kind.
        with q.lock:
            q.streak = q.streak + 1 if dest == "failed" else 0
        if dest == "done" and j.get("on_done"):
            env = dict(os.environ, JOB_ID=j["id"], RESULT_DIR=q.p("results", j["id"]))
            with open(log, "a") as out:
                subprocess.run(["bash", "-c", j["on_done"]], env=env, stdout=out, stderr=subprocess.STDOUT)


# ---- the keeper -----------------------------------------------------------------

def last_event_t(q):
    """The time of the last event written, read from the file's end -- passing over the asks that
    start this keeper (autostart, resume), which come after the cut and are not where it began."""
    try:
        with open(q.p("events.jsonl"), "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 8192))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("event") not in ("autostart", "resume", "resume adding"):
            return e.get("t")
    return None


def booted_at():
    """When this machine booted, as a keeper.json stamp."""
    try:
        if sys.platform == "darwin":
            m = re.search(r"sec = (\d+)", subprocess.run(["sysctl", "-n", "kern.boottime"], capture_output=True, text=True, timeout=10).stdout)
            t = int(m.group(1)) if m else None
        else:
            t = next(int(l.split()[1]) for l in open("/proc/stat") if l.startswith("btime"))
    except (OSError, subprocess.SubprocessError, StopIteration, ValueError):
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t)) if t else None


def keeper(q):
    cfg = q.config()
    # A KEEPER THAT NEVER ENDED LEFT ITS PID BEHIND. Every end the keeper makes (a stop, a drain, a
    # shutdown, an exception) removes keeper.pid in its finally; a power cut, a crash of the Mac or a
    # kill does not. So a keeper.pid naming another process, found by the keeper starting now, is the
    # mark of a cut: where it began (the last event written), when this Mac came back, and when the
    # keeper did, go to cut.json for the After a cut page (tools/boots.py). Its own pid is an exec.
    try:
        before = int(open(q.p("keeper.pid")).read())
    except (OSError, ValueError):
        before = None
    cut = before is not None and before != os.getpid()
    quiet = last_event_t(q) if cut else None
    with open(q.p("keeper.pid"), "w") as f:
        f.write(str(os.getpid()))
    q.procs = {}
    q.streak = 0
    # What the keeper before handed over, if it was this process (exec keeps the pid; a pid
    # from another process could name some other child): each job stays in running/ for its lane.
    try:
        hand = json.load(open(q.p("handover.json")))
        os.remove(q.p("handover.json"))
    except (OSError, ValueError):
        hand = {}
    if hand.get("keeper") == os.getpid():
        q.adopt = {e["host"]: e for e in hand.get("jobs", []) if os.path.exists(e["file"])}
    taken = {e["file"] for e in q.adopt.values()}
    # Jobs a keeper that died left running go back on the queue: their lanes
    # died with it.
    requeued = 0
    for j in q.jobs_in("running"):
        if j["_file"] in taken:
            continue
        os.rename(j["_file"], q.p("queue", os.path.basename(j["_file"])))
        q.event("requeued", job=j["id"], why="the keeper before this one died while it ran")
        requeued += 1
    if cut:
        rec = {"quiet_since": quiet, "keeper_back": time.strftime("%Y-%m-%dT%H:%M:%S"), "requeued": requeued,
               "mac_booted": booted_at(), "source": "keeper"}
        with open(q.p(".cut.json.tmp"), "w") as f:
            json.dump(rec, f, indent=1)
        os.replace(q.p(".cut.json.tmp"), q.p("cut.json"))
        q.event("came back after a cut", quiet_since=quiet, requeued=requeued)
    # Nothing is running now, so nothing is left to send back.
    for jid in os.listdir(q.p("send-back")):
        os.remove(q.p("send-back", jid))
    q.event("keeper started", pid=os.getpid())
    # A Mac running the keeper stays awake exactly while it runs: caffeinate
    # waits on the keeper's pid and ends with it (config "keep_awake": false
    # to leave the Mac to its own settings).
    awake = None
    # A keeper that restarted itself is the same process (exec keeps the
    # pid), so the caffeinate waiting on it still holds: it is kept.
    try:
        inherited = int(os.environ.pop("FLEET_QUEUE_AWAKE", ""))
        os.kill(inherited, 0)
        awake = inherited
    except (ValueError, OSError):
        pass
    if awake is None and sys.platform == "darwin" and cfg.get("keep_awake", True):
        try:
            awake = subprocess.Popen(["caffeinate", "-dimsu", "-w", str(os.getpid())], stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True).pid
        except OSError:
            awake = None
    life = {"pid": os.getpid(), "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "awake": awake,
            "last_plan": None, "last_plan_added": None, "last_sync": None, "sync_s": cfg.get("sync_s", 1800),
            "last_chores": None, "chores_said": None, "idle": None, "last_boots": None, "boots_said": None,
            # The code it runs: health() sets it against the file on disk.
            "code": code_id(), "file": os.path.abspath(__file__),
            "restart_lose_s": cfg.get("restart_lose_s", 600)}

    # A spell of idle lanes goes on across the keeper's own restart (the same pid): one flag, not two.
    prev = load_json(q.p("keeper.json")) or {}
    if prev.get("pid") == os.getpid() and prev.get("idle"):
        life["idle"] = prev["idle"]

    def tell():
        with open(q.p(".keeper.json.tmp"), "w") as f:
            json.dump(life, f)
        os.replace(q.p(".keeper.json.tmp"), q.p("keeper.json"))
    alive = threading.Event()
    alive.set()
    threads = {}
    planner = cfg.get("planner")
    low = cfg.get("low_water", 2 * len(cfg["hosts"]))
    poll = cfg.get("poll_s", 10)

    def plan(n):
        took_from = now()
        # A PASS HOLDS THE BEAT: the planner runs in this loop, so the beat waits on it, and a pass
        # had come to 53-65 s against health's 60 (8 November: heartbeat BAD at every pass, a stuck
        # loop to anyone reading it, the keeper well). The pass says when it began, for health, and
        # the stamp stays until the next beat (the loop's top), because the beat waits on what follows
        # the pass too: 11:20 that day, a 64 s pass, 10 s adding its five jobs, then the poll's sleep.
        life["planning_since"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        tell()
        r = subprocess.run(["bash", "-c", "%s plan %d" % (planner, n)], capture_output=True, text=True, timeout=PLAN_TIMEOUT_S)
        life["last_plan_s"] = round(now() - took_from, 1)
        if r.returncode != 0:
            q.event("planner failed", detail=(r.stderr or r.stdout)[-400:])
            q.notice("planner", "the planner failed: " + (r.stderr or r.stdout).strip()[-200:])
            return
        life["last_plan"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        added = 0
        for job in json.loads(r.stdout or "[]"):
            if q.add(job):
                added += 1
        life["last_plan_added"] = added
        if added:
            q.event("planned", added=added, seconds=life["last_plan_s"])

    def collect():
        if planner:
            r = subprocess.run(["bash", "-c", "%s collect" % planner], capture_output=True, text=True, timeout=3600)
            q.event("collected", detail=(r.stdout or r.stderr)[-400:])

    syncing = threading.Lock()

    def sync():
        # On its own thread, one at a time: gathering is slow and must not
        # hold the keeper.
        if not planner or not syncing.acquire(blocking=False):
            return
        try:
            r = subprocess.run(["bash", "-c", "%s sync" % planner], capture_output=True, text=True, timeout=3600)
            q.event("synced" if r.returncode == 0 else "sync failed", detail=(r.stdout or r.stderr)[-400:])
            life["last_sync"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            if r.returncode != 0:
                q.notice("sync", "the sync failed: " + (r.stderr or r.stdout).strip()[-200:])
        except subprocess.TimeoutExpired:
            q.event("sync failed", detail="timed out")
        finally:
            syncing.release()

    chore_lock = threading.Lock()

    def chores():
        # THE HOUSEKEEPING IS THE KEEPER'S (the lab report of 4 November, change C). The Results and
        # Analysis pages' documents and the recordings' sweep were begun by the window, so a closed
        # window let the disks fill and opening one began everything at once. The planner's `chores`
        # says what is stale and begins it in the background; this only asks, on its own thread.
        if not planner or not chore_lock.acquire(blocking=False):
            return
        try:
            r = subprocess.run(["bash", "-c", "%s chores" % planner], capture_output=True, text=True, timeout=300)
            life["last_chores"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            life["chores_said"] = (r.stdout or "").strip()[-300:] or None
            if r.returncode != 0:
                said = (r.stderr or r.stdout).strip()
                q.event("chores failed", detail=said[-400:])
                q.notice("chores", "the housekeeping failed: " + (said.splitlines() or ["?"])[-1][-200:])
        except subprocess.TimeoutExpired:
            q.event("chores failed", detail="timed out")
        finally:
            chore_lock.release()

    boots_lock = threading.Lock()
    boots_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "boots.py")

    def boots():
        # AFTER A CUT THE CHECKS ARE THE KEEPER'S (Paul, 8 November: "The actions we are doing after a
        # power loss, should be done auto, with GUI buttons"). tools/boots.py reads a machine once a
        # boot -- the firmware against the boot before, the islands' saves, the queue's own files --
        # so asking often costs a boot id a machine. Asked at the start, soon after a machine that
        # could not be reached answers, and each boots_s.
        if not os.path.exists(boots_py) or not boots_lock.acquire(blocking=False):
            return
        try:
            r = subprocess.run([sys.executable, "-I", boots_py, q.d, "check"], capture_output=True, text=True, timeout=900)
            life["last_boots"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            life["boots_said"] = (r.stdout or r.stderr or "").strip()[-300:] or None
            if r.returncode != 0:
                q.event("boots failed", detail=(r.stderr or r.stdout)[-400:])
        except subprocess.TimeoutExpired:
            q.event("boots failed", detail="timed out")
        finally:
            boots_lock.release()

    boots_s = cfg.get("boots_s", 600)
    last_boots = 0.0
    chores_s = cfg.get("chores_s", 60)
    last_chores = 0.0
    sync_s = cfg.get("sync_s", 1800)
    last_sync = 0.0
    # A run asked for (DIR/runs/) is planned at once, not at the low-water mark.
    runs_seen = 0.0
    planned_at = 0.0
    plan_s = cfg.get("plan_s", 300)
    # A lane idle with nothing it can start asks for work each starve_s,
    # however long the queue (starved()).
    starve_s = cfg.get("starve_s", 60)
    told_hungry = []
    code_seen = (life["code"], os.stat(__file__).st_mtime if os.path.exists(__file__) else 0)

    def restart(why):
        # THE KEEPER RESTARTS ITSELF ON NEW CODE. A keeper started at 12:28
        # ran 12:28's code until 21:20, and the fix made at 14:29 waited for
        # "its next start" all evening. The process execs itself: the same
        # pid, so keeper.pid and the caffeinate hold.
        #
        # AND IT KEEPS ITS JOBS (4 November). It stopped every running job and
        # ran it again from the start: 132 jobs and 7.7 machine-hours in the
        # week to 4 November. Now no lane takes more work, each finishes what is
        # not its command (a send, a fetch) or parks on its command, and the
        # running jobs are written down, pid and all (handover.json), for the
        # new keeper, whose children they still are. A lane still busy after 90
        # seconds is cut off as before, and its job runs again.
        q.restarting = True
        q.event("keeper restarting", why=why)
        alive.clear()
        with q.hand_lock:
            q.handing = True
        until = now() + 90
        while now() < until:
            with q.hand_lock:
                parked = set(q.parked)
            if all(not t.is_alive() or n in parked for n, t in threads.items()):
                break
            time.sleep(0.5)
        with q.hand_lock:
            jobs = [{"id": jid, "pid": child.pid, "host": name, "file": f, "t0": t0}
                    for jid, (child, host) in q.procs.items() if jid in q.started
                    for t0, f, name in [q.started[jid]]]
        with open(q.p(".handover.json.tmp"), "w") as f:
            json.dump({"keeper": os.getpid(), "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "jobs": jobs}, f)
        os.replace(q.p(".handover.json.tmp"), q.p("handover.json"))
        q.event("handed over", jobs=[j["id"] for j in jobs])
        # restart-check.sh's knob (config "handover_hold_s", 0): the handover held open, so that
        # a job can end inside it and be read from its exit by the new keeper.
        time.sleep(q.config().get("handover_hold_s", 0))
        try:
            os.remove(q.p("RESTART"))
        except OSError:
            pass
        sys.stdout.flush()
        sys.stderr.flush()
        env = dict(os.environ, FLEET_QUEUE_AWAKE=str(awake or ""))
        os.execve(sys.executable, [sys.executable, os.path.abspath(__file__), q.d, "start"], env)

    try:
        while True:
            with open(q.p("keeper.beat"), "w") as f:
                f.write(str(now()))
            life["beat"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            life.pop("planning_since", None)
            life["next_sync"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(last_sync + sync_s)) if last_sync and sync_s else None
            tell()
            if q.flag("SHUTDOWN"):
                # Each lane powers its host off after the job in hand; when
                # none is left the keeper reports and ends.
                if not any(t.is_alive() for t in threads.values()) and not q.jobs_in("running"):
                    collect()
                    report = shutdown_report(q)
                    q.event("shut down", detail=report["summary"])
                    q.notice("shutdown", "the fleet shut down: " + report["summary"])
                    break
                time.sleep(poll)
                continue
            if planner and sync_s and now() - last_sync > sync_s:
                last_sync = now()
                threading.Thread(target=sync, daemon=True).start()
            if planner and chores_s and now() - last_chores > chores_s:
                last_chores = now()
                threading.Thread(target=chores, daemon=True).start()
            if boots_s and (now() - last_boots > boots_s or (q.boots_at is not None and now() >= q.boots_at)):
                last_boots = now()
                q.boots_at = None
                threading.Thread(target=boots, daemon=True).start()
            # A machine finishing leaves once its lanes are empty; then a job pinned to a machine
            # that left or paused moves where it may, or is flagged.
            leave_when_done(q)
            restart_when_done(q)
            rehome(q, q.config())
            # Keep a lane alive for every host; one that died is started again.
            for h in q.config()["hosts"]:
                t = threads.get(h["name"])
                if t is None or not t.is_alive():
                    if t is not None:
                        q.event("lane restarted", host=h["name"])
                    t = threading.Thread(target=lane, args=(q, h, alive), daemon=True)
                    t.start()
                    threads[h["name"]] = t
            # One job stopped (`stop-job`): its lane sees why, files it under stopped/ and goes
            # on. A job not started yet is its lane's to skip, and one past its command finishes.
            for jid in os.listdir(q.p("stop-job")):
                if jid in q.procs:
                    p, host = q.procs[jid]
                    q.event("stopping job", job=jid, host=host["name"])
                    stop_remote(host, jid)
                    p.terminate()
            for jid in os.listdir(q.p("send-back")):
                if jid in q.procs:
                    p, host = q.procs[jid]
                    q.event("sending job back", job=jid, host=host["name"])
                    stop_remote(host, jid)
                    p.terminate()
            if q.flag("STOP_NOW"):
                q.event("stopping now")
                alive.clear()
                for jid, (p, host) in list(q.procs.items()):
                    stop_remote(host, jid)
                    p.terminate()
                for t in threads.values():
                    t.join(timeout=60)
                # What was running goes to stopped/, its log kept.
                for j in q.jobs_in("running"):
                    os.rename(j["_file"], q.p("stopped", os.path.basename(j["_file"])))
                collect()
                q.event("stopped")
                break
            # THE BREAKER. A job that fails at once empties the queue as fast
            # as the planner fills it; after this many failures in a row the
            # keeper stops adding and says so (converge stops after three).
            limit = cfg.get("max_failures_in_a_row", 5)
            # THE BREAKER RESETS ITSELF, ONCE (Paul, 4 November: "what step of a human is required.
            # automate this please"). Its stop is marked as the breaker's, so a person's Stop adding is
            # never lifted by it. After breaker_resume_min (30) the queue adds again; a breaker that trips
            # again within two hours of resetting itself stays off, since then the cause is real and a
            # person reads logs/. A breaker's stop does not end the keeper when the queue drains.
            breaker_file = q.p("breaker.json")
            if q.streak >= limit and not q.flag("STOP_ADDING"):
                with open(q.p("STOP_ADDING"), "w") as f:
                    f.write("breaker %d\n" % int(time.time()))
                q.event("stop adding", why="%d jobs failed in a row: the breaker; it resets itself in %d min unless it tripped within two hours of its last reset"
                        % (q.streak, cfg.get("breaker_resume_min", 30)))
                q.notice("breaker", "%d jobs failed in a row: the queue stopped adding; it adds again by itself in %d minutes, unless it trips again soon after (read logs/)"
                         % (q.streak, cfg.get("breaker_resume_min", 30)))
            resume_s = 60 * cfg.get("breaker_resume_min", 30)
            if resume_s > 0 and breaker_stop(q) and time.time() - os.path.getmtime(q.p("STOP_ADDING")) >= resume_s:
                last_reset = (load_json(breaker_file) or {}).get("reset_at", 0)
                if time.time() - last_reset < 2 * 3600:
                    if not life.get("breaker_told"):
                        q.event("breaker stays off", why="it tripped again within two hours of resetting itself")
                        q.notice("breaker", "the breaker tripped again within two hours of resetting itself: it stays off until a person resumes adding (read logs/)")
                        life["breaker_told"] = True
                else:
                    try:
                        os.remove(q.p("STOP_ADDING"))
                    except OSError:
                        pass
                    q.streak = 0
                    life["breaker_told"] = False
                    with open(breaker_file, "w") as f:
                        json.dump({"reset_at": time.time()}, f)
                    q.event("resume adding", why="the breaker reset itself after %d min" % (resume_s // 60))
                    q.notice("breaker", "the queue adds again by itself, %d minutes after the breaker" % (resume_s // 60))
            # New code on disk: the keeper restarts at its next beat, its jobs
            # handed over (restart()), or at once when a person pressed
            # Restart (DIR/RESTART). Not while a lane delivers or fetches: a
            # transfer is not a process the new keeper can take up.
            try:
                mtime = os.stat(__file__).st_mtime
            except OSError:
                mtime = code_seen[1]
            if mtime != code_seen[1]:
                code_seen = (code_id() or code_seen[0], mtime)
            stale = code_seen[0] != life["code"]
            life["code_on_disk"] = code_seen[0]
            if q.flag("RESTART"):
                restart("Restart was pressed")
            if stale:
                moving = [l for l in (lane_file(q, h["name"]) for h in q.config()["hosts"]) if l.get("state") in ("delivering", "fetching")]
                if not moving:
                    restart("new code on disk (%s, was %s)" % (code_seen[0], life["code"]))
            waiting_jobs = q.jobs_in("queue")
            queued = len(waiting_jobs)
            running = len(q.jobs_in("running"))
            cfg_now = q.config()
            cpu_q = cpu_queued(cfg_now, waiting_jobs)
            # The low water is the CPU's (A), with a few seconds between passes so a planner that has
            # nothing to add is not asked each poll; a chain's step back asks too (B).
            gap = time.time() - planned_at
            short = cpu_q is not None and cpu_q < low and gap > cfg_now.get("low_min_s", 20)
            chain = q.replan_at is not None and now() >= q.replan_at and gap > cfg_now.get("replan_min_s", 5)
            hungry = starved(q, q.config()) if planner and not q.flag("STOP_ADDING") else []
            life["starved"] = hungry
            # A FLEET WITH NOTHING TO DO SAYS SO (change D): once a spell, with the reason it can see.
            idle, since = idle_lanes(q, q.config()) if hungry else ([], None)
            spell = life.get("idle")
            if idle:
                # One flag a spell, keyed by the moment it was seen (two spells may share a lane's
                # since); its reason read again each minute (it reads every finished job), and at once
                # when the lanes change.
                spell = spell or {"key": "idle:%d" % now(), "since": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(since)),
                                  "lanes": [], "at": 0}
                spell["quiet"] = None
                if now() - spell["at"] > 60 or spell["lanes"] != idle:
                    spell.update(lanes=idle, why=idle_reason(q, q.config(), idle, life), at=now())
                    q.notice("idle", "%d CPU lane%s idle since %s with nothing they can start (%s): %s" % (
                        len(idle), "" if len(idle) == 1 else "s", spell["since"][11:16], ", ".join(idle), spell["why"]), key=spell["key"])
                life["idle"] = spell
            elif spell:
                # It ends when no CPU lane has been idle with nothing for idle_end_s (60): a job
                # queued and taken in the same second is not the end of it.
                spell["quiet"] = spell.get("quiet") or now()
                if now() - spell["quiet"] >= q.config().get("idle_end_s", 60):
                    q.event("idle lanes at work again", lanes=spell["lanes"], since=spell["since"])
                    life["idle"] = None
            if q.flag("STOP_ADDING"):
                # The breaker's stop waits to reset itself: the keeper stays up. A person's stop drains and ends.
                if queued == 0 and running == 0 and not breaker_stop(q):
                    collect()
                    q.event("drained")
                    alive.clear()
                    break
            elif planner and (short or chain or runs_mtime(q) > runs_seen or time.time() - planned_at > plan_s
                              or (hungry and time.time() - planned_at > starve_s)):
                # Also every plan_s (300 s) whatever the queue's length, so
                # auto mode's promotions and the rotation never wait for it
                # to drain; and each starve_s while a lane is idle with
                # nothing it can start (starved()). Plan now touches runs/.
                if hungry and not short and hungry != told_hungry:
                    q.event("planning for idle lanes", hosts=hungry, queued=queued)
                told_hungry = hungry
                runs_seen = runs_mtime(q)
                planned_at = time.time()
                if chain:
                    life["last_replan"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                # Asked before the pass: a step that comes back during it asks for the next one.
                q.replan_at = None
                try:
                    plan(max(2 * low - (cpu_q if cpu_q is not None else queued), low))
                except (subprocess.TimeoutExpired, ValueError) as e:
                    q.event("planner failed", detail=str(e))
            time.sleep(poll)
    finally:
        alive.clear()
        try:
            os.remove(q.p("keeper.pid"))
        except OSError:
            pass


def runs_mtime(q):
    try:
        return os.stat(q.p("runs")).st_mtime
    except OSError:
        return 0.0


def shutdown_report(q):
    """Who finished what, and what was left: DIR/shutdown.json."""
    ev = [json.loads(l) for l in open(q.p("events.jsonl"))]
    t0 = max((e["t"] for e in ev if e.get("event") == "shutdown now"), default="")
    hosts = {}
    for h in q.config()["hosts"]:
        mine = [e for e in ev if e.get("host") == h["name"]]
        last = [e for e in mine if e.get("event") in ("done", "failed", "stopped")]
        end = [e for e in mine if e["t"] >= t0 and e.get("event") in ("powered off", "left running", "poweroff failed")]
        hosts[h["name"]] = {"last_job": last[-1]["job"] if last else None, "last_result": last[-1]["event"] if last else None,
                            "finished_at": last[-1]["t"] if last else None,
                            "power": end[-1]["event"] if end else "unknown",
                            "reported": any(e.get("event") == "reported" and e["t"] >= t0 for e in mine)}
    left = [j["id"] for j in q.jobs_in("queue")]
    report = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "asked": t0, "hosts": hosts, "left_on_the_queue": left,
              "summary": "; ".join("%s: %s, %s" % (n, h["last_job"] or "nothing", h["power"]) for n, h in hosts.items())
              + "; %d jobs never started" % len(left)}
    with open(q.p("shutdown.json"), "w") as f:
        json.dump(report, f, indent=1)
    return report


def keeper_alive(q):
    """The running keeper's pid, or None. A LIVE PID IS NOT A KEEPER: keeper.pid outlives a keeper
    the power took (its finally never ran), and after the reboot that number may be any process's,
    which read as "the keeper is running" would start none -- the one thing a console opened after
    a cut must not get wrong. So the pid's command must be this file's."""
    try:
        pid = int(open(q.p("keeper.pid")).read())
        os.kill(pid, 0)
    except (OSError, ValueError):
        return None
    try:
        cmd = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return pid
    return pid if os.path.basename(__file__) in cmd else None


# The planner's timeout: a pass longer than this is ended, and health counts a beat held up to this
# long (and heartbeat_s more) by a pass as the keeper working.
PLAN_TIMEOUT_S = 600


def took(s):
    s = int(s)
    return "%d h %02d m" % (s // 3600, s // 60 % 60) if s >= 3600 else "%d min" % (s // 60) if s >= 60 else "%d s" % s


def stamp_age(t):
    """Seconds since a keeper.json stamp (local time), or None."""
    try:
        return now() - time.mktime(time.strptime(t, "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None


def health(q):
    """Is it running as it should? Each check a level (ok, warn, bad), a name
    and a sentence, for the console's Settings page and `health`. Nothing is
    fixed here: the keeper fixes what it can by itself (plans for idle
    lanes, restarts on new code), and what is left is a button."""
    cfg = q.config()
    pid = keeper_alive(q)
    out = []

    def check(level, name, text):
        out.append({"level": level, "name": name, "text": text})
    info = {}
    if pid:
        try:
            info = json.load(open(q.p("keeper.json")))
        except (OSError, ValueError):
            pass
    lanes = {h["name"]: lane_file(q, h["name"]) for h in cfg["hosts"]}
    running = [(n, l) for n, l in lanes.items() if l.get("job")]
    oldest = max(running, key=lambda r: now() - r[1].get("since", now()), default=None)
    if not pid:
        check("bad", "keeper", "no keeper is running: nothing starts (Resume the queue)")
        return out
    check("ok", "keeper", "pid %d since %s" % (pid, (info.get("started") or "?")[11:16]))
    beat = stamp_age(info.get("beat"))
    poll = cfg.get("poll_s", 10)
    beat_s = cfg.get("heartbeat_s", max(60, 6 * poll))
    pass_s = stamp_age(info.get("planning_since"))
    if beat is not None and beat <= beat_s:
        check("ok", "heartbeat", "last beat %s ago" % took(beat))
    elif beat is not None and pass_s is not None and pass_s <= PLAN_TIMEOUT_S + beat_s:
        # A planner pass began since the last beat (plan()), and the planner's own timeout ends it:
        # no beat until the pass, its jobs added and the poll's sleep are over is the keeper working.
        # Past that timeout it is stuck after all.
        check("ok", "heartbeat", "last beat %s ago: a planner pass, begun %s ago, holds it" % (took(beat), took(pass_s)))
    else:
        check("bad", "heartbeat", "no beat for %s: the keeper is alive but its loop is stuck" % took(beat or 0))
    # The operator's certificate (the plan of 2 November, chapter 14: a warning before it expires). An
    # expired one once dialled every machine and had this Mac penalised for a day before anyone knew.
    for cert in sorted(glob.glob(os.path.expanduser("~/.copal/fleets/*/operator-cert.pub"))):
        fleet = os.path.basename(os.path.dirname(cert))
        try:
            said = subprocess.run(["ssh-keygen", "-L", "-f", cert], capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.TimeoutExpired):
            continue
        m = re.search(r"Valid: from \S+ to (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)", said)
        if not m:
            continue
        left = time.mktime(time.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")) - now()
        if left <= 0:
            check("bad", "certificate", "%s's operator certificate expired at %s: every button and the chat room fail until Renew (Fleet)" % (fleet, m.group(1)[11:16]))
        elif left < 24 * 3600:
            check("warn", "certificate", "%s's operator certificate runs out in %s, at %s: Renew it (Fleet) before then" % (fleet, took(left), m.group(1).replace("T", " ")))
        else:
            check("ok", "certificate", "%s's operator certificate is good for %s" % (fleet, took(left)))
    disk = code_id()
    lose = info.get("restart_lose_s", 600)
    held = ("; %s's %s is %s in" % (oldest[0], oldest[1].get("title") or oldest[1]["job"], took(now() - oldest[1]["since"]))
            if oldest and now() - oldest[1].get("since", now()) >= lose else "")
    if info.get("code"):
        if info["code"] == disk:
            check("ok", "code", "it runs the code on disk (%s)" % disk)
        else:
            check("warn", "code", "it runs older code (%s, the file is %s): it restarts itself, its running jobs carried "
                  "on, once no lane is delivering or fetching, or press Restart the keeper" % (info["code"], disk))
    else:
        changed = os.stat(__file__).st_mtime
        started = stamp_age(info.get("started"))
        if started is not None and now() - started < changed:
            check("warn", "code", "it started at %s, before the file changed at %s, and is too old to restart "
                  "itself: press Restart the keeper%s" % (info["started"][11:16], time.strftime("%H:%M", time.localtime(changed)), held))
        else:
            check("ok", "code", "it started after the file last changed")
    events = []
    try:
        events = [json.loads(l) for l in open(q.p("events.jsonl")).readlines()[-400:]]
    except (OSError, ValueError):
        pass
    plan_s = cfg.get("plan_s", 300)
    planned = stamp_age(info.get("last_plan"))
    failed = [e for e in events if e.get("event") == "planner failed" and (info.get("last_plan") or "") < e["t"]]
    if failed:
        check("bad", "planning", "the planner failed at %s: %s" % (failed[-1]["t"][11:16], (failed[-1].get("detail") or "")[-160:]))
    elif q.flag("STOP_ADDING"):
        check("warn", "planning", "adding nothing: the queue drains (Resume adding)")
    elif planned is None or planned > 2 * plan_s + 60:
        check("warn", "planning", "last asked the planner %s ago" % (took(planned) if planned is not None else "never"))
    else:
        extra = ""
        if info.get("last_plan_s") is not None:
            extra += "; a pass takes %s" % took(info["last_plan_s"])
        back = stamp_age(info.get("last_replan"))
        if back is not None:
            extra += "; a chain's step last asked for one %s ago" % took(back)
        check("ok", "planning", "last asked the planner %s ago%s" % (took(planned), extra))
    sync_s = cfg.get("sync_s", 1800)
    synced = stamp_age(info.get("last_sync"))
    if not sync_s:
        check("ok", "sync", "sync_s is 0: the keeper gathers nothing by itself")
    elif synced is None or synced > sync_s + 600:
        check("warn", "sync", "last gathered the machines' records %s ago" % (took(synced) if synced is not None else "never"))
    else:
        check("ok", "sync", "last gathered %s ago" % took(synced or 0))
    chores_s = cfg.get("chores_s", 60)
    chored = stamp_age(info.get("last_chores"))
    if cfg.get("planner") and chores_s:
        if chored is None or chored > chores_s + 600:
            check("warn", "chores", "the housekeeping (the pages' documents, the recordings' sweep) last asked %s" % (
                "%s ago" % took(chored) if chored is not None else "never: a keeper older than the chores"))
        else:
            check("ok", "chores", "the housekeeping asked %s ago%s" % (took(chored), ": " + info["chores_said"] if info.get("chores_said") else ""))
    # After a cut (tools/boots.py): a machine back different, an island's save that did not reach its
    # disk, a queue file that does not read back. The record says its own level.
    rec = load_json(q.p("plan", "boots.json")) or {}
    if rec.get("health"):
        lv, text = rec["health"][0], rec["health"][1]
        age = stamp_age(rec.get("checked"))
        stale = age is not None and age > max(1800, 3 * cfg.get("boots_s", 600))
        check(lv if lv in ("ok", "warn", "bad") else "warn", "boots", text + (" (read %s ago)" % took(age) if stale else ""))
    elif os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "boots.py")):
        check("warn", "boots", "no machine read since its boot yet: the keeper asks tools/boots.py at its start")
    if info.get("awake") is not None or sys.platform == "darwin":
        try:
            os.kill(int(info.get("awake")), 0)
            check("ok", "awake", "caffeinate %d holds this Mac awake" % info["awake"])
        except (TypeError, ValueError, OSError):
            check("warn" if cfg.get("keep_awake", True) else "ok", "awake", "nothing holds this Mac awake" if cfg.get("keep_awake", True) else "keep_awake is off")
    down = [n for n, l in lanes.items() if l.get("state") == "unreachable"]
    if down:
        check("bad", "machines", "cannot be reached, its lane waiting: %s" % ", ".join(down))
    else:
        check("ok", "machines", "every machine answers")
    aside = sorted({h.get("lane_of", h["name"]) for h in cfg["hosts"] if h.get("paused")})
    if aside:
        check("ok", "paused", "set aside by a person, until Resume: %s" % ", ".join(aside))
    if cfg.get("paused_projects"):
        check("ok", "paused", "projects paused on every machine: %s" % ", ".join(cfg["paused_projects"]))
    hungry = starved(q, cfg)
    idle, since = idle_lanes(q, cfg) if hungry else ([], None)
    if idle:
        check("bad", "lanes", "idle %s with nothing they can start: %s; %s" % (
            took(now() - since), ", ".join(idle), (info.get("idle") or {}).get("why") or idle_reason(q, cfg, idle, info)))
    elif hungry:
        check("warn", "lanes", "idle with nothing they can start: %s (the keeper asks the planner for them each %s)"
              % (", ".join(hungry), took(cfg.get("starve_s", 60))))
    else:
        check("ok", "lanes", "%d of %d running; every idle lane has work it can start" % (len(running), len(lanes)))
    # The jobs no lane can take: needs no machine has, or one machine only
    # (a build for it, say) and that machine an hour into something else.
    # A job pinned to a machine a person removed is not lost but kept: a GPU island's segments wait
    # on the island's own disk, and run in order when Add brings the machine back. Said, not BAD.
    done = q.ids_in("done")
    benched = {b["name"] for b in cfg.get("bench", [])}
    nobody, behind, kept = [], {}, {}
    for j in q.jobs_in("queue"):
        can = [h for h in cfg["hosts"] if fits(h, j)]
        need = j.get("needs", "cpu")
        if not can and need.startswith("host:") and need[5:] in benched:
            kept.setdefault(need[5:], []).append(j["id"])
        elif not can:
            nobody.append(j["id"])
        elif len(can) == 1 and ready(can[0], j, done):
            behind.setdefault(can[0]["name"], []).append(j["id"])
    if nobody:
        check("bad", "jobs", "%d queued that no machine can take (%s): their needs match no lane" % (len(nobody), ", ".join(nobody[:4])))
    if kept:
        check("ok", "aside", "; ".join("%d kept for %s, which a person removed: they run when Add brings it back" % (len(v), n)
                                       for n, v in sorted(kept.items())))
    waits = ["%d behind %s's %s (%s in)" % (len(v), n, lanes[n].get("title") or lanes[n]["job"], took(now() - lanes[n]["since"]))
             for n, v in sorted(behind.items()) if lanes[n].get("job") and now() - lanes[n].get("since", now()) > 3600]
    if waits:
        check("warn", "jobs", "waiting for one machine, busy over an hour: " + "; ".join(waits))
    elif not nobody:
        check("ok", "jobs", "every queued job has a machine it can run on")
    # The search, as the planner last saw it (plan/search.json): busy lanes
    # are not finding. Widening is the planner's own; a search still dry at
    # three times the stall wants what a planner cannot do, a change to the
    # brain.
    s = {}
    try:
        s = json.load(open(q.p("plan", "search.json")))
    except (OSError, ValueError):
        pass
    if s:
        last = ("the last find %s, %d trials ago" % (s["last_find"], s["since_find"]) if s.get("last_find")
                else "nothing found in %d" % s["since_find"])
        said = "%d trials on today's defaults, %d different (%d repeats not asked); %s" % (
            s.get("reads", 0), s.get("distinct", 0), s.get("repeats", 0), last)
        q_ = s.get("sequential") or {}
        if q_:
            said += "; read on until decided: %d reading, %d to read on, %d dropped, %d passed to the held-out reads%s" % (
                q_.get("reading", 0), q_.get("read on", 0), q_.get("dropped", 0), q_.get("passed", 0),
                ", %d seeds a decision" % q_["seeds_a_decision"] if q_.get("seeds_a_decision") else "")
        if s.get("ab"):
            said += "; A/B %d of %d versions asked on today's defaults" % (s["ab"]["versions"] - s["ab"]["left"], s["ab"]["versions"])
        stall = s.get("stall", 150)
        if s.get("stalled") and s.get("reads", 0) - s.get("widened_at", s.get("reads", 0)) >= 3 * stall:
            check("warn", "search", said + ": dry %d trials since it widened, the next gain wants a change to the brain itself"
                  % (s["reads"] - s["widened_at"]))
        elif s.get("stalled"):
            check("ok", "search", said + ": widened (the fit reaches %s doublings, and one wide trial a generation)" % s.get("bound"))
        else:
            check("ok", "search", said)
    # The line: generations carried, not yet proven past main.
    try:
        p = json.load(open(q.p("plan", "pipeline.json")))
        if p.get("line", {}).get("promotions"):
            check("ok", "line", "%d generation(s) carried on the line at %s; last proof %s" % (
                p["line"]["promotions"], p["line"].get("commit"), json.dumps(p.get("proof")) if p.get("proof") else "not yet read"))
    except (OSError, ValueError):
        pass
    # The model slots (plan treadcore's models/models.tsv): the league of
    # learned brains the A/B reads against the rules, by generation.
    try:
        rows = [l.split("\t") for l in open(q.p("models", "models.tsv")).read().splitlines()[1:] if l.strip()]
    except OSError:
        rows = []
    if rows:
        check("ok", "models", "%d of 7 slots, generation %s the newest: %s" % (
            len(rows), max(int(r[2]) for r in rows), ", ".join("%s %s" % (r[0], r[1]) for r in rows)))
    # The difficulty: how far every bar is lowered, so a promotion comes
    # about every every_min. At its floor and a promotion twice overdue, the
    # trials hold no more at any bar a promotion should pass.
    d = s.get("difficulty") or {}
    if d.get("since"):
        every = d.get("every_min", 240)
        ago = (now() - d["since"]) / 60
        # The bar's own words: since 13 November it stands (its ease and its ceiling are one number) and
        # "easier after 4 h dry" was no longer true of it; and "since the last" is since the bar last
        # moved, which a line coming off also does, so it is not called a generation.
        pinned = d.get("ease", 0) >= d.get("floor", 3.0) - 0.051
        said = "the bar: a generation passes at held-out z %.2f; %s since it last moved, %d step(s) this run; %s" % (
            d.get("held_z", 3), took(ago * 60), d.get("generations", 0),
            "it stands there: a dry spell widens the search and does not lower it" if pinned else "harder each generation, easier after 4 h dry")
        if d.get("ease", 0) >= d.get("floor", 3.0) and ago > 480:
            check("warn", "difficulty", said + ": at its easiest and nothing found: the brain itself needs a change")
        else:
            check("ok", "difficulty", said)
    return out


def restart_cost(q):
    """What Restart the keeper carries across: the jobs running, handed over to the new keeper (a lane
    still delivering or fetching after 90 seconds is cut off, and its job runs again)."""
    rows = []
    for h in q.config()["hosts"]:
        l = lane_file(q, h["name"])
        if l.get("job"):
            rows.append((now() - l.get("since", now()), l.get("title") or l["job"], h["name"]))
    rows.sort(reverse=True)
    return {"jobs": len(rows), "oldest": ("%s's %s, %s in" % (rows[0][2], rows[0][1], took(rows[0][0]))) if rows else ""}


def roster(q, cfg, pid):
    """A row a machine, whatever its lanes: in the queue, on the bench (it was removed),
    or only registered (machines.json). What the buttons act on, and absent nothing:
    a machine must be findable to be added."""
    try:
        reg = json.load(open(q.p("machines.json")))
    except (OSError, ValueError):
        reg = {}
    ps = projects_of(cfg)
    rows, seen = [], set()
    for h in cfg["hosts"] + cfg.get("bench", []) + [{"name": n, "target": m.get("target", "")} for n, m in reg.items()]:
        name = h.get("lane_of", h["name"])
        if name in seen or (h.get("name", "").endswith("-cuda") and "lane_of" not in h):
            continue
        seen.add(name)
        ls = [x for x in cfg["hosts"] if name in (x["name"], x.get("lane_of"))]
        jobs = []
        for x in ls:
            l = lane_file(q, x["name"])
            if pid and l.get("job"):
                jobs.append({"lane": x["name"], "job": l["job"], "kind": l.get("kind"), "title": l.get("title"),
                             "state": l.get("state"), "age_s": int(now() - l.get("since", now()))})
        states = [lane_file(q, x["name"]).get("state") for x in ls]
        paused = bool(ls) and all(x.get("paused") for x in ls)
        leaving = any(x.get("leaving") for x in ls)
        restarting = next((x["restarting"] for x in ls if x.get("restarting")), None)
        word = ("not in the queue" if not ls else
                "leaving" if leaving else
                ("restarting" if restarting.get("stage") == "sent" else "restarting after its job") if restarting else
                "stopping" if paused and jobs else
                "paused" if paused else
                "no keeper" if not pid else
                "running" if jobs else
                "cannot be reached" if "unreachable" in states else
                "idle")
        on = {}
        for p, d in ps.items():
            able = [x for x in ls if d.get("caps", "cpu") in x.get("caps", ["cpu"])]
            on[p] = None if not able else not all(p in x.get("off", ()) for x in able)
        benched = any(name in (b["name"], b.get("lane_of")) for b in cfg.get("bench", []))
        cpu_lanes = [x for x in ls if "cuda" not in x.get("caps", [])]
        rows.append({"name": name, "target": h.get("target", ""), "state": word, "joined": bool(ls), "bench": benched,
                     "paused": paused, "leaving": leaving, "restarting": bool(restarting),
                     # Whether Restart can reboot it: its restart rule, copied from the probe.
                     "can_restart": any(x.get("reboot") for x in ls if not x.get("lane_of")),
                     "jobs": jobs, "on": on,
                     "cpus": next((x["cpus"] for x in cpu_lanes if x.get("cpus")), None),
                     "cores": int(((reg.get(name) or {}).get("facts") or {}).get("cpus") or 0) or None})
    return rows


def status(q):
    cfg = q.config()
    lanes = []
    for h in cfg["hosts"]:
        try:
            with open(q.p("lanes", h["name"] + ".json")) as f:
                l = json.load(f)
        except (OSError, ValueError):
            l = {"host": h["name"], "state": "not started"}
        if l.get("since"):
            l["age_s"] = int(now() - l["since"])
        l["caps"] = h.get("caps", ["cpu"])
        lanes.append(l)
    counts = {}
    for sub in ("queue", "running", "done", "failed", "stopped"):
        for j in q.jobs_in(sub):
            k = j.get("kind", "job")
            counts.setdefault(k, {}).setdefault(sub, 0)
            counts[k][sub] += 1
    pid = keeper_alive(q)
    state = ("stopping now" if q.flag("STOP_NOW") and pid else
             "shutting down: each machine finishes, reports, powers off" if q.flag("SHUTDOWN") and pid else
             "shut down" if q.flag("SHUTDOWN") and not pid else
             "stopped" if not pid else
             "draining: adding nothing" if q.flag("STOP_ADDING") else "running, adding")
    recent = sorted(q.jobs_in("done") + q.jobs_in("failed") + q.jobs_in("stopped"), key=lambda j: j.get("ended", ""))[-12:]
    upcoming = q.jobs_in("queue")[:8]
    events = []
    try:
        events = [json.loads(l) for l in open(q.p("events.jsonl")).readlines()[-8:]]
    except OSError:
        pass
    shutdown = None
    try:
        shutdown = json.load(open(q.p("shutdown.json"))) if q.flag("SHUTDOWN") else None
    except (OSError, ValueError):
        pass
    sync = None
    try:
        sync = json.load(open(os.path.join(os.path.dirname(q.d.rstrip("/")), "..", "ledger", "sync.json")))
    except (OSError, ValueError):
        pass
    try:
        keeper_info = json.load(open(q.p("keeper.json"))) if pid else None
    except (OSError, ValueError):
        keeper_info = None
    return {"dir": q.d, "state": state, "keeper_pid": pid, "adding": not q.flag("STOP_ADDING"),
            "keeper": keeper_info, "flags": q.flags(), "progress": q.progress()[-200:],
            "auto": q.config().get("auto", True) is not False,
            "rotation": q.config().get("rotation", True) is not False,
            "shutdown": shutdown, "sync": sync,
            "counts": counts, "lanes": lanes,
            "recent": [{"id": j["id"], "kind": j.get("kind"), "title": j.get("title"), "host": j.get("host"),
                        "seconds": j.get("seconds"), "ok": j["_file"].startswith(q.p("done"))} for j in recent],
            "upcoming": [{"id": j["id"], "kind": j.get("kind"), "title": j.get("title"), "needs": j.get("needs")} for j in upcoming],
            "events": events, "health": health(q), "restart": restart_cost(q),
            "roster": roster(q, cfg, pid),
            "projects": [{"name": n, "paused": n in cfg.get("paused_projects", ())} for n in projects_of(cfg)]}


def ensure(q):
    pid = keeper_alive(q)
    if pid:
        print("the keeper is running (pid %d)" % pid)
        return
    log = open(q.p("keeper.log"), "a")
    p = subprocess.Popen([sys.executable, os.path.abspath(__file__), q.d, "start"], stdout=log, stderr=log,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    print("the keeper started (pid %d)" % p.pid)


def restart_keeper(q):
    """Restart the keeper on the code on disk. A keeper that can restart
    itself (keeper.json says its code) is asked to (DIR/RESTART); one from
    before that is stopped from outside: its jobs stopped on their hosts
    (their ssh would outlive it, and the new keeper would run them twice),
    then a new keeper, which puts them back on the queue."""
    pid = keeper_alive(q)
    if not pid:
        return ensure(q)
    try:
        info = json.load(open(q.p("keeper.json")))
    except (OSError, ValueError):
        info = {}
    cost = restart_cost(q)
    if info.get("code"):
        open(q.p("RESTART"), "w").close()
        q.event("restart asked")
        print("the keeper restarts at its next beat; %d running jobs carried on" % cost["jobs"])
        return
    q.event("restart asked", how="stopped from outside: a keeper from before restarts")
    os.kill(pid, signal.SIGTERM)
    for _ in range(40):
        if not keeper_alive(q):
            break
        time.sleep(0.5)
    else:
        sys.exit("the keeper (pid %d) did not end" % pid)
    hosts = {h["name"]: h for h in q.config()["hosts"]}
    for j in q.jobs_in("running"):
        h = hosts.get(os.path.basename(os.path.dirname(j["_file"])))
        if h:
            stop_remote(h, j["id"])
    try:
        os.remove(q.p("keeper.pid"))
    except OSError:
        pass
    ensure(q)
    print("restarted: %d running jobs went back on the queue" % cost["jobs"])


def save_config(q, cfg):
    """By a rename: every lane reads this file at every pick."""
    tmp = q.p(".config.json.tmp")
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=1)
    os.replace(tmp, q.p("config.json"))


# THE RESTART (Paul, 8 November: "i would like to be able to reboot on command. can we set that up on
# every machine"). A machine told to restart takes nothing new, as a Finish; once none of its lanes
# has a job in hand the keeper reads its boot id and sends its reboot command (the "reboot" its rule
# allows, copied by the probe from fleet-poweroff-setup.sh's sudoers or doas file); and when it
# answers with another boot id it is back, and takes work again. Paused all the while, so a machine
# rebooting is not a machine down: no flag, no lane waiting on it. Not back in RESTART_WAIT_S, it is
# flagged and left paused for a person. `restart now` sends its running jobs back first, as Stop.
RESTART_WAIT_S = 1200
BOOT_ID = "cat /proc/sys/kernel/random/boot_id 2>/dev/null || sysctl -n kern.boottime"
_restart_read = {}


def boot_id(host):
    """The machine's boot id, or None when it does not answer. One short ssh, not remote()'s three
    tries: a machine rebooting does not answer for minutes, and the beat must not wait on it."""
    script = host.get("boot_id_cmd") or BOOT_ID
    argv = ["bash", "-c", script] if host["target"] == "-" else SSH + ["-o", "ConnectTimeout=5", host["target"], script]
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=15)
    except (subprocess.TimeoutExpired, OSError):
        return None
    out = (r.stdout or "").strip()
    return out if r.returncode == 0 and out else None


def restart_when_done(q):
    """Each restarting machine, a step at each beat (at most one ssh a machine a half minute)."""
    cfg = q.config()
    mains = [h for h in cfg["hosts"] if h.get("restarting") and not h.get("lane_of")]
    if not mains:
        return
    busy = {os.path.basename(os.path.dirname(j["_file"])) for j in q.jobs_in("running")}
    changed = False
    for main in mains:
        name, r = main["name"], main["restarting"]
        ls = [h for h in cfg["hosts"] if name in (h["name"], h.get("lane_of"))]
        if now() - _restart_read.get(name, 0) < cfg.get("restart_poll_s", 30):
            continue
        if r.get("stage") == "finishing":
            if any(h["name"] in busy for h in ls):
                continue
            _restart_read[name] = now()
            boot = boot_id(main)
            if boot is None:
                continue
            cmd = main.get("reboot")
            if main["target"] == "-":
                argv = ["bash", "-c", "nohup sh -c 'sleep 2; %s' >/dev/null 2>&1 &" % cmd]
            else:
                argv = SSH + ["-o", "ConnectTimeout=5", main["target"], "nohup sh -c 'sleep 2; %s' >/dev/null 2>&1 &" % cmd]
            try:
                subprocess.run(argv, capture_output=True, text=True, timeout=30)
            except (subprocess.TimeoutExpired, OSError):
                pass  # the connection may hang as it goes down; the boot id says whether it went
            r.update(stage="sent", boot=boot, sent=now())
            changed = True
            q.event("machine rebooting", host=name)
        elif r.get("stage") == "sent":
            _restart_read[name] = now()
            boot = boot_id(main)
            if boot and boot != r.get("boot"):
                for h in ls:
                    h.pop("paused", None)
                main.pop("restarting", None)
                changed = True
                q.event("machine back from restart", host=name, seconds=int(now() - r.get("sent", now())))
                q.boots_at = q.boots_at or now() + 20
            elif now() - r.get("sent", now()) > RESTART_WAIT_S and not r.get("flagged"):
                r["flagged"] = True
                changed = True
                q.notice("restart", "%s did not come back from its restart in %d minutes: it stays paused; Resume takes it back"
                         % (name, RESTART_WAIT_S // 60), key="restart:%s:%s" % (name, r.get("sent")))
    if changed:
        save_config(q, cfg)


def leave_when_done(q):
    """Finish, then remove: a machine marked leaving takes nothing new (it is paused), and once none
    of its lanes has a job in hand it goes to the bench as Remove sends it. Nothing is sent back,
    because nothing was cut. Run at each keeper beat."""
    cfg = q.config()
    leaving = sorted({h.get("lane_of", h["name"]) for h in cfg["hosts"] if h.get("leaving")})
    if not leaving:
        return
    busy = {os.path.basename(os.path.dirname(j["_file"])) for j in q.jobs_in("running")}
    for name in leaving:
        ls = [h for h in cfg["hosts"] if name in (h["name"], h.get("lane_of"))]
        if any(h["name"] in busy for h in ls):
            continue
        cfg["hosts"] = [h for h in cfg["hosts"] if h not in ls]
        for h in ls:
            h.pop("leaving", None)
        cfg["bench"] = [b for b in cfg.get("bench", []) if name not in (b["name"], b.get("lane_of"))] + ls
        save_config(q, cfg)
        q.event("machine removed", host=name, why="finished the jobs in hand")


def send_back(q, cfg, which):
    """The running jobs `which` picks go back on the queue at the keeper's next beat."""
    if not keeper_alive(q):
        return 0
    n = 0
    for j in q.jobs_in("running"):
        if which(j, os.path.basename(os.path.dirname(j["_file"]))):
            open(q.p("send-back", j["id"]), "w").close()
            n += 1
    return n


def autostart(q):
    """The console opening (Paul, 8 November: "when you launch orrery it would implicitly resume or
    start"). THE KEEPER STARTS UNLESS A PERSON STOPPED IT. A cut leaves no switch behind -- the
    power took the keeper mid-beat -- while every stop a person makes does: STOP_NOW, SHUTDOWN, or a
    drain (STOP_ADDING) that has run out of work. Those wait for Start, because a console that undid
    a stop each time it opened would make Stop a suggestion (30 October: the queue stopped for days
    while the brain was redesigned)."""
    pid = keeper_alive(q)
    if pid:
        print("the keeper is running (pid %d)" % pid)
        return
    if q.flag("STOP_NOW") or q.flag("SHUTDOWN"):
        print("stopped by a person: the keeper waits for Start")
        return
    if q.flag("STOP_ADDING") and not q.jobs_in("queue") and not q.jobs_in("running"):
        print("drained by a person and finished: the keeper waits for Start")
        return
    q.event("autostart", why="the console opened and no keeper ran")
    ensure(q)


def resume(q):
    for f in ("STOP_ADDING",) + (() if keeper_alive(q) else ("STOP_NOW", "SHUTDOWN")):
        try:
            os.remove(q.p(f))
        except OSError:
            pass
    q.event("resume")
    ensure(q)


def machine(q, name, how, at_once=False):
    cfg = q.config()
    mine = lambda h: name in (h["name"], h.get("lane_of"))
    ls = [h for h in cfg["hosts"] if mine(h)]
    if how == "add":
        if ls:
            sys.exit("%s is already in the queue" % name)
        ls = [h for h in cfg.get("bench", []) if mine(h)]
        if ls:
            cfg["bench"] = [h for h in cfg["bench"] if not mine(h)]
        else:
            try:
                m = json.load(open(q.p("machines.json")))[name]
            except (OSError, ValueError, KeyError):
                sys.exit("%s is on neither the bench nor machines.json: add it on the Machines screen first" % name)
            facts = m.get("facts", {})
            h = {"name": name, "target": m["target"], "caps": ["cpu", "gpu"] if facts.get("gpu") else ["cpu"], "nice": 10}
            if facts.get("poweroff"):
                h["poweroff"] = facts["poweroff"]
            ls = [h]
        for h in ls:
            h.pop("paused", None)
        cfg["hosts"] += ls
        save_config(q, cfg)
        q.event("machine added", host=name)
        print("%s is in the queue; its lane starts at the keeper's next beat" % name)
        return
    if not ls:
        sys.exit("%s is not in the queue" % name)
    if how.startswith("cpus"):
        # "cpus N": its CPU lanes' jobs told N CPUs, a power of two no more than it has; "cpus all" lifts it.
        word = how.split()[1] if " " in how else ""
        try:
            cores = int((json.load(open(q.p("machines.json"))).get(name, {}).get("facts") or {}).get("cpus") or 0)
        except (OSError, ValueError):
            cores = 0
        if word == "all":
            n = None
        elif word.isdigit() and int(word) in CPU_STEPS and (not cores or int(word) <= cores):
            n = int(word)
        else:
            sys.exit("cpus is 1, 2, 4, 8 ... (a power of two) up to %s, or all" % (cores or "its cores"))
        for h in ls:
            if "cuda" in h.get("caps", []):
                continue
            if n:
                h["cpus"] = n
            else:
                h.pop("cpus", None)
        save_config(q, cfg)
        q.event("machine cpus", host=name, cpus=n or "all")
        print("%s's jobs are told %s CPUs from its next job" % (name, n or "all its"))
        return
    if how == "remove":
        # REMOVE IS AT ONCE (Paul, 7 November: "when I remove a computer, it stops computation, and
        # places its job back in the queue"). It used to leave after the job in hand, and a GPU
        # island, whose jobs are half-hour segments one after another, went on computing on a machine
        # the console showed as gone. What its lanes run goes back on the queue, as Stop now sends it
        # (an island's segment loses the generations since its last save), and it is on the bench
        # before the jobs are cut. The gentle way out is Finish, then remove: `finish`, below.
        names = {h["name"] for h in ls}
        cfg["hosts"] = [h for h in cfg["hosts"] if not mine(h)]
        for h in ls:
            h.pop("leaving", None)
            h.pop("restarting", None)
        cfg["bench"] = [h for h in cfg.get("bench", []) if not mine(h)] + ls
        save_config(q, cfg)
        q.event("machine removed", host=name)
        back = send_back(q, cfg, lambda j, lane: lane in names)
        n = rehome(q, cfg)
        print("%s leaves the queue now%s; Add brings it back%s" % (
            name, ", %d running job(s) back on the queue" % back if back else "", "; %d queued job(s) pinned to it moved" % n if n else ""))
        return
    if how == "finish":
        # FINISH, THEN REMOVE (Paul, 7 November: "a pause then stop button ... stop taking new jobs,
        # and stop accepting new endless jobs"). A pause now, nothing new, island segments
        # included, and a mark: the keeper's beat (leave_when_done) moves it to the bench once none
        # of its lanes has a job in hand. Nothing is cut, so an island ends on a saved segment.
        names = {h["name"] for h in ls}
        for h in ls:
            h["paused"] = True
            h["leaving"] = True
            h.pop("restarting", None)
        save_config(q, cfg)
        q.event("machine finishing", host=name)
        n = rehome(q, cfg)
        busy = [j for j in q.jobs_in("running") if os.path.basename(os.path.dirname(j["_file"])) in names]
        print("%s takes nothing new and leaves the queue %s%s" % (
            name, "when its %d job(s) in hand end" % len(busy) if busy else "at the keeper's next beat: nothing is in hand",
            "; %d queued job(s) pinned to it moved" % n if n else ""))
        return
    if how == "restart":
        main = next((h for h in ls if h["name"] == name), None)
        if not main or not main.get("reboot"):
            sys.exit("%s has no restart rule: apply \"Let the fleet power it off and restart it\" on Machines, "
                     "then Probe it" % name)
        names = {h["name"] for h in ls}
        for h in ls:
            h["paused"] = True
            h.pop("leaving", None)
        main["restarting"] = {"stage": "finishing", "since": time.strftime("%Y-%m-%dT%H:%M:%S")}
        save_config(q, cfg)
        q.event("machine restarting", host=name, now=bool(at_once))
        back = send_back(q, cfg, lambda j, lane: lane in names) if at_once else 0
        busy = [j for j in q.jobs_in("running") if os.path.basename(os.path.dirname(j["_file"])) in names]
        print("%s takes nothing new; %s it restarts, and takes work again when it is back%s" % (
            name, "with its jobs sent back," if at_once else ("after its %d job(s) in hand" % len(busy) if busy else "at the keeper's next beat"),
            " (%d back on the queue)" % back if back else ""))
        return
    for h in ls:
        # Each of these keeps the machine in the queue, so each takes back a Finish's leaving, and a
        # Restart not yet sent (one sent is the machine's own to finish).
        h.pop("leaving", None)
        if how in ("resume", "pause", "stop"):
            h.pop("restarting", None)
        if how == "resume":
            h.pop("paused", None)
        elif how in ("pause", "stop"):
            h["paused"] = True
        else:
            sys.exit("machine NAME pause|finish|stop|resume|remove|add|restart [now]")
    save_config(q, cfg)
    q.event("machine " + how, host=name)
    n = rehome(q, cfg) if how != "resume" else 0
    if n:
        print("%d queued job(s) pinned to %s moved to another machine" % (n, name))
    if how == "resume":
        print("%s takes work again" % name)
    elif how == "stop":
        names = {h["name"] for h in ls}
        n = send_back(q, cfg, lambda j, lane: lane in names)
        print("%s stopped: %d running jobs go back on the queue" % (name, n))
    else:
        print("%s paused: the job in hand finishes, nothing new starts" % name)


def assign(q, name, project, how):
    cfg = q.config()
    if project not in projects_of(cfg) or how not in ("on", "off"):
        sys.exit("assign NAME PROJECT on|off; the projects are %s" % ", ".join(projects_of(cfg)))
    ls = [h for h in cfg["hosts"] if name in (h["name"], h.get("lane_of"))]
    if not ls:
        sys.exit("%s is not in the queue" % name)
    for h in ls:
        off = [p for p in h.get("off", []) if p != project] + ([project] if how == "off" else [])
        if off:
            h["off"] = off
        else:
            h.pop("off", None)
    save_config(q, cfg)
    q.event("assigned", host=name, project=project, to=how)
    print("%s %s %s: the job in hand finishes either way" % (name, "takes" if how == "on" else "no longer takes", project))


def project(q, name, how):
    cfg = q.config()
    if name not in projects_of(cfg) or how not in ("pause", "stop", "resume"):
        sys.exit("project NAME pause|stop|resume; the projects are %s" % ", ".join(projects_of(cfg)))
    paused = [p for p in cfg.get("paused_projects", []) if p != name] + ([] if how == "resume" else [name])
    cfg["paused_projects"] = paused
    save_config(q, cfg)
    q.event("project " + how, project=name)
    if how == "stop":
        n = send_back(q, cfg, lambda j, lane: project_of(cfg, j) == name)
        print("%s stopped everywhere: %d running jobs go back on the queue" % (name, n))
    else:
        print("%s %s" % (name, "takes work again" if how == "resume" else "paused: what runs finishes, nothing new starts"))


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    q = Queue(argv[0])
    cmd = argv[1]
    if cmd == "start":
        # A keeper that restarted itself is this process: its pid is ours.
        if keeper_alive(q) and keeper_alive(q) != os.getpid():
            sys.exit("a keeper is already running (pid %s)" % keeper_alive(q))
        for f in ("STOP_NOW", "SHUTDOWN"):
            try:
                os.remove(q.p(f))
            except OSError:
                pass
        keeper(q)
    elif cmd == "ensure":
        ensure(q)
    elif cmd == "autostart":
        autostart(q)
    elif cmd == "resume":
        resume(q)
    elif cmd == "machine":
        if len(argv) < 4:
            sys.exit("machine NAME pause|finish|stop|resume|remove|add|restart [now]|cpus N")
        machine(q, argv[2], " ".join(argv[3:5]) if argv[3] == "cpus" else argv[3], at_once=argv[4:5] == ["now"] and argv[3] == "restart")
    elif cmd == "assign":
        if len(argv) < 5:
            sys.exit("assign NAME PROJECT on|off")
        assign(q, argv[2], argv[3], argv[4])
    elif cmd == "project":
        if len(argv) < 4:
            sys.exit("project NAME pause|stop|resume")
        project(q, argv[2], argv[3])
    elif cmd == "plan-now":
        # The keeper plans when runs/ changes: every keeper, this one and
        # those from before the button.
        os.makedirs(q.p("runs"), exist_ok=True)
        os.utime(q.p("runs"))
        q.event("plan asked")
        print("the keeper asks the planner for work at its next beat")
    elif cmd == "restart":
        restart_keeper(q)
    elif cmd == "health":
        h = health(q)
        if "--json" in argv:
            print(json.dumps(h, indent=1))
        else:
            for c in h:
                print("%-4s %-10s %s" % ({"ok": "ok", "warn": "LOOK", "bad": "BAD"}[c["level"]], c["name"], c["text"]))
    elif cmd == "stop-adding":
        open(q.p("STOP_ADDING"), "w").close()
        q.event("stop adding")
        print("adding stopped: the queue drains, then results are collected and the keeper ends")
    elif cmd == "resume-adding":
        for f in ("STOP_ADDING",):
            try:
                os.remove(q.p(f))
            except OSError:
                pass
        q.event("resume adding")
        print("adding again")
    elif cmd == "stop-now":
        open(q.p("STOP_NOW"), "w").close()
        q.event("stop now")
        print("stopping now: running jobs are stopped, results collected, the keeper ends")
    elif cmd == "stop-job":
        if len(argv) < 3:
            sys.exit("stop-job ID")
        jid = argv[2]
        waiting = [j for j in q.jobs_in("queue") if j["id"] == jid]
        if waiting:
            os.rename(waiting[0]["_file"], q.p("stopped", os.path.basename(waiting[0]["_file"])))
            q.event("job stopped", job=jid, was="queued")
            print("%s left the queue" % jid)
        elif any(j["id"] == jid for j in q.jobs_in("running")):
            open(q.p("stop-job", jid), "w").close()
            q.event("stop job", job=jid)
            print("%s stops at the keeper's next beat; its lane goes on to the next job" % jid)
        else:
            sys.exit("%s is neither queued nor running" % jid)
    elif cmd == "shutdown-now":
        open(q.p("STOP_ADDING"), "w").close()
        open(q.p("SHUTDOWN"), "w").close()
        q.event("shutdown now")
        print("shutting the fleet down: nothing new starts; each machine finishes its job, reports, then powers off")
    elif cmd == "sync":
        cfg = q.config()
        r = subprocess.run(["bash", "-c", "%s sync" % cfg["planner"]], text=True)
        sys.exit(r.returncode)
    elif cmd == "now":
        # Do it now: the planner syncs, then promotes the strongest current
        # candidate (tested, its families read, pushed in auto mode), or
        # re-reads the strongest older ones on today's defaults.
        cfg = q.config()
        r = subprocess.run(["bash", "-c", "%s now" % cfg["planner"]], text=True)
        sys.exit(r.returncode)
    elif cmd == "resolve":
        # The local line (promotions that self-modified, without push
        # permission or with auto mode off) pushed to main, from a machine
        # that can push.
        cfg = q.config()
        r = subprocess.run(["bash", "-c", "%s resolve" % cfg["planner"]], text=True)
        sys.exit(r.returncode)
    elif cmd == "new":
        if len(argv) < 3:
            sys.exit("new KIND [key=value ...]")
        os.makedirs(q.p("runs"), exist_ok=True)
        n = 1 + max([int(f[1:5]) for f in os.listdir(q.p("runs")) if f[:1] == "r" and f[1:5].isdigit()] or [0])
        rid = "r%04d" % n
        params = dict(kv.split("=", 1) for kv in argv[3:] if "=" in kv)
        with open(q.p("runs", rid + ".json"), "w") as f:
            json.dump({"kind": argv[2], "params": params, "asked": time.strftime("%Y-%m-%dT%H:%M:%S")}, f, indent=1)
        q.event("run asked", run=rid, kind=argv[2], params=params)
        print("%s: %s asked; the planner turns it into jobs at its next top-up" % (rid, argv[2]))
    elif cmd == "runs":
        r = subprocess.run(["bash", "-c", "%s runs" % q.config()["planner"]], text=True)
        sys.exit(r.returncode)
    elif cmd == "approve":
        # Paul's word on a prepared promotion: the planner moves main to it.
        r = subprocess.run(["bash", "-c", "%s approve %s" % (q.config()["planner"], shlex.quote(argv[2]))], text=True)
        q.event("approved" if r.returncode == 0 else "approve failed", run=argv[2])
        sys.exit(r.returncode)
    elif cmd == "flags":
        fl = q.flags(every="--all" in argv)
        if "--json" in argv:
            print(json.dumps(fl, indent=1))
        elif "--brief" in argv:
            if fl:
                print("orrery %s: %d flag(s) not acknowledged" % (os.path.basename(q.d.rstrip("/")), len(fl)))
                for f in fl:
                    print("  [%s] %s %s: %s" % (f["id"], f["t"][11:16], f["kind"], f["text"]))
        else:
            for f in fl:
                print("%s %s %-10s %s%s" % (f["id"], f["t"], f["kind"], f["text"], "  (acknowledged by %s)" % f["ack"]["by"] if f.get("ack") else ""))
    elif cmd in ("auto", "rotation"):
        # auto on|off: whether candidates promote themselves; rotation on|off:
        # whether auto mode asks one of each kind of run in turn. The plan
        # reads config.json's "auto" and "rotation", each on unless false.
        key = cmd
        if len(argv) < 3 or argv[2] not in ("on", "off"):
            print("%s is %s" % (key, "on" if q.config().get(key, True) is not False else "off"))
        else:
            cfg = json.load(open(q.p("config.json")))
            cfg[key] = argv[2] == "on"
            with open(q.p("config.json.tmp"), "w") as f:
                json.dump(cfg, f, indent=1)
            os.replace(q.p("config.json.tmp"), q.p("config.json"))
            q.event(key, on=cfg[key])
            print("%s is %s" % (key, argv[2]))
    elif cmd == "progress":
        for f in q.progress():
            print("%s %-10s %s" % (f["t"], f["kind"], f["text"]))
    elif cmd == "ack":
        by = argv[argv.index("--by") + 1] if "--by" in argv else os.environ.get("USER", "someone")
        n = q.ack(argv[2], by)
        print("%d flag(s) acknowledged" % n)
    elif cmd == "push-check":
        # Can this coordinator push the project's branch (Approve is a push)?
        r = subprocess.run(["bash", "-c", "%s push-check" % q.config()["planner"]], text=True)
        sys.exit(r.returncode)
    elif cmd == "cancel":
        rid = argv[2]
        try:
            os.rename(q.p("runs", rid + ".json"), q.p("runs", rid + ".cancelled"))
        except OSError:
            sys.exit("no run %s" % rid)
        n = 0
        for j in q.jobs_in("queue"):
            if j["id"].startswith(rid + "-"):
                os.rename(j["_file"], q.p("stopped", os.path.basename(j["_file"])))
                n += 1
        q.event("run cancelled", run=rid, dropped=n)
        print("%s cancelled: %d queued jobs left the queue; running ones finish" % (rid, n))
    elif cmd == "status":
        s = status(q)
        if "--json" in argv:
            print(json.dumps(s, indent=1))
        else:
            print("%s  (keeper %s)" % (s["state"], s["keeper_pid"] or "not running"))
            for k, c in sorted(s["counts"].items()):
                print("  %-10s %s" % (k, "  ".join("%s %d" % (x, c.get(x, 0)) for x in ("queue", "running", "done", "failed", "stopped"))))
            for l in s["lanes"]:
                print("  %-12s %-10s %s" % (l["host"], l.get("state"), l.get("title") or ""))
    elif cmd == "add":
        for path in argv[2:]:
            with open(path) as f:
                jobs = json.load(f)
            for j in (jobs if isinstance(jobs, list) else [jobs]):
                print(("added " if q.add(j) else "already known ") + j["id"])
    else:
        # THE CONSOLE'S VERBS THAT RUN A TOOL (nets, growth, recordings, bridge, montage, videos, and every
        # verb added after) live in fleet-verbs.py, read fresh each time: a new button changes that file,
        # not this one, so the keeper does not restart for it (Paul, 4 November: "making blockages
        # minimized"; seven restarts had thrown away 71 jobs in two days, most for a new verb).
        verbs = fleet_verbs()
        if verbs and cmd in verbs.VERBS:
            verbs.VERBS[cmd](q, argv)
            return
        sys.exit(__doc__)


def fleet_verbs():
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fleet-verbs.py")
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location("fleet_verbs", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


if __name__ == "__main__":
    main(sys.argv[1:])
