# Always Forward: Why the Line Has Not Gained Since 6 November, the Gain a Rule Held Back, and a Harness That Mints Only Real Blocks

*Paul Richeson · Lab Report — IEEE Format · 13 November 2026*

Paul Richeson, treadcore.org; Claude Code (Claude Opus 5.5) as the pair. Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery and treadcore.

Companions: orrery `tools/report/forward.py` (every number and figure here, from the queue and git), `tools/plans/treadcore.py` (`SEQ`, `ease`, `held_pass`, `noise`, `trades_away`, `anchor_trial`, `line_proof`), `tools/plans/difficulty-sim.py`; treadcore `scripts/ledger.py`, `source/treadcore-brain/src/fleet.rs` (`brain_census`) and `weights.rs` (`w_smooth`). The data: `docs/forward/data.json`, read on the morning of 13 November. Earlier reports: *A Difficulty for Promotions* [1], *The Whole Line* [2], *A Stale Dial* [3], *Outgrowing Yourself* [4].

## Abstract

Paul asked why it has been days since a result, whether anything is being waited for, whether the fleet can keep mining while it waits, the way a blockchain does, and whether the brain is already as good as it can get. **The line has not gained since 6 November.** Main last moved at 11:17 that day. Since then ten generations have gone onto the line, and their held-out reads claim **+6.49 a seat** between them. The proof, which plays main against the line, reads the line at **−0.01 ± 0.06** over 29,600 seeds. The anchor reads say the same from another side: each plays the defaults of three generations back against today's. From 1 to 6 November, 15 of 21 anchors found today's defaults better by two errors or more, by 1.16 a seat on average. Since then none has, and the last four read the older defaults *ahead*, by +0.05 to +0.60. Three things explain it, all measured. **The game got noisier, and the bar went down.** A seed now swings **8.1 a seat**; the planner's stages were tuned on 29 October for 4.9. On today's defaults the trials' true gains spread only **0.20 a seat** around their mean, so a 55-seed first read correlates 0.18 with the truth. The ratchet, dry for four hours, lowers its held-out bar to z 1.5. That is a difficulty retarget, as Bitcoin's is, but a block here is a statistical claim, not a checked hash, so lowering the bar holds the block rate and empties the blocks. The trials that passed their stages from 10 to 13 November read +0.72 there and **+0.09** again on fresh seeds: they keep 0.12 of what they claimed, where in the first week they kept a third. **The largest gain was waiting on a person, and nothing said so.** `w_smooth = 0.525` has read **+2.0 to +4.3 a seat** held out, about ten times anything on the line. The trade rule has refused it **13 times** since 5 November, because it also gives up **0.30 to 1.33 kills less deaths a seat**, past 2.5 times that floor. **The dials are nearly spent, the brain is not.** All 56 A/B versions and every far read are asked, and the spread near today is the smallest yet. But one switch inside `w_smooth` is worth +3, and a family that collapses from 400 runs of 400 to none when `w_pos_defend` goes from its 0.75 to 0.375 says the next gains are in the code. Seven recommendations follow, with costs in fleet-hours. The first three: decide or split `w_smooth`; stop minting empty blocks by raising the held-out bar back to z 2.5 and spending a dry spell on wider search; and settle the line's ten generations in one factorial read of about five fleet-hours. A daily rating against three frozen brains is the chain Paul asked for: every block on it a measurement, never a claim.

*Index Terms*: winner's curse, optimizer's curse, empirical Bayes, sequential testing, false discovery, difficulty retargeting, design of experiments, coevolutionary cycling, hall of fame, variance reduction, Goodhart's law.

## I. The question

Paul, on 13 November, after the planner's two crashes were fixed: "What can we do to always increase steps forward? It's been a while since we had a result. Is there anything we are waiting for, or do we just need to test the best numbers change? Is there a way to continue, to mine like a blockchain, while we wait for the winner? If it's been days since we found a result, what about this process can we investigate to allow for a result to appear? It could be we are maximally optimized, but I doubt it. Write a lab report about incremental progress every generation: how we can always move forward, and how we can apply a better training harness."

