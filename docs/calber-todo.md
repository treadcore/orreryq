# calber: What Is Left to Do

*Paul Richeson · a to-do from the power cut of 7 November 2026*

Everything here came out of the power cut and its two reports: [`calber-power-cut-lab-report.md`](calber-power-cut-lab-report.md), what happened, and [`calber-bios-recovery-lab-report.md`](calber-bios-recovery-lab-report.md), the repair and the BIOS. Paul (7 November): "add all these considerations in a todo. I can't do them yet."

Each item says where it is argued. Tick an item here when it is done, and say what was found.

---

## Where calber stands now (7 November, 09:45)

- **Out of the queue, on the bench.** Removed at 09:30 from Projects.
- **Its island waits for it.** Segment `x-calber-cuda-3342` was sent back at 09:36, at generation 282,588 of 282,599, before its save. The island's checkpoint is the one saved at 09:07:10, generation 282,500. Segments 3343 to 3347 are kept for it, and health says so ("kept for calber-cuda").
- **To bring it back:** Projects → **Add**. The segments run in order from the checkpoint.
- **To take it out next time without losing a segment:** press **Finish, then out**, not Remove. The machine takes nothing new, the job in hand ends and saves, and then it leaves by itself. This needs Orrery quit and reopened once, for the new buttons.

## 1. At the machine: one BIOS visit

Take calber out with **Finish, then out** first, and wait until it reads "Removed". Then, in the BIOS:

