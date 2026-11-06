# Outgrowing Yourself: What the GPU Hands the Game, What a Generation Keeps, and Whether the Card-Hours Pay

*Paul Richeson · Lab Report — IEEE Format · 6 November 2026*

Paul Richeson, treadcore.org; Claude Code (Claude Opus 5.5) as the pair. Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery and treadcore.

Companions: orrery `tools/report/outgrowing.py` (every number and figure here, from the queue and git), `tools/plans/treadcore.py` (`crucible_ladder_home`, `bridge_jobs`, `clone_jobs`, `line_proof`), `tools/bridge.py`; crucible `src/crucible.cu`; treadcore `source/treadcore-brain/src/styles.rs`. The data: `docs/outgrowing/data.json`, read at 08:30 on 6 November. Reports of 1 and 5 November: *The Whole Line* [1], *The Duty Cycle* [2], *Three Generations, Filmed* [3].

## Abstract

Paul asked how a value computed on the GPU's CUDA cards gets back into the main run and on what conditions, how the GPU adds to the data, whether its compute hours can be justified, and what happens to a working system as it tries to outgrow its past versions: how long a generation takes, how many there are, and how big each one is. **Everything here is read from the queue's records and from git.** There are two ways for a GPU result to reach treadcore's `main`, and **neither has delivered anything yet.** On the first road, the bridge, a world milestone is read in the game as the Gladiator (bot style 17) and shipped as a net file. It has made no reads, because no milestone has been made since its code landed. On the second, the clone, the rules are re-learned on calber's card for the Scholar (style 6). It has run four rounds, and every clone read under the Scholar it would have replaced (−2.78, −1.73, −0.68 and −2.75 a seat). The only GPU net on main, M0015 as the Gladiator, was committed by hand on 4 November. **No GPU number reaches the line's dials**, which are the brain the game plays by default: those move only on CPU censuses. The cards have run 442 card-hours since 28 October (25.5% of the fleet's job-hours). They used 52.9 kWh (26.8% of its energy), about $9 at the planner's 17¢ a kWh, or $1.41 a day now. The world ladder made 13 milestones in its first 6.5 hours, each by a smaller margin than the last, and none in the 50 hours and **149 card-hours** since. The last milestone, M0015, won its exam on 0.4% of duels, lost none and drew 99.6%. The islands have settled into a stable state where not losing pays, and the exam only credits winning. The line, meanwhile, committed **32 generations in nine days** (5.0 a day since 1 November). A generation takes a median **1.0 h** from its first read to its commit, and then a median **4.6 h** to reach main. **A generation keeps about 0.28 of the gain its held-out read claims** (± 0.03, over 19 distinct lines the proof read). Main's six moves since 1 November took lines whose generations had claimed +14.96 a seat in all; the proofs that passed them read +9.43. The line today claims +2.75 over four generations and proves +0.45 ± 0.23, and has waited 20 hours. Six recommendations follow, none built. Two of them carry the most weight: make the arena's exam credit something a net can still gain, and key the proof's pool on the line's dials rather than its commit.

*Index Terms*: neuroevolution, coevolution, mediocre stable states, behaviour cloning, statistical acceptance testing, winner's curse, selection bias, continuous delivery, compute accounting.

## I. The question

Paul, on the morning of 6 November, after the trailer: "Explain how the values from CUDA make it back into the main run. What are the conditions? Write a lab report. Give diagrams. Show me HTML. How does the GPU add to the data? We are getting many compute hours. Can we justify this? Write a lab report, IEEE, about post-working reality: transitions to improvements, outgrowing past versions of yourself. I'm asking about the turnaround time, the generations that occur, and the scalar improvements."

Five questions, then: the road and its conditions (section III); how many generations there are and when (IV); the turnaround (V); the size of an improvement, claimed and kept (VI); and what the GPU contributes and costs, with whether that is justified (VII to IX). Section X is about what working means once the pipeline works.

## II. Two machines that grow

The fleet grows two different things, and the answer to every question depends on keeping them apart.

