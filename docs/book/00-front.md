# The Post-Mortem and the Plan: a week of training, the goals rewritten, and the player it is for

*Paul Richeson, with Claude. 2 November 2026. Treadcore and orrery, in chapters.*

Treadcore is a sixteen-player tank game for the drone battlefield. Orrery is the console and the planner that run a room of machines to train the game's bots. Between 25 October and 2 November 2026 that room ran about a week without a hand on it: it read some two thousand trial brains, carried thirty-odd generations of weights onto a line, proved the line against the shipped game, and moved the shipped game eight times. This book is the post-mortem of that week and of the month that led to it, written for a newcomer: what the project is for, what it was told to do, what it did, what it learned, what it left undone, and what comes next.

It is written at the altitude of the process, not the dial. Where a number matters it is named once, with its error; where a report already carries the detail, this book links to it rather than repeating it. Paul's directives, which arrived as fast typing over four weeks, are given here in plain words with their spelling put right and their sense kept; the originals are quoted in the check-in reports the chapters cite.

The second half of the book is the plan. The design of this game was always in six parts: the design itself; its implementation; the training of the programmed brain's weights; the training of a transform that becomes a learned player; the combining of the two; and orrery, which orders the seeds, the promotions and the values so that the whole converges on a well-defined player. The first half of that is done and measured. The second half, which this plan sets out, starts where the week's numbers say it must: by locking the game's physical constants into ranges, so the search stops spending itself on numbers that were never meant to move.

## How to read it

Read the first chapter, then whichever question brought you. Chapters 1 to 8 are the post-mortem: the project, its goals, its directives, the week, the process, the findings, the lessons, the unfinished work. Chapters 9 to 15 are the plan: physical constraints and scale, personas, the wingman, the transform, the economy and logistics, play with and against bots, and the testing plan. Chapter 16 is the reference list, in IEEE form, which the plan cites by number. Every chapter ends with what it links to.

!chapters

## The reports this book stands on

The lab reports of the month are on this site, one page each, and listed on the [Lab Reports](../index.html) page. The ones a chapter leans on most: [The Whole Line](../2026-11-01-the-whole-line.html) (how the fleet's work reaches the game), [The Double Report](../2026-11-01-double-report.html) (the process end to end, and a guide to every screen of orrery), [Eight Named Minds](../2026-11-01-bot-styles.html) (bot styles), [A Stale Dial](../2026-11-01-a-stale-dial.html) (what a total score hides), [A Terrain for Each Dataset](../2026-11-01-terrain.html) (the local maxima), [Waves, Width and Waiting](../2026-11-01-waves.html) (temperament, the net's width, the queue), [Generations](../2026-10-27-generations.html) and [The Learned Tank](../2026-10-26-the-learned-tank.html) (the net), and treadcore's own [roadmap](https://github.com/treadcore/treadcore/blob/main/documentation/ROADMAP.md), [brain report](https://github.com/treadcore/treadcore/blob/main/documentation/LAB-REPORT-BRAIN.md) and [check-ins](https://github.com/treadcore/treadcore/tree/main/documentation/checkins).
