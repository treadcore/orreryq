#!/usr/bin/env python3
"""Numbered marks on the pictures of docs/hearth-regulation-lab-report.md: for each picture a list of
(number, x, y) in the picture's own pixels, drawn as a ringed number, written beside the original as
NAME-marked.png. The report's tables say what each number is.

    python3 tools/report/hearth-annotate.py        (from the repository's root; needs rsvg-convert)

The pictures are 1400 x 860 frames of Orrery (tools/report/hearth-shots.list). A picture taken again
with the panel laid out otherwise wants its marks moved here.
"""
import os
import subprocess

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "hearth-regulation")
MARKS = {
    "hearth": [(1, 150, 286), (2, 640, 262), (3, 870, 262), (4, 1310, 262), (5, 150, 380), (6, 150, 444), (7, 640, 524), (8, 740, 548), (9, 740, 688), (10, 1340, 548)],
    "diagram": [(1, 150, 288), (2, 150, 330), (3, 840, 330), (4, 150, 400), (5, 880, 504), (6, 750, 522), (7, 150, 650), (8, 680, 600), (9, 850, 538), (10, 1040, 650), (11, 1070, 330), (12, 385, 800), (13, 1148, 430), (14, 150, 834)],
    "fleet": [],
}


def main():
    for name, marks in MARKS.items():
        src = os.path.join(D, name + ".png")
        if not marks or not os.path.exists(src):
            continue
        body = ""
        for n, x, y in marks:
            body += ('<circle cx="%d" cy="%d" r="15" fill="#0e1013" stroke="#f7d96f" stroke-width="3"/>'
                     '<text x="%d" y="%d" font-family="Helvetica, Arial, sans-serif" font-size="17" font-weight="700" fill="#f7d96f" text-anchor="middle">%d</text>') % (x, y, x, y + 6, n)
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1400" height="860" viewBox="0 0 1400 860">'
               '<image href="%s.png" xlink:href="%s.png" width="1400" height="860"/>%s</svg>') % (name, name, body)
        open(os.path.join(D, name + "-marked.svg"), "w").write(svg)
        subprocess.run(["rsvg-convert", "-w", "1400", "-h", "860", "-o", name + "-marked.png", name + "-marked.svg"], cwd=D, check=True)
        os.remove(os.path.join(D, name + "-marked.svg"))
        print("%s-marked.png: %d marks" % (name, len(marks)))


if __name__ == "__main__":
    main()
