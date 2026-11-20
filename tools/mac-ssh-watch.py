#!/usr/bin/env python3
"""mac-ssh-watch.py [SECONDS] -- is this Mac letting ssh reach the fleet, and whose ssh is it refusing?

For SECONDS (default 40) it records every ssh process that starts, with the chain of programs that
launched it, and reads the kernel's own line for each connection it tried. Then a table: launched by
whom, to where, connected or refused, and the kernel's reason.

WHY IT EXISTS. On 18 November 2026 macOS refused, by its local network policy, every connection the
console and its keeper opened, and the queue read that as machines being down. The refusal is made
on this Mac before a packet leaves (error 65, No route to host, reason NECP), so nothing on the far
machine shows it, and the refused ssh lives a few milliseconds, so ps in a loop sees none of them:
it caught 0 of 76. This reads libproc in a tight loop and caught 223 of 223.
docs/local-signing-lab-report.md is the account.

A refusal with reason NECP and a chain that begins at orrery is the application without its grant:
System Settings, Privacy & Security, Local Network. Error 64, Host is down, is a machine that is off
and nothing to do with this. It needs no root. It is for macOS and says so elsewhere."""
import collections
import ctypes
import ctypes.util
import re
import struct
import subprocess
import sys
import time

if sys.platform != "darwin":
    sys.exit("mac-ssh-watch.py: this is for macOS")
SECS = float(sys.argv[1]) if len(sys.argv) > 1 else 40.0
lib = ctypes.CDLL(ctypes.util.find_library("proc"))
libc = ctypes.CDLL(ctypes.util.find_library("c"))


def pids():
    n = lib.proc_listallpids(None, 0)
    buf = (ctypes.c_int * (n + 64))()
    n = lib.proc_listallpids(buf, ctypes.sizeof(buf))
    return buf[:n]


def name(pid):
    b = ctypes.create_string_buffer(64)
    lib.proc_name(pid, b, 64)
    return b.value.decode("utf-8", "replace")


def ppid(pid):
    b = ctypes.create_string_buffer(136)          # struct proc_bsdshortinfo... use PROC_PIDT_SHORTBSDINFO (13)
    if lib.proc_pidinfo(pid, 13, 0, b, 64) <= 0:
        return 0
    return struct.unpack_from("II", b.raw)[1]


def args(pid):
    mib = (ctypes.c_int * 3)(1, 49, pid)          # CTL_KERN, KERN_PROCARGS2
    size = ctypes.c_size_t(0)
    if libc.sysctl(mib, 3, None, ctypes.byref(size), None, 0) != 0:
        return ""
    b = ctypes.create_string_buffer(size.value)
    if libc.sysctl(mib, 3, b, ctypes.byref(size), None, 0) != 0:
        return ""
    raw = b.raw[:size.value]
    argc = struct.unpack_from("i", raw)[0]
    parts = [p for p in raw[4:].split(b"\0") if p]
    return " ".join(p.decode("utf-8", "replace") for p in parts[1:1 + argc])[:400]



# /usr/bin/log, not `log`: in zsh that is a builtin. The kernel writes two lines a connection, the
# drop with its reason and the summary with its error; both name the process.
stream = subprocess.Popen(
    ["/usr/bin/log", "stream", "--style", "compact", "--predicate",
     'process == "kernel" AND eventMessage CONTAINS "process: ssh" AND '
     '(eventMessage CONTAINS "connect outgoing" OR eventMessage CONTAINS "reason:")'],
    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, errors="replace")
time.sleep(1.0)

known = set(pids())
young = {}
seen = {}
end = time.time() + SECS
while time.time() < end:
    t = time.time()
    for p in pids():
        if p not in known:
            known.add(p)
            young[p] = t
    for p in list(young):
        # A new process is its parent's image until it execs: it is asked its name for three seconds.
        if t - young[p] > 3:
            del young[p]
            continue
        if name(p) != "ssh":
            continue
        del young[p]
        chain, q = [], ppid(p)
        cmd = args(p)
        while q > 1 and len(chain) < 12:
            chain.append((name(q), args(q)))
            q = ppid(q)
        seen[str(p)] = (chain, cmd)
time.sleep(1.0)
stream.terminate()
text = stream.stdout.read()

result, why = {}, {}
for line in text.splitlines():
    p = re.search(r"process: ssh:(\d+)", line)
    if not p:
        continue
    pid = p.group(1)
    w = re.search(r"reason: (\w+)", line)
    if w and "SYN_SENT" in line:
        why[pid] = w.group(1)
    # " error: N" and not "so_error: N", which is on the same line and is always 0.
    m = re.search(r" error: (\d+)", line)
    if m:
        if m.group(1) == "0":
            result[pid] = "connected"
        else:
            result.setdefault(pid, "refused, error " + m.group(1))


def who(chain):
    """The program at the root of the chain, and the tool nearest the ssh."""
    if not chain:
        return "not caught", ""
    root_name, root_args = chain[-1]
    tool = re.findall(r"tools/[\w./-]+|copal fleet \w+", chain[0][1])
    if "Orrery.app" in root_args or root_name == "orrery":
        root_name = "Orrery"
    elif "fleet-queue.py" in root_args:
        root_name = "the keeper"
    return root_name, (tool[0] if tool else chain[0][0])


rows = collections.Counter()
for pid, r in result.items():
    chain, cmd = seen.get(pid, ([], ""))
    target = (re.findall(r"[\w-]+@[\w.\-]+", cmd) or ["?"])[0]
    if r != "connected" and pid in why:
        r += ", reason " + why[pid]
    rows[(r,) + who(chain) + (target,)] += 1

print("%d ssh processes started in %.0f s; the kernel recorded a connection for %d" % (len(seen), SECS, len(result)))
print("%5s  %-32s %-12s %-28s %s" % ("count", "result", "launched by", "through", "to"))
for (r, root, tool, target), n in sorted(rows.items(), key=lambda kv: (kv[0][0], -kv[1])):
    print("%5d  %-32s %-12s %-28s %s" % (n, r, root, tool[:28], target))
refused = sum(n for k, n in rows.items() if "NECP" in k[0] and k[1] == "Orrery")
if refused:
    print("\nREFUSED BY THIS MAC: %d connections Orrery launched. Its grant: System Settings, Privacy & Security, Local Network." % refused)
    sys.exit(1)
print("\nok: nothing Orrery launched was refused by this Mac's policy")
