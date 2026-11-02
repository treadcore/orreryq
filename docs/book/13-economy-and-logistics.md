# The economy and the logistics of a base

Paul's ask, in his words made plain: a fun zero-sum economy, where every mineral but the growing trees is finite; bonuses for refineries, smelters and wood harvesters; a logistics layer where each base has a worker that does its work and recharges its empty supplies, and a pillbox does too, except that a pillbox that is hit loses its ammunition (it all goes up) and keeps only what it makes afresh; a description of how cities develop and refineries are built; and perhaps a teammate who stays back issuing the building orders while defending. This is a design chapter: nothing in it is built, and the first step is named.

## The economy as it is

Material comes from trees: a squad fells a forest tile in four seconds for four material, and the tree grows back in two minutes. A tank carries eight. Walls, roads, bridges, mines and pillboxes cost one or two; a boat five. Depots resupply armour, fuel, shells and drones; since game 4 a depot makes one thing a second for all who draw on it and holds twenty of each kind, so a depot is a well that can run dry under a crowd and refills on its own. A pillbox holds eight shells for its owner and regains one every ten seconds. Structures go on pads: a power plant powers a zone of eighteen tiles; a refinery is a fuel and shell stop that halves the side's fuel burn; a workshop repairs and mends; a data centre is fire control and radar. Scoring pays a kill 100, a capture 25, an interception 5 and two points every ten seconds for each structure held; game 4 added rewards for going forward, which chapter 6 showed the search will farm. The upgrades proposal of 18 October ([PROPOSAL-UPGRADES](https://github.com/treadcore/treadcore/blob/main/documentation/PROPOSAL-UPGRADES.md)) adds *supply*, a side's second count earned from holdings and kills, and sixteen things to buy with it; it was traced once and never built.

Nothing in this is finite. Shells and drones appear at depots from nowhere, for ever. That is what makes a sixteen-minute elimination game work, and what makes a thirty-minute one shapeless.

## The design: four stocks, one of them renewable

!html(figs/the-stocks.html)

| Stock | Source | Finite? | Spent on | The structure that improves it |
| --- | --- | --- | --- | --- |
| wood | forest tiles, felled by the squad; regrows | no | roads, walls, bridges, boats, pillboxes | the **harvester**: a works on a pad by a forest; the squad's harvest near it yields six, not four, and the tile regrows in one minute |
| ore | **deposits**: a new map object, a few per map, each with a fixed stock | yes | shells (smelted), pillbox and structure armour plate | the **smelter**: a works that turns ore into a depot's shell stock, one a second; without one a depot's shells do not refill |
| oil | **wells**: a map object with a fixed stock | yes | fuel, drone batteries | the **refinery**: already a works; now it turns a well's oil into the side's fuel and halves the burn, as it does |
| supply | holdings and kills, as the proposal has it | earned, not mined | upgrades; and trade | the **depot stores** upgrade |

Zero-sum is the point: the ore and oil on a map are the ore and oil there is. A side that takes a deposit denies it; a side that loses its smelter runs its guns dry over minutes, not seconds; a long match becomes a contest over three or four places on the map rather than a crowd at the depots. Trees stay renewable so a side can always build, if slowly, and nobody is locked out of the game.

## Logistics: workers, and what a hit costs a pillbox

A base today is a depot, what stands near it, and whatever tanks happen to be there. The design gives it a crew: **workers**, a base's own squad, who never board a tank. They do three things, in order: carry (smelted shells from the smelter to the depot, fuel from the refinery, shells from the depot to the base's pillboxes), repair (what the workshop's slow mending does not reach), and build (what the city's plan says next). Roads speed them; a base with no road to its smelter is a base whose guns run dry in a siege. Workers are an abstraction a world can run cheaply: a stock in transit with a travel time along the route, drawn as a small figure on the road.

A pillbox's ammunition then has a source and a fate. It fills from its depot by the workers, not from nowhere; and when the pillbox is hit, its stored shells go up: the stock falls to zero, the blast is drawn, and the pillbox fights on with only what the workers bring and what it makes itself (one shell in ten seconds, as now). A besieged pillbox is a dangerous thing for a minute and a quiet one after, which is what a siege is, and why cutting the road matters.

## How a city develops

A base grows through four shapes, each the squad's and the workers' work on top of the last, and each what the builder role and the base cycle already try to make today:

1. **A camp**: a depot held, two pillboxes brought home, a ring road begun.
2. **A town**: a power plant on its pad, a harvester by the wood, walls at the gate, the castle's two pillboxes inside and posts on the road out.
3. **A works town**: a smelter at the nearest ore and the road to it, a refinery at the nearest well, the depot's stores upgraded, the workshop mending.
4. **A city**: the data centre's fire control and radar, concrete walls, a gatehouse, a dock if there is water, supply roads to the allies' towns.

The order is a plan, not a script: the team's posture leans it (Defend buys plating, Connect buys roads, Economy buys stores), and the brain's improvement slot (`upgrade_vs_mend`) already exists to weigh an upgrade against a mend.

## The quartermaster

Paul's "one teammate stays back issuing the city-building commands while defending" is a role. A person's team already has a builder on Auto whose castle goes round the person's depot, and the guard now keeps building while the castle is unfinished (`crew_stay`). The quartermaster is that builder given the city's plan and the workers to carry it out: it stays within the base's alarm, defends when the base is threatened, and otherwise issues the next item of the plan, buys upgrades with supply by the team's posture, and asks the fleet for ore and oil ground when a stock runs low. It is a `roles` version (`quartermaster`) and a `city_plan` choice (camp, town, works, city) on top of the builder that exists, which is why it comes after the stocks and before the trade.

## Trade, from the game Paul described

The trade mechanics he pasted (ports trade with ports and factories with factories; a payout that grows with distance and is highest between allies; trade units that spawn by themselves and are captured or protected; an embargo for five minutes on an attack, or for good by choice) map onto this game as supply: two depots of allied sides joined by road or water trade supply by the distance between them, with the allied rate above the team rate above a side's own; a convoy is a stock in transit the workers run and a raider can take; attacking a trading partner embargoes the pair for five minutes. The three-way rule already keeps alliances a choice rather than the end of the game. Trade gives a reason to hold a road and to keep an ally, which is what goal 3 (command, not only driving) and goal 5 (longer matches) have both lacked ([82], [83], [86]).

## The staged plan, and what each stage costs

Every stage is a rule change: a `GAME_VERSION` bump, the evidence started anew, every dial promoted before it suspect, and a census before and after. That is expensive, which is why the stages are few and bundled, and why each has its proof written first.

| Stage | Game version | What changes | Proof, written before the run |
| --- | --- | --- | --- |
| 1. The pillbox's stock | 5 | a hit pillbox loses its shells; a pillbox refills only from a depot within reach that has stock (the workers, abstract) | pillbox shots a match fall; a besieged base is taken more often; the guarded-base family still holds at 65% |
| 2. Ore and the smelter | 6 | deposits on the maps; the squad harvests ore; the smelter; depots make shells only from ore; the harvester | a match of 30 minutes has a shape (holdings decide it); shells a match fall by half; a side without ore loses its guns within five minutes |
| 3. Workers and the city | 7 | workers as stock in transit; the city's four shapes; the quartermaster role and the city plan; oil and the refinery's source | building rises without the walk reward; supply as the proposal has it; the upgrades |
| 4. Trade | 8 | allied depots trade supply by distance; convoys; the embargo | alliances form in bots' matches; a trade road is defended |

Stage 1 is one session and touches `step_pillboxes`, `step_depots` and the pillbox's resupply; its only new state is nothing (a stock that falls to zero). Stage 2 is the large one: a map object, a terrain or object kind, a structure kind, and the depot's rule. The map files that carry deposits are new files; the old ones play as before until they are given deposits.

## What the training data should carry

The census logs each team's built, road, kills and deaths already (chapter 6 read them). For the economy they need ore mined, shells smelted, fuel refined, supply earned and traded, convoys taken, and minutes a pillbox stood empty, so that the score's blind spots do not repeat: the trade guard's floors extend to these, and a persona (Venice) can be judged on what it is for.

## Links

[PROPOSAL-UPGRADES.md](https://github.com/treadcore/treadcore/blob/main/documentation/PROPOSAL-UPGRADES.md) · [Too Many Shots](../2026-10-30-balance.html) · [DESIGN.md](https://github.com/treadcore/treadcore/blob/main/documentation/DESIGN.md) · [GOVERNANCE.md](https://github.com/treadcore/treadcore/blob/main/documentation/GOVERNANCE.md) section 5 (a change to the rules wants a trace) · real-time strategy economies and balance [82]–[89].
