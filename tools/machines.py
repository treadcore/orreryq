#!/usr/bin/env python3
"""machines.py QUEUE COMMAND ... -- the fleet's machines, from a fresh install
to a node: what each one is, what has been applied to it, and the recipes
that make it a node. orrery's Machines view reads and drives it.

    status                  every machine and its recipes, as JSON (no ssh)
    probe [NAME|all]        read each machine over ssh, as the user: its OS,
                            CPU, memory, GPU, driver, CUDA, Rust, checkout,
                            tmux, copal-tm, login banner, power-off rule,
                            firmware (BIOS, microcode, each disk's, the
                            network cards', fwupd's updates); from those,
                            each recipe's state, and which firmware is behind
    add NAME USER@ADDRESS   a machine not in the fleet yet (a fresh install
                            with OpenSSH and your key: ssh-copy-id first)
    details RECIPE NAME     what applying it would do, as JSON: the files and
                            their sha256, the command, whether it applies
    stage RECIPE NAME       copy the recipe's files to ~/orrery-recipes/ on the
                            machine; print the command to type (as JSON)
    join NAME [--yes]       add it to the queue's config.json and the fleet's
                            nodes list (orrery's Sessions)
    pull NAME|all           every git checkout in the machine's home pulled,
                            fast-forward only, as the user (fleet-pull.sh)

THE RECIPES ARE ORRERY'S OWN SCRIPTS (tools/), and nothing else: each needs
root, and root is never run from here. `stage` copies; the command is typed
into the machine's tmux session by orrery's Sessions view, where the person
types the sudo password (Paul, 28 October: "Type it in a Sessions tile").
Every recipe checks before it acts, so running one again is safe; a recipe's
state ("applied") is read by `probe` from what it leaves behind, as the user,
with no root.

The registry is QUEUE/machines.json. Machines in the queue's config.json are
in it by being there.
"""
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8"]

# Each recipe: what it is, on which systems, what it needs, its files (from
# tools/), the command run on the machine as root, and what it does.
RECIPES = [
    {"id": "fleet-node", "title": "Make it a fleet node",
     "os": ["ubuntu 24.04"],
     "files": ["fleet-node.sh", "cuda-node.sh", "fleet-login.sh", "topnotch.sh", "fleet-poweroff-setup.sh"],
     "run": "bash fleet-node.sh",
     "does": ["the build tools (build-essential, pkg-config, git, curl, tmux)",
              "Rust for the user (rustup), in their home",
              "~/code/treadcore over HTTPS, and ~/fleet",
              "with an NVIDIA card: cuda-node.sh (the driver kept or installed, CUDA 12.9, the check)",
              "tmux and copal-tm",
              "the login banner (topnotch)",
              "the power-off rule (sudoers: poweroff, nothing else)"]},
    {"id": "cuda-node", "title": "CUDA: the driver, CUDA 12.9, tmux, copal-tm",
     "os": ["ubuntu 24.04"], "needs": "nvidia",
     "files": ["cuda-node.sh"], "run": "bash cuda-node.sh",
     "does": ["Ubuntu's 580 driver branch: kept if installed, else installed (prebuilt, signed modules)",
              "NVIDIA's CUDA repository at a low apt priority (it can never replace Ubuntu's driver)",
              "the CUDA 12.9 toolkit, and its PATH for every login",
              "the check: nvidia-smi and a CUDA program compiled for the card",
              "tmux, and copal-tm for the user"]},
    {"id": "fleet-login", "title": "The login banner (topnotch)",
     "os": ["ubuntu"],
     "files": ["fleet-login.sh", "topnotch.sh"], "run": "bash fleet-login.sh --role {role}",
     "does": ["/usr/local/bin/topnotch and the login message 01-copal-fleet: CPU, memory, disk, the GPU now, SSH work",
              "Ubuntu's advertising in the login message turned off (fleet-login.sh --undo puts it back)"]},
    {"id": "copal-node", "title": "Make it a fleet node (Copal)",
     "os": ["alpine"],
     "files": ["copal-node.sh", "fleet-poweroff-setup.sh"], "run": "sh copal-node.sh",
     "does": ["the build tools from Alpine's repositories, those missing (build-base, git, curl, tmux, rust, cargo)",
              "~/code/treadcore over HTTPS, and ~/fleet, as the user",
              "the power-off rule (doas: poweroff, nothing else)",
              "nothing else: Copal's lockdown, services and SSH are left as they are"]},
    # Not a state but an errand: never "applied", always there to run.
    {"id": "update", "title": "Update the system's packages",
     "os": ["ubuntu", "alpine"], "errand": True,
     "files": ["fleet-update.sh", "fleet-firmware.sh"], "run": "sh fleet-update.sh",
     "does": ["apk update and apk upgrade (Alpine), or apt-get update and upgrade (Ubuntu)",
              "a new kernel waits for the next boot: nothing is restarted",
              "then the firmware and SMART report, as root (fleet-firmware.sh --save), which the probe reads"]},
    {"id": "auto-update", "title": "Update daily and at boot",
     "os": ["ubuntu", "alpine"],
     "files": ["fleet-auto-update.sh", "fleet-update.sh", "fleet-firmware.sh"], "run": "sh fleet-auto-update.sh",
     "does": ["fleet-update.sh --auto every day (Alpine: crond at 2:00; Ubuntu: a systemd timer near 3:00, a missed day made up)",
              "each run ends with the firmware and SMART report (fleet-firmware.sh, with smartmontools and nvme-cli), which the probe reads",
              "and a few minutes after every boot (Alpine: OpenRC's local service; Ubuntu: the timer's OnBootSec)",
              "on Ubuntu the NVIDIA driver and CUDA held back in those runs: a driver upgraded under a running machine stops CUDA until the boot",
              "nothing is restarted; each run's line in /var/log/fleet-update.log; fleet-auto-update.sh --undo takes it away"]},
    {"id": "microcode", "title": "Load the CPU's microcode",
     "os": ["ubuntu", "alpine"], "needs": "x86",
     "files": ["fleet-microcode.sh"], "run": "sh fleet-microcode.sh",
     "does": ["Alpine and Copal: apk add intel-ucode (or amd-ucode), and each grub.cfg initrd line of the installed system loads its image first (the old grub.cfg kept as grub.cfg.pre-ucode)",
              "Ubuntu: apt installs intel-microcode (or amd64-microcode), into the initramfs",
              "loaded at the next boot, which this does not do: a running machine is not restarted"]},
    {"id": "poweroff", "title": "Let the fleet power it off",
     "os": ["ubuntu", "alpine"],
     "files": ["fleet-poweroff-setup.sh"], "run": "sh fleet-poweroff-setup.sh",
     "does": ["one rule: the user may run poweroff as root without a password, and nothing else"]},
    {"id": "listener", "title": "Answer the Lab's buttons",
     "os": ["ubuntu", "alpine"], "signed": True,
     "files": ["fleet-listener.sh", "fleet-exec.sh"], "run": "sh fleet-listener.sh",
     "does": ["the account copal-fleet: no password, no tty, one forced command (Message, Run, Scene, Power, facts)",
              "the fleet's CA and this machine's host certificate, signed here and checked there",
              "a human's certificate logs in as the user (Terminal, Exchange, Send); the user's own key keeps working",
              "one marked block in sshd_config, proved by sshd -t or taken back; sshd reloaded, not restarted",
              "the last message at every login",
              "--undo takes it all away"]},
]

