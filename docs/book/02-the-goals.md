# The goals, rewritten

The goals have been written three times: as treadcore's roadmap (18 October), as orrery's plan (September, then the backlog of 29 October), and, between the lines, as four weeks of Paul's directives. This chapter puts them in one place, says what each means in plain words, where it stands, and what the asks of 2 November add. It links back rather than repeating; nothing here changes an old report.

## Treadcore's six goals, as the roadmap states them

| Goal | In plain words | State | Where |
| --- | --- | --- | --- |
| 1. One world, many machines | a world that is playable, editable, networked and programmable at once: deterministic, sixteen seats, maps and an editor, teams and alliances, prediction, play across the Internet, a headless server | met | [ROADMAP](https://github.com/treadcore/treadcore/blob/main/documentation/ROADMAP.md) goal 1 |
| 2. The battlefield the war made | indirect fire, the bubble, recon, strike and longshot drones, jammers, industry under drones | met; balance continues | goal 2, [Too Many Shots](../2026-10-30-balance.html) |
| 3. Command, not only driving | goal modes, fleets, castles, pillboxes that move, a coordination screen | half met: allies' goals, fleet orders from the screen, shared drones and transfers, build patterns by ping are open | goal 3, steps 11c to 11i |
| 4. Bots that think as a team | one tunable decision pattern on shared memory, cheap enough for sixteen at 4x speed | being finished: every part on by default since 20 October; tuning is the fleet's job | goal 4, the brain report |
| 5. Longer, truer matches | real numbers and tuned ranges (11f), upgrades bought for supply (11g), the flag and the town's vision (11j), a score for ground held over time | open | goal 5, [PROPOSAL-UPGRADES](https://github.com/treadcore/treadcore/blob/main/documentation/PROPOSAL-UPGRADES.md) |
| 6. In players' hands | packages, a release, two real routers | 0.2.0 released 26 October; the two-router proof still open | goal 6 |

## Orrery's goals, as its documents state them

Orrery's first design set (console, surface, wire, lockdown, media) had one goal: **the console the operator stands in front of**, with no dependencies, able to reach a locked-down node by SSH, SFTP, TLS and RDP, with verbs that act on a selection and refuse structurally what they cannot do. All eleven of its phases are done ([the writeup](https://github.com/richeson/orrery/blob/main/docs/writeup.html)). The second set, written in the last week of October, has three goals that this book inherits:

- **The fleet as one computer**: a queue, a lane a machine, a keeper, with health checks and buttons for anything a person might need to do ([fleet-train](https://github.com/richeson/orrery/blob/main/docs/fleet-train.md)).
- **One coherent process**: a ratchet of generations on a line, proved before it reaches the game, drawn as a Gantt and a Kanban, every value adjustable from a screen ([The Whole Line](../2026-11-01-the-whole-line.html), [Double Report](../2026-11-01-double-report.html)).
- **More brains judged by one judge**: versions, roles, senses, a league of learned models, the crucible bridge, each read by the same census ([brains.md](https://github.com/richeson/orrery/blob/main/docs/brains.md)).

## The goals as the directives express them

Read across the check-ins and the commit messages, Paul's prompts return to the same eight things. They are the project's working goals whether or not a document names them:

1. **Always progress forward and carry the weights.** Nothing found is thrown away; a generation builds on the last; a pass is carried across a generation rather than re-read from nothing.
2. **Automatic, with buttons.** The fleet should promote by itself when in auto mode and the machine can push; anything manual should be a button; a process that needs a person at the keyboard has failed.
3. **Every number a weight, every either-or a scalar, every feature on by default.** "Should it do x or y" becomes a weight that blends the two plus a switch; new behaviour ships on with a sensible starting number; the census is the guard.
4. **Numbers stay in their ranges, and a decree is a constant.** Every number may have a min and max; min equal to max is a person's ruling, which only Paul makes.
5. **Record every step.** A lab-report section, a roadmap item, a changelog line, a journal entry and an IEEE-style check-in, with the prompt quoted word for word and each decision traced to its cause.
6. **Measure before believing.** The rule before the run; two standard errors as the bar; a census of 400 seeds, not a smoke test; one lever at a time.
7. **The game is for a person.** Hard at full skill, playable at 0.6; the bots should play like a side; a person should be able to pick a bot by name, set a goal, and be followed.
8. **Speed it up, but not with noise.** One promotion every half hour was asked for and the noise it buys was measured; less noise was then asked for, and the bars were raised.

## What 2 November adds

The asks of 2 November are the second half of the design, and they fall into the same frame:

| Ask | Which goal it serves | New or continued |
| --- | --- | --- |
| Lock the physical constraints into ranges first | 4 (ranges and decrees), 5 (real numbers, 11f) | continues 11f, which has been open since 18 October |
| A scale system for ballistic arcs and drone speed | 5 (real numbers) | new: maps differ in size and the constants assume 25 m a tile |
| Named personas from the terrain's local maxima | 4 (bots that think as a team), 7 (pick a bot by name) | continues bot styles with a method for naming them |
| A wingman that follows the human | 3 (command, not only driving), 7 | the scripted wingman exists; a trained one and a person's say over it are new |
| Training gauntlets for these abilities | 6 (measure before believing) | continues the gauntlet of 27 October |
| A wider or deeper transform | the fourth part of the design | the width watch exists; depth is new |
| A zero-sum economy, refineries, smelters, harvesters | 5 (longer, truer matches), 11g | new; the upgrades proposal is its nearest kin |
| Logistics: workers, bases that recharge, a pillbox that loses its ammo when hit | 5 | new |
| Cities, and a teammate who builds while defending | 3, 4 | the builder role exists on a person's team; the rest is new |
| Human-with-bots play, goal and personality toggles, fleet messages, ally bot play | 3, 7 | continues 11c and 11d |
| Every feature an interface element | 2 (automatic, with buttons) | an audit, then the elements |
| The goals rewritten, the how-to, the post-mortem, in chapters, with IEEE references | 5 (record every step) | this book |

## The gap

Three things the documents promise that the directives have outrun, and one the other way:

- The roadmap's goal 4 says tuning comes once the features are in. The features have been in since 20 October and the fleet has tuned for a week; what the week found is that the search also tunes numbers that should have been constants. That is why the plan begins with ranges.
- Goal 3's coordination screen was to carry allies' goals and fleet orders. The screen shows the fleet's rungs now; orders from it, and a person's say over a wingman, are still to come, and chapter 14 designs them.
- Goal 5 (longer, truer matches) has had a proposal since 18 October and no step; the economy asked for on 2 November is where it goes.
- The other way: the directives asked for one promotion every twenty minutes, then every half hour, then for less noise. The numbers settled it (chapter 6): the pace is set by the seeds a read needs, and the bars now stand at z 1.5 with a floor of a quarter point a seat.

## Links

[ROADMAP.md](https://github.com/treadcore/treadcore/blob/main/documentation/ROADMAP.md) · [CONCEPT.md](https://github.com/treadcore/treadcore/blob/main/documentation/CONCEPT.md) · [brains.md](https://github.com/richeson/orrery/blob/main/docs/brains.md) · [plan.md](https://github.com/richeson/orrery/blob/main/docs/plan.md) · [The Whole Line](../2026-11-01-the-whole-line.html) · chapter 3 for the directives in full, chapter 8 for the register of open items.