**The line** grows the game's own brain. That brain is treadcore's scripted rules, with about three hundred dials: weights, distances, switches. A *generation* of the line is a commit to treadcore that moves a few dials. It starts as a **trial** drawn by `suggest.py` from a fit to every census so far. The trial is read in **censuses**: whole games of treadcore, run on the CPUs, the trial's dials against today's defaults on the same seeds, with the score difference a seat as the measure. The reads run from 55 seeds, on to about 190, then 400 seeds that no search has seen. A trial past the bars is held to its families, its gauntlet and the brain's tests, then committed to **the line** (`orrery/accepted`), which every machine builds. Main, the branch a player installs, takes the line only through an hourly **proof** [1].

**Crucible** grows small neural networks on the three CUDA cards, on calber, whitewolf and boburner. It evolves populations of 55-48-48-4 nets that play 1-against-1 duels in an arena built with the game's sixteen physical constants (speed, turn, armour, gun range, reload, pillboxes). A segment of 100 generations takes 9 to 13 minutes. Each segment's champion sits an **exam** against the ladder. When it beats the newest **milestone** by two standard errors, it becomes the next milestone [4]. A crucible generation is therefore not a line generation: the islands count about 700, 510 and 460 generations an hour, and calber stands at generation 275,600.

The two share sixteen constants and nothing else. The arena has no forest, roads, water, economy, drones or maps, and it scores by its own fitness: damage dealt less taken, ±2 for a win or a loss, −1 for a draw. It does not use the game's score.

## III. How a value from CUDA reaches main

!html(outgrowing/fig-roads.html)

*Fig. 1. The roads to main, each gate as the code has it. Blue is the GPU's road and orange the line; green is main. The dashed curve marks the connection people assume exists, from the GPU to the line's dials. It does not exist. Styles 17 and 6 play only when a person picks them, in a menu or with `--bots`.*

**Two roads lead from the GPU to main, and both carry a file, not a number.** The first is **the bridge**, which brings the Gladiator. The planner watches the world ladder. When the newest milestone is not the one already shipped and has not been read, it asks two censuses on the fastest machine, 48 seeds each over every map: the defaults with the candidate seated as style 17 (`GLADIATOR=file`), and the same with the shipped one. If the candidate is better by more than two errors, the auto mode ships it. `tools/bridge.py` checks the file (20,944 bytes, the world layout), makes a worktree of `origin/main`, runs the styles tests on the Mac, commits `nets/gladiator.bin` and pushes **straight to main**. There is no held-out read and no proof. The second is **the clone**, which brings the Scholar. It runs every 12 hours when the line has a new head. It records the rules playing 120 games (ten CPU jobs), trains a net from scratch on calber's card by behaviour cloning [5] (12 epochs; 77 to 287 seconds of card time), and judges it on 48 seeds with one seat beside the rules, plus a 100-run gauntlet. It ships into `nets/scholar.bin` only if it is better by two errors and no gauntlet item falls under its floor or the Scholar's.

| Road | Gate | Condition | Where |
|---|---|---|---|
| Gladiator | Segment | 100 generations; exam of 2,048 duels against each of up to 8 rungs | `crucible_exam` |
| | Milestone | margin over the newest > 2 se, and the ladder's mean ≥ 0 | `treadcore.py` 4454 |
| | Bridge read | the newest milestone only; 2 censuses × 48 seeds, all maps; diff > 2 se | 4592, 4616–4628 |
| | Ship | auto mode and the push dry-run ok; styles tests; push to main | 2420, 3515; `bridge.py` 62–72 |
| Scholar | Round due | 12 h since the last, and a new line head | 4757 |
| | Record, train | 120 games on the CPUs; behaviour cloning on calber's card | 4762–4777 |
| | Judge | 48 seeds, one seat, diff > 2 se; gauntlet: nothing worse by 2 se, nothing under a floor | 4796–4836 |
| | Ship | auto mode and the push ok; styles tests; push to main | 4839; `bridge.py` 107–128 |
| The line | Proof | main's values vs the line, 800 seeds an hour, pooled; z ≥ 3 and the trade rule | 1512, 5170 |

*Table I. Every gate between a computation and main. Line numbers are in `tools/plans/treadcore.py` at orrery 3556714. The bridge's two errors are combined unpaired (`hypot`), although its comment calls the read paired: the bar it sets is stricter than the one described.*

