#!/bin/sh
# fleet-radbeeper-root.sh: what only root can do for a Geiger counter to be a room probe from boot.
# Paul, 16 November: "add the concept of thermal probes. allow orrery copal fleet machines to look
# and install rad beeper if the usb tty device is a GMC 300, 500, 600 ...". tools/fleet-probes.sh
# does what the user can (look, ask, build radbeeper into ~/.cargo/bin, a service until the next
# boot); this is the rest.
#
# Run it ON THE MACHINE, once, as root. ROOT IS NEVER RUN FROM ORRERY: the password is typed by you.
# By hand, from this Mac, for one machine:
#
#   scp tools/fleet-radbeeper-root.sh tools/fleet-probes.sh user@MACHINE:orrery-recipes/
#   ssh -t user@MACHINE 'cd ~/orrery-recipes && doas sh fleet-radbeeper-root.sh'     (Alpine, Copal)
#   ssh -t user@MACHINE 'cd ~/orrery-recipes && sudo sh fleet-radbeeper-root.sh'     (Ubuntu)
#
# Or with the other root setups, one password a machine: `sh tools/fleet-root-round.sh MACHINE...`,
# once that script's list has this recipe. It does not yet. The change there is: add
# `fleet-radbeeper-root.sh fleet-probes.sh` to its FILES line, and `&& sh fleet-radbeeper-root.sh`
# to the end of the command it runs under doas or sudo (and to the --dry line that prints it).
#
#   ... fleet-radbeeper-root.sh --show    prints the files it would write, as anyone, and writes none
#   ... fleet-radbeeper-root.sh --undo    takes the service, the rule and the starter away
#
# WHAT IT DOES, each checked before it is done, so a second run changes nothing:
#   1. The user (the one who ran doas or sudo) into the group that owns the serial ports, dialout:
#      it counts from that user's next login.
#   2. /var/lib/radbeeper, root:dialout, mode 2775: one log for the service and for the user, and
#      where the collector (fleet-telemetry.sh) reads room.radXXXX.c from.
#   A MACHINE COPAL HAS SET UP (its own /etc/init.d/radbeeper, stage 10) IS LEFT THERE: its service
#   is Copal's, and is not rewritten, restarted or stopped from here.
#   3. /usr/local/bin/radbeeper: the user's own build (~/.cargo/bin/radbeeper, made by
#      `fleet-probes.py QUEUE install MACHINE`), copied. With no build there it says so and stops
#      after 1 and 2.
#   4. /usr/local/sbin/fleet-radbeeper-serve.sh, the starter: it reads each USB serial port's
#      identity from sysfs and gives radbeeper ONLY the ports that have a counter's (the ACCEPT
#      list of fleet-probes.sh, read from the copy beside this file). A radbeeper left to look for
#      itself opens every port, and opening a radio's port restarts the radio. No such port: it
#      writes why to /var/lib/radbeeper/status and stops, which is the normal state.
#   5. The boot service `radbeeper`: OpenRC on Alpine (modelled on Copal's own init script),
#      systemd on Ubuntu; and a udev rule that starts it when a port with a counter's identity
#      appears. A user's service from `fleet-probes.sh serve` holds the port, so it is stopped
#      first; what it logged stays in ~/.local/share/radbeeper and is not merged.
#
# NOT DONE HERE: a second counter plugged in while the service runs with the first is not taken up
# until the service is restarted (it was given its ports by name). A GMC-300, 500 or 600 is served
# for its counts and gives no temperature: GQ-RFC1201 gives <GETTEMP>> to the GMC-320 from Re 3.01.
set -eu

BIN=/usr/local/bin/radbeeper
STARTER=/usr/local/sbin/fleet-radbeeper-serve.sh
LOGS=/var/lib/radbeeper
GROUP=dialout
RULE=/etc/udev/rules.d/60-fleet-radbeeper.rules
UNIT=/etc/systemd/system/radbeeper.service
INIT=/etc/init.d/radbeeper
MARK="orrery tools/fleet-radbeeper-root.sh wrote this"
T=$(cd "$(dirname "$0")" && pwd)

