# F15 on calber: Reading a BIOS List Correctly, the Firmware It Brought, CSM Off, and Nothing Left to Update

*Paul Richeson · Lab Report — IEEE Format · 7 November 2026*

Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery.

Companions: `docs/calber-power-cut-lab-report.md` (the outage); `docs/calber-bios-recovery-lab-report.md` (the CMOS clear and the settings); `docs/ram-speed-lab-report.md` (the memory at 3200, and §VI, the firmware survey this report finishes); `docs/calber-todo.md` (what is left).

---

## Abstract

calber ran BIOS F15a, a beta from November 2019. Gigabyte lists two releases after it:
- **F15b** (March 2021) adds only Resizable BAR, which the GTX 1080 Ti cannot use;
- **F15** (November 2021) carries "major vulnerabilities updates" and cannot be rolled back.

F15 looks older than F15a, but it is two years newer: on Gigabyte's lists a letter marks a beta or interim build, and the plain number is the finished release.

F15 was downloaded from Gigabyte's own server, its image checked by hash, and flashed with Q-Flash from a USB stick on 7 November. The flash changed three things:

| | Before | After |
| --- | --- | --- |
| BIOS | F15a, 11/28/2019 | **F15, 11/13/2021** |
| Microcode built into the BIOS | 0xCA | 0xEA |
| Intel ME firmware | 11.8.70.3626 | **11.8.81.3807** |

The ME update came inside the BIOS image, so no separate ME update is needed. XMP Profile 1, set again after the flash, still runs the memory at 3200 MT/s (27,714 MB/s triad, 58.7 ns).

With CSM then turned off, the boot list fell from ten entries to two, and the legacy table left the kernel log. No errors were logged at boot. Every drive, the network and the GPU came up.

Afterwards nothing is left to update:
- fwupd, as user and as root, offers nothing for the drives or the TPM;
- the CPU microcode (0x104), the kernel and every package are current.

The UEFI revocation list that fwupd offered before the flash is moot now: the flash left Secure Boot in Setup Mode with no keys at all, and Secure Boot is off. One measurement is still owed: how long an unattended boot spends in firmware.

## I. Introduction

The memory report's firmware survey (§VI) left the BIOS as the one open item. A third-party index had shown F15a as the board's last release; another copy showed an F15 from 2021. Gigabyte's own page refused automated reads (HTTP 403), so Paul read it himself and pasted it: "i present this". He had downloaded the F15b zip. Then he asked: "What do you want F15, is that a downgrade." And: "wow. confusing."

The work this report records:
1. read the list correctly, and choose a version;
2. get the file and prove it is the file;
3. flash it, set calber up again, and check every claim from Linux;
4. answer "is there any more firmware to update".

## II. Gigabyte's List, Read Correctly

Two things on Gigabyte's BIOS list mislead.

**On the page, each release's notes stand above its version line, not below it.** A reader who expects a version's notes to follow it pins each paragraph on the wrong release. They belong to the version below them: F12's notes, for example, match the F12 entry in an independent copy.

**The names do not sort by date.** A letter after the number marks a beta or interim build. The plain number is the release.

| Version | Date | Gigabyte's notes | For calber |
| --- | --- | --- | --- |
| F15a | Nov 28, 2019 | "Workaround beta BIOS to improve Kingston DDR4-2666 stability … Add NTFS format support for Q-Flash" | what it ran |
| F15b | Mar 23, 2021 | "Enable Resizable Base-Address Register (Resizable-BAR) option to enhance GPU performance" | nothing: Pascal cards cannot use Resizable BAR |
| **F15** | **Nov 29, 2021** | "Major vulnerabilities updates … Credits to Assaf Carlsbad and Itai Liba from SentinelOne. Introduce capsule BIOS support starting this version. Customers will NOT be able to reverse to previous BIOS version." Checksum 1683 | **the one to flash** |

Three things agree that F15 is the newest:
- **its date**;
- **its place at the top of a list that runs newest first**;
- **its note that there is no way back.**

That note only makes sense for the latest release. **Go by the dates, not the letters.**

The third-party index cited in the recovery report had shown F15a as the last. It was wrong, and that report now says so.

## III. Method

### A. The file

