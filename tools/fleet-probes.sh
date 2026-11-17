#!/bin/sh
# fleet-probes.sh: a machine looks for a Geiger counter on its USB ports and, where there is one,
# gets radbeeper for it, so the counter's own thermometer becomes a reading of the room. Paul, 16
# November: "add the concept of thermal probes. allow orrery copal fleet machines to look and install
# rad beeper if the usb tty device is a GMC 300, 500, 600, or anything matching the spec of" GQ's
# protocol document, GQ-RFC1201.
#
# It runs ON THE MACHINE, as the user, no root: orrery's tools/fleet-probes.py copies it to
# ~/.fleet-queue/fleet-probes.sh and runs one verb.
#
#   sh fleet-probes.sh look        every USB serial device and what its USB identity says it is.
#                                  NO PORT IS OPENED: sysfs, radbeeper's socket and /proc only
#   sh fleet-probes.sh ask PORT    ask one port what it is (<GETVER>>). Only a port `look` marks
#                                  counter=possible, held=no and openable=yes is opened
#   sh fleet-probes.sh install     radbeeper, built as the user by cargo into ~/.cargo/bin, where it
#                                  is absent or older than the one that logs temperature
#   sh fleet-probes.sh serve       start `radbeeper service` as the user for the counters that
#                                  answer and that nothing serves; it does not survive a reboot
#   sh fleet-probes.sh status      a line a counter: serial, counts a minute, temperature, who serves
#
# A LINE IS key=value PAIRS WITH A TAB BETWEEN THEM, and starts kind=machine, kind=port, kind=ask,
# kind=install, kind=serve or kind=counter. A value keeps its spaces; it never holds a tab.
#
# WHY A PORT IS NOT OPENED TO SEE WHAT IT IS. Opening a serial port raises its control lines, and a
# radio board restarts on that (Paul's LoRa radio does). So what a port is, is read from the USB
# device behind it, and only a port whose identity is one a GQ counter has shipped with is ever
# opened. `radbeeper probe` and `radbeeper service` with no --device open every ttyUSB and ttyACM
# there is: they are never run that way here, only with the ports this has passed.
#
# WHAT GIVES A TEMPERATURE. GQ-RFC1201 gives <GETTEMP>> to "GMC-320 Re.3.01 or later" and to no
# other model. A GMC-300, 500 or 600 is found, installed for and served just the same, and is read
# for its counts; it gives no temperature and is not asked for one.
set -u

# THE USB IDENTITIES A PORT MAY HAVE AND BE OPENED: vendor:product, lower case, a space between.
# This is the one list.
#   1a86:7523  the CH340 bridge. Both of Paul's counters have it (a GMC-320 Re 4.26 and a
#              GMC-320+V4 Re 4.83, read from sysfs on saskatchewan, 16 November 2026), and Copal's
#              udev rule (/etc/udev/rules.d/60-radbeeper.rules, stage 10) names it "the GMC-320".
# NOT ACCEPTED, though Copal's rule lists them as bridges GQ has shipped behind:
#   10c4:ea60  CP210x. It is also the bridge on most ESP32 radio boards, the very thing that must
#              not be opened, and no counter here has it.
#   067b:2303  PL2303. No counter here has it.
# A counter that turns up behind one of those shows in `look` as counter=no with its identity; add
# the identity here once it is known to be a counter.
ACCEPT="1a86:7523"

ME=$(id -un)
LOCAL=$HOME/.local/share/radbeeper
SYSTEM=/var/lib/radbeeper
GIT=https://github.com/vonglurt/radbeeper
TAB=$(printf '\t')

