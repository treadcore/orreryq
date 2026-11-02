# What the numbers said

The week's findings, each in a paragraph, with the one number that carries it. The reports hold the tables.

## The search works, and it is noisy

Over the week the fleet read about two thousand trials on today's defaults and carried nineteen generations onto the line in this run. The line proved past main nine times from +1.97 to −0.60 a seat; the last three reads were +3.16 ± 0.46, +1.46 ± 0.35 and +1.82 ± 0.42 over 800 seeds. The game's seed-to-seed swing is about 9.5 points a seat, twice what the difficulty simulation first assumed, so a read of 400 seeds has an error near half a point, and that sets the pace: a generation every half hour is the most the seeds allow, and a promotion every twenty minutes would be mostly noise ([Promotion Difficulty](../2026-10-29-difficulty.html)). Of the thirteen generations of 1 November, replayed under the rules written that night, four would have landed; nine were a switch going off at +0.10 and back on at +0.08, or a dial walking four steps on luck.

## Half the promotions failed on tests, not on brains

Seven of the first fourteen promotions failed, every one of them at the brain's unit tests and none at the families or the census. The tests pinned defaults by reading `Settings::default()` rather than naming the numbers they tested, so every move of a searchable number broke a test that had nothing to say about it. Each such failure cost a passed candidate. Sweeping all of them together on 1 November fixed the line more than any bar did ([The Whole Line](../2026-11-01-the-whole-line.html)). The same fault recurred twice afterwards (the matrix's test, the improvement's test) and each was fixed the same way: a test names the weights it tests.

## A total score hides its composition

Europe's +18 for a hand-written style was one stale dial: `w_pos_fortify` had been promoted at 6.0 under an older game, and under game 4's reward for going forward it was paying tanks to walk. A trial at 0.4 read +3.65 ± 0.62 at z 5.9 across all maps; broken down, all of it was advance rewards, with kills-less-deaths −0.17 ± 0.05. The rules written before the read refused it; 1.5 was taken and 0.4 held ([A Stale Dial](../2026-11-01-a-stale-dial.html)). The same lesson came back on the night of 1 November: a candidate turned the base cycle off at +0.83 on the score, and built 4.8 less a team, laid 4.1 less road and lost 0.40 kills-less-deaths a seat, none of which the score weighs. Read at 400 seeds the next morning: cycle off scores +0.33 ± 0.49 and loses 5.03 ± 0.39 built, 4.14 ± 0.27 road and 0.66 ± 0.07 a seat in fights. The guard built that morning holds a candidate that gives up more than a floor past two errors; replayed over the sixteen candidates since the evening before, it would have held eleven.

## Material was never the limit

Teams held six of eight material from the fifth minute to the last, and squads spent 6% of their time on construction against 13% going home. Nothing asked them to build: the fill-up cycle ran for the leader and the guard alone, and a wingman built only while its leader stood at the fort. Two dials, `cycle_all` and `crew_stay`, built +3.16 ± 0.35 a team (18%) and laid +2.14 ± 0.20 road (34%) at 400 seeds, with kills-less-deaths +0.19 ± 0.06 and the score flat at −0.26 ± 0.46 ([Waves, Width and Waiting](../2026-11-01-waves.html), section IX). They were promoted by hand, since the score would never have let them through.

## The waves reach behaviour and do not win

Each entry of the temperament matrix moves its own wave's behaviour with the right sign: pressing up to ±18 points of fights; mood makes tanks more careful at high. A negative control (waves on, amount zero, identical games) read exactly zero over 400 seeds, which made every later difference believable. No clear gain in kills, deaths or score followed, and stances occupy about 3% of live seconds, so two of the matrix's rows have little to move ([Waves](../2026-11-01-waves.html)).

## Wider is not yet worth it

The transform trained at widths 32, 64 and 128 read 67.1, 67.7 and 68.7 on the drive head and 64.6, 65.7 and 66.4 on the gun: 128 beats 64 by 0.85 points, under the bar of 1.0 set before the test. The width watch repeats the test every twenty generations ([Waves](../2026-11-01-waves.html), section VI). The transform in slot 1, trained by SPSA over 942 numbers, is the Overrider style; it is not promoted.

## The nets are twenty points behind the rules

A net that learned by imitating the rules (Scholar) read about 20 a seat under them; a pure net cannot build or crew. The GPU was not faster than a CPU for a net this small (6.4 ms a step against 5.6). Behaviour cloning gets a net playing in minutes and inherits its teacher's faults ([The Learned Tank](../2026-10-26-the-learned-tank.html), [Generations](../2026-10-27-generations.html)). The crucible champion plays the fight inside a rules tank at 84% against its yardstick on its own arena; on this simulator the gun had to stay the rules' (−17.8 a seat when the champion fired).

## The styles, read

Raider +3.06 and Expander +2.35 at 400 seeds, mostly on europe before the stale dial was found; Timid +0.39 on fresh seeds after reading +3.15 on picked ones; Duelist −17.14; Scholar −56.84 ([Eight Named Minds](../2026-11-01-bot-styles.html)). Picking the best of several first reads inflates it; a re-read on fresh seeds is the only honest number.

## The queue was the bottleneck, not the machines

A winner's first read to pass fell from 57 minutes to 25 (three samples) once read-ons went to the front of the queue, the queue per machine fell to two, and quick machines took the long reads; the wait for a read-on fell from 10.2 to 0.7 minutes; a proof takes 7.5 to 9.6 minutes. New trials still wait about ten minutes ([Waves](../2026-11-01-waves.html), section VII).

## The terrain is thin where it matters

Of 88 maxima flagged on the terrain at 18:22 on 1 November, 77 had been read and 58 of those were not settled; two dials at a time are a slice of a 118-dial space, and the hills the search drew are mostly where it had already read. The old terrain had used 109 of 2,675 reads before it was rebuilt from each census's own directory ([A Terrain for Each Dataset](../2026-11-01-terrain.html)). This matters for the personas of chapter 10: the maxima name a few places, not a map.

## The dials that moved most

Over the week the fleet moved `w_pos_fortify` from 6.0 to 1.5, 0.75, 0.375 and 0.1875 (and tried 0.4, held); `base_r` from 16 to 32 to 8 to 6.15; `alpha` from 0.4 to 0.18; `press_odds` from 2.68 to 1.34; `kite_in` from 9 to 4.5 to 2.25; `near_scale` from 15 to 30; `connect_tiles` 4 to 5.1; `w_mine` 0.5 to 1 to 0.86; `coming_r` 180 to 221; and flipped `pings`, `bridges` and `escort` off and `cycle` off and on. Several of these are distances and times with a meaning in the world: `coming_r` at 221 tiles is wider than the map's diagonal, `base_r` walked a factor of five in a day. That is the finding chapter 9 acts on: numbers that were meant to be constants were searched as if they were preferences.

## Links

Every report named above; chapter 7 for what these findings teach; chapter 9 for what they change.