# Read on the machine as the user: plain sh (busybox on Alpine), key=value.
PROBE = r'''
k() { printf '%s=%s\n' "$1" "$2"; }
. /etc/os-release 2>/dev/null
k os_id "${ID:-}"; k os_version "${VERSION_ID:-}"; k pretty "${PRETTY_NAME:-}"
k kernel "$(uname -r)"; k arch "$(uname -m)"
k cpus "$(grep -c ^processor /proc/cpuinfo)"
k cpu_model "$(grep -m1 'model name' /proc/cpuinfo | sed 's/.*: //')"
k mem_gb "$(awk '/MemTotal/ {printf "%.0f", $2/1048576}' /proc/meminfo)"
k disk "$(df -h / | awk 'NR==2 {print $3 " of " $2}')"
k addrs "$(ip -4 -o addr show scope global 2>/dev/null | awk '{print $2 " " $4}' | tr '\n' ';')"
g=""; for d in /sys/bus/pci/devices/*; do
  [ "$(cat $d/vendor 2>/dev/null)" = 0x10de ] || continue
  case "$(cat $d/class 2>/dev/null)" in 0x03*) g=$(basename $d);; esac
done
k nvidia_pci "$g"
k gpu "$(command -v lspci >/dev/null && lspci 2>/dev/null | grep -iE 'vga|3d' | grep -i nvidia | sed 's/.*: //' | head -n1)"
k nvidia_driver "$(sed -n 's/.*Kernel Module *\([0-9.]*\).*/\1/p' /proc/driver/nvidia/version 2>/dev/null | head -n1)"
k nvidia_smi "$(command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n1)"
k cuda "$(ls -d /usr/local/cuda-*/bin/nvcc 2>/dev/null | sed 's|/usr/local/cuda-\([^/]*\)/.*|\1|' | awk '{print length($0), $0}' | sort -n | tail -n1 | cut -d' ' -f2)"
k cargo "$( ( [ -x ~/.cargo/bin/cargo ] && ~/.cargo/bin/cargo --version ) || ( command -v cargo >/dev/null && cargo --version ) )"
k treadcore "$(git -C ~/code/treadcore log --oneline -1 2>/dev/null | cut -c1-7)"
k tmux "$(command -v tmux)"
k screen "$(command -v screen)"
k copal_tm "$( ( [ -x ~/.local/bin/copal-tm ] && echo ~/.local/bin/copal-tm ) || command -v copal-tm)"
k topnotch "$( [ -x /usr/local/bin/topnotch ] && echo yes)"
k listener "$( [ -x /usr/bin/copal-fleet-exec ] && echo yes)"
# The power-off command exactly as the rule allows it (fleet-poweroff-setup.sh):
# sudo lists it, for a NOPASSWD rule, to the user; doas's rule file is root's
# alone, but that it exists can be seen.
p=$(sudo -n -l 2>/dev/null | sed -n 's/.*NOPASSWD: *\(.*poweroff.*\)$/\1/p' | head -n1)
if [ -n "$p" ]; then k poweroff "sudo -n $p"
elif [ -e /etc/doas.d/fleet-poweroff.conf ]; then k poweroff "doas -n $(command -v poweroff || echo /sbin/poweroff)"
else k poweroff ""; fi
# Kept up to date by itself (fleet-auto-update.sh), and its last run's line.
k auto_update "$( ( [ -e /etc/periodic/daily/fleet-update ] || [ -e /etc/systemd/system/fleet-update.timer ] ) && echo yes)"
k updated "$(tail -n1 /var/log/fleet-update.log 2>/dev/null)"
k uptime "$(uptime | sed 's/.*up *//; s/, *[0-9]* user.*//')"
# The firmware, as the user: what the board, the CPU, the disks and the network
# cards run. firmware() below says which of it is behind.
dmi() { tr -s ' ' < /sys/class/dmi/id/$1 2>/dev/null | sed 's/ *$//'; }
k fw_system "$(dmi sys_vendor) $(dmi product_name)"
k fw_board "$(dmi board_vendor) $(dmi board_name)"
k fw_bios "$(dmi bios_version) $(dmi bios_date)"
k cpu_vendor "$(sed -n 's/^vendor_id[[:space:]]*: //p' /proc/cpuinfo | head -n1)"
fms=$(printf '%02x-%02x-%02x' "$(sed -n 's/^cpu family[[:space:]]*: //p' /proc/cpuinfo | head -n1)" \
  "$(sed -n 's/^model[[:space:]]*: //p' /proc/cpuinfo | head -n1)" "$(sed -n 's/^stepping[[:space:]]*: //p' /proc/cpuinfo | head -n1)" 2>/dev/null)
k cpu_fms "$fms"
k microcode "$(sed -n 's/^microcode[[:space:]]*: //p' /proc/cpuinfo | head -n1)"
# The microcode package and the revision it carries for this CPU: Ubuntu's
# files (06-5e-03.initramfs for a CPU Ubuntu loads only at boot), or Alpine's
# /boot/intel-ucode.img, one cpio of them all.
if command -v apk >/dev/null 2>&1; then
  k ucode_pkg "$(apk info -v 2>/dev/null | grep -E '^(intel|amd)-ucode-[0-9]' | tr '\n' ' ')"
  k ucode_repo "$(apk policy intel-ucode 2>/dev/null | sed -n '2s/^ *\([^:]*\):.*/\1/p')"
elif command -v dpkg-query >/dev/null 2>&1; then
  k ucode_pkg "$(dpkg-query -W -f '${Package}-${Version} ${Status}\n' intel-microcode amd64-microcode 2>/dev/null | grep 'install ok installed' | cut -d' ' -f1 | tr '\n' ' ')"
fi
u=/lib/firmware/intel-ucode/$fms; [ -f "$u" ] || u=$u.initramfs
if [ -f "$u" ]; then k ucode_file "0x$(od -An -tx4 -j4 -N4 "$u" | tr -d ' ' | sed 's/^0*//')"
elif [ -f /boot/intel-ucode.img ] && command -v python3 >/dev/null 2>&1; then
  k ucode_file "$(python3 -c '
import struct, sys
f, m, s = (int(x, 16) for x in sys.argv[1].split("-"))
want = (m >> 4) << 16 | f << 8 | (m & 15) << 4 | s
b = open("/boot/intel-ucode.img", "rb").read()
o, best = b.find(b"GenuineIntel.bin"), 0
o = (o + 17 + 3) & ~3 if o > 0 else len(b)
while o + 48 <= len(b):
    v, rev, d, sig = struct.unpack_from("<4I", b, o)
    ds, ts = struct.unpack_from("<2I", b, o + 28)
    if v != 1: break
    ts, ds = ts or 2048, ds or 2000
    sigs = [sig] + ([struct.unpack_from("<I", b, o + 48 + ds + 20 + 12 * i)[0] for i in range(struct.unpack_from("<I", b, o + 48 + ds)[0])] if ts > ds + 48 else [])
    best = max(best, rev) if want in sigs else best
    o += ts
print(hex(best) if best else "")' "$fms" 2>/dev/null)"
fi
# Each disk: its name, model and firmware revision, as the kernel reads them.
d=""; for n in /sys/class/nvme/nvme*; do [ -e "$n/model" ] || continue
  d="$d$(basename $n) $(tr -s ' ' < $n/model | sed 's/ *$//') $(tr -d ' ' < $n/firmware_rev);"; done
for b in /sys/block/sd*; do [ -e "$b/device/model" ] || continue
  d="$d$(basename $b) $(tr -s ' ' < $b/device/model | sed 's/ *$//') $(tr -d ' ' < $b/device/rev 2>/dev/null);"; done
k disks_fw "$d"
et=ethtool; for t in ethtool /usr/sbin/ethtool /sbin/ethtool; do command -v $t >/dev/null 2>&1 && et=$t && break; done
e=""; for n in /sys/class/net/*; do [ -e "$n/device/driver" ] || continue
  e="$e$(basename $n) $(basename "$(readlink $n/device/driver)") $($et -i $(basename $n) 2>/dev/null | sed -n 's/^firmware-version: *//p');"; done
k nics_fw "$e"
# The firmware and SMART report the daily update saves as root (fleet-firmware.sh
# --save), read here as the user: when it was made, and each disk's line,
# NAME|MODEL|SMART, a '#' after each. And whether the boot loads a microcode
# image (Copal's grub.cfg names it; Ubuntu's initramfs carries the package).
k fw_auto "$( [ -x /usr/local/sbin/fleet-firmware.sh ] && echo yes)"
r=/var/lib/fleet-firmware/report.tsv
if [ -r "$r" ]; then
  k fw_saved "$(sed -n 's/.*; scanned \([^;]*\);.*/\1/p' "$r" | head -n1)"
  k smart "$(awk -F'\t' '$1 == "disk" { d = $5; sub(/^[^;]*; [^;]*; /, "", d); printf "%s|%s|%s#", $2, $3, d }' "$r")"
fi
k ucode_boot "$(grep -l 'ucode\.img' /boot/boot/grub/grub.cfg /boot/grub/grub.cfg 2>/dev/null | head -n1)"
# fwupd, where it is installed (Ubuntu's own): the updates LVFS has for this
# machine, from the metadata its timer fetched, as the user, no root. A daemon
# that failed to start would hold the probe 25 s a call, so it is not asked.
if command -v fwupdmgr >/dev/null 2>&1; then
  k fwupd "$(dpkg-query -W -f '${Version}' fwupd 2>/dev/null || apk info -v 2>/dev/null | grep '^fwupd-[0-9]')"
  if command -v systemctl >/dev/null 2>&1 && systemctl -q is-failed fwupd 2>/dev/null; then k fwupd_error "its service failed to start"
  else
    k fwupd_meta "$(ls -l --time-style=+%Y-%m-%d /var/lib/fwupd/metadata/lvfs/ 2>/dev/null | awk '!/jcat/ && $6 ~ /^20/ {print $6; exit}')"
    k fwupd_updates "$(timeout 20 fwupdmgr get-updates --json --no-unreported-check --no-metadata-check 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except ValueError:
    sys.exit()
print(";".join("%s|%s|%s" % (x.get("Name"), x.get("Version"), (x.get("Releases") or [{}])[0].get("Version")) for x in d.get("Devices", [])))' 2>/dev/null)"
  fi
fi
'''

