# The Film Directive: a film script beside every lab report

*Orrery · treadcore.org · standing directive, from 13 November 2026 · MIT License, Copyright (c) 2026 Paul Richeson*

Paul, 13 November 2026: "It would be nice to have an animation script per html markdown combo of lab reports from this point forward as a general directive ... to follow up and attempt animations after lab report. We should definitely keep the animation scripts parallel to documentation. Maybe have a separate youtube (not github) output folder for publishing."

This file is the directive and the prompt. The lab report that argues it, with the code, is *A Film Beside Every Report* (`docs/film-lab-report.md`).

## The directive, in one paragraph

**Every lab report from 13 November 2026 on is followed by an attempt at its film.** When a report's Markdown and its page are written, the same session writes the report's storyboard and film script beside them, renders stills to check it, renders the film if the machine has the time, builds its page and its YouTube kit, and says plainly what was rendered and what was only attempted. The film's script is kept in the repository parallel to the report; the finished film for publishing is kept outside it.

## Where things go

| What | Where | In the repository |
|---|---|---|
| The report | `docs/NAME-lab-report.md`, `docs/NAME-lab-report.html` | yes |
| The storyboard: the film as data | `docs/NAME/storyboard.json` | yes |
| The film's script, when the shared one is not enough | `tools/report/NAME_film.py` (on `tools/report/film.py`) | yes |
| The film's page, stills, captions, narration | `docs/NAME-film.html`, `docs/NAME/step-*.svg`, `captions.vtt`, `teleprompt.txt` | yes |
| The film for the page | `docs/NAME/film.mp4`, 720p, under 15 MB | yes |
| The kit for YouTube: the 1080p film, title, description with chapters, captions, thumbnail | `output/youtube/NAME/` (`ORRERY_OUTPUT` moves it) | **no**: `output/` is ignored |

`NAME` is the report's own short name (`seeds`, `loop`, `process`). One name ties the report, the storyboard, the script, the page and the kit.

## The order of work

1. **The report first.** The film is made from a finished argument, never the other way.
2. **The storyboard.** One JSON file: the title and subtitle, the blocks and where they stand, each step with what moves, why, the rule, and its narration, the opening, the close, the credits. Start from `docs/process/storyboard.json`.
3. **The narration, read aloud once.** A scene is as long as its words at 150 words a minute. If a sentence is hard to say it is hard to hear: rewrite it.
4. **Stills before film.** `process_film.py still T OUT.png` for one moment of every kind of scene. Look at each. A full render is twenty minutes drawn and two hours in Blender; a still is a second.
5. **The film**, drawn: `process_film.py film`. In Blender when the report has a place or a recording worth standing in: `process_blend_film.py frames A B DIR`.
6. **The page**: `process_film.py page`. **The kit**: `process_film.py youtube MASTER.mp4`.
7. **Say what happened.** Rendered and watched; rendered and only stills checked; attempted and not rendered. Never "done" for a film nobody has seen in motion.

## The method

1. **The words first.** Narration sets every length. A `|` in the narration is a cue, and the picture's moves are written against cues, never against seconds.
2. **One stage, drawn once.** Every block has one place for the whole film. Scenes move a camera and change what is lit.
3. **Every frame is a function of its time.** No state carries from frame to frame, so any frame renders alone, a still is a frame, and frames render a core each.
4. **A move gathers, goes and lands.** The source dips, the thing travels on an ease in and out with a trail, the destination swells. One thing moves at a time.
5. **Outside in.** The whole first, far off; then its few largest parts; then the borders between them; then inside, one loop at a time. Every step shows the path down to it and a small map of the whole.
6. **A border is an event.** Where something crosses from one territory to another the film marks it: a ring, a change of colour, and the rule for crossing in words.
7. **A cold open.** Before the title, one true thing from the report that should not be possible, then why it is, then the question the film answers. From the report's own numbers, never invented.
8. **Words stand on a plate.** Nothing a viewer reads is laid straight over a moving picture. Text has fixed places: the step's words bottom left, the teleprompt bottom right, the path top left, the small map top right.
9. **The background follows the script.** If recordings play behind the diagram, the storyboard says which is lit while each step is told (`"field": "M0030"`).

## Style

- **Drawn films** follow 3Blue1Brown: near-black ground, its blue, green and yellow, yellow kept for what the eye should go to, words written on a letter at a time, a faint plane under the figures, a yellow rectangle round what has just landed.
- **Narration** is plain and exact: short sentences, a number said the way a person says it, one idea a sentence, the wonder left to the facts.
- **Blender films** are the same film in a place: the diagram as slabs and blocks, arrows as tubes, charts as boards standing beside it, recordings reenacted on fields behind it, and everything read parented to the camera one unit in front of the lens.

## Titles, credits, licence

- **A report** keeps the house form: `# Title: Three or Four Clauses`, then `*Paul Richeson · Lab Report — IEEE Format · DATE*`, the byline and licence line, Companions, Abstract, sections in roman numerals, References in IEEE style.
- **A film** takes the report's subject as its title and ends on its credits:

  > Orrery · treadcore.org
  > Paul Richeson: producer, animator, writer, coder, implementer, developer, founder
  > Team pair: Claude Code (the model's name)
  > MIT License · Copyright (c) 2026 Paul Richeson

  These are the storyboard's `credits`; the close holds twelve seconds so they can be read, and the YouTube description carries the same four lines.

## What not to do

- Do not time a scene by hand. Change the words.
- Do not render a film to find a mistake a still would show.
- Do not test a verb that pushes or publishes with a flag you have not read the code for.
- Do not put the 1080p master in the repository, nor anything over 15 MB on a page.
- Do not upload. The kit is for a person to take to YouTube.
- Do not claim motion was checked when only stills were.

## The prompt

Paste this after a lab report is written, with `NAME` set:

```text
The lab report docs/NAME-lab-report.md is written. Now attempt its film, by docs/film-directive.md.

1. Read the report and docs/process/storyboard.json. Write docs/NAME/storyboard.json: the report's
   argument as blocks and arrows (or its own figures as scenes), each step with what moves, why, the
   rule, and a narration of 30 to 50 words in plain exact sentences. Open cold on one true number from
   the report that should not be possible. Close on its principle and the credits.
2. If the shared script cannot draw it, write tools/report/NAME_film.py on tools/report/film.py: every
   frame a function of its time, scenes as long as their narration, cues for every move.
3. Render one still of every kind of scene and look at each. Fix what is wrong. Then render the film
   (drawn; in Blender too if the report has a place or a recording to stand in).
4. Build the page (docs/NAME-film.html) and the YouTube kit (output/youtube/NAME/). Publish the page.
   Commit the scripts, the storyboard, the page and the 720p film; never the master.
5. Report what was rendered, what was only checked as stills, how long it is, and what is open.
```
