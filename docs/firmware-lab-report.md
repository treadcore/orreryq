# Every Part's Firmware: a Scan of the Fleet, What Is Current, and How Each Part Is Updated

*Paul Richeson · Lab Report — IEEE Format · 8 November 2026*

Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery.

Companions: `docs/calber-update-f15-lab-report.md` (how to read a BIOS list); `docs/ram-speed-lab-report.md` (§VI, calber's firmware survey, which this report extends to the fleet); `docs/calber-ssd-lab-report.md` (calber's six SATA SSDs); `docs/storage-lab-report.md` (the fleet's disks).

---

## Abstract

On 8 November orrery's Machines probe found that saskatchewan's i7-13700F was running microcode 0x10f. That revision came with its BIOS of March 2023, which predates Intel's fix for the 13th Gen Vmin shift, the fault that slowly wears these chips out. Alpine's `intel-ucode` package carried 0x137, but nothing on a Copal install loads it. Paul installed the package, added it to grub.cfg, and rebooted; saskatchewan has run 0x137 since.

Paul then asked for the same check on every part and every machine:
> "I want copal to be able to scan and suggest or at least list version of SSD nvme and all upgradable firmware and version numbers. I want a report and we can scan and use that report to investigate whether the version codes are current."

This report describes that scan and what it found:
- **A scanner, `tools/fleet-firmware.sh`.** It reads every part that carries firmware: the BIOS, the CPU microcode, each disk, each network card, each GPU, and whatever fwupd can update. Run as root it also reads SMART health.
- **One scanner, three users.** The Machines probe runs it, the daily update saves its root report, and Copal ships it as `copal firmware`.
- **The fleet.** Across the seven Linux machines it read 91 parts.
- **Current versions.** Each distinct part was looked up on its maker's own pages.
- **Results:**

| Status | Parts | What it means |
| --- | --- | --- |
| Behind | 13 | listed below |
| Current | 74 | 15 run their maker's newest release. 58 are parts whose makers publish no firmware at all: every hard disk, most of the cheap SSDs, the onboard network chips, and the GPUs as far as Linux goes. The last is calber's fwupd, which has nothing to offer. |
| Not checked | 4 | listed in §IV-G |

What is behind:
1. **BIOS:**
   - boburner: F52h → F55d. Four years of AMD security fixes are missing, including LogoFAIL, Sinkclose and the microcode signature flaw.
   - saskatchewan: B.D3 → BDA.
   - bosporus: 2.1 → 2.2.
2. **CPU microcode:**
   - columbia: 0xf → 0x21.
   - jaguaribe and bosporus: 0x15 → 0x1f.
3. **SSDs:**
   - saskatchewan's Samsung 980 PRO 1TB: 2B2QGXA7 → 5B2QGXA7.
   - whitewolf's Samsung 950 PRO: 1B0QBXX7 → 2B0QBXX7.
   - The two Crucial P3 4TB drives: P9CR30A → P9CR30D.
4. **Wi-Fi firmware:** the Intel cards in saskatchewan and columbia are four builds behind upstream.
5. **Secure Boot:** whitewolf's revocation list (UEFI dbx) is behind; fwupd offers the newer one.

**SMART health has not been read yet.** It needs root, so it arrives with the daily update once that recipe is applied again on each machine.

## I. Introduction

The Machines probe already read each machine's system, CPU, GPU and tools, all as the user and without root. On 8 November Paul asked whether saskatchewan had firmware updates, and how to check: "help me get commands. i actually want this part of the fleet information probe."

The first answer was the microcode. The rest of the question needed four things:
1. a scan that names every part's firmware;
2. a report of the whole fleet;
3. a lookup of each part against its maker;
4. a way to update what is behind.

He added two more: "A copal updater which also probes upgrades smart", and that "these should be part of copal too".

## II. The Scan

**What it reads.** `tools/fleet-firmware.sh` is plain sh, so it runs under busybox on Copal and under dash on Ubuntu. It prints one line per part: kind, name, model, version and detail. It reads sysfs, /proc and the package database, and writes to no device. It prints no serial numbers, because its output ends up in published reports.

| Part | Read from | Needs root |
| --- | --- | --- |
| BIOS | DMI: board, version, date, UEFI or legacy | no |
| CPU microcode | `/proc/cpuinfo`; the installed package and the revision it carries for this CPU (Ubuntu's file for the CPU, or Alpine's `/boot/intel-ucode.img`); whether the boot loads it | no |
| NVMe disk | sysfs model and firmware | no |
| SATA disk | the drive's own identity data, `/sys/class/ata_device/devN.M/id` (see below) | no |
| Disk on a SAS card | `smartctl -i` | yes |
| Network card | `ethtool -i` | no |
| GPU | `nvidia-smi` (the VBIOS version) | no |
| fwupd | the devices it can update and the updates its service has | no |
| SMART health | `smartctl`: percentage used, spare, media errors, reallocated and pending sectors, hours | yes |
| NVMe firmware slots | `nvme fw-log` | yes |
| UEFI firmware table (ESRT) | sysfs, which Copal makes root-only | yes |

**The kernel shortens SATA firmware strings.** A drive's firmware revision is 8 characters and its model 40. The fields the kernel exposes, `/sys/block/sdX/device/rev` and `model`, keep only 4 and 16 (libata's `ata_scsiop_inq_std` [21]). As a result:
- bosporus's Samsung read as "Samsung SSD 850" with firmware "2B6Q". That could not say whether it was an 850 EVO, which is current, or an 850 PRO on a firmware Samsung withdrew.
- jaguaribe's TEAM drives read as "0A" and "0B".

