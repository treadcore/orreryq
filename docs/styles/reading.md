
**How to read these.** Points a seat, a whole team of the style against whole teams of Fleet, on all eleven maps, on the build of each read's day. Both are the census's own numbers, by the same road a dial takes. The search's own bar for main is z 3.

### A. The hand-written styles beat the search's brain

This was not expected, and it is the report's largest finding. **Raider reads +3.06 +/- 0.74 and Expander +2.35 +/- 0.73 over 400 seeds each, z 4.1 and z 3.2,** both past the proof's bar. These are play styles written by hand in October, with a dozen dials each, against a brain the fleet has searched for days. Timid is the warning beside them: it read +3.15 past two errors at 110 seeds, the best of all, and fell to +0.39 +/- 0.62 on unseen seeds, which is exactly what picking the best first read does.

Three cautions before anyone acts on it:

- **Most of it is one map.** On `europe` both read about +18 a seat. Without it, Raider averages about +1.6 and Expander about +0.8. **Section VII follows this up, and it corrects the guess made here:** it is one dial, and it matters on nearly every map.
- **Seven were looked at and the best three were kept,** which is why they were read again on seeds of their own, and these numbers are those reads.
- **Each also loses somewhere.** Raider is -3.6 on `fidos-airstrip`; Expander is -5.2 on `atlantic`.

`bot_style` is not searched, on purpose. Nothing has moved.

### B. What is not better

**Castle reads -2.19 +/- 0.77:** a fortress gives up a little, which is a fair price for a style a person may enjoy playing against. **Overrider reads +0.28 +/- 0.72:** the transform does no harm and no good yet, as expected of one this early in its training.

### C. The learned styles: the road works, and the minds are not ready

**Scholar reads -56.84 +/- 1.97.** The old "about 20 behind" dates from an earlier game. The game now pays for building, roads and advancing, and a net that cannot build earns none of it. It plays its part in a mixed team, and no one should expect it to carry one.

**Duelist reads -17.14 +/- 1.34,** after one round of correcting the adapter. Its history is the useful part:

| Build | Read | Seeds | What changed |
| --- | --- | --- | --- |
| first | -25.20 +/- 1.02 | 110, one map (macmini) | the champion took Move and gun |
| errand restored | -17.83 +/- 1.97 | 24, here | the rules say a Move once, so a duel had left the tank stranded |
| rules keep the gun | -14.88 +/- 3.40 | 24, here | its fire output means "my hull is on him", not a trigger |
| as shipped | -17.14 +/- 1.34 | 110, all maps | the same build as the row above, better read |

The last read is the one to quote. So a champion from a duel on an empty arena, steering a tank in a real battle, costs 17 points a seat: the GPU's work now reaches the game, and it is not yet good there. Its gate opens whenever an enemy is near, and steering for a duel is a poor way to hold ground, take depots or stay near a team. **Three things could change this: open the gate more rarely; train islands against opponents and terrain nearer the game, with the families as their exam; or clone the champion and fine-tune it on the real senses.** All three are measurable now, because the road exists.

### D. Two faults this work found

**By-hand census runs on macmini read one map of eleven.** The fix of 31 October reached only the search's jobs. Castle first read -3.88 and the Duelist -25 that way, so those reads are discarded and read again. Fixed in `census_job`.

**An anchor undid three generations on noise.** While these reads ran, `w4845`, the defaults from before `r0069`, passed at a generation's low bar and went on the line as generation 5 on +0.29 +/- 0.38, z 0.76, returning `bio`, `alpha` and the rest to where main has them. A find may be carried unproven because the proof stands behind it. A retreat has nothing behind it. **An anchor must now clear the proof's z 3,** with a test. We did not rewrite the line by hand on a live run: the carry is reading those finds again on the new baseline, which is the road they should come back by. And the commit said "no change" while changing six values: that label is still wrong.
