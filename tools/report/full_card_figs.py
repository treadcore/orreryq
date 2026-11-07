#!/usr/bin/env python3
"""full_card_figs.py OUTDIR -- the diagrams of *Every Generation on Film* (docs/full-card-lab-report.md).

Paul, 6 November: "show diagrams about architecture, about blocks and diagrams and different types of
computations represented by icons and symbols." Inline SVG in the report's own tokens (var(--ink), --tile,
--line, --dim, --accent, --up), so each reads in the light and the dark page alike. One icon a kind of
computation, the same everywhere:

    ray      a fan: rays cast from the tank (the senses)
    wave     nested squares: a breadth-first wave over the grid (the route)
    arcs     three curves: the tank's own motion projected (the dynamic window)
    branch   a diamond: a rule's choice (the script, the errand, the breach)
    matrix   a lattice: the net's multiply-adds (think)
    loop     a ring with an arrow: numbers read back next step (memory)
    gate     a switch: the net's say opened or shut
    film     a strip: frames encoded (FFmpeg)
"""
import os
import sys

FONT = 'font-family="var(--cond), system-ui, sans-serif"'


def svg(w, h, label, body):
    return ('<figure>\n<svg viewBox="0 0 %d %d" width="100%%" role="img" aria-label="%s" style="max-width:%dpx;display:block" %s>\n'
            '<defs><marker id="%s" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
            '<path d="M0 0 L10 5 L0 10 z" fill="var(--accent)"/></marker></defs>\n%s\n</svg>\n</figure>\n') % (w, h, label, w, FONT, MARK[0], body)


MARK = ["a"]


def arrow(x0, y0, x1, y1, label="", dx=0, dy=-6, dash=False):
    s = '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="var(--accent)" stroke-width="1.6"%s marker-end="url(#%s)"/>' % (
        x0, y0, x1, y1, ' stroke-dasharray="5 4"' if dash else "", MARK[0])
    if label:
        s += text((x0 + x1) / 2 + dx, (y0 + y1) / 2 + dy, label, 11.5, "var(--dim)", "middle")
    return s


def text(x, y, s, size=13, fill="var(--ink)", anchor="start", weight=None):
    return '<text x="%g" y="%g" font-size="%g" fill="%s" text-anchor="%s"%s>%s</text>' % (
        x, y, size, fill, anchor, ' font-weight="%s"' % weight if weight else "", s.replace("&", "&amp;").replace("<", "&lt;"))


def box(x, y, w, h, title, sub=(), fill="var(--tile)", stroke="var(--line)", accent=False):
    s = '<rect x="%g" y="%g" width="%g" height="%g" rx="6" fill="%s" stroke="%s" stroke-width="%s"/>' % (
        x, y, w, h, fill, "var(--accent)" if accent else stroke, 1.8 if accent else 1)
    s += text(x + w / 2, y + 20, title, 13.5, "var(--ink)", "middle", "700")
    for i, line in enumerate(sub):
        s += text(x + w / 2, y + 38 + 15 * i, line, 11.5, "var(--dim)", "middle")
    return s


# ---- the icons: each drawn in a 24-pixel square whose top left is (x, y) ------------------------------------
def i_ray(x, y):
    s = '<circle cx="%g" cy="%g" r="3" fill="var(--ink)"/>' % (x + 4, y + 12)
    for dy in (-10, -5, 0, 5, 10):
        s += '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="var(--ink)" stroke-width="1.2"/>' % (x + 6, y + 12, x + 24, y + 12 + dy)
    return s


def i_wave(x, y):
    return "".join('<rect x="%g" y="%g" width="%g" height="%g" fill="none" stroke="var(--ink)" stroke-width="1.2"/>' % (
        x + 12 - r, y + 12 - r, 2 * r, 2 * r) for r in (3, 7, 11)) + '<rect x="%g" y="%g" width="4" height="4" fill="var(--accent)"/>' % (x + 10, y + 10)


