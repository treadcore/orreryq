#!/bin/sh
# A FLEET WITH NOTHING TO DO SAYS SO, AND THE HOUSEKEEPING IS THE KEEPER'S (the lab report of 4
# November, "Fifty-Four Idle Minutes", changes D and C), against a real keeper with no fleet: every
# lane is this machine (target "-"), and the planner is a stub that plans nothing and counts its
# chores. Each line is a claim; the first false one ends it.
#
#     sh tools/idle-check.sh
set -eu
T=$(cd "$(dirname "$0")" && pwd)
Q=$(mktemp -d)/grove
W=$(dirname "$Q")/work
mkdir -p "$Q" "$W"
q() { python3 "$T/fleet-queue.py" "$Q" "$@"; }
trap 'q stop-now >/dev/null 2>&1 || true; sleep 1' EXIT
where() { for d in queue done stopped failed; do ls "$Q/$d" | grep -q -- "-$1.json" && { echo "$d"; return; }; done; ls "$Q"/running/* 2>/dev/null | grep -q -- "-$1.json" && echo running || echo nowhere; }
flags() { q flags --all --json | python3 -c "import json,sys;print(sum(1 for f in json.load(sys.stdin) if f['kind']=='idle'))"; }
flag_text() { q flags --all --json | python3 -c "import json,sys;print([f['text'] for f in json.load(sys.stdin) if f['kind']=='idle'][$1])"; }
wait_for() { # what it should say, then the command saying it
    want=$1; shift; i=0
    until [ "$("$@")" = "$want" ]; do
        i=$((i + 1)); [ $i -lt 120 ] || { echo "FAILED: $* said $("$@"), not $want"; exit 1; }
        sleep 0.5
    done
    echo "ok  $* -> $want"
}
cat > "$W/planner.sh" <<E
#!/bin/sh
case "\$2" in
  plan) echo "[]" ;;
  chores) date +%s >> "$W/chores"; echo "began nothing" ;;
  *) true ;;
esac
E
chmod +x "$W/planner.sh"
cat > "$Q/config.json" <<E
{"hosts": [{"name": "a", "target": "-", "caps": ["cpu"]}, {"name": "b", "target": "-", "caps": ["cpu"]}],
 "planner": "$W/planner.sh $Q", "poll_s": 1, "keep_awake": false, "sync_s": 0, "low_water": 0,
 "starve_idle_s": 1, "starve_s": 2, "idle_flag_s": 6, "idle_end_s": 4, "chores_s": 2, "max_failures_in_a_row": 50}
E
# The night of 4 November, small: each machine's build fails on git, and the work waits behind them.
# The command holds a line like an error's; the reason must be what the job said, not what it was told.
python3 - "$Q" <<'E'
import json, sys
q = sys.argv[1]
cmd = "cat >/dev/null <<'X'\nfatal: words in the command, not what it said\nX\necho 'fatal: invalid reference: orrery/accepted' >&2; exit 128"
for h in "ab":
    json.dump({"id": "prep-" + h, "kind": "prepare", "title": "build", "needs": "host:" + h, "cmd": cmd}, open("%s/prep-%s.in" % (q, h), "w"))
json.dump({"id": "w1", "kind": "weights", "title": "w1", "needs": "cpu", "after_host": "prep-{host}", "cmd": "true"}, open(q + "/w1.in", "w"))
E
for j in prep-a prep-b w1; do q add "$Q/$j.in" >/dev/null; done
q ensure >/dev/null
wait_for failed where prep-a
wait_for failed where prep-b
wait_for queue where w1
wait_for 1 flags
flag_text 0 | grep -q "2 CPU lanes idle since" && echo "ok  two idle lanes, said once"
flag_text 0 | grep -q "the build failed on 2 machines (a, b): fatal: invalid reference: orrery/accepted (logs/prep-a.log)" \
    && echo "ok  the reason: the builds failed, with the first error the job wrote, not one in its command"
q health | grep -q "^BAD  lanes .*the build failed on 2 machines" && echo "ok  health says it too"
sleep 4; [ "$(flags)" = 1 ] && echo "ok  one flag a spell, however long it lasts"
touch "$Q/RESTART"
wait_for 2 grep -c '"event": "keeper started"' "$Q/events.jsonl"
sleep 4; [ "$(flags)" = 1 ] && echo "ok  and across the keeper's own restart"

# Work they can start: the spell ends once both are at work a while, and is said to have ended.
q stop-job w1 >/dev/null
for j in w2 w3; do printf '{"id": "%s", "kind": "weights", "title": "%s", "needs": "cpu", "cmd": "sleep 8"}\n' $j $j > "$Q/$j.in"; q add "$Q/$j.in" >/dev/null; done
wait_for 1 grep -c '"event": "idle lanes at work again"' "$Q/events.jsonl"
wait_for done where w2

# Nothing queued at all: a new spell, and its reason is the planner's.
wait_for 2 flags
flag_text 1 | grep -q "nothing queued fits a, b (0 queued); the planner was last asked at [0-9][0-9]:[0-9][0-9] and added 0" \
    && echo "ok  nothing queued: said so, with when the planner was asked and what it added"

# The housekeeping, on the keeper's clock: with no window anywhere.
n=$(wc -l < "$W/chores" | tr -d " ")
[ "$n" -ge 5 ] && echo "ok  the keeper asked for the chores $n times in $(( $(tail -1 "$W/chores") - $(head -1 "$W/chores") )) seconds"
q health | grep -q "^ok   chores .*began nothing" && echo "ok  health says when the housekeeping was last asked, and what it said"
echo "PASS"
