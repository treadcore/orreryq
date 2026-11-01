#!/usr/bin/env python3
"""fortify_figs.py: the figures of docs/fortify-lab-report.md, from the reads as they were, and its Markdown."""
import html, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.normpath(os.path.join(HERE, "..", "..", "docs"))
OUT = os.path.join(DOCS, "fortify")
STYLE = open(os.path.join(DOCS, "whole-line", "fig-flow.html")).read().split("</style>")[0] + "</style>\n"
e = lambda s: html.escape(str(s), quote=True)
t = lambda x, y, s, c="", a="start": '<text x="%d" y="%d" class="%s" text-anchor="%s">%s</text>' % (x, y, c, a, e(s))
def fig(w, h, b, cap, name, css=False):
    open(os.path.join(OUT, name + ".html"), "w").write((STYLE if css else "") + '<figure><div class="viz"><svg viewBox="0 0 %d %d" role="img" aria-label="%s">%s</svg></div><figcaption>%s</figcaption></figure>\n' % (w, h, e(re.sub("<[^>]+>", "", cap)), "".join(b), cap))
# Fig 1: the dose, two panels, one axis each.
def dose():
    b = []
    rows = [("6.0, as it was", 0, 0, 0, 0), ("1.5, now", 1.34, .37, .36, .31), ("0.4, held", 3.58, .52, -.30, .41)]
    def panel(x0, title, i, col):
        w = 410; lo, hi = -1.5, 5.0
        px = lambda v: x0 + (v - lo) / (hi - lo) * w
        o = [t(x0, 16, title, "b")]
        for v in (-1, 0, 1, 2, 3, 4, 5):
            o.append('<line x1="%.1f" x2="%.1f" y1="26" y2="150" class="%s"/>' % (px(v), px(v), "now" if v == 0 else "ln"))
            o.append(t(int(px(v)), 168, "%+d" % v if v else "0", "d sm", "middle"))
        for k, r in enumerate(rows):
            y = 52 + k * 40
            d, s = r[i], r[i + 1]
            o.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="%s" stroke-width="2"/>' % (px(d - 2 * s), px(d + 2 * s), y, y, col))
            o.append('<circle cx="%.1f" cy="%d" r="6" fill="%s" stroke="var(--tile)" stroke-width="2"><title>%s: %+.2f +/- %.2f</title></circle>' % (px(d), y, col, e(r[0]), d, s))
            o.append(t(int(px(d + 2 * s)) + 8, y + 4, "%+.2f" % d if s else "", "sm"))
        return o
    for k, r in enumerate(rows):
        b.append(t(4, 56 + k * 40, r[0], "b"))
    b += panel(130, "The score", 1, "var(--s-first)")
    b += panel(560, "The score without going forward", 3, "var(--s-held)")
    fig(990, 180, b, "<strong>Fig. 1. What the dial buys, and what remains.</strong> Points a seat against 6.0, on all maps, with two errors either side. The gain grows as the dial falls. Without the rewards for going forward, there is none to speak of.", "dose", True)
