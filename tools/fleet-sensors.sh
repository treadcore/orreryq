#!/bin/sh
# fleet-sensors.sh: the temperatures only root can read, read by root and left where the user's
# collector (fleet-telemetry.sh) picks them up. Paul, 15 November: "looking for things like southbridge
# or anything with thermometer, including the harddrives ... In particular, I want to maybe find the
# temperature of the mellanox 10GbE. They might get hot."
#
# Run it ON THE MACHINE, once, as root (orrery's Machines view: the recipe "Read every thermometer";
# or tools/fleet-root-round.sh, one password a machine):
#
#   cd ~/orrery-recipes && doas sh fleet-sensors.sh      (Alpine, Copal)
#   cd ~/orrery-recipes && sudo sh fleet-sensors.sh      (Ubuntu)
#   ... fleet-sensors.sh --undo                          takes it all away
#
# WHAT IT ADDS, each checked before it is done, so a second run changes nothing:
#   1. The kernel's own sensor drivers, now and at every boot: drivetemp (each SATA disk's
#      temperature, as a hwmon sensor the user can read) and the board's chip where the kernel has a
#      driver for it (nct6775, nct6683, it87, w83627ehf: fans, the board's and the chipset's
#      thermometers). A driver with no chip to find says so and is left out.
#   2. lm-sensors, smartmontools, ethtool, and mstflint where the system offers it.
#   3. /usr/local/sbin/fleet-sensors-read.sh, run from boot as root: every 15 seconds it writes
#      /run/fleet-sensors/root.kv, a `key value` a line, readable by all:
#        w.NAME         watts from the CPU's energy counter (RAPL), which the kernel keeps for root
#        nic.IF.module  a 10 GbE port's plugged module (ethtool -m: an optic tells; a copper cable does not)
#        nic.IF.chip    the card's own chip (mstflint's mget_temp, on the cards that have a sensor)
#        ipmi.NAME      a server board's own sensors (ipmitool, each minute): inlet, each CPU, fans
#        disk.NAME      a disk's SMART temperature where no kernel sensor gives it (each minute)
# What a machine does NOT tell is said at the end: no guess is written down as a reading.
set -eu

[ "$(id -u)" = 0 ] || { echo "run as root (doas or sudo)" >&2; exit 1; }
READER=/usr/local/sbin/fleet-sensors-read.sh
MODS="drivetemp nct6775 nct6683 it87 w83627ehf coretemp k10temp"

if [ "${1:-}" = "--undo" ]; then
    if command -v systemctl >/dev/null; then
        systemctl disable --now fleet-sensors.service 2>/dev/null || true
        rm -f /etc/systemd/system/fleet-sensors.service /etc/modules-load.d/fleet-sensors.conf
        systemctl daemon-reload
    fi
    rm -f /etc/local.d/fleet-sensors.start "$READER"
    [ -f /etc/modules ] && sed -i '/# fleet-sensors$/d' /etc/modules
    pkill -f fleet-sensors-read.sh 2>/dev/null || true
    rm -rf /run/fleet-sensors
    echo "taken away: the reader and the boot's module list (modules loaded now stay until the next boot)"
    exit 0
fi

# 2. the programs
if command -v apk >/dev/null; then
    apk add lm-sensors smartmontools ethtool pciutils >/dev/null || echo "apk could not add every program: what is there is used"
    apk add mstflint >/dev/null 2>&1 || true
    apk add ipmitool >/dev/null 2>&1 || true
elif command -v apt-get >/dev/null; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get -o DPkg::Lock::Timeout=900 install -y --no-install-recommends lm-sensors smartmontools ethtool pciutils >/dev/null \
        || echo "apt could not install every program: what is there is used"
    apt-get -o DPkg::Lock::Timeout=900 install -y --no-install-recommends mstflint >/dev/null 2>&1 || true
    [ -e /dev/ipmi0 ] || [ -d /sys/class/ipmi ] && apt-get -o DPkg::Lock::Timeout=900 install -y --no-install-recommends ipmitool >/dev/null 2>&1 || true
fi

# 1. the drivers
loaded=
for m in $MODS; do
    if modprobe "$m" 2>/dev/null; then loaded="$loaded $m"; fi
done
# A server board's own controller, where there is one.
for m in ipmi_si ipmi_devintf; do modprobe "$m" 2>/dev/null && loaded="$loaded $m" || true; done
if [ -d /etc/modules-load.d ] && command -v systemctl >/dev/null; then
    { echo "# orrery tools/fleet-sensors.sh: the sensor drivers this machine has a chip for."; for m in $loaded; do echo "$m"; done; } > /etc/modules-load.d/fleet-sensors.conf
else
    touch /etc/modules
    sed -i '/# fleet-sensors$/d' /etc/modules
    for m in $loaded; do grep -qx "$m" /etc/modules || echo "$m # fleet-sensors" >> /etc/modules; done
fi
echo "sensor drivers loaded now and at boot:${loaded:- none}"

# 3. the reader
mkdir -p "$(dirname "$READER")"
cat > "$READER" <<'READER_EOF'
#!/bin/sh
# orrery tools/fleet-sensors.sh wrote this: root's readings for the user's collector, every 15 s.
D=/run/fleet-sensors
mkdir -p $D && chmod 0755 $D
n=0
slow=
while :; do
    out=
    now=$(date +%s)
    # The CPU's watts, from its energy counter.
    for r in /sys/class/powercap/intel-rapl:? /sys/class/powercap/intel-rapl:?:?; do
        [ -r "$r/energy_uj" ] || continue
        read -r e < "$r/energy_uj"; read -r name < "$r/name"
        id=$(echo "${r##*/}" | tr -c 'a-z0-9\n' '_')
        eval "pe=\${PE_$id:-}; pt=\${PT_$id:-}"
        if [ -n "$pe" ] && [ "$now" -gt "$pt" ] && [ "$e" -ge "$pe" ]; then
            mw=$(( (e - pe) / (now - pt) / 1000 ))
            case "${r##*/}" in intel-rapl:?:?) p=${r%:*}; key="w.${name}_${p##*:}" ;; *) key="w.$name" ;; esac
            out="$out
