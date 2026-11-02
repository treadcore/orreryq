# Physical constraints first, and a scale for the world

The plan begins where the week's numbers point. Of the brain's 135 weights, about a third are distances, times and counts with a meaning in the world: how far a teammate can be and still be "coming", how long a target stays called, how many strike drones fly at once. The search has treated them as preferences, and some of them walked: `base_r` went 16, 32, 8, 6.15 in one day; `coming_r` reached 221 tiles on a map 128 tiles wide. A number that means something in the world has limits the world sets, and the first step of the second half is to write them down. Then the scale: the game's constants assume a tile of 25 metres and a game speed about six times life, and the maps range from a 128-tile island to a 1,024-tile world. A scale system says what a tile is on each map, so that flight times, arcs and speeds can be reasoned about, and so that the game can show a player real units.

## The rule, and who may use it

Paul's rule of 30 October stands: every number may have a minimum and a maximum in `source/treadcore-brain/RANGES`; nothing moves a number outside its range (not a weights file, not a trial, not a promotion); the search stays inside; and a *decree*, min equal to max, is a person's ruling that only Paul makes. What this chapter adds are ranges, not decrees. Each is grounded in a constant of the simulator or the map, and each says so beside it. Three numbers are *decree candidates*: they are facts of the simulator or Paul's own word, and the chapter names them for him rather than writing them.

## What is physical

| Kind | Count | Examples | What bounds it |
| --- | --- | --- | --- |
| physical: a distance in tiles | 30 | `near_scale`, `base_r`, `odds_r`, `coming_r`, `crew_reach`, `kite_in`, `post_spacing`, the ping reaches, the dodge's margin and clearance | the gun's reach (60), the map (128 wide, 181 across), a pillbox's ring (8), direct range (10), vision (10 and 20) |
| physical: a time in seconds | 17 | `called_for`, `mass_for`, `forget_for`, `dodge_horizon`, `bridge_keep`, `duck_memory`, `longshot_every`, `bio_period` | a shell's flight (6 s at full range), a reload (4 s, 12 s), a match (16 to 30 min) |
| physical: a count or material | 10 | `focus_cap`, `answer_cap`, `confirm`, `strikes_max`, `posts_max`, `c_boat`, `tree_material`, `forest_need` | the bay (2, 6, 3, 2), the squad (4), the material a tank carries (8), sixteen seats |
| a share, 0 to 1 | 31 | `alpha`, `w_duck`, `focus_blend`, `skill`, `w_front`, the thresholded yes-or-no weights | already ranged, or added here |
| a worth or preference | 33 | `w_near`, `w_wounded`, `w_pos_fortify`, `w_mend`, `pillbox_worth` | free: a worth is what the search is for |
| a choice or switch | 14 | `bot_style`, `roles`, `ladder`, `crew_stay`, `cycle_all` | held to their versions by construction |

## The ranges

Added to RANGES on 2 November, each with its reason. A range holds a number at its edge rather than refusing it, so a trial that asks for more gets the edge and is read there. The defaults of 2 November all lie inside.

