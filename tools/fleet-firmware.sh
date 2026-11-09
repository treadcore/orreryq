#!/bin/sh
# fleet-firmware.sh -- every part of a machine that carries firmware, and its version.
#
# Paul, 8 November: "I want copal to be able to scan and suggest or at least list version of SSD
# nvme and all upgradable firmware and version numbers. I want a report and we can scan and use
# that report to investigate whether the version codes are current."
#
#   sh fleet-firmware.sh                   the report, to stdout: as the user, everything but SMART
#   doas sh fleet-firmware.sh --save       as root: SMART, the UEFI firmware table and each NVMe
#   sudo sh fleet-firmware.sh --save       drive's firmware slots too, and the report kept at
#                                          /var/lib/fleet-firmware/report.tsv for the probe to read
#
# ONE LINE A PART, five fields and a tab between them: KIND NAME MODEL VERSION DETAIL. The kinds:
# machine, bios, cpu, disk, nic, gpu, fwupd (a device fwupd can update), update (fwupd has a newer
# release), esrt (the UEFI firmware table: what the firmware itself says it can take a capsule
# for). A field nobody can read is "-", never empty, and a reading that needs root says so in
# DETAIL rather than leaving a gap: "smart: root only" is not "healthy".
#
# NOTHING IS WRITTEN TO A DEVICE. It reads sysfs, /proc, the package database and, as root,
# smartctl, nvme-cli and fwupd's own list. Serial numbers are not printed: the report goes into
# lab reports that are published.
#
# Plain sh (busybox ash on Alpine and Copal, dash on Ubuntu); orrery's probe runs it with sh -s.
set -u

ROOT=0
[ "$(id -u)" = 0 ] && ROOT=1
SAVE=0
[ "${1:-}" = "--save" ] && SAVE=1
if [ "$SAVE" = 1 ] && [ "$ROOT" = 0 ]; then
    echo "--save keeps the report in /var/lib/fleet-firmware: run it as root (doas or sudo)" >&2
    exit 1
fi
PATH=$PATH:/sbin:/usr/sbin

row() {
    printf '%s\t%s\t%s\t%s\t%s\n' "$1" "${2:--}" "${3:--}" "${4:--}" "${5:--}"
}
# A sysfs or /proc value on one line, its runs of spaces made one, trimmed.
rd() { [ -r "$1" ] && tr -s ' \n' '  ' < "$1" 2>/dev/null | sed 's/^ *//; s/ *$//'; }
have() { command -v "$1" >/dev/null 2>&1; }

