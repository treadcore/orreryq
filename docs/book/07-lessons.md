# Lessons

What the month teaches about the process, drawn from the lessons each report recorded and from the week's record. Each is stated as a rule a future week can be run by, with the place it was learned. They are grouped: what worked, what wasted time, the faults that hid, what the numbers say about the judge, and how to record and ship.

## What worked

- **Write the rule before the run.** A z 5.9 result was refused by rules written before the read, because the rules said what would count and the breakdown said it did not ([A Stale Dial](../2026-11-01-a-stale-dial.html)). The width test's bar of 1.0, set in advance, made a 0.85 gain a clean "not yet" ([Waves](../2026-11-01-waves.html)). Every design in this book's plan names its bar first.
- **Build the negative control first.** A waves-on, amount-zero control over 400 seeds reading exactly zero let every later difference be believed. A control costs one read and saves a week of argument.
- **Make every new thing a version the same judge reads.** Choices, switches, roles, model slots, styles and the temperament rows were all read by one census unchanged; the judge did not have to be rebuilt for each ([brains.md](https://github.com/richeson/orrery/blob/main/docs/brains.md)).
- **Prove each link in a container before touching a real machine.** The fleet listener, the CUDA nodes and the Copal machines were each rehearsed on throwaway machines first; the faults found there were cheap ([Commanding the Fleet](../2026-10-30-fleet-orchestration.html)).
- **Prove against other people's servers, not your own fakes.** A real sshd, OpenSSH's sftp-server and openssl found what no fake would have; the one module with no fake was the one with no surprise.
- **Mine the records already on disk.** Five diagnostic views (terrain, spectrum, matrices, senses, fleet) came from reads already made, for no new games ([Reading a Growing Brain](../2026-10-30-analysis.html)).
- **A frame rendered to a file is an acceptance test.** Three drawing bugs invisible to a green test run were found only by looking; a byte-identical frame proved a refactor; this book's own tooling was proved the same way.

## What wasted time

- **Tests that pinned constants rather than rules.** Half of all promotions for three days failed on them; fixing them one at a time cost a passed candidate each. The sweep that fixed them all at once fixed the line ([The Whole Line](../2026-11-01-the-whole-line.html)).
- **Measuring every change together.** Game 4's six levers went in at once over eight seeds of one map, and there was no way to say which did what ([Too Many Shots](../2026-10-30-balance.html)). One lever at a time, 400 seeds, all maps.
- **Short smoke tests.** A 300-second one-map test read a dial as exactly zero that a full census read at +1.5; smoke tests must be 900 seconds on real maps or not run ([Algorhythm](../2026-10-30-algorhythm.html)).
- **Lowering the bars.** The simulation showed the read-on limit buys nothing and that ease past about 2.5 promotes mostly noise; the pace is set by seeds, not bars ([Promotion Difficulty](../2026-10-29-difficulty.html)).
- **The process outrunning its own checks.** A proof takes a quarter of an hour and generations landed inside it, so a proof that passed at z 4.82 had nothing left to land. The fix was to land the commit that was read, not the line's head.
- **A dashboard that mixed retired with failed.** It made a healthy queue look broken and sent the owner hunting a fault that was 96% jobs that never ran ([Double Report](../2026-11-01-double-report.html)).
- **Written-down state.** A saved address list called two healthy machines down; a value copied at join time went stale silently. Read the truth every run.

## The faults that hid

- **A self-inflicted fault behind a hardware one.** jaguaribe's dead clock battery and the SSH resets looked like one fault; the resets were orrery's own four-second polling with an expired eight-hour certificate, which OpenSSH penalised ([A Dead Clock Battery](../2026-11-01-jaguaribe-clock.html)).
- **A crash recorded as a verdict.** Reading a panic as UNDER hid a strongest-in-fleet result for three hours ([Many Versions of One Brain](../2026-10-30-brain-versions.html)). A crash is never a number.
- **A keeper running the code it started with.** Fixes to the keeper did nothing all evening; it now restarts itself on new code.
- **A fit that cannot tell a dead dial from noise.** A dial not routed by the chosen switch reads exactly zero and looks settled.
- **A nearby search that cannot find a far optimum.** The fit looks within a doubling or two; `w_pos_fortify`'s best value was eight to sixteen times away, and the far read was built for it ([Eight Named Minds](../2026-11-01-bot-styles.html)).
- **A variadic FFI declared fixed.** `fcntl` declared with a fixed third argument compiled, ran and never delivered `O_NONBLOCK`; it hid for two phases because every test asked a question before reading.

## What the numbers say about the judge

- **The score is blind to what it does not weigh.** It paid for walking and did not notice 18% less building or a third of a point a seat lost in fights. A judge must read the composition, not the total; the trade guard is the first rule that does.
- **Picking the best of several first reads inflates it.** Timid went from +3.15 on picked seeds to +0.39 on fresh ones. The held-out reads exist for this, and the fit's memory must not let a picked read back in.
- **A tiny effect has a tiny error.** +0.08 ± 0.04 clears any z and is worth nothing; a floor on the gain, not only on z, keeps the line from filling with noise.
- **The seed swing is the pace.** 9.5 points a seat means 400 seeds for half a point; the search cannot be hurried past that except by playing more seeds in parallel, which is machines.
- **Values promoted under an older game go stale, and the search cannot find its way back** without a far read or a person. A game change must start the evidence anew (GAME_VERSION), and every dial promoted before it is suspect.

## On recording and shipping

- **Every step recorded is a step that can be audited.** This book was possible because each check-in quotes its prompt and traces its decisions; the one week with thinner records (the fleet's first days) is the one hardest to reconstruct.
- **A commit to main is a fleet event.** It replays the line, rebuilds every machine and voids a proof in flight; source goes out when no proof runs, and documents go out any time, which is why the planner learned the difference.
- **Hand the irreversible to the person.** Nothing in orrery formats a disk, pushes a tag or lifts a decree; destructive steps are staged scripts with a list, not buttons. The two things that went to main by a person's hand this week (the building dials, the cycle restored) were the two the score could not see.
- **Say what was left out, on the page, with counts.** The terrain report's "88 maxima, 77 read, 58 unsettled, 3 bare" is the cheapest guard against the same rot recurring, and this book's register (chapter 8) is written the same way.

## Links

The lessons sections of each report named; [Fleet Commanders](../2026-10-30-fleet-commanders.html) and [Commanding the Fleet](../2026-10-30-fleet-orchestration.html) for the proving-in-containers method; [From Cargo to AppKit](../2026-10-28-appkit-gui.html) for the frame-as-test method.