| Weight | Default | Min | Max | Why |
| --- | --- | --- | --- | --- |
| near_scale | 30 | 2 | 60 | nearness is scaled by a distance: under two tiles it is adjacency, past the gun's reach (60) nothing is near |
| called_for | 15 | 1 | 120 | a ping older than two minutes is history; `forget_for` is 120 |
| focus_cap | 2 | 1 | 5 | teammates on one target: a fleet is five |
| base_r | 6.15 | 2 | 32 | the base's reach for threats: a depot's radius (2) to a quarter of the map |
| odds_r | 14 | 8 | 60 | tanks that count toward a fight: a pillbox's ring to the gun's reach |
| coming_r | 221 | 10 | 256 | a teammate "coming" from beyond the largest map (256) is not coming; today's 221 means everyone counts, and Paul may wish to decree less |
| mass_for | 12 | 1 | 60 | seconds to hold off for help |
| answer_cap | 3 | 0 | 15 | nearer teammates who answer instead: sixteen seats |
| crew_reach | 40 | 5 | 128 | a crew answers a call this near: the map's width |
| kite_margin | 1.5 | 0 | 10 | past the target's reach, within direct range |
| kite_in | 2.25 | 0 | 10 | the ring a step in ends on |
| kite_turn | 0.8 | 0 | 5 | seconds beyond the drive |
| kite_spare | 0.4 | 0 | 4 | seconds of a 4-second reload to spare |
| confirm, confirm_turret | 2, 3 | 1 | 10 | thinks in a row |
| jitter | 3 | 0 | 20 | a goal's shift smoothed under this many tiles |
| retreat_armor | 50 | 0 | 100 | armour is 100 |
| retreat_shells | 4 | 0 | 24 | a tank holds 24 |
| forget_for | 120 | 10 | 1800 | a match is at most 30 minutes |
| bridge_soft | 6 | 0 | 30 | a bridge this long costs no extra |
| c_boat, t_launch | 5, 3 | 0 | 16 | material, in trees' worth; a tank carries 8 |
| tree_material | 4 | 1 | 8 | **decree candidate**: the simulator gives 4 a tree (`HARVEST_MATERIAL`) |
| forest_need | 12 | 0 | 64 | trees a base asks for |
| site_area | 400 | 16 | 16384 | tiles of an island; 128 squared |
| site_reach, w_site_beach | 30, 20 | 0 | 128 | tiles, the map's width |
| column_gap | 2 | 0.5 | 6 | tiles between tanks in file |
| column_past | 2 | 0 | 20 | tiles past a bridge |
| ping_help_reach, ping_defend_reach | 60, 90 | 5 | 128 | tiles, the map's width |
| ping_defend_hold | 1.5 | 0.5 | 5 | times a rally's length |
| ping_warn_reach, ping_warn_flee, ping_caution_reach | 25, 15, 20 | 2 | 60 | tiles, within the gun's reach |
| ping_outnumbered | 1.5 | 1 | 4 | a ratio of tanks |
| bio_period | 60 | 60 | 60 | **a decree by Paul's word** (1 November: "it was already at 60, 73, 86 seconds per cycle; that's perfect") |
| patch_reach | 10 | 0 | 30 | tiles the transform may move a point |
| dodge_horizon | 1.08 | 0.2 | 6 | seconds before a shell lands; a full-range shell flies 6 |
| dodge_margin | 0.8 | 0 | 5 | tiles past the splash (2.5) |
| dodge_clear | 2.5 | 0.5 | 10 | tiles driven clear |
| landfall_wait | 10 | 0 | 60 | seconds standing off a beach |
| landfall_memory, front_memory | 30, 30 | 0 | 300 | seconds a hostile is remembered |
| connect_tiles | 5.12 | 1 | 16 | road tiles a visit |
| castle_road | 2 | 0 | 6 | pillboxes on the castle's road |
| post_spacing | 31.9 | 6 | 64 | tiles between posts: twice a pillbox's spacing to half the map |
| posts_max | 6 | 0 | 20 | there are twenty neutral pillboxes |
| junction_clear | 3 | 0 | 10 | tiles from a junction |
| bridge_keep | 90 | 10 | 600 | seconds a part-laid bridge stays a job |
| bridge_reach, fetch_gather | 40, 20 | 0 | 128 | tiles |
| duck_memory | 2.5 | 0 | 30 | seconds a gun is remembered |
| duck_ready | 1.5 | 0 | 4 | seconds; a tank's reload is 4 |
| longshot_every | 1.25 | 0.5 | 60 | seconds between longshots |
| strikes_max | 3.3 | 0 | 4 | **decree candidate**: the bay holds 3; a fourth cannot launch |
| escort_distance, wing_leash, wing_greed, wing_threat, wing_ahead | 4, 20, 16, 10, 16 | 1, 5, 2, 2, 2 | 12, 60, 40, 30, 40 | the wingman's five numbers, weights from today (chapter 11): a tank's length to direct range; a leash within the gun's reach |
| the shares (`skill`, `connect_idle`, `long_game`, `posture_scored`, `dodge_hold`, `landfall_shy`, the thresholded yes-or-no weights, `upgrade_vs_mend`, `w_front`, `w_front_post`, `w_front_push`, `focus_blend`, `assist`, `bio_amount`, `patch_confidence`) | | 0 | 1 | outside 0 to 1 a share is not one |
| site_poor | 0.5 | −1 | 1 | a site score runs −1 to 1 |

What this changes in the search: a trial that asked for `coming_r` 400 is read at 256; the far read, which doubles and halves a dial four times, stops at the edges; and the fit's draws are bounded, which is what `suggest.py` already does with the file. What it changes in the game: nothing today, since every default lies inside.

## The scale system

### What a tile is

| Map | Tiles | At 25 m a tile | What it depicts | Scale it should declare |
| --- | --- | --- | --- | --- |
| island, industry | 128 × 128 | 3.2 km | a generated island | 25 m |
| naval | 160 × 160 | 4 km | an archipelago | 25 m |
| big-lizard, constanine, fidos-airstrip, fortressisles2, fortressislesx | 256 × 256 | 6.4 km | converted prior-art maps | 25 m |
| europe | 320 × 256 | 8 km | Europe, about 4,000 km across | about 12 km: a theatre, not a field |
| atlantic | 512 × 333 | 12.8 km | the Atlantic, about 6,000 km | about 12 km |
| world | 1024 × 1024 | 25.6 km | the world | about 40 km |

The game plays every one of these with the same constants, so on europe a tank crosses the continent in eighty seconds and a mortar reaches 700 km. Nobody minds, because the game's time and distance are gameplay, not physics; but the census reads europe and atlantic among its eleven maps, and a brain tuned there is tuned for a theatre game. The scale system makes the difference explicit rather than removing it.

