# calber's Recovery: Clearing CMOS on a Gigabyte Z370 AORUS, Putting the BIOS Back, and the Checks After a Power Cut

*Paul Richeson (@Micro) · Lab Report — IEEE Format · 7 November 2026*

Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery.

Companions: `docs/calber-power-cut-lab-report.md` (what calber was doing when the power went, and where the fleet picked up again), which comes before this one; `docs/jaguaribe-clock-lab-report.md` (another machine's power loss, a dead clock battery); `docs/x8dt3-lab-report.md` (a Supermicro's jumpers and BIOS).

---

## Abstract

calber lost mains power in the middle of a full-load CUDA run. Afterwards it hung at the AMI boot banner ("Press <DEL> to enter setup" / "Entering Setup..."). Shorting the CLR_CMOS jumper fixed it: the board power-cycled about three times, which is normal memory retraining after a clear, and booted. This report is the guide Paul worked from: the clear, the Gigabyte hotkeys, the settings to put back, re-adding hardware one piece at a time, the checks to run in Ubuntu, the BIOS version, and how to prevent a repeat.

It has been checked against calber's own logs, read over SSH after the repair. Where the machine differs from the general guide, the difference is noted in place and listed in Section XII. Three of those differences change advice. The card Paul pulled is not an LSI SAS HBA but a two-port JMicron SATA card carrying only a DVD writer. The i7-9700F has no integrated graphics. And on this board the clear kept the clock and the boot entries, but turned off the firmware TPM and SGX and probably turned CSM on.

XMP is off. The four 16 GB sticks are sold as DDR4-3200 and run at 2400 MT/s and 1.2 V. That is below even the 2666 Intel rates the processor for. Section V gives the steps to consider, in order of risk. What is still to be done at the machine, from a shell and by decision is kept as one checklist in `docs/calber-todo.md`. The jobs the fleet has already run say memory speed is not what limits calber, so whatever change is made is measured with those same jobs, not with a separate benchmark.

## I. What Happened

calber lost mains power in the middle of a full-load CUDA run, at about 07:27 PST on 7 November. It then hung at the AMI boot banner. Shorting the CLR_CMOS jumper fixed it. The board power-cycled about three times, which is normal memory retraining after a clear, and booted. It was back in the fleet at 08:36. The SAS HBA (in fact a SATA card, Section VI) stays out for now.

Several things pointed to a stale-configuration hang rather than dead hardware:

- NumLock toggled, and DEL and Ctrl+Alt+Del were acted on, so the firmware was alive and polling USB, not crashed.
- Memory training completed and the banner was drawn, so RAM was not the cause. Testing with one stick changed nothing.
- Removing the add-in card alone did not help, so it was not one card's option ROM.
- BIOS: AMI Aptio 2.20.1271, dated 11/28/2019, ID 1ATQP151.

**Why a power cut does this.** This is the likely explanation; nothing here proves it. The UEFI keeps per-device state in NVRAM, keyed to PCIe slot paths: option-ROM settings, resource allocations and boot entries. A cut mid-run can leave that state inconsistent with what the devices report at the next POST. The firmware then waits forever on a device in late POST, after the banner but before setup or the boot loader. Clearing CMOS discards the cached state, so everything is enumerated fresh. Moving a GPU to a different slot works for the same reason: a new device path gets a fresh init. That is why "move the 1080 to another slot" is folklore. Pulling all the RAM sticks does not do the same job. A no-memory POST only triggers the board's overclock-recovery path, which resets Tweaker clocks and leaves untouched the NVRAM device state that caused this hang.

**On calber, the clear reset some state and kept the rest.** Setup's own choices went back to defaults: the firmware TPM and SGX went off, and CSM probably went on. But the boot entries and the clock survived (Section IV). So the clear certainly reset setup's settings. Whether it also discarded per-device state cannot be seen from Linux.

The machine, as read from Linux on 7 November:

| | |
| --- | --- |
| Board | Gigabyte Z370 AORUS Gaming WIFI (DMI board name `Z370 AORUS Gaming WIFI-CF`); PCB revision not in DMI (`x.x`) |
| BIOS | **F15a**, 11/28/2019 (AMI Aptio, build tag 1ATQP151) |
| Processor | Intel Core i7-9700F, 8 cores, **no integrated graphics** |
| Memory | 4 × 16 GB Team Group DDR4 (`TEAMGROUP-UD4-3200`), single rank, all four slots; **2400 MT/s at 1.2 V, XMP off** (`dmidecode -t 17`) |
| GPU | NVIDIA GeForce GTX 1080 Ti (Pascal), PCIe gen 3 ×16, driver 580.178.04 |
| Boot drive | HP EX950 2 TB NVMe: the EFI partition and ext4 root |
| Other drives | HP EX900 1 TB NVMe (LUKS, not opened at boot); six 480 GB SATA SSDs on the onboard ports (btrfs `raid10-array`, not mounted) |
| Network | Intel I219-V gigabit (`eno1`); Intel Wireless 3165 |
| The card pulled | JMicron JMB58x SATA AHCI (PCI 197b:0585), 2 ports, one HL-DT-ST GH24NS95 DVD writer |