def i_arcs(x, y):
    s = '<circle cx="%g" cy="%g" r="2.5" fill="var(--ink)"/>' % (x + 3, y + 12)
    for c in (-9, 0, 9):
        s += '<path d="M%g %g Q%g %g %g %g" fill="none" stroke="var(--ink)" stroke-width="1.3"/>' % (x + 4, y + 12, x + 14, y + 12, x + 23, y + 12 + c)
    return s


def i_branch(x, y):
    return '<path d="M%g %g L%g %g L%g %g L%g %g z" fill="none" stroke="var(--ink)" stroke-width="1.4"/>' % (x + 12, y + 1, x + 23, y + 12, x + 12, y + 23, x + 1, y + 12)


def i_matrix(x, y):
    s = ""
    cols = [(x + 3, (5, 12, 19)), (x + 12, (3, 9, 15, 21)), (x + 21, (8, 16))]
    for (ax, ays), (bx, bys) in zip(cols, cols[1:]):
        for ay in ays:
            for by in bys:
                s += '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="var(--dim)" stroke-width="0.6"/>' % (ax, y + ay, bx, y + by)
    for cx, cys in cols:
        for cy in cys:
            s += '<circle cx="%g" cy="%g" r="1.9" fill="var(--ink)"/>' % (cx, y + cy)
    return s


def i_loop(x, y):
    return ('<path d="M%g %g A9 9 0 1 1 %g %g" fill="none" stroke="var(--ink)" stroke-width="1.4"/>' % (x + 12, y + 3, x + 4, y + 8)
            + '<path d="M%g %g l-1 6 l6 -2 z" fill="var(--ink)"/>' % (x + 2, y + 6))


def i_gate(x, y):
    return ('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="var(--ink)" stroke-width="1.4"/>' % (x + 1, y + 16, x + 8, y + 16)
            + '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="var(--ink)" stroke-width="1.4"/>' % (x + 8, y + 16, x + 17, y + 7)
            + '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="var(--ink)" stroke-width="1.4"/>' % (x + 17, y + 16, x + 23, y + 16)
            + '<circle cx="%g" cy="%g" r="1.8" fill="var(--ink)"/><circle cx="%g" cy="%g" r="1.8" fill="var(--ink)"/>' % (x + 8, y + 16, x + 17, y + 16))


def i_film(x, y):
    s = '<rect x="%g" y="%g" width="22" height="18" rx="2" fill="none" stroke="var(--ink)" stroke-width="1.3"/>' % (x + 1, y + 3)
    for k in range(4):
        s += '<rect x="%g" y="%g" width="3" height="2.5" fill="var(--ink)"/><rect x="%g" y="%g" width="3" height="2.5" fill="var(--ink)"/>' % (
            x + 3 + 5 * k, y + 5, x + 3 + 5 * k, y + 16.5)
    return s


ICONS = {"ray": i_ray, "wave": i_wave, "arcs": i_arcs, "branch": i_branch, "matrix": i_matrix, "loop": i_loop, "gate": i_gate, "film": i_film}


