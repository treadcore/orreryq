#!/usr/bin/env python3
"""collect.py -- every lab report of orrery and of treadcore as HTML, and one page that lists them all.

Paul, 4 November: "in fact continue to collect treadcore and orrery lab reports and place them as html."
all.sh runs this after building orrery's own reports, so the collection follows both repositories.

  python3 tools/report/collect.py            build what changed, then the list and the index's cards
  python3 tools/report/collect.py --all      build every page again

WHAT IT BUILDS. treadcore's lab reports (documentation/LAB-REPORT*.md) to docs/treadcore/, and its
check-in reports (documentation/checkins/CI-*.md) to docs/treadcore/checkins/, each a page in the same
form as orrery's reports (page.html and md.py: the masthead, the contents, numbered sections, images
embedded). A page is built again only when its Markdown, md.py, page.html or this file is newer.

WHAT IT LISTS. docs/reports.html: orrery's lab reports (docs/*-lab-report.md), treadcore's lab reports,
its check-ins and the reports posted on treadcore.org (treadcore's reports/*.html), newest first. And in
docs/index.html, between the collect.py markers in the Lab reports section, a card each for the newest
orrery report, the list, treadcore's brain report and the newest check-in; the count in the masthead.

IT READS treadcore's checkout (TREADCORE, default ~/code/treadcore) and never writes there.
"""
import base64
import html
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from md import Doc, inline  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
DOCS = os.path.join(ROOT, "docs")
TC = os.path.expanduser(os.environ.get("TREADCORE", "~/code/treadcore"))
OUT_TC = os.path.join(DOCS, "treadcore")
OUT_CI = os.path.join(OUT_TC, "checkins")
GITHUB = "https://github.com/treadcore/treadcore/blob/main/"
SITE = "https://treadcore.org/reports/"
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], 1)}
TEMPLATE = os.path.join(HERE, "page.html")
# A report's card on the index says what the hand-made cards say: its topic and what it found, in a few
# lines. A report not named here gets its eyebrow's first part and its abstract's opening.
CARDS = {
    "visual": ("Montage · every screen",
               "The film shows the champion thinking: a crowd of its other duels, its 55 inputs, two layers lit by their strongest "
               "currents, eight seconds of its decisions, the generation. Every screen of orrery and of the game, pictured; a Mind "
               "explorer to play in the page; the films listed on Results, Videos."),
}


class Page(Doc):
    """md.py's converter, with an image of any common type, and a missing one said rather than fatal."""

    def image(self, alt, path):
        p = os.path.join(self.base, path)
        if not os.path.exists(p):
            return '<p class="note">[an image the source names is not in its checkout: %s]</p>' % html.escape(path)
        ext = os.path.splitext(p)[1].lower().lstrip(".")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "svg": "image/svg+xml", "webp": "image/webp"}.get(ext, "image/png")
        return '<img alt="%s" src="data:%s;base64,%s">' % (html.escape(alt), mime, base64.b64encode(open(p, "rb").read()).decode())


def git_date(path):
    """The day a file was last committed, YYYY-MM-DD; its own time when git does not know it."""
    r = subprocess.run(["git", "-C", os.path.dirname(path), "log", "-1", "--format=%cs", "--", os.path.basename(path)], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    import time
    return time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(path)))


def written_date(text, fallback):
    """The date a report says it was written ("... · 30 October 2026", "18 October 2026."), as YYYY-MM-DD."""
    m = re.search(r"(\d{1,2}) (%s) (20\d\d)" % "|".join(MONTHS), text[:2000])
    return "%s-%02d-%02d" % (m.group(3), MONTHS[m.group(2)], int(m.group(1))) if m else fallback


def stale(src, out, force):
    if force or not os.path.exists(out):
        return True
    newest = max(os.path.getmtime(p) for p in (src, TEMPLATE, os.path.join(HERE, "md.py"), os.path.abspath(__file__)))
    return os.path.getmtime(out) < newest


def page(title, short, eyebrow, front, nav, toc, main, up):
    p = open(TEMPLATE).read()
    p = p.replace('<strong><a href="index.html">orrery</a> · lab report</strong>',
                  '<strong><a href="%sreports.html">lab reports</a> · <a href="%sindex.html">orrery</a></strong>' % (up, up))
    p = p.replace('<nav class="toc"', '<nav class="toc" id="contents"', 1)
    p = p.replace("{{SHORT}}", html.escape(short)).replace("{{EYEBROW}}", html.escape(eyebrow)).replace("{{TITLE}}", title)
    p = p.replace("{{FRONT}}", front).replace("{{NAV}}", nav).replace("{{TOC}}", toc).replace("{{MAIN}}", main)
    return p


