#!/bin/sh
# ram-bench.sh HOST LABEL [REPS] -- a machine's memory, and the fleet's own work on it, measured the same
# way before and after a change to its memory (Paul, 7 November: "i'm going to change ram config. can
# you profile speeds. start the collection of needed data").
#
#     sh tools/ram-bench.sh calber 2400-jedec          before: what the BIOS gives it now
#     sh tools/ram-bench.sh calber 2666 3              after: the label says what was changed
#
# THREE MEASURES, EACH ON A FIXED INPUT, so that the only thing that differs between two runs is the
# machine:
#   stream   bandwidth, MB/s: copy, scale, add and triad over three 1 GiB arrays of doubles, best of
#            ten, on every core (OpenMP) and on one. What the memory clock moves first.
#   latency  ns a load: one load at a time along a random cycle through 512 MiB, huge pages asked for,
#            so the time is the memory's, not the cache's.
#   census   seconds: the work the queue gives the machine, w13740's trial (a census calber ran at 07:22
#            on 7 November) on 16 seeds of 900 s games on all cores and 2 on one core. The census
#            binary and its worktree (c/fd7b36d), the models and the patches are copied ONCE into
#            ~/fleet/bench-ram/inputs, so a later prune or promotion cannot change the work. Each run's
#            pooled.txt is hashed: equal hashes prove two runs played the same games.
#
# Run it on a machine OUT OF THE QUEUE (Projects: Finish, then out): the queue's jobs would share its
# cores and its memory, and the numbers would be theirs. The machine's clocks, power limit and
# temperatures are written beside each result, because a memory change that also moves the CPU's
# clock is two changes.
#
# Results: ~/fleet/bench-ram/LABEL-STAMP.txt on the machine, printed, and copied here to
# docs/<host>-ram/. The fleet's own jobs are the second measure, over a day back in the queue:
# tools/job-speed.py.
set -eu
if [ "${1:-}" != "--here" ]; then
    HOST=${1:?HOST LABEL [REPS]}; LABEL=${2:?HOST LABEL [REPS]}; REPS=${3:-3}
    ssh "$HOST" 'mkdir -p ~/fleet/bench-ram && cat > ~/fleet/bench-ram/ram-bench.sh' < "$0"
    ssh "$HOST" "sh ~/fleet/bench-ram/ram-bench.sh --here '$LABEL' '$REPS'"
    out=$(ssh "$HOST" 'ls -t ~/fleet/bench-ram/*.txt | head -1')
    mkdir -p "$(dirname "$0")/../docs/$HOST-ram"
    scp -q "$HOST:$out" "$(dirname "$0")/../docs/$HOST-ram/"
    echo "copied to docs/$HOST-ram/$(basename "$out")"
    exit 0
fi

# ---- on the machine ----
LABEL=$2; REPS=$3
B=~/fleet/bench-ram; I=$B/inputs; mkdir -p $B
STAMP=$(date -u +%Y%m%d-%H%M%S); OUT=$B/$LABEL-$STAMP.txt
say() { echo "$*" | tee -a "$OUT"; }

# The inputs, frozen the first time.
if [ ! -d "$I/c/wt" ]; then
    mkdir -p "$I"
    cp -a ~/fleet/q-grove/c/fd7b36d "$I/c"
    cp -a ~/fleet/q-grove/models "$I/models"; cp -a ~/fleet/q-grove/patches "$I/patches"
    echo IyBvcnJlcnk6IHdpZGUsIHBhc3QgdGhlIGZpdCdzIGJvdW5kICh0aGUgc2VhcmNoIHN0YWxsZWQpCmtpdGVfaW5fYWxvbmUgPSAxLjU2ODM1CnBpbmdfd2Fybl9yZWFjaCA9IDguOTkyMzgKcmV0cmVhdF9hcm1vciA9IDEwMAo= | base64 -d > "$I/w13740.weights"
fi