### The three numbers

1. **Scale**, metres a tile, declared in the map file's header (`scale 25`), 25 when absent. It changes no rule; it labels.
2. **Tempo**, how many real seconds a game second stands for, declared with the scale. At 25 m a tile the game's own numbers fit a tempo of about 6: a tank at 4 tiles a second is 360 km/h in game time and 60 km/h at tempo 6; a recon quadcopter 75 km/h; an interceptor 135 km/h; an FPV strike 97 km/h; a recon's 150-second battery is a quarter of an hour; a sixteen-minute match is an hour and a half. Those are the vehicles the drones are modelled on.
3. **The class**: *field* (scale under 100 m), where the physical table below should hold, or *theatre*, where it does not and the HUD says so.

### The constants in real units, at 25 m a tile and tempo 6

| Constant | Game | Real, at tempo 6 | The system it stands for | Fit |
| --- | --- | --- | --- | --- |
| tank speed | 4 tiles/s | 60 km/h | a main battle tank on a road, 65 to 70 km/h | fits |
| recon Mk I speed, battery | 5 tiles/s, 150 s | 75 km/h, 15 min | a quadcopter, 50 to 90 km/h, 20 to 40 min | fits |
| recon Mk II | 6.5 tiles/s, 210 s | 97 km/h, 21 min | a VTOL fixed-wing | fits |
| interceptor Mk I | 9 tiles/s, 90 s | 135 km/h, 9 min | a kinetic interceptor drone, 150 to 300 km/h | slow by half |
| interceptor Mk III | 14 tiles/s | 210 km/h | a high-speed interceptor | fits |
| strike (FPV) | 6.5 tiles/s, 45 s | 97 km/h, 4.5 min | an FPV, 100 to 150 km/h, 5 to 10 min | fits |
| loitering munition | 5.5 tiles/s, 90 s | 82 km/h, 9 min | a loitering munition, about 110 km/h, 30 min | slow, short |
| longshot | 3 tiles/s, 150 s | 45 km/h, 15 min | a one-way attack drone, 150 to 200 km/h, hours | slow by four; kept slow so a bubble on its path has time |
| indirect gun | 12 to 60 tiles, 6 s at full range | 300 m to 1.5 km, 36 s | a 120 mm mortar, 200 m to 7 km, 15 to 25 s at 1.5 km | short, and the shell flies twice as long; kept long so a tank can move if it sees the launch |
| direct gun | 10 tiles, 40 tiles/s | 250 m, 170 m/s | a tank gun, 2 to 4 km, 800 to 1,700 m/s | a quarter of the range, a fifth of the speed: the island is small |
| recon vision, link | 20, 40 tiles | 500 m, 1 km | a drone's camera and radio | short, by design: the island is small |
| pillbox range | 8 tiles | 200 m | a fortified gun | fits a machine gun, not a cannon |

The fit column is the finding: the vehicles and the drones scale together at tempo 6, and the two exceptions are the longshot (four times too slow) and the gun (short and slow). Both are gameplay choices the code already explains in its comments, and the plan keeps them; what it adds is that they are now written in one table, in one place, with the real units beside them, so a change is a one-line diff with a sentence (which is what `rules.rs` has always said it wants to be).

### Ballistic arcs

A shell today flies a straight track at 10 tiles a second and lands; the arc is drawn, not simulated. A real arc for a range *R* at launch speed *v* and angle *θ* has *R* = *v*² sin 2*θ* / *g* and flight time *t* = 2 *v* sin *θ* / *g*; at a high angle the time grows with the range's square root, not linearly. The design keeps the straight track (determinism, replay, every read of the week) and adds the arc as a displayed quantity: given the scale and tempo, the HUD can show "a 1.2 km lob, 5 s" and the newswire can say it, with the real arc's apex for the picture. A later game version may make the flight time follow the square root; that is a rule change, a GAME_VERSION bump, and a census, and it is not built.

### Where the scale system is built, and where not

- Built: the ranges above, in RANGES, with the brain's test that every default lies inside; the physical table in `rules.rs`'s documentation with a test that recomputes the real units from the constants, so the table cannot go stale.
- Designed, not built: the `scale` and `tempo` header fields (a map-format change with a round-trip test), the class on the HUD, the arc as a displayed quantity, and the square-root flight time behind a game version. Each is a one-session step; none changes a read already made.

## Links

[Too Many Shots](../2026-10-30-balance.html) (game 4's numbers and the rule of ranges) · [RESEARCH.md](https://github.com/treadcore/treadcore/blob/main/documentation/RESEARCH.md) (the systems the drones are modelled on) · [DESIGN.md](https://github.com/treadcore/treadcore/blob/main/documentation/DESIGN.md) · `source/treadcore-sim/src/rules.rs` · `source/treadcore-brain/RANGES` · McCoy on exterior ballistics [105].