**Neither road has shipped anything.** The bridge has made no reads (`plan/bridge.json`: `reads: []`). Its code landed at 10:06 on 4 November, four hours after the last milestone. M0015 had already been committed by hand as the Gladiator at 10:31 (treadcore 21fdfbd), read at −2.53 ± 1.21 a seat against the defaults and +4.99 ± 2.08 over the Duelist it replaced. With the newest milestone already shipped, the bridge has had nothing to read. The clone has run four rounds, and all four lost:

| Round | Asked | Rules at | Clone | Scholar (bc2) | Clone less Scholar | Gauntlet worse |
|---|---|---|---|---|---|---|
| 1 | 4 Nov 11:06 | 21fdfbd | −42.71 | −39.93 | −2.78 ± 3.93 | none |
| 2 | 4 Nov 23:06 | f04f157 | −9.32 | −7.59 | −1.73 ± 2.18 | G2, G3, G8 |
| 3 | 5 Nov 11:08 | d9e9aef | −8.25 | −7.57 | −0.68 ± 2.01 | G22, G3, G8 |
| 4 | 5 Nov 23:09 | a96baf9 | −10.53 | −7.78 | −2.75 ± 2.26 | G3 |

*Table II. The clone rounds (`plan/clone.json`). Round 1 seated the clone as the whole team. Rounds 2 to 4 seated it as one seat beside the rules, which is why their scores are so much smaller. Round 5 is due about 11:10 today, since the line's head is now 96c4954.*

**No GPU number reaches the line's dials.** This is the answer to "how do the values make it back into the main run": they do not, by design and in fact. The censuses that move the dials send only a trial's dials. `bot_style`, `bot_mix`, `model` and `patch` are all 0 on the line. A style plays only when `bot_style` is above 0. The planner never asks an A/B of a style and never promotes one. `suggest.py` drops every row that names a choice or a net. The gauntlets that guard a promotion play the scripted brain (`GAUNTLET_BRAINS=scripted`). The influence runs the other way: a Gladiator in a game plays on top of the line's dials.

**How the GPU adds to the data, then.** It adds the ladder's data to orrery's own records: 922 world segments in `growth.tsv`, 811 exams against M0015 in `lineage.tsv`, and the Growth page and the films built from them. It adds one shipped net, by hand. It adds four clone rounds that measured how far an imitation falls short. It adds nothing to the censuses, the ledger, the fit, or anything else the line reads.

## IV. The generations that occur

!html(outgrowing/fig-lanes.html)

