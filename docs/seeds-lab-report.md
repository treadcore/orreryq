# Where the Seeds Went: A Proof Held by One Map, Trials That Read as Noise, a First Bar at Zero, and a Net Shipped on One Read

*Paul Richeson · Lab Report — IEEE Format · 13 November 2026*

Paul Richeson, treadcore.org; Claude Code (Claude Fable 5.2) as the pair. Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery and treadcore.

Companions: orrery `tools/plans/treadcore.py` (`line_proof`'s map flag, `_pool`'s maps, `KEEP_EASE`, `WIDE`, `BRIDGE_CONFIRM`, `bridge_jobs`, `reread_older`), `tools/bridge.py` (`WORLD_SHAPES`, `--dry`), `tools/report/seeds.py` (the figures and numbers here). The data: `docs/seeds/data.json`, read at 13:01 on 13 November from the live queue.

## Abstract

Paul, at midday on 13 November, after five reports in a morning [1]–[5]: "another analysis. additional improvements." This one reads what the fleet's seeds bought, trial by trial, and finds four things. **First, the day's one real gain is proved and is not on main.** `w_smooth = 0.525` read +3.91 ± 0.11 a seat over main on 9,600 seeds, 34 errors clear, and wins on twelve maps of thirteen; on the thirteenth, flame-war-modified, it loses 1.96 ± 0.40, and a guard written for 400-seed reads holds the whole line off main for that, and said nothing. It is now a flag, and the decision is Paul's. **Second, the fit's sample trials and the wide trials read exactly as trials that do nothing read**: 2,667 of them since w17000, 326,324 seeds, a mean first read of z 0.00 and −0.07 and a spread of 1.02 and 1.00, where no effect at all gives 0 and 1. **Third, the first read-on bar stood at z 0**, so half of all such trials read on; the 267 that began between 0 and 0.25 cost 21,108 seeds and 16 held-out reads and made no candidate. **Fourth, a GPU net shipped on one read**: M0030, +2.28 ± 0.98 on 192 seeds, its two successors reading −0.68 and −0.93; and it shipped at 11:39 today by a mistake of the pair's, a dry run that was not dry, which moved main and cost the proof 2,400 seeds. Six changes follow, all live: the map flag; the first bar at 0.25; no wide trials; a second read before any net ships, and a ship that waits for the line; a dry run that is one; and no re-read of a candidate that asks for today's own values.

## I. The proof, and the one map

!html(seeds/fig-maps.html)

*Fig. 1. The line `394c4ac` (main with `w_smooth = 0.525`) against main, 9,600 seeds, twelve reads of the proof pooled, a map at a time. Green is the line ahead, orange behind; the whisker is two errors either side. Every map together: +3.91 ± 0.11.*

**The line is proved by 34 errors and does not land, because of one row of this figure.** The proof lands a line when its lead is three errors past main and no map reads two errors under (`line_proof`: `-d / se >= HELD_Z and not p["above"]`). The second clause was written when a proof was 400 or 800 seeds: thirteen maps at that size put one two errors under by chance about one time in four, and the clause kept a lucky read from landing on the strength of the rest. At 9,600 seeds a map has about 740 seeds of its own, and flame-war-modified at −1.96 ± 0.40 is 4.9 errors under: not chance, a real loss on that map.

So the rule did what it says, and at the settle rule's seeds it means something it did not mean before: **every map must not lose**, which is stricter than anything Paul has asked for. He let the trade through ("Let it through") and passed a small drop on a floor ("Pass on a small drop"); neither sentence was about a map, so this one is not decided by them. What was wrong beyond question is that it was silent. The line stood as "1 generation on the line, proof has read 9,600 seeds", the watch said ok, the settle rule let go of it (it is decided: far over the gain), and nothing would ever have landed it or taken it off.

**Now it is said.** A line proved on every map together and held by a map raises a flag that names the maps and their numbers and how to send it as it is (`fleet-queue.py QUEUE resolve`), and stays up until acknowledged or landed. The numbers Paul decides on: +3.91 a seat on every map together; +10.17 on fortressisles2, +9.03 on fidos-airstrip, +8.11 on proving; +1.02 ± 0.45 on europe, the weakest win; −1.96 ± 0.40 on flame-war-modified, the one loss. The pair's recommendation is to send it: one map in thirteen gives up two points where the other twelve take a mean of nearly four and a half, and the map is now named, so the search can be asked what `w_smooth` does there.