Six questions, then: whether there has been a result (section III), whether the generations are real (IV), why not (V), what is being waited for (VI), whether this is the optimum (VII), and how to move forward every generation with a better harness (VIII and IX).

## II. What a generation is, and the ratchet that paces it

A **trial** is a few dials moved from today's defaults, drawn by `suggest.py` from a fit to every census so far. It is read in **censuses**: whole games of treadcore on the CPUs, sixteen seats in three teams, the trial's team against two teams on the defaults. Every seed is played three times, so that each team takes the trial seat once and the starts' unevenness cancels (`brain_census`, "Fair"). The measure is the trial team's score less the defaults', a seat. The reads go in stages, **55, 82, 124, 187, 275 and 418 seeds**, each with a bar to read on and two with a bar to pass (`SEQ`, 29 October). A trial that passes has **held-out reads** of 400 seeds that no stage has seen. A held-out read past `HELD_Z` (3.0), less the ease, makes a **candidate**. A candidate that gains at least `MIN_GAIN` (0.25 a seat), whose families hold, whose trades are within the rule and whose tests pass is committed to **the line** as a **generation**. Main takes the line only through **the proof**: main's values against the line's, 400 seeds a read, pooled until z 3.

The **ratchet** paces the generations (`ease`, 1 and 3 November). Each generation raises the bar; four hours without one lowers it, and lowers it again each hour after, down to a floor. The floor is an ease of 1.5. There, every stage's read-on bar is lowered by 0.5, the stages' pass bars by 1.5 (to z 1.1 at 187 and 275 seeds, and **z 0.5 at 418**), and the held-out bar to **z 1.5**. On the evening of 12 November, 41 hours after the last generation, health said it stood at its easiest and found nothing: "the brain itself needs a change".

## III. The record since main last moved

| | Since 1 November | Since main last moved (6 Nov 11:17) |
|---|---|---|
| Generations committed | 37 | 10 (r0220 to r0326) |
| Main moves | 8 | **0** |
| Claimed by the generations' held-out reads | — | **+6.49** a seat |
| The proof's best-read head | — | 769cfa2 (8 generations): **−0.01 ± 0.06** over 29,600 seeds |
| The line now | — | f1ce347 (10 generations): −0.01 ± 0.17 over 3,200 seeds |

*Table I. The line's record. A claim is the sum of the generations' held-out reads; the proof reads main's values against the line's on fresh seeds and pools its reads while the line's head stands.*

!html(forward/fig-line.html)

*Fig. 2. The line since main's last move. The orange step is the claim, which rises with each generation's held-out read. The green points are the proof's reads of the line over main, one for each head it read, ± 1 se. Hover a mark for its numbers.*

**There has been no result since 6 November: the line's ten generations sum to nothing measurable.** The closest the line came was its fourth head, 8017a71 (r0220 to r0239). It read +0.25 ± 0.08 over 13,600 seeds, z 2.92, a tenth of an error short of the proof's bar. Then r0254 landed, the head moved, and no later head read as well: the four read most, +0.12, +0.09, +0.16 and −0.01. Two kinds of dial movement on the line are signs of chance rather than gain. Some dials went back and forth: `duck_ready` 1.5 → 3 (r0223) → 0.75 (r0290); `wing_ahead` 16 → 11.2 (r0235) → 40 (r0290); `ping_warn_reach`, which main took from 25 to 6.25 on 6 November, went back to 24.6 (r0235). And r0257 turned `crew_stay` off on +0.27 ± 0.14. That switch was turned on by hand on 1 November for building: +3.16 built a team, at −0.26 on the score [3].

## IV. Are the generations real? The anchors

After each promotion the planner reads the defaults from three promotions back as a trial against today's (`anchor_trial`, 1 November): three census reads, 855 seeds in all. It is the one measurement in the system that asks whether three generations together are better than none. Negative means today's defaults are better.

!html(forward/fig-anchors.html)

*Fig. 1. Every anchor read: the defaults three generations back, less today's, ± 1 se. Filled marks are two errors or more from even. The dashed line is main's last move.*

