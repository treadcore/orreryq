#!/usr/bin/env python3
"""double.py: assembles docs/double-lab-report.md, the double report: Part One is the whole-line
report as it stands, Part Two the story and the guide. Each screen's section comes from SCREENS
below, with its numbered marks drawn over the picture, and its answers from tools/plans/line.json,
so the guide and the panels on the screens say one thing."""
import html
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.normpath(os.path.join(HERE, "..", "..", "docs"))
LINE = {s["key"]: s for s in json.load(open(os.path.join(HERE, "..", "plans", "line.json")))["screens"]}

STYLE = """<style>
.shot{margin:1.3em 0}.shot .frame{position:relative;border:1px solid var(--line);border-radius:6px;overflow:hidden;background:#111}
.shot img{display:block;width:100%;height:auto}.shot svg{position:absolute;inset:0;width:100%;height:100%}
.shot circle{fill:#ffd21f;stroke:#000;stroke-width:2}.shot text{font:700 20px var(--cond);fill:#000;text-anchor:middle;dominant-baseline:central}
ol.marks{font-family:var(--cond);font-size:var(--step--1);columns:2;column-gap:2em;margin:.5em 0 1.2em;padding-left:1.6em}ol.marks li{break-inside:avoid;margin-bottom:.35em}
@media (max-width:760px){ol.marks{columns:1}}
.answers{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:.8em 1.4em;margin:.8em 0;font-size:var(--step--1)}
.answers b{display:block;font-family:var(--cond)}
.pair{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:1em}
</style>
"""


def shot(name, marks=(), cap="", size=(1400, 860)):
    dots = "".join('<circle cx="%d" cy="%d" r="15"/><text x="%d" y="%d">%d</text>' % (x, y, x, y, i + 1) for i, (x, y, _) in enumerate(marks))
    svg = '<svg viewBox="0 0 %d %d" aria-hidden="true">%s</svg>' % (size[0], size[1], dots) if marks else ""
    alt = html.escape(re.sub(r"<[^>]+>", "", cap) or name, quote=True)
    out = '<figure class="shot"><div class="frame"><img loading="lazy" src="double/%s.png" alt="%s">%s</div>%s</figure>\n' % (name, alt, svg, "<figcaption>%s</figcaption>" % cap if cap else "")
    if marks:
        out += '<ol class="marks">%s</ol>\n' % "".join("<li>%s</li>" % t for _, _, t in marks)
    return out