- [ ] **CSM Support → Disabled** (Boot tab). POST has taken 31.6 s since the clear, against 11.8 s on every boot before it. *Recovery report §IV.*
- [ ] **AC BACK** (Settings → Platform Power). The clear probably set it to Always Off, so calber now stays off after a cut until someone presses the button. Choose **Always On**, the fleet's way, or Always Off until there is a UPS. *Recovery report §IV, §X.*
- [ ] **Full Screen LOGO Show → Disabled**, so a hang shows where it stopped.
- [ ] **Network Stack (PXE) → Disabled.** calber never boots from the network.
- [ ] **Smart Fan 5: read the temperature labels.** One sensor reads 85 to 91 °C under load (`gigabyte_wmi` temp5, unlabelled in Linux). If it is "VRM MOS", ramp a system fan on it, or cap CPU power (§3).
- [ ] **Memory, choice 2:** Extreme Memory Profile (X.M.P.) left Disabled, System Memory Multiplier **26.66** (2666 at 1.2 V, the processor's rating). On the X.M.P. screen, **write down the profile's speed, timings and voltage** for §V.A of the recovery report. *Recovery report §V.C, §V.D.*
- [ ] Optional: Wi-Fi, Bluetooth and HD Audio off (all unused). PTT and SGX back on only if something will use them.
- [ ] **F11 → Save Profile ("stock")**, and export it to a USB stick.
- [ ] **Read the PCB revision off the board** ("REV: 1.0", 1.1 or 2.0). It decides which BIOS list on Gigabyte's site applies. *Recovery report §VIII.*
- [ ] Tape a strip beside the CLR_CMOS header, and keep the profile's USB stick taped inside the case.

Then boot, run `sudo dmidecode -t 17 | grep Configured` (it should read 2666 MT/s on all four sticks), and press **Add**.

### Measuring the memory change (started 7 November, about 10:00)

- [x] **Before, on the bench:** `sh tools/ram-bench.sh calber 2400-jedec 3`, run with calber out of the queue and idle. It measures bandwidth, latency, and a frozen census (w13740's trial, 16 seeds on all cores and 2 on one core). Results are in `docs/calber-ram/`. At 2400 MT/s: triad 22,284 MB/s on all cores and 20,291 on one; 69.6 ns a load; the census 72.2, 71.8 and 72.1 s on 8 cores and 16.1 and 16.2 s on one, with equal pooled hashes each time.
- [x] **Before, from the fleet's jobs:** `docs/calber-ram/jobs-2400-jedec.txt`, from `tools/job-speed.py`: 4.24 s a seed before the cut, 3.65 at 2400 since the clear, 0.82 against the fleet.
- [x] **After the BIOS change, before Add (7 November, 11:14):** dmidecode reads 3200 MT/s on all four sticks. `sh tools/ram-bench.sh calber 3200 3`: triad 27,686 MB/s on all cores (+24%) and 24,436 on one (+20%); 61.5 ns a load (12% quicker); the census 71.2 s on 8 cores against 72.0 (1.1% faster) and 16.0 s on one against 16.1. The pooled hashes are equal, so it played the same games. **The memory is a quarter faster, and the census, calber's own work, about 1%.**
- [x] **The DRAM voltage:** 1.35 V. Paul: "it went 1.35 the profile 1 set everything perfect." dmidecode's 1.2 V is the sticks' standard rating, not the live voltage.
- [x] **The stress test at 3200: declined.** Paul, 7 November: "stop the ram check. i don't want an hour long run." What ran: two short `stress-ng --verify` passes (42 s and 1 min), both clean, and five census runs whose pooled results matched 2400's exactly. If calber ever fails a job with an odd error, or an island state is refused, the memory is the first suspect: go back to 2666 at 1.2 V.
- [ ] **After a day back in the queue:** `python3 tools/job-speed.py ~/code/treadcore/build/queue/grove calber 2026-11-07T08:36 2026-11-07T09:31 <Add time>`.
- [x] The comparison and the general procedure: `docs/ram-speed-lab-report.md` (XMP Profile 1, 3200 at 1.35 V; memory +24%, census +1.1%).

## 2. From a shell on calber (needs the password)

- [ ] NVMe health: `sudo nvme smart-log /dev/nvme0 && sudo nvme smart-log /dev/nvme1`. Expect `unsafe_shutdowns` up by one and `media_errors` 0.
- [ ] SATA health: `for d in /dev/sd[a-f]; do sudo smartctl -H -A $d; done`. Expect Reallocated, Pending and Uncorrectable all 0.
- [ ] The CPU's real watts under the census, to choose a power limit (§3):
  `f=/sys/class/powercap/intel-rapl:0/energy_uj; a=$(sudo cat $f); sleep 10; b=$(sudo cat $f); echo $(( (b - a) / 10000000 )) W`
- [ ] Wake-on-LAN: `sudo ethtool eno1 | grep -i wake`.
- [x] `sudo apt upgrade` (Paul, 11:36): `libsqlite3-0` 2.8 → 2.9. Nothing else waits; microcode and kernel are current.
- [x] **The UEFI dbx update is moot.** The F15 flash left Secure Boot in Setup Mode with no keys (no PK, KEK, db or dbx; `mokutil`: "Platform is in Setup Mode"), so fwupd has nothing to update and lists no updates at all. Secure Boot is off, so nothing depends on it. If Secure Boot is ever wanted: in the BIOS, install the factory default keys first, then `sudo fwupdmgr refresh --force && sudo fwupdmgr update`.
- [ ] Optional: the cut's leftovers, thirteen empty files that nothing reads: `rm -r ~/fleet/q-grove/c/fd7b36d/wt/build/census/20261107-152643 ~/fleet/q-grove/trials/e12793.weights`.

## 2b. The six SATA SSDs: the fastest layout for a Blu-ray working disk (started 7 November)

The six 480 GB SSDs (serials 18080648001999 … 18080648003316) hold an unmounted btrfs `raid10-array` today. `tools/disk-bench.py`, copied to `calber:~/fleet/disk-bench/`, finds them by serial and refuses anything else. Its layouts and measures are in its own header.

- [ ] `sudo apt update && sudo apt install -y fio zfsutils-linux` (then `zfs version`: userland 2.2.2 against kernel module 2.4.1; if ZFS refuses, the ZFS layouts fail alone and the rest run).
- [ ] **Look first:** `sudo python3 ~/fleet/disk-bench/disk-bench.py inspect`. It reads SMART for all six and mounts the btrfs read-only, then lists it.
- [ ] **Paul's go to erase `raid10-array`**, after seeing what it holds.
- [ ] **Run:** `sudo systemd-run --unit=disk-bench --collect python3 /home/user/fleet/disk-bench/disk-bench.py run --erase all` (about an hour; it survives the SSH session; watch `tail -f ~/fleet/disk-bench/results/LOG`). Or the pairs first: `… run --erase raw-each pair-zfs pair-btrfs pair-md-ext4`.
- [ ] `python3 ~/fleet/disk-bench/disk-bench.py report`, then a lab report, then build the winner for good, share it (Machines → Storage) and open it in Exchange.
- [ ] A Blu-ray writer needs a SATA port: all six onboard ports hold these SSDs, and the 2-port JMicron card (which carried a DVD writer) is out. Either the card goes back in, or the writer goes on USB.

## 3. Decisions (each waits for Paul's word; none is built)

- [ ] **crucible: save `island.state` atomically.** Write a temporary file, fsync, rename, and keep the previous state as `.prev`. A cut in the half-minute after a save would otherwise lose the island's only copy, about 14 hours of the card's work. *Power-cut report, Finding 7.*
- [ ] **A daily copy of each island's state to the Mac**, so one disk is not the only record.
- [ ] **CPU power limit.** It is unlimited now (4,090 W in RAPL), with all cores at 4.5 GHz. Intel's long-term figure is 65 W, and something like 95 W is a middle ground. Decide after the watts reading in §2.
- [ ] **Memory past choice 2.** XMP one step down (3000), or the full 3200 profile, only if choice 2's measurement shows memory matters. Run a memory test first: an hour of `stress-ng --vm 4 --vm-bytes 75% --vm-method all --verify -t 1h` with calber out of the queue, or MemTest86 overnight. *Recovery report §V.C, step 8.*
- [ ] **Timeline: draw "sent back" apart from "failed"**, and say why in the tooltip ("sent back: host unreachable"), so a power cut no longer reads as a crash. *Power-cut report §V.*
- [ ] **Timeline: the tooltip's clock** keeps the planner's seconds and rounds, so 07:13:08 reads 07:13, not 07:12. *Power-cut report §III.D.*
- [ ] **The keeper: two lanes raising one flag at once.** During the outage, at about 07:28, calber's CPU and GPU lanes raised the same "cannot be reached" flag together. Both wrote the same temporary file in `notice()` (`tools/fleet-queue.py:244`), one rename failed, and that lane's thread died; the keeper started it again at 07:29:31. The fix is a temporary name per writer (its thread). It is one line, but every save of that file restarts the live keeper.
- [ ] **The keeper: a false "heartbeat" alarm.** The planner runs inside the keeper's beat (`plan()`, a `subprocess.run`), so the beat goes quiet for the length of each pass. Health calls a minute's silence BAD "stuck", and seven of today's 440 passes ran over 60 s (58 to 63 s around 09:50). Either run the pass beside the beat, or let health allow for the pass it can see running.
- [x] **BIOS F15, flashed 7 November about 12:05** with Q-Flash from the USB stick (it appeared on the second try; the copies on both EFI partitions were listed too). The kernel reads `BIOS F15 11/13/2021`; the BIOS's own microcode is now 0xEA (it was 0xCA), and Ubuntu still loads 0x104 over it. **The flash also updated the Intel ME firmware, 11.8.70.3626 → 11.8.81.3807**, so no separate ME update is needed. dmidecode (Paul, after the flash) confirms all four sticks at 3200 MT/s. Paul set XMP Profile 1 and the boot order (ubuntu on the 2 TB drive first, `Boot0002`, current). After the flash: triad 27,714 MB/s, 58.7 ns a load, so 3200 holds. The flash cleared the old boot entries (Windows, Qubes and the rest); the firmware TPM is on again (F15's default).
- [x] **Set again after the flash (7 November, about 12:15):** CSM **Disabled**, Full Screen LOGO off, AC BACK, Network Stack off, profile "F15" (Paul: "done"). Read from Linux: no legacy MP table, the boot list down to `ubuntu` (current, first) and the EX900's `UEFI OS`, no errors this boot, all six SSDs, the network and the GPU present.
- [ ] **The startup time of an unattended boot.** That boot spent 8 min 4 s in firmware, which includes the time in setup. After a plain `sudo reboot`, `systemd-analyze` should read about 12 s, as before the cut.
- [x] **The BIOS file copies stay** (Paul: "no cleanup needed"): `Z370AOGW.F15` remains at the top of both EFI partitions, in calber's home folder and on the USB stick. They don't affect booting.

## 4. To buy

- [ ] **A UPS**: line-interactive, pure sine wave, about 900 W class. Install nut or apcupsd, so Ubuntu shuts down cleanly on battery. *Recovery report §X.*

## 5. After the changes (ask Claude)

- [ ] **Measure the memory change with the fleet's own jobs**, not a benchmark: calber's seconds per seed on the same build against the fleet's median change, over a day. The baseline is 4.24 s per seed before the cut. The first 16 jobs at 2400 MT/s since the clear read 0.82 of that, relative to the fleet. *Recovery report §V.B.*
- [ ] Check that health reads clean, and that the island ran 3342 onward from generation 282,500.
- [ ] Update both reports with what the BIOS screens showed (the XMP profile, the temperature labels, the PCB revision) and with what was changed.

## Done on 7 November

- [x] The analysis and the repair, as two lab reports.
- [x] **Remove now stops what runs and puts it back on the queue**, at once. Stop now did this already. The new **Finish, then out** takes nothing new, lets the job in hand end, and then leaves (`tools/fleet-queue.py`: `machine NAME finish`, `leave_when_done`). Remove asks twice while the machine has a job. A pinned job kept for a removed machine reads "kept", not BAD. Proved by `sh tools/fleet-queue-check.sh` (six new claims), `restart-check.sh` and `breaker-check.sh`. The live keeper took the new code at 09:42 and 09:44 with nothing requeued, and Orrery.app was reinstalled.
- [x] Segment 3342 stopped by hand at 09:36 and put back on the queue. calber had been removed under the old Remove, which let the job run on.
- [x] **BIOS F15 and the firmware survey, written up:** `docs/calber-update-f15-lab-report.md`.
- [x] `nvme-cli` and `smartmontools` installed on calber. `dmidecode` read: XMP is off.
