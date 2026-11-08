# The Share and the Wire: calber's Array over NFS, and the Home Network Mapped

*Paul Richeson · Lab Report — IEEE Format · 7 November 2026 · a growing report: the map, and the share sync and async from the Mac, the VM, nasser and xinanjiang, are measured; saskatchewan rewired and placed; a film; more machines will join*

Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery.

Companions:
- `tools/nfs-client-bench.py`, the share measured from the machine that uses it;
- `tools/net-map.py`, the network's links and paths, measured over ssh with nothing installed;
- `tools/net-report.py`, the map, the charts and the tables, drawn from those measures;
- `tools/disk-bench.py serve`, and calber's `nfs.sh`, the share itself;
- `docs/network/`, every result and figure;
- `docs/calber-ssd-lab-report.md`, the array's own numbers, measured inside calber.

---

## Abstract

calber's six SSDs, as mdadm RAID10 with ext4, were shared over NFS and measured from the machines that would use them, while the home network between them was mapped from inside.

**The wire, not the array, sets the share's speed for large files.** Every 1 GbE client reached the same 117 MB/s, a sixteenth of the array's 1.9 GB/s.

**Small files are slow on a sync share, and the server's counters show why.** Every change costs about 8 disk flushes across the six SSDs: the journal flushes all six, and these drives lack forced writes (FUA), so the kernel adds a flush on each of the two disks holding the commit. A Linux client spends 2 changes on a new file and makes 140 a second. The Mac spends 7 and makes 44. calber makes 40,700 a second on its own disks.

**The Mac pays twice on small files:**
- NFSv3 cannot hold extended attributes, so every file the Mac writes gets a hidden `._` companion;
- every 4K random read fetches a whole read-size block.

macOS's own 32K defaults gave 3,554 4K reads a second, 32 times a 1 MiB mount. A plain Finder mount is the right one.

**An async share makes small files 2.6–5.7 times faster, and it is a choice of risk.** The flushes go: 0.1–0.3 disk flushes a file, against 16–41 on the sync share. What remains is round trips. A Linux client spends 2 compound requests a file and made about 800 files a second. The Mac spends 17 separate requests and made about 100. The server now confirms a write before it is on disk, so a crash or power cut on calber loses the last seconds of what its clients were told was written.

**The network:**
- a switching core with 10 GbE and 1 GbE ports, which carried 5.7 Gb/s from eight 1 GbE machines at once;
- whitewolf and boburner on 10 GbE, 9,380 Mb/s between them;
- nasser and xinanjiang sharing one 1 GbE link behind a small switch of their own;
- saskatchewan's link at 100 Mb/s until Paul rewired it: now 941 Mb/s, on the small switch beside nasser and xinanjiang;
- jaguaribe's 10 GbE card without a link.

## The Film

!html(network/film-wire.html)

*Film 1, from 0:31: "Then the wire", the closing scene of the SSD report's film (`docs/calber-disks/film.mp4`). The array's 1.85 GB/s narrows to the 117 MB/s of one 1 GbE link, and small files made a second fall from 40,700 on calber's own disks to 147 from a Linux client and 39 from the Mac, on a log scale. The film opens with the thirteen layouts that competed for the disks; this report begins where it ends.*

## I. Introduction

The SSD report scored RAID10 on ext4 best for an NFS share, at 1.46× one disk. That score was weighted from measures taken inside calber; nothing had crossed the network. Paul: "I'm really impressed by the NFS speed. Can we set this up with a test. Perhaps even our network test with the VM inside." Then: "compare this same test on nasser and xinanjiang. map the network topography and observe (generically the switches, the 10gig links between the 1GbE connects) … keep adding to it. we will be continuing with more computers after this concludes."

So the report asks two questions, and keeps asking them as machines are added:
1. What does the share give each machine that mounts it?
2. What is the network between them made of?

## II. History