# (key, heading, file, how to use it, marks, [(hover file, what it shows)])
SCREENS = [
 ("Machines", "Machines, Machines", "machines", "Pick a machine on the left. Probe reads it and changes nothing. A new machine goes in the box at the foot as <code>NAME user@address</code>, and Join puts it in the fleet. Every recipe that changes a machine asks first and shows what it will run.",
  [(310,105,"The selected machine, lit. Green words mean it is new and not yet in the fleet."),(700,135,"Everything the probe read: system, CPU, GPU, disk, tools, power-off."),(1225,77,"Pull projects, Join and Probe act on this machine."),(830,320,"Each recipe's state: not for it, applied, not applied (amber), ready to run."),(1335,338,"Apply or Run. Each asks first, then types its command into a Sessions tile for you."),(280,617,"Add a machine."),(820,470,"What was done here, and when.")],
  [("hover-machines","Hovering a row: its recipes, its system and kernel, and what a click does.")]),
 ("Media", "Machines, Media", "media", "The wizard for making a machine from nothing: answer the interview, make the cards, then Prepare, Build and Write in order. It reads the steps from the Copal checkout. You need this only when a machine is new.",
  [(170,94,"The job, in one line."),(250,165,"The steps in order, the one you are on first."),(1200,165,"The command each step runs, for anyone who prefers typing it."),(250,281,"The buttons for this step.")], []),
 ("Storage", "Machines, Storage", "storage", "Pick a machine to read its disks. To share a path, choose a machine, type the path and press Share; then press where a share's row meets a machine's column to mount it. <strong>Nothing here formats a disk.</strong> A change is staged in a Sessions tile, and a person presses Enter.",
  [(305,108,"A machine: its fastest link, memory, disks, how many are free, and its part in Ceph."),(780,115,"A ZFS pool, with its size and health."),(650,170,"Each disk, its role and what it holds."),(920,575,"Type a path to share."),(330,605,"The patch bay: a row a share, a column a machine."),(1290,604,"How to share: NFS, sshfs or SMB.")],
  [("hover-storage","Hovering a machine: memory, link, disks that could join a pool, its Ceph role.")]),
 ("Projects", "Projects", "projects", "The one place that says who works on what. Press On or Off where a machine meets a project. Pause and Stop now at the top act on a whole project. This is where to look if a GPU sits idle.",
  [(450,135,"treadcore: queue state, candidates, the machines set to run it."),(1050,135,"crucible: each island's generation, how it does against the yardstick and the ladder, its speed."),(280,292,"Pause or stop a whole project."),(482,393,"A machine on or off a project. Here boburner's GPU is Off, which is why it is idle."),(1270,360,"Pause, Stop now or Remove a machine."),(225,735,"The ladder: the milestones crucible's champions are examined against."),(600,795,"The latest exams, in errors against a milestone.")],
  [("hover-projects","Hovering a machine: state, each project, what it runs, and why only one project reaches the game.")]),
 ("Queue/Fleet", "Queue, Fleet", "queue-fleet", "Open this first. Every row should have a lit lamp and a job. Pause lets the job in hand finish; Stop now sends it back to the queue; Remove takes the machine out afterward. Sync now gathers results. Shut the fleet down asks twice.",
  [(600,80,"The whole queue in a sentence."),(500,103,"All jobs ever: green done, grey retired (not failures), red failed."),(1170,125,"Stop adding, stop now, sync, shut down."),(620,195,"The newest dial read, with its gain."),(172,245,"The lamp. Lit means working."),(340,245,"How busy its cores are; amber past 90%."),(1200,245,"This machine's buttons.")],
  [("hover-bar","Hovering the bar's grey part: what retired means, so it is not read as failure."),("hover-roster","Hovering a machine: cores, GPU, every job, and which projects it is on.")]),
 ("Queue/Runs", "Queue, Runs", "queue-runs", "Press a run's name on the left to ask for one by hand: it goes before the standing search. The list on the right is every run ever asked. Red means failed, and amber self-modified means carried on the line and not yet on main.",
  [(210,270,"A run by its kind."),(490,295,"What each kind does."),(650,238,"The rotation line. It names all kinds, while plan.json today gives the rotation only the transform: a label to correct."),(1040,478,"A promotion that tests stopped."),(1040,818,"A generation carried on the line."),(1350,818,"To main pushes the line by hand. The proof does this by itself.")], []),
 ("Pipeline/Board", "Queue, Board", "pipe-board", "The one screen for the question what should I do next. Read the red headline. A blocked or NOT BUILT task is a gap only a person can fill.",
  [(500,52,"Press the bar to open the screen's explanation."),(520,80,"The next essential: what most work waits on."),(520,98,"The generation, the bar it passes at, how long since the last, when it eases."),(300,190,"Each task with its machines and expected time."),(1000,190,"Its bar. Arrows are dependencies."),(300,640,"The Kanban: blocked, waiting, running, done.")],
  [("hover-board","Hovering a task: its state, note, every machine, its timing, what it waits on, what waits on it.")]),
 ("Pipeline/Flow", "Queue, Flow", "pipe-flow", "The data-flow picture. Click a box to pin its words below. Choose a trial above the table to follow its numbers. Rows one and two reach the game, and the red boxes are where work stops short.",
  [(240,115,"Where a trial comes from."),(700,115,"Each box: last day's jobs and hours, what is on and waiting."),(1230,115,"The commit every machine builds: the road loops back to the top."),(920,290,"NOT BUILT: where nothing passes."),(300,580,"The box chosen: what it takes, gives and simulates, and what it adds to treadcore."),(900,450,"Choose a trial."),(900,560,"Its reads, each with machine, time, seeds, gain and z."),(900,822,"How it ended.")],
  [("hover-flow","Hovering a box: all of its story, without clicking.")]),
 ("Pipeline/Timeline", "Queue, Timeline", "pipe-timeline", "Six hours measured on the left, the next stretch forecast on the right. Hollow bars have not happened. Look for gaps and for one colour taking everything.",
  [(280,75,"Measured: from the event log."),(1120,75,"Forecast: the queue dealt out at the last day's medians."),(200,190,"A machine."),(700,190,"Its work. Colour is the stage: the key is at the foot."),(1100,190,"Now."),(1160,240,"Hollow: not yet done."),(500,335,"A long grey bar is crucible. A blank row is an idle machine.")],
  [("hover-timeline","Hovering a bar: machine, stage, when, and where the data came from.")]),
 ("Pipeline/Queued", "Queue, Queued", "pipe-queued", "What runs and what waits, in the order it will go, each with why it is there. Nothing to press: it answers why is this in my queue.",
  [(600,78,"How many are running and waiting."),(205,130,"The stage, with its colour."),(500,130,"The job. Green is running now."),(600,145,"Why it is here, and how it fits the line."),(1250,130,"Who has it, or who it waits for.")],
  [("hover-queued","Hovering a row: everything, including whether it goes ahead of the queue.")]),
 ("Pipeline/Values", "Queue, Values", "pipe-values", "Press minus or plus to move a value one step. It is live at the next plan, about a minute, and no job restarts. Default puts it back. Amber means someone moved it.",
  [(260,125,"The value, and its range."),(430,118,"Its value now. Amber: moved."),(510,127,"Minus and plus."),(575,127,"Back to its default."),(950,125,"What it does.")],
  [("hover-values","Hovering a value: what happens if you raise or lower it, and where it is kept.")]),
 ("Results/Candidates", "Results, Candidates", "res-candidates", "Everything that passed its held-out read. Filter by promoted, current or older. Only current ones may promote themselves. Do it now pushes through by hand and asks twice.",
  [(1235,82,"Do it now: sync, promote, push."),(1310,150,"Auto mode on or off."),(600,210,"The promotions, newest first, with why each stopped."),(350,273,"Filter them."),(310,297,"Its time, its name, its held-out reads."),(500,297,"Its standing: current, older (with the commit it was read at), promoted."),(800,297,"What it moves.")],
  [("hover-candidate","Hovering a candidate: its reads, what it moves, and what its standing means.")]),
 ("Results/Found", "Results, Found", "res-found", "A running picture of what the search keeps finding. Read it for patterns and do not treat a line as proof: FOUND is a first read past two errors, and a few of those are luck.",
  [(330,166,"The dials found most often."),(660,166,"Each machine: found of all it read."),(1100,230,"The newest reads. Green: FOUND."),(1340,230,"Who read it.")],
  [("hover-found","Hovering a machine: what found means, and what a machine reading oddly would look like.")]),
 ("Results/Net", "Results, Net", "res-net", "The learned tank's net, bc2. Point at any cell to read its weight; click a matrix to enlarge it. Its training has been dormant since 30 October.",
  [(300,260,"Senses into the first layer. Dark columns are senses it ignores."),(600,340,"The middle layer."),(890,300,"The second layer into the 47 action scores."),(600,575,"How much it listens to each of the 143 senses."),(600,665,"How much reaches each of the 47 scores."),(760,765,"How often it makes the scripted brain's choice on unseen matches. Green bar: this net. Red tick: always guessing the commonest. Mortar, drone and lead barely beat that tick, so their high numbers mean little.")],
  [("hover-net","Hovering a cell: its weight, its row and column, and what its sign means.")]),
 ("Results/Flags", "Results, Flags", "res-flags", "What wants a person. Acknowledge each one, or all. Empty is the good state.",
  [(400,180,"The list, or the words that say it is empty.")], []),
 ("Results/Algorhythm/Patch", "Results, Algorhythm, Patch", "algo-patch", "The brain drawn as a synthesizer: read the top row left to right. Nothing here changes anything.",
  [(255,205,"Senses, then dials, then switches, then rules, then the transform, then the Move: the order the brain runs."),(320,325,"The choices: one whole number picks a function. bio is off in this picture's commit, and on square in the line's next."),(1140,335,"The biorhythm's three slow waves."),(520,480,"How far each dial has moved, in doublings."),(1020,480,"The largest moves, by name."),(770,700,"The transform's numbers: red and green. Today all of this reaches only the census.")],
  [("hover-switch","Hovering a dial: which function it has chosen, and every version.")]),
 ("Results/Algorhythm/Terrain", "Results, Algorhythm, Terrain", "algo-terrain", "It should draw reads as a landscape over two dials. <strong>Today it is empty, and that is a fault of the data and not of the screen:</strong> game 4's reads sit only in each job's results and not in any ledger it reads. See the amendment.",
  [(320,182,"What it says instead of inventing a surface.")], []),
 ("Results/Algorhythm/Spectrum", "Results, Algorhythm, Spectrum", "algo-spectrum", "How crucible's nets change over time, without reading a single weight. New bright rows are new skills; a flat picture means an island has stopped learning.",
  [(420,260,"A column a champion, strongest direction on top."),(1100,250,"The size of all its weights."),(1100,350,"How far it is from where it began."),(790,600,"The dials over the promotions, in doublings.")],
  [("hover-spectrum","Hovering a cell: its singular value, and what bright and flat mean.")]),
 ("Results/Algorhythm/Matrices", "Results, Algorhythm, Matrices", "algo-matrices", "Tables for how much of the net's size it really uses. Read the effective rank and the scree plot: they tell you how large a slot needs to be.",
  [(420,240,"Each layer: largest stretch, norm, stable and effective rank, share near zero."),(420,500,"Singular values by layer, on a log scale."),(1050,500,"What each group of senses could reach in each action.")],
  [("hover-matrices","Hovering a cell: the sense group, the action, and the limit of what the number says.")]),
 ("Results/Algorhythm/Senses", "Results, Algorhythm, Senses", "algo-senses", "What the net actually listens to, drawn around the tank, forward up. A dark ring is a channel nobody uses, and removing it would make the census and the transform cheaper.",
  [(560,500,"The compass: eight directions, eleven rings. Brighter is a stronger first-layer weight."),(560,265,"Ahead."),(1020,270,"The rings by name, with a bar each."),(1020,480,"The other senses, one bar a number.")],
  [("hover-senses","Hovering a dot: which channel, which direction, its sense number and weight.")]),
 ("Results/Algorhythm/Fleet", "Results, Algorhythm, Fleet", "algo-fleet", "The short version of Flow, and proposed for removal. It will go once nobody needs it.",
  [(280,200,"The three sources of trials."),(760,395,"The road to main, with live counts."),(450,605,"Numbers set by decree."),(450,660,"The rest of the machine, and what is out of the rotation.")],
  [("hover-road","Hovering a box: its words, and where the fuller picture is.")]),
 ("Lab", "Watch, Lab", "lab", "The room. Click a tile to select it, then use a verb. In this fleet there is no warden announcing, so every tile reads off the bus; the Fleet chapter is the live way to command these machines.",
  [(230,180,"A machine as a tile: name, status, and temperature when reported."),(80,130,"Scenes and tags, for selecting many."),(1240,20,"How many are declared, up, and on the bus."),(120,840,"What is selected.")],
  [("hover-lab","Hovering a tile: address, role, whether it has announced, what it runs, its tags.")]),
 ("Sessions", "Watch, Sessions", "sessions", "A terminal on every machine, each a tmux session that outlives Orrery. Click a tile to type into it; Enlarge fills the window. Recipes type their commands here for you to run.",
  [(370,75,"The machine, and its session."),(525,75,"Enlarge."),(360,200,"A real terminal: this is copal-tm, showing the machine's processes."),(1180,75,"A machine that cannot be reached says so here.")], []),
 ("Orchestrate", "Fleet, Orchestrate", "orchestrate", "Choose machines by question, then send a verb. Type a query such as <code>os=ubuntu idle</code> or press a chip; the verbs act on what is chosen. Each goes through a forced command signed by the certificate, not a shell. Renew when the time left runs short.",
  [(450,120,"The certificate: who you are and how long is left."),(845,120,"Renew it; Survey asks every machine what it is."),(530,177,"Select by question."),(1160,177,"Or by chip."),(450,300,"The machines, with system, load, build, certificate. The lamp means its listener is up."),(1200,430,"What each verb can reach today, and why not."),(490,737,"What to send."),(1080,737,"The verbs, greyed until something is chosen.")],
  [("hover-orchestrate","Hovering a machine: system, load, build, listener and certificate together.")]),
 ("Chat", "Fleet, Chat", "chat", "One room with every machine, each holding its own copy. A machine can answer with what it knows. It does not touch the training.",
  [(500,75,"Which machines are in the room."),(500,300,"The conversation."),(600,842,"Say something here.")], []),
 ("Settings/Keeper", "Settings, Keeper", "set-keeper", "The health page. Everything green means the keeper, its code, planning and lanes are as they should be. Amber is worth a look, and red is wrong now. Restart the keeper asks twice, because running jobs go back on the queue.",
  [(170,125,"A check's lamp."),(350,185,"The keeper, its heartbeat, its code, planning, sync."),(650,266,"Here: boburner's GPU has nothing it can start."),(650,357,"The line: generations carried, and the last proof against main."),(650,437,"The difficulty, as it is now."),(1238,132,"Plan now, Sync now, Restart the keeper.")],
  [("hover-keeper","Hovering a check: its state in words, its whole text, and its source.")]),
 ("Settings/Commits", "Settings, Commits", "set-commits", "The brain's history, one row a commit, with every default it changed in green. Click a row to open it on GitHub. A commit marked local line has not reached main.",
  [(290,147,"The date and commit."),(700,147,"What it says. A promotion names its evidence."),(390,163,"The defaults it moved."),(1260,147,"Whether the fleet built it, or it is carried locally.")], []),
]


