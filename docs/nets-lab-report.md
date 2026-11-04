# The Nets Explorer: Every Learned Net, Where It Has Been, and a Vault That Keeps Only on Request

*Paul Richeson · Lab Report — IEEE Format · 3 November 2026*

Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery.

Companions: orrery `tools/nets.py`, `src/nets.rs`, `tools/fleet-queue.py` (the `nets` verb), `tools/plans/treadcore-view.py`, `src/draw.rs` (the clip); treadcore `source/treadcore-brain/src/net.rs` (the file), `learn.rs` (the milestones), `styles.rs` (the roster), `documentation/LAB-REPORT-BRAIN.md` sections 136 and 137.

---

## Abstract

A learned net is a `.bin` file of a few thousand floats, and the fleet makes one at the end of every train run and every school. Until today each lay where it fell: in its run's results directory among twenty thousand others, in treadcore's `nets/` when someone copied it by hand, in a model slot when the planner promoted it, in a style's row when a lab report named it. Nothing said where a net had been, what had read it, or why it was kept, and nothing kept one on purpose. This report builds the explorer: a register of every net the fleet made or keeps (`tools/nets.py`, into `plan/nets.json`), a page in orrery's Results that draws the register as one scrolling window of cards (`src/nets.rs`, the Nets page), and a vault with four verbs, capture, promote, expire and note, THAT COPIES NOTHING UNASKED. A card carries the net's journey as a ribbon of stations, its reads as a gauntlet strip and held-out bars, its weights as a sixteen-square fingerprint with the listening by sense group and the speaking by head, and its notes; the window's left rail draws the lineage from each parent net to the runs that began from it. The register of this fleet holds twenty-one nets and refreshes in about a second; the vault holds one copy, the first-minute net, a milestone by request, and a note on a net whose copy was expired, which is the policy working as designed.

## I. The ask, and what stood in its way

Paul, 3 November: "a design implementation of those .bin that travel through Orrery and the computations. Can I get an explorer of milestones that are promoted. I want an explorer to visually analyze and annotate the results and describe in the program why it's useful for what and where. Make it a scroll window. We like complex visualization techniques. We would need a way to save, capture, and expire some of these .bin files. We need an efficient way to keep them for milestones, but not unnecessarily or even slow down, so maybe by request only, with promotion abilities."

Four things, then: an account of where the files go and what computes on them; a window to look at them in; the words for what each is for; and a keeping policy that costs nothing until someone asks. The obstacle to the first three was that no single record existed. The train harness writes `NAME.bin` and `harness.log` into `out/rNNNN-train/`; the school writes `best.bin` and a round a file; the planner copies a promoted net to `models/K.bin` and writes a row of `models.tsv`; a person copies a net to `nets/` and adds a row to `styles.tsv`; the gauntlet reads whatever `MILESTONES` and `GAUNTLET_NETS` name and writes `gauntlet.tsv`; the lab report names files in prose. Six records in six forms, none pointing at the others. The obstacle to the fourth was the opposite: the results tree is where every net already lies, and a vault that copied every net would double a directory that is already the largest thing on the disk and slow the poll that reads it.

## II. The register: `tools/nets.py`

The register is one document, `QUEUE/plan/nets.json`, rebuilt by `tools/nets.py QUEUE refresh` and read by `treadcore-view.py` into orrery's status document under `nets`, beside `gauntlet` and `personas`. The view script starts a refresh in the background when the file is older than five minutes, as it does for `analysis.json`, and never waits for it.

**Discovery is narrow on purpose.** The tool reads treadcore's `nets/*.bin` and `nets/patches/*.bin`, the queue's `models/*.bin`, the vault's `*.bin`, and the results tree only at `results/r*-train/fleet/q-grove/out/*/*.bin` and `results/r*-school/.../best.bin`. The census directories, which are the twenty thousand, are never listed. Every file is hashed once (sha256, the first twelve hex digits are its name in the register) and cached by (path, size, mtime), so a refresh after the first hashes new files only: 1.0 to 2.2 s on this fleet.

