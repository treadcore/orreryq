# Old Decisions, Reopened: Eight Rules Set Aside or Changed as Trial Runs, What the Review Found, and the Next Round

*Paul Richeson · Lab Report — IEEE Format · 13 November 2026*

Paul Richeson, treadcore.org; Claude Code (Claude Fable 5.2) as the pair. Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery and treadcore.

Companions: orrery `tools/plans/treadcore.py` (`trade_allow`, `held_more_jobs`, `anchor_trial`, `orphan`), `tools/plans/line.json` (the values), `tools/plans/board-check.py`, `src/generations.rs` (the Yardstick tab), `tools/report/reopened.py` (the figures, diagrams and numbers here); the queue's `tuning.json`, `plan.json`, `config.json` and `hold.json`; treadcore branch `smooth-parts` (LR 157, and the floor in `RANGES`). The data: `docs/reopened/data.json`. This is the third report of the day, after *Always Forward* [1] and *Every Block Checked* [2]; orrery commits e7300f4, 7ab25bb and 509c91a.

## Abstract

*Every Block Checked* [2] ended with eight things open and eight rules questioned. Paul's answer: "Do them. Implement. We are fixing old training decisions. Adapt. Just trial runs. After you code it, review it again, write a lab report about the changes with diagrams, and also do another round of following your suggestions as you find more out." **Every change here is a trial run: a value or a line of configuration, with the way back written beside it** (Table I). **Six rules were set aside.** The transform rotation took **9.7% of the CPU machines' hours** (1,496 jobs in three days) making patches that no promotion can take. The clone rounds ran fifteen times, and no clone was shipped. Boburner's island made fourteen milestones that read **−6.78 a seat** on average in the game, where calber's eight read +0.17 and one was shipped. The rule that a dial moved in the last two generations needs z 3 fired twice in a week, and the bar of z 2.5 and the settling line now do its work. The anchor reads are replaced by the yardstick and by a line coming off. The hold on `w_pos_fortify` 0.4 dated from game 4. **Two rules were changed.** The trade rule's limit now grows with the gain: up to +1.0 a seat it is 2.5 floors as before, and past that in proportion, so `w_smooth = 0.525` at +3.3, giving up 4.7 floors, is within 8.25. And the first read is 150 seeds where it was 55, the same design at today's swing. **The review found one fault in the day's own work**: with the held-out bar back at z 2.5 and one held-out read of 400 seeds, only a read of +1.0 could pass, and a trial truly worth +0.3 would pass four times in a hundred. A held-out read that is promising and undecided is now read on, up to six reads. **One consequence is said plainly: with the trade rule changed, `w_smooth = 0.525` can now reach main by itself**, at a cost of about half a point of kills less deaths a seat. Section XII says how each trial will be judged and what would turn it back. Section XIII is the next round.

*Index Terms*: trial runs, reversible configuration, cost accounting, selection bias, sequential testing, proportional limits, Goodhart's law, code review.

## I. The instruction, and the method

Paul, 13 November: "Commit. Push. Write a lab report about removing and fixing the following 8 items. Do them. Implement. We are fixing old training decisions. Adapt. Just trial runs. After you code it, review it again, write a lab report about the changes with diagrams, and also do another round of following your suggestions as you find more out."

**The method was the same for each.** Read what the rule had cost and what it had bought, from the queue. Change it by a value where a value existed, and make one where it did not, with 0 or the old number meaning "as it was". Prove the code in `board-check`. Say how to undo it. Then read the whole day's changes again, for what they do together.

!html(reopened/dia-map.html)

*Diagram 1. The line's gates on the evening of 13 November: what was kept, what was changed, what was set aside, and what the day added. Each box's first line says which.*

| Trial run | Where | Was | Is | To undo |
|---|---|---|---|---|
| The transform rotation | `plan.json` `rotation` | the transform lane | `false` | put `{"transform": [["patch", {}]]}` back |
| The clone rounds | value `clone_every_h` | 12 | 0 | `fleet-tune.py Q clone_every_h default` |
| Boburner's island | `config.json`, `off` on boburner-cuda | on | off | `fleet-queue.py Q assign boburner-cuda crucible on` |
| A dial moved again | value `settle_gens` | 2 | 0 | `settle_gens default` |
| The anchor reads | value `anchor` | 3 | 0 | `anchor default` |
| The hold | `hold.json` | `w_pos_fortify` 0.4 | empty | `fleet-tune.py Q hold w_pos_fortify 0.4` |
| The trade rule's limit | value `trade_gain` | 0 (fixed) | 1.0 | `trade_gain default` |
| The first read | `plan.json` `weights.seeds` | 55 | 150 | set 55 |
| Held-out reads | value `held_reads` | 1 | 6 | `held_reads default` |
| The held-out bar | values `ease_max`, `ease_now` | 1.5 | 0.5 | set 1.5 |
| One dial at a time | value `far_share` | 0.25 | 0.5 | `far_share default` |
| The line settling | value `settle_seeds` | off | 9,600 | 0 |
| The yardstick | value `rating_seeds` | off | 2,000 | 0 |
| A second lane | `config.json`, saskatchewan-2 | none | one | remove the entry |