clean() { printf '%s' "$1" | tr '\t\n\r' '   '; }
# out KEY VALUE ...: one line of key=value, tabs between.
out() {
    line=
    while [ $# -ge 2 ]; do
        line="$line${line:+$TAB}$1=$(clean "$2")"
        shift 2
    done
    printf '%s\n' "$line"
}

# The radbeeper to use: the first that runs and logs temperature, else the first that runs.
find_radbeeper() {
    RB= ; RB_TEMP=no ; RB_VERSION=
    first=
    for c in "$(command -v radbeeper 2>/dev/null)" "$HOME/.cargo/bin/radbeeper" "$HOME/.local/bin/radbeeper" /usr/local/bin/radbeeper; do
        [ -n "$c" ] && [ -x "$c" ] || continue
        v=$("$c" --version 2>/dev/null | head -n 1) || continue
        case "$v" in radbeeper*) ;; *) continue ;; esac
        [ -n "$first" ] || first=$c
        # The one that logs temperature has --no-temp in its help; the version number did not change.
        if "$c" --help 2>/dev/null | grep -q -- '--no-temp'; then
            RB=$c; RB_TEMP=yes; break
        fi
    done
    [ -n "$RB" ] || RB=$first
    [ -n "$RB" ] && RB_VERSION=$("$RB" --version 2>/dev/null | head -n 1 | sed 's/^radbeeper *//')
    return 0
}

# The radbeeper processes that may hold a port: "PID USER ARGS" a line. hotplug holds none.
radbeeper_procs() {
    { ps -eo pid=,user=,args= 2>/dev/null || ps -o pid=,user=,args= 2>/dev/null; } \
        | awk '/radbeeper/ && !/fleet-probes/ && (/radbeeper(-gui)?( .*)? (service|watch)( |$)/ || /radbeeper-gui/) { $1 = $1; print }'
}

# What the running services say they serve, without a port being opened: `radbeeper now` attaches
# to the service's socket. "DIR<TAB>serial cpm cpm_300 usvh age temp_c temp_age live port version".
served_now() {
    NOW=
    [ -n "$RB" ] || return 0
    "$RB" --help 2>/dev/null | grep -q 'radbeeper now' || return 0
    for d in "$SYSTEM" "$LOCAL"; do
        [ -S "$d/sock" ] || continue
        if command -v timeout >/dev/null 2>&1; then r=$(timeout 30 "$RB" now --logs "$d" 2>/dev/null)
        else r=$("$RB" now --logs "$d" 2>/dev/null); fi
        [ -n "$r" ] || continue
        NOW="$NOW$(printf '%s\n' "$r" | grep -v '^#' | sed "s|^|$d$TAB|")
"
    done
}

# The USB device behind a tty: the nearest directory above it that has an idVendor.
usb_of() {
    d=$(readlink -f "/sys/class/tty/$1/device" 2>/dev/null) || return 1
    while [ -n "$d" ] && [ "$d" != / ]; do
        [ -r "$d/idVendor" ] && { echo "$d"; return 0; }
        d=${d%/*}
    done
    return 1
}
attr() { [ -r "$1" ] && head -n 1 "$1" 2>/dev/null; }

# The model, the firmware and the thermometer out of a <GETVER>> answer such as "GMC-320Re 4.26".
read_version() {
    V_MODEL=${1%%Re*}
    V_FW=$(printf '%s' "$1" | sed -n 's/.*Re *\([0-9][0-9.]*\).*/\1/p')
    V_THERM=no
    case "$V_MODEL" in
        GMC-320*) [ -n "$V_FW" ] && [ "$(awk -v f="$V_FW" 'BEGIN { print (f + 0 >= 3.01) ? 1 : 0 }')" = 1 ] && V_THERM=yes ;;
    esac
}

