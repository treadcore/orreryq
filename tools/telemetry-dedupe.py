#!/usr/bin/env python3
"""telemetry-dedupe: remove the copies the telemetry pull appended before 19 November 2026.

    python3 tools/telemetry-dedupe.py QUEUE          says what it would do, file by file, and changes nothing
    python3 tools/telemetry-dedupe.py QUEUE --do     does it

Until 19 November the pull re-sent every older day file whole at each pull and appended it again
(tools/telemetry.py, pull_one). Each day file keeps every line once, in the order first written: the first
copy of a day was fetched by offset and is byte for byte the machine's own file, and every copy after it is
that file again, so keeping first occurrences gives the original back exactly (saskatchewan's 16 November:
6,940,069 bytes, the machine's own size). Each machine's newest two files are left alone (a pull may still
be writing them), and a file that changes while it is read is left as it was."""
import os, sys, time
q, do = sys.argv[1], "--do" in sys.argv
tot0 = tot1 = 0
for m in sorted(os.listdir(os.path.join(q, "telemetry"))):
    d = os.path.join(q, "telemetry", m)
    logs = sorted(f for f in os.listdir(d) if f.endswith(".log"))
    for f in logs[:-2]:                      # the newest two may still be written to by a pull
        p = os.path.join(d, f)
        before, mt = os.path.getsize(p), os.path.getmtime(p)
        seen, n, kept = set(), 0, 0
        tmp = p + ".dedupe"
        with open(p, "rb") as src, open(tmp, "wb") as dst:
            for line in src:
                n += 1
                if line in seen:
                    continue
                seen.add(line)
                dst.write(line)
                kept += 1
        after = os.path.getsize(tmp)
        tot0 += before; tot1 += after
        if do and os.path.getmtime(p) == mt:
            os.replace(tmp, p)
            said = "replaced"
        else:
            os.remove(tmp)
            said = "would replace" if not do else "CHANGED WHILE READ: left"
        print("%-13s %s  %9d lines -> %7d   %8.1f MB -> %6.1f MB  %s" % (m, f, n, kept, before / 1e6, after / 1e6, said), flush=True)
print("total %.2f GB -> %.2f GB" % (tot0 / 1e9, tot1 / 1e9))
