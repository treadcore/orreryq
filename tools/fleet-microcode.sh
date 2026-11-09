#!/bin/sh
# Load the CPU's newest microcode at every boot: the distribution's package, handed to the kernel
# before the initramfs. A CPU otherwise runs the microcode its BIOS carries, and a BIOS is seldom
# updated: on 8 November saskatchewan's i7-13700F ran its BIOS's 0x10f of March 2023, from before
# Intel's fix for the 13th Gen Vmin shift, the instability that wears the chip out, while Alpine's
# intel-ucode carried 0x137. Paul installed the package and edited grub.cfg by hand; this is that,
# for the rest (columbia, jaguaribe, bosporus), and for any machine added later.
#
# Run it ON THE MACHINE, as root (orrery's Machines view: the recipe "Load the CPU's microcode"):
#
#   cd ~/orrery-recipes && doas sh fleet-microcode.sh      (Alpine, Copal)
#   cd ~/orrery-recipes && sudo sh fleet-microcode.sh      (Ubuntu)
#
# Alpine and Copal: apk add intel-ucode (or amd-ucode), then each initrd line in grub.cfg that
# loads the installed system's initramfs gets the image first, the old grub.cfg kept beside it as
# grub.cfg.pre-ucode; it is checked that the image is where grub will look before grub.cfg is
# touched, because an initrd line naming a missing file stops the boot. Ubuntu: apt installs
# intel-microcode (or amd64-microcode), whose hook puts it in the initramfs. Either way the new
# microcode is loaded at the next boot, which this does not do: a machine running a census is not
# restarted by a recipe. Run again, it changes nothing.
set -eu

[ "$(id -u)" = 0 ] || { echo "run as root (doas or sudo)" >&2; exit 1; }
case "$(sed -n 's/^vendor_id[[:space:]]*: //p' /proc/cpuinfo | head -n 1)" in
    GenuineIntel) apkpkg=intel-ucode; debpkg=intel-microcode ;;
    AuthenticAMD) apkpkg=amd-ucode;   debpkg=amd64-microcode ;;
    *) echo "not an Intel or AMD x86 CPU: no microcode package for it"; exit 0 ;;
esac
running=$(sed -n 's/^microcode[[:space:]]*: //p' /proc/cpuinfo | head -n 1)

if command -v apk >/dev/null 2>&1; then
    apk add "$apkpkg"
    img=/boot/$apkpkg.img
    [ -s "$img" ] || { echo "$apkpkg is installed but $img is not there: grub.cfg left alone" >&2; exit 1; }
    cfg=
    for c in /boot/boot/grub/grub.cfg /boot/grub/grub.cfg; do
        [ -f "$c" ] && cfg=$c && break
    done
    [ -n "$cfg" ] || { echo "no grub.cfg under /boot: add /$apkpkg.img to the boot loader's initrd by hand" >&2; exit 1; }
    # Grub reads paths from the boot partition, which is mounted at /boot: /boot/x is /x to it.
    case "$(awk '$2 == "/boot" { print $1 }' /proc/mounts)" in
        '') echo "/boot is not its own partition here: add the image to $cfg by hand" >&2; exit 1 ;;
    esac
    if grep -q "initrd /$apkpkg.img " "$cfg"; then
        echo "$cfg already loads /$apkpkg.img"
    else
        cp "$cfg" "$cfg.pre-ucode"
        # Only the installed system's entries: their initrd is /initramfs-FLAVOUR at the partition's
        # root. The live rescue's (/boot/initramfs-lts) is the stick's own and is left as it was.
        sed -i "s|^\([[:space:]]*initrd\) /initramfs-|\1 /$apkpkg.img /initramfs-|" "$cfg"
        n=$(grep -c "initrd /$apkpkg.img " "$cfg" || true)
        if [ "$n" = 0 ]; then
            cp "$cfg.pre-ucode" "$cfg"
            echo "no initrd line in $cfg names /initramfs-*: left as it was; add /$apkpkg.img by hand" >&2
            exit 1
        fi
        echo "$cfg: $n initrd line(s) now load /$apkpkg.img first (the old one is $cfg.pre-ucode)"
    fi
elif command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get -o DPkg::Lock::Timeout=900 install -y "$debpkg"
    echo "$debpkg is installed; its hook put it in the initramfs"
else
    echo "no apk or apt here" >&2
    exit 1
fi
echo "the CPU runs $running until the next boot, then the package's"
