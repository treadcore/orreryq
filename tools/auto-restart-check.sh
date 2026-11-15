#!/bin/sh
# The restart after an upgrade, by itself (Paul, 15 November: "design an auto restart after a upgrade
# happens ... sequence the events. such that the machine can update"), against a real keeper and real jobs
# on this machine. A machine's reading is a file (heat_probe), its reboot a line appended to its boot id
# file. Each line is a claim; the first false one ends it.
#
#     sh tools/auto-restart-check.sh [KEEPER.py]
set -eu
T=$(cd "$(dirname "$0")" && pwd)
K=${1:-$T/fleet-queue.py}
Q=$(mktemp -d)/grove
mkdir -p "$Q"
q() { python3 "$K" "$Q" "$@"; }
trap 'q stop-now >/dev/null 2>&1 || true; sleep 1' EXIT
said() { grep -c "\"event\": \"$1\"" "$Q/events.jsonl" 2>/dev/null || true; }
where() { for d in queue done stopped failed; do ls "$Q/$d" | grep -q -- "-$1.json" && { echo "$d"; return; }; done; ls "$Q"/running/* 2>/dev/null | grep -q -- "-$1.json" && echo running || echo nowhere; }
boots() { cat "$Q/boot-$1"; }
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
job() { printf '{"id": "%s", "kind": "k1", "title": "%s", "needs": "host:%s", "cmd": "%s"}\n' "$1" "$1" "$2" "$3" > "$Q/$1.in"; q add "$Q/$1.in" >/dev/null; }
printf one > "$Q/boot-a"; printf one > "$Q/boot-b"
# One probe for both machines: each lane's reading is its own file, named by the lane's CPUs told (1 or 2).
cat > "$Q/config.json" <<E
{"hosts": [{"name": "a", "target": "-", "caps": ["cpu"], "reboot": "printf x >> $Q/boot-a; rm -f $Q/waits-a", "boot_id_cmd": "cat $Q/boot-a", "heat_probe": "cat $Q/waits-a 2>/dev/null; true"},
           {"name": "b", "target": "-", "caps": ["cpu"], "reboot": "printf x >> $Q/boot-b; rm -f $Q/waits-b", "boot_id_cmd": "cat $Q/boot-b", "heat_probe": "cat $Q/waits-b 2>/dev/null; true"}],
 "poll_s": 1, "keep_awake": false, "sync_s": 0, "low_water": 0, "temp_s": 1, "restart_poll_s": 1}
E
q resume >/dev/null
sleep 3
# Off: a boot waits, health says so, nothing restarts.
echo "reboot kernel 2 is installed, 1 runs" > "$Q/waits-a"
echo "reboot kernel 2 is installed, 1 runs" > "$Q/waits-b"
i=0; until q health | grep -q "boots.*a boot waits on 2"; do i=$((i + 1)); [ $i -lt 40 ] || { echo "FAILED: health never said a boot waits"; q health; exit 1; }; sleep 0.5; done
echo "ok  health says a boot waits on both, and that auto restart is off"
stays one 6 boots a
# On: one machine at a time, each after its job in hand.
job long a "sleep 5"
wait_for running where long
q auto-restart on >/dev/null
wait_for 1 said "machine restarting"
[ "$(boots a)$(boots b)" = oneone ] && echo "ok  one machine is restarting, and no reboot is sent while its job runs"
job next a true
wait_for done where long
wait_for 1 said "machine back from restart"
[ "$(where next)" != queue ] || wait_for done where next
wait_for 2 said "machine restarting"
grep '"machine restarting"' "$Q/events.jsonl" | tail -1 | grep -q '"host": "b"' && grep -n '"done", "job": "next"\|"machine restarting", "host": "b"' "$Q/events.jsonl" | head -1 | grep -q next && echo "ok  the second was sent only after the first had finished a job since its return"
wait_for 2 said "machine back from restart"
[ "$(boots a)$(boots b)" = onexonex ] && echo "ok  each rebooted once, the second only after the first was back"
wait_for done where next
python3 -c "import json;c=json.load(open('$Q/config.json'));assert not any(h.get('paused') or h.get('restarting') for h in c['hosts']), c" && echo "ok  both are back in the queue"
stays onex 8 boots a
# A reboot that does not clear the reason is not repeated: it is flagged.
job last b true
wait_for done where last
echo "reboot kernel 2 is installed, 1 runs" > "$Q/waits-a"
i=0; until ls "$Q/flags" 2>/dev/null | grep -q restart; do i=$((i + 1)); [ $i -lt 40 ] || { echo "FAILED: no flag for a reason that outlived its restart"; exit 1; }; sleep 0.5; done
[ "$(boots a)" = onex ] && echo "ok  the same reason after a restart raises a flag and no second reboot"
echo "PASSED"