# One port, by sysfs, the socket and /proc: sets P_* and opens nothing.
read_port() {
    P_TTY=$1; P_PORT=/dev/$1
    P_USB=; P_PRODUCT=; P_MAKER=; P_DRIVER=; P_COUNTER=no; P_WHY=; P_HELD=no; P_BY=
    P_SERIAL=; P_VERSION=; P_DIR=; P_OPEN=no; P_GROUP=
    u=$(usb_of "$1") || u=
    if [ -n "$u" ]; then
        P_USB=$(attr "$u/idVendor"):$(attr "$u/idProduct")
        P_PRODUCT=$(attr "$u/product"); P_MAKER=$(attr "$u/manufacturer")
    fi
    [ -e "/sys/class/tty/$1/device/driver" ] && P_DRIVER=$(basename "$(readlink "/sys/class/tty/$1/device/driver")")
    case " $ACCEPT " in
        *" $P_USB "*) P_COUNTER=possible; P_WHY="$P_USB is a bridge a GQ counter ships with" ;;
        *) P_WHY="${P_USB:-no USB identity} is not on the list of counter bridges: never opened" ;;
    esac
    [ -r "$P_PORT" ] && [ -w "$P_PORT" ] && P_OPEN=yes
    P_GROUP=$(stat -c %G "$P_PORT" 2>/dev/null)
    # Who has it. A service says so itself; this user's own processes show in /proc; a radbeeper
    # of root's that would not say leaves the port "maybe" held, and it is then not opened.
    n=$(printf '%s' "$NOW" | awk -F'\t' -v p="$P_PORT" '$10 == p { print; exit }')
    if [ -n "$n" ]; then
        P_HELD=radbeeper
        P_DIR=$(printf '%s' "$n" | cut -f 1); P_SERIAL=$(printf '%s' "$n" | cut -f 2); P_VERSION=$(printf '%s' "$n" | cut -f 11)
        P_BY=$(server_of "$P_DIR")
        return 0
    fi
    pid=$(ls -l /proc/[0-9]*/fd 2>/dev/null | awk -v p="$P_PORT" '/^\/proc\// { split($0, a, "/"); pid = a[3] } $NF == p { print pid; exit }')
    if [ -n "$pid" ]; then
        P_HELD=process; P_BY="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | cut -c 1-60) (pid $pid)"
    elif [ -n "$PROCS" ]; then
        P_HELD=maybe; P_BY="a radbeeper is running that does not say what it holds: $(printf '%s' "$PROCS" | head -n 1 | cut -c 1-70)"
    fi
}

# Who serves a log directory: the service whose user fits it, as "boot service (root, pid N)".
server_of() {
    printf '%s\n' "$PROCS" | awk -v me="$ME" -v boot="$(boot_service)" -v mine="$([ "$1" = "$LOCAL" ] && echo 1 || echo 0)" '
        / service( |$)/ {
            if ($2 == me) { if (u == "") u = "user service (" $2 ", pid " $1 ")" }
            else if (o == "") o = (($2 == "root" && boot != "none") ? "boot service" : "service") " (" $2 ", pid " $1 ")"
        }
        END { print (mine == 1 || o == "") ? u : o }'
}

ports() { for t in /sys/class/tty/ttyUSB* /sys/class/tty/ttyACM*; do [ -e "$t" ] && echo "${t##*/}"; done; }

boot_service() {
    if [ -e /etc/init.d/radbeeper ]; then echo openrc
    elif [ -e /etc/systemd/system/radbeeper.service ] || [ -e /lib/systemd/system/radbeeper.service ]; then echo systemd
    else echo none; fi
}

begin() { find_radbeeper; PROCS=$(radbeeper_procs); served_now; }

look() {
    begin
    cargo=$(command -v cargo 2>/dev/null); [ -n "$cargo" ] || { [ -x "$HOME/.cargo/bin/cargo" ] && cargo=$HOME/.cargo/bin/cargo; }
    n=$(ports | wc -l | tr -d ' ')
    out kind machine host "$(hostname)" os "$(. /etc/os-release 2>/dev/null; echo "${ID:-?} ${VERSION_ID:-}")" \
        ports "$n" radbeeper "${RB:-none}" version "${RB_VERSION:-}" logs_temperature "$RB_TEMP" \
        cargo "${cargo:-none}" boot_service "$(boot_service)" \
        in_dialout "$(id -Gn | tr ' ' '\n' | grep -qx dialout && echo yes || echo no)"
    for t in $(ports); do
        read_port "$t"
        set -- kind port port "$P_PORT" usb "$P_USB" product "$P_PRODUCT" manufacturer "$P_MAKER" driver "$P_DRIVER" \
            counter "$P_COUNTER" why "$P_WHY" held "$P_HELD" by "$P_BY" openable "$P_OPEN" group "$P_GROUP"
        if [ -n "$P_VERSION" ]; then
            read_version "$P_VERSION"
            set -- "$@" serial "$P_SERIAL" version "$P_VERSION" model "$V_MODEL" firmware "$V_FW" thermometer "$V_THERM" logs "$P_DIR"
        fi
        out "$@"
    done
}

