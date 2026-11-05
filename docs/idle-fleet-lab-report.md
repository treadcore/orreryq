# Fifty-Four Idle Minutes: the Line Replayed Twice, Three Guards, and Restarting Orrery Without Losing Work

*Paul Richeson · Lab Report — IEEE Format · 4 November 2026*

Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery.

Companions: `tools/plans/treadcore.py` (the planner: `Plan.writer`, `heal_line`, `retry_failed_builds`, the pooled proof); `tools/plans/board-check.py`; `tools/fleet-queue.py` (the keeper); `tools/plans/treadcore-view.py` (the console's document); orrery commits `228c30c` and `b19b5c2`; treadcore commit `aebeb1d` (LR 147).

## Abstract

From 20:10 to 21:04 on 4 November all eight of the fleet's CPU machines stood idle while the queue held work. A commit to treadcore's main at 20:04 meant the fleet's *line*, the promotions it carries on top of main, had to be rebuilt on the new main. The keeper's planner rebuilt it and saved the result as commit `f04f157`. Forty seconds later a report that only reads, `analysis.py`, which the console starts every ten minutes, rebuilt it again as `d821e7b`, moved the line's branch and its bundle to its own copy, and saved nothing. Every machine was then told to build `f04f157` from a bundle that did not hold it; all eight builds failed within a second, nothing ever asked for them again, and with no machine built the planner had no CPU work to give. Three faults lined up: a reader with a writer's side effect, two records of one fact that could disagree, and a failure that was never retried. A fourth let it last: the console said "LOOK" and nobody was told. Three guards now stand in the way (`b19b5c2`): only a planner that saves its state may move the line; on every pass the saved state sets the branch and bundle back if they disagree; and a failed build is asked again once. They went live at 21:00; the builds passed by 21:03 and every lane ran by 21:04. The report then answers Paul's second question, whether Orrery can be restarted without trouble. **The application can: it starts nothing the fleet depends on, and today's two launches cost nothing.** What it does carry is housekeeping that runs only while its window is open. The keeper, which most of the name "Orrery" stands for in practice, is another matter: since 29 October its restarts have sent 132 running jobs back to start again, 7.7 machine-hours of work thrown away. Four changes, not built when it was written, would let both restart without losing work; three were built by the next morning (sections X and XI).

## I. The question

Paul's words, as the evening went:

> yeah. how it going. i see it just transitioned i think. tell me.

> write a lab report about the situation we wont let happen again. Is there an issue with restarting the application Orrery. Is there a way to allow restarting Orrery without issues?

The "transition" Paul saw was the Pipeline's lanes: eight bars stopped, three kept moving (the GPU islands).

## II. What the reader needs: main, the line, the bundle, the builds

**Main** is treadcore's `main` branch on GitHub: the game as everyone gets it. When the fleet finds a better set of the brain's numbers, it *promotes* it. A promotion that has passed its tests, families and gauntlet is first put on the **line**, a short branch of the fleet's own (`orrery/accepted`) that sits on top of main and that every machine builds and plays. The line goes to main only when a *proof* (800 games of main's numbers against the line's) shows it is better by three standard errors.

> **Side note — why a line at all.** A promotion that waits for a proof before the fleet can build on it would hold the search still for an hour each time. The line lets the fleet work from the newest promotion at once, while the proof decides, unhurried, whether it reaches everyone.

When main moves under the line (someone commits to treadcore), the line's own commits are **replayed**: copied, in order, on top of the new main. They get new commit names, because a commit's name is a hash of its contents *and its parent*.

The machines do not fetch the line from GitHub, where it does not exist; the Mac sends it to them as a **bundle**, a single file holding the line's own commits (`plan/accepted.bundle`), with every build job. A machine may run CPU work only once its **build** of the fleet's current commit (a job named `prep-MACHINE-COMMIT`) is done.

The **planner** (`tools/plans/treadcore.py`) decides all of this. The keeper runs it every minute or two; it reads its memory, `plan/state.json`, decides, and writes the memory back at the end of its pass. Other programs use the planner's code to *read*: `analysis.py`, for one, builds the Analysis pages from it.

## III. What happened

*Table I. 4 November, from the keeper's events, the branch's history and the logs.*

| Time | What |
|---|---|
| 19:31 | r0179 (`bio` 0 to 3) goes on the line as `bdca5eb`; confirmed on all eight machines at 19:36 |
| 19:54 | The line's proof: −0.23 ± 0.22 against main, inside the noise; the next proof is due at 20:54 |
| 20:04 | treadcore `aebeb1d` (LR 147, the pinned test brain) on main; it touches the game's source, so the line must be replayed |
| 20:08:40 | The keeper's planner replays the line as **`f04f157`**, moves the branch and writes the bundle; at the end of its pass, 20:09:38, it saves `f04f157` in its state |
| 20:09:20 | A reader, `analysis.py`, which had read the state before the keeper's pass saved it, replays the line again as **`d821e7b`**: the same files, a different commit name. It moves the branch, rewrites the bundle, and saves nothing |
| 20:09:50 to 20:12:44 | The keeper sends eight builds of `f04f157`, each with the bundle of `d821e7b`. Each fails in about a second: `fatal: invalid reference: f04f1579…` |
| 20:10 on | The eight CPU lanes are idle; the health line reads "LOOK lanes: idle with nothing they can start"; the three GPU islands work on |
| 20:55 | Paul: "i see it just transitioned" |
| 21:00:33 | The fix's first pass: "the line's branch was d821e7b and its bundle held d821e7b, while the line is f04f157: both set to f04f157"; the eight failed builds set aside and asked again |
| 21:01:48 to 21:03:21 | All eight builds pass |
| 21:04 | Every lane runs |
| 21:06 | The line's proof, twelve minutes late, is queued |

> **Side note — how the second replayer is known.** No log names it. The branch's history shows a second replay at 20:09:20, and the bundle's time is 20:09. The keeper runs its planner's passes one at a time, and the pass that made `f04f157` did not end until 20:09:38; the keeper's other call on the planner, the five-minute sync (it began at 20:08:25), never asks which commit the fleet builds. Besides the keeper, the only program that runs the planner's code unasked is `analysis.py`, and its code does replay: it asks the planner for its trials' reads, and they ask which commit the fleet builds. Its last run finished at 20:53:55; at its cycle of about eleven minutes a run falls at 20:08 to 20:09 (an inference: its earlier runs leave no record). It is the second replayer by elimination.

**THE COST WAS 7.2 MACHINE-HOURS OF CPU** (eight lanes for 54 minutes) and a proof twelve minutes late. Nothing was lost: no result was wrong, and the GPU islands never stopped.

## IV. Why: three faults in a row, and a fourth that let it last

**1. A reader had a writer's side effect.** Asking the planner "what commit does the fleet build?" (`sha()`) ran the code that replays the line when main has moved. That is right for the keeper's pass, which then saves what it did. `analysis.py` asks the same question to draw its pages; it replayed too, moved the branch and the bundle, and, being a reader, saved no state. The keeper's pass and the report raced, and each made its own copy of the same commit.

> **Side note — why two copies of one commit.** The two replays put the same files on the same parent, but a commit's name also hashes the time it was made. Made forty seconds apart, they are two commits: `f04f157` and `d821e7b`. Neither is wrong; having both is.

**2. One fact was kept in two places.** The line's head was written in the planner's state *and* in a git branch and its bundle. Nothing checked that they agreed, and from 20:09:20 they did not: the state, which names the builds, said `f04f157`; the bundle, which carries the commits, held `d821e7b`.

**3. A failed build was never asked again.** The planner asks for a machine's build once a commit and, finding the build's name among the failed jobs, never again. With every machine's build failed, no machine was ever ready, and the planner, rightly, gave unready machines no CPU work. The fleet would have stood until main or the line moved next.

**4. Nobody was told.** The console's health line showed "LOOK" for 50 minutes, and the keeper listed every CPU lane as *starved* in its own record. A LOOK is a line in a list; it is not a flag, and it asks no one.

## V. The guards (`b19b5c2`)

**A writer moves the line; a reader sees it as it was kept.** `Plan.writer` is false unless the planner runs as one of the commands that save the state (`plan`, `now`, `approve`, `resolve`, `why`, `tag`, `adopt`). A reader asking `sha()` gets the line's head as the state holds it, replayed or not, and touches no branch, bundle or flag.

**The state is the line's truth.** On every writer's pass, `heal_line` compares the branch and the bundle with the state's head; if either names another commit, both are set to the state's, and a flag says so. It is two git reads a pass when all is well.

**A failed build is asked again, once.** `retry_failed_builds` moves a failed build of the fleet's current commit to `failed-retried/` and lets the planner ask for it again, once a machine and commit. A build that fails for a real reason, a compile error, fails twice and stops, as before.

**Proved.** `board-check.py` has a check for each: a reader replays nothing while the writer does; a branch moved behind the state's back is set back on the next pass, and said; a failed build of this commit is set aside once and an older commit's is left. The keeper's own check (`fleet-queue-check.sh`) passes. Live, the first pass after the change healed the line at 21:00:33 and the fleet was whole four minutes later (Table I).

> **Side note — the proof's reads are pooled now (`228c30c`).** Earlier the same evening, each hourly proof of an unchanged line was judged alone on fresh seeds: the same question asked again, 17 machine-minutes each time, and each time a one-in-750 chance for a line that changes nothing to pass by luck. Now each proof of one line against one main adds its seeds to those before it. A commit on either side, as at 20:04, starts the pool again, because a commit can change the game.

## VI. Restarting Orrery: three things carry the name

"Orrery" is three programs, and they restart differently.

**The application** (`/Applications/Orrery.app`): the window, its pages and buttons. **It is not the keeper's parent:** the keeper (pid 1789) runs under the system, in a session of its own, and has been the same process since 31 October at 18:01. Quitting the application leaves the keeper and every job alone. Its ssh connections stay up for the next launch to reuse. Today the application was launched at about 14:26 and again at 16:59; neither launch was followed, in the next five minutes, by a job sent back, a machine unreachable, or a restart.

**The document the window runs** (`treadcore-view.py`, every few seconds while the window is open). Besides drawing, it starts the fleet's housekeeping in the background when a file is old:

*Table II. What runs only while Orrery's window is open.*

| Work | Every | What it does |
|---|---|---|
| analysis.py | 10 minutes | the Analysis pages |
| nets.py refresh | 5 minutes | Results, Nets |
| growth.py refresh | 5 minutes (sizes each 30) | Results, Growth; an ssh to every machine |
| recordings.py list | 30 minutes | Results, Recordings; an ssh to every machine |
| recordings.py **sweep** | 6 hours | **deletes** recordings whose recipe is proved |

With the window closed, none of this runs: the pages go stale, and the sweep that keeps the disks from filling waits. When the window opens again, everything stale starts in the same few seconds. Before `b19b5c2` that included a replay of the line by `analysis.py`; **so opening Orrery after main had moved could have caused tonight's fault by itself.** It cannot now.

**The keeper** (`tools/fleet-queue.py … start`): the queue, the lanes, the planner's clock. This is where restarting costs. The keeper restarts itself when its own file changes (or when Restart is pressed): it stops every job on its machine, re-executes itself in place (same pid, so `caffeinate` holds the Mac awake throughout), and puts the stopped jobs back on the queue, to run again from the start. For a change it makes on its own, it waits until no job has run longer than ten minutes, so a six-hour job is never thrown away for a code change.

*Table III. What restarts cost, 29 October to 4 November (the keeper's events).*

| Cause | Jobs run again | Machine-hours lost |
|---|---|---|
| The keeper restarted for new code (13 times) or Restart pressed (once) | 125 | 7.4 |
| Left marked running across a restart, longer than its 90-second wait, and sent back by the next keeper | 7 | 0.3 |
| Left marked running by the fleet's shutdown at 14:04 on 31 October, sent back when the keeper started again at 18:01 | 3 | none: the fleet was off |
| ssh failed (host unreachable), 25 of them in two hours on 30 and 31 October, as machines went down | 36 | 5.0, not a restart's |

The keeper's events call the second and third rows "the keeper before this one died while it ran"; no keeper died this week.

Tonight's 19:42 restart, for the console's verbs moving out of the keeper's file, sent back eleven jobs, the line's proof among them. That change (`f51fb2f`) means editing those verbs no longer restarts the keeper; any other edit to `fleet-queue.py` still does.

## VII. Restarting without losing work: four changes

**A. The keeper keeps its jobs across its own restart (built the same night: section X).** A process that re-executes itself keeps its children: the ssh processes running the jobs live on, still the keeper's, still writing their logs. Today the keeper stops them before it restarts. Instead it would write each running job's ssh pid into the job's record, re-execute, and the new keeper would *adopt* them: wait on each pid (`os.waitpid`, which works on a child it did not start in this image), then finish it as any job finishes (deliver, fetch, done or failed). The lane of a machine with an adopted job takes nothing new until it ends. New code would then take effect at once, with no wait for a quiet moment. **This is the 132 jobs and 7.7 machine-hours of Table III.** About a hundred lines in `fleet-queue.py`, and a check in `fleet-queue-check.sh` that restarts a keeper under running jobs and sees each finish once.

**B. The machine keeps the job's end.** A keeper that *dies* (a crash, the Mac restarting under a running fleet) cannot wait on ssh processes it did not start; the next keeper runs every such job again, and does not stop the old one, which may still be running. The job's wrapper on each machine already writes the job's pid to `~/.fleet-queue/ID.pid`; it would also write the exit code to `~/.fleet-queue/ID.rc` and the output to a log beside it. A new keeper would ask each machine about the jobs it inherited: still running (watch it), ended (read its code and log, fetch, finish), or gone (run it again). **No keeper died this week, so B saves nothing measured;** it is insurance against the day one does. It is larger than A, since a job's output today returns through its ssh.

**C. The housekeeping moves from the window to the keeper (built the next morning: section XI).** The keeper already runs the planner on a clock; it would start Table II's work on the same schedule, and the console would only read the files. Closing the window would then stop nothing, and opening it would start nothing: an Orrery that can come and go as it likes. A few dozen lines, most of them moved.

**D. A fleet with nothing to do says so (built the next morning: section XI).** When CPU lanes stand idle with nothing they can start for fifteen minutes, the keeper raises a flag with the reason it can see: the current commit's builds failed on N machines, with the first error line; or the planner asked for nothing, and why. Tonight that flag would have named `fatal: invalid reference` at 20:25, half an hour before anyone saw the lanes. A few lines in the keeper's health and flags.

*Table IV. The four, by what they save.*

| Change | Saves | Size | Risk |
|---|---|---|---|
| A, adopt across a restart (built) | 7.7 h a week; new code at once | about 100 lines | a job finished twice if the adoption is wrong; the check guards it |
| B, the end kept on the machine | nothing measured: insurance against a keeper that dies | larger | touches every job's wrapper |
| C, housekeeping in the keeper (built) | stale pages, a late sweep, a burst on opening | small | none to the fleet |
| D, idle lanes flagged (built) | the next 54 minutes like tonight's | small | none |

The order I would take: D (the cheapest, and the one that would have named tonight's fault first), C, A, and B only if a keeper ever dies.

## VIII. Discussion

Tonight's fault had no single cause, which is why it lasted. The replay itself is sound, and a replay twice is harmless while one record names the line; two records that can disagree turned a harmless repeat into a contradiction, and a build that was never retried turned a contradiction into an hour. Each guard closes one link: readers no longer write, the state wins every disagreement, and a failure is asked again. Any one of them would have ended tonight's fault in minutes; together they leave no path for it.

The broader lesson is about where work lives. The console was built to draw and to press buttons, and over the weeks it acquired duties: refreshing, sweeping, and, by accident, replaying. A window is the wrong home for anything the fleet depends on, because people close windows. The keeper is the fleet's clock; what must happen on time belongs to it.

The keeper's restarts are the other half of Paul's question. The fleet has learned to restart itself for new code, and to wait so as not to throw away long work, but it still throws away short work every time: 132 of the week's 172 requeues. A process that keeps its children across its own restart, and machines that remember how each job ended, would make a restart something nobody needs to time.

## IX. What Paul decides

Which of A to D to build, and in what order. Paul chose A the same night (section X), and D and C the next morning (section XI); B waits. Section XI leaves Paul one more: a treadcore test that reads the code's defaults, and holds back the night's best candidate.

## X. Addendum, the same night: A built

Paul: "build A. commit. push report."

**What was built.** The handover of section VII.A, in `tools/fleet-queue.py`. On a restart no lane takes more work; each lane finishes what is not its command (a send, a fetch) or parks on its command, and from that moment nothing reaps a child, so a job that ends inside the handover keeps its exit code for the new keeper. The running jobs are written to `handover.json` with their pids, and the process re-executes. The new keeper takes up a job only if the handover was written by the same process (a pid from another process could name some other child); it waits on the pid, keeps the job's first clock for its timeout and its start time for its lane, and finishes it as any job finishes. A job whose process turns out not to be its own goes back on the queue, said. On new code the keeper now restarts at its next beat, unless a lane is delivering or fetching; the ten-minute wait is gone. The Settings page's Restart says how many running jobs it carries on, no longer how many run again.

**How it was checked.** A new check, `tools/restart-check.sh`, runs a real keeper with five lanes on this Mac and five jobs that each count their own runs. It presses Restart under all five, and again under the longest:

- the same process re-executes, and all five jobs are taken up;
- a job that ends inside the handover (held open three seconds by the check's own setting, `handover_hold_s`), before the new keeper begins, is read from its exit and is done;
- a job that exits 3 is failed with code 3;
- a job with a 15-second limit times out at 15 seconds on its first clock;
- a job stopped by hand after the handover stops;
- the second restart hands the longest job over again, and its one log runs from before both restarts to after;
- a handover written by another process is not taken up, and the job it names runs from the queue;
- every job started once and ran once, and nothing but that one went back on the queue.

It passed three runs in a row; `fleet-queue-check.sh` and `breaker-check.sh` pass, and orrery's 397 tests.

**One more restart costs what they all did.** The keeper running when this lands is the old code, and its restart into the new is the old kind: what runs then goes back on the queue, for the last time. A pressed Restart can still cut off a lane that is delivering or fetching for more than 90 seconds; B, C and D are not built.

## XI. Addendum, the next morning: D and C built, and a fault the night found

Paul: "build D and C. commit push."

**The night.** Under the handover's keeper the fleet ran 1,328 jobs from 21:52 to 05:29, with no restart and nothing sent back. It found one fault, of the same family as section III's. At 00:15 the night's one promotion (r0182: grove/w10040, `ping_style` 0 to 2, census +2.05 ± 1.31, held out +0.69 ± 0.44) went to macmini and died in one second on `fatal: invalid reference: orrery/accepted`. **The line is a branch only on the Mac.** Every build fetches the line's commits from its bundle, but under no name. A promotion runs on any CPU lane since 3 November, and r0182 was the first promotion built on a line to leave the Mac. The planner then misread the failure as "the brain's tests failed", because the log begins with the job's command, and the command holds every verdict's words. A candidate whose tests failed waits for main to move; main did not move, the other two candidates were judged noise, and **no generation landed all night.**

**The promotion, fixed.** The job takes the line's bundle with it and names the line by its commit, which is the same on every machine (`promote_base`). A verdict is read only from a line of its own; any other failure is "the promotion job failed", followed by the first `fatal:` or `error:` line. A candidate whose promotion failed that way is tried again at once, once. Live, at 05:37, the planner tried grove/w10040 again as r0185. bosporus fetched the line, built on it and ran the tests, which this time judged the candidate on its own numbers. One test fails: `commander::tests::with_pings_on_as_built_a_bot_comes_to_any_ping`. **It builds its settings with `Settings::parse`, which starts from the code's defaults, not the pinned brain:** a gap in LR 147's lint, which forbids `Settings::default()` but not a parse on top of it. The test is treadcore's and waits for Paul.

**D, built: a fleet with nothing to do says so.** When CPU lanes have been idle for `idle_flag_s` (900 s) with nothing they can start, the keeper raises one flag per spell, saying what it can see, in this order:

- a build that failed: on how many machines and which, with the first error line of its last run (the command at the head of the log is skipped);
- builds not done;
- jobs waited on, not done;
- nothing queued that fits, with when the planner was last asked and what it added.

While the spell lasts, health shows the same reason as BAD. A spell ends after a minute with no such lane ("idle lanes at work again"), and it carries across the keeper's own restart, so one spell raises one flag. Since 31 October there were two such spells: saskatchewan for 29 minutes on 3 November, and section III's 54 minutes. **For the second, the flag would have read, at 20:25: the build failed on 8 machines: `fatal: invalid reference: f04f1579f4a8…`.** That is the line this code reads from those logs today.

**C, built: the housekeeping is the keeper's.** The planner's new `chores` command begins whatever is stale, in the background, on the window's old clocks and behind its old locks:

- `analysis.py` every 10 minutes;
- `nets.py` and `growth.py` refreshes every 5;
- the `recordings.py` list every half hour, and its sweep every 6 hours.

The keeper asks for the chores every `chores_s` (60 s) on a thread of its own. The list and the sweep now run strictly one at a time; the window could start a sweep while a list was still running. The window starts nothing: its four functions only read. Health gains a `chores` line. The schedule lives in the planner, which is read from disk each time, so changing it restarts nothing.

**How it was checked.** A new check, `tools/idle-check.sh`, runs a real keeper with two lanes on this Mac and a stub planner that plans nothing and counts its chores:

- each machine's build fails on git, with an error-like line planted in its command: one flag, naming 2 machines and the error the job wrote, not the one in its command;
- health says the same;
- the flag is raised once however long the spell lasts, and once across the keeper's restart;
- work arrives, and the spell ends and says so;
- with nothing queued at all, a new spell names the planner's last ask and what it added;
- the keeper asked for its chores every two seconds, with no window, and health says when and what was begun.

`board-check.py` gains checks for:

- the chores' clocks and locks, with stand-in tools;
- a promotion from a clone without the line's branch: the old command fails with the night's error, and the new one builds on the line and its commit comes home;
- verdicts read from lines of their own;
- a fault retried once, and a real test failure left to wait for main.

`fleet-queue-check.sh`, `breaker-check.sh`, `restart-check.sh` and `idle-check.sh` pass, as do orrery's 397 tests.

**Live.** Landing the keeper restarted it for new code at 05:46:43, nine seconds after the file changed. 11 running jobs were handed over and adopted at 05:46:44, and none went back on the queue. Its chores then began each document as it came due: nets.py at 05:48:30, growth.py at 05:49:36, analysis.py at 05:51:48, each written within a minute. A last refinement, reading a log's last run rather than its first, restarted it again at 05:51:59: 11 more were handed over, three of them for the second time. **Restarting the keeper is now something nobody needs to time.** B, the end kept on the machine for a keeper that *dies*, is not built.

## References

[1] orrery commit `b19b5c2`, "A reader replays nothing, the state is the line's truth, and a failed build is asked again once", 4 November 2026.

[2] orrery commit `228c30c`, "The line's proofs pooled", 4 November 2026.

[3] orrery commit `f51fb2f`, "The console's verbs out of the keeper's file", 4 November 2026.

[4] treadcore commit `aebeb1d`, LAB-REPORT-BRAIN.md section 147, "The tests play a pinned brain", 4 November 2026.

[5] The keeper's events (`QUEUE/events.jsonl`), log (`keeper.log`) and the build logs `logs/prep-*-f04f157.log`, 29 October to 4 November 2026.

[6] git reflog of `orrery/accepted` in the Mac's treadcore checkout, 4 November 2026.

[7] `tools/restart-check.sh`, the handover against a real keeper, 4 November 2026.

[8] `tools/idle-check.sh`, idle lanes and the housekeeping against a real keeper, 5 November 2026.

[9] The keeper's events and `logs/r0182-promote.log`, `logs/r0185-promote.log`, 5 November 2026.
