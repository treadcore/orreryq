# The Zero-Sum Economy: ore, oil, the workers, supply and trade, built in one evening, and the gauntlets that train it

*Paul Richeson, with Claude. 2 November 2026. Lab report: the plan's chapter 13, stages 2 to 4, as built and as read.*

*Companion to [The Post-Mortem and the Plan](https://treadcore.org/reports/2026-11-02-the-plan/) (chapter 13 is the design this report builds) and [The Day's Difference](2026-11-02-the-days-difference.html) (the afternoon's code). The records are treadcore's `LAB-REPORT-BRAIN.md` sections 128 to 130 and CI-085 and CI-086.*

## Abstract

Until this evening nothing in treadcore was finite. Shells and drones appeared at depots from nowhere, for ever; a sixteen-minute elimination game worked and a thirty-minute one had no shape. Paul asked for "a fun zero-sum economy, where every mineral but the growing trees is finite", with bonuses for refineries, smelters and wood harvesters, a logistics layer in which a base's workers carry what it makes, cities that grow, and trade. Between the afternoon and midnight of 2 November three rules landed, each a game version: **game 6**, ore in finite deposits, a smelter that turns it into a depot's shells, a harvester by the wood, and a depot that makes no shells of its own; **game 7**, oil in wells for the refineries and the depots' fuel, the workers as stock in transit on the roads, supply earned from what a side holds and destroys and spent on the depot's stores, and the base's guard as quartermaster building the town, the works and the city; **game 8**, convoys of supply between a side's depots by road or by sea, both ends paid by the distance, a raider that takes them and a cover that drives at the raider. The scripted brain runs all of it: on the naval map for ten minutes the fleet's own bots built three smelters, mined 36 ore, smelted 32 shells, sent 63 workers of which 62 arrived, bought two stores and raised seven of the city's works, and no tank waited at a dry depot past five seconds. Five logistics gauntlets were written for both brains, from the deposit through the factory and the port to the city, with the reward terms a training course can name; the scripted brain passes all five at ten of ten, the nets pass none that needs the squad, which is the gap the seventeen new senses and the rewards exist to close. Two faults of the old game came out under the new rules and are fixed. What the fleet reads from here is game 8; what it is not yet is in section IX.

## I. Method

The design was written first (the book's chapter 13, that afternoon) with four stages and a proof for each, written before the run. Each stage was built in the simulator with its tests, then in the scripted brain, then in the window, then read: by the simulator's unit tests, by one end-to-end match of the fleet's own team brains on the naval map (`the_bots_build_a_smelter_mine_and_smelt`, nine seats, three teams, ten minutes), by a short census of two seeds and five minutes on the generated island, and, for the last stage, by the gauntlet of single decisions on ten seeds. Every stage bumped `GAME_VERSION`, so the fleet starts its evidence anew at 8; nothing below is a read of a search, only of the rules and the brain as they are. The numbers that are first guesses are named as such in section IX.

## II. The economy as it was

Material came from trees: a squad felled a forest tile in four seconds for four, the tree grew back in two minutes. Depots resupplied armour, fuel, shells and drones; since game 4 a depot made one thing a second for all who drew on it and held twenty of each kind. A pillbox held eight shells and regained one every ten seconds; game 5 (the afternoon) made a hit pillbox lose its stock and refill from a depot of its side within twelve tiles. Structures stood on pads: a power plant, a refinery that halved the side's fuel burn and was a fuel and shell stop, a workshop, a data centre, a jammer. Nothing was finite.

## III. Game 6: ore, the smelter, the harvester

**Deposits.** A map object, `deposit x y [stock]` in a map file (`MAPS.md`), seeded where a file places none: one for every second start, six tenths of the way from that start to the centre, on the nearest open ground, 120 ore each. Between two bases rather than at either, so each is a place to hold, and fewer of them than there are sides. `maps/industry`, `island` and `naval` carry their own, written by the same rule so a map's author can move them.

**The rule.** On an ore map (`World::ore_game`; `Scenario.ore`, on unless said; `treadcore-server --no-ore` for game 5) a depot's making passes over shells and a refinery's shell stop is dry: a shell exists only because a squad mined ore and a smelter made it. The squad mines a deposit with the same order it fells a tree (`Harvest` on the deposit's tile, six seconds, four ore, eight aboard beside its material; the ORE lamps on the HUD); a tank within three tiles of a working smelter of its side unloads all it carries; every second a smelter with ore makes a shell.

**The works at their resource.** The smelter and the harvester are structure kinds that stand on open ground within three tiles of a deposit or of forest, not on a pad, and run on their own crew, not the grid (`at_resource`, `needs_power` false). Four material for a smelter, three for a harvester. A harvest within eight tiles of a working harvester yields six and the tree returns in a minute. Trees stay renewable, so a side can always build, if slowly; a side without ore loses its guns within minutes.

**The brain.** Two weights inside RANGES, `ore_low` 10 (the depot's shells under which a crew fetches ore) and `ore_reach` 40 tiles. The ore run is a small state machine (`Commander::ore_run`): with no smelter of the side in reach, the side's nearest tank to the ore with the material builds one beside it; else, when the nearest depot is short, drive to the deposit, send the squad, drive to the smelter, unload. The base's guard runs whenever the depot is short, which is the logistics of a base; every other tank once after each fill-up, as the base cycle is once. A tank standing at a depot with nothing to give, its armour whole, leaves after ten seconds and does not come home for shells for a minute: without this a side without ore parked at its depot for the match, which the first end-to-end run showed.

**Read.** Simulator: the mine, unload and smelt chain against a depot that made nothing; the works' siting refused far from the ore and accepted beside it; the harvester's six and its minute; the map's read, write and seeding; game 5 under `ore: false`. End to end, nine bots on the naval map for ten minutes: five smelters, forty ore, thirty-six smelted, the longest wait at a dry depot eight seconds. A two-seed census: two teams mined and smelted 12 and 20, and the team that did neither scored between them. **The economy is not yet the score**, and that is the trade guard's next floor.

**A fault found.** The hunter had always lobbed one blind shell at a neutral pillbox its squad was about to take (`shell_boxes`, LR 86), and the depot's free shell replaced it before the test looked. Game 6 replaces nothing, so `a_commander_takes_a_neutral_pillbox_without_a_shot` failed and the lob is gone: a live target keeps the gun.

## IV. Game 7: oil, the workers, supply, the quartermaster

**Oil.** Wells as deposits (`well x y [stock]`, seeded for the starts the deposits skipped), pumped as ore is mined, unloaded within three tiles of a working refinery of the side. A refinery with oil does what it did, the side's burn halved and a fuel stop; one without does neither, and each stop costs it an oil. On a map with wells a depot's fuel comes from a refinery of the side within thirty tiles with oil, an oil a stop; with none, a trickle of ten a stop. Fuel is therefore not fully zero-sum: the trickle is the mercy that keeps a tank from being stuck, as the dry-depot rule is for shells, and it is a decision for Paul whether it stays.

**The workers.** A number moved became a thing on the road. A smelter makes its shells into its own store, and every ten seconds a worker leaves it with up to five for the nearest depot of the side with room; the depot's shells for its pillboxes travel the same way, counting what is already on its way. Workers walk the map's route at a squad's pace over the terrain's cost, so a road is faster; they are drawn as small figures with their load. A splash within the blast loses one; a hostile tank within two tiles takes one, the shells to the tank. A base with no road to its smelter is a base whose shells come slowly, and cutting the road matters, which is what a siege is.

**Supply.** PROPOSAL-UPGRADES 1.1 as it had it: a live pillbox pays one every ten seconds, a depot two, a powered structure one every twenty, a kill ten, a capture five. A side spends as one, the buyer's own first: the guard who buys for the base earns the least. One upgrade, the depot's stores, sixty supply beside a depot of the side (`F6`): it holds thirty of each kind and makes twice a second. The top strip of the window shows the side's supply, shells, ore, oil and workers; it is the stocks page for now.

**The quartermaster.** `city.rs`: the next item a base wants, read from what stands, as far as `city_plan` allows (none, camp, town, works, city; works as built). A camp is the castle plan's and the cycle's. The town adds a harvester by the nearest wood. The works add the stores when the side has sixty, the road to the smelter a tile a visit, the industrial zone taken (a structure of nobody's or a wreck within forty tiles, the power plant first, because nothing else of the zone works without it), and a refinery on a pad a plant of ours covers where there is oil and none to take. The city adds a data centre and a workshop. The guard is the quartermaster: quiet, it drives within its squad's reach of the site, sends the squad, holds, and asks the city again when the squad is back; a threat to the base takes it back to its guard. The oil run is the ore run with a flag, after the shells.

**Read.** Simulator: the oil chain and the depot's fuel at the full rate and at the trickle; a worker taken and a worker lost; supply earned by holding and a kill, the stores bought and refused three ways. End to end under game 7: two smelters, 28 ore, 24 smelted, seven workers left and six arrived, seven of the city's works, no oil yet, because the refineries of the zone were taken late and a captured refinery wants the zone's plant first, which is why the city takes the plant first now. Supply in a short census: 258 to 583 a team in five minutes, with one thing to buy.

## V. Game 8: trade, the raider, the cover

From twenty seconds in and every minute after, each owned depot sends one convoy of supply to its nearest partner of the side, by the map's route on land or straight over the water between two ports (a depot within two tiles of water); its load is the route's length times a quarter a tile between a seat's own depots or a half between two seats of a side, and both ends are paid when it arrives. The first cut paid every pair both ways: a side of five depots earned by the square of them, 16,951 supply in five minutes, which is why it is one convoy a depot a round at half the rate. A convoy is a worker: lost to a splash, taken by a tank that drives up, the supply to the taker. The embargo of the plan is not built, because allies cannot hurt each other in this game and nothing can be embargoed until a betrayal is a thing.

The scripted brain, on Auto or the hunt and not resupplying, covers a convoy of its own when a hostile tank is near it or its road (drives to seven tenths of direct range and leaves the gun to the doctrine) and otherwise, with nothing in sight, drives onto a convoy of another side within sixteen tiles, meeting it ahead on its road. Two things were learned writing it: the cover must run with the squad out, because a tank that fortifies has its squad out for most of a match; and a sitter the tank cannot see it cannot cover, which shaped the gauntlet.

## VI. The gauntlets: from the refinery to the factory, the port and the city

Paul: "create a series of gauntlets to train the AI (both). to reward trains moving from oil refinery to factory, to port, to city." Five files in `scenarios/gauntlet/`, run as the twelve before them are: for the scripted brain as a Commander with the file's goal, for the untrained net, and for every net in `nets/`, on the same ten seeds, and nightly by the fleet into the console's Results → Gauntlet page.

| gauntlet | the decision | passed when |
| --- | --- | --- |
| G13 ore to the smelter | a deposit of forty eight tiles east; a smelter of the side and its empty depot eight tiles west | a shell smelted within the minute |
| G14 oil to the refinery | a well east; a refinery with its plant, dry, west | oil unloaded within the minute |
| G15 the convoy comes through | two depots of the side twenty-four tiles apart on a road; a tank of another side sits by it with a fifth of its armour | a convoy arrived in two and a half minutes |
| G16 the raider takes the convoy | two depots of another side on a road; the tank six tiles from it | a worker taken in ninety seconds |
| G17 the chain to the city | the deposit; the smelter as the factory; the side's depot on the shore as the port; its depot inland up the road as the city | shells delivered to a depot and a convoy arrived, in two minutes |

To write them the scenario form grew `[[deposit]]`, `[[well]]` and `[[structure]]` (kind, owner, a plant beside on `powered = true`), `road` as a terrain kind, and the counts `ore`, `smelted`, `oil`, `oil_in`, `delivered`, `convoys`, `taken` and `lost` as expectations and as reward terms, so a training course (`GROUND=`) can pay each leg of the chain: in G17 a quarter an ore, a half a shell smelted, a half a shell delivered, one a convoy.

**For the learned tank** the senses grew by seventeen (`senses::ECON`, 160 in all): the nearest deposit with ore and the nearest well (sine, cosine, nearness over 64 tiles, stock as a share of 120), the side's nearest working smelter and refinery (sine, cosine, nearness), the ore and the oil aboard as shares of eight, the side's supply as a share of 200. An old net of 143 inputs is widened with zeros as the nets of 133 were; a transform made for fewer inputs is widened with zero columns where the new senses are, so slot 1 plays as it did. What a net still lacks is a trained squad head: the order that mines is the squad's, and no net has learned to give one. That is the training these gauntlets are for.

**Read, ten seeds a cell:**

| gauntlet | scripted | untrained | phase1 | phase3 | map4 | map5 | map7 | map7a |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G13 ore to the smelter | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| G14 oil to the refinery | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| G15 the convoy comes through | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 |
| G16 the raider takes the convoy | 10 | 7 | 10 | 9 | 10 | 8 | 9 | 10 |
| G17 the chain to the city | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

The scripted brain passes all five. The nets pass none that needs the squad, and pass G15 and G16 because any gun kills a sitter with a fifth of its armour and any tank that wanders near a road meets a convoy. G15 as written is a check that the chain runs when the road is clear, not a read of a decision: it took four tries to write (a rule bot by the road captured the far depot, and a side of one depot trades with nobody; a sitter at full armour outlived two convoys; a sitter out of the tank's ten tiles of sight was never covered; the sitter's death ended a two-player match before the first convoy left), and it wants a raider with a brain that a scenario can forbid to capture, which the form does not yet say. The twelve older gauntlets read as before within a seed under game 8.

**Addendum, the night of 2 November (LR 131).** Paul: "train the nets on the gauntlets." The attempt found the zeros above were the mask's: `NetBrain` scored the squad head and never acted on it. The head is wired (capture, build a smelter, mend, fell, mine or pump, home, each offered when there is one to give within eight tiles), G13, G14 and G17 pay the drive to the works as a `closer` potential, and the trainer took the five files as one course (48 pairs, 12 episodes a generation, sigma 0.05, 4 s a generation on the Mac). From the clone `bc2` the search was flat from generation 6 (a clone that stands still in an empty field has no gradient). From `map7` it learned the raid (G16 20 of 20) and the drive west, and never the mine, in 600 generations at two step sizes. A probe gave the cause: `bc2` scores mine over hold by four and mines; `map7` scores hold at −9 and mine at −238, a margin no step of the search crosses, the rows of a head never trained but carried through a thousand generations. `Net::zero_head`, `RESET=squad` in the trainer: from `map7` with the squad head begun at zero, passed 1.00 by generation 20 and every course held out at 300: G13 19 of 20, G14 20, G15 20, G16 17, G17 20. The net is `nets/logistics.bin`; the ten-seed table with it beside the milestones is LR 131.

**Second addendum, the small hours of 3 November (LR 132).** Paul: "a mask byte for the squad head so tools/bc can clone it; a course on the fleet's maps with the squad on, since a net that mines in a field of two may not among sixteen; the census to read what the trained head does to a side's ore and smelted lines." The recording carries the squad head's mask (`TCBC3`) and `tools/bc` trains the head, proved to the decimal; the clone of forty matches (`nets/bc3.bin`) fights better alone than `bc2` and its squad head learned hold, because the scripted brain mines 169 times in 1.7 million samples of dealt matches. A scenario may now name a fleet map; on industry, island and naval, seat 0 of nine, the logistics net and a 28-generation child of it read 0 of 10, dead in the first minute to a neutral pillbox's ring on two maps and idle on the third: the premise held, and what stands between the field of two and the sixteen is the first minute of a dealt match, not the mine. Style 16, the Quartermaster, is the logistics net; the fleet's census of it (r0155) is running.

## VII. The end-to-end read, stage by stage

The same match, nine of the fleet's team brains in three teams on the naval map for ten minutes, one seed:

| | game 6 | game 7 | game 8 |
| --- | --- | --- | --- |
| smelters built | 5 | 2 | 3 |
| ore mined | 40 | 28 | 36 |
| shells smelted | 36 | 24 | 32 |
| workers left / arrived | – | 7 / 6 | 63 / 62 |
| the city's works | – | 7 | 7 |
| stores bought | – | 0 | 2 |
| supply a seat at the end | – | 10 to 291 | 10 to 376 |
| longest wait at a dry depot | 8 s | 3 s | 5 s |

Game 7's fewer smelters are the quartermaster's doing: the guard that built them in game 6 now also builds the town. The workers' count under game 8 is the convoys: sixty-three left and sixty-two arrived, so the roads of the naval map's teams were clear of raiders in that seed. No oil was pumped in any of the three: the refineries of the industrial zone are neutral and want their plant taken first, which the city does now, and ten minutes is short for it.

## VIII. What changed in the code

Simulator (`treadcore-sim`): `Deposit`, `Well`, `Carry`, `CarryKind`, `Upgrade`, `Command::Buy`; `Structure.ore/shells/oil`, `Pillboys.ore/oil`, `Depot.stores`, `Player.supply`; `Scenario.ore`; `step_carries`, `step_trade`, `splash_carries`, `send_worker`, `trade_arrives`, `is_port`, `supply_of_side`, `spend_supply`; the depot's `make_from(ore_game, cap)`; eleven events; the map's `deposit` and `well` lines, `seed_deposits`, `seed_wells`; nine refusals in the chair; `GAME_VERSION` 8. Brain (`treadcore-brain`): `city.rs`; `Commander::ore_run` (ore and oil, five stages), `city`, the raid and the cover; `Cycle::smelter_site`; the dry-depot rule in `needs_home`; weights `ore_low`, `ore_reach`, `oil_low`, `city_plan`, `w_up_stores` inside RANGES; `Act::OreRun`, `City`, `Raid`; the ledger's `ore`, `smelted`, `oil`, `supply`, `workers_lost`, `workers_taken` on the census line; the scenario form's placements, counts and rewards; `senses::ECON`; `Patch::from_bytes` widened. Window: the heap, the derrick, the smelter, the harvester, the worker; the ORE lamps; the smelter's ring; the top strip's stocks; `F6`; the wire's words. Orrery reads `ore`, `smelted`, `oil` and `supply` from the composition line.

## IX. Limits, and Paul's decisions

- The numbers are first guesses: 120 ore and 120 oil a deposit, a shell an ore, an oil a fuel stop, five a worker every ten seconds, a quarter and a half a tile of trade, sixty for the stores. Each wants a census, and the trade guard wants `ore` and `smelted` as floors once the fleet has read game 8.
- Supply has one thing to buy and earns in the hundreds a seat in ten minutes; the proposal's other upgrades, or a steeper first price, are the next decision.
- Fuel is not zero-sum (the trickle); the embargo is not built; the dock and the concrete walls of the city's fourth shape are not built; the stocks page is the top strip.
- The nets run the economy's first leg in a field of two (section VI, the addenda) and not yet among nine on the fleet's maps, where the learner dies in the first minute; the clone's squad head has its mask and learned hold from matches that seldom mine. The census of the Quartermaster (style 16) is the fleet's to finish.
- G15 reads every brain alike; it needs the scenario form to hold a depot against capture.
- Every read before this is of the old game; the first censuses of game 8 decide whether the quartermaster's city costs the guard its guard.

## X. Links

Treadcore: `LAB-REPORT-BRAIN.md` sections 128 to 130, CI-085, CI-086, journals 0105 and 0106, `HOW-TO-PLAY.md` section 6b (the ore; oil, the workers, supply and trade), `MAPS.md`, `PROPOSAL-UPGRADES.md`, `scenarios/gauntlet/g13` to `g17`. Orrery: the book's chapter 13, [The Day's Difference](2026-11-02-the-days-difference.html), the trade guard (`tools/plans/treadcore.py`).