| Anchors read | Reads | Mean, old less today | Range | Today's better by two errors |
|---|---|---|---|---|
| 1 – 6 November, to main's last move | 21 | **−1.16** | −3.08 to +0.22 | 15 |
| 6 – 9 November | 6 | −0.19 | −0.42 to +0.13 | 0 |
| 10 – 13 November | 4 | **+0.39** | +0.05 to +0.60 | 0 |

*Table II. The anchors, in three periods.*

**Real progress was fast until 6 November and stopped there.** Through the first week, three generations at a time made the defaults better by one to three points a seat, which is why main moved eight times from 1 to 6 November. Since then the anchors sit at even, and since 10 November on the old side of it. Each anchor is a single read of ±0.33, so no one of them settles anything. Ten in a row, though, agree with the proof, read on different seeds by a different method: **the line since 6 November has made generations without making the brain better.**

## V. Why: the noise, the spread and the bar

**The noise grew with the game.** A census's error over a seed's root gives a seed's swing, and the queue's own reads show it across every set of defaults. It was 4.6 to 5.3 a seat until 30 October. That evening `advance_plan forward` and `mine_plan raid` became the defaults (treadcore 17cf9f7), and it went to 10 to 12. After game 8 (9165c1d, 2 November) it settled at about 7 to 8. On today's defaults it is **8.1**, over 1,966 first reads. The planner's stages say in their own comment that they were simulated for 4.9.

**The spread of the trials is the smallest it has been.** The first reads of one set of defaults spread by their own noise plus the spread of the trials' true gains; the difference of variances measures the second, τ. On 1 and 2 November τ was 0.8 to 1.9 a seat: some trials were truly much better. Since 6 November it has mostly been 0.4 to 0.7, and on today's longest-read defaults (769cfa2) **0.20**, around a mean of −0.01. Those spreads also count the trials that break the game (−3 to −20 a seat), so even they overstate the side worth having. At τ 0.20 a first read of 55 seeds (± 1.09) correlates **0.18** with the trial's true gain, and a read of 400 seeds 0.44.

**What passed, read again.** The held-out reads are the honest test of the stages: on seeds no stage saw, they say what the trials that passed truly hold.

!html(forward/fig-kept.html)

*Fig. 3. The trials that passed their stages: the mean of the reads that passed them, and the mean of their held-out reads, by period. "Kept" is the second over the first. Simple means over trials. In an inverse-variance pool, a switch that changes nothing (reading 0 with an error near 0) would outweigh the rest.*

| Period | Trials | Stage reads | Held-out reads | Kept | Slope, held on stage |
|---|---|---|---|---|---|
| 28 Oct – 1 Nov | 179 | +0.41 | +0.13 | 0.33 | 0.63 |
| 2 – 5 Nov | 358 | +0.60 | +0.19 | 0.32 | 0.53 |
| 6 – 9 Nov | 234 | +0.68 | +0.14 | 0.20 | 0.59 |
| 10 – 13 Nov | 203 | +0.72 | **+0.09** | **0.12** | **0.19** |

*Table III. Stage reads against held-out reads.*

As the bar fell, the stage reads that passed rose, from +0.41 to +0.72, and what they held fell, from +0.19 to +0.09. A trial selected for a high read is selected partly for its luck: the winner's curse of the oil-lease auctions [5], the optimizer's curse of decision analysis [6]. The lower the bar and the smaller the true spread, the larger luck's share. In the last period it is nearly all of it.

**The ratchet is a difficulty retarget.** Bitcoin retargets its difficulty every 2,016 blocks to hold ten minutes a block [7], and it can, because anyone checks a block exactly: a hash under the target is a fact. The ratchet does the same to hold a generation every few hours, lowering its bar after four dry hours. **BUT A GENERATION'S VALIDITY IS A STATISTICAL CLAIM, NOT A CHECKED HASH: LOWERING THE BAR KEEPS THE BLOCK RATE AND EMPTIES THE BLOCKS.** A blockchain's other half is that every node re-verifies every block, and a block that fails is orphaned. Here that half exists, in the proof and the anchors. They have orphaned every block since 6 November, and nothing acts on it: the line keeps them.

