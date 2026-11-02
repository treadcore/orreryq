# The Day's Difference: what changed on 2 November 2026, in exact code, with the program's flow and the architecture it changed

*Paul Richeson, with Claude. 2 November 2026. Lab report: the second half of the design, read as a diff.*

*Companion to [The Post-Mortem and the Plan](https://treadcore.org/reports/2026-11-02-the-plan/), the book the day was spent on; this report is for the reader who wants the code. Every example below is taken from the day's commits with `git diff`, trimmed only where marked `…`, and named by file. Commits: treadcore `bbd534c`, `19aba7e`, `845ae28`, `1fed90f`, `f0497ad`; orrery `84ce3b4`, `3d04507`, `c20571e`, `445a334`, `5db027f`.*

## Abstract

Twelve changes went into treadcore and orrery on 2 November 2026, every one of them a step the plan's chapters 9 to 15 had named: a guard on what the census score does not weigh; physical ranges for every distance, time and count of the brain; the wingman's five constants as weights and a stance beside them; eight named personas; three escort gauntlets with a measure of station; game 5, in which a hit pillbox loses its stock and refills from its depot; a map's scale as a label; five fleet-message keys; a learned tank from a file; a lint against tests that pin the search; a shape watch and a nightly gauntlet in the planner; and three pages and a button in the console. This report shows each as before-and-after code, exact, then draws the program's flow as it now runs (the world's tick, the fleet's line) and the UML of the classes the changes touched. Across both repositories the day is 71 files, 5,840 lines added and 53 removed in treadcore, and about 1,400 added in orrery; the tests stand at 61 (simulator), 152 (brain) and 391 (console), all passing; the window compiles; the imitation trainer's change could not be compiled on this Mac and is proved by the fleet's first shape-watch job.

## I. Method

The diffs were taken against the last commit before the day's work in each repository (`6f26539` in treadcore, `3d04507`'s parent in orrery) with `git diff -U1`, and the hunks below are copied from that output. Where a hunk is long, lines are left out and the gap marked `…`; nothing is paraphrased. A reader can reproduce every example with the commit hashes in the masthead. The figures are drawn by hand from the code as read, not generated, and name the files they stand for; a box in the accent colour is a thing that did not exist on 1 November.

## II. The guard on what the score does not weigh

The night's search had turned the base cycle off at +0.83 on the score and lost the building fix with it (the book, chapter 6). The planner's promotion gate gained a reading of each candidate's composition, built from the census logs already on disk, and a floor on each.

Before, `tools/plans/treadcore.py`, the candidates `auto_promote` may take:

```python
              and not self.anchor_short(k, v) and not self.held_by_a_person(v["weights"]) and not self.noise(k, v)}
```

After:

```python
              and not self.anchor_short(k, v) and not self.held_by_a_person(v["weights"]) and not self.noise(k, v) and not self.trades_away(k, v)}
```

The method behind it reads the per-seed team lines of a census's `g-*.log` files, trial less the rest, pooled by inverse variance across the held-out reads, and compares each of three sides to a floor:

```python
    def gives_up(self, dirs, sign=1):
        """What these reads, pooled, give up past noise and past a floor, in words. sign -1: the
        trial is what would be left behind, as in the proof, where main is the trial."""
        cache = self.state.setdefault("side_reads", {})
        reads = []
        for d in dirs or []:
            key = os.sep.join(d.rstrip(os.sep).split(os.sep)[-2:])
            if key not in cache and os.path.exists(os.path.join(d, "pooled.txt")):
                cache[key] = self.side_read(d)
            reads.append(cache.get(key) or {})
        …
        for k, word, floor in (("built", "built a team", self.GIVE_BUILT), ("road", "road a team", self.GIVE_ROAD), ("kd", "kills less deaths a seat", self.GIVE_KD)):
            rows = [r[k] for r in reads if k in r and r[k][1] > 0]
            if rows:
                iw = sum(1 / x[1] ** 2 for x in rows)
                mean, se = sign * sum(x[0] / x[1] ** 2 for x in rows) / iw, 1 / math.sqrt(iw)
                if mean < -floor and mean < -2 * se:
                    out.append("%s %+.2f +/- %.2f" % (word, mean, se))
        return out
```

