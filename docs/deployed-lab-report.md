# The First Morning: Watching the Design of 13 November Go Live, the Line That Came Back, and a Watch That Reads Each Mechanism

*Paul Richeson · Lab Report — IEEE Format · 13 November 2026*

Paul Richeson, treadcore.org; Claude Code (Claude Fable 5.2) as the pair. Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery and treadcore.

Companions: orrery `tools/deploy-watch.py` (the watch), `tools/plans/deployed.json` (what the queue holds), `tools/plans/treadcore.py` (`promote_run`, `orphan`, the verb `orphan`), `tools/plans/line.json`, `tools/report/deployed.py` (the figures, diagrams and numbers here). The data: `docs/deployed/data.json`, read at 09:53 on 13 November. The day's earlier reports: *Always Forward* [1], *Every Block Checked* [2], *Old Decisions, Reopened* [3]. orrery commits 79aea74 and 7f1607b; treadcore 2945c7e.

## Abstract

Paul, at about 09:40 on 13 November: "Let's commit to the new design decisions. Let's start the new code, with all your new implementations. All on main. Commit. Push. Write a report about monitoring this new code deployment." **The design is the code's own now.** What had run through the morning as values moved in the queue is the planner's defaults (orrery 7f1607b), treadcore's main carries the split of `w_smooth` and the floor on `w_pos_defend` (2945c7e), and what the queue itself holds is kept in the repository as `tools/plans/deployed.json`. Fourteen commits reached the two mains between 07:05 and 09:48, and the keeper took the new code once, at 07:39, by handing its jobs over. **The deployment had one fault, found by looking and not by a check.** At 09:26 the removal rule took its first line off: ten generations, on −0.02 ± 0.10 over main in 10,400 seeds. A minute later all ten were back. The run loop knew four ends of a promotion and "orphaned" was not one of them, so it took each for work not yet done and put it on the line again, one every seven seconds. The check had proved a block coming off; it had not asked what the next pass would do. It was fixed in a quarter of an hour (79aea74), the line was taken off again at 09:33 and has stayed off, and it cost the fleet two builds of main and a quarter of an hour of planner passes six minutes apart. **So this report's main product is a watch.** `tools/deploy-watch.py` reads the queue's own records and says, a line a mechanism, whether each part of the design has been *seen* doing what it was built for: `ok`, `LOOK` (not yet seen, or a person's to judge) or `BAD` (doing what it must not). At 09:53 it read ten `ok` and two `LOOK`: the yardstick's first day was 13 reads of 15 back, and no trial of a part of `w_smooth` had yet been asked. In the first full hour of the design the CPU machines finished **11,147 seeds against 7,635 an hour before it**. Four things have not happened yet and are what to watch for: a trade let through, a part of `w_smooth` read, a day on the yardstick, and a generation that settles and is proved.

*Index Terms*: deployment monitoring, canary checks, post-incident review, state machines, unknown states, reversible configuration, observability.

## I. What was deployed

**Everything is on main, in both repositories.**

| When | Repository | Commit | What |
|---|---|---|---|
| 07:05 | orrery | c76ef92 | the planner's state files written through a temp file of each process's own |
| 07:54 | orrery | 971de6b | a second lane; the line settles; one dial at a time |
| 08:12 | treadcore | 3013570 | `w_smooth` split into four choices (on main at 09:27) |
| 08:13 | orrery | 5a730fc | a block that fails comes off; a refusal kept; the yardstick |
| 08:41 | treadcore | 2945c7e | `w_pos_defend` floored at 0.75 (on main at 09:27) |
| 08:46 | orrery | e7300f4 | the Yardstick tab; main built again after a line comes off |
| 08:56 | orrery | 7ab25bb | a trade weighed by its gain; anchors can be off |
| 08:58 | orrery | 509c91a | the held-out read is read on |
| 09:45 | orrery | 79aea74 | orphaned is an end (the fault of section IV) |
| 09:48 | orrery | 7f1607b | the design as the code's defaults; `deployed.json` |

*Table I. The commits that carry the design. Four more of the fourteen are the day's three reports and a line of wording.*

**The defaults now say what the morning's trials said** [3]: the held-out bar at z 2.5, up to six held-out reads, half of new trials one dial at a time, a trade weighed by its gain, and the anchors, the rule of a dial moved again, the half hour between generations, the clone rounds and the temperament rounds off. The Values page shows nothing as moved. **What only the queue holds** is in `tools/plans/deployed.json`, because the queue's files are in no repository: the rotation off, a first read of 150 seeds, saskatchewan's second lane, the iMac on its own jobs only, boburner's island on the bench.

## II. How a change reaches the running fleet

!html(deployed/dia-deploy.html)

*Diagram 1. Four roads to the fleet. The keeper restarts itself when its own file changes; the planner is a new process each pass; a value is read each pass; a commit to the game is built by every machine before anything runs on it.*