def screens():
    out = [STYLE]
    for key, head, name, how, marks, hovers in SCREENS:
        a = LINE[key]
        out.append("<h3>%s</h3>\n<p>%s</p>\n" % (html.escape(head), how))
        out.append(shot(name, marks))
        out.append('<div class="answers">%s</div>\n' % "".join("<div><b>%s</b>%s</div>" % (q, html.escape(a[k])) for q, k in (("What it does", "does"), ("Where it ties in", "ties"), ("Why it is drawn this way", "drawn"), ("What to look for", "look"), ("What is simulated", "sim"), ("Why it helps the brain", "helps"))))
        for f, cap in hovers:
            out.append(shot(f, (), "<strong>Inspector.</strong> " + cap))
    open(os.path.join(DOCS, "double", "screens.html"), "w").write("".join(out))


GAME = [("game-menu", "<strong>The launch menu.</strong> A fresh shot of the game on this Mac. Every row stands for a command-line flag. The Bots row sets skill only, not style, which is the gap the next report closes."),
        ("game-frame", "<strong>In play.</strong> The tank in the middle is yours. The rings are ranges; the green shows the ground your team holds. Left: the order column. Right: the roster, your tanks, pillboxes and depots. Every bot here runs the weights the fleet carries."),
        ("game-fire", "<strong>Under fire.</strong> What the numbers exist for: <code>rate</code> chose these targets, and the ring shows direct range, 10 tiles."),
        ("game-sixteen", "<strong>Sixteen seats.</strong> What a census plays, three times a seed, thousands of times a day, with no person and no window."),
        ("game-over", "<strong>A match's end.</strong> The scores here are made of the same terms as the seat score in Section XIV.")]