**One record a sha.** The same bytes in `nets/`, a model slot and a results directory are one net that travelled, and the register says so: a record carries every copy's path and how it is held (ships, slot, vault, result), and takes the name people use, the shipped name first, then the slot's, then the run's. A school's net is named `rNNNN-best` so two schools' bests do not collide.

**What a record holds.**

| field | from | what it says |
| --- | --- | --- |
| `run` | `runs/rNNNN.json`, the out directory, `keeper.log` | the run that made it: kind, asked when and by whom, its courses, its parameters, the machine |
| `parent` | the run's `start` | the net the search began from |
| `held_out` | `harness.log` | the harness's held-out lines: course, passed of n, reward, floor, verdict |
| `curve` | `harness.log` | forty points of the population's mean and the net's score by generation |
| `gauntlet` | `build/train/gauntlet.tsv` | the share passed on each of G1 to G17 in the last gauntlet record, by the file's stem |
| `sections` | `LAB-REPORT-BRAIN.md` | the sections that name the file, number and title |
| `starts` | `runs/*.json` | the runs that began their search from it |
| `slot`, `style`, `milestone` | `models.tsv`, `styles.tsv`, `learn.rs` | the slot and generation; the style's slot, origin and note; whether it is a milestone by code or by the vault |
| `numbers` | the file | sizes, parameters; each layer's Frobenius norm, max, sparsity and first three singular values; the fingerprint; the listening; the speaking |
| `vault` | `vault/vault.json` | the kept copy, its origin, when captured, the notes |
| `why` | all of the above | the sentence (section IV) |

**The numbers.** The file is `TCNET1`: a magic, the count of sizes, the sizes, then each layer's weights and biases as little-endian f32 (`net.rs`). The tool reads it with `struct`, no numpy (orrery and its tools carry no dependencies). The fingerprint is the first layer's |w| pooled to sixteen by sixteen, rows the hidden units, columns the inputs in the tank's order. The listening is the mean |w| of the first layer's columns each sense group owns (compass 88, body 12, nav 6, contacts 18, hints 9, shells 5, air 5, the economy 17, as `analysis.py` lays them out; a net of 133 inputs stops at the group its width reaches). The speaking is the mean |w| of the last layer's rows each head owns (drive 10, gun 11, lead 3, mortar 11, drone 5, squad 4, signal 3). The singular values are by power iteration with deflation, twelve steps, three values: an octave of the spectrum, enough to say whether a layer is one direction or many, at a cost of milliseconds. A file that is not `TCNET1` is registered with what it is instead: `duelist.bin` is 2,340 raw floats, a crucible hybrid's weights; `patches/1.bin` is a `TCP1` patch, a transform over the rules and not a net.

## III. The window: `src/nets.rs`

The Nets page is the fourth key of Results, between Net and Algorhythm, page 13 (`ORRERY_FRAME_PAGE=13`). Under the chapter's strip it has a filter row, the vault's line, two verbs that are the page's own (Expire..., Refresh; drawn for an operator only), the register's line, and the window.

**The window scrolls in pixels, not rows,** because a card's height is its own: the sentence wraps to the window's width, the notes add a line each, an opened card is tall. The wheel moves it three pixels a unit; the bar on the right is a thumb the window's share of the whole, and a press on it jumps. The canvas took a clip rectangle for this (`draw.rs`): every pixel set while the cards draw must fall in the window, so a card half scrolled off paints only its visible half and the header above keeps its own paint. Clipping belongs in the canvas and not in each drawing call, because a label, a disc and a rectangle all cross an edge the same way, and glyphs go through the same setter.

