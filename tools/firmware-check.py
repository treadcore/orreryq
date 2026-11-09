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


fw = m.firmware(SASKATCHEWAN)
u = part(fw, "microcode")
claim("saskatchewan's microcode is behind, 0x10f against 0x137", (u.get("state"), u.get("now"), u.get("newest")) == ("behind", "0x10f", "0x137"))
claim("and says it runs the BIOS's own, and what that leaves open", "no microcode package" in u["why"] and "Vmin shift" in u["why"])
claim("and says Copal's way to load it", u["how"].startswith("doas apk add intel-ucode") and "grub.cfg" in u["how"])
n0, n1 = part(fw, "nvme0 Samsung SSD 980 PRO 1TB"), part(fw, "nvme1 Samsung SSD 980 PRO 2TB")
claim("its 980 PRO 1TB on 2B2QGXA7 is behind 5B2QGXA7", (n0.get("state"), n0.get("newest")) == ("behind", "5B2QGXA7"))
claim("its 980 PRO 2TB on 5B2QGXA7 is current", n1.get("state") == "current")
claim("a part with no entry is not checked, never current", part(fw, "nvme2 CT4000P3SSD8").get("state") == "not checked" and part(fw, "sdc TEAM TM8PS7002T").get("now") == "0A0")
claim("each network card is shown, its firmware's file named", part(m.firmware(dict(SASKATCHEWAN, nics_fw="eth0 r8169 rtl8125b-2_0.0.2 07/13/20;wlan0 iwlwifi 89.735b75a4.0 so-a0-gf-a0-89.uc;")), "eth0 r8169")
      == {"part": "eth0 r8169", "now": "rtl8125b-2_0.0.2 07/13/20", "newest": "", "state": "not checked", "why": "", "how": ""})
claim("its BIOS is shown, not judged", part(fw, "BIOS") == {"part": "BIOS", "now": "B.D3 03/24/2023", "newest": "", "state": "not checked",
                                                              "why": "Micro-Star International Co., Ltd. PRO B760-VC WIFI (MS-7D98): its vendor's support page", "how": ""})
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
claim("boburner's AMD microcode is not checked", part(fw, "microcode").get("state") == "not checked")
claim("a failed fwupd is named, not taken for no updates", part(fw, "fwupd (LVFS)").get("why") == "its service failed to start" and part(fw, "fwupd (LVFS)").get("state") == "not checked")

claim("a Mac has no firmware list", m.firmware({"os_id": "macos", "fw_bios": ""}) == [])
claim("a machine probed before the firmware was read has none", m.firmware({"os_id": "ubuntu", "pretty": "Ubuntu"}) == [])

print("FAILED: %d" % len(fails) if fails else "all %s" % "passed")
sys.exit(1 if fails else 0)
