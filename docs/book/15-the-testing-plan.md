# The testing plan

What the week taught about testing is in chapter 7: write the rule before the run, read the composition and not the total, never pick the best of several first reads, and keep the seeds the judge reads apart from the seeds the learner sees. This chapter turns that into a plan with levels, owners and a schedule, for the game as it is and for what chapters 9 to 14 add. The literature it leans on is the evaluation protocol for learned agents: fixed and disjoint seeds, confidence intervals on everything, and enough runs to say anything at all ([93], [95], [96], [97]).

## The levels

| Level | What it proves | Runs | Bar | Owner |
| --- | --- | --- | --- | --- |
| 1. Unit tests | the simulator's rules and the brain's functions | every commit, on the Mac and on each machine's build | green; and the lint: a brain test may not read a searchable default without naming it | the build |
| 2. Gauntlets | single decisions: twelve now, nine of the tank and three of the wingman | fixed seeds, for the rules, each net, each persona | each file's floor; a persona must pass the tank's nine at the rules' floors | `make gauntlet`, nightly |
| 3. Families | behaviours a census cannot see: nine floors (a raid on a guarded base, a duel in the open, a tank under a shell) | every candidate, on its branch | the floors; a candidate under one does not promote | the planner |
| 4. The census | a brain against today's, 400 seeds, eleven maps, the composition read | every trial, every persona, every shape of net | two held-out reads pooled past z 3; the noise rules; the trade guard's floors | the planner |
| 5. The proof | the line against main, 800 seeds | hourly | z 3, no map under, nothing given up past the floors | the planner |
| 6. Playtests | whether it is fun, feels different, and works for a person | a person, a match each | a written sheet a match | Paul |
| 7. The machine | sixteen bots at 4x in a window; the card's time a step | on a change to the brain's cost | the meter's seat-seconds a think; no frame over its budget | `make debug`, the meter |

## What is new in each level

**Unit tests.** The lint of level 1 is the fix for the week's commonest failure, written as a test of the tests: it reads `source/treadcore-brain/src/*.rs`, finds every test that calls `Settings::default()` or `Tactics::default()`, and requires that the test set each weight it asserts on by name. A test that does not is named in the failure, which is what a pinned test should have been from the start. The physical table of chapter 9 has a test that recomputes the real units from the constants.

**Gauntlets.** The three escort gauntlets of chapter 11 join the nine. A persona's certificate is the census; its fitness to play at all is the gauntlet: a persona that cannot fire at an enemy in reach is not a persona, it is a fault.

**Families.** Two families are wanted that do not exist: a team answering a call (so pings-off can never again be promoted on a census that has no person in it), and a wingman keeping its leader alive against a raid. Each is a scenario file with a floor, written before the run.

**The census.** The composition is read by the guard (built, road, kills less deaths) and should be read for the economy's stocks when they exist (chapter 13). A persona's census asks two more questions: which maps it wins on, and whether its composition matches its name (Rome builds, Assyria shells).

**The proof.** As it is; the one change is that a proof that lands on main writes a line on the Lab Reports page's running table, so the site shows the shipped game's provenance.

**Playtests.** The level the week did not run. A sheet a match, kept in `LAB-REPORT-PLAYTEST.md` as the first playtest's were:

- *Against a persona, blind*: a person plays one match against each of the sixteen in a shuffled order and names the persona at the end; a persona named at chance is not one.
- *With the wingmen*: a person drives a sweep with two wingmen at each stance and says which they would take into a fight; the wingmen's numbers that the person prefers are written beside the search's.
- *The orders*: each fleet message of chapter 14, given once, with what the fleet did written down.
- *The long match*: thirty minutes under the economy's first stage, and whether it had a shape.
- *The network*: two machines, two real routers, the proof goal 6 has owed since October.

Pictures come from the VM as the three reports of 1 November did; a playtest without a picture did not happen.

## The matrix

Sixteen personas by eleven maps by two kinds of opponent (today's defaults, and each other) is 352 cells of 400 seeds, about 140,000 matches: four days of the fleet at its present pace. It is not asked for at once. The order: each persona against the defaults (sixteen reads, a day), then the round robin on three maps (a day), then the rest as the terrain's regions ask for them.

## The schedule

| When | What runs | Where it shows |
| --- | --- | --- |
| every commit | unit tests, the lint | the build; a red Mac does not push |
| every minute | the planner's plan: trials, read-ons, held-out reads, families, promotions | Queue |
| every hour | the proof | the `line` flag; the Lab Reports table |
| every night | the gauntlet, for the rules, every net and every persona | Results → Gauntlet (chapter 14) |
| every twenty generations | the shape watch (chapter 12), the temperament round | Settings → Long run |
| every week | a playtest afternoon: one sheet a match; the register (chapter 8) re-read | `LAB-REPORT-PLAYTEST.md`, this book's next edition |

## What is fixed first, by the data

The analysis of the week's logs says what to fix before any of the above can be believed, in order:

1. The score's blind spots: the guard holds them; the reward for going forward is priced in chapter 13 and waits for Paul.
2. Pinned tests: the lint.
3. The thin terrain: regions pressed on the live fleet, so maxima are read to a verdict.
4. The net that cannot build: a squad head trained before any claim that a net is behind for want of width.
5. The flaky sftp tests: a fixed directory, two tests; not gating, but noise in every run.

## Links

[LAB-REPORT-PLAYTEST.md](https://github.com/treadcore/treadcore/blob/main/documentation/LAB-REPORT-PLAYTEST.md) · [CENSUS.md](https://github.com/treadcore/treadcore/blob/main/documentation/CENSUS.md) · [Generations](../2026-10-27-generations.html) (the gauntlet) · [Promotion Difficulty](../2026-10-29-difficulty.html) · evaluation protocols [90]–[97] · noisy fitness [25]–[32].
