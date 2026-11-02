#!/usr/bin/env python3
"""build.py REPORT.md OUT.html [SHORT [EYEBROW]] -- a lab report as a page.

all.sh builds every one, each with its eyebrow (the small line over the
title).

SHORT is the browser tab's title, a few words (the report's own title up
to its colon by default). The page links back to docs/index.html, where
every report is listed. The converter for the Markdown the reports use
(headings, paragraphs, nested lists, tables, fenced code, block quotes,
images, inline code, bold, italic, links; images embedded) is md.py beside
this file, which chapters.py shares for a book of chapters.
"""
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md import Doc, inline  # noqa: E402

SRC, OUT = sys.argv[1], sys.argv[2]
BASE = os.path.dirname(os.path.abspath(SRC))
lines = open(SRC).read().split("\n")

# The masthead: the title, the format line, the copyright, the companions.
title = lines[0].lstrip("# ").strip()
body_start = next(i for i, l in enumerate(lines) if l.startswith("## Abstract"))
doc = Doc(BASE)
front = doc.blocks(lines[1:body_start])
main = doc.blocks(lines[body_start:])
main = main.replace("</section>", "", 1) + "</section>"
toc = doc.toc

nav = "".join('<a href="#%s">%s</a>' % (sid, html.escape(re.sub(r"^([IVX]+)\.\s.*", r"\1", t) if re.match(r"^[IVX]+\.", t) else t.split(".")[0])) for sid, t in toc)
toc_list = "".join('<li><a href="#%s">%s</a></li>' % (sid, inline(t)) for sid, t in toc)

page = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "page.html")).read()
short = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else re.sub(r"`", "", title.split(":")[0]).strip()
eyebrow = sys.argv[4] if len(sys.argv) > 4 else "orrery · lab report"
page = page.replace("{{SHORT}}", html.escape(short)).replace("{{EYEBROW}}", html.escape(eyebrow)).replace("{{TITLE}}", inline(title)).replace("{{FRONT}}", front).replace("{{NAV}}", nav)
page = page.replace("{{TOC}}", toc_list).replace("{{MAIN}}", main)
open(OUT, "w").write(page)
print("wrote", OUT, len(page), "bytes;", len(toc), "sections")