*Fig. 2. Nine days in lanes. The GPU's milestones (two carried over from the hybrid home, then thirteen in the night of 3–4 November); the GPU's nets on main (filled: M0015, by hand) and the clone rounds (hollow); the game's own version changes, after which a seat's score means something new; every line commit (hollow: by a person's hand); and every move of main, from the coordinator's reflog of `origin/main`.*

**The line made 32 generations, 27 of them since 1 November: five a day.** 55 promotion tries were asked. 32 landed (28 now on main, 4 on the line) and 23 failed, 19 of those at the brain's tests and none at the families. The gap between two generations has a median of 2.5 h and a mean of 6.7 h. The mean is pulled up by the shutdown of 31 October and by the 53 hours of 2 to 4 November, when games 5 to 8 and score 1 changed the game under the fleet and the auto mode stood paused after two failed promotions (r0156, r0166). **Main moved 12 times.** The first six took one generation each, straight to main, before the line existed. The last six took 10, 3, 3, 1, 1 and 2 generations through the proof.

**The GPU made 15 milestones, 13 of them in six and a half hours.** The world home began at 23:00 on 3 November. Its milestones came at one every 25 minutes until 05:42 on 4 November, and then stopped. Since then the islands have run about 85,000 generations: calber from 241,300 to 275,600, whitewolf and boburner about 25,000 each. None has been a milestone.

## V. Turnaround

!html(outgrowing/fig-turnaround.html)

*Fig. 3. Every committed generation: from its trial's first job to its commit (orange, hours before the commit), and from its commit to main (green, hours after). Before 1 November a promotion went straight to main. Dashed bars are the four generations still on the line, waiting at 08:30.*

**A question becomes a commit in about an hour, and a commit becomes main in about four and a half.** From a trial's first read to its commit takes a median 1.0 h over 30 generations (mean 3.2 h; shortest 10 minutes, longest 35 hours, for r0068 across the shutdown). Since the proof began on 1 November, a commit has reached main in a median 4.6 h (mean 5.5 h, longest 16.1 h), so a question reaches main in a median 5.9 h. The Duty Cycle measured the first stretch from the other side: a trial's chain is mostly waiting between links, not work [2].

**The second stretch is where the time goes now.** r0196 has waited 20.0 h, r0199 16.5 h, r0201 13.1 h and r0209 3.2 h. They wait because the proof has not reached z 3 (section VI). They also wait for a reason that is the pipeline's own: **a push to main restarts the proof.** The proof pools its hourly reads for one line head against one main. Every push to main replays the line and gives it a new head, and that includes a report, a fix to a test, or a lab report like this one. Of the 26 heads the proof has read, **6 had the same generations as the head before**, and each threw away its predecessor's pool. The line that took r0179 and r0186 to main was read under three heads in two and a half hours: +0.80, +0.49, then +1.28, and passed on the third. Pooled by inverse variance [10], the three read +0.88 ± 0.19. The restart costs more than time. Each new head is a fresh look, and a bar of z 3 met once among many short looks is easier to meet by luck than once at the end of one long pool [11].

## VI. Scalar improvements: what a generation claims, and what it keeps

!html(outgrowing/fig-claims.html)

*Fig. 4. For each line head the proof read: the sum of the held-out reads its generations claimed (x) against what the proof read of the line over main (y, ± 1 se). Filled points passed (z ≥ 3). A point on the dashed line kept all it claimed. Hover a point for its generations and seeds.*

**A generation keeps about a quarter of what it claims.** A generation's held-out read is honest about its own seeds: 400 that no search has seen. But it is read only because it passed the reads before it, and it is committed only because it passed the held-out bar. A read selected for being high is, on average, too high. This is the winner's curse [6], and selection bias in its most familiar form [7]. The proof is the first read of the generations that nothing has selected, and it reads the line against main directly. Pooling the proof's reads by the line's contents gives 19 distinct lines. Fitting proven against claimed, weighted by the errors, gives a slope of **0.28 ± 0.03**; the plain ratio of their sums is 0.32. The record has two clean single cases. r0179 (`bio 0 -> 3`) claimed +0.51 and was read alone over 8,000 seeds at **+0.03 ± 0.07**. r0196 (four dials) claimed +0.96 and was read alone over 2,400 seeds at **+0.00 ± 0.18**.

| Line (generations on it) | Claimed | Proven | Seeds |
|---|---|---|---|
| r0069 … r0103 (10 generations; main 1 Nov 20:07) | +4.34 | +1.43 ± 0.41 | 800 |
| r0110, r0113, r0118 (main 1 Nov 23:55) | +4.07 | +3.16 ± 0.46 | 800 |
| r0124, r0126, r0132 (main 2 Nov 09:43) | +3.38 | +1.82 ± 0.42 | 800 |
| r0133 (main 2 Nov 16:31) | +1.17 | +0.81 ± 0.23 | 3,200 |
| r0178 (main 4 Nov 18:24) | +0.80 | +0.71 ± 0.20 | 800 |
| r0179 alone | +0.51 | +0.03 ± 0.07 | 8,000 |
| r0179, r0186 (main 5 Nov 11:37) | +1.20 | +0.88 ± 0.19 | 2,400 |
| r0196 alone | +0.96 | +0.00 ± 0.18 | 2,400 |
| r0196, r0199 | +1.46 | +0.33 ± 0.18 | 2,400 |
| r0196, r0199, r0201 | +2.02 | +0.27 ± 0.11 | 6,400 |
| r0196, r0199, r0201, r0209 (the line now) | +2.75 | +0.45 ± 0.23 | 1,600 |

*Table III. A selection of the 19 distinct lines, every read of one line pooled across its heads (all in `docs/outgrowing/distinct.json`). "Claimed" is the sum of the generations' held-out reads. "Proven" is the proof's read of the line over main, a seat. Where a line moved main, the proven value shown is the pool, not only the passing read.*

**What main has gained, in one unit.** A seat's score changed meaning twice in these nine days: the economy (games 5 to 8, 2 November) and the score that counts building (score 1, 13:00 on 4 November). Sums across those changes add different things. Since score 1, main has moved twice, taking three generations. The proofs read those moves at +0.71 ± 0.20 and +0.88 ± 0.19 pooled, so **main today is about +1.6 ± 0.3 a seat over the brain of 4 November at 13:00**; those three generations had claimed +2.00. The line's four more claim +2.75 and prove +0.45 ± 0.23. Over the whole stretch, seven generations claimed +4.75, and about +2.0 has been proved. For scale, one seat's score swings by about 9.5 from game to game [1], so 1.6 is a sixth of one game's spread. It is a real improvement, and it is less than half of what was claimed.

Three things shrink a claim, and the record cannot separate them. Selection is one. The second is interaction: dials tuned against today's defaults are read together against a main that has since moved. The third is that the game itself changed under some of the reads. The cure is the same for all three, and the pipeline already has it: the proof. What the pipeline lacks is a way to say so out loud. The trailer, the montage and the Flow all show the claim, and only the proof card shows what was kept.

## VII. Outgrowing past versions of yourself: the islands

!html(outgrowing/fig-ladder.html)

*Fig. 5. (a) The margin each milestone set over the one before it, in standard errors, against the bar of 2. (b) Every exam against M0015 since it was made: the best and the median of each hour. (c) The yardstick: the share of duels won against crucible's fixed scripted opponent, a half-day's median over all islands.*

**The ladder outgrew itself thirteen times in a night, each time by less, and then stopped.** The margins fell from 51.6 and 35.8 standard errors to 2.3, 2.3, 2.5 and 2.8, just over the bar. The exams explain why. M0014 won its exam winning 1.1% of duels, losing 0.4% and drawing 98.4%. **M0015 won by winning 0.4%, losing none and drawing 99.6%.** Since then, 811 exams have met M0015. Their median champion draws 93% of duels against it, wins 0.2% and loses 6.7%, and the best margin any reached is +1.43. In panel (b) the median has climbed from −40 to about −8 standard errors, and the best has stayed between −2 and +1.

**The past self has become a net that never loses.** Over the same days the islands' champions have taken less and less pillbox damage, from 0.29 to 0.06 of a shell's worth a duel. Their yardstick has not moved: 0.719 of duels won against the fixed opponent on 4 November, 0.729 now. The populations have found what coevolution's literature calls a **mediocre stable state** [8]: play that is safe against itself, with less to gain from winning than to lose by trying. An exam that counts wins less losses over standard errors cannot credit a net for drawing. A successor must win against a fortress, and the arena now pays for staying out of fights. Measured against the fixed opponent instead of each other [9], the islands are still where they were at 05:42 on 4 November. In the ladder's own terms, the islands have not outgrown M0015.

## VIII. Compute hours, and what they bought

!html(outgrowing/fig-hours.html)

*Fig. 6. Job-hours a day: the three cards' (blue; at most 72 a day) and the CPU machines' (orange), with the day's energy beneath. The fleet was shut down on 31 October.*

| Since 28 October | GPU (3 cards) | CPU (about 10 machines) |
|---|---|---|
| Job-hours | 442.1 card-hours (25.5%) | 1,290.3 machine-hours |
| Energy, cost at 17¢ a kWh | 52.9 kWh (26.8%), $9.00 | 144.5 kWh, $24.56 |
| Now, a day | about 70 card-hours, 8.3 kWh, $1.41 | about 185 machine-hours, 23 kWh, $3.95 |
| Since the world arena (3 Nov 23:00) | 169.1 card-hours | — |
| Since the last milestone (4 Nov 05:42) | 149.1 card-hours, about $4.20 | — |
| What reached main | 1 net file, by hand | 32 generations, 12 moves of main |

*Table IV. Job-hours are each job's seconds on its machine, from `events.jsonl`; a CPU job uses the whole machine and a GPU job uses its card. Energy is the planner's tally (`plan/timeline-bins.json`): measured where a machine has a counter, and modelled where it has none, as on the Xeons. The price is power.json's guess until Paul sets his own.*

**The cards are cheap, and lately they have bought nothing the game uses.** The three cards draw about 8.3 kWh a day, $1.41 at the guessed price. That is a quarter of the fleet's energy, and they run near 99% of the time [2]. Since 28 October those hours bought the following:

- **15 milestones.** Thirteen of them came in the first six and a half hours of the world arena.
- **One shipped net, M0015 as the Gladiator, committed by hand.** It is +4.99 ± 2.08 a seat better than the Duelist it replaced, and −2.53 ± 1.21 against the rules: a better opponent style, but not the brain.
- **Four clone rounds**, none better than the Scholar.
- **The films and the Growth page.**

Since M0015, the last thing that could ship, the cards have run 149 card-hours, about $4.20 of electricity, with no milestone, no ship and no read of any kind for the line.

## IX. Can it be justified?

**In money, yes. In what it hands the game, not now. The honest justification is a change, not more hours.** The cards would otherwise idle: a crucible job takes a card, not the CPU lanes on the same machines. So their cost is the electricity, about $1.41 a day, plus the attention their pages and films take. Against that, the arena has stood still for two days, and its exam cannot see the only direction left open to it. Six transitions, each small, each with a number to watch. None is built; each waits on Paul.

1. **Make the exam able to see progress again.** Read a champion against a milestone over decisive duels only, and require it to be no worse against the fixed yardstick. Or keep the exam and change the arena so that not losing is not enough: draws cost more than they do now, or the arena shrinks as the duel goes on. *Watch:* a milestone within a day, and the yardstick above 0.73.
2. **Point a card at what the line uses.** The clone's training takes one to five minutes of card time and runs every 12 hours. More rounds with more recorded games, or imitation of the line's head for the Scholar, would turn card-hours into reads the game can use. *Watch:* a clone round within 2 errors of the Scholar.
3. **Or rest two of the three islands while the ladder stands.** That saves about 5.5 kWh, roughly $0.95, a day, and keeps one island searching. This is the option if neither 1 nor 2 is wanted.
4. **Key the proof's pool on the line's dials, not its commit.** Two heads with the same promotions over the same main are the same question. Pooling them would have kept 6 of the last 26 pools instead of starting again. *Watch:* commit-to-main time under the present median of 4.6 h.
5. **Say what was kept.** Show the proof's read beside the held-out claim on the trailer, the montage, the Flow and the run detail, and shrink a claim before showing it. An empirical-Bayes shrinkage toward the line's own record of 0.28 is the simplest honest version [7]. *Watch:* nothing in orrery shows a claim without its proof.
6. **Read the brain against a fixed past self.** Every number in section VI is a step, a line over the main before it. Once a week, read today's line against a frozen brain, such as main as it stood after score 1 (43f9f67). That tells "outgrowing past versions" in one number, as the islands' yardstick does for them [9]. *Watch:* that number, week on week.

A smaller fault was found on the way. The bridge's comment calls its read paired, but its two errors are combined as if independent. That makes its bar stricter than the one written, so a real improvement is less likely to ship. Pairing the two censuses' seats would put the bar where the comment says it is.

## X. Post-working reality

The pipeline works. Questions are asked by themselves, read on machines nobody watches, committed, built everywhere, filmed and proved. What changes when a system works is the question it can be asked. Before, the question was whether it runs. Now it is what it keeps, and the record answers in three parts.

**What is kept is smaller than what is claimed.** Each step's honest read, chosen for passing, overstates the step about three and a half times. The steps still add up: three generations since score 1 made main +1.6 a seat better, proved, and four more wait. A working system's improvements are real and modest, and an account that adds up claims will overstate them every time.

**Outgrowing yourself is fast, then hard, and can stop for reasons that are not about skill.** The islands beat their past selves thirteen times in a night, and then made a past self that cannot lose. Whether a successor is better now depends on what the exam can see, not on how many hours it runs. The line has the same shape more slowly. Main's first moves through the proof were +1.4 to +3.2 a seat. Its recent ones are +0.7 to +0.9, and the line now waiting reads +0.45. Diminishing returns are what working looks like from inside, as the Red Queen's measurements found for coevolving populations long before this one [9].

**Transitions come from measurement, not more compute.** Each of the six recommendations changes what is measured or where it is pooled; none adds hours. The cards are cheap enough to keep. What would justify them is a target they can still move, an exam that can see them move it, and a road from the result to the game that something actually travels.

## XI. What is not shown, and what is open

- **The heads overlap.** Lines that share generations are not independent reads, so the fit's ± 0.03 is too narrow. The ratio of sums (0.32) and the two single-generation cases agree with it.
- **The units changed.** A seat's score before 2 November, before 4 November at 13:00, and after, are three different measures. No sum here crosses those boundaries except the claimed-against-kept fit, which compares each line with its own proof at the same time.
- **When main moved comes from one reflog**, the coordinator's (this Mac's) record of its own pushes. The commits' dates cannot be used: a proof that passes fast-forwards main, and the commits keep the dates they were made on the line.
- **Energy is partly modelled.** The Xeons have no energy counter, and the cards' energy is the card's lane only. The host's CPU is counted in its CPU lane.
- **No recommendation is built**, and none has been read. The fixed-past-self read (6) needs a census that crosses dials added since score 1; how to seat old values in today's table is open.
- **Clone round 5** is due about 11:10 today and is not in Table II.

