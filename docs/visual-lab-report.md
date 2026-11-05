orrery · treadcore · crucible · the visual state of a working prototype

# Seeing the Brain Grow: The Montage, the Mind in the Corners, and Every Screen of Orrery and Treadcore

*Paul Richeson · Lab Report — IEEE Format · 4 November 2026*

Paul Richeson, treadcore.org; Claude Code (Claude Opus 5.5) as the pair. Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery and treadcore.

Companions: orrery `tools/montage.py`, `src/montage.rs`, `tools/recordings.py`, `tools/plans/treadcore.py`; crucible `src/crucible.cu` (trace version 2); treadcore `documentation/LAB-REPORT-BRAIN.md` sections 138 to 146. The film: `output/treadcore-montage-0003.mp4`, also `docs/visual/montage.mp4`.

## Abstract

Treadcore is an MIT-licensed tank game whose computer players are trained by a fleet of ten ordinary computers and three graphics cards. A console named orrery runs that fleet, and a CUDA program named crucible evolves small neural networks on the graphics cards. Until today the learning could be read only as tables of numbers. This report documents the system's visual state on 4 November 2026 and the work of that day. We rebuilt the training montage, a film that follows the best champion of each generation through its duels. Every other duel of the same start now appears as a faded crowd moving with the camera, and the champion's network is drawn thinking in the film's corners: its 55 inputs, its two hidden layers of 48 with the strongest currents lit, an eight-second spectrogram of its decisions, and the generation. A title sequence borrows treadcore.org's brushed metal and phosphor. Every film is copied, with a chapter list ready for upload, to an output folder. The same animation now plays inside orrery, from a 0.55 MB file written beside the film, and a new page lists every finished film with its data, ready to post. We photographed every screen of orrery (30 pictures) and of the game (8 pictures), and we describe the redesigned flow by which a change to the brains becomes a promotion: a paired census, a trade guard, and since today a gauntlet guard of 22 single-decision tests. The recordings that once filled 114.5 GB on one machine are now debug material, kept only on request. The film of twelve generations is 99 s long, 4.2 MB, and took 233 s to make.

**Index Terms**: neuroevolution, neural network visualization, behaviour cloning, simulation-based testing, game AI, visual analytics, software architecture, immediate-mode graphical user interface.

## To the reader: what to expect

This report is written for an application software architect who has not seen these programs before and wants to judge a working prototype: what it is for, how its parts fit, what it can show, and where its claims stop.

Expect three things. First, a **map**: three programs (the game, the console, the GPU trainer) and the flow of a decision through them, from an idea about how a tank should play to a commit that changes how it plays. Second, **pictures**: every screen as it was on the evening of 4 November, each with a caption that says what it is for. Third, **evidence**: every claim of improvement in this project is tied to a measurement with an error bar, and a change that did not meet its rule is reported as a failure, as two of today's did.

The side notes, numbered in red, explain an idea when it first appears: what a neural network is, why a census is paired, what a spectrogram shows. A reader who knows the idea can skip the note; a reader who does not should find enough there to follow the argument. Nothing in this report requires knowing Rust, CUDA, or machine learning in advance.

The impression we hope to leave is of a system that is small enough to understand, honest about what it has not shown, and built so that every picture is drawn from recorded data rather than from a guess.

## I. Introduction: a game that teaches itself

Treadcore is an overhead tank game for up to sixteen players. Each tank carries a gun with two modes (a flat direct shot to ten tiles, and a lobbed mortar from twelve to sixty), a bay of drones (recon, interceptor, strike, longshot), and a squad of builders that capture pillboxes, mine ore and lay roads. Empty seats are filled by computer players, which the project calls *bots* or *brains*. The game is MIT licensed<sup>1</sup> and runs on Linux, macOS and Windows.

> **Note 1.** **MIT license.** A permissive open-source license: anyone may use, copy, change and sell the software, provided the copyright notice travels with it. All three programs in this report carry it.

A brain decides, several times a second, where its tank drives, what it shoots at, and which drone it launches. There are two kinds. **The rules** are hand-written: a commander, a tactician and a doctrine, about fourteen thousand lines of Rust with some three hundred numbers, called *dials*, that tune them. **The nets** are small neural networks<sup>2</sup> that read the game as a list of numbers and answer with a choice.

> **Note 2.** **Neural network.** A function built from layers of simple units. Each unit adds up its inputs, each multiplied by a learned weight, and passes the sum through a squashing curve. Stacking layers lets the function represent complicated decisions [12]. "Training" means finding weights that make the function do what we want.

The project's question is how to make these brains better without guessing. Its answer is a fleet: ten computers that play thousands of matches a day, each comparing a changed brain against today's on the same random seeds. A change is accepted only if it wins by more than two standard errors<sup>3</sup>. Three of the computers also hold graphics cards, where a second program evolves populations of neural networks by the million.

> **Note 3.** **Standard error.** How much an average would wobble if the experiment were repeated. Two standard errors either side of a measured average covers the true value about 95 times in 100. "Outside two errors" is the project's bar for calling a difference real.

A system like this produces numbers faster than anyone can read them. The question this report answers is a visual one: can a person watch the brains learn? Since 4 November the answer is yes, in three places: a film, a page in the console, and this report.

## II. The system at a glance

Three programs, each in its own repository, share the work. Figure 1 shows how a decision moves among them.

- **treadcore**, the game, in Rust. Its simulation is deterministic<sup>4</sup>: given the same seed and the same brains, a match plays the same way every time, which is what makes fair comparisons possible. It also holds the brains, the tests called *gauntlets*, and the *census* that measures a brain against another.

- **orrery**, the console, in Rust with no third-party libraries. It draws its own window, keeps a queue of jobs for the fleet, plans what to run next, and shows the results. Its planner, `tools/plans/treadcore.py`, decides each minute which machine plays what.

- **crucible**, the GPU trainer, in CUDA<sup>5</sup>. Each graphics card runs an *island*: a population of networks that duel each other in a small arena under the game's rules, the winners breeding the next generation. A champion judged better than every one before it becomes a *milestone*.

> **Note 4.** **Determinism.** Every random choice in the simulation comes from a seeded generator, and nothing depends on the clock or on thread timing. Two runs with the same inputs produce the same bytes. The project proves this for recordings by making them twice and comparing their SHA-256 hashes [17].

> **Note 5.** **CUDA.** NVIDIA's way of running C++ on a graphics card's thousands of small cores. Crucible plays one duel per core, so a card plays tens of thousands of duels at once.

*(The diagram of Fig. 1 is drawn in the HTML version.)*

***Fig. 1.** The program flow after today's redesign. Top: a change to the rules is measured by a paired census on the CPU fleet, read twice more on held-out seeds, held by two guards, and only then committed. Bottom: crucible's islands evolve networks under the game's rules; each milestone is read in the game as the Gladiator style, filmed, and, through the clone stage, used to judge an imitation of the rules.*