| Time (PST) | What | Who |
| --- | --- | --- |
| 16:10 | The test staged: `nfs.sh`, `nfs-client-bench.py`, the Bench screen holding its Run button while the disks are shared | Claude |
| 16:41 | `ssh -t calber sudo sh fleet/disk-bench/nfs.sh setup`: the NFS server and iperf3 installed, the six disks built as RAID10 with ext4 and shared, sync | Paul |
| 16:42 | calber runs the client bench on its own mount: the baseline | Claude |
| 16:43 | iperf3 from the Mac: 117.5 MB/s up, 117.1 down, 0.58 ms | Claude |
| 16:44 | The Mac mounts the share without root, then cannot read it: macOS keeps network volumes from Terminal until allowed. Paul allows it and restarts Terminal | Paul |
| 17:00–17:05 | The first Mac run: 41 files made a second, and 20,042 files listed of 10,000 made, the `._` companions. The bench is fixed twice: companions counted apart, and a companion the Mac removes by itself is no failure | Claude |
| 17:10 | The inventory: eleven machines' links | Claude |
| 17:11–17:15 | The Mac, sync, 1 MiB reads and writes | Claude |
| 17:16–17:20 | The map: a pair, the star, the fan-ins, the pings | Claude |
| 17:20–17:24 | The Mac remounted at 64K, then at its defaults (32K) | Claude |
| 17:25 | nasser, xinanjiang and the VM set up as clients (`setup.sh`, NFS 4.2) | Paul |
| 17:25–17:39 | The three Linux clients in turn, sync: the VM, nasser, xinanjiang | Claude |
| 17:40–17:41 | The server's counters around 200 files made, moved and removed, from the Mac and from xinanjiang: NFS operations and disk flushes a file | Claude |
| 17:48 | `nfs.sh async`: the same share, its files kept, answering before the disks | Paul |
| 17:48–18:01 | Every client again on the async share, then the counts again | Claude |
| about 17:55 | saskatchewan rewired | Paul |
| 18:02–18:04 | The map again: saskatchewan at 941 Mb/s, and behind the small switch with nasser and xinanjiang | Claude |
| 17:50–18:15 | The film: forty seconds of the SSD report, its last scene this report's (The Film) | Claude |

## III. Method

### A. The share

`nfs.sh setup` installs the NFS server and iperf3, then calls `disk-bench.py serve`:
1. blank the six disks;
2. build RAID10 with ext4 exactly as the bench does (512K chunk, near-2 layout, write-intent bitmap, inode tables written at once);
3. mount it at `/mnt/bench`;
4. export it to the home subnet: `192.168.8.0/24(rw,sync,insecure,no_subtree_check,no_root_squash)`.

`nfs.sh async` switches the export with the files kept, and `nfs.sh stop` ends it and blanks the disks. While the disks are shared, Orrery's Bench screen holds its Run button and says how to end the share.

### B. The client bench

`nfs-client-bench.py` is the same on every machine: python3 and fio, no root.
- **net:** iperf3 for 10 s each way, and 20 pings.
- **large files,** with fio's direct I/O so the client's own memory is not measured:
  - 4 GB written, then read, in 1M blocks at queue 8;
  - four readers at once;
  - 4K random reads and writes at queue 16;
  - a 4K write and its fsync, one at a time.
- **the tree:** as many 4K files as a minute makes, up to 10,000 in 40 folders. They are then listed with their sizes (twice), sorted, moved into 20 folders, read and removed.

A share that reads faster than 1 GbE can carry is flagged: its client answered from memory.

### C. The map

`net-map.py` reaches each machine by ssh and runs python3 from stdin: nothing installed, no root.
- **inventory:** each machine's links from `/sys/class/net`: speed, driver, address.
- **pair, star, fan-in:** one TCP stream per sender for 5–8 s, counted at the receiver over the stretch when every sender was sending. Checked against iperf3 on the same path: 940.2 Mb/s against 940.

**Three rules turn rates into switches:**
1. a sender's rate alone is its own link's speed, or its own limit;
2. two senders that halve each other, together one link's worth, sit behind one link;
3. a group whose total passes one link's worth proves a faster link between it and the receiver.

## IV. The Network

### A. The machines' links

