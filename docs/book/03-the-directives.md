# The directives, in plain words

Paul's prompts arrived as fast typing, often one line, often mid-run. The check-in reports quote each one word for word; this chapter gives their sense, spelling put right, grouped by what they were about and dated, so a reader can see what the project was told and in what order. Where a directive was later reversed or refined, both are kept. Nothing here is a quotation; the originals are in the [check-ins](https://github.com/treadcore/treadcore/tree/main/documentation/checkins) and in the commit messages, which carry them in parentheses.

## On how the work is done

- **18 October.** Work one step at a time, synchronously; record every step with a lab-report section, a roadmap item, a changelog line, a journal entry and an IEEE-style check-in.
- **20 October.** Keep all the new behaviour and keep adding; the brain must still work, even if slightly less well; the scalars are adjusted after the features are in, but each feature lands with a sensible starting number.
- **28 October.** The computer running orrery should be the one pushing; the queue should promote by itself unless auto mode is off, and auto mode should be on.
- **29 October.** Make the search's A/B testing of alternate functions more efficient, so a brain can branch into parallel versions toggled like weights, as an enum.
- **30 October.** Instead of a fixed list of locked values, one general rule: every number may have a minimum and a maximum, and a decree sets both equal.
- **1 November.** Write a report on each of the training methods; streamline and unify them into one coherent process shown as a Gantt chart with dependencies, machine names, expected durations, and the task with the most dependents marked as next essential. Commit, push, implement.
- **1 November.** Use orrery and give a screen-by-screen breakdown; add an inspector with hover information on just about every piece of data.
- **2 November.** Max fix mode: read all the lab reports a section at a time and write the long post-mortem; rewrite the goals and the how-to, linking to past reports without editing them; less specifics, more overview; summaries of prompts and directives, spell-corrected and simplified; only proven generational techniques, cited in IEEE form.

## On the game's rules

- **16 October.** Increase everyone's sight, especially the air units'; a downed tank has twenty seconds to be repaired before death and respawn; reference each drone against real systems, with similar flight times and a rotation of marks.
- **17 October.** More momentum and a more consistent top speed; a tank should still move forward through a turn; the tanks should prioritise the wedge.
- **18 October.** Think of more base upgrades and ways for players to buy them.
- **30 October.** There is too much ammunition; reward leaving the base full and coming back empty; a longer reload for mortars prices the shot itself; do not get castles of turrets, soft-enforce it; a tank in a castle has better protection; the trees need to regrow; turn advance_plan and mine_plan on by default; lower the guarded-base family's floor to 65%; reward going forward heavily.
- **2 November.** Lock the physical constraints into ranges first; ranges of artillery, direct fire, interceptors and long-range drones should be reasonable for their distances, with flight times at our scale; a scale system, since maps differ in size; bonuses for refineries, smelters and wood harvesters; a fun zero-sum economy where every mineral but growing trees is finite; a logistics layer where each base has a worker that recharges it, and a pillbox hit loses its ammunition and keeps only what it makes afresh; describe how cities develop and refineries are built; perhaps one teammate stays back issuing the building orders while defending.

## On the bots

- **17 October.** The bots should hold a line and never stand about; a fleet of five in a wedge; rotation between a defence point and a push point.
- **19 October.** Yes, all three landfall behaviours on; the dodge should be planned rather than reflexive.
- **20 October.** Give smoothing an insignificant coefficient as a weight rather than a switch.
- **25 October.** Personalities, step one: named play styles as weight files.
- **29 October.** A parallel B-style tank brain with the ability to toggle between them like weights; think like different units (roles); an enum of up to eight alternate AI models fed back into the game.
- **30 October.** Think of the program as a synthesizer: analogue dials, whole-number switches, and a learned transform that may override the rules when it is confident; pings should carry a kind (help, caution, warn, defend); the biorhythm waves should be about a minute long with offsets, like biorhythms.
- **1 November.** Bot styles 0 to 7, selectable by name; connect the biorhythms to the output temperament and correlate them with the matrix; expand the matrix's dimensions if it has no tail; fix the desire to build; promote the fortify dial anyway.
- **2 November.** Named personas, differentiated by the topography of local maxima, perhaps after Civilization V's civilizations by their historic strengths; a wingman trained to follow my moves, like an escort mission; training gauntlets to converge on all these abilities; maybe a larger transform matrix, or more layers; toggles between goals and personalities; ways to assign fleet messages; ally bot play.

## On the search and the fleet

- **27 October.** Make the 1080 Ti machine run CUDA on a setup NVIDIA supports; a login that shows the node's address, GPU and state; bring the second GPU machine up to date.
- **28 October.** Bring every make target into orrery as a button; the keeper should be part of orrery and keep the Mac awake; a brushed-metal look; five chapters in the order the work goes.
- **29 October.** A difficulty like a block chain's, aiming at one promotion every twenty minutes; then, measured, one every two and a half hours; stages that grow more gently; a script that updates each machine daily and at boot; a settings program that deploys and configures storage.
- **30 October.** Verify that the A/B testing and the enum matching are finished before anything is published; elect and prove a candidate quicker; stop and resume each machine individually; add a way for the queue to stop a single job; create and install a listener on the Ubuntu and Alpine machines; it is not one-on-one, it is one room.
- **31 October.** Stop all queue tasks while the brain is redesigned.
- **1 November.** Look at europe first and find the fault; follow the recommendations and do it, documenting what is measured; continue implementing; is there any consistent bottleneck, just trying to speed it all up; can we get a little less noise in the promotions; the operator certificate should last thirty days.
- **2 November.** Do it (restore the building fix the search undid, guard what the score does not weigh, fix the pinned test); work only in this session, no background agents.

## On the console and the reports

- **28 October.** How do I get an application launcher after make install; write a lab report about the Mac applications and about the AppKit window.
- **30 October.** A three-dimensional view of the local maxima, something like a spectrogram, an analysis of the matrix, the input sensors as the tank sees them.
- **1 November.** Perform the terrain visualisation for each dataset, with regions of operation that can be selected, so the search can be seen working on all the maxima; write a lab report on the dead clock battery; pictures from the real game on the VM.
- **2 November.** Markdown converted to chaptered HTML linked from the site's index; a Lab Reports section; diagrams; the output in IEEE format.

## What the directives did not say

Three questions came back to Paul and are still his to answer; the plan marks each where it bears: whether bots should answer a person's ping whatever the pings switch says (they did not, after pings-off was promoted on a bots-only census); whether to send Raider or Expander down the road as a candidate; and whether the 0.25-a-tile reward for going forward should be repriced, since it is what keeps paying the search to stop building (chapter 6).

## Links

[check-ins](https://github.com/treadcore/treadcore/tree/main/documentation/checkins) · [journal](https://github.com/treadcore/treadcore/tree/main/journal) · the commit messages of both repositories, which quote each prompt · chapter 4 for the same weeks as a timeline.
