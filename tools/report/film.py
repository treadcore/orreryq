#!/usr/bin/env python3
"""film: what every drawn film of these reports shares. A film is a function from a time to a picture.

THE METHOD, in the order a film is made (Paul, 13 November: "is there a way to generalize the script describing
creating animations ... describe the timing, pacing, and introduction outside in"):

1. THE WORDS FIRST. Each scene has a narration. Its length at WPM words a minute, with a breath before and
   after, IS the scene's length (`Timeline.say`): nothing is timed by hand, and a scene can never be shorter
   than what is said over it. A "|" in the narration is a cue: `scene["cues"]` holds the second at which the
   word after it is spoken, and the picture's moves are written against cues, not against seconds.
2. ONE STAGE, DRAWN ONCE. The art is a map of fixed things (blocks, borders, arrows) in one coordinate space.
   Scenes do not redraw it: they move a camera over it and change what is lit. The viewer learns the map once.
3. EVERY FRAME IS A FUNCTION OF ITS TIME. Nothing accumulates. A property is `seg(t, a, b)` (0 before a, 1
   after b, eased between) or a `Track` of keyframes; any frame can be rendered alone, in any order, on any
   core, and a still for a page is the same call as a frame of the film.
4. A MOVE HAS THREE PARTS (the animator's rule): it gathers (anticipation: `dip`), it goes (ease in and out:
   `smooth`), it lands (follow-through: `swell`, `back`). One thing moves at a time; while words appear,
   nothing else does.
5. OUTSIDE IN. The film opens on the whole, far off, names its few largest parts, then the borders between
   them, and only then goes inside. Every later scene carries a small map of the whole with its own place
   lit, so no part is seen out of its context.
6. THE TELEPROMPT (`teleprompter`) scrolls the narration in a corner at the same WPM, the spoken word lit;
   `captions` writes the same words as WebVTT and as a timed script.

Frames are SVG, rasterised by librsvg (`rsvg-convert`) a core each, joined by FFmpeg. Plain Python.
"""
import math
import os
import shutil
import subprocess
import tempfile


# ---- easing: every curve takes a share 0..1 and returns a share ------------------------------------------------

def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def smooth(p):
    """Slow away, slow arrival: the default for anything that travels."""
    p = clamp(p)
    return p * p * p * (p * (p * 6 - 15) + 10)


def out(p):
    """Fast away, slow arrival: for things that appear."""
    return 1 - (1 - clamp(p)) ** 3


def back(p, s=1.6):
    """Arrives a little past, and settles: for things that land."""
    p = clamp(p) - 1
    return p * p * ((s + 1) * p + s) + 1


def seg(t, a, b, ease=smooth):
    """0 before a, 1 after b, eased between: the one tween everything is built from."""
    return ease((t - a) / (b - a)) if b > a else float(t >= b)


def appear(t, a, b, fade=0.45):
    """Opacity of a thing shown from a to b."""
    return min(seg(t, a, a + fade), 1 - seg(t, b - fade, b))


def swell(dt, dur=0.5):
    """A single rise and fall over dur seconds from dt = 0: a landing, a pulse."""
    return math.sin(math.pi * dt / dur) if 0 <= dt <= dur else 0.0


def lerp(a, b, p):
    return a + (b - a) * p


def mix(c1, c2, p):
    a, b = [int(c1[i:i + 2], 16) for i in (1, 3, 5)], [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(round(lerp(x, y, clamp(p)))) for x, y in zip(a, b))


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---- the timeline: scenes as long as their words ----------------------------------------------------------------

