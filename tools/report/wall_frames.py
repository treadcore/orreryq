#!/usr/bin/env python3
"""wall_frames.py FRAMES.jsonl OUTDIR -- a wall taking the gun, drawn from treadcore-sim's own state.

Paul, 6 November: "continue unifiying the motor and the types of direct fire to take down a wall ... we have
new screenshots to take ... feed many zoomed in and concept level articulate what the crop shows." The game's
client has no picture of its own to take from a script, so the scene is played by treadcore-sim itself (a
scratch program steps a World and writes every tile, tank and shell a frame every other tick, JSON lines) and
drawn here tile for tile in the montage's palette: grass, wall, rubble, the learner in sky blue, the other in
red, shells in orange. A struck tile is outlined in orange and carries the health it has left (of 90).

Writes OUTDIR/wall-<n>-<name>.png, the whole field, and OUTDIR/wall-<n>-<name>-zoom.png, the ten tiles
round the gap at six times the scale, for the moments: before, each shell in flight, the first hit, the fall,
the drive through.
"""
import json
import os
import subprocess
import sys

GRASS, GRID = (27, 41, 30), (34, 52, 37)
WALL, RUBBLE, ROAD = (120, 132, 118), (104, 94, 79), (70, 70, 64)
ME, FOE, SHELL, MARK = (108, 196, 255), (232, 88, 79), (255, 160, 64), (255, 160, 64)
TILE = {".": GRASS, "W": WALL, "%": RUBBLE, "=": ROAD}


class Img:
    def __init__(self, w, h, c):
        self.w, self.h = w, h
        self.b = bytearray(bytes(c) * (w * h))

    def rect(self, x, y, w, h, c):
        for yy in range(max(0, int(y)), min(self.h, int(y + h))):
            o = (yy * self.w + max(0, int(x))) * 3
            n = max(0, min(self.w, int(x + w)) - max(0, int(x)))
            self.b[o:o + 3 * n] = bytes(c) * n

    def disc(self, cx, cy, r, c):
        for yy in range(int(cy - r), int(cy + r) + 1):
            for xx in range(int(cx - r), int(cx + r) + 1):
                if 0 <= xx < self.w and 0 <= yy < self.h and (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                    o = (yy * self.w + xx) * 3
                    self.b[o:o + 3] = bytes(c)

    def line(self, x0, y0, x1, y1, c, wd=2):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(n + 1):
            x, y = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n
            self.rect(x - wd / 2, y - wd / 2, wd, wd, c)

    def outline(self, x, y, w, h, c, wd=3):
        self.rect(x, y, w, wd, c)
        self.rect(x, y + h - wd, w, wd, c)
        self.rect(x, y, wd, h, c)
        self.rect(x + w - wd, y, wd, h, c)

    def save(self, path):
        ppm = path[:-4] + ".ppm"
        with open(ppm, "wb") as f:
            f.write(b"P6\n%d %d\n255\n" % (self.w, self.h) + bytes(self.b))
        subprocess.run(["magick", ppm, path], check=True)
        os.remove(ppm)


def draw(fr, px, x0=0, y0=0, x1=None, y1=None):
    """One frame, tiles x0..x1, y0..y1 at px pixels a tile."""
    rows = fr["tiles"].split("|")
    x1 = x1 if x1 is not None else len(rows[0])
    y1 = y1 if y1 is not None else len(rows)
    im = Img((x1 - x0) * px, (y1 - y0) * px, GRASS)
    for y in range(y0, y1):
        for x in range(x0, x1):
            c = TILE.get(rows[y][x], GRASS)
            im.rect((x - x0) * px + 1, (y - y0) * px + 1, px - 1, px - 1, c)
            if c is GRASS:
                im.rect((x - x0) * px, (y - y0) * px, px, 1, GRID)
                im.rect((x - x0) * px, (y - y0) * px, 1, px, GRID)
    labels = []
    for (x, y, hp) in fr["wall_hits"]:
        if x0 <= x < x1 and y0 <= y < y1:
            im.outline((x - x0) * px, (y - y0) * px, px, px, MARK, max(2, px // 12))
            labels.append(((x - x0 + 0.5) * px, (y - y0 + 0.5) * px, "%d" % hp))
    for (owner, tx, ty, hd) in fr["tanks"]:
        cx, cy = (tx - x0) * px, (ty - y0) * px
        import math
        im.line(cx, cy, cx + math.cos(hd) * px * 1.0, cy + math.sin(hd) * px * 1.0, (20, 20, 20), max(2, px // 8))
        im.disc(cx, cy, px * 0.75, ME if owner == 0 else FOE)
        im.line(cx, cy, cx + math.cos(hd) * px * 1.1, cy + math.sin(hd) * px * 1.1, (16, 24, 32), max(2, px // 10))
    for (sx, sy) in fr["shells"]:
        im.disc((sx - x0) * px, (sy - y0) * px, max(2, px * 0.18), SHELL)
    return im, labels


def write(im, labels, path, px):
    im.save(path)
    if labels:
        args = ["magick", path, "-font", "Helvetica-Bold", "-pointsize", str(max(12, px // 3)), "-fill", "white", "-gravity", "NorthWest"]
        for (x, y, s) in labels:
            args += ["-annotate", "+%d+%d" % (x - px * 0.28, y - px * 0.2), s]
        subprocess.run(args + [path], check=True)


def main(a):
    if len(a) < 2:
        print(__doc__)
        sys.exit(2)
    fr = {f["tick"]: f for f in (json.loads(l) for l in open(a[0]))}
    out = a[1]
    os.makedirs(out, exist_ok=True)
    first = min(t for t, f in fr.items() if f["wall_hits"])
    fell = min(t for t, f in fr.items() if any(e[0] == "fell" for e in f["events"]))
    through = min(t for t, f in fr.items() if f["tanks"][0][1] > 22.0)
    # A shell halfway: the frame in the middle of each flight.
    flights = [t for t, f in sorted(fr.items()) if f["shells"]]
    one = [t for t in flights if t < first]
    two = [t for t in flights if first < t < fell]
    moments = [(0, "before", min(fr) + 4), (1, "first-shell", one[len(one) // 2]), (2, "first-hit", first),
               (3, "second-shell", two[len(two) // 2]), (4, "fallen", fell), (5, "through", through)]
    for n, name, t in moments:
        f = fr[t]
        im, labels = draw(f, 24)
        write(im, labels, os.path.join(out, "wall-%d-%s.png" % (n, name)), 24)
        im, labels = draw(f, 64, 15, 7, 26, 16)
        write(im, labels, os.path.join(out, "wall-%d-%s-zoom.png" % (n, name)), 64)
        print("wall-%d-%s: tick %d (%.1f s)" % (n, name, t, t / 20.0))


if __name__ == "__main__":
    main(sys.argv[1:])