def legend():
    names = [("ray", "rays cast (the senses)"), ("wave", "a wave over the grid (the route)"), ("arcs", "its own motion, projected"),
             ("branch", "a rule's choice"), ("matrix", "the net's multiply-adds"), ("loop", "read back next step (memory)"),
             ("gate", "the net's say, open or shut"), ("film", "frames encoded")]
    body = ""
    for i, (k, s) in enumerate(names):
        x, y = 20 + (i % 4) * 235, 18 + (i // 4) * 40
        body += ICONS[k](x, y) + text(x + 34, y + 17, s, 12.5)
    return svg(960, 98, "The icons: one for each kind of computation in the figures that follow", body)


# ---- 1. the fleet's architecture ----------------------------------------------------------------------------
def architecture():
    b = ""
    b += '<rect x="10" y="10" width="300" height="430" rx="10" fill="none" stroke="var(--line)" stroke-dasharray="5 4"/>' + text(24, 32, "THIS MAC", 12, "var(--dim)", weight="700")
    b += box(30, 46, 260, 70, "orrery's keeper and planner", ("fleet-queue.py; treadcore.py each pass", "plan.json: crucible.nav, eps 256"))
    b += box(30, 136, 260, 62, "~/code/crucible (main bf0c99d)", ("shipped to an island with each segment",))
    b += box(30, 218, 260, 62, "treadcore main (game 9)", ("the line builds it: e499699 and on",))
    b += box(30, 300, 260, 60, "films: footage.py, montage.py", ("maze_film.py renders on this Mac",))
    b += box(30, 376, 260, 52, "Orrery (the app)", ("Results, Generations: the GPU's home",))
    b += '<rect x="360" y="10" width="290" height="430" rx="10" fill="none" stroke="var(--line)" stroke-dasharray="5 4"/>' + text(374, 32, "THREE GPU ISLANDS", 12, "var(--dim)", weight="700")
    b += box(380, 46, 250, 108, "a segment of the maze home", ("make WORLD HYBRID FOREST NAV", "100 generations, 2048 nets", "256 duels a net, tasks 1 in 4"), accent=True)
    b += ICONS["matrix"](392, 118) + ICONS["wave"](422, 118) + ICONS["arcs"](452, 118) + ICONS["ray"](482, 118)
    b += box(380, 176, 250, 70, "the CUDA gauntlet", ("24 files, 256 runs each, paired",))
    b += box(380, 266, 250, 70, "a milestone (a generation)", ("elected on the card: the weighed z",))
    b += box(380, 356, 250, 70, "footage traces", ("9 tests x 8 runs a generation",))
    b += '<rect x="700" y="10" width="250" height="430" rx="10" fill="none" stroke="var(--line)" stroke-dasharray="5 4"/>' + text(714, 32, "CPU MACHINES", 12, "var(--dim)", weight="700")
    b += box(720, 46, 210, 70, "the line's census", ("the rules' dials, game 9",))
    b += box(720, 186, 210, 92, "the bridge", ("a generation as the Gladiator", "192 seeds, every map", "credited when it holds"), accent=True)
    b += box(720, 330, 210, 70, "main", ("proved past by the line",))
    b += arrow(290, 80, 380, 92, "plans segments")
    b += arrow(290, 167, 380, 110, "source, each segment", dy=14)
    b += arrow(505, 154, 505, 176, "")
    b += arrow(505, 246, 505, 266, "elects")
    b += arrow(380, 300, 290, 328, "milestone back", dy=16)
    b += arrow(630, 300, 720, 236, "read in the game", dy=-8)
    b += arrow(290, 249, 720, 80, "", dash=True) + text(688, 128, "builds the line", 11.5, "var(--dim)", "end")
    b += arrow(380, 392, 290, 330, "traces back", dx=-8, dy=26)
    b += arrow(825, 116, 825, 186, "")
    b += arrow(825, 278, 825, 330, "proof")
    return svg(960, 450, "The fleet: the Mac plans and ships crucible's source; three GPU islands train the maze home, elect generations on the CUDA gauntlet and trace footage; CPU machines play the game's census and read each generation as the Gladiator", b)


# ---- 2. the card: blocks, shared memory, threads ------------------------------------------------------------
def card():
    b = ""
    for col, (title, eps, occ, note) in enumerate([("128 duels a net (before)", 128, "12%", "256 threads of 2,048 an SM can hold"),
                                                    ("256 duels a net (now)", 256, "25%", "512 threads, the same shared memory")]):
        x0 = 20 + col * 480
        b += text(x0 + 220, 24, title, 14, "var(--ink)", "middle", "700")
        b += '<rect x="%d" y="36" width="440" height="300" rx="10" fill="var(--panel)" stroke="var(--line)"/>' % x0
        b += text(x0 + 16, 58, "ONE SM (Pascal)", 11.5, "var(--dim)", weight="700")
        # shared memory bar: 96 KB, two blocks of 46 KB
        b += text(x0 + 16, 84, "shared memory 96 KB", 12, "var(--dim)")
        b += '<rect x="%d" y="92" width="408" height="30" fill="none" stroke="var(--line)"/>' % (x0 + 16)
        for k in range(2):
            b += '<rect x="%g" y="93" width="%g" height="28" fill="var(--tile)" stroke="var(--accent)"/>' % (x0 + 17 + k * 196, 194)
            b += ICONS["matrix"](x0 + 24 + k * 196, 95) + text(x0 + 56 + k * 196, 112, "block %d: its net's weights, 46 KB" % (k + 1), 11)
        b += text(x0 + 16, 140, "4 KB left: no third block fits", 11, "var(--dim)")
        # threads
        b += text(x0 + 16, 168, "threads (a dot = 16 duels)", 12, "var(--dim)")
        per = eps // 16
        for k in range(2):
            for j in range(per):
                cx = x0 + 22 + (j % 16) * 12 + k * 210
                cy = 184 + (j // 16) * 12
                b += '<circle cx="%d" cy="%d" r="4" fill="var(--accent)"/>' % (cx, cy)
        b += text(x0 + 16, 230, "registers: 128 a thread x %d = %s of 65,536" % (2 * eps, "32,768" if eps == 128 else "65,536"), 11.5, "var(--dim)")
        b += '<rect x="%d" y="246" width="408" height="16" fill="none" stroke="var(--line)"/>' % (x0 + 16)
        b += '<rect x="%d" y="247" width="%g" height="14" fill="var(--up)"/>' % (x0 + 17, 406 * (0.125 if eps == 128 else 0.25))
        b += text(x0 + 16, 284, "occupancy %s: %s" % (occ, note), 12.5, "var(--ink)", weight="700")
        b += text(x0 + 16, 306, "a second home on this card would need two more 46 KB blocks", 11, "var(--dim)") if col == 0 else text(x0 + 16, 306, "a generation: twice the duels in 1.57x the time", 11, "var(--dim)")
    return svg(960, 345, "The card's blocks: a Pascal SM's 96 KB of shared memory holds two blocks of 46 KB, each a net's weights; doubling the duels a net doubles the threads sharing those weights, 12% to 25% occupancy, where a second population would find no room", b)


# ---- 3. one tank-step, its parts and their measured shares ---------------------------------------------------
def step():
    b = ""
    parts = [("route", "wave", "the route sense", "line of sight? else the wave", 33), ("arcs", "arcs", "three arcs", "18 points, every 3rd step", 6),
             ("sense", "ray", "the senses", "12 rays, pillboxes, trees", 26), ("rules", "branch", "rules and errand", "script, then the route", 2),
             ("think", "matrix", "the net", "64 x 48 x 48 x 6", 34)]
    x = 20
    for i, (k, ic, title, sub, share) in enumerate(parts):
        b += '<rect x="%g" y="30" width="150" height="76" rx="6" fill="var(--tile)" stroke="var(--line)"/>' % x
        b += ICONS[ic](x + 10, 40) + text(x + 42, 57, title, 13, "var(--ink)", weight="700") + text(x + 12, 88, sub, 11, "var(--dim)")
        if i < len(parts) - 1:
            b += arrow(x + 150, 68, x + 178, 68)
        x += 178
    b += arrow(860, 68, 884, 68)
    b += ICONS["gate"](890, 44) + text(902, 84, "gate", 11.5, "var(--dim)", "middle")
    b += ICONS["loop"](890, 92) + text(902, 132, "2 kept", 11.5, "var(--dim)", "middle")
    # measured shares
    b += text(20, 140, "WHERE A DECISION'S TIME GOES (clock64, one lane a warp, ten generations each)", 11.5, "var(--dim)", weight="700")
    rows = [("maze build", [("route", 33), ("arcs", 6), ("sense", 26), ("rules", 2), ("think", 34)]),
            ("forest build", [("route", 0), ("arcs", 0), ("sense", 41), ("rules", 2), ("think", 57)])]
    colour = {"route": "var(--accent)", "arcs": "var(--accent)", "sense": "var(--up)", "rules": "var(--dim)", "think": "var(--ink)"}
    for r, (name, parts2) in enumerate(rows):
        y = 156 + r * 34
        b += text(20, y + 15, name, 12.5, "var(--ink)", weight="700")
        x = 120
        for k, v in parts2:
            if v <= 0:
                continue
            w = 7.8 * v
            b += '<rect x="%g" y="%d" width="%g" height="22" fill="%s" opacity="%s"/>' % (x, y, w - 2, colour[k], "0.55" if k in ("route", "arcs") else "0.8")
            if v >= 6:
                b += text(x + w / 2, y + 15, "%s %d%%" % (k, v), 11, "var(--base)", "middle", "700")
            x += w
    b += text(20, 236, "On a card of its own the maze build plays 22.5 million steps a second, the forest build 21.5; beside another process the maze build halves.", 11.5, "var(--dim)")
    return svg(960, 250, "One tank-step of the maze build: the route sense, the arcs, the senses, the rules and errand, the net, then its gate and the two kept numbers; and the measured share of a decision's time each takes, beside the forest build's", b)


# ---- 4. the inputs and outputs ------------------------------------------------------------------------------
def inputs():
    b = ""
    bands = [(0, 24, "12 rays: wall, enemy", "ray", 190), (24, 32, "tank, enemy", None, 90), (32, 35, "rules' answer", "branch", 96),
             (35, 47, "pillbox rays", "ray", 110), (47, 55, "pillbox, ammo", None, 104), (55, 59, "route: bearing,", "wave", 112),
             (59, 62, "three arcs", "arcs", 100), (62, 64, "two kept", "loop", 100)]
    x = 20
    for a, z, name, ic, w in bands:
        new = a >= 55
        b += '<rect x="%g" y="40" width="%g" height="34" fill="%s" stroke="%s"/>' % (x, w - 3, "var(--tile)", "var(--accent)" if new else "var(--line)")
        b += text(x + w / 2, 62, "%d-%d" % (a, z - 1), 11, "var(--dim)", "middle")
        if ic:
            b += ICONS[ic](x + w / 2 - 12, 80)
        b += text(x + w / 2, 122, name, 11, "var(--ink)" if not new else "var(--accent)", "middle")
        if a == 55:
            b += text(x + w / 2, 136, "length, walled", 11, "var(--accent)", "middle")
        x += w
    b += text(20, 28, "THE 64 INPUTS (crucible's NAV, treadcore's nav_senses): 0 to 54 the world's 55, 55 to 63 the maze's nine", 11.5, "var(--dim)", weight="700")
    b += arrow(470, 146, 470, 170, "")
    b += box(370, 172, 200, 56, "the net, 48 and 48", ("5,766 weights",))
    b += ICONS["matrix"](378, 178)
    outs = ["turn", "throttle", "fire", "gate", "kept 1", "kept 2"]
    for i, o in enumerate(outs):
        x = 270 + i * 70
        b += '<rect x="%d" y="250" width="64" height="30" fill="var(--tile)" stroke="%s"/>' % (x, "var(--accent)" if i >= 4 else "var(--line)")
        b += text(x + 32, 270, o, 11.5, "var(--ink)", "middle")
    b += arrow(470, 228, 470, 248, "")
    b += '<path d="M%d 282 C %d 320, 960 320, 892 76" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-dasharray="5 4" marker-end="url(#%s)"/>' % (620, 640, MARK[0])
    b += text(770, 318, "read back next decision", 11.5, "var(--dim)", "middle")
    return svg(960, 330, "The maze net's 64 inputs: twelve rays, the tank and enemy, the rules' answer, the world's pillboxes and ammunition, then nine new ones (the route, three arcs, two kept numbers); six outputs, the last two read back as inputs", b)


# ---- 5. the wall rule in both games -------------------------------------------------------------------------
def wall():
    b = ""
    # treadcore: tile grid
    b += text(20, 24, "TREADCORE (game 9): tiles", 12, "var(--dim)", weight="700")
    for hit, (lab, hp) in enumerate([("one hit", 45), ("two hits", 0)]):
        ox = 20 + hit * 220
        b += text(ox + 90, 46, lab, 12.5, "var(--ink)", "middle", "700")
        for r in range(7):
            ty = 56 + r * 24
            is_hit = r in (3, 4)
            fill = "var(--line)" if not is_hit else ("var(--tile)" if hp == 0 else "var(--line)")
            b += '<rect x="%d" y="%d" width="22" height="22" fill="%s" stroke="%s"/>' % (ox + 80, ty, fill, "var(--accent)" if is_hit else "var(--dim)")
            if is_hit:
                b += text(ox + 91, ty + 15, str(hp) if hp else "", 10.5, "var(--ink)", "middle", "700")
        b += '<circle cx="%d" cy="%d" r="8" fill="var(--accent)" opacity="0.8"/>' % (ox + 30, 56 + 4 * 24)
        b += arrow(ox + 40, 56 + 4 * 24, ox + 78, 56 + 4 * 24 - 2, "")
        if hp == 0:
            b += text(ox + 140, 56 + 4 * 24, "rubble: a gap", 11.5, "var(--ink)")
            b += text(ox + 140, 56 + 4 * 24 + 15, "two tiles wide", 11.5, "var(--dim)")
    b += text(20, 248, "45 of a tile's 90 to the tile struck and its neighbour along the wall", 11.5, "var(--dim)")
    # crucible: box
    b += text(500, 24, "CRUCIBLE (bf0c99d): boxes", 12, "var(--dim)", weight="700")
    b += text(590, 46, "a bar, two hits", 12.5, "var(--ink)", "middle", "700")
    b += '<rect x="580" y="56" width="22" height="64" fill="var(--line)" stroke="var(--dim)"/><rect x="580" y="128" width="22" height="96" fill="var(--line)" stroke="var(--dim)"/>'
    b += '<rect x="580" y="120" width="22" height="8" fill="none"/>'
    b += text(612, 120, "a gap of 3", 11.5, "var(--ink)")
    b += text(612, 136, "where it struck;", 11.5, "var(--dim)")
    b += text(612, 152, "both ends stand,", 11.5, "var(--dim)")
    b += text(612, 168, "whole again", 11.5, "var(--dim)")
    b += '<circle cx="530" cy="124" r="8" fill="var(--accent)" opacity="0.8"/>' + arrow(540, 124, 578, 124, "")
    # mortar
    b += text(760, 24, "THE MORTAR (both rules' choice)", 12, "var(--dim)", weight="700")
    b += '<path d="M770 210 Q840 40 900 150" fill="none" stroke="var(--accent)" stroke-dasharray="4 4" stroke-width="1.5"/>'
    b += '<circle cx="900" cy="150" r="30" fill="var(--accent)" opacity="0.15" stroke="var(--accent)"/>'
    b += text(900, 200, "splash fells a wall", 11.5, "var(--ink)", "middle")
    b += text(900, 215, "at once (treadcore)", 11.5, "var(--dim)", "middle")
    b += text(500, 248, "crucible's tank is 2 tiles wide, treadcore's 1.5: its gap is 3 where treadcore's is 2", 11.5, "var(--dim)")
    return svg(960, 262, "One wall rule in two games: in treadcore a direct hit takes 45 of 90 from the tile struck and its neighbour, so two hits open a two-tile gap; in crucible two hits open a three-tile gap in the bar where it struck; the mortar's splash still fells a wall at once", b)


# ---- 6. the breach decision ----------------------------------------------------------------------------------
def breach():
    b = ""
    steps = [("storming a base,", "no gun left"), ("first impassable", "on the line: a wall?"), ("way in shut, or", "> w_breach x the line?"), ("in the gun's reach", "and sight?")]
    x = 20
    for i, (l1, l2) in enumerate(steps):
        b += '<path d="M%g 70 L%g 34 L%g 70 L%g 106 z" fill="var(--tile)" stroke="var(--line)"/>' % (x, x + 85, x + 170, x + 85)
        b += text(x + 85, 66, l1, 11.5, "var(--ink)", "middle") + text(x + 85, 81, l2, 11.5, "var(--ink)", "middle")
        if i < len(steps) - 1:
            b += arrow(x + 170, 70, x + 196, 70, "yes", dy=-6)
            b += arrow(x + 85, 106, x + 85, 140, "no", dx=12, dy=4)
            b += text(x + 85, 154, ["rules as before", "no breach", "drive round"][i], 11.5, "var(--dim)", "middle")
        x += 196
    b += box(812, 26, 128, 40, "the gun", (), accent=True)
    b += box(812, 96, 128, 40, "the mortar", ())
    b += arrow(778, 70, 812, 46, "") + text(792, 48, "yes", 11.5, "var(--dim)", "end")
    b += arrow(778, 70, 812, 116, "") + text(800, 128, "no", 11.5, "var(--dim)", "end")
    b += text(876, 158, "beyond both: a firing position", 11.5, "var(--dim)", "middle")
    b += text(20, 186, "w_breach = 0 (the default): never by choice. The press temper moves the bar as it moves press_odds.", 11.5, "var(--dim)")
    return svg(960, 200, "The intrusion dial's decision: a storming tank with no gun left to shell, whose straight line meets a wall first and whose way in is shut or longer than w_breach times the line, shells that wall: with the gun in reach and sight, else the mortar", b)


# ---- 7. the camp: stages and how a stage pays --------------------------------------------------------------
def camp():
    b = ""
    stages = [("the beacon", "reach a spot", 1, 8), ("a castle rises", "take it", 2, 25), ("a second rises", "raze it", 1.5, 20)]
    x = 20
    for i, (t1, t2, rw, q) in enumerate(stages):
        b += box(x, 30, 150, 66, t1, (t2, "reward %g, quick %g s" % (rw, q)), accent=(i == 0))
        if i < 2:
            b += arrow(x + 150, 63, x + 210, 63, "spawns", dy=-8)
        x += 210
    b += text(20, 22, "K1, THE BEACON CAMP: each stage done spawns the next one's castle where the file says", 11.5, "var(--dim)", weight="700")
    # pay curve
    ox, oy, w, h = 680, 30, 250, 120
    b += '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="var(--dim)"/>' % (ox, oy + h, ox + w, oy + h)
    b += '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="var(--dim)"/>' % (ox, oy, ox, oy + h)
    b += '<polyline points="%d,%d %d,%d %d,%d" fill="none" stroke="var(--accent)" stroke-width="2"/>' % (ox, oy + 10, ox + 150, oy + 65, ox + w, oy + 65)
    b += text(ox - 6, oy + 14, "2x", 11, "var(--dim)", "end") + text(ox - 6, oy + 69, "1x", 11, "var(--dim)", "end")
    b += text(ox + 150, oy + h + 15, "quick", 11, "var(--dim)", "middle") + text(ox + w, oy + h + 30, "seconds in the stage", 11, "var(--dim)", "end")
    b += text(ox + 125, oy - 8, "a stage's pay: twice its reward done at once, its reward if slow", 11, "var(--dim)", "middle")
    b += text(20, 128, "Trained errand champion: K1 128 of 128, K2 128 of 128, K3 30 of 128. M0016: 0, 128, 10.", 12, "var(--ink)")
    return svg(960, 190, "The camp: stages in order, a beacon, then a castle that rises to be taken, then a second to raze; a stage pays twice its reward when done at once, falling to the reward itself at its quick time", b)


# ---- 8. the read-along machine ------------------------------------------------------------------------------
def teleprompt():
    b = ""
    b += box(20, 40, 170, 66, "the report page", ("page.html's timeline()",))
    b += box(250, 20, 210, 56, "headless Chrome", ("the timeline, at 1280 x 720",))
    b += box(250, 96, 210, 56, "headless Chrome", ("one photograph, the whole page",))
    b += box(520, 58, 210, 76, "FFmpeg", ("a crop slid by sendcmd,", "a whole pixel a frame,", "films laid over"), accent=True)
    b += ICONS["film"](528, 64)
    b += box(790, 30, 150, 52, "page.mp4", ("x264 or AV1",))
    b += box(790, 106, 150, 52, "the bundle", ("WebP tiles + player",))
    b += arrow(190, 64, 250, 48, "asks")
    b += arrow(190, 84, 250, 120, "")
    b += arrow(460, 48, 520, 84, "segments")
    b += arrow(460, 124, 520, 104, "tall image", dy=16)
    b += arrow(730, 84, 790, 58, "")
    b += arrow(730, 110, 790, 130, "")
    b += box(20, 150, 170, 40, "Read along button", ())
    b += arrow(105, 106, 105, 150, "the same timeline", dx=62, dy=4)
    return svg(960, 200, "The read-along machine: the page's own timeline, asked of headless Chrome, and one photograph of the page; FFmpeg slides a window down it a whole pixel at a time with the films laid over, into an MP4 or a bundle of WebP tiles with a player; the page's Read along button plays the same timeline", b)


# ---- 9. the footage pipeline --------------------------------------------------------------------------------
def footage():
    b = ""
    b += box(20, 40, 150, 66, "a new generation", ("the GPU home's own",))
    b += box(220, 40, 170, 66, "an island", ("9 tests x 8 runs", "--trace-scen"), accent=True)
    b += ICONS["matrix"](228, 46)
    b += box(440, 40, 150, 66, "this Mac", ("maze_film.py x 9",))
    b += ICONS["film"](448, 46)
    b += box(640, 40, 140, 66, "the sheet", ("3 x 3, 13 s",))
    b += box(820, 40, 120, 66, "the reel", ("every sheet",))
    b += arrow(170, 73, 220, 73, "planner")
    b += arrow(390, 73, 440, 73, "traces")
    b += arrow(590, 73, 640, 73, "films")
    b += arrow(780, 73, 820, 73, "")
    tests = ["N1", "N3", "M0", "M1", "M2", "M3", "B1", "T1", "T2"]
    for i, t in enumerate(tests):
        x, y = 650 + (i % 3) * 40, 124 + (i // 3) * 22
        b += '<rect x="%d" y="%d" width="36" height="18" fill="var(--tile)" stroke="var(--line)"/>' % (x, y) + text(x + 18, y + 13, t, 10.5, "var(--ink)", "middle")
    b += text(20, 140, "footage_watch, each planner pass: a generation with no footage is traced on an island and filmed here;", 11.5, "var(--dim)")
    b += text(20, 156, "the sheets join into output/treadcore-footage.mp4. Carried generations are not filmed.", 11.5, "var(--dim)")
    return svg(960, 200, "The footage of every generation: when the GPU's home makes one, an island traces nine tests eight runs each, this Mac films them, three by three on one sheet, and the sheets join into a reel", b)


def main(a):
    out = a[0] if a else "."
    os.makedirs(out, exist_ok=True)
    figs = {"legend": legend, "architecture": architecture, "card": card, "step": step, "inputs": inputs, "wall": wall,
            "breach": breach, "camp": camp, "teleprompt": teleprompt, "footage": footage}
    for k, f in figs.items():
        MARK[0] = "a-" + k
        open(os.path.join(out, "fig-%s.html" % k), "w").write(f())
    print("wrote %d figures to %s" % (len(figs), out))


if __name__ == "__main__":
    main(sys.argv[1:])