**The card** is a black readout set into the metal, light text in it, as the house draws every reading, its left edge coloured by what kind of thing it is (accent a milestone, green a slot, amber a style, the vault's blend a kept copy, the line colour the rest). From the top:

1. The name, in the large face; a click opens the card tall or closes it, and an opened card scrolls to the top of the window. Beside it the badges: milestone, slot K with its generation, style S or clone, vault, and how it is held. On the right the identity: sha, size, written when, the sizes as 160-64-64-47.
2. The sentence of what it is for, three lines (six when open), the whole in its tip.
3. Three columns. JOURNEY: a ribbon of stations, a disc each, present stations only, so the ribbon's length is the story: the run on its machine, results, nets/, vault, slot K, style S, and a ring for each run that began from it; labels alternate above and below the line; under it the parent, the run's parameters and courses, and the lab report's sections on the right. READS: G1 to G17 as a strip, green at nine tenths passed or better, a blend toward red below, red at nothing, the tile colour unread; the held-out courses as bars with the floor as a tick and passed-of-n on the right; the training curve as two lines in a box, the population's mean dim and the net's own score light. WEIGHTS: the fingerprint, a two-ramp colour from the readout's black through the accent to white with a gamma that spreads the middle (one ramp made the whole square one green); the listening as bars that run from half the quietest group to the loudest, because the ear's differences are tenths and bars from zero all look full; the speaking by head the same way; a line a layer with its shape, norm, three singular values and the share of weights under a thousandth.
4. The notes, newest first, six at most: the `styles.tsv` note and the vault's. Then, for an operator, the verbs: Capture, Promote or Demote, and Note..., which opens a field in the card; Return sends the line to the vault's register.

**The lineage rail** runs in the margin on the left of the cards: for every card whose parent is also shown, a vertical line from the parent's title to the child's, a disc at the parent and a ring at the child, a colour a family, nested by a few pixels when families overlap. A parent not shown under the current filter is a stub that says "from". On this fleet it draws `logistics` to `first-minute`, and will draw `first-minute` to r0163's net and `logistics` to r0164's when they land.

Every element has a tip that says what it is and where it came from: the strip's cells name the gauntlet and its source file, the stations name the path, the fingerprint says what its rows and columns are and the brightest cell's value, the layers' lines say what a singular value trio means. The page describes itself; that was the ask.

## IV. The sentence: why it is useful, for what and where

`why_of` in `nets.py` writes one sentence a net from its record, in this order: what kind of thing it is and where it is held; the run that made it, its generations, its start and its machine; the style it plays or the slot it holds; a milestone's standing as the yardstick; what it holds on the gauntlet and what it has nothing on; the held-out courses passed and not yet; the runs that began from it; the sections that read it. A person can check every clause against the files the register points at. Two of this fleet's:

> A milestone, shipped in treadcore's nets/. Holds model slot 5 (generation 1) and plays whole teams in the league's censuses. On the gauntlet it holds G1, G2, G3, G4, G8, G15, G16. It has nothing on G6, G9, G10, G12, G13, G14, G17. Read in LR 100.

> A trained net, shipped in treadcore's nets/. Made by run r0158 (train, 400 generations from logistics.bin) on a fleet machine for the courses g13-ore-to-the-smelter, ... 12-the-first-minute-naval. On the gauntlet it holds G1, G2, G3, G4, G13, G14, G15, G16, G17. It has nothing on G5, G6, G9, G10, G11, G12. Held out it passed 7 of 8 courses; not yet 12-the-first-minute-naval. Runs r0163 began from it. Read in LR 136, 137.

The sentence is generated and says so by its form; a person's reading goes in the notes, which are the other half of "annotate".

## V. The vault: capture, promote, expire, note

`QUEUE/vault/` holds `vault.json`, the register of kept things, and the copies, named `NAME-sha.bin`. The verbs are `tools/fleet-queue.py QUEUE nets ...`, delegated whole to `nets.py`, so the page's buttons are one verb each and the shell has the same ones.

- **capture PATH|NAME [--as NAME] [--why TEXT]**: copy the file into the vault with its sha and origin; a name in the register means the registered net wherever the shell stands. The same bytes are never copied twice. A net that had notes before a copy gets the copy beside them.
- **promote NAME [--slot K]**: mark it a milestone, capturing it first if it was not kept. With `--slot K`, copy it to `models/K.bin` and write its row of `models.tsv` in the planner's form (generation one past the highest), which is the league's promotion by hand.
- **demote NAME**: take the milestone back; expire may then remove the copy. A milestone named in the brain's code (`MILESTONES` in `learn.rs`) stays one whatever the vault says.
- **expire [--days N] [--do]**: list the vault copies that are no milestone, no slot and no style and older than N days (14); remove them only with `--do`. THE RECORD AND ITS NOTES STAY WITH NO COPY, and a line is added saying when the copy went, so what was learned of a net outlives its bytes and a later capture joins them. The page's Expire... button lists on the first press and removes on the second.
- **note NAME TEXT**: a dated line in the register, copy or no copy.
- **forget NAME**: remove the record and its copy; refused for a milestone.

The policy, in the register's own line: the register points; the vault copies only on capture; expire removes vault copies that are no milestone, slot or style, older than 14 days, and only with --do. Nothing runs on a timer. The cost of not asking is zero bytes and a refresh of a second.

## VI. What was read while building it

The register's first refresh found twenty-one nets: thirteen shipped, six in slots (two of them also shipped milestones, `map7a` and `map4`), one that lies only in its results directory (r0021's `phase1`, a milestone by name in `learn.rs` whose shipped copy is other bytes, which the register shows by its two shas), and the two that are not nets. The lineage it could draw was one edge, `logistics` to `first-minute`, because r0158 is the first train run whose record carried a `start`; the older runs' records are empty, and the page says so in place of their numbers. `g6-r0045-phase1` in slot 7 has the sha of r0037's `phase1` (slot 2): the planner promoted the same bytes twice under two names, which the register's one-record-a-sha rule shows in a single card with four copies. The verbs were run through in order on the live queue: a note on `bc1` with no copy, a capture of `first-minute` with a reason, its promotion, an expire at zero days that kept the milestone and listed nothing, a capture of `bc1`, an expire at zero days with `--do` that removed `bc1`'s copy and left its two notes; the vault filter draws both cards with the right buttons (Demote on the milestone, Capture on the expired).

