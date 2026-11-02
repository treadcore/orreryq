# The wingman: an escort for a person

Paul's ask: a wingman trained so that it follows my moves, like an escort mission. Part of it exists and nobody can touch it; part of it does not exist. This chapter says which is which, makes the existing part adjustable today, sets the gauntlets a wingman must pass, and designs the trained one.

## What exists

A person's team is dealt a builder, a guard and two wingmen; the wingmen's goal is Escort, with the person as leader ([fleet.rs](https://github.com/treadcore/treadcore/blob/main/source/treadcore-brain/src/fleet.rs)). A wingman holds a station a few tiles behind the leader's heading, goes no further than a leash from it, takes what it wants (a pillbox, a depot, a threat to the leader, a threat to another ally) within a greed radius, treats anything hostile within a threat radius of the leader as its first job, looks ahead of the leader's heading for what is coming, keeps a task three seconds before a lower one may replace it, and regroups when the leader boards a boat or when it has lost it. A person orders the fleet with a ping (`Q` or the middle button): the leader's ping is the fleet's order, and the bots converge and attack. The coordination screen (Space) lists the fleet and what each is doing; `G` steps the person's own goal, Escort among them, so a person may also follow a bot.

Five numbers govern all of this, and until today they were constants in `commander.rs`: the station (4 tiles), the leash (20), the greed (16), the threat radius (10), the look-ahead (16). A constant cannot be moved by the person, by a persona or by the search.

!html(figs/the-wingman.html)

## Built today: the five numbers as weights

`escort_distance`, `wing_leash`, `wing_greed`, `wing_threat` and `wing_ahead` are weights with the same defaults, so nothing plays differently, and with ranges (chapter 9). What that gives at once:

- **A slider each on the U page**, so a person can pull the wingmen in close (station 2, leash 8) for a drive through pillbox country, or let them roam (greed 30) for a sweep.
- **A persona's say**: Mongolia's wingmen roam, Rome's hug the road, Japan's stand off nothing.
- **The search's say**: five more dials the fit may move, read by the census like any other, held to their ranges.

## The gauntlets, built today

The gauntlet is the brain's set of single-decision tests, nine until today (fire in reach, an enemy behind, a shell on a standing tank, a strike coming, low armour with home in sight, a depot to take, a pillbox outside its ring, out of a pillbox's ring, a depot across the water), each a scenario file with a floor, run on fixed seeds for the scripted brain, the untrained net and every net in `nets/` ([Generations](../2026-10-27-generations.html)). Three escort gauntlets join them, and a new expectation, `station`, counts the share of a run a seat spends within a distance of another:

| Gauntlet | The scene | Passed when | Floor |
| --- | --- | --- | --- |
| G10 keep station | an allied leader on the rules drives fifty tiles to a depot and holds it; the wingman starts eight tiles behind | the wingman is within eight tiles of the leader for half the run | 0.8 |
| G11 cover the leader | the same, and an enemy tank is set down ten tiles ahead of the leader at twenty seconds | the wingman hits the enemy at least once, and is within the leash (twenty tiles) for eight tenths of the run | 0.7 |
| G12 come back | the same, and a hostile shell lands on the wingman at ten seconds | the wingman is not hit, and is within the leash for eight tenths of the run | 0.8 |

The scripted wingman was read against them first, thirty seeds each, on 2 November: G11 29 of 30, G12 30 of 30, and G10 held for 57 to 59% of the run on every seed, which is 0 of 30 at the seven-tenths bar the gauntlet was first written with. That is the finding about the scripted brain: it takes the first half minute to close on a leader that drives as fast as it does, because its station is behind the leader and a tank cannot overtake its own speed. The bar stands at a half, which it clears, and 57% is the number a trained wingman has to beat. A gauntlet the scripted brain fails is kept as a finding, not softened away; the file says what was read.

## The trained wingman: the design

The learned tank has 133 senses, a net of two hidden layers of 64, and heads for driving and shooting; it learns by imitation first and by evolution strategies after ([66]–[73], [1]–[8]). A wingman is the same net with one more job.

1. **Make the leader a sense.** The compass already carries allied contacts by sector; the one addition is a leader channel: the leader's bearing and distance, its heading, and whether it is moving, so "follow my moves" has something to follow. That is four numbers on the periscope, and it changes the senses' count, which every trained net reads, so it is a new generation of nets, not a patch to the old.
2. **Imitate the scripted wingman.** The recording fleet records a thousand escort matches with the person's seat on the autopilot and the wingmen scripted; behaviour cloning on the card gives a net that keeps station in minutes, as it gave Scholar. This is the warm start the literature recommends before any search ([66], [68], [71]).
3. **Then evolve against the gauntlets.** Evolution strategies on the escort gauntlets with a reward that pays for station kept, for damage given to what threatens the leader, and against damage the leader takes; the gauntlets are the curriculum, easiest first ([90], [91]). Fitness is noisy, so the reads are pooled and the bar is written before the run ([25], [27]).
4. **Formation, not pursuit.** A wingman that drives at the leader's position is a follower; one that holds a station in the leader's frame (behind and to a side, turning as the leader turns) is a wingman. Leader-follower formation control gives the geometry: the desired position is the leader's position plus an offset rotated by the leader's heading, and the error to close is in that frame ([74], [75], [77]). The scripted wingman's `behind = leader − facing × escort_distance` is the degenerate case with the offset on the axis; the trained one should learn the side too, and the person should be able to set it (left, right, behind).
5. **Judge it as a wingman, not as a tank.** The census score cannot see what an escort is for. The read is: the leader's survival and score with this wingman against with the scripted one, at 400 seeds, on the person's team with the person on the autopilot; plus the gauntlets; plus a person's playtest (chapter 15).

## What the person should be able to say

Today: ping. Designed in chapter 14 as elements: a fleet message key for *form up on me*, *hold here*, *take that*, *screen ahead*, *go home*, each a call the wingmen already understand or a goal they can take; a wingman stance (shadow, flank, screen, free) as a choice weight the U page shows; and the station's side.

## Links

[Eight Named Minds](../2026-11-01-bot-styles.html) · [Generations](../2026-10-27-generations.html) (the gauntlet) · [AI-BRAINZ-PLAN.md](https://github.com/treadcore/treadcore/blob/main/documentation/AI-BRAINZ-PLAN.md) · [LEARNING-DESIGN.md](https://github.com/treadcore/treadcore/blob/main/documentation/LEARNING-DESIGN.md) · formation control [74]–[81] · imitation [66]–[73] · curriculum [90]–[97].