## XII. How to make it again

`python3 -I tools/report/outgrowing.py QUEUE docs/outgrowing` reads the queue and treadcore's git, then writes `docs/outgrowing/data.json` and the six figures as inline SVG on the page's own colours. `sh tools/report/all.sh` builds this page with the rest. Figure colours: blue for the GPU, orange for the line, green for main. The light steps were deepened for the report's tan paper and validated for colour vision (worst pair ΔE 7.7, with every series labelled); the dark steps are the reference palette's (ΔE 9.4).

## References

[1] orrery, *The Whole Line: One Table, Read by the Planner, orrery and This Report*, lab report, 1 November 2026.

[2] orrery, *The Duty Cycle: The Fleet That Trains the Bots Is 98% Busy and Waits on No One*, lab report, 5 November 2026, with addenda XIV to XVI.

[3] orrery, *Three Generations, Filmed: The Line from Question to Commit, a Crowd of Duels That Are Really Different, and Every Wire in Its Node's Colour*, lab report, 5 November 2026.

[4] C. D. Rosin and R. K. Belew, "New methods for competitive coevolution," *Evolutionary Computation*, vol. 5, no. 1, pp. 1–29, 1997.

[5] D. A. Pomerleau, "ALVINN: An autonomous land vehicle in a neural network," in *Advances in Neural Information Processing Systems 1*, D. S. Touretzky, Ed. San Mateo, CA: Morgan Kaufmann, 1989, pp. 305–313.

