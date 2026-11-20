# One GPU generation, end to end: M0049-boburner-cuda-g138500

Read only, 19 November 2026, from the live queue `Q = /Users/user/code/treadcore/build/queue/grove` and the crucible source `/Users/user/code/treadcore/crucible/src/crucible.cu` (the copy the planner sends, `crucible_src()`; treadcore commit ab615a8). All times are the Mac's local time (PST). Nothing in the queue was changed and no fleet machine was contacted.

**In one paragraph.** No home has elected a milestone in the last three days. The most recent milestone of any home is **M0049-boburner-cuda-g138500** of the maze home `crucible-world-hybrid-forest-nav`, made 15 Nov 22:06:03, about 91 hours before this was written. One 100-generation segment, `x-boburner-cuda-1756`, made it on the GTX 1070 Ti in boburner. The segment waited 4 h 01 min in the GPU queue and ran 49.5 min. Its champion held every floor of the 24-file CUDA gauntlet and read **+1.99 z** on the weighed gauntlet against the standing milestone M0032, but the bar was 3.00, so the rule kept it. It became the window's best, and the planner **forced** it in as M0049 when three hours had passed since M0048. Forty-nine minutes later the game read it as the Gladiator at **-8.84 ± 1.22 a seat** under the shipped M0030 and refused it. The top rung went back to M0032, but **the floors M0049 raised stayed**. Of the 316 segments examined since then (about 206 GPU-hours), none has held those floors, so the home has made no generation since.

---

## A. The generation

### A1. Identity

| | | source |
|---|---|---|
| id | M0049-boburner-cuda-g138500 | `Q/crucible-world-hybrid-forest-nav/milestones/M0049-boburner-cuda-g138500.bin` |
| home | crucible-world-hybrid-forest-nav (the maze home: WORLD + HYBRID + FOREST + NAV, its parent the forest home) | `plan.json` crucible: world, hybrid, forest, nav true |
| island / card / machine | island `boburner-cuda` = the CUDA lane of **boburner**: NVIDIA GeForce GTX 1070 Ti, sm_61, 19 SMs, 1683 MHz, 8.5 GB | the segment's console |
| segment | `x-boburner-cuda-1756` (title "crucible island boburner-cuda, segment 1756"), one segment, after `x-boburner-cuda-1755` | `Q/done/1794783658403-x-boburner-cuda-1756.json` |
| generations | ran g138400 to g138499 (100), resumed from the island state 1755 saved at g138400, saved g138500 | console, `gens.tsv` |
| generation counter g | 138500, the island's cumulative generation count. boburner was at g112700 when the maze home made its first generation on 6 Nov, and was at g148500 on 19 Nov 16:43. | `growth.tsv` |
| bytes | 23,064 (5,766 float32), sha256 `de95e8ae08c9fc29…85097e4c88a`, identical in `milestones/`, `champions/x-boburner-cuda-1756.bin` and the segment's `champ.bin` | shasum |
| parent ("after") | M0032-calber-cuda-g291900, the newest milestone the game has not refused | `plan/state.json` `crucible_ladder:crucible-world-hybrid-forest-nav` |
| how elected | **forced**: "elected (3.0 h without a generation): the window's best, the gauntlet +1.99 z weighed, the yardstick +1.15 z, every floor held" | `Q/flags/1794809163390-crucible.json`; state entry `"elected": true, "zg": 1.99, "zy": 1.15` |
| the game's verdict | bridge 35: -8.84 ± 1.221 a seat as the Gladiator, against the shipped M0030. **Refused**, so it is no rung. | `plan/bridge.json` reads[n=35]; `Q/flags/1794812104438-*.json` |
| card | `Q/crucible-world-hybrid-forest-nav/milestones/M0049-boburner-cuda-g138500.card.json`, written 15 Nov 22:57. Its `"election": null` is there because a forced election writes no elect.tsv row of its own. | netcard.py |

### A2. Timeline

| when (15 Nov) | what | source |
|---|---|---|
| 14:57:16 | `x-boburner-cuda-1750` ends. The planner keeps six segments queued per island (`ahead` 6), so it asks for a new one. | events.jsonl |
| **15:00:58** | `x-boburner-cuda-1756` queued, after 1755 | the done file's ms prefix 1794783658403 |
| 19:01:51 | 1755 ends (g138400). Its champion becomes M0048 at 19:05:46 (forced). | events.jsonl, state |
| **19:01:54** | 1756 starts on boburner-cuda, after **241 min in the queue** | events.jsonl line 143432 |
| 19:01:54 to 19:51:23 | build-stamp check, load island.state (g138400; hall of fame 4,096), 3 imports and 3 migrants, 8 ladder rungs, then **100 generations in 2,587.1 s** (25.4 s each, about 20.8 M tank-steps/s, about 235 GFLOP/s), the exam (2,048 duels against each of 8 rungs and the yardstick), and the gauntlet (24 files × 256 runs, champion and M0032 on the same runs) | console.txt |
| 19:48:43 | the game refuses M0048 (-9.43 ± 1.18), so the top rung goes back to M0032 | bridge.json n=34 |
| **19:51:23** | 1756 done (2,968.8 s = 49.5 min) | events.jsonl line 143542 |
| **19:52:13** | Planner pass: 1756 is examined against M0032, the top rung. Result: "kept: the gauntlet +1.99 z (weighed by difficulty), the yardstick +1.15 z, head to head +0.5 se, against the bar 3.00". It holds every floor, so it becomes the window's best candidate. | elect.tsv line 844; lineage.tsv |
| 20:40:52, 21:30:26 | the next two boburner champions read +1.61 (holding) and +1.44 (under T3), so neither displaces 1756 | elect.tsv |
| **22:06:03** | **Forced election**: GPU_FORCE_H = 3.0 h have passed since M0048 with no generation, so the window's best (1756) is copied to `milestones/M0049-boburner-cuda-g138500.bin` | flag 1794809163390; `gpu_force()` treadcore.py:5241 |
| 22:06:04 | footage asked; bridge 35 asked (192 seeds on macmini) | flags 1794809164311-footage; bridge.json |
| 22:31:17 | footage filmed on calber: **96 of 96** (12 tests × 8 runs: n1 n3 m0 m1 m2 m3 b1 t1 t2 k1 k2 k3) | `Q/archive/footage/crucible-world-hybrid-forest-nav/M0049-boburner-cuda-g138500/result.json` |
| **22:55:04** | Bridge read: the team with M0049 as the Gladiator scores -12.17 ± 0.94 a seat against the defaults (z -12.95), and the shipped M0030's team -3.33 ± 0.78, a difference of **-8.84 ± 1.22**. The game refuses M0049, and the newest standing rung is M0032 again. | flags 1794812104438-bridge/-crucible |

Queued to refused: 7 h 54 min. In the queue: 4 h 01 min. On the card: 49.5 min. Waiting as the window's best: 2 h 14 min.

### A3. What the segment ran (the command)

From the done record's `cmd` (built by `crucible_jobs()`, treadcore.py:5789):

```
make HYBRID=1 WORLD=1 FOREST=1 NAV=1 H=48 R_ACCEL=4.0f R_BRAKE=6.0f R_CONCEAL_RANGE=3.0f R_DAMAGE=45.0f R_GUN_RANGE=10.0f
     R_HIT_R=0.8f R_HP=100.0f R_PB_DAMAGE=15.0f R_PB_HEALTH=60.0f R_PB_RANGE=8.0f R_PB_RELOAD=2.0f R_RELOAD=4.0f
     R_SCORE_CAPTURE_W=0.25f R_SCORE_HOLD_W=0.02f R_SHELLS=24.0f R_SSPEED=40.0f R_TURN=3.0f R_VISION=10.0f R_VMAX=4.0f
./crucible --pop 2048 --eps 256 --gens 100 --yard 10 --seed 32137 --lad 0.2 --draw -1.0 --load $H/island.state
     --import  $H/in/calber-cuda.bin,$H/in/whitewolf-cuda.bin,$H/in/game.bin
     --migrate $H/in/calber-cuda.bin,$H/in/whitewolf-cuda.bin,$H/in/game.bin
     --ladder  rungs/M0001…,M0007…,M0013…,M0023…,M0024…,M0030…,M0031…,M0032-calber-cuda-g291900.bin
     --save $H/island.state --export $O/champ.bin --out $O/gens.tsv --exam $O/exam.tsv
     --tasks $H/gauntlet --task-p 0.5 --gauntlet $H/gauntlet --gauntlet-runs 256 --gauntlet-out $O/gauntlet.tsv
     --gauntlet-ref rungs/M0032-calber-cuda-g291900.bin
```

**What it trained against.**