# WHAT IS OUT, kept by hand, with where it was read and when: the probe reads
# what a machine runs, and nothing on it says what its vendor has since
# published (fwupd does, for the parts whose vendors give LVFS their files,
# and it reads them itself). An entry here is a part found in the fleet and
# looked up; a part not here is "not checked", never "current".
MICROCODE = {
    "read": "intel-ucode 20260812 (Alpine's package of Intel's microcode), read 8 November 2026",
    # family-model-stepping: the newest revision, and what being below it means
    "06-b7-01": ("0x137", "a 13th Gen desktop Core: below 0x12b it is open to the Vmin shift, "
                          "the instability that wears the chip out (Intel's fix, September 2024)"),
    "06-be-00": ("0x21", ""),
    "06-2c-02": ("0x1f", "Westmere's last, of May 2018: the Spectre and L1TF fixes"),
    "06-9e-0d": ("0x104", ""),
    "06-5e-03": ("0xf0", ""),
}
PARTS = [
    {"model": "Samsung SSD 980 PRO", "newest": "5B2QGXA7",
     "read": "Samsung's SSD firmware page (the 980 PRO's ISO), 8 November 2026",
     "bad": {"3B2QGXA7": "the firmware that turns a 980 PRO read-only and kills it (Samsung, February 2023)"},
     "how": "Samsung's 980 PRO ISO, booted from a USB stick (or its fumagician run as root)"},
]
HOW_UCODE = {
    # Copal's grub.cfg is copal-init.sh's, written by hand, so nothing adds the image to it.
    "alpine": "doas apk add intel-ucode; in /boot/boot/grub/grub.cfg each initrd line becomes initrd /intel-ucode.img /initramfs-lts; a boot",
    "ubuntu": "sudo apt install intel-microcode, and a boot",
}