## VII. Limits, and what is next

- The fingerprint is the first layer only, and a wash of middling cells; a per-column rank would show the louder inputs plainer. The second layer is read by its norm and singular values alone.
- The journey's machine comes from `run.env` where a census writes one and from `keeper.log` for a train run; a train run older than the log's tail reads as "a fleet machine".
- A model slot's promotion by hand (`--slot`) writes the planner's file while the planner may be reading it; it is a verb for a person at the shell, and the page offers only the milestone.
- The lineage draws parents by name; a net renamed between its run and its shipping is matched by the file's stem, and a parent never registered is a stub.
- Not built: a diff of two nets' fingerprints side by side; the vault's copies on the fleet's share rather than this Mac; a card for a crucible hybrid's weights, which the register names but does not read.

## VIII. Links

Orrery: `tools/nets.py`, `src/nets.rs`, `src/draw.rs` (the clip), `tools/fleet-queue.py` (`nets`), `tools/plans/treadcore-view.py` (`nets()`); the frames `ORRERY_FRAME_PAGE=13 ORRERY_FRAME_OPERATOR=1 ORRERY_FRAME_SCROLL=px ORRERY_FRAME_OPEN=name ORRERY_FRAME_FILTER=n`. Treadcore: `net.rs` (`TCNET1`), `learn.rs` (`MILESTONES`, `GAUNTLET_NETS`), `styles.rs`, `nets/styles.tsv`, `build/train/gauntlet.tsv`, LR 136 and 137. The plan: chapter 15 (the testing plan), chapter 6 (what the numbers said).