The full strings are in the drive's 256-word identity block, which libata publishes world-readable. The scanner decodes words 23–26 (the firmware) and 27–46 (the model). The 850 then names itself as an "850 EVO 500GB" on "EMT02B6Q", Samsung's newest.

One more wrinkle: jaguaribe's controller runs in IDE mode, with two drives on each ATA port. Matching a disk to its identity file by port alone gave sdh the SanDisk's identity. The match now uses the SCSI target number, which is the master/slave position on the port.

**Who runs it.** It is one file with three users, so the probe, the daily report and Copal can never disagree:
1. **The Machines probe** sends it after its own script and turns its rows into the facts the Firmware line and its checks read. The whole fleet takes 15 s.
2. **The daily update** (`fleet-update.sh`) runs it as root at the end of every run. It keeps the report at `/var/lib/fleet-firmware/report.tsv`, which the probe then reads as the user. That is how SMART reaches the Machines screen.
3. **Copal ships it as `copal firmware`**, written next to the `copal` command each time `copal-init` runs. Copal's `make sync-firmware` copies it in from orrery, and `make lint` fails if the two copies differ (the same arrangement as orrery's crypto profile).

## III. The Fleet

The seven Linux machines have 91 parts with firmware between them:
- 7 BIOSes and 7 CPUs;
- 54 disks: 9 NVMe, the rest SATA;
- 17 network ports;
- 3 GPUs;
- three lines from fwupd: whitewolf's Secure Boot list, calber's empty answer and boburner's failed service.

The tables, machine by machine, are in the Appendix. The two Macs update their firmware through macOS and are not part of this scan.

## IV. What Is Current

Each distinct part was looked up on its maker's own page, on 8 November, by four parallel searches: boards, SSDs, hard disks, and the rest. Gigabyte's, MSI's, Crucial's and TEAMGROUP's pages refuse automated reads, so those were read in a browser. A version found only on a secondary page is marked as such.

### A. Boards

| Machine | Board | Runs | Maker's newest | Notes |
| --- | --- | --- | --- | --- |
| boburner | Gigabyte AB350-Gaming 3 | F52h (Jul 2022) | **F55d (3 Sep 2026)** [11] | F53 fixes LogoFAIL. F54d fixes Sinkclose. F54g fixes the microcode signature flaw (CVE-2024-36347). F54 and F55d fix AMD's TPM. |
| saskatchewan | MSI PRO B760-VC WIFI (MS-7D98) | B.D3 (Mar 2023) | **BDA (17 Nov 2025)**, desktop line [12] | No notes from MSI. MSI lists this board under the Aegis R, not the Aegis RS, so read the case's sticker first. The retail board's line got 0x12B (Oct 2024) and 0x12F (May 2025). |
| bosporus | Supermicro X8DT3 | 2.1 | **2.2** [14] | Undated, no notes. |
| columbia | MINIX NEO Z300-0dB | 5.27 (Aug 2024) | AD0J0.235 (24 Mar 2026) [13] | Only on MINIX's file server, no notes. How "5.27" maps to MINIX's build names is unknown. |
| jaguaribe | Supermicro X8DTL | 2.1b | 2.1b [14] | Current. Supermicro also offers a separate microcode tool with the Spectre fixes. |
| calber | Gigabyte Z370 AORUS Gaming WIFI | F15 | F15 | Current (the F15 report). |
| whitewolf | Gigabyte Z170M-D3H | F22f (Mar 2018) | F22f | Current; nothing published since. |

