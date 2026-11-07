#!/usr/bin/env python3
"""The guide's two diagrams, as self-contained SVG files in the site's screen colours: the loop
(guide-loop.svg) and the two roads into the game (guide-roads.svg). Hard colours rather than
currentColor, because GitHub shows the README's pictures as images, where nothing is inherited.

    python3 tools/report/guide_figs.py docs/site/guide

The numbers in the boxes are the Generations page's, Roads tab, as it read on 6 November.
"""
import sys, html

OUT = sys.argv[1]
BG, EDGE, TILE, LINE = "#0a0c0a", "#2b2c2e", "#111511", "#2f3a31"
INK, SOFT, DIM = "#e6ede6", "#9fb0a2", "#6f7f72"
PHOS, AMBER, SKY, TAN, RED = "#33f24d", "#ffbf4d", "#73c7ff", "#bfa070", "#f23326"
SANS = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', monospace"


def esc(s):
    return html.escape(s, quote=True)


class Svg:
    def __init__(self, w, h, label):
        self.w, self.h, self.parts = w, h, []
        self.label = label

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, size=12, fill=INK, weight=400, anchor="start", font=SANS, spacing=None):
        ls = f' letter-spacing="{spacing}"' if spacing else ""
        self.add(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{fill}" '
                 f'font-weight="{weight}" text-anchor="{anchor}"{ls}>{esc(s)}</text>')

    def group(self, x, y, w, h, title, colour=SOFT):
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="none" stroke="{LINE}" stroke-dasharray="5 4"/>')
        self.text(x + 14, y + 22, title, 11, colour, 700, spacing="1.2")

    def box(self, x, y, w, h, title, lines, accent=LINE, tcol=INK, mono_first=False, num=None):
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="{TILE}" stroke="{accent}" stroke-width="1.4"/>')
        tx = x + 12
        if num is not None:
            self.add(f'<circle cx="{x + 20}" cy="{y + 19}" r="10" fill="{accent}"/>')
            self.text(x + 20, y + 23.5, str(num), 12, BG, 800, "middle")
            tx = x + 38
        self.text(tx, y + 24, title, 14, tcol, 700)
        for i, ln in enumerate(lines):
            mono = mono_first and i == 0
            self.text(x + 12, y + 44 + i * 16, ln, 11.5 if mono else 12, SOFT, 400, font=MONO if mono else SANS)

    def chip(self, x, y, w, s, dot=None):
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="20" rx="4" fill="#0d110d" stroke="{LINE}"/>')
        tx = x + 8
        if dot:
            self.add(f'<circle cx="{x + 9}" cy="{y + 10}" r="3.5" fill="{dot}"/>')
            tx = x + 17
        self.text(tx, y + 14, s, 11, INK, 400, font=MONO)

    def arrow(self, pts, colour, label=None, at=None, anchor="middle", dash=False, lcol=None):
        mid = f"m{len(self.parts)}"
        self.add(f'<defs><marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                 f'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{colour}"/></marker></defs>')
        d = " ".join(f"{x},{y}" for x, y in pts)
        da = ' stroke-dasharray="6 4"' if dash else ""
        self.add(f'<polyline points="{d}" fill="none" stroke="{colour}" stroke-width="2"{da} marker-end="url(#{mid})"/>')
        if label:
            lx, ly = at
            for i, ln in enumerate(label.split("\n")):
                self.text(lx, ly + i * 14, ln, 11.5, lcol or colour, 600, anchor)

    def write(self, path):
        body = "\n".join(self.parts)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
               f'role="img" aria-label="{esc(self.label)}">\n<title>{esc(self.label)}</title>\n'
               f'<rect x="0.5" y="0.5" width="{self.w - 1}" height="{self.h - 1}" rx="14" fill="{BG}" stroke="{EDGE}"/>\n'
               f'{body}\n</svg>\n')
        open(path, "w").write(svg)


# ---- 1. The loop: one queue, a planner, a keeper, the lanes, and the game ----
s = Svg(960, 600, "The Orrery Queue: the planner writes jobs into one queue on the Mac; the keeper hands each free lane "
        "its next job over ssh; nine CPU lanes play the game's census and three GPU lanes evolve crucible's nets; every "
        "job comes back as a file the planner reads; what holds goes onto the line and then treadcore's main, and an "
        "elected net ships to nets/. The console draws all of it.")
# the console, a band over everything
s.add(f'<rect x="20" y="20" width="920" height="54" rx="8" fill="#0f140f" stroke="{PHOS}" stroke-width="1.4"/>')
s.text(36, 44, "orrery, the console", 15, PHOS, 700)
s.text(36, 62, "one window that draws the queue, the fleet and every result; its buttons write requests into the queue, and a person can hold any dial", 12, SOFT)

s.group(20, 92, 506, 300, "THIS MAC")
s.box(36, 126, 214, 100, "the planner", ["tools/plans/treadcore.py", "a pass every few minutes:", "what to try, read on, promote"], AMBER, mono_first=True)
s.box(296, 126, 214, 100, "the queue: grove", ["plan.json  results/", "and events.jsonl, a folder:", "a job a file, a result a file"], PHOS, mono_first=True)
s.box(36, 278, 214, 100, "the line", ["orrery/accepted", "every trial that held,", "committed, built everywhere"], AMBER, mono_first=True)
s.box(296, 278, 214, 100, "the keeper", ["tools/fleet-queue.py", "a free lane gets the next job", "and the code it needs"], PHOS, mono_first=True)