| | |
| --- | --- |
| Source | `download.gigabyte.com/FileList/BIOS/mb_bios_z370-aorus-gaming-wifi_f15.zip`, Gigabyte's own file server, which answered where its web page refused |
| Zip | 6,740,356 bytes (the page says 6.43 MB), Last-Modified 6 December 2021; sha256 `1038a5ac…ba85e6` |
| Inside | `Z370AOGW.F15` (16,777,216 bytes, 6 Dec 2021), `Efiflash.exe` and `autoexec.bat` (a DOS flasher, for a legacy boot stick), `readme.txt` (the flasher's switches, among them `/DB`, "update both main & backup BIOS") |
| Image | sha256 `ca83dfd1fab52d33720ad496ad2a1c89a6400b986aa377e459a78db1bdd8c5aa` |

Only the image and the readme were taken out of the zip, into their own folder (`~/Downloads/z370-bios-f15/`). Q-Flash, in the BIOS, needs only the image. Paul's earlier F15b download is the same server's file: its size matched the server's to the byte.

### B. Onto something Q-Flash can read

The Mac has only USB-C and calber's ports are USB-A, so the stick went into calber, and everything after was done there. A careful check found it first. calber's six SATA SSDs, `sda` to `sdf`, hold an unmounted btrfs raid10 array, and nothing may write to them. The stick was the 7.5 GB "UDisk" at `/dev/sdh`, removable, on USB. It was already FAT32 on an MBR table, so nothing was erased:
- the image was copied to its top level and its hash checked there;
- at Paul's asking, the music already on the stick (MIDI style folders and macOS's hidden `._*`, `.fseventsd` and `.Spotlight-V100`) was moved into `MUSIC/`, leaving the image alone at the top.

**The first time, Q-Flash did not list the stick.** It listed two other disks: the FAT32 EFI partitions of the two NVMe drives. So the image was copied to the top of both, hash checked, with `sudo cp`:
- `nvme1n1p1`, the EX950 boot drive's, mounted at `/boot/efi`;
- `nvme0n1p1`, the EX900's, which also holds another system's Limine boot loader.

**The second time, the stick was listed,** and Paul flashed from it. Why it was missing the first time is not known. **Q-Flash reads a FAT32 EFI partition as readily as a stick**: a fallback worth remembering when a stick does not show. The copies stay where they are (Paul: "no cleanup needed"). A file at the top of an EFI partition does not affect booting.

### C. After the flash

Paul set XMP Profile 1 and the boot order (ubuntu on the 2 TB drive first). After a check from Linux showed CSM was still on, he went back and set:
- CSM Support **Disabled**;
- Full Screen LOGO Show off;
- AC BACK;
- Network Stack (PXE) off;
- a settings profile saved as "F15".

Each claim in Section IV was then read from calber over SSH, without root, or from Paul's `sudo dmidecode`.

## IV. Results

