# The register of unfinished work

Every report keeps its open items honestly, which is why they can be gathered. Read section by section, the twenty-eight orrery reports and design documents leave 380 open entries; many are the same item seen from two reports, so about 250 are distinct. Treadcore's roadmap adds its own backlog (goal 3's four steps, goal 5's three, the two-router proof). This chapter sorts them by area, names the ones that matter, says which the asks of 2 November cover, and gives each group a disposition: *do now* (this plan builds it), *design now* (this plan designs it and names its first step), *later*, or *refuse* (with the reason). The counts are of entries, not of distinct items.

## By area

| Area | Entries | Do now | Design now | Later | Refuse |
| --- | --- | --- | --- | --- | --- |
| The game's rules and economy | 24 | the physical ranges; the scale header | the economy, logistics, cities (chapter 13) | the upgrades proposal's traces; the castle's drone share | |
| The programmed brain | 46 | the wingman's numbers as weights; personas | per-role ladders; a learned target pick; rewritten functions | think_every, think_order | |
| The learned net, the transform, crucible | 38 | the escort gauntlets | the transform's shape (chapter 12) | a boldness output; netlets; the crucible bridge to slot 7 | |
| The training line and planner | 52 | | the testing plan (chapter 15) | carry's gain measured; a check-in per trial; a tournament of two passing versions | a family difficulty adjustor (refused on 1 November) |
| The judge: score, census, terrain | 31 | | | the reward breakdown on every candidate's report; an occlusion census of the senses; regions pressed on the live fleet | |
| The fleet and its machines | 54 | | | storage (Hexamir, Ceph, the mirror); jaguaribe's battery; power on; persistent logs on Copal; the real listener install | Observe (a capture daemon on every node) |
| The console's screens | 41 | a Lab Reports page; the hold as a row | every feature an element (chapter 14) | screen merges; fewer clicks to frequent paths; a certificate warning | |
| The game's window | 22 | personas on the launch menu | goal and personality toggles, fleet messages, ally play (chapter 14) | a game-side slot for a net; the lobby's bots row | |
| Reports, releases, the site | 27 | this book; the site's reports section | | notarization; a second Mac; the two-router proof | |
| Orrery's console core (wire, RDP, refactors) | 45 | | | the five priced refactors; hypr-rdp's unknowns; the credentials pane | AES fallback |

## The items that matter most, in order

1. **Numbers that were constants were searched as preferences.** `base_r` walked 16 → 32 → 8 → 6.15 in a day; `coming_r` sits at 221 tiles on a 128-tile map. Do now: chapter 9's ranges.
2. **The score cannot see building or fights.** Found on 1 and 2 November; the guard holds it for now; the reward for going forward (0.25 a tile) still pays the search to stop building. Paul's decision; chapter 13 prices it.
3. **A promoted model plays in the census only.** Neither the game's bots nor the families deal a net or a transform; the client cannot load one from a file. Design now, in chapter 14: the game-side slot.
4. **The wingman cannot be told anything.** A person's two wingmen follow by five constants nobody can move; a style cannot be chosen for the autopilot apart from the wingmen; the U page's style dial acts only at the next match. Do now and design now: chapter 11 and 14.
5. **Half the maxima are unsettled and most maps draw none.** The terrain is thin; personas drawn from it are seeds, not results. Chapter 10 says so and certifies each by census.
6. **The economy is a proposal with one trace.** Supply and upgrades were designed on 18 October and traced on the 21st; nothing since. Chapter 13 folds them into the zero-sum economy.
7. **The real fleet buttons are proved in containers, not on the machines.** The listener install needs a root password typed on each machine. Later: a person's afternoon.
8. **Storage.** Shared storage is a staged script and a plan; nothing formats a disk. Later, and by hand first.
9. **Pinned tests.** Fixed three times; a fourth can still exist. Chapter 15's testing plan adds a lint: a brain test may not read a searchable default without naming it.
10. **Two flaky sftp tests.** About one run in three while the Mac is busy, in code this work never touched. Later; they do not gate the fleet.

## What the asks of 2 November do not cover, and stays open

- The crucible bridge to slot 7 and the league (the transform clone of a champion on treadcore's senses); crucible's champions still do not play treadcore except inside the Duelist.
- Why `ladder = hunt_first` plays games identical to the default; exact-zero reads are flagged now, the cause is not found.
- A check-in record per trial; the carry's gain measured; the simulation's pace figures corrected for what a generation discards.
- The fit's uneven coverage: 21 weights read one to four times while `dodge_horizon` has hundreds.
- The console's priced refactors (one SSH connection per node, row blits, one byte writer, one pane lifecycle), each written up with its price and none urgent.
- Power on, notarization, a second Mac, the two-router proof, the Raspberry Pi suite.

## Refused, and kept as refused

- **Observe** (a thumbnail of every node): a capture daemon on every machine with no deadline. Refused in the console's design and again here.
- **A family difficulty adjustor**: families are floors on behaviours the census cannot see; easing them defeats them.
- **Lowering the bars to speed the line**: measured on 29 October; the pace is seeds.
- **AES in the TLS client**: 370 times slower than ChaCha by hand; one suite is the design.

## Links

The open-items sections of every report listed on the [Lab Reports](../index.html) page · [ROADMAP.md](https://github.com/treadcore/treadcore/blob/main/documentation/ROADMAP.md) backlog · [plan.md](https://github.com/richeson/orrery/blob/main/docs/plan.md) "Backlog after 29 October" · [refactor.md](https://github.com/richeson/orrery/blob/main/docs/refactor.md).
