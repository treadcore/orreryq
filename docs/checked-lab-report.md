# Every Block Checked: A Line That Settles, a Block That Comes Off, One Dial at a Time, a Cliff Explained, `w_smooth` Split, and a Fixed Yardstick

*Paul Richeson · Lab Report — IEEE Format · 13 November 2026*

Paul Richeson, treadcore.org; Claude Code (Claude Fable 5.2) as the pair. Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery and treadcore.

Companions: orrery `tools/plans/treadcore.py` (`settling`, `orphan`, `refused_still`, `far_trials`, `rating`, `prep_id`), `tools/fleet-queue.py` (`builder`), `tools/plans/board-check.py`, `tools/fleet-queue-check.sh`, `tools/report/checked.py` (the figures and numbers here), `tools/plans/line.json` (three new values); treadcore `source/treadcore-brain/src/weights.rs` (`smooth_part`) and `commander.rs`, LR 157. The data: `docs/checked/data.json` and `docs/checked/cliff.tsv`. This report builds what *Always Forward* [1] recommended that morning; orrery commits c76ef92, 971de6b and 5a730fc.

## Abstract

*Always Forward* [1] found that the line had made ten generations since 6 November and gained nothing, and listed seven steps. Paul read it and said three things: "it seems that we abandon a block too frequently", "can we adjust one parameter at a time", and "Remove a block that fails. The fixed yardstick. Implement." This report is what was built that day, and what each piece was measured to do. **Nine things were built, and each has its diagram here.** (1) **A second lane** on saskatchewan and boburner: a census leaves most cores idle between jobs and in each job's tail, and a second lane took saskatchewan from about 1,810 to about 2,700 seeds an hour. (2) **The iMac keeps only its own jobs**: a read there took 2,490 s against macmini's 85. (3) **The held-out bar is back at z 2.5.** (4) **The line settles before it grows**: of 37 line heads the proof had read, 28 were left when a generation moved the head, after a median 1,600 seeds, where a true +0.25 takes 9,400 to show; now no generation joins the line until the proof has read its head 9,600 seeds, six reads at a time. (5) **A block that fails its check comes off**: a head read its seeds whose lead, with two errors added, is still under 0.25 is orphaned, and the fleet builds main again. (6) **A refusal is kept**: a trial the trade rule refused is not read again until the rule moves. (7) **One dial at a time, round after round**: trials that move three or four dials are nine in ten, and their true gains spread 0.25 to 0.30 a seat; trials that move one spread 1.15. The single-dial sweep now repeats, a step nearer each round, and takes half of each generation's new trials. (8) **`w_smooth` is split** in treadcore into four choices, each read alone by the A/B trials; at the defaults no game plays differently. (9) **The fixed yardstick**: once a day, today's defaults against main as it stood on 28 October, 2 November and 6 November, 2,000 seeds each, the same seeds every day. One thing was found and not changed: **the cliff under `w_pos_defend` is a tie.** The family "a raid on the held ground" holds 400 of 400 at the default 0.75 and 56 of 400 at 0.74, because the posture is an auction and Defend's bid of 0.75 only equals the building posture's. Section XI says what happened to the line's ten generations under the new rule, and what is still open.

*Index Terms*: sequential testing, confirmation before commitment, orphaned blocks, one-factor-at-a-time, factorial confounding, tie-breaking, hall of fame, fixed benchmark, continuous delivery.

## I. The instructions

Paul, 13 November, in order: "yes build 1 and 2. commit push." Then, on the first three steps of *Always Forward*, quoted back. Then: "Reading the Always Forward, it seems that we abandon a block too frequently. Analyse these claims, implement a reasonable way to train. Also can we adjust one parameter at a time, is that even in the procedure? At the beginning we adjusted multiple and tried to stand up above the noise. Is there a way to make it more specific?" Then, of the order proposed (the removal rule and the ten old generations, the cliff sweep, the `w_smooth` split, the daily rating): "Do your recommendation. Remove a block that fails. The fixed yardstick. Implement. Write lab report."