# Fig 2: the waterfall
def waterfall():
    items = [("Tiles advanced", 57.79 * .25 / 5), ("Advance stages", 1.10 * 3 / 5), ("Pillboxes taken, damage, hits, ground", None), ("Kills less deaths", -.20), ("Works and road", -7.97 * .1 / 5 - 2.44 * .05 / 5)]
    total, known = 3.42, 57.79 * .25 / 5 + 1.10 * 3 / 5 - .20 + (-7.97 * .1 / 5 - 2.44 * .05 / 5)
    items[2] = (items[2][0], total - known)
    W, L, R = 980, 290, 80
    lo, hi = -.6, 4.0
    px = lambda v: L + (v - lo) / (hi - lo) * (W - L - R)
    b = ['<line x1="%.1f" x2="%.1f" y1="8" y2="%d" class="now"/>' % (px(0), px(0), 16 + 30 * (len(items) + 1))]
    run = 0.0
    for i, (n, v) in enumerate(items):
        y = 12 + i * 30
        a, c = run, run + v
        b.append(t(4, y + 15, n))
        b.append('<rect x="%.1f" y="%d" width="%.1f" height="18" rx="2" fill="%s"><title>%s: %+.2f a seat</title></rect>' % (px(min(a, c)), y + 2, max(2, abs(px(c) - px(a))), "var(--s-read)" if v > 0 else "var(--s-bad)", e(n), v))
        b.append(t(int(px(max(a, c))) + 6, y + 15, "%+.2f" % v, "sm"))
        run = c
    y = 12 + len(items) * 30
    b.append(t(4, y + 15, "The score", "b"))
    b.append('<rect x="%.1f" y="%d" width="%.1f" height="18" rx="2" fill="var(--s-first)"/>' % (px(0), y + 2, px(total) - px(0)))
    b.append(t(int(px(total)) + 6, y + 15, "%+.2f" % total, "b sm"))
    fig(W, y + 30, b, "<strong>Fig. 2. Where 0.4's +3.42 came from,</strong> each measured change at what the score pays for it, per seat (<code>r0097</code>, 220 seeds). The third row is what is left of the rewards and the score after the others, since hits, damage, pillboxes and ground are paid at several rates.", "waterfall")
# Fig 3: per map
def maps():
    tot = dict(zip("industry island naval big-lizard constanine fidos-airstrip fortressisles2 fortressislesx atlantic europe generated".split(), (5.55, 2.90, .86, 4.29, 6.57, -1.15, 2.52, 1.85, 1.19, 14.25, 1.46)))
    wo = {"atlantic": 1.1, "big-lizard": -.9, "constanine": -.3, "europe": 4.6, "fidos-airstrip": -2.3, "fortressisles2": -.8, "fortressislesx": -1.6, "generated": -.7, "industry": -1.8, "island": -1.0, "naval": .4}
    rows = sorted(tot, key=lambda k: -tot[k])
    W, L, R = 980, 140, 60
    lo, hi = -4, 16
    px = lambda v: L + (v - lo) / (hi - lo) * (W - L - R)
    b = []
    for v in range(-4, 17, 4):
        b.append('<line x1="%.1f" x2="%.1f" y1="8" y2="%d" class="%s"/>' % (px(v), px(v), 12 + 26 * len(rows), "now" if v == 0 else "ln"))
        b.append(t(int(px(v)), 28 + 26 * len(rows), "%+d" % v if v else "0", "d sm", "middle"))
    for i, m in enumerate(rows):
        y = 10 + i * 26
        b.append(t(4, y + 14, m))
        for v, col, off in ((tot[m], "var(--s-first)", 1), (wo[m], "var(--s-held)", 12)):
            b.append('<rect x="%.1f" y="%d" width="%.1f" height="9" rx="1" fill="%s"><title>%s: %+.1f</title></rect>' % (px(min(0, v)), y + off, abs(px(v) - px(0)), col, e(m), v))
    y = 46 + 26 * len(rows)
    b.append('<rect x="4" y="%d" width="10" height="10" fill="var(--s-first)"/>' % (y - 9))
    b.append(t(18, y, "The score, 400 seeds (r0090)", "d sm"))
    b.append('<rect x="230" y="%d" width="10" height="10" fill="var(--s-held)"/>' % (y - 9))
    b.append(t(244, y, "Without going forward, 220 seeds (r0097)", "d sm"))
    fig(W, y + 8, b, "<strong>Fig. 3. 0.4 against 6.0, by map.</strong> Points a seat. Each map has about 36 seeds in the first and 20 in the second, so single bars are rough. Most of the blue goes when the going-forward rewards are taken out, except on <code>europe</code>.", "maps")
dose(); waterfall(); maps()
r = open(os.path.join(OUT, "rules.md")).read()
b = open(os.path.join(OUT, "body.md")).read().replace("!html(fortify/rules.html)", r)
open(os.path.join(DOCS, "fortify-lab-report.md"), "w").write(b)
print("ok")