### B. Microcode

| Machine | CPU | Runs | Newest | Loaded from |
| --- | --- | --- | --- | --- |
| saskatchewan | i7-13700F (06-b7-01) | 0x137 | 0x137 | intel-ucode, by grub.cfg (since this report) |
| calber | i7-9700F (06-9e-0d) | 0x104 | 0x104 | Ubuntu's intel-microcode |
| whitewolf | i7-6700K (06-5e-03) | 0xf0 | 0xf0 | Ubuntu's intel-microcode |
| boburner | Ryzen 7 3700X (17-71-00) | 0x8701034 | 0x8701034 by the OS [16] | Ubuntu's amd64-microcode. The EntrySign fix comes only in the BIOS's AGESA (ComboAM4v2PI 1.2.0.E or later, which is F54g and after on this board). |
| columbia | i3-N300 (06-be-00) | **0xf** | 0x21 | none: the BIOS's own |
| jaguaribe | 2× Xeon X5670 (06-2c-02) | **0x15** | 0x1f (May 2018: the Spectre and L1TF fixes) | none |
| bosporus | 2× Xeon E5645 (06-2c-02) | **0x15** | 0x1f | none |

The Intel revisions come from Alpine's `intel-ucode` 20260812, read out of its cpio for each CPU signature.

The four Alpine machines had no microcode package, and nothing on Copal would have loaded one. Its grub.cfg is written once by `copal-init.sh`; Alpine's `update-grub`, which would add the image, is never run on it. §V describes the fix.

### C. Solid-State Drives

| Drive | Where | Runs | Maker's newest | Notes |
| --- | --- | --- | --- | --- |
| Samsung 980 PRO 1TB | saskatchewan | **2B2QGXA7** | 5B2QGXA7 [4] | 2B2QGXA7 is not the faulty 3B2QGXA7, which turned drives read-only [3], but it is behind. |
| Samsung 980 PRO 2TB | saskatchewan | 5B2QGXA7 | 5B2QGXA7 | current |
| Samsung 950 PRO 256GB | whitewolf | **1B0QBXX7** | 2B0QBXX7 (file dated 30 Oct 2017) [5] | no notes from Samsung |
| Samsung 850 EVO 500GB | bosporus | EMT02B6Q | EMT02B6Q [6] | current |
| Crucial P3 4TB | saskatchewan, boburner | **P9CR30A** | P9CR30D [8] | Crucial's public page says there is no update; its own update server, the one Storage Executive asks, offers P9CR30D. Its notes cover a BIOS enumeration fault on ThinkPads, not data loss. |
| HP EX900 1TB, EX950 2TB | calber | R0802E0, 42A0S63C | none published | HP's pages offer nothing |
| FORESEE 512GB | columbia | SN12221 | none published | |
| "SATA SSD" ×6 (unbranded Phison S11) | calber | SBFM61.2 | none published | Forum images are cross-flashes; don't. |
| TEAM L5 LITE 3D 480GB, 120GB; TEAM MS30 2TB | jaguaribe, saskatchewan | Q0410A, Q0510B, W0220A0 | none published | |
| SanDisk Ultra II 480GB | jaguaribe | X41200RL | none on SanDisk's pages | Its forums name X41310RL and X41320RL; unconfirmed. |
| Transcend MSA230S 128GB ×2 | saskatchewan | R0427GN1 | only through SSD Scope (Windows) | |

LVFS, fwupd's update service, carries none of these drives [20]. Its Samsung and Phison entries are Dell and Lenovo OEM parts, and Crucial is "not uploading firmware to the LVFS".

### D. Hard Disks

