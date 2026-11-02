# Playing with and against the bots, and every feature an element

A week of training made the bots better at a game nobody was playing. This chapter is about the person in the seat: what they can set and say today, what they cannot, and the element each missing thing gets. Then the same audit for orrery, where the rule is Paul's: anything a person might need to do is a button, and anything the machines know is on a screen.

## In the game today

The launch menu (`treadcore` with no flags) is rows: map, sides, skill, a style for each of four teams, lives, length, speed, driver (you, or the autopilot to watch). The same choices are flags, so the menu adds nothing the command line cannot say. In play, the keys drive and fire; `G` steps the person's own goal (auto, hunt pillboxes, defend depot, defend base, defend pillbox, hold, fortify, escort, the wheel); Space raises the coordination screen with the ladder's rungs on 1 to 6, a click to hold there, a right-click for the push point, and the fleet's lines; `U` opens the team's sliders, every weight of the brain, including, from today, the wingman's five and the persona dial; `Q` pings the cursor for the side and allied bots converge; `C` chains a pillbox for two tanks to haul; `O` is the autopilot; proposals and chat have their keys; `K` rebinds any key. A person's team is dealt a builder, a guard and two wingmen on the person (chapter 11).

## What a person cannot do, and the element for each

| Want | Today | The element | State |
| --- | --- | --- | --- |
| pick a persona for a team | the menu's team rows list the eight styles | the rows list sixteen: the styles and the personas | built today, since the menu reads the roster |
| change a bot's style or persona during a match | the `bot_style` slider acts at the next match, because a style is made with the brain | a *re-deal* on the host: the slider's change rebuilds that team's bot brains at their next think; no rule or wire change, host-side only | designed |
| a style for my own autopilot apart from my wingmen | one dial for the team | a second row on the U page, *my autopilot*, over the person's Commander alone | designed |
| tell a wingman where to be | ping | the wingman's five sliders (station, leash, greed, threat, look-ahead); a *stance* choice (shadow, flank, screen, free) and a *side* (left, right, behind) as choice weights the U page shows | sliders built today; the choices designed |
| give the fleet an order by name | one ping means "converge and attack" | *fleet messages*: Form up, Hold here, Take that, Screen ahead, Go home, Spread out; each a typed ping the brain already distinguishes (`ping_style`'s help, warn, defend kinds) or a goal; on keys a person assigns in the `K` screen, which rebinds any action; the coordination screen lists them and the last one sent | designed |
| have bots answer my ping whatever the switch | since pings-off was promoted on a bots-only census, a person's ping is answered only if `pings` is on | a person's ping is always a call: the switch governs bot-to-bot calls alone | designed, and Paul's to decide (chapter 3) |
| set a bot's goal | bots climb their own ladder | per-bot goal from the coordination screen: a line per fleet member with its rung and a key to pin a goal (defend base, hold, escort me) | designed |
| ally with a bots' team | proposals exist in the world and the window; whether a bots' team answers a person's is not measured | an *ally policy* weight for bots (never, when outnumbered, when offered, always) and the menu's sides row offering "allies: ask the bots" | designed |
| play a net or a transform in a match | the census reads a slot; the game cannot load one from a file, and the `patch` row on the U page could ask for a file the game does not have | a game-side slot: `--brain-file` and a menu row listing `nets/` and the fleet's slots, off by default; the `patch` row refuses above zero until a file is there | designed; the refusal first |
| see who is who in a crowd | the names overprint; the name is the whole of how styles are told apart | a persona's colour band on the hull and a glyph on the minimap | designed |
| set bots' styles in a network match | the host reads `--bots`; the lobby has no row | a bots row in the lobby, sent as the host's setting | designed |

## In orrery today

Six chapters and 27 screens, each with its six answers in the one table (`line.json`): Machines (and Storage, Media), Projects, Queue (Fleet, Runs, Board, Flow, Timeline, Queued, Values, then the Pipeline's pages), Results (the Algorhythm tabs: Patch, Terrain, Spectrum, Matrices, Senses, Temper, Fleet; the net; the ledger), Lab, Sessions, Fleet, Chat, Settings (Keeper, Long run, Commits). Every value of the process is a row with a step; every machine and project has pause, stop, resume, remove and add; the keeper has restart; a run can be asked for (census, promote, switches, parts, train) and cancelled.

## What orrery knows and does not show, and the element for each

| Feature | Today | The element | State |
| --- | --- | --- | --- |
| a dial held by a person | `hold.json`, a file | a *hold* on each row of Values and of the brain's dials: the value held, who, when; a press writes the file | designed |
| the physical ranges | `RANGES`, a file the brain compiles in | Settings → Ranges: every number with its min, default and max, its kind (distance, time, count, share, worth), and the decrees marked; a trial's clamp shown on its row | designed; the page's data (`plan/ranges.json`) built today |
| the personas and their reads | `nets/styles.tsv` and the census results | Results → Personas: the sixteen with their dials over the defaults, their last read (total and composition), the maps they win on, and a *Read* button that asks the census | designed |
| the trade guard's decisions | a flag a candidate | the Candidates page shows built, road and kills-less-deaths beside the score for every candidate, and the floor each is held by | designed |
| the gauntlets | `make gauntlet` and a TSV | Results → Gauntlet: a row a gauntlet, a column a brain (rules, each net, each persona), the pass share and the reaction's median; red under the floor | designed |
| the testing plan's state | nowhere | Settings → Tests: the levels of chapter 15 with the last time each ran, what passed, and what a person owes (a playtest, a battery, an install) | designed |
| a certificate about to expire | a silent penalty | a Settings → Keeper check turning amber a day before, and Renew beside it | designed |
| the book and the reports | the site | the Lab Reports page, with every report of the month and this book | built today |
| frequent paths | several clicks | Command-digit reaches chapters; the next step is a key a page | later |

## The rule for new features

From here, a feature lands with its element or with a line in this table saying which element it will get and why not yet. The audit is cheap because the one table of screens already asks every screen six questions; a feature with no screen fails the seventh.

## Links

[How to Play](https://github.com/treadcore/treadcore/blob/main/documentation/HOW-TO-PLAY.md) · [Double Report](../2026-11-01-double-report.html) (every screen of orrery, pictured) · [Eight Named Minds](../2026-11-01-bot-styles.html) (what a style cannot do in a match) · `source/treadcore-client/src/menu.rs`, `goal.rs`, `tune.rs`, `keys.rs` · `tools/plans/line.json` · human interaction with automation [106].