## II. What the sample trials read

!html(seeds/fig-noise.html)

*Fig. 2. The first read of each of the 2,667 sample and wide trials since w17000, in its own errors. The dashed steps are what the same number of trials with no effect at all would give.*

**The bars sit on the dashed line.** A trial's first read, divided by its error, is a draw from a bell of spread 1 about its true effect. If the trials' true effects were worth finding, the bell would be wider than 1 and there would be more reads past +2 than chance gives.

| What proposed it | Trials | Seeds | Mean first z | Spread | Past +2 (chance) | Under −2 | Reached held-out | Candidates |
|---|---|---|---|---|---|---|---|---|
| the fit's samples, three or four dials | 1,390 | 176,770 | +0.00 | 1.02 | 36 (32) | 36 | 68 | 7 |
| wide trials, a stalled search's | 1,277 | 149,554 | −0.07 | 1.00 | 17 (29) | 42 | 59 | 4 |
| a switch or a choice flipped (A/B) | 238 | 24,587 | −0.66 | 1.61 | 5 (5) | 41 | 16 | 3 |
| the fit's best | 43 | 8,831 | +0.26 | 1.06 | 0 (1) | 0 | 2 | 0 |
| one dial alone, far (since this morning) | 23 | 4,374 | +0.02 | 0.98 | 0 (1) | 1 | 0 | 0 |

**The samples: mean +0.004 with an error of 0.027, spread 1.024 with an error of 0.019.** A spread of 1.024 leaves room for true effects of at most about 0.3 of a first read's error, a quarter of a point a seat, which agrees with the 0.20 to 0.30 that *Always Forward* [1] found by another road. Effects that size are under the gain a generation must show (0.25) and far under what a 55-seed read can see. The wide trials are worse than nothing: fewer past +2 than chance and more under −2, since a wide move mostly breaks something.

**The A/B trials are the one kind whose spread is not 1.** At 1.61 the true effects spread about 1.3 errors, well over a point a seat, and mostly downward: turning off a thing the brain does costs. That is where this brain's sensitivity is, in what it does and not in a dial's third digit, and it is where today's gain came from: `w_smooth` is four behaviours and a blend, taken from off to half on. The eleven candidates the samples and wide trials made are what 127 trials reaching the held-out reads leave when the bars are eased; the proof of 6 to 13 November read ten such generations as −0.01 ± 0.06 together [1].

**What this changes.** This morning's one-dial rounds already took half of each generation's new trials from the fit (`FAR_SHARE` 0.5), and the A/B trials a third. This report takes the wide trials to none (`WIDE` 0; one a generation before, when stalled). The fit's samples keep what is left, about a sixth, and are the next thing to question after three days of the one-dial rounds: the 23 far trials so far are too few to say anything.

## III. The first bar stood at zero

!html(seeds/fig-first.html)

*Fig. 3. The 2,960 trials first read at 55 seeds, by what the first read said: the seeds each group read after it, and the candidates (passed both held-out reads) that came of it. Orange: no candidate.*

**With the ease at 0.5 the first keep bar was z 0.5 less 0.5.** A trial read on if its first read was above zero, which half of all trials that do nothing are; a staged read saves seeds only by what its early bars turn away [6]. The 267 that began between 0 and 0.25: 265 read on, 21,108 seeds after the first read, 16 held-out reads, no candidate. The fifteen candidates began at 0.34, 0.48, 0.59 and up.

**The bar is now z 0.25 at the first stage** and a quarter higher at each later one (`KEEP_EASE` 0.25, where 0.5 was). On these 2,960 trials that would have saved one seed in nine of those read after the first read, and a tenth of the held-out reads, and lost no candidate. At today's 150-seed first read the same z is a smaller effect, so a real one clears the bar more easily than it did.

## IV. One read credits nothing

**M0030 shipped on one read.** The bridge reads each GPU milestone in the game against the shipped Gladiator on 192 seeds and credits it past two errors. Twenty-two reads have been made. One read in forty-four is past +2 by chance alone, so that some read of the twenty-two would be is four chances in ten.