## II. Clearing CMOS on a Gigabyte Aorus Board

The jumper is the method that worked and the one to use first. Gigabyte labels it CLR_CMOS and uses a bare 2-pin header, usually with no cap on it. It is usually near the bottom edge of the board, close to the front-panel header and the coin battery.

1. PSU rocker switch to O, pull the mains cord, hold the case power button for 20 seconds.
2. Touch bare chassis metal to discharge yourself.
3. Touch a flat screwdriver tip across both CLR_CMOS pins for 5 to 10 seconds. Do not short anything else nearby: the front-panel header is a 9-pin block, and the CMOS jumper stands alone as 2 pins.
4. Plug in, PSU switch to I, power on. Expect the board to cycle on and off two or three times (memory retraining), then show the banner or drop straight into setup.

Alternatives if the jumper is awkward to reach:

- **Rear-panel CLR CMOS button:** higher-end Aorus boards (Master, Xtreme, some Ultra) have one next to the Q-Flash Plus button. Same procedure: hold it 5 seconds with the PSU unplugged.
- **Battery pull:** pop the CR2032 (push the metal tab sideways), hold the power button 10 seconds, wait a full 10 minutes, and reinsert it with + facing up. One minute is not reliably enough on Gigabyte boards.
- **Blind reset from inside setup,** if the firmware responds to keys but the screen is frozen: press DEL, wait 60 seconds, then F7, Enter, F10, Enter. That is Load Optimized Defaults, confirm, Save & Exit, confirm. A reboot means it worked.

After any of these the BIOS is at factory defaults, and the settings in Section IV must be put back. The guide expected the date, the time and the boot list to be lost too. On calber they were not.

## III. Gigabyte BIOS Hotkeys

Gigabyte differs from generic AMI on the defaults key (F7, not F9) and on Q-Flash (F8). These keys work on every Aorus UEFI from the Z390/X570/TRX40 generation onward, and calber's Z370 uses the same layout.

| Key | Where | Does |
| --- | --- | --- |
| DEL | At the POST banner | Enter setup |
| F12 | At the POST banner | One-time boot menu (pick a USB installer or another drive) |
| END | At the POST banner | Q-Flash on older boards |
| F2 | In setup | Switch between Easy Mode and Advanced (Classic) Mode |
| F7 | In setup | Load Optimized Defaults |
| F8 | In setup | Q-Flash (BIOS update from USB) |
| F9 | In setup | System information |
| F10 | In setup | Save & Exit (Enter confirms) |
| F11 | In setup | Save or load settings profiles |
| F12 | In setup | Screenshot to a USB stick |
| Esc | In setup | Back, or exit without saving |
| Ctrl+Alt+Del | Anywhere, including a frozen banner | Reset |

The menu paths in this guide are for Advanced Mode (press F2 if setup opens in Easy Mode). The tab names on Gigabyte are Favorites, Tweaker, Settings, System Info, Boot, and Save & Exit.

## IV. Reconfiguring the BIOS After a Clear

Put these back in the order listed, save with F10, and boot Ubuntu once before enabling XMP. Paths are for Advanced Mode. The exact wording shifts slightly between Intel and AMD Aorus boards, so take the nearest match; calber's board is Intel. The last column is what calber's logs show now, read from Linux after the clear.