*Table I. Every trial run of the day and the way back. A value is moved on the Values page or with `tools/fleet-tune.py`; all are live at the next pass and none restarts a job.*

## II. Where the hours went

!html(reopened/fig-hours.html)

*Fig. 1. The CPU machines' job-hours from 10 November to the morning of the 13th, by the kind of job. The lighter bar is the rotation, set aside here.*

| Kind | Jobs | Hours | Share |
|---|---|---|---|
| Reads on | 4,741 | 193.0 | 41.2% |
| First reads | 3,510 | 167.1 | 35.7% |
| The transform rotation | 1,496 | 45.2 | **9.7%** |
| Held-out reads | 829 | 39.0 | 8.3% |
| The proof | 128 | 18.8 | 4.0% |
| Everything else | 152 | 5.1 | 1.1% |

*Table II. The same, in numbers. The iMac and the cards are left out.*

## III. The transform rotation

!html(reopened/dia-rotation.html)

*Diagram 2. The rotation's one lane. `rotate()` asks a patch run; its censuses put a transform of two steps in a slot; `auto_promote()` passes over anything with a patch in it, because the game has no file for a slot.*

**A tenth of the fleet made what could not be used.** The planner's own comment says it: "NOT A TRANSFORM, YET. The slot's file lives with the queue and the game has none: promoted, `patch = k` would stop every game that starts. It waits for a person." Ninety-three patch runs finished in the week. `plan.json`'s `rotation` is now `false`. The lane comes back when the game can load a slot.

## IV. The clone rounds

!html(reopened/dia-clone.html)

*Diagram 3. A clone round: record the rules, train a net to copy them on calber's card, judge it beside the rules.*

!html(reopened/fig-clone.html)

*Fig. 2. Every clone round: the clone less the Scholar it would replace, ± 2 se. A clone ships when it is past two errors.*

**Fifteen rounds, none shipped.** Twelve clones read under the Scholar and three over, none of them past its error (the best, round 8, +2.11 ± 1.99). A round costs ten CPU jobs of recording, a few minutes of one card and a judging census, twice a day. `clone_every_h` is 0. A clone that mines and fights wants a frozen trunk in the trainer (treadcore LR 135): until that is built a round reads the same answer.

## V. Boburner's island

!html(reopened/dia-island.html)

*Diagram 4. The three islands and the bridge that reads their milestones in the game.*

!html(reopened/fig-isles.html)

*Fig. 3. Every milestone the bridge read in the game, less the shipped Gladiator, by the island that made it. The larger mark was shipped.*

| Island | Milestones read | Mean in the game | Range | Shipped |
|---|---|---|---|---|
| boburner | 14 | **−6.78** | −8.75 to −4.72 | 0 |
| calber | 8 | +0.17 | −1.35 to +2.28 | 1 |

*Table III. The bridge's 22 reads. Whitewolf's island has made no milestone the bridge read.*

**Which island made a net says more than the arena's exam does** [2]. Boburner's island has settled somewhere the game does not reward, and every milestone from it costs the bridge two censuses to say so again. Its card rests: `assign boburner-cuda crucible off`. Calber's and whitewolf's run on.

## VI. A dial moved again

!html(reopened/dia-settle-gens.html)

*Diagram 5. `noise()`'s second rule, and what does its work now.*

The rule (`SETTLE_GENS` 2, 1 November): a candidate that moves a dial moved in the last two generations must reach z 3. It was made when a held-out read passed at z 1.5 and dials wandered on luck. It fired twice in the week. With the held-out bar at z 2.5, and one block checked before the next may join, a dial cannot wander that way. `settle_gens` is 0.

## VII. The anchor reads

!html(reopened/dia-anchor.html)

*Diagram 6. The anchor's question, and the two things that answer it now.*

After each promotion the anchor read the defaults of three promotions back against today's: three censuses, 855 seeds, thirty-one times since 1 November. It was the measurement that showed the line had stopped gaining [1], and it earned its keep. But it reads different seeds each time against a moving base, and nothing acted on what it found. The yardstick asks the same question against three fixed days on fixed seeds, and a line that fails its check now comes off [2]. `anchor` is 0, which the code had to learn to mean "none".

