#!/usr/bin/env python3
"""telemetry-pull-check: the telemetry pull names every day file this Mac has, so a machine sends only what is new.

    python3 tools/telemetry-pull-check.py [TELEMETRY_PY]      ends PASSED, or FAILED with what was sent again

Until 19 November the pull named only the newest three files, and the machine sends a file it is not told
of from its first byte: from a machine's fourth day on, every pull sent each older day whole again, and it
was appended again, every five minutes (14 GB of telemetry on the Mac, saskatchewan's 16 November 262
copies of itself). A fake machine with five days, the newest half fetched and cut mid-line, must be sent
the newest file's second half and nothing else. The machine's half of the pull is run as written, in sh, on
the fake machine's folder; nothing is reached over ssh. Given an older telemetry.py (with
fleet-telemetry.sh beside it) the check shows that copy's fault."""
import os, sys, subprocess, importlib.util, tempfile
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "telemetry.py")
spec = importlib.util.spec_from_file_location("telemetry", src); T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)
base = tempfile.mkdtemp()
rem, loc = os.path.join(base, "remote", "telemetry"), os.path.join(base, "local", "telemetry", "m")
os.makedirs(rem); os.makedirs(loc)
days = ["20261115.log", "20261116.log", "20261117.log", "20261118.log", "20261119.log"]
for i, f in enumerate(days):
    body = "".join("t=%d x=%d\n" % (i * 1000 + k, k) for k in range(50))
    open(os.path.join(rem, f), "w").write(body)
    open(os.path.join(loc, f), "w").write(body if i < 4 else body[: len(body) // 2 - 3])   # the newest half fetched, its last line cut short
calls = []
real = subprocess.run
T.subprocess = type("S", (), {"run": staticmethod(lambda cmd, input, **k: calls.append(input) or subprocess.CompletedProcess(cmd, 0, b"@@end\n", b"")), "TimeoutExpired": subprocess.TimeoutExpired})
T.pull_one(os.path.join(base, "local"), "m", "x", {})
have = calls[0].decode().split('HAVE=" ')[1].split(' "')[0]
frag = T.REMOTE[T.REMOTE.index('HAVE="'):].replace("%(have)s", have).replace("%%", "%")
out = real(["sh", "-c", "cd %s; %s" % (os.path.dirname(rem), frag)], capture_output=True, text=True).stdout
files = [l for l in out.splitlines() if l.startswith("@@file")]
n = sum(1 for l in out.splitlines() if l.startswith("t="))
print("named:", have)
print("sent:", files, n, "lines")
ok = files == ["@@file 20261119.log"] and n == 25
print("PASSED: only the newest file's missing half is sent" if ok else "FAILED: older days are sent again")
sys.exit(0 if ok else 1)