WHO=${SUDO_USER:-${DOAS_USER:-}}
[ -n "$WHO" ] && [ "$WHO" != root ] || WHO=$(stat -c %U "$T")
HOME_OF=$(getent passwd "$WHO" | cut -d: -f6)

# The identities a counter's port may have: fleet-probes.sh keeps the list, and this reads it.
ACCEPT=
for f in "$T/fleet-probes.sh" "$HOME_OF/.fleet-queue/fleet-probes.sh"; do
    [ -r "$f" ] || continue
    ACCEPT=$(sed -n 's/^ACCEPT="\([0-9a-f: ]*\)"$/\1/p' "$f" | head -n 1)
    [ -n "$ACCEPT" ] && break
done
[ -n "$ACCEPT" ] || { echo "fleet-probes.sh is not beside this file nor in $HOME_OF/.fleet-queue: it holds the list of counter identities, and without it no port is named" >&2; exit 1; }

starter_text() {
    cat <<EOF
#!/bin/sh
# $MARK: radbeeper for the ports that have a counter's USB identity, and no others.
#   fleet-radbeeper-serve.sh          serve them (what the boot service runs)
#   fleet-radbeeper-serve.sh ports    name them, opening nothing
#   fleet-radbeeper-serve.sh plugged  what the udev rule runs on OpenRC: start the service, detached
ACCEPT="$ACCEPT"
EOF
    cat <<'EOF'
ports() {
    for t in /sys/class/tty/ttyUSB* /sys/class/tty/ttyACM*; do
        [ -e "$t" ] || continue
        d=$(readlink -f "$t/device") || continue
        while [ -n "$d" ] && [ "$d" != / ] && [ ! -r "$d/idVendor" ]; do d=${d%/*}; done
        [ -r "$d/idVendor" ] || continue
        case " $ACCEPT " in *" $(cat "$d/idVendor"):$(cat "$d/idProduct") "*) echo "/dev/${t##*/}" ;; esac
    done
}
case "${1:-}" in
    ports) ports; exit 0 ;;
    plugged)
        # udev kills a child that outlives its event; six seconds lets the node reach its group
        # and a person's own monitor take the port first (as Copal's radbeeper-plugged does).
        setsid /bin/sh -c 'sleep 6; rc-service radbeeper status >/dev/null 2>&1 || rc-service radbeeper start >/dev/null 2>&1' >/dev/null 2>&1 </dev/null &
        exit 0 ;;
esac
devs=
for p in $(ports); do devs="$devs --device $p"; done
if [ -z "$devs" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S')  dormant: no USB serial port here has a counter's identity ($ACCEPT)" > /var/lib/radbeeper/status
    exit 0
fi
umask 002
# shellcheck disable=SC2086
exec /usr/local/bin/radbeeper service $devs --logs /var/lib/radbeeper
EOF
}

init_text() {
    cat <<EOF
#!/sbin/openrc-run
# $MARK, after Copal's own init script for radbeeper.
# Dormant is the normal state on a machine with no counter: stopped, the reason in
# $LOGS/status. It looks again at the next boot, or when a counter is plugged in.
name="radbeeper"
description="Geiger counter monitor and room thermometer (dormant when no counter is present)"
command="$STARTER"
command_background=true
# The service is root's and the log is also the user's: files the group can write.
umask=002
pidfile="/run/radbeeper.pid"
output_log="/var/log/radbeeper/service.log"
error_log="/var/log/radbeeper/service.log"

depend() {
	after coldplug udev-postmount modules
	need localmount
}

start_pre() {
	checkpath -d -m 0755 /var/log/radbeeper
	checkpath -d -m 2775 -o root:$GROUP $LOGS
	if [ -n "\$($STARTER ports)" ]; then
		return 0
	fi
	$STARTER >/dev/null 2>&1 || true
	einfo "No port with a counter's USB identity -- radbeeper stays dormant."
	einfo "Why: cat $LOGS/status"
	return 1
}
EOF
}