**Why the ratchet was built to ease.** The planner's own simulation (`difficulty-sim.py`) draws the trials' true gains from a normal distribution and reads them as the planner does. In every such model, lowering the bar adds more true gains than false ones, because a normal distribution always has a right tail to find. Given the queue, the simulation measures about N(−0.24, 0.38) and promises **+5.8 a seat a day** at an ease of 1.5 on the run drawn here (+7.2 and +7.9 on two earlier runs that morning: it is a simulation, and the queue moves). Given the mean and swing measured here, it still promises +0.7 to +3.8, for a spread of 0.10 to 0.20.

!html(forward/fig-sim.html)

*Fig. 5. The true gain a day each model promises at today's ease of 1.5, and the gain the proof measured since main last moved (its best-read head over the days between, ± 1 se). Hover a bar for the promotion rate, each promotion's true gain and the share truly worse.*

**The measured gain is −0.001 ± 0.009 a seat a day.** No normal model of the trials gives that. The trials' true gains are not normal: they hold many small effects, a long tail of breakages, and almost nothing on the right. A simulation built on a normal is the reason the floor was set where it is (1 November), and it should not be trusted to set it again until it is fed the right tail the held-out reads measure (Table III), not the spread of the first reads.

## VI. What we have been waiting for

**`w_smooth = 0.525`.** One trial has passed both held-out reads on nearly every set of defaults since 5 November, and each time the trade rule refused it.

!html(forward/fig-smooth.html)

*Fig. 6. `w_smooth = 0.525`, each time the trade rule refused it: its held-out gain on the score (green), and the kills less deaths it gave up (orange, ± 1 se). The dashed line is the rule's limit, 2.5 times the 0.10 floor.*

Thirteen refusals from 5 to 10 November, held out at **+2.00 to +4.32** a seat (median +3.31), each giving up **0.30 to 1.33** kills less deaths a seat (the last nine 0.30 to 0.55), 3 to 13 times the floor. The rule lets a trade of 2.5 times through by itself and refuses past it, by itself (`trades_away`, 4 November: "nothing waits"). So nothing waits, and nothing tells a person either. The planner asks the trial again on each new set of defaults: 56 censuses and **11,382 seeds** so far, and on the morning of this report it was being read a fourteenth time (w19844, +2.88 over four held-out reads). `w_smooth` is not one dial. Its doc in `weights.rs`: "the move's desire vector and the retreat thresholds blend by it; the rung's and the turret's confirmation, the stance's advance scalar and resupply by the doctrine alone act above 0.5 (yes or no)". At 0.05, the default, all four of those are off. At 0.525 all four come on together, and the blend moves tenfold.

**This is a decision about what the bot is for, and it is a person's.** The score says +3.3; the fights say −0.47. When a measure becomes the target it can be gained by giving up what it was meant to stand for. The trade rule exists against exactly that, Goodhart's regressional and adversarial cases [8]. But a +3.3 gain at a cost of 0.47 is not obviously a bad trade, and the switch is five changes bundled in one number. The other things waiting on a person:

- **The hold on `w_pos_fortify` 0.4**, in `hold.json` since 1 November [3]. It is still there, and every trial that sets it is still read and never promoted.
- **"A raid on the held ground."** Four candidates passed both held-out reads and fell under this family's floor of 95%, every one to **0 of 400**: w17362, w18357, w18795, w18871. All four lowered `w_pos_defend` from its 0.75, to between 0.19 and 0.38; at 0.75 and at 1.5 the family holds 400 of 400. A fifth (w16444, `w_pos_economy` 2.8) fell to 29 of 400. A family that falls from 400 to 0 on a small move is a cliff, a threshold somewhere in the code, not a trade-off. The floor caught it correctly, and each such candidate is lost until someone finds the threshold.
- **The proof**, which will not pass while the line is not better than main.

## VII. Are we maximally optimized?

**Near today's defaults, at the resolution the fleet can afford, very nearly.** The evidence:

- The spread of the trials' true gains on today's defaults is 0.20 a seat.
- All 56 A/B versions of the brain's choices have been asked on today's defaults, and no far read is left (`plan/search.json`: `ab` 56 of 56, `far_left` 0). The search has tried 237 distinct trials since the last generation.
- Finding a true +0.25 at z 3 against a seed's swing of 8.1 takes (3 × 8.1 / 0.25)² ≈ **9,400 seeds** of it alone. That is 1.3 hours of the whole fleet, and the fleet reads about 1,100 trials a day.