def build(src, out, eyebrow, up, source_url):
    """A Markdown report as a page: its title, what stands before its first section as the front, the rest
    numbered. A report of many sections (the brain's has 146) gets a short bar: the contents and the newest."""
    lines = open(src).read().split("\n")
    title = lines[0].lstrip("# ").strip()
    ab = next((i for i, l in enumerate(lines) if l.startswith("## Abstract")), None)
    body = ab if ab is not None else next((i for i, l in enumerate(lines) if l.startswith("## ")), 1)
    doc = Page(os.path.dirname(src))
    front = doc.blocks(lines[1:body]) + '<p class="note">Source: <a href="%s">%s</a>, built by orrery\'s tools/report/collect.py.</p>' % (source_url, html.escape(os.path.relpath(src, TC)))
    main = doc.blocks(lines[body:])
    main = main.replace("</section>", "", 1) + "</section>"
    toc = doc.toc
    if len(toc) <= 16:
        nav = "".join('<a href="#%s">%s</a>' % (sid, html.escape(re.sub(r"^([IVX]+)\.\s.*", r"\1", t) if re.match(r"^[IVX]+\.", t) else t.split(".")[0][:14])) for sid, t in toc)
    else:
        nav = '<a href="#contents">Contents</a>' + ('<a href="#%s">Newest section</a>' % toc[-1][0] if toc else "")
    toc_list = "".join('<li><a href="#%s">%s</a></li>' % (sid, inline(t)) for sid, t in toc)
    short = re.sub(r"[`*]", "", title.split(":")[0]).strip()
    if len(short) > 60:
        short = short[:60].rsplit(" ", 1)[0].rstrip(",;")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out + ".part", "w") as f:
        f.write(page(inline(title), short, eyebrow, front, nav, toc_list, main, up))
    os.replace(out + ".part", out)
    return title, toc


def first_title(path):
    with open(path) as f:
        return f.readline().lstrip("# ").strip()


def collect(force=False):
    built = 0
    # ---- treadcore's lab reports ----
    tc_reports = []
    for name in sorted(os.listdir(os.path.join(TC, "documentation"))):
        if not re.match(r"^LAB-REPORT.*\.md$", name):
            continue
        src = os.path.join(TC, "documentation", name)
        slug = name[:-3].lower()
        out = os.path.join(OUT_TC, slug + ".html")
        if stale(src, out, force):
            build(src, out, "treadcore · lab report · %s" % (slug.replace("lab-report-", "").replace("lab-report", "the game") or "the game"), "../", GITHUB + "documentation/" + name)
            built += 1
        text = open(src).read()
        secs = re.findall(r"^## (.+)$", text, re.M)
        tc_reports.append({"title": first_title(src), "date": git_date(src), "href": "treadcore/%s.html" % slug, "src": GITHUB + "documentation/" + name,
                           "sections": len(secs), "newest": secs[-1] if secs else "", "slug": slug, "lines": text.count("\n")})
    tc_reports.sort(key=lambda r: r["date"], reverse=True)
    # ---- treadcore's check-ins ----
    checkins = []
    cdir = os.path.join(TC, "documentation", "checkins")
    for name in sorted(os.listdir(cdir)):
        m = re.match(r"^CI-(\d+)-(\d{4}-\d\d-\d\d)-.*\.md$", name)
        if not m:
            continue
        src = os.path.join(cdir, name)
        out = os.path.join(OUT_CI, name[:-3] + ".html")
        if stale(src, out, force):
            build(src, out, "treadcore · check-in report CI-%s" % m.group(1), "../../", GITHUB + "documentation/checkins/" + name)
            built += 1
        checkins.append({"n": int(m.group(1)), "date": m.group(2), "title": first_title(src), "href": "treadcore/checkins/%s.html" % name[:-3]})
    checkins.sort(key=lambda c: (c["date"], c["n"]), reverse=True)
    # ---- orrery's lab reports ----
    eyebrows = {}
    for line in open(os.path.join(HERE, "all.sh")):
        parts = line.strip().split("|")
        if len(parts) == 3:
            eyebrows[parts[0]] = parts[2]
    orrery = []
    for name in sorted(os.listdir(DOCS)):
        if not name.endswith("-lab-report.md"):
            continue
        key = name[:-len("-lab-report.md")]
        src = os.path.join(DOCS, name)
        if not os.path.exists(os.path.join(DOCS, key + "-lab-report.html")):
            continue
        text = open(src).read()
        eb = eyebrows.get(key)
        if not eb:
            m = re.search(r'<p class="eyebrow">(.*?)</p>', open(os.path.join(DOCS, key + "-lab-report.html")).read())
            eb = html.unescape(m.group(1)) if m else "orrery · lab report"
        lines = [l for l in text.split("\n") if l.strip()]
        title = next((l.lstrip("# ").strip() for l in lines if l.startswith("# ")), key)
        orrery.append({"title": title, "date": written_date(text, git_date(src)), "href": key + "-lab-report.html", "md": name, "topic": eb, "key": key})
    orrery.sort(key=lambda r: (r["date"], r["key"]), reverse=True)
    # ---- posted on treadcore.org ----
    posts = []
    rdir = os.path.join(TC, "reports")
    for name in sorted(os.listdir(rdir)) if os.path.isdir(rdir) else []:
        m = re.match(r"^(\d{4}-\d\d-\d\d)-(.+)\.html$", name)
        if not m:
            continue
        t = re.search(r"<title>(.*?)</title>", open(os.path.join(rdir, name), errors="replace").read(20000), re.S)
        posts.append({"date": m.group(1), "title": html.unescape(t.group(1)).strip() if t else m.group(2).replace("-", " "), "href": SITE + name})
    posts.sort(key=lambda p: p["date"], reverse=True)
    write_list(orrery, tc_reports, checkins, posts)
    write_cards(orrery, tc_reports, checkins, posts)
    print("collect: %d pages built; listed %d orrery reports, %d treadcore reports, %d check-ins, %d posted on treadcore.org"
          % (built, len(orrery), len(tc_reports), len(checkins), len(posts)))