scan() {
    # ---- the machine ----------------------------------------------------------------------
    . /etc/os-release 2>/dev/null
    row machine "$(hostname)" "$(rd /sys/class/dmi/id/sys_vendor) $(rd /sys/class/dmi/id/product_name)" \
        "-" "${PRETTY_NAME:-?}; kernel $(uname -r); scanned $(date '+%Y-%m-%dT%H:%M:%S%z'); $([ $ROOT = 1 ] && echo 'as root' || echo 'as the user: no SMART')"

    # ---- the board's firmware ---------------------------------------------------------------
    if [ -r /sys/class/dmi/id/bios_version ]; then
        row bios board "$(rd /sys/class/dmi/id/board_vendor) $(rd /sys/class/dmi/id/board_name)" \
            "$(rd /sys/class/dmi/id/bios_version)" \
            "$(rd /sys/class/dmi/id/bios_date); $(rd /sys/class/dmi/id/bios_vendor); $([ -d /sys/firmware/efi ] && echo UEFI || echo 'legacy BIOS')"
    fi

    # ---- the CPU's microcode: what runs, and what the package would load --------------------
    model=$(sed -n 's/^model name[[:space:]]*: //p' /proc/cpuinfo | head -n 1 | tr -s ' ')
    mc=$(sed -n 's/^microcode[[:space:]]*: //p' /proc/cpuinfo | head -n 1)
    vendor=$(sed -n 's/^vendor_id[[:space:]]*: //p' /proc/cpuinfo | head -n 1)
    fms=$(printf '%02x-%02x-%02x' "$(sed -n 's/^cpu family[[:space:]]*: //p' /proc/cpuinfo | head -n 1)" \
        "$(sed -n 's/^model[[:space:]]*: //p' /proc/cpuinfo | head -n 1)" \
        "$(sed -n 's/^stepping[[:space:]]*: //p' /proc/cpuinfo | head -n 1)" 2>/dev/null)
    if [ -n "$mc" ]; then
        pkg=
        if have apk; then
            pkg=$(apk info -v 2>/dev/null | grep -E '^(intel|amd)-ucode-[0-9]' | head -n 1)
        elif have dpkg-query; then
            case "$vendor" in
                GenuineIntel) p=intel-microcode ;;
                *) p=amd64-microcode ;;
            esac
            pkg=$(dpkg-query -W -f '${Package}-${Version} ${Status}\n' "$p" 2>/dev/null | grep 'install ok installed' | cut -d' ' -f1)
        fi
        # Loaded at boot: Copal's grub.cfg names the image itself; Ubuntu's initramfs carries it.
        load="no package: the BIOS's own"
        if [ -n "$pkg" ]; then
            load="$pkg, not in grub.cfg"
            for c in /boot/boot/grub/grub.cfg /boot/grub/grub.cfg; do
                [ -r "$c" ] && grep -q 'ucode\.img' "$c" && load="$pkg, loaded at boot" && break
            done
            have dpkg-query && load="$pkg, in the initramfs"
        fi
        u=/lib/firmware/intel-ucode/$fms
        [ -f "$u" ] || u=$u.initramfs
        if [ -f "$u" ]; then
            load="$load; it carries 0x$(od -An -tx4 -j4 -N4 "$u" | tr -d ' ' | sed 's/^0*//')"
        fi
        row cpu cpu "$model" "$mc" "family-model-stepping $fms; $load"
    fi

    # ---- each disk ---------------------------------------------------------------------------
    for n in /sys/class/nvme/nvme*; do
        [ -r "$n/firmware_rev" ] || continue
        name=$(basename "$n")
        dev=
        for b in "$n"/nvme*n1; do [ -e "$b" ] && dev=$(basename "$b") && break; done
        size=$( [ -n "$dev" ] && awk '{printf "%.0f GB", $1 * 512 / 1e9}' "/sys/block/$dev/size" 2>/dev/null)
        row disk "$name" "$(rd "$n/model")" "$(rd "$n/firmware_rev" | tr -d ' ')" "NVMe; ${size:-?}; $(health "/dev/$name")"
    done
    for b in /sys/block/sd*; do
        [ -r "$b/device/model" ] || continue
        name=$(basename "$b")
        size=$(awk '{printf "%.0f GB", $1 * 512 / 1e9}' "$b/size" 2>/dev/null)
        rot=$( [ "$(cat "$b/queue/rotational" 2>/dev/null)" = 1 ] && echo HDD || echo SSD)
        v=$(rd "$b/device/vendor")
        [ "$v" = ATA ] && v=
        row disk "$name" "${v:+$v }$(rd "$b/device/model")" "$(rd "$b/device/rev" | tr -d ' ')" \
            "SATA $rot; ${size:-?}; $(health "/dev/$name")"
    done

    # ---- each network card -------------------------------------------------------------------
    et=
    for t in ethtool /usr/sbin/ethtool /sbin/ethtool; do have "$t" && et=$t && break; done
    for n in /sys/class/net/*; do
        [ -e "$n/device/driver" ] || continue
        i=$(basename "$n")
        drv=$(basename "$(readlink "$n/device/driver")")
        id="$(sed 's/^0x//' "$n/device/vendor" 2>/dev/null):$(sed 's/^0x//' "$n/device/device" 2>/dev/null)"
        fw=$( [ -n "$et" ] && "$et" -i "$i" 2>/dev/null | sed -n 's/^firmware-version: *//p')
        row nic "$i" "$drv, PCI $id" "${fw:--}" "$( [ -n "$et" ] || echo 'no ethtool to read it')"
    done

    # ---- the GPU's own BIOS ------------------------------------------------------------------
    if have nvidia-smi; then
        nvidia-smi --query-gpu=index,name,vbios_version,driver_version --format=csv,noheader 2>/dev/null |
        while IFS=, read -r ix nm vb dv; do
            row gpu "gpu$(echo "$ix" | tr -d ' ')" "$(echo "$nm" | sed 's/^ *//')" "$(echo "$vb" | tr -d ' ')" "NVIDIA driver$dv"
        done
    fi

    # ---- fwupd: what it can update here, and what LVFS has newer ------------------------------
    if have fwupdmgr && have python3; then
        if have systemctl && systemctl -q is-failed fwupd 2>/dev/null; then
            row fwupd fwupd "-" "-" "its service failed to start: not asked"
        else
            for q in get-devices get-updates; do
                timeout 25 fwupdmgr "$q" --json --no-unreported-check --no-metadata-check 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except ValueError:
    sys.exit()