[6] J. P. A. Ioannidis, "Why most discovered true associations are inflated," *Epidemiology*, vol. 19, no. 5, pp. 640–648, 2008.

[7] B. Efron, "Tweedie's formula and selection bias," *Journal of the American Statistical Association*, vol. 106, no. 496, pp. 1602–1614, 2011.

[8] S. G. Ficici and J. B. Pollack, "Challenges in coevolutionary learning: Arms-race dynamics, open-endedness, and mediocre stable states," in *Artificial Life VI: Proc. 6th Int. Conf. Artificial Life*, C. Adami, R. K. Belew, H. Kitano, and C. E. Taylor, Eds. Cambridge, MA: MIT Press, 1998, pp. 238–247.

[9] D. Cliff and G. F. Miller, "Tracking the Red Queen: Measurements of adaptive progress in co-evolutionary simulations," in *Advances in Artificial Life: Proc. 3rd European Conf. Artificial Life (ECAL '95)*, Lecture Notes in Computer Science, vol. 929. Berlin: Springer, 1995, pp. 200–218.

[10] W. G. Cochran, "The combination of estimates from different experiments," *Biometrics*, vol. 10, no. 1, pp. 101–129, 1954.

[11] P. Armitage, C. K. McPherson, and B. C. Rowe, "Repeated significance tests on accumulating data," *Journal of the Royal Statistical Society, Series A*, vol. 132, no. 2, pp. 235–244, 1969.
