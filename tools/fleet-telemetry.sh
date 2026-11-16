#!/bin/sh
# fleet-telemetry.sh: a machine writes down its own temperatures, every few seconds, for the thermal
# model (Paul, 15 November: "calculate a Tau, or a time constant ... how reactive in the time constant
# to the step function of turning a system on fully on and off ... But first we need to collect the
# data. Make as part of the fleet script").
#
# It runs ON THE MACHINE, as the user, no root: orrery's tools/telemetry.py copies it to
# ~/.fleet-queue/fleet-telemetry.sh, starts it, starts it again after a boot or a new version, and
# brings its lines back to the queue.
#
#   sh fleet-telemetry.sh run [SECONDS]   sample every SECONDS (5) until stopped; one at a time
#   sh fleet-telemetry.sh once            one sample, printed
#   sh fleet-telemetry.sh stop | status
#
# A SAMPLE IS ONE LINE of key=value in ~/.fleet-queue/telemetry/YYYYMMDD.log (UTC days, 14 kept):
#   t        seconds since 1970
#   up       seconds since the boot: a machine switched on is a step of its own
#   busy     the CPUs' use since the last sample, 0 to 1 (/proc/stat)
#   load     the one-minute load average
#   mhz      the cores' mean clock now: a CPU holding itself back for heat shows here first
#   NAME.LABEL   every temperature the kernel has (hwmon), degrees C: the CPU's package (each core's
#            own is left out), the board's, each NVMe's, a SATA disk's once drivetemp is loaded
#   NAME.fanN / NAME.pwmN / NAME.powerN   fans in rpm, their drive 0-255, watts, where a chip tells
#   w.NAME   watts from the CPU's own energy counter (RAPL), where the user may read it
#   gpu.c gpu.w gpu.use gpu.fan   the card: degrees, watts, percent busy, fan percent (nvidia-smi)
#   rad.ID.cpm   a Geiger counter's counts a minute over five minutes, where radbeeper logs one
#   room.radID.c   that counter's own thermometer, degrees C, where radbeeper logs it
#   and whatever root's own readings say in /run/fleet-sensors/*.kv (fleet-sensors.sh: the 10 GbE
#   card's module, a disk's SMART temperature), a `key value` a line.
# Nothing here needs a program the smallest Alpine lacks: the shell reads the files itself, so a
# sample costs no process but the card's.
set -u
D=${FLEET_TELEMETRY_DIR:-$HOME/.fleet-queue/telemetry}
PIDF=$D/pid
EVERY=${2:-5}
mkdir -p "$D"

# The sensors, found once and again each ten minutes (a module loaded later is then seen): "key file".
scan() {
    LIST=
    for h in /sys/class/hwmon/hwmon*; do
        [ -r "$h/name" ] || continue
        read -r name < "$h/name"
        n=${h##*hwmon}
        # A CPU with a package sensor is told by it; an older one (a Xeon 5600) has only its cores', and
        # those are then kept.
        pkg=
        for l in "$h"/temp*_label; do
            [ -r "$l" ] && read -r lab < "$l" && case "$lab" in Package*|Tctl*) pkg=1 ;; esac
        done
        for f in "$h"/temp*_input "$h"/fan*_input "$h"/pwm[0-9] "$h"/power*_input; do
            [ -r "$f" ] || continue
            b=${f##*/}; b=${b%_input}
            lab=$b
            if [ -r "$h/${b}_label" ]; then read -r lab < "$h/${b}_label"; fi
            case "$lab" in Core\ *) [ -n "$pkg" ] && continue ;; esac
            lab=$(echo "$lab" | tr -c 'A-Za-z0-9\n' '_')
            LIST="$LIST ${name}_$n.$lab:$f"
        done
    done
    RAPL=
    for r in /sys/class/powercap/intel-rapl:?; do
        [ -r "$r/energy_uj" ] && read -r _e < "$r/energy_uj" 2>/dev/null && RAPL="$RAPL $r"
    done
    GPU=
    command -v nvidia-smi >/dev/null 2>&1 && GPU=1
    SCANNED=$(date +%s)
}

