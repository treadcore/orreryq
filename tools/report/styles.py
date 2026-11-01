#!/usr/bin/env python3
"""styles.py QUEUE: docs/bot-styles-lab-report.md, from docs/styles/body.md and the fleet's census of each style."""
import glob, html, json, math, os, re, sys

Q = os.path.abspath(sys.argv[1])
HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.normpath(os.path.join(HERE, "..", "..", "docs"))
OUT = os.path.join(DOCS, "styles")
ROSTER = [(0, "Fleet", "Rules", "the brain the fleet's search has carried: today's defaults"), (1, "Raider", "Rules", "goes and fights: leans to expanding, closes at even odds, picks off the wounded"), (2, "Castle", "Rules", "holds its ground: leans to fortifying and defending"), (3, "Expander", "Rules", "takes the map: depots and pillboxes first"), (4, "Timid", "Rules", "keeps away: fights only with the odds well on its side"), (5, "Overrider", "Transform", "the rules, with the learned transform moving their answer when it is sure"), (6, "Scholar", "Net", "a net that learned by imitating the rules: all senses, no rules"), (7, "Duelist", "Duel", "the rules, with a champion from crucible's GPU islands in every fight")]
STYLE = open(os.path.join(DOCS, "whole-line", "fig-flow.html")).read().split("</style>")[0] + "</style>\n"


def e(s):
    return html.escape(str(s), quote=True)


def t(x, y, s, cls="", a="start"):
    return '<text x="%d" y="%d" class="%s" text-anchor="%s">%s</text>' % (x, y, cls, a, e(s))


def fig(w, h, body, cap):
    return '<figure><div class="viz"><svg viewBox="0 0 %d %d" role="img" aria-label="%s">%s</svg></div><figcaption>%s</figcaption></figure>\n' % (w, h, e(re.sub("<[^>]+>", "", cap)), "".join(body), cap)


def decision():
    b = ['<defs><marker id="ah2" markerWidth="8" markerHeight="8" refX="7" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7 Z" fill="var(--accent)"/></marker></defs>']
    rows = [("Rules", "the Commander, with dials", "Fleet, Raider, Castle, Expander, Timid", None), ("Transform", "the rules, then a net moves the Move", "Overrider", "gate: y2 at least 0.5"), ("Net", "143 senses to 47 scores", "Scholar", None), ("Duel", "the rules, then a champion takes the fight", "Duelist", "gate: y3 above 0")]
    for i, (k, a, c, g) in enumerate(rows):
        y = 14 + i * 74
        b.append('<rect x="8" y="%d" width="400" height="60" rx="5" class="box"/>' % y)
        b.append(t(20, y + 22, k, "b"))
        b.append(t(100, y + 22, a))
        b.append(t(20, y + 44, c, "d sm"))
        if g:
            b.append(t(400, y + 44, g, "d sm", "end"))
        b.append('<path d="M408 %d H480 V158 H520" class="ar" marker-end="url(#ah2)"/>' % (y + 30))
    b.append('<rect x="520" y="118" width="170" height="80" rx="5" class="box"/>')
    b.append(t(605, 150, "Command", "b", "middle"))
    b.append(t(605, 172, "Move, FireDirect, Launch", "d sm", "middle"))
    b.append('<path d="M690 158 H740" class="ar" marker-end="url(#ah2)"/>')
    b.append('<rect x="740" y="118" width="230" height="80" rx="5" class="box"/>')
    b.append(t(855, 150, "The simulator", "b", "middle"))
    b.append(t(855, 172, "judges all of them alike", "d sm", "middle"))
    b.append(t(520, 240, "A style is one row. The menu chooses a row for each team.", "b"))
    b.append(t(520, 260, "A new kind of mind is one more row: anything that says Commands.", "d sm"))
    return STYLE + fig(980, 310, b, "<strong>Fig. 1. The final decision.</strong> Four kinds of mind today, one vocabulary, one judge. That is why they can share a map and be read by one census.")


def census(prefix="style"):
    """The fleet's reads of each style: the newest census run named style-K-NAME, from its results."""
    out = {}
    for f in sorted(glob.glob(os.path.join(Q, "runs", "*.json"))):
        r = json.load(open(f))
        m = re.match(prefix + r"-(\d)-", (r.get("params") or {}).get("name", ""))
        if r.get("kind") != "census" or not m:
            continue
        rid = os.path.basename(f)[:-5]
        for p in glob.glob(os.path.join(Q, "results", rid + "-00", "fleet", "q-grove", "out", rid + "-00", "*", "pooled.txt")) + glob.glob(os.path.join(Q, "results", rid + "-00", "**", "pooled.txt"), recursive=True):
            first = open(p).readline()
            g = re.match(r"every map\s+([-+][\d.]+) \+/- ([\d.]+) over\s+(\d+)", first)
            if g:
                maps = [(a, float(b)) for a, b in re.findall(r"^(\S+)\s+([-+][\d.]+) \+/-", open(p).read(), re.M) if a != "every"]
                out[int(m.group(1))] = (float(g.group(1)), float(g.group(2)), int(g.group(3)), maps, rid)
                break
    return out


