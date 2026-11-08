#!/bin/sh
# After a power cut, against a real keeper with no fleet (every lane is this machine, target "-"):
# the console's autostart, a keeper.pid the power left behind, the record of the cut, and the
# checks after it (tools/boots.py). Each line is a claim; the first false one ends it.
#
#     sh tools/autostart-check.sh
set -eu
T=$(cd "$(dirname "$0")" && pwd)
Q=$(mktemp -d)/grove
mkdir -p "$Q"
q() { python3 "$T/fleet-queue.py" "$Q" "$@"; }
sleep 600 & FOREIGN=$!
trap 'q stop-now >/dev/null 2>&1 || true; kill $FOREIGN 2>/dev/null || true; sleep 1' EXIT
alive() { python3 -c "
import importlib.util, sys
s = importlib.util.spec_from_file_location('fq', '$T/fleet-queue.py'); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
print('up' if m.keeper_alive(m.Queue('$Q')) else 'down')"; }
wait_for() { # what it should say, then the command saying it
    want=$1; shift; i=0
    until [ "$("$@")" = "$want" ]; do
        i=$((i + 1)); [ $i -lt 60 ] || { echo "FAILED: $* said $("$@"), not $want"; exit 1; }
        sleep 0.5
    done
    echo "ok  $* -> $want"
}
claim() { # a sentence, then the test
    what=$1; shift
    if "$@"; then echo "ok  $what"; else echo "FAILED: $what"; exit 1; fi
}
has() { [ -e "$Q/$1" ]; }
events() { grep -c "\"$1\"" "$Q/events.jsonl" 2>/dev/null || true; }
cat > "$Q/config.json" <<E
{"hosts": [{"name": "a", "target": "-", "caps": ["cpu"]}],
 "poll_s": 1, "keep_awake": false, "sync_s": 0, "low_water": 0}
E

# A pid the power left behind, now another process's: not a keeper.
echo $FOREIGN > "$Q/keeper.pid"
wait_for down alive
claim "a live pid that is not this file's is not a keeper" [ "$(alive)" = down ]

# The console opening after a cut: no switch a person left, so the keeper starts.
mkdir -p "$Q/running/a"
echo '{"id": "j1", "kind": "k", "title": "j1", "needs": "cpu", "cmd": "sleep 30"}' > "$Q/running/a/1-j1.json"
echo '{"t": "2026-11-07T21:01:56", "event": "started", "job": "j1", "host": "a"}' > "$Q/events.jsonl"
q autostart >/dev/null
wait_for up alive
claim "autostart says why it started" [ "$(events autostart)" = 1 ]
wait_for true sh -c "[ -e '$Q/cut.json' ] && echo true || echo false"
claim "the cut begins at the last event the keeper before wrote" grep -q '"quiet_since": "2026-11-07T21:01:56"' "$Q/cut.json"
claim "and counts the job it left running, put back on the queue" grep -q '"requeued": 1' "$Q/cut.json"
claim "the event says the keeper came back after a cut" [ "$(events 'came back after a cut')" = 1 ]
wait_for true sh -c "[ -e '$Q/plan/boots.json' ] && echo true || echo false"
claim "the keeper read the machines at its start (tools/boots.py)" grep -q '"health"' "$Q/plan/boots.json"
claim "and health has a boots line" sh -c "python3 '$T/fleet-queue.py' '$Q' health | grep -q ' boots '"

# A person's stop: autostart leaves it stopped, and the stop is not a cut.
rm -f "$Q/cut.json"
q stop-now >/dev/null
wait_for down alive
claim "a stop ends the keeper with its pid file gone" [ ! -e "$Q/keeper.pid" ]
said=$(q autostart)
claim "autostart leaves a person's stop alone ($said)" [ "$(alive)" = down ]
claim "and says it waits for Start" sh -c "echo '$said' | grep -q 'waits for Start'"

# Start (resume) after the stop: a keeper again, and no cut recorded.
q resume >/dev/null
wait_for up alive
sleep 2
claim "a keeper started after a clean stop records no cut" [ ! -e "$Q/cut.json" ]

# A finished drain is a person's too.
q stop-adding >/dev/null
wait_for down alive
said=$(q autostart)
claim "autostart leaves a finished drain alone ($said)" [ "$(alive)" = down ]
echo PASS