**Three of the four roads have no restart, and that is what made a morning of fourteen commits possible.** The keeper's file changed once: at 07:39 it handed its running jobs over to itself and went on, and none ran twice. Every other change was the planner's file or a value, live at the next pass, about a minute on. The fourth road is the slow one. A commit to treadcore's source makes every machine build, and retires what was queued on the commit before: about a minute a machine, and the search stops while it happens.

**That is also the risk.** A change to the planner is live the moment it is saved, checks run or not, and it acts on real state. The fault of section IV was live for one pass.

## III. The watch

!html(deployed/dia-watch.html)

*Diagram 3. What the watch reads and what its three levels mean.*

**A check proves a mechanism can work; the watch says it has been seen working.** `python3 tools/deploy-watch.py QUEUE` prints one line for each mechanism of the design. It reads the planner's state, the events, the run states, the flags and the newest trials, and it moves nothing.

| Check | What it reads | The reading at 09:53 |
|---|---|---|
| planner | passes in the last half hour; any failed | ok: 14 passes, a median 14 s, the longest wait 390 s |
| jobs | jobs failed since 07:39 | ok: none |
| orphans | every orphaned promotion still off the line and still marked | ok: 2 lines came off, 10 promotions orphaned, none back |
| line | the line's age and its proof's seeds | ok: no line; the fleet builds main |
| first read | the seeds of the newest trials against `plan.json` | ok: 150 |
| one dial | the round and what is left of it | ok: round 2, 245 of 256 still to ask |
| held-out | trials read on past their first held-out read | ok: three (w19840, w19913, w19935) |
| trade | trades let through and refused; refusals kept | ok: none either way yet |
| yardstick | the newest day's rows, or the round's reads back | LOOK: no day yet, 13 of 15 reads back |
| set aside | any rotation run, clone round or anchor read since the switches | ok: none |
| `w_smooth`'s parts | trials of each of the four choices | LOOK: none asked yet |
| pace | census jobs finished in the last hour | ok: 70 |

*Table II. The twelve checks. The first three are the ones that can read `BAD`; a trade let through reads `LOOK` on purpose, because it is a person's to judge.*

**The thresholds are from how the system works, not from taste.** A planner pass is asked when the queue runs low, when a chain's step comes back, when a lane starves, and at the latest every five minutes. With reads of 150 and 400 seeds the queue drains slowly, so four or five minutes between passes is the keeper not needing one. The watch says `LOOK` past seven minutes, which is the keeper held.

## IV. The line that came back

!html(deployed/dia-incident.html)

*Diagram 2. The fault, the fix, and what it cost.*

| When | What happened |
|---|---|
| 09:26:31 | The proof stands at −0.02 ± 0.10 over main in 10,400 seeds. `orphan()` marks ten promotions orphaned, sets the line's branch to main and drops the line. As designed. |
| 09:27 | The split of `w_smooth` is pushed to treadcore's main, as planned for the moment the line was off. |
| 09:27:43 to 09:28:45 | The planner's next pass prepares each of the ten promotions again and puts it on the line: ten resets of the branch, seven seconds apart. The line stands again, on the new main. |
| 09:29 | Seen, by reading the planner's state for another reason: a line where there should be none. |
| 09:33 | With the fix in place, the verb `orphan` takes the line off again on the same read. |
| 09:36 | Two passes later the line is still off and the ten still read orphaned. |
| 09:45 | The fix is pushed (79aea74). |

*Table III. The incident, by the keeper's clock and git's.*

**The cause was a state the rest of the code did not know.** A promotion run ends in one of four states: prepared, approved, self-modified, rejected. `promote_run()` returns at once for those and otherwise does the promotion's next step. `orphan()` wrote a fifth, "orphaned", and nothing else had heard of it. To the run loop, an orphaned promotion was a promotion not yet made.

**Why the check did not catch it.** `board-check` proved, against a real repository, that a line comes off: the runs marked, the branch at main, main untouched, the fleet on main. It did not run the next pass. The fault was not in the mechanism but in what met it afterwards.

**The fix.** "Orphaned" ends a run, in `promote_run()` and in the run loop, with a claim in `board-check` that an orphaned run is not prepared again. A verb, `treadcore.py QUEUE orphan`, takes a line off again on the read that took it off before, and only when the line carries exactly the same promotions.

**What it cost.** The fleet built the line on the new main and then main itself: two builds a machine. For about a quarter of an hour the planner's passes were six minutes apart and two CPU lanes stood idle waiting for builds. No job failed, nothing reached treadcore's main that should not have, and no read was lost that the change of defaults would not have retired anyway.

**What changes in practice.** Two habits, both cheap:

- **A new state is searched for.** Before a status, a kind or a flag is added, every place that tests the old ones is read. Here that was two tuples.
- **A check runs the pass after.** A mechanism that changes the planner's state is checked with the next pass run on that state, not only for what it leaves behind.

And one instrument: the watch's `orphans` line is this fault's own check, and it reads `BAD` within a pass.

