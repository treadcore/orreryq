#!/usr/bin/env python3
"""firmware-check.py -- machines.py's firmware(), on what the fleet's machines said on 8 November.

    python3 tools/firmware-check.py

Each machine's facts are its probe's own lines of that afternoon, cut to the firmware's; each claim is
what Paul would be told. Nothing is read over ssh: the probe's half is proved by running it.
"""
import importlib.util
import os
import sys

spec = importlib.util.spec_from_file_location("machines", os.path.join(os.path.dirname(os.path.abspath(__file__)), "machines.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

SASKATCHEWAN = {"os_id": "alpine", "fw_bios": "B.D3 03/24/2023", "fw_board": "Micro-Star International Co., Ltd. PRO B760-VC WIFI (MS-7D98)",
                "cpu_vendor": "GenuineIntel", "cpu_fms": "06-b7-01", "microcode": "0x10f", "ucode_pkg": "", "ucode_repo": "20260812-r0",
                "disks_fw": "nvme0 Samsung SSD 980 PRO 1TB 2B2QGXA7;nvme1 Samsung SSD 980 PRO 2TB 5B2QGXA7;nvme2 CT4000P3SSD8 P9CR30A;sdc TEAM TM8PS7002T 0A0;"}
WHITEWOLF = {"os_id": "ubuntu", "fw_bios": "F22f 03/09/2018", "cpu_vendor": "GenuineIntel", "cpu_fms": "06-5e-03", "microcode": "0xf0",
             "ucode_pkg": "intel-microcode-3.20260210.0ubuntu0.24.04.1 ", "ucode_file": "0xf0",
             "disks_fw": "nvme0 Samsung SSD 950 PRO 256GB 1B0QBXX7;", "fwupd": "2.0.20-1ubuntu2~24.04.2", "fwupd_meta": "2026-11-07",
             "fwupd_updates": "UEFI dbx|20230501|20260707"}
BOBURNER = {"os_id": "ubuntu", "fw_bios": "F52h 07/27/2022", "cpu_vendor": "AuthenticAMD", "cpu_fms": "17-71-00", "microcode": "0x8701034",
            "disks_fw": "nvme0 CT4000P3SSD8 P9CR30A;", "fwupd": "1.9.27-0ubuntu1~24.04.1", "fwupd_error": "its service failed to start"}
fails = []


def claim(what, ok):
    print("%s  %s" % ("ok  " if ok else "FAIL", what))
    if not ok:
        fails.append(what)


def part(fw, name):
    return next((f for f in fw if f["part"] == name), {})


# fleet-firmware.sh's rows, read into the facts above: the probe's only reading of the firmware
rows = [l.split("\t") for l in """machine\tsaskatchewan\tMicro-Star International Co., Ltd. US Desktop Aegis RS\t-\tAlpine Linux v3.24; kernel 6.18.60-0-lts; scanned 2026-11-08T18:40:00-0800; as the user: no SMART
bios\tboard\tMicro-Star International Co., Ltd. PRO B760-VC WIFI (MS-7D98)\tB.D3\t03/24/2023; American Megatrends International, LLC.; UEFI
cpu\tcpu\t13th Gen Intel(R) Core(TM) i7-13700F\t0x137\tfamily-model-stepping 06-b7-01; intel-ucode-20260812-r0, loaded at boot; it carries 0x137
disk\tnvme2\tSamsung SSD 980 PRO 1TB\t2B2QGXA7\tNVMe; 1000 GB; smart: root only
disk\tsdb\tTS128GMSA230S\tR0427GN1\tSATA SSD; 128 GB; smart: root only
nic\teth0\tr8169, PCI 10ec:8125\trtl8125b-2_0.0.2 07/13/20\t-
update\tUEFI dbx\tMicrosoft\t20230501\tnewer: 20260707 (UEFI Secure Boot Forbidden Signature Database)""".splitlines()]
ff = m.fw_facts(rows)
claim("the scanner's rows read into the probe's facts", (ff["fw_bios"], ff["fw_board"], ff["microcode"], ff["cpu_fms"], ff["ucode_pkg"], ff["ucode_file"])
      == ("B.D3 03/24/2023", "Micro-Star International Co., Ltd. PRO B760-VC WIFI (MS-7D98)", "0x137", "06-b7-01", "intel-ucode-20260812-r0", "0x137"))
claim("and its disks, cards and fwupd's updates", ff["disks_fw"] == "nvme2 Samsung SSD 980 PRO 1TB 2B2QGXA7;sdb TS128GMSA230S R0427GN1;"
      and ff["nics_fw"] == "eth0 r8169 rtl8125b-2_0.0.2 07/13/20;" and ff["fwupd_updates"] == "UEFI dbx|20230501|20260707")
claim("a CPU on its BIOS's own microcode has no package", m.fw_facts([["cpu", "cpu", "x", "0x15", "family-model-stepping 06-2c-02; no package: the BIOS's own"]])["ucode_pkg"] == "")

fw = m.firmware(SASKATCHEWAN)
u = part(fw, "microcode")
claim("saskatchewan's microcode is behind, 0x10f against 0x137", (u.get("state"), u.get("now"), u.get("newest")) == ("behind", "0x10f", "0x137"))
claim("and says it runs the BIOS's own, and what that leaves open", "no microcode package" in u["why"] and "Vmin shift" in u["why"])
claim("and says Copal's way to load it", u["how"].startswith("doas apk add intel-ucode") and "grub.cfg" in u["how"])
n0, n1 = part(fw, "nvme0 Samsung SSD 980 PRO 1TB"), part(fw, "nvme1 Samsung SSD 980 PRO 2TB")
claim("its 980 PRO 1TB on 2B2QGXA7 is behind 5B2QGXA7", (n0.get("state"), n0.get("newest")) == ("behind", "5B2QGXA7"))
claim("its 980 PRO 2TB on 5B2QGXA7 is current", n1.get("state") == "current")
unknown = part(m.firmware(dict(SASKATCHEWAN, disks_fw="sdx ACME SSD 1TB A1;")), "sdx ACME SSD 1TB")
claim("a part with no entry is not checked, never current", unknown.get("state") == "not checked" and unknown.get("now") == "A1")
claim("the Crucial P3 is behind its maker's update server", (part(fw, "nvme2 CT4000P3SSD8").get("state"), part(fw, "nvme2 CT4000P3SSD8").get("newest")) == ("behind", "P9CR30D"))
claim("a disk whose maker publishes nothing is current, and says so", part(fw, "sdc TEAM TM8PS7002T").get("state") == "current" and "TEAMGROUP" in part(fw, "sdc TEAM TM8PS7002T")["why"])
whole = m.firmware(dict(SASKATCHEWAN, disks_fw="sdc Samsung SSD 850 EVO 500GB EMT02B6Q;sdd Samsung SSD 850 PRO 256GB EXM02B6Q;sde Samsung SSD 950 PRO 256GB 1B0QBXX7;"))
claim("an 850 EVO on EMT02B6Q is current (read whole, not as 2B6Q)", part(whole, "sdc Samsung SSD 850 EVO 500GB").get("state") == "current")
claim("an 850 PRO on the withdrawn EXM02B6Q is bad", part(whole, "sdd Samsung SSD 850 PRO 256GB").get("state") == "bad")
claim("a 950 PRO on 1B0QBXX7 is behind 2B0QBXX7", part(whole, "sde Samsung SSD 950 PRO 256GB").get("newest") == "2B0QBXX7")
claim("each network card is shown, its firmware's file named", part(m.firmware(dict(SASKATCHEWAN, nics_fw="eth0 r8169 rtl8125b-2_0.0.2 07/13/20;wlan0 iwlwifi 89.735b75a4.0 so-a0-gf-a0-89.uc;")), "eth0 r8169")
      == {"part": "eth0 r8169", "now": "rtl8125b-2_0.0.2 07/13/20", "newest": "rtl8125b-2_0.0.2 07/13/20", "state": "current",
          "why": "the newest file for the chip in upstream linux-firmware (its WHENCE)", "how": ""})
nics = m.firmware(dict(SASKATCHEWAN, nics_fw="wlan0 iwlwifi 89.735b75a4.0 so-a0-gf-a0-89.uc;enp8s0 mlx4_core 2.9.1000;enp9s0 mlx4_core 2.9.1200;eth9 acme 1.0;"))
claim("the AX211's -89 build is behind upstream's", (part(nics, "wlan0 iwlwifi")["state"], part(nics, "wlan0 iwlwifi")["newest"]) == ("behind", "89.a67023b2.0"))
claim("a ConnectX-2 on 2.9.1000 asks for its PSID, one on 2.9.1200 is the last there is",
      part(nics, "enp8s0 mlx4_core")["state"] == "not checked" and "mstflint" in part(nics, "enp8s0 mlx4_core")["why"]
      and part(nics, "enp9s0 mlx4_core")["state"] == "current")
claim("a card with no entry is not checked", part(nics, "eth9 acme")["state"] == "not checked")
claim("a Pascal card's VBIOS: nothing NVIDIA publishes for Linux", part(m.firmware(dict(WHITEWOLF, gpus_fw="gpu0|NVIDIA GeForce GTX 1080|86.04.60.01.80;")), "gpu0 NVIDIA GeForce GTX 1080")["state"] == "current")
b = part(fw, "BIOS")
claim("its BIOS B.D3 is behind MSI's BDA, with the sticker to read first", (b["state"], b["newest"]) == ("behind", "B.DA") and "sticker" in b["why"] and "Rufus" in b["how"])
claim("a board with no entry is shown, not judged", part(m.firmware(dict(SASKATCHEWAN, fw_board="ACME X1")), "BIOS")["state"] == "not checked")
claim("boburner's F52h is behind F55d", (lambda x: (x["state"], x["newest"]))(part(m.firmware(dict(BOBURNER, fw_board="Gigabyte Technology Co., Ltd. AB350-Gaming 3-CF")), "BIOS")) == ("behind", "F55d"))
claim("whitewolf's F22f is current", part(m.firmware(dict(WHITEWOLF, fw_board="Gigabyte Technology Co., Ltd. Z170M-D3H-CF")), "BIOS")["state"] == "current")
claim("MINIX's build names are not compared with DMI's", part(m.firmware(dict(SASKATCHEWAN, fw_board="MINIX Technology Limited NEO Z300-0dB", fw_bios="5.27 08/31/2024")), "BIOS")["state"] == "not checked")
bad = m.firmware(dict(SASKATCHEWAN, disks_fw="nvme0 Samsung SSD 980 PRO 2TB 3B2QGXA7;"))
claim("a 980 PRO on 3B2QGXA7 is bad, with the fault named", part(bad, "nvme0 Samsung SSD 980 PRO 2TB").get("state") == "bad" and "read-only" in part(bad, "nvme0 Samsung SSD 980 PRO 2TB")["why"])
up = part(m.firmware(dict(SASKATCHEWAN, ucode_pkg="intel-ucode-20260812-r0 ", ucode_file="0x137")), "microcode")
claim("the package installed and not loaded is said so", up.get("state") == "behind" and up["why"].startswith("the package carries 0x137 and the boot does not load it"))
claim("loaded, it is current", part(m.firmware(dict(SASKATCHEWAN, ucode_pkg="intel-ucode-20260812-r0 ", ucode_file="0x137", microcode="0x137")), "microcode").get("state") == "current")
claim("a package newer than the table is the newest", part(m.firmware(dict(SASKATCHEWAN, ucode_file="0x139")), "microcode").get("newest") == "0x139")

fw = m.firmware(WHITEWOLF)
claim("whitewolf's microcode is current", part(fw, "microcode").get("state") == "current")
claim("whitewolf's UEFI dbx is behind, by fwupd", (part(fw, "UEFI dbx").get("state"), part(fw, "UEFI dbx").get("newest"), part(fw, "UEFI dbx").get("how")) == ("behind", "20260707", "sudo fwupdmgr update"))
claim("with updates, fwupd's own line is not drawn twice", not part(fw, "fwupd (LVFS)"))
claim("with none, fwupd says it looked", part(m.firmware(dict(WHITEWOLF, fwupd_updates="")), "fwupd (LVFS)").get("state") == "current")

fw = m.firmware(BOBURNER)
claim("boburner's AMD microcode is the newest the OS can load, and says where the rest comes from",
      part(fw, "microcode").get("state") == "current" and "AGESA" in part(fw, "microcode")["why"])
claim("a failed fwupd is named, not taken for no updates", part(fw, "fwupd (LVFS)").get("why") == "its service failed to start" and part(fw, "fwupd (LVFS)").get("state") == "not checked")

# SMART, from the report the daily update saves as root (fleet-firmware.sh --save)
SMART = dict(SASKATCHEWAN, fw_saved="2026-11-08T18:30:00-0800",
             smart="nvme2|Samsung SSD 980 PRO 1TB|smart PASSED, 4% used, spare 100%, 0 media errors, 21000 h, 38 C#"
                   "sdc|TEAM TM8PS7002T|smart FAILED!, 8 reallocated, 3 pending, 30000 h#")
fw = m.firmware(SMART)
n0, sc = part(fw, "nvme0 Samsung SSD 980 PRO 1TB"), part(fw, "sdc TEAM TM8PS7002T")
claim("a disk the boot renamed (nvme2 then, nvme0 now) is still matched by its model", "4% used" in n0["why"] and n0["state"] == "behind")
claim("a disk whose SMART says FAILED is bad, whatever its firmware", sc["state"] == "bad" and sc["why"].startswith("SMART: smart FAILED!"))
claim("the report's time is a part of its own", part(fw, "SMART report").get("now") == "2026-11-08T18:30:00-0800" and part(fw, "SMART report")["state"] == "current")
claim("no report is said, with what installs it", part(m.firmware(SASKATCHEWAN), "SMART report").get("state") == "not checked"
      and "Update daily and at boot" in part(m.firmware(SASKATCHEWAN), "SMART report")["why"])

# the recipes: microcode for an x86 machine, applied when the boot loads it; the daily update
# applied only with its firmware scan
ms = m.Machines.__new__(m.Machines)
r = m.Machines.recipe("microcode")
claim("the microcode recipe is for x86 machines", ms.applies(r, {"os_id": "alpine", "os_version": "3.24", "arch": "x86_64"})[0]
      and not ms.applies(r, {"os_id": "alpine", "os_version": "3.24", "arch": "aarch64"})[0])
claim("applied on Copal when grub.cfg loads the image, on Ubuntu when the package is in",
      m.Machines.applied("microcode", {"os_id": "alpine", "ucode_boot": "/boot/boot/grub/grub.cfg"})
      and not m.Machines.applied("microcode", {"os_id": "alpine", "ucode_pkg": "intel-ucode-20260812-r0 "})
      and m.Machines.applied("microcode", {"os_id": "ubuntu", "ucode_pkg": "intel-microcode-3.20260210 "}))
claim("the daily update counts as applied only with its firmware scan",
      not m.Machines.applied("auto-update", {"auto_update": "yes"}) and m.Machines.applied("auto-update", {"auto_update": "yes", "fw_auto": "yes"}))

claim("a Mac has no firmware list", m.firmware({"os_id": "macos", "fw_bios": ""}) == [])
claim("a machine probed before the firmware was read has none", m.firmware({"os_id": "ubuntu", "pretty": "Ubuntu"}) == [])

print("FAILED: %d" % len(fails) if fails else "all %s" % "passed")
sys.exit(1 if fails else 0)