def game():
    out = "".join(shot(n, (), c, (1200, 740)) for n, c in GAME)
    open(os.path.join(DOCS, "double", "game.html"), "w").write(out)


def bits():
    """The small figures the story sets in its text."""
    w = lambda name, text: open(os.path.join(DOCS, "double", name + ".html"), "w").write(text)
    w("game-sixteen-fig", shot("game-sixteen", (), "<strong>A match, as a census plays it,</strong> if there were a window. There is not.", (1200, 740)))
    w("game-fire-fig", shot("game-fire", (), "<strong>What a Command looks like from inside.</strong> A person's orders and a bot's are the same type.", (1280, 800)))
    w("anatomy", shot("queue-fleet", ((90, 20, "The chapters: the order of the work. The lit one is here."), (1240, 20, "What this chapter is saying now."), (75, 58, "This chapter's pages."), (70, 815, "The chapter's job, in a few words."), (500, 50, "About this screen: one line shut, six answers open. It shuts when you leave."), (1335, 50, "The inspector's switch."), (760, 500, "The screen itself.")), "<strong>The parts every screen shares.</strong>"))
    trace = open(os.path.join(DOCS, "whole-line", "fig-traces.html")).read().replace("Fig. 2. Trials through the line.", "The same figure as Part One's Fig. 2.")
    w("../whole-line/fig-traces-copy", trace)
    rows = [("drive", 66.6), ("gun", 62.7), ("mortar", 89.9), ("drone", 96.8), ("lead", 99.8)]
    w("net-agree", '<div class="table"><table><thead><tr><th>Head</th><th>Choices</th><th>Makes the rules\' choice, unseen matches</th></tr></thead><tbody>' + "".join("<tr><td>%s</td><td>%s</td><td>%.1f%%</td></tr>" % (n, c, p) for (n, p), c in zip(rows, (10, 9, 9, 5, 3))) + "</tbody></table></div>\n" + shot("res-net", ((760, 765, "Its bars, as on Results, Net."),), "", (1400, 860)))
    w("road-a", road("Fig. II-1. The first road, one number's life.", [("a match", "seat scores"), ("pool.sh", "d +/- se"), ("ledger.py", "a row"), ("suggest.py", "curves"), ("trial.weights", "bio = 3"), ("census", "z by stage"), ("held read", "z 0.95"), ("families, tests", "held"), ("set-defaults", "weights.rs"), ("build", "new baseline"), ("rate, pick", "a target"), ("FireDirect", "a shell")]))
    w("road-b", road("Fig. II-2. The second road: every net ends in the same Command.", [("143 senses", "0.5 ahead"), ("forward", "16,431 numbers"), ("47 scores", "seven heads"), ("choose", "top allowed"), ("Command", "Move, Fire"), ("World", "judges alike"), ("score", "the census"), ("a net's trainer", "BC, ES, SPSA")]))
    insp = [("hover-switcher", "The switch, on every screen."), ("hover-flow", "A stage's story on the road."), ("hover-values", "A value: what raising it does."), ("hover-net", "One weight of 16,431."), ("hover-senses", "One sense: channel and direction."), ("hover-spectrum", "One champion's direction."), ("hover-matrices", "A sense group and an action."), ("hover-terrain", "Even an empty screen answers."), ("about-flow", "The explanation panel, open."), ("about-senses", "Open on a tab."), ("about-fleet", "Open over the machines.")]
    w("inspector", '<div class="pair">' + "".join(shot(f, (), c) for f, c in insp) + "</div>\n")


