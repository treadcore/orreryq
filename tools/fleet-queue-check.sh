#!/bin/sh
# The machine and project buttons, against a real keeper and real jobs, with no
# fleet: every lane is this machine (target "-"), so a stopped job is really
# stopped. Each line is a claim; the first false one ends it.
#
#     sh tools/fleet-queue-check.sh
set -eu
T=$(cd "$(dirname "$0")" && pwd)
Q=$(mktemp -d)/grove
mkdir -p "$Q"
q() { python3 "$T/fleet-queue.py" "$Q" "$@"; }
trap 'q stop-now >/dev/null 2>&1 || true; sleep 1' EXIT
lane() { python3 -c "import json;print(json.load(open('$Q/lanes/$1.json'))['state'])" 2>/dev/null || echo none; }
where() { for d in queue done stopped failed; do ls "$Q/$d" | grep -q "$1" && { echo "$d"; return; }; done; ls "$Q"/running/* 2>/dev/null | grep -q "$1" && echo running || echo nowhere; }
wait_for() { # what it should say, then the command saying it
    want=$1; shift; i=0
    until [ "$("$@")" = "$want" ]; do
        i=$((i + 1)); [ $i -lt 60 ] || { echo "FAILED: $* said $("$@"), not $want"; exit 1; }
        sleep 0.5
    done
    echo "ok  $* -> $want"
}
job() { cat > "$Q/$1.in" <<E
{"id": "$1", "kind": "$2", "title": "$1", "needs": "cpu", "cmd": "$3"}
E
q add "$Q/$1.in" >/dev/null; }
cat > "$Q/config.json" <<E
{"hosts": [{"name": "a", "target": "-", "caps": ["cpu"]}, {"name": "b", "target": "-", "caps": ["cpu"]}],
 "projects": {"one": {"caps": "cpu"}, "two": {"caps": "cpu", "kinds": ["k2"]}},
 "poll_s": 1, "keep_awake": false, "sync_s": 0, "low_water": 0}
E
cat > "$Q/machines.json" <<E
{"spare": {"target": "-", "facts": {}}}
E

# Resume from a shut-down queue: the switches a stop leaves must not stop it again.
touch "$Q/SHUTDOWN" "$Q/STOP_NOW" "$Q/STOP_ADDING"
q resume >/dev/null
wait_for idle lane a
[ ! -e "$Q/STOP_ADDING" ] && echo "ok  resume takes the drain off, or the keeper would end at once"

q machine a pause >/dev/null; wait_for paused lane a
job j1 k1 "sleep 60"
wait_for running where j1
python3 -c "import json;assert json.load(open('$Q/lanes/b.json'))['job']=='j1'" && echo "ok  only the machine not paused took the job"

q machine b stop >/dev/null
wait_for queue where j1
wait_for paused lane b
[ "$(grep -c 'goes back on the queue' "$Q/logs/j1.log")" = 1 ] && echo "ok  a stopped machine's job went back, not to stopped/"

q assign a one off >/dev/null; q machine a resume >/dev/null
wait_for idle lane a
sleep 3; [ "$(where j1)" = queue ] && echo "ok  a machine taken off a project leaves that project's job on the queue"
job j2 k2 "true"
wait_for done where j2
q assign a one on >/dev/null
wait_for running where j1

q project one stop >/dev/null
wait_for queue where j1
sleep 3; [ "$(where j1)" = queue ] && echo "ok  a project stopped stays stopped"
q project one resume >/dev/null
wait_for running where j1
q stop-job j1 >/dev/null; wait_for stopped where j1

# REMOVE IS AT ONCE (Paul, 7 November): the job in hand goes back on the queue and the machine leaves now.
job r1 k1 "sleep 60"
wait_for running where r1
q machine a remove >/dev/null
wait_for queue where r1
wait_for removed lane a
[ "$(grep -c 'goes back on the queue' "$Q/logs/r1.log")" = 1 ] && echo "ok  a machine removed with a job in hand sent it back and left at once"
python3 -c "import json;c=json.load(open('$Q/config.json'));assert [h['name'] for h in c['bench']]==['a']" && echo "ok  a removed machine waits on the bench"
q machine a add >/dev/null; wait_for running where r1
q stop-job r1 >/dev/null; wait_for stopped where r1
# FINISH, THEN REMOVE: nothing new starts, the job in hand ends as it would, then the machine leaves by itself.
job f1 k1 "sleep 4"
wait_for running where f1
q machine a finish >/dev/null
job f2 k1 "true"
q status --json | python3 -c "
import json,sys
r={x['name']:x for x in json.load(sys.stdin)['roster']}
assert r['a']['state']=='leaving' and r['a']['leaving'] and r['a']['paused'], r['a']" && echo "ok  a finishing machine says it is leaving"
sleep 1; [ "$(where f2)" = queue ] && echo "ok  a finishing machine takes nothing new"
wait_for done where f1
wait_for removed lane a
python3 -c "import json;c=json.load(open('$Q/config.json'));b=[h for h in c['bench'] if h['name']=='a'];assert b and 'leaving' not in b[0], c" && echo "ok  its job finished, not sent back, and then it left for the bench"
[ "$(grep -c 'goes back on the queue' "$Q/logs/f1.log")" = 0 ] && echo "ok  nothing of a finishing machine's job was cut"
q machine a add >/dev/null; wait_for done where f2
# A pause takes a Finish back: the machine stays in the queue.
job f3 k1 "sleep 4"
wait_for running where f3
q machine a finish >/dev/null; q machine a pause >/dev/null
wait_for done where f3
sleep 2; [ "$(lane a)" = paused ] && echo "ok  Pause after Finish keeps the machine in the queue"
q machine a resume >/dev/null; wait_for idle lane a
q machine spare add >/dev/null; wait_for idle lane spare
# THE CPU LIMITER: a machine told 2 CPUs runs its jobs believing it has 2, a shell under it too;
# a number not a power of two is refused; "all" lifts it.
q machine a cpus 2 >/dev/null; q machine spare cpus 2 >/dev/null
job c1 k1 'echo $(nproc 2>/dev/null || sysctl -n hw.ncpu) $THREADS $(bash -c \"nproc 2>/dev/null || sysctl -n hw.ncpu\") > '"$Q"'/cpus.txt'
wait_for done where c1
[ "$(cat "$Q/cpus.txt")" = "2 2 2" ] && echo "ok  a machine told 2 CPUs: its job, its threads and a shell under it all see 2"
q machine a cpus 3 >/dev/null 2>&1 && { echo "FAILED: 3 CPUs taken"; exit 1; } || echo "ok  3 is not a power of two: refused"
q machine a cpus all >/dev/null
python3 -c "import json;c=json.load(open('$Q/config.json'));a=[h for h in c['hosts'] if h['name']=='a'][0];assert 'cpus' not in a" && echo "ok  all lifts the limit"
q status --json | python3 -c "
import json,sys
r={x['name']:x for x in json.load(sys.stdin)['roster']}
assert r['spare']['joined'] and r['a']['joined'] and r['b']['paused'], r
assert r['a']['on']=={'one':True,'two':True}, r['a']
assert r['spare']['cpus']==2 and r['a']['cpus'] is None, (r['spare'], r['a'])" && echo "ok  the status says all of it, each machine's CPUs with it"
# RESTART: nothing new, the job in hand ends, the reboot is sent, and the machine takes work again
# when it answers with another boot id. Here "a" reboots by writing its boot id file.
q machine b restart >/dev/null 2>&1 && { echo "FAILED: b restarted with no restart rule"; exit 1; } || echo "ok  a machine with no restart rule is refused, and told what to apply"
printf one > "$Q/bootid"
python3 - "$Q" <<'PY'
import json, sys
p = sys.argv[1] + "/config.json"
c = json.load(open(p))
c["restart_poll_s"] = 1
for h in c["hosts"]:
    if h["name"] == "a":
        h["reboot"] = "printf x >> %s/bootid" % sys.argv[1]
        h["boot_id_cmd"] = "cat %s/bootid" % sys.argv[1]
json.dump(c, open(p, "w"))
PY
q machine b pause >/dev/null; q machine spare pause >/dev/null
job x1 k1 "sleep 4"
wait_for running where x1
q machine a restart >/dev/null
q status --json | python3 -c "
import json,sys
r={x['name']:x for x in json.load(sys.stdin)['roster']}
assert r['a']['restarting'] and r['a']['state']=='restarting after its job', r['a']
assert r['a']['can_restart'] and not r['b']['can_restart'], (r['a'], r['b'])" && echo "ok  a restarting machine says so, while its job runs; the status says who can restart"
job x2 k1 "true"
sleep 1; [ "$(where x2)" = queue ] && echo "ok  a restarting machine takes nothing new"
wait_for done where x1
i=0; until grep -q '"machine back from restart"' "$Q/events.jsonl"; do i=$((i + 1)); [ $i -lt 40 ] || { echo "FAILED: a never came back"; exit 1; }; sleep 0.5; done
grep -q '"machine rebooting"' "$Q/events.jsonl" && [ "$(cat "$Q/bootid")" = onex ] && echo "ok  after the job, the reboot was sent, and the new boot id read as its return"
wait_for done where x2
python3 -c "import json;c=json.load(open('$Q/config.json'));a=[h for h in c['hosts'] if h['name']=='a'][0];assert 'restarting' not in a and 'paused' not in a, a" && echo "ok  back, it is in the queue and takes work again"
# RESTART NOW: the job in hand goes back on the queue first, and runs again once the machine is back.
job x3 k1 "sleep 6"
wait_for running where x3
q machine a restart now >/dev/null
i=0; until [ "$(grep -c '"machine back from restart"' "$Q/events.jsonl")" = 2 ]; do i=$((i + 1)); [ $i -lt 60 ] || { echo "FAILED: a never came back from restart now"; exit 1; }; sleep 0.5; done
grep -q '"requeued", "job": "x3"' "$Q/events.jsonl" && [ "$(cat "$Q/bootid")" = onexx ] && echo "ok  restart now sent the job in hand back, then rebooted, and the machine came back"
wait_for done where x3
echo "PASS"