!html(checked/dia-road.html)

*Diagram 1. The road of a promotion, from a trial to main, with what was added on 13 November marked NEW. Blue boxes are data and say where it is kept; orange boxes are functions, by their names in `tools/plans/treadcore.py`; green boxes are outcomes. A dashed arrow is something read, not a step taken.*

## II. A second lane on a machine

A census splits its seeds over every core (`JOBS=$(nproc)`) and is as long as its slowest share. Sampled each five seconds for a minute, saskatchewan ran 3, 2, 0, 0, 0, 8, 6, 4, 4, 17, 17 and 17 census processes on 24 threads. Between jobs nothing ran for about fifteen seconds, and each job ended in a tail of a few slow seeds. The fleet's "98% busy" [2] counted lanes, not cores: the load average was 7 to 10 of 24 on saskatchewan and 6 to 8 of 16 on boburner.

**What was built.** A host entry in `config.json` with `"build_of"` naming the machine's first lane is a second lane there. The keeper asks after the first lane's build (`builder()`), and the planner asks no build of the second (`prep_id`). Nothing else distinguishes it: it is paused, finished and restarted with its machine through `lane_of`, as a CUDA lane is.

!html(checked/dia-lane.html)

*Diagram 2. A second lane. Two entries in `config.json` make two lanes on one machine; the second asks after the first's build through `builder()`, and the planner's `prep_id()` asks no build of it.*

**What it did.** Saskatchewan read 6,346 seeds from 04:00 to 07:30, 1,813 an hour. In the first minutes with two lanes it read about 2,700 an hour, and its load went to 19. That is a short window, and the gain should be read again over a day. Boburner has a second lane as well, not yet measured.

**The iMac.** A trial read took 2,490 s on the iMac's lane and 85 s on macmini's: 63 jobs in 43.6 hours since 11 November, and any trial whose next read fell there waited forty minutes. Its lane now takes only jobs that name it (`caps: ["own"]`). It was not left the background pieces, as first proposed: a held-out read owns the pieces read ahead for it, so one running on the iMac would hold that read as long.

## III. The held-out bar

`ease_max` and `ease_now` are 0.5 in the queue's `tuning.json`, so a held-out read passes at z 2.5 and the ratchet cannot lower it past that. On the Values page; nothing in code.

## IV. Blocks abandoned

!html(checked/fig-heads.html)

*Fig. 1. Every line head the proof read: the seeds it had been read when it passed or was left, and its z then. A head is left when a generation moves it, and the proof's pool begins again. Hover a mark for its numbers.*

| | Heads | Median seeds read | Median hours |
|---|---|---|---|
| Passed, and main moved | 9 | — | — |
| Left when the head moved | 28 | 1,600 | 1.3 |
| Left past z 2 | 4 | 800 to 13,600 | — |

*Table I. The proof's heads, 1 to 13 November. 91% of the proof's seeds went to heads that were left.*

**Paul's reading was right.** A true +0.25 against a seed's swing of 8.1 takes (3 × 8.1 / 0.25)² ≈ 9,400 seeds to show at z 3 [1]. Four heads of 37 were ever read that many. 8017a71 stood at +0.25 ± 0.08, z 2.92, over 13,600 seeds when r0254 landed on it. The same is true one level down: on the last long-read defaults, 959 of 1,938 trials were dropped after one read of 55 seeds, and a trial truly worth +0.3 reads under z 0 there about four times in ten. That second level is not changed here (section XII).

**What was built: the line settles before it grows** (`settling`). While the line's head has not been read `SETTLE_SEEDS` (9,600) seeds by its proof, `auto_promote` adds no generation: a test begun is read until it is decided [5]. The proof meanwhile is asked at once, with no hour between, six reads of 400 seeds at a time. Candidates that pass in the meantime stay candidates on the same defaults, and `auto_promote` takes the strongest when the hold ends. A head read its seeds and neither proved nor refused is read on to twice as many, then let go. A head whose proof cannot be asked holds nothing past eight hours.