# The question itself, when radbeeper is not there to put it: the same sequence as radbeeper's
# src/counter.rs identify(). The port is locked as radbeeper locks it, so one a radbeeper holds is
# left without a byte written. 115200 then 57600 and no other rate.
asker() {
    cat <<'ASKER_EOF'
import fcntl, os, select, sys, termios, time

def read(fd, want, wait):
    got, end = b"", time.time() + wait
    while len(got) < want:
        left = end - time.time()
        if left <= 0 or not select.select([fd], [], [], left)[0]:
            break
        try:
            b = os.read(fd, want - len(got))
        except BlockingIOError:
            continue
        if not b:
            break
        got += b
    return got

def ask(path):
    for name, baud in (("115200", termios.B115200), ("57600", termios.B57600)):
        fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return "answer=busy"
            t = termios.tcgetattr(fd)
            t[0] &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK | termios.ISTRIP | termios.INLCR
                      | termios.IGNCR | termios.ICRNL | termios.IXON)
            t[1] &= ~termios.OPOST
            t[2] &= ~(termios.CSIZE | termios.PARENB | termios.CSTOPB | termios.CRTSCTS)
            t[2] |= termios.CS8 | termios.CREAD | termios.CLOCAL
            t[3] &= ~(termios.ECHO | termios.ECHONL | termios.ICANON | termios.ISIG | termios.IEXTEN)
            t[4] = t[5] = baud
            t[6][termios.VMIN] = 0
            t[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSANOW, t)
            termios.tcflush(fd, termios.TCIOFLUSH)
            # A counter left streaming is told to stop first, as radbeeper tells it.
            os.write(fd, b"<HEARTBEAT0>>")
            time.sleep(0.2)
            termios.tcflush(fd, termios.TCIFLUSH)
            os.write(fd, b"<GETVER>>")
            # Fourteen bytes is the document's answer; a GMC-320+V4 gives seventeen.
            raw = read(fd, 14, 1.0)
            while raw and len(raw) <= 64:
                more = read(fd, 16, 0.12)
                if not more:
                    break
                raw += more
            text = "".join(chr(c) for c in raw if 32 <= c < 127).strip()
            if "GMC" not in text.upper():
                continue
            termios.tcflush(fd, termios.TCIFLUSH)
            os.write(fd, b"<GETSERIAL>>")
            s = read(fd, 7, 1.0)
            serial = "".join("%02X" % c for c in s) if len(s) == 7 else "unknown"
            return "answer=gmc\tversion=%s\tserial=%s\tbaud=%s" % (text, serial, name)
        finally:
            os.close(fd)
    return "answer=none"

try:
    print(ask(sys.argv[1]))
except OSError as e:
    print("answer=error\terror=%s" % e.strerror)
ASKER_EOF
}