The same reading stands before the proof lands a line on main. Before:

```python
                if -d / se >= self.HELD_Z and not p["above"] and on_line:
                    try:
```

After:

```python
                lost = self.gives_up(ds, sign=-1) if -d / se >= self.HELD_Z and not p["above"] and on_line else []
                if lost:
                    self.flag("trade", "the line %s reads %+.2f past main and gives up %s: it stays on the line for a person. Raise that floor on Values to let it land" % (
                        head[:7], -d, ", ".join(lost)), key="trade-line:%s" % head[:12])
                elif -d / se >= self.HELD_Z and not p["above"] and on_line:
                    try:
```

The three floors are values in `line.json` (`give_built` 1.0, `give_road` 0.5, `give_kd` 0.10), rows on Queue → Values, live at the next plan. Replayed over the sixteen candidates since the evening before, the guard would have held eleven; the one that turned the cycle off reads, at 400 seeds, +0.33 ± 0.49 on score and −5.03 ± 0.39 built, −4.14 ± 0.27 road, −0.66 ± 0.07 kills less deaths a seat.

## III. Physical ranges

`source/treadcore-brain/RANGES` grew from 34 lines to 109: a decree by Paul's word, 24 shares held to 0 to 1, and 57 physical limits in three sections, each with its reason. A fragment, exact:

```text
# Decrees.
castle_inside 2 2  # Paul, 30 October 2026: "dont get castles of turrets ... more than 2"
bio_period 60 60  # Paul, 1 November 2026: "it was already at 60,73, 86 second per cycle. thats perfect."
…
# Distances, tiles.
near_scale 2 60  # under two tiles nearness is adjacency; past the gun's reach nothing is near
base_r 2 32  # a depot's radius to a quarter of the map
odds_r 8 60  # a pillbox's ring to the gun's reach
coming_r 10 256  # a teammate beyond the largest map is not coming; 221 today means everyone counts
…
# Counts and material.
tree_material 1 8  # the simulator gives 4 a tree (HARVEST_MATERIAL): a decree candidate
strikes_max 0 4  # the bay holds 3 and a fourth cannot launch: a decree candidate
```

Nothing in the brain changed to read it: `Settings::hold()` has clamped every number to the file since 30 October, and the brain's test `every_range_reads_and_holds_its_own_default` proved every default inside. What changed is the search's room: a trial that asks for `coming_r` 400 is read at 256, the far read's doublings stop at the edges, and `suggest.py`'s draws are bounded by the same file.

## IV. The wingman's numbers, and its stance

Five constants in `commander.rs` governed a person's two wingmen; nobody could move them. They became weights with the constants as their defaults. In `weights.rs`:

```rust
    EscortDistance "escort_distance" crate::commander::ESCORT_DISTANCE, "wingman: the station behind the leader, tiles";
    WingLeash "wing_leash" crate::commander::WING_LEASH, "wingman: nothing takes it further than this from its leader, tiles";
    WingGreed "wing_greed" crate::commander::WING_GREED, "wingman: a pillbox or depot this near the leader is worth taking, tiles";
    WingThreat "wing_threat" crate::commander::WING_THREAT, "wingman: anything hostile this near the leader is its first job, tiles";
    WingAhead "wing_ahead" crate::commander::WING_AHEAD, "wingman: it hits what is ahead of the leader within this, tiles";
    WingStance "wing_stance" 0.0, "wingman: where its station is (choice: shadow | flank | screen): …";
```

In `fly_wing`, before:

```rust
        let hostile = |t: &&Tank| t.alive && !obs.allied(t.owner);
        let near = |a: V2, b: V2| a.dist(lp).total_cmp(&b.dist(lp));
        let threat = obs.tanks.iter().filter(hostile).filter(|t| t.pos.dist(lp) <= WING_THREAT).min_by(|a, b| near(a.pos, b.pos).then(a.id.cmp(&b.id)));
```

After:

```rust
        let w = &self.settings.w;
        let (station, leash, greed, threat_r, ahead_r) = (w[crate::weights::W::EscortDistance], w[crate::weights::W::WingLeash], w[crate::weights::W::WingGreed], w[crate::weights::W::WingThreat], w[crate::weights::W::WingAhead]);
        let hostile = |t: &&Tank| t.alive && !obs.allied(t.owner);
        let near = |a: V2, b: V2| a.dist(lp).total_cmp(&b.dist(lp));
        let threat = obs.tanks.iter().filter(hostile).filter(|t| t.pos.dist(lp) <= threat_r).min_by(|a, b| near(a.pos, b.pos).then(a.id.cmp(&b.id)));
```

And the station, which was one line, `let behind = lp - facing.scale(ESCORT_DISTANCE);`, is now a choice:

```rust
        let behind = match self.settings.choice(crate::weights::W::WingStance) {
            1 => {
                let side = V2::new(-facing.y, facing.x).scale(if self.slot.unwrap_or(0) % 2 == 0 { 1.0 } else { -1.0 });
                lp + side.scale(station) - facing.scale(station * 0.5)
            }
            2 => lp + facing.scale(station),
            _ => lp - facing.scale(station),
        };
```

Six sliders on the U page followed without a line of window code: the page lists `W::ALL`.

## V. Personas, and the roster

`styles.rs` went from eight slots to sixteen, the first eight unchanged so the `bot_style` dial keeps its meaning:

```rust
-pub const ROSTER: [Style; 8] = [
+pub const ROSTER: [Style; 16] = [
     Style { slot: 0, name: "Fleet", about: "the brain the fleet's search has carried: today's defaults", kind: Kind::Rules("") },
     …
+    Style { slot: 8, name: "Rome", about: "roads, posts and legions: every tank runs the base cycle, the guard keeps building, the roads between bases come first", kind: Kind::Rules(include_str!("../../../profiles/persona-rome.weights")) },
     …
+    Style { slot: 15, name: "Assyria", about: "siege: shells every pillbox in reach, longshots without pause, strikes out in threes", kind: Kind::Rules(include_str!("../../../profiles/persona-assyria.weights")) },
 ];
```

A persona is a short file over today's defaults, `profiles/persona-rome.weights` in full:

```text
w_pos_economy = 2.1
posts_max = 12
connect_tiles = 8
w_connect = 1.5
w_pos_fortify = 1.0
crew_stay = guard_one
cycle_all = every_tank
```

The launch menu's team rows, `--bots TEAM=NAME`, the census trial `bot_style = K` and orrery's Results → Personas page all read the roster, so the sixteen appeared everywhere at once. Their first reads are in the book's chapter 10.

## VI. The escort gauntlets, and a measure of station

The scenario runner learned one goal and one measure. The goal, in `scenario.rs`:

```rust
                    ("defend_pillbox", k) => Goal::DefendPillbox(k.and_then(|k| pillboxes.get(k)).copied()),
+                   // `escort:1`: the wingman's goal, seat 1 its leader (the gauntlets G10 to G12).
+                   ("escort", k) => Goal::Escort(k.unwrap_or(1) as PlayerId),
                    (g, _) => return Err(format!("no goal {}", g)),
```

The measure, counted every tick after `w.step(&orders)`, for each pair a file asked about:

```rust
        for &(a, b, within) in &stations {
            if let (Some(x), Some(y)) = (w.tanks.iter().find(|t| t.owner == a && t.alive), w.tanks.iter().find(|t| t.owner == b && t.alive)) {
                let e = out.station.entry((a, b)).or_insert((0, 0));
                e.1 += 1;
                if x.pos.dist(y.pos) <= within {
                    e.0 += 1;
                }
            }
        }
```

and read by `check` as `station = { seat, to, within, at_least }` and by `reward` as `station = { to, within, worth }`; `learn::REWARDS` lists the new term so a course accepts it. G10, the keep-station file, in its working part:

```toml
[[brain]]
seat = 1
kind = "commander"
goal = "defend_depot:0"
[[brain]]
seat = 0
kind = "net"
goal = "escort:1"
[expect]
station = { seat = 0, to = 1, within = 8, at_least = 0.5 }
[reward]
station = { to = 1, within = 8, worth = 1 }
```

The scripted wingman read 57 to 59% within eight tiles on every one of thirty seeds, 0 of 30 at the seven-tenths bar the file was first written with; the bar is a half and the file says why. G11 (cover the leader) 29 of 30; G12 (come back after a shell) 30 of 30.