- **The population.** 2,048 nets of boburner's own lineage, kept on the card's machine in `island.state` between segments. The lineage has been widened three times, each new weight starting at zero: hybrid 35-32-32-4, then the world's 55-48-48-4 (3 to 4 Nov), then the maze's 64-48-48-6 (6 Nov).
- **The imports and migrants.** Three nets went into the hall of fame as opponents and into the population's last places as possible parents (crucible ab615a8, 13 Nov):
  - calber's latest champion, by timing `x-calber-cuda-3715` (g316600);
  - whitewolf's latest, by timing `x-whitewolf-cuda-2637` (g222300);
  - `game.bin` = **M0030-calber-cuda-g290500**, the net the game ships as the Gladiator.

  The console reads "imported 3 champion(s) into the hall of fame (4096 there)" and "3 migrant(s) joined the population of 2048".
- **One opponent per net per generation**, drawn per block (`play()`, crucible.cu:1576): with chance 0.5 a scripted sparring partner of random skill (aim tolerance 0.05 to 0.6 rad, stand-off 4 to 9 tiles, one of 5 styles: the script, Raider, Castle, Expander, Timid), with chance 0.2 one of the 8 ladder milestones, otherwise one from the 4,096-net hall of fame (half the time one of the newest 16). The champion joins the hall every 5 generations.
- **Tasks.** `--task-p 0.5`: half of each net's 256 threads (whole warps) play one of the gauntlet's 24 files instead of a duel. Every net gets the same file in a generation. Passing, closing on the goal and the score are paid. The task pass rate every 10 generations was 50.0, 75.0, 78.9, 72.9, 100.0, 97.2, 75.0, 55.0, 99.9 and 81.5%; it swings because one file is drawn for all. The files: B1, C1, C2, C7, C8, C19, C21, F1–F3, K1–K3, M0–M3, N0–N3, T1–T3 (`/Users/user/code/treadcore/crucible/gauntlet/*.toml`).
- **Score.** A win +2, a loss −2, a draw −1.0 (`--draw`), plus damage.
- **Rules.** Treadcore's `rules.rs` at the fleet commit 81e0df3, passed as the `R_` make variables above (`world_rules()`). The world has 4 pillboxes and 1,200 steps (120 s) a duel. The console summarises them as "speed 4 accel 4 brake 6 turn 3; armour 100, 24 shells; gun 10 tiles at 40/s for 45 every 4 s, hit radius 0.8; vision 10; pillboxes 8 tiles for 15 every 2 s, health 60".
- **Selection** (crucible defaults, not overridden). The 16 best (elite) are copied unchanged. The other 2,032 are children of the top quarter (512), every weight nudged by a Gaussian of σ = 0.03. The exported champion is individual 0 after the last breed, the best of generation 138499.
- **The dice.** `--seed 32137` is boburner's fixed island seed (1000 + 97 × (sum of the name's characters mod 1000)). It is mixed with the generation number in every hash, so each generation's dice differ but can be reproduced.
- **Every 10 generations (`--yard 10`).** The champion plays the scripted yardstick. Win/draw/loss went from 0.65/0.28/0.06 at g138409 to 0.65/0.28/0.07 at g138499. Its score against the whole ladder was 0.12 to 0.23 and against the top rung −0.06 to +0.03. "The net overrode the rules" on 84.0 to 85.0% of steps; that is the whole population's training, tasks included.

### A4. The exam and the gauntlet

**Exam** (`exam.tsv`, 2,048 duels each, win/draw/loss): the yardstick 0.655/0.281/0.064; the yardstick as M0032 plays it 0.638/0.286/0.076; M0001 0.753/0.205/0.042; M0007 0.375/0.502/0.124; M0013 0.050/0.896/0.054; M0023 0.293/0.640/0.067; M0024 0.371/0.566/0.063; M0030 0.123/0.813/0.065; M0031 0.100/0.831/0.070; **M0032 0.068/0.868/0.064**. Head to head with M0032 that is (w − l)/se = **+0.49 se**, and the ladder mean (w − l) is +0.198.

**Gauntlet** (`gauntlet.tsv`, 256 runs a file, the champion and M0032 on the same runs). The mean share is champion 0.810 against M0032 0.801. Paired, the champion is +0.0088 ± 0.0024 over 6,144 runs: 138 runs only the champion passed, 84 only M0032.

| file | M0049 | M0032 | floor it faced (M0048's share − 1/16) | floor after M0049 (now) |
|---|---|---|---|---|
| B1 breach the walled base | 1.000 | 1.000 | 0.9375 | 0.9375 |
| C1 fire at an enemy in reach | 1.000 | 1.000 | 0.9375 | 0.9375 |
| C2 an enemy behind | 1.000 | 1.000 | 0.9375 | 0.9375 |
| C7 a pillbox from outside its ring | **0.242** | 0.277 | 0.1836 | **0.1797** |
| C8 out of a pillbox's ring | 0.863 | 0.891 | 0.8281 | 0.8008 |
| C19 two pillboxes, one at a time | 0.000 | 0.000 | 0 | 0 |
| C21 alone: kite | 0.000 | 0.000 | 0 | 0 |
| F1 into the trees | 0.000 | 0.000 | 0 | 0 |
| F2 round the trees | 1.000 | 1.000 | 0.9375 | 0.9375 |
| F3 the lurker in the trees | 0.348 | 0.324 | 0.2852 | 0.2852 |
| K1 / K2 / K3 camps | 1.000 each | 1.000 each | 0.9375 | 0.9375 |
| M0 / M1 / M2 mazes, take the pillbox | 1.000 each | 1.000 each | 0.9375 | 0.9375 |
| M3 the @ maze, take the pillbox | 0.996 | 1.000 | 0.9375 | 0.9336 |
| N0–N3 mazes, reach the end | 1.000 each | 1.000 each | 0.9375 | 0.9375 |
| T1 take a pillbox | 1.000 | 0.941 | 0.9375 | 0.9375 |
| T2 take the base | 1.000 | 1.000 | 0.9258 | 0.9375 |
| T3 build a base: take and hold | **0.980** | 0.785 | 0.9023 | **0.9180** |

The weighed step (`gpu_step()`, treadcore.py:5172), recomputed here exactly. Each file's weight is 0.25 + 0.75 × (1 − M0032's share), and z = Σ w(b − c)/n ÷ √Σ w²(b + c)/n². Only six files had discordant runs:

| file | only M0049 (b) | only M0032 (c) | weight | w(b − c)/n |
|---|---|---|---|---|
| C7 | 58 | 67 | 0.792 | −0.0278 |
| C8 | 0 | 7 | 0.332 | −0.0091 |
| F3 | 11 | 5 | 0.757 | +0.0177 |
| M3 | 0 | 1 | 0.250 | −0.0010 |
| T1 | 15 | 0 | 0.294 | +0.0172 |
| T3 | 54 | 4 | 0.411 | +0.0803 |

The sum is 0.0774 and the σ is 0.0390, so **zg = +1.99**. The total b − c is +54. The yardstick z on the same seeds is (0.6553 − 0.6382)/se = **+1.15**. Almost the whole step is T3, building and holding a base, where M0049 passed 251 of 256 runs and M0032 201.

### A5. The election, and what it changed

