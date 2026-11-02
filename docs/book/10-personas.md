# Personas from the terrain

A style is a whole brain with a name. Eight exist: Fleet, Raider, Castle, Expander, Timid, Overrider, Scholar and Duelist ([Eight Named Minds](../2026-11-01-bot-styles.html)). Paul asked for more, differentiated by the topography of the terrain's local maxima, and named like Civilization V's civilizations, each after a historic culture's strengths. This chapter gives the method, the eight personas built today, how each is certified, and how they are kept fresh as the line moves.

## The method: niches, not a winner

A search that keeps only the single best brain throws away every other way of being good. Quality-diversity methods keep one elite per *niche*, a cell of a behaviour space, and illuminate the whole map of what is possible rather than its summit ([41], [42], [45], [48]). The terrain of a dataset is that map drawn two dials at a time, and a local maximum on it is a niche the search has found and left: a place where a brain is good in its own way. Procedural personas in games are the same idea applied to play styles: a persona is a utility function, a set of weights, that produces a recognisable way of playing, and it is evaluated by playing, not by looking at it ([50], [51], [53]).

So a persona here is: a name; the dials that place it on a maximum or a measured style; the strength that defines it in one line; and a census read of its own, against today's defaults, at 400 seeds, which is its certificate. A persona with no read is a hypothesis and says so.

## What the terrain offers today

The terrain is thin (chapter 6): its pairs are drawn from six dials (`w_duck`, `w_pos_economy`, `posts_max`, `alpha`, `base_r`, `advance_band`), most maps draw no maximum, and 58 of 77 read maxima were unsettled on 1 November. Three hills recur across datasets and are read:

| Hill | Where | Reads | Says |
| --- | --- | --- | --- |
| the builder | `w_pos_economy` about 2.1 with `posts_max` about 12 | +2.56 ± 0.66 (every map), +1.12 ± 0.33 (score without going forward) | holds |
| the steady economist | `w_pos_economy` 2.35 with `alpha` 0.19, and with `w_duck` 1.0 | +1.2 ± 0.46 | holds |
| the bold | `w_duck` about 0.23 (ducks a quarter as often) | +0.24 ± 0.16 on kills less deaths | unsure |

And the styles have reads: Raider +3.06 and Expander +2.35 (inflated by europe's stale dial), Timid +0.39 on fresh seeds. The personas stand on these where they can and say "unread" where they cannot.

## The eight, built today

Slots 8 to 15 of the roster, so the first eight keep their numbers; each a weights file in `profiles/`, selectable by name or number anywhere a style is: the launch menu's team rows, `--bots TEAM=NAME`, the U page's `bot_style` dial, and a census trial.

| Slot | Persona | After | The strength, in play | Dials over today's defaults | Stands on |
| --- | --- | --- | --- | --- | --- |
| 8 | Rome | roads, posts and legions | builds the roads and the posts between bases; every tank runs the base cycle; the guard keeps building | `w_pos_economy` 2.1, `posts_max` 12, `connect_tiles` 8, `w_connect` 1.5, `w_pos_fortify` 1.0, `crew_stay` guard_one, `cycle_all` every_tank | the builder hill |
| 9 | China | the Great Wall | a walled castle, mended first, defended hard | Castle's dials, `w_pos_fortify` 1.5, `castle_road` 4, `w_mend` 1.5, `w_pos_defend` 4 | Castle's read; the castle rules |
| 10 | Mongolia | the horde | raids, presses at even odds, picks off the wounded, ducks a quarter as often | Raider's dials, `w_duck` 0.25, `press_odds` 1.0 | Raider +3.06, the bold hill |
| 11 | Shoshone | territory | takes the map: depots and pillboxes first, the front forward | Expander's dials, `w_front` 0.5, `advance_plan` forward | Expander +2.35 |
| 12 | Venice | trade and treasure | the economy first, no expansion; stocks before fights; a moat of mines | `w_pos_economy` 2.35, `alpha` 0.19, `w_pos_expand` 0.1, `home_pick` stocked, `w_mine` 1.5 | the steady economist hill |
| 13 | Japan | bushido | fights at full strength however hurt; does not go home | `retreat_armor` 20, `retreat_shells` 1, `press_odds` 1.0, `w_wounded` 0.6, `w_duck` 0.5 | unread: a hypothesis |
| 14 | Polynesia | the sea | island hops, boats and beaches; a navy's patience | the navy profile's dials, `landfall_wait` 20, `w_site_beach` 40 | the navy profile; unread by census |
| 15 | Assyria | siege | shells every pillbox in reach, longshots without pause, strikes out in threes | `shell_boxes` 1, `longshot_every` 0.5, `strikes_max` 3, `pillbox_worth` 1.2, `w_pos_fortify` 0.5 | the cowboy's spend (LR 86); unread as a whole |

Each persona keeps the seat's skill (a person's choice, no part of a style) and today's defaults for every dial it does not name, so a persona rides the line: when the fleet moves a default a persona did not fix, the persona moves with it. That is the keeping-fresh rule, and it is why a persona is a short file, not a whole brain.