# The two small programs, built the first time.
if [ ! -x "$B/stream" ]; then
cat > $B/stream.c <<'C'
#include <stdio.h>
#include <stdlib.h>
#include <omp.h>
#define N (128L * 1024 * 1024)
int main(void) {
    double *a = malloc(N * 8), *b = malloc(N * 8), *c = malloc(N * 8), s = 3.0, best[4] = {1e30, 1e30, 1e30, 1e30};
    if (!a || !b || !c) return 1;
    #pragma omp parallel for
    for (long i = 0; i < N; i++) { a[i] = 1.0; b[i] = 2.0; c[i] = 0.0; }
    for (int k = 0; k < 10; k++) {
        double t = omp_get_wtime();
        #pragma omp parallel for
        for (long i = 0; i < N; i++) c[i] = a[i];
        t = omp_get_wtime() - t; if (t < best[0]) best[0] = t;
        t = omp_get_wtime();
        #pragma omp parallel for
        for (long i = 0; i < N; i++) b[i] = s * c[i];
        t = omp_get_wtime() - t; if (t < best[1]) best[1] = t;
        t = omp_get_wtime();
        #pragma omp parallel for
        for (long i = 0; i < N; i++) c[i] = a[i] + b[i];
        t = omp_get_wtime() - t; if (t < best[2]) best[2] = t;
        t = omp_get_wtime();
        #pragma omp parallel for
        for (long i = 0; i < N; i++) a[i] = b[i] + s * c[i];
        t = omp_get_wtime() - t; if (t < best[3]) best[3] = t;
    }
    double mb = N * 8 / 1e6;
    printf("copy %.0f scale %.0f add %.0f triad %.0f MB/s (threads %d, check %.1f)\n",
           2 * mb / best[0], 2 * mb / best[1], 3 * mb / best[2], 3 * mb / best[3], omp_get_max_threads(), a[N / 2]);
    return 0;
}
C
cat > $B/latency.c <<'C'
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>
#include <sys/mman.h>
#define M (64L * 1024 * 1024)
int main(void) {
    size_t bytes = M * sizeof(size_t);
    size_t *p = mmap(NULL, bytes, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (p == MAP_FAILED) return 1;
    madvise(p, bytes, MADV_HUGEPAGE);
    for (size_t i = 0; i < M; i++) p[i] = i;
    uint64_t x = 88172645463325252ULL;
    for (size_t i = M - 1; i > 0; i--) {          /* Sattolo: one cycle through every slot */
        x ^= x << 13; x ^= x >> 7; x ^= x << 17;
        size_t j = x % i, t = p[i]; p[i] = p[j]; p[j] = t;
    }
    size_t at = 0, steps = 100L * 1000 * 1000;
    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (size_t i = 0; i < steps; i++) at = p[at];
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double ns = ((t1.tv_sec - t0.tv_sec) * 1e9 + (t1.tv_nsec - t0.tv_nsec)) / steps;
    printf("%.1f ns a load over 512 MiB (end %zu)\n", ns, at);
    return 0;
}
C
gcc -O2 -fopenmp -o $B/stream $B/stream.c
gcc -O2 -o $B/latency $B/latency.c
fi

# The busiest core's clock and the mean of all of them, read 5 s into a run.
mhz() { awk '/MHz/ {s += $4; n++; if ($4 > m) m = $4} END {printf "%.0f max, %.0f mean", m, s / n}' /proc/cpuinfo; }
temp() { for h in /sys/class/hwmon/hwmon*; do [ "$(cat $h/name)" = coretemp ] && echo $(( $(cat $h/temp1_input) / 1000 )); done; }
board() { for h in /sys/class/hwmon/hwmon*; do [ "$(cat $h/name)" = gigabyte_wmi ] && echo $(( $(cat $h/temp5_input) / 1000 )); done; }

say "# ram-bench $LABEL on $(hostname), $(date '+%Y-%m-%d %H:%M:%S %Z')"
say "kernel $(uname -r); $(grep -m1 'model name' /proc/cpuinfo | sed 's/.*: //'); governor $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor) $(cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference 2>/dev/null)"
say "power limit $(( $(cat /sys/class/powercap/intel-rapl:0/constraint_0_power_limit_uw) / 1000000 )) W long term; load before $(cut -d' ' -f1 /proc/loadavg); package $(temp) C, board sensor 5 $(board) C"
say "memory: the label says it ($LABEL); confirm with sudo dmidecode -t 17 | grep Configured"
pgrep -f 'census-bin|crucible --pop' >/dev/null && say "WARNING: a census or crucible runs here now: the numbers are shared"

say "stream, all cores: $(OMP_NUM_THREADS=$(nproc) $B/stream)"
say "stream, one core:  $(OMP_NUM_THREADS=1 $B/stream)"
say "latency: $($B/latency)"

census() { # JOBS SEEDS
    cd $I/c/wt
    t0=$(date +%s.%N)
    ( sleep 5; echo "$(mhz)" > $B/.mhz ) &
    TRIAL=$I/w13740.weights CENSUS_MODELS=$I/models CENSUS_PATCHES=$I/patches SEEDS=$2 SEED0=157400000 SECS=900 MAP=all \
        PROBE=0 RESPAWNS=3 JOBS=$1 CENSUS_BIN=$I/c/census-bin scripts/census.sh >/dev/null 2>&1
    t1=$(date +%s.%N); wait
    d=$(ls -td build/census/*/ | head -1)
    h=$(md5sum $d/pooled.txt 2>/dev/null | cut -c1-8)
    rm -rf "$d"
    echo "$(awk "BEGIN {printf \"%.1f\", $t1 - $t0}") s  (cores at $(cat $B/.mhz) MHz, package $(temp) C, board sensor 5 $(board) C, pooled $h)"
}
r=1; while [ $r -le "$REPS" ]; do say "census, 16 seeds on $(nproc) cores, run $r: $(census $(nproc) 16)"; r=$((r + 1)); done
r=1; while [ $r -le 2 ]; do say "census, 2 seeds on one core, run $r: $(census 1 2)"; r=$((r + 1)); done
say "# done $(date '+%H:%M:%S')"