s.group(552, 92, 388, 300, "THE FLEET  ·  9 MACHINES, 12 LANES")
s.box(568, 126, 356, 132, "9 CPU lanes: the census", ["treadcore itself, headless, many games a job;", "a trial is the brain with a few dials moved"], AMBER)
cpu = ["saskatchewan", "jaguaribe", "bosporus", "columbia", "macmini", "this Mac", "boburner", "calber", "whitewolf"]
for i, m in enumerate(cpu):
    s.chip(580 + (i % 3) * 112, 194 + (i // 3) * 24 - 4, 106, m, SKY if m in ("boburner", "calber", "whitewolf") else None)
s.box(568, 278, 356, 100, "3 GPU lanes: crucible's islands", ["a population of nets on each CUDA card,", "evolved a segment at a time, then elected"], SKY)
s.text(912, 372, "● a card in the machine", 10.5, SKY, 400, "end")

s.group(20, 470, 920, 110, "TREADCORE, THE GAME  ·  github.com/treadcore/treadcore")
s.box(36, 504, 440, 62, "main: the brain's defaults", ["the dials every bot in the game plays with"], TAN)
s.box(568, 504, 356, 62, "nets/: the learned nets", ["gladiator.bin and the milestones"], TAN)

# the arrows
s.arrow([(250, 158), (294, 158)], PHOS, "writes", (272, 151))
s.arrow([(296, 196), (252, 196)], AMBER, "reads", (274, 214))
s.arrow([(403, 226), (403, 276)], PHOS, "next job", (412, 256), "start")
s.arrow([(510, 328), (566, 328)], PHOS, "ssh: run", (538, 320))
s.arrow([(566, 160), (512, 160)], AMBER, "a file\nback", (539, 140))
s.arrow([(143, 226), (143, 276)], AMBER, "promotes what held", (152, 256), "start")
s.arrow([(143, 378), (143, 502)], TAN, "when the line reads past", (152, 430), "start", lcol=SOFT)
s.text(152, 444, "main: 800 seeds an hour, z ≥ 3", 11.5, SOFT, 400)
s.arrow([(746, 378), (746, 502)], SKY, "elected, read by the census", (756, 430), "start", lcol=SOFT)
s.text(756, 444, "as the Gladiator, then shipped", 11.5, SOFT, 400)
s.write(f"{OUT}/guide-loop.svg")


# ---- 2. Two roads into the game ----
s = Svg(960, 640, "Two roads into the game. On CPUs the census reads a trial of the brain's dials on 55 seeds, reads on, "
        "holds it out on 400 new seeds, puts it through 9 families, 22 gauntlets and 168 tests, and onto the line and main. "
        "On CUDA a population evolves a segment of 100 generations, is weighed on crucible's gauntlet against the bar, is "
        "elected a milestone, filmed on 12 tests, read by the census as the Gladiator and shipped as a net file.")
s.text(36, 44, "THE CENSUS, ON CPUs", 12, AMBER, 700, spacing="1.2")
s.text(36, 62, "the hand-written brain's dials", 12, SOFT)
s.text(524, 44, "THE ISLANDS, ON CUDA", 12, SKY, 700, spacing="1.2")
s.text(524, 62, "the learned net, crucible's", 12, SOFT)

left = [
    ("Trial", ["a few dials moved, drawn from the fit", "of every census so far (suggest.py)"]),
    ("First read", ["55 seeds against today's defaults;", "the hopeless are dropped for the price"]),
    ("Read on, then held out", ["more seeds until it is decided (about 190);", "then 400 seeds no search has seen"]),
    ("Families, gauntlet, tests", ["9 families, 22 gauntlets, 168 tests,", "each at its floor"]),
    ("The line", ["committed on orrery/accepted,", "built on every machine"]),
    ("Main", ["main's values against the line,", "800 seeds an hour, until z ≥ 3"]),
]
right = [
    ("A segment", ["100 generations of a population on one card:", "trees, walls, takeovers, mazes and camps"]),
    ("The CUDA gauntlet", ["24 files, weighed by how hard each is:", "a z against the bar, and every floor held"]),
    ("Elected: a milestone", ["every floor held, no worse on the yardstick,", "over the bar, or ahead of the champion head to head"]),
    ("Filmed", ["12 tests, 8 runs each, a sheet and a reel;", "a card with what made the net"]),
    ("Bridge read", ["the census plays it as style 17, the Gladiator:", "two censuses of 48 seeds, every map"]),
    ("nets/gladiator.bin", ["on main beside the milestones;", "it ships itself"]),
]
H, G, Y0 = 72, 18, 80
for i, (t, ln) in enumerate(left):
    y = Y0 + i * (H + G)
    s.box(36, y, 400, H, t, ln, AMBER if i < 5 else PHOS, num=i + 1)
    if i:
        s.arrow([(236, y - G), (236, y - 2)], AMBER if i < 5 else PHOS)
for i, (t, ln) in enumerate(right):
    y = Y0 + i * (H + G)
    s.box(524, y, 400, H, t, ln, SKY if i < 5 else PHOS, num=i + 1)
    if i:
        s.arrow([(724, y - G), (724, y - 2)], SKY if i < 5 else PHOS)
# the bridge: the CPUs' census plays the GPU's elected net
yb = Y0 + 4 * (H + G) + 36
s.arrow([(452, yb), (520, yb)], SKY, "the CPUs", (482, yb - 9), dash=True)
s.text(482, yb + 19, "play it", 11.5, SKY, 600, "middle")
for k, w in enumerate(["no GPU number", "reaches", "the dials"]):
    s.text(480, 30 + Y0 + 1 * (H + G) + k * 14, w, 11, DIM, 400, "middle")
s.write(f"{OUT}/guide-roads.svg")
print("wrote", OUT)
