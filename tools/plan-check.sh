#!/bin/sh
# WHEN THE KEEPER ASKS THE PLANNER (the duty-cycle report's changes A and B), against a real keeper
# with no fleet: every lane is this machine (target "-"), the planner a stub that writes down each
# time it is asked. Each line is a claim; the first false one ends it.
#
#     sh tools/plan-check.sh [KEEPER]     KEEPER: another fleet-queue.py to compare (the old one)
set -eu
T=$(cd "$(dirname "$0")" && pwd)
K=${1:-$T/fleet-queue.py}
W=$(mktemp -d)
stub() { # the planner: it writes the time it was asked, and once (A file there) asks for a chain's step
    cat > "$W/planner.sh" <<E
#!/bin/sh
case "\$2" in
  plan) date +%s >> "\$1/asked"
        if [ -e "\$1/give" ]; then rm -f "\$1/give"; cat "\$1/give.json"; else echo "[]"; fi ;;
  *) true ;;
esac
E
    chmod +x "$W/planner.sh"
}
keeper() { # QUEUE CONFIG: a keeper on QUEUE, started
    mkdir -p "$1"; printf '%s\n' "$2" > "$1/config.json"
    python3 "$K" "$1" ensure >/dev/null
    i=0; until [ -s "$1/keeper.pid" ]; do i=$((i + 1)); [ $i -lt 100 ] || { echo "FAILED: no keeper"; exit 1; }; sleep 0.1; done
}
stop() { python3 "$K" "$1" stop-now >/dev/null 2>&1 || true; sleep 1; }
asked() { [ -e "$1/asked" ] && wc -l < "$1/asked" | tr -d ' ' || echo 0; }
stub

# A. Eight GPU jobs queued (the islands' buffer), the CPU's queue empty: the low water is the CPU's.
A=$W/a
mkdir -p "$A"
trap 'stop $A; stop $W/b; rm -rf "$W"' EXIT
keeper "$A" "{\"hosts\": [{\"name\": \"cpu1\", \"target\": \"-\", \"caps\": [\"cpu\"]}, {\"name\": \"gpu1\", \"target\": \"-\", \"caps\": [\"cuda\"]}],
 \"planner\": \"$W/planner.sh $A\", \"poll_s\": 1, \"keep_awake\": false, \"sync_s\": 0, \"chores_s\": 0, \"low_water\": 7,
 \"plan_s\": 3600, \"starve_idle_s\": 3600, \"starve_s\": 3600, \"low_min_s\": 3, \"idle_flag_s\": 0}"
for n in 1 2 3 4 5 6 7 8 9; do
    printf '{"id": "x-%s", "kind": "crucible", "title": "segment %s", "needs": "cuda", "cmd": "sleep 60"}\n' $n $n > "$A/x$n.in"
    python3 "$K" "$A" add "$A/x$n.in" >/dev/null
done
first=$(asked "$A")
sleep 12
n=$(( $(asked "$A") - first ))
if [ "$K" = "$T/fleet-queue.py" ]; then
    { [ $n -ge 2 ] && [ $n -le 5 ]; } || { echo "FAILED: the planner asked $n times in 12 s"; exit 1; }
    echo "ok  eight GPU jobs queued and the CPU's empty: the planner asked $n times in 12 s, each low_min_s (3 s) at most"
else
    echo "the keeper given ($K): the planner asked $n times in 12 s"
fi
stop "$A"

# B. A chain's step comes back: the planner is asked within replan_after_s, not at plan_s.
B=$W/b
printf '[{"id": "r1-k01", "kind": "census", "title": "transform r1: step 1 of 30", "needs": "cpu", "cmd": "sleep 2", "replan": true}]\n' > "$W/give.json"
mkdir -p "$B"; cp "$W/give.json" "$B/give.json"; touch "$B/give"
keeper "$B" "{\"hosts\": [{\"name\": \"cpu1\", \"target\": \"-\", \"caps\": [\"cpu\"]}],
 \"planner\": \"$W/planner.sh $B\", \"poll_s\": 1, \"keep_awake\": false, \"sync_s\": 0, \"chores_s\": 0, \"low_water\": 0,
 \"plan_s\": 3600, \"starve_idle_s\": 3600, \"starve_s\": 3600, \"replan_after_s\": 2, \"idle_flag_s\": 0}"
i=0; until grep -q '"event": "done", "job": "r1-k01"' "$B/events.jsonl" 2>/dev/null; do i=$((i + 1)); [ $i -lt 60 ] || { echo "FAILED: the step never came back"; exit 1; }; sleep 0.5; done
back=$(date +%s); before=$(asked "$B")
i=0; until [ "$(asked "$B")" -gt "$before" ]; do i=$((i + 1)); [ $i -lt 30 ] || break; sleep 0.5; done
if [ "$K" = "$T/fleet-queue.py" ]; then
    [ "$(asked "$B")" -gt "$before" ] || { echo "FAILED: not asked after the step came back"; exit 1; }
    echo "ok  a chain's step came back and the planner was asked $(( $(tail -1 "$B/asked") - back )) s later (replan_after_s 2; plan_s 3600)"
    sleep 2
    python3 "$K" "$B" health | grep "planning" | grep -q "a chain's step last asked for one" || { echo "FAILED: health says"; python3 "$K" "$B" health | grep planning; exit 1; }
    echo "ok  health says when a chain's step last asked, and how long a pass takes"
else
    [ "$(asked "$B")" -gt "$before" ] && echo "the keeper given: asked after the step" || echo "the keeper given: not asked within 15 s of the step's return"
fi
echo "PASS"
