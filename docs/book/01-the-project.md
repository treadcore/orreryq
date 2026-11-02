# The project on one page

Two programs and a room of machines, with one aim: a tank game whose bots play like a side, and a process that makes them better by itself, in a way a person can read, steer and trust.

## The game

Treadcore is an overhead tank game for up to sixteen players on a 128 by 128 tile island, one tile 25 metres. It descends from a 1980s tank game and adds what the war of the last few years handed the tank: the gun fires indirect at a point a recon drone is watching, interceptors hold a ring round the hull and ram what flies in, strike and longshot drones carry the fight past the horizon, and jammers blind everyone's link alike. Each tank carries a squad of four that captures pillboxes, builds walls, roads, bridges and mines, fells trees for material, and can lift a pillbox and carry it home. Depots resupply. Alliances form and break under a three-way rule. The windows find each other on a LAN or across the Internet and elect a host; nobody runs a server. It is Rust, with Bevy for the window; the simulation is deterministic and headless, and everything above it drives it through two calls, `step` and `observe`. The player's guide is [How to Play](https://github.com/treadcore/treadcore/blob/main/documentation/HOW-TO-PLAY.md); the rules and their reasons are [DESIGN.md](https://github.com/treadcore/treadcore/blob/main/documentation/DESIGN.md).

## The two brains

Every seat a person does not take is a bot, and a bot is one of two kinds of mind, or a mix.

**The programmed brain** (the Commander, in `treadcore-brain`) is a ladder of goals a person can also set by hand: defend the base, fortify, hunt pillboxes, expand, guard. Under it sit about 135 named numbers, the *weights*: some are worths that lean a choice, some are shares between 0 and 1, some are distances and times with a meaning in the world, some are whole-number *choices* that pick one of several rewritten versions of a function, and a few are on-off *switches*. A team shares one board (influence, the front, posture, jobs) and plays roles: a leader, a guard, rangers, wingmen, and on a person's team a builder. Eight named *styles* (Fleet, Raider, Castle, Expander, Timid, Overrider, Scholar, Duelist) are whole brains anybody can pick by name and put on a side. The month's record of building it is the [brain's lab report](https://github.com/treadcore/treadcore/blob/main/documentation/LAB-REPORT-BRAIN.md), 126 numbered sections.

**The learned brain** is small on purpose. A tank's senses are 133 numbers (a compass of sectors, the body, the instruments, a periscope's contacts, hints); a net of two hidden layers of 64 reads them and chooses. Beside it sits the *transform*: a few hundred numbers that read the senses, the slow waves of a tank's temperament and the rules' own answer, and may move that answer when confident. All zeros is the brain as it was, so training starts exactly where the rules stand. A GPU arena, crucible, breeds a third kind: duelling champions on islands of a population, whose best plays the fight inside a rules tank on this simulator. The plan for the learned tank is [AI-BRAINZ-PLAN.md](https://github.com/treadcore/treadcore/blob/main/documentation/AI-BRAINZ-PLAN.md); how it is trained, and the parity between CPU and GPU, is [LEARNING-DESIGN.md](https://github.com/treadcore/treadcore/blob/main/documentation/LEARNING-DESIGN.md).

## The instrument

Orrery began as a fleet console with no dependencies: a window drawn by hand on a Mac and on Wayland, SSH, SFTP, TLS and RDP written from the standards, so that a locked-down node on a LAN that never reaches the Internet could be reached, read and commanded. In the last week of October it grew the second half of its job: it holds the orchestration of training. A *keeper* runs a queue; each machine is a lane; a *planner* decides every minute what the lanes should do. The work is a *census*: seeded matches of a trial brain against the shipped one, pooled by inverse variance, and judged against bars written before the run. A trial that passes its reads and two held-out reads becomes a *generation* on a local *line*; the line is proved against the shipped game at 800 seeds, hourly, and goes to main past z 3. Every number of that process a person might want to move is a *value* on a screen; everything a person might need to do is a button; what the machines found is drawn, with hover, on the Results chapter's tabs. The [Double Report](../2026-11-01-double-report.html) is the guide to every screen; [The Whole Line](../2026-11-01-the-whole-line.html) is the process end to end.

## The definition of the design

Paul set the frame on 2 November in six parts, and this book keeps to it:

!html(figs/design-in-six.html)

1. **The design**: the game's rules, the brain's shape, the process. Written, mostly; chapter 2 says where.
2. **The implementation**: the game, the brains, the console. Built and shipped (0.2.0).
3. **Training the programmed brain's weights**: the fleet's censuses, the line, the proof. Running; a week of it is this book's subject.
4. **Training the transform into a learned player**: built, with a first trained transform in a slot; not yet promoted, and the width test said wider is not yet worth it.
5. **Combining the two**: the Overrider style (rules under a transform) and the Duelist (rules with a champion in the fight) exist; the net cannot yet build or crew.
6. **Orrery orchestrating the whole**: dependencies, the order of seeds, promotion, values. Built; its faults were the week's main lesson.

## Where it stands, in one table

| Part | State on 2 November 2026 | Evidence |
| --- | --- | --- |
| The game | 0.2.0 released; game 4's rules (12 s mortar, finite depots, going forward paid) since 30 October | [release](https://github.com/treadcore/treadcore/blob/main/documentation/RELEASE.md), [Too Many Shots](../2026-10-30-balance.html) |
| The programmed brain | 135 weights, 19 switches, 12 choices, 8 styles; every part on by default | [brain report](https://github.com/treadcore/treadcore/blob/main/documentation/LAB-REPORT-BRAIN.md), [Eight Named Minds](../2026-11-01-bot-styles.html) |
| The learned brain | nets that drive and shoot, about 20 points a seat behind the rules; a transform in slot 1; a crucible champion in the Duelist | [Generations](../2026-10-27-generations.html), [Waves](../2026-11-01-waves.html) |
| The line | 19 generations this run; main moved eight times in the week; the newest proof +1.82 ± 0.42 over 800 seeds | chapter 4 |
| The fleet | nine machines, three with CUDA cards; about 114 machine-hours a day | [The Whole Line](../2026-11-01-the-whole-line.html) |
| The console | six chapters, 27 screens, every value a row, every action a button | [Double Report](../2026-11-01-double-report.html) |

Chapter 2 rewrites the goals; chapter 5 is the how-to for the line; the plan begins at chapter 9.
