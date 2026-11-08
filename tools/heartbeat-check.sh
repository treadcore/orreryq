#!/bin/sh
# THE HEARTBEAT AND A PLANNER PASS (8 November: heartbeat BAD at every pass, the keeper well), against a
# real keeper with no fleet: one lane on this machine, the planner a stub that sleeps through its pass.
# Here poll_s is 3 and heartbeat_s 6, so a beat comes every 3 s and a 12 s pass is two limits long; after
# the pass the loop sleeps its poll before the next beat, and that is the window the first fix missed
# (11:24, a pass's stamp gone, the beat not yet back, BAD). Each line is a claim; the first false one
# ends it.
#
#     sh tools/heartbeat-check.sh            KEEPER=another/fleet-queue.py to try another keeper
set -eu
T=$(cd "$(dirname "$0")" && pwd)
K=${KEEPER:-$T/fleet-queue.py}
W=$(mktemp -d)
Q=$W/q
cat > "$W/planner.sh" <<P
#!/bin/sh
case "\$1" in
  plan) [ -e "$W/slow" ] && { rm -f "$W/slow"; touch "$W/in-pass"; sleep 12; rm -f "$W/in-pass"; }; echo "[]" ;;
  *) true ;;
esac
P
chmod +x "$W/planner.sh"
mkdir -p "$Q"
printf '%s\n' "{\"hosts\": [{\"name\": \"cpu1\", \"target\": \"-\", \"caps\": [\"cpu\"]}],
 \"planner\": \"$W/planner.sh\", \"poll_s\": 3, \"keep_awake\": false, \"sync_s\": 0, \"chores_s\": 0, \"low_water\": 0,
 \"plan_s\": 3600, \"starve_idle_s\": 3600, \"starve_s\": 3600, \"low_min_s\": 1, \"idle_flag_s\": 0, \"heartbeat_s\": 6}" > "$Q/config.json"
pid=
trap '[ -n "$pid" ] && kill -CONT "$pid" 2>/dev/null; python3 "$K" "$Q" stop-now >/dev/null 2>&1 || true; sleep 1; rm -rf "$W"' EXIT
python3 "$K" "$Q" ensure >/dev/null
i=0; until [ -s "$Q/keeper.pid" ]; do i=$((i + 1)); [ $i -lt 100 ] || { echo "FAILED: no keeper"; exit 1; }; sleep 0.1; done
pid=$(cat "$Q/keeper.pid")
beat() { python3 "$K" "$Q" health | grep heartbeat | sed 's/  */ /g'; }
sleep 4

said=$(beat)
echo "$said" | grep -q "^ok" || { echo "FAILED: a beating keeper reads: $said"; exit 1; }
echo "ok  a keeper beating each 3 s: $said"

touch "$W/slow"
python3 "$K" "$Q" plan-now >/dev/null
i=0; until [ -e "$W/in-pass" ]; do i=$((i + 1)); [ $i -lt 100 ] || { echo "FAILED: no pass began"; exit 1; }; sleep 0.1; done
sleep 9
said=$(beat)
echo "$said" | grep -q "^ok.*a planner pass" || { echo "FAILED: 9 s into a pass, heartbeat_s 6, health says: $said"; exit 1; }
echo "ok  9 s into a 12 s pass, past the limit: $said"

i=0; while [ -e "$W/in-pass" ]; do i=$((i + 1)); [ $i -lt 100 ] || { echo "FAILED: the pass never ended"; exit 1; }; sleep 0.1; done
sleep 0.5
said=$(beat)
echo "$said" | grep -q "^ok.*a planner pass" || { echo "FAILED: the pass over, the loop in its poll's sleep, health says: $said"; exit 1; }
echo "ok  the pass over and the next beat not yet come: $said"

sleep 5
grep -q planning_since "$Q/keeper.json" && { echo "FAILED: keeper.json keeps the pass after the next beat"; exit 1; }
said=$(beat)
echo "$said" | grep -q "^ok" || { echo "FAILED: after the next beat: $said"; exit 1; }
echo "ok  at the next beat the pass's stamp is gone: $said"

kill -STOP "$pid"
sleep 8
said=$(beat)
kill -CONT "$pid"
echo "$said" | grep -q "^BAD.*stuck" || { echo "FAILED: a loop held 8 s with no pass, heartbeat_s 6, says: $said"; exit 1; }
echo "ok  a loop held 8 s with no pass since its beat: $said"
echo PASS