| | F15a, before | F15, after | Read from |
| --- | --- | --- | --- |
| BIOS | F15a 11/28/2019 | **F15 11/13/2021** (built two weeks before Gigabyte posted it) | kernel `DMI:` line, `/sys/class/dmi/id` |
| Microcode inside the BIOS | 0xCA | 0xEA | dmidecode type 221; kernel "Updated early from" |
| Microcode running | 0x104 | 0x104 (Ubuntu's `intel-microcode`, loaded over the BIOS's) | `/proc/cpuinfo` |
| **Intel ME firmware** | 11.8.70.3626 | **11.8.81.3807** | `/sys/class/mei/mei0/fw_ver`; dmidecode type 221 |
| Memory | 3200 MT/s, triad 27,686 MB/s, 61.5 ns | 3200 MT/s, **triad 27,714 MB/s, 58.7 ns** | dmidecode; `ram-bench`'s programs |
| Boot entries | 10, among them old named entries (Windows, Qubes, debian, endeavouros, XCP-ng, Commodore) and, with CSM on, legacy entries for every disk | **2**: `ubuntu` (current, first) and the EX900's `UEFI OS` | `efibootmgr` |
| CSM | on (the legacy MP table in the kernel log) | **off** (no MP table) | kernel log |
| Firmware TPM | on | on (F15's default; fwupd lists it, 303.12.0.0) | ACPI TPM2 table; fwupd |
| Secure Boot | off | off, and in **Setup Mode with no keys**: no PK, KEK, db or dbx | `mokutil --sb-state`; efivars |
| Errors this boot | none of note | none (only the usual "SGX disabled" notice) | `journalctl -p err` |
| Hardware | | six SATA SSDs, both NVMe, network up, GPU at PCIe gen 3 ×16, no GPU errors | `lsblk`, `ip`, `nvidia-smi`, kernel log |

The flash wiped the boot list of its old entries, and turning CSM off removed the legacy ones: the two changes are separate. In dmidecode, the board's version string changed from `x.x` to `Default string`, so the PCB revision still has to be read off the board.

**Not measured yet:** how long a normal boot spends in firmware. The first boot after the flash read 2 min 40 s, and the one after the CSM change 8 min 4 s, each including Paul's time in setup. Before the power cut, with CSM off, it was 11.8 s. After the clear, with CSM on, 31.6 s.

## V. Nothing Left to Update

| What | Now | Updates |
| --- | --- | --- |
| BIOS | F15, Gigabyte's newest | none. Gigabyte does not publish to fwupd: future BIOSes come through Q-Flash |
| Intel ME | 11.8.81.3807 | none needed; it came with F15 |
| CPU microcode | 0x104 | `intel-microcode` is current |
| Kernel | 7.0.0-42 | current |
| Ubuntu packages | | none. Paul applied the one waiting (`libsqlite3-0` 2.8 → 2.9) at 11:36 |
| NVMe drives (EX900 R0802E0, EX950 42A0S63C), six SATA SSDs (SBFM61.2), TPM | | none: `fwupdmgr get-updates` and `sudo fwupdtool get-updates` both say so |
| UEFI dbx | none: Secure Boot has no keys | moot while Secure Boot is off |
| NVIDIA driver | 580.178.04 | held on purpose for the Pascal card |

`sudo fwupdtool get-updates` printed three warnings, all harmless:
- **The capsule plugin "failed to get screen size"** because the NVIDIA driver provides no `/dev/dri/card0`. It wants the size only to draw a picture during a capsule update.
- **`/dev/sdg`, "No medium found",** twice: the empty USB card reader.

**If Secure Boot is ever wanted:** install the factory default keys in the BIOS first. Then `sudo fwupdmgr refresh --force && sudo fwupdmgr update` brings the revocation list up to date.

**Routine checks, as admin:**

    sudo fwupdmgr refresh --force
    fwupdmgr get-updates
    sudo apt update && sudo apt upgrade

`sudo fwupdmgr update` only when `get-updates` lists something.

## VI. CSM, and Why It Is Off

The Compatibility Support Module makes UEFI firmware act as an old PC BIOS. It is there for things made before UEFI:
- **video cards with only a legacy video BIOS** (roughly those from before 2012). With CSM off, such a card shows nothing until the operating system's driver loads;
- **disk and network controllers whose boot code is legacy only**;
- **old operating systems and DOS tools**, such as the `Efiflash.exe` in Gigabyte's own zip.

calber needs none of it. Ubuntu boots the UEFI way (`\EFI\UBUNTU\SHIMX64.EFI`). The 1080 Ti carries a UEFI graphics driver (GOP), as every GeForce 10-series card does. And CSM was off before the power cut, with nothing missing.

Leaving it on cost four things:
- **time**: 11.8 s of firmware before the cut against 31.6 s after the clear turned it on;
- **a boot list** padded with a legacy entry for every disk;
- **more startup code to stall in**, which is how the power cut's hang happened;
- **Secure Boot and Resizable BAR are blocked**, though calber uses neither.

Paul: "alright you convinced me."

## VII. Discussion

1. **Read a vendor's list by its dates, and check which line a note belongs to.** Both of Gigabyte's habits, notes above versions and lettered betas that sort after their release, point the eye the wrong way. The safe readings are the date and the vendor's own remark that there is no way back.
2. **Take the file from the vendor's server and record its hash.** The page refused a script while the file server answered. The size and the date on the page confirm the file. The hash proves that the stick, the two EFI partitions and the download all held the same bytes.
3. **A BIOS flash is a reset of everything kept in NVRAM:** the settings (XMP included), the boot list, and here the Secure Boot keys too. The settings were set again by hand and saved as a profile, "F15". The boot list rebuilt itself from the drives. Nothing used the keys.
4. **The ME came inside the BIOS.** The third-party list's separate ME 12 file was, as far as I know, for Z390-class chips. Following it would have meant flashing the wrong ME for this chipset. Reading the version before and after (`/sys/class/mei`) settled that no separate update was needed.
5. **Q-Flash can read a FAT32 EFI partition** when it does not see a stick.

## VIII. What Is Left

- [ ] An unattended reboot (`sudo reboot`, calber is out of the queue), then `systemd-analyze`: the firmware time with CSM off on F15, expected near 12 s.
- [ ] Add calber back to the queue in Orrery. Its island resumes at generation 282,500. Then `tools/job-speed.py` after a day, for the memory report.
- [ ] Optional: the thermal log (`sh tools/thermal-log.sh calber install`), for the liquid loop's heat soak.

## IX. Limitations

- Why Q-Flash missed the stick the first time is unknown. It may have been the port or the timing.
- AC BACK, the logo and PXE cannot be read from Linux. That they are set is Paul's report.
- Gigabyte publishes one paragraph of notes for F15. What else changed inside it beyond the microcode and the ME is not known.
- The ME reading is a version number. Which advisories 11.8.81 closes is not checked here.

## References

[1] Gigabyte, "Z370 AORUS GAMING WIFI (Rev. 1.0), Support, BIOS" (F1 to F15). [Online]. Available: https://www.gigabyte.com/Motherboard/Z370-AORUS-GAMING-WIFI-rev-10/support#Support-Bios

[2] Gigabyte, F15 BIOS archive. [Online]. Available: https://download.gigabyte.com/FileList/BIOS/mb_bios_z370-aorus-gaming-wifi_f15.zip

[3] Station-Drivers, "Z370 AORUS GAMING WIFI" (a third-party copy of Gigabyte's list). [Online]. Available: https://www.station-drivers.com/index.php/en/bios-news/13-gigabyte-bios-drivers/234-intel-z370-serie-300/1975-z370-aorus-gaming-wifi