sample() {
    now=$(date +%s)
    read -r _c u n s i w q sq st _rest < /proc/stat
    tot=$((u + n + s + i + w + q + sq + st)); idle=$((i + w))
    if [ -n "${PTOT:-}" ] && [ "$tot" -gt "$PTOT" ]; then
        b=$(( (1000 * ((tot - PTOT) - (idle - PIDLE))) / (tot - PTOT) ))
        busy=$((b / 1000)).$(printf %03d $((b % 1000)))
    else
        busy=
    fi
    PTOT=$tot; PIDLE=$idle
    read -r load _rest < /proc/loadavg
    read -r up _rest < /proc/uptime
    line="t=$now up=${up%.*}${busy:+ busy=$busy} load=$load"
    sum=0; k=0
    for f in /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq; do
        [ -r "$f" ] && read -r v < "$f" 2>/dev/null && sum=$((sum + v)) && k=$((k + 1))
    done
    [ "$k" -gt 0 ] && line="$line mhz=$((sum / k / 1000))"
    for e in $LIST; do
        key=${e%%:*}; f=${e#*:}
        read -r v < "$f" 2>/dev/null || continue
        [ -n "$v" ] || continue
        case "$f" in
            *temp*) line="$line $key=$((v / 1000)).$(( (v % 1000) / 100 ))" ;;
            *power*) line="$line $key=$((v / 1000000)).$(( (v % 1000000) / 100000 ))" ;;
            *) line="$line $key=$v" ;;
        esac
    done
    for r in $RAPL; do
        read -r e < "$r/energy_uj" 2>/dev/null || continue
        read -r rn < "$r/name" 2>/dev/null || rn=${r##*:}
        eval "pe=\${PE_${r##*:}:-}; pt=\${PT_${r##*:}:-}"
        if [ -n "$pe" ] && [ "$now" -gt "$pt" ] && [ "$e" -ge "$pe" ]; then
            mw=$(( (e - pe) / (now - pt) / 1000 ))
            line="$line w.$rn=$((mw / 1000)).$(( (mw % 1000) / 100 ))"
        fi
        eval "PE_${r##*:}=$e; PT_${r##*:}=$now"
    done
    if [ -n "$GPU" ]; then
        g=$(nvidia-smi --query-gpu=temperature.gpu,power.draw,utilization.gpu,fan.speed --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
        if [ -n "$g" ]; then
            IFS=, read -r gc gw gu gf <<E
$g
E
            line="$line gpu.c=$gc gpu.w=$gw gpu.use=$gu"
            case "$gf" in ''|*[!0-9]*) ;; *) line="$line gpu.fan=$gf" ;; esac
        fi
    fi
    # The Geiger counters radbeeper logs, where it runs (saskatchewan): each counter's five-minute
    # counts a minute, from the last line of this month's log, if that line is under two minutes old.
    for x in /var/lib/radbeeper/cpm-[0-9A-F]*-"$(date +%Y-%m)".tsv; do
        [ -r "$x" ] || continue
        [ $(( now - $(stat -c %Y "$x" 2>/dev/null || echo 0) )) -lt 120 ] || continue
        id=${x##*/cpm-}; id=${id%%-*}
        v=$(tail -n 1 "$x" | cut -f 7)
        case "$v" in ''|*[!0-9.]*) ;; *) line="$line rad.${id#??????????}.cpm=$v" ;; esac
    done
    # The same counters' own thermometers, where radbeeper asks them (a GMC-320, and a radbeeper that
    # writes temp-ID-YYYY-MM.tsv): degrees C from that log's last line, if it is under two minutes
    # old. It is inside the counter's case, and it is the nearest thing here to the room's air.
    for x in /var/lib/radbeeper/temp-[0-9A-F]*-"$(date +%Y-%m)".tsv; do
        [ -r "$x" ] || continue
        [ $(( now - $(stat -c %Y "$x" 2>/dev/null || echo 0) )) -lt 120 ] || continue
        id=${x##*/temp-}; id=${id%%-*}
        v=$(tail -n 1 "$x" | cut -f 2)
        case "$v" in ''|*[!0-9.-]*) ;; *) line="$line room.rad${id#??????????}.c=$v" ;; esac
    done
    for x in /run/fleet-sensors/*.kv; do
        [ -r "$x" ] || continue
        while read -r key v _rest; do
            [ -n "$key" ] && [ -n "$v" ] && line="$line $key=$v"
        done < "$x"
    done
    echo "$line"
}

running() { [ -r "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; }

case "${1:-}" in
    once)
        scan; sample >/dev/null; sleep 1; sample ;;
    status)
        if running; then echo "running, pid $(cat "$PIDF"), every $(cat "$D/every" 2>/dev/null || echo ?) s"; else echo "not running"; fi ;;
    stop)
        # Every copy, and gone before this returns: one left sleeping would take the next one's pid file.
        running && kill "$(cat "$PIDF")"
        pkill -f 'fleet-telemetry.sh run' 2>/dev/null
        i=0; while pgrep -f 'fleet-telemetry.sh run' >/dev/null 2>&1 && [ $i -lt 10 ]; do sleep 1; i=$((i + 1)); done
        pkill -9 -f 'fleet-telemetry.sh run' 2>/dev/null
        rm -f "$PIDF"; echo stopped ;;
    run)
        running && { echo "already running, pid $(cat "$PIDF")"; exit 0; }
        echo $$ > "$PIDF"; echo "$EVERY" > "$D/every"
        trap '[ "$(cat "$PIDF" 2>/dev/null)" = "$$" ] && rm -f "$PIDF"; exit 0' TERM INT
        scan
        while :; do
            [ $(( $(date +%s) - SCANNED )) -gt 600 ] && scan
            day=$(date -u +%Y%m%d)
            if [ "$day" != "${DAY:-}" ]; then
                DAY=$day
                find "$D" -name '*.log' -mtime +14 -delete 2>/dev/null
            fi
            sample >> "$D/$day.log"
            sleep "$EVERY"
        done ;;
    *)
        sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