upd = sys.argv[1] == "get-updates"
for x in d.get("Devices", []):
    flags = x.get("Flags", [])
    if not upd and "updatable" not in flags:
        continue
    rel = (x.get("Releases") or [{}])[0]
    f = ["update" if upd else "fwupd", x.get("Name") or "-", x.get("Vendor") or "-", x.get("Version") or "-",
         ("newer: %s (%s)" % (rel.get("Version"), rel.get("Summary") or "")) if upd else "updatable through fwupd"]
    print("\t".join(str(v).replace("\t", " ").replace("\n", " ") for v in f))' "$q"
            done
        fi
    fi

    # ---- as root: the UEFI firmware table ----------------------------------------------------
    for e in /sys/firmware/efi/esrt/entries/entry*; do
        [ -d "$e" ] || continue
        if [ ! -r "$e/fw_version" ]; then
            row esrt "$(basename "$e")" "-" "-" "root only"
            continue
        fi
        case "$(cat "$e/fw_type")" in
            1) ty="system firmware" ;;
            2) ty="device firmware" ;;
            3) ty="UEFI driver" ;;
            *) ty="type $(cat "$e/fw_type")" ;;
        esac
        row esrt "$(basename "$e")" "$ty $(cat "$e/fw_class")" "$(printf '0x%x' "$(cat "$e/fw_version")")" \
            "lowest it takes $(printf '0x%x' "$(cat "$e/lowest_supported_fw_version")"); last attempt $(cat "$e/last_attempt_version") status $(cat "$e/last_attempt_status")"
    done
}

# A disk's health in a few words: smartctl as root, or why not.
health() {
    [ "$ROOT" = 1 ] || { printf 'smart: root only'; return 0; }
    have smartctl || { printf 'smart: no smartctl (smartmontools)'; return 0; }
    smartctl -H -A -i "$1" 2>/dev/null | awk '
        /overall-health self-assessment test result:/ { h = $NF }
        /SMART Health Status:/                         { h = $NF }
        /^Critical Warning:/                           { if ($3 != "0x00") cw = " critical warning " $3 }
        /^Percentage Used:/                            { used = $3 }
        /^Available Spare:/                            { spare = $3 }
        /^Media and Data Integrity Errors:/            { me = $NF }
        /^Power On Hours:/                             { gsub(/,/, "", $4); poh = $4 }
        /^Temperature:/                                { t = $2 " C" }
        # SATA attributes: ID NAME FLAG VALUE WORST THRESH TYPE UPDATED WHEN_FAILED RAW
        $1 == 5   { realloc = $10 }
        $1 == 9   { poh = $10 + 0 }
        $1 == 177 || $1 == 231 || $1 == 233 || $1 == 202 { if (life == "") life = $4 }
        $1 == 194 { t = $10 " C" }
        $1 == 197 { pend = $10 }
        END {
            s = "smart " (h == "" ? "unreadable" : h)
            if (cw != "")      s = s cw
            if (used != "")    s = s ", " used " used"
            if (spare != "")   s = s ", spare " spare
            if (me != "")      s = s ", " me " media errors"
            if (life != "")    s = s ", life " life
            if (realloc != "") s = s ", " realloc " reallocated"
            if (pend != "")    s = s ", " pend " pending"
            if (poh != "")     s = s ", " poh " h"
            if (t != "")       s = s ", " t
            printf "%s", s
        }'
    # Its firmware slots (NVMe, nvme-cli): which slot runs, and what each holds.
    case "$1" in
        /dev/nvme*)
            if have nvme; then
                printf '; slots %s' "$(nvme fw-log "$1" 2>/dev/null | sed -n 's/^afi *: *\(.*\)/afi \1/p; s/^frs\([0-9]\) *: *[0-9a-fx]* *(\(.*\))/\1=\2/p' | tr '\n' ' ' | sed 's/ *$//')"
            fi ;;
    esac
}

if [ "$SAVE" = 1 ]; then
    mkdir -p /var/lib/fleet-firmware
    scan > /var/lib/fleet-firmware/report.tsv.tmp
    chmod 0644 /var/lib/fleet-firmware/report.tsv.tmp
    mv /var/lib/fleet-firmware/report.tsv.tmp /var/lib/fleet-firmware/report.tsv
    cat /var/lib/fleet-firmware/report.tsv
else
    scan
fi