def results(reads):
    if not reads:
        return "The fleet's reads are not back yet."
    w, L, rowh = 980, 130, 38
    lo = min(min(d - 2 * s for d, s, *_ in reads.values()), -1)
    hi = max(max(d + 2 * s for d, s, *_ in reads.values()), 1)
    x = lambda v: L + (v - lo) / (hi - lo) * (w - L - 90)
    b = []
    step = next(s for s in (0.5, 1, 2, 5, 10, 20, 50) if (hi - lo) / s <= 8)
    v = math.ceil(lo / step) * step
    while v <= hi:
        b.append('<line x1="%.1f" x2="%.1f" y1="10" y2="%d" class="%s"/>' % (x(v), x(v), 20 + rowh * len(reads), "now" if v == 0 else "ln"))
        b.append(t(int(x(v)), 34 + rowh * len(reads), "%+g" % v if v else "Fleet", "d sm", "middle"))
        v += step
    for i, k in enumerate(sorted(reads)):
        d, s, n, *_ = reads[k]
        y = 20 + i * rowh
        name = ROSTER[k]
        b.append(t(4, y + 18, "%d %s" % (k, name[1]), "b"))
        col = "var(--s-read)" if d - 2 * s > 0 else "var(--s-bad)" if d + 2 * s < 0 else "var(--s-gpu)"
        b.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="%s" stroke-width="2"/>' % (x(d - 2 * s), x(d + 2 * s), y + 14, y + 14, col))
        b.append('<circle cx="%.1f" cy="%d" r="6" fill="%s" stroke="var(--tile)" stroke-width="2"><title>%s: %+.2f +/- %.2f over %d seeds</title></circle>' % (x(d), y + 14, col, name[1], d, s, n))
        b.append(t(int(x(d + 2 * s)) + 8, y + 18, "%+.2f" % d, "sm"))
    table = "| Style | Kind | Points a seat against Fleet | z | Seeds | Worst map | Best map |\n| --- | --- | --- | --- | --- | --- | --- |\n"
    for k in sorted(reads):
        d, s, n, maps, rid = reads[k]
        worst = min(maps, key=lambda m: m[1]) if maps else ("-", 0)
        best = max(maps, key=lambda m: m[1]) if maps else ("-", 0)
        table += "| %d %s | %s | %+.2f +/- %.2f | %+.1f | %d | %s %+.1f | %s %+.1f |\n" % (k, ROSTER[k][1], ROSTER[k][2], d, s, d / s if s else 0, n, worst[0], worst[1], best[0], best[1])
    open(os.path.join(OUT, "census.html"), "w").write(fig(w, 50 + rowh * len(reads), b, "<strong>Fig. 3. Each style against the fleet's brain.</strong> A whole team of the style, against whole teams of Fleet, by the same census as any dial: points a seat, with two errors either side. Green is past two errors above; red, below."))
    checks = census("check")
    if checks:
        table += "\nThe three that read above Fleet were then read again, on seeds of their own:\n\n| Style | Points a seat against Fleet | z | Seeds |\n| --- | --- | --- | --- |\n"
        for k in sorted(checks):
            d, se, n, *_ = checks[k]
            table += "| %d %s | %+.2f +/- %.2f | %+.1f | %d |\n" % (k, ROSTER[k][1], d, se, d / se, n)
    return "!html(styles/census.html)\n\n" + table


def main():
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "decision.html"), "w").write(decision())
    rows = "".join("<tr><td>%d</td><td><strong>%s</strong></td><td>%s</td><td>%s</td></tr>" % (a, b, c, e(d)) for a, b, c, d in ROSTER)
    open(os.path.join(OUT, "roster.html"), "w").write('<div class="table"><table><thead><tr><th>Slot</th><th>Name</th><th>Kind</th><th>What it is</th></tr></thead><tbody>%s</tbody></table></div>\n' % rows)
    open(os.path.join(OUT, "menu.html"), "w").write('<figure style="max-width:760px"><img loading="lazy" src="styles/menu.png" alt="The launch menu with team rows" style="width:100%;border:1px solid var(--line);border-radius:6px"><figcaption><strong>Fig. 2. The launch menu, today.</strong> A fresh shot from the game on this Mac. Your team and teams 2 to 4 each choose a style; Skill is what the old Bots row always set.</figcaption></figure>\n')
    open(os.path.join(OUT, "board.html"), "w").write('<figure><img loading="lazy" src="styles/board.png" alt="The Board" style="width:100%;border:1px solid var(--line);border-radius:6px"><figcaption><strong>Fig. 4. The Board after this work,</strong> from the live run.</figcaption></figure>\n')
    reads = census()
    res = results(reads)
    # Words a person writes over the numbers, once read.
    note = os.path.join(OUT, "reading.md")
    if os.path.exists(note):
        res += "\n" + open(note).read()
    line = os.path.join(OUT, "abstract-result.txt")
    s = open(os.path.join(OUT, "body.md")).read().replace("RESULTS", res).replace("RESULT_LINE", open(line).read().strip() if os.path.exists(line) else "")
    open(os.path.join(DOCS, "bot-styles-lab-report.md"), "w").write(s)
    print("reads", {k: v[:3] for k, v in reads.items()})


main()
