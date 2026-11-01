# A Stale Dial: What We Measured, What Changed, and What We Refused

*Lab Report — IEEE Format · 1 November 2026*

Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery and treadcore.

Companions: [Eight Named Minds](bot-styles-lab-report.html), which found the lead; [the Double Report](double-lab-report.html), which explains the road. In treadcore: [CENSUS.md](https://github.com/treadcore/treadcore/blob/main/documentation/CENSUS.md).

---

## Abstract

A hand-written style read +18 points a seat on one map, and tracing it led to one number: `w_pos_fortify`, promoted at 6.0 under a game that no longer exists. Lowered to 0.4 it reads +3.65 +/- 0.62 over 400 seeds on all eleven maps, z 5.9, and the search could not have reached it. Paul said to do it, and to document what we were measuring. So the rules for accepting it were written before its breakdown was read. **The result is a change made and a change refused.** `w_pos_fortify = 1.5` is on the line: +1.34 +/- 0.37 pooled, with kills less deaths unchanged. **0.4 is held, by our own rules:** its whole gain is the reward for tiles walked, and with those rewards taken out it reads -0.30 +/- 0.41. Meanwhile it kills less, past two errors. Whether that trade is what the game should reward is Paul's call. The work also found and fixed four faults in the run, including one that had silently stranded two jobs.

**Index Terms:** pre-registration, sequential testing, reward design, parameter search, game AI.

---

## I. What was asked

Paul, 1 November, on being told of the dial and that it changes how bots play:

> "yes. please follow recomendations. DO it. Document what you are measuring. lab report about conclusions and changes."

## II. What we are measuring, and the rules set before the results

Treadcore's working rule is "the rule before the run": write down what would confirm a change before reading it. These rules were written at about 14:20 on 1 November, while the held-out reads of `w4970` (`w_pos_fortify = 0.4`) were still running. They are copied here unchanged, and the results follow in Section IV.

### A. The instrument

| Measure | What it is | Where it comes from |
| --- | --- | --- |
| **d** | Trial team's mean score a seat, less the other teams', per seed. A paired reading, so a map's luck mostly cancels | `g-*.log`, one seed played three times |
| **se** | Its standard error over seeds | `pool.sh` |
| **z** | d / se. How many errors from no difference | `pooled.txt` |
| **Held-out read** | The census on seeds from 60,000,000 up, never used to choose a trial | job `h####` |
| **Proof** | The line against main, 800 seeds from 700,000,000 up | job `pv####` |
| **Family** | A set piece with a floor: nine of them, 6,600 runs | `every_family_holds_its_floor` |

A seat's score is a sum, and one thing we want to know is which part moved:

| Part | In the score | Why it matters here |
| --- | --- | --- |
| **Combat** | kills less deaths, a win, direct hits, pillbox damage | Does it fight better? |
| **Ground** | ground held, pillboxes and depots taken, defends | Does it hold more? |
| **Going forward** | tiles advanced (0.25 each), advance stages, tows | **What this dial pays most, and what we must not mistake for skill** |
| **Works** | built, road, bridges, castle time | **What this dial may cost** |

And the behaviour itself: seconds a team spends on each rung of the Auto ladder (fortify, turrets, hunt, expand), and the share of posture picks in each posture. These logs now name each reward, which they did not when this began.

### B. The rules

**R1, to join the line.** `w_pos_fortify = 0.4` joins by the ordinary road or not at all: past its held-out bar for that hour, every family at or above its floor, and all the brain's unit tests passing. **No exception by hand,** however good the earlier read.

**R2, to reach main.** The line must read z 3 past main, 800 unseen seeds, no map two errors under. Main does not move on anything less.

**R3, to count as a real gain beyond the reward for walking.** With tiles advanced and advance stages taken out of the score, 0.4 should still be above Fleet on all maps by more than two errors. **If it is not, the honest conclusion is that this dial mostly collects a reward, and the report must say so,** even with the change standing.

**R4, what would make us take it back.** Any of: a family under its floor; the line reading two errors under main at its proof; or combat clearly worse (kills less deaths past two errors below). Then it goes back by a person's hand or by an anchor at z 3.

**R5, the Connect dial.** `connect_idle = 0` goes by the same road. Before it was measured here on two maps it read inside the noise. It is judged on all eleven at 400 seeds; it need only not lose, since it removes a score for work nobody can do. Below two errors, it stays at 1.

**Not measured, and said now:** whether the game is more fun or looks better. Bots that build less early are a change of character, and only a person playing can judge that.


**One honest note on the timing.** When these rules were written, the 400-seed total of +3.65 was already known; that is why the rules exist. Its breakdown into combat, ground and going forward was not, and no log yet itemised going forward. R3 and R4 were written blind to what they would find.

## III. How it was run

| Read | Trial | Against | Seeds | Purpose |
| --- | --- | --- | --- | --- |
| `r0090` | 0.4 | 6.0 | 400 | The total on every map |
| `r0091` | 1.5 | 6.0 | 400 | A nearer step |
| `h0351`, `h0352` | 0.4 | 6.0 | 400 each, held out | Its own unseen reads, by the road |
| `h0349`, `h0350` | 1.5 | 6.0 | 400 each, held out | The same for 1.5 |
| `r0097` | 0.4 | 6.0 | 220, itemised | R3 and R4 |
| `r0098` | 1.5 | 6.0 | 220, itemised | R3 and R4 |
| `h0354` | 0.4 | 1.5 | 400, held out | 0.4 carried onto the new baseline |
| `r0096` | `connect_idle` 0 | 1 | 400 | R5 |

Each is the census of Section II-A, on all eleven maps, on the fleet's machines. The itemised reads are the first with each reward named in the log, added for this report.

## IV. Results

### A. The dial's effect

!html(fortify/dose.html)

| | 1.5 against 6.0 | 0.4 against 6.0 | 0.4 against 1.5 |
| --- | --- | --- | --- |
| The score, by census | **+1.34 +/- 0.37** (pooled, 620 seeds) | **+3.58 +/- 0.52** (pooled, 620 seeds) | +3.05 +/- 0.69 |
| Held-out reads | +1.06 +/- 0.50 and +0.22 +/- 0.48 | +3.80 +/- 0.67 and +3.64 +/- 0.62 | +3.05 +/- 0.69 |
| **Without going forward** | **+0.36 +/- 0.31** | **-0.30 +/- 0.41** | +0.25 +/- 0.30 |
| Kills less deaths, a seat | -0.05 +/- 0.05 (pooled) | **-0.17 +/- 0.05** (pooled) | +0.03 +/- 0.07 |
| Built, team | -3.4 | -7.8 | -4.5 |
| Road, team | -1.5 | -2.2 | -0.8 |
| Ground held | +0.10 | +0.14 | +0.11 |
| Tiles advanced, team | +9 | +58 | +43 |

Fleet teams built about 15 on `naval` and 21 on `europe`, so 0.4 gives up something like half their works. Note 1.5's second held-out read: it is a modest change, and its gain is the less certain of the two.

### B. Where 0.4's points came from

Multiply each measured change by what the score pays for it, per seat:

!html(fortify/waterfall.html)

**Tiles advanced alone pay +2.89, and advance stages +0.66: together +3.55 of a +3.42 gain.** Everything else nets to about nothing. Teams with 0.4 walk further, take a few more pillboxes, hold a little more ground, kill less and build far less.

### C. By map

!html(fortify/maps.html)

`europe` still shows most, and without going forward it remains +4.6: on that one map a real part of the gain survives. It is 20 seeds of noise on each bar, so this is a lead, not a result.

### D. The behaviour

| Share of a trial team's time on Auto's rungs | 1.5 | 0.4 |
| --- | --- | --- |
| Expand | 48% | **64%** |
| Fortify | 24% | **11%** |
| Turrets | 6% | 3% |
| Defend the base | 18% | 16% |

From the itemised reads. So 0.4 does what it says: less castle, more going out.

## V. Conclusions, rule by rule

| Rule | `w_pos_fortify` 1.5 | `w_pos_fortify` 0.4 |
| --- | --- | --- |
| R1, held-out, families, tests | **Passed:** the road carried it as `r0092` | Reads and families passed. Stopped by hand before the tests |
| R2, line z 3 past main | Pending: the next proof reads it | Not reached |
| R3, a gain beyond walking | **Not shown:** +0.36 +/- 0.31, inside the noise | **Failed:** -0.30 +/- 0.41 |
| R4, combat clearly worse | **No:** -0.05 +/- 0.05 | **Yes:** -0.17 +/- 0.05, z -3.1 |

**1.5 stands,** with a caveat: most of its gain is also rewards. **0.4 is held.** R4 says take it back and R3 says it mostly collects a reward, so the rule written first decides, however good +3.65 looked.

**The Connect dial stays at 1.** `connect_idle = 0` read +0.32 +/- 0.22: it did not lose, but it did not pass the road's first bar and it was not adopted. Kills less deaths read -0.07 +/- 0.03. So the road left it where it was. Teams still do not fill pillbox slots; this dial only changes what the posture thinks of that.

**So was it a fault?** Partly. The number was set for an older game, and Fleet does sit on its castle longer than today's game pays for. But **most of the +18 we chased was the score paying for walking, on the map with the most to walk.** The search was not hiding a much better brain. It was hiding a different trade.

### The question this leaves for Paul

You asked for this reward: "reward massivly the forward advancmaent". So by the score you chose, 0.4 is better by more than three points a seat, past any bar we have. By kills and works it is worse. **Our rules refused it, and they are ours to change:** they say what we would accept as evidence, and only you can say what the game should reward. Three choices, each one number:

1. **Stay at 1.5.** The safe choice, and where the run now stands.
2. **Choose 0.4 anyway,** because forward play is what you want. Remove the line from `QUEUE/hold.json`, and the road does the rest.
3. **Reprice the walk.** If 0.25 a tile is too generous now that the rest of the game has moved, change it, bump `GAME_VERSION`, and read everything again. Then this dial will find its own level.

A playtest answers this better than any census:

```sh
printf 'w_pos_fortify = 0.4\n' > /tmp/fort.weights
treadcore --solo --autopilot --weights /tmp/fort.weights
```

## VI. What changed

**In the run, live now:**

| Change | Where | Why |
| --- | --- | --- |
| `w_pos_fortify` 6.0 to **1.5**, as generation 7 (`r0092`) | the line | Passed the road and R4 |
| `w_pos_fortify = 0.4` **held** | `QUEUE/hold.json` | Failed R3 and R4; its reads go on, it does not promote or carry |

**In orrery's planner:**

| Fault found | Fix |
| --- | --- |
| **A by-hand census could be stranded.** A generation retired the build it waited on, and it sat high in the queue forever, with health saying "every queued job has a machine". `r0093` and `r0094` lost 20 minutes this way | A build a queued job waits on is kept |
| **A named style could promote itself.** A census of `bot_style = 1` that passed was adopted, and could have replaced every bot's brain. Two were adopted; neither reached a candidate | Named styles are never adopted, carried or promoted |
| **An anchor could undo generations on noise** (found the same day) | An anchor must clear z 3 |
| **By-hand censuses on macmini read one map** (the same) | The paste fix now covers them |
| A read taken to measure was adopted as if to promote | `adopt=no` on a census |

**In treadcore (`fcaadc3`):**

- The census log names every reward, so the next +18 explains itself.
- The dial `connect_idle`, at 1 as built: no default moved.

## VII. What this says about the search

**It cannot see far.** The fit's reach is one doubling, two when stalled. 0.4 was nearly four away, and it took hand-written styles from another week to point at it. After a game change, each dial should be read at a quarter and four times today. **Nor does it look past the total:** a gain made of one reward reads the same as a gain made of everything, and z 5.9 was reassuring right up until it was broken down. The new log makes this possible, and a candidate's report could carry it automatically.

## VIII. Threats and what is open

**Pooled reads mix builds,** since the line moved between them: `r0090` and `h0351` on one commit, `r0097` and `r0098` on another, each with the base set to 6.0 by hand in the later ones. **The behaviour table has no column for 6.0,** since the census logs a trial team's rungs and not the baseline's. **R3 rests on 220 seeds,** so its error is larger than the 400-seed reads'. **Per-map bars are 20 seeds each.** **R2 is not yet read:** nothing has reached main. The last proof, before these generations, read +0.54 +/- 0.35. **1.5 landed before its R3 and R4 reads were back,** because the road moved first; had it failed R4, it would have been taken back by hand.

**Open:**

- Teams never fill pillbox slots: a tank must own the pillbox it carries, and the commander holding the plan rarely does. The real mend gives the job to the owner.
- The hold is a file with no button: Queue, Values could show it.
- The fit's memory, batched generations and looking far: the proposals of the abandoned-work review, not yet built.

## IX. Reproducing this

```sh
Q=~/code/treadcore/build/queue/grove
python3 tools/fleet-queue.py $Q new census "trial=w_pos_fortify = 0.4" "base=w_pos_fortify = 6.0" name=x seeds=220 adopt=no
python3 tools/report/fortify.py $Q r0097-00         # what its gain is made of
cat $Q/hold.json                                    # what a person holds
```
