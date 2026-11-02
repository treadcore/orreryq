#!/usr/bin/env python3
"""md.py: the Markdown the lab reports use, as HTML -- the converter that build.py (one report, one
page) and chapters.py (a book: an index and a page a chapter) share.

Headings, paragraphs, nested lists, tables, fenced code, block quotes, images (embedded), inline code,
bold, italic, links, and two things of our own: `!html(path)` pastes a figure drawn by a script as it is,
and a paragraph in *asterisks* alone is a note. A `Doc` keeps the table of contents its ## headings make,
so a page can set a sticky bar of section numerals from it. It was build.py's body until 2 November 2026;
the output is the same byte for byte, which all.sh run before and after proved."""
import base64
import html
import os
import re
import sys

ITEM = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")


def slug(t):
    t = re.sub(r"`|\*", "", t)
    m = re.match(r"^([IVX]+)\.\s+(.*)", t)
    if m:
        return "s" + m.group(1).lower()
    m = re.match(r"^Appendix ([A-Z])", t)
    if m:
        return "appendix-" + m.group(1).lower()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:40]


def inline(t):
    codes = []

    def keep(m):
        codes.append("<code>%s</code>" % html.escape(m.group(1)))
        return "\x00%d\x00" % (len(codes) - 1)

    t = re.sub(r"`([^`]+)`", keep, t)
    t = t.replace("\\|", "|")
    t = html.escape(t, quote=False)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", t)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], t)


class Doc:
    """One document's converter. Images and `!html` figures are read relative to `base`; `toc`
    collects (id, text) of each ## heading as blocks() meets it, in order."""

    def __init__(self, base):
        self.base = base
        self.toc = []

    def image(self, alt, path):
        data = base64.b64encode(open(os.path.join(self.base, path), "rb").read()).decode()
        return '<img alt="%s" src="data:image/png;base64,%s">' % (html.escape(alt), data)

    def blocks(self, ls):
        out = []
        i = 0
        while i < len(ls):
            ln = ls[i]
            s = ln.strip()
            if not s:
                i += 1
                continue
            # A figure drawn by a script, as it is: !html(path), relative to the report.
            m = re.match(r"^!html\((.+)\)$", s)
            if m:
                out.append(open(os.path.join(self.base, m.group(1))).read())
                i += 1
                continue
            if s.startswith("```"):
                lang = s[3:].strip()
                j = i + 1
                body = []
                while j < len(ls) and not ls[j].strip().startswith("```"):
                    body.append(ls[j])
                    j += 1
                cls = ' class="diagram"' if not lang else ""
                label = '<span class="lang">%s</span>' % lang if lang else ""
                out.append('<div class="code"%s>%s<pre><code>%s</code></pre></div>' % (cls, label, html.escape("\n".join(body))))
                i = j + 1
                continue
            if s == "---":
                i += 1
                continue
            m = re.match(r"^(#{1,3})\s+(.*)", s)
            if m:
                n, text = len(m.group(1)), m.group(2)
                if n == 1:
                    out.append("<h1>%s</h1>" % inline(text))
                else:
                    sid = slug(text)
                    if n == 2:
                        self.toc.append((sid, re.sub(r"`", "", text)))
                        out.append('</section><section id="%s"><h2>%s</h2>' % (sid, inline(text)))
                    else:
                        out.append('<h3 id="%s">%s</h3>' % (sid, inline(text)))
                i += 1
                continue
            # One image or several on a line, side by side in one figure.
            pics = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", s)
            m = pics and re.fullmatch(r"(\s*!\[[^\]]*\]\([^)]+\))+\s*", s)
            if m:
                cap = ""
                j = i + 1
                while j < len(ls) and not ls[j].strip():
                    j += 1
                if j < len(ls) and ls[j].strip().startswith("*Fig."):
                    cl = []
                    while j < len(ls) and ls[j].strip():
                        cl.append(ls[j].strip())
                        j += 1
                    cap = "<figcaption>%s</figcaption>" % inline(" ".join(cl).strip("*"))
                    i = j
                else:
                    i += 1
                out.append("<figure>%s%s</figure>" % ("".join(self.image(alt, p) for alt, p in pics), cap))
                continue
            if s.startswith("|"):
                rows = []
                while i < len(ls) and ls[i].strip().startswith("|"):
                    rows.append(ls[i].strip())
                    i += 1
                cells = [re.split(r"(?<!\\)\|", r.strip("|")) for r in rows]
                head, body = cells[0], [c for c in cells[2:]]
                empty_head = all(not h.strip() for h in head)
                t = ['<div class="table"><table>']
                if not empty_head:
                    t.append("<thead><tr>%s</tr></thead>" % "".join("<th>%s</th>" % inline(h.strip()) for h in head))
                t.append("<tbody>")
                for r in body:
                    t.append("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c.strip()) for c in r))
                t.append("</tbody></table></div>")
                out.append("".join(t))
                continue
            if s.startswith(">"):
                q = []
                while i < len(ls) and ls[i].strip().startswith(">"):
                    q.append(ls[i].strip()[1:].strip())
                    i += 1
                out.append("<blockquote><p>%s</p></blockquote>" % inline(" ".join(q)))
                continue
            m = ITEM.match(ln)
            if m:
                base = len(m.group(1))
                ordered = m.group(2)[0].isdigit()
                items = []
                while i < len(ls):
                    mm = ITEM.match(ls[i])
                    if mm and len(mm.group(1)) == base:
                        items.append([mm.group(3)])
                        i += 1
                        continue
                    if ls[i].strip() and (len(ls[i]) - len(ls[i].lstrip())) > base:
                        items[-1].append(ls[i][base + (3 if ordered else 2):] if True else ls[i])
                        i += 1
                        continue
                    if not ls[i].strip() and i + 1 < len(ls) and ITEM.match(ls[i + 1]) and len(ITEM.match(ls[i + 1]).group(1)) >= base:
                        i += 1
                        continue
                    break
                tag = "ol" if ordered else "ul"
                parts = []
                for it in items:
                    first, rest = it[0], it[1:]
                    # Continuation text belongs to the item's first paragraph
                    # until a nested list or a blank line starts.
                    k = 0
                    while k < len(rest) and rest[k].strip() and not ITEM.match(rest[k]):
                        first += " " + rest[k].strip()
                        k += 1
                    inner = self.blocks([r.lstrip() if not ITEM.match(r) else r for r in rest[k:]]) if rest[k:] else ""
                    parts.append("<li>%s%s</li>" % (inline(first), inner))
                out.append("<%s>%s</%s>" % (tag, "".join(parts), tag))
                continue
            p = []
            while i < len(ls) and ls[i].strip() and not re.match(r"^(#{1,3}\s|```|\||>|!\[)", ls[i].strip()) and not ITEM.match(ls[i]):
                p.append(ls[i].strip())
                i += 1
            if not p:
                # A line some block's pattern starts and no block took (a
                # heading past ###, an image line that is not one): a paragraph
                # of its own, rather than the loop standing on it for good.
                sys.stderr.write("md.py: line taken as text: %s\n" % ls[i].strip()[:70])
                p.append(ls[i].strip())
                i += 1
            text = " ".join(p)
            if text.startswith("*") and text.endswith("*") and text.count("*") == 2:
                out.append('<p class="note">%s</p>' % inline(text.strip("*")))
            else:
                out.append("<p>%s</p>" % inline(text))
        return "".join(out)