**Everywhere else, no.** The gains that made the first week were not small moves of many dials:

- turning `pings` off (+1.92 held out, r0062);
- `mine_plan` 2 → 1 (+2.05, r0068);
- a stale dial, `w_pos_fortify` 6 → 1.5 → 0.75 (+1.06, then +1.34) [3];
- the building switches `cycle_all` and `crew_stay` (+3.16 built) [3].

Today's evidence points the same way:

- **`w_smooth`'s switch is worth +3 by itself**: the size of the first week, sitting behind one coupled dial.
- **`w_pos_defend` has a cliff**: one family falls from 400 of 400 to none somewhere between 0.75 and 0.375.

**The brain is not at its optimum. The search's neighbourhood is. The next gains are in what the code lets a dial mean**: splitting a switch that bundles five behaviours, finding a threshold that makes a family fall off a cliff, adding the choices nobody has written yet. This is what health has been saying since 11 November.

## VIII. Mining while we wait

The fleet never stops: it reads **178,316 seeds a day**, three matches each, 153,492 of them in the search (first reads 59,000, read-ons 74,000, held-out 20,000) and about 16,000 in the proof. What Paul asks is what that work should append to, so that every day adds something that stays.

**What already stays.** Every census is kept in the queue and read by the fit: since 1 November, `suggest.py --memory` reads past sets of defaults as well: 5,950 rows of earlier defaults beside today's 560 on the morning of this report. That is the ledger, and it is already the right shape for "mining": append-only, never discarded, every row a true difference on its own day.

**What should not be appended.** A generation passed on a z of 1.5, selected from about 1,100 first reads a day at a spread of 0.20, is mostly luck. Ten of them cost the line its proof (the head moves, and the pool starts again) and turned back dials a person set. **AN EMPTY BLOCK IS NOT FREE: IT COSTS THE NEXT REAL ONE ITS PROOF.**

**What a block should be.** A blockchain's blocks are trustworthy because each is checked, not because they come often. Two kinds of block can be checked here:

1. **A rating against frozen brains**: today's defaults read against three fixed past mains every day, about 2,000 seeds each. It is always valid, because it is a measurement and not a claim. It only moves when strength does, and it shows cycling, a generation beating its parent and not its grandparent, which a chain of parent-against-child reads cannot see [9], [10], [11].
2. **A generation through a calibrated gate**, whose claim is what the held-out reads of trials like it have kept (Table III), not what its own read says. The pass is decided on that shrunken value [12].

## IX. Seven steps forward, and a better harness