def firmware(f):
    """Each part's firmware against what is known to be out: [{part, now, newest, state, why, how}],
    state "behind", "bad" (a known fault), "current" or "not checked"."""
    if not f or f.get("os_id") == "macos" or "fw_bios" not in f:
        return []
    out = []

    def add(part, now, newest="", state="not checked", why="", how=""):
        out.append({"part": part, "now": now, "newest": newest, "state": state, "why": why, "how": how})

    def hexint(v):
        try:
            return int(v, 16)
        except (TypeError, ValueError):
            return None
    add("BIOS", f.get("fw_bios", ""), why="%s: its vendor's support page" % (f.get("fw_board") or "the board"))
    run, fms = f.get("microcode", ""), f.get("cpu_fms", "")
    if f.get("cpu_vendor") == "GenuineIntel" and hexint(run) is not None:
        known, means = MICROCODE.get(fms, ("", ""))
        pkg = f.get("ucode_file", "")
        newest = max([v for v in (known, pkg) if hexint(v)], key=hexint, default="")
        how = HOW_UCODE.get(f.get("os_id"), "")
        if not newest:
            add("microcode", run, why="no revision on record for CPU %s" % fms)
        elif hexint(run) >= hexint(newest):
            add("microcode", run, newest, "current")
        else:
            if hexint(pkg) and hexint(pkg) > hexint(run):
                why = "the package carries %s and the boot does not load it" % pkg
            elif "intel" not in f.get("ucode_pkg", ""):
                why = "no microcode package: the BIOS's own"
            else:
                why = "the package carries no newer one"
            add("microcode", run, newest, "behind", "; ".join(x for x in (why, means) if x), how)
    elif run:
        add("microcode", run, why="%s: not checked" % (f.get("cpu_vendor") or "the CPU"))
    # Each disk's SMART, from the report the daily update saved as root: by its name and model, or
    # by its model alone when one disk has it (a boot can rename nvme0 nvme2).
    smart = [r.split("|", 2) for r in f.get("smart", "").split("#") if r.count("|") >= 2]

    def health(name, model):
        hit = [h for n, m, h in smart if n == name and m.endswith(model)] or \
              [h for n, m, h in smart if m.endswith(model) and sum(1 for _, m2, _ in smart if m2 == m) == 1]
        return hit[0] if hit else ""
    for d in [x for x in f.get("disks_fw", "").split(";") if x.strip()]:
        name, _, rest = d.partition(" ")
        model, _, fw = rest.rpartition(" ")
        h = health(name, model)
        p = next((p for p in PARTS if model.startswith(p["model"])), None)
        if h and ("FAILED" in h or "critical warning" in h):
            add("%s %s" % (name, model), fw, (p or {}).get("newest", ""), "bad", "SMART: " + h,
                "back it up now; then smartctl -a as root")
        elif not p:
            add("%s %s" % (name, model), fw, why=h)
        elif fw in p.get("bad", {}):
            add("%s %s" % (name, model), fw, p["newest"], "bad", "; ".join(x for x in (p["bad"][fw], h) if x), p["how"])
        elif fw != p["newest"]:
            add("%s %s" % (name, model), fw, p["newest"], "behind", "; ".join(x for x in ("read: " + p["read"], h) if x), p["how"])
        else:
            add("%s %s" % (name, model), fw, fw, "current", h)
    if f.get("fw_saved"):
        add("SMART report", f["fw_saved"], state="current", why="saved by the daily update's firmware scan, as root")
    else:
        add("SMART report", "none", why="no report: Apply \"Update daily and at boot\" to install the scan",
            how="it installs fleet-firmware.sh with smartmontools and nvme-cli, and runs it")
    # A network card's firmware: a file the driver loads from linux-firmware (kept by the system's
    # updates), or the card's own (e1000e, igb, mlx4).
    for n in [x for x in f.get("nics_fw", "").split(";") if x.strip()]:
        name, drv, ver = (n.split(" ", 2) + ["", ""])[:3]
        add("%s %s" % (name, drv), ver.strip())
    if f.get("fwupd_error"):
        add("fwupd (LVFS)", f.get("fwupd", ""), why=f["fwupd_error"], how="sudo systemctl status fwupd; an upgraded fwupd may start")
    elif "fwupd" in f:
        ups = [u.split("|") for u in f.get("fwupd_updates", "").split(";") if u.count("|") == 2]
        for name, now, new in ups:
            add(name, now, new, "behind", "fwupd (LVFS)", "sudo fwupdmgr update")
        if not ups:
            add("fwupd (LVFS)", "metadata of %s" % (f.get("fwupd_meta") or "?"), state="current",
                why="no update for the parts whose vendors publish there")
    return out