## VIII. The hold

!html(reopened/dia-hold.html)

*Diagram 7. A hold: a value a trial may read at and never promote to.*

`w_pos_fortify` 0.4 was held on 1 November, under game 4, because its gain was all in the reward for going forward [3]. The game is at 9, the score has counted building since `SCORE_VERSION` 1, and the default has since moved to 0.0249 by other roads. The hold guarded a question that is no longer asked. `hold.json` is empty.

## IX. The trade rule

!html(reopened/dia-trade.html)

*Diagram 8. The trade rule with its limit weighed by the gain. Both outcomes are of a trial giving up 0.47 kills less deaths a seat.*

**The limit was the same whatever was bought.** A candidate could give up 2.5 times a floor, so 0.25 kills less deaths a seat, for a gain of +0.3 and for a gain of +3.3 alike. `w_smooth = 0.525` gained +2.00 to +4.32 held out and gave up 0.30 to 1.33, and was refused thirteen times [1].

**What was built** (`trade_allow`). With `trade_gain` set, the limit is 2.5 floors up to that gain a seat and grows in proportion past it. At 1.0:

| Held-out gain | Allowed, in floors | Gives up 0.47 (4.7 floors) | Gives up 1.33 (13.3 floors) |
|---|---|---|---|
| +0.3 | 2.5 | refused | refused |
| +1.0 | 2.5 | refused | refused |
| +2.89 | 7.2 | goes on | refused |
| +3.3 | 8.25 | goes on | refused |

*Table IV. The rule at `trade_gain` 1.0. The line's own check, against main, asks the same with its proved lead.*

**This is the change that most wants a person's eye.** It is a judgement about the game: that a bot scoring three points more a seat may fight half a point worse. The rule that refused it was Paul's, made on 2 November because the score was blind to fights: a guard against a measure gained by giving up what it stands for [4]. It is relaxed here as a trial, on his word, and section XI says what follows from it.

## X. The stages, and the held-out read

!html(reopened/dia-stage.html)

*Diagram 10. The stages scale with the first read; the first read now scales with the swing.*

**The first read is 150 seeds.** The stages were simulated on 29 October for a seed's swing of 4.9 a seat [1]. A read's z for a given true gain goes as the root of its seeds over the swing, so the same design at a swing of 8.1 wants (8.1 / 4.9)² = 2.7 times the seeds: 150 for 55, and stages of 150, 225, 338, 510, 750 and 1,140. The fleet reads about 390 new trials a day where it read 1,070.

!html(reopened/dia-held.html)

*Diagram 9. A held-out read that is promising and undecided is read on.*

**The held-out read is read on** (`held_more_jobs`). This is the review's finding, in the next section.

## XI. The review

The day's changes were read again together, function by function: `settling`, `orphan`, the proof's hook, `trade`, `rating`, `far_trials`, `prep_id`, `builder`.

**One fault, in the day's own work.** Raising the held-out bar to z 2.5 [2] met an older rule: "a generation takes one read" (1 November), one held-out read of 400 seeds, good to about 0.40 a seat. At z 2.5 that read must say +1.0 to pass. A trial truly worth +0.3 expects z 0.74 and passes about four times in a hundred. The line would have been able to take only gains three times the size of anything it has kept since 6 November. Now a held-out read whose pooled z is from 1.0 up to the bar is read again on fresh seeds and pooled, up to `held_reads` (6): 2,400 seeds, good to 0.17, where +0.45 can pass.

**One consequence, said plainly.** With `trade_gain` at 1.0 the refusals of `w_smooth = 0.525` no longer stand: a refusal is kept with the rule as it stood, and the rule has moved. When it is read again it will be within the limit. If the families hold it joins the line; the line's proof would then read about +3 over main, pass, and push it. **`w_smooth = 0.525` can reach main by itself**, and with it about half a point of kills less deaths a seat. That is what the trial allows. The split of `w_smooth` into its parts [2] would say which part pays and which costs, and it is not on treadcore's main yet (section XIV). A person who would rather wait for the split sets `trade_gain` to 0.

**Two smaller things.** Boburner's second lane gave nothing (1,347 seeds an hour before, 1,292 with it), where saskatchewan's gave 1,813 to 2,488 over an hour; boburner's was taken out. And a hold on the line ends eight hours after its last promotion whatever its proof has read (`SETTLE_MAX_H`): on 13 November that was 10:00, with the head at 8,000 of 9,600 seeds at 08:58.