| Setting | Path | Set to | Why | calber now |
| --- | --- | --- | --- | --- |
| Date and time | System Info | Current | A wrong clock breaks TLS, apt and log timestamps | **Kept** by the clear; the chip read the right time on the first boot |
| Fast Boot | Boot → Fast Boot | Disabled | Keeps the USB keyboard live at POST, so DEL always works | Not visible from Linux |
| CSM Support | Boot → CSM Support | Disabled | Pure UEFI boot for Ubuntu; needed for Resizable BAR | **Probably Enabled** (Gigabyte's default): a legacy MP table appears now and did not before the cut |
| Secure Boot | Boot → Secure Boot | Disabled unless you had it on | Avoids NVIDIA DKMS module-signing problems | Disabled, as it was before |
| SATA mode | Settings → IO Ports → SATA And RST Configuration (Intel) | AHCI | The clear may reset it; RAID mode hides drives from Ubuntu | AHCI: all six SSDs link at 6 Gbps |
| Above 4G Decoding | Settings → IO Ports | Enabled | Needed for compute GPUs with large BARs | Optional on calber: the 1080 Ti's BAR1 is 256 MiB, and there is no SAS HBA |
| Re-Size BAR Support | Settings → IO Ports | Auto | Faster GPU memory mapping; needs Above 4G on and CSM off | **Does not apply**: Pascal cards cannot use it, and a 2019 Z370 BIOS probably lacks the option |
| Initial Display Output | Settings → IO Ports | The slot the display GPU is in | Stops the firmware picking the wrong card | The 1080 Ti is the only display device (the 9700F has no integrated graphics) |
| Intel Platform Trust Technology (PTT) | Settings → Miscellaneous | Enabled, if wanted | The firmware TPM | **Was on, now off.** Nothing on calber uses it now |
| Software Guard Extensions (SGX) | Settings → Miscellaneous | Software Controlled, if wanted | Enclaves; nothing in the fleet uses them | **Was on, now off** |
| AC BACK | Settings → Platform Power | Always On (or Memory) | What the box does after the next power cut (Section X) | Not visible from Linux |
| ErP | Settings → Platform Power | Disabled | Keeps Wake-on-LAN and USB standby power working | Not visible from Linux |
| Fan curves | Settings → Smart Fan 5 or 6 | Your profile | The defaults are quiet-biased, not compute-biased | GPU at 59 °C under the island's load |
| Boot Option #1 | Boot | ubuntu on the boot drive | NVRAM entries may be wiped by a clear (note below) | **Kept**: `Boot0007* Ubuntu` is current and first |
| XMP | Tweaker → Extreme Memory Profile (X.M.P.) | Profile 1, last | Only after one clean boot at stock speed | **Off**: 2400 MT/s at 1.2 V on sticks sold as 3200. Section V weighs the choices |

**Boot entries.** After a clear the UEFI boot list can be empty. The board then falls back to `\EFI\BOOT\BOOTX64.EFI`, which Ubuntu installs by default, so it normally boots anyway. If it lands on a "no boot device" screen or in the Gigabyte setup, press F12 and pick the boot drive's UEFI entry. Then, from Ubuntu, run `sudo grub-install` to recreate the ubuntu entry, and check it with `efibootmgr -v`. On calber none of this was needed: the list kept Ubuntu and six old entries from other systems (Windows, Qubes, debian, endeavouros, XCP-ng, Commodore OS Vision), which can be removed with `efibootmgr -b NNNN -B` if they are not wanted.

**Save a profile once everything is right.** Press F11 and choose Save Profile, and export it to a USB stick too. Next time a clear is needed, F11 → Load Profile restores all of this in one step.

## V. XMP on calber: the Memory, What the Jobs Already Say, and Steps to Consider

### A. The memory

Paul read it with `sudo dmidecode` at about 09:20 on 7 November:

| | |
| --- | --- |
| Sticks | 4 × 16 GB DDR4, Team Group (maker code 04EF), part string `TEAMGROUP-UD4-3200`, **single rank**, in ChannelA-DIMM0/1 and ChannelB-DIMM0/1 |
| Running at | **2400 MT/s, 1.2 V**, all four |
| The sticks' standard (JEDEC) speed | 2400 MT/s (dmidecode's "Speed") |
| Sold as | 3200, which on these sticks is their XMP profile |
| Rated for the processor | DDR4-2666 (Intel's figure for the i7-9700F) |

**XMP is off, and the board runs the sticks at their own standard profile, 2400.** That is below even what Intel rates the processor for. Team writes the same part string on more than one 3200 kit, so the profile's exact timings and voltage are not in dmidecode. They are on the BIOS's X.M.P. screen, and should be noted here when read. Whether XMP was on before the clear cannot be read now.

The layout is a fair case for faster memory. The sticks are single rank, so each channel carries two ranks, a lighter load on the memory controller than four dual-rank sticks.

### B. What the jobs already done say

Before anything is changed, the fleet's own computations can answer one question without a benchmark: **has calber slowed since the clear, at 2400?** Every census and weights job records its seeds and its seconds. Taking 900-second games only, the seconds per seed on each machine, 24 hours before the cut against 08:36 to 09:28 after:

| Machine | Before (jobs) | After (jobs) | After ÷ before |
| --- | --- | --- | --- |
| **calber** | 4.24 (422) | 3.65 (16) | **0.862** |
| calber, the same build (`fd7b36d`) only | 4.52 (135) | 3.65 (16) | 0.81 |
| boburner | 2.90 (562) | 3.04 (17) | 1.047 |
| saskatchewan | 1.99 (719) | 2.08 (31) | 1.047 |
| columbia | 6.47 (265) | 6.74 (10) | 1.041 |
| macmini | 1.46 (1,058) | 1.48 (36) | 1.009 |
| bosporus, jaguaribe, whitewolf | — | — | 1.08, 1.11, 1.10 |

Over the same hour the rest of the fleet slowed by a median of 4.7%, because of the job mix. calber got faster: 0.82 of its old time relative to the fleet. Nothing in the queue changed for it (the same `nice`, no CPU limit, CPU busy 0.76 of the time before and 0.81 after). The cause is not known. The likeliest candidates are the defaults' unlimited CPU power limit (4,090 W in RAPL now) and the new kernel. Sixteen jobs is a small sample, and a day of jobs will settle it.

**What it means for XMP.** At 2400 calber does the fleet's work no slower than it did before the cut. Either the memory ran at 2400 before as well, or these jobs hardly feel memory speed, and the jobs cannot tell the two apart. Either way, memory speed is not what limits calber's census. **Expect XMP to gain little, and measure the gain rather than assume it.**

### C. The choices, least risk first

| Choice | Setting | Speed | Risk |
| --- | --- | --- | --- |
| 1. Leave it | XMP Disabled, multiplier Auto | 2400 at 1.2 V | None; what runs now |
| 2. **The processor's rated speed** | XMP Disabled, System Memory Multiplier **26.66**, timings Auto | 2666 at 1.2 V | Small: within Intel's rating for the CPU, and well below the sticks' |
| 3. One step under the profile | XMP Profile 1, then the multiplier lowered to 30.00 (or 29.33) | 3000 (or 2933) at the profile's voltage | Moderate: an overclock of the memory controller, with margin |
| 4. The full profile | XMP Profile 1 | 3200 at the profile's voltage (typically 1.35 V) | The highest: the sticks' rating, above the CPU's |

**For a machine that runs unattended around the clock, choice 2 is the one to try first.** It takes a third of the step to 3200, and stays within the processor's rating. Go further only if its measurement (step 7) shows the memory matters.

### D. Steps to consider in the BIOS

1. **Pause calber in the queue first**, and wait until both of its lanes are idle. The island segment then finishes and saves, and the reboot loses nothing.
2. **Make the other settings in Section IV first** (CSM, AC BACK, the logo, PXE). Then press **F11 → Save Profile** and name it "stock". If the memory will not train at the new speed, the board power-cycles and comes back at factory defaults, and this profile puts everything else back in one step.
3. **Tweaker tab.** For choice 2, leave Extreme Memory Profile (X.M.P.) Disabled and set System Memory Multiplier to 26.66. For choices 3 and 4, set Extreme Memory Profile (X.M.P.) to Profile1. **Note the speed, timings and voltage the profile screen shows, for Section V.A.** For choice 3, then lower the System Memory Multiplier one step and keep the profile's timings and voltage.
4. **Leave the rest on Auto.** Leave Memory Enhancement Settings at Normal. Raise no voltage by hand: a profile that needs more than its own voltage is the wrong profile for this machine.
5. **Save with F10 and expect a longer first POST** while the memory trains. If the board cycles three times and comes back at defaults, the speed did not train. Load "stock" with F11, and take the next choice down.
6. **In Ubuntu, confirm it took:** `sudo dmidecode -t 17 | grep -E "Configured (Memory Speed|Voltage)"` should read the new speed on all four sticks.
7. **Measure it with the fleet's own jobs, not a benchmark.** Resume calber and let it work a day. Then compare its seconds per seed on the same build against the fleet's median change, as in the table in V.B. If calber's figure does not move by more than the job mix moves the others (a few percent), the faster memory is not worth its risk on this machine. Stay at, or go back to, the choice below it.
8. **A memory check before trusting choices 3 or 4.** The fleet's jobs do not test memory. A flipped bit changes a census result, or an island's state, silently and does not crash. Run `stress-ng --vm 4 --vm-bytes 75% --vm-method all --verify -t 1h` with calber still paused, or MemTest86 from a USB stick overnight, when Paul chooses. Choice 2 is within the processor's rating and can rely on the measurement alone.
9. **Save the result as a profile** (F11), and export it to the USB stick. A future CMOS clear sets the memory back to 2400.

If calber ever fails a job with an unfamiliar error, crashes, or writes an island state the next segment refuses, undo the memory change first.

### E. Measured: 2400 against 3200

Paul set 3200 MT/s on 7 November at about 11:00, and dmidecode confirms it on all four sticks. Both runs used `tools/ram-bench.sh` with calber out of the queue and idle, on the same frozen inputs, a few minutes from cold (`docs/calber-ram/`):

| Measure | 2400 MT/s | 3200 MT/s | Change |
| --- | --- | --- | --- |
| Bandwidth, all 8 cores (triad) | 22,284 MB/s | 27,686 MB/s | +24% |
| Bandwidth, one core (triad) | 20,291 MB/s | 24,436 MB/s | +20% |
| Latency, one load over 512 MiB | 69.6 ns | 61.5 ns | 12% quicker |
| Census, 16 seeds on 8 cores | 72.2, 71.8, 72.1 s | 71.2, 71.4, 71.1 s | 1.1% faster |
| Census, 2 seeds on one core | 16.1, 16.2 s | 16.0, 16.0 s | 0.9% faster |

**The memory got a quarter faster, and calber's own work about one percent faster.** The census runs agree to within half a second, and every run of each size produced the same pooled result, so the 0.8 s is real and the games are identical. It is also small: the census lives in the processor's caches, as the jobs already done had suggested (V.B). The clocks were 4.5 GHz under load in both. The fleet's day of jobs is still to be read (`tools/job-speed.py`).

XMP Profile 1 set the speed and the DRAM voltage, 1.35 V, by itself. Paul: "it went 1.35 the profile 1 set everything perfect." dmidecode still reports 1.2 V: SMBIOS gives the sticks' standard rating, not the live voltage, so the BIOS screen is the place to read it. One thing is open before 3200 is trusted: only about two minutes of `stress-ng --verify` ran at 3200 (both passed), against the hour asked for. The general procedure and the quick guide are in `docs/ram-speed-lab-report.md`.

A one-percent gain does not pay for silent errors, so 2666 at 1.2 V stays the fallback if the hour does not pass.

## VI. Re-adding Hardware One Piece at a Time

Add one thing per boot, and get all the way into Ubuntu each time. If a step brings the hang back, that part is the one with the problem, and a second CMOS clear with it removed gets you going again.

calber's journal shows this order was followed. The first boot after the clear, at 08:28, had no SATA drive linked and no network carrier. It was shut down cleanly at 08:30. The boot at 08:35 had everything but the card.

1. **RAM:** all sticks back in the slots the manual pairs (on Gigabyte four-slot boards, A2/B2 first, then A1/B1). Boot at stock speed, and enable XMP only after this boot is clean.
2. **Ethernet cable.** The onboard NIC's PXE ROM is a known source of silent hangs after a power cut, so boot once with it plugged in before adding anything else. If PXE boot is never used, set Boot → Network Stack to Disabled: POST gets faster and one hang source goes away.
3. **The six onboard SATA ports.** Watch the first POST. If the banner stalls for more than 30 seconds, one drive is still in firmware recovery. Pull drives one at a time to find it, then leave that drive powered on its own for 30 to 60 minutes before giving up on it. On calber all six linked at 6 Gbps on the first full boot.
4. **GPU:** already in. If it ever hangs again at the banner with a frozen screen, move it to the other x16 slot before clearing CMOS; that alone often fixes it.
5. **The add-in card, last,** and only after two clean boots without it.

**On calber the card is not a SAS HBA.** In every boot before the cut, the kernel listed it as a JMicron SATA AHCI controller, PCI 197b:0585, at bus 04, with 2 of 5 ports implemented. Its only device was an HL-DT-ST GH24NS95 DVD writer, at 1.5 Gbps. No data drive was on it. The six SSDs are on the board's own ports. So the HBA steps the guide first gave do not apply: there is no SAS3/MPT configuration page, no `mpt3sas` driver and no Boot Support setting. Linux drives the card with its ordinary `ahci` driver. The card is needed only for the DVD writer, so it can stay out. If it goes back:

- Put it back as the last step, and boot twice cleanly first.
- If the hang returns with it in, the card's option ROM is the suspect. A JMicron card's legacy ROM runs only with CSM enabled, so set CSM Support to Disabled (Section IV) before trying again.
- Or give the DVD writer a USB enclosure instead, and leave the slot empty.

The HBA advice, kept for a machine that does have one: seat it in a CPU-attached slot if possible, and confirm Above 4G Decoding is still Enabled. On the first POST, press DEL and look for the HBA's own configuration page under the Settings or Advanced tab; an LSI/Broadcom card in IT mode shows as a SAS3/MPT controller. If the page is there, the UEFI driver loaded. In that page, set Boot Support to "OS only" (or Disabled) if nothing boots from the HBA. The card then skips its drive scan at POST, and Linux's `mpt3sas` driver finds the drives anyway; this removes the slowest and most hang-prone step of POST. If the HBA has no UEFI driver and only a legacy ROM, leave CSM Disabled and let Linux handle it. The ROM is only needed to boot from those drives.

After the last step, save a BIOS profile (F11), so the whole configuration can be restored in one step.

## VII. Ubuntu Post-Recovery Checks

The power cut interrupted writes, the clear could have reset the BIOS clock, and the GPU was at full load when the power died. Check all three before putting the box back to work. The last column is calber at about 08:50 on 7 November, read without root.

| Check | Command | Looking for | calber |
| --- | --- | --- | --- |
| Clock synced | `timedatectl` | "System clock synchronized: yes" (the clear can reset the RTC) | **yes**; the RTC was never wrong |
| Boot entry exists | `sudo efibootmgr -v` | An ubuntu entry pointing at `shimx64.efi`; if it is missing, `sudo grub-install` | **yes**: `Boot0007* Ubuntu` on the EX950's EFI partition, current and first |
| What the crashed session saw | `journalctl -b -2 -p err` on calber | Errors from the boot that lost power | **one**, `motd-news` at 04:11; nothing near the cut. On calber that boot is `-b -2`, not `-b -1`, because the two-minute test boot at 08:28 is `-b -1` |
| Filesystem errors this boot | `sudo dmesg \| grep -iE 'ext4\|xfs\|btrfs\|I/O error'` | Nothing; any "recovery" or "error" line means run a full check | **none**. On the first boot fsck found the EFI partition's dirty bit (it was mounted when the power went) and removed it, and the initramfs checked root, which mounted clean |
| Full root fsck (ext4) | At GRUB press `e`, append `fsck.mode=force fsck.repair=yes` to the linux line, F10 | A clean pass; repeat only if it reported fixes | Not run. Optional, given the clean mount |
| Btrfs or ZFS instead | `sudo btrfs scrub start -B /` or `sudo zpool scrub <pool>`, then `zpool status` | 0 errors | Does not apply: the six-SSD btrfs `raid10-array` was not mounted before the cut or since, so the cut could not touch it. All six devices scan at transid 11 |
| NVMe health | `sudo nvme smart-log /dev/nvme0` and `/dev/nvme1` | `unsafe_shutdowns` up by one (expected); `media_errors` 0 | **Not run: needs root** |
| SATA drive health | `sudo smartctl -a /dev/sdX` for each | Reallocated, Pending and Uncorrectable sectors all 0 | **Not run: needs root** |
| GPU alive | `nvidia-smi` | Card listed, idle temperature sane, no "Unknown Error" | **yes**: GTX 1080 Ti, 59 °C, 141 W, P2, PCIe gen 3 ×16 |
| GPU faults | `sudo dmesg \| grep -i xid` | No Xid lines after boot | **none**, in this boot or in the one that lost power |
| GPU memory damage | `nvidia-smi -q -d ROW_REMAPPER` (Ampere and later) or `-d PAGE_RETIREMENT` | 0 pending or failed remaps | Does not apply: a GeForce 1080 Ti reports N/A for both |
| Short CUDA load test | Your usual job for 10 minutes, with `nvidia-smi dmon` in another terminal | Stable clocks and power, no throttling, no Xid | **passed**, using the island itself: 49 generations in 13¾ minutes at the normal pace, 142 to 144 W at 100% busy |
| The pending firmware update | `fwupdmgr get-updates` | Which device it is for; note it, do not apply yet | **UEFI dbx** 20230501 → 20260707, urgency High. Secure Boot is off on calber, so the list has no say in how it boots |

`fwupdmgr get-updates` can list several kinds of entry. Each one shows the device, the current and new versions, an Urgency (low to critical), flags such as "needs a reboot", and the vendor's release notes. `fwupdmgr get-devices` shows everything fwupd knows about, and whether each is marked Updatable. Most Ubuntu desktops see exactly one entry, and calber does.

| Listed as | What it is | Applies how | Apply when |
| --- | --- | --- | --- |
| UEFI dbx | The Secure Boot revocation list, which blocks known-bad bootloaders | A UEFI capsule at the next reboot | The usual entry. Low risk, but only after two clean boots; fwupd refuses it if the current shim is on the list |
| System Firmware | The motherboard BIOS | A capsule at reboot | Will not appear here: Gigabyte does not publish to LVFS, so the BIOS updates only through Q-Flash |
| NVMe SSD (Samsung, WD, Crucial, Kingston, Seagate) | The drive controller's firmware | Written live, active after a reboot | Only after SMART is clean and the data are backed up; never on a drive still recovering from the cut. On calber fwupd lists both HP NVMe drives with no update |
| USB receiver or peripheral (Logitech Unifying, Corsair, SteelSeries) | Dongle, keyboard or mouse firmware | Live, no reboot | Any time; unrelated to the hang |
| Thunderbolt, USB hub, NIC (Intel, Realtek, VIA) | Controller firmware | Live or at reboot | Only when the release notes name a bug you have |
| GPU | Not offered: NVIDIA ships no LVFS updates, and the VBIOS changes only through the card vendor's tool | n/a | n/a |

CPU microcode is not fwupd's either. It arrives through the `intel-microcode` or `amd64-microcode` package with normal apt updates. calber's i7-9700F is loaded early from 0xca to 0x104 at each boot.

If the tools are missing: `sudo apt install nvme-cli smartmontools`. Resume the CUDA job from its last checkpoint rather than trusting output files written in the final seconds before the cut. On calber that is exactly what happened: the island resumed from the checkpoint of 07:13:00, and the files written in the last half-minute are on the disk at 0 bytes (the companion report, Section III).

## VIII. BIOS Version: Current Versus Newest

Gigabyte numbers its BIOS releases F1, F2, F3 and so on, separately for each board. A trailing letter (F11a, F12e) marks a beta. The AMI banner's `Ver: 1ATQP151` string is a build tag, not the F number, so the comparison has to use the F number from one of these places:

| Where | How | Shows |
| --- | --- | --- |
| BIOS setup | The System Info tab, or F9 anywhere in setup | BIOS Version (the F number) and BIOS Date |
| Ubuntu | `sudo dmidecode -s baseboard-product-name && sudo dmidecode -s bios-version && sudo dmidecode -s bios-release-date`; without root, `cat /sys/class/dmi/id/{board_name,bios_version,bios_date}` | The exact board model, the F number and the date |
| Q-Flash | F8 in setup, then Update BIOS, and pick the file on a FAT32 stick | The current BIOS version and the file's version side by side, before anything is written |
| Gigabyte's support page | gigabyte.com → Support → Motherboard → the exact model → BIOS tab | Every release with its date and notes; the top row is the newest |

**Answered for calber:** the board is the Z370 AORUS Gaming WIFI, and the BIOS is **F15a of 11/28/2019**, read from `/sys/class/dmi/id`. By Gigabyte's own convention the trailing "a" marks F15a a beta. Gigabyte's own page (read by Paul on 7 November) lists two newer releases. F15b (Mar 23, 2021) adds Resizable BAR, of no use to a Pascal card. F15 (Nov 29, 2021) carries "major vulnerabilities updates" and cannot be rolled back. F15 is the one to flash; `docs/ram-speed-lab-report.md` §VI. An earlier third-party index [1] had shown F15a as the last; it was wrong. The BIOS's own CPU microcode is 0xCA (dmidecode's firmware table, type 221). Ubuntu loads 0x104 over it early in every boot, so microcode is no reason to flash. The ME firmware is 11.8.70.3626.

