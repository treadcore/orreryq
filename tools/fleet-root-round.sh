#!/bin/sh
# fleet-root-round.sh [--dry] MACHINE... -- the root setups of 8 November on each machine, one password
# a machine, typed by you in this terminal.
#
#   sh tools/fleet-root-round.sh saskatchewan columbia jaguaribe bosporus boburner calber whitewolf
#
# On each machine, from ~/orrery-recipes (the files copied there first, as the Machines view stages
# them), under ONE doas or sudo:
#   1. fleet-poweroff-setup.sh  the power-off and restart rules: the fleet's Shut down and Restart
#                               (Paul: "i would like to be able to reboot on command ... on every machine")
#   2. fleet-auto-update.sh     the daily update, which now ends with the firmware and SMART scan
#                               (fleet-firmware.sh, with smartmontools and nvme-cli)
#   3. fleet-microcode.sh       the CPU's microcode loaded at every boot (a machine that has it is left
#                               as it is); it takes effect at the next boot, which Restart now gives
#
# ROOT IS NEVER RUN FROM ORRERY: this is ssh -t, and the password is asked for in this terminal, by
# the machine, of the person at it. Each script checks before it acts, so a second round changes
# nothing. A machine that does not answer is said and passed over. Afterwards: Machines, Probe all;
# then Restart on the Queue page, for the microcode.
set -u
T=$(cd "$(dirname "$0")" && pwd)
DRY=0
[ "${1:-}" = "--dry" ] && { DRY=1; shift; }
[ $# -gt 0 ] || { sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
FILES="fleet-poweroff-setup.sh fleet-auto-update.sh fleet-update.sh fleet-firmware.sh fleet-microcode.sh"
SSH="ssh -o ConnectTimeout=8"
ok= ; failed=
for m in "$@"; do
    case "$m" in *@*) target=$m ;; *) target=user@$m ;; esac
    echo "== $m ($target)"
    if [ "$DRY" = 1 ]; then
        echo "   copy: $FILES -> ~/orrery-recipes/"
        echo "   then: cd ~/orrery-recipes && doas|sudo sh -c 'sh fleet-poweroff-setup.sh && sh fleet-auto-update.sh && sh fleet-microcode.sh'"
        continue
    fi
    if ! $SSH -o BatchMode=yes "$target" 'mkdir -p ~/orrery-recipes' 2>/dev/null; then
        echo "   does not answer: passed over"
        failed="$failed $m"
        continue
    fi
    ( cd "$T" && scp -q -o ConnectTimeout=8 $FILES "$target:orrery-recipes/" ) || { echo "   copy failed: passed over"; failed="$failed $m"; continue; }
    root=$($SSH -o BatchMode=yes "$target" 'command -v doas >/dev/null 2>&1 && echo doas || echo sudo')
    echo "   $root asks for $m's password:"
    if $SSH -t "$target" "cd ~/orrery-recipes && $root sh -c 'sh fleet-poweroff-setup.sh && sh fleet-auto-update.sh && sh fleet-microcode.sh'"; then
        ok="$ok $m"
    else
        echo "   something failed on $m: its lines above say what"
        failed="$failed $m"
    fi
done
[ "$DRY" = 1 ] && exit 0
echo
echo "done:${ok:- none}"
[ -n "$failed" ] && echo "not done:$failed"
echo "next: Machines, Probe all (the rules reach the queue's config); then Restart, on the Queue page, where the microcode waits for a boot"
