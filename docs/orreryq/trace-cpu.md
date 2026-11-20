# One CPU generation, end to end: w21532, ladder 0 -> 3, on main at 22:47 on 15 November

Traced from the live queue `/Users/user/code/treadcore/build/queue/grove` (QUEUE) on 19 November 2026,
read-only. Every time below is the Mac's clock (PST). The per-job rows are in `trace-cpu.json` beside this file.

## 0. Why this generation

In the last three days only one generation reached the line: **r0338** (w23266, four dials) promoted on
18 Nov at 21:16. Its proof read it **+0.07 +/- 0.04 over main in 9,600 seeds**, under the 0.25 a generation must be
worth, and it was orphaned at 23:22 the same night (`plan/runs/r0338/state.json`, flag `line`). Main has not
moved since 15 Nov 22:47.

So the example is the most recent promotion whose line proved to main: **r0337**, trial **w21532**, 15 Nov,
four days back. It shared its line with r0336 (w21399), promoted six hours earlier, and the two went to main
together as `81e0df3`. It is the quickest generation to main since 5 November but one (2.9 hours from its first
job; the median of nine is 9.0 hours, from `tools/report/outgrowing.py`).

## 1. The trial and where it came from

| | |
|---|---|
| Trial | **w21532**, title `ab-ladder-expand_first: ladder 3` |
| Dial | `ladder`, a *choice* dial in treadcore's `weights.rs`: "the ladder's order, defend base first in each (choice: as_built \| expand_before_hunt \| hunt_first \| expand_first)" |
| Change | `ladder = 0` (as_built) -> **`ladder = 3` (expand_first)**; the trial file: `# A/B: ladder expand_first against as_built` / `ladder = 3` |
| Source | **An A/B version trial.** The planner (`ab_trials` in `tools/plans/treadcore.py`) asks every switch and every choice version that is not the default, once each, alone, on each new set of defaults. suggest.py leaves these out. No person, no fit, no far trial, no carried pass. |
| Defaults it ran on | `2a1a1e9`, the local line: main `f5794cc` plus r0336 (w21399: called_for 15 -> 7.5, confirm 2 -> 1, kite_in 2.25 -> 1.125, strikes_max 3.30 -> 4), on the line from 15:38 |
| Its siblings | 62 A/B trials asked on 2a1a1e9, among them the other two ladder versions, w21529 (ladder 1) and w21531 (ladder 2) |
| Commit | `81e0df3`, 21:07:42: "promote grove/w21532 as the brain's defaults -- ladder 0 -> 3; census +0.44 +/- 0.37, held out +0.56 +/- 0.26 and +0.28 +/- 0.25 and +0.62 +/- 0.28; families holds". It touched `weights.rs` and `scenarios/families/a-tank-under-a-ready-gun.toml` (the floor moved). |

**It had been asked 38 times before.** `ladder = 3` is re-asked on every new set of defaults: 39 trials from
w1488 (29 Oct) to w21532 (`plan/done-titles.json`, `results/w*/.../pooled.txt`). Twice before, it passed its
held-out reads and was stopped by the same family:

| when | trial | held out | family `a-tank-under-a-ready-gun` (floor 80.0%) | verdict |
|---|---|---|---|---|
| 1 Nov 18:17 | w5290 | +1.10 +/- 0.33 (400) | 78.9% | UNDER (f0127) |
| 5 Nov 17:53 | w11272 | +0.47 +/- 0.25 (400) | 79.7% | UNDER (f0264) |
| 15 Nov 21:00 | **w21532** | +0.47 +/- 0.15 (1,128, three reads) | 79.6% | **holds, a small drop**: the floor moved to 0.78 (f0345) |