!html(checked/dia-settle.html)

*Diagram 3. The line settling. `auto_promote()` asks `settling()` before any generation; while the head is short of its seeds the generation is held and `line_proof()` reads the head six reads at a time, and the pooled reads are what `settling()` counts.*

## V. A block that fails comes off

**What was built** (`orphan`). When a head has been read its 9,600 seeds and its lead over main, with two errors added, is still under `MIN_GAIN` (0.25 a seat), the line comes off:

- each of its promotions is marked `orphaned`, with the read that orphaned it;
- the line's branch is set to main's commit;
- the fleet builds main again, and the search reads against main's defaults;
- main is not touched and nothing is pushed.

It is the half of a chain that *Always Forward* found missing: every node checks a block, and one that fails is orphaned [6].

The trials are not forgotten. Each stays a candidate of its day and may be read again on main's defaults, as any older candidate is, now against a bar of z 2.5.

**The three outcomes of a check**, then: proved (z 3: the line goes to main, as before), refused (the upper bound under 0.25: orphaned), or undecided (read on, to 19,200 seeds, then let go).

!html(checked/dia-orphan.html)

*Diagram 4. The three outcomes of a line's check, from the one pooled proof: proved and pushed by `resolve()`, refused and taken off by `orphan()`, or neither and read on.*

## VI. A refusal is kept

`w_smooth = 0.525` was the strongest older candidate on every set of defaults, so `reread_older` asked it again each time, and each time the trade rule refused it: 13 times, 56 censuses, 11,382 seeds [1]. Now a trial the rule refuses is kept in the planner's state with the rule as it stood (`TRADE_TIMES` and the three floors), and `reread_older` passes over it until one of those moves.

!html(checked/dia-refusal.html)

*Diagram 5. A refusal kept. `trades_away()` writes what it refused into the planner's state with the rule as it stood; `reread_older()` asks `refused_still()` and passes over it.*

## VII. One dial at a time

!html(checked/fig-dials.html)

*Fig. 2. The spread of the trials' true gains past their noise, by how many dials a trial moves; first reads since 6 November against the defaults.*

| Dials moved | First reads | Spread of true gains | Read held out | Held-out mean |
|---|---|---|---|---|
| 1 | 877 | **1.15** | 59 | +0.61 |
| 2 | 138 | 0.17 | 9 | +0.03 |
| 3 | 3,369 | 0.25 | 161 | +0.06 |
| 4 | 3,731 | 0.29 | 183 | −0.02 |
| 5 or more | 18 | — | 11 | −0.01 |

*Table II. Trials by how many dials they move. The one-dial row holds the repeated reads of `w_smooth = 0.525`, which lift its held-out mean; its spread also counts single dials that break the game.*

**The procedure did not adjust one parameter at a time, except in two corners.** The fit (`suggest.py`) draws each trial as three or four dials moved together: 7,100 of 8,133 first reads. A good move is then read together with two that may cancel it, and nothing says which dial did what. The two corners were the A/B trials (one switch or one choice) and the far read (each dial alone at a quarter and at four times), and the far read ran once for each game version.

**What was built** (`far_trials`, `FAR_STEPS`). When a round of the far read is done, the next begins on the defaults of its day, a step nearer: four times and a quarter, then twice and a half, then the root of two each way, and then twice and the root again for as long as the defaults keep moving. A round on defaults already read waits. Its share of each generation's new trials is a value, `far_share`, set to 0.5. Round 2 began that morning: 128 dials, 256 trials, each at twice and at half of today's.

!html(checked/dia-far.html)

*Diagram 6. One dial at a time. `far_trials()` writes one trial a dial at each end of a step; the trials go by the ordinary road; a round done begins the next at a smaller step.*

## VIII. The cliff

Four candidates passed both held-out reads and scored 0 of 400 on the family "a raid on the held ground" [1]. All four lowered `w_pos_defend`. The family was read across the dial on saskatchewan's build:

`SCENARIO=scenarios/families/a-raid-on-the-held-ground.toml RUNS=400 SCENARIO_SET="w_pos_defend=V" census-bin --ignored scenario_many --nocapture`

!html(checked/fig-cliff.html)

*Fig. 3. Runs held of 400, as `w_pos_defend` comes down from its default.*

| `w_pos_defend` | Held of 400 |
|---|---|
| 0.75 (the default) | **400** |
| 0.74 to 0.65 | **56** |
| 0.60 to 0.40 | 29 |
| 0.375 | 0 |

*Table III. The sweep. Six values from 0.74 to 0.65 all read 56; nine from 0.60 to 0.40 all read 29.*

**The cliff is a tie.** The team's posture is an auction (`board.rs`): each posture's value is its weight times its score, and the best wins, ties going to the earlier in the ladder's order. In the family, a raid on the held ground puts `base_threat` past a half, so Defend's score is 1 and its value is `w_pos_defend`, 0.75. The building posture's value in that scenario is exactly 0.75 as well. Defend wins on the tie. At 0.74 it loses in 344 seeds of 400, and the Commander goes on building: the trace at 0.70 reads "fortify: the squad is building" from 25 s to the end, where at 0.75 it reads "THE HELD GROUND RAIDED" at 29.9 s.

!html(checked/dia-auction.html)

*Diagram 7. The posture auction in `board.rs`. Each posture's value is its weight times its score; the best wins, and a tie goes to the ladder's order, where Defend stands first. In this family both values are 0.75.*

**This is not a fault in the family, and nothing was changed.** Lowering `w_pos_defend` does mean answering raids less, and the family's floor is the rule that says a raid is answered. What the sweep shows is that the default stands exactly on the edge: the search can raise this dial and can never lower it, and every trial that lowers it is read through its stages and its held-out reads before the family refuses it. Two ways out are Paul's to choose: a floor on the dial at 0.75, so no such trial is drawn; or the raid made a rule above the auction, as the base's own threat is (LR 24), which would free the dial to mean something else.

## IX. `w_smooth`, split

`w_smooth` blends the move's desire vector and the retreat thresholds, and above 0.5 it turns on four yes-or-no behaviours, each at one place in `commander.rs` (`Settings::smooth_on`): the turret's confirmation, the stance's advance scalar, resupply by the doctrine alone, and the rung's confirmation.

**What was built** (treadcore, LR 157, commit 3013570 on the branch `smooth-parts`). Four choices at the table's end: `smooth_turret`, `smooth_stance`, `smooth_supply` and `smooth_rung`, each `with_w_smooth | off | on`. `Settings::smooth_part(W)` answers for one part, and the four places ask it. At the defaults every part follows `w_smooth`, so no game plays differently, and the pinned brain names the four at 0. orrery's A/B trials read every version of every choice each generation, so each part is read on by itself.

!html(checked/dia-smooth.html)

*Diagram 8. `w_smooth` split. The blend stays the number's own; each of the four yes-or-no behaviours is asked through `smooth_part()`, which follows `w_smooth` until that part's own choice says off or on, and the A/B trials read each choice alone.*

**Proved.** `each_part_of_smoothing_follows_w_smooth_until_its_own_choice_says`; treadcore-brain, 178 passed.

**Not yet on treadcore's main.** A commit to the game's source replays the line and starts its proof's pool again, so the push waits for the line's check to end (section XI).

## X. The fixed yardstick

Every read the line makes is of a child against its parent. A chain of those cannot say whether the brain is stronger than it was a week ago, and it cannot see a generation that beats its parent and loses to its grandparent [3], [4].

**What was built** (`rating`). Once a day, today's defaults are read against main as it stood on three fixed days: 28 October (dc3df01), 2 November (da7e1da) and 6 November (63f2667). Each is a trial of that day's values on today's game, five reads of 400 seeds, and **the same seeds every day**, so that a day's difference is the brain's and not the draw's. The rows are kept in `plan/rating.json`: the day, today's commit, the old one, today's lead, its error, its seeds. A flag says each day's reading. It promotes nothing and decides nothing. The value `rating_seeds` sets its size; 0 turns it off. At 2,000 seeds a brain it is 6,000 seeds a day, about 3% of the fleet.