| # | Step | Cost | What it should buy |
|---|---|---|---|
| 1 | **Decide `w_smooth`, or split it.** Make its five behaviours their own switches (rung confirmation, turret confirmation, the stance's advance scalar, resupply by doctrine, and the blend), so the search reads each alone. Stop re-asking a refused trial on each new set of defaults until a person or a rule changes. | Splitting: a treadcore change, then about 5 × 1,600 seeds (1 fleet-hour) | The largest known gain, +3.3, without the fights it costs, if one switch carries the gain and another the loss |
| 2 | **Stop minting empty blocks.** Put the held-out bar's floor back to z 2.5 (an ease of 0.5). When four hours are dry, widen the search instead of lowering the bar: larger moves, the far reads again on today's defaults, more seeds a trial. | A value in `line.json`; widening is built (`bound`, far reads) | Fewer generations, each worth its proof; the line stops turning back dials |
| 3 | **Settle the line.** Read its ten generations in one Plackett–Burman design [13]: 12 settings of the ten changes, each against main, 3,200 seeds a setting. Keep the generations whose own effect is past two errors, rebuild the line from them, and let the proof decide. Or reset the line to main, which loses nothing measured. | 38,400 seeds: about **5 fleet-hours** | Each generation's own effect to ±0.08; a line that can pass its proof |
| 4 | **Rate against frozen brains, daily.** Today's defaults against main as it stood on 28 October (dc3df01), 2 November (da7e1da) and 6 November (63f2667), 2,000 seeds each, kept as a table and drawn on a Results page. | 6,000 seeds a day: **3% of the fleet** | The chain Paul asked for: a record of strength that only moves when strength does, and that sees cycling [10], [11] |
| 5 | **Retune the stages for 8.1, not 4.9.** Feed `difficulty-sim.py` the right tail the held-out reads measure, then set the first read's size and the stages from it. At a spread of 0.20, a first read of 220 seeds correlates 0.34 with the truth, and one of 55 0.18. | A simulation and a value; no fleet time | Fewer trials, each better known; the false share down [14], [15] |
| 6 | **Weigh the maps by their swing.** A seed swings 4.1 a seat on naval and 12.8 on big-lizard (Fig. 4). Pooling each map by its precision, rather than equally, gives the same error with **26% fewer seeds**. It changes what "better" means, towards the steadier maps, and that is Paul's call. | A change to `pool` | A quarter more reads for the same seeds [16] |
| 7 | **Find the cliff.** Read "a raid on the held ground" across `w_pos_defend` from 0.75 down to 0.375 in steps, and look at one match where it falls. | About 4,000 runs of the family; an hour of a person | A threshold found, and the candidates it has been throwing away given back |

*Table IV. The steps, in order. A fleet-hour is about 7,400 seeds.*

!html(forward/fig-maps.html)

*Fig. 4. A seed's swing on each map, from the held-out reads and proofs since main last moved: each map's error times the root of its seeds (about a thirteenth of the read).*

**On a better training harness.** The harness today is a funnel: sequential reads [17], as Stockfish's fishtest runs them [18], a held-out confirmation, and a proof. It is a good design for a world with a right tail. Steps 2, 3 and 5 adapt it to a world without one. Beyond them, three directions from the literature fit this fleet, in order of fit:

- **Gradient steps from every read.** SPSA [19] or an evolution strategy such as CMA-ES [20] moves the defaults a little each generation, by the read-weighted average of every trial, rather than jumping to one winner. Nothing read is wasted, and the step size can be held to what the proof confirms. On a landscape as flat as today's it will move slowly. Its place is after step 1 adds switches with something on the other side of them.
- **Racing with early stopping**, as successive halving and Hyperband do [21]: many arms, few seeds each, the bottom half dropped at each rung. That is what `SEQ` already is. Its rungs need resetting for this noise (step 5).
- **A league, not a ladder.** A population of brains, each read against a mix of the others and of frozen past ones, the way AlphaStar's league was trained [10] and as crucible's islands already are. On the CPU side that means bot styles and personas as standing opponents in the census, not only the defaults.

## X. The same shape on the GPU

Crucible's world ladder has not made a milestone past M0015 since 4 November [4]. The maze home elects one by a timer when none is earned ("elected, 3.0 h without a generation"). On 12 November, M0034 and M0035 read **−5.01 ± 1.03** and **−5.05 ± 1.02** a seat in the game, as the Gladiator, against the shipped M0015 (bridge reads 19 and 20). An election by timer is a retarget too: it keeps the generations coming and does not make them better. The fixed yardstick of step 4 is what tells the two apart, there as here.

## XI. What is not shown, and what is open

- **τ is a difference of variances, and it assumes the seeds' noise is the same across trials.** Trials that break the game add to it. That is why the spread overstates the useful tail, and why Table III is the better measure.
- **The anchors are single reads of about ±0.33.** No single anchor decides anything; the run of them and the proof decide together.
- **Noise and cycling are not separated.** Both predict anchors at even. The dials going back and forth fit noise; a frozen-brain rating (step 4) would show cycling if it is there.
- **Additivity is not tested.** The ten generations may each be real and cancel together. Step 3's factorial reads their interactions' sizes as well as their effects.
- **The simulation is normal by construction** (`difficulty-sim.py`). Fig. 5 shows how far that is from what was measured. It is not a model of the right tail.
- **Map weighting changes the measure.** The 26% is for the same error on a different average.
- **What `w_smooth`'s gain is made of has not been read.** Splitting it (step 1) is what reads it.
- **Some machines stamp their censuses in UTC.** The anchors here are placed by the keeper's end time for each job, not by the census stamp.

## XII. How to make it again

`python3 tools/report/forward.py ~/code/treadcore/build/queue/grove docs/forward` reads every census the queue has fetched (about 45,000), runs the planner's simulation four times, and writes `docs/forward/data.json` and the six figures, in about a minute and a half. `sh tools/report/all.sh` builds this page with the rest.

## References

[1] orrery, *A Difficulty for Promotions: How Often the Brain Should Change, Measured*, lab report, 29 October 2026.

[2] orrery, *The Whole Line: How the Fleet's Work Reaches treadcore, and What Stops It*, lab report, 1 November 2026.

[3] orrery, *A Stale Dial: What We Measured, What Changed, and What We Refused*, lab report, 1 November 2026.

[4] orrery, *Outgrowing Yourself: What the GPU Hands the Game, What a Generation Keeps, and Whether the Card-Hours Pay*, lab report, 6 November 2026.

[5] E. C. Capen, R. V. Clapp, and W. M. Campbell, "Competitive bidding in high-risk situations," *Journal of Petroleum Technology*, vol. 23, no. 6, pp. 641–653, 1971.

[6] J. E. Smith and R. L. Winkler, "The optimizer's curse: Skepticism and postdecision surprise in decision analysis," *Management Science*, vol. 52, no. 3, pp. 311–322, 2006.

[7] S. Nakamoto, "Bitcoin: A peer-to-peer electronic cash system," 2008. [Online]. Available: https://bitcoin.org/bitcoin.pdf

[8] D. Manheim and S. Garrabrant, "Categorizing variants of Goodhart's law," arXiv:1803.04585, 2018.

[9] C. D. Rosin and R. K. Belew, "New methods for competitive coevolution," *Evolutionary Computation*, vol. 5, no. 1, pp. 1–29, 1997.

[10] O. Vinyals et al., "Grandmaster level in StarCraft II using multi-agent reinforcement learning," *Nature*, vol. 575, pp. 350–354, 2019.

[11] D. Balduzzi, K. Tuyls, J. Pérolat, and T. Graepel, "Re-evaluating evaluation," in *Advances in Neural Information Processing Systems 31*, 2018.

[12] B. Efron, *Large-Scale Inference: Empirical Bayes Methods for Estimation, Testing, and Prediction*. Cambridge, U.K.: Cambridge Univ. Press, 2010.

[13] R. L. Plackett and J. P. Burman, "The design of optimum multifactorial experiments," *Biometrika*, vol. 33, no. 4, pp. 305–325, 1946.

[14] Y. Benjamini and Y. Hochberg, "Controlling the false discovery rate: A practical and powerful approach to multiple testing," *Journal of the Royal Statistical Society, Series B*, vol. 57, no. 1, pp. 289–300, 1995.

[15] J. P. A. Ioannidis, "Why most discovered true associations are inflated," *Epidemiology*, vol. 19, no. 5, pp. 640–648, 2008.

[16] A. Deng, Y. Xu, R. Kohavi, and T. Walker, "Improving the sensitivity of online controlled experiments by utilizing pre-experiment data," in *Proc. 6th ACM Int. Conf. Web Search and Data Mining (WSDM)*, 2013, pp. 123–132.

[17] A. Wald, "Sequential tests of statistical hypotheses," *Annals of Mathematical Statistics*, vol. 16, no. 2, pp. 117–186, 1945.

[18] Stockfish developers, "Fishtest: the Stockfish testing framework." [Online]. Available: https://github.com/official-stockfish/fishtest

[19] J. C. Spall, "Multivariate stochastic approximation using a simultaneous perturbation gradient approximation," *IEEE Transactions on Automatic Control*, vol. 37, no. 3, pp. 332–341, 1992.

[20] N. Hansen, "The CMA evolution strategy: A tutorial," arXiv:1604.00772, 2016.

[21] L. Li, K. Jamieson, G. DeSalvo, A. Rostamizadeh, and A. Talwalkar, "Hyperband: A novel bandit-based approach to hyperparameter optimization," *Journal of Machine Learning Research*, vol. 18, no. 185, pp. 1–52, 2018.