## Certifying a persona

A persona earns its line in the table by a census: 400 seeds, all eleven maps, against today's defaults, with the composition read as well as the total (built, road, kills less deaths), the way chapter 6 learned to read. The read is asked for by hand (`fleet-queue.py grove new census "trial=bot_style = 8" seeds=400 adopt=no`); orrery's Results, Personas page carries each slot's last read. The eight were read on the afternoon of 2 November, on the game before stage 1 of the economy landed (chapter 13), and are asked for again under game 5:

| Persona | Score, a seat | Built, a team | Road, a team | Kills less deaths, a seat | What the read says |
| --- | ---: | ---: | ---: | ---: | --- |
| Rome | −5.13 ± 0.58 | +5.96 ± 0.40 | +2.12 ± 0.21 | +0.05 ± 0.06 | builds a third more and fights even; the score pays for walking, not building |
| China | −5.17 ± 0.67 | +4.53 ± 0.37 | +0.42 ± 0.19 | −0.07 ± 0.07 | the castle goes up; the score does not pay for it |
| Mongolia | −0.30 ± 0.65 | +3.53 ± 0.37 | +0.74 ± 0.17 | +0.01 ± 0.07 | even on score, and builds more than the Fleet: the bold hill's `w_duck` 0.25 cost nothing in fights |
| Shoshone | −7.15 ± 0.63 | +1.48 ± 0.30 | −0.53 ± 0.16 | −0.49 ± 0.07 | the one true loss: the front forward and the advance plan together lose half a kill a seat |
| Venice | +0.39 ± 0.54 | −1.71 ± 0.30 | −0.55 ± 0.15 | −0.06 ± 0.06 | even, and builds less: an economist by score, not by stock |
| Japan | −0.63 ± 0.61 | −0.28 ± 0.34 | −0.06 ± 0.17 | −0.06 ± 0.07 | no different from the Fleet within noise: bushido does not show at these dials |
| Polynesia | −0.36 ± 0.45 | −1.04 ± 0.21 | −0.17 ± 0.08 | −0.01 ± 0.06 | even; its maps (naval, the isles) are where to read it next |
| Assyria | −0.96 ± 0.63 | +5.32 ± 0.41 | +1.38 ± 0.20 | +0.04 ± 0.07 | the siege builds too, which was not its design; its longshots are not what the score counts |

Read as the table reads: six of the eight are within noise of the Fleet on the score, two lose, and three of them (Rome, China, Assyria) build five to six more a team for that score, which is chapter 6's finding again from another side, since the score weighs the walk and not the wall. Shoshone is a real finding against `w_front` 0.5 with `advance_plan` forward: the pair loses fights. None of the eight is certified by the score alone, and none should be: a persona's certificate is its composition matching its name, and Rome's, China's and Assyria's do. Two further reads say what a persona is for:

- **Which maps it wins on.** The census's per-map lines; a persona is a strength on some maps and a weakness on others, and the table should say which (Polynesia on naval and the isles, Rome on industry).
- **Does it feel different?** No census can read that. Chapter 15's playtest plan has a person play one match against each persona and name it blind; a persona nobody can tell from the Fleet is not one.

## How personas grow from here

- **From hills, as the terrain fills.** Regions (`tools/regions.py`) can send trials to a maximum; a maximum that settles and holds becomes a persona candidate, named by what its dials do. The terrain should draw the persona slots as points, which it does not yet.
- **From the matrix.** The temperament matrix (chapter 6) moves a persona's mood over a minute; a persona may carry its own rows, so Japan presses on its high and Venice holds on its low.
- **From the learned kinds.** Scholar and Duelist are personas of another kind of mind; a trained wingman (chapter 11) is a third. The roster takes any kind that ends in a `Command`.
- **A tournament.** Once each persona has a read, a round robin on fixed seeds (the `roundrobin.sh` the scripts already have) gives the Elo table the ledger was built for, and a persona's row says whom it beats.

## What is not claimed

The names are Paul's taste to confirm; the dials behind them are the claim. Six of the eight stand on a measured hill or a measured style; Japan and Polynesia are hypotheses until their reads return. The terrain's thinness means the "topography" is three hills on six dials, and the method is written so that more hills make more personas without a new method.

## Links

[Eight Named Minds](../2026-11-01-bot-styles.html) · [A Terrain for Each Dataset](../2026-11-01-terrain.html) · `source/treadcore-brain/src/styles.rs` · `profiles/` · MAP-Elites and quality diversity [41]–[49] · procedural personas [50]–[57].