# ask PORT, with begin already done: sets A_ANSWER (gmc, none, busy, refused, error) and A_*.
ask_port() {
    A_ANSWER=refused; A_WHY=; A_VERSION=; A_SERIAL=; A_BAUD=; A_HOW=
    case "$1" in /dev/ttyUSB[0-9]*|/dev/ttyACM[0-9]*) ;; *) A_WHY="not a USB serial port: /dev/ttyUSBn or /dev/ttyACMn"; return 0 ;; esac
    [ -e "/sys/class/tty/${1#/dev/}" ] || { A_WHY="no such port"; return 0; }
    read_port "${1#/dev/}"
    [ "$P_COUNTER" = possible ] || { A_WHY="not opened: $P_WHY"; return 0; }
    [ "$P_HELD" = no ] || { A_WHY="not opened: held ($P_HELD) by $P_BY"; return 0; }
    [ "$P_OPEN" = yes ] || { A_WHY="$ME cannot open it: it is the group $P_GROUP's, and adding $ME to $P_GROUP is the root recipe's job (tools/fleet-radbeeper-root.sh)"; return 0; }
    if [ -n "$RB" ]; then
        A_HOW="$RB probe --device"
        r=$("$RB" probe --device "$1" 2>&1)
        A_VERSION=$(printf '%s\n' "$r" | sed -n 's/^counter  *//p' | head -n 1)
        A_SERIAL=$(printf '%s\n' "$r" | sed -n 's/^serial  *//p' | head -n 1)
        A_BAUD=$(printf '%s\n' "$r" | sed -n 's/^port .* @ \([0-9]*\) baud.*/\1/p' | head -n 1)
        if [ -n "$A_VERSION" ]; then A_ANSWER=gmc
        elif printf '%s' "$r" | grep -q '^port busy'; then A_ANSWER=busy
        else A_ANSWER=none; fi
    elif command -v python3 >/dev/null 2>&1; then
        A_HOW="python3 termios"
        r=$(asker | python3 - "$1" 2>&1 | tail -n 1)
        A_ANSWER=$(printf '%s' "$r" | tr '\t' '\n' | sed -n 's/^answer=//p')
        A_VERSION=$(printf '%s' "$r" | tr '\t' '\n' | sed -n 's/^version=//p')
        A_SERIAL=$(printf '%s' "$r" | tr '\t' '\n' | sed -n 's/^serial=//p')
        A_BAUD=$(printf '%s' "$r" | tr '\t' '\n' | sed -n 's/^baud=//p')
        [ -n "$A_ANSWER" ] || { A_ANSWER=error; A_WHY=$r; }
    else
        A_WHY="neither radbeeper nor python3 is here to put the question: run install first"
    fi
    return 0
}

ask() {
    [ -n "${1:-}" ] || { echo "ask PORT" >&2; exit 2; }
    begin
    ask_port "$1"
    case "$A_ANSWER" in
        gmc)
            read_version "$A_VERSION"
            if [ "$V_THERM" = yes ]; then note="GQ-RFC1201 gives <GETTEMP>> to GMC-320 Re.3.01 or later: this one has the thermometer"
            else note="GQ-RFC1201 gives <GETTEMP>> only to GMC-320 Re.3.01 or later: this one is read for counts and gives no temperature"; fi
            out kind ask port "$1" answer gmc version "$A_VERSION" model "$V_MODEL" firmware "$V_FW" serial "$A_SERIAL" \
                baud "$A_BAUD" thermometer "$V_THERM" note "$note" asked_by "$A_HOW" ;;
        none) out kind ask port "$1" answer none note "nothing answered <GETVER>> with a GMC version at 115200 or 57600: not a counter, or switched off" asked_by "$A_HOW" ;;
        busy) out kind ask port "$1" answer busy note "a radbeeper holds the port's lock: nothing was written to it" asked_by "$A_HOW" ;;
        *) out kind ask port "$1" answer "$A_ANSWER" note "$A_WHY" ;;
    esac
}

