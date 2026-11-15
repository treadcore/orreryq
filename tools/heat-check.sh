#!/bin/sh
# The temperature monitor and the cool-off (Paul, 15 November: "create a temperature monitor every so
# often, and if the ssh client drops off ... some sort of cool off period"), against a real keeper and real
# jobs on this machine. The sensor is a file (config.json's heat_probe), so the check sets the weather.
# Each line is a claim; the first false one ends it.
#
#     sh tools/heat-check.sh [KEEPER.py]
set -eu
T=$(cd "$(dirname "$0")" && pwd)
K=${1:-$T/fleet-queue.py}
Q=$(mktemp -d)/grove
mkdir -p "$Q"
q() { python3 "$K" "$Q" "$@"; }
trap 'q stop-now >/dev/null 2>&1 || true; sleep 1' EXIT
lane() { python3 -c "import json;print(json.load(open('$Q/lanes/$1.json'))['state'])" 2>/dev/null || echo none; }
said() { grep -c "\"event\": \"$1\"" "$Q/events.jsonl" 2>/dev/null || true; }
where() { for d in queue done stopped failed; do ls "$Q/$d" | grep -q -- "-$1.json" && { echo "$d"; return; }; done; ls "$Q"/running/* 2>/dev/null | grep -q -- "-$1.json" && echo running || echo nowhere; }
wait_for() {
    want=$1; shift; i=0
    until [ "$("$@")" = "$want" ]; do
        i=$((i + 1)); [ $i -lt 80 ] || { echo "FAILED: $* said $("$@"), not $want"; exit 1; }
        sleep 0.5
    done
    echo "ok  $* -> $want"
}
stays() {
    want=$1; n=$2; shift 2; i=0
    while [ $i -lt $n ]; do
        [ "$("$@")" = "$want" ] || { echo "FAILED: $* said $("$@"), not $want"; exit 1; }
        i=$((i + 1)); sleep 0.5
    done
    echo "ok  $* stays $want"
}
job() { cat > "$Q/$1.in" <<E
{"id": "$1", "kind": "k1", "title": "$1", "needs": "cpu", "cmd": "$2"}
E
q add "$Q/$1.in" >/dev/null; }
sensor() { echo "coretemp $1 86000" > "$Q/sensor"; }
cat > "$Q/config.json" <<E
{"hosts": [{"name": "a", "target": "-", "caps": ["cpu"]}, {"name": "a-2", "target": "-", "caps": ["cpu"], "lane_of": "a"}],
 "poll_s": 1, "keep_awake": false, "sync_s": 0, "low_water": 0,
 "heat_probe": "cat $Q/sensor", "temp_s": 1, "cool_off_s": 6}
E
sensor 60000
q resume >/dev/null
wait_for idle lane a
job cool true
wait_for done where cool
q temps | grep -q "CPU 60 of 86" && echo "ok  temps prints the reading against the sensor's own limit"

# Hot: the job in hand finishes, nothing new starts, on either lane of the machine.
job long "sleep 6"
wait_for running where long
sensor 90000
wait_for 1 said hot
job waits true
wait_for done where long
wait_for cooling lane a
wait_for cooling lane a-2
stays queue 6 where waits
ls "$Q/flags" | grep -q heat && echo "ok  a flag says the machine is hot"
q health | grep -q "heat.*hot" && echo "ok  health says so"
# Under the limit but not 8 under: still held.
sensor 80000
stays queue 6 where waits
sensor 70000
wait_for 1 said cooled
wait_for done where waits

# A dropped connection: the job goes back, the machine rests while it is read, then the job runs.
job drop "[ -f $Q/dropped ] || { touch $Q/dropped; exit 255; }"
wait_for 1 said cool-off
wait_for cooling lane a
wait_for cooling lane a-2
stays queue 6 where drop
wait_for done where drop
echo "PASSED"
