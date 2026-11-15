#!/bin/sh
# leftover-check.sh KEEPER.py MACHINE: a real job on a real machine, its connection closed under it.
# Each line is a claim. The job writes a line a second to a file on the machine; a copy left running
# shows as two writers.
set -u
K=$1; M=$2; Q=$(mktemp -d)/grove; mkdir -p "$Q"; ID=lefttest$$
q() { python3 "$K" "$Q" "$@"; }
trap 'q stop-now >/dev/null 2>&1; sleep 2; ssh -o BatchMode=yes user@$M "rm -f ~/lefttest-*.txt" 2>/dev/null' EXIT
cat > "$Q/config.json" <<J
{"hosts": [{"name": "$M", "target": "user@$M", "caps": ["cpu"]}], "poll_s": 1, "keep_awake": false, "sync_s": 0, "low_water": 0}
J
echo '{}' > "$Q/machines.json"
cat > "$Q/j.in" <<J
{"id": "$ID", "kind": "k", "title": "$ID", "needs": "cpu", "cmd": "while :; do echo \$\$ >> ~/lefttest-$ID.txt; sleep 1; done"}
J
q resume >/dev/null; q add "$Q/j.in" >/dev/null
writers() { ssh -o BatchMode=yes user@$M "tail -6 ~/lefttest-$ID.txt 2>/dev/null | sort -u | wc -l" | tr -d ' '; }
i=0; until ls "$Q"/running/*/ 2>/dev/null | grep -q $ID && [ "$(writers)" = 1 ]; do i=$((i+1)); [ $i -lt 40 ] || { echo "FAILED: the job never ran"; exit 1; }; sleep 1; done
echo "ok  the job runs on $M: 1 writer"
ssh -O exit user@$M 2>/dev/null; echo "    (the shared connection to $M closed under it)"
i=0; until grep -q '"requeued"' "$Q/events.jsonl" 2>/dev/null; do i=$((i+1)); [ $i -lt 90 ] || { echo "FAILED: never put back"; tail -3 "$Q/events.jsonl"; exit 1; }; sleep 1; done
echo "ok  put back: $(grep -c '"requeued"' "$Q/events.jsonl") time(s); the log says: $(grep 'ssh failed' "$Q/logs/$ID.log" | tail -1)"
i=0; until [ "$(grep -c '"started"' "$Q/events.jsonl")" -ge 2 ]; do i=$((i+1)); [ $i -lt 60 ] || { echo "FAILED: not started again"; exit 1; }; sleep 1; done
sleep 8; w=$(writers)
[ "$w" = 1 ] && echo "ok  started again, and still 1 writer on $M: the first copy was stopped" || echo "FAILED: $w writers on $M: the first copy runs on beside the second"