install() {
    find_radbeeper
    if [ -n "$RB" ] && [ "$RB_TEMP" = yes ]; then
        out kind install did nothing radbeeper "$RB" version "$RB_VERSION" logs_temperature yes note "already here, and it logs temperature"
        return 0
    fi
    had="${RB:+$RB $RB_VERSION, which does not log temperature}"
    cargo=$(command -v cargo 2>/dev/null); [ -n "$cargo" ] || { [ -x "$HOME/.cargo/bin/cargo" ] && cargo=$HOME/.cargo/bin/cargo; }
    if [ -z "$cargo" ]; then
        out kind install did stopped radbeeper "${RB:-none}" missing cargo \
            note "no cargo on PATH or in ~/.cargo/bin: radbeeper is built from source by Rust's cargo (1.70 or newer), and no toolchain is downloaded here. On Alpine or Copal: apk add cargo. On Ubuntu: apt install cargo, or rustup. Then run install again${had:+ (here now: $had)}"
        return 1
    fi
    if ! command -v cc >/dev/null 2>&1 && ! command -v gcc >/dev/null 2>&1; then
        out kind install did stopped radbeeper "${RB:-none}" missing cc \
            note "cargo is here ($cargo) and no C compiler to link with (cc): apk add build-base, or apt install build-essential, then run install again"
        return 1
    fi
    # Built in cargo's own scratch and put in ~/.cargo/bin: no checkout a running service uses is
    # touched, and nothing is replaced under a service (one that runs another copy keeps running it).
    log=$HOME/.fleet-queue/fleet-probes-install.log
    mkdir -p "$HOME/.fleet-queue"
    if nice -n 19 "$cargo" install --git "$GIT" --locked radbeeper > "$log" 2>&1; then
        new=$HOME/.cargo/bin/radbeeper
        v=$("$new" --version 2>/dev/null | head -n 1 | sed 's/^radbeeper *//')
        if "$new" --help 2>/dev/null | grep -q -- '--no-temp'; then t=yes; else t=no; fi
        out kind install did installed radbeeper "$new" version "$v" logs_temperature "$t" from "$GIT" \
            note "built by $cargo${had:+; it stands beside $had}$([ "$t" = no ] && echo '; this build does NOT log temperature')"
        return 0
    fi
    out kind install did failed radbeeper "${RB:-none}" note "cargo install failed: $(grep -v '^ *$' "$log" | tail -n 3 | tr '\n' ' ' | cut -c 1-300)" log "$log"
    return 1
}

serve() {
    begin
    if [ -z "$RB" ]; then
        out kind serve did stopped note "radbeeper is not installed: run install first"
        return 1
    fi
    list=; said=0
    for t in $(ports); do
        read_port "$t"
        [ "$P_COUNTER" = possible ] || continue
        said=1
        if [ "$P_HELD" != no ]; then
            out kind serve port "$P_PORT" did nothing note "already held ($P_HELD) by $P_BY"
        elif [ "$(boot_service)" != none ]; then
            out kind serve port "$P_PORT" did nothing note "a boot service is installed here ($(boot_service)) and is not serving this port: starting it is root's (rc-service radbeeper start, or systemctl start radbeeper), and a second service is not started beside it"
        elif [ "$P_OPEN" != yes ]; then
            out kind serve port "$P_PORT" did nothing needs_group "$P_GROUP" note "$ME cannot open $P_PORT: it is the group $P_GROUP's. Adding $ME to $P_GROUP is the root recipe's job (tools/fleet-radbeeper-root.sh), and the group counts from the next login"
        else
            port=$P_PORT
            ask_port "$port"
            if [ "$A_ANSWER" = gmc ]; then
                list="$list $port"
            else
                out kind serve port "$port" did nothing note "asked, and it is not a counter that answers ($A_ANSWER${A_WHY:+: $A_WHY})"
            fi
        fi
    done
    if [ -z "$list" ]; then
        [ "$said" = 1 ] || out kind serve did nothing note "no port here could be a counter"
        return 0
    fi
    if printf '%s\n' "$PROCS" | awk -v me="$ME" '$2 == me && / service( |$)/ { f = 1 } END { exit !f }'; then
        out kind serve did nothing ports "$list" note "a user service of $ME's is already running and was started without these ports: it is not stopped or restarted from here"
        return 0
    fi
    mkdir -p "$LOCAL"
    devs=; for p in $list; do devs="$devs --device $p"; done
    # Only the ports that answered are named: a service left to look for itself opens every port.
    if command -v setsid >/dev/null 2>&1; then
        # shellcheck disable=SC2086
        setsid "$RB" service $devs --logs "$LOCAL" >> "$LOCAL/service.log" 2>&1 < /dev/null &
    else
        # shellcheck disable=SC2086
        nohup "$RB" service $devs --logs "$LOCAL" >> "$LOCAL/service.log" 2>&1 < /dev/null &
    fi
    pid=$!
    sleep 5
    if kill -0 "$pid" 2>/dev/null; then
        out kind serve did started ports "$list" pid "$pid" logs "$LOCAL" radbeeper "$RB" logs_temperature "$RB_TEMP" \
            note "radbeeper service runs as $ME and writes $LOCAL. It does NOT survive a reboot: a service from boot is the root recipe (tools/fleet-radbeeper-root.sh)$([ "$RB_TEMP" = no ] && echo '. This radbeeper does not log temperature: run install')"
    else
        out kind serve did failed ports "$list" note "the service stopped at once: $(tail -n 3 "$LOCAL/service.log" 2>/dev/null | tr '\n' ' ' | cut -c 1-300)"
        return 1
    fi
}