| Milestone | Island, generation | Against M0015, a seat | Seeds |
|---|---|---|---|
| M0030 | calber, 290,500 | +2.28 ± 0.98 | 192 |
| M0031 | calber, 291,400 | −0.68 ± 1.03 | 192 |
| M0032 | calber, 291,900 | −0.93 ± 1.03 | 192 |

Nine hundred generations on, the same island's nets read under the net M0030 was credited over. That does not say M0030 is no better; it says one read cannot.

**Why it had not shipped on 10 November, and how it shipped today.** `bridge.py` knew a world champion by one size, 20,944 bytes; since the maze the islands have made nets of 23,064 (nine senses of the way and two outputs more), which the game reads. The ship was refused, and the refusal went to a log. Reading that log at 11:37 today, the pair fixed the size and typed `ship M0030 --dry` to test it. The dry run existed in `ship_file` and was wired to no verb; the extra word was passed over; the tests ran, the commit was made and pushed (treadcore `1f23ff0`). Nobody asked for it. Main moved under the settling line, the line was replayed to `394c4ac`, and the proof began again from nothing with 2,400 seeds read.

**What follows, all built.** A first read past two errors asks for a second, of the same pair on 576 fresh seeds (`BRIDGE_CONFIRM`), and the second alone decides: it was not picked for being high, so its number is fair [7]. A credited net ships only when no line is settling. A net that shipped on one read before this rule is checked the same way, the old Gladiator against it: M0015 against M0030 is bridge 23, queued at 12:50 on boburner, and its flag will say confirmed, or not confirmed and how to go back. A ship that does not land is flagged. `--dry` is read by `ship` and `ship-clone`, and a word a verb does not know stops it.

## V. What was built

| Rule | Was | Now | To undo |
|---|---|---|---|
| A proved line held by a map | silent | a flag naming the maps, and `resolve` | nothing to undo |
| First read-on bar | z 0.0 | z 0.25 | `KEEP_EASE = 0.5` |
| Wide trials when stalled | 1 a generation | none | `WIDE = 1` |
| A GPU net's credit | one read, 192 seeds | a second read, 576 fresh seeds, decides | `BRIDGE_CONFIRM` and the `kind` branches of `bridge_jobs` |
| A ship | at once | when the line has settled | the `to_ship` block |
| A ship that fails | a line in a log | a flag | nothing to undo |
| `bridge.py ship --dry` | shipped | runs the tests, commits nothing | nothing to undo |
| A world champion's size | 20,944 bytes | 20,944 or 23,064 | `WORLD_SHAPES` |
| An old candidate equal to today's defaults | read again against itself | skipped | `is_defaults` in `reread_older` |

The last was seen in passing: w12077 and w15613 are `w_smooth = 0.525`, as the generation just promoted was, and both were being read again on the line that had taken it, the defaults against themselves.

## VI. What is open

- **Paul's, now:** whether `w_smooth = 0.525` goes to main with flame-war-modified two points under. And whether M0030 stays, once bridge 23 has read.
- **The map guard itself.** At a proof's seeds "two errors under" finds any real loss however small. A rule in points (a map may give up so much, as a floor now may) would say what is meant; it is not built, because what is meant is Paul's to say.
- **The fit's samples.** A sixth of new trials still, and noise by this report. To be read again beside the one-dial rounds after three days.
- **The game's verdicts on the ladder** were all read against M0015; the shipped net is now M0030.
- **What `w_smooth` does on flame-war-modified**, and the blend, which the four parts do not cover [5].

## VII. How to make it again

`python3 tools/report/seeds.py QUEUE docs/seeds` reads the queue and writes `data.json` and the three figures; `--redraw docs/seeds` draws from the data. `tools/report/all.sh` builds the page.

## References

[1] orrery, *Always Forward*, lab report, 13 November 2026.

[2] orrery, *Every Block Checked*, lab report, 13 November 2026.

[3] orrery, *Old Decisions, Reopened*, lab report, 13 November 2026.

[4] orrery, *The First Morning*, lab report, 13 November 2026.

[5] orrery, *The Loop Closed*, lab report, 13 November 2026.

[6] A. Wald, "Sequential tests of statistical hypotheses," *Annals of Mathematical Statistics*, vol. 16, no. 2, pp. 117–186, 1945.

[7] J. P. A. Ioannidis, "Why most discovered true associations are inflated," *Epidemiology*, vol. 19, no. 5, pp. 640–648, 2008.