| Machine | Address | Link | Card (driver) | Notes |
| --- | --- | --- | --- | --- |
| this Mac (iMac) | 192.168.8.143 | 1 GbE | built-in Ethernet | also on Wi-Fi to a second network, 192.168.1.0/24 |
| treadcore-vm | 192.168.64.39 | virtual | virtio, NAT through the Mac | |
| calber | 192.168.8.179 | 1 GbE | Intel (e1000e) | Wi-Fi unused |
| whitewolf | 192.168.8.193 | **10 GbE** | Mellanox ConnectX (mlx4) | its Intel 1 GbE unused |
| boburner | 192.168.8.113 | **10 GbE** | Mellanox ConnectX (mlx4) | its Realtek 1 GbE unused |
| jaguaribe | 192.168.8.245 | 1 GbE | Intel (e1000e) | **a Mellanox 10 GbE port without a link** |
| bosporus | 192.168.8.194 | 1 GbE | Intel (igb), four ports | three unused |
| columbia | 192.168.8.223 | 1 GbE | Realtek (r8169) | |
| saskatchewan | 192.168.8.235 | 1 GbE, **100 Mb/s until rewired** | Realtek (r8169) | rewired about 17:55; now on the small switch |
| nasser | 192.168.8.121 | 1 GbE | Broadcom (tg3) | an i3-2310M laptop |
| xinanjiang | 192.168.8.217 | 1 GbE | Realtek (r8169) | |
| router | 192.168.8.1 | | GL.iNet, by its hardware address | the way out |

### B. Each machine alone

!html(network/star.html)

**Every machine reached its own link's limit but one.** nasser sent 737–748 Mb/s with one stream or four: the 2011 laptop's limit, its CPU or its card, not the network's (Section IV.C). The VM inside the Mac lost nothing to its NAT at first, 940 Mb/s, and 869 in the second star. **saskatchewan sent 94 Mb/s before it was rewired, the most a 100 Mb/s link carries, and 941.5 after:** ten times as much, from a cable.

### C. All at once, and who shares

| Sent to whitewolf at once | Each, Mb/s | Together |
| --- | --- | --- |
| eight 1 GbE machines | the Mac 918, calber 932, jaguaribe 937, bosporus 941, columbia 939, nasser 391, xinanjiang 551, saskatchewan 94 | **5,702** |
| nasser and xinanjiang | 473 and 469 | **941.5** |
| nasser and columbia | 746 and 942 | 1,687 |
| xinanjiang and bosporus | 942 and 941 | 1,883 |
| nasser alone, four streams | 748 | |
| **after saskatchewan was rewired:** | | |
| saskatchewan and nasser | 471 and 471 | **941.5** |
| saskatchewan and xinanjiang | 470 and 472 | **941.5** |
| saskatchewan and the Mac | 942 and 940 | 1,882 |
| saskatchewan and columbia | 940 and 942 | 1,882 |
| eight 1 GbE machines | the Mac 940, calber 937, jaguaribe 941, bosporus 942, columbia 941; nasser 313, xinanjiang 294, saskatchewan 335 | **5,642** |

**nasser and xinanjiang share one link, and since its rewiring saskatchewan shares it too.** Any two of the three together made exactly one 1 GbE link's worth, split evenly, and all three together split it in three (313 + 294 + 335 = 941.5). Each kept its full rate beside a machine elsewhere. Every other 1 GbE machine kept 937–941 Mb/s with all eight sending.

### D. What the switches must be

!html(network/topology.html)

1. **A core with 10 GbE and 1 GbE ports.** whitewolf and boburner exchanged 9,380 Mb/s on one stream (9,398 on four), a full 10 GbE path. Eight 1 GbE machines delivered 5,702 Mb/s to whitewolf at once, so whatever joins the 1 GbE ports to whitewolf's carries at least six 1 GbE links' worth. That is a 10 GbE link between switches, or one switch's own backplane. **No measure here can tell those apart:** eight 1 GbE senders cannot fill a 10 GbE link, and a 10 GbE hop adds 1.2 µs, beneath the machines' own timing noise.
2. **A small switch with one 1 GbE link up into the core,** holding nasser, xinanjiang and now saskatchewan. When they talk to the rest of the network at once, they share that one link. Two GPU-less machines and saskatchewan's 24 cores behind one 1 GbE link is fine for the fleet's work, which moves little data, and would not be for a share.
3. **saskatchewan's link negotiated 100 Mb/s until Paul rewired it.** Its card does 1 GbE. 1000BASE-T needs all four pairs of a cable, and 100BASE-TX only two [3], so a cable with a broken pair, or one of two pairs, links at 100. After the rewiring it linked at 1,000 and carried 941.5 Mb/s.
4. **jaguaribe has a 10 GbE port and no link on it.** With a cable to a free 10 GbE port, it would join whitewolf and boburner.

