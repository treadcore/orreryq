# The Double Report: How the Fleet Reaches the Game, and How to Use Orrery

*Lab Report and User Guide — IEEE Format · 1 November 2026*

Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery and treadcore.

Part One is the design of the process. Part Two is the story of how data becomes a bot's instructions, the amendment, and the guide to every screen, with pictures. Sources: [Orrery](https://github.com/treadcore/orreryq), [treadcore](https://github.com/treadcore/treadcore), [its documents](https://github.com/treadcore/treadcore/blob/main/documentation/INDEX.md).

---

## Abstract

**Part One** asks how the work of nine machines reaches a game, and finds that only two of nine training methods do. It reports that half of all promotions had stopped at unit tests and none at a family, moves the difficulty into values a person can change, and shows the process as a road, a timeline and a schedule. **Part Two** tells the same process as one story. A match is played, and a score becomes a number in a ledger; a curve fitted to the ledger proposes a change; reads judge it; a commit makes it a default; and in the next match that default changes which tank a bot fires on. It tells the second story too: how a vector of 143 senses passes through a matrix and becomes a command, by imitation, by evolution, by a confident override and on a graphics card. Then it is a user guide: every one of Orrery's 27 screens is pictured from the live run, numbered and explained, along with the inspector built for this report, which puts what a thing is, where it came from and what it means under the pointer on almost every number.

**Index Terms:** data flow, sequential testing, neural networks, residual learning, heuristic evaluation, user guide.

## Part One: The Whole Line

*How the fleet's work reaches treadcore. Published as its own report the same day; here whole.*

The grove fleet runs about 114 machine-hours of work a day across nine training methods, and the person who owns it could not say how they connect to the game. This report draws the connection, stage by stage, with what each stage takes, gives, simulates and adds to treadcore. Only the dial search and A/B reach the game today. The transform stops at a file the game cannot read. Crucible's GPU islands stop earlier: their nets have different senses and outputs, and no road leads from them to treadcore. Imitation nets play only in the census, because the client never loads a net.

The history answers a question nobody had asked. Half of all promotions ever requested (7 of 14) failed, every one at the brain's unit tests and none at a family. The last two were passes under the new ratchet, stopped by tests that read defaults they were meant to be independent of. A patch to six tests fixed them, on main as treadcore `1b14192`, and the first candidate it freed then passed its tests. No family job has ever failed. The red segment on the Queue page that reads like failure was 96% retired jobs, nearly all of which never ran.

We moved the difficulty into thirteen values a person can change, simulated what they buy, and applied two to the live run: ease 2.6 (held z 0.40) and a ceiling of 2.75. Every screen now explains itself in a panel collapsed by default, the queue says why each job is there, and a new Flow, Timeline, Queued and Values sit in the Queue chapter's column. Every generation now writes its own record, and the raw record packs for disc or release. A trial that passed on the defaults a generation replaces now gets another read rather than being thrown away.

**Index Terms:** data flow, sequential testing, generational search, heuristic evaluation, training records, residual learning.

---

## I. What was asked

Paul, 1 November, quoted because each clause became a section:

> "we want to write reports about each of our training methods. in specific I want to stream line, to unify the approach of all the features in this fleet ... I want to store all this training information. Github or maybe burned compressed media. I want snapshots and generations. I specifically want to conceptualize the idea of data flow from each of the modules. I don't understand how they all connect back to treadcore ... We should see diagrams and gantt style scheduling, connecting back to a timeline for the past and a gantt chart of scheduled tasks. also on the queue write a blerb about why the item is in the queue ... We have way too many screens, Or at least, I need an explanation on each screen (collapsed by default) ... We want full hurestic analysis."

And while this was being written:

> "I see the Crucible, GPU islands is its own thing. How can we imrpove the gerations, perhaps the Crucible is like the Families? Is there a difficulty adjustor that we can use to make it so families can be at optimal or more frequency ... I'm seeing lots of families fail in the history ... Is its Netbrain used as an optional imported net weights into treadcore ... We can also run multiple and mix or alternate between using source of instructions by computing both."

The answers, in order: Section II, the connection. Section III, a report on each method. Section IV, what the history says. Section V, the values. Section VI, families and crucible. Section VII, one approach, check-ins and netlets, and mixing brains. Section VIII, storage. Section IX, the screens and the heuristic analysis.

## II. How the pieces connect

Treadcore's bots play by rules: `commander.rs`, `tactics.rs`, `crew.rs`, `fleet.rs`. Those rules read about 120 numbers and 18 switches from `weights.rs`, and that file is the fleet's only way into the game today. Everything else is either a way of choosing those numbers or a thing that has not got a road yet.

!html(whole-line/fig-flow.html)

**Read it as a loop.** The fit proposes a set of dials. The census plays it against today's defaults. If it survives the reads, its numbers become a commit, every machine builds it, and that commit becomes the baseline the next trial is read against. Nothing here trains a net: the search is a Monte Carlo experiment on a hand-written program.

**The census is the instrument.** One seed is one starting world, played three times so that each team takes the trial seat once. Every bot is a full brain and no person plays: 15 minutes of game time, three respawns, on eleven maps. The reading is the trial team's score a seat less the baseline's, and both meet the same start, so most of a map's luck cancels. A seed still swings about 9.5 a seat, which is why every later stage exists.

!html(whole-line/stages.html)

### A. One trial, moving

The Flow page on the Queue chapter shows these numbers live. A trial called w4602 went like this at 09:32 to 10:31 on 1 November: a draw from the fit that moved many dials; first read on macmini, +2.58 +/- 1.51, z +1.71; three reads on, on saskatchewan, calber and boburner, the pool holding near z 2; then 400 unseen seeds on jaguaribe, -0.22 +/- 0.49. It looked strong for 187 seeds and was nothing. That is the reason for a held-out read.

!html(whole-line/fig-traces.html)

### B. The past and the schedule

!html(whole-line/fig-timeline.html)

!html(whole-line/fig-board.html)

The fine stripes on the left are the 90-second first reads. Long orange bars are held-out reads, at about 13 minutes each. The pink ones are the line's proof. The gap near 07:15 is the keeper's restart for the ratchet.

## III. A report on each training method

Each is a proposer of something the game might use. The verdict at the end of each is what it adds to treadcore today.

### A. The dial search

**Method.** `suggest.py` fits the ledger of every census and draws from what the fit does not yet know, keeping each number inside `RANGES`. The sequential census reads it. **Conditions.** Whole matches of bots, on all eleven maps. **Spend.** 105 of the day's 114 hours, with A/B. **Result.** First reads since the current defaults average z +0.18, with 59% at or above zero. **Report:** [difficulty](difficulty-lab-report.html). **Adds:** the numbers in `weights.rs` and `tactics.rs`, and so how every bot plays. *Reaches the game.*

### B. A/B versions

