# The Loop Closed: Floors That Give, the Game's Verdict Back to the Cards, a Watch That Flags, and What More CUDA Cards Would Speed

*Paul Richeson · Lab Report — IEEE Format · 13 November 2026*

Paul Richeson, treadcore.org; Claude Code (Claude Fable 5.2) as the pair. Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery and treadcore.

Companions: orrery `tools/plans/treadcore.py` (`FLOOR_GIVE`, `guard_verdict`, `game_says`, `standing`, `ladder_top`, `island_refused`, `watching`), `tools/fleet-queue.py` (`Queue.ack`, health's words), `tools/deploy-watch.py`, `tools/report/loop.py` (the diagrams and numbers here); treadcore `scripts/floors.py`, `scenario.rs` (`FLOOR_GIVE`), LR 158. The data: `docs/loop/data.json`, read at 10:37 on 13 November. The day's reports before this: [1] to [4]. orrery b4ae394 and the commit of this report; treadcore 6a706cd.

## Abstract

Paul, after *The First Morning* [4]: "I want to accept the world, the best suggested way to move forward ... and adapting the tests to just pass with current numbers. Then we can progress forward. Please use your best intuition to design a better learning process. ... Fix the milestone process to be more adaptive and cyclical. Remove bottlenecks and checkpoints: if it's good, it should promote, test and accept. Reincorporate the adjustments found back into the loop. Create a diagram explaining how adding more CUDA GPUs will accelerate this, and in what way." Asked which tests should follow the brain, he named all three kinds; asked what a drop should do: "pass on a small drop". **Five things were built.** (1) **A floor gives.** A family or a gauntlet file under its floor by no more than 0.05 of a share passes, and the promotion moves that floor down to what the new brain scored; under by more is a collapse and still refuses. (2) **The game's verdict comes back to the cards.** A milestone the game reads under the shipped Gladiator by two errors is no rung of the ladder: 14 of 37 are marked, every one of boburner's that was read, and the one to beat is calber's M0032 where it was boburner's M0037. An island whose last three read milestones were all refused sends no migrants, and the net the game ships goes to every island each segment. (3) **The watch runs by itself**, every ten minutes in the planner, and raises a flag for each check that reads `BAD`. (4) **A refusal is progress**: a candidate refused by a family is said once with its reason and wants no acknowledging. (5) **Acknowledge all works**: one flag file broken in the cut of 8 November had stopped every acknowledgement. **Three things were seen for the first time** [4]: a trade let through (`w_smooth = 0.525`, +3.46 held out for 0.44 kills less deaths), the yardstick's first day (**+3.87 ± 0.25** over main of 28 October, **+1.57 ± 0.22** over 2 November, **+0.20 ± 0.22** over 6 November), and the four parts of `w_smooth` read alone, none of which carries its gain by itself. **On the cards:** more of them speed proposals, breadth and the wait for a credited net, each in proportion or better. They do not speed the search of the game's own dials, which is read in whole games on the CPUs. And they make more of what the arena likes, which over 22 milestones agreed with the game at −0.40.

*Index Terms*: adaptive thresholds, regression tolerance, closed-loop selection, island model, migration, coevolution, hall of fame, parallel speedup, alerting.

## I. The design, in one picture

!html(loop/dia-loop.html)

*Diagram 1. The learning process on the evening of 13 November. Above, the game's own brain: the search, the reads, the gates, the line that settles, and main. Below, the cards: the islands, a milestone, the bridge that reads it in the game. Dashed arrows are what comes back: an orphaned block's trial to the search, main to the yardstick, and, new here, the game's verdict to the islands.*

**The principle Paul asked for is one sentence: if it is good, it is promoted, tested and accepted, and what was learned goes back in.** Three places broke it before today. A candidate good by points and a point under one floor was refused whole. A milestone the game refused stayed the cards' own bar and spread to the other islands. And what needed a person stood beside what did not, so the page that asks for attention asked for it 23 times.

## II. A floor gives

!html(loop/dia-floor.html)

*Diagram 2. The three things a score under a floor can be.*

**What was built.** treadcore (LR 158, 6a706cd): the families' test reads `FLOOR_GIVE`, a share, and a family within it of its floor "holds, a small drop". `scripts/floors.py` reads the families' lines and the gauntlet's table against the scenario files; a small drop passes and, at a promotion, its floor is rewritten to what was scored less a hundredth; a collapse exits 1 with nothing written. orrery: the value `floor_give` (0.05; 0 is every floor a wall, as it was) reaches the families' jobs, the guard's verdict and the promotion, whose commit now carries the scenario files.

| Case | Before | Now |
|---|---|---|
| G20 at 58% of a 60% floor (seven candidates in a week) | waits | passes; G20's floor becomes 0.57 |
| a family at 52% of 55% | refused | passes; its floor becomes 0.51 |
| "a raid on the held ground" at 0 of 400, floor 95% | refused | refused: a collapse |

*Table I. The rule on three real cases.*

**The third kind of test needed nothing new but one line.** The brain's unit tests have read a pinned brain, not the defaults, since treadcore's LR 147: no promotion has failed on a moved default since 5 November. The one that failed today was this morning's own test of the split, which expected `w_smooth` off by default. It names `w_smooth` now.

**What it costs, said plainly.** A floor moved down stays down until a person raises it. A run of small drops can walk a floor a long way, five points at a time. The watch's `floors` line lists each floor moved.

## III. The game's verdict comes back to the cards

| Island | Milestones | Read in the game | Refused | Credited | Mean in the game |
|---|---|---|---|---|---|
| boburner | 17 | 14 | **14** | 0 | **−6.78** |
| calber | 19 | 8 | 0 | 1 | +0.17 |
| whitewolf | 1 | 0 | 0 | 0 | — |

*Table II. The ladder of the maze home, 37 milestones, by the island that made each. "Refused" is read under the shipped Gladiator by two errors.*

**Before.** The card elected and the game credited, and there it ended. Each of boburner's fourteen stood in turn as the newest rung, the one every island's next champion was examined against and the reference of every gauntlet; and each segment took the other islands' newest champions as migrants, boburner's among them.

**What was built** (`game_says`, `standing`, `ladder_top`, `island_refused`).

- **A refused milestone is no rung.** The bridge writes its read on the milestone. The ladder the segments are sent leaves the refused out, and the one to beat is the newest standing. At 10:35 that moved from M0037 (boburner) to **M0032 (calber)**.
- **A refused island sends no migrants** while its last three read milestones were all refused. It still receives them: migration between islands is what keeps them one search and not three [6].
- **The game's net goes to every island**, each segment, beside the standing islands' champions: what the game credited is what the cards grow from, a hall of fame of one [5].
- **A refusal is said once**, as progress, with the read.

**What was not built.** A champion is still read in the game only once the card has elected it a milestone: the game does not yet read an island's best when no milestone comes. And an island is pulled by migrants, not restarted: boburner's population is what it was.

## IV. What more CUDA cards would speed

!html(loop/dia-gpu.html)

*Diagram 3. A card is an island. What rises with the number of cards, what it costs the CPUs, and what no card touches.*

**Three things rise with the cards.**

1. **Proposals, in proportion.** A card runs one island: 2,048 nets for 100 generations a segment, about forty minutes with its gauntlet. Three cards made 18 milestones of their own in 6.4 days, under three a day. Six would make about six.
2. **Breadth.** Each island is its own lineage. With the game's net going to all of them, more islands are more starts from the same credited place.
3. **The wait for a credited net, better than in proportion at first.** If a card's chance of a credited milestone in a day is *p*, the chance that at least one of *N* has one is 1 − (1 − *p*)^*N*. Calber's record is one credited in eight read, about one a week. At that rate for each card, three cards wait about 2.7 days for the next and six about 1.7: each card added shortens the wait, by less each time.

**One thing rises with them and is cheap.** Every milestone is read in the game: two censuses of 192 seeds, 384 in all. Six a day is 2,300 seeds, a little over 1% of what the CPU machines read; even twenty cards would ask about 4%.

**Two things no card speeds.**

- **The game's own brain.** Its dials are read in whole games of treadcore on the CPUs, 178,000 seeds a day whatever the cards do [1]. A card reads no census: the scripted brain is not on it. The line, its proof and the yardstick are all CPU work.
- **The arena's judgement.** Over the 22 milestones the bridge has read, a milestone's margin in the arena's exam and its read in the game agree at **−0.40**. More cards make more of what the arena rewards. Until the exam rewards what the game does, a fourth card buys mostly more refusals, now at least refused quickly and kept off the ladder.

**So the order is: the exam, then the cards.** And one use of a card that would change the first limit: a census of the scripted brain on the card. That is a port of the game's rules to CUDA, not a setting, and it is the only road by which a card would speed the dials.

## V. The watch flags, and the page asks for less

!html(loop/dia-flags.html)

*Diagram 4. Which flags want a person.*

- **The watch runs in the planner** every ten minutes (`watching`), keeps its fourteen lines in `plan/deploy-watch.json`, and raises a flag of kind `watch` for each that reads `BAD`. Two lines were added: the ladder (what the game refused, the one to beat, who sends no migrants) and the floors moved.
- **A candidate refused by a family is progress**, with the family and the count: "grove/w18795 is refused, as it should be: a raid on the held ground held 0 of 400 (floor 95.0%)". Seven of the 23 flags on the page that morning were these.
- **Acknowledge all.** `Queue.ack` read every flag file with no guard. One, written twice over in the power cut of 8 November, was not JSON ("Extra data: line 1 column 193"), and every acknowledgement died on it before reaching another. It passes over what it cannot read; the file is mended; the sixteen flags still standing were acknowledged at Paul's word.
- **Health says what is so**: the bar "stands there: a dry spell widens the search and does not lower it".

## VI. Seen for the first time

**The yardstick's first day** (the line as it stood at 08:12, f1ce347, on 2,000 seeds a brain):

| Against main of | Today's lead, a seat | Dials that differ |
|---|---|---|
| 28 October | **+3.87 ± 0.25** | 47 |
| 2 November | **+1.57 ± 0.22** | 40 |
| 6 November | +0.20 ± 0.22 | 22 |

*Table III. The first rows of `plan/rating.json`. They say by another road what the proof and the anchors said [1]: real gains through the first week, and none measurable since 6 November.*

**A trade let through.** `w_smooth = 0.525` (w20026) read +3.46 ± 0.54 held out and gave up 0.44 kills less deaths a seat, 4.4 floors where the rule weighed by its gain allows 8.7. Paul's word on it that morning: "let it through". Its first promotion failed on the test of section II; with that mended the planner asked again by itself (r0332), and it was running when this was written.

**The parts of `w_smooth`, each on alone** (first reads of 150 seeds, asked ahead of the A/B queue at Paul's word):

| Part | Score, a seat | Kills less deaths |
|---|---|---|
| the turret's confirmation | −2.09 ± 0.71 | −0.14 ± 0.14 |
| the stance's advance scalar | +0.03 ± 0.71 | −0.05 ± 0.11 |
| resupply by the doctrine alone | +1.93 ± 0.87 | **−1.46 ± 0.14** |
| the rung's confirmation | +0.31 ± 0.64 | +0.09 ± 0.12 |
| all of `w_smooth` 0.525 | +4.29 ± 0.90 | −0.34 ± 0.20 |

*Table IV. One read each; the held-out reads of the first two were inside their noise.*

**No part carries the gain alone.** Resupply by the doctrine carries about half of it and more than all of the fights lost; the turret's confirmation costs by itself. What is left is the blend, the one thing the four switches do not cover, or the parts together. These are single reads and settle nothing yet.

## VII. What is open

- **The exam** that elects a milestone on the card still rewards what the game does not. This is the largest thing left on the cards' side.
- **The game reading an island's best champion** when no milestone comes, and **restarting an island** the game keeps refusing: not built.
- **The blend of `w_smooth`** is not split from its switches.
- **A generation that settles and is proved** has still not been seen. r0332 is the first that could.
- **Floors can walk down.** Nothing raises one back.
- **The shipped Gladiator is still M0015**, though the bridge credited M0030 on 10 November: why that ship did not land has not been read.

## VIII. How to make it again

`python3 tools/report/loop.py ~/code/treadcore/build/queue/grove docs/loop` writes `docs/loop/data.json` and the four diagrams. The checks: `python3 -I tools/plans/board-check.py`, `sh tools/fleet-queue-check.sh`, `cargo test`; in treadcore, `cargo test -p treadcore-brain --release`.

## References

[1] orrery, *Always Forward*, lab report, 13 November 2026.

[2] orrery, *Every Block Checked*, lab report, 13 November 2026.

[3] orrery, *Old Decisions, Reopened*, lab report, 13 November 2026.

[4] orrery, *The First Morning*, lab report, 13 November 2026.

[5] C. D. Rosin and R. K. Belew, "New methods for competitive coevolution," *Evolutionary Computation*, vol. 5, no. 1, pp. 1–29, 1997.

[6] E. Cantú-Paz, "A survey of parallel genetic algorithms," *Calculateurs Parallèles, Réseaux et Systèmes Répartis*, vol. 10, no. 2, pp. 141–171, 1998.
