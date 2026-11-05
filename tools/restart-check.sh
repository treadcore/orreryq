#!/bin/sh
# THE HANDOVER, against a real keeper and real jobs, with no fleet: every lane is this machine
# (target "-"). A restart under running jobs keeps them: each finishes once, its work done once,
# with its own exit code; one that ends inside the handover is read from its exit all the same; a
# timeout and a stop still hold after it; and a second restart hands over again. Each line is a
# claim; the first false one ends it.
#
#     sh tools/restart-check.sh
set -eu
T=$(cd "$(dirname "$0")" && pwd)
Q=$(mktemp -d)/grove
W=$(dirname "$Q")/work
mkdir -p "$Q" "$W"
q() { python3 "$T/fleet-queue.py" "$Q" "$@"; }
trap 'q stop-now >/dev/null 2>&1 || true; sleep 1' EXIT
where() { for d in queue done stopped failed; do ls "$Q/$d" | grep -q -- "-$1.json" && { echo "$d"; return; }; done; ls "$Q"/running/* 2>/dev/null | grep -q -- "-$1.json" && echo running || echo nowhere; }
events() { grep -c "\"event\": \"$1\", \"job\": \"$2\"" "$Q/events.jsonl" || true; }
wait_for() { # what it should say, then the command saying it
    want=$1; shift; i=0
    until [ "$("$@")" = "$want" ]; do
        i=$((i + 1)); [ $i -lt 120 ] || { echo "FAILED: $* said $("$@"), not $want"; exit 1; }
        sleep 0.5
    done
    echo "ok  $* -> $want"
}
job() { # id, command, timeout
    printf '{"id": "%s", "kind": "k", "title": "%s", "needs": "cpu", "cmd": "%s", "timeout_s": %s}\n' "$1" "$1" "$2" "${3:-600}" > "$Q/$1.in"
    q add "$Q/$1.in" >/dev/null
}
cat > "$Q/config.json" <<E
{"hosts": [{"name": "a", "target": "-", "caps": ["cpu"]}, {"name": "b", "target": "-", "caps": ["cpu"]},
           {"name": "c", "target": "-", "caps": ["cpu"]}, {"name": "d", "target": "-", "caps": ["cpu"]},
           {"name": "e", "target": "-", "caps": ["cpu"]}],
 "poll_s": 1, "keep_awake": false, "sync_s": 0, "low_water": 0, "handover_hold_s": 3}
E
# A handover another process wrote is not taken up: its pids could name some other child. The job
# it names goes back on the queue, as one a dead keeper left, and runs.
mkdir -p "$Q/running/a"
printf '{"id": "ghost", "kind": "k", "title": "ghost", "needs": "cpu", "cmd": "echo run >> %s/ghost"}\n' "$W" > "$Q/running/a/1-ghost.json"
printf '{"keeper": 1, "jobs": [{"id": "ghost", "pid": 1, "host": "a", "file": "%s/running/a/1-ghost.json", "t0": 0}]}\n' "$Q" > "$Q/handover.json"
q ensure >/dev/null
i=0; until [ -s "$Q/keeper.pid" ]; do i=$((i + 1)); [ $i -lt 100 ] || { echo "FAILED: no keeper"; exit 1; }; sleep 0.1; done
pid=$(cat "$Q/keeper.pid")

wait_for done where ghost
[ "$(events adopted ghost)" = 0 ] && [ ! -e "$Q/handover.json" ] && echo "ok  another process's handover is not taken up; its job ran from the queue"

# Each job counts its runs in a file of its own: a job run twice says 2.
job long "echo run >> $W/long; echo before; sleep 40; echo after"
job short "echo run >> $W/short; sleep 3; date +%s > $W/short.end"
job fails "echo run >> $W/fails; sleep 8; exit 3"
job slow "echo run >> $W/slow; sleep 300" 15
job held "echo run >> $W/held; sleep 300"
for j in long short fails slow held; do wait_for running where $j; done
touch "$Q/RESTART"
wait_for 1 grep -c '"event": "handed over"' "$Q/events.jsonl"
wait_for 2 grep -c '"event": "keeper started"' "$Q/events.jsonl"
[ "$(cat "$Q/keeper.pid")" = "$pid" ] && echo "ok  the same process, re-executed"
for j in long short fails slow held; do wait_for 1 events adopted $j; done
q stop-job held >/dev/null
wait_for stopped where held
echo "ok  a job stopped by hand after the handover stops"
wait_for done where short
started=$(python3 -c "
import json,time
t=[json.loads(l)['t'] for l in open('$Q/events.jsonl') if '\"keeper started\"' in l][-1]
print(int(time.mktime(time.strptime(t,'%Y-%m-%dT%H:%M:%S'))))")
[ "$(cat "$W/short.end")" -lt "$started" ] && echo "ok  a job that ended inside the handover, before the new keeper began, is read from its exit: done"
wait_for failed where fails
grep -q '"rc": 3' "$Q"/failed/*-fails.json && echo "ok  an adopted job's own exit code: 3"
wait_for failed where slow
grep -q "timed out after 15 s" "$Q/logs/slow.log" && echo "ok  an adopted job still times out on its first clock"
# A second restart while 'long' runs: handed over again.
touch "$Q/RESTART"
wait_for 2 grep -c '"event": "handed over"' "$Q/events.jsonl"
wait_for 2 events adopted long
wait_for done where long
grep -q before "$Q/logs/long.log" && grep -q after "$Q/logs/long.log" && echo "ok  one log, from before the restarts to after"
for j in ghost long short fails slow held; do
    [ "$(wc -l < "$W/$j" | tr -d ' ')" = 1 ] || { echo "FAILED: $j ran $(wc -l < "$W/$j") times"; exit 1; }
done
echo "ok  every job ran once"
[ "$(grep -c '"event": "requeued"' "$Q/events.jsonl" || true)" = 1 ] && echo "ok  nothing went back on the queue but the ghost"
for j in long short fails slow held; do [ "$(events started $j)" = 1 ] || { echo "FAILED: $j started $(events started $j) times"; exit 1; }; done
echo "ok  every job started once"
echo "PASS"