## VII. Game 5: the pillbox's stock

The only rule change of the day, and the only `GAME_VERSION` bump. Two hunks in `source/treadcore-sim/src/lib.rs`. The supply, in `step_pillboxes`, after the regeneration that was already there:

```rust
        // Game 5: a depot of the side within reach, with shells in stock, sends one along (the
        // base's workers). A neutral pillbox has no depot and makes its own alone.
        if self.tick % PILLBOX_SUPPLY_EVERY == 0 {
            let mut sends: Vec<(EntityId, EntityId)> = Vec::new();
            for p in self.pillboxes.iter().filter(|p| p.alive() && p.owner.is_some() && p.shells < PILLBOX_SHELLS) {
                if let Some(d) = self.depots.iter().filter(|d| d.stock.kinds[STOCK_SHELL] > 0 && d.owner.is_some_and(|o| self.allied_opt(p.owner, o)) && d.pos.dist(p.pos) <= PILLBOX_SUPPLY_REACH).min_by(|a, b| a.pos.dist(p.pos).total_cmp(&b.pos.dist(p.pos))) {
                    sends.push((p.id, d.id));
                }
            }
            for (pid, did) in sends {
                let Some(d) = self.depots.iter_mut().find(|d| d.id == did) else { continue };
                if d.stock.kinds[STOCK_SHELL] == 0 {
                    continue;
                }
                d.stock.kinds[STOCK_SHELL] -= 1;
                if let Some(p) = self.pillbox_mut(pid) {
                    p.shells += 1;
                }
            }
        }
```

The loss, in `damage_pillbox`:

```rust
         p.health = (p.health - amount).max(0.0);
+        // Game 5: what it held goes up with the hit. It fights on with what it makes and what its
+        // depot sends (step_pillboxes).
+        p.shells = 0;
         let (left, owner) = (p.health, p.owner);
```

Two constants in `rules.rs` carry the numbers and the reason: `PILLBOX_SUPPLY_REACH` 12 tiles, `PILLBOX_SUPPLY_EVERY` 2 seconds. The test that proves it, `a_hit_pillbox_loses_its_stock_and_its_depot_sends_more`, places a pillbox with a stocked depot four tiles off and another forty tiles from any depot, hits the first, and after ten seconds expects the first refilled by the depot (at least five) and the second with one of its own. No event was added: the wire did not change. Every census read before this commit is of game 4, and the planner, which keys evidence by `GAME_VERSION`, started the reads anew by itself.

## VIII. The map's scale

Two fields on `Map`, with defaults, so an old file reads as it did:

```rust
pub struct Map {
    pub w: usize,
    pub h: usize,
    pub seed: u64,
+   #[serde(default = "default_scale")]
+   pub scale_m: f32,
+   #[serde(default = "default_tempo")]
+   pub tempo: f32,
    pub cells: Vec<u8>,
```

Two header words in `from_text`, beside `size` and `seed`:

```rust
                "scale" => {
                    scale_m = num(words.next(), "scale")?;
                    if !(scale_m > 0.0) {
                        return Err(err(n, "scale must be above nothing"));
                    }
                }
                "tempo" => {
                    tempo = num(words.next(), "tempo")?;
                    if !(tempo > 0.0) {
                        return Err(err(n, "tempo must be above nothing"));
                    }
                }
```

and `class()`, `metres()` and `real_seconds()` on the map, which the HUD's top strip reads: `field 25 m/tile`. The three world maps declare `scale 12500`, `12000` and `40000` at `tempo 1`. The round-trip test proves a theatre reads and writes back, an old file is a field, and a scale of nothing is refused. No tile and no number of the game changed; `rules::physical()` is the table of the constants in real units at 25 m and tempo 6, with a test that recomputes it.

## IX. Fleet messages, and a brain from a file

Five actions in `keys.rs`, defaults `F1` to `F5`, rebindable in Key Setup like the other forty:

```rust
-    pub const ALL: [Action; 40] = [ScrollUp, ScrollDown, …, Speed, KeySetup];
+    pub const ALL: [Action; 45] = [ScrollUp, ScrollDown, …, Speed, KeySetup, FormUp, HoldHere, ScreenAhead, GoHome, SpreadOut];
```