def road(cap, steps):
    w, h, n = 1160, 320, len(steps)
    per = (n + 1) // 2
    bw, bh = 150, 62
    gx = (w - per * bw) // max(1, per - 1) if per > 1 else 0
    pos = []
    for i in range(n):
        row = i // per
        col = i % per if row == 0 else per - 1 - (i % per)
        pos.append((col * (bw + gx), 16 + row * 160))
    parts = ['<defs><marker id="ar" markerWidth="8" markerHeight="8" refX="7" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7 Z" fill="var(--accent)"/></marker></defs>']
    for i in range(n):
        a, b = pos[i], pos[(i + 1) % n]
        if a[1] == b[1]:
            x1, x2 = (a[0] + bw, b[0]) if b[0] > a[0] else (a[0], b[0] + bw)
            parts.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="var(--accent)" stroke-width="2" marker-end="url(#ar)"/>' % (x1, a[1] + bh // 2, x2, b[1] + bh // 2))
        else:
            y1, y2 = (a[1] + bh, b[1]) if b[1] > a[1] else (a[1], b[1] + bh)
            parts.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="var(--accent)" stroke-width="2" marker-end="url(#ar)"/>' % (a[0] + bw // 2, y1, b[0] + bw // 2, y2))
    for (x, y), (t1, t2) in zip(pos, steps):
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" rx="5" class="box"/><text x="%d" y="%d" class="b">%s</text><text x="%d" y="%d" class="d sm">%s</text>' % (x, y, bw, bh, x + 12, y + 25, html.escape(t1), x + 12, y + 45, html.escape(t2)))
    return '<figure><div class="viz"><svg viewBox="-2 0 %d %d" role="img" aria-label="%s">%s</svg></div><figcaption><strong>%s</strong> Read it clockwise; the last box feeds the first.</figcaption></figure>\n' % (w + 4, h, html.escape(cap, quote=True), "".join(parts), cap)


def main():
    screens()
    game()
    bits()
    one = open(os.path.join(DOCS, "whole-line-lab-report.md")).read()
    # Part One from its Abstract on, the abstract made a section of its own.
    body = one[one.index("## Abstract"):].replace("## Abstract\n", "## Part One: The Whole Line\n\n*How the fleet's work reaches treadcore. Published as its own report the same day; here whole.*\n", 1)
    two = open(os.path.join(DOCS, "double", "part-two.md")).read()
    head = open(os.path.join(DOCS, "double", "front.md")).read()
    open(os.path.join(DOCS, "double-lab-report.md"), "w").write(head + "\n" + body + "\n---\n\n" + two)
    print("double-lab-report.md written")


main()