- **By rule.** It held every floor and was no worse on the yardstick (guard), but zg 1.99 < bar 3.00 and zy 1.15 < 3.00. Head to head was +0.49 se, under the old rule's 2. So the rule kept it, and since it held, it became the window's best.
- **Forced.** `gpu_force()`: when GPU_FORCE_H = 3.0 h pass with no generation, the window's best is elected. "The window's best" means the largest weighed step among candidates that held every floor and the guard with zg > 0, examined against the current top. M0048 was made 19:05:46, and 22:06:03 is 3.0 h later.
- **What the election did** (`gpu_elected()`). The bar was raised a notch, capped at its maximum 3.00 (it has since eased, 0.25 a dry hour, to its minimum 1.00). **Every floor was reset to M0049's own share less 1/√256 = 0.0625.** That made C7 0.1797 and T3 0.918, the floors in force today. The window's best was cleared.
- **What the game did.** The bridge refused M0049 49 minutes later. `ladder_top()` skips refused milestones, so the rung segments must beat went back to M0032, **but the floors were not reset**. M0032 itself scores T3 0.785, under today's T3 floor of 0.918, so the standing top could not be elected under the floors its refused successor left. This is the lock described in A7.
- **The rules in force** (treadcore.py:5110–5117 and 5017): GPU_BAR_START 2.0, MIN 1.0, MAX 3.0; +0.25 after a generation; −0.25 for every dry hour; forced after 3.0 h dry; small trades allowed at 2.0 over the bar; floor = share − 1/√n; FLOOR_GIVE 0.05 (the CPU line's).

### A6. How champions and seeds move

1. **Within an island, segment to segment.** The whole population (2,048) and the hall of fame (4,096) live in `~/fleet/q-grove/crucible-world-hybrid-forest-nav/island.state` on boburner. Each segment holds a lock, loads that file, runs 100 generations and saves it. 1756 began from what 1755 saved at g138400. The Mac never holds the population, only each segment's champion.
2. **Island to island.** At each dispatch the keeper sends the other islands' newest champions (`Q/…-nav/latest/NAME.bin`), unless `island_refused()` applies: an island whose last three milestones read by the game were all refused. **boburner is refused**, so its champions are sent to nobody. x-calber-cuda-3717 imported whitewolf and game.bin only, and x-whitewolf-cuda-2639 imported calber and game.bin only, while boburner receives both of theirs. The net the game ships (M0030) goes to all three as `game.bin`. Every import is both an opponent (hall of fame) and a migrant (population).
3. **The ladder.** The ladder is up to 8 rungs: the newest four standing milestones and four older ones spread evenly, with refused milestones left out (`ladder_rungs()`). The rungs are opponents (chance 0.2), the exam, and, through the newest standing rung, the gauntlet's reference. Today's ladder (`ladder/ladder.txt`) is M0001, M0007, M0013, M0023, M0024, M0030, M0031, M0032, the same as 1756's.
4. **Home to home.** A new home starts with its parent's milestones as carried rungs and the parent's `island.state`, widened with zeros. The maze home began 6 Nov 15:57:55 from the forest home: M0001 to M0019 were carried, and M0020 is its first own milestone.
5. **To the game.** Every new milestone is read in treadcore as the Gladiator (style 17) on 192 seeds. It ships only if it is better than the shipped one by two errors. M0030 (10 Nov, +2.28 ± 0.98) is the last one credited; every milestone since stands below it or is refused.

### A7. Paths not taken

**The window M0048 → M0049** (19:05:46 to 22:06:03, lineage.tsv + elect.tsv):

| examined | segment | g | examined against | result |
|---|---|---|---|---|
| 19:13:17 | x-calber-cuda-3716 | 316700 | M0032 | not eligible: examined against M0032 while M0048 was the top (it was dispatched before the game refused M0048) |
| 19:17:56 | x-whitewolf-cuda-2638 | 222400 | M0032 | not eligible, same reason |
| 19:44:43 | x-calber-cuda-3717 | 316800 | M0048 | zg −11.92, under floors C7 0.00 < 0.18, M3 0.70 < 0.94, T3 0.71 < 0.90 |
| **19:52:13** | **x-boburner-cuda-1756** | **138500** | **M0032** | **zg +1.99, every floor held, under the bar 3.00: the window's best → M0049** |
| 20:00:08 | x-whitewolf-cuda-2639 | 222500 | M0048 | not eligible: examined against M0048, by then refused |
| 20:14:06 | x-calber-cuda-3718 | 316900 | M0048 | not eligible, same |
| 20:40:52 | x-boburner-cuda-1757 | 138600 | M0032 | zg +1.61, held, under the bar 2.75; smaller than 1.99 |
| 20:40:52 | x-whitewolf-cuda-2640 | 222600 | M0032 | zg −4.99, under C7 0.00 < 0.18 and T3 0.87 < 0.90 |
| 20:47:36 | x-calber-cuda-3719 | 317000 | M0032 | zg −5.38, under C7, T3 |
| 21:20:10 | x-calber-cuda-3720 | 317100 | M0032 | zg −6.16, under C7, T3 |
| 21:25:21 | x-whitewolf-cuda-2641 | 222700 | M0032 | zg −6.92, under C7, T3 |
| 21:30:26 | x-boburner-cuda-1758 | 138700 | M0032 | zg +1.44, under T3 0.90 < 0.90 (by a hair) |
| 21:50:50 | x-calber-cuda-3721 | 317200 | M0032 | zg −4.97, under C7, T3 |
| 22:06:03 | x-whitewolf-cuda-2642 | 222800 | M0032 | zg −5.52, under C7, T3 |

So 4 of the 14 were never eligible. The top flips to a new milestone and back within the hour the game takes to read it, and a segment's rung is fixed when it is dispatched. This happened in the window before M0048 too (x-calber-cuda-3710, x-boburner-cuda-1752, x-whitewolf-cuda-2634, 3713, 1753, 2636).

**Since M0049** (15 Nov 22:06 to 19 Nov 16:59). There were **316** examinations, **310** of them against the standing top M0032. **None held every floor.** Only three had zg > 0, all boburner, all just under T2 (0.90 to 0.93 < 0.9375):

- x-boburner-cuda-1761: +2.03
- x-boburner-cuda-1762: +0.79
- x-boburner-cuda-1764: +1.91

| island | examined | zg > 0 | held | zg mean (min, max) | mean gauntlet share |
|---|---|---|---|---|---|
| boburner-cuda | 92 | 3 | 0 | −5.80 (−13.67, +2.03) | 0.791 |
| calber-cuda | 126 | 0 | 0 | −6.13 (−12.16, −5.10) | 0.792 |
| whitewolf-cuda | 92 | 0 | 0 | −5.85 (−13.84, −4.61) | 0.793 |

The floors missed:

| island | C7 (floor 0.18) | T3 (floor 0.918) | other |
|---|---|---|---|
| calber | 126 of 126 | 126 | |
| whitewolf | 92 of 92 | 92 | |
| boburner | 87 of 92 | 87 | T2 8; M1 5; M3, M0 4 |

The islands now score C7 at 0.00 to 0.02. These floors are M0049's, a milestone the game refused, and they stay until a candidate meets them or a person asks for an election: with no candidate, `crucible elect` only waits. The GPU spent about **206 hours** on these segments: boburner 74.5 h, calber 65.5 h, whitewolf 65.7 h.

### A8. Waiting in the GPU queue (the `ahead` buffer)

Each island keeps **6 segments queued**, each `after` the one before (`crucible_jobs()`, `opt["ahead"]` default 6). A segment therefore waits about five of its island's segments: 1756 waited **241 min** (5 × about 48.5 min).

From queue (the done file's prefix) to start, for the segments started since M0049 (`segs-since.tsv` in the scratchpad):

| island | median wait | p10 / p90 | median run | segments started |
|---|---|---|---|---|
| boburner | 240 min | 96 / 254 | 48.0 min | 111 (93 done, 12 requeued, 3 failed) |
| calber | 153 min | 109 / 221 | 30.7 min | 145 (128 done, 14 requeued, 3 failed) |
| whitewolf | 210 min | 206 / 290 | 42.0 min | 104 (94 done, 9 requeued, 1 failed) |

Most of what a segment uses is fixed when it is queued: the island list it imports, its flags and its seed. The files themselves (the ladder slots, `latest/*.bin`, `game.bin`) are read when the keeper dispatches it. So a segment trains against the ladder as it stood about four hours before it ends.

### A9. What this home changed, and what is tested

**Changed for the maze home, relative to its parent, the forest home** (6 Nov; `docs/round-corner-lab-report.md` §III and §X; crucible.cu `NAV`, `ERRAND`):

- **9 inputs** (64 in all): the route (sine and cosine of the bearing to the next waypoint, the route's length, walled), three arcs of the tank's own projected motion (left, straight, right: the share of 1.5 s free), and **2 memory cells**.
- **2 outputs** (6 in all): the memory written back.
- **The rules' errand** (`ERRAND=1`): the hybrid's rules route by the arena's grid search, as the game's Commander does.
- **The maze, route, camp and breach files** in the gauntlet (M0–M3, N0–N3, K1–K3, B1), 24 files, also used as training tasks.

**Run options in force** (`Q/plan.json`, last written 13 Nov 08:56): gens 100, pop 2048, eps 256, yard 10, task_p 0.5, gauntlet_runs 256, ahead 6 (default). Left at crucible's defaults: elite 16, σ 0.03, every 5, cap 4096, spar 0.5, lad 0.2, draw −1.0.

**Changed home-wide on 13 Nov:**

- crucible ab615a8: imports become migrants.
- The planner: a milestone the game refuses is no rung, a refused island's champions are no migrants, and game.bin goes to every island.

Nothing changed in the M0048 → M0049 window: the rules were 81e0df3 and the build flags were identical.

**What is tested:**

- the CUDA gauntlet, every segment: 24 files × 256 runs, paired with the newest standing rung, weighed by difficulty, with floors;
- the yardstick, 2,048 duels, every segment;
- the ladder exam, 8 × 2,048 duels;
- footage, at election: 12 files × 8 runs, filmed;
- the bridge, at election: a census in the real game, 192 seeds.

No ablation or controlled arm tests the maze senses on the fleet. The only controlled test is the four 30-generation arms of 6 Nov in the round-corner report.

### A10. The ladder over time: generations, and the lack of them

Milestones made by each home, its own and not carried (`plan/state.json` `crucible_ladder*`):

| home | own milestones | by day |
|---|---|---|
| crucible (plain) | 1 | 28 Oct |
| crucible-hybrid | 3 | 30 Oct 1, 3 Nov 2 |
| crucible-world-hybrid | 13 | 3 Nov 4, 4 Nov 9 (M0015 4 Nov 05:42 was its last) |
| crucible-world-hybrid-forest | 6 | 6 Nov 6 (then the maze home took over) |
| **crucible-world-hybrid-forest-nav** | **30** | 6 Nov 3, 7 Nov 5, 8 Nov 1, 9 Nov 1, 10 Nov 4, 12 Nov 2, 13 Nov 2, 14 Nov 6, 15 Nov 6; **16 to 19 Nov 0** |

The maze home rung by rung: the milestone's own gauntlet mean share, the step it was elected on, and the game's read as the Gladiator against the shipped net. All times are 2026.

| milestone | made | island | how | zg | gauntlet mean share | game (a seat) |
|---|---|---|---|---|---|---|
| M0020 g112700 | 6 Nov 18:14 | boburner | rule | +25.92 | 0.642 | −8.75 refused |
| M0021 g112900 | 6 Nov 20:03 | boburner | rule | +20.52 | 0.738 | −8.47 refused |
| M0022 g280400 | 6 Nov 20:36 | calber | rule | +10.74 | 0.771 | +1.26 stands |
| M0023 g281200 | 7 Nov 00:50 | calber | rule | +2.89 | 0.779 | +1.02 stands |
| M0024 g281700 | 7 Nov 03:51 | calber | forced | +1.38 | 0.786 | +0.20 stands |
| M0025–M0029 | 7–9 Nov | boburner | 4 rule, 1 forced | +0.76 to +2.68 | 0.788–0.802 | −7.1 to −8.0 refused |
| **M0030 g290500** | 10 Nov 00:25 | calber | rule | −0.88 (elected on the yardstick, zy +1.13 ≥ bar 1.00) | 0.801 | **+2.28 ± 0.98 credited, shipped** |
| M0031 g291400 | 10 Nov 05:06 | calber | rule | +0.31 | 0.802 | −0.68 stands |
| **M0032 g291900** | 10 Nov 07:40 | calber | rule | +0.43 | 0.801 | −0.93 stands (**the top rung since**) |
| M0033–M0037 | 10–13 Nov | boburner | 3 rule, 2 forced | −0.27 to +2.52 | 0.803–0.807 | −5.0 to −7.2 refused |
| M0038–M0048 | 14–15 Nov | boburner | 4 rule, 7 forced | +0.32 to +2.18 | 0.805–0.811 | −6.99 to −10.95 refused |
| **M0049 g138500** | 15 Nov 22:06 | boburner | forced | +1.99 | 0.810 | **−8.84 ± 1.22 refused** |

**What the ladder shows.**

- **The gauntlet's mean share stopped moving.** It rose from 0.64 to 0.80 between 6 and 8 Nov and has stayed between 0.80 and 0.81 since.
- **The yardstick stopped moving.** boburner's win rate was 0.58 at g112700, 0.63 at g124000, 0.64 at g135500, 0.654 at g138500 and 0.653 at g148500 (`growth.tsv`).
- **The game has credited nothing since M0030** on 10 Nov.
- **Every milestone after M0032 is boburner's, and the game refused all 17.** Boburner wins the forced elections, which pay for T3, C7 and F3. The game reads its nets 5 to 11 points a seat under the shipped one. Calber's nets are the ones the game rates, and they cannot reach the floors boburner's elections set.

The generation count rises and the measured skill does not. On 14 and 15 Nov most elections were forced, three hours apart, and since 15 Nov 22:06 there have been none.

---

## B. The net

### B1. Shape and format

- **64 → 48 → 48 → 6, tanh on every layer** (crucible.cu `think()`, line 681). The input count is 32 + RULES_IN 3 + WORLD_IN 20 + NAV_IN 9, and there are 4 base outputs plus 2 memory outputs. **There are two hidden layers**, so net.json uses the generalised keys: `w1` (48 × 64, h1 × input), `b1`, `w2` (48 × 48, h2 × h1), `b2`, `w3` (6 × 48, output × h2), `b3`. `significance.hidden_out` is h2 → output, and `significance.h1_h2` is added.
- **The file** is 5,766 little-endian float32 with no header, row-major, in the order W1[48][64], b1[48], W2[48][48], b2[48], W3[6][48], b3[6]; weight W1[j][i] is float j·64 + i. This is the same reading as `tools/montage.py` `Net` and `tools/report/netcard.py`.
- **The reading is checked against a recording.** Montage 11 recorded M0041–M0045's inputs and the h1, h2 and y that montage.py computed from them, at 2 decimals. With those nets' own files:
  - h1 recomputed from the recorded inputs lies within 0.05 for 98.7–99.5% of values, with sign agreement ≥ 99.9%;
  - h2 from the recorded h1 has a maximum error of 0.04–0.10 and 100% sign agreement;
  - y from the recorded h2 has a maximum error of 0.005–0.12 and 98.8–100% sign agreement;
  - the share of steps with the gate open is reproduced exactly in all five chapters.

  (Chained end to end from 2-decimal inputs, a few near-zero units flip; that is the record's rounding.) Script: `gpu/check2.py`.

### B2. What goes in, and what comes out

**The sensor matrix: 12 rays × 3 channels** (`sense()`, crucible.cu:597). Ray r points at the hull's heading + 30°·r (r = 0 is dead ahead; r grows with the angle, the same sense as a positive turn), and each value is 1 − distance/40:

- **near** (input 2r): the nearest of wall, pillar, a forest's walls or the enemy tank;
- **enemy** (input 2r+1): the enemy tank on that ray, seen only within 10 tiles and not hidden in trees;
- **pillbox** (input 35+r): a live pillbox not its own.

**Scalars:**

| inputs | group | meaning |
|---|---|---|
| 24–31 | body | own speed/4; own armour/100; gun ready (1/0); enemy armour/100; sine and cosine of the bearing to the enemy; an incoming shell's nearness (1 − d/10); **31 is the constant 1.0, a second bias** |
| 32–34 | rules | the rules' own answer this step (the script, or under `ERRAND` the route-following errand): turn (heading error/π), speed (0–1), fire (±1) |
| 47–52 | pillbox | the nearest live pillbox: sine and cosine of its bearing, nearness, its reload (0 = can fire now), its health, "it has you" (within 8 and in line) |
| 53–54 | gun | own shells/24, own reload left/4 s |
| 55–58 | route | sine and cosine of the bearing to the route's next waypoint, the route's length/40, walled (no way) |
| 59–61 | arcs | the share of 1.5 s the tank could drive along an arc turning left (k = −1), straight, or right (k = +1) |
| 62–63 | memory | the net's own outputs 4 and 5 from the step before |

**Outputs, and the hybrid gate** (`decide()`, crucible.cu:871):

| output | meaning |
|---|---|
| 0 | turn correction |
| 1 | speed correction |
| 2 | fire correction |
| 3 | gate (confidence) |
| 4 | memory 0, written |
| 5 | memory 1, written |

`open = y[3] > 0`. When open, turn, speed and fire are clip(rules + y[0..2], −1, 1). When shut, the tank plays the rules exactly. `mem[m] = y[4+m]` every step. The tank fires when the fire value is above 0, it is loaded, and it has a shell. Turn is a heading error of value × π rad; speed is value × 4 tiles/s, with no reverse.

### B3. Where the activations come from

**Recorded activations of a close net, not of M0049 itself.** The inputs are the 723 recorded steps of montage 11 (409 steps: boburner's M0041–M0045 and the island at g137300, filmed 15 Nov 10:07) and montage 10 (314 steps: boburner's M0036–M0040, 14 Nov). Both are `Q/archive/montages/00NN/mind.json`. Those are real states of world duels (clips around pillbox fights, kill shots and a loss), seen by M0049's own island 1,200 to 3,000 generations earlier. M0049's h1, h2 and outputs were recomputed from its weights on those inputs.

**The caveats:**

1. They are not M0049's own games. M0049 agrees with M0048 in weights (correlation 0.9986; the L2 of the difference is 35 against 662) and with M0045 (correlation 0.991). Its output signs agree with M0045's on these states for 82% (turn), 74% (speed), 85% (fire) and 95% (gate) of steps.
2. They are duels, not the gauntlet's mazes, so the route and arcs are seen in open fights.
3. Inputs 62–63 are the recorded nets' memory.
4. Some inputs never fired in the sample (significance 0 there is the sample's): the enemy channel on rays 2–8, the pillbox on ray 7, and route walled.

There is no trace of M0049 itself. The footage tool deletes its traces after filming (`tools/report/footage.py` lines 109 and 160), and no montage has been made since M0045.

**Significance** = |w| × mean |activation of the source| over these 723 steps:

- input → h1 uses the recorded inputs;
- h1 → h2 and h2 → output use M0049's own h1 and h2.

Two more measures are given because of B4.1 and B4.2:

- **ablation**: an input, or a group of inputs, held at its sample mean, and the mean absolute change of the outputs and of the action the tank actually takes after the gate;
- **gradient × input**: in net.json only, and of little use in a saturated net.

### B4. What the numbers say (read before drawing)

1. **It is a network of switches.** 95.6% of h1 values and 96.9% of h2 values lie beyond ±0.99. The median absolute pre-activation is 29 in h1, 47 in h2 and 41 at the outputs. Over the 723 steps there are 294 distinct sign patterns in h1, 335 in h2 and 32 in the outputs.
   - 6 h1 units never change sign (14, 15, 30, 31, 36, 46) and 2 h2 units never do (8, 16): they act as biases.
   - 24 h1 units and 35 h2 units take each sign on at least 5% of steps; these are the live switches.

   Mean |h| is about 0.95–1.0 for every unit, so for the hidden layers |w| × mean|a| is about |w|. The ablation is the measure that separates what matters.
2. **The size of a weight tells its age, not its use.** Mutation adds N(0, 0.03) to every weight of every child, so a weight left to drift has an RMS of 0.03·√G after G generations. The RMS of each block matches the time since that block was born:

   | block | born (boburner g) | G | drift 0.03√G | measured RMS |
   |---|---|---|---|---|
   | first 32 hidden units: rays, body, rules; W2 0–31; W3 rows 0–3 | about 0 (hybrid, 30 Oct) | about 138,500 | 11.2 | 10.5, 12.2, 11.8; 11.0; about 10.0 |
   | the world's inputs (35–54); hidden units 32–47 | about 85,000 (3–4 Nov) | about 53,500 | 6.9 | 7.0; 7.0–7.8 (rules 5.4) |
   | route, arcs, memory inputs; memory output rows | about 112,600 (6 Nov) | about 25,900 | 4.8 | 4.9, 4.9, 5.3; 4.5 |

   The netcard's "senses" (the L2 of each group's columns: rays 323, body 214, rules 122, world 216, route 68, arcs 59, memory 52) are this clock. **|w| alone ranks weights by age.**

   The maze senses' weights are exactly at drift size. The round-corner report's hope that they would grow past drift is not visible in their size. They do move the outputs, though, by the ablation in point 4.
3. **The gate is mostly shut in these duels.** b3[3] = +20.5 and w3[3][3] = +48.8, so **h2[3] is the gate neuron**: its sign matches the gate on 98.5% of steps. The gate is open on only **6.8%** of these steps, so M0049 changes the rules' action on 6.8% and the fire decision on 1.1%. On these fights the rules (the errand and the script) drive. The island's own count, "the net overrode the rules on 84–85% of steps", covers the whole population's training, half of it tasks.
4. **What it listens to.** The table below is the group ablation: the mean absolute change of outputs 0–3, the share of steps the gate flips, and the mean absolute change of the tank's actual turn, speed and fire.

   | group | outputs 0–3 | gate flips | actual turn | actual speed | actual fire |
   |---|---|---|---|---|---|
   | rays, near channel | 0.457 | 9.7% | 0.115 | 0.037 | 0.058 |
   | rules | 0.436 | 11.1% | 0.130 | 0.065 | 0.061 |
   | body | 0.433 | 11.1% | 0.138 | 0.052 | 0.033 |
   | pillbox | 0.306 | 7.5% | 0.083 | 0.039 | 0.039 |
   | rays, enemy channel | 0.301 | 4.7% | 0.053 | 0.025 | 0.021 |
   | rays, pillbox channel | 0.244 | 6.5% | 0.069 | 0.032 | 0.030 |
   | arcs | 0.219 | 4.3% | 0.045 | 0.022 | 0.017 |
   | gun | 0.168 | 4.8% | 0.072 | 0.032 | 0.019 |
   | memory | 0.158 | 3.7% | 0.046 | 0.030 | 0.026 |
   | **route** | **0.076** | **1.8%** | **0.026** | **0.007** | **0.007** |

   The single inputs that matter most, by ablation:
   - rules' fire (34): 0.355, gate flips 12.7%
   - gun ready (26): 0.350, 13.3%
   - enemy dead ahead (ray 0, enemy channel, 1): 0.298
   - rules' speed (33): 0.267
   - own armour (25): 0.230
   - enemy bearing sine (28): 0.229
   - enemy armour (27): 0.215
   - the side rays near 120°, 90°, 150° and 60° (8, 6, 10, 4): 0.20 each
   - pillbox bearing (48, 47): 0.20

   In fights, the route sense is the least used of the groups.
5. **The memory acts mostly as a bias.** In the sample, input 62 is negative on 95% of steps and input 63 positive on 85%. M0049's own memory outputs are y4 > 0 on 5% of steps and y5 > 0 on 82%.
6. **It is a different net from calber's.** M0049's weights correlate 0.02 with M0032's and M0030's; separate lineages since October, never mixed. Its output signs agree with M0032's on these states for 81% (turn), 56% (speed), 55% (fire) and 92% (gate) of steps.

### B5. Drawing hints

- **Inputs** as a 12 × 3 polar matrix (the rays) plus 7 scalar blocks: body, rules, pillbox, gun, route, arcs, memory.
- **h1 and h2** as columns of 48. Mark the 6 + 2 constant-sign units as bias-like, and the live switches (`units.h1_live`, `units.h2_live` in net.json).
- **Outputs**: 6, with the gate drawn as a switch between the rules' answer (inputs 32–34) and the corrections.
- **Edges**: draw the top 40 input → h1, the top 20 (or 40) h1 → h2 and the top 20 h2 → output, coloured by the sign of w with width by s.
- **Emphasis**: h2[3] → gate (+48.8) is the single strongest connection in the net.
- **Group importance**: size the input blocks by the group ablation (B4.4), not by |w| (B4.2).

### B6. The tables

Significance s = |w| × mean |source activation| over the 723 recorded steps (B3). Ablation = that input held at its sample mean: mean |change| of outputs 0–3, and the share of steps the gate flips. Signed weights are M0049's own. Index conventions as in B2; h1 j and h2 k are 0-based.

#### Inputs (all 64)

| i | input | group | mean abs x | sd | col L2 of w1 | sum s = abs(w) x mean abs x | ablation: mean abs change of outputs 0-3 | gate flips |
|---|---|---|---|---|---|---|---|---|
| 0 | ray00@000deg near (wall/pillar/tree-wall/tank, 1-d/40) | rays.near | 0.609 | 0.313 | 63.6 | 204.3 | 0.161 | 0.025 |
| 1 | ray00@000deg enemy tank (1-d/40) | rays.enemy | 0.493 | 0.409 | 62.5 | 175.5 | 0.298 | 0.046 |
| 2 | ray01@030deg near (wall/pillar/tree-wall/tank, 1-d/40) | rays.near | 0.394 | 0.320 | 65.4 | 136.7 | 0.174 | 0.040 |
| 3 | ray01@030deg enemy tank (1-d/40) | rays.enemy | 0.028 | 0.164 | 63.7 | 10.0 | 0.041 | 0.011 |
| 4 | ray02@060deg near (wall/pillar/tree-wall/tank, 1-d/40) | rays.near | 0.325 | 0.339 | 70.1 | 113.5 | 0.196 | 0.017 |
| 5 | ray02@060deg enemy tank (1-d/40) | rays.enemy | 0.000 | 0.000 | 62.2 | 0.0 | 0.000 | 0.000 |
| 6 | ray03@090deg near (wall/pillar/tree-wall/tank, 1-d/40) | rays.near | 0.397 | 0.398 | 58.3 | 125.6 | 0.203 | 0.035 |
| 7 | ray03@090deg enemy tank (1-d/40) | rays.enemy | 0.000 | 0.000 | 67.4 | 0.0 | 0.000 | 0.000 |
| 8 | ray04@120deg near (wall/pillar/tree-wall/tank, 1-d/40) | rays.near | 0.500 | 0.417 | 52.1 | 138.0 | 0.206 | 0.040 |
| 9 | ray04@120deg enemy tank (1-d/40) | rays.enemy | 0.000 | 0.000 | 73.0 | 0.0 | 0.000 | 0.000 |
| 10 | ray05@150deg near (wall/pillar/tree-wall/tank, 1-d/40) | rays.near | 0.512 | 0.356 | 69.7 | 189.3 | 0.197 | 0.032 |
| 11 | ray05@150deg enemy tank (1-d/40) | rays.enemy | 0.000 | 0.000 | 77.0 | 0.0 | 0.000 | 0.000 |
| 12 | ray06@180deg near (wall/pillar/tree-wall/tank, 1-d/40) | rays.near | 0.243 | 0.266 | 67.3 | 87.5 | 0.126 | 0.014 |
| 13 | ray06@180deg enemy tank (1-d/40) | rays.enemy | 0.000 | 0.000 | 67.2 | 0.0 | 0.000 | 0.000 |
| 14 | ray07@210deg near (wall/pillar/tree-wall/tank, 1-d/40) | rays.near | 0.369 | 0.288 | 60.2 | 127.2 | 0.157 | 0.030 |
| 15 | ray07@210deg enemy tank (1-d/40) | rays.enemy | 0.000 | 0.000 | 62.4 | 0.0 | 0.000 | 0.000 |
| 16 | ray08@240deg near (wall/pillar/tree-wall/tank, 1-d/40) | rays.near | 0.586 | 0.261 | 60.1 | 189.5 | 0.147 | 0.035 |
| 17 | ray08@240deg enemy tank (1-d/40) | rays.enemy | 0.000 | 0.000 | 83.8 | 0.0 | 0.000 | 0.000 |
| 18 | ray09@270deg near (wall/pillar/tree-wall/tank, 1-d/40) | rays.near | 0.638 | 0.252 | 64.9 | 225.9 | 0.145 | 0.043 |
| 19 | ray09@270deg enemy tank (1-d/40) | rays.enemy | 0.005 | 0.064 | 64.7 | 1.7 | 0.008 | 0.003 |
| 20 | ray10@300deg near (wall/pillar/tree-wall/tank, 1-d/40) | rays.near | 0.664 | 0.252 | 71.1 | 246.7 | 0.152 | 0.035 |
| 21 | ray10@300deg enemy tank (1-d/40) | rays.enemy | 0.009 | 0.086 | 69.1 | 3.2 | 0.023 | 0.003 |
| 22 | ray11@330deg near (wall/pillar/tree-wall/tank, 1-d/40) | rays.near | 0.673 | 0.303 | 52.7 | 199.0 | 0.163 | 0.019 |
| 23 | ray11@330deg enemy tank (1-d/40) | rays.enemy | 0.034 | 0.173 | 66.4 | 11.9 | 0.072 | 0.025 |
| 24 | own speed v/VMAX | body | 0.322 | 0.405 | 72.5 | 130.6 | 0.172 | 0.062 |
| 25 | own armour hp/100 | body | 0.691 | 0.358 | 68.7 | 251.3 | 0.230 | 0.040 |
| 26 | gun ready (reload<=0) | body | 0.452 | 0.498 | 89.9 | 214.7 | 0.350 | 0.133 |
| 27 | enemy armour hp/100 | body | 0.358 | 0.261 | 79.1 | 159.5 | 0.215 | 0.043 |
| 28 | enemy bearing sin | body | 0.167 | 0.306 | 75.9 | 70.9 | 0.229 | 0.065 |
| 29 | enemy bearing cos | body | 0.926 | 0.178 | 69.2 | 355.7 | 0.115 | 0.022 |
| 30 | incoming shell nearness (1-d/10) | body | 0.041 | 0.143 | 77.0 | 16.7 | 0.058 | 0.025 |
| 31 | constant 1 (bias input) | body | 1.000 | 0.000 | 72.0 | 403.9 | 0.000 | 0.000 |
| 32 | rules' turn (heading error/pi) | rules | 0.023 | 0.070 | 68.2 | 8.2 | 0.043 | 0.007 |
| 33 | rules' speed (0..1) | rules | 0.405 | 0.530 | 72.4 | 145.7 | 0.267 | 0.076 |
| 34 | rules' fire (+1/-1) | rules | 1.000 | 0.992 | 70.0 | 380.0 | 0.355 | 0.127 |
| 35 | ray00@000deg pillbox (1-d/40) | rays.pillbox | 0.177 | 0.346 | 47.6 | 48.8 | 0.122 | 0.028 |
| 36 | ray01@030deg pillbox (1-d/40) | rays.pillbox | 0.098 | 0.278 | 55.8 | 30.0 | 0.153 | 0.025 |
| 37 | ray02@060deg pillbox (1-d/40) | rays.pillbox | 0.144 | 0.319 | 49.8 | 40.4 | 0.141 | 0.021 |
| 38 | ray03@090deg pillbox (1-d/40) | rays.pillbox | 0.118 | 0.291 | 51.1 | 34.7 | 0.119 | 0.036 |
| 39 | ray04@120deg pillbox (1-d/40) | rays.pillbox | 0.107 | 0.251 | 48.9 | 30.8 | 0.141 | 0.008 |
| 40 | ray05@150deg pillbox (1-d/40) | rays.pillbox | 0.040 | 0.145 | 52.4 | 11.1 | 0.065 | 0.014 |
| 41 | ray06@180deg pillbox (1-d/40) | rays.pillbox | 0.027 | 0.142 | 47.6 | 7.1 | 0.041 | 0.005 |
| 42 | ray07@210deg pillbox (1-d/40) | rays.pillbox | 0.000 | 0.000 | 45.1 | 0.0 | 0.000 | 0.000 |
| 43 | ray08@240deg pillbox (1-d/40) | rays.pillbox | 0.010 | 0.088 | 50.2 | 2.9 | 0.020 | 0.003 |
| 44 | ray09@270deg pillbox (1-d/40) | rays.pillbox | 0.003 | 0.052 | 42.8 | 0.8 | 0.003 | 0.003 |
| 45 | ray10@300deg pillbox (1-d/40) | rays.pillbox | 0.009 | 0.085 | 48.4 | 2.3 | 0.010 | 0.004 |
| 46 | ray11@330deg pillbox (1-d/40) | rays.pillbox | 0.022 | 0.128 | 51.9 | 6.4 | 0.030 | 0.005 |
| 47 | pillbox bearing sin | pillbox | 0.546 | 0.499 | 50.1 | 152.2 | 0.196 | 0.057 |
| 48 | pillbox bearing cos | pillbox | 0.716 | 0.684 | 48.3 | 197.7 | 0.200 | 0.053 |
| 49 | pillbox nearness (1-d/40) | pillbox | 0.723 | 0.157 | 47.8 | 186.8 | 0.098 | 0.011 |
| 50 | pillbox reload (0=can fire now) | pillbox | 0.203 | 0.330 | 41.4 | 47.6 | 0.135 | 0.025 |
| 51 | pillbox health | pillbox | 0.861 | 0.291 | 54.4 | 255.8 | 0.144 | 0.022 |
| 52 | pillbox has you (in 8, line clear) | pillbox | 0.255 | 0.436 | 42.1 | 58.6 | 0.172 | 0.053 |
| 53 | own shells/24 | gun | 0.960 | 0.046 | 39.4 | 216.5 | 0.026 | 0.001 |
| 54 | own reload remaining/4s | gun | 0.263 | 0.382 | 48.9 | 73.8 | 0.148 | 0.048 |
| 55 | route bearing sin (next waypoint) | route | 0.062 | 0.179 | 32.9 | 11.7 | 0.062 | 0.014 |
| 56 | route bearing cos | route | 0.978 | 0.106 | 36.1 | 205.8 | 0.019 | 0.005 |
| 57 | route length/40 | route | 0.247 | 0.091 | 32.8 | 46.8 | 0.042 | 0.011 |
| 58 | route walled (no way) | route | 0.000 | 0.000 | 34.5 | 0.0 | 0.000 | 0.000 |
| 59 | arc left free (k=-1) | arcs | 0.758 | 0.388 | 32.3 | 134.2 | 0.150 | 0.022 |
| 60 | arc straight free (k=0) | arcs | 0.795 | 0.363 | 36.6 | 163.3 | 0.168 | 0.042 |
| 61 | arc right free (k=+1) | arcs | 0.796 | 0.368 | 33.7 | 154.3 | 0.133 | 0.030 |
| 62 | memory 0 (own output 4, last step) | memory | 0.996 | 0.418 | 37.8 | 211.0 | 0.110 | 0.025 |
| 63 | memory 1 (own output 5, last step) | memory | 0.987 | 0.693 | 35.0 | 183.0 | 0.141 | 0.042 |

#### The sensor matrix: 12 rays x 3 channels (sum s / ablation)

| ray | bearing | near: s | near: abl | enemy: s | enemy: abl | pillbox: s | pillbox: abl |
|---|---|---|---|---|---|---|---|
| 0 | 0 deg | 204 | 0.161 | 175 | 0.298 | 49 | 0.122 |
| 1 | 30 deg | 137 | 0.174 | 10 | 0.041 | 30 | 0.153 |
| 2 | 60 deg | 113 | 0.196 | 0 | 0.000 | 40 | 0.141 |
| 3 | 90 deg | 126 | 0.203 | 0 | 0.000 | 35 | 0.119 |
| 4 | 120 deg | 138 | 0.206 | 0 | 0.000 | 31 | 0.141 |
| 5 | 150 deg | 189 | 0.197 | 0 | 0.000 | 11 | 0.065 |
| 6 | 180 deg | 87 | 0.126 | 0 | 0.000 | 7 | 0.041 |
| 7 | 210 deg | 127 | 0.157 | 0 | 0.000 | 0 | 0.000 |
| 8 | 240 deg | 190 | 0.147 | 0 | 0.000 | 3 | 0.020 |
| 9 | 270 deg | 226 | 0.145 | 2 | 0.008 | 1 | 0.003 |
| 10 | 300 deg | 247 | 0.152 | 3 | 0.023 | 2 | 0.010 |
| 11 | 330 deg | 199 | 0.163 | 12 | 0.072 | 6 | 0.030 |

#### Top 40 input -> h1 connections

| # | input i | input | h1 j | w | s = abs(w) x mean abs x |
|---|---|---|---|---|---|
| 1 | 34 | rules' fire | 23 | +24.91 | 24.91 |
| 2 | 29 | enemy bearing cos | 15 | +26.66 | 24.68 |
| 3 | 34 | rules' fire | 6 | +24.38 | 24.38 |
| 4 | 34 | rules' fire | 28 | +23.92 | 23.92 |
| 5 | 31 | constant 1 | 5 | -23.51 | 23.51 |
| 6 | 31 | constant 1 | 29 | -23.35 | 23.35 |
| 7 | 20 | ray10@300deg near | 12 | -34.38 | 22.85 |
| 8 | 25 | own armour hp/100 | 26 | -29.56 | 20.41 |
| 9 | 31 | constant 1 | 39 | -20.08 | 20.08 |
| 10 | 34 | rules' fire | 17 | +19.43 | 19.43 |
| 11 | 31 | constant 1 | 26 | +18.79 | 18.79 |
| 12 | 26 | gun ready | 9 | +41.44 | 18.74 |
| 13 | 29 | enemy bearing cos | 20 | +20.04 | 18.55 |
| 14 | 31 | constant 1 | 46 | -17.96 | 17.96 |
| 15 | 26 | gun ready | 1 | -38.95 | 17.62 |
| 16 | 31 | constant 1 | 15 | +17.45 | 17.45 |
| 17 | 0 | ray00@000deg near | 4 | -27.79 | 16.92 |
| 18 | 20 | ray10@300deg near | 25 | +25.37 | 16.86 |
| 19 | 29 | enemy bearing cos | 18 | -17.92 | 16.59 |
| 20 | 29 | enemy bearing cos | 31 | +17.70 | 16.39 |
| 21 | 29 | enemy bearing cos | 10 | +17.67 | 16.36 |
| 22 | 25 | own armour hp/100 | 5 | +23.65 | 16.33 |
| 23 | 10 | ray05@150deg near | 8 | +31.57 | 16.18 |
| 24 | 31 | constant 1 | 7 | +16.10 | 16.10 |
| 25 | 51 | pillbox health | 30 | -18.68 | 16.08 |
| 26 | 18 | ray09@270deg near | 27 | -25.12 | 16.03 |
| 27 | 63 | memory 1 | 30 | -16.12 | 15.90 |
| 28 | 31 | constant 1 | 30 | -15.53 | 15.53 |
| 29 | 49 | pillbox nearness | 1 | +21.19 | 15.32 |
| 30 | 31 | constant 1 | 2 | +15.30 | 15.30 |
| 31 | 34 | rules' fire | 16 | +15.30 | 15.30 |
| 32 | 34 | rules' fire | 31 | -14.68 | 14.68 |
| 33 | 34 | rules' fire | 7 | -14.54 | 14.54 |
| 34 | 31 | constant 1 | 17 | +14.53 | 14.53 |
| 35 | 10 | ray05@150deg near | 18 | -28.35 | 14.53 |
| 36 | 34 | rules' fire | 29 | +14.42 | 14.42 |
| 37 | 16 | ray08@240deg near | 22 | -24.22 | 14.19 |
| 38 | 34 | rules' fire | 21 | +14.17 | 14.17 |
| 39 | 51 | pillbox health | 46 | -16.44 | 14.16 |
| 40 | 29 | enemy bearing cos | 22 | -15.08 | 13.96 |

#### Top 20 h1 -> h2 connections (of the 40 in net.json)

| # | h1 j | h2 k | w | s = abs(w) x mean abs h1 |
|---|---|---|---|---|
| 1 | 3 | 2 | +39.38 | 38.49 |
| 2 | 31 | 2 | -36.58 | 36.54 |
| 3 | 8 | 4 | -34.68 | 34.47 |
| 4 | 15 | 31 | +32.81 | 32.81 |
| 5 | 5 | 31 | +32.65 | 32.44 |
| 6 | 18 | 24 | +32.31 | 32.16 |
| 7 | 16 | 7 | +32.12 | 31.96 |
| 8 | 25 | 14 | -31.77 | 31.25 |
| 9 | 31 | 19 | +31.11 | 31.07 |
| 10 | 10 | 3 | +29.94 | 28.80 |
| 11 | 22 | 14 | -28.56 | 28.53 |
| 12 | 28 | 1 | -28.36 | 28.14 |
| 13 | 9 | 3 | -28.25 | 27.95 |
| 14 | 7 | 6 | +28.32 | 27.80 |
| 15 | 29 | 23 | -27.88 | 27.61 |
| 16 | 22 | 9 | +27.38 | 27.35 |
| 17 | 2 | 8 | +27.57 | 27.29 |
| 18 | 9 | 7 | +27.03 | 26.74 |
| 19 | 14 | 13 | +26.59 | 26.59 |
| 20 | 27 | 25 | -26.52 | 26.41 |

#### Top 20 h2 -> output connections

| # | h2 k | output | w | s = abs(w) x mean abs h2 |
|---|---|---|---|---|
| 1 | 3 | 3 gate | +48.77 | 48.64 |
| 2 | 1 | 1 speed | -28.66 | 28.65 |
| 3 | 22 | 0 turn | -27.39 | 27.32 |
| 4 | 11 | 1 speed | +25.64 | 25.18 |
| 5 | 12 | 2 fire | -24.48 | 24.31 |
| 6 | 28 | 1 speed | -24.23 | 24.09 |
| 7 | 17 | 0 turn | -23.53 | 23.49 |
| 8 | 5 | 2 fire | -22.16 | 21.84 |
| 9 | 6 | 1 speed | +21.29 | 21.04 |
| 10 | 0 | 0 turn | -21.05 | 20.54 |
| 11 | 22 | 2 fire | -19.51 | 19.46 |
| 12 | 0 | 3 gate | +19.67 | 19.20 |
| 13 | 30 | 2 fire | +19.13 | 19.09 |
| 14 | 18 | 0 turn | -19.41 | 18.97 |
| 15 | 2 | 0 turn | +18.51 | 18.38 |
| 16 | 11 | 0 turn | -18.27 | 17.94 |
| 17 | 3 | 0 turn | -17.38 | 17.34 |
| 18 | 10 | 2 fire | -16.96 | 16.89 |
| 19 | 9 | 1 speed | -17.25 | 16.88 |
| 20 | 15 | 2 fire | -15.97 | 15.94 |

#### Per output: bias, strongest h2 units, and the inputs whose ablation moves it most

| output | b3 | mean y | share y>0 | strongest h2 (w) | inputs that move it most when held at their mean (mean abs change) |
|---|---|---|---|---|---|
| 0 turn correction | +6.20 | +0.653 | 0.827 | h2[22] -27.4, h2[17] -23.5, h2[0] -21.1, h2[18] -19.4 | 1 ray00@000deg enemy tank 0.45, 26 gun ready 0.38, 34 rules' fire 0.32, 27 enemy armour hp/100 0.29, 33 rules' speed 0.29 |
| 1 speed correction | +9.33 | +0.119 | 0.559 | h2[1] -28.7, h2[11] +25.6, h2[28] -24.2, h2[6] +21.3 | 34 rules' fire 0.73, 26 gun ready 0.61, 25 own armour hp/100 0.54, 1 ray00@000deg enemy tank 0.50, 33 rules' speed 0.50 |
| 2 fire correction | +3.59 | -0.855 | 0.072 | h2[12] -24.5, h2[5] -22.2, h2[22] -19.5, h2[30] +19.1 | 24 own speed v/VMAX 0.15, 1 ray00@000deg enemy tank 0.15, 26 gun ready 0.15, 4 ray02@060deg near 0.14, 8 ray04@120deg near 0.14 |
| 3 gate / confidence | +20.51 | -0.867 | 0.068 | h2[3] +48.8, h2[0] +19.7, h2[10] -14.8, h2[6] -13.1 | 26 gun ready 0.27, 34 rules' fire 0.25, 33 rules' speed 0.15, 24 own speed v/VMAX 0.13, 28 enemy bearing sin 0.13 |
| 4 memory 0 write | +0.11 | -0.894 | 0.050 | h2[19] -12.8, h2[21] +11.6, h2[43] -11.7, h2[11] -11.5 | 12 ray06@180deg near 0.16, 28 enemy bearing sin 0.13, 61 arc right free 0.12, 48 pillbox bearing cos 0.12, 24 own speed v/VMAX 0.12 |
| 5 memory 1 write | -1.17 | +0.651 | 0.824 | h2[35] +8.2, h2[1] -7.2, h2[46] -6.9, h2[8] +6.3 | 34 rules' fire 0.32, 26 gun ready 0.31, 10 ray05@150deg near 0.30, 33 rules' speed 0.28, 4 ray02@060deg near 0.26 |

#### Groups

| group | inputs | L2 of w1 columns | per-weight RMS | generations of pure drift that RMS equals (0.03 sqrt G) | sum s |
|---|---|---|---|---|---|
| rays (near+enemy) | 0-23 | 323.2 | 9.52 | 100721 | 2185 |
| body | 24-31 | 214.4 | 10.94 | 133043 | 1603 |
| rules | 32-34 | 121.6 | 10.14 | 114152 | 534 |
| world (pillbox rays, pillbox, gun) | 35-54 | 216.4 | 6.98 | 54199 | 1404 |
| route | 55-58 | 68.2 | 4.92 | 26922 | 264 |
| arcs | 59-61 | 59.3 | 4.94 | 27151 | 452 |
| memory | 62-63 | 51.5 | 5.26 | 30700 | 394 |

Group ablations (the group's inputs held at their sample means):

| group | n | mean abs change, outputs 0-3 | gate flips | per output (turn, speed, fire, gate, mem0, mem1) |
|---|---|---|---|---|
| rays.near | 12 | 0.457 | 0.097 | 0.45, 0.93, 0.26, 0.19, 0.15, 0.34 |
| rays.enemy | 12 | 0.301 | 0.047 | 0.41, 0.53, 0.17, 0.10, 0.11, 0.25 |
| rays.pillbox | 12 | 0.244 | 0.065 | 0.24, 0.49, 0.12, 0.13, 0.09, 0.17 |
| body | 8 | 0.433 | 0.111 | 0.53, 0.76, 0.22, 0.22, 0.12, 0.55 |
| rules | 3 | 0.436 | 0.111 | 0.53, 0.82, 0.16, 0.23, 0.13, 0.35 |
| pillbox | 6 | 0.306 | 0.075 | 0.27, 0.59, 0.22, 0.15, 0.17, 0.34 |
| gun | 2 | 0.168 | 0.048 | 0.18, 0.32, 0.07, 0.10, 0.07, 0.18 |
| route | 4 | 0.076 | 0.018 | 0.09, 0.12, 0.06, 0.04, 0.07, 0.07 |
| arcs | 3 | 0.219 | 0.043 | 0.30, 0.34, 0.16, 0.08, 0.12, 0.24 |
| memory | 2 | 0.158 | 0.037 | 0.10, 0.33, 0.13, 0.07, 0.06, 0.24 |

---

## C. Can an existing tool draw this net?

Not as a picture of M0049. What exists, checked by reading the code:

- **`tools/report/netcard.py`** writes JSON only: the card and `cards.json`. It draws nothing.
- **`tools/montage.py`** draws the net's "mind" corners only inside a film. The film needs a fresh trace made on a GPU island over ssh (`--trace`), which is outside this read-only brief. It also draws the montage's chapters, not a chosen milestone.
- **Orrery, Results → Montage (page 16)** plays the existing montage 11 with its mind panels. Those are M0041–M0045 and g137300, the same island 1,200 to 2,600 generations earlier, not M0049.
- **Orrery, Results → Nets (page 13)** draws a 16-square first-layer fingerprint, the listening by sense group and the speaking by head, but only for nets in `plan/nets.json`. That register has 23 rows and none of them is M0049.

I did not run Orrery, so I give no frame command. The figure is best drawn from `net.json`.

## What I could not find, or could only infer

- **No milestone in the last three days.** The newest of any home is M0049, from 15 Nov 22:06.
- **No activations of M0049 itself.** Its footage traces were deleted after filming, and no montage covers it. The activations here are M0049 run on states recorded from M0036–M0045 and g137300, in duels only.
- **The exact bytes it imported.** `latest/calber-cuda.bin` and `latest/whitewolf-cuda.bin` have been overwritten many times since. Which champions they were at dispatch (x-calber-cuda-3715, x-whitewolf-cuda-2637) is **inferred from timing**, assuming the keeper reads `send` files at dispatch as the planner's comments say.
- **The island's population and hall of fame.** They live in `island.state` on boburner, not on this Mac, so where M0049 ranked in its population, and its ancestry within the 100 generations, is not visible.
- **The floors in force when 1756 was examined** are reconstructed from M0048's gauntlet shares less 1/16. The state keeps only today's floors. The reconstruction agrees with the floors quoted in the elect.tsv rows around it.
- **When eps, gens and task_p changed for this home.** `plan.json` has no history; the 256 duels and the maze home are dated 6 Nov in docs/round-corner-lab-report.md §X.
- **The forced election has no elect.tsv row of its own.** It is recorded in `plan/state.json` (`"elected": true`) and in the flag file, and the card's `election` is null.
- **Not where the brief expected:**
  - The vault (`Q/vault/`) holds one net, first-minute-b3be24e4bb68.bin, and `plan/nets.json` does not list M0049.
  - `Q/archive/milestones/` does not exist. The cards are `Q/<home>/milestones/ID.card.json` and `Q/<home>/cards.json`.
  - `plan/pipeline.json` keeps only the last six hours of island jobs, under the chain names "island boburner-cuda" and so on, stage "islands", so it holds nothing from 15 Nov.
- **Ray and arc orientation on screen.** Ray r is at heading + 30°·r and the arcs are k = −1, 0, +1, which the source comment calls "left, straight, right". Whether +angle is left or right on screen I did not verify.

## Files

**Written** (scratchpad):

- `trace-gpu.md`: this report.
- `net.json`: the weights, the names, the significance and the checks.
- `gpu/`, the scripts and intermediates:
  - `net_analysis.py`, `check2.py`, `effective.py`: the net;
  - `tables.py` → `tables.md`, plus `digest.json`, `effective.json`, `units.json`;
  - `segs.py`, `since.py`, `ladders.py`: part A;
  - `segs-since.tsv`.

**Read** (`Q = /Users/user/code/treadcore/build/queue/grove`):

- The home's files:
  - `Q/crucible-world-hybrid-forest-nav/{elect.tsv, lineage.tsv, growth.tsv}`
  - `…/milestones/M0049-boburner-cuda-g138500.bin`, its `.card.json`, and the M0032, M0030, M0041, M0045 and M0048 `.bin`
  - `…/ladder/ladder.txt`
- The segment: `Q/results/x-boburner-cuda-1756/fleet/q-grove/out/x-boburner-cuda-1756/{console.txt, gens.tsv, exam.tsv, gauntlet.tsv, champ.bin}`, `Q/results/x-boburner-cuda-1755/…/gauntlet.tsv`, `Q/done/1794783658403-x-boburner-cuda-1756.json`, and the other islands' done files.
- The planner and keeper:
  - `Q/plan/state.json`: `crucible_ladder:*`, `crucible`, `crucible_rules`
  - `Q/plan/bridge.json`, `Q/plan.json`, `Q/plan/pipeline.json`, `Q/plan/nets.json`
  - `Q/events.jsonl`
  - `Q/flags/1794809163390-crucible.json`, `1794809164311-footage.json`, `1794812104438-bridge.json`, `1794812104438-crucible.json`
- The archive: `Q/archive/footage/crucible-world-hybrid-forest-nav/M0049-boburner-cuda-g138500/result.json`, and `Q/archive/montages/0010/` and `0011/` (`mind.json`, `summary.json`).
- The code:
  - `/Users/user/code/orrery/tools/plans/treadcore.py` (4706–4990, 5110–5268, 5520–5547, 5789–5911)
  - `tools/montage.py` (346–447), `tools/report/netcard.py`, `tools/report/footage.py`, `src/montage.rs`, `src/nets.rs`
  - `/Users/user/code/treadcore/crucible/src/crucible.cu` (1–200, 470–720, 829–960, 1570–1605, 2015–2100, 3040–3085)
- The background: `docs/round-corner-lab-report.md`.
