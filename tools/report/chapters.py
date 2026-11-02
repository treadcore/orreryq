#!/usr/bin/env python3
"""chapters.py BOOK OUT [BRAND [EYEBROW [FOOT]]] -- a book of chapters as linked pages.

BOOK is a directory of Markdown: `00-front.md` (the book's title on its first line, then the front
matter: the abstract, how to read it, anything before the chapters; a line `!chapters` marks where
the chapter list goes, else it follows the front matter) and `NN-slug.md` chapters, each beginning
`# Title`, with ## for its sections. OUT gets index.html and one NN-slug.html a chapter, so a chapter
links another as `[the wingman](07-the-wingman.html)` and a section of it as
`07-the-wingman.html#its-slug` (md.slug of the heading). Images and `!html` figures are read relative
to BOOK and embedded, as build.py embeds them.

BRAND is the sticky bar's first word (default "treadcore · lab reports"), EYEBROW the small line over
the book's title on the index (a chapter's eyebrow is "chapter N of M"), FOOT the footer's sentence.
THE LOOK IS page.html's, AS EVERY LAB REPORT: one Markdown form, one page form, and now one book form,
so a reader who knows the reports knows the book. The index lists every chapter with its first
paragraph; a chapter page carries the bar (the book, contents, its section numerals, previous, next),
its own contents, and previous and next again at the foot. A book of one chapter is still a book.
"""
import glob
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md import Doc, inline  # noqa: E402

BOOK, OUT = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/")
BRAND = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else "treadcore · lab reports"
EYEBROW = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else "treadcore · a lab report in chapters"
FOOT = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] else "Paul Richeson, November 2026. MIT licensed, as treadcore. The Markdown original is beside this page, one file a chapter."

HERE = os.path.dirname(os.path.abspath(__file__))
# page.html up to its bar: the styles, which every page of the book shares with every report.
HEAD = open(os.path.join(HERE, "page.html")).read().split('<div class="bar">', 1)[0]
MORE = """<style>
/* The book's own two pieces: the chapter list on the index, and previous/next at a chapter's foot. */
ol.chapters { list-style: none; padding: 0; margin: 0 0 1.4em; }
ol.chapters li { padding: 14px 0; border-bottom: 1px solid var(--rule); max-width: var(--measure); margin: 0; }
ol.chapters li:last-child { border-bottom: none; }
ol.chapters .n { font-family: var(--mono); font-size: var(--step--1); letter-spacing: .1em; color: var(--accent); margin-right: 12px; }
ol.chapters a.t { font-family: var(--cond); font-weight: 700; font-size: var(--step-1); text-decoration: none; }
ol.chapters a.t:hover, ol.chapters a.t:focus-visible { text-decoration: underline; text-decoration-color: var(--accent); }
ol.chapters p { margin: 6px 0 0; font-size: var(--step--1); color: var(--dim); }
nav.pn { display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; font-family: var(--cond); padding-block: 18px; border-top: 1px solid var(--rule); }
nav.pn a { color: var(--ink); text-decoration: none; }
nav.pn a:hover, nav.pn a:focus-visible { text-decoration: underline; text-decoration-color: var(--accent); }
</style>
"""


def read(path):
    """(title, the lines before the first ## heading, the lines from it on)."""
    lines = open(path).read().split("\n")
    title = lines[0].lstrip("# ").strip()
    body = lines[1:]
    cut = next((i for i, l in enumerate(body) if l.startswith("## ")), len(body))
    return title, body[:cut], body[cut:]


def first_paragraph(lines):
    """The first run of plain text lines, as inline HTML: a chapter's blurb on the index."""
    p = []
    for l in lines:
        s = l.strip()
        if not s:
            if p:
                break
            continue
        if not p and re.match(r"^(#|!|\||>|```|[-*]\s|\d+\.\s)", s):
            continue
        if p and re.match(r"^(#|!|\||>|```)", s):
            break
        p.append(s)
    return inline(" ".join(p))


def numerals(toc):
    return "".join('<a href="#%s">%s</a>' % (sid, html.escape(re.sub(r"^([IVX]+)\.\s.*", r"\1", t) if re.match(r"^[IVX]+\.", t) else t.split(".")[0])) for sid, t in toc)


def sections(main):
    """blocks() opens a section at each ## and closes the one before it: drop the first close, add the last."""
    return main.replace("</section>", "", 1) + "</section>" if main else ""