**Method.** Every switch flipped and every choice's other versions, each generation: 37 today. **Conditions.** The same census. **Result.** A/B reads worse at first, z -0.80 with 30% above zero, because most switches are on for a reason. But it has passed every real held-out read it reached since 31 October, three of three. The single-change trials also make the cleanest commits: w4399 and w2087, the last two generations, each changed one thing. **Report:** [brain versions](brain-versions-lab-report.html). **Adds:** which functions run. *Reaches the game.*

### C. Families

**Method.** Set pieces, not matches: a duel in the open, a raid on a guarded base, a rolling tank under two shells. Nine families, 6,600 runs, 33 seconds in all, each with a floor. **Result.** See Section VI. **Adds:** a veto, so that the average cannot rise by trading away a skill. *Reaches the game by what it refuses.*

### D. Anchors and the proof

**Method.** After a generation, the defaults from three generations back are read as a trial. Each hour, main's values are read against the line. **Result.** The clearest good news in this report. The defaults before r0060 read -5.87 +/- 0.66 and -5.40 +/- 0.67 against today's; those before r0062 read -4.08 +/- 0.66 and -3.42 +/- 0.64. Those gaps are three promotions' work, measured on seeds no search saw, and they are a far larger signal than any single generation's read. The proof, by contrast, reads the one carried generation at -0.14 +/- 0.16 against main: no difference yet. **Adds:** the correction and the gate. *Decides what reaches the game.*

### E. The transform

**Method.** A residual net over the rules' Move: it reads the senses, the biorhythm and the rules' own answer, and may move the point if it is confident. All zeros is the brain as it was. SPSA moves all 942 numbers by one noisy census a step. **Conditions.** The census with the patch switched on. **Spend.** About half an hour a day. **Result.** Six steps today read between -3.72 and +4.97 with errors near 2: noise, as expected this early. **Report:** [Algorhythm](algorhythm-lab-report.html). **Adds:** nothing yet. *The census reads the slot; the game has no file for it.*

### F. Crucible's GPU islands

**Method.** 2,048 small nets per island duel on the card, 128 episodes and 100 generations a segment, with champions passed between islands. **Conditions.** Its own arena: 64 x 64, six pillars, twelve rays, one shell each. A net of 32 inputs and 3 outputs. **Spend.** 7.5 hours a day today, on cards that do 400 to 580 million tank-steps a second. **Report:** [one source, two CUDAs](cuda-hybrid-lab-report.html). **Adds:** nothing. *No road.* See Section VI.

### G. Imitation: record, train, school, gauntlet

