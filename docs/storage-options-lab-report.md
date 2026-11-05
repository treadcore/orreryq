# Shared Storage, Reconsidered: Ceph for the Recordings and Builds, rsync and sftp, and Why Nothing Needs Deciding Yet

*Paul Richeson · Lab Report — IEEE Format · 4 November 2026*

Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery.

Companions: `docs/storage-lab-report.md` (29 October: the survey of the fleet's 45 disks, the one way through for each job, the plan for a small Ceph); `tools/storage.py`, `tools/recordings.py`, `tools/growth.py`; orrery commit `3ab85d0` (the sftp test).

## Abstract

On the evening of 4 November Paul asked four questions in a row: whether rsync would do better than sftp, whether there is another way than sftp, whether a Ceph mount between the servers could hold the largest data, with the recordings and builds in CephFS at three copies on NVMe, and whether that would solve the problem at all. This report sets out what was found and the options; **nothing is decided**. The problem that started it, disks filled by recordings and builds, is already answered: recordings are dropped once a recipe proves they can be made again, builds are pruned when main moves, and a flag is raised when any place passes 20 GB. At 18:28 on 4 November the whole fleet's training data was 33.7 GB, with no place over the limit. sftp is sound; its one failing test was a fault in the test, fixed. rsync is on every fleet machine but the Mac, which has Apple's openrsync. Ceph would hold the recordings and builds with three copies, but no NVMe in the fleet is free (every one holds a system or someone's data), three drives would have to be added, and the third node would need either a cable or would slow every write to 1 Gb. Ceph runs on Linux only; the Mac would reach it through a gateway, and cannot usefully be part of the cluster. A replication plan that keeps copies by how replaceable the data is would store the recordings and builds once, since a recipe remakes them exactly. The report ends with what would bring the question back.

## I. The question

Paul's words, in the order they came:

> how about rsync

> is there any other sftp solution. i have give up on rsync, sorry i thought it was a good idea.

> what i had in mind was a ceph mount between the servers for the largest size. Can we consider the ceph mount. part of the fleet. what can the mac do with the ceph mount. can it even be part of the server, for the right size. is there a better replication strategy.

> the recordings and builds; on CephFS x3. prefer nvme.

> would this solve our problem. seems like sftp is fine. what can you do to delay.

> talk about these suggestions. lab report. nothing descided yet.

## II. What the problem was, and what already answers it

On the morning of 4 November one machine, calber, held 114.5 GB of recordings and another, whitewolf, 18.9 GB: the rules recorded playing, a few hundred bytes a decision, for training nets by imitation. Old builds of the game lay beside them on every machine. Three changes the same day answered it:

- **Recordings are dropped once a recipe is proved.** A recording is a function of the program that made it and the seeds it played, so orrery keeps the build, the seeds and the SHA-256 of every shard, makes one shard of each build again, and deletes the shards only when the copy is equal byte for byte. A sweep every six hours does the same for new runs; a run marked *keep* stays. Calber went from 114.5 GB to 6.5 GB; two runs worth 87.5 GB were dropped.
- **Builds are pruned when main moves,** except those a recipe still needs. The first prune freed 45.3 GB.
- **Sizes are measured,** and a place over 20 GB raises a flag (Results, Growth; Settings, Long run).

*Table I. Measured on 4 November at 18:28 (Results, Growth): every place under the 20 GB limit, no warnings.*

| Machine | Where | Size | Most of it |
|---|---|---|---|
| mac | the queue | 12.9 GB | game logs of the reads: first reads 4.7, read-ons 3.5 |
| mac | treadcore build/ | 4.5 GB | the census and gauntlet builds |
| mac | the Mac's lane | 0.7 GB | its job outputs |
| macmini | ~/fleet | 3.4 GB | job outputs 2.6 |
| saskatchewan | ~/fleet | 3.1 GB | job outputs 2.8 |
| calber | ~/fleet | 2.6 GB | job outputs 1.5 |
| boburner | ~/fleet | 2.4 GB | job outputs 1.9 |
| whitewolf | ~/fleet | 1.4 GB | job outputs 0.9 |
| jaguaribe | ~/fleet | 1.3 GB | job outputs 0.9 |
| columbia | ~/fleet | 1.1 GB | job outputs 0.8 |
| bosporus | ~/fleet | 0.4 GB | job outputs 0.2 |
| **all** | | **33.7 GB** | |

## III. Moving files: sftp, scp, rsync, and the rest

orrery's Files pane speaks SFTP itself, over SSH, with nothing installed on either end. Its one failing test (*a directory lists with sizes and kinds and no dot entries*, about one full run in five) was a fault in the test: two tests on threads of one process named their temporary folders by the clock, a Mac's clock moves a microsecond at a time, and two tests handed the same folder listed each other's files. A counter in the name fixed it (`3ab85d0`; four full runs, 397 tests passed each). SFTP itself was never at fault.

*Table II. rsync on the fleet, 4 November.*

| Machine | rsync |
|---|---|
| saskatchewan, columbia, jaguaribe, bosporus (Alpine) | 3.5.0, protocol 3 |
| calber, boburner, whitewolf (Ubuntu) | 3.2.7, protocol 3 |
| the Mac | openrsync, protocol 29 (Apple's, a subset of the options) |
| macmini | did not answer |

*Table III. The ways to move a file, and what each is for.*

| Way | Good for | Cost |
|---|---|---|
| **SFTP** (orrery's own) | browsing: list, open, save one file in the Files pane | none; built |
| **scp** (in use) | a file or a few | none; on every machine |
| **rsync** | large copies: resumes a broken transfer, sends only what changed, compresses text | on the fleet; the Mac's openrsync takes only the common options (`-a --partial -z`), or Homebrew's rsync |
| **tar over SSH** | a whole folder of many small files, as one stream | none; Alpine's and macOS's tar both do it |
| **NFS share** (orrery's Storage view) | a folder every machine sees, so nothing is copied | built; the Storage view stages it |
| **SSHFS** | a remote folder mounted on the Mac | macFUSE, a kernel extension on the Mac |

The connections are shared (SSH ControlMaster for the fleet hosts since 4 November), so each copy reuses an open connection. Nothing in this section is slow enough today to change.

## IV. Ceph for the recordings and builds, three copies on NVMe

**What Ceph needs** [1], [2]: three monitors at least, an odd number, for a quorum; about 4 GB of memory for each storage daemon (OSD), and 1 to 2 GB for each monitor and manager; whole devices for the OSDs; and links of 10 Gb between the nodes, since every write waits for all three copies. Its deployment tool, cephadm, wants systemd and containers [3], so it runs on the Ubuntu machines; on Alpine, Ceph's packages exist but the setup is by hand, a procedure the Alpine wiki marks as work in progress [4].

**No NVMe in the fleet is free.** The survey of 4 November (Machines, Storage; as the user, nothing changed):

*Table IV. Every NVMe in the fleet.*

| Machine | NVMe | Use now |
|---|---|---|
| boburner | Crucial P3, 4 TB | the system |
| whitewolf | Samsung 950 PRO, 256 GB | the system |
| calber | HP EX950, 2 TB | the system |
| calber | HP EX900, 1 TB | encrypted (LUKS): someone's data |
| saskatchewan | Samsung 980 PRO, 2 TB | the system |
| saskatchewan | Samsung 980 PRO 1 TB; Crucial P3 4 TB | mounted as data volumes |
| columbia | FORESEE, 512 GB | the system |

So the plan of 29 October stands: three NVMe would be added, one a node.

*Table V. What three copies leave, with the 85% full ratio kept free.*

| Drives | Raw | Usable |
|---|---|---|
| 3 × 1 TB | 3 TB | about 0.85 TB |
| 3 × 2 TB | 6 TB | about 1.7 TB |

Against Table I's 33.7 GB, 1 TB drives are ample while recordings are dropped; 2 TB would hold recordings kept instead.

*Table VI. Where the three would go.*

| Node | Link | Memory | Notes |
|---|---|---|---|
| boburner | 10 Gb | 31 GB | Ubuntu, cephadm |
| whitewolf | 10 Gb (its fast port is .195) | 63 GB | Ubuntu, cephadm |
| jaguaribe | 10 Gb card, **not cabled** | 47 GB | Alpine: Ceph by hand |
| calber | 1 Gb | 63 GB | Ubuntu, cephadm; every write held to about 110 MB/s |

**One gain beyond space.** With builds on storage every machine sees, the fleet could build each treadcore commit once for each system (an Alpine build and an Ubuntu build differ) and share it. Today each machine builds its own.

## V. The Mac and Ceph

**A client, through a gateway.** macOS has no supported CephFS client. A Ceph node can serve the file system over SMB (Samba) or NFS (Ceph's own NFS service, NFS-Ganesha), and the Mac mounts that, in the Finder or with `mount`.

**Not a server.** Ceph's daemons do not run on macOS, only in a Linux virtual machine. An OSD in a VM on the Mac would share its 16 GB of memory and its one SSD, sit on 1 Gb, and set off a recovery across the cluster each time the Mac restarts for an update. The Mac does better as the coordinator, its own data backed up to wherever the fleet keeps copies.

## VI. Replication: copies by how replaceable the data is

Three copies of everything spends the most space on what matters least. The data falls into three kinds.

*Table VII. Copies by kind.*

| Kind | What | Where it could live | Copies |
|---|---|---|---|
| small and irreplaceable | the queue's archive, the films, the nets' vault, configuration | CephFS at three copies, or ZFS with snapshots | 3, and git for the code |
| large and reproducible | recordings (each with its proved recipe), builds, traces | one large pool | 1: a recipe remakes them exactly |
| large and irreplaceable | media and datasets on boburner's Hexamir | ZFS RAID-Z2, shared over NFS | 2: a nightly snapshot copied to the Asustor |

The recordings and builds Paul named are the second kind. Three copies would protect bytes a recipe can already remake; one copy and the recipe is the cheaper protection.

**Erasure coding** keeps parity in place of whole copies: a pool of 4 data and 2 parity chunks keeps 67% of its raw space and survives two failures [5]. A CephFS data pool can be erasure-coded (its metadata pool stays replicated) [6]. To survive a whole machine lost, each chunk must sit on its own machine: six machines with Ceph drives for 4+2, where the fleet has three on 10 Gb.

**The Supermicro as the large pool.** The X8DT3-LN4F that came back on 3 November has 48 GB of memory, 24 threads and a drive cage behind an add-in LSI card. ZFS in RAID-Z2 on its cage, shared over NFS, would be the large pool of Table VII without Ceph. Its links are four 1 Gb ports, which can be bonded.

## VII. What would bring the question back

None of these holds today. Any one would:

1. Recordings are to be **kept** long-term instead of dropped once their recipe is proved.
2. The shared data passes **a few hundred GB**, or a place keeps raising the 20 GB flag after a sweep and a prune.
3. **Three Ubuntu nodes have 10 Gb,** so Ceph would run at its speed.
4. A machine's loss would cost **data with no copy and no recipe.**

## VIII. Discussion

*Table VIII. The options, side by side; none chosen.*

| Option | It costs | It gains | Today |
|---|---|---|---|
| Keep what is built (recipes, sweeps, prunes, the 20 GB flag) | nothing | the space problem stays answered | in place |
| rsync for the large copies | a fallback to scp where it is absent | resumable, change-only copies | not needed at 33.7 GB |
| CephFS ×3 on NVMe for recordings and builds | three NVMe, a cable or a slow third node, about 4 GB of memory a node, a cluster to keep | three copies; builds shared once a system | not needed; no free NVMe |
| ZFS RAID-Z2 on the Supermicro, over NFS | the cage's drives, an HBA in IT mode | one large pool, two failures survived | possible once the cage's drives are counted |
| Copies by kind (Table VII) | a rule written down | the most protection for the space | a matter of policy |

**One step costs nothing whichever way this goes:** cabling jaguaribe's 10 Gb port makes a third 10 Gb machine, which NFS uses today and Ceph would need tomorrow.

**What this report does not do.** It formats no disk, buys nothing, and changes no setting. It records the options and the evidence so that the choice, when it comes, starts from here.

## References

[1] Ceph Documentation, "Hardware recommendations." https://docs.ceph.com/en/latest/start/hardware-recommendations/

[2] Ceph Documentation, "Monitor config reference" (monitors, quorum). https://docs.ceph.com/en/latest/rados/configuration/mon-config-ref/

[3] Ceph Documentation, "cephadm." https://docs.ceph.com/en/latest/cephadm/

[4] Alpine Linux Wiki, "CEPH" (work in progress). https://wiki.alpinelinux.org/wiki/CEPH

[5] Ceph Documentation, "Erasure code." https://docs.ceph.com/en/latest/rados/operations/erasure-code/

[6] Ceph Documentation, "Create a Ceph file system" (erasure-coded data pools). https://docs.ceph.com/en/latest/cephfs/createfs/