The PCB revision matters: the model line on the board ends in REV: 1.0, 1.1 or 2.0, and each revision has its own BIOS list. Pick the page that matches, or the file will refuse to flash; a user on the sister Gaming 7 board reports exactly that refusal ("BIOS ID check error") from Q-Flash [2]. Some boards also have a note saying an older BIOS must step through an intermediate version before the newest. Read the top of the list before flashing. **calber's revision is not in DMI** (`x.x`); it must be read off the board.

What to do with the comparison: if the newest is only one or two releases ahead and the notes are about CPU support you do not need, stay put. Update when the notes mention memory compatibility, PCIe stability, AGESA or microcode, or a security fix, and then only with the box on a UPS.

## IX. Where the Island's Checkpoint Stands

This is not a BIOS matter, but it decides what the next cut costs. crucible writes the island's checkpoint, `island.state`, in place every 32 minutes, with no temporary file and no `fsync`. A cut in the half-minute before those 141.7 MB reach the disk would leave a file the next segment refuses, and the population, about 14 hours of the card's work, exists nowhere else. The companion report (Findings 7, What Needs a Person 1) proposes the atomic save. It has not been built.

## X. Preventing a Repeat

A UPS is the real fix. The rest limits the damage when the next cut happens anyway.

- **UPS:** a line-interactive, pure-sine-wave unit rated above the box's full-load draw. A compute GPU plus a CPU is typically 500 to 900 W at the wall, so a 1500 VA / 900 W class unit gives a few minutes. Install nut or apcupsd, so that Ubuntu shuts down cleanly on battery instead of running until the UPS dies. calber's own share is smaller, with its GPU drawing about 140 W under the island, so the same unit lasts longer.
- **AC BACK** (Settings → Platform Power) decides what the board does when power returns. Always On brings the box back unattended, which is right for a compute node on a UPS. Without a UPS, Always Off is safer: flickering mains would otherwise power-cycle the box repeatedly, and that is exactly what corrupts NVRAM state. The cost of Always Off is that calber then waits for a person after every cut. jaguaribe's report argues the other way for that machine.
- **Checkpoint the CUDA job every few minutes,** so that a cut costs minutes, not hours. calber's island checkpoints every segment, 32 minutes, and lost about 14 minutes. The weak point is the save itself (Section IX).
- **Firmware:** the running BIOS is from 11/28/2019. Once the box is stable and on a UPS, update it with Q-Flash (F8 in setup, the file on a FAT32 USB stick) from Gigabyte's page for the exact board model and revision. Then redo the settings table, because profiles saved under one BIOS version usually will not load under another. Apply the fwupd update the same way, after confirming which device it targets; on calber that is the dbx.
- **Q-Flash Plus,** if the board has the button on the rear panel, reflashes the BIOS with no CPU or RAM installed. It is the recovery route if a cut ever lands during a BIOS write.
- **Mark the CLR_CMOS header** with a strip of tape, so it can be found with the GPU in. Keep the saved BIOS profile on a USB stick taped inside the case.