**What the pings showed.** The fastest of 40 full-size pings from whitewolf took 239 µs longer than small ones to saskatchewan: two 120 µs serialisations of a 1,500-byte frame at 100 Mb/s, exactly. To the 1 GbE machines the difference ran 0–153 µs, against the 24 µs a 1 GbE hop adds. Each machine's own interrupt timing is larger than a hop, so the pings cannot count switches here.

## V. The Share

### A. The baseline and the wire

calber ran the client bench on its own mount of the array, and the Mac ran iperf3 to it.

| | calber, its own disks | the wire, Mac and calber |
| --- | --- | --- |
| large files | 746 MB/s written, 1,851 read | 117.5 MB/s up, 117.1 down |
| 4K random reads | 111,514 a second | ping 0.58 ms |
| a 4K write and its fsync | 463 a second, 2.1 ms a flush | |
| small files made | 40,700 a second | |
| listed with sizes | 543,000 a second | |

### B. Every client, sync

| Client | Mount | Seq W MB/s | Seq R MB/s | 4K reads/s | 4K writes/s | Write+fsync/s | Make files/s | List files/s | Move files/s | Read files/s | Remove files/s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| calber, its own disks | ext4 | 746 | 1,851 | 111,514 | 88,726 | 463 | 40,700 | 543,325 | 70,348 | 132,824 | 118,133 |
| the Mac | NFSv3, 1 MiB | 117 | 117 | 111 | 1,936 | 338 | 40 | 20,678 | 86 | 743 | 94 |
| the Mac (quick) | NFSv3, 64K | 89 | 116 | 1,780 | 1,975 | 342 | 44 | 24,329 | 95 | 1,270 | 115 |
| the Mac (quick) | NFSv3, its defaults: 32K | 115 | 116 | 3,554 | 2,006 | 365 | 39 | 25,560 | 98 | **1,599** | 124 |
| the VM, inside the Mac | NFS 4.2, 1 MiB | 115 | 116 | 11,092 | 3,239 | **458** | 135 | **54,811** | 324 | 722 | 241 |
| nasser | NFS 4.2, 1 MiB | 92 | 117 | **20,070** | **3,247** | 431 | 142 | 24,903 | 343 | 1,142 | 216 |
| xinanjiang | NFS 4.2, 1 MiB | **118** | **117** | 19,011 | 3,238 | 402 | **147** | 31,624 | **363** | 1,014 | **275** |

The export is sync. The best share in each column is bold. "Quick" runs wrote 1 GB and ran 8 s a test; their per-second rates compare with the full runs'. The trees were as large as a minute of making allowed: 2,400 files from the Mac, 8,160–8,840 from the Linux machines.

1. **Large files run at the wire's limit,** 115–117 MB/s each way, from one reader or four.
2. **Small files run at about 40 made, 90 moved and 100–120 removed a second.** Each of those is a change the server must have on disk before it answers.
3. **Listing is cheap.** NFS returns names and their attributes in batches (READDIRPLUS), so a listing with sizes ran at 20,000–25,000 files a second. A second listing ran at 120,000–139,000, from the Mac's attribute cache, which it keeps 5–60 s.

### C. The Mac's two taxes

1. **A `._` companion for every file.** macOS tags every file a program makes with extended attributes, and NFSv3 cannot carry them [1]. So the Mac writes each file's attributes into a hidden AppleDouble file beside it: 2,440 companions for 2,400 files, one for each file and folder. Every file made, moved or removed is two. `dot_clean` merges them back on a Mac. The extended-attribute support NFSv4.2 added [2] is not in the Mac's NFS client.
2. **A whole read-size block for every small read.** With direct I/O, the Mac fetched one full read-size block for each 4K random read: 111 a second at 1 MiB, 1,780 at 64K, 3,554 at 32K. Each is the wire's 117 MB/s divided by the block. **The defaults are the best of the three:** they keep large files at the wire's speed and give small reads the most. The explicit 1 MiB, the usual advice for Linux, is the worst on a Mac.

### D. From the Linux machines