# This Mac, the coordinator (a host whose target is "-"): read here, with
# macOS's own tools, since it has no /proc and no ssh address.
LOCAL_PROBE = r'''
k() { printf '%s=%s\n' "$1" "$2"; }
k os_id macos; k os_version "$(sw_vers -productVersion)"; k pretty "macOS $(sw_vers -productVersion)"
k hostname "$(scutil --get LocalHostName 2>/dev/null || hostname -s)"
k kernel "$(uname -r)"; k arch "$(uname -m)"
k cpus "$(sysctl -n hw.ncpu)"; k cpu_model "$(sysctl -n machdep.cpu.brand_string)"
k mem_gb "$(( $(sysctl -n hw.memsize) / 1073741824 ))"
k disk "$(df -h /System/Volumes/Data 2>/dev/null | awk 'NR==2 {print $3 " of " $2}')"
a=""; for i in en0 en1 en2; do x=$(ipconfig getifaddr $i 2>/dev/null) && a="$a$i $x;"; done; k addrs "$a"
k gpu "$(system_profiler SPDisplaysDataType 2>/dev/null | sed -n 's/^ *Chipset Model: *//p' | head -n1)"
PATH="$PATH:$HOME/.cargo/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin"
k cargo "$(command -v cargo >/dev/null && cargo --version)"
k treadcore "$(git -C ~/code/treadcore log --oneline -1 2>/dev/null | cut -c1-7)"
k tmux "$(command -v tmux)"; k copal_tm "$(command -v copal-tm)"
k orrery_app "$( [ -d ~/Applications/Orrery.app ] && echo yes)"
k copal_tm_app "$( [ -d ~/Applications/'Copal TM.app' ] && echo yes)"
k uptime "$(uptime | sed 's/.*up *//; s/, *[0-9]* user.*//')"
'''


def load(p, d):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def save(p, v):
    with open(p + ".tmp", "w") as f:
        json.dump(v, f, indent=1)
    os.replace(p + ".tmp", p)


