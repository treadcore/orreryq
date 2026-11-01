# A Dead Clock Battery and an Expired Certificate: Why jaguaribe Left the Fleet

*Lab Report — IEEE Format · 1 November 2026*

Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery.

Companions: `tools/orchestrate.py` (the guard); `tools/fleet-queue.py` (the retries);
`docs/copal-machines-lab-report.md` (how jaguaribe joined).

---

## Abstract

jaguaribe, a Supermicro X8DTL with two Xeon X5670s, did no work for 17 hours and 54 minutes
after the fleet's shutdown on 31 October. Paul found a CMOS error at the console and a dead
clock battery. The machine's own log shows it booted believing the date was 16 November 2012,
and that chronyd stepped the clock forward 440,470,337.786 seconds, about 13.96 years, 26
seconds after boot. The date is now correct, and the system clock and the clock chip agree
to the second. It is not fixed for good: the next loss of mains power will reset the chip
again until the battery is replaced.

The logs also settled a second question. The SSH resets seen on all three Copal machines are
not a network fault. orrery's chat room dialled every machine every 4 seconds with an operator
certificate that expired on 30 October. Each refusal cost the Mac's address a penalty in
OpenSSH 10.3, and sshd then dropped connections from that address, the keeper's among them.
The three Ubuntu machines run OpenSSH 9.6, which has no such penalties, and logged none.

## I. Introduction

The fleet's keeper had reported jaguaribe unreachable since 31 October. An earlier reading in
this work described it as dropping off the network repeatedly. That was wrong: there were two
separate faults, and one logging bug that made them look like one.

## II. Method

Everything was read as the ordinary user, with no change to the machine:
`/var/log/messages`, `/sys/class/rtc/rtc0`, `/sys/class/dmi/id`, chrony's configuration, file
times under `/etc` and `~/.fleet-queue`, `/proc/stat`, and the queue's `events.jsonl`. The
other machines' logs and `ssh -V` were read for comparison.

**What could not be read.** `/var/log` on Copal is a tmpfs, so **every log from before this
boot is gone**. `dmesg` and `/var/lib/chrony` need root. A subnet sweep and a look at the
router's leases were refused by this session's permission system and not attempted again.

## III. Results

### A. The clock

| Evidence | Reading |
| --- | --- |
| Board and BIOS | Supermicro X8DTL, BIOS 2.1b, **dated 11/16/2012** |
| First log line this boot | `Nov 16 07:03:59` (2012) |
| chronyd, 07:56:22 | `System clock wrong by 440470337.786110 seconds`, then stepped |
| True boot time (`btime`) | 2026-11-01 07:55:56 PST |
| Chip against system, after | 0 s; `rtcsync` keeps the chip set while the machine runs |
| Time source | `pool.ntp.org`, `makestep 1.0 3` |

The date the clock fell back to is the BIOS's own build date. That is the usual sign of a chip
that lost its contents.

Files under `/etc` carry two wrong dates: 15 November 2012 at 16:46 PST, and 16 November at
07:03 PST. So there were **two boots on the wrong clock**, about 14 h 18 min apart.

### B. A probable timeline

| Real time | Event | Basis |
| --- | --- | --- |
| 31 Oct 14:02 | Last job, `w2224`, starts; its pid file is never removed | measured |
| 31 Oct 14:04 | `shutdown now` for the fleet | measured |
| 31 Oct about 16:52 | Mains back; the chip resets to 16:00 PST on 15 Nov 2012 (midnight UTC) | inferred |
| 31 Oct about 17:38 | A first boot on the wrong clock writes `/etc/hostname` | inferred |
| 1 Nov 07:55:56 | The boot that came back | measured |
| 1 Nov 07:56:22 | chronyd corrects the clock | measured |
| 1 Nov 07:58:01 | Rebuilt on `7a0ca91`, takes a census | measured |

The inferred times count back from the measured boot, and assume the chip ran steadily. saskatchewan
also booted about 16:52, which fits but does not prove it. Why the 17:38 boot never answered the
keeper is unknown: its logs died with it. A BIOS waiting for a key at a CMOS error, which is
what Paul saw, would explain the hours after it. It does not explain that boot itself.

### C. What the wrong clock can break

