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

Every 5 generations the champion joins a hall of fame; islands swap champions; an exam against a ladder of milestones keeps honest score. Fast and real, in its own world. Its nets have not played a tank in treadcore, which the design report that follows this one sets out to change.

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

Everything above exists to change what happens here. The menu is fresh from today; the rest are from the game's own playtest record of 13 to 26 October, so some of its rules have moved since, and its look has not.

!html(double/game.html)

Where to see the fleet's work in play: **every bot in these pictures runs `weights.rs`**. Press `U` for the sliders: a row for every weight and switch, for your own team. Those are the same numbers this report follows, and you can feel the difference between a raider and a castle-builder by loading `profiles/`. Selecting brains by name per team is the next report.

## XX. Threats and what is open

**Pictures are frames, not screen captures.** `--frame` runs the same drawing code as the window from the same documents, without the window's own state. A selection a person made, or a live hover, can look different. **Treadcore's pictures are old,** as said. **The story's numbers are one trial's:** `w4540` is real, and it is not a proof that `bio` helps. **The worked target score leaves out five terms** so the sum can be followed; the code has them all. **The bc2 training figures come from the lab report,** not from running it again.

**Open:** the Terrain's reads; the Runs line's words; the 2,302 retired jobs still say something real about the cost of a generation; the merges proposed in Section IX-B; a warning before the certificate ends; and the game cannot read a slot, which is the next piece of work.

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
