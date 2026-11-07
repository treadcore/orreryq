# Orreryq — feature guide

The console, chapter by chapter and page by page, as it stood over the running
fleet at 20:48 on 6 November 2026. **Every picture is a frame the program drew
of the live queue with its own `--frame` renderer** — the same drawing code as
the window, no screen and no photograph — so what you see is what the window
shows, down to the job ids. To take them all again:

```sh
SHOTS=tools/report/feature-shots.list OUT=docs/features/live \
    tools/report/double-shots.sh ~/code/treadcore/build/queue/grove
```

What each page says under its own **About this screen** is the source of the
words below: *does* is what the page is for, *look for* is what a person
should catch on it. Both come from `tools/plans/line.json`, so the window and
this guide say the same thing. For what Orreryq is and how the pieces fit, start
with the [README](../README.md); for the console's first faces (the wall, the
seat and the museum interface, pictured from the demo fixture), the
[museum guide](MUSEUM_GUIDE.md).

## Contents

0. [Every page: the header, the rail, the inspector, About](#0-every-page)
1. [Machines: Machines, Media, Storage](#1-machines)
2. [Projects](#2-projects)
3. [Queue: Fleet, Runs, and the Pipeline's eight pages](#3-queue)
4. [Results: what the fleet found, fifteen pages](#4-results)
5. [Watch: Lab, Sessions](#5-watch)
6. [Fleet: Orchestrate, Chat](#6-fleet)
7. [Settings: Keeper, Long run, Ranges, Commits](#7-settings)

## 0. Every page

**The header** is the seven chapters, `Command` and a digit each, and on its
right the fleet and how many of its machines answer. **The rail** down the left
holds the chapter's pages; a lamp on a page is lit green when it has news and
red when it wants a person (Growth 1 and Flags 15 below). **The footer** of the
rail says, in a line, where in the process the chapter sits.

| | |
|---|---|
| ![About this screen, open](features/live/0-about.png) | ![The inspector under the pointer](features/live/0-inspector.png) |
| **About this screen**, open: six short answers — what the screen does, where it ties in, why it is drawn this way, what to look for, what is being simulated, and why it helps the brain. | **The inspector**: point at almost anything and a panel says what it is, where its number came from and which file holds it. Here, a task on the Pipeline's Board. |

## 1. Machines

### Machines

![Machines](features/live/1-machines.png)

Adds a computer to the fleet: **probe** it (system, CPU, GPU, driver, CUDA,
Rust, the fleet's tools), **apply** a setup recipe, **join** it to the queue.
Apply is hard to press on purpose: the machine's name must be typed, and the
command runs in a terminal of its own where the operator types the sudo
password; orrery never holds one. *Look for:* a machine stuck on a step, or a
recipe that says ready to run.

### Media

![Media](features/live/1-media.png)

The cards and images the machines were made from: which card carries which
token and which have been written. *Look for:* a card whose image is older
than the fleet's.

### Storage

![Storage](features/live/1-storage.png)

The fleet's disks and shares as a patch bay: survey, share, mount. *Look for:*
a disk filling up, or a 10 Gb link not plugged in.

## 2. Projects

![Projects](features/live/2-projects.png)

Which machine works on what: treadcore's census on the CPUs, crucible on the
CUDA cards, with pause, stop and resume per machine and per project. *Look
for:* a machine on no project, or a project paused and forgotten.

## 3. Queue

### Fleet

![Queue, Fleet](features/live/3-fleet.png)

Each machine, its job now, its cores, and its buttons: pause (the job in hand
finishes, nothing new starts), stop now (the job goes back on the queue),
remove, add. The bar over them is every job the queue has run. *Look for:* a
lamp not lit under a full queue, or one machine on old work.

### Runs

![Queue, Runs](features/live/3-runs.png)

Asks for a one-off run (a search, a census, a recording, a gauntlet, net
training and more), cancels one, accepts one; the list beside it is every run and how
it ended. *Look for:* a run failed or left running with no lanes.

### The Pipeline: Board

![Pipeline, Board](features/live/3-board.png)

The whole line as tasks: their order, their machines, the time each is
expected to take, and in red at the top **the next essential task**. Under the
Gantt chart, the same tasks as a kanban of waiting, running and done. *Look
for:* red, the biggest blocker; NOT BUILT, a gap in the road to one brain.

### Flow

![Pipeline, Flow](features/live/3-flow.png)

How data moves: what each stage takes in and gives out, and one real trial's
numbers traced through. *Look for:* how far each trial got, and where the road
stops — a red box means data goes no further.

### Timeline

![Pipeline, Timeline](features/live/3-timeline.png)

Every machine: what it did, what it does now and what it will do next, at six
zooms from the hour to three months. Left of now is measured; right of now is
a forecast from medians, and says so. *Look for:* gaps on the left, which are
lost time; green marks, which are generations; and a block pointed at, whose
whole chain lights.

### Queued

![Pipeline, Queued](features/live/3-queued.png)

What is waiting and running, each with why it is there. *Look for:* priority
work behind a long queue, or one kind crowding out the rest.

### Values

![Pipeline, Values](features/live/3-values.png)

The numbers that set how hard a generation is, each with its default. Change one here and the next plan uses it. *Look for:* a
value away from its default, and whether the generation gap on the Board
answers.

### Blame

![Pipeline, Blame](features/live/3-blame.png)

Every machine at a round table: who it waits on, and the help it takes from
the queue while it does; beside it, each machine's own queue, folding by a
click. *Look for:* a red arrow, the only real blame — work standing while
another machine finishes. Amber that stays is a chain handed back to the
planner; a busy share under 90% is time to find.

### Lineup

![Pipeline, Lineup](features/live/3-lineup.png)

Every chain in its own rows, a Gantt chart each: a trial, a run, a build, an
island, the line's proof. *Look for:* a red wall, a dead end (a trial dropped
after its reads, a held-out read that did not pass, a promotion that failed);
green, won; amber, still going.

### Hit Parade

![Pipeline, Hit Parade](features/live/3-parade.png)

The tally of every job handed off: each machine a row, each kind of job a
column, counted. *Look for:* a share under 99% in amber or red, and a machine
whose rate falls behind its kind's.

## 4. Results

The rail's own order. The headline over every Results page is the search's
standing: candidates, improvements, auto mode, and the newest change read.

### Candidates

![Results, Candidates](features/live/4-candidates.png)

Trials past their held-out read: a list of what may become a generation, and
nothing to answer. *Look for:* current ones waiting, and the same one failing
tests twice.

### Found

![Results, Found](features/live/4-found.png)

Each improvement read, by dial and by machine. *Look for:* a dial that keeps
coming up, or one machine reading differently from the others.

### Net

![Results, Net](features/live/4-net.png)

The learned tank's net: its weight matrices, a cell a weight. *Look for:* dead
rows or columns, a sense or an action nothing reaches.

### Nets

![Results, Nets](features/live/4-nets.png)

Every learned net the fleet made or keeps: where each has been, what read it
on every gauntlet, its weights and its notes; capture, promote and expire by
request.

### Growth

![Results, Growth](features/live/4-growth.png)

crucible's generations, a sample a segment — fitness, yardstick, exam, and the
champion's matrices — and the sizes every place the fleet's generations fill,
with Measure and Purge. *Look for:* a norm that keeps climbing while the exam
falls (the net is saturating, not learning), and a red bar, a place over the
limit.

### Generations

![Results, Generations, Roads](features/live/4-generations.png)

The lab report *Outgrowing Yourself*, live, a tab a figure: **Roads** (above,
the GPU's road and the CPU's to main, a box a stage with today's numbers),
Days, Turnaround, Kept, GPU, Gauntlet and Hours.

| | |
|---|---|
| ![Generations, GPU](features/live/4-generations-gpu.png) | ![Generations, Gauntlet](features/live/4-generations-gauntlet.png) |
| **GPU**: each generation's margin over the one before, the exams against the newest world generation, and the yardstick. | **Gauntlet**: each segment's weighed step on crucible's gauntlet against the bar, and why it was or was not elected. |

### Recordings

![Results, Recordings](features/live/4-recordings.png)

Every behaviour-cloning recording: its shards on the store, its recipe (the
binary and seeds that make it again), who still reads it; Keep, Drop,
Re-record, and a seed read a tank at a time. *Look for:* a run with a complete
recipe and no reader, which the sweep drops within six hours.

### Montage

![Results, Montage](features/live/4-montage.png)

The generations since the last film, as a film: each new milestone's champion
in crucible's world duels, the camera on its best won duel and every other
duel a ghost, the net's inputs and decisions drawn beside it. Make, watch it
made, play. *Look for:* the won share growing chapter on chapter.

### Videos

![Results, Videos](features/live/4-videos.png)

The films in orrery's output folder, newest first, with their data: made,
length, size, chapters, the generations each covers, and the chapter marks to
paste into a video site's description.

### Algorhythm

![Results, Algorhythm, Patch](features/live/4-algorhythm.png)

The brain as a patch: dials, switches and the transform, in order. *Look for:*
stages at zero — they cost nothing and do nothing. Its other tabs read the
brain from other sides:

| | |
|---|---|
| ![Algorhythm, Terrain](features/live/4-terrain.png) | ![Algorhythm, Matrices](features/live/4-matrices.png) |
| **Terrain**: each dataset's reads as a landscape over two dials, with its local maxima. Places to look, never results. | **Matrices**: the shipped net's layers as tables. Low stable rank means the net uses little of its size. |

Spectrum, Senses, Temper and Fleet are tabs beside these.

### Personas

![Results, Personas](features/live/4-personas.png)

The roster of styles and personas: what each plays, the dials its profile sets
over today's defaults, and its last census read — the Gladiator, crucible's
elected net, among them. *Look for:* a persona still unread, or one reading
under today's defaults by two errors.

### Gauntlet

![Results, Gauntlet](features/live/4-gauntlet.png)

The single-decision tests' last record: a row a gauntlet, a column a brain
(the rules, the untrained net, every net in `nets/`), the share of seeds
passed, red under the file's floor. *Look for:* a red cell for the rules,
which is a finding about the scripted brain.

### Flags

![Results, Flags](features/live/4-flags.png)

What needs a person, and what progress was made; acknowledge it. *Look for:*
red, unacknowledged, or the same flag rising again.

## 5. Watch

### Lab

![Watch, Lab](features/live/5-lab.png)

The room of machines, a live tile each, as the copal fleet knows it. *Look
for:* a dark tile, or a machine hot under load.

### Sessions

![Watch, Sessions](features/live/5-sessions.png)

A terminal for each machine, kept alive in tmux, in a grid. *Look for:* a
build error or a stack trace nothing reported.

## 6. Fleet

### Orchestrate

![Fleet, Orchestrate](features/live/6-orchestrate.png)

Who may command the fleet, what each machine is, and the verbs: select by
question, send a verb, each answer per machine. *Look for:* a certificate near
expiry, or a machine answering differently.

### Chat

![Fleet, Chat](features/live/6-chat.png)

One room to talk with each machine, kept on the machine. *Look for:* a machine
that stopped answering.

## 7. Settings

### Keeper

![Settings, Keeper](features/live/7-keeper.png)

Is it running as it should: the keeper, its code, its planning and the lanes,
every check a line, with its buttons. *Look for:* an amber or red lamp, above
all search, difficulty and starving lanes.

### Long run

![Settings, Long run](features/live/7-longrun.png)

The work that repeats over many generations: its options, and what it last
found. An option at 0 means that work is off.

### Ranges

![Settings, Ranges](features/live/7-ranges.png)

The brain's RANGES: every number's limits, today's default between them, its
kind, the reason, and the decrees — only Paul decrees. *Look for:* a default at
an edge of its range, which means the search wants past it.

### Commits

![Settings, Commits](features/live/7-commits.png)

The line the fleet builds, newest first, with the defaults each changed; a row
opens it on GitHub. *Look for:* how often a commit is a generation, and
whether a machine is behind.

---

MIT. Copyright (c) 2026 Paul Richeson.