def day(d):
    y, m, dd = d.split("-")
    return "%d %s %s" % (int(dd), [k for k, v in MONTHS.items() if v == int(m)][0][:3], y)


def write_list(orrery, tc_reports, checkins, posts):
    e = html.escape
    rows = lambda items: "".join(items)
    sec1 = rows('<tr><td>%s</td><td><a href="%s">%s</a></td><td>%s</td><td><a href="%s">Markdown</a></td></tr>' % (day(r["date"]), r["href"], inline(r["title"]), e(r["topic"]), r["md"]) for r in orrery)
    sec2 = rows('<tr><td>%s</td><td><a href="%s">%s</a></td><td>%d</td><td>%s</td><td><a href="%s">source</a></td></tr>' % (day(r["date"]), r["href"], inline(r["title"]), r["sections"], inline(r["newest"][:90]), r["src"]) for r in tc_reports)
    sec3 = rows('<tr><td>CI-%03d</td><td>%s</td><td><a href="%s">%s</a></td></tr>' % (c["n"], day(c["date"]), c["href"], inline(c["title"])) for c in checkins)
    sec4 = rows('<tr><td>%s</td><td><a href="%s">%s</a></td></tr>' % (day(p["date"]), p["href"], e(p["title"])) for p in posts)
    tbl = lambda head, body: '<div class="table"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % ("".join("<th>%s</th>" % h for h in head), body)
    main = (
        '<section id="orrery"><h2>I. orrery\'s lab reports</h2><p>The console\'s own reports, each built from its Markdown by <code>tools/report/build.py</code> (or, for one with a working figure, written as its page). %d in all.</p>%s</section>'
        % (len(orrery), tbl(["Written", "Report", "About", ""], sec1))
        + '<section id="treadcore"><h2>II. treadcore\'s lab reports</h2><p>The game\'s reports, from <code>documentation/</code> in its repository, as pages here. The brain\'s report grows a section a step; its newest is named.</p>%s</section>'
        % tbl(["Updated", "Report", "Sections", "Newest section", ""], sec2)
        + '<section id="checkins"><h2>III. treadcore\'s check-in reports</h2><p>One for each step of the brain, in IEEE form: the intent in Paul\'s words, the decisions and their causes, the method, the results, what is not built. %d in all, newest first.</p>%s</section>'
        % (len(checkins), tbl(["Number", "Date", "Report"], sec3))
        + '<section id="posted"><h2>IV. Posted on treadcore.org</h2><p>The reports put on the game\'s site, %d in all; these links leave this folder.</p>%s</section>'
        % (len(posts), tbl(["Posted", "Report"], sec4))
    )
    toc = [("orrery", "I. orrery's lab reports"), ("treadcore", "II. treadcore's lab reports"), ("checkins", "III. treadcore's check-in reports"), ("posted", "IV. Posted on treadcore.org")]
    front = ('<p class="note">Collected by <code>tools/report/collect.py</code>, which <code>tools/report/all.sh</code> runs after building orrery\'s reports.</p>'
             '<p>%d lab reports of orrery, %d of treadcore, %d check-in reports and %d reports posted on treadcore.org. Every page is HTML in this folder but the last, which link to the game\'s site.</p>'
             % (len(orrery), len(tc_reports), len(checkins), len(posts)))
    nav = "".join('<a href="#%s">%s</a>' % (sid, t.split(".")[0]) for sid, t in toc)
    toc_list = "".join('<li><a href="#%s">%s</a></li>' % (sid, html.escape(t)) for sid, t in toc)
    p = page("Every Lab Report: orrery's and treadcore's, in One Place", "Every Lab Report", "orrery · treadcore · the lab reports, collected", front, nav, toc_list, main, "")
    with open(os.path.join(DOCS, "reports.html") + ".part", "w") as f:
        f.write(p)
    os.replace(os.path.join(DOCS, "reports.html") + ".part", os.path.join(DOCS, "reports.html"))