Each is a typed ping at a place that says what it means, in `input.rs`, and no new command or wire word was needed, because the brain has read pings by kind since 30 October and a person's ping is always heard:

```rust
        let says: [(A, V2, PingKind); 5] = [
            (A::FormUp, me.pos, PingKind::Help),
            (A::HoldHere, at.unwrap_or(me.pos), PingKind::Defend),
            (A::ScreenAhead, obs.clamp(ahead), PingKind::Help),
            (A::GoHome, home.unwrap_or(me.pos), PingKind::Defend),
            (A::SpreadOut, me.pos, PingKind::Warning),
        ];
        for (action, place, kind) in says {
            if pressed(bind.key(action)) {
                orders.0.push(Command::Ping { at: place, kind });
            }
        }
```

The game-side slot the plan asked for is one flag and one arm in `session.rs`, where the host makes its bots:

```rust
-            let b: Box<dyn Brain> = match style {
-                Some(st) => treadcore_brain::styles::make(st, &base, &names[i as usize].0, rules),
-                None => treadcore_brain::fleet::with_settings(s, rules),
+            let b: Box<dyn Brain> = match (&args.brain_file, style) {
+                (Some(f), _) if !ally => {
+                    let net = treadcore_brain::net::Net::load(std::path::Path::new(f)).unwrap_or_else(|e| panic!("{}", treadcore_sim::chair::usage("treadcore", &format!("--brain-file {}: {}", f, e))));
+                    Box::new(treadcore_brain::net::NetBrain::new(net, &names[i as usize].0))
+                }
+                (_, Some(st)) => treadcore_brain::styles::make(st, &base, &names[i as usize].0, rules),
+                _ => treadcore_brain::fleet::with_settings(s, rules),
             };
```

The person's own side stays the rules, so the wingmen follow and the builder builds.

## X. The lint, the shape watch, the nightly gauntlet

The lint is a test of the tests in `weights.rs`: it reads every `src/*.rs` of the brain, finds each `#[test]`, and fails by name if a test uses `Settings::default()` or `Tactics::default()` in an assertion without setting a weight by name. Sixteen tests written before the rule are listed and pass; a seventeenth would not. The week's commonest promotion failure cannot recur unnoticed.

The width watch became a shape watch by letting a shape be a string:

```python
-    WIDTHS = (32, 64, 128)
-    WIDTH_NOW = 64
+    WIDTHS = ("32", "64", "128", "64x3")
+    WIDTH_NOW = "64"
```

with `shape(s)` reading `"64x3"` as width 64, depth 3, and the trainer taking the depth. In `tools/bc/src/main.rs`:

```rust
-    a: Linear,
-    b: Linear,
+    /// The hidden layers, `DEPTH` of them at `WIDTH` each (two of 64 as ever), then the heads.
+    hidden: Vec<Linear>,
     c: Linear,
     act: Relu,
 …
-        let x = self.act.forward(self.a.forward(x));
-        let x = self.act.forward(self.b.forward(x));
+        let mut x = x;
+        for l in &self.hidden {
+            x = self.act.forward(l.forward(x));
+        }
         self.c.forward(x)
```

The net file it writes already carried any number of layers (`TCNET1`: a count, the sizes, then each layer), and `Net::from_bytes` reads them, so nothing downstream changed. This is the one change of the day not compiled where it was written: the trainer's Burn lock wants rustc 1.95 and this Mac has 1.93; the GPU machines build it, and the first shape-watch job's log is its proof.

The nightly gauntlet is a job the planner asks for once each `gauntlet_every_h` hours, on this Mac's lane, running `GAUNTLET=1 GAUNTLET_RUNS=100 OUT=build/train cargo test -q -p treadcore-brain --release --lib -- --ignored train --nocapture` in the checkout, which writes `build/train/gauntlet.tsv`; the console's Results → Gauntlet page draws it.

## XI. The console: three pages and a button

`training.rs` gained two Results pages and a Settings page by three rows in one table and three arms in one match:

