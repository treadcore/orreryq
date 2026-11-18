#!/bin/sh
# fleet-wol.sh: arm a machine's network card to wake it from off, as root. Paul, 17 November: "wake on
# lan. supermicro. x8dtl-if wake on lan. I might need to enter bios. I can set that up. So prepare to
# issue wake on lans on command with the script. also trigger shutdown."
#
# THREE THINGS MUST ALL BE SO for a packet to start a machine that was shut down:
#   1. the BIOS lets the card wake the board (on a Supermicro X8: Advanced, then the ACPI or the
#      power settings; the item is named Wake On LAN, or PME, or Resume On LAN; and the board must
#      keep standby power, so the supply's switch stays on). This is a person at the BIOS.
#   2. Linux leaves the card armed when it powers off: `ethtool -s DEV wol g`. That is this script,
#      and it does not last through a reboot unless it is said again at every boot, which `on` sets up.
#   3. the packet reaches the card: the same network, sent to its broadcast address. That is
#      tools/hearth-hold.py's `wake NAME`, from the Mac.
#
# Run it ON THE MACHINE, as root, by hand (it is NOT part of tools/fleet-root-round.sh and nothing
# calls it):
#
#   doas sh fleet-wol.sh show      the card on the default route, what it supports and how it is set
#   doas sh fleet-wol.sh on        arm it for the magic packet now, and at every boot
#   doas sh fleet-wol.sh off       disarm it, and take the boot line away
#
# From the Mac, for machine NAME:
#   scp tools/fleet-wol.sh user@NAME: && ssh -t user@NAME 'doas sh fleet-wol.sh on'
#
# `on` installs ethtool where it is missing (apk or apt). The boot line is /etc/local.d/wol.start on
# Alpine and Copal (the `local` service, which it enables), and a systemd unit elsewhere.
#
# NOT TRIED ON ANY MACHINE OF THE FLEET (17 November). Checked for syntax only.
set -eu
DEV=$(ip -o route get 1.1.1.1 2>/dev/null | sed -n 's/.* dev \([^ ]*\).*/\1/p')
[ -n "$DEV" ] || { echo "no default route: which card to arm is not known"; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

show() {
    echo "card: $DEV, address $(cat /sys/class/net/$DEV/address)"
    echo "the kernel's wake switch for it: $(cat /sys/class/net/$DEV/device/power/wakeup 2>/dev/null || echo not told)"
    if have ethtool; then
        ethtool "$DEV" 2>/dev/null | grep -i 'wake-on' || echo "ethtool says nothing of wake-on for $DEV: run it as root"
        echo "  (g among Supports means the magic packet can wake it; Wake-on: g means it is armed, d that it is not)"
    else
        echo "ethtool is not installed: \`on\` installs it"
    fi
}

case "${1:-show}" in
show)
    show ;;
on)
    [ "$(id -u)" = 0 ] || { echo "run it as root"; exit 1; }
    if ! have ethtool; then
        if have apk; then apk add --quiet ethtool; elif have apt-get; then apt-get install -y -q ethtool; else echo "no apk or apt-get: install ethtool by hand"; exit 1; fi
    fi
    ethtool -s "$DEV" wol g
    E=$(command -v ethtool)
    if [ -d /etc/local.d ] && have rc-update; then
        printf '#!/bin/sh\n# fleet-wol.sh: armed again at every boot\n%s -s %s wol g\n' "$E" "$DEV" > /etc/local.d/wol.start
        chmod +x /etc/local.d/wol.start
        rc-update add local default >/dev/null 2>&1 || true
        echo "armed now, and at every boot by /etc/local.d/wol.start"
    elif have systemctl; then
        printf '[Unit]\nDescription=arm wake-on-LAN (fleet-wol.sh)\nAfter=network.target\n[Service]\nType=oneshot\nExecStart=%s -s %s wol g\n[Install]\nWantedBy=multi-user.target\n' "$E" "$DEV" > /etc/systemd/system/fleet-wol.service
        systemctl daemon-reload && systemctl enable --quiet fleet-wol.service
        echo "armed now, and at every boot by fleet-wol.service"
    else
        echo "armed now; NO boot line was set (neither /etc/local.d nor systemd): it is lost at the next boot"
    fi
    show ;;
off)
    [ "$(id -u)" = 0 ] || { echo "run it as root"; exit 1; }
    have ethtool && ethtool -s "$DEV" wol d || true
    rm -f /etc/local.d/wol.start
    if have systemctl && [ -f /etc/systemd/system/fleet-wol.service ]; then systemctl disable --quiet fleet-wol.service || true; rm -f /etc/systemd/system/fleet-wol.service; fi
    show ;;
*)
    echo "show, on or off"; exit 2 ;;
esac