class Machines:
    def __init__(self, q):
        self.q = os.path.abspath(q)
        self.cfg = load(os.path.join(self.q, "config.json"), {})
        self.reg_path = os.path.join(self.q, "machines.json")
        self.reg = load(self.reg_path, {})
        # Machines in the queue are in the registry by being there.
        for h in self.cfg.get("hosts", []):
            m = self.reg.setdefault(h["name"], {})
            m["target"] = h.get("target") or "-"
        self.fleet = self.cfg.get("fleet", "grove")

    def keep(self):
        save(self.reg_path, self.reg)

    def joined(self, name):
        return any(h["name"] == name for h in self.cfg.get("hosts", []))

    # ---- facts ------------------------------------------------------------------
    def probe(self, name):
        m = self.reg[name]
        try:
            if m["target"] == "-":
                r = subprocess.run(["bash", "-c", LOCAL_PROBE], capture_output=True, text=True, timeout=60)
            else:
                r = subprocess.run(SSH + [m["target"], PROBE], capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            m["probe_error"] = "no answer in 60 s"
            return
        if r.returncode != 0 and not r.stdout:
            m["probe_error"] = (r.stderr.strip().splitlines() or ["ssh failed"])[-1]
            return
        facts = {}
        for l in r.stdout.splitlines():
            if "=" in l:
                key, v = l.split("=", 1)
                facts[key] = v.strip()
        m["facts"] = facts
        m["probed"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        m.pop("probe_error", None)
        self.sync_poweroff(name, facts.get("poweroff", ""))

    def sync_poweroff(self, name, cmd):
        """A machine in the queue powers off by the command its rule now
        allows: join copied it once, so a rule applied after joining (or
        taken away) left shutdown-now with the wrong one, and the machine
        was left running (29 October: saskatchewan, xinanjiang, jaguaribe)."""
        path = os.path.join(self.q, "config.json")
        cfg = load(path, {})
        for h in cfg.get("hosts", []):
            if h["name"] == name and not h.get("lane_of") and h.get("poweroff", "") != cmd:
                if cmd:
                    h["poweroff"] = cmd
                else:
                    h.pop("poweroff", None)
                save(path, cfg)
                self.cfg = cfg

    # ---- recipes ------------------------------------------------------------------
    @staticmethod
    def recipe(rid):
        for r in RECIPES:
            if r["id"] == rid:
                return r
        raise SystemExit("no recipe %s (there are: %s)" % (rid, ", ".join(r["id"] for r in RECIPES)))

    @staticmethod
    def system(f):
        return "%s %s" % (f.get("os_id", ""), f.get("os_version", ""))

    def applies(self, r, f):
        """(yes, why): whether a recipe is for this machine, from its facts."""
        if not f:
            return False, "not probed yet"
        sysname = self.system(f)
        if not any(sysname == o or sysname.startswith(o + " ") or f.get("os_id") == o for o in r["os"]):
            return False, "for %s; this is %s" % (" or ".join(r["os"]), f.get("pretty") or sysname)
        if r.get("needs") == "nvidia" and not f.get("nvidia_pci"):
            return False, "needs an NVIDIA card; none on the PCI bus"
        if r.get("needs") == "x86" and f.get("arch") not in ("x86_64", "i686", "i386"):
            return False, "for an x86 CPU; this is %s" % (f.get("arch") or "not known")
        return True, ""

    @staticmethod
    def applied(rid, f):
        """Whether its effects are there, read without root."""
        nv = bool(f.get("nvidia_pci"))
        have = {
            "fleet-login": bool(f.get("topnotch")),
            "poweroff": bool(f.get("poweroff")),
            "listener": bool(f.get("listener")),
            # The daily update and, since 8 November, its firmware and SMART scan: a machine set up
            # before has the first and not the second, and Apply puts the second there.
            "auto-update": bool(f.get("auto_update")) and bool(f.get("fw_auto")),
            "microcode": bool(f.get("ucode_boot")) or ("microcode" in f.get("ucode_pkg", "") and f.get("os_id") != "alpine"),
            "copal-node": bool(f.get("cargo") and f.get("treadcore") and f.get("tmux") and f.get("poweroff")),
            "cuda-node": bool(f.get("nvidia_smi") and f.get("cuda") and f.get("tmux") and f.get("copal_tm")),
        }
        have["fleet-node"] = bool(f.get("cargo") and f.get("treadcore") and f.get("tmux") and f.get("copal_tm")
                                  and have["fleet-login"] and have["poweroff"] and (not nv or have["cuda-node"]))
        return have.get(rid, False)

    def recipe_states(self, name):
        f = self.reg[name].get("facts") or {}
        out = []
        for r in RECIPES:
            ok, why = self.applies(r, f)
            state = ("ready to run" if ok and r.get("errand") else "applied" if ok and self.applied(r["id"], f)
                     else "not applied" if ok else "not for it")
            # Everything the confirmation shows, so it needs no second call.
            out.append({"id": r["id"], "title": r["title"], "state": state, "why": why, "root": True,
                        "command": self.command(r, name), "does": r["does"],
                        "files": [{"name": fn, "sha256": self.sha(fn)} for fn in r["files"]]})
        return out

    _sums = {}

    @classmethod
    def sha(cls, fn):
        if fn not in cls._sums:
            cls._sums[fn] = hashlib.sha256(open(os.path.join(TOOLS, fn), "rb").read()).hexdigest()
        return cls._sums[fn]

    def root_cmd(self, f):
        return "doas" if f.get("os_id") == "alpine" else "sudo"

    def command(self, r, name):
        f = self.reg[name].get("facts") or {}
        role = "cuda" if f.get("nvidia_pci") else "cpu"
        return "cd ~/orrery-recipes && %s %s" % (self.root_cmd(f), r["run"].format(role=role))

    def details(self, rid, name):
        r, m = self.recipe(rid), self.reg[name]
        f = m.get("facts") or {}
        ok, why = self.applies(r, f)
        files = []
        for fn in r["files"]:
            p = os.path.join(TOOLS, fn)
            files.append({"name": fn, "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest(), "bytes": os.path.getsize(p)})
        return {"recipe": rid, "title": r["title"], "machine": name, "target": m["target"],
                "system": f.get("pretty", "not probed"), "gpu": f.get("gpu") or f.get("nvidia_smi") or "",
                "applies": ok, "why": why, "state": "applied" if self.applied(rid, f) else "not applied",
                "does": r["does"], "files": files, "to": "~/orrery-recipes/",
                "command": self.command(r, name), "root": self.root_cmd(f)}

    def stage(self, rid, name):
        d = self.details(rid, name)
        if not d["applies"]:
            raise SystemExit("%s is not for %s: %s" % (rid, name, d["why"]))
        t = self.reg[name]["target"]
        r = subprocess.run(SSH + [t, "mkdir -p ~/orrery-recipes"], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            raise SystemExit("cannot reach %s: %s" % (t, r.stderr.strip()[-200:]))
        r = subprocess.run(["scp", "-q", "-o", "BatchMode=yes"] + [os.path.join(TOOLS, f["name"]) for f in d["files"]]
                           + ["%s:orrery-recipes/" % t], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            raise SystemExit("copying to %s failed: %s" % (t, r.stderr.strip()[-200:]))
        if self.recipe(rid).get("signed"):
            self.sign_for(name, t)
        # What arrived is what was shown: the sums read back on the machine.
        names = " ".join(shlex.quote(f["name"]) for f in d["files"])
        r = subprocess.run(SSH + [t, "cd ~/orrery-recipes && (sha256sum %s 2>/dev/null || shasum -a 256 %s)" % (names, names)],
                           capture_output=True, text=True, timeout=30)
        there = dict((l.split()[1], l.split()[0]) for l in r.stdout.splitlines() if len(l.split()) == 2)
        bad = [f["name"] for f in d["files"] if there.get(f["name"]) != f["sha256"]]
        if bad:
            raise SystemExit("on %s the sums of %s do not match what was sent" % (name, ", ".join(bad)))
        self.reg[name].setdefault("log", []).append({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "staged": rid, "command": d["command"]})
        self.keep()
        return {"machine": name, "target": t, "command": d["command"], "files": [f["name"] for f in d["files"]]}

    def sign_for(self, name, t):
        """This machine's host certificate and the CA's public key, beside the
        recipe. THE SIGNING IS copal fleet certify's: orrery never creates a
        credential (docs/lockdown.md, section 5), it carries one. The key was
        born on the machine and is read over a login known_hosts vouches for;
        the listener checks what arrives."""
        capub = os.path.expanduser("~/.copal/ca/%s_ca.pub" % self.fleet)
        r = subprocess.run(SSH + [t, "cat /etc/ssh/ssh_host_ed25519_key.pub"], capture_output=True, text=True, timeout=30)
        if r.returncode != 0 or not r.stdout.startswith("ssh-ed25519"):
            raise SystemExit("%s has no ed25519 host key to sign" % name)
        addrs = re.findall(r"(\d+\.\d+\.\d+\.\d+)/", (self.reg[name].get("facts") or {}).get("addrs", ""))
        env = dict(os.environ, PATH=os.environ.get("PATH", "") + ":" + os.path.expanduser("~/.local/bin"))
        c = subprocess.run(["copal", "fleet", "certify", "--fleet", self.fleet, name] + addrs,
                           input=r.stdout, capture_output=True, text=True, timeout=30, env=env)
        if c.returncode != 0:
            raise SystemExit("signing %s failed: %s" % (name, c.stderr.strip()[-200:]))
        cert = c.stdout.strip().splitlines()[-1]
        with tempfile.TemporaryDirectory() as d:
            for src, dst in ((cert, "fleet-host-cert.pub"), (capub, "fleet-ca.pub")):
                shutil.copy(src, os.path.join(d, dst))
            r = subprocess.run(["scp", "-q", "-o", "BatchMode=yes", os.path.join(d, "fleet-host-cert.pub"),
                                os.path.join(d, "fleet-ca.pub"), "%s:orrery-recipes/" % t],
                               capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                raise SystemExit("copying the certificate to %s failed: %s" % (name, r.stderr.strip()[-200:]))

    # ---- joining ------------------------------------------------------------------
    def join(self, name):
        m = self.reg[name]
        f = m.get("facts") or {}
        if self.joined(name):
            raise SystemExit("%s is in the queue already" % name)
        if not (f.get("cargo") and f.get("treadcore")):
            raise SystemExit("%s has no Rust or no treadcore checkout yet: apply %s first, then probe"
                             % (name, "copal-node" if f.get("os_id") == "alpine" else "fleet-node"))
        caps = ["cpu", "gpu"] if f.get("nvidia_smi") and f.get("cuda") else ["cpu"]
        host = {"name": name, "target": m["target"], "caps": caps, "nice": 10}
        # The command exactly as the machine's rule allows it.
        if f.get("poweroff"):
            host["poweroff"] = f["poweroff"]
        cfg = load(os.path.join(self.q, "config.json"), {})
        cfg["hosts"].append(host)
        save(os.path.join(self.q, "config.json"), cfg)
        nodes = os.path.expanduser("~/.copal/fleets/%s/nodes" % self.fleet)
        addr = m["target"].split("@", 1)[-1]
        if os.path.exists(nodes) and not re.search(r"^%s\s" % re.escape(name), open(nodes).read(), re.M):
            with open(nodes, "a") as fh:
                fh.write("%-15s %s\n" % (name, addr))
        m.setdefault("log", []).append({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "joined": host})
        self.keep()
        return host

    def pull(self, name):
        """(answered, a line a checkout): fleet-pull.sh run over ssh as the
        user, fed on its stdin, so nothing is left on the machine."""
        target = self.reg[name]["target"] if name in self.reg else next(
            (h["target"] for h in self.cfg.get("hosts", []) if h["name"] == name), None)
        if not target:
            raise SystemExit("no machine %s" % name)
        body = open(os.path.join(TOOLS, "fleet-pull.sh"), "rb").read()
        argv = ["sh", "-s"] if target == "-" else SSH + [target, "sh -s"]
        try:
            r = subprocess.run(argv, input=body, capture_output=True, timeout=600)
        except subprocess.TimeoutExpired:
            return False, ["no answer in ten minutes"]
        out = r.stdout.decode(errors="replace").splitlines()
        if r.returncode != 0 and not out:
            return False, [(r.stderr.decode(errors="replace").strip().splitlines() or ["ssh failed"])[-1]]
        m = self.reg.setdefault(name, {"target": target})
        m.setdefault("log", []).append({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "pulled": out[-12:]})
        self.keep()
        return True, out

    # ---- crucible's lanes ------------------------------------------------------------
    # Paul, 28 October: "i want to see a button to add more gpu CUDA to the
    # mix, add crucible." A machine in the queue whose probe found an NVIDIA
    # card and CUDA gets a second lane, NAME-cuda, caps ["cuda"]: the same
    # machine, taking only crucible's segments, so its CPUs go on with
    # treadcore's censuses. It has no power-off of its own; the machine's own
    # lane powers it off.
    def cuda_ready(self):
        """(name, why not or ''): every joined machine, and whether it can
        take a crucible lane."""
        out = []
        for h in self.cfg.get("hosts", []):
            if "cuda" in h.get("caps", []):
                continue
            f = (self.reg.get(h["name"]) or {}).get("facts") or {}
            why = "" if f.get("nvidia_smi") and f.get("cuda") else ("no NVIDIA card" if not f.get("nvidia_pci") else "no CUDA yet: apply cuda-node")
            out.append((h["name"], why))
        return out

    def cuda_lanes(self, how, which="all"):
        cfg = load(os.path.join(self.q, "config.json"), {})
        hosts = cfg.get("hosts", [])
        have = {h["name"] for h in hosts}
        done = []
        if how == "add":
            for name, why in self.cuda_ready():
                if why or (which != "all" and name != which) or name + "-cuda" in have:
                    continue
                me = next(h for h in hosts if h["name"] == name)
                hosts.append({"name": name + "-cuda", "target": me["target"], "caps": ["cuda"], "nice": 10, "lane_of": name})
                done.append(name + "-cuda")
        elif how == "remove":
            keep = [h for h in hosts if not ("cuda" in h.get("caps", []) and (which == "all" or h.get("lane_of") == which))]
            done = [h["name"] for h in hosts if h not in keep]
            hosts[:] = keep
        else:
            raise SystemExit("cuda-lanes add|remove [NAME|all]")
        if done:
            cfg["hosts"] = hosts
            save(os.path.join(self.q, "config.json"), cfg)
            for n in done:
                m = self.reg.get(n[:-5] if n.endswith("-cuda") else n)
                if m is not None:
                    m.setdefault("log", []).append({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "cuda_lane": how})
            self.keep()
        return done

    def status(self):
        out = []
        for name in sorted(self.reg, key=lambda n: (self.joined(n), n)):
            m = self.reg[name]
            f = m.get("facts") or {}
            out.append({"name": name, "target": m.get("target", ""), "joined": self.joined(name),
                         "probed": m.get("probed", ""), "error": m.get("probe_error", ""), "facts": f,
                         "firmware": firmware(f),
                         "recipes": self.recipe_states(name), "log": m.get("log", [])[-5:],
                         "cuda_lane": any(h.get("lane_of") == name for h in self.cfg.get("hosts", []))})
        ready = [n for n, why in self.cuda_ready() if not why]
        lanes = [h["name"] for h in self.cfg.get("hosts", []) if "cuda" in h.get("caps", [])]
        return {"fleet": self.fleet, "machines": out, "cuda_ready": ready, "cuda_lanes": lanes}


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    ms, cmd = Machines(argv[1]), argv[2]
    if cmd == "status":
        print(json.dumps(ms.status()))
    elif cmd == "probe":
        names = list(ms.reg) if len(argv) < 4 or argv[3] == "all" else [argv[3]]
        for n in names:
            if n not in ms.reg:
                sys.exit("no machine %s" % n)
            ms.probe(n)
            m = ms.reg[n]
            print("%-13s %s" % (n, m.get("probe_error") or "%s; %s" % (m["facts"].get("pretty"), m["facts"].get("gpu") or "no NVIDIA card")))
        ms.keep()
    elif cmd == "add":
        if len(argv) < 5 or "@" not in argv[4] or not re.match(r"^[A-Za-z0-9][A-Za-z0-9-]*$", argv[3]):
            sys.exit("add NAME USER@ADDRESS (a name of letters, digits and hyphens)")
        ms.reg.setdefault(argv[3], {})["target"] = argv[4]
        ms.probe(argv[3])
        ms.keep()
        print(json.dumps(ms.status()["machines"][[m["name"] for m in ms.status()["machines"]].index(argv[3])]["recipes"]))
    elif cmd == "details":
        print(json.dumps(ms.details(argv[3], argv[4])))
    elif cmd == "stage":
        print(json.dumps(ms.stage(argv[3], argv[4])))
    elif cmd == "join":
        print(json.dumps(ms.join(argv[3])))
    elif cmd == "pull":
        names = [h["name"] for h in ms.cfg.get("hosts", []) if not h.get("lane_of")] if len(argv) < 4 or argv[3] == "all" else [argv[3]]
        bad = 0
        for n in names:
            ok, lines = ms.pull(n)
            bad += not ok
            for l in lines:
                print("%s: %s" % (n, l))
        print("pulled on %d machine(s)%s" % (len(names) - bad, ", %d did not answer" % bad if bad else ""))
        sys.exit(1 if bad and len(names) == 1 else 0)
    elif cmd == "cuda-lanes":
        how = argv[3] if len(argv) > 3 else "list"
        if how == "list":
            for n, why in ms.cuda_ready():
                lane = any(h.get("lane_of") == n for h in ms.cfg.get("hosts", []))
                print("%-13s %s" % (n, "crucible lane" if lane else (why or "ready for a crucible lane")))
        else:
            done = ms.cuda_lanes(how, argv[4] if len(argv) > 4 else "all")
            print("%s: %s" % ("added" if how == "add" else "removed", ", ".join(done) or "nothing to do"))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
