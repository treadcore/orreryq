#!/usr/bin/env python3
"""filmdoc.py OUTDIR -- the diagram of *A Film Beside Every Report* (docs/film-lab-report.md): what is written,
what draws it, and where each thing goes. The numbers in the report's tables are read by hand from the session
of 13 November; this draws only the one picture."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import checked as ck  # noqa: E402
import outgrowing as og  # noqa: E402


def dia_pipeline():
    f = ck.Flow(0, 0, "Diagram 1: a report, its film, and where each thing goes")
    f.T(20, 14, "WRITTEN, in the repository", "ttl")
    f.N("rep", 20, 26, 200, "data", "the lab report", ["docs/NAME-lab-report.md", "and its page"])
    f.N("story", 270, 26, 220, "data", "the storyboard", ["docs/NAME/storyboard.json:", "the film as data"])
    f.N("rec", 540, 26, 200, "data", "recordings", ["docs/NAME/battles.json:", "a card's own trace"])
    f.A("rep", "story", "the argument")
    f.T(20, 150, "WHAT DRAWS IT", "ttl")
    f.N("eng", 20, 162, 200, "fn", "film.py", ["easing, scenes timed by", "their words, teleprompt"])
    f.N("drawn", 270, 162, 220, "fn", "process_film.py", ["SVG frames, a core each;", "stills, page, kit"])
    f.N("blend", 540, 162, 200, "fn", "process_blend_film.py", ["the same timing, in a", "place; words on the lens"])
    f.A("story", "drawn").A("eng", "drawn").A("drawn", "blend", "timing").A("rec", "blend").A("story", "blend", dash=True)
    f.T(20, 286, "WHAT COMES OUT", "ttl")
    f.N("page", 20, 298, 200, "out", "the page", ["docs/NAME-film.html:", "film, chapters, stills"])
    f.N("web", 270, 298, 220, "out", "the film, 720p", ["docs/NAME/film.mp4,", "under 15 MB: repository"])
    f.N("yt", 540, 298, 200, "out", "the YouTube kit", ["output/youtube/NAME/:", "NOT the repository"])
    f.A("drawn", "page").A("drawn", "web").A("drawn", "yt").A("blend", "yt")
    return f.key().svg()


def main(a):
    out = os.path.abspath(a[0])
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "dia-pipeline.html"), "w").write(og.STYLE + dia_pipeline() + "\n")
    print("wrote %s" % out)


if __name__ == "__main__":
    main(sys.argv[1:])