def card(when, topic, title, href, text, links, new=False):
    return ('    <article class="report%s">\n      <div class="when"><span>%s</span><span class="topic">%s</span></div>\n'
            '      <h3><a href="%s">%s</a></h3>\n      <p>%s</p>\n      <div class="links">%s</div>\n    </article>\n'
            % (" new" if new else "", when, html.escape(topic), href, title, text, "".join('<a href="%s">%s</a>' % (h, html.escape(t)) for h, t in links)))


def write_cards(orrery, tc_reports, checkins, posts):
    """The generated cards at the head of the index's Lab reports section, and the masthead's count."""
    p = os.path.join(DOCS, "index.html")
    s = open(p).read()
    begin, end = "    <!-- collect.py: begin -->\n", "    <!-- collect.py: end -->\n"
    cards = ""
    newest = orrery[0] if orrery else None
    if newest and "%s-lab-report.html" % newest["key"] not in re.sub(r"<!-- collect\.py: begin -->.*?<!-- collect\.py: end -->", "", s, flags=re.S):
        lead = re.search(r'<section id="abstract">.*?<p>(.*?)</p>', open(os.path.join(DOCS, newest["href"])).read(), re.S)
        text = re.sub(r"<[^>]+>", "", lead.group(1)) if lead else ""
        text = (text[:330].rsplit(" ", 1)[0] + "...") if len(text) > 330 else text
        topic = newest["topic"].replace("orrery · ", "").split(" · ")[0].capitalize()
        topic, text = CARDS.get(newest["key"], (topic, text))
        links = [(newest["href"], "the full report"), (newest["md"], "the Markdown")]
        if os.path.exists(os.path.join(DOCS, "visual", "montage.mp4")) and newest["key"] == "visual":
            links.append(("visual/montage.mp4", "the film"))
        # Posted on treadcore.org: the posting whose title opens the report's.
        posted = next((p for p in posts if newest["title"].startswith(p["title"]) or p["title"].startswith(newest["title"].split(":")[0])), None)
        if posted:
            links.append((posted["href"], "on treadcore.org"))
        cards += card(day(newest["date"]), topic, inline(newest["title"]), newest["href"], html.escape(text), links, new=True)
    cards += card(day(max([r["date"] for r in orrery] + [c["date"] for c in checkins])), "Collected", "Every Lab Report, orrery's and treadcore's", "reports.html",
                  "%d of orrery's, %d of treadcore's, %d check-in reports and %d posted on treadcore.org, as pages here, newest first. Rebuilt with orrery's own each time <code>tools/report/all.sh</code> runs." % (len(orrery), len(tc_reports), len(checkins), len(posts)),
                  [("reports.html", "the list"), ("reports.html#checkins", "the check-ins")], new=True)
    brain = next((r for r in tc_reports if r["slug"] == "lab-report-brain"), None)
    if brain:
        cards += card(day(brain["date"]), "treadcore · brain", inline(brain["title"]).capitalize(), brain["href"],
                      "The game's brain, a section a step: %d sections so far. The newest: %s" % (brain["sections"], inline(brain["newest"])),
                      [(brain["href"], "the full report"), (brain["src"], "the source")])
    if checkins:
        c = checkins[0]
        cards += card(day(c["date"]), "treadcore · check-in CI-%03d" % c["n"], inline(c["title"]), c["href"],
                      "The newest of treadcore's %d check-in reports: the intent, the decisions and their causes, the method, the results, and what is not built." % len(checkins),
                      [(c["href"], "the report"), ("reports.html#checkins", "every check-in")])
    if begin in s and end in s:
        s = s[:s.index(begin) + len(begin)] + cards + s[s.index(end):]
    else:
        anchor = '  <div class="reports">\n'
        if anchor not in s:
            raise SystemExit("docs/index.html: no reports grid to put the cards in")
        s = s.replace(anchor, anchor + begin + cards + end, 1)
    total = len(re.findall(r'<article class="report', s))
    s = re.sub(r"<span><b>\d+</b> lab reports[^<]*</span>", "<span><b>%d</b> lab reports, <b>%d</b> check-ins</span>" % (len(orrery) + len(tc_reports), len(checkins)), s, count=1)
    with open(p + ".part", "w") as f:
        f.write(s)
    os.replace(p + ".part", p)
    return total


if __name__ == "__main__":
    collect(force="--all" in sys.argv[1:])