Between boot and the step, 26 seconds here, `sshd` was already listening and the clock was 14
years behind. Reasoned from how these checks work, and not tested: a certificate is not yet valid
to it, HTTPS fails for `git fetch` and for packages, and a census stamped then sorts as 2012. If
the internet were down at boot all of that would last until it returned. Here it did no harm. Nine
files in `/etc` keep 2012 dates, harmlessly, and the build ran after the step.

### D. The SSH resets

| Machine | OpenSSH | Refused certificates in its log | Penalty drops |
| --- | --- | --- | --- |
| saskatchewan | 10.3p1 | 338 in 29 minutes | 104 |
| columbia | 10.3p1 | 82 in 7 minutes | 26 |
| jaguaribe | 10.3p1 | 24 in 3 minutes | 6 |
| calber, boburner, whitewolf | 9.6p1 | 0 in an hour | 0 |

The log lines are exact:

    error: Refusing certificate ID "user@users-iMac.lan" ... Certificate invalid: expired
    drop connection #0 from [192.168.8.143]:60164 ... penalty: failed authentication

The certificate lasted to 30 October 19:30. Keeper events of "host unreachable", from 29 October
to that time and from then until today:

| Machine | Before | After |
| --- | --- | --- |
| saskatchewan | 2 | 91 |
| columbia | 2 | 34 |
| jaguaribe | 2 | 14 |
| calber | 2 | 1 |
| boburner | 3 | 0 |

The windows are about equal in length, though the fleet was stopped for part of each.

### E. The false "host back"

A lane waiting on a machine logs "host back" whenever the wait ends, including when a keeper
restart ends it. The entries for jaguaribe at 07:12 and 07:16 on 1 November were this: it was
off. The health line "every machine answers" at about 07:13 was probably the same. Not yet mended.

## IV. Changes Made

1. **The date.** Nothing was needed by hand: chronyd had corrected it, and the chip with it.
2. **`tools/orchestrate.py`.** The chat room and the minute's survey no longer dial on an expired certificate.
   Measured: with the chat room's guard in at about 07:59, penalty drops stopped on all three machines (last at 07:58:58
   and 07:59:07) and refusals fell from one every 4 s to about one a minute, the survey's. The certificate was renewed at
   08:00, and there has been no refusal or drop since 08:00:24, nor any keeper "unreachable" since 07:19. The survey's
   guard went in at 08:01, after the renewal, so it **has not been seen working against an expired certificate**.
3. Earlier today, in `tools/fleet-queue.py`: retries on ssh's failure, so a reset cannot lose a finished census.
4. **The operator certificate lasts 720 hours (thirty days), not 8**, at Paul's asking. It is adjustable: `copal fleet
   login --hours N` once, or a number in the fleet's `cert-hours` file for every login and Orrery's Renew. The price is
   stated in `docs/lockdown.md`: a stolen operator key holds the fleet for up to that long.

The queue took jaguaribe back by itself, with no change to any record.

## V. What Needs a Person

1. **Replace the battery.** On this board that is most likely a CR2032; check the holder before
   buying. Then confirm the date in the BIOS.
2. **If the BIOS offers it, stop it halting on errors**, so that a machine with no one at it still boots.
3. **Decide how long the operator certificate should last.** Thirty days by Paul's decision (Section IV).
   Shorter is safer if the Mac is ever lost: write hours in `~/.copal/fleets/grove/cert-hours`, then press Renew.

No `ssh-copy-id` is needed anywhere: the fleet's user key is accepted on every machine read here.

Until the battery is in, leave the machine's mains power on, since the chip is kept by standby power.

## VI. Limitations

- The battery's death is Paul's reading at the console, and the logs agree. It was not measured.
- Other machines' batteries were not tested. Their chips agree with their clocks, but `rtcsync` makes
  that so on any running machine. Only a boot after a power loss shows a weak battery. saskatchewan and
  columbia keep under an hour of log, so an old step would no longer be there to find.
- The penalties are shown to happen and to drop connections. How much of each unreachable count they
  explain was not separated from the machines' real absences.
- The penalty settings themselves (`sshd -T`) need root and were not read; the behaviour is in the log.

## VII. Future Work

- Persistent logs on Copal: this report's central question could not be answered because they vanish at each boot.
- Mend the false "host back".
- The guard covers the chat room. The minute's survey and button presses still dial as they did.
- A warning before the thirty days run out: the guard stops the penalties, but the chat room then goes quiet.