class Timeline:
    def __init__(self, wpm=150, lead=0.8, tail=1.8):
        self.wpm, self.lead, self.tail, self.scenes, self.t = wpm, lead, tail, [], 0.0

    def say(self, kind, narration, least=0.0, **kw):
        words, cues = [], []
        for w in narration.split():
            if w == "|":
                cues.append(self.lead + len(words) * 60.0 / self.wpm)
            else:
                words.append(w)
        dur = max(least, self.lead + len(words) * 60.0 / self.wpm + self.tail)
        self.scenes.append(dict(kind=kind, t0=self.t, t1=self.t + dur, words=words, cues=cues, **kw))
        self.t += dur

    def at(self, t):
        for s in self.scenes:
            if t < s["t1"]:
                return s
        return self.scenes[-1]

    def sentences(self, sc):
        """(start, end, words) of each sentence of a scene, at the narration's pace."""
        res, first, ws = [], 0, sc["words"]
        for i, w in enumerate(ws):
            if w[-1] in ".?!:" or i == len(ws) - 1:
                res.append((sc["t0"] + self.lead + first * 60.0 / self.wpm, sc["t0"] + self.lead + (i + 1) * 60.0 / self.wpm, " ".join(ws[first:i + 1])))
                first = i + 1
        return res


def clock(t):
    return "%d:%02d" % (t // 60, t % 60)


def stamp(t):
    return "%02d:%02d:%06.3f" % (t // 3600, t % 3600 // 60, t % 60)


def captions(tl, names, out_dir, title):
    """The narration as WebVTT captions and as a timed script; the number of words."""
    vtt, txt = ["WEBVTT", ""], ["%s: the narration, at %d words a minute (%s)" % (title, tl.wpm, clock(tl.t)), ""]
    for sc in tl.scenes:
        txt += ["[%s] %s" % (clock(sc["t0"]), names(sc).upper()), " ".join(sc["words"]), ""]
        for a, b, words in tl.sentences(sc):
            vtt += ["%s --> %s" % (stamp(a), stamp(b)), words, ""]
    open(os.path.join(out_dir, "captions.vtt"), "w").write("\n".join(vtt))
    open(os.path.join(out_dir, "teleprompt.txt"), "w").write("\n".join(txt))
    return sum(len(sc["words"]) for sc in tl.scenes)


def youtube(tl, chapters, out_dir, slug, title, blurb, credits, master=None, poster=None, made_by=""):
    """WHAT A PERSON TAKES TO YOUTUBE, in its own folder outside the repository (output/ is not GitHub's): the
    film, its title, its description with the chapters as YouTube reads them (a time and a name a line, the
    first at 0:00), the credits and the licence, its captions (SubRip), its thumbnail, and the narration as a
    script. `chapters` is [(seconds, name)]. Nothing is uploaded from here: a person does that."""
    os.makedirs(out_dir, exist_ok=True)
    seen, lines = set(), []
    for t, name in chapters:
        c = clock(t)
        if c not in seen and (not lines or t - last >= 10):      # YouTube wants chapters ten seconds apart at least
            seen.add(c)
            lines.append("%s %s" % (c, name))
            last = t
    desc = [title, "", blurb, ""] + lines + [""] + list(credits) + ([made_by] if made_by else [])
    open(os.path.join(out_dir, "description.txt"), "w").write("\n".join(desc) + "\n")
    open(os.path.join(out_dir, "title.txt"), "w").write(title + "\n")
    srt, n = [], 0
    for sc in tl.scenes:
        for a, b, words in tl.sentences(sc):
            n += 1
            srt += [str(n), "%s --> %s" % (stamp(a).replace(".", ","), stamp(b).replace(".", ",")), words, ""]
    open(os.path.join(out_dir, "captions.srt"), "w").write("\n".join(srt))
    open(os.path.join(out_dir, "teleprompt.txt"), "w").write("\n".join(
        ["%s: the narration, at %d words a minute (%s)" % (title, tl.wpm, clock(tl.t)), ""] + [l for sc in tl.scenes for l in ("[%s]" % clock(sc["t0"]), " ".join(sc["words"]), "")]))
    made = ["description.txt", "title.txt", "captions.srt", "teleprompt.txt"]
    if master and os.path.exists(master):
        shutil.copy(master, os.path.join(out_dir, slug + ".mp4"))
        made.append(slug + ".mp4")
    if poster and os.path.exists(poster):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", poster, "-vf", "scale=1280:720:flags=lanczos", os.path.join(out_dir, "thumbnail.png")], check=True)
        made.append("thumbnail.png")
    return made


# ---- the teleprompt ----------------------------------------------------------------------------------------------

def teleprompter(tl, t, sc, box, font, ink, dim, lit, faint, width=36):
    """The scene's narration scrolling in a box at the timeline's pace, the word being spoken lit."""
    if "lines" not in sc:
        lines, cur, n = [], [], 0
        for i, w in enumerate(sc["words"]):
            if n + len(w) + 1 > width and cur:
                lines.append(cur)
                cur, n = [], 0
            cur.append((i, w))
            n += len(w) + 1
        sc["lines"] = lines + ([cur] if cur else [])
    lines = sc["lines"]
    if not lines:
        return ""
    u = t - sc["t0"]
    op = seg(u, 0.0, 0.5) * (1 - seg(t, sc["t1"] - 0.4, sc["t1"]))
    pos = clamp((u - tl.lead) * tl.wpm / 60.0, 0, len(sc["words"]) - 0.001)
    li = next(i for i, l in enumerate(lines) if l[-1][0] >= int(pos))
    frac = (pos - lines[li][0][0]) / len(lines[li])
    x, y, w, h = box
    size, lh, top = 23.5, 34, y + 50
    y0 = top + lh * 1.2 - (li + frac) * lh
    b = '<rect x="%d" y="%d" width="%d" height="%d" rx="14" fill="#0a0b0d" fill-opacity="%.3f" stroke="%s" stroke-opacity="%.3f" stroke-width="1.5"/>' % (x, y, w, h, 0.97 * op, faint, op)
    b += '<text x="%d" y="%d" font-family="%s" font-size="12.5" font-weight="700" letter-spacing="2" fill="%s" fill-opacity="%.3f">NARRATION  ·  %d WORDS A MINUTE</text>' % (
        x + 18, y + 27, font, dim, op, tl.wpm)
    b += '<polygon points="%d,%.1f %d,%.1f %d,%.1f" fill="%s" fill-opacity="%.3f"/>' % (x + 8, top + lh * 1.2 - 15, x + 8, top + lh * 1.2 + 1, x + 16, top + lh * 1.2 - 7, lit, op)
    b += '<clipPath id="tp"><rect x="%d" y="%d" width="%d" height="%d"/></clipPath><g clip-path="url(#tp)">' % (x, top - 12, w, h - 50)
    for i, l in enumerate(lines):
        yy = y0 + i * lh
        if yy < top - 30 or yy > y + h + 30:
            continue
        spans = "".join('<tspan fill="%s" fill-opacity="%.3f" font-weight="%d">%s </tspan>' % (
            lit if k == int(pos) else ink, op * (1.0 if k == int(pos) else 0.38 if k < pos else 0.88), 700 if k == int(pos) else 400, esc(w_)) for k, w_ in l)
        b += '<text x="%d" y="%.1f" font-family="%s" font-size="%.1f" xml:space="preserve">%s</text>' % (x + 26, yy, font, size, spans)
    return b + "</g>"


# ---- rendering ---------------------------------------------------------------------------------------------------

def render(svg, png, w, h):
    subprocess.run(["rsvg-convert", "-w", str(w), "-h", str(h), "-o", png], input=svg.encode(), check=True)


_JOB = {}


def _one(i):
    j = _JOB
    render(j["frame"](i / j["fps"]), os.path.join(j["tmp"], "f%05d.png" % i), *j["size"])


def render_film(frame, length, fps, size, out, poster_at=None, crf=23):
    """Every frame of frame(t) for t in [0, length), a core each, then the film; the poster is one of its frames.
    A process a core, forked, not a thread: drawing a frame is Python, and threads took turns at it (5 frames a
    second on eight cores on 13 November, where the rasteriser alone would do 30)."""
    import multiprocessing
    tmp = tempfile.mkdtemp(prefix="film-")
    n = int(length * fps)
    _JOB.update(frame=frame, fps=fps, tmp=tmp, size=size)
    with multiprocessing.get_context("fork").Pool(os.cpu_count() or 4) as pool:
        pool.map(_one, range(n), chunksize=24)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(tmp, "f%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", str(crf), "-preset", "slow", "-tune", "animation", "-movflags", "+faststart", out], check=True)
    if poster_at is not None:
        shutil.copy(os.path.join(tmp, "f%05d.png" % int(poster_at * fps)), os.path.join(os.path.dirname(out), "poster.png"))
    shutil.rmtree(tmp)
    return n