None of the thirteen models has newer firmware from its maker [9]:
- WD Red, WD Blue, WD Green and the white-label 8 TB drives: WD says firmware for these is "normally not needed or available".
- HGST and Hitachi Ultrastar: only through a support case, for a drive still under warranty.
- Toshiba: publishes nothing.
- Seagate BarraCuda: its serial-number lookup was not run.

Two laptop drives have newer firmware from PC makers only:
- the HGST Travelstar: HP's A7L0 [10];
- the Toshiba: Dell's AV007D.

Both are Windows tools for HP's and Dell's own machines. OEM firmware on a retail drive can brick it, so neither is recommended.

**fwupd's "updatable" means less than it says.** fwupd marks whitewolf's six Travelstars "updatable", but that only means the drives accept a firmware download command [20]. No firmware for them exists on LVFS.

The known faults are fixed by settings or by where the drive is used, not by firmware:
- the WD Green's 8-second head parking, which `idle3ctl` changes;
- shingled (SMR) recording on the BarraCuda 8 TB and, probably, the WD Blue 2 TB, which makes long writes slow.

### E. Network Cards and GPUs

| Part | Where | Runs | Newest | Notes |
| --- | --- | --- | --- | --- |
| Realtek 8168G, 8125B (r8169) | boburner; saskatchewan, columbia | rtl8168g-2 0.0.1, rtl8125b-2 0.0.2 | the same [15] | Upstream linux-firmware's newest files |
| Intel 7265D Wi-Fi | calber | 29.9ef079ed.0 | the same | current |
| Intel AX211 / AX201 Wi-Fi | saskatchewan, columbia | **89.735b75a4.0** | four newer -89 builds upstream, the last committed 8 November 2026 [15] | Distribution packages lag behind upstream |
| Mellanox ConnectX-2 | boburner, whitewolf; jaguaribe | 2.9.1200; **2.9.1000** | 2.9.1200 (secondary pages only) [17] | End of life. Whether jaguaribe's card can take 2.9.1200 depends on its image ID (PSID), which `mstflint query` reads; ConnectX-2 support left mstflint after 4.20. |
| Intel 82576 (igb), I219/82574L (e1000e) | bosporus; calber, whitewolf, jaguaribe | 1.2.3; 0.2-4, 0.8-4, 1.8-0 | none published [18] | Onboard NVMs come only with the board's BIOS. |
| NVIDIA Pascal VBIOS (1070 Ti, 1080 Ti, 1080) | boburner, calber, whitewolf | 86.04.85.00.34, 86.02.39.00.9D, 86.04.60.01.80 | NVIDIA's DisplayPort 1.3/1.4 tool, Windows only [19] | It matters only with a DP 1.4 monitor, and these machines run headless. |

### F. fwupd

| Machine | fwupd |
| --- | --- |
| whitewolf | offers the UEFI revocation list (dbx) 20230501 → 20260707 |
| calber | offers nothing |
| boburner | its service fails to start (fwupd 1.9.27; 2.0.20 is waiting in the package updates). The probe reports that, rather than "no updates". |
| Copal machines | fwupd isn't installed. It would add little there: none of their parts' makers publish to LVFS. |

### G. Not Checked

Four parts:
- jaguaribe's ConnectX-2: needs its image ID first.
- columbia's MINIX BIOS: the build names can't be compared with what DMI shows.
- calber's USB card reader: no maker to look up.
- boburner's fwupd: it does not start.

## V. Microcode

| Version on saskatchewan | Microcode |
| --- | --- |
| Its BIOS of March 2023 | 0x10f |
| Intel's Vmin-shift fixes | 0x12B (September 2024), 0x12F (2025) [1], [2] |
| Alpine's `intel-ucode` 20260812 | 0x137 |

The fix needed no BIOS flash. Early-loading microcode from the boot loader is how Linux distributions ship Intel's fixes. Paul's three commands:
1. `doas apk add intel-ucode`
2. a `sed` that makes each installed entry's `initrd /initramfs-lts` into `initrd /intel-ucode.img /initramfs-lts`
3. Finish, then a reboot

saskatchewan came back at 17:26 on 0x137 and took a job at 17:28. A BIOS update would also bring Intel's Default Settings power profile, so the BIOS remains worth flashing (§IV-A).