$key $((mw / 1000)).$(( (mw % 1000) / 100 ))"
        fi
        eval "PE_$id=$e; PT_$id=$now"
    done
    # A 10 GbE port: its module, and the card's own chip.
    for i in /sys/class/net/*; do
        [ -e "$i/device/driver" ] || continue
        case "$(basename "$(readlink "$i/device/driver")")" in mlx4_core|mlx5_core|ixgbe|i40e|bnx2x|ice|qede) ;; *) continue ;; esac
        if=${i##*/}
        t=$(ethtool -m "$if" 2>/dev/null | sed -n 's/.*Module temperature *: *\([0-9.]*\) degrees C.*/\1/p' | head -n1)
        [ -n "$t" ] && out="$out
nic.$if.module $t"
        pci=$(basename "$(readlink "$i/device")")
        for tool in mget_temp mstmget_temp; do
            command -v $tool >/dev/null 2>&1 || continue
            t=$($tool -d "$pci" 2>/dev/null | tr -dc '0-9.\n' | head -n1)
            [ -n "$t" ] && out="$out
nic.$if.chip $t" && break
        done
    done
    # Each minute: the board's own controller, and the disks no kernel sensor covers.
    if [ $((n % 4)) = 0 ]; then
        slow=
        if command -v ipmitool >/dev/null 2>&1 && [ -e /dev/ipmi0 ]; then
            slow=$(ipmitool sdr list 2>/dev/null | awk -F'|' '$3 ~ /ok/ && ($2 ~ /degrees C/ || $2 ~ /RPM/ || $2 ~ /Watts/) { k=$1; gsub(/^ +| +$/,"",k); gsub(/[^A-Za-z0-9]+/,"_",k); split($2,v," "); print "ipmi." k " " v[1] }')
        fi
        if command -v smartctl >/dev/null 2>&1 && ! grep -qx drivetemp /sys/class/hwmon/hwmon*/name 2>/dev/null; then
            for d in /sys/block/sd?; do
                [ -e "$d" ] || continue
                t=$(smartctl -n standby -A "/dev/${d##*/}" 2>/dev/null | awk '$2 ~ /Temperature_Celsius|Airflow_Temperature/ { print $10; exit }')
                [ -n "$t" ] && slow="$slow
disk.${d##*/} $t"
            done
        fi
    fi
    n=$((n + 1))
    printf '%s\n%s\n' "$out" "$slow" | sed '/^$/d' > $D/.root.kv && chmod 0644 $D/.root.kv && mv $D/.root.kv $D/root.kv
    sleep 15
done
READER_EOF
chmod 0755 "$READER"

if command -v rc-update >/dev/null 2>&1; then
    mkdir -p /etc/local.d
    printf '#!/bin/sh\n# orrery tools/fleet-sensors.sh: root'"'"'s sensor readings, from boot.\npgrep -f fleet-sensors-read.sh >/dev/null || ( %s >/dev/null 2>&1 & )\n' "$READER" > /etc/local.d/fleet-sensors.start
    chmod 0755 /etc/local.d/fleet-sensors.start
    rc-update add local default >/dev/null 2>&1 || true
    pkill -f fleet-sensors-read.sh 2>/dev/null || true
    ( setsid "$READER" >/dev/null 2>&1 < /dev/null & )
    echo "the reader: started, and at boot by /etc/local.d/fleet-sensors.start"
elif command -v systemctl >/dev/null; then
    cat > /etc/systemd/system/fleet-sensors.service <<EOF
[Unit]
Description=orrery: the temperatures only root can read, for the telemetry (fleet-sensors.sh)

[Service]
ExecStart=$READER
Restart=always
RestartSec=30
Nice=10

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable fleet-sensors.service >/dev/null 2>&1
    systemctl restart fleet-sensors.service
    echo "the reader: fleet-sensors.service, started and enabled"
else
    echo "neither OpenRC (Alpine) nor systemd (Ubuntu) here: the reader is not started" >&2
    exit 1
fi

# What this machine tells, said plainly.
sleep 20
echo "root's readings now (/run/fleet-sensors/root.kv):"
sed 's/^/    /' /run/fleet-sensors/root.kv 2>/dev/null || echo "    none yet"
echo "the kernel's sensors:"
for h in /sys/class/hwmon/hwmon*; do
    printf '    %s: %s temperatures, %s fans\n' "$(cat "$h/name")" "$(ls "$h"/temp*_input 2>/dev/null | wc -l | tr -d ' ')" "$(ls "$h"/fan*_input 2>/dev/null | wc -l | tr -d ' ')"
done
for i in /sys/class/net/*; do
    [ -e "$i/device/driver" ] || continue
    case "$(basename "$(readlink "$i/device/driver")")" in
        mlx4_core|mlx5_core|ixgbe|i40e)
            grep -q "^nic.${i##*/}\." /run/fleet-sensors/root.kv 2>/dev/null \
                || echo "the 10 GbE port ${i##*/} tells no temperature: its module has no thermometer (a copper cable has none) and its chip answers no tool here" ;;
    esac
done