The VM inside the Mac, nasser and xinanjiang mounted the share with NFS 4.2 and 1 MiB reads and writes, and ran one at a time.
1. **They make, move and remove files three to four times as fast as the Mac:** 135–147 files made a second against 39–44. The counters say why (Section VI.2): two changes a file against seven.
2. **They read 4K blocks as 4K blocks:** 19,000–20,000 random reads a second on the LAN, against the Mac's best of 3,554. A Linux client sends what was asked for, whatever its read size.
3. **The VM loses half its small reads to its place inside the Mac:** 11,092 a second at 1.04 ms a ping, against 0.52–0.58 ms on the LAN. Large files lost nothing (115–116 MB/s).
4. **nasser writes at 92 MB/s,** its own ceiling: iperf3 sent 91.4 MB/s from it and received 117.1, and the map found its 748 Mb/s alone (Section IV.B).
5. **A write and its fsync, one at a time, ran at 402–458 a second from every Linux client,** the same as calber's own 463. One flush round of the disks, about 2.2 ms, is the whole cost; the wire's half millisecond hides beneath it.

### E. sync and async

At 17:48 the share was switched to async with its files kept, and every client ran again on the same mount.

!html(network/async.html)

| Client | Make files/s, sync → async | Move | Remove | 4K writes/s | Write+fsync/s |
| --- | --- | --- | --- | --- | --- |
| the Mac (32K) | 39 → **101** | 98 → 142 | 124 → 220 | 2,006 → **27,330** | 365 → 2,296 |
| the VM | 135 → **510** | 324 → 1,065 | 241 → 761 | 3,239 → 11,155 | 458 → 1,044 |
| nasser | 142 → **804** | 343 → 1,482 | 216 → 1,318 | 3,247 → 19,138 | 431 → 1,745 |
| xinanjiang | 147 → **803** | 363 → 1,188 | 275 → 878 | 3,238 → 24,643 | 402 → 2,312 |

1. **Every small-file step got faster by 1.4–6.1 times,** and random 4K writes by 3.4–13.6 times. Large files did not change: they were already at the wire's 117 MB/s.
2. **The write-and-fsync column is the warning.** Async clients completed 1,044–2,312 a second, past the 463 calber manages on its own disks. A fsync can only be that quick if it does not reach the disks: the server answers first.
3. **The flushes went, the operations did not.** The same 200-file count on the async share:

| Client, step | Changes a file | Disk flushes a file, sync → async | Files a second, sync → async |
| --- | --- | --- | --- |
| the Mac, make | 7.08 | 40.9 → **0.31** | 44 → 98 |
| the Mac, move | 2.00 | 16.3 → 0 | 84 → 184 |
| the Mac, remove | 2.03 | 16.5 → 0.19 | 107 → 268 |
| xinanjiang, make | 2.01 | 16.4 → **0.12** | 138 → 592 |
| xinanjiang, move | 1.00 | 8.2 → 0 | 307 → 1,333 |
| xinanjiang, remove | 2.01 | 8.4 → 0 | 234 → 541 |

## VI. Why the Share Behaves as It Does

1. **1 GbE carries 117 MB/s of payload** (941 Mb/s of TCP), and every client's large-file rate sits there. The array behind it reads 1.9 GB/s. For large files a share of these disks wants 10 GbE: whitewolf and boburner already have it, and calber does not.
2. **A sync share pays about 8 disk flushes for each change, counted** (below). NFS's sync export answers a change only once it is on stable storage, and a change on ext4 is a journal commit.
3. **Reading and listing need no flush,** which is why they run tens to hundreds of times faster than making.
4. **On an async share, a file costs round trips, and the Mac makes more of them.** The Mac's NFSv3 sends each step as its own request: 17.3 requests a file made, each waiting its 0.58 ms round trip. That is 10 ms, or 100 files a second, and it made 98. A Linux client's NFS 4.2 bundles a file's steps into compound requests, 2.05 a file. At 0.5–0.6 ms each, that is about 800 a second, and it made 804.

**The count.** The server's counters, read around 200 files made, moved and removed (`tools/nfs-ops.py`):


| Client, step | Changes a file | Disk flushes a file | Files a second |
| --- | --- | --- | --- |
| the Mac, make | 7.08: create 2, write 2, commit 2, setattr 1 | 40.9 | 44 |
| the Mac, move | 2.00: rename 2 | 16.3 | 84 |
| the Mac, remove | 2.03: remove 2 | 16.5 | 107 |
| xinanjiang, make | 2.01: open (it creates) 1, write 1 | 16.4 | 138 |
| xinanjiang, move | 1.00: rename 1 | 8.2 | 307 |
| xinanjiang, remove | 2.01: remove 1, setattr 1 | 8.4 | 234 |