unit_text() {
    cat <<EOF
# $MARK.
[Unit]
Description=radbeeper: Geiger counter monitor and room thermometer (dormant when no counter is present)
After=local-fs.target systemd-udevd.service

[Service]
ExecStart=$STARTER
UMask=0002
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF
}

rule_text() {
    echo "# $MARK: start the logger when a port with a counter's USB identity appears."
    for id in $ACCEPT; do
        if [ "$1" = systemd ]; then
            echo "ACTION==\"add\", SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"${id%:*}\", ATTRS{idProduct}==\"${id#*:}\", TAG+=\"systemd\", ENV{SYSTEMD_WANTS}+=\"radbeeper.service\""
        else
            echo "ACTION==\"add\", SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"${id%:*}\", ATTRS{idProduct}==\"${id#*:}\", RUN+=\"$STARTER plugged\""
        fi
    done
}

if [ "${1:-}" = "--show" ]; then
    echo "for the user $WHO; counter identities: $ACCEPT"
    echo "== $STARTER"; starter_text
    echo "== $INIT (Alpine)"; init_text
    echo "== $UNIT (Ubuntu)"; unit_text
    echo "== $RULE (Alpine)"; rule_text openrc
    echo "== $RULE (Ubuntu)"; rule_text systemd
    exit 0
fi

[ "$(id -u)" = 0 ] || { echo "run as root (doas or sudo)" >&2; exit 1; }

ours() { [ -e "$1" ] && grep -q "$MARK" "$1"; }

if [ "${1:-}" = "--undo" ]; then
    if ours "$UNIT"; then
        systemctl disable --now radbeeper.service 2>/dev/null || true
        rm -f "$UNIT"; systemctl daemon-reload
    fi
    if ours "$INIT"; then
        rc-service radbeeper stop 2>/dev/null || true
        rc-update del radbeeper default >/dev/null 2>&1 || true
        rm -f "$INIT"
    fi
    if ours "$RULE"; then rm -f "$RULE"; udevadm control --reload 2>/dev/null || true; fi
    if ours "$STARTER"; then rm -f "$STARTER"; fi
    echo "taken away: the service, the udev rule and the starter, where this wrote them. Left: $BIN, $LOGS and its logs, and $WHO in $GROUP"
    exit 0
fi

# put FILE MODE: the text on stdin becomes FILE if it differs; says which, and counts a change.
changed=0
put() {
    tmp=$1.fleet-new
    cat > "$tmp"
    if [ -e "$1" ] && cmp -s "$tmp" "$1"; then
        rm -f "$tmp"; echo "as it was: $1"
    else
        chmod "$2" "$tmp"; mv "$tmp" "$1"; changed=1; echo "written: $1"
    fi
}

# 1. the group
getent group "$GROUP" >/dev/null || { addgroup -S "$GROUP" 2>/dev/null || groupadd -r "$GROUP"; echo "the group $GROUP: made"; }
if id -nG "$WHO" | tr ' ' '\n' | grep -qx "$GROUP"; then
    echo "$WHO is in $GROUP already"
else
    if command -v usermod >/dev/null 2>&1; then usermod -aG "$GROUP" "$WHO"; else addgroup "$WHO" "$GROUP"; fi
    echo "$WHO added to $GROUP: it counts from $WHO's next login"
fi

# 2. the log directory
mkdir -p "$LOGS"
if [ "$(stat -c '%U:%G %a' "$LOGS")" = "root:$GROUP 2775" ]; then
    echo "as it was: $LOGS (root:$GROUP 2775)"
else
    chown root:"$GROUP" "$LOGS"; chmod 2775 "$LOGS"; echo "$LOGS: root:$GROUP, mode 2775"
fi

# Copal's own service is Copal's.
if [ -e "$INIT" ] && ! ours "$INIT"; then
    echo "Copal's own radbeeper service is here ($INIT): left as it is, not restarted. Its radbeeper is updated by Copal (copal-build radbeeper, then the service restarted by you)"
    if "$BIN" --help 2>/dev/null | grep -q -- '--no-temp'; then echo "its radbeeper logs temperature"; else echo "its radbeeper does NOT log temperature yet"; fi
    exit 0
