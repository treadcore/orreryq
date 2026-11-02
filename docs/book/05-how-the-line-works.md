# How the line works: the how-to

This is the process as it runs on 2 November, for someone who has to watch it, steer it or restart it. Every number here is a value a person can move from a screen; every state is a flag a person can read. The detail of each stage is in [The Whole Line](../2026-11-01-the-whole-line.html); the screens, pictured, are in the [Double Report](../2026-11-01-double-report.html).

## The idea in one paragraph

A brain is a list of numbers. The fleet proposes small changes to the list, plays each against the shipped list in seeded matches, and keeps the changes that win by more than chance. A change that wins becomes a *generation* on a local *line*. The line is a branch of the game that main has not yet accepted; every hour it is played against main at 800 seeds, and if it is better past z 3 on every map, it becomes main, and every machine builds the new game. Nothing a machine finds reaches a player without that proof, and nothing is thrown away: a pass on old defaults is read again on the new ones.

## The stages

!html(figs/the-funnel.html)

```
 the fit's draws, A/B of switches and choices, the far read, the temperament
 rounds, the width watch, the anchors            ->  a trial (a weights file)
 read on until decided: 55, 110, 220, 440 seeds  ->  dropped, or passed
 two held-out reads, 400 seeds each, pooled      ->  a candidate (z >= 3, no map under)
 the noise rules, the trade guard, the hold      ->  waits, or goes on
 the brain's tests, nine scenario families       ->  a promotion run
 the generation lands on the line                ->  every machine builds it
 the proof: the line against main, 800 seeds     ->  main, past z 3 and no map under
```

1. **Trials.** The planner writes a weights file that differs from today's defaults in one to four numbers. Most come from the *fit*, an inverse-variance model of every read so far that remembers earlier defaults as what they were (the fit's memory). Each generation also tries every switch flipped and every version of every choice (A/B), looks far from today on a few dials, runs a round of the temperament matrix, and every twenty generations trains the transform at another width. An *anchor* re-reads the defaults of three generations ago against today's, to catch drift.
2. **Read on until decided.** A trial plays 55 seeds; if it is not plainly worse it plays on to 110, 220 and 440, and is dropped the moment it falls two errors under. About a tenth survive.
3. **Held out.** A survivor is read twice more on seeds it has never seen, 400 each; the two are pooled. It is a *candidate* at z 3 or better with no map two errors under.
4. **The gates.** A candidate waits if its gain is under a quarter point a seat (MIN_GAIN), if it moves a dial the last two generations already moved and is under z 3 (SETTLE_GENS), if its held-out reads give up more building, road or kills-less-deaths than a floor allows (the trade guard: 1.0 built, 0.5 road, 0.10 a seat), or if it sets a dial to a value a person has held (hold.json). Each wait is a flag that says why.
5. **Tests and families.** The brain's unit tests and the nine scenario families (floors on behaviours a census cannot see, such as a raid on a guarded base) run on the candidate's branch. A test that pinned a default rather than the rule it tests was the week's commonest failure, and they were rewritten.
6. **The generation.** The promotion commits the new defaults to the line, tagged, and every machine builds it. One generation a half hour at most; candidates that pass meanwhile go together as a batch if they move different dials.
7. **The proof.** Hourly, main's values are read as a trial against the line over 800 seeds. Past z 3 with no map two errors under, and giving up nothing past the trade floors, the commit that was read lands on main. Under −2, a flag says the anchors should undo it.

## What a person moves, and where

| Value | Default | Screen | What it does |
| --- | --- | --- | --- |
| ease_now, ease_max | 1.5, 1.5 | Queue → Values | the bars' ease; never under z 1.5 since 1 November |
| min_gain | 0.25 | Values | the floor on a generation's gain, points a seat |
| settle_gens | 2 | Values | a dial moved this recently needs full z 3 to move again |
| give_built, give_road, give_kd | 1.0, 0.5, 0.10 | Values | the trade guard's floors |
| generation_every_min | 30 | Values | the window between generations |
| held_seeds | 400 | Values | seeds in a held-out read; the proof is two of them |
| queue_per_machine | 2 | Values | jobs waiting per machine |
| far_share, memory_tau, memory_drift | | Settings → Long run | the far read and the fit's memory |
| temper_every, temper_share, temper_step | 12, | Long run | the temperament rounds |
| width_every, width_seeds, width_bar | 20, , 1.0 | Long run | the width watch |

Values are written to the queue's `tuning.json` and are live at the next plan, about a minute, with no restart. `hold.json` holds a dial's value by hand; it has no button yet (chapter 8).

## The screens, in the order the work goes

**Machines** (and Storage, Media): each machine, its state, pause, stop, resume, remove, add, errands. **Projects**: treadcore and crucible, on or off per machine. **Queue**: Fleet (lanes and what each runs), Runs (every run asked for and where it is), Board, Flow, Timeline (the Gantt), Queued, Values; then the Pipeline's pages. **Results**: the Algorhythm tabs (Patch, Terrain, Spectrum, Matrices, Senses, Temper, Fleet), the net's pictures, the ledger. **Lab**, **Sessions**, **Fleet** (the listener's buttons: Message, Clip, Save, Shot, one chat room), **Chat**. **Settings**: Keeper (health, restart), Long run, Commits.

## When something is wrong

- **A lane idle with nothing it can start**: health's `lanes` line names it; usually a cap no queued job wants (boburner's card is off for crucible by a setting).
- **Promotions failing in a row**: read the run's log; a test that pins a default the search moved is the usual cause; auto mode pauses only when two different candidates fail alike.
- **The line under main**: the `line` flag; the anchors undo a drift; nothing is removed by hand.
- **Main moved under the Mac**: pull with rebase before pushing; a source commit to main replays the line and rebuilds every machine, and voids a proof in flight, so push source only when no proof runs.
- **The keeper is stale**: it restarts itself when its file changes and nothing running is over ten minutes old; `restart` forces it. The planner runs from disk each minute, so a half-finished edit is live: edit in a copy.

## Links

[The Whole Line](../2026-11-01-the-whole-line.html) · [Double Report](../2026-11-01-double-report.html) · [Promotion Difficulty](../2026-10-29-difficulty.html) · [fleet-train.md](https://github.com/richeson/orrery/blob/main/docs/fleet-train.md) · `tools/plans/line.json`, the one table of values, stages and screens.
