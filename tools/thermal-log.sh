#!/bin/sh
# thermal-log.sh HOST install|show|remove -- a machine's temperatures and clocks, once a minute, kept
# across reboots in ~/fleet/bench-ram/thermal.tsv, from the user's own crontab (no root).
#
# Paul, 7 November: "its a liquid cooled system, it takes a while for heat soak." A bench of a few
# minutes runs on a cold loop; this is the hours after it, while the fleet works the machine. It shows
# how long the loop takes to soak, where each board sensor settles, and whether anything throttles:
# the busiest core's clock falling under load while the package runs hot. One line a minute is
# about 150 KB a day. Remove it when the question is answered.
#
# Columns: time (UTC), load, CPU MHz (busiest core, mean), package and hottest core C, the board's six
# sensors (gigabyte_wmi temp1..temp6, unlabelled in Linux; the BIOS's Smart Fan 5 screen names them),
# the NVMe drives' C, and the GPU's C, W, busy % and fan %.
set -eu
HOST=${1:?HOST install|show|remove}; HOW=${2:-show}
case "$HOW" in
install)
    ssh "$HOST" 'mkdir -p ~/fleet/bench-ram && cat > ~/fleet/bench-ram/thermal.sh' <<'S'
#!/bin/sh
f=~/fleet/bench-ram/thermal.tsv
[ -f $f ] || printf 'utc\tload\tmhz_max\tmhz_mean\tpkg_c\tcore_max_c\tb1\tb2\tb3\tb4\tb5\tb6\tnvme_c\tgpu_c\tgpu_w\tgpu_busy\tgpu_fan\n' > $f
c() { echo $(( $(cat "$1" 2>/dev/null || echo 0) / 1000 )); }
pkg=; cmax=0; b=; nv=
for h in /sys/class/hwmon/hwmon*; do
    case "$(cat $h/name)" in
    coretemp) pkg=$(c $h/temp1_input); for t in $h/temp*_input; do v=$(c $t); [ $v -gt $cmax ] && cmax=$v; done ;;
    gigabyte_wmi) for i in 1 2 3 4 5 6; do b="$b$(c $h/temp${i}_input)\t"; done ;;
    nvme) nv="$nv$(c $h/temp1_input)/" ;;
    esac
done
mhz=$(awk '/MHz/ {s += $4; n++; if ($4 > m) m = $4} END {printf "%.0f\t%.0f", m, s / n}' /proc/cpuinfo)
gpu=$(nvidia-smi --query-gpu=temperature.gpu,power.draw,utilization.gpu,fan.speed --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ' | tr ',' '\t')
printf "%s\t%s\t%s\t%s\t%s\t$b%s\t%s\n" "$(date -u +%Y-%m-%dT%H:%M)" "$(cut -d' ' -f1 /proc/loadavg)" "$mhz" "$pkg" "$cmax" "${nv%/}" "${gpu:-\t\t\t}" >> $f
S
    ssh "$HOST" '(crontab -l 2>/dev/null | grep -v bench-ram/thermal.sh; echo "* * * * * sh ~/fleet/bench-ram/thermal.sh") | crontab - && crontab -l'
    ;;
show)
    ssh "$HOST" 'tail -n 20 ~/fleet/bench-ram/thermal.tsv | column -t'
    ;;
remove)
    ssh "$HOST" '(crontab -l 2>/dev/null | grep -v bench-ram/thermal.sh) | crontab - ; crontab -l 2>/dev/null; echo "removed; the log stays in ~/fleet/bench-ram/thermal.tsv"'
    ;;
*) echo "thermal-log.sh HOST install|show|remove"; exit 2 ;;
esac