## V. The first morning, in the planner's passes

!html(deployed/fig-passes.html)

*Fig. 1. Every planner pass from 06:00: the wait since the pass before. The larger marks waited more than three minutes. Hover a mark for the pass's own length and what it added.*

**Two things show.** From about 08:20 the passes spread out, to three to five minutes: that is the design, not a fault. The proof was reading six jobs of 400 seeds at a time, the yardstick fifteen, and from 08:50 first reads were 150 seeds, so the queue drained slowly and the keeper asked less often. And from 09:27 to 09:42 they are six minutes apart with the keeper's beat held by a pass: that is the incident, the planner's pass itself taking 85 seconds as it rebuilt what a change of defaults makes it rebuild, twice.

## VI. The first morning, in seeds

!html(deployed/fig-seeds.html)

*Fig. 2. Census seeds finished on the CPU machines each hour of 13 November. The lighter bar is the first full hour of the new design.*

**11,147 seeds in the hour from 08:00, against a mean of 7,635 in the eight hours before: 46% more.** One hour is one hour. It holds saskatchewan's second lane and the iMac no longer taking reads, and it is before the incident. The hour from 09:00 holds the two rebuilds and will read lower. The number to trust is a day's, and the watch's `pace` line is where it will be read.

## VII. Seen, and not faults

- **The ratchet counted a generation that was not one.** With the ten orphaned, the newest promotion became r0209, of 6 November, and the ratchet took it for new: health read "23 min since the last, generation 38" and the bar went from z 2.50 to 2.55. No promotion was made. It is harmless at this size and wrong in its words.
- **Health says "widened (bound 4, half of each generation wide trials)".** A wide trial has been one a generation since 31 October. The words are stale.
- **Two of the yardstick's fifteen reads** were asked on the line's build, which was retired when the line came off. The round ends when they are stopped or done, and its first rows will be of the line as it stood.
- **`w_smooth = 0.525` is being read again** (w20026, "carried to 2945c7e"), as section XI of *Old Decisions, Reopened* [3] said it would be. If it passes it will show on the watch's `trade` line as `LOOK`.

## VIII. Not yet seen

| Mechanism | What will show it | Where |
|---|---|---|
| A trade let through by its gain | a flag "goes on by the trade rule" | the watch, `trade` |
| A part of `w_smooth` read alone | a trial titled with `smooth_turret`, `_stance`, `_supply` or `_rung` | the watch, `w_smooth's parts` |
| A day on the yardstick | rows in `plan/rating.json` | the watch; Results, Generations, Yardstick |
| A generation that settles and is proved | "the line settles first", then "proved past main" | the watch, `line`; Fig. 2 of [1] |
| A held-out read passing on its third or fourth read | a candidate with more than two held-out reads | the watch, `held-out` |
| A round of one-dial trials finished | round 3 begun | the watch, `one dial` |

*Table IV. What the design has not yet done on the live fleet. Each was proved in a check.*

## IX. How to keep watching

1. **Each morning, and after any commit to the planner:** `python3 tools/deploy-watch.py ~/code/treadcore/build/queue/grove`. Twelve lines. A `BAD` is acted on at once; a `LOOK` is read.
2. **After a change that alters the planner's state:** read the state two passes later, not only the check's output.
3. **To turn any part back:** Table I of *Old Decisions, Reopened* [3] gives each value and its old number. Since 7f1607b the old numbers are no longer the defaults, so "default" means the new design: to go back, set the old number.
4. **To see what the queue was holding on the day:** `tools/plans/deployed.json`.
5. **After three days:** read the reads on as a share of the hours (41% before [3]), the finds a day, and the yardstick's rows, and decide the stages.

## X. What is open

- **The watch is run by hand.** It is not yet a line of health or a page of the app, and it does not raise a flag. A `BAD` is seen only by whoever runs it.
- **The ratchet's words and the widened search's words** (section VII) are not mended.
- **The second lane's gain, the first read at 150 and the held-out read read on** each want days, not an hour.
- **A person has not yet said** whether `w_smooth = 0.525` may reach main unattended [3].

## XI. How to make it again

`python3 tools/report/deployed.py ~/code/treadcore/build/queue/grove docs/deployed` runs the watch, reads the day's passes, seeds and commits, and writes `docs/deployed/data.json`, the two figures and the three diagrams; `--redraw docs/deployed` draws them again.

## References

[1] orrery, *Always Forward: Why the Line Has Not Gained Since 6 November, the Gain a Rule Held Back, and a Harness That Mints Only Real Blocks*, lab report, 13 November 2026.

[2] orrery, *Every Block Checked: A Line That Settles, a Block That Comes Off, One Dial at a Time, a Cliff Explained, `w_smooth` Split, and a Fixed Yardstick*, lab report, 13 November 2026.

[3] orrery, *Old Decisions, Reopened: Eight Rules Set Aside or Changed as Trial Runs, What the Review Found, and the Next Round*, lab report, 13 November 2026.