**Method.** Recorded rule-brain matches teach a net of about 16,000 numbers, then it is examined. **State.** Dormant since 30 October: the rotation now holds only the transform. **Result.** The learned tank is about 20 a seat behind the rules. **Report:** [a CUDA node](cuda-node-lab-report.html), [LEARNING-DESIGN](https://github.com/treadcore/treadcore/blob/main/documentation/LEARNING-DESIGN.md). **Adds:** `nets/bc2.bin`, seated by the census. *The client never loads a net.*

### H. Whole-brain sweeps

Switches, parts, a census of the best, round robin: each part alone against the defaults. **State.** Dormant since 29 October, with the A/B doing the same job continuously. **Adds:** readings the fit can use through the ledger.

### I. Older searches

SPSA and `tune` over a chosen few dials. **State.** Dormant since 29 October. They are duplicates of the fit in purpose, and the fit has the better record. **Adds:** nothing the fit does not. They should stay asleep, and their runs stay available by hand.

### J. Duplication, plainly

There is one real duplication left: three dormant ways of searching dials. The live methods do not overlap. But the CPU lanes and the GPU lanes are not one brain. The CPU search is a hand-written program being tuned, and the GPU search is a different creature in a different world.

!html(whole-line/fig-hours.html)

## IV. What the history says

!html(whole-line/fig-promotions.html)

### A. Half of all promotions stopped at a test

| Asked | Candidate | Ended | Why |
| --- | --- | --- | --- |
| 28 Oct 10:12 | @strongest | failed | `default_weights_are_todays_constants` |
| 29 Oct 14:06, 16:19 | w1198, twice | failed | the tests; `the_square_law` |
| 29 Oct 14:17 | w1266 | failed | `a_capped_castle_fills_then_lines_the_road` |
| 30 Oct 12:57 | w1656 | failed | `a_switch_comes_back_and_a_slider_keeps_the_target` |
| 1 Nov 09:54 | w4540 | failed | `with_bio_off_there_is_no_wave_at_all` |
| 1 Nov 10:31 | w4616 | failed | `a_slider_steps_and_steps_back`, `smooth_is_a_weight_...` |

These tests are not catching bad brains. They call `Settings::default()` and then assert a number, so when the fleet moves that default the test fails. [brains.md](brains.md) already gives the rule: "If an existing test pins a number the choice moves, give that test the number it was written for." The last failures break that rule. **Any trial that moves `alpha` cannot promote, and 65 of the last 177 fit draws (37%) move it.** The seven failures hit six different tests, so fixing them one failure at a time is slow: each costs a passed candidate.

The patch is small edits to tests alone, in [`whole-line/treadcore-test-pins.patch`](whole-line/treadcore-test-pins.patch). We applied it to a scratch copy of 9d438c8 with both failed candidates' values and ran the brain's tests: 134 passed, 0 failed.

Because the failures keep finding new tests, we then looked for all of them at once: every number that the search may move, 107 of them, moved 7% together, inside `RANGES`. That found three more pinned tests before they could stop a candidate: `the_posture_leans_the_ladder`, `a_fleet_crosses_a_bridge_in_file` and `a_switch_comes_back_and_a_slider_keeps_the_target`. The patch fixes those too, six tests in three files, and with it all 134 pass at +7% and with both candidates' values. Moving everything together by -40% or +50% still fails 5 and 3 tests, among them `every_scenario_holds`. We left those alone: a brain with every dial that far out may really be a different brain, and that is what those tests are for.

**Applied, 1 November, at Paul's word ("commit. push. impliment."), as treadcore `1b14192`.** Main moving did the rest with no hand on it: the planner replayed the line on top of it as 62f5a00 and retried both stopped candidates, and `w4540` went through the tests that had stopped it. A failure like these can still come from a test nobody has found, so the Board now marks any stopped promotion as blocked and next essential.

### B. Why the red bar looked like failure

The Queue page drew "2,429 failed or stopped" in one red bar. Here is what it held:

| | Jobs | Hours spent | What it is |
| --- | --- | --- | --- |
| Stopped, first reads and reads on | 2,124 | 0.2 | queued for a generation that was overtaken: they never ran |
| Stopped, other | 146 | 13.5 | builds, held-out reads, whole runs, and what a person or a restart stopped |
| Failed, first reads and reads on | 112 | 4.2 | the job exited 0 on nearly all; 108 of the fleet's failures are on saskatchewan and columbia, where SSH penalties hit, so most likely results that could not be fetched |
| Failed, GPU segments | 40 | 0.1 | no machine named on nearly all: not started or stopped with the queue |
| Failed, promotions | 7 | 0.1 | Section IV-A |
| **Failed, families** | **0** | 0 | |

The bar now draws retired apart from failed, in grey.

### C. What a generation throws away

Each generation discards every read on the old defaults. When r0069 landed at 08:18, two held-out reads in progress would have passed: w4398 at z 0.83 and w4424 at z 1.07. The 2,124 retired jobs above are the same effect, cheaply. It matters more the faster generations come: at one every 30 minutes, a trial that needs 25 minutes of reads rarely finishes. **This limits the pace, and the simulation in Section V does not model it,** so its pace figures are optimistic.

So a generation now carries what it would have lost. `carry_passes` takes up to three trials that passed on the defaults the last generation replaced, strongest first, and gives each one read on the new ones, ahead of the search. Only one generation back, because a read says less as the defaults drift. Run against the live queue, it chose exactly `w4424` and `w4398`.

### D. The funnel, at the current defaults

In the 2.5 hours from 08:20: 212 first reads, 139 reads on, 10 held-out reads. Of 121 trials decided, 113 were dropped and 8 passed the read-on bars. Of the real held-out reads, 2 passed, and tests stopped both. No generation was carried in that time. Without the test failures, the same passes would have come 98 and 37 minutes apart.

## V. The values

Every number that sets the difficulty, and how much is carried, now lives in one table, [`tools/plans/line.json`](../tools/plans/line.json), and is changed by the Values page, by `tools/fleet-tune.py QUEUE KEY VALUE`, or by hand in `QUEUE/tuning.json`. A change is live at the next plan, about a minute, and restarts nothing. Each is held to its range at the button, in the tool and in the planner. A broken file means the defaults, never a stopped plan.

!html(whole-line/values.html)

### A. What they buy

`tools/plans/difficulty-sim.py` now takes this game's noise and the read-on limit. The prior had to be calibrated, because fitting it to first reads (N(-0.14, 1.03)) gave one generation every 11 minutes, which the run plainly does not do: outliers such as the anchors inflate the spread. N(-0.65, 0.45) at 9,000 seeds an hour reproduces 86 trials an hour against the 85 measured, and a pass rate of 7% against 6%; it gives 20% at the held-out read against two of five measured, a handful.

!html(whole-line/fig-sim.html)

| Ease | Held z | One every | Truly worse | Gain a day |
| --- | --- | --- | --- | --- |
| 2.0 | 1.00 | 86 min | 25% | +3.8 |
| 2.2 | 0.80 | 65 min | 29% | +4.0 |
| 2.4 | 0.60 | 48 min | 35% | +3.7 |
| 2.5 | 0.50 | 44 min | 42% | +2.6 |
| **2.6** | **0.40** | **37 min** | **37%** | **+4.6** |
| 2.75 | 0.25 | 34 min | 45% | +2.1 |
| 3.0 | 0.00 | 26 min | 49% | +1.1 |

The Monte Carlo error on these is large enough that 2.5 and 2.6 are not really different. The shape is what to trust: the gain holds to about 2.6, then falls.

Raising the read-on limit from 0.5 to 0.75 or 1.0 bought no gain at any ease, so it stays at 0.5.

### B. What was applied to the run

Applied at about 10:40 and read back from the planner's own state:

- **Ease now 2.6**, held z 0.40. This is the fastest setting that gives up no gain. From here each generation takes 0.05 off.
- **Ease ceiling 2.75**, down from 3.0. At 3.0, a generation can pass on no evidence at all, and half are truly worse.

Everything else stays where you set it: 0.05 harder each generation, and four hours dry before easing.

**About half an hour is not reachable through the bars alone.** The simulation reaches 30 minutes only at an ease near 2.75 with the read-on limit raised, where gain falls to +1.2 a day. The honest expectation is 35 to 50 minutes, and whether the carry improves on it is not yet measured.

## VI. Families and crucible

### A. Are families failing?

No. Across 130 family verdicts on record, 2 were UNDER, both on the defaults and both one family, a raid on a guarded base at 70.2% against a floor of 75%. You lowered that floor to 65% on 30 October. All 62 of the fleet's candidates hold every floor. What looked like family failure was the tests and the red bar of Section IV.

| Family | Mean held | Floor | Margin in errors |
| --- | --- | --- | --- |
| a duel in the open | 85.5% | 55% | 16 |
| a raid on a guarded base | 71.6% | 65% | 3.5 |
| a tank under a ready gun | 81.4% | 80% | 1.2 |
| a rolling tank under two shells | 99.3% | 99% | 1.0 |
| five others | 99.8 to 100% | 95 to 99% | 3.5 or more |

### B. Should families have a difficulty adjustor?

**No, and none was built.** An adjustor would make floors easier to pass, and the floors are not what stops anything. It would save nothing: all nine families together cost 33 seconds, about 0.1 hours a day (Fig. 5). The floors are also your decision, in the scenario files. Two sit close, a ready gun and two shells, and those are the first to watch if a family ever does begin to fail.

### C. Can the beginning success rate improve?

Yes, and the bars are the wrong lever, because Section V shows the read-on limit buys nothing. In order of what each would buy:

1. **The test patch, done.** More than a third of fit draws became promotable at once.
2. **Carry a pass across a generation, done.** A trial that passed on the replaced defaults gets a held-out read on the new baseline. It covers held-out passes only: a trial still in its reads on when a generation lands is still dropped. Its gain is not yet measured.
3. **Test before the long read.** Running the tests before a 13-minute held-out read would save a read each time they fail. After the patch they should rarely fail, so this comes after it.
4. **Keep the proposers as they are.** Fit draws lead at first read and A/B leads at held-out read, so neither should crowd out the other. Moving families earlier would save nothing, since they almost never fail.

### D. Is crucible like the families?

They are opposite in role, and the difference is useful. A family is a **veto**: a cheap fixed test on the game's own simulation that can only say no. Crucible is a **proposer**: an enormously fast search in another world that cannot yet say anything about this one.

The likeness points to the way to join them. A family is a short scene on the real simulation with a pass rate, so **the families are the natural exam for a bridged net,** and later the natural curriculum. Duelling skill from crucible, cloned into a net with treadcore's senses, could be read first against `a-duel-in-the-open` and the shell families, in 33 seconds, long before it faces a census. That is a far cheaper first read than any it has now.

### E. Is crucible's net an optional import for treadcore?

**No, and it cannot be yet.** The two have nothing in common but the word:

| | crucible's net | treadcore's `Net` |
| --- | --- | --- |
| Reads | 32: twelve rays, bearing, speed, hit points, reload | 143 senses of the real game |
| Decides | 3: turn, throttle, fire | 42 scores across seven action heads |
| World | an empty arena, a duel | bases, drones, depots, mines, teams |
| Used by | crucible | `NetBrain`, in the census, the tests and the trainer |

Treadcore's own `NetBrain` is not an option for players either: the client has no way to load a net. **So the sliders move dials today, not brains.** The `model` and `patch` rows do appear in the `U` page, as every weight does, and that looks like a bug to fix: from reading `patch.rs`, moving `patch` above 0 asks for `CENSUS_PATCHES`, which a player's machine does not have, and it panics. We read this and did not run it. The design in [brains.md](brains.md) is a bridge: play a champion as a teacher inside an arena with treadcore's senses, and clone it into a treadcore net (behaviour cloning, as `bc1` was made). The result goes in slot 7 and is read like anything else.

Expect little at first. A clone learns to duel, and the census scores a whole game. Its likeliest use is a patch or a role rather than a whole brain.

## VII. One approach

### A. Every method is a proposer

!html(whole-line/fig-unified.html)

The unification is one sentence: **a method's only job is to produce something the census can seat, and the same road judges all of them.** The dials already work this way. The transform and the nets become the same once the game can load a slot. The rule costs no new process, and it makes the GPU question precise: not "how do we use the GPUs" but "what can crucible hand to the check-in?"

### B. Check-ins and netlets

A **check-in** is one proposal entering the road, one record: what it is (a weights file or a slot), its hash, who proposed it (fit, A/B, SPSA, crucible segment), its parent generation, each read, and how it ended. Today those facts are spread across the job, the `results/` directory and the run's state. `plan/pipeline.json`'s `traces` assembles them for the last eight, and the generation record keeps them for what is promoted. The step left is to write one for every trial at its end.

A **netlet** is a small learned part with one job: a slot file and a manifest naming its inputs, outputs, parent and evidence. The transform is the first: 942 numbers, all zeros meaning the brain as it was. The rule that makes netlets safe to keep adding is the transform's own: **a netlet that does nothing costs nothing and changes nothing,** so the census can read it as it reads any dial. One could steer retreats, another aim mortars. Each is promoted or dropped alone.

### C. Mixing brains: computing both

!html(whole-line/fig-mix.html)

Your idea fits the house rule, "either/or is a scalar". There are four ways to do it, cheapest and most honest first:

- **C, override when sure, is built:** the patch. The rules decide and a net may move their point past a confidence bar. Since the net can only be worse by moving something, the census reads the risk directly.
- **A, by seat, is built for the census:** `roles` and `model` choose per team. It wants one more step to choose per tank, and no game path yet.
- **B, alternate,** a tank following one source and then the other on a slow clock, is new. The biorhythm's clock would serve. It is cheap to compute and gives the game some variety, which a person may enjoy even where the census shows no gain.
- **D, blend,** is new and has a limit. The rules produce a decision and the net produces 42 scores, so they cannot be averaged before the choice. They can be averaged afterward, at the Move's point, which is where the patch already acts. It does not apply to firing or building, which are yes or no.

A net decision takes about 10 microseconds, so computing both costs little. Each needs a game-side slot first, which is the same gap again: **the game reading a slot is the one piece of work that unblocks netlets, mixing, the bridge, and player-selectable brains together.**

### D. The order

1. The test patch. Done: treadcore `1b14192`.
2. Carry a pass across a generation. Done.
3. A game-side slot: the client loads a patch or net from a file, off by default. This is what makes the transform shippable.
4. The bridge from crucible to slot 7, with the families as its exam.
5. Mixing modes B and D as weights, then player sliders for them.

## VIII. Storing the record

!html(whole-line/fig-storage.html)

**Generations go in git.** `tools/fleet-archive.py QUEUE snapshot` writes one directory per generation with its values, evidence, families and commit, plus a list of every promotion including the failures. The planner now runs it whenever a promotion finishes. The seven generations so far, with the settings and ledgers, come to 1.2 MB, so years of this fit comfortably in a git repository.

**Raw packs go on an SSD, then on release assets or disc.** `fleet-archive.py QUEUE pack bd25` writes what no earlier pack holds to `PACK-NNN.tar.xz`, closing each below a disc's size, with `MANIFEST.tsv` holding every file's sha256. `verify` reads every file back out and checks it.

The whole record so far was packed and checked: **3.82 GB and 173,018 files went into one 393 MB pack, 9.7 to 1, in 25 minutes at low priority. Reading every file back found 0 differences.** It sits at `QUEUE/archive/packs/`, on this Mac only. The record grows by about 0.9 GB a day raw, or about 95 MB a day packed.

**GitHub or disc: both, for different things.** My recommendation:

| | Git repo | GitHub release asset | BD-R or M-DISC |
| --- | --- | --- | --- |
| Holds | generations, ledgers | packs | packs |
| Good at | diffing, searching, linking from reports | offsite copy, one link | a copy nothing can change, off any network |
| Limit | 100 MB a file; repos should stay small | 2 GB a file | 25 GB a disc; a person's time |
| Risk | a large repo is slow forever | a host's terms | a burner, and shelf life |

Those GitHub limits are as I know them; check them before relying on them. Both orrery and treadcore are **public** repositories, and the raw logs hold machine names, user names, addresses and paths. So the record belongs in a separate **private** repository, and packs should not be published as they stand. Nothing has been sent anywhere.

The manifest is what makes a disc trustworthy decades on: it needs only `tar` and `sha256sum`. At this rate a 25 GB BD-R holds about eight months, and today's pack would fit on a CD.

## IX. The screens

### A. What changed

**Explanations.** Every screen has an "About this screen" bar. Shut, it is one line saying what the screen does. Open, it answers six questions: what it does, where it ties in, why it is drawn this way, what to look for, what is being simulated, and why it helps the brain. It closes when you leave. A test fails if any screen is missing an answer, or if a word has a character the fonts cannot draw. All the words live in `line.json`, the same table the planner and this report read.

**The queue says why.** Queue, Queued lists what is running and waiting, in order, each with a line on why it is there. A held-out read adds the bar it must pass. The `upcoming` list had been collected and never drawn.

**The data has a picture.** Queue, Flow draws the road with one real trial traced beneath; Queue, Timeline draws past and forecast by machine; Queue, Values holds the buttons.

**A rearrangement.** The Pipeline had no key in the Queue's column, and the only way there was a menu. One chapter now has one column: Fleet, Runs, Board, Flow, Timeline, Queued, Values.

### B. Too many screens?

There are 27 faces, counting pages and tabs. By what they answer, they fall into five groups, and only one is about the line:

| Question | Screens | Count |
| --- | --- | --- |
| Is the line moving, and why not? | Fleet, Board, Flow, Timeline, Queued, Values, Candidates, Flags, Keeper | 9 |
| What did it find, and what is in the brain? | Found, Commits, Algorhythm (6 tabs), Net | 9 |
| What are the machines? | Machines, Media, Storage, Projects | 4 |
| Touch a machine | Lab, Sessions, Orchestrate, Chat | 4 |
| Ask for something by hand | Runs | 1 |

We removed none. Each still has a job, and removing one is your call. These are the merges I would make next, in order: Algorhythm's Fleet tab goes (Flow replaces it, with more). Net folds into Algorhythm's Matrices, since it shows the same net. Flags and Keeper's alerts become one list. That takes 27 to 24, and the next bigger saving would be moving Media and Chat behind menus, since neither touches the line.

### C. Heuristic analysis

Nielsen's ten usability heuristics, applied to the console as it stood this morning:

| Heuristic | Finding | Severity | Now |
| --- | --- | --- | --- |
| Visibility of status | Red bar mixed retired with failed, and read as failure | high | fixed |
| Visibility of status | A passed candidate stopped by tests showed nowhere as stopped | high | fixed: blocked, next essential |
| Match to the real world | "Ease", "held z", "stage" are this project's own words | medium | explained on Values and in About |
| User control | No way to move the difficulty without editing code | high | fixed: Values, with Default |
| Consistency | Queue's column dropped the chapter's second view | medium | fixed |
| Error prevention | Values could be set past where they were simulated | medium | fixed: ranges, three places |
| Recognition over recall | The queue's order and reasons existed only in the planner's head | high | fixed: Queued |
| Flexibility | Frequent paths need several clicks; `Command-digit` reaches chapters only | low | open |
| Minimalism | 27 faces, and eight are not about the line at all | medium | explained; merges proposed |
| Recover from errors | Expired certificate caused silent network penalties | high | fixed 1 November; no warning before expiry yet |
| Help | Nothing said what a screen was for | high | fixed |

The search has heuristics of its own, and this is how they held up:

| Heuristic | Held? | Evidence |
| --- | --- | --- |
| Cheap reads first | Yes | Half of all trials stop at 55 seeds |
| Selected reads must be read again unseen | Yes | w4602: z 1.9 pooled, then -0.45 unseen |
| Cheap checks before expensive ones | **No** | Tests run after a 13-minute read and stopped 7 of 14 |
| Fix what stops the most | **Was no** | The Board's essential was "not built" while the line stood stopped; now fixed |
| One lower bar with one high gate | Too early | One generation on the line; proof reads -0.14 +/- 0.16 |
| Generations add up | Yes | Anchors: +3.4 to +5.9 over three promotions, unseen seeds |
| Lower bars give more | Only to a point | Fig. 7, and no gain at all from the read-on limit |

### D. Every screen

!html(whole-line/screens.html)

## X. Threats to validity

The simulation is a rough model. Its prior was fitted to the funnel rather than measured, it matches first reads and passes better than it matches held-out reads, and it ignores what a new generation discards. The funnel since the ratchet covers only 2.5 hours and two passes: too small to say whether 2.6 will give the cadence shown. The anchor gains include several promotions, and we did not separate how much each gave. The run moves while this is written, so its numbers are as of about 10:55 on 1 November, and the figures can be redrawn by `tools/report/whole-line.py`.

## XI. Still open

- A trial still in its reads on when a generation lands is still dropped, and the carry's gain is unmeasured.
- The game has no slot, so neither the transform, the nets nor any mix can ship.
- No check-in record is written per trial yet, only per generation.
- The Timeline and Flow pages need the new build: the running Orrery is the old one until it is reopened.
- The raw record is on this Mac alone. No disc is burned and nothing is uploaded.
- The `patch` row on treadcore's `U` page looks able to crash a player's game (Section VI-E): read, not run.
- This report's figures are one moment of the run. The screens are live.

## XII. Reproducing this

```sh
Q=~/code/treadcore/build/queue/grove
python3 tools/fleet-tune.py $Q                 # the values as they are
python3 tools/fleet-tune.py $Q ease_now 2.6    # move one
python3 tools/plans/difficulty-sim.py --mu -0.65 --tau 0.45 --rate 9000 --keep 0.5
python3 tools/fleet-archive.py $Q snapshot     # generations
python3 tools/fleet-archive.py $Q pack bd25    # raw, for a disc
python3 tools/fleet-archive.py $Q verify
python3 tools/report/whole-line.py $Q && sh tools/report/all.sh
```

---

## Part Two: The Story and the Guide

*Paul, 1 November: "use Orrery. and give a screen by screen breakdown. Annoteate. Add an ammendment second pass more pictures and explanations of screen. With a story of the functions, the transforms, and the data flow. Write a linear story of a lab report telling us how data transforms and becomes AI instructions. Both in brainz weights, and AI neural nets. Describe like a user guide how to user Orrery in its current state, take pictures of every screen ... add insepctor mode to just about every data with hover information ... This is part two to the last report ... double feature."*

## XIII. Amendment to Part One

A second pass through the running system changed these things. Part One above is otherwise as it was published, with the transform's size corrected in place.

- **Generations 3 and 4 landed.** `r0073` promoted `w4540`, `bio` from off to square, stopped that morning by a test. Then `r0074` promoted `w4749`. **`w4749` holds the same values as `w4616`, the second stopped candidate, so the carry of Section IV-C brought a find across a generation that would once have been thrown away.** One case, but it is the case the carry was built for. Its held-out read was +0.82 +/- 0.40.
- **The transform has 942 numbers, not 918.** 918 was right before four base senses joined its inputs on 30 October: 3 x (153 + 3) + 3 is 471 a step, over 2 steps.
- **The proof has moved the wrong way, a little.** The line against main read -0.14 +/- 0.16, then -0.28 +/- 0.17: z -1.64 with `r0069` alone carried, inside the noise. It has not read the later generations yet. This is why the generations are carried and not pushed.
- **A generation emptied the Terrain.** `tools/analysis.py` asked only `main` for commits, and only `fleet.tsv` for reads. Generations stand on line commits, and `fleet.tsv` keeps a queue's reads for today's defaults alone. We fixed the commit half. The reads of game 4 are in each job's results and in no ledger the tab reads, so it still shows nothing, and says so. Reading them from the results is open work.
- **The Runs page's rotation line overstates.** It names every kind of run, and `plan.json` today gives the rotation only the transform. Section III-G's "dormant" is what is true.
- **`boburner`'s GPU is off Crucible on purpose or by accident.** The log shows it set off at 07:59 on 1 November. It is the amber lamp on Keeper.
- **Generations 1 to 4 were then undone by an anchor, on noise.** The anchor read at a generation's low bar, and `w4845`, the defaults three back, went on the line as generation 5 at z 0.76. An anchor must now clear the proof's z 3. The story below still follows `w4540`, and `bio` is off again until something reads it back on. See [Eight Named Minds](bot-styles-lab-report.html).
- **By-hand census runs on macmini read one map of eleven,** because the fix of 31 October reached only the search's jobs. Fixed.
- **Every commit on treadcore's main replays the line,** with new hashes. A build of the replaced commit then reads as failed in one flag until the new builds are in. That is a false alarm, and it arises whenever a person commits to main.

## XIV. The first road: how a match becomes a dial

This is one number's life, told in order, with the real data of `w4540`. Follow the arrow all the way round: the last step feeds the first.

### A. A world is played

Nothing in the fleet begins with a rule about what is good. It begins with a game. `brain_census` takes a seed, makes a starting world from it on one of eleven maps, and seats sixteen bots on three teams. The world is played three times so each team takes the trial seat once. The trial team runs one brain, the others the baseline. No person plays and no window opens. The match has 15 minutes of game time and three respawns, and the simulator is deterministic: the same seed and binary play the same match.

!html(double/game-sixteen-fig.html)

**What enters:** a weights file, a seed. **What leaves:** a score for each seat, in `g-SEED.log`.

### B. A match becomes a number

Each seat's score is a weighted sum of what it did (`ledger.rs`): a win is worth 10, a kill 1, a death costs 1, ground held 2, a build 0.1, a road 0.05, time in a castle 3, and there are rewards for a direct hit, a pillbox taken from the enemy, an advance, a full trip home and more. The fleet's definition of playing well is these lines of arithmetic, so a change here changes what every later step means, and it bumps `GAME_VERSION`.

A seed's reading **d** is the trial team's mean score a seat less the baseline's. Both meet the same start, so most of a map's luck cancels. `pool.sh` then takes the seeds' readings x:

```text
d = mean(x)        se = sqrt( sum (x - d)^2 / (n - 1) ) / sqrt(n)        z = d / se
```

A seed still swings about 9.5 a seat, so 55 seeds have an error near 1.27. `w4540`'s first census read +0.28 +/- 1.11: nothing yet. That number and its error are all the rest of the road ever sees.

**What leaves:** `pooled.txt`: `every map +0.28 +/- 1.11 over 55 seeds`.

### C. The number joins a ledger

`ledger.py` makes one row per census: host, commit, seeds, the trial's dials, d, se, z and each map's reading. `fleet.tsv` holds about 3,600 of these. **This table is the fleet's memory.** Everything the search knows about the brain, it knows from these rows.

### D. A curve proposes a change

`suggest.py` fits the ledger. For each dial it measures how far a trial moved it, in doublings, x = log2(v / default), and fits every dial's effect as a curve:

```text
d ~ sum over dials ( a x + b x^2 )     each row weighted 1 / se^2,  ridge 1.0
```

The top of a curve says where that dial seems best, and the fit's own uncertainty says how little it knows. Then it proposes in several ways: `best`, the tops it is sure of; `sample-N`, a draw from what it does not know (Thompson sampling: try what might be good); `screen`, a dial not yet read at half or double. Beside it, `ab_trials` flips each switch and tries each choice's other versions. `w4540` came from there: "A/B: bio square against off."

RANGES holds every proposal inside its limits, and a person's decree (min equal to max) is never searched.

**What leaves:** `trial.weights`: `bio = 3`. A proposed brain is one small text file.

### E. Reads judge it

The same census, on fresh seeds, stage by stage: 55, 82, 124, 187, 275, 418. A trial leaves as soon as its pooled z says keep, drop or pass, with the bars lowered by the ease. Half stop at the first read, and that cheapness pays for everything after. Then comes the read that matters: 400 seeds from 60,000,000 up, which no search has seen, because a selected trial's early reads are lucky by construction. `w4540`: **+0.39 +/- 0.41, z 0.95**, past the bar of 0.60 that hour.

!html(whole-line/fig-traces-copy.html)

### F. Families, then tests

Nine set pieces check what an average can hide, in 33 seconds. Then, on a branch, the brain's own unit tests. `w4540` failed here at 09:54, on a test that had pinned a default, and passed at 11:33 once six tests were put right.

### G. Numbers become source code

`set-defaults.py` rewrites the number on its line in `weights.rs`, and the same field of `Tactics::default()`. This is the actual generation, every character of it:

```diff
-    Bio "bio" 0.0, "intuition: the shape of a tank's slow waves (choice: off | sine | triangle | square | saw): bio.rs";
+    Bio "bio" 3.0, "intuition: the shape of a tank's slow waves (choice: off | sine | triangle | square | saw): bio.rs";
```

**This is the moment data becomes an instruction.** The commit says why: `promote grove/w4540 as the brain's defaults -- bio 0.0 -> 3.0; census +0.28 +/- 1.11, held out +0.39 +/- 0.41`. Every machine builds it, and it becomes the baseline the next trial is read against. It stays on the local line until the proof reads it z 3 past main.

### H. The number runs in a match

When a bot is made, `Settings` holds every weight and `set_settings` hands them to the parts of the brain. Each time a bot thinks, to choose a target, `Tactician::rate` scores each enemy (`tactics.rs`). Here it is with today's numbers:

```text
near = w_near / (1 + d / near_scale)                 w_near 2.0, near_scale 15
s    = near + w_wounded x hurt                       w_wounded 1.2
       + w_finish    if one direct shot kills        w_finish 0.553
       + w_in_range  if within 10 tiles              w_in_range 1.4
       + focus, threat, stick, boat and call terms
```

Worked through, leaving out those last terms:

| Enemy | Distance | Armour | near | wounded | finish | in range | Score |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | 8 | 40 of 100 | 1.30 | 0.72 | 0.55 | 1.40 | **3.98** |
| B | 25 | 100 | 0.75 | 0 | 0 | 0 | 0.75 |

A wins by far. Had A's lead been small, a challenger must beat the held target by 15% (`margin`) two thinks in a row (`confirm`), so a bot does not flicker between targets. These two numbers exist because the fit found them worth having.

### I. A dial changes a bot's mood

What `bio = 3` does: each tank now has three slow square waves, at periods of 60, 73 and 86 seconds, offset by its seat. Their mean is its mood, and it scales how bold the tank is:

```text
engage_odds = 0.354 x (1 + 0.25 x mood)
```

With a square wave the mood takes four values, so a tank's nerve moves between 0.27 and 0.44 odds: **some moments a bot presses, and some moments it holds.** A person would call that temperament. The census says only that it read +0.39, inside two errors, so it is a generation and not yet a proof. (The next generation moved `bio_amount` to 0.18.)

### J. The number becomes a shell

```text
target -> think_map -> aim = lead(me, target) -> Command::FireDirect { at: aim } -> Order { player, cmd }
       -> World::step -> apply: not reloading? has shells? in range? line of sight?
       -> a Shell with its impact tick; shells - 1; reload = 4 s
```

`Command` is the whole vocabulary a brain has: Move, Stop, FireDirect, FireIndirect, Launch, Deploy, Tow, Ping and a few more. Any brain, rules or net, ends here. The simulator judges all of them alike, so a brain cannot cheat. It can only order.

!html(double/game-fire-fig.html)

### K. The circle closes

The shell does 45 damage and A, at armour 40, dies. A kill: +1 in the seat's score, and the trial team's mean rises, so the seed's d rises and with it the pooled d. The ledger gains a row, the curve moves a little, and a new trial is proposed.

!html(double/road-a.html)

## XV. The second road: how senses become a command

A net decides differently: nothing in it says "near" or "wounded". Everything it knows is numbers in, numbers out.

### A. What it senses

143 numbers (`senses.rs`). The first 88 are a compass: 8 directions by 11 channels, hostile tank, allied tank, hostile pillbox, neutral pillbox, our pillbox, depot to take, our depot, shell coming, ground, cover, call. A thing's strength is `1 / (1 + d/8)`: a hostile tank 8 tiles dead ahead puts **0.5** in sense number 0. Then body 12, navigation 6, contacts 18, hints 9, shells 5, air 5. The Senses tab of Section XVII shows which of these bc2 actually uses.

### B. What it does with them

A net is three tables of numbers, 143 to 64 to 64 to 47. Each layer multiplies, adds an offset, and clips below zero, except the last:

```text
for each output o:   v[o] = sum( w[o,i] x[i] ) + b[o]       then max(v, 0) except on the last layer
```

That is 143x64 + 64 + 64x64 + 64 + 64x47 + 47 = **16,431 numbers**, on the Net screen as three pictures. It takes about 10 microseconds, five times a second.

### C. From scores to commands

The 47 scores split into seven heads: drive 10, gun 9, lead 3, mortar 9, drone 5, squad 7, signal 4. In each, the highest allowed choice wins. Drive becomes `Move` six tiles toward that sector. Gun becomes `FireDirect`, mortar `FireIndirect`, drone `Launch`, signal `Ping`. Squad is masked off. **The same Command, the same simulator, the same census.** That is why a net and the rules can be compared at all.

### D. Teaching it: imitation

`record` plays scripted matches, and every fifth of a second, for each living seat, stores 143 senses and 7 labels for what the rule brain did. `tools/bc` trains by masked cross-entropy with Adam. For bc2: 52.3 million samples from 1,260 seeds, batch 32,768, learning rate 0.01, 12 epochs, in 226 seconds on a GPU, whole seeds held out. Rust's own forward pass then re-reads the held-out samples to check it matches the trainer. The result makes the rules' choice this often on matches it never saw:

!html(double/net-agree.html)

The red ticks are why those numbers need care: always guessing the commonest choice nearly reaches them on mortar, drone and lead. Only drive and gun show real learning. **And copying is not playing:** the learned tank reads about **20 a seat behind the rules** (`nets/phase3.bin`, -23.52 +/- 0.38). A clone has seen only what the rules do when things go well.

### E. Practising it: evolution

`train` and `school` make the net its own teacher with antithetic evolution: take the net, add noise to all 16,431 numbers, play both the plus and minus, and step toward whichever scored higher. `school` runs a curriculum of training maps, and keeps a net only if it rose past two errors and broke no passed course. `gauntlet` is an examination only. All dormant since 30 October, with the transform taking their place.

### F. The transform: a confident override

The idea at the heart of Algorhythm, which is also where any mixing of brains begins: **the rules decide, then a small net may move their answer if it is sure.** It reads the senses, three waves, the rules' answer and four base senses: 153 numbers. Two steps later:

```text
y[k+1] = y[k] + tanh( A[k] [x; y[k]] + b[k] )       y = (across, down, confidence)
if y[2] >= 0.5:   to = clamp( to + (y0, y1) x 10 tiles )
```

All zeros is the brain exactly as it was. So it starts just past the gate, at `b[2] = 0.6` (tanh 0.6 is 0.54), moving nothing. Since it can be worse only by moving something, the census reads the risk directly.

Its 942 numbers cannot be fitted by a curve, so it trains by SPSA: one random direction s, a census of theta + c s against theta - c s, and one small step:

```text
theta[i] += clamp( a_k d / (2 c_k s[i]), +/- 0.01 )      a_k = 0.00025 / (k+1)^0.602     c_k = 0.03 / k^0.101
```

A read of d = +2 at step 1 moves each number about 0.0055. Today's steps read between -3.72 and +4.97 with errors near 2: noise, as it should be this early. Thirty steps at a few minutes each is a slow road, and that is the price of asking one question of 942 numbers.

### G. Crucible: a different world

A graphics card plays 2,048 small nets against each other, in duels: an empty 64 by 64 arena, six pillars, one shell each. Their world is twelve rays, a bearing, speed, hit points and reload: 32 senses, plus the scripted tank's own answer in the hybrid build, 35 in all. Net sizes 35, 32, 32, 4, tanh throughout: exactly **2,340 numbers**, which is why `champ.bin` is 9,360 bytes.

```text
fitness = dealt - taken +/- 2 for a win or loss + draw value + 0.5 x aim/steps
keep the best 16;  all others: a copy of a top-quarter parent + 0.03 x gauss per weight
```

Every 5 generations the champion joins a hall of fame; islands swap champions; an exam against a ladder of milestones keeps honest score. Fast and real, in its own world. Its nets had not played a tank in treadcore when this was written; [the report that follows](bot-styles-lab-report.html) changes that.

!html(double/road-b.html)

## XVI. A user guide to Orrery

### A. Starting it

```sh
cd ~/code/orrery
make install OPTIONS='--operator paul --fleet grove --fleet-cmd "copal fleet" --queue ~/code/treadcore/build/queue/grove --user user'
open /Applications/Orrery.app      # or: orrery --gui --operator paul --fleet grove --queue DIR
```

`make install` keeps the options it was last given, so afterward `make install` alone is enough. The older [user guide](user-guide.html) still holds for the museum interface; this one covers the training console as it stands. Without `--operator`, Orrery is read-only: its buttons do not exist.

### B. The shape of every screen

!html(double/anatomy.html)

The chapters run in the order of the work: add a computer, give it work, the work runs, read what it found, look in, command it. Settings sits under it all. **Press a chapter's number with the command key to go there.**

### C. Your first five minutes each day

1. **Settings, Keeper.** Every lamp green? Amber on `lanes` or `search` is the most common thing to read.
2. **Queue, Board.** Read the red headline. If it names something other than the road to one brain, that is your job today.
3. **Queue, Fleet.** A machine with no lit lamp is lost seeds.
4. **Results, Candidates.** What is promoted, what stopped, and why.
5. **Queue, Values,** only if generations are coming too slowly or too cheaply.

### D. How do I...

| I want to | Go to | Do |
| --- | --- | --- |
| Know what to fix next | Queue, Board | Read the red headline |
| See how a trial did | Queue, Flow | Pick it above the table |
| Know why a job is queued | Queue, Queued | Read its second line |
| See what the fleet did today | Queue, Timeline | Read left of the line |
| Make generations easier or harder | Queue, Values | Press minus or plus on Ease now |
| Pause one machine | Queue, Fleet | Pause: its job in hand finishes |
| Take a machine off a job now | Queue, Fleet | Stop now: the job goes back in the queue |
| Put a GPU back on Crucible | Projects | Press Off so it reads On |
| Add a machine | Machines | Type `NAME user@address`, Add, Probe, Join |
| Update a machine | Machines | Press Run beside its update recipe |
| Promote the best candidate now | Results, Candidates | Do it now, twice |
| Stop promotions going out | Results, Candidates | Turn auto off |
| Renew the certificate | Fleet, Orchestrate | Renew. 30 days unless `cert-hours` says otherwise |
| Send a command to several machines | Fleet, Orchestrate | Select, then press a verb |
| Reach a terminal | Watch, Sessions | Click a tile; Enlarge to fill the window |
| Check the planner is running | Settings, Keeper | `planning` and `heartbeat` |
| Keep the training record | Terminal | `python3 tools/fleet-archive.py QUEUE pack bd25`, then `verify` |
| Move a value without the window | Terminal | `python3 tools/fleet-tune.py QUEUE KEY VALUE` |

### E. Mouse and keys

| Gesture | What it does |
| --- | --- |
| **Hover anything** | The inspector: what it is, where it came from, what it means (Section XVIII) |
| Click a chapter or a column key | Go there |
| Click the About bar | Open or close this screen's explanation |
| Click a Flow box | Pin its words below the road |
| Click a matrix on Net | Enlarge it; Escape closes |
| Click a row on Commits | Open that commit on GitHub |
| The turn buttons on Terrain | Turn the surface, once it has ground to draw |
| Wheel, or drag a scroll bar | Move a long list |
| Command-1 to 7 | Go to that chapter |
| Command-I | Turn the inspector off or on |
| Command-Q | Quit: the fleet keeps running, because the keeper is not this window |

A button that can do harm asks twice: its first press changes its words. **Nothing lost if Orrery closes:** the keeper, the jobs and the tmux sessions all go on without it.

## XVII. Every screen

Each section says how to use the screen, marks it, and gives the six answers the screen's own panel gives. Every picture was made by the program's own renderer, `--frame`, from the live run around noon on 1 November.

!html(double/screens.html)

## XVIII. The inspector

Paul asked for "inspector mode to just about every data with hover information". It is on by default. **A thing you must know to switch on is a thing nobody finds.** Move the pointer onto a number, a bar, a cell or a row, and a box follows with what it is, where it came from and what it means. The thing it describes gets a thin outline.

!html(double/inspector.html)

It works at two levels:

- **A written tip, in over forty places:** bars, chart points, heat-map cells, dials, tiles. Each screen asks `ui.tip(rect, lines)`. The lines are in a closure, so a screen with thousands of cells writes out only the one under the pointer.
- **The row, for everything else.** When any text on a line was cut off, hovering it shows that whole line in full. So no truncated title anywhere in the console is lost, even on a screen with no tip of its own.

Sessions' terminals have no tips, because their text is the machine's own. The tip draws last and over everything, and turns back at the window's edge. It costs one rectangle test for each thing drawn. Five tests prove it: only what is under the pointer is ever written out, what is on top wins, off is off, the row holds only the pointer's line, and a long tip stays inside the window at every corner.

| Where | Hover over | It says |
| --- | --- | --- |
| Every screen | Inspector on | How to use it, and how to turn it off |
| Queue, Fleet | The jobs bar | What done, retired and failed mean, with counts |
| Queue, Fleet | A machine | Cores, GPU, every job, its projects |
| Queue, Board | A task or card | State, every machine, timing, what it waits on |
| Queue, Flow | A box | Takes, gives, simulates, adds, with the last day's work |
| Queue, Flow | A read | Machine, seeds, gain, what its z means, its source file |
| Queue, Timeline | A bar | Machine, stage, from when to when; forecast or measured |
| Queue, Timeline | A mark | Which generation, or stopped candidate |
| Queue, Values | A value | Raise it, lower it, its key, its range |
| Results, Candidates | A row | Reads, moves, what its standing means |
| Results, Found | A machine | What found means, and how to spot a bad reader |
| Results, Net | A weight | Its value, row and column, what its sign means |
| Algorhythm, Patch | A stage or dial | What it does; every version |
| Algorhythm, Terrain | Ground or a flag | What height means; a peak's reads |
| Algorhythm, Spectrum | A cell or line | The singular value, and what bright or flat means |
| Algorhythm, Matrices | A cell | Sense group, action, and the limit of the number |
| Algorhythm, Senses | A dot, ring or bar | Channel, direction, sense number, weight |
| Settings, Keeper | A check | Its state in words, its whole text |
| Lab, Machines, Storage, Projects, Orchestrate | A row or tile | What the row leaves out |

## XIX. Treadcore

Everything above exists to change what happens here. These were taken on 1 November in a real window on `treadcore-vm`, a virtual machine on this Mac, from main at `5c599f7`, with the desktop's top bar cropped off. Only the match's end is older, from the playtest record of October.

!html(double/game.html)

Where to see the fleet's work in play: **every bot in these pictures runs `weights.rs`**. Press Space for the coordination screen, then `U` for the sliders: a row for every weight and switch, for your own team. Those are the same numbers this report follows, and you can feel the difference between a raider and a castle-builder by loading `profiles/`. Selecting brains by name per team is [the next report](bot-styles-lab-report.html).

## XX. Threats and what is open

**Pictures are frames, not screen captures.** `--frame` runs the same drawing code as the window from the same documents, without the window's own state. A selection a person made, or a live hover, can look different. **Treadcore's pictures are of main,** so they show the weights before the line reaches it, and they come from a virtual machine drawing in software, which says nothing of the frame rate on real hardware. **The story's numbers are one trial's:** `w4540` is real, and it is not a proof that `bio` helps. **The worked target score leaves out five terms** so the sum can be followed; the code has them all. **The bc2 training figures come from the lab report,** not from running it again.

**Open:** the Terrain's reads; the Runs line's words; the 2,302 retired jobs still say something real about the cost of a generation; the merges proposed in Section IX-B; a warning before the certificate ends; and the game's slots, since built: see [Eight Named Minds](bot-styles-lab-report.html).

## XXI. Reproducing this

```sh
Q=~/code/treadcore/build/queue/grove
sh tools/report/double-shots.sh $Q       # every picture, from the live run
python3 tools/report/whole-line.py $Q    # Part One's figures
python3 tools/report/double.py           # the report's Markdown, from Part One and these
sh tools/report/all.sh                   # the pages
# One frame, one hover:
ORRERY_FRAME_PAGE=1 ORRERY_FRAME_HOVER=690,110 ORRERY_FRAME_OPERATOR=1 target/release/orrery \
  --operator paul --frame out.ppm --frame-view pipeline --frame-state $Q/plan/pipeline.json --frame-size 1400x860
```
