## II. What we are measuring, and the rules set before the results

Treadcore's working rule is "the rule before the run": write down what would confirm a change before reading it. These rules were written at about 14:20 on 1 November, while the held-out reads of `w4970` (`w_pos_fortify = 0.4`) were still running. They are copied here unchanged, and the results follow in Section IV.

### A. The instrument

| Measure | What it is | Where it comes from |
| --- | --- | --- |
| **d** | Trial team's mean score a seat, less the other teams', per seed. A paired reading, so a map's luck mostly cancels | `g-*.log`, one seed played three times |
| **se** | Its standard error over seeds | `pool.sh` |
| **z** | d / se. How many errors from no difference | `pooled.txt` |
| **Held-out read** | The census on seeds from 60,000,000 up, never used to choose a trial | job `h####` |
| **Proof** | The line against main, 800 seeds from 700,000,000 up | job `pv####` |
| **Family** | A set piece with a floor: nine of them, 6,600 runs | `every_family_holds_its_floor` |

A seat's score is a sum, and one thing we want to know is which part moved:

| Part | In the score | Why it matters here |
| --- | --- | --- |
| **Combat** | kills less deaths, a win, direct hits, pillbox damage | Does it fight better? |
| **Ground** | ground held, pillboxes and depots taken, defends | Does it hold more? |
| **Going forward** | tiles advanced (0.25 each), advance stages, tows | **What this dial pays most, and what we must not mistake for skill** |
| **Works** | built, road, bridges, castle time | **What this dial may cost** |

And the behaviour itself: seconds a team spends on each rung of the Auto ladder (fortify, turrets, hunt, expand), and the share of posture picks in each posture. These logs now name each reward, which they did not when this began.

### B. The rules

**R1, to join the line.** `w_pos_fortify = 0.4` joins by the ordinary road or not at all: past its held-out bar for that hour, every family at or above its floor, and all the brain's unit tests passing. **No exception by hand,** however good the earlier read.

**R2, to reach main.** The line must read z 3 past main, 800 unseen seeds, no map two errors under. Main does not move on anything less.

**R3, to count as a real gain beyond the reward for walking.** With tiles advanced and advance stages taken out of the score, 0.4 should still be above Fleet on all maps by more than two errors. **If it is not, the honest conclusion is that this dial mostly collects a reward, and the report must say so,** even with the change standing.

**R4, what would make us take it back.** Any of: a family under its floor; the line reading two errors under main at its proof; or combat clearly worse (kills less deaths past two errors below). Then it goes back by a person's hand or by an anchor at z 3.

**R5, the Connect dial.** `connect_idle = 0` goes by the same road. Before it was measured here on two maps it read inside the noise. It is judged on all eleven at 400 seeds; it need only not lose, since it removes a score for work nobody can do. Below two errors, it stays at 1.

**Not measured, and said now:** whether the game is more fun or looks better. Bots that build less early are a change of character, and only a person playing can judge that.