**Every change costs about 8 flushes,** and the eight are accounted for. ext4 commits each change to its journal, and a commit first flushes every disk of the array: six. These drives do not take forced writes (`fua=0`), though the array tells ext4 it does (`fua=1`). So the commit block's forced write goes to its two mirror disks as a write and a flush each: two more. The six flush at once, then the two, so a change costs about two flush rounds, some 5–7 ms. **The Mac's file costs seven changes because of its companion:** it creates, writes and commits each of the two files, and sets the attributes once. A Linux client creates in its open and sends a file of one write as already stable, so it needs no commit. Seven against two is 3.5 to 1, and the rates were 3.1 to 1.

## VII. Conclusions So Far

- **Move large files over the share, and do small-file work on calber itself.** The share gives large files the wire's full 117 MB/s. Making or moving thousands of small files over it runs at under 1% of calber's own speed.
- **For small-file work over the share, a Linux client is three to eight times the Mac,** and the VM inside the Mac is one: 135 files made a second against 39 on the sync share, 510–804 against 101 on the async.
- **Async if the work can be made again; sync if it cannot.** Async made small files 2.6–5.7 times faster. It also confirms writes calber has not yet made, and calber lost power this morning. A Blu-ray working disk holds images that can be rebuilt from their sources, so async suits it, with a UPS. Check each image's checksum before burning it: an image written just before a crash can be confirmed and still be short. Masters that exist nowhere else belong on a sync share.
- **Mount on the Mac with its defaults:** Finder, Go → Connect to Server, `nfs://192.168.8.179/mnt/bench`, or `mount_nfs` with no options.
- **Expect the `._` files** on anything the Mac writes to the share.
- **saskatchewan's cable is fixed:** 941.5 Mb/s, against 94. It now shares the small switch's one link with nasser and xinanjiang; a port on the core would give it a link of its own.
- **jaguaribe's 10 GbE needs only a cable,** if the core has a free 10 GbE port.

## VIII. What Is Next

This report grows: each new machine becomes a row in IV.A, a bar in IV.B, a box on the map and a column of the share.
- [x] **The Linux clients, sync:** the VM, nasser, xinanjiang, 17:25–17:39 (Section V.D).
- [x] **Count what a file costs,** 17:40–17:41: NFS operations and disk flushes a file (Section VI.2).
- [x] **The share async,** 17:48–18:01: every client again, and the counts (Section V.E).
- [x] **saskatchewan's cable,** rewired about 17:55: 941.5 Mb/s, on the small switch (Sections IV.B–D).
- [x] **The film,** 40 s, its last scene this report's (The Film).
- [ ] **More machines.** To add one:
  1. give it a line in `net-map.py`'s HOSTS and run `inventory`, then `star whitewolf`;
  2. run fan-ins with its neighbours, to find what it shares;
  3. on it, `nfs-bench/setup.sh` as root, then `nfs-client-bench.py net` and `run`;
  4. on the Mac, `net-report.py fetch`, `draw` and `table`.
- [ ] **When the share is done:** unmount the clients, then `nfs.sh stop`, then the twelve RAID10 versions (`tune.sh`, SSD report VIII).

## IX. Limitations

- **One trial a measure.** The Mac's 64K and default runs were quick runs.
- **Fan-in senders start within about a tenth of a second of each other.** The counted stretch leaves out the first and last second.
- **The fleet was computing during the map,** at loads of 5–9. Each loaded machine still reached its link's limit at 1 GbE; at 10 GbE the CPU could be the limit, and the one 10 GbE pair reached 9,380.
- **The core's structure is inferred, not seen.** The switches answer nothing, so the map shows what they do, not what they are.
- **The Mac's dip to 89 MB/s writing at 64K** is a single quick trial.

## References

[1] B. Callaghan, B. Pawlowski and P. Staubach, "NFS Version 3 Protocol Specification," RFC 1813, June 1995. [Online]. Available: https://www.rfc-editor.org/rfc/rfc1813

[2] M. Naik and M. Eshel, "File System Extended Attributes in NFSv4," RFC 8276, December 2017. [Online]. Available: https://www.rfc-editor.org/rfc/rfc8276

[3] IEEE Standard for Ethernet, IEEE Std 802.3-2022, Clause 25 (100BASE-TX) and Clause 40 (1000BASE-T).

[4] iperf3, ESnet. [Online]. Available: https://github.com/esnet/iperf

[5] fio, Flexible I/O Tester. [Online]. Available: https://github.com/axboe/fio