## XI. Troubleshooting Ladder if It Hangs Again

Work down the list. Each rung is cheaper and more reversible than the next, and each one also tells you something. Stop at the first rung that gets you into setup or Ubuntu.

1. **Is the firmware alive?** Press NumLock a few times. If the LED toggles, it is waiting on a device or the display is frozen: go to 2. If the LED is frozen, it is a hard hang: go to 4.
2. **Is it already past the banner?** Do not press DEL. Wait 5 minutes, then ping or SSH it and watch the NIC LEDs. If it is reachable, the GPU froze the display: go to 6. If not, go to 3. The fleet's own view helps here too: the keeper's "host back" line, or calber's lanes on the Timeline, say within seconds whether Ubuntu came up.
3. **Blind defaults:** DEL, wait 60 seconds, F7, Enter, F10, Enter. If it reboots, that is done: redo the settings table. If nothing happens, go to 4.
4. **Clear CMOS with the CLR_CMOS jumper** (PSU unplugged, power button held, 10-second short). If it boots, redo the settings table. If it still hangs, go to 5.
5. **Unplug everything but the keyboard:** every other USB device, the Ethernet cable, and every SATA and NVMe drive. If it boots, reconnect one per boot to find the culprit. If it still hangs, go to 6.
6. **Pull the GPU and move it to the other x16 slot;** move the monitor to a different output and cable. On calber, booting with no card is not a picture test: the i7-9700F has no integrated graphics, so with the card out the screen stays dark even on a good POST. Listen for the POST beep, or watch the board's status LEDs. If it boots, the card or the slot is the problem. If it still hangs, go to 7.
7. **One RAM stick in A2,** then the other stick, then the other slot. If it boots, a stick or a slot is bad. If it still hangs, go to 8.
8. **Battery out for 10 minutes** with the PSU unplugged, then a Q-Flash Plus reflash of the BIOS if the board has it. If it still hangs with the GPU out, one stick in and no drives, the board or the PSU took the hit.