The rule that let 79.6% pass came into treadcore on 13 Nov at 10:24 (`6a706cd`, "A small drop passes and moves
its floor; a collapse does not"). So the generation was partly a rule change meeting an idea the A/B kept asking.

**The seeds (the "seed transfer").** Every read is a census of the trial's values against the defaults on
`MAP=all`, the 13 maps, where seed n plays map n mod 13 (`scripts/census.sh`). Each kind of read draws from its
own block, so no read reuses another's seeds:

| read | seed block (planner rule) | w21532's seeds |
|---|---|---|
| first read | 20,000,000 + 10,000 x trial number | 235,320,000 to 235,320,141 (142 own) + 8 probes = 150 |
| read-ons | 300,000,000 + 1,000 x read-on counter | e22790 322,790,000 (67+8); e22794 322,794,000 (105+8); e22799 322,799,000 (164+8); e22801 322,801,000 (164+8) |
| held-out reads | 60,000,000 + 200,000 x held counter, four pieces of 100 | h1503 360,600,000; h1504 360,800,000; h1505 361,000,000 (each piece 92 own + 8 probes; merged 368 + 8 = 376) |
| line proof | 700,000,000 + 200,000 x proof counter | pv0499 799,800,000 ... pv0516 803,200,000 (392 own + 8 probes each) |
| probes | (1,000,000,000 + j) x 13 + map index | 13000000002, ...017, ...027, ...039, ...064, ...067, ...082, ...092 on naval, constanine, island, industry, generated: **the same eight in every MAP=all census** |

How the held-out read differs from the trial's reads: it plays seeds 60 million up, a block no trial or read-on
draws from, against the same defaults commit (2a1a1e9), on the same 13 maps; it is asked only after the
sequential read has passed, as four 100-seed pieces on the four fast lanes (`needs: fast`), merged by treadcore's
`pool.sh` into one read under the read's own id; and it is judged pooled across reads, not stage by stage. The
eight probe seeds are the one thing every read shares. The proof turns the question round: main's values are
the trial and the line is the base, so the line's lead is minus the census's d. (One quirk: a pooled sequential
read counts the eight probe games once per read, 40 of its 682 seeds; the merged held read counts them once.)

## 2. The story, with times

**15:38.** r0336 joins the line; the defaults become `2a1a1e9`. At 15:42 the line "settles first" (its proof must
read 9,600 seeds before another generation may join), three passes of the last generation are carried, and the
far round 5 is asked (128 dials, each at 1.41 times and 1/1.41 of today's). The A/B set is asked anew.

**19:41:26.** The planner asks w21532, the 39th `ladder = 3`. It waits 11.1 minutes: eleven jobs start on CPU
lanes ahead of it, six of them high-priority read-ons of other trials (e22783 to e22788), three earlier trials
(w21529 to w21531) and a bridge census.

**19:52:32 to 19:57:52**, boburner, 150 seeds: **+0.44 +/- 0.37, z 1.19**. Inside the noise, over the first keep
bar (z 0.25), so it reads on.

**19:58 to 20:20.** Three read-ons, each asked by the next planner pass and taken within three minutes
(they are high priority): 225 seeds z 1.86, 338 seeds z 2.20, and at **20:20:27, 510 seeds, +0.63 +/- 0.22, z 2.92**,
past the 510-seed pass bar of z 2.1 with no map two errors under. The trial had passed.

**20:20:34. A read asked twice.** The planner pass that ran from about 20:20:24 to 20:20:34 asked
"read on 4 of w21532 (172 seeds more, z +2.20 on 338)" again as e22801, the same words as e22799, which had
returned at 20:20:27, inside that pass. `sequential()` reads the finished jobs' titles first and the running
jobs second: e22799 was not yet in `done/` when the first was read and no longer in `running/` when the second
was, so the pass saw neither its seeds nor a read in flight. e22801 ran on calber, the slowest CPU lane, 10.3
minutes for the 172 seeds macmini had read in 3.5. It cost 24.3 Wh and about 11.6 minutes of the chain (the
held-out read would have been asked by the pass at 20:21:08). After it: 682 seeds, +0.60 +/- 0.19, z 3.17.

**20:32:44 to 21:00:40. Three held-out reads**, 400 seeds each in four pieces. The bar is pooled z 2.5
(HELD_Z 3.0 less the ease, 0.5). Read 1: +0.56 +/- 0.26, z 2.15: promising and undecided (between 1.0 and 2.5),
so it is read again. Read 2: +0.28 +/- 0.25; pooled +0.41 +/- 0.18, z 2.30: again. Read 3: +0.62 +/- 0.28; pooled
**+0.47 +/- 0.15 over 1,128 seeds, z 3.13**, no map under, fortressislesx (+1.87 +/- 0.72) and europe (+1.17 +/- 0.41)
two errors up. From 20:41 two of the four fast lanes (saskatchewan, saskatchewan-2) were held by the last two
proof reads of r0336's line (pv0497, pv0498, 18 to 19 minutes each), so reads 2 and 3 ran their four pieces on
two lanes, macmini and boburner, and each read's last piece waited 5.4 and 6.3 minutes.

**21:00:42.** Flag: "candidate w21532 passed both held-out reads (+0.56, +0.28, +0.62): ladder 3". Nothing held
it: r0336's line had already read its 19,200 seeds (+0.15 +/- 0.08, neither proved nor refused) and was let go.
Families (f0345, calber, 48 s): holds 48. The gauntlet's floors (gx0084, macmini, 4 s). **21:04:39** auto asks
r0337; the promote job runs the brain's tests (178 passed) and families on a branch and commits **81e0df3 at
21:07:42**. 21:08:32 approved: the local line is now 81e0df3 (r0336 + r0337).

**21:10 to 21:17.** Six machines build 81e0df3 (each as its lane comes free). **21:20:15** the proof is asked,
six reads at a time because the line is settling, on the four fast lanes.

**The proof, three rounds of six.** Round 1 (2,400 seeds) **+0.64 +/- 0.24, z 2.62**: under the proof's bar of z 3.0.
Round 2 (4,800) **+0.64 +/- 0.17, z 3.77**, but constanine two errors on main's side: a map holds it. Round 3 (7,200)
**+0.59 +/- 0.14, z 4.27**, no map under. **22:47:05: "the line 81e0df3 proved past main: +0.59 +/- 0.14 over
7200 seeds; it is main now"** (origin/main moved 22:47:00 by the reflog). Each round lasts as long as one fast
lane needs for two or three 400-seed jobs (macmini 7.3 minutes a job, boburner 12.9, saskatchewan 18.5).

**16 Nov 14:51:34** values confirmed on 5 of 5 machines. The yardstick of 16 Nov reads 81e0df3 against the fixed
mains (below).

## 3. Every job of the chain
| # | job | stage | lane | queued | started | ended | wait min | run min | seeds (block) | result (d +/- se, seeds) | pooled after | maps 2 se up / down | Wh |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | w21532 | first | boburner | 19:41:26 | 19:52:32 | 19:57:52 | 11.10 | 5.33 | 150 from 235,320,000 | +0.44 +/- 0.37, 150 | +0.44 +/- 0.37 z 1.19, 150 | - / - | 10.56 |
| 2 | e22790 | read | whitewolf | 19:58:17 | 19:59:47 | 20:06:16 | 1.49 | 6.49 | 75 from 322,790,000 | +0.90 +/- 0.57, 75 | +0.58 +/- 0.31 z 1.86, 225 | - / fortressisles2 | 14.18 |
| 3 | e22794 | read | boburner | 20:07:27 | 20:09:12 | 20:13:39 | 1.74 | 4.45 | 113 from 322,794,000 | +0.54 +/- 0.46, 113 | +0.56 +/- 0.26 z 2.20, 338 | europe / fortressisles2 | 8.82 |
| 4 | e22799 | read | macmini | 20:14:13 | 20:16:56 | 20:20:27 | 2.70 | 3.52 | 172 from 322,799,000 | +0.79 +/- 0.40, 172 | +0.63 +/- 0.22 z 2.92, 510 | - / - | 1.73 |
| 5 | e22801 | read | calber | 20:20:34 | 20:21:51 | 20:32:11 | 1.27 | 10.34 | 172 from 322,801,000 | +0.49 +/- 0.38, 172 | +0.60 +/- 0.19 z 3.17, 682 | - / - | 24.27 |
| 6 | h1503-p1 | held | boburner | 20:32:44 | 20:33:57 | 20:38:03 | 1.21 | 4.10 | 100 from 360,600,000 | +1.20 +/- 0.49, 100 |  | fortressisles2 / - | 8.12 |
| 7 | h1503-p2 | held | macmini | 20:32:47 | 20:35:41 | 20:37:47 | 2.90 | 2.11 | 100 from 360,600,100 | +0.01 +/- 0.45, 100 |  | - / fortressisles2 | 1.04 |
| 8 | h1503-p3 | held | saskatchewan | 20:32:49 | 20:36:14 | 20:41:04 | 3.41 | 4.84 | 100 from 360,600,200 | +0.67 +/- 0.46, 100 |  | europe / - | 14.98 |
| 9 | h1503-p4 | held | saskatchewan-2 | 20:32:52 | 20:36:37 | 20:41:44 | 3.74 | 5.11 | 100 from 360,600,300 | +0.73 +/- 0.59, 100 |  | - / - | 0.0 |
| | **h1503 merged** | held | (4 pieces) | | | 20:42:07 | | | 400 asked | +0.56 +/- 0.26, 376 | +0.56 +/- 0.26 z 2.15, 376 | - / - | |
| 10 | h1504-p1 | held | boburner | 20:42:19 | 20:43:44 | 20:47:47 | 1.41 | 4.04 | 100 from 360,800,000 | -0.11 +/- 0.47, 100 |  | - / - | 7.99 |
| 11 | h1504-p2 | held | macmini | 20:42:22 | 20:45:13 | 20:47:16 | 2.85 | 2.05 | 100 from 360,800,100 | +0.60 +/- 0.48, 100 |  | proving / - | 1.01 |
| 12 | h1504-p3 | held | macmini | 20:42:24 | 20:47:19 | 20:49:24 | 4.91 | 2.08 | 100 from 360,800,200 | +0.82 +/- 0.39, 100 |  | constanine / flame-war-modified, proving | 1.02 |
| 13 | h1504-p4 | held | boburner | 20:42:27 | 20:47:50 | 20:51:50 | 5.38 | 4.00 | 100 from 360,800,300 | +0.22 +/- 0.55, 100 |  | - / - | 7.92 |
| | **h1504 merged** | held | (4 pieces) | | | 20:51:56 | | | 400 asked | +0.28 +/- 0.25, 376 | +0.41 +/- 0.18 z 2.30, 752 | island / - | |
| 14 | h1505-p1 | held | macmini | 20:52:08 | 20:54:15 | 20:56:16 | 2.11 | 2.02 | 100 from 361,000,000 | +0.39 +/- 0.44, 100 |  | constanine / - | 0.99 |
| 15 | h1505-p2 | held | macmini | 20:52:11 | 20:56:28 | 20:58:29 | 4.28 | 2.02 | 100 from 361,000,100 | +0.65 +/- 0.59, 100 |  | - / - | 0.99 |
| 16 | h1505-p3 | held | boburner | 20:52:14 | 20:56:30 | 21:00:30 | 4.27 | 4.00 | 100 from 361,000,200 | +1.65 +/- 0.58, 100 |  | europe, fortressislesx, generated / - | 7.92 |
| 17 | h1505-p4 | held | macmini | 20:52:17 | 20:58:33 | 21:00:40 | 6.26 | 2.13 | 100 from 361,000,300 | +0.12 +/- 0.52, 100 |  | flame-war-modified / proving | 1.05 |
| | **h1505 merged** | held | (4 pieces) | | | 21:00:41 | | | 400 asked | +0.62 +/- 0.28, 376 | +0.47 +/- 0.15 z 3.13, 1128 | fortressislesx / - | |
| 18 | f0345 | families | calber | 21:00:56 | 21:01:18 | 21:02:06 | 0.36 | 0.81 |  |  |  |  | 1.92 |
| 19 | gx0084 | other | macmini | 21:02:32 | 21:03:46 | 21:03:50 | 1.23 | 0.07 |  |  |  |  | 0.03 |
| 20 | r0337-promote | promote | macmini | 21:05:15 | 21:06:54 | 21:07:42 | 1.65 | 0.81 |  |  |  |  | 0.41 |

Builds of 81e0df3 (chain "build 81e0df3"):

| job | lane | started | ended | run min | Wh |
|---|---|---|---|---|---|
| prep-columbia-81e0df3 | columbia | 21:10:34 | 21:11:37 | 1.06 | 0.29 |
| prep-calber-81e0df3 | calber | 21:12:06 | 21:12:31 | 0.41 | 0.93 |
| prep-macmini-81e0df3 | macmini | 21:12:37 | 21:12:51 | 0.24 | 0.1 |
| prep-boburner-81e0df3 | boburner | 21:12:52 | 21:13:12 | 0.32 | 0.63 |
| prep-saskatchewan-81e0df3 | saskatchewan | 21:13:49 | 21:14:23 | 0.57 | 1.81 |
| prep-whitewolf-81e0df3 | whitewolf | 21:16:27 | 21:16:54 | 0.46 | 0.99 |

The line proof (chain "line 81e0df3"; main's values read as a trial against the line, so the line's lead is -d):

| job | lane | queued | started | ended | wait min | run min | seeds (block) | line lead this job | pooled lead after | line ahead / behind (2 se, pooled) | Wh |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pv0499 | saskatchewan | 21:20:15 | 21:21:32 | 21:40:10 | 1.27 | 18.63 | 400 from 799,800,000 | +0.43 +/- 0.61 | +0.43 +/- 0.61 z 0.70, 400 | industry / constanine | 58.8 |
| pv0500 | saskatchewan-2 | 21:20:18 | 21:22:07 | 21:40:26 | 1.80 | 18.32 | 400 from 800,000,000 | +0.64 +/- 0.64 | +0.53 +/- 0.44 z 1.20, 800 | - / - | 0.0 |
| pv0501 | macmini | 21:20:21 | 21:22:16 | 21:29:32 | 1.90 | 7.27 | 400 from 800,200,000 | +1.44 +/- 0.61 | +0.84 +/- 0.36 z 2.36, 1200 | proving, europe / - | 3.64 |
| pv0502 | boburner | 21:20:24 | 21:24:05 | 21:37:06 | 3.67 | 13.00 | 400 from 800,400,000 | +0.35 +/- 0.56 | +0.70 +/- 0.30 z 2.32, 1600 | fortressislesx, proving, europe / fortressisles2 | 26.1 |
| pv0503 | macmini | 21:20:27 | 21:29:35 | 21:36:54 | 9.13 | 7.32 | 400 from 800,600,000 | +0.57 +/- 0.59 | +0.67 +/- 0.27 z 2.51, 2000 | fortressislesx, proving / - | 3.67 |
| pv0504 | macmini | 21:20:30 | 21:36:57 | 21:44:17 | 16.45 | 7.33 | 400 from 800,800,000 | +0.47 +/- 0.56 | +0.64 +/- 0.24 z 2.62, 2400 | fortressislesx, proving / - | 3.67 |
| pv0505 | macmini | 21:45:43 | 21:47:29 | 21:54:45 | 1.76 | 7.28 | 400 from 801,000,000 | +0.07 +/- 0.55 | +0.54 +/- 0.22 z 2.45, 2800 | fortressislesx, proving / - | 3.65 |
| pv0506 | saskatchewan | 21:45:46 | 21:47:29 | 22:06:05 | 1.71 | 18.61 | 400 from 801,200,000 | +0.24 +/- 0.57 | +0.50 +/- 0.21 z 2.44, 3200 | fortressislesx, proving / - | 58.73 |
| pv0507 | saskatchewan-2 | 21:45:49 | 21:47:42 | 22:06:09 | 1.88 | 18.46 | 400 from 801,400,000 | +0.49 +/- 0.61 | +0.50 +/- 0.20 z 2.57, 3600 | flame-war-modified, fortressislesx, proving / - | 0.0 |
| pv0508 | boburner | 21:45:51 | 21:48:03 | 22:00:57 | 2.19 | 12.89 | 400 from 801,600,000 | +1.17 +/- 0.62 | +0.56 +/- 0.19 z 3.02, 4000 | flame-war-modified, fortressislesx, proving / constanine | 25.87 |
| pv0509 | macmini | 21:45:54 | 21:54:50 | 22:02:06 | 8.93 | 7.28 | 400 from 801,800,000 | +1.44 +/- 0.58 | +0.65 +/- 0.18 z 3.63, 4400 | flame-war-modified, fortressislesx, proving, europe / - | 3.65 |
| pv0510 | boburner | 21:45:57 | 22:01:09 | 22:14:00 | 15.19 | 12.85 | 400 from 802,000,000 | +0.59 +/- 0.59 | +0.64 +/- 0.17 z 3.77, 4800 | flame-war-modified, fortressislesx, proving, europe / constanine | 25.8 |
| pv0511 | saskatchewan | 22:16:14 | 22:18:07 | 22:36:32 | 1.88 | 18.42 | 400 from 802,200,000 | +0.13 +/- 0.57 | +0.60 +/- 0.16 z 3.67, 5200 | flame-war-modified, fortressislesx, proving, europe / constanine | 58.12 |
| pv0512 | macmini | 22:16:16 | 22:19:05 | 22:26:22 | 2.80 | 7.28 | 400 from 802,400,000 | +1.84 +/- 0.63 | +0.68 +/- 0.16 z 4.29, 5600 | flame-war-modified, fortressislesx, proving / constanine | 3.65 |
| pv0513 | boburner | 22:16:19 | 22:19:28 | 22:32:21 | 3.14 | 12.90 | 400 from 802,600,000 | +0.20 +/- 0.56 | +0.64 +/- 0.15 z 4.22, 6000 | fidos-airstrip, flame-war-modified, fortressislesx, proving / constanine | 25.88 |
| pv0514 | saskatchewan-2 | 22:16:22 | 22:20:56 | 22:38:57 | 4.56 | 18.02 | 400 from 802,800,000 | +0.04 +/- 0.58 | +0.60 +/- 0.15 z 4.10, 6400 | flame-war-modified, fortressislesx, europe / constanine | 0.0 |
| pv0515 | macmini | 22:16:24 | 22:26:25 | 22:33:50 | 10.00 | 7.41 | 400 from 803,000,000 | -0.26 +/- 0.58 | +0.55 +/- 0.14 z 3.87, 6800 | flame-war-modified, fortressislesx, europe / - | 3.71 |
| pv0516 | boburner | 22:16:27 | 22:32:25 | 22:45:09 | 15.96 | 12.74 | 400 from 803,200,000 | +1.15 +/- 0.55 | +0.59 +/- 0.14 z 4.27, 7200 | flame-war-modified, fortressislesx, proving, europe / - | 25.57 |

Queued times are the queue file's own stamp (`done/SEQ-ID.json`: SEQ is the epoch in ms when the keeper
queued it, set back 10^11 for a high-priority job, `tools/fleet-queue.py` line 231). Started and ended are
`events.jsonl`. Wait = started - queued. Results are each job's `results/ID/fleet/q-grove/out/ID/*/pooled.txt`;
"pooled after" pools by inverse variance as the planner's `pool()` does. Wh is the model described in section 7.
No job of the chain was requeued or failed.

## 4. Totals: where the 3 hours 6 minutes went

**First ask to promotion: 19:41:26 to 21:07:42 = 86.3 minutes.** On the critical path (each link's slowest job):

| | minutes | share |
|---|---|---|
| running | 43.0 | 50% |
| waiting in the queue for a lane | 37.0 | 43% |
| between a job's return and the next ask (planner passes, a decision) | 5.8 | 7% |
| the keeper adding a held read's four pieces | 0.4 | |

Link by link (gap before it / queue wait / run, minutes): first read 0 / 11.1 / 5.3; e22790 0.4 / 1.5 / 6.5;
e22794 1.2 / 1.8 / 4.5; e22799 0.6 / 2.7 / 3.5; **e22801 (the duplicate) 0.1 / 1.3 / 10.3**; h1503 0.6 / 3.8 / 5.1;
h1504 0.6 / 5.4 / 4.0; h1505 0.3 / 6.3 / 2.1; families 0.3 / 0.4 / 0.8; gauntlet 0.4 / 1.2 / 0.1; promote 1.4 / 1.7 / 0.8.

**Promotion to main: 21:07:42 to 22:47:05 = 99.4 minutes**: approval 0.8; waiting for and running the builds of
81e0df3 11.7 (2.0 + 6.3 + 3.4 until the pass saw them built everywhere); proof rounds 24.0 + 28.3 + 28.9 = 81.2;
the passes between rounds and the verdict 5.6. Inside each round the slowest lane runs back to back (round 1:
macmini ran pv0501, pv0503, pv0504; rounds 2 and 3: boburner ran two each), so of the 81.2 minutes about 73 are a
lane running proof seeds and about 8 a round's first wait for a lane.

**First ask to main: 185.7 minutes** (3 h 05 m 39 s). Running on the critical path about 116 minutes, waiting
about 70.

Why it waited, in order of size:
1. **The proof needs 7,200 seeds on four lanes** (81 minutes): three rounds, because round 1 was under z 3.0 and
   round 2 was held by constanine.
2. **The queue turn of the first read** (11.1 minutes): it was a normal-priority trial behind high-priority
   read-ons and earlier trials.
3. **Fast lanes shared with r0336's proof** (the held reads' 3.8, 5.4 and 6.3 minute waits): pv0497 and pv0498
   held saskatchewan and saskatchewan-2 from 20:41 to 21:00.
4. **The duplicate read-on** (about 11.6 minutes of wall time, section 2).
5. **Build** of the new line (11.7 minutes before the proof could be asked).
6. Planner-pass latency is small here: 0.1 to 1.4 minutes a link (passes took 8.6 to 21.7 s; the read-ons wait
   for the regular pass, the held reads carry `replan`).

## 5. Paths not taken: the same generation's other trials

On the defaults 2a1a1e9 (15:38 to 21:08) the planner asked **120 trials**: 62 A/B versions, 40 far trials, 12
suggest.py draws, 3 carried passes, 3 old candidates read again. 36 were read on, 8 reached a held-out read, and
one passed: w21532. 21 played the very games of the defaults (+0.00 +/- 0.00). They took **258 jobs, 29.4
lane-hours, 30,038 seeds and about 3.0 kWh** (model) for one generation. Bars in force: keep z 0.25 / 0.55 /
0.85 / 1.15 / 1.45 at 150 / 225 / 338 / 510 / 750 seeds; pass z 2.1 at 510 and 750, 1.5 at 1,140; held-out z 2.5.

| trial | source | change | reads | why it stopped |
|---|---|---|---|---|
| w21529 | A/B | ladder 0 -> 1 (expand_before_hunt) | 150: +0.08 +/- 0.37; 225: +0.01 +/- 0.31, z 0.02 | under the 225-seed keep bar 0.55: dropped |
| w21531 | A/B | ladder 0 -> 2 (hunt_first) | 150: +0.00 +/- 0.00 | plays the very games of the defaults: nothing to read |
| w21541 | far, one dial / 1.41 | castle_road 2.0 -> 1.41844 | 510: +0.10 +/- 0.04, z 2.27 (passed 2.1); held h1502: +0.00 +/- 0.07 (376) | held-out z 0.0, under 1.0: not read again; dropped (and +0.10 is under the 0.25 a generation is worth) |
| w21511 | A/B | bio square -> sine | 1,140: +0.39 +/- 0.22, z 1.77 (over the last bar 1.5) | europe -0.84 +/- 0.37, a map two errors under, blocks the pass |
| w21456 | carried pass of w21243 (a suggest.py draw) | bio_amount 0.330678, ore_reach 10, strikes_max 4, w_pos_expand 0.1 | 150: +2.48 +/- 0.75, z 3.31; held h1491: -0.28 +/- 0.46 | held-out read under 1.0: dropped |
| w21508 | old candidate w12077 read again (a far trial of 6 Nov) | w_smooth 0.525 | 150: +1.47 +/- 0.93; two held reads pooled -0.69 +/- 0.45 (752), naval and proving under | held-out under: dropped |
| w21473 | suggest.py, a draw from the fit's uncertainty | alpha 0.214489, odds_r 15.1916, ping_defend_hold 0.75, ping_help_reach 51.5291 | 750: +0.36 +/- 0.40, z 0.89 | under the 750-seed keep bar 1.45 |
| w21464 | far, one dial x 1.41 | alpha 0.347728 | 150: +2.28 +/- 1.03, z 2.21; 338: +0.38 +/- 0.70, z 0.54 | a lucky first read regressed; under 0.85 |
| w21474 | A/B | caps -dodge | 150: -8.11 +/- 0.99 | dropped at the first read |
| w21506 | A/B | advance_plan forward -> as_built | 150: -3.20 +/- 0.68 | dropped at the first read |

(The "change" column gives the trial file's values; for far trials the "from" is the planner's "today's" value,
which I did not look up except castle_road's 1/1.41 relation.) Source: `results/wNNNNN/.../trial.weights` and
`pooled.txt`, read-ons by title in `plan/done-titles.json`; my script is `siblings.py` beside this file, rows in
`siblings-2a1a1e9.json`.

## 6. The generation's place in the series

**Generations lately** (line promotions from `plan/runs/rNNNN/state.json`; main's moves from the reflog via
`outgrowing.py`):

| day | onto the line | main moved | came off (orphaned) |
|---|---|---|---|
| 13 Nov | r0323, r0326, r0332, r0333 | 13:44 `394c4ac` (r0332, w_smooth) | 09:26: ten (r0220 to r0326); 20:06: r0333 |
| 14 Nov | r0334 | 16:46 `f5794cc` (r0334) | |
| 15 Nov | r0335, r0336, **r0337** | **22:47 `81e0df3` (r0336 + r0337)** | 07:33: r0335 |
| 16, 17 Nov | none | | |
| 18 Nov | r0338 | | 23:22: r0338 (+0.07 +/- 0.04 over 9,600) |
| 19 Nov (to 17:00) | none | | |

Nine generations onto the line from 13 to 19 November: four reached main in three moves (r0332, r0334, and
r0336 with r0337), five came off (r0323 and r0326 in the batch of ten on 13 Nov, r0333, r0335, r0338). About
1.3 line generations a day, 0.6 to main a day. No line generation for 72 hours after r0337, and main has stood
at 81e0df3 for 90 hours.

**The bar at the time**: ease 0.5, so the held-out bar was pooled z 2.5 and the sequential pass bars z 2.1 / 1.5.
This is inferred from the ratchet's rule (r0336 seen about 15:38 lowered the base to 0.45; four hours dry put it
back at the 0.5 ceiling about 19:38), not from a log of that hour. Today `plan/pipeline.json` reads ease 0.5,
held_z 2.5, base 0.4. The line proof's bar is z 3.0 without ease, plus no map two errors under, and a line is
orphaned if its lead plus two errors is under 0.25 after 9,600 seeds.

**What the line gained over main**: the proof of 81e0df3, **+0.59 +/- 0.14 a seat over 7,200 seeds, z 4.27**.
That is r0336 and r0337 together. r0336's line alone (2a1a1e9) read **+0.15 +/- 0.08 over 20,000 seeds**
(z 1.85, pv0449 to pv0498); w21532's own held reads were +0.47 +/- 0.15. The two promotions claimed 1.93 by their
last held reads (1.31 + 0.62; outgrowing.py's "claimed") or about 1.48 by their pooled held reads (+1.00 + 0.47);
main kept 0.59, a third to two-fifths of the claim.

**Generational increase on the fixed yardstick** (`plan/rating.json`: today's defaults against main of fixed
days, 2,000 seeds, the same seeds every day):

| read at | today's | vs main of 28 Oct | vs 2 Nov | vs 6 Nov |
|---|---|---|---|---|
| 15 Nov 12:11 | f5794cc (before) | +7.52 +/- 0.27 | +6.92 +/- 0.25 | +5.27 +/- 0.26 |
| 16 Nov 13:21 | 81e0df3 (after) | +8.18 +/- 0.27 | +7.44 +/- 0.26 | +5.19 +/- 0.26 |
| 17 Nov 14:28 | 81e0df3 | +8.13 +/- 0.28 | +7.33 +/- 0.25 | +5.22 +/- 0.26 |
| 18 Nov 15:41 | 81e0df3 | +8.22 +/- 0.27 | +7.43 +/- 0.26 | +5.24 +/- 0.26 |
| change across the generation | | **+0.66** | **+0.52** | **-0.09** |

On fixed seeds 81e0df3 repeats within 0.11 from day to day, so the +0.66 and +0.52 are larger than that
repeat; against 6 Nov's main there is no change. Two of three yardsticks agree with the proof's +0.59.

## 7. Energy

The model is the planner's (`plan/timeline-bins.json`, the `tally` of 2026-11-15): each job's lane at its
busy watts for the seconds it ran. The 15 Nov rates are boburner 118.8 W, macmini 29.5, calber 140.9, whitewolf
131.2, saskatchewan 185, columbia 18.3, and **saskatchewan-2 0 W** (the box's watts are booked to its first lane,
so 59.9 lane-minutes of this story count nothing).

| part | lane-minutes | Wh (model) |
|---|---|---|
| trial chain to promotion (20 jobs) | 70.3 | 115.0 |
| of it, the duplicate read-on e22801 | 10.3 | 24.3 |
| builds of 81e0df3 (6) | 3.1 | 4.8 |
| line proof (18) | 226.0 | 330.5 |
| **first ask to main** | 299.4 | **450.3 Wh, about $0.08 at $0.17/kWh** |
| the whole generation's 120 trials (for comparison) | 1,764 | about 3,035 |
| r0336's line proof, which r0337's line replaced (50 jobs) | 636 | about 921 |

A job's Wh is in each row of section 3. `QUEUE/hearth/energy.json` covers 17 to 19 Nov only (Wh a job: boburner
14.89, calber 20.43, columbia 4.74, saskatchewan 7.57, whitewolf 28.56, bosporus 47.91, jaguaribe 36.59; no
macmini), so it cannot price these jobs; the timeline bins can.

## 8. Putting this chain on Orrery's Timeline and Lineup

**The live `plan/pipeline.json` cannot show it.** Its timeline holds the jobs of the last six hours only
(`TIMELINE_H = 6` in the planner; its chains run w23465 to w23725 now), and the day/days/weeks zooms are bins by
stage with no chain in them. So I built a scratch state as the planner would have written it at 15 Nov 22:50:
`pipeline-w21532.json` (made by `frame_state.py`, both beside this file): the live file with its `timeline`
replaced by the 3.5 hours 19:20 to 22:50 from `events.jsonl` (11 lanes, 233 jobs, each with its chain by the
planner's own `chain_of` and its Wh), chain verdicts as `chain_meta` would give them (w21532 "promoted as r0337,
and on main"; "line 81e0df3" kind proof, good null; "build 81e0df3" good), and the live marks moved to that clock.
`zoom` and `power` are left out, so only the hour and hours zooms draw and no watts strip. Not rendered.

```
STATE=/private/tmp/claude-501/-Users-user-code-orrery/89899697-6c64-4d98-9801-4f537869abbe/scratchpad/pipeline-w21532.json
cd /Users/user/code/orrery
# Timeline, following the chain
ORRERY_FRAME_OPERATOR=1 ORRERY_FRAME_PAGE=2 ORRERY_FRAME_CHAIN=w21532 ORRERY_FRAME_ZOOM=hours \
  target/release/orrery --operator paul --fleet grove --frame timeline.ppm --frame-view pipeline --frame-state $STATE --frame-size 1600x1000
# Lineup, the trial's row alone
ORRERY_FRAME_OPERATOR=1 ORRERY_FRAME_PAGE=6 ORRERY_FRAME_CHAIN=w21532 ORRERY_FRAME_LINEUP=trials ORRERY_FRAME_LINEUP_END=won \
  target/release/orrery --operator paul --fleet grove --frame lineup.ppm --frame-view pipeline --frame-state $STATE --frame-size 1600x1000
# Lineup, the proof's row
ORRERY_FRAME_OPERATOR=1 ORRERY_FRAME_PAGE=6 ORRERY_FRAME_LINEUP=runs ORRERY_FRAME_LINEUP_END=going ...same flags
```

Notes on the flags (`src/main.rs` lines 934 to 948, `src/pipeline.rs` 65, 2366, 2367):
- `ORRERY_FRAME_LINEUP_END` is **a name, not a time**: `every end`, `going`, `won` or `dead ends`. Anything else
  falls back to `every end`. The comment in `tools/report/orreryq-shots.list` ("LINEUP_END=epoch seconds ends the
  Lineup there") does not match the code.
- `ORRERY_FRAME_LINEUP` is `trials`, `runs`, `builds`, `islands` or `all`. The proof chain is kind `proof`, which
  the Lineup files under `runs`; its verdict is null as the planner writes it, so it sits under `going`.
- `ORRERY_FRAME_ZOOM` serves both pages: the Timeline takes hour/hours/day/days/weeks/months (unset = hours, the
  file's `past_h`); the Lineup takes only hour/hours, and unset means "each its own", which fits a three-hour chain.
- `tools/report/double-shots.sh` fixes `P=$Q/plan/pipeline.json`, so the `CHAIN=` lines of `orreryq-shots.list`
  draw from the live file and will not find w21532; call the binary directly with `--frame-state` as above.
- The live marks put "main: w21532" at 21:07 (the commit's time); main actually moved at 22:47:00.

## 9. What I could not find, and caveats

- **No promotion in the last three days reached main.** The only one, r0338 (18 Nov), was orphaned; the example
  is four days old.
- **The ease at the hour** is inferred from the ratchet's rule, not logged. The decisions do not depend on it:
  the sequential read was past both 2.1 and 2.15 at 510 seeds, and the held-out reads were read on and passed
  under either bar.
- **The cause of the duplicate read-on** is read from the code and the timings (a pass from about 20:20:24 to
  20:20:34, e22799 back at 20:20:27); there is no log line that says it. Planner passes log only their length.
- **Energy is the planner's model**, not a meter; saskatchewan-2 counts 0 W, and the Supermicros were not in this
  chain.
- **Queue order**: why the A/B ladder trials were asked at 19:41, four hours after the defaults changed, is the
  planner filling the queue a few trials a pass; I did not reconstruct the queue's contents at each pass.
- **Probe games are not identical between runs**: the same probe seed played twice in h1503's pieces gave slightly
  different rung times (fortify 32 vs 34 seat-seconds), both +0.00 on naval. I did not test this further.
- The far trials' "from" values in section 5 are not given except castle_road.
- The ratchet's `generations` counter (48) counts an orphaning as a new generation seen: after r0338 was orphaned
  the planner saw r0337 as new again and lowered the base from 0.45 to 0.4 (since 18 Nov 23:23, `last_gap_min`
  124). This is a side finding, read from `plan/state.json` and the code, not tested.

## 10. Sources

- `QUEUE/events.jsonl` (start, end, host, seconds of every job; planner passes)
- `QUEUE/done/*.json` (each job's command, seeds, queue stamp, host, seconds) and `QUEUE/plan/done-titles.json`
- `QUEUE/results/<job>/fleet/q-grove/out/<job>/*/pooled.txt` and `run.env` (every read's result, seeds, commit)
- `QUEUE/results/f0127, f0264, f0345` (the family verdicts), `results/r0337-promote/` (tests, families, floors, commit)
- `QUEUE/plan/runs/r0332 ... r0338/state.json` (promotion status, evidence, approved, orphaned, confirmed)
- `QUEUE/plan/state.json` (orphans, proof, difficulty), `QUEUE/flags/*.json` (candidate, promote, line, resolve, rating)
- `QUEUE/plan/rating.json` (the yardstick), `QUEUE/plan/timeline-bins.json` (energy tally),
  `QUEUE/plan/pipeline.json` (today's bars and the six-hour timeline), `QUEUE/hearth/energy.json`
- `tools/plans/treadcore.py` (SEQ, HELD_Z, ease, held_read, line_proof, orphan, chain_of, stage_of, sequential,
  timeline_view, chain_meta), `tools/fleet-queue.py` (queue stamp), treadcore `scripts/census.sh` (probes, maps),
  treadcore `git log` (81e0df3, 6a706cd)
- `tools/report/outgrowing.py` run read-only into `outgrowing/` beside this file (main's moves, turnaround, claims)
- My scripts beside this file: `pool.py`, `build.py`, `totals.py`, `siblings.py`, `frame_state.py`
