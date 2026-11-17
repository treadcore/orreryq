#!/bin/sh
# fleet-cpu-cap.sh: hold a machine's CPU to fewer watts, or a lower clock, as root. Paul, 16 November:
# "a dynamic heat target, which scales back like a PID controller, which sets the CPU core throttling".
#
# WHAT THE FLEET DOES WITHOUT ROOT is coarser: a lane takes no new job (the queue's pause), or its jobs
# are told fewer CPUs (`machine NAME cpus N`). Those are what tools/hearth.py uses. A cap on the watts
# of a CPU that goes on working is the kernel's to set, and the kernel keeps it for root.
#
# Run it ON THE MACHINE, as root, by hand (it is NOT part of tools/fleet-root-round.sh, NOT a Machines
# recipe, and tools/hearth.py never calls it):
#
#   doas sh fleet-cpu-cap.sh show          what the machine has and how it is set; changes nothing
#   doas sh fleet-cpu-cap.sh watts 45      Intel: each package's long-term limit (RAPL) to 45 W
#   doas sh fleet-cpu-cap.sh clock 60      any CPU: no core's clock above 60% of its highest
#   doas sh fleet-cpu-cap.sh off           both as they were
#
# NOTHING IS WRITTEN TO DISK BUT /run: a reboot takes every cap away, and `off` puts back what `watts`
# found (kept in /run/fleet-cpu-cap/). `watts` is Intel's powercap interface (intel-rapl); a Ryzen
# has no limit there to write and is told so; `clock` works wherever cpufreq does. A BIOS that locks
# the package limit ignores `watts`: `show` afterwards says what the kernel now reads.
#
# NOT TRIED ON ANY MACHINE OF THE FLEET (16 November). Checked for syntax only.
set -eu
KEEP=/run/fleet-cpu-cap
RAPL=/sys/class/powercap
FREQ=/sys/devices/system/cpu/cpufreq

packages() { ls -d $RAPL/intel-rapl:[0-9] $RAPL/intel-rapl:[0-9][0-9] 2>/dev/null || true; }

show() {
    for p in $(packages); do
        [ -r "$p/constraint_0_power_limit_uw" ] || continue
        echo "$(cat "$p/name"): long-term limit $(( $(cat "$p/constraint_0_power_limit_uw") / 1000000 )) W$( [ -r "$p/constraint_0_max_power_uw" ] && echo ", the most it allows $(( $(cat "$p/constraint_0_max_power_uw") / 1000000 )) W" )"
    done
    [ -n "$(packages)" ] || echo "no intel-rapl package here: \`watts\` has nothing to set"
    for c in "$FREQ"/policy*; do
        [ -r "$c/scaling_max_freq" ] || continue
        echo "$(basename "$c"): clock up to $(( $(cat "$c/scaling_max_freq") / 1000 )) MHz of $(( $(cat "$c/cpuinfo_max_freq") / 1000 )) MHz"
    done | sort -u -k2 | head -4
    [ -d "$FREQ" ] || echo "no cpufreq here: \`clock\` has nothing to set"
}

case "${1:-}" in
show)
    show ;;
watts)
    [ "$(id -u)" = 0 ] || { echo "run as root (doas or sudo)" >&2; exit 1; }
    w=${2:-}
    case "$w" in ''|*[!0-9]*) echo "watts N: a whole number of watts" >&2; exit 2 ;; esac
    [ "$w" -ge 10 ] || { echo "under 10 W is refused: a package held that low may not keep its own kernel running" >&2; exit 2; }
    [ -n "$(packages)" ] || { echo "no intel-rapl package here (an AMD CPU, or the driver is absent): nothing set" >&2; exit 1; }
    mkdir -p "$KEEP"
    for p in $(packages); do
        f=$p/constraint_0_power_limit_uw
        k=$KEEP/$(basename "$p").uw
        [ -f "$k" ] || cat "$f" > "$k"
        echo $(( w * 1000000 )) > "$f"
    done
    show ;;
clock)
    [ "$(id -u)" = 0 ] || { echo "run as root (doas or sudo)" >&2; exit 1; }
    pct=${2:-}
    case "$pct" in ''|*[!0-9]*) echo "clock PERCENT: 20 to 100" >&2; exit 2 ;; esac
    [ "$pct" -ge 20 ] && [ "$pct" -le 100 ] || { echo "clock PERCENT: 20 to 100" >&2; exit 2; }
    [ -d "$FREQ" ] || { echo "no cpufreq here: nothing set" >&2; exit 1; }
    for c in "$FREQ"/policy*; do
        max=$(cat "$c/cpuinfo_max_freq"); min=$(cat "$c/cpuinfo_min_freq")
        want=$(( max / 100 * pct ))
        [ "$want" -ge "$min" ] || want=$min
        echo "$want" > "$c/scaling_max_freq"
    done
    show ;;
off)
    [ "$(id -u)" = 0 ] || { echo "run as root (doas or sudo)" >&2; exit 1; }
    for p in $(packages); do
        k=$KEEP/$(basename "$p").uw
        [ -f "$k" ] && { cat "$k" > "$p/constraint_0_power_limit_uw"; rm -f "$k"; }
    done
    for c in "$FREQ"/policy*; do
        [ -w "$c/scaling_max_freq" ] && cat "$c/cpuinfo_max_freq" > "$c/scaling_max_freq"
    done
    show ;;
*)
    sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