# The collector's name for a counter's temperature: the serial's last four characters.
key_of() { printf 'room.rad%s.c' "$(printf '%s' "$1" | sed 's/^.\{10\}//')"; }

status() {
    begin
    seen=
    # The counters a running service serves, from the service.
    # (An empty field is carried as "-" through read, which would close up two tabs.)
    printf '%s' "$NOW" | awk -F'\t' -v OFS='\t' 'NF > 1 { for (i = 1; i <= NF; i++) if ($i == "") $i = "-"; print }' \
    | while IFS="$TAB" read -r dir serial cpm cpm300 usvh age temp tage live port version; do
        [ "$temp" = - ] && temp=
        [ "$tage" = - ] && tage=
        [ "$cpm" = - ] && cpm=
        [ "$cpm300" = - ] && cpm300=
        read_version "$version"
        set -- kind counter serial "$serial" model "$V_MODEL" firmware "$V_FW" port "$port" live "$live" \
            cpm "$cpm" cpm_300 "$cpm300" thermometer "$V_THERM" temp_c "$temp" temp_age "$tage" \
            served_by "$(server_of "$dir")" logs "$dir"
        [ "$V_THERM" = yes ] && set -- "$@" key "$(key_of "$serial")"
        out "$@"
    done
    # What a log says where no service would answer: this month's files, written in the last two minutes.
    month=$(date +%Y-%m); now=$(date +%s)
    for d in "$SYSTEM" "$LOCAL"; do
        for x in "$d"/cpm-[0-9A-F]*-"$month".tsv; do
            [ -r "$x" ] || continue
            serial=${x##*/cpm-}; serial=${serial%%-*}
            printf '%s' "$NOW" | grep -q "$TAB$serial$TAB" && continue
            a=$(( now - $(stat -c %Y "$x" 2>/dev/null || echo 0) ))
            [ "$a" -lt 120 ] || continue
            set -- kind counter serial "$serial" cpm_300 "$(tail -n 1 "$x" | cut -f 7)" cpm_age "$a" \
                served_by "a radbeeper that does not answer $ME (read from its log)" logs "$d"
            tf=$d/temp-$serial-$month.tsv
            if [ -r "$tf" ]; then
                set -- "$@" thermometer yes temp_c "$(tail -n 1 "$tf" | cut -f 2)" \
                    temp_age "$(( now - $(stat -c %Y "$tf" 2>/dev/null || echo 0) ))" key "$(key_of "$serial")"
            fi
            out "$@"
        done
    done
    # A port that could be a counter and that nothing serves.
    for t in $(ports); do
        read_port "$t"
        [ "$P_COUNTER" = possible ] && [ "$P_HELD" != radbeeper ] || continue
        out kind counter port "$P_PORT" usb "$P_USB" served_by none held "$P_HELD" \
            note "could be a counter and is not served: ask $P_PORT, then install and serve"
    done
}

case "${1:-}" in
    look) look ;;
    ask) ask "${2:-}" ;;
    install) install ;;
    serve) serve ;;
    status) status ;;
    asker) asker ;;
    *) sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