!html(checked/dia-yard.html)

*Diagram 9. The fixed yardstick. Three mains of fixed days, each read as a trial against today's defaults on the same seeds every day; the pooled rows are kept in `plan/rating.json`.*

**What it is not.** A dial the old main did not have stays at today's value: it is today's code with that day's numbers, not that day's game. And no page draws it yet.

## XI. The first day

**The line's check.** When the settle rule went live at 07:50 the line stood at f1ce347, ten generations, read 3,200 seeds at −0.01 ± 0.17. The planner raised "the line f1ce347 settles first: its proof has read 3200 of 9600 seeds" and asked six proofs at once (pv0347 to pv0352).

When this was written the first round was four reads of six back, and the head stood at 3,200 seeds counted. **The outcome is not in this report.** At −0.01 the rule will orphan the ten generations when the head reaches 9,600 seeds, unless the next reads lift its upper bound past 0.25: the planner's flag will say which, and the generations' states will read `orphaned` or stay. The `w_smooth` split goes to treadcore's main after that.

**The yardstick.** Its first round, fifteen reads of 400 seeds, was asked that morning and was in the queue when this was written. Its first rows will be of the line as it stood, f1ce347, against the three mains.

## XII. What is not built, and what is open

- **Trials dropped after one read.** Half of all trials stop at 55 seeds. The stages are still those simulated for a seed's swing of 4.9 [1]. A few days of one-dial rounds will say what the stages should be.
- **A page for the yardstick**, and for the orphans. The rows are in `plan/rating.json` and the planner's state.
- **The line's ten generations, read apart.** The combined experiment of *Always Forward* was not run: the proof had already read eight of the ten at −0.01 ± 0.06.
- **A build that was pruned.** If a line comes off and main's own build has been pruned from a machine, its build job reads as done and is not asked again. Main had never been built by the fleet on 13 November, so this could not happen that day. It is not handled.
- **`w_pos_defend`'s edge** (section VIII): a floor, or a rule. Paul's.
- **Weighting the maps by their swing** [1]: Paul's.
- **The second lane's gain** was read over minutes. It wants a day.
- **Which part of `w_smooth` carries the gain.** The fleet's reads will say, once the split is on main.

## XIII. How to make it again

`python3 tools/report/checked.py ~/code/treadcore/build/queue/grove docs/checked` reads the queue and writes `docs/checked/data.json`, the three figures and the nine diagrams; `--redraw docs/checked` draws them again from the data. The cliff's sweep is `docs/checked/cliff.tsv`, made by the command in section VIII. The checks: `python3 -I tools/plans/board-check.py`, `sh tools/fleet-queue-check.sh`, `sh tools/plan-check.sh`, `sh tools/restart-check.sh`.

## References

[1] orrery, *Always Forward: Why the Line Has Not Gained Since 6 November, the Gain a Rule Held Back, and a Harness That Mints Only Real Blocks*, lab report, 13 November 2026.

[2] orrery, *The Duty Cycle: The Fleet That Trains the Bots Is 98% Busy and Waits on No One*, lab report, 5 November 2026.

[3] C. D. Rosin and R. K. Belew, "New methods for competitive coevolution," *Evolutionary Computation*, vol. 5, no. 1, pp. 1–29, 1997.

[4] D. Balduzzi, K. Tuyls, J. Pérolat, and T. Graepel, "Re-evaluating evaluation," in *Advances in Neural Information Processing Systems 31*, 2018.

[5] A. Wald, "Sequential tests of statistical hypotheses," *Annals of Mathematical Statistics*, vol. 16, no. 2, pp. 117–186, 1945.

[6] S. Nakamoto, "Bitcoin: A peer-to-peer electronic cash system," 2008. [Online]. Available: https://bitcoin.org/bitcoin.pdf
