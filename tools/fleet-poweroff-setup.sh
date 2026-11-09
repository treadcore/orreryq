#!/bin/sh
# Let the fleet power this machine off and restart it, and nothing else (fleet-queue's
# shutdown-now and Restart; docs/fleet-train.md section 5).
#
# Run it ON THE MACHINE, once, as root (orrery's Machines view: the recipe "Let the fleet power
# it off and restart it"):
#
#   cd ~/orrery-recipes && doas sh fleet-poweroff-setup.sh      (Alpine, Copal)
#   cd ~/orrery-recipes && sudo sh fleet-poweroff-setup.sh      (Ubuntu)
#
# It writes two rules: the user named (USER_NAME=, default "user") may run the power-off command
# and the reboot command as root without a password. No other command is allowed by them (Paul,
# 8 November: "i would like to be able to reboot on command. can we set that up on every
# machine"). Each is its own file, so that the probe, as the user, can see which is there: doas's
# rules are root's to read, but not their names. It prints the "poweroff" and "reboot" lines for
# the host's entry in the queue's config.json; the probe copies them there itself. Run again, it
# writes the same rules. To take one away: delete its file (/etc/doas.d/fleet-poweroff.conf and
# fleet-reboot.conf, or /etc/sudoers.d/fleet-poweroff and fleet-reboot).
set -eu

U="${USER_NAME:-user}"
[ "$(id -u)" = 0 ] || { echo "run as root (doas or sudo)" >&2; exit 1; }
id "$U" >/dev/null 2>&1 || { echo "no user $U here" >&2; exit 1; }

# One doas rule in its own file, proved by doas -C before it is put in place.
doas_rule() {   # NAME COMMAND WHAT
    f=/etc/doas.d/fleet-$1.conf
    printf '# Written by orrery tools/fleet-poweroff-setup.sh: the fleet may %s this machine.\npermit nopass %s as root cmd %s\n' "$3" "$U" "$2" > "$f.tmp"
    chmod 0400 "$f.tmp"
    doas -C "$f.tmp" >/dev/null 2>&1 || { rm -f "$f.tmp"; echo "doas rejected the $1 rule; nothing changed" >&2; exit 1; }
    mv "$f.tmp" "$f"
    echo "wrote $f"
}

# One sudoers rule in its own file, proved by visudo before it is put in place.
sudo_rule() {   # NAME COMMAND WHAT
    f=/etc/sudoers.d/fleet-$1
    printf '# Written by orrery tools/fleet-poweroff-setup.sh: the fleet may %s this machine.\n%s ALL=(root) NOPASSWD: %s\n' "$3" "$U" "$2" > "$f.tmp"
    chmod 0440 "$f.tmp"
    visudo -cf "$f.tmp" >/dev/null || { rm -f "$f.tmp"; echo "visudo rejected the $1 rule; nothing changed" >&2; exit 1; }
    mv "$f.tmp" "$f"
    echo "wrote $f"
}

if [ -d /etc/doas.d ] && command -v doas >/dev/null; then
    P=$(command -v poweroff || echo /sbin/poweroff)
    R=$(command -v reboot || echo /sbin/reboot)
    doas_rule poweroff "$P" "power off"
    doas_rule reboot "$R" "restart"
    echo "config.json, this host: \"poweroff\": \"doas -n $P\", \"reboot\": \"doas -n $R\""
elif [ -d /etc/sudoers.d ] && command -v sudo >/dev/null; then
    S=$(command -v systemctl || true)
    if [ -n "$S" ]; then
        P="$S poweroff"; R="$S reboot"
    else
        P=$(command -v poweroff || echo /sbin/poweroff); R=$(command -v reboot || echo /sbin/reboot)
    fi
    sudo_rule poweroff "$P" "power off"
    sudo_rule reboot "$R" "restart"
    echo "config.json, this host: \"poweroff\": \"sudo -n $P\", \"reboot\": \"sudo -n $R\""
else
    echo "neither doas (with /etc/doas.d) nor sudo (with /etc/sudoers.d) here; nothing changed" >&2
    exit 1
fi