fi

# 3. the program
SRC=$HOME_OF/.cargo/bin/radbeeper
if [ -x "$SRC" ] && "$SRC" --version >/dev/null 2>&1; then
    if [ -e "$BIN" ] && cmp -s "$SRC" "$BIN"; then
        echo "as it was: $BIN ($("$BIN" --version | head -n 1))"
    else
        install -m 0755 -o root -g root "$SRC" "$BIN"; changed=1
        echo "$BIN: copied from $SRC ($("$BIN" --version | head -n 1))"
    fi
elif [ -x "$BIN" ] && "$BIN" --version >/dev/null 2>&1; then
    echo "no build of $WHO's at $SRC: $BIN is used as it stands ($("$BIN" --version | head -n 1))"
else
    echo "no radbeeper: neither $SRC nor $BIN. Run, from the Mac: python3 tools/fleet-probes.py QUEUE install $(hostname); then this again. The group and the directory are done"
    exit 0
fi
"$BIN" --help 2>/dev/null | grep -q -- '--no-temp' || echo "this radbeeper does NOT log temperature: it is older than 16 November 2026. install again, then this again"

# 4. the starter
mkdir -p "$(dirname "$STARTER")"
starter_text | put "$STARTER" 0755

# 5. the boot service and the rule
if command -v rc-update >/dev/null 2>&1; then kind=openrc
elif command -v systemctl >/dev/null 2>&1; then kind=systemd
else echo "neither OpenRC (Alpine) nor systemd (Ubuntu) here: no boot service is written" >&2; exit 1; fi
if [ "$kind" = openrc ]; then init_text | put "$INIT" 0755; else unit_text | put "$UNIT" 0644; fi
if [ -d /etc/udev/rules.d ]; then
    rule_text "$kind" | put "$RULE" 0644
    udevadm control --reload 2>/dev/null || true
fi

# A user's own service holds the port the boot service wants.
for pid in $(ps -eo pid=,user=,args= | awk -v u="$WHO" '$2 == u && /radbeeper/ && / service( |$)/ { print $1 }'); do
    kill "$pid" 2>/dev/null && { echo "$WHO's own radbeeper service (pid $pid) stopped: the boot service takes its ports. Its logs stay in $HOME_OF/.local/share/radbeeper"; changed=1; sleep 3; }
done

if [ "$kind" = openrc ]; then
    rc-update add radbeeper default >/dev/null 2>&1 || true
    if [ "$changed" = 1 ] || ! rc-service radbeeper status >/dev/null 2>&1; then
        rc-service radbeeper restart >/dev/null 2>&1 || true
        echo "the service: started where a counter is, and at every boot (rc-update, default)"
    else
        echo "the service: running, as it was"
    fi
else
    [ "$changed" = 1 ] && systemctl daemon-reload
    systemctl enable radbeeper.service >/dev/null 2>&1
    if [ "$changed" = 1 ] || ! systemctl is-active --quiet radbeeper.service; then
        systemctl restart radbeeper.service
        echo "the service: radbeeper.service, started where a counter is, and enabled"
    else
        echo "the service: radbeeper.service running, as it was"
    fi
fi

# What it is doing, said plainly.
sleep 8
echo "ports with a counter's identity ($ACCEPT):$(for p in $("$STARTER" ports); do printf ' %s' "$p"; done)"
echo "status ($LOGS/status): $(cat "$LOGS/status" 2>/dev/null || echo none yet)"
ls "$LOGS"/temp-*-"$(date +%Y-%m)".tsv >/dev/null 2>&1 && echo "a temperature log is being written: the collector reports it as room.radXXXX.c" \
    || echo "no temperature log yet: a GMC-320 from Re 3.01 gives one within a minute of starting; a GMC-300, 500 or 600 gives counts and no temperature"