The design keeps one rule throughout: nothing changes how a brain plays until a measurement says it is not worse. The pictures in this report sit on top of that rule; none of them decides anything.

## III. The brains, and their program flow redesigned

### A. Two kinds of brain, and the styles between them

The rules are three layers. The **commander** picks a goal (hunt pillboxes, defend the base, escort a leader, fortify) and an errand within it. The **tactician** picks a target and decides whether to close, wait, or kite, by weighing distance, threat and the odds of the fight<sup>6</sup>. The **doctrine** fires the gun and launches the drones. Every number they use is a dial with a written range (`RANGES`), so the fleet can search them, and only Paul may fix one as a constant.

> **Note 6.** **The odds, by Lanchester's square law.** With aimed fire, a side's fighting strength grows with the square of its numbers [6]: three tanks beat two by much more than three to two. The tactician computes our strength squared over theirs and holds off, engages, or presses accordingly.

The nets read 160 numbers a decision: a compass of eight sectors with eleven channels each (enemy tanks, friends, pillboxes, depots, shells), the tank's body (armour, shells, reload), its instruments, a periscope of the nearest enemy and the nearest thing to take, the rules' hints, an incoming shell and a drone. They answer with a choice in each of seven heads: drive, gun, lead, mortar, drone, squad, signal. The game's own trainer finds their weights by evolution strategies with the Adam step rule [1], [21], or by imitation (Section III-D).

Between the two sit the **styles**: a roster of seventeen ways to play, each a set of dial values or a shipped net. Style 6, the Scholar, is a net that learned by imitating the rules. Style 7, the Duelist, and style 17, the Gladiator, read a champion from crucible's islands and drive with it, behind a *gate*<sup>7</sup> that lets the champion steer only when it is confident.

> **Note 7.** **A hybrid's gate.** The champion's network has one output more than it needs: its confidence. While the confidence is below zero the tank does what the rules say; above it, the rules' answer plus the network's correction. A new network starts with the gate shut, so it starts as good as the rules. This is the idea of residual policy learning [11].

### B. How a change is judged

A **census** plays the same seeds twice: once with the trial brain in a seat and once with today's, every other seat unchanged. Each match is 900 game seconds on one of twelve maps, with sixteen seats in teams and three respawns. Each seat is scored by a ledger of what it did: kills, deaths, damage, pillboxes taken, ore delivered and, since today's section 139, what it built and kept standing. The census reports the trial's score minus the base's, a seat at a time, averaged over the seeds, with its standard error. Because both halves of a pair share their seed, the luck of the map cancels<sup>8</sup>.

> **Note 8.** **Why paired.** Two brains on different seeds differ by skill and by luck; on the same seed, mostly by skill. The variance of a difference of correlated measurements is smaller than the sum of their variances, so a paired census needs far fewer games to see the same effect [16].

The project writes down the rule that would confirm a change before running its census, and a result inside two standard errors is reported as inside the noise. A default that changes must also hold the **families**, nine scenario sets of up to a thousand runs each (a tank under a shell, a raid on a guarded base), each with a floor of its own.

### C. The guards on a promotion, redesigned today

In auto mode orrery commits a winning candidate to the game by itself. Two guards now stand in front of that commit.

- **The trade guard** holds a candidate that wins by doing less of what the game needs: one whose team gives up more building, or more road, than a tenth of what the other teams build or lay is held even if it scores more. The tenth is a share of the other teams' own numbers, so it means the same on every map.

- **The gauntlet guard** (section 143, today) reads each candidate on all 22 gauntlets<sup>9</sup> with its own dials, and holds it if any file falls under its floor. The promotion job reads the batch again just before it commits.

> **Note 9.** **Gauntlet.** A file of one decision, set up so the right answer is plain: an enemy in reach (fire), a shell landing on you (move), a hostile pillbox and a neutral one (shoot the first, spare the second). Each is played on the same 200 seeds by every brain, and the share passed is compared with the file's *floor*.

The floors themselves were reset today to **today's success**: each is the rules' share on 200 seeds less two standard errors of a hundred, rounded down to the twentieth, and never lowered. A generation that falls under one has stepped back; every generation above all of them is a step forward. Paul's words: "adjust the floors to be what we have now as success, so we can create generations from here forwards."

### D. The GPU growth step

On each graphics card, crucible keeps a population of networks of 55 inputs, two hidden layers of 48 and 4 outputs<sup>10</sup>. Each generation, every network duels sparring partners and milestones in an arena with pillars and four neutral pillboxes, under the game's own numbers (reload, range, damage, speed); the best quarter breed the next generation, each child its parent plus a little gaussian noise. This is neuroevolution: no gradients, only selection [1], [2], [3].

> **Note 10.** **55-48-48-4, tanh.** 55 numbers in, two layers of 48 units, 4 numbers out: turn, speed, fire, and the gate. Every unit uses the hyperbolic tangent, a curve that maps any sum into −1 to 1. Large sums sit near ±1, "saturated", which is why the film's squares are often fully lit [13]. 5,236 weights in all.

