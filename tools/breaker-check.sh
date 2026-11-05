#!/bin/sh
# The breaker resets itself, once (Paul, 4 November: "automate this please"), against a real keeper and
# real jobs on this machine. Three jobs failing in a row stop the queue adding; the breaker's stop keeps the
# keeper up through the drain and lifts itself after breaker_resume_min; a breaker that trips again within
# two hours of resetting itself stays off for a person. Each line is a claim; the first false one ends it.
#
#     sh tools/breaker-check.sh
set -eu
T=$(cd "$(dirname "$0")" && pwd)
Q=$(mktemp -d)/grove
mkdir -p "$Q"
q() { python3 "$T/fleet-queue.py" "$Q" "$@"; }
trap 'q stop-now >/dev/null 2>&1 || true; sleep 1' EXIT
lane() { python3 -c "import json;print(json.load(open('$Q/lanes/$1.json'))['state'])" 2>/dev/null || echo none; }
breaker() { if [ -f "$Q/STOP_ADDING" ]; then head -c 7 "$Q/STOP_ADDING"; echo; else echo off; fi; }
said() { grep -c "\"event\": \"$1\"" "$Q/events.jsonl" 2>/dev/null || echo 0; }
alive() { q status --json | python3 -c "import json,sys,os; p=json.load(sys.stdin).get('keeper_pid'); print('up' if p else 'down')"; }
wait_for() {
    want=$1; shift; i=0
    until [ "$("$@")" = "$want" ]; do
        i=$((i + 1)); [ $i -lt 80 ] || { echo "FAILED: $* said $("$@"), not $want"; exit 1; }
        sleep 0.5
    done
    echo "ok  $* -> $want"
}
job() { cat > "$Q/$1.in" <<E
{"id": "$1", "kind": "k1", "title": "$1", "needs": "cpu", "cmd": "$2"}
E
q add "$Q/$1.in" >/dev/null; }
cat > "$Q/config.json" <<E
{"hosts": [{"name": "a", "target": "-", "caps": ["cpu"]}],
 "poll_s": 1, "keep_awake": false, "sync_s": 0, "low_water": 0,
 "max_failures_in_a_row": 3, "breaker_resume_min": 0.1}
E
q resume >/dev/null
wait_for idle lane a
for i in 1 2 3; do job f$i false; done
wait_for breaker breaker
sleep 2
[ "$(alive)" = up ] && echo "ok  the breaker's stop keeps the keeper up through the drain"
wait_for off breaker
[ "$(said 'resume adding')" -ge 1 ] && echo "ok  it reset itself, and said so"
for i in 4 5 6; do job f$i false; done
wait_for breaker breaker
sleep 9
[ "$(breaker)" = breaker ] && [ "$(said 'breaker stays off')" -ge 1 ] && echo "ok  tripped again within two hours of its reset: it stays off for a person"
[ "$(alive)" = up ] && echo "ok  and the keeper waits, still up"
echo "PASS"