**Not found.** No fault was found in `orphan`, the rounds of the one-dial read, the second lane's builds or the yardstick's seeds. They are proved by `board-check` and `fleet-queue-check`, and three of the four had not yet run to their end on the live fleet when this was written.

## XII. How each trial is judged

| Trial | Read | It stays if | It goes back if |
|---|---|---|---|
| The line settling, a block coming off | the Yardstick tab's orphans; the proof | lines are proved or come off within a day | the line stands held for days with nothing decided |
| Held-out bar 2.5, six reads | generations a week; the yardstick | each generation moves the yardstick's newest row | a week with no generation and candidates stuck under the bar |
| First read 150 | finds a day; reads on as a share of hours | reads on fall from 41% and finds do not | finds fall in step with trials |
| One dial at a time | which round's trials pass held out | single dials pass more often than the fit's | a round passes nothing |
| The trade limit by the gain | every "goes on by the trade rule" flag; kills less deaths on the yardstick's games | what it lets through plays as well to a person | fights fall on main and a playtest says so |
| Rotation, clones, anchors, the rule of two generations | nothing | nobody misses them | a question arises that only they answered |
| Boburner's island off | calber's milestones | calber's keep shipping | calber's stop and boburner's is wanted for variety |

*Table V. What is watched, and the sign either way.*

## XIII. The next round

Found while doing this one, in the order they would pay:

1. **Reads on are 41% of the hours.** With a first read of 150 the stages after it are the larger share of a trial. A stage's read-on bar could rise, or two stages go. To be read after three days at 150.
2. **The widened search is crowded.** Half of each generation's new trials are now one dial at a time, a third at most the A/B versions, and when stalled half are wide trials: the fit's own trials get what is left. With the bar at 2.5 "stalled" will be the usual state. Wide trials should yield to the one-dial rounds, which are the same idea done one dial at a time.
3. **The ratchet no longer ratchets.** With its ceiling and its value both at 0.5 the ease cannot move. The code of `ease()` could go, and the bar become one value.
4. **`GENERATION_EVERY_MIN`** (30) is inside what the settling line already holds.
5. **Whitewolf's island** raised "failed three segments in a row" 27 times in the week and holds 20.5 GB, over its limit. It has made no milestone the bridge read. It should be looked at before it is left running.
6. **The temperament matrix** has asked 72 trials in three rounds. What they found has not been read here.
7. **The maps' weights** [1]: still Paul's.

Items 4 and 6 were done and item 5 looked at the same morning (section XIV); 2 needed nothing, a wide trial being one a generation already.

## XIV. What happened next, and what is not done

- **The line came off at 09:26.** Its proof read −0.02 ± 0.10 over main in 10,400 seeds, and the ten generations r0220 to r0326 were orphaned by the rule [2]. The fleet builds main.
- **treadcore's main has the split and the floor** since 09:27 (2945c7e): `w_smooth`'s four parts as choices (LR 157) and `w_pos_defend` held at 0.75 or more. The A/B trials read each part from the next generation.
- **The next round, done the same morning**: the half hour between generations is 0 (`generation_every_min`), and the temperament rounds are off (`temper_every` 0): three rounds, 24 settings and 9,869 seeds, none past z 2 upward and one, `temper_engage_3` at +0.5, at −1.37 ± 0.43. Whitewolf's island was looked at and is well: its 27 warnings were all of one bad build on 6 November, and its disk is at 5.3 GB. It is left running.
- **Not done**: the yardstick's first rows were not back; the Yardstick tab was drawn and looked at with constructed rows; reads on, 41% of the hours, wait for three days at a first read of 150.

## XV. How to make it again

`python3 tools/report/reopened.py ~/code/treadcore/build/queue/grove docs/reopened` writes `docs/reopened/data.json`, the three figures and the ten diagrams; `--redraw docs/reopened` draws them again. The checks: `python3 -I tools/plans/board-check.py`, `sh tools/fleet-queue-check.sh`, `sh tools/plan-check.sh`, `cargo test`.

## References

[1] orrery, *Always Forward: Why the Line Has Not Gained Since 6 November, the Gain a Rule Held Back, and a Harness That Mints Only Real Blocks*, lab report, 13 November 2026.

[2] orrery, *Every Block Checked: A Line That Settles, a Block That Comes Off, One Dial at a Time, a Cliff Explained, `w_smooth` Split, and a Fixed Yardstick*, lab report, 13 November 2026.

[3] orrery, *A Stale Dial: What We Measured, What Changed, and What We Refused*, lab report, 1 November 2026.

[4] D. Manheim and S. Garrabrant, "Categorizing variants of Goodhart's law," arXiv:1803.04585, 2018.