A champion the ladder judges better than every one before it becomes a milestone; fifteen exist. Three things now follow a milestone automatically. The **bridge** reads it in the real game as the Gladiator, in a census against the one shipped, and ships it if it reads better. The **montage** films the milestones every five. And the **clone** stage records the rules, trains an imitation of them on the graphics card<sup>11</sup>, and judges it by census and gauntlet before it can replace the Scholar. Its first round (clone −42.71 a seat against the Scholar's −39.93) did not ship.

> **Note 11.** **Behaviour cloning.** Training a network to do what an expert did, from recordings of the expert: a supervised problem, each recorded situation labelled with the expert's choice [4]. Its known weakness is drift: a clone that strays where the expert never went has never seen what to do there [5].

### E. Today's changes to the brains

*Table I. The brain's lab report, sections 138 to 146 (4 November 2026)*

| LR | Change | Measured | Outcome |
| --- | --- | --- | --- |
| 138 | The Gladiator: crucible's world champion read in the game with its 20 world senses | +4.99 ± 2.08 a seat over the Duelist, every map | shipped as style 17 |
| 139 | The score counts building: repair, wood near the base, pillbox life, turret survival and kill rate, guns ready | the far read restarted on the new score | committed |
| 140 | `duel_gate`: how readily the Gladiator's gate opens | 0.6 against 0: +0.08 ± 0.40, 400 seeds | default stays 0 |
| 141 | Five boundary gauntlets: which pillbox to shoot, which tank to answer, kite or stand | the rules 0% to 56% | floors at today's success |
| 142 | `w_shooter`: answer the tank that shot you first | G20 44% to 72%; census −0.57 ± 0.77 | default 2 |
| 143 | The gauntlet guards every promotion | today's rules hold all 22 floors | built |
| 144 | G18 and G19 corrected: a pillbox stood on the ring's edge from a rounding | the rules pass both 200 of 200 | floors 0.95 |
| 145 | `kite_in_alone`: alone, the step in stays shallow | G21 24.5% to 35.5%, paired +8.3 ± 2.6; census −1.12 ± 0.92 | default 6 |
| 146 | The ring as a sense for the nets | harmless; no help to imitation; G7 −9.9 ± 4.4 | parked, not on main |

Two of the nine did not do what was hoped, and the table says so. Section 145 also tried two designs before the one it kept: a duck from an evenly loaded gun (no effect, because a tank sees exactly as far as a gun reaches, ten tiles, so a gun is first seen inside its own reach) and holding the mortar while kiting (worse, because the mortar's splash hits counted for a third of what the rules gave). Section 146 found that the nets' failure on G18 was one of experience, not of eyes: a net that has imitated the rules where G18's choice comes up passes it every time without the new sense.

## IV. Recordings: from storage hog to debug and cleanup

To train a net by imitation, the fleet records the rules playing: at each decision, the 160 senses and the seven choices, a few hundred bytes a sample, millions of samples a run<sup>12</sup>. By the morning of 4 November one machine, calber, held 114.5 GB of them and another 18.9 GB. Nothing read most of them twice.

> **Note 12.** **A shard.** One file of recorded samples, named by its first seed (format TCBC3: a 16-byte header with the number of senses and heads, then fixed-size records). A run is a folder of shards.

The redesign rests on determinism. A shard is a function of two things: the program that made it and the seeds it played. So orrery now keeps a **recipe** for each run (the program's build, its seeds, and the SHA-256 hash of every shard), proves the recipe by making one shard of each program again and comparing it byte for byte, and only then deletes the shards. Any shard can be made again, exactly, from its recipe. Recording itself happens only when a clone round needs it.

- Recordings are **dropped by default** once their recipe is proved; a run marked *keep* (or the global setting `keep_recordings`) stays for debugging.

- A **sweep** every six hours drops what is complete and unmarked.

- A **reader** opens one seed of one run, remaking its shard from the recipe if it was dropped, and follows each tank through it.

- Builds of the game are **pruned** when main moves, except those a recipe still needs.

The result: calber's fleet folder went from 114.5 GB to 6.5 GB, two recording runs worth 87.5 GB were dropped with proved recipes, and the first build prune freed another 45.3 GB. Section VI shows the Recordings page (Fig. 24).

## V. The montage: a film of the generations

The montage answers a plain question: what does a better generation look like? It films each milestone's champion in the moments that decide a duel, and since today it shows what the champion's network was doing in those moments.

[The film](visual/montage.mp4)

***Fig. 2.** Montage 3: the whole ladder, twelve chapters from M0001 to the newest champion, 99 s, 4.2 MB, made in 233 s by one press. The same file is in `output/` with a description ready for upload.*

### A. What a chapter is

Each chapter is one milestone. Its champion plays 64 duels in **one arena from one start**: the same pillars, the same four pillboxes, the same places for both tanks, drawn once from a seed. Only the opponent changes with the duel's number: half are sparring partners of five styles (a script, a Raider, a Castle, an Expander, a Timid tank), half are milestones spread along the ladder. Duel 17 is the same contest in every chapter, so the film compares like with like<sup>13</sup>.

> **Note 13.** **Controlled comparison.** The film holds everything fixed but the champion: the arena, the start, the opponents and their dice. Any difference between chapters is then the champion's doing, the same reasoning as the paired census in Section III.

The camera follows the duel the champion won best. It cuts each kill shot and each pillbox fight from one second before to half a second after, at three frames a step (a step is 0.1 s of game time, so the film runs at real speed). When the generation changes, a title holds the upper right for a quarter of a second. Between chapters, orrery's own pages tell the story: the flowchart of Fig. 15, the Growth page with the chapter's generation marked, and its facts in large type.

### B. The crowd: every other duel, faded

Paul asked for "a crowd of tanks on the same map because the pill boxes don't move ... enemy ghost tanks ... a faded overlay with same camera movement to make it align." Because every duel shares the arena, all 64 can be drawn on one map at the same step. The followed duel is drawn solid; every other duel's champion (blue) and opponent (red) are drawn as faded tanks with a short track behind them<sup>14</sup>. They use the followed tank's camera, so the crowd moves with the shot. A duel that has already ended keeps its tanks where they stopped, fading out over three seconds. In the first film the crowd had mostly vanished by the time of a kill shot, because by then most duels were over; it no longer empties.

> **Note 14.** **A pre-blended fade.** True transparency mixes each pixel with what is under it, which costs a multiply per pixel per ghost. Over a field of one colour the mix is known in advance, so each ghost is painted in its colour already mixed with the grass at 36%: the field itself is the mask. It costs nothing extra, at the price of ghosts that do not darken where they overlap.

Two smaller changes came from looking at the film. The camera now frames the fight, aiming a third of the way from the champion toward a living foe within 16 tiles, and may look six tiles past a wall. Before that, a kill shot by the north wall put the champion under the caption and its foe under the generation.

### C. The mind in the corners

The champion's network is drawn in three corners of every clip frame, and the generation in the fourth. Fig. 3 is a real frame; point at a corner, or tab to it, to read what it shows.

![A frame of the film: the followed champion and its foe in the middle, faded tanks of other duels around them, the inputs top left, the transform bottom left, the decisions bottom right, the generation and the arena's map top right](visual/montage-clip.png)

***Fig. 3.** A frame of the film with its regions marked. Every number drawn in it comes from the trace of the duel; nothing is interpolated but the tanks' positions between two steps.*

How the corners are made. Crucible's trace (the file the film is cut from) gained a version 2 today: at every step of every duel it records the 55 numbers the champion's network read and the 4 it drove with. The two hidden layers are not stored. The film computes them again from the champion's own 5,236 weights, using crucible's own forward pass, layer by layer, with the same tanh<sup>15</sup>. Because that computation is exact, the corners show the network as it was, not an approximation.

> **Note 15.** **The forward pass.** For each unit of a layer: multiply each input by its weight, add them and a bias, and take tanh of the sum. Three layers of that turn 55 inputs into 4 outputs. With the weights and the inputs known, anyone can repeat it and get the same numbers.

The lines in the transform are the strongest *currents* of the step: for every connection, its weight times the activity of the unit it starts from, the part that unit contributed to the next one's sum. The 28 strongest from the first layer to the second and the 14 strongest from the second layer to the outputs are drawn, brighter for stronger. This is a simple form of attribution<sup>16</sup>: it shows which paths carried the decision, not why the weights are what they are.

> **Note 16.** **Attribution, and its limits.** "Weight times activation" is the first-order share of a unit in the next sum, the idea behind many saliency methods [9], [10]. It ignores what the squashing curve does afterwards and how paths combine, so it is a guide to the eye, not a proof of what the network "thinks."

Older champions are drawn too. The first milestones are of the old arena's smaller network; the film widens them into the new shape exactly as crucible does, every new weight zero, so their answers are unchanged and the units they never had stay black.

### D. The decision spectrogram

Paul asked for "a history of decisions like a spectrogram of fire, from a bright square display." A spectrogram<sup>17</sup> draws time across and channels down, with brightness for strength. Here the channels are the tank's turn, its speed, its fire, the network's own say (its gate output), and a row of shots. Eight seconds are shown, a column a step, the newest at the right. A glance shows when the champion committed to an attack (speed and fire lit together), when it handed the wheel back to the rules (the gate turns amber), and where its shells landed.

> **Note 17.** **Spectrogram.** In sound, a picture of frequency against time, brightness for loudness [14]. The name is borrowed for any picture of channels against time; orrery already uses one for how each champion's middle layer changes across generations (Fig. 27).

### E. Play it here

Fig. 4 is the same animation, running in this page from the film's own data (three of its twelve chapters, 133 KB). Press Play, pick a chapter, or drag the step. Point at any square to name it: an input gets its meaning and value, a hidden unit lights its own currents in white.

*(The Mind explorer runs in the HTML version.)*

***Fig. 4.** The Mind explorer. It opens paused on the first step whose shell hit. Colours as in the film: green positive, amber negative, black zero, brightness the size.*

### F. The title sequence

The film opens on treadcore.org's own look (Fig. 5): the battlefield behind a dark veil and scanlines, a brushed-metal plate with four screws, the name etched into it, an eyebrow label above, a phosphor screen that types what the film holds, and the game's newswire along the foot. It is drawn with ImageMagick [19] from the site's own colours (`site.css`), 36 frames typed at ten a second and faded in, 3.6 s. A card follows that names the four corners on a real frame (Fig. 6).

![The title sequence: a brushed-metal plate with four screws, the name Treadcore etched, and a phosphor screen typing the film's generations](visual/montage-title.png)
***Fig. 5.** The title sequence, in treadcore.org's metal and phosphor.*

![A card titled How to read the film, with a labelled frame and one line for each corner](visual/montage-how.png)
***Fig. 6.** How to read the film: the corners named on a real frame.*

![A chapter card: the generation in large type, orrery's Growth page with the generation marked, and the champion's facts](visual/montage-chapter.png)
***Fig. 7.** A chapter opens on orrery's Growth page with its generation marked, and its facts in 32-point type.*

![The closing card: every chapter's wins, losses and draws from the same start](visual/montage-end.png)
***Fig. 8.** The closing card: every chapter's 64 duels, won, lost and drawn.*

### G. Scripted, and placed in the output folder

The whole film is one command, or one press of *Make montage* on orrery's Montage page:

```
python3 tools/montage.py ~/code/treadcore/build/queue/grove make            # the generations since the last film
python3 tools/montage.py ~/code/treadcore/build/queue/grove make --since start  # the whole ladder again
```

It traces the chapters on whichever GPU island answers, renders every frame in plain Python, joins the pieces with FFmpeg [18], and writes three places: the archive (`archive/montages/NNNN/`: the film, its summary, its mind), orrery's Montage page, and the **output folder**, `orrery/output/` (or `ORRERY_OUTPUT`), where `treadcore-montage-NNNN.mp4` sits beside a `.txt` with a title, a description and a timestamp for every chapter, ready to paste into a video site. The trace and the frames are deleted when the film is made; git ignores the output folder.

```
Treadcore: crucible montage 3, generations 200 to 247,700

Champions of crucible's GPU islands, trained by neuroevolution under treadcore's rules, each playing 64 duels from one start. The camera follows the duel each won best; the faded tanks are the other duels at the same moment. In the corners, the champion's net thinking: its inputs, its two hidden layers with the strongest currents lit, its decisions over the last eight seconds, and the generation.

0:00 Title
0:03 How to read the film
0:09 The flowchart
0:19 Generation 200 (M0001)
0:25 Generation 235,800 (M0002)
0:30 Generation 236,600 (M0004)
0:36 Generation 162,500 (M0005)
0:42 Generation 237,000 (M0006)
0:49 Generation 85,900 (M0008)
0:55 Generation 238,100 (M0009)
1:03 Generation 238,700 (M0011)
1:09 Generation 239,000 (M0012)
1:15 Generation 239,200 (M0013)
1:21 Generation 241,300 (M0015)
1:27 Generation 247,700 (the newest)
1:33 Every chapter's duels

MIT licensed: https://treadcore.org  Made by orrery (tools/montage.py) on 2026-11-04.
```

Since the evening of 4 November the finished films have their own page in orrery, Results, Videos (Fig. 9): a list with data, not a player, as Paul asked ("its just a list with data, not a player"). Each film in the output folder is a row with when it was made, its length, its size, its chapters and the generations it covers; the one chosen shows its title, its description and its chapter marks, the lines to paste when it is posted to a video site, and where the file and its text are. *Open* plays it in the machine's own player and *Show* finds it in the file browser. The page never plays or moves a file itself, and offers only a plain file name to the command behind the buttons, since that command passes through a shell.

![Orrery's Results, Videos page: the films in the output folder as rows with their date, length, size, chapters and generations, and the chosen film's title, description, file paths and chapter marks](visual/orrery-results-17-videos.png)
***Fig. 9.** Results, Videos: the films ready to post, their data, and the chosen one's description and chapter marks.*

### H. Inside orrery: the Mind player

The animation does not need the film. Each film now has a `mind.json` beside it, every step of every clip with its inputs, layers, outputs, shots and currents (0.55 MB). The Montage page draws the corners from it natively, in orrery's own renderer at its six frames a second, paced by the wall clock so a step still lasts 0.1 s (Fig. 10). It has *Play mind*, *Pause* and chapter buttons, and when paused it rests on the first step whose shell hit.

![Orrery's Montage page: the Mind player drawn above the list of films, with the chosen film's chapters and their wins at the right](visual/orrery-results-16-montage.png)
***Fig. 10.** Results, Montage in orrery: the Mind player above the films, each chapter's wins, losses and draws at the right.*

A recording of the game itself (Section IV) does not yet carry these overlays: the game's nets are a different network from crucible's, and the game's own window does not yet draw them. Section IX lists this as not built.

## VI. A tour of orrery, every screen

Orrery is one window with seven tabs along the top (Machines, Projects, Queue, Results, Watch, Fleet, Settings), a list of pages down the left, and a line under the tabs, *About this screen*, that says what each page is for. It is written in Rust with no third-party libraries: it draws every pixel itself, letters included, and redraws the whole window six times a second<sup>18</sup>. Every picture here was drawn by orrery's own `--frame` renderer from the live queue at about 15:40 on 4 November, the same code that draws the window, so the pictures are the window. The steel frame is treadcore's brushed metal; the screens inside are its phosphor.

> **Note 18.** **Immediate-mode interface.** Instead of keeping a tree of widgets and updating it, the program draws the whole screen from its data every frame. It is simple and cannot show stale state, and it is cheap here because the screen is rectangles and 8-by-13 letters: a full frame takes well under a millisecond.

### A. Machines, Projects and Queue: the fleet at work

![Machines: every computer in the fleet with its system, and the recipes that make a new one a fleet node](visual/orrery-machines.png)
***Fig. 11.** Machines. Every computer the fleet knows, with its system, processor, graphics card and disk, and the recipes that turn a fresh install into a fleet node (probe it, apply a recipe, join it). The Mac at the top coordinates: it runs the keeper and pushes.*

![Projects: treadcore on the processors and crucible on the graphics cards, each machine's share, and crucible's ladder of milestones](visual/orrery-projects.png)
***Fig. 12.** Projects. Two projects share the fleet: treadcore on the processors, crucible on the graphics cards. Each machine's row shows what each project is doing on it; the strip at the foot is crucible's ladder of milestones.*

![Queue: jobs queued, running, done and failed, and each machine with its current job](visual/orrery-queue.png)
***Fig. 13.** Queue, Fleet. The queue at a glance (20 queued, 11 running, 24,317 done) and each machine with the job it holds now, a census pair, a held-out read, or a crucible island.*

![Queue, Runs: the kinds of run an operator can ask for, and the recent runs with their states](visual/orrery-queue-1-runs.png)
***Fig. 14.** Queue, Runs. The kinds of run a person can ask for (search, tune, census, parts, switches, record, gauntlet, families, promote) and the newest runs, failures in red with their reason.*

![The flowchart: the stages a trial passes through, from a proposal to the line, with counts at each stage and one real trial traced](visual/orrery-pipeline.png)
***Fig. 15.** Queue, Flow: the flowchart of Fig. 1 as the fleet runs it, with the count at each stage (proposed, first read on 55 seeds, read again on 400, held out, families, tests, promoted) and one real trial traced through it. The montage opens on this page.*

### B. Results: what the search found

Results is where the search reports. Its first line is the same on every page: the candidates found, how many are on today's defaults, the improvements so far, and whether auto mode is on. Its Videos and Montage pages are in Section V (Figs. 9 and 10).

![Candidates: trials past both held-out reads, and the promotions with their outcomes](visual/orrery-results-0-fleet.png)
***Fig. 16.** Candidates. Trials that passed both held-out reads, newest first, and the promotions above them. A failed promotion is red, with the test or guard that stopped it.*

![Found: improvements by variable and by machine, as bars](visual/orrery-results-2-found.png)
***Fig. 17.** Found. The 1,110 improvements by the dial they changed and the machine that found them; the list at the right is the newest changes with their sizes.*

![Net: the learned tank's weights drawn as three images, and how much each sense group and each head matters](visual/orrery-results-3-net.png)
***Fig. 18.** Net. The shipped net's weights as three pictures, one a layer, red for negative and green for positive; under them, how much the net listens to each group of senses and how often each head agrees with the rules.*

![Flags: what needs attention, each with an acknowledge button](visual/orrery-results-4-flags.png)
***Fig. 19.** Flags. What needs a person: a montage ready, a disk over its limit, a promotion paused. Each is acknowledged here.*

![Personas: the roster of seventeen styles, what each plays, its dials and its last census read](visual/orrery-results-10-personas.png)
***Fig. 20.** Personas. The roster of styles (Raider, Castle, Expander, Timid, Scholar, Duelist, Gladiator and the rest): what each plays, its dials against today's defaults, and its last census read.*

![Gauntlet: a row per single-decision test and a column per brain, the share passed, red under the file's floor](visual/orrery-results-12-gauntlet.png)
***Fig. 21.** Gauntlet. A row a test, a column a brain, the share of 200 seeds passed, red under the file's floor. This is the fleet's last gauntlet record, from 3 November at 19:51, before today's five new files; the next fleet gauntlet adds G18 to G22.*

![Nets: every learned net the fleet made or keeps, as cards with where each has been and what read it](visual/orrery-results-13-nets.png)
***Fig. 22.** Nets. Every learned net the fleet made or keeps, one card each: where it has been, what read it, its weights in miniature, its notes. Copies are made only on request.*

![Growth: crucible's islands over their generations: best and mean fitness, yardstick win share, exam, senses shares, pillbox damage, hit rate; and the fleet's disk use](visual/orrery-results-14-growth.png)
***Fig. 23.** Growth. Crucible's three islands over their generations: best and mean fitness, the share won against a fixed scripted yardstick, an exam on held-out duels, how much the champion listens to its world senses and to the rules, pillbox damage, hit rate. Below, what each machine's generations cost in disk, red over 20 GB.*

![Recordings: each recording run's size, recipe, and who reads it, with keep, drop and re-record, and a seed read a tank at a time](visual/orrery-results-15-recordings.png)
***Fig. 24.** Recordings (Section IV). Each run's size on its store, whether its recipe is proved, and who reads it; keep, drop, re-record; and one seed opened a tank at a time.*

### C. Algorhythm: the brain as a patch, and six ways to look inside it

Algorhythm is a set of tabs for reading the brain as a whole: its dials and switches, and the shape of the search around it<sup>19</sup>.

> **Note 19.** **Why look inside at all.** A census says whether a brain is better, not why. These views suggest where to look next; only a census proves a change. The house rule is printed on the Terrain tab itself.

![Algorhythm, Patch: the brain's genes, dials, switches and transforms, as a synthesizer's patch](visual/orrery-algorhythm-0-patch.png)
***Fig. 25.** Patch. The brain drawn as a synthesizer's patch, in order: what it senses, 142 weighted dials (29 moved by training), 15 choices and 18 on-off switches, the rules, a transform of 7 slots that learned nets fill on top of the rules (a residual patch [11]), and the move. Before a dial is turned it is one of 10<sup>14.8</sup> programs.*

![Algorhythm, Terrain: the census results as a landscape over two dials, with peaks marked](visual/orrery-algorhythm-1-terrain.png)
***Fig. 26.** Terrain. Past census reads drawn as a landscape over two dials at a time<sup>20</sup>, today's defaults marked, local peaks numbered with their heights and errors.*

![Algorhythm, Spectrum: a spectrogram of each champion's middle layer, a column a champion, oldest at the left](visual/orrery-algorhythm-2-spectrum.png)
***Fig. 27.** Spectrum. Each crucible champion's middle layer as a column of singular values, strongest at the top, oldest at the left: how the networks' structure changed over 4,822 champions. Right: their total size and distance from where they began.*

![Algorhythm, Matrices: the singular values of each weight matrix and a heat map of what each group of senses reaches](visual/orrery-algorhythm-3-matrices.png)
***Fig. 28.** Matrices. Each of the shipped net's weight matrices read by its singular values<sup>21</sup> (how many directions it really uses), and which sense groups reach which heads.*

![Algorhythm, Senses: the net's listening drawn as the tank's own compass](visual/orrery-algorhythm-4-senses.png)
***Fig. 29.** Senses. How hard the net listens to each sense, drawn as the tank's own compass of eight sectors, brighter for stronger; the body, instruments and contacts listed beside it.*

![Algorhythm, Fleet: the planner's orchestration drawn as a diagram of stages and machines](visual/orrery-algorhythm-5-fleet.png)
***Fig. 30.** Fleet. The planner's orchestration as a diagram: proposals, first reads, held-out reads, families and tests, the transforms trained on the GPU, and where each machine is in it.*

![Algorhythm, Temper: the temperament matrix, how waves of mood raise or calm engage, press, retreat and trigger](visual/orrery-algorhythm-6-temper.png)
***Fig. 31.** Temper. The temperament matrix: slow waves that rouse or calm a tank's engage, press, retreat and trigger, and what each row did in measured plays (seconds in a fight, kills, deaths).*

> **Note 20.** **A terrain from scattered reads.** Each census read is a point: two dial values and a score. A smooth surface through them is estimated by kernel regression [15], a weighted average of nearby reads, closer reads weighing more. It shrinks heights where reads are few, which is why the page will not call a peak real without a census.

> **Note 21.** **Singular values and stable rank.** Any matrix can be written as a sum of simple layers, each with a strength, its singular value. If a few are large and the rest small, the matrix uses few directions. The stable rank, the sum of the squared values over the largest squared, counts them roughly; the film's chapter cards show it, about 10 of 48 for today's champions.

### D. Watch, Fleet, Storage and Settings

![Watch, Sessions: a live terminal of a machine, its processors and processes, kept alive in tmux](visual/orrery-watch-sessions.png)
***Fig. 32.** Watch, Sessions. A terminal for each machine, kept alive in tmux; here this Mac's processors and processes. Click a tile to type into it.*

![Fleet: the certificate authority, each machine's certificate and listener, and the verbs the fleet can run on a machine](visual/orrery-fleet.png)
***Fig. 33.** Fleet. The fleet's own certificate authority<sup>22</sup> (7 of 9 machines listening), each machine's system, load, treadcore commit and certificate, and the verbs a machine answers: message, clip, chat, shot, save, run, scene, power.*

![Storage: the fleet's disks and shares, each machine's free space and the network shares between them](visual/orrery-storage.png)
***Fig. 34.** Storage. Each machine's disks and free space, and the network shares between them; a share is made or removed here.*

![Settings, Keeper: is the keeper running as it should, its code, its planning and its lanes](visual/orrery-settings.png)
***Fig. 35.** Settings, Keeper. Is the keeper (the program that keeps every machine busy) running as it should: its code, its last plan, its lanes, and the one thing that wants a look, here a difficulty the planner raised.*

![Settings, Ranges: every number's limits, the decrees, and the reason beside each](visual/orrery-settings-11-ranges.png)
***Fig. 36.** Settings, Ranges. Every dial's limits with the reason beside it. A dial whose minimum equals its maximum is a decree, a constant only Paul may set.*

![Settings, Commits: the line the fleet builds, newest first, with the defaults each commit changed](visual/orrery-settings-7-commits.png)
***Fig. 37.** Settings, Commits. The line of commits the fleet builds, newest first (today's LR 145 at the top), each with the defaults it changed; a row opens it on GitHub.*

![Settings, Long run: what repeats over many generations, its options and what it last found](visual/orrery-settings-9-longrun.png)
***Fig. 38.** Settings, Long run. What repeats over many generations and what it last found (here, 222 of 252 far trials left on game 8+score1), with its options: how far the fit looks back, the share of each top-up that looks far, and how often the temperament and the net's width are read.*

> **Note 22.** **A fleet certificate authority.** The console signs each machine's key with its own authority, so machines and console can prove who they are to each other without passwords, the way SSH certificates work.

## VII. A tour of treadcore, the game

The game's pictures were taken on a virtual machine running the game in a real window, software-rendered, from main at commit `0e10d4a` (today's LR 145). The match is the window's default: the naval map, three teams, fifteen bots, three respawns. The player's tank is on autopilot, so the rules drive it; what the pictures show is the brain at work<sup>23</sup>.

> **Note 23.** **Autopilot.** The O key hands the player's tank to the same rules that drive the bots, with the player's goal. Everything the coordination screen shows is that brain's own account of what it is doing.

![The game in play: the island map with tanks, pillboxes and depots; the build orders on the left; the tank's shells, drones, squad, armour and fuel on the right; the newswire at the foot](visual/treadcore-01-play-start.png)
***Fig. 39.** In play. Top: seat, team, tick, game time, the field's scale and the goal. Left: the orders, each with its key. Right, in brushed metal: the autopilot lamp, shells, the drone bay (recon, strike, longshot, interceptors), the squad and its material, armour and fuel, kills, pillboxes, depots, works, and the map. Foot: the air line and the newswire.*

![The game later in the match: a fleet sailing in formation between islands, rings of reach around tanks and pillboxes](visual/treadcore-02-play-fight.png)
***Fig. 40.** Island hopping. The player's wingmen sail in formation; each ring is a reach: a gun's, a drone's, a pillbox's. The newswire reports a bot boarding a boat.*

![The coordination screen: the ladder of rungs, the rotation, and every ally's errand in words](visual/treadcore-03-coordination.png)
***Fig. 41.** Coordination (Space). The brain explains itself: the ladder of rungs (defend the base, fortify, turrets, hunt, expand, guard), the first one whose condition holds being what the tank does; the rotation between defence and push; and each ally's errand in words.*

![The team's weights page: the switches of the team's bots, on or off](visual/treadcore-04-sliders.png)
***Fig. 42.** Weights (U, from coordination). The team's switches, on or off: pings, dodge, bridges, rotate, duck, posture and the rest. They are the same dials and switches the fleet searches; a person can set them for their own side.*

![Key setup over the map: every action in groups with its key](visual/treadcore-05-key-setup.png)
***Fig. 43.** Key Setup (K). Every action in groups with its key; a key moved onto an action that had one swaps with it, so every action keeps exactly one.*

![Later in the match: tanks massed on an island around a depot, a pillbox's ring and shells in the air](visual/treadcore-06-play-later.png)
***Fig. 44.** A fight for an island. Tanks of two sides massed around a depot; the newswire's line at the foot is a refusal: "PEBKAC: airspace full (the lamps called it)".*

![The game after the goal key: the tank's goal shown in the top line](visual/treadcore-07-goal.png)
***Fig. 45.** Goals (G). G steps through the goals (auto, hunt pillboxes, defend a depot or the base, hold, fortify, escort, the wheel); the top line names the one in force.*

![Late in the match: a strike on a depot, lines of fire converging](visual/treadcore-08-play-late.png)
***Fig. 46.** Late in the match: lines of fire converge on a depot, and a wingman reports "slugs out, grunts ready: hitting the depot."*

The game's window does not yet draw the mind of a net-driven tank. The rules, which drove every tank above, explain themselves in words on the coordination screen instead (Fig. 41), the counterpart of the film's corners for a hand-written brain.

## VIII. Measurements

*Table II. The visual work of 4 November, measured*

| What | Measured | Note |
| --- | --- | --- |
| The film | 99 s, 12 chapters, 1,152 clip frames, 4.2 MB | H.264, 1280 by 720, 30 frames a second |
| Making it | 233 s from one press | a trace on a GPU island, then frames in Python on the Mac |
| A frame with the corners | about 37 ms | three frames in 0.11 s; the corners cost almost nothing |
| The trace, version 2 | about 299 MB for 12 chapters | 81 floats a step against 22; deleted once the film is made |
| The mind file | 0.55 MB | kept beside the film for orrery's Mind player |
| The title sequence | 36 frames, 3.6 s | ImageMagick, in treadcore.org's colours |
| Screens photographed | 30 of orrery, 8 of the game | orrery by its own `--frame`; the game on a virtual machine |
| Recordings on calber | 114.5 GB to 6.5 GB | 87.5 GB dropped with proved recipes; 45.3 GB of old builds pruned |
| G21, the rules alone | 24.5% to 35.5% | paired +8.3 ± 2.6 points over 600 seeds |
| The brain's tests | 165 pass | one new: `alone_the_step_in_stays_shallow` |

*Table III. The film's chapters: 64 duels each, the same start and opponents*

| Milestone | Island | Generation | Won | Lost | Drawn |
| --- | --- | --- | --- | --- | --- |
| M0001 | boburner | 200 | 38 | 0 | 26 |
| M0002 | calber | 235,800 | 2 | 42 | 20 |
| M0004 | calber | 236,600 | 12 | 26 | 26 |
| M0005 | whitewolf | 162,500 | 38 | 0 | 26 |
| M0006 | calber | 237,000 | 38 | 0 | 26 |
| M0008 | boburner | 85,900 | 39 | 0 | 25 |
| M0009 | calber | 238,100 | 42 | 7 | 15 |
| M0011 | calber | 238,700 | 40 | 0 | 24 |
| M0012 | calber | 239,000 | 32 | 0 | 32 |
| M0013 | calber | 239,200 | 32 | 0 | 32 |
| M0015 | calber | 241,300 | 40 | 0 | 24 |
| the newest | calber | 247,700 | 39 | 0 | 25 |

Two readings of Table III, both cautious. The generations are counted on each island separately, so they do not rise in ladder order. And the early hybrid champions win as often as the latest ones (M0001, of the old arena's net, wins 38 of 64) because a hybrid with its gate mostly shut plays the rules' script, which beats sparring partners; the film shows how a champion fights, while the ladder, which judges champions against each other, decides which is better.

## IX. Limitations, and what is not built

- **The game does not draw the mind.** The corners exist in the film and in orrery for crucible's champions. The game's own nets (160 senses, seven heads) are a different network, and the game's window has no overlay for them yet. The Gladiator, which drives crucible's champion inside the game, is the natural first candidate.

- **The game's recordings carry no overlays.** Section IV's recordings are training data, not film. A recording that also carried a net's layers would be larger again; the film's own trace carries them and is deleted after use.

- **The fade is pre-blended.** Ghosts are mixed with the grass's colour, so where two overlap the nearer one wins instead of both darkening.

- **The currents are first-order.** Weight times activation shows where a decision flowed, not why; it ignores the tanh after each sum.

- **Video-site chapters.** The output's chapter list is correct, but most chapters are about six seconds long, and a video site that requires ten seconds a chapter will show the list as text rather than as chapters.

- **The Gauntlet page lags the files.** It shows the fleet's last gauntlet job (3 November, 17 files); today's five appear when the fleet runs the next one.

- **The ring sense is parked.** It is proved harmless and was not shown to help imitation; G19's result swings from 0 to 172 of 200 with the training run's random start alone, which is the next problem to solve.

- **Committed.** Everything in Section V is on the main lines: orrery `d9892ba` and `2b5ad05` (the Videos page), crucible `e09089a` (which has no remote), treadcore `5b2f7c7` (section 146). The ring sense itself is kept off main, in a stash.

## X. Conclusion

A system that learns by measurement produces a great deal of evidence and very little to look at. Today it gained three ways to look. The film now shows what a generation does and what its network did while doing it: the crowd of its other duels, its inputs, its two hidden layers with their strongest currents, and its decisions in an eight-second spectrogram. Orrery plays the same animation without the film, and this page lets a reader point at any square and be told what it is. Following Tufte's advice to show the data and nothing that is not the data [7], every mark in the corners is a number from the trace or an exact recomputation from the champion's weights.

The pictures do not replace the measurements. The day's brain work shows why: of nine changes, two did not do what was hoped, and both were caught by a rule written before the run, not by a picture. What the pictures add is a way to see where to look next, and to show someone new, in a minute and a half, what the fleet has been doing.

## Acknowledgment

The fleet's machines, the islands' graphics cards, and the virtual machine that ran the game's window did the work in this report. The game's look on the web, which the title sequence borrows, is treadcore.org's.

## References

- T. Salimans, J. Ho, X. Chen, S. Sidor, and I. Sutskever, "Evolution strategies as a scalable alternative to reinforcement learning," arXiv:1703.03864, 2017.

- F. P. Such, V. Madhavan, E. Conti, J. Lehman, K. O. Stanley, and J. Clune, "Deep neuroevolution: Genetic algorithms are a competitive alternative for training deep neural networks for reinforcement learning," arXiv:1712.06567, 2017.

- K. O. Stanley and R. Miikkulainen, "Evolving neural networks through augmenting topologies," *Evol. Comput.*, vol. 10, no. 2, pp. 99–127, 2002.

- D. A. Pomerleau, "ALVINN: An autonomous land vehicle in a neural network," in *Adv. Neural Inf. Process. Syst. 1*, 1989, pp. 305–313.

- S. Ross, G. J. Gordon, and J. A. Bagnell, "A reduction of imitation learning and structured prediction to no-regret online learning," in *Proc. AISTATS*, 2011, pp. 627–635.

- F. W. Lanchester, *Aircraft in Warfare: The Dawn of the Fourth Arm*. London, U.K.: Constable, 1916.

- E. R. Tufte, *The Visual Display of Quantitative Information*. Cheshire, CT, USA: Graphics Press, 1983.

- C. Olah, A. Mordvintsev, and L. Schubert, "Feature visualization," *Distill*, 2017.

- M. D. Zeiler and R. Fergus, "Visualizing and understanding convolutional networks," in *Proc. ECCV*, 2014, pp. 818–833.

- K. Simonyan, A. Vedaldi, and A. Zisserman, "Deep inside convolutional networks: Visualising image classification models and saliency maps," arXiv:1312.6034, 2013.

- T. Silver, K. Allen, J. Tenenbaum, and L. Kaelbling, "Residual policy learning," arXiv:1812.06298, 2018.

- K. Hornik, M. Stinchcombe, and H. White, "Multilayer feedforward networks are universal approximators," *Neural Netw.*, vol. 2, no. 5, pp. 359–366, 1989.

- X. Glorot and Y. Bengio, "Understanding the difficulty of training deep feedforward neural networks," in *Proc. AISTATS*, 2010, pp. 249–256.

- A. V. Oppenheim and R. W. Schafer, *Discrete-Time Signal Processing*, 3rd ed. Upper Saddle River, NJ, USA: Pearson, 2010.

- E. A. Nadaraya, "On estimating regression," *Theory Probab. Appl.*, vol. 9, no. 1, pp. 141–142, 1964.

- G. E. P. Box, J. S. Hunter, and W. G. Hunter, *Statistics for Experimenters*, 2nd ed. Hoboken, NJ, USA: Wiley, 2005.

- National Institute of Standards and Technology, "Secure Hash Standard (SHS)," FIPS PUB 180-4, 2015.

- FFmpeg Developers, *FFmpeg*. [Online]. Available: https://ffmpeg.org

- ImageMagick Studio LLC, *ImageMagick*. [Online]. Available: https://imagemagick.org

- J. E. Bresenham, "Algorithm for computer control of a digital plotter," *IBM Syst. J.*, vol. 4, no. 1, pp. 25–30, 1965.

- D. P. Kingma and J. Ba, "Adam: A method for stochastic optimization," in *Proc. ICLR*, 2015.

## Appendix A. The 55 inputs of a world champion

What crucible's world network reads each step (`sense()` in `src/crucible.cu`), in the order the film's top-left corner draws them, eleven to a row. Rays turn with the tank: ray 0 points ahead, each next ray 30 degrees clockwise. A world champion already senses a pillbox's ring (inputs 49 to 52), which the game's own nets did not until section 146 tried it.

*Table IV. The inputs*

| Index | What it reads |
| --- | --- |
| 0 | ray 0 (0 degrees): the nearest wall, pillar or tank on it, 1 touching |
| 1 | ray 0 (0 degrees): the enemy tank, if this ray meets it first |
| 2 | ray 1 (30 degrees): the nearest wall, pillar or tank on it, 1 touching |
| 3 | ray 1 (30 degrees): the enemy tank, if this ray meets it first |
| 4 | ray 2 (60 degrees): the nearest wall, pillar or tank on it, 1 touching |
| 5 | ray 2 (60 degrees): the enemy tank, if this ray meets it first |
| 6 | ray 3 (90 degrees): the nearest wall, pillar or tank on it, 1 touching |
| 7 | ray 3 (90 degrees): the enemy tank, if this ray meets it first |
| 8 | ray 4 (120 degrees): the nearest wall, pillar or tank on it, 1 touching |
| 9 | ray 4 (120 degrees): the enemy tank, if this ray meets it first |
| 10 | ray 5 (150 degrees): the nearest wall, pillar or tank on it, 1 touching |
| 11 | ray 5 (150 degrees): the enemy tank, if this ray meets it first |
| 12 | ray 6 (180 degrees): the nearest wall, pillar or tank on it, 1 touching |
| 13 | ray 6 (180 degrees): the enemy tank, if this ray meets it first |
| 14 | ray 7 (210 degrees): the nearest wall, pillar or tank on it, 1 touching |
| 15 | ray 7 (210 degrees): the enemy tank, if this ray meets it first |
| 16 | ray 8 (240 degrees): the nearest wall, pillar or tank on it, 1 touching |
| 17 | ray 8 (240 degrees): the enemy tank, if this ray meets it first |
| 18 | ray 9 (270 degrees): the nearest wall, pillar or tank on it, 1 touching |
| 19 | ray 9 (270 degrees): the enemy tank, if this ray meets it first |
| 20 | ray 10 (300 degrees): the nearest wall, pillar or tank on it, 1 touching |
| 21 | ray 10 (300 degrees): the enemy tank, if this ray meets it first |
| 22 | ray 11 (330 degrees): the nearest wall, pillar or tank on it, 1 touching |
| 23 | ray 11 (330 degrees): the enemy tank, if this ray meets it first |
| 24 | own speed, a share of top speed |
| 25 | own armour, a share of full |
| 26 | gun loaded (1) or reloading (0) |
| 27 | enemy armour, a share of full |
| 28 | enemy bearing, sine (right is +) |
| 29 | enemy bearing, cosine (ahead is +) |
| 30 | enemy shell near (1 on top of the tank) |
| 31 | bias: always 1 |
| 32 | the rules' answer: turn |
| 33 | the rules' answer: speed |
| 34 | the rules' answer: fire |
| 35 | ray 0 (0 degrees): a live pillbox on it, 1 touching |
| 36 | ray 1 (30 degrees): a live pillbox on it, 1 touching |
| 37 | ray 2 (60 degrees): a live pillbox on it, 1 touching |
| 38 | ray 3 (90 degrees): a live pillbox on it, 1 touching |
| 39 | ray 4 (120 degrees): a live pillbox on it, 1 touching |
| 40 | ray 5 (150 degrees): a live pillbox on it, 1 touching |
| 41 | ray 6 (180 degrees): a live pillbox on it, 1 touching |
| 42 | ray 7 (210 degrees): a live pillbox on it, 1 touching |
| 43 | ray 8 (240 degrees): a live pillbox on it, 1 touching |
| 44 | ray 9 (270 degrees): a live pillbox on it, 1 touching |
| 45 | ray 10 (300 degrees): a live pillbox on it, 1 touching |
| 46 | ray 11 (330 degrees): a live pillbox on it, 1 touching |
| 47 | the nearest live pillbox: bearing, sine |
| 48 | the nearest live pillbox: bearing, cosine |
| 49 | the nearest live pillbox: nearness |
| 50 | the nearest live pillbox: reload (0 = can fire now) |
| 51 | the nearest live pillbox: health |
| 52 | the nearest live pillbox has you (inside its ring, line clear) |
| 53 | shells left, a share of full |
| 54 | own gun's reload, a share |

## Appendix B. Making a film

```
# from orrery's checkout; QUEUE is the planner's queue folder
python3 tools/montage.py QUEUE make                 # the milestones since the last film
python3 tools/montage.py QUEUE make --since start   # the whole ladder
python3 tools/montage.py QUEUE make --chapters 8 --duels 32 --host calber
python3 tools/montage.py QUEUE status               # what it is doing now
ORRERY_OUTPUT=~/Movies python3 tools/montage.py QUEUE make   # put the finished film elsewhere
```

A film writes `archive/montages/NNNN/` (`montage.mp4`, `summary.json` with the chapter marks, `mind.json`, the poster) and `output/treadcore-montage-NNNN.mp4` with its `.txt`. The planner makes one by itself every five new milestones. On orrery's Montage page, *Make montage* does the same, *Play* opens the film in the machine's player, and *Play mind* animates its corners in place.

Paul Richeson, 4 November 2026. MIT licensed, as orrery and treadcore. The pictures are in `docs/visual/`; the film is `docs/visual/montage.mp4` and `output/treadcore-montage-0003.mp4`.