What now does this everywhere:
- **New installs.** Copal's stage 3 installs `intel-ucode` or `amd-ucode` into every new install and writes the image into grub.cfg itself.
- **Existing machines.** The Machines recipe "Load the CPU's microcode" (`fleet-microcode.sh`) does Paul's edit on a running machine:
  - It checks that the image exists before naming it, because an initrd line naming a missing file stops the boot.
  - It keeps the old file as `grub.cfg.pre-ucode`.
  - It leaves the live rescue entry alone.
  - Run on a copy of saskatchewan's old grub.cfg, it produces Paul's hand-made edit byte for byte.
  - On Ubuntu it installs the package, which goes into the initramfs.
  - It restarts nothing.

columbia, jaguaribe and bosporus show it "not applied".

## VI. How Each Part Is Updated

The process, in the order that keeps a machine's work safe:

1. **Scan.** Probe the machine (Machines, Probe) and read its Firmware line.
2. **Read SMART first.** A drive with media errors or pending sectors is backed up before anything else is touched.
3. **Finish the machine's lane.** The machine hands in the job it has and leaves the queue, as saskatchewan did. No firmware update is made under a running job.
4. **Update, part by part, with the maker's own tool:**

| Part | How | Root? | Restart? |
| --- | --- | --- | --- |
| Microcode | recipe "Load the CPU's microcode" | yes (typed into the machine's Sessions tile) | a reboot |
| Gigabyte BIOS | Q-Flash from a FAT32 USB stick | at the console | yes |
| MSI desktop BIOS | MSI's bootable USB stick (Rufus), then load optimized defaults | at the console | yes |
| Supermicro BIOS | the DOS flash utility in the zip, from a bootable USB stick | at the console | yes |
| Samsung SSD | Samsung's ISO for the drive, booted from USB; or its `fumagician`, extracted from the ISO and run as root; then a full power cycle | yes | power cycle |
| Crucial P3 | Storage Executive (Windows); or as root `nvme fw-download` and `nvme fw-commit` with Crucial's image. That route is untried on the P3, which has one firmware slot, so a failed flash leaves no fallback. | yes | controller reset |
| Wi-Fi | the `linux-firmware` package, once it carries the new build | daily update | reload the driver |
| UEFI dbx | `sudo fwupdmgr update` | yes | reboot |
| ConnectX-2 | `mstflint -d BDF query`, then burn the image for its PSID (mstflint 4.20 or older) | yes | reboot |

5. **Reboot, probe again, and compare.** The Firmware line should show the part as current.
6. **Rejoin the fleet.** Add from the bench brings back the machine's settings.

Nothing here flashes firmware by itself. A firmware flash is a person's act at the machine. The probe says what is behind and what to type.

## VII. SMART

| Machine | SMART report |
| --- | --- |
| all seven | none yet |

The daily update keeps the report once "Update daily and at boot" is applied again on each machine. That step installs the scan, `smartmontools` and `nvme-cli`. Until then the Machines screen shows the recipe "not applied" and the report "none".

Once the report arrives:
- A disk whose SMART reports FAILED, or a critical warning, shows as **bad** whatever its firmware, with "back it up now".
- Every other disk carries its wear, spare, errors and hours in its line.
- A disk the reboot renamed (saskatchewan's 980 PRO went from nvme0 to nvme2) is matched by its model.

## VIII. What It Cannot Know

- **What is newest comes from a table kept by hand** (`MICROCODE`, `PARTS`, `BIOSES`, `NICS`, `GPUS` in `tools/machines.py`). Each entry says where it was read and when. Only fwupd checks itself, and only for its makers. The table ages, so a later lookup should replace it, not trust it.
- **A part not in it is "not checked", never "current".**
- **A maker that publishes nothing has the newest firmware there will be.** Such a part is "current", and its line says why.
- **MSI's desktop BIOS names, MINIX's builds and Gigabyte's lettered releases don't sort by date.** Dates matter, not letters.
- **Release notes are often missing.** MSI's BDA and Samsung's 950 PRO firmware have none.

## IX. Recommendations

In order of risk:
1. **Apply "Load the CPU's microcode" on columbia, jaguaribe and bosporus,** with Finish first and a reboot after. It costs nothing, is reversible, and is the only fix for the Westmere Xeons' Spectre and L1TF exposure short of the BIOS.
2. **Apply "Update daily and at boot" again on every machine,** so SMART is read daily.
3. **boburner: flash F55d.** It brings four years of AMD security fixes and the EntrySign microcode, which the OS cannot load.
4. **saskatchewan:**
   - Read the case's sticker.
   - If it is the Aegis R 13th, flash BDA.
   - Update the 980 PRO 1TB to 5B2QGXA7 with Samsung's ISO, after SMART has been read.
5. **whitewolf:**
   - Apply fwupd's dbx update.
   - The 950 PRO's 2B0QBXX7 has no notes, so it is optional.
6. **The Crucial P3s (P9CR30D):** optional. Its notes fix nothing the fleet has hit, and the update route from Linux is untried.
7. **Leave alone:** the hard disks, the OEM laptop-drive images, the unbranded SSDs' forum firmware, and the GPUs' DP tool.

## References

[1] Intel, "Intel Core 13th and 14th Gen Vmin Shift Instability Update — New Microcode Update (0x12F)," Intel Community, 2025.
[2] Tom's Hardware, "Raptor Lake instability saga continues as Intel releases 0x12F update to fix Vmin instability," 2025. https://www.tomshardware.com/pc-components/cpus/raptor-lake-instability-saga-continues-as-intel-releases-0x12f-update-to-fix-vmin-instability
[3] Puget Systems, "Critical Samsung SSD Firmware Update," 2023. https://www.pugetsystems.com/support/guides/critical-samsung-ssd-firmware-update/
[4] Samsung Semiconductor, "Consumer Storage: Tools." https://semiconductor.samsung.com/consumer-storage/support/tools/
[5] Samsung Australia, "SSD 950 PRO NVMe M.2 256GB (MZ-V5P256BW): Support." https://www.samsung.com/au/support/model/MZ-V5P256BW/
[6] Samsung, support pages for the 850 EVO (MZ-75E2T0B) and 850 PRO (MZ-7KE128BW). https://www.samsung.com/pt/support/model/MZ-75E2T0B/EU/ ; https://www.samsung.com/au/support/model/MZ-7KE128BW
[7] ComputerBase, "Fehlerhafte Firmware für SSD 850 Pro zurückgezogen," Feb. 2015. https://www.computerbase.de/2015-02/fehlerhafte-firmware-fuer-ssd-850-pro-zurueckgezogen/
[8] Crucial, "P3 SSD support," and its Storage Executive update server. https://www.crucial.com/support/ssd-support/p3-support ; https://www.orderingmemory.com/firmware/firmware.aspx?key=P3&fw=P9CR30A&fwType=CR
[9] Western Digital, "Firmware updates for WD drives," KB 50745, updated 11 Jun. 2026; "Kitfox," KB 51537. https://support-en.wd.com/app/answers/detailweb/a_id/50745 ; https://support-en.wd.com/app/answers/detailweb/a_id/51537
[10] HP, SoftPaq SP76532 (HGST Travelstar 5K1000 firmware A7L0). https://ftp.ext.hp.com/pub/softpaq/sp76501-77000/sp76532.html
[11] Gigabyte, BIOS lists for the GA-AB350-Gaming 3 (rev 1.x), GA-Z170M-D3H (rev 1.0) and Z370 AORUS Gaming WIFI (rev 1.0). https://www.gigabyte.com/Motherboard/GA-AB350-Gaming-3-rev-1x/support#Support-Bios
[12] MSI, "Aegis R 13th: Support," and "PRO B760-VC WIFI: Support." https://us.msi.com/Desktop/Aegis-R-13th/support#bios ; https://www.msi.com/Motherboard/PRO-B760-VC-WIFI/support#bios
[13] MINIX, file server, `MINXI_Z300-0dB_BIOS_AD0J0.235_20260324.zip`. https://files.theminixforum.com/shared/bios/
[14] Supermicro, BIOS downloads for the X8DTL-i and X8DT3. https://www.supermicro.com/en/support/resources/downloadcenter/firmware/MBD-X8DTL-i/BIOS ; https://www.supermicro.com/en/support/resources/downloadcenter/firmware/MBD-X8DT3/BIOS
[15] linux-firmware, WHENCE and the iwlwifi so-a0 commit history (gitlab.com/kernel-firmware mirror). https://gitlab.com/kernel-firmware/linux-firmware/-/raw/main/WHENCE
[16] linux-firmware, `amd-ucode/README`; NVD, CVE-2024-36347. https://gitlab.com/kernel-firmware/linux-firmware/-/raw/main/amd-ucode/README
[17] NVIDIA Networking, "ConnectX EN firmware"; TrueNAS Community, "HP branded ConnectX-2 firmware update." https://network.nvidia.com/support/firmware/connectxen/
[18] Intel, "NVM Update Package" (adapters user guide), and support article 000057261. https://edc.intel.com/content/www/us/en/design/products/ethernet/adapters-and-devices-user-guide/nvm-update-package/
[19] NVIDIA, "Graphics Firmware Update Tool for DisplayPort 1.3 and 1.4 Displays." https://www.nvidia.com/en-us/drivers/nv-uefi-update-x64/
[20] fwupd, "ATA plugin" (libfwupdplugin documentation); LVFS vendor list. https://fwupd.github.io/libfwupdplugin/ata-README.html ; https://fwupd.org/lvfs/vendors/
[21] Linux kernel, `drivers/ata/libata-scsi.c`, `ata_scsiop_inq_std`; `drivers/ata/libata-transport.c` (the `id` attribute).

## Appendix: Every Machine's Parts

Read on 8 November 2026 by `tools/fleet-firmware.sh` through the Machines probe, as the user. "Same" means the part runs the newest known version. "Current" with no newer version listed means its maker publishes none. Network ports without a cable show anyway, because their firmware is the card's.

**saskatchewan**: MSI US Desktop Aegis RS; 13th Gen Intel Core i7-13700F; Alpine Linux v3.24.

| Part | Runs | Newest known | State |
| --- | --- | --- | --- |
| BIOS | B.D3 03/24/2023 | B.DA | **behind** |
| microcode | 0x137 | same | current |
| Samsung SSD 980 PRO 2TB (nvme0) | 5B2QGXA7 | same | current |
| CT4000P3SSD8 (nvme1) | P9CR30A | P9CR30D | **behind** |
| Samsung SSD 980 PRO 1TB (nvme2) | 2B2QGXA7 | 5B2QGXA7 | **behind** |
| WDC WD20EZBX-00AYRA0 (sda) | 01.01A01 | same | current |
| TS128GMSA230S (sdb, sdd) | R0427GN1 | same | current |
| TEAM TM8PS7002T (sdc) | W0220A0 | same | current |
| eth0 r8169 | rtl8125b-2_0.0.2 07/13/20 | same | current |
| wlan0 iwlwifi | 89.735b75a4.0 so-a0-gf-a0-89.uc | 89.a67023b2.0 | **behind** |

**boburner**: Gigabyte AB350-Gaming 3; AMD Ryzen 7 3700X; Ubuntu 24.04.5 LTS.

| Part | Runs | Newest known | State |
| --- | --- | --- | --- |
| BIOS | F52h 07/27/2022 | F55d | **behind** |
| microcode | 0x8701034 | same | current |
| CT4000P3SSD8 (nvme0) | P9CR30A | P9CR30D | **behind** |
| HGST HDN726040ALE614 (sda, sdb, sdc, sdf) | APGNW7JH | same | current |
| Hitachi HUS724040ALE641 (sdd) | MJAOA5F0 | same | current |
| HGST HUS724040ALA640 (sde) | MFAOAC50 | same | current |
| gpu0 NVIDIA GeForce GTX 1070 Ti | 86.04.85.00.34 | same | current |
| eno1 r8169 | rtl8168g-2_0.0.1 02/06/13 | same | current |
| enp6s0 mlx4_core | 2.9.1200 | same | current |
| fwupd (LVFS) | 1.9.27-0ubuntu1~24.04.1 | - | not checked |

**calber**: Gigabyte Z370 AORUS Gaming WIFI; Intel Core i7-9700F; Ubuntu 24.04.5 LTS.

| Part | Runs | Newest known | State |
| --- | --- | --- | --- |
| BIOS | F15 11/13/2021 | F15 | current |
| microcode | 0x104 | same | current |
| HP SSD EX900 1TB (nvme0) | R0802E0 | same | current |
| HP SSD EX950 2TB (nvme1) | 42A0S63C | same | current |
| SATA SSD (sda, sdb, sdc, sdd, sde, sdf) | SBFM61.2 | same | current |
| Generic STORAGE DEVICE (sdg) | 9451 | - | not checked |
| gpu0 NVIDIA GeForce GTX 1080 Ti | 86.02.39.00.9D | same | current |
| eno1 e1000e | 0.2-4 | same | current |
| wlp8s0 iwlwifi | 29.9ef079ed.0 7265D-29.ucode | same | current |
| fwupd (LVFS) | metadata of 2026-11-07 | - | current |

**whitewolf**: Gigabyte Z170M-D3H; Intel Core i7-6700K; Ubuntu 24.04.5 LTS.

| Part | Runs | Newest known | State |
| --- | --- | --- | --- |
| BIOS | F22f 03/09/2018 | F22f | current |
| microcode | 0xf0 | same | current |
| Samsung SSD 950 PRO 256GB (nvme0) | 1B0QBXX7 | 2B0QBXX7 | **behind** |
| HGST HTS541010A9E680 (sda, sdb, sdc, sdd, sde, sdf) | JA0OA7J0 | same | current |
| gpu0 NVIDIA GeForce GTX 1080 | 86.04.60.01.80 | same | current |
| enp0s31f6 e1000e | 0.8-4 | same | current |
| enp8s0 mlx4_core | 2.9.1200 | same | current |
| UEFI dbx | 20230501 | 20260707 | **behind** |

**columbia**: MINIX NEO Z300-0dB; Intel Core i3-N300; Alpine Linux v3.24.

| Part | Runs | Newest known | State |
| --- | --- | --- | --- |
| BIOS | 5.27 08/31/2024 | AD0J0.235 | not checked |
| microcode | 0xf | 0x21 | **behind** |
| FORESEE 512GB SSD (nvme0) | SN12221 | same | current |
| eth0 r8169 | rtl8125b-2_0.0.2 07/13/20 | same | current |
| wlan0 iwlwifi | 89.735b75a4.0 so-a0-hr-b0-89.uc | 89.a67023b2.0 | **behind** |

**jaguaribe**: Supermicro X8DTL; Intel Xeon X5670 (two); Alpine Linux v3.24.

| Part | Runs | Newest known | State |
| --- | --- | --- | --- |
| BIOS | 2.1b 11/16/2012 | 2.1b | current |
| microcode | 0x15 | 0x1f | **behind** |
| Hitachi HUA72302 (sda, sdd) | A840 | same | current |
| Hitachi HDS5C302 (sdb, sdc) | A180 | same | current |
| WDC WD20EARX-22P (sde) | AB51 | same | current |
| WDC WD20EARX-008 (sdf) | AB51 | same | current |
| SanDisk Ultra II 480GB (sdg) | X41200RL | same | current |
| TEAML5Lite3D480G (sdh, sdj) | Q0410A | same | current |
| TEAM L5 LITE SSD 120GB (sdi) | Q0510B | same | current |
| HGST HTS541010A9E680 (sdk) | JA0OA7J0 | same | current |
| eth0 e1000e | 1.8-0 | same | current |
| eth1 e1000e | 1.8-0 | same | current |
| eth2 mlx4_core | 2.9.1000 | - | not checked |

**bosporus**: Supermicro X8DT3; Intel Xeon E5645 (two); Alpine Linux v3.24.

| Part | Runs | Newest known | State |
| --- | --- | --- | --- |
| BIOS | 2.1 03/17/2012 | 2.2 | **behind** |
| microcode | 0x15 | 0x1f | **behind** |
| TOSHIBA MQ01ACF050 (sda) | AV0A1C | same | current |
| WDC WD80EFAX-68LHPN0 (sdb, sdd) | 83.H0A83 | same | current |
| Samsung SSD 850 EVO 500GB (sdc) | EMT02B6Q | same | current |
| WDC WD80EDAZ-11T (sde, sdf, sdg, sdh, sdi) | 0A81 | same | current |
| WDC WD80EMAZ-00W (sdj, sdk) | 0A83 | same | current |
| ST8000DM004-2CX1 (sdl) | 0001 | same | current |
| eth0 igb | 1.2.3 | same | current |
| eth1 igb | 1.2.3 | same | current |
| eth2 igb | 1.2.3 | same | current |
| eth3 igb | 1.2.3 | same | current |