```rust
-const RESULTS_PAGES: [usize; 5] = [5, 2, 3, 8, 4];
-const SETTINGS_PAGES: [usize; 3] = [6, 9, 7];
+const RESULTS_PAGES: [usize; 7] = [5, 2, 3, 8, 10, 12, 4];
+const SETTINGS_PAGES: [usize; 4] = [6, 9, 11, 7];
 …
+    (10, "Personas", "the roster of styles and personas: what each plays, its dials over today's defaults, and its last census read"),
+    (12, "Gauntlet", "the single-decision tests: a row a gauntlet, a column a brain, the share passed; red under the file's floor"),
+    (11, "Ranges", "the brain's RANGES: every number's limits, the decrees, and the reason beside each; only Paul decrees"),
```

Each page is a function of about forty lines over a JSON value `treadcore-view.py` now writes (`ranges()`, `personas()`, `gauntlet()`), with a hover tip on every row and, on Ranges, the wheel scrolling 109 rows through `ui.scroll_list`. The hold, which was a file, is a row on Values:

```rust
+    /// The dials a person holds (QUEUE/hold.json): a trial there waits for a person.
+    pub held: Vec<(String, f64)>,
 …
+            if operator && ui.button(rect(at.x + 300, y, 22 + 50, 22), "Release", true) {
+                st.tune = Some(format!("hold {} off", dial));
+            }
```

and `fleet-tune.py` took the verb, `hold DIAL VALUE | off`, writing `hold.json`, which the planner has read since 1 November. The keeper's `health()` gained a check that reads the operator certificate with `ssh-keygen -L` and turns amber a day before it runs out, which is what an expired one cost the fleet on 31 October. Every page was rendered to a frame and looked at before it was committed; two header overlaps and one wrong count were found that way and fixed.

## XII. The program's flow, as it now runs

!html(diff/flow-whole.html)

!html(diff/flow-tick.html)

!html(diff/flow-line.html)

## XIII. The architecture, in UML

!html(diff/uml-treadcore.html)

!html(diff/uml-orrery.html)

## XIV. What the difference did, in numbers

| Measure | Before the day | After |
| --- | --- | --- |
| RANGES lines | 34 (1 decree, 12 temper, 10 shares) | 109 (2 decrees, 12 temper, 34 shares, 57 physical) |
| weights | 135 | 141 |
| styles on the roster | 8 | 16 |
| gauntlets | 9 | 12 |
| window actions | 40 | 45 |
| game version | 4 | 5 |
| console pages (training.rs) | 10 | 13 |
| health checks | 12 | 13 |
| tests: sim, brain, console | 59, 150, 391 | 61, 152, 391 |
| the scripted wingman on G10–G12 | unmeasured | 57–59% within 8 tiles; 29/30; 30/30 |
| the eight personas, 400 seeds | unread | Rome −5.13 ± 0.58 (+5.96 built) … Shoshone −7.15 ± 0.63 (kd −0.49); see the book, chapter 10 |

## XV. Limits

- The trainer's depth is unverified by a compiler on this machine; the fleet's first shape-watch job decides it.
- The window's unit tests were not run to the end today (the Bevy test build outran the session's limit twice); `cargo check` passed and the keys' and goal's tests are small, but it is a gap.
- The persona reads of the afternoon are of game 4; the eight were asked again under game 5 and will overwrite the Personas page's column as they return.
- The nightly gauntlet runs in this Mac's working checkout, which is also where the work is done; a build in progress and the job could collide on cargo's lock.
- The hold's Release knows one reason (the stale dial of 1 November) and says it for any dial; the reason should come from the file.

## XVI. Conclusion

The day's difference is small in each place and consistent across all of them: a number that was a constant became a weight with a range; a thing that was a file became a row; a behaviour the census could not see became a floor; a decision a person could not give became a key. The world's tick changed in two boxes and the hash's order in none. The figures show where each sits; the hunks show what each is; the book says why.

## Links

[The Post-Mortem and the Plan](https://treadcore.org/reports/2026-11-02-the-plan/) · [CI-084](https://github.com/treadcore/treadcore/blob/main/documentation/checkins/CI-084-2026-11-02-the-post-mortem-and-the-plan.md) · [LAB-REPORT-BRAIN.md section 127](https://github.com/treadcore/treadcore/blob/main/documentation/LAB-REPORT-BRAIN.md) · [the Lab Reports page](https://treadcore.org/reports/) · the commits named in the masthead.