## XII. Where This Report Departs from the Guide as First Written

Each change rests on calber's logs of 7 November. The guide's general advice is kept wherever it still holds.

1. **The card is a JMicron SATA card with a DVD writer, not an LSI SAS HBA** (Section VI). Kernel log, every boot before the cut: `pci 0000:04:00.0: [197b:0585] ... class 0x010601`, "2/5 ports implemented", `ata7.00: ATAPI: HL-DT-ST DVDRAM GH24NS95`. The SAS3/MPT page, `mpt3sas` and Boot Support do not apply to it.
2. **The i7-9700F has no integrated graphics** (Sections IV and XI). The ladder's "boot with no card" gives no picture on calber.
3. **The clear kept the clock** (Sections II and IV). The first boot after it logged `PM: RTC time: 16:28:28, date: 2026-11-07`, which was correct.
4. **The clear kept the boot entries** (Section IV). `efibootmgr` still lists `Boot0007* Ubuntu` first, with six older entries.
5. **Settings the guide's table did not name were reset:** Intel PTT (TPM2 table before, "No TPM chip found" now) and SGX (on before, "disabled or unsupported by BIOS" now). CSM probably went from off to on: a legacy MP table appears now and did not before.
6. **Resizable BAR does not apply** to a Pascal card. The 1080 Ti's BAR1 is 256 MiB.
7. **On calber the crashed session is `journalctl -b -2`,** because the short test boot at 08:28 took `-b -1`.
8. **GPU memory remapping checks read N/A** on a GeForce 1080 Ti.
9. **The open question about the model is answered** (Section VIII): Z370 AORUS Gaming WIFI, BIOS F15a, 11/28/2019, Intel. The PCB revision still has to be read off the board.
10. **The pending firmware update is the UEFI dbx,** 20230501 → 20260707, urgency High. Secure Boot is off on calber.
11. **One step of the ladder is renumbered.** Rung 2 sends a machine that answers over the network but shows a frozen screen to rung 6, the GPU rung. The guide first said rung 5, which unplugs drives and USB and does not touch the display.
12. **XMP is a choice of four, not "Profile 1, last"** (Section V). The memory runs at 2400, the jobs already done show calber no slower at that speed, and the processor's rated 2666 at 1.2 V comes before the sticks' 3200 profile.

## References

[1] Softpedia Drivers, "Z370 AORUS Gaming WIFI (rev. 1.0)" BIOS listing, including F15a. [Online]. Available: https://drivers.softpedia.com/downloadTag/Z370%20AORUS%20Gaming%20WIFI%20%28rev.%201.0%29,2

[2] Tom's Hardware forums, "BIOS ID check error" (Q-Flash refusing an F15 file on a Z370 AORUS Gaming 7). [Online]. Available: https://forums.tomshardware.com/threads/bios-id-check-error.3773410