def render(short, eyebrow, title, front, toc, main, bar_links, pn):
    toc_html = '<nav class="toc" aria-label="Contents"><h2>Contents</h2><ol>%s</ol></nav>\n  ' % "".join('<li><a href="#%s">%s</a></li>' % (sid, inline(t)) for sid, t in toc) if toc else ""
    bar = '<div class="bar"><div class="bar-in"><strong><a href="index.html">%s</a></strong>%s</div></div>\n' % (html.escape(BRAND), bar_links)
    return (HEAD.replace("{{SHORT}}", html.escape(short)) + MORE + bar
            + '<div class="wrap">\n  <header class="mast">\n    <p class="eyebrow">%s</p>\n    <h1>%s</h1>\n    <div class="front">%s</div>\n  </header>\n  %s<main>\n  %s\n  </main>\n  %s<footer>\n    <p>%s</p>\n  </footer>\n</div>\n'
            % (html.escape(eyebrow), inline(title), front, toc_html, main, pn, inline(FOOT)))


def split_marker(lines):
    """(before, after) around a `!chapters` line, or (lines, None)."""
    stripped = [l.strip() for l in lines]
    if "!chapters" in stripped:
        i = stripped.index("!chapters")
        return lines[:i], lines[i + 1:]
    return lines, None


files = sorted(f for f in glob.glob(os.path.join(BOOK, "[0-9][0-9]-*.md")) if not os.path.basename(f).startswith("00-"))
if not files:
    sys.exit("chapters.py: no NN-slug.md chapters in %s" % BOOK)
front_file = os.path.join(BOOK, "00-front.md")
if not os.path.exists(front_file):
    sys.exit("chapters.py: %s has no 00-front.md (the book's title and front matter)" % BOOK)

chapters = []
for k, f in enumerate(files):
    title, lead, rest = read(f)
    chapters.append({"n": k + 1, "html": os.path.splitext(os.path.basename(f))[0] + ".html", "title": title,
                     "lead": lead, "rest": rest, "blurb": first_paragraph(lead) or first_paragraph(rest)})
M = len(chapters)
os.makedirs(OUT, exist_ok=True)

for c in chapters:
    doc = Doc(BOOK)
    front = doc.blocks(c["lead"])
    main = sections(doc.blocks(c["rest"]))
    prev = chapters[c["n"] - 2] if c["n"] > 1 else None
    nxt = chapters[c["n"]] if c["n"] < M else None
    links = ('<a href="index.html">contents</a>' + numerals(doc.toc)
             + ('<a href="%s">&larr; %d</a>' % (prev["html"], prev["n"]) if prev else "")
             + ('<a href="%s">%d &rarr;</a>' % (nxt["html"], nxt["n"]) if nxt else ""))
    pn = '<nav class="pn" aria-label="Chapters"><span>%s</span><span>%s</span></nav>\n  ' % (
        '<a href="%s">&larr; %d. %s</a>' % (prev["html"], prev["n"], inline(prev["title"])) if prev else '<a href="index.html">&larr; contents</a>',
        '<a href="%s">%d. %s &rarr;</a>' % (nxt["html"], nxt["n"], inline(nxt["title"])) if nxt else '<a href="index.html">contents &rarr;</a>')
    page = render(c["title"], "chapter %d of %d" % (c["n"], M), c["title"], front, doc.toc, main, links, pn)
    open(os.path.join(OUT, c["html"]), "w").write(page)

# The index: the book's title and front matter, the chapter list where `!chapters` stands or after
# the front matter, and any sections the front file has.
btitle, blead, brest = read(front_file)
doc = Doc(BOOK)
listing = '<ol class="chapters">%s</ol>' % "".join(
    '<li><span class="n">%02d</span><a class="t" href="%s">%s</a><p>%s</p></li>' % (c["n"], c["html"], inline(c["title"]), c["blurb"]) for c in chapters)
a, b = split_marker(blead)
front = doc.blocks(a) + (listing + doc.blocks(b) if b is not None else "")
a2, b2 = split_marker(brest)
main = doc.blocks(a2) + (listing + doc.blocks(b2) if b2 is not None else "")
if b is None and b2 is None:
    main += listing
main = sections(main) if doc.toc else main
first = chapters[0]
links = numerals(doc.toc) + '<a href="%s">1 &rarr;</a>' % first["html"]
pn = '<nav class="pn" aria-label="Chapters"><span></span><span><a href="%s">1. %s &rarr;</a></span></nav>\n  ' % (first["html"], inline(first["title"]))
open(os.path.join(OUT, "index.html"), "w").write(render(btitle, EYEBROW, btitle, front, doc.toc, main, links, pn))
print("wrote %s: index.html and %d chapters" % (OUT, M))
