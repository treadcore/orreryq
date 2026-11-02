#!/usr/bin/env python3
"""fleet-tune.py QUEUE [KEY VALUE | KEY default] -- the values the run may be moved by.

The list, each with its range and default, is tools/plans/line.json; what has been moved is
QUEUE/tuning.json; the planner reads both at each plan, so a change is live in about a minute
and no job or keeper restarts. A separate tool from fleet-queue.py ON PURPOSE: a keeper restarts
itself when its own file changes, and a dial should never be why a job runs twice.

With no KEY it prints what each is now. A number past its range is refused here and held to the
range by the planner too: the file may be edited by hand. `default` takes the key out of the file.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def table():
    return json.load(open(os.path.join(HERE, "plans", "line.json")))["values"]


def load(p, default):
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return default


def save(path, doc):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    with os.fdopen(fd, "w") as f:
        json.dump(doc, f, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def main(a):
    if not a:
        sys.exit(__doc__)
    q = os.path.abspath(a[0])
    path = os.path.join(q, "tuning.json")
    asked = load(path, {})
    if len(a) == 1:
        live = {v["key"]: v for v in load(os.path.join(q, "plan", "pipeline.json"), {}).get("values", [])}
        for v in table():
            now = live.get(v["key"], {}).get("value", asked.get(v["key"], v["default"]))
            print("%-18s %8s %-12s %s  default %s, %s to %s" % (v["key"], now, v["unit"], "moved" if v["key"] in asked else "     ", v["default"], v["min"], v["max"]))
        return
    # `hold DIAL VALUE` and `hold DIAL off`: QUEUE/hold.json, a dial's value a person has held (the plan of
    # 2 November, chapter 14: the hold was a file with no button). A trial setting the dial to that
    # value does not promote itself; its reads go on. The planner reads the file at each plan.
    if len(a) == 4 and a[1] == "hold":
        hp = os.path.join(q, "hold.json")
        hold = load(hp, {}) or {}
        dial, val = a[2], a[3]
        if val == "off":
            hold.pop(dial, None)
            said = "%s is no longer held" % dial
        else:
            try:
                hold[dial] = float(val)
            except ValueError:
                sys.exit("%s is not a number" % val)
            said = "%s held at %s: a trial there waits for a person" % (dial, hold[dial])
        save(hp, hold)
        with open(os.path.join(q, "events.jsonl"), "a") as f:
            import time
            f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": "hold", "text": said}) + "\n")
        print(said)
        return
    if len(a) != 3:
        sys.exit("usage: fleet-tune.py QUEUE [KEY VALUE | KEY default | hold DIAL VALUE | hold DIAL off]")
    key, val = a[1], a[2]
    v = next((x for x in table() if x["key"] == key), None)
    if not v:
        sys.exit("no value called %s: %s" % (key, ", ".join(x["key"] for x in table())))
    if val == "default":
        asked.pop(key, None)
        said = "%s back to its default, %s" % (key, v["default"])
    else:
        try:
            n = float(val)
        except ValueError:
            sys.exit("%s is not a number" % val)
        if not v["min"] <= n <= v["max"]:
            sys.exit("%s runs from %s to %s" % (key, v["min"], v["max"]))
        asked[key] = int(n) if isinstance(v["default"], int) else round(n, 3)
        said = "%s is %s %s at the next plan" % (key, asked[key], v["unit"])
    save(path, asked)
    # The keeper plans when runs/ changes.
    os.makedirs(os.path.join(q, "runs"), exist_ok=True)
    os.utime(os.path.join(q, "runs"))
    with open(os.path.join(q, "events.jsonl"), "a") as f:
        import time
        f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": "value moved", "text": said}) + "\n")
    print(said)


if __name__ == "__main__":
    main(sys.argv[1:])
