#!/usr/bin/env python3
"""montage.py QUEUE make [--chapters N] [--duels N] [--host NAME] [--seed S] [--since start|LABEL] | trailer [--gens N] [--duels N]
[--host NAME] | line [OUT.mp4] | status -- the generations
since the last montage, as a film: crucible's world duels, the camera on the best winning tank, every other
duel a ghost.

Paul, 4 November: "add visual recording mechanism. where we can get a montoge of kill shots and pillbox
fights. Make it like a AI training montoge, where we have about 1 second of clips just before the shot, and
about 0.5 seconds after. We then watch the multitudes of permutations in the same world such that the camera
following the best winning tank as it grows via generations, give a title screen 0.25 second long overlay when
we switch generation showing in the upper right ... make this repeatable via a button in Orrery ... All the
other permutations are ghosts." Asked and answered the same morning: crucible's world duels; the ghosts are
the same start played many times with the dice choosing the opponent; each press covers the generations since
the last montage.

THE CHAPTERS are the world home's ladder: each milestone taken since the last montage is a generation the
fleet judged better than every one before it, and the newest champion of the island that took the latest one
closes the film. More than --chapters (12) are thinned, the first and the last kept.

THE DUELS come from crucible's own --trace, on a GPU island (the islands' build, run once in
~/fleet/q-NAME/montage): every chapter's champion plays --duels (128) duels in ONE ARENA, the opponents drawn
by the duel's index -- half sparring partners of drawn skill, half milestones spread over the ladder -- and
each duel's tanks moved up to SPREAD (3) tiles from one start by dice that are the duel's index too
(--trace-spread, 5 November: from one start the 64 duels had been a dozen games, their ghosts stacked). So
duel d is the same contest in every chapter and the film compares like with like. The trace writes every
step (0.1 s) of every duel.

THE CLIPS. In each chapter the camera follows the duel the champion won best (the highest fitness among its
wins; with no win, its best duel), and cuts its kill shot and its pillbox fights -- a pillbox struck, taken,
or shooting at it -- from 1.0 s before to 0.5 s after each, a step drawn as three frames at 30 a second.
Every other duel is drawn at the same moment as a ghost: dim, and no thing in one duel touches another. The
pillboxes are the followed duel's. When the generation changes, a title holds the upper right for 0.25 s.
Since 5 November each chapter also replays its kill shot at half speed and closer, shows its hardest win
(against the strongest milestone it beat) and a loss, and draws the champions of the five chapters before it
in the followed duel, lavender, the older the fainter.

THE LINE comes first (Paul, 5 November: "describe the success story of each generation move ... Show the
chain, show the arrows in the flowchart"): the game's own brain, the last generations orrery's line
committed, each as its chain of jobs with an arrow from each to the one it followed, the dials it moved in
the weights table's words, every try of its promotion with what failed and what mended it, orrery's
Timeline, Flow and Lineup with its chain lit, and where its commit stands against main. `montage.py QUEUE
line [OUT.mp4]` renders that act alone.

THE TRAILER (6 November) is the line's news under a minute: the generations committed since the last film
told them, one champion's duel, where the commits stand. The planner asks for one every 2 generations;
archive/trailers/NNNN/, output/treadcore-trailer-NNNN.mp4, plan/trailer.json its state.

THE STORY between them is orrery's own pictures: the flowchart, the history (Growth), the terrain and the
spectrum open the film; each chapter opens on the Growth page with its generation marked and the facts of its
segment in 48 and 32 point type; the last card is every chapter's wins, losses and draws in a column.

AFTER: the film and summary.json go to archive/montages/NNNN/; the trace, the frames and the segments are
deleted, on the GPU machine as on the Mac; a flag says the film is ready. plan/montage.json is the state the
Montage page shows while it works, with plan/montage-preview.ppm, the newest frame, small.
"""
import array
import glob
import importlib.util
import json
import math
import os
import re
import shlex
import shutil
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CRUCIBLE = os.path.expanduser("~/code/treadcore/crucible")


def _growth():
    spec = importlib.util.spec_from_file_location("growth", os.path.join(HERE, "growth.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


G = _growth()
load, save = G.load, G.save

W, H, FPS = 1280, 720, 30
SUB = 3                    # frames a step: a step is 0.1 s
BEFORE, AFTER = 10, 5      # steps: 1.0 s before the shot, 0.5 s after
TITLE_S = 0.25
TREC = 22
FONT = "Helvetica"
FONT_B = "Helvetica-Bold"
# treadcore.org's screens are monospace (site.css --mono: ui-monospace, Menlo); Courier where there is none.
MONO = "/System/Library/Fonts/Menlo.ttc" if os.path.exists("/System/Library/Fonts/Menlo.ttc") else "Courier"
MONO_B = ".SF-NS-Mono-Bold" if os.path.exists("/System/Library/Fonts/SFNSMono.ttf") else "Courier-Bold"
# Where a finished film is put for a person to take (Paul, 4 November: "Make sure the video creation is
# scripted such that its auto placed in the output folder"): orrery's output/, or ORRERY_OUTPUT.
OUTPUT = os.environ.get("ORRERY_OUTPUT") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
X264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]

# The look is treadcore's clip renderer's (site.css, night): dark grass, the learner in sky blue with its
# armour bar, the foe in red, shells in orange, a hit as a white ring; the pillboxes neutral sand.
GRASS, GRID, OUT = (27, 41, 30), (34, 52, 37), (12, 18, 14)
WALL, ROCK, ROCK_E = (90, 107, 92), (104, 94, 79), (70, 63, 54)
PB, PB_DEAD, PB_BAR = (216, 194, 122), (60, 58, 51), (120, 200, 110)
ME, FOE, ME_G, FOE_G = (108, 196, 255), (232, 88, 79), (44, 84, 108), (88, 46, 44)
# The corners are treadcore.org's screens (site.css): black glass, phosphor green, amber, a dim green rim.
SCR, SCR_RIM, PHOS, PHOS_DIM, AMBER, SKY, RED_HUD = (7, 8, 7), (29, 138, 44), (51, 242, 77), (29, 138, 44), (255, 191, 77), (115, 199, 255), (242, 51, 38)
HISTORY = 80               # steps of decisions in the spectrogram: 8 s
# Each traced duel's tanks moved up to this many tiles from the one start (crucible --trace-spread): one
# start made 128 duels a dozen games, and the ghosts stood on one another (5 November).
SPREAD = 3.0
SHELL, RING, ZAP = (255, 160, 64), (255, 255, 255), (255, 224, 138)
# The champions of the chapters before, in the followed duel: lavender, apart from both sides' colours.
LAV = (200, 168, 255)
TREES, TREES_E = (20, 64, 30), (14, 46, 22)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


STATE = "montage.json"     # the trailer's own is trailer.json: the Montage page follows the film, not it


def state(q, **kw):
    p = os.path.join(q, "plan", STATE)
    st = load(p, {}) or {}
    st.update(kw)
    st["at"] = now()
    save(p, st)
    return st


def run(cmd, timeout=600, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)


# ---- the chapters ----------------------------------------------------------------------------

def home_of(q):
    c = (load(os.path.join(q, "plan.json"), {}) or {}).get("crucible") or {}
    return ("crucible" + ("-world" if c.get("world") else "") + ("-hybrid" if c.get("hybrid") else "")
            + ("-forest" if c.get("world") and c.get("forest") else "")
            + ("-nav" if c.get("world") and c.get("forest") and c.get("nav") else "")), c


MS = re.compile(r"^(M\d{4})-(.+)-g(\d+)\.bin$")


def milestones(hd):
    out = []
    for f in sorted(glob.glob(os.path.join(hd, "milestones", "M*.bin"))):
        m = MS.match(os.path.basename(f))
        if m:
            out.append({"name": m.group(1), "island": m.group(2), "gen": int(m.group(3)), "path": f,
                        "label": os.path.basename(f)[:-4]})
    return out


def facts_of(hd, island, gen):
    """The segment's row in the home's growth record nearest this island's generation."""
    rows = []
    try:
        with open(os.path.join(hd, "growth.tsv")) as f:
            head = f.readline().rstrip("\n").split("\t")
            for line in f:
                r = dict(zip(head, line.rstrip("\n").split("\t")))
                if r.get("island") == island:
                    rows.append(r)
    except OSError:
        return {}
    best = min(rows, key=lambda r: abs(float(r.get("gen") or 0) - gen), default=None)
    return best or {}


def choose(q, hd, last, most):
    ms = milestones(hd)
    names = [m["label"] for m in ms]
    start = names.index(last) + 1 if last in names else 0
    ch = ms[start:]
    # The newest champion of the island that took the latest milestone closes the film, when it is newer.
    lead = (ch[-1] if ch else ms[-1] if ms else None)
    if lead:
        latest = os.path.join(hd, "latest", lead["island"] + ".bin")
        rec = facts_of(hd, lead["island"], 1e12)
        g = int(float(rec.get("gen") or 0))
        if os.path.exists(latest) and g > lead["gen"]:
            ch.append({"name": "now", "island": lead["island"], "gen": g, "path": latest, "label": "%s-g%d" % (lead["island"], g)})
    if len(ch) > most:
        keep = sorted({round(i * (len(ch) - 1) / (most - 1)) for i in range(most)})
        ch = [ch[i] for i in keep]
    # Opponents: up to six milestones spread over the whole ladder, the newest among them.
    opp = [ms[round(i * (len(ms) - 1) / 5)] for i in range(6)] if len(ms) >= 6 else ms
    seen, opps = set(), []
    for m in opp:
        if m["label"] not in seen:
            seen.add(m["label"])
            opps.append(m)
    for c in ch:
        c["facts"] = facts_of(hd, c["island"], c["gen"])
    return ch, opps, ms


# ---- the trace -------------------------------------------------------------------------------

def gpu_hosts(q):
    reg = load(os.path.join(q, "machines.json"), {}) or {}
    reg = dict(reg.items()) if isinstance(reg, dict) else {x.get("name"): x for x in reg}
    cfg = load(os.path.join(q, "config.json"), {}) or {}
    out = []
    for h in cfg.get("hosts", []):
        if "cuda" in (h.get("caps") or []):
            v = reg.get(h["name"]) or reg.get(h["name"].replace("-cuda", ""))
            t = v.get("target") if isinstance(v, dict) else v
            if t:
                out.append((h["name"].replace("-cuda", ""), t))
    return out


def trace(q, chapters, opps, cfg, duels, seed, want_host, work):
    # The planner's home on every machine is ~/fleet/q-NAME, NAME the queue's folder.
    home = "fleet/q-%s/montage" % os.path.basename(q.rstrip("/"))
    hosts = gpu_hosts(q)
    if want_host:
        hosts = [h for h in hosts if h[0] == want_host] or hosts
    flags = ("HYBRID=1 " if cfg.get("hybrid") else "") + ("WORLD=1 " if cfg.get("world") else "") + ("FOREST=1 " if cfg.get("world") and cfg.get("forest") else "")
    flags += "NAV=1 " if cfg.get("world") and cfg.get("forest") and cfg.get("nav") else ""
    hw = int(cfg.get("h") or (48 if cfg.get("world") else 32))
    flags += "H=%d" % hw if hw != 32 else ""
    if "WORLD=1" not in flags:
        raise RuntimeError("the montage traces world duels: plan.json's crucible.world is off")
    # The game's rules as the islands play them now (the planner's world_flags), so the film is their world.
    rules = ((load(os.path.join(q, "plan", "state.json"), {}) or {}).get("crucible_rules") or {}).get("flags") or ""
    if re.match(r"^[\w.= -]*$", rules):
        flags = (flags.strip() + " " + rules).strip()
    for name, target in hosts:
        r = run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", target, "mkdir -p ~/%s/src ~/%s/in && rm -f ~/%s/in/*.bin" % (home, home, home)], 60)
        if r.returncode != 0:
            continue
        sc = run(["scp", "-q", "-o", "BatchMode=yes", os.path.join(CRUCIBLE, "src", "crucible.cu"), "%s:%s/src/" % (target, home)], 120)
        sc2 = run(["scp", "-q", "-o", "BatchMode=yes", os.path.join(CRUCIBLE, "Makefile"), "%s:%s/" % (target, home)], 120)
        bins = []
        for i, c in enumerate(chapters):
            bins.append(("c%02d.bin" % i, c["path"]))
        for i, o in enumerate(opps):
            bins.append(("o%02d.bin" % i, o["path"]))
        sc3 = run(["scp", "-q", "-o", "BatchMode=yes"] + [p for _, p in bins] + ["%s:%s/in/" % (target, home)], 300) if bins else sc
        # scp keeps the source names; rename on the far side to the chapter order.
        ren = "; ".join("cp %s %s" % (shlex.quote(os.path.basename(p)), b) for b, p in bins)
        cmd = (
            "set -e; cd ~/%(h)s; F='%(f)s'; [ \"$(cat .flags 2>/dev/null)\" = \"$F\" ] || { rm -f crucible; echo \"$F\" > .flags; }; "
            "make -s %(f)s NVCC=${NVCC:-/usr/local/cuda/bin/nvcc} >/dev/null 2>&1 || make %(f)s NVCC=${NVCC:-/usr/local/cuda/bin/nvcc}; "
            "cd in; %(ren)s; cd ..; "
            "./crucible --trace trace.bin --champions %(c)s %(o)s --trace-duels %(d)d --trace-seed %(s)d --trace-spread %(sp)s | grep '^# trace'"
        ) % {"h": home, "f": flags.strip(), "ren": ren, "d": duels, "s": seed, "sp": SPREAD,
             "c": ",".join("in/c%02d.bin" % i for i in range(len(chapters))),
             "o": ("--opponents " + ",".join("in/o%02d.bin" % i for i in range(len(opps)))) if opps else ""}
        r = run(["ssh", "-o", "BatchMode=yes", target, "sh -c %s" % shlex.quote(cmd)], 1800)
        if r.returncode != 0 or sc.returncode or sc2.returncode or sc3.returncode:
            state(q, said="the trace on %s failed: %s" % (name, (r.stderr or r.stdout).strip()[-300:]))
            continue
        out = os.path.join(work, "trace.bin")
        g = run(["scp", "-q", "-o", "BatchMode=yes", "%s:%s/trace.bin" % (target, home), out], 600)
        run(["ssh", "-o", "BatchMode=yes", target, "rm -f ~/%s/trace.bin ~/%s/in/*.bin" % (home, home)], 60)
        if g.returncode == 0:
            return out, name, r.stdout.strip().splitlines()
    raise RuntimeError("no GPU island could run the trace (%s)" % ", ".join(n for n, _ in hosts))


class Trace:
    def __init__(self, path):
        with open(path, "rb") as f:
            b = f.read()
        hdr = struct.unpack_from("<9i", b, 0)
        if hdr[0] != 0x63747231:
            raise RuntimeError("not a crucible trace")
        _, self.version, self.nc, self.nd, self.steps, trec, self.npl, self.npb, _ = hdr
        if trec != TREC:
            raise RuntimeError("a trace of %d floats a step, not %d" % (trec, TREC))
        off = 36
        self.dt, self.arena, self.hp, self.pb_hp, self.gun, self.pb_range = struct.unpack_from("<6f", b, off)
        off += 24
        # Version 2 (crucible, 4 November): the net's shape, and after each champion's steps its mind.
        self.nin = self.nh = self.nout = 0
        if self.version >= 2:
            self.nin, self.nh, self.nout = struct.unpack_from("<3i", b, off)
            off += 12
        # Version 3 (crucible FOREST, 6 November): how many groves and walls, then they follow the pillboxes.
        ngr = nwl = 0
        if self.version >= 3:
            ngr, nwl = struct.unpack_from("<2i", b, off)
            off += 8
        na = 3 * self.npl + 2 * self.npb + 3 * ngr + 4 * nwl
        ar = struct.unpack_from("<%df" % na, b, off)
        off += 4 * na
        p = self.npl
        self.pillars = [(ar[i], ar[p + i], ar[2 * p + i]) for i in range(p)]
        self.boxes = [(ar[3 * p + k], ar[3 * p + self.npb + k]) for k in range(self.npb)]
        o = 3 * p + 2 * self.npb
        self.groves = [(ar[o + g], ar[o + ngr + g], ar[o + 2 * ngr + g]) for g in range(ngr) if ar[o + 2 * ngr + g] > 0]
        o += 3 * ngr
        self.walls = [tuple(ar[o + 4 * k:o + 4 * k + 4]) for k in range(nwl) if ar[o + 4 * k] <= ar[o + 4 * k + 2]]
        self.opp_of = struct.unpack_from("<%di" % self.nd, b, off)
        off += 4 * self.nd
        self.champs = []
        n = self.nd * self.steps * TREC
        for _ in range(self.nc):
            out = struct.unpack_from("<%di" % self.nd, b, off); off += 4 * self.nd
            last = struct.unpack_from("<%di" % self.nd, b, off); off += 4 * self.nd
            fit = struct.unpack_from("<%df" % self.nd, b, off); off += 4 * self.nd
            rec = array.array("f")
            rec.frombytes(b[off:off + 4 * n]); off += 4 * n
            mind = None
            if self.version >= 2:
                m = self.nd * self.steps * (self.nin + self.nout)
                mind = array.array("f")
                mind.frombytes(b[off:off + 4 * m]); off += 4 * m
            self.champs.append({"outcome": out, "lasted": last, "fit": fit, "rec": rec, "mind": mind})

    def at(self, c, d, t):
        """Duel d's step t of champion c, as a tuple of TREC floats; past its end, its last step."""
        ch = self.champs[c]
        t = max(0, min(t, ch["lasted"][d] - 1))
        i = (d * self.steps + t) * TREC
        return ch["rec"][i:i + TREC]

    def mind(self, c, d, t):
        """What champion c's net read in duel d at step t, and what its tank did: (inputs, actions); None
        for a version 1 trace."""
        ch = self.champs[c]
        if ch["mind"] is None:
            return None
        t = max(0, min(t, ch["lasted"][d] - 1))
        k = self.nin + self.nout
        i = (d * self.steps + t) * k
        v = ch["mind"][i:i + k]
        return v[:self.nin], v[self.nin:]


# ---- the mind: the champion's net, recomputed ------------------------------------------------------
#
# Paul, 4 November: "show all the inputs, transform and output as a bunch of 1x1 pixel on three of the
# corners, with generation counter in the 4th corner. if you can show the activation of the circuits and
# animate them ... I like to see a history of decisions like a spectrogram of fire, from a bright square
# display." The trace carries what the net READ and what the tank DID; the two layers between are
# computed here from the champion's own weights by crucible's forward pass (`think`: NIN -> H -> H -> NOUT,
# tanh throughout, row-major), which is exact, so the film shows the net as it thought and not a guess.

def nw_of(nin, h, nout):
    return nin * h + h + h * h + h + h * nout + nout


def widen(src, nin, nh, nout, path):
    """An older champion in this net's shape, as crucible's read_champion widens it (`widen`): its shape
    found from its size among the four kinds (32 or 52 inputs plain, 35 or 55 hybrid), the first 32
    inputs in place, a hybrid's three rules at 32 to 34, the world's twenty at 35; every new weight zero,
    so its answers are what they were; a hybrid's new confidence shut (-0.5). The ladder's first
    milestones are of the old arena's net."""
    for (k_in, k_out) in ((32, 3), (35, 4), (52, 3), (55, 4), (61, 5), (64, 6)):
        for h in range(1, 513):
            n = nw_of(k_in, h, k_out)
            if n == len(src):
                break
            if n > len(src):
                h = None
                break
        else:
            h = None
        if h:
            break
    else:
        raise RuntimeError("%s: %d weights, of no net's shape" % (path, len(src)))
    if k_in > nin or h > nh or k_out > nout:
        raise RuntimeError("%s: a %d-%d-%d-%d net does not shrink into %d-%d-%d-%d" % (path, k_in, h, h, k_out, nin, nh, nh, nout))
    rules = k_in in (35, 55, 64)
    at = 35 if rules else 32
    # crucible's input_to: the world's twenty after the rules, the maze's nine (NAV) after the world's.
    world = 20 if k_in in (52, 55, 61, 64) else 0
    at_world = 35 if nin in (35, 55, 64) else 32

    def to(i):
        if i < 32:
            return i
        if rules and i < 35:
            return i
        if i < at + world:
            return at_world + (i - at)
        return at_world + 20 + (i - at - world)
    out = [0.0] * nw_of(nin, nh, nout)
    sW1, sb1 = 0, k_in * h
    sW2, sb2 = sb1 + h, sb1 + h + h * h
    sW3, sb3 = sb2 + h, sb2 + h + h * k_out
    W1, b1 = 0, nin * nh
    W2, b2 = b1 + nh, b1 + nh + nh * nh
    W3, b3 = b2 + nh, b2 + nh + nh * nout
    for j in range(h):
        for i in range(k_in):
            out[W1 + j * nin + to(i)] = src[sW1 + j * k_in + i]
        out[b1 + j] = src[sb1 + j]
        for i in range(h):
            out[W2 + j * nh + i] = src[sW2 + j * h + i]
        out[b2 + j] = src[sb2 + j]
    for k in range(k_out):
        for i in range(h):
            out[W3 + k * nh + i] = src[sW3 + k * h + i]
        out[b3 + k] = src[sb3 + k]
    if k_out < 4 <= nout:
        out[b3 + 3] = -0.5                     # a hybrid's confidence is output 3; the memory comes after it
    return out


class Net:
    def __init__(self, path, nin, nh, nout):
        with open(path, "rb") as f:
            raw = f.read()
        nw = nin * nh + nh + nh * nh + nh + nh * nout + nout
        if len(raw) % 4:
            raise RuntimeError("%s: %d bytes, not a net" % (path, len(raw)))
        w = struct.unpack("<%df" % (len(raw) // 4), raw)
        if len(w) != nw:
            w = widen(w, nin, nh, nout, path)
        self.nin, self.nh, self.nout = nin, nh, nout
        k = 0
        self.w1 = [w[k + j * nin:k + (j + 1) * nin] for j in range(nh)]; k += nin * nh
        self.b1 = w[k:k + nh]; k += nh
        self.w2 = [w[k + j * nh:k + (j + 1) * nh] for j in range(nh)]; k += nh * nh
        self.b2 = w[k:k + nh]; k += nh
        self.w3 = [w[k + j * nh:k + (j + 1) * nh] for j in range(nout)]; k += nh * nout
        self.b3 = w[k:k + nout]
        self.cache = {}

    def think(self, x, key=None):
        """(h1, h2, y): the two hidden layers and the net's own outputs, before the hybrid's gate."""
        if key is not None and key in self.cache:
            return self.cache[key]
        h1 = [math.tanh(b + sum(a * v for a, v in zip(row, x))) for row, b in zip(self.w1, self.b1)]
        h2 = [math.tanh(b + sum(a * v for a, v in zip(row, h1))) for row, b in zip(self.w2, self.b2)]
        y = [math.tanh(b + sum(a * v for a, v in zip(row, h2))) for row, b in zip(self.w3, self.b3)]
        if key is not None:
            self.cache[key] = (h1, h2, y)
        return h1, h2, y

    def circuits(self, h1, h2, most=28):
        """The strongest currents this step: weight times the signal it carries, h1 -> h2 and h2 -> out."""
        a = sorted(((abs(self.w2[j][i] * h1[i]), 0, i, j, self.w2[j][i] * h1[i]) for j in range(self.nh) for i in range(self.nh)), reverse=True)[:most]
        b = sorted(((abs(self.w3[k][i] * h2[i]), 1, i, k, self.w3[k][i] * h2[i]) for k in range(self.nout) for i in range(self.nh)), reverse=True)[:most // 2]
        return a + b


# ---- the clips -------------------------------------------------------------------------------

def follow(tr, c):
    ch = tr.champs[c]
    won = [d for d in range(tr.nd) if ch["outcome"][d] == 1]
    pool = won or list(range(tr.nd))
    return max(pool, key=lambda d: (ch["fit"][d], -ch["lasted"][d]))


def events(tr, c, d):
    """(priority, step, what) for every moment of duel d worth a clip."""
    ev = []
    for t in range(tr.champs[c]["lasted"][d]):
        s = tr.at(c, d, t)
        fa, pa = int(s[18]), int(s[20])
        if fa == 1 and s[10] <= 0:
            ev.append((5, t, "Kill shot"))
        elif fa == 3:
            ev.append((4, t, "A pillbox taken"))
        elif fa == 2:
            ev.append((3, t, "Pillbox fight: a shell on a pillbox"))
        elif pa > 0:
            ev.append((2, t, "Pillbox fight: the pillbox fires"))
        elif fa == 1:
            ev.append((1, t, "A hit"))
    return ev


def clips_of(ev, lasted, most):
    clips = []
    for pri, t, what in sorted(sorted(ev, key=lambda e: (-e[0], e[1]))[:most], key=lambda e: e[1]):
        a, b = max(0, t - BEFORE), min(lasted - 1 + AFTER, t + AFTER)
        if clips and a <= clips[-1]["to"]:
            clips[-1]["to"] = max(clips[-1]["to"], b)
            if what not in clips[-1]["what"]:
                clips[-1]["what"] += " · " + what
        else:
            clips.append({"from": a, "to": b, "what": what, "at": t})
    return clips


def moments(tr, c, d, most=5):
    """The clips of a chapter, as (duel, clip): the followed duel's kill shot and its pillbox fights --
    and when it fought no pillbox, the pillbox fight of the next best duel the champion won, the camera on
    that duel's learner for that clip. A plain hit fills in only when there is room, once.

    THEN TWO MORE DUELS (Paul, 5 November: "show more demonstration of the battles"): the hardest win --
    the kill shot of the won duel against the strongest opponent, a milestone high on the ladder -- and a
    loss, its last second and a half, where the champion died. A film of wins alone says nothing of
    what a generation still cannot do."""
    ch = tr.champs[c]
    ev = events(tr, c, d)
    pill = [e for e in ev if 2 <= e[0] <= 4]
    keep = [e for e in ev if e[0] == 5] + sorted(pill, key=lambda e: -e[0])[:3]
    if len(keep) < 3:
        keep += [e for e in ev if e[0] == 1][:1]
    out = [(d, k) for k in clips_of(keep, ch["lasted"][d], most)]
    if not pill:
        order = sorted((e for e in range(tr.nd) if e != d), key=lambda e: (ch["outcome"][e] != 1, -ch["fit"][e]))
        for e in order:
            pe = [x for x in events(tr, c, e) if 2 <= x[0] <= 4]
            if pe:
                best = max(pe, key=lambda x: x[0])
                out += [(e, k) for k in clips_of([best], ch["lasted"][e], 1)]
                break
    if not out:
        t = max(0, ch["lasted"][d] - 1)
        out = [(d, k) for k in clips_of([(0, t, "The duel's last moments")], ch["lasted"][d], 1)]
    out = sorted(out, key=lambda x: (x[0] != d, x[1]["from"]))
    used = {e for e, _ in out}
    hard = [e for e in range(tr.nd) if e not in used and ch["outcome"][e] == 1 and tr.opp_of[e] >= 0]
    if hard:
        e = max(hard, key=lambda e: (tr.opp_of[e], ch["fit"][e]))
        kill = [x for x in events(tr, c, e) if x[0] == 5]
        if kill:
            for k in clips_of(kill[:1], ch["lasted"][e], 1):
                k["what"] = "The hardest win: " + k["what"].lower()
                out.append((e, k))
                used.add(e)
    lost = [e for e in range(tr.nd) if e not in used and ch["outcome"][e] == -1]
    if lost:
        e = max(lost, key=lambda e: (ch["lasted"][e], ch["fit"][e]))
        died = next((t for t in range(ch["lasted"][e]) if tr.at(c, e, t)[3] <= 0), ch["lasted"][e] - 1)
        out.append((e, {"from": max(0, died - BEFORE - 5), "to": min(ch["lasted"][e] - 1 + AFTER, died + AFTER),
                        "what": "A loss: where it died", "at": died}))
    return out


# ---- the drawing -----------------------------------------------------------------------------

SPANS = {}


def spans(r):
    if r not in SPANS:
        SPANS[r] = [(dy, int(math.sqrt(max(0, r * r - dy * dy)))) for dy in range(-r, r + 1)]
    return SPANS[r]


class Canvas:
    def __init__(self, base):
        self.b = bytearray(base)

    def hspan(self, x0, x1, y, c):
        if y < 0 or y >= H:
            return
        x0, x1 = max(0, x0), min(W - 1, x1)
        if x1 < x0:
            return
        i = (y * W + x0) * 3
        self.b[i:i + 3 * (x1 - x0 + 1)] = c * (x1 - x0 + 1)

    def rect(self, x, y, w, h, c):
        cb = bytes(c)
        for yy in range(max(0, y), min(H, y + h)):
            self.hspan(x, x + w - 1, yy, cb)

    def disc(self, cx, cy, r, c):
        cb = bytes(c)
        for dy, half in spans(max(1, r)):
            self.hspan(cx - half, cx + half, cy + dy, cb)

    def put(self, x, y, cb):
        if 0 <= x < W and 0 <= y < H:
            i = (y * W + x) * 3
            self.b[i:i + 3] = cb

    def line(self, x0, y0, x1, y1, c, w=1, dots=False):
        """A line `w` pixels wide; dotted, two on and two off, when `dots`."""
        cb = bytes(c)
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err, n = dx + dy, 0
        while n < 4000:
            n += 1
            if dots and (n // 2) % 2:
                pass
            elif w == 1:
                self.put(x0, y0, cb)
            else:
                for yy in range(y0 - w // 2, y0 + (w + 1) // 2):
                    self.hspan(x0 - w // 2, x0 + (w - 1) // 2, yy, cb)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def ring(self, cx, cy, r, c, w=2):
        """A solid ring, two spans a row between its outer and inner circles."""
        cb = bytes(c)
        ri = max(0, r - w)
        for dy in range(-r, r + 1):
            wo = int(math.sqrt(max(0, r * r - dy * dy)))
            if abs(dy) < ri:
                wi = int(math.sqrt(ri * ri - dy * dy))
                self.hspan(cx - wo, cx - wi - 1, cy + dy, cb)
                self.hspan(cx + wi + 1, cx + wo, cy + dy, cb)
            else:
                self.hspan(cx - wo, cx + wo, cy + dy, cb)


def node_hue(i):
    """A node's own colour, which every wire leaving it wears (Paul, 5 November: "try for a way so that
    the wires are different colors so we can see the node connections"): the golden angle round the
    wheel, so neighbours in the grid never share a hue and 48 stay apart. src/montage.rs's `node_hue`
    is the same rule, so the film and orrery's Mind player agree wire for wire."""
    h = math.modf(i * 0.381966011250105)[0] * 6.0
    s, v = 0.62, 1.0
    f = h - int(h)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r, g, b = ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))[min(5, int(h))]
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def lerp(a, b, f):
    return a + (b - a) * f


def alerp(a, b, f):
    d = (b - a + math.pi) % (2 * math.pi) - math.pi
    return a + d * f


def mix(a, b, f):
    return (int(a[0] + (b[0] - a[0]) * f), int(a[1] + (b[1] - a[1]) * f), int(a[2] + (b[2] - a[2]) * f))


def shade(v, signed=True):
    """A number as the screens show one: phosphor green for +, amber for -, black glass at 0, the
    brightness its size (a power under 1, so a small signal still shows)."""
    a = max(-1.0, min(1.0, v))
    if not signed:
        a = max(0.0, a)
    return mix(SCR, PHOS if a >= 0 else AMBER, abs(a) ** 0.6)


# The corners' places (1280 x 720): inputs top left, the transform bottom left, the decisions bottom right,
# the generation top right with the arena's map under it. Each panel's first 30 pixels hold its label.
P_IN = (16, 16, 230, 134)
P_TX = (16, H - 16 - 154, 624, 154)    # wide: the wires between the layers need the room to be told apart
P_DE = (W - 16 - 436, H - 16 - 122, 436, 122)
P_GEN = (W - 16 - 300, 16, 300, 96)
MAP = (W - 16 - 150, 124, 150)
DE_ROWS = ("turn", "speed", "fire", "net's say", "shots")


class Film:
    """The frames of one chapter's clips: the followed duel solid, every other duel a ghost, and in the
    corners the champion's net thinking."""

    def __init__(self, tr, c, d, net=None, tiles=30.0, pull=3.0):
        self.tr, self.c, self.d, self.net, self.pull = tr, c, d, net, pull
        self.scale = W / tiles         # 30 tiles across: the camera's window; a replay comes closer
        self.blank = bytes(OUT) * (W * H)
        self.cam = None
        self.fixed = None              # a still camera, (x, y): the whole of a maze (report/maze_film.py)

    def to_px(self, x, y):
        return int((x - self.cam[0]) * self.scale + W / 2), int((y - self.cam[1]) * self.scale + H / 2)

    def frame(self, t, f, flash, bare=False):
        """Step t and the fraction f of the way to the next; `bare`, the field alone (the title's)."""
        tr, c, d = self.tr, self.c, self.d
        s0, s1 = tr.at(c, d, t), tr.at(c, d, t + 1)
        ax, ay = lerp(s0[0], s1[0], f), lerp(s0[1], s1[1], f)
        # The camera frames the fight: a third of the way toward a living foe within 16 tiles, and up to six
        # tiles past the walls, so a tank by a wall is not pushed under the corners (the first film's kill
        # shots by the north wall stood under the caption, the foe under the generation).
        bx_, by_ = lerp(s0[7], s1[7], f), lerp(s0[8], s1[8], f)
        if s0[10] > 0 and math.hypot(bx_ - ax, by_ - ay) < 16.0:
            ax, ay = ax + (bx_ - ax) / self.pull, ay + (by_ - ay) / self.pull
        want = self.fixed or (min(max(ax, 9.0), tr.arena - 9.0), min(max(ay, 2.4), tr.arena - 2.4))
        self.cam = want if self.cam is None else (lerp(self.cam[0], want[0], 0.25), lerp(self.cam[1], want[1], 0.25))
        cv = Canvas(self.blank)
        S = self.scale
        # The arena: grass inside the walls, a tile grid.
        x0, y0 = self.to_px(0, 0)
        x1, y1 = self.to_px(tr.arena, tr.arena)
        cv.rect(x0, y0, x1 - x0, y1 - y0, GRASS)
        g = bytes(GRID)
        for k in range(0, int(tr.arena) + 1, 2):
            gx, _ = self.to_px(k, 0)
            if 0 <= gx < W:
                for yy in range(max(0, y0), min(H, y1)):
                    cv.put(gx, yy, g)
            _, gy = self.to_px(0, k)
            cv.hspan(max(0, x0), min(W - 1, x1), gy, g)
        cv.rect(x0 - 4, y0 - 4, x1 - x0 + 8, 4, WALL)
        cv.rect(x0 - 4, y1, x1 - x0 + 8, 4, WALL)
        cv.rect(x0 - 4, y0, 4, y1 - y0, WALL)
        cv.rect(x1, y0, 4, y1 - y0, WALL)
        # The trees under everything that stands (crucible FOREST): a grove a disc of dark leaves.
        for (gx, gy, gr) in getattr(tr, "groves", []):
            sx, sy = self.to_px(gx, gy)
            cv.disc(sx, sy, int(gr * S), TREES_E)
            cv.disc(sx, sy, max(1, int((gr - 0.5) * S)), TREES)
        for (px, py, pr) in tr.pillars:
            sx, sy = self.to_px(px, py)
            cv.disc(sx, sy, int(pr * S) + 3, ROCK_E)
            cv.disc(sx, sy, int(pr * S), ROCK)
        for (wx0, wy0, wx1, wy1) in getattr(tr, "walls", []):
            ax, ay = self.to_px(wx0, wy0)
            bx_, by_ = self.to_px(wx1, wy1)
            cv.rect(min(ax, bx_), min(ay, by_), max(2, abs(bx_ - ax)), max(2, abs(by_ - ay)), WALL)
        # The pillboxes, as they stand in the followed duel.
        for k, (bx, by) in enumerate(tr.boxes):
            sx, sy = self.to_px(bx, by)
            hp = s0[14 + k]
            if hp < -500:
                continue           # a camp's castle not yet risen (crucible writes -999 until its stage spawns it)
            half = int(0.55 * S)
            cv.rect(sx - half, sy - half, 2 * half, 2 * half, PB if hp > 0 else PB_DEAD)
            if hp > 0:
                cv.rect(sx - half, sy - half - 10, int(2 * half * hp / tr.pb_hp), 5, PB_BAR)
        # THE CROWD (Paul, 4 November: "a crowd of tanks on the same map because the pill boxes dont move.
        # or even enemy ghost tanks ... a faded overlay with same camera movement to make it align"): every
        # other duel at this same step, the champion and its foe, drawn as tanks faded into the grass. The
        # fade is pre-blended with the field's colour -- the field is the mask -- which costs nothing a
        # pixel. The camera is the followed tank's, so the crowd moves with it. A duel already over keeps its
        # tanks where they ended, fading out over three seconds, so the crowd does not empty as the duels
        # finish (the first film's kill shots stood alone: by then most of the 64 were done). Six seconds since
        # 5 November, when the crowd went to 128 duels a chapter.
        gr = max(4, int(0.62 * S))
        for e in range(tr.nd):
            if e == d:
                continue
            last = tr.champs[c]["lasted"][e]
            over = t - (last - 1)
            fade = 1.0 if over <= 0 else max(0.0, 1.0 - over / 60.0)
            te = min(t, last - 1)
            g0 = tr.at(c, e, te)
            g1 = tr.at(c, e, te + 1) if over <= 0 else g0
            for (k, col) in ((7, FOE), (0, ME)):
                if g0[k + 3] <= 0:
                    continue
                # A tank still standing when its duel ended -- a winner, or both at a draw -- stays in the
                # crowd at half strength where it stood, so the crowd thins by the dead and not by the clock.
                a = 0.42 * (fade if over <= 0 else max(fade, 0.5))
                if a <= 0:
                    continue
                x, y = lerp(g0[k], g1[k], f), lerp(g0[k + 1], g1[k + 1], f)
                sx, sy = self.to_px(x, y)
                if not (-60 < sx < W + 60 and -60 < sy < H + 60):
                    continue
                if k == 0 and over <= 0:
                    for back in (12, 8, 4):
                        p0 = tr.at(c, e, max(0, te - back))
                        px_, py_ = self.to_px(p0[0], p0[1])
                        cv.disc(px_, py_, 2, mix(GRASS, col, a * 0.6))
                edge = mix(GRASS, (6, 9, 7), a * 1.4)
                cv.disc(sx, sy, gr + 2, edge)
                cv.disc(sx, sy, gr, mix(GRASS, col, a))
                hx, hy = self.to_px(x + math.cos(g0[k + 2]) * 1.25, y + math.sin(g0[k + 2]) * 1.25)
                cv.line(sx, sy, hx, hy, edge, w=3)
        # THE GENERATIONS BEFORE, IN THIS SAME DUEL (Paul, 5 November: "can you show more ghosts in the
        # movie"): duel d is one start and one opponent in every chapter, so the champions of the five
        # chapters before this one played it too. Each is drawn where it stood at this step, lavender, the
        # older the fainter, with its track behind it -- the eye sees the newest generation take a line
        # the older ones did not. Only the learner: the foe in their duels answered a different tank.
        for back, a in ((5, 0.16), (4, 0.21), (3, 0.27), (2, 0.35), (1, 0.46)):
            pc = c - back
            if pc < 0:
                continue
            last = tr.champs[pc]["lasted"][d]
            te = min(t, last - 1)
            g0 = tr.at(pc, d, te)
            if g0[3] <= 0:
                continue
            g1 = tr.at(pc, d, te + 1) if t < last - 1 else g0
            x, y = lerp(g0[0], g1[0], f), lerp(g0[1], g1[1], f)
            sx, sy = self.to_px(x, y)
            if not (-60 < sx < W + 60 and -60 < sy < H + 60):
                continue
            for k in range(1, 9):
                p0 = tr.at(pc, d, max(0, te - 3 * k))
                px_, py_ = self.to_px(p0[0], p0[1])
                cv.disc(px_, py_, 2, mix(GRASS, LAV, a * (1.0 - k / 10.0)))
            cv.disc(sx, sy, int(0.8 * S) + 2, mix(GRASS, (6, 9, 7), a * 1.4))
            cv.disc(sx, sy, int(0.8 * S), mix(GRASS, LAV, a))
            hx, hy = self.to_px(x + math.cos(g0[2]) * 1.4, y + math.sin(g0[2]) * 1.4)
            cv.line(sx, sy, hx, hy, mix(GRASS, (6, 9, 7), a * 1.6), w=3)
        # The followed duel: both tanks, their shells, the hits.
        tank_r = int(0.8 * S)
        for (k, col) in ((7, FOE), (0, ME)):
            x, y, a, hp = lerp(s0[k], s1[k], f), lerp(s0[k + 1], s1[k + 1], f), alerp(s0[k + 2], s1[k + 2], f), s0[k + 3]
            sx, sy = self.to_px(x, y)
            if hp <= 0:
                cv.disc(sx, sy, tank_r, (40, 40, 40))
                continue
            cv.disc(sx, sy, tank_r + 2, (10, 14, 12))
            cv.disc(sx, sy, tank_r, col)
            bx, by = self.to_px(x + math.cos(a) * 1.5, y + math.sin(a) * 1.5)
            cv.line(sx, sy, bx, by, (20, 24, 22), w=max(3, int(0.22 * S)))
            cv.rect(sx - tank_r, sy - tank_r - 14, 2 * tank_r, 6, (20, 24, 22))
            cv.rect(sx - tank_r, sy - tank_r - 14, int(2 * tank_r * max(0.0, hp) / tr.hp), 6, (120, 220, 110) if hp > tr.hp * 0.4 else (230, 180, 60))
            if s0[k + 6] > 0:
                ssx, ssy = self.to_px(s0[k + 4], s0[k + 5])
                tx, ty = self.to_px(s1[k + 4], s1[k + 5]) if s1[k + 6] > 0 else (ssx, ssy)
                cx, cy = int(lerp(ssx, tx, f)), int(lerp(ssy, ty, f))
                cv.line(int(lerp(sx, cx, 0.6)), int(lerp(sy, cy, 0.6)), cx, cy, (150, 90, 40), w=2)
                cv.disc(cx, cy, max(3, int(0.18 * S)), SHELL)
        for (kind, x, y, age) in flash:
            sx, sy = self.to_px(x, y)
            if kind == "hit":
                cv.ring(sx, sy, int((0.9 + 0.35 * age) * S), RING, 3)
            elif kind == "kill":
                cv.ring(sx, sy, int((1.0 + 0.6 * age) * S), RING, 4)
                cv.ring(sx, sy, int((0.6 + 0.4 * age) * S), SHELL, 3)
            elif kind.startswith("zap:"):
                tx, ty = (float(v) for v in kind[4:].split(","))
                ex, ey = self.to_px(tx, ty)
                cv.line(sx, sy, ex, ey, ZAP, w=3)
        if bare:
            return cv.b
        if self.net is not None:
            hud_of(self, cv, t)
        if self.fixed:
            return cv.b                # the whole maze is the frame: no generation panel, no small map
        panel(cv, P_GEN)
        # The arena whole, small, top right under the generation: every duel's learner a dot, the camera's
        # window a frame.
        mm, ms = MAP[2], MAP[2] / tr.arena
        mx, my = MAP[0], MAP[1]
        cv.rect(mx - 2, my - 2, mm + 4, mm + 4, (8, 10, 9))
        cv.rect(mx, my, mm, mm, (22, 33, 25))
        for (px, py, pr) in tr.pillars:
            cv.disc(mx + int(px * ms), my + int(py * ms), max(1, int(pr * ms)), ROCK)
        for e in range(tr.nd):
            g0 = tr.at(c, e, t)
            if g0[3] > 0:
                cv.disc(mx + int(g0[0] * ms), my + int(g0[1] * ms), 1, ME if e == d else ME_G)
        tw, th = W / self.scale, H / self.scale
        wx, wy = mx + int((self.cam[0] - tw / 2) * ms), my + int((self.cam[1] - th / 2) * ms)
        for (a, b, w, h) in ((wx, wy, int(tw * ms), 1), (wx, wy + int(th * ms), int(tw * ms), 1), (wx, wy, 1, int(th * ms)), (wx + int(tw * ms), wy, 1, int(th * ms))):
            cv.rect(a, b, w, h, (200, 200, 200))
        return cv.b


def panel(cv, box):
    """A screen of treadcore.org's: black glass in a dim phosphor rim, a scanline every third row."""
    x, y, w, h = box
    cv.rect(x - 2, y - 2, w + 4, h + 4, (4, 5, 4))
    cv.rect(x - 1, y - 1, w + 2, h + 2, SCR_RIM)
    cv.rect(x, y, w, h, SCR)
    line = bytes((11, 14, 11))
    for yy in range(y + 1, y + h, 3):
        cv.hspan(x, x + w - 1, yy, line)


def shot_of(tr, c, d, u):
    """The shots row's colour at step u: red where its shell hit the foe, amber where it struck a
    pillbox, white where a shell left the gun, sky where a pillbox fired at it; None for nothing."""
    s = tr.at(c, d, u)
    fa = int(s[18])
    if fa == 1:
        return RED_HUD
    if fa in (2, 3):
        return AMBER
    if u > 0 and s[6] > tr.at(c, d, u - 1)[6] + 1e-4:
        return (240, 248, 240)
    if int(s[20]) > 0:
        return SKY
    return None


def hud_of(film, cv, t):
    """The three corners of the mind (the fourth, the generation, is a picture laid over by ffmpeg)."""
    tr, c, d, net = film.tr, film.c, film.d, film.net
    mt = tr.mind(c, d, t)
    if mt is None:
        return
    x, act = mt
    h1, h2, y = net.think(x, (d, t))
    # ---- top left: the inputs, 11 a row ----
    panel(cv, P_IN)
    x0, y0 = P_IN[0] + 12, P_IN[1] + 30
    for i, v in enumerate(x):
        cv.rect(x0 + (i % 11) * 19, y0 + (i // 11) * 19, 16, 16, shade(v))
    # ---- bottom left: the transform, h1 -> h2 -> out, the strongest currents lit ----
    panel(cv, P_TX)
    bx, by = P_TX[0] + 12, P_TX[1] + 34
    g1 = [(bx + (i % 8) * 15 + 6, by + (i // 8) * 15 + 6) for i in range(net.nh)]
    g2 = [(bx + 300 + (i % 8) * 15 + 6, by + (i // 8) * 15 + 6) for i in range(net.nh)]
    go = [(bx + 520 + 10, by + k * 28 + 10) for k in range(net.nout)]
    # The strongest 18 currents between the layers and 9 into the decisions: more and the wires are a mat.
    cur = net.circuits(h1, h2, 18)
    top = max((e[0] for e in cur), default=1.0) or 1.0
    # A WIRE WEARS ITS SOURCE NODE'S COLOUR, its brightness the current's size, dotted when it inhibits;
    # each node is framed in its own colour. The wires are drawn OVER the grids and each begins at a dot
    # of its colour on the node it left and ends at a ring on the node it feeds, so a connection is read
    # node to node: under the grids, only the right-hand column's wires could be seen leaving. (Before 5
    # November every wire was green or amber by its sign, and 42 of them read as one green fan.)
    for n_, ((cx, cy), v) in enumerate(zip(g1, h1)):
        cv.rect(cx - 7, cy - 7, 14, 14, node_hue(n_))
        cv.rect(cx - 5, cy - 5, 10, 10, shade(v))
    for n_, ((cx, cy), v) in enumerate(zip(g2, h2)):
        cv.rect(cx - 7, cy - 7, 14, 14, node_hue(n_ + net.nh))
        cv.rect(cx - 5, cy - 5, 10, 10, shade(v))
    for (mag, layer, i, j, v) in reversed(cur):
        a, b = (g1[i], g2[j]) if layer == 0 else (g2[i], go[j])
        k = (mag / top) ** 0.8
        hue = node_hue(i + layer * net.nh)
        cv.line(a[0], a[1], b[0], b[1], mix(SCR, hue, 0.35 + 0.65 * k), w=2 if k > 0.5 else 1, dots=v < 0)
    for (mag, layer, i, j, v) in cur:
        a, b = (g1[i], g2[j]) if layer == 0 else (g2[i], go[j])
        hue = node_hue(i + layer * net.nh)
        cv.disc(a[0], a[1], 3, hue)
        if layer == 0:
            cv.ring(b[0], b[1], 4, hue, 1)
    for (cx, cy), v in zip(go, y):
        cv.rect(cx - 10, cy - 10, 20, 20, shade(v))
    # ---- bottom right: the decisions, a spectrogram of the last eight seconds ----
    panel(cv, P_DE)
    sx0, sy0 = P_DE[0] + 12 + 92, P_DE[1] + 32
    for k in range(HISTORY):
        u = t - (HISTORY - 1) + k
        if u < 0:
            continue
        m = tr.mind(c, d, u)
        if m is None:
            continue
        _, _, yu = net.think(m[0], (d, u))
        au = m[1]
        col = sx0 + k * 4
        vals = (shade(au[0]), shade(au[1], False), shade(au[2]), shade(yu[-1]))
        for r, cl in enumerate(vals):
            cv.rect(col, sy0 + r * 16, 4, 14, cl)
        sc = shot_of(tr, c, d, u)
        if sc:
            cv.rect(col, sy0 + 4 * 16, 4, 14, sc)
    cv.rect(sx0 + HISTORY * 4, sy0 - 2, 1, 5 * 16, PHOS)


def flashes(tr, c, d, t, f):
    """Rings and lines over the followed duel near step t: a hit, a kill, a pillbox firing."""
    out = []
    for back in range(0, 6):
        u = t - back
        if u < 0:
            break
        s = tr.at(c, d, u)
        age = (back + f) / 6.0
        if int(s[18]) == 1:
            out.append(("kill" if s[10] <= 0 else "hit", s[7], s[8], age))
        if int(s[19]) == 1 and back < 3:
            out.append(("hit", s[0], s[1], age))
        if int(s[18]) in (2, 3):
            prev = tr.at(c, d, u - 1)
            for k, (bx, by) in enumerate(tr.boxes):
                if s[14 + k] < prev[14 + k]:
                    out.append(("kill" if s[14 + k] <= 0 else "hit", bx, by, age))
        if back < 2:
            for k, (bx, by) in enumerate(tr.boxes):
                if s[14 + k] <= 0:
                    continue
                for (n, tx, ty) in ((int(s[20]), s[0], s[1]), (int(s[21]), s[7], s[8])):
                    if n > 0 and math.hypot(tx - bx, ty - by) <= tr.pb_range + 0.5:
                        out.append(("zap:%f,%f" % (tx, ty), bx, by, age))
    return out


def render_clip(tr, ci, cd, clip, what, net, opps, labels, gen, ttl, out, preview, sub_n=SUB, tiles=30.0, mind=True, hud=True, poster=False):
    """One clip of chapter ci's duel cd to the segment `out`: the field drawn a frame at a time into
    ffmpeg, the corners' labels, the generation and the caption laid over, and with `ttl` the generation's
    0.25 s title over the upper right. hud=False is a replay: no corners, closer. Returns (frames written,
    the mind's steps, the poster frame when `poster` asks for one)."""
    c = tr.champs[ci]
    film = Film(tr, ci, cd, net if hud else None, tiles, 3.0 if hud else 2.0)
    cap = out[:-4] + "-cap.png"
    o = tr.opp_of[cd]
    vs = ("a " + ("scripted tank", "Raider", "Castle", "Expander", "Timid", "Lurker")[min(5, -1 - o)]) if o < 0 else opps[o]["name"] if o < len(opps) else "a milestone"
    # 21 point: at 22 the longest captions (a replay's, a hardest win's) ran under the generation's panel.
    label_png(cap, "%s  ·  duel %d of %d against %s, %s" % (what, cd + 1, tr.nd, vs, "won" if c["outcome"][cd] == 1 else "lost" if c["outcome"][cd] == -1 else "drawn"), 21, font=FONT)
    ttl = ttl if hud else None
    inputs = (["-i", labels] if hud else []) + ["-i", gen, "-i", cap] + (["-i", ttl] if ttl else [])
    # The caption centred in the gap between the inputs' panel and the generation's, not on the frame:
    # centred on the frame, a long one ran under the generation (film 4).
    mid = (P_IN[0] + P_IN[2] + P_GEN[0]) // 2
    filt = ("[0][1]overlay=0:0[a];[a][2]overlay=%d:%d[b];[b][3]overlay=%d-w/2:16" % (P_GEN[0], P_GEN[1], mid)
            + ("[c];[c][4]overlay=W-w-24:24:enable='lt(t,%.2f)'" % TITLE_S if ttl else "")) if hud else \
        ("[0][1]overlay=%d:%d[b];[b][2]overlay=%d-w/2:16" % (P_GEN[0], P_GEN[1], mid))
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-"]
                         + inputs + ["-filter_complex", filt] + X264 + [out], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    nfr = 0
    steps = []
    poster_ppm = None
    for t in range(clip["from"], clip["to"] + 1):
        if mind and net is not None:
            sc = shot_of(tr, ci, cd, t)
            steps.append(pack_mind(net, tr, ci, cd, t, {RED_HUD: "hit", AMBER: "pillbox", SKY: "pillbox fired", (240, 248, 240): "shot"}.get(sc, "") if sc else ""))
        for sub in range(sub_n):
            fr = film.frame(t, sub / sub_n, flashes(tr, ci, cd, t, sub / sub_n))
            p.stdin.write(fr)
            nfr += 1
            if nfr % 15 == 1:
                with open(preview + ".part", "wb") as pf:
                    pf.write(small(fr))
                os.replace(preview + ".part", preview)
            if poster and t == clip.get("at", clip["from"]) and sub == 0:
                poster_ppm = small(fr)
    p.stdin.close()
    err = p.stderr.read().decode(errors="replace")
    if p.wait() != 0:
        raise RuntimeError("ffmpeg: %s" % err.strip()[-300:])
    return nfr, steps, poster_ppm


def small(frame):
    """A quarter-size copy (320 x 180) for the Montage page's preview, as a PPM."""
    out = bytearray(320 * 180 * 3)
    for y in range(180):
        row = frame[(y * 4) * W * 3:(y * 4 + 1) * W * 3]
        o = y * 320 * 3
        out[o:o + 960:3] = row[0::12]
        out[o + 1:o + 960:3] = row[1::12]
        out[o + 2:o + 960:3] = row[2::12]
    return b"P6\n320 180\n255\n" + bytes(out)


# ---- text, slides, orrery's pictures ---------------------------------------------------------

def magick(args, timeout=120):
    r = run(["magick"] + args, timeout)
    if r.returncode != 0:
        raise RuntimeError("magick: %s" % r.stderr.strip()[-300:])


def text_png(path, lines, size=(W, H), bg="none"):
    """Lines of (text, points, colour, font) stacked from the top left of a transparent card."""
    args = ["-size", "%dx%d" % size, "xc:%s" % bg]
    y = 0
    for (t, pt, col, font, x) in lines:
        y += int(pt * 1.25)
        args += ["-font", font, "-pointsize", str(pt), "-fill", col, "-annotate", "+%d+%d" % (x, y), t]
    magick(args + [path])


def label_png(path, text, pt, fg="white", bg="#000000b0", pad=14, font=FONT_B):
    magick(["-background", bg, "-fill", fg, "-font", font, "-pointsize", str(pt), "label:%s" % text,
            "-bordercolor", bg, "-border", str(pad), path])


def orrery_frame(work, status, name, view, env, size="1280x720"):
    exe = os.path.join(ROOT, "target", "release", "orrery")
    if not os.path.exists(exe):
        return None
    out = os.path.join(work, name + ".ppm")
    e = dict(os.environ, **env)
    r = run([exe, "--frame", out, "--frame-view", view, "--frame-state", status, "--frame-size", size], 120, env=e)
    if r.returncode != 0 or not os.path.exists(out):
        return None
    png = os.path.join(work, name + ".png")
    magick([out, png])
    return png


def card(work, name, bg_png, title, sub, facts, pt=32, step=48):
    """A slide: a picture (orrery's) on the left or behind, a title in 48 point, facts in 32 (smaller when
    there are more than fit)."""
    out = os.path.join(work, name + ".png")
    args = ["-size", "%dx%d" % (W, H), "xc:#0b100d"]
    if bg_png:
        args += ["(", bg_png, "-resize", "720x450", ")", "-geometry", "+30+160", "-composite"]
    args += ["-font", FONT_B, "-pointsize", "48", "-fill", "white", "-annotate", "+40+80", title]
    if sub:
        args += ["-font", FONT, "-pointsize", "32", "-fill", "#9fd4ff", "-annotate", "+40+130", sub]
    x = 780 if bg_png else 60
    y = 200
    for f in facts:
        args += ["-font", MONO if pt < 32 else FONT, "-pointsize", str(pt), "-fill", "#e8e8e8", "-annotate", "+%d+%d" % (x, y), f]
        y += step
    magick(args + [out])
    return out


def still(png, seconds, out):
    r = run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", png, "-t", "%.2f" % seconds, "-vf", "scale=%d:%d,format=yuv420p" % (W, H)] + X264 + [out], 300)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: %s" % r.stderr.strip()[-300:])
    return out


def num(v, k=2):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "-"
    return ("%%.%df" % k) % x


# ---- the corners' words, the generation, the title sequence ------------------------------------------

def hud_labels(work):
    """The corners' labels, once a film: a transparent frame laid over every clip."""
    out = os.path.join(work, "hud-labels.png")
    args = ["-size", "%dx%d" % (W, H), "xc:none", "-font", MONO, "-pointsize", "13", "-fill", "#9effa8"]
    args += ["-annotate", "+%d+%d" % (P_IN[0] + 12, P_IN[1] + 20), "INPUTS  the 55 numbers it senses"]
    args += ["-annotate", "+%d+%d" % (P_TX[0] + 12, P_TX[1] + 20), "TRANSFORM  55 > 48 > 48 > 4: a wire wears its node's colour, dotted inhibits"]
    args += ["-annotate", "+%d+%d" % (P_DE[0] + 12, P_DE[1] + 20), "DECISIONS  the last 8 s, newest at the right"]
    bx, by = P_TX[0] + 12, P_TX[1] + 34
    for k, word in enumerate(("turn", "speed", "fire", "gate")):
        args += ["-annotate", "+%d+%d" % (bx + 548, by + k * 28 + 15), word]
    for r, word in enumerate(DE_ROWS):
        args += ["-annotate", "+%d+%d" % (P_DE[0] + 12, P_DE[1] + 32 + r * 16 + 11), word]
    magick(args + [out])
    return out


def gen_png(work, ci, ch, of):
    """The fourth corner: the generation, large, in phosphor."""
    out = os.path.join(work, "gen-%02d.png" % ci)
    name = ch["name"] if ch["name"] != "now" else "the newest"
    magick(["-size", "%dx%d" % (P_GEN[2], P_GEN[3]), "xc:none",
            "-font", MONO, "-pointsize", "13", "-fill", "#9effa8", "-annotate", "+12+20", "GENERATION",
            "-font", MONO_B, "-pointsize", "40", "-fill", "#33f24d", "-annotate", "+12+62", format(ch["gen"], ","),
            "-font", MONO, "-pointsize", "13", "-fill", "#ffbf4d", "-annotate", "+12+86",
            "%s  chapter %d of %d  %s" % (name, ci + 1, of, ch["island"].replace("-cuda", "")), out])
    return out


def title_sequence(work, n, chapters, tr, home, field, seg_out):
    """The opening in treadcore.org's look (index.html, site.css): the battlefield behind a veil and its
    scanlines, a brushed-metal plate with four screws, the name etched, an eyebrow label, a phosphor
    screen that types what the film holds, and the newswire along the foot. 3.6 s, faded in."""
    first, lastc = chapters[0], chapters[-1]
    gens = "generations %s to %s" % (format(first["gen"], ","), format(lastc["gen"], ","))
    return plate(work, field, "CRUCIBLE  ·  MONTAGE %d  ·  %s" % (n, home.upper().replace("CRUCIBLE-", "").replace("-", " ")),
                 "> %s, %s" % (home.replace("crucible-", ""), gens), "  the net's inputs, layers and decisions in the corners",
                 [("#33f24d", 24, "%d chapters" % len(chapters)), ("#ffbf4d", 190, "%d duels in one world each" % tr.nd),
                  ("#73c7ff", 520, "the camera follows the best win"), ("#f23326", 880, "every other duel a ghost")], seg_out)


def plate(work, field, eyebrow, line1, line2, wire, seg_out):
    """The plate itself, any film's: `field` behind it, `eyebrow` etched over the name, `line1` and `line2`
    typed on its screen, `wire` the newswire's (colour, x, words). Leaves t-35.png, the plate whole."""
    base = os.path.join(work, "t-base.png")
    px, py, pw, ph = 190, 120, 900, 360
    magick(["-size", "1x3", "xc:none", "-fill", "#00000030", "-draw", "point 0,0", "-write", "mpr:sl", "+delete",
            field, "-modulate", "65,85", "-fill", "#020403", "-colorize", "30",
            "(", "-size", "%dx%d" % (W, H), "radial-gradient:none-#020403c0", ")", "-composite",
            "(", "-size", "%dx%d" % (W, H), "tile:mpr:sl", ")", "-composite",
            # the plate: metal.rs's gradient, a brush's streaks, a rounded edge
            "(", "-size", "%dx%d" % (pw, ph), "gradient:#ececec-#8a8a8a",
            "(", "-size", "%dx%d" % (pw, ph), "xc:gray50", "-attenuate", "0.5", "+noise", "Uniform", "-motion-blur", "0x60+0", "-colorspace", "gray", ")",
            "-compose", "blend", "-define", "compose:args=22", "-composite",
            "(", "-size", "%dx%d" % (pw, ph), "xc:none", "-fill", "white", "-draw", "roundrectangle 0,0 %d,%d 14,14" % (pw - 1, ph - 1), ")",
            "-compose", "dstin", "-composite", "-compose", "over",
            "-fill", "none", "-stroke", "#2b2c2e", "-strokewidth", "2", "-draw", "roundrectangle 1,1 %d,%d 14,14" % (pw - 2, ph - 2),
            "-stroke", "#ffffffd0", "-strokewidth", "1", "-draw", "line 14,3 %d,3" % (pw - 15),
            ")", "-geometry", "+%d+%d" % (px, py), "-composite",
            # four screws
            "-stroke", "#555", "-strokewidth", "1", "-fill", "#b8b8b8",
            "-draw", "circle %d,%d %d,%d" % (px + 22, py + 22, px + 29, py + 22),
            "-draw", "circle %d,%d %d,%d" % (px + pw - 22, py + 22, px + pw - 15, py + 22),
            "-draw", "circle %d,%d %d,%d" % (px + 22, py + ph - 22, px + 29, py + ph - 22),
            "-draw", "circle %d,%d %d,%d" % (px + pw - 22, py + ph - 22, px + pw - 15, py + ph - 22),
            "-stroke", "#444", "-strokewidth", "2",
            "-draw", "line %d,%d %d,%d" % (px + 18, py + 18, px + 26, py + 26),
            "-draw", "line %d,%d %d,%d" % (px + pw - 26, py + 18, px + pw - 18, py + 26),
            "-draw", "line %d,%d %d,%d" % (px + 18, py + ph - 26, px + 26, py + ph - 18),
            "-draw", "line %d,%d %d,%d" % (px + pw - 26, py + ph - 26, px + pw - 18, py + ph - 18),
            "-stroke", "none",
            # the eyebrow, the etched name (a highlight a pixel under it), the meta line
            "-font", MONO_B, "-pointsize", "17", "-kerning", "3", "-fill", "#3c3e40",
            "-annotate", "+%d+%d" % (px + 60, py + 62), eyebrow,
            "-kerning", "0", "-font", FONT_B, "-pointsize", "104",
            "-fill", "#ffffffd8", "-annotate", "+%d+%d" % (px + 56, py + 166), "Treadcore",
            "-fill", "#121214", "-annotate", "+%d+%d" % (px + 56, py + 165), "Treadcore",
            "-font", MONO, "-pointsize", "15", "-fill", "#3c3e40",
            "-annotate", "+%d+%d" % (px + 60, py + ph - 30), "MIT  ·  treadcore.org  ·  orrery  ·  %s" % time.strftime("%d %B %Y"),
            # the screen the words type onto
            "-fill", "#070807", "-stroke", "#2b2c2e", "-strokewidth", "2",
            "-draw", "roundrectangle %d,%d %d,%d 8,8" % (px + 50, py + 196, px + pw - 50, py + 290), "-stroke", "none",
            # the newswire
            "-fill", "#070807", "-draw", "rectangle 0,%d %d,%d" % (H - 58, W, H - 22),
            "-font", MONO, "-pointsize", "16"]
           + [a for col, x, words in wire for a in ("-fill", col, "-annotate", "+%d+%d" % (x, H - 34), words)]
           + [base])
    frames = 36
    for i in range(frames):
        k = int((len(line1) + len(line2)) * min(1.0, i / 22.0))
        a, b = line1[:k], line2[:max(0, k - len(line1))]
        cur = "_" if (i // 3) % 2 == 0 else " "
        magick([base, "-font", MONO, "-pointsize", "22", "-fill", "#33f24d",
                "-annotate", "+%d+%d" % (px + 70, py + 234), a + (cur if k < len(line1) else ""),
                "-fill", "#1d8a2c", "-annotate", "+%d+%d" % (px + 70, py + 270), b + (cur if k >= len(line1) else ""),
                os.path.join(work, "t-%02d.png" % i)])
    r = run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "10", "-i", os.path.join(work, "t-%02d.png"),
             "-vf", "fps=%d,fade=in:0:12,format=yuv420p" % FPS] + X264 + [seg_out], 300)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg title: %s" % r.stderr.strip()[-300:])
    return seg_out, frames / 10.0


def how_to_read(work, frame_png):
    """A card that names the four corners on a real frame of the film."""
    out = os.path.join(work, "how.png")
    magick(["-size", "%dx%d" % (W, H), "xc:#0b100d", "(", frame_png, "-resize", "760x428", ")", "-geometry", "+30+150", "-composite",
            "-font", FONT_B, "-pointsize", "44", "-fill", "white", "-annotate", "+40+80", "How to read the film",
            "-font", FONT, "-pointsize", "26", "-fill", "#9fd4ff", "-annotate", "+40+124", "The champion's net, thinking, in the four corners",
            "-font", FONT, "-pointsize", "24", "-fill", "#e8e8e8",
            "-annotate", "+820+190", "Top left: what it senses,",
            "-annotate", "+820+220", "55 numbers a step.",
            "-annotate", "+820+275", "Bottom left: the transform,",
            "-annotate", "+820+305", "two layers of 48; a wire",
            "-annotate", "+820+335", "wears its node's colour.",
            "-annotate", "+820+390", "Bottom right: its decisions,",
            "-annotate", "+820+420", "8 s of turn, speed, fire.",
            "-annotate", "+820+475", "Top right: the generation,",
            "-annotate", "+820+505", "and the arena's map.",
            "-fill", "#33f24d", "-annotate", "+820+560", "Green +, amber -,",
            "-annotate", "+820+590", "black zero.",
            "-fill", "#9fd4ff", "-annotate", "+40+628", "Faded tanks: the other duels at the same moment, in the same world.",
            "-fill", "#c8a8ff", "-annotate", "+40+664", "Lavender: the champions of the chapters before, in this same duel.",
            out])
    return out


def stamp(sec):
    sec = int(sec)
    return "%d:%02d" % (sec // 60, sec % 60)


def pack_mind(net, tr, c, d, t, h):
    """One step of the mind for orrery's Montage page: rounded, with its strongest currents."""
    x, act = tr.mind(c, d, t)
    h1, h2, y = net.think(x, (d, t))
    r = lambda v: [round(float(a), 2) for a in v]
    cur = net.circuits(h1, h2, 16)
    return {"t": t, "x": r(x), "h1": r(h1), "h2": r(h2), "y": r(y), "a": r(act), "s": h,
            "c": [[e[1], e[2], e[3], round(e[4], 2)] for e in cur]}


# ---- the line: the game's brain, generation by generation ------------------------------------
#
# Paul, 5 November, the evening r0201 put w11352 on the line: "describe the success story of each
# generation move ... Add this to the montage. Show the chain, show the arrows in the flowchart. In fact.
# show more investigation." The crucible chapters are the GPU islands' nets; the game's own brain moves
# by the line -- a trial read on 55 seeds, read on, read on 400 seeds no search has seen, held to its
# families, its gauntlet and 168 tests, committed -- and none of that was in the film. Now each of the
# last generations is told as the planner recorded it: every job of its chain on the machine that ran
# it, an arrow from each to the job it followed, every try of its promotion with the fault that stopped
# it and the commit that mended it, the dials it moved in the words of treadcore's weights table, and
# where its commit stands: on the line, or on main.

LINE_GENS = 3
# The Flow's colours (src/line.rs `colour`), so a stage is one colour in orrery and in the film.
STAGE_HEX = {"first": "#2a78d6", "read": "#1baf7a", "held": "#eb6834", "families": "#eda100", "gauntlet": "#c9952f",
             "promote": "#eda100", "line": "#6250d6", "main": "#33f24d"}
STAGE_WORD = {"first": "First read", "read": "Read on", "held": "Held-out read", "families": "Families",
              "gauntlet": "Gauntlet", "promote": "Tests, commit", "line": "The line"}
COLS = ["first", "read", "held", "families", "gauntlet", "promote", "line"]


def planner(q):
    s = importlib.util.spec_from_file_location("orrery_plan", os.path.join(HERE, "plans", "treadcore.py"))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m, m.Plan(q)


def epoch(s):
    try:
        return time.mktime(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None


def took_words(sec):
    return "%d s" % sec if sec < 90 else "%.1f min" % (sec / 60.0) if sec < 5400 else "%.1f h" % (sec / 3600.0)


def dial_words(tc, ref="origin/main"):
    """Each dial's description, as treadcore's weights table gives it at main: `Name "dial" default, "words";`."""
    out = {}
    for f in ("weights.rs", "tactics.rs"):
        r = run(["git", "-C", tc, "show", "%s:source/treadcore-brain/src/%s" % (ref, f)], 60)
        for m in re.finditer(r'^\s*\w+\s+"(\w+)"\s+[^,]+,\s+"(.*)";\s*$', r.stdout, re.M):
            out.setdefault(m.group(1), m.group(2).replace('\\"', '"'))
    return out


def line_story(q, most=LINE_GENS):
    """The last `most` generations that were committed, each as its chain of jobs, its tries, its dials
    and its evidence; the line and main as they stand; the proof between them. Everything is read from
    the queue's records and git: nothing here is the film's own opinion."""
    m, p = planner(q)
    runs = [r for r in p.runs() if r["kind"] == "promote"]
    st_of = {r["id"]: p.rstate(r["id"]) for r in runs}
    won = [r for r in runs if st_of[r["id"]].get("status") in ("approved", "self-modified")]
    pick = won[-most:]
    if not pick:
        return None
    cand_of = lambda r: st_of[r["id"]].get("candidate") or (r.get("params") or {}).get("candidate", "")
    t_min = min(epoch(r.get("asked", "")) or time.time() for r in pick) - 86400
    jobs = {}
    for sub in ("done", "failed", "failed-retried"):
        for f in glob.glob(os.path.join(q, sub, "*.json")):
            try:
                if os.path.getmtime(f) < t_min:
                    continue
                j = load(f)
            except OSError:
                continue
            if j and j.get("id") and j["id"] not in jobs:
                j["_ok"] = sub == "done"
                jobs[j["id"]] = j
    starts = {}
    lo = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t_min))
    with open(os.path.join(q, "events.jsonl")) as f:
        for line in f:
            if '"started"' in line and line[7:26] >= lo:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                starts[e["job"]] = e["t"]
    chains = {}
    for i, j in jobs.items():
        chains.setdefault(m.Plan.chain_of(i, j.get("title", "")), []).append(j)
    tc = p.tc
    remote_main = run(["git", "-C", tc, "rev-parse", "origin/main"]).stdout.strip()
    on = lambda sha, ref: bool(sha) and run(["git", "-C", tc, "merge-base", "--is-ancestor", sha, ref]).returncode == 0
    words = dial_words(tc)
    gens = []
    for r in pick:
        rid, st = r["id"], st_of[r["id"]]
        cand = cand_of(r)
        trial = cand.split("/", 1)[-1]
        nodes, dirs = [], []
        for j in sorted(chains.get(trial, []), key=lambda x: starts.get(x["id"], x.get("ended", ""))):
            i, title = j["id"], j.get("title", "")
            k = p.stage_of(i, title)
            if i.startswith("gx"):
                k = "gauntlet"
            if k not in COLS:
                continue
            a, b = epoch(starts.get(i, "")), epoch(j.get("ended", ""))
            if b is None:
                continue
            a = a or b - float(j.get("seconds") or 0)
            n = {"id": i, "stage": k, "host": j.get("host", ""), "a": a, "b": b, "ok": j["_ok"], "title": title}
            ds = glob.glob(os.path.join(q, "results", i, p.home, "out", i, "*", ""))
            one = p.pool(ds) if ds else None
            if one:
                d, se, ns = one["every"]
                n.update(d=d, se=se, n=ns)
                if k in ("first", "read"):
                    dirs += ds
                    al = p.pool(dirs)
                    if al and al["every"][1]:
                        n["z"] = al["every"][0] / al["every"][1]
                        n["pooled"] = al["every"]
                elif se:
                    n["z"] = d / se
            mr = re.match(r"read on (\d+)", title)
            n["group"] = "read %s" % mr.group(1) if mr else "held" if k == "held" else k if k in ("first", "gauntlet") else i
            nodes.append(n)
        # The tries: every promotion of this candidate up to this one, the ones that died at the writer
        # (no job) among them.
        tries = []
        for x in runs:
            if cand_of(x) != cand:
                continue
            s_ = st_of[x["id"]]
            ok = s_.get("status") in ("approved", "self-modified")
            tries.append({"run": x["id"], "asked": x.get("asked", ""), "ok": ok, "why": s_.get("why", ""), "job": s_.get("job"), "by": x.get("by", "")})
            if not s_.get("job"):
                t_ = epoch(x.get("asked", "")) or 0
                nodes.append({"id": x["id"], "stage": "promote", "host": "orrery", "a": t_, "b": t_ + 1, "ok": False, "group": x["id"],
                              "title": "the writer", "fault": s_.get("why") or ""})
            if x["id"] == rid:
                break
        for n in nodes:
            if n["stage"] == "promote" and not n["ok"] and "fault" not in n:
                why = next((t["why"] for t in tries if t["job"] == n["id"]), "")
                mm = re.search(r"\(([^)]*)\)", why)
                n["fault"] = why
        sha = st.get("commit", "")
        appr = epoch(st.get("approved", "")) or (max(n["b"] for n in nodes) if nodes else 0)
        where = "main" if on(sha, remote_main) else "the line" if on(sha, p.LINE) else "replayed"
        nodes.append({"id": sha[:7], "stage": "line", "host": "every machine", "a": appr, "b": appr + 1, "ok": True, "group": "line",
                      "title": "on " + where})
        nodes.sort(key=lambda n: n["a"])
        # Each job's arrow: from the newest job that had ended when it began, not one of its own siblings.
        for k_, n in enumerate(nodes):
            before = [x for x in nodes[:k_] if x["b"] <= n["a"] + 3 and x["group"] != n["group"]]
            n["prev"] = nodes.index(max(before, key=lambda x: x["b"])) if before else None
        out = os.path.join(q, "results", st.get("job") or "-", p.home, "out", st.get("job") or "-")
        tests = families = gauntlet = ""
        try:
            tests = next((l for l in open(os.path.join(out, "tests.txt")) if l.startswith("test result")), "").strip()
            fl = [l for l in open(os.path.join(out, "families.txt")) if l.startswith("family")]
            families = "%d of %d families hold" % (sum(1 for l in fl if l.rstrip().endswith(")") and "holds" in l), len(fl))
        except OSError:
            pass
        try:
            gauntlet = next((l.strip() for l in open(os.path.join(q, "logs", st.get("job", "") + ".log")) if l.startswith("gauntlet")), "")
        except OSError:
            pass
        mt = re.search(r"(\d+) passed", tests)
        held = None
        for n in nodes:
            if n["stage"] == "held":
                hid = n["id"].split("-p")[0]
                pd = p.piece_dir(hid)
                one = p.pool([pd]) if pd else None
                if one:
                    held = one["every"]
                elif "d" in n and n.get("n", 0) >= 400:
                    held = (n["d"], n["se"], n["n"])
        dials = []
        for c in st.get("changed", []):
            mm = re.match(r"(\w+) (\S+) -> (\S+)", c)
            if mm:
                dials.append({"name": mm.group(1), "old": mm.group(2), "new": mm.group(3), "words": words.get(mm.group(1), "")})
        # The fixes: commits in orrery and treadcore that name a failed try or the candidate, made between the
        # first failure and an hour after the generation landed (a fix is often committed after it was live).
        fixes = []
        failed = [t for t in tries if not t["ok"]]
        if failed:
            since, upto = failed[0]["asked"], time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(appr + 3600))
            seen = set()
            for repo, name in ((ROOT, "orrery"), (tc, "treadcore")):
                for key in [t["run"] for t in failed] + [trial]:
                    g = run(["git", "-C", repo, "log", "--all", "--since", since, "--until", upto, "--grep", key, "--format=%h\t%ad\t%s", "--date=format:%H:%M"], 60)
                    for l in g.stdout.splitlines():
                        h, at, subj = (l.split("\t") + ["", ""])[:3]
                        if h not in seen and not subj.startswith("promote "):
                            seen.add(h)
                            fixes.append({"repo": name, "sha": h, "at": at, "subject": subj})
        subj = run(["git", "-C", tc, "log", "-1", "--format=%s", sha], 30).stdout.strip() if sha else ""
        hosts = sorted({n["host"] for n in nodes if n["stage"] not in ("line",) and n["host"] not in ("orrery", "4 machines")})
        gens.append({"run": rid, "trial": trial, "note": "", "dials": dials, "nodes": nodes, "tries": tries, "fixes": fixes,
                     "commit": sha, "subject": subj, "where": where, "approved": st.get("approved", ""),
                     "census": (st.get("evidence") or {}).get("census"), "held": held, "tests": int(mt.group(1)) if mt else None,
                     "families": families, "gauntlet": gauntlet, "hosts": hosts, "by": r.get("by", ""),
                     "first_at": min((n["a"] for n in nodes), default=appr), "detail": st.get("detail", "")})
    line = p.state.get("local_line") or {}
    pf = p.state.get("proof") or {}
    main_gen = next((r["id"] for r in reversed(runs) if st_of[r["id"]].get("status") == "approved"), None)
    return {"gens": gens, "main": remote_main[:7], "main_gen": main_gen, "main_cand": cand_of(next(r for r in runs if r["id"] == main_gen)) if main_gen else "",
            "main_changed": st_of[main_gen].get("changed", []) if main_gen else [], "line": (line.get("commit") or "")[:7],
            "line_runs": line.get("promotions", []), "proof": pf.get("last"), "proof_pool_head": ((pf.get("pooled") or {}).get("head") or "")[:7],
            "proof_next": (pf.get("last_at") or 0) + p.PROOF_EVERY_MIN * 60, "held_z": p.HELD_Z,
            "bar": (p.state.get("difficulty") or {}).get("held_z")}


def short_num(v):
    """A dial's value as a person writes it: 99.2672 as 99.27, 0.0249411 as 0.0249, 24 as 24."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return str(v)
    if x == int(x):
        return "%d" % x
    return ("%.4f" % x).rstrip("0") if abs(x) < 1 else ("%.2f" % x).rstrip("0").rstrip(".")


def clock_of(t):
    return time.strftime("%H:%M", time.localtime(t))


def wrap(text, n):
    out, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > n:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return out + ([cur] if cur else [])


def chain_layout(g):
    """Each node's box: its stage's column, stacked in the order the jobs began."""
    x0, gap, top, bottom = 24, 10, 196, 590
    cw = (W - 2 * x0 - (len(COLS) - 1) * gap) // len(COLS)
    per = {}
    for n in g["nodes"]:
        per.setdefault(n["stage"], []).append(n)
    for k, ns in per.items():
        step = min(84, (bottom - top) // max(1, len(ns)))
        for r_, n in enumerate(ns):
            col = COLS.index(k)
            n["box"] = (x0 + col * (cw + gap), top + r_ * step, cw, min(72, step - 8))
    return x0, cw, gap


def fault_words(why):
    """A failure's own words, short enough for a box: the job's wrapper and the log's address taken off."""
    w = re.sub(r"^the promotion job failed \((.*)\): see logs/.*$", r"\1", why or "")
    w = re.sub(r"^fatal: ", "", w)
    w = re.sub(r" \(got .*$| \(nothing written\)$", "", w)
    return w


def node_lines(n):
    """A box's words: the job, its machine and time, then what it read or how it failed. 22 a line."""
    lines = [n["id"], "%s · %s" % (n["host"][:12], took_words(max(1, n["b"] - n["a"]))) if n["stage"] != "line" else "at " + clock_of(n["a"])]
    if n["stage"] == "line":
        lines = [n["id"], n["title"] + " at " + clock_of(n["a"]), "built everywhere"]
    elif "fault" in n:
        lines += wrap(fault_words(n["fault"]), 22)[:2]
    elif "d" in n:
        lines.append("%d seeds %+.2f±%.2f" % (n["n"], n["d"], n["se"]))
        if "z" in n:
            lines.append(("pooled " if n["stage"] in ("first", "read") else "") + "z %+.2f" % n["z"])
    elif n["stage"] == "families":
        lines.append("every family holds" if n["ok"] else "failed")
    elif n["stage"] == "gauntlet":
        lines.append("the floors read" if n["ok"] else "failed")
    elif n["stage"] == "promote":
        lines.append("committed" if n["ok"] else "failed")
    return lines


def arrow_mvg(a, b, col):
    """An MVG bezier from box a to box b with its head, and the dark line under it."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if bx > ax + aw:
        s, e, d = (ax + aw + 1, ay + ah // 2), (bx - 3, by + bh // 2), (1, 0)
    elif bx + bw < ax:
        s, e, d = (ax - 1, ay + ah // 2), (bx + bw + 3, by + bh // 2), (-1, 0)
    elif by > ay:
        s, e, d = (ax + aw // 2, ay + ah + 1), (bx + bw // 2, by - 3), (0, 1)
    else:
        s, e, d = (ax + aw // 2, ay - 1), (bx + bw // 2, by + bh + 3), (0, -1)
    k = max(20, abs(e[0] - s[0]) // 2 if d[1] == 0 else abs(e[1] - s[1]) // 2)
    c1, c2 = (s[0] + d[0] * k, s[1] + d[1] * k), (e[0] - d[0] * k, e[1] - d[1] * k)
    path = "bezier %d,%d %d,%d %d,%d %d,%d" % (s + c1 + c2 + e)
    hx, hy = e
    px, py = -d[1], d[0]
    head = "polygon %d,%d %d,%d %d,%d" % (hx + d[0] * 2, hy + d[1] * 2, hx - d[0] * 11 + px * 6, hy - d[1] * 11 + py * 6, hx - d[0] * 11 - px * 6, hy - d[1] * 11 - py * 6)
    return ["-fill", "none", "-stroke", "#050705", "-strokewidth", "6", "-draw", path,
            "-stroke", col, "-strokewidth", "2", "-draw", path, "-stroke", "none", "-fill", col, "-draw", head]


def chain_frames(work, gi, g, of, story, step=0.5, hold=5.0):
    """The chain revealed a job at a time: frame k has the first k jobs and the arrows into them; the
    last has the story under it. Each job shows `step` seconds before the next, the whole `hold`. Returns
    [(png, seconds)]."""
    x0, cw, gap = chain_layout(g)
    nodes = g["nodes"]
    span = (max(n["b"] for n in nodes) - g["first_at"]) / 60.0
    dials = " · ".join("%s %s → %s" % (d["name"], short_num(d["old"]), short_num(d["new"])) for d in g["dials"])
    base = ["-size", "%dx%d" % (W, H), "xc:#0b100d",
            "-font", FONT_B, "-pointsize", "38", "-fill", "white", "-annotate", "+24+60", "Generation %s · %s" % (g["run"], g["trial"]),
            "-font", MONO, "-pointsize", "16", "-fill", "#9fd4ff", "-annotate", "+24+96", dials,
            "-font", FONT, "-pointsize", "19", "-fill", "#ffbf4d", "-annotate", "+24+126",
            "%s, %s to %s, %s · %d jobs on %d machines · generation %d of the %d told" % (
                time.strftime("%-d %b", time.localtime(g["first_at"])), clock_of(g["first_at"]), clock_of(max(n["b"] for n in nodes)),
                took_words(span * 60), sum(1 for n in nodes if n["stage"] != "line"), len(g["hosts"]), gi + 1, of)]
    held = g.get("held")
    for k in COLS:
        x = x0 + COLS.index(k) * (cw + gap)
        base += ["-font", FONT_B, "-pointsize", "17", "-fill", STAGE_HEX[k], "-annotate", "+%d+168" % x, STAGE_WORD[k]]
        sub = ""
        if k == "held" and held:
            sub = "%+.2f±%.2f, z %.2f" % (held[0], held[1], held[0] / held[1] if held[1] else 0)
        elif k == "read":
            pooled = [n for n in nodes if n["stage"] in ("first", "read") and "pooled" in n]
            if pooled:
                sub = "%d seeds, z %.2f" % (pooled[-1]["pooled"][2], pooled[-1]["z"])
        elif k == "promote" and g.get("tests"):
            sub = "%d tests pass" % g["tests"]
        if sub:
            base += ["-font", MONO, "-pointsize", "12", "-fill", "#8fa396", "-annotate", "+%d+185" % x, sub]
    out = []
    for k in range(1, len(nodes) + 2):
        shown = nodes[:min(k, len(nodes))]
        args = list(base)
        for n in shown:
            if n["prev"] is not None:
                a = nodes[n["prev"]]
                col = "#f23326" if (a["stage"] == "promote" and not a["ok"]) else "#ffbf4d"
                args += arrow_mvg(a["box"], n["box"], col)
        for n in shown:
            x, y, w_, h_ = n["box"]
            bad = not n["ok"]
            stroke = "#f23326" if bad else STAGE_HEX[n["stage"]]
            newest = n is shown[-1] and k <= len(nodes)
            args += ["-fill", "#2a1210" if bad else "#121a15", "-stroke", "#ffffff" if newest else stroke, "-strokewidth", "3" if newest else "2",
                     "-draw", "roundrectangle %d,%d %d,%d 6,6" % (x, y, x + w_, y + h_), "-stroke", "none"]
            for li, t in enumerate(node_lines(n)[:4]):
                if 15 + li * 15 > h_:
                    break
                args += ["-font", MONO_B if li == 0 else MONO, "-pointsize", "13" if li == 0 else "11",
                         "-fill", "white" if li == 0 else ("#ff8f80" if bad and li >= 2 else "#cfe0d4"), "-annotate", "+%d+%d" % (x + 8, y + 16 + li * 15), t]
        if g["where"] != "main" and k > len(nodes):
            x, y, w_, h_ = nodes[-1]["box"]
            y2 = y + h_ + 40
            args += ["-fill", "none", "-stroke", "#33f24d", "-strokewidth", "2", "-draw", "stroke-dasharray 7 5 roundrectangle %d,%d %d,%d 6,6" % (x, y2, x + w_, y2 + 56), "-stroke", "none",
                     "-font", MONO_B, "-pointsize", "13", "-fill", "#33f24d", "-annotate", "+%d+%d" % (x + 8, y2 + 18), "main",
                     "-font", MONO, "-pointsize", "12", "-fill", "#9fd49f", "-annotate", "+%d+%d" % (x + 8, y2 + 34), "after the proof",
                     "-annotate", "+%d+%d" % (x + 8, y2 + 49), "past z %.1f" % story["held_z"]]
            args += arrow_mvg(nodes[-1]["box"], (x, y2, w_, 56), "#33f24d")
        if k > len(nodes):
            args += ["-fill", "#0f1712", "-draw", "rectangle 0,608 %d,%d" % (W, H)]
            ev = []
            if g.get("census"):
                ev.append("census %+.2f ± %.2f" % tuple(g["census"][:2]))
            if held:
                ev.append("held out %+.2f ± %.2f on %d unseen seeds (z %.2f)" % (held[0], held[1], held[2], held[0] / held[1] if held[1] else 0))
            if g.get("families"):
                ev.append(g["families"])
            if g.get("gauntlet"):
                ev.append(g["gauntlet"].replace("gauntlet: holds", "the gauntlet holds"))
            tries = g["tries"]
            said = "committed %s by %s, %s" % (g["commit"][:7], "orrery's auto mode" if g["by"] == "auto" else g["by"] or "a person",
                                               "on main" if g["where"] == "main" else "on the line, waiting for the proof against main")
            if len(tries) > 1:
                said = "%d tries: %s; %s" % (len(tries), ", ".join("%s %s" % (t["run"], "landed" if t["ok"] else "failed") for t in tries), said)
            args += ["-font", FONT, "-pointsize", "19", "-fill", "#33f24d", "-annotate", "+36+640", " · ".join(ev),
                     "-fill", "#e8e8e8", "-annotate", "+36+672", said,
                     "-font", FONT, "-pointsize", "15", "-fill", "#8fa396", "-annotate", "+36+700",
                     "Each arrow runs from the job a link followed: the newest of the chain to have ended when it began. Red: a try that failed, and the one after it."]
        png = os.path.join(work, "chain-%d-%02d.png" % (gi, k))
        magick(args + [png])
        out.append((png, step if k <= len(nodes) else hold))
    return out


def frames_to(pairs, out):
    """Stills with their own durations, one segment. CUT AT THEIR SUM: the concat demuxer drops the last
    still's duration unless the still is listed again, and listed again it plays that duration twice --
    each chain's last card held 10 s, not 5, and every chapter mark after the first chain ran early (film 5's
    added to 112 s of 127). Measured 6 November on ffmpeg 9.0.2: 0.5 + 2.0 asked, 1.03 s without the
    repeat, 4.53 s with it, 2.50 cut."""
    lst = out + ".txt"
    total = sum(s for _, s in pairs)
    with open(lst, "w") as f:
        for png, sec in pairs:
            f.write("file '%s'\nduration %.2f\n" % (png, sec))
        f.write("file '%s'\n" % pairs[-1][0])
    r = run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-vf", "fps=%d,scale=%d:%d,format=yuv420p" % (FPS, W, H)]
            + X264 + ["-t", "%.3f" % total, out], 300)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg chain: %s" % r.stderr.strip()[-300:])
    return out, total


def text_card(work, name, title, sub, rows):
    """A card of rows, each (text, colour, point size, font); long rows wrapped."""
    args = ["-size", "%dx%d" % (W, H), "xc:#0b100d", "-font", FONT_B, "-pointsize", "40", "-fill", "white", "-annotate", "+40+70", title]
    if sub:
        args += ["-font", FONT, "-pointsize", "24", "-fill", "#9fd4ff", "-annotate", "+40+112", sub]
    y = 160
    for text, col, pt, font in rows:
        if text is None:
            y += pt // 2
            continue
        chars = int(1190 / (pt * (0.62 if font in (MONO, MONO_B) else 0.5)))
        for l in wrap(text, chars) or [""]:
            args += ["-font", font, "-pointsize", str(pt), "-fill", col, "-annotate", "+40+%d" % y, l]
            y += int(pt * 1.3)
        if y > H - 20:
            break
    out = os.path.join(work, name + ".png")
    magick(args + [out])
    return out


def dial_card(work, gi, g):
    rows = []
    for d in g["dials"]:
        rows.append(("%s   %s  →  %s" % (d["name"], d["old"], d["new"]), "#33f24d", 26, MONO_B))
        rows.append((d["words"] or "(no words in the weights table)", "#e8e8e8", 19, FONT))
        rows.append((None, None, 30, None))
    rows.append(("%s  %s" % (g["commit"][:7], g["subject"][:150]), "#8fa396", 15, MONO))
    return text_card(work, "dials-%d" % gi, "What %s moved" % g["run"], "%s, in the words of treadcore's weights table at main" % g["trial"], rows)


def tries_card(work, gi, g):
    rows = []
    for t in g["tries"]:
        col = "#33f24d" if t["ok"] else "#ff6b5e"
        rows.append(("%s  asked %s by %s  %s" % (t["run"], t["asked"][11:16], t["by"] or "?", "LANDED" if t["ok"] else "FAILED"), col, 24, MONO_B))
        if t["why"]:
            rows.append((t["why"], "#e8e8e8", 19, FONT))
        rows.append((None, None, 30, None))
    if g["fixes"]:
        rows.append(("What mended it, found by the run and the trial named in each commit:", "#9fd4ff", 20, FONT))
        for f in sorted(g["fixes"], key=lambda f: f["at"])[:4]:
            rows.append(("%s %s %s  %s" % (f["repo"], f["sha"], f["at"], f["subject"]), "#e8e8e8", 16, MONO))
    # What the failures were, said from their own words: a failure at the tests, a family or the gauntlet
    # is the candidate's numbers judged; anything else stopped before they were.
    judged = [t for t in g["tries"] if not t["ok"] and re.search(r"tests failed|family|gauntlet", t["why"])]
    sub = ("every failure stopped before its numbers were judged" if not judged else
           "%d of the failures were its own numbers judged" % len(judged))
    if all(t["by"] == "auto" for t in g["tries"]):
        sub += "; every try asked by the auto mode"
    return text_card(work, "tries-%d" % gi, "The investigation: %s took %d tries" % (g["trial"], len(g["tries"])), sub, rows)


def act_card(work, story):
    rows = []
    for g in story["gens"]:
        h = g.get("held")
        rows.append(("%s  %s  %s  held %s  %d %s  %s on %s" % (
            g["run"], g["trial"], g["approved"][11:16], "%+.2f±%.2f" % (h[0], h[1]) if h else "-", len(g["tries"]),
            "try " if len(g["tries"]) == 1 else "tries", g["commit"][:7], g["where"]), "#e8e8e8", 22, MONO))
        rows.append(("    " + "; ".join("%s %s → %s" % (d["name"], d["old"], d["new"]) for d in g["dials"]), "#8fa396", 16, MONO))
        rows.append((None, None, 26, None))
    rows.append(("main is %s, its last generation %s (%s: %s)" % (story["main"], story["main_gen"] or "-", story["main_cand"].split("/")[-1],
                                                                  "; ".join(story["main_changed"])), "#33f24d", 20, MONO))
    return text_card(work, "line-act", "The line: the game's brain, a generation at a time",
                     "the last %d generations, each from a question to a commit" % len(story["gens"]), rows)


def proof_card(work, story):
    pf = story.get("proof") or {}
    gens = story["gens"]
    on_line = [g for g in gens if g["where"] != "main"]
    rows = [("Committed: yes. %s on the line, head %s." % (", ".join(story["line_runs"]) or "nothing", story["line"] or "-"), "#33f24d", 24, FONT),
            ("The line is a branch on the coordinator (orrery/accepted). Every machine builds it, plays it and reads new trials against it.", "#e8e8e8", 19, FONT),
            (None, None, 14, None),
            ("Pushed to main: %s. Main is %s; its last generation is %s." % ("not yet" if on_line else "yes", story["main"], story["main_gen"] or "-"),
             "#ffbf4d" if on_line else "#33f24d", 24, FONT),
            ("Main takes the line by a proof: main's values read as a trial against the line, 800 seeds an hour, pooled while neither moves; "
             "the line past main at z %.1f, and no map given up past the trade rule." % story["held_z"], "#e8e8e8", 19, FONT),
            (None, None, 14, None)]
    if pf:
        rows.append(("The last proof read the line at %s: %+.2f ± %.2f over %s seeds, z %.2f of %.1f." % (
            pf.get("head", "?"), pf.get("d", 0), pf.get("se", 0), format(pf.get("seeds", 0), ","), pf.get("z", 0), story["held_z"]), "#e8e8e8", 22, FONT))
        if story["line"] and pf.get("head") and not story["line"].startswith(pf["head"][:7]):
            rows.append(("A new generation on the line starts the pool again: the next proof reads %s, due about %s." % (story["line"], clock_of(story["proof_next"])),
                         "#9fd4ff", 20, FONT))
    return text_card(work, "proof", "Committed, not yet on main" if on_line else "On main", "where the commits stand, %s" % time.strftime("%-d %B %H:%M"), rows)


def line_act(q, work, add, seg_path, status, most=LINE_GENS):
    """The act, segment by segment, through `add`. Returns the story, or None when nothing was committed."""
    story = line_story(q, most)
    if not story:
        return None
    pj = os.path.join(q, "plan", "pipeline.json")
    pipe = load(pj, {}) or {}
    add(still(act_card(work, story), 6.0, seg_path()), 6.0, "The line: the game's brain")
    newest = story["gens"][-1]["trial"]
    if any(t.get("trial") == newest for t in pipe.get("traces") or []):
        png = orrery_frame(work, pj, "flow-road", "pipeline", {"ORRERY_FRAME_PAGE": "1", "ORRERY_FRAME_TRACE": newest})
        if png:
            add(still(captioned(work, png, "The flowchart, %s's road lit: each stage it walked, numbered, and the one it waits at" % newest), 4.0, seg_path()), 4.0)
    chained = {j[5] for l in ((pipe.get("timeline") or {}).get("lanes") or []) for j in (l.get("jobs") or []) if len(j) > 5}
    for gi, g in enumerate(story["gens"]):
        seg, sec = frames_to(chain_frames(work, gi, g, len(story["gens"]), story), seg_path())
        add(seg, sec, "%s %s: its chain" % (g["run"], g["trial"]))
        add(still(dial_card(work, gi, g), 6.0, seg_path()), 6.0)
        if len(g["tries"]) > 1:
            add(still(tries_card(work, gi, g), 8.0, seg_path()), 8.0, "The investigation: %s's %d tries" % (g["trial"], len(g["tries"])))
        if g["trial"] in chained:
            png = orrery_frame(work, pj, "tl-%s" % g["trial"], "pipeline", {"ORRERY_FRAME_PAGE": "2", "ORRERY_FRAME_CHAIN": g["trial"]})
            if png:
                add(still(captioned(work, png, "The Timeline follows %s: each job on its machine, an arrow from the one it followed" % g["trial"]), 4.0, seg_path()), 4.0)
    for name, env, cap in (("tl-day", {"ORRERY_FRAME_PAGE": "2", "ORRERY_FRAME_ZOOM": "day"}, "The day: a green line each generation, the bins coloured by stage"),
                           ("lineup", {"ORRERY_FRAME_PAGE": "6", "ORRERY_FRAME_LINEUP": "trials"}, "The Lineup: every trial's chain, how far it went, how it ended"),
                           ("parade", {"ORRERY_FRAME_PAGE": "7"}, "The Hit Parade: the day's counts")):
        png = orrery_frame(work, pj, name, "pipeline", env)
        if png:
            add(still(captioned(work, png, cap), 3.0, seg_path()), 3.0)
    add(still(proof_card(work, story), 8.0, seg_path()), 8.0, "Committed, and where it stands")
    return story


def captioned(work, png, cap):
    lab = os.path.join(work, os.path.basename(png)[:-4] + "-cap.png")
    label_png(lab, cap, 26)
    comp = os.path.join(work, os.path.basename(png)[:-4] + "-card.png")
    magick([png, lab, "-gravity", "south", "-geometry", "+0+20", "-composite", comp])
    return comp


def line_only(q, out):
    """`montage.py QUEUE line OUT.mp4`: the line's act alone, for a look before a whole film."""
    work = os.path.join(q, "plan", "montage-line-work")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    segs, marks, clock, n = [], [], [0.0], [0]

    def seg_path():
        n[0] += 1
        return os.path.join(work, "seg-%04d.mp4" % n[0])

    def add(path, seconds, mark=None):
        if mark:
            marks.append((clock[0], mark))
        segs.append(path)
        clock[0] += seconds
    story = line_act(q, work, add, seg_path, None)
    if not story:
        print("nothing committed to tell")
        return 1
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as f:
        for s in segs:
            f.write("file '%s'\n" % s)
    r = run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", out], 600)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-300:])
    save(out + ".json", story)
    for a, m_ in marks:
        print(stamp(a), m_)
    print("%s: %.0f s; frames in %s" % (out, clock[0], work))
    return 0


# ---- the film --------------------------------------------------------------------------------

def make(q, most=12, duels=128, host=None, seed=7, since=None):
    lock = os.path.join(q, "plan", "montage.lock")
    if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 3 * 3600:
        print("a montage is being made (plan/montage.json says where it is)")
        return 1
    open(lock, "w").close()
    work = os.path.join(q, "plan", "montage-work")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    try:
        return _make(q, most, duels, host, seed, work, since)
    except Exception as e:
        state(q, state="failed", said=str(e)[:400])
        print("montage failed: %s" % e)
        return 1
    finally:
        shutil.rmtree(work, ignore_errors=True)
        try:
            os.remove(lock)
        except OSError:
            pass


def _make(q, most, duels, host, seed, work, since=None):
    t0 = time.time()
    adir = os.path.join(q, "archive", "montages")
    os.makedirs(adir, exist_ok=True)
    idx = load(os.path.join(adir, "index.json"), {"montages": []}) or {"montages": []}
    last = idx["montages"][-1]["last"] if idx["montages"] else None
    # --since start (or a milestone's label): the whole ladder again, or from there, whatever was filmed.
    if since:
        last = None if since == "start" else since
    homename, cfg = home_of(q)
    hd = os.path.join(q, homename)
    state(q, state="choosing", progress=0.0, said="the generations since %s" % (last or "the start"))
    chapters, opps, ladder = choose(q, hd, last, most)
    if not chapters:
        state(q, state="done", progress=1.0, said="no generation since montage %d (%s): nothing to film" % (len(idx["montages"]), last))
        print("nothing new since %s" % last)
        return 0
    state(q, state="tracing", progress=0.05, said="%d chapters, %d duels each, on a GPU island" % (len(chapters), duels))
    tpath, tracer, lines = trace(q, chapters, opps, cfg, duels, seed, host, work)
    tr = Trace(tpath)
    n = len(idx["montages"]) + 1
    status = os.path.join(work, "status.json")
    with open(status, "w") as f:
        r = run([sys.executable, "-I", os.path.join(HERE, "plans", "treadcore-view.py"), "--queue", q], 300)
        f.write(r.stdout)
    segs = []
    seg_n = [0]
    clock = [0.0]
    marks = []

    def seg_path():
        seg_n[0] += 1
        return os.path.join(work, "seg-%04d.mp4" % seg_n[0])

    def add(path, seconds, mark=None):
        if mark:
            marks.append((clock[0], mark))
        segs.append(path)
        clock[0] += seconds

    # ---- the opening: the title sequence, how to read it, then orrery's flowchart, history, terrain, spectrum ----
    state(q, state="rendering", progress=0.1, said="the opening")
    nets = [Net(c["path"], tr.nin, tr.nh, tr.nout) if tr.version >= 2 else None for c in chapters]
    d0 = follow(tr, 0)
    m0 = moments(tr, 0, d0)
    t_show = m0[0][1].get("at", m0[0][1]["from"]) if m0 else 0
    f0 = Film(tr, 0, m0[0][0] if m0 else d0, nets[0])
    field = os.path.join(work, "field.ppm")
    with open(field, "wb") as f:
        f.write(b"P6\n%d %d\n255\n" % (W, H) + bytes(Film(tr, 0, d0).frame(0, 0.0, [], bare=True)))
    tseg, tsec = title_sequence(work, n, chapters, tr, homename, field, seg_path())
    add(tseg, tsec, "Title")
    title = os.path.join(work, "t-%02d.png" % 35)
    labels = hud_labels(work)
    if nets[0] is not None:
        shown = os.path.join(work, "shown.ppm")
        with open(shown, "wb") as f:
            f.write(b"P6\n%d %d\n255\n" % (W, H) + bytes(f0.frame(t_show, 0.0, flashes(tr, 0, f0.d, t_show, 0.0))))
        shown_png = os.path.join(work, "shown.png")
        magick([shown, labels, "-composite", shown_png])
        add(still(how_to_read(work, shown_png), 6.0, seg_path()), 6.0, "How to read the film")
    story = [("pipeline", "pipeline", {"ORRERY_FRAME_PAGE": "1"}, "The flowchart: where a generation goes"),
             ("growth", "results", {"ORRERY_FRAME_PAGE": "14"}, "The history: every island's generations (Growth)"),
             ("terrain", "results", {"ORRERY_FRAME_PAGE": "8", "ORRERY_FRAME_TAB": "1"}, "The terrain: the census reads as a landscape over two dials"),
             ("spectrum", "results", {"ORRERY_FRAME_PAGE": "8", "ORRERY_FRAME_TAB": "2"}, "The spectrogram: each champion's middle layer, oldest at the left")]
    for name, view, env, cap in story:
        doc = os.path.join(q, "plan", "pipeline.json") if view == "pipeline" else status
        png = orrery_frame(work, doc, name, view, env)
        if not png:
            continue
        lab = os.path.join(work, name + "-cap.png")
        label_png(lab, cap, 32)
        comp = os.path.join(work, name + "-card.png")
        magick([png, lab, "-gravity", "south", "-geometry", "+0+24", "-composite", comp])
        add(still(comp, 2.5, seg_path()), 2.5, cap.split(":")[0] if name == "pipeline" else None)
    # ---- the line: the game's brain, the last generations committed, each from its question to its commit ----
    state(q, state="rendering", progress=0.12, said="the line's generations")
    try:
        story = line_act(q, work, add, seg_path, status)
    except Exception as e:  # the act is the film's news, not its spine: a fault in it says so and the film goes on
        story = None
        state(q, said="the line's act was left out: %s" % str(e)[:200])
    # ---- the chapters ----
    summary = []
    mind_doc = []
    poster_ppm = None
    preview = os.path.join(q, "plan", "montage-preview.ppm")
    frames_total = 0
    for ci, ch in enumerate(chapters):
        state(q, state="rendering", progress=0.15 + 0.75 * ci / len(chapters), chapter=ci + 1, of=len(chapters),
              said="chapter %d of %d: %s, generation %d" % (ci + 1, len(chapters), ch["label"], ch["gen"]))
        c = tr.champs[ci]
        w_, l_, d_ = sum(1 for o in c["outcome"] if o == 1), sum(1 for o in c["outcome"] if o == -1), sum(1 for o in c["outcome"] if o == 0)
        d = follow(tr, ci)
        clips = moments(tr, ci, d)
        fx = ch.get("facts") or {}
        dims = (fx.get("dims") or "").split("-")
        facts = ["%s, gen %s" % (ch["island"].replace("-cuda", ""), format(ch["gen"], ",")),
                 "%d won · %d lost · %d drawn" % (w_, l_, d_),
                 "best %s · mean %s" % (num(fx.get("best")), num(fx.get("mean"))),
                 "yardstick %s" % num(fx.get("yard")),
                 "exam %s" % num(fx.get("exam")),
                 "hits a shot %s" % num(fx.get("hit_rate")),
                 "pillbox damage %s" % num(fx.get("pill_taken")),
                 "stable rank %s of %s" % (num(fx.get("srank1"), 1), dims[1] if len(dims) > 1 else "-")]
        gpng = orrery_frame(work, status, "g%02d" % ci, "results", {"ORRERY_FRAME_PAGE": "14", "ORRERY_FRAME_GEN": str(ch["gen"]), "ORRERY_FRAME_ISLAND": ch["island"]})
        slide = card(work, "chapter-%02d" % ci, gpng, "Generation %s" % format(ch["gen"], ","),
                     "%s · %s" % (ch["name"] if ch["name"] != "now" else "the newest champion", ch["island"].replace("-cuda", "")), facts)
        add(still(slide, 3.0, seg_path()), 3.0, "Generation %s (%s)" % (format(ch["gen"], ","), ch["name"] if ch["name"] != "now" else "the newest"))
        ttl = os.path.join(work, "ttl-%02d.png" % ci)
        label_png(ttl, "Generation %s · %s" % (format(ch["gen"], ","), ch["name"] if ch["name"] != "now" else "now"), 48)
        gen = gen_png(work, ci, ch, len(chapters))
        minds = []
        replayed = False

        def shoot(k, cd, clip, what, sub_n=SUB, tiles=30.0, mind=True, hud=True):
            """One clip through render_clip, on the chapter's first clip the generation's title over the
            upper right; its frames go into the film, its mind to the page's. Returns the frames written."""
            nonlocal poster_ppm
            out = seg_path()
            nfr, steps, pp = render_clip(tr, ci, cd, clip, what, nets[ci], opps, labels, gen, ttl if k == 0 and hud else None, out, preview,
                                         sub_n, tiles, mind, hud, poster=k == 0 and mind)
            poster_ppm = pp or poster_ppm
            add(out, nfr / float(FPS))
            if mind:
                minds.append({"what": what, "duel": cd, "from": clip["from"], "to": clip["to"], "steps": steps})
            return nfr

        for k, (cd, clip) in enumerate(clips):
            clip["duel"] = cd
            nfr = shoot(k, cd, clip, clip["what"])
            frames_total += nfr
            clip["frames"] = nfr
            # THE KILL SHOT AGAIN, at half speed and closer (Paul, 5 November: "show more demonstration of
            # the battles"): the second before it and the moment after, 20 tiles across instead of 30, so
            # the shell's flight and the turn that aimed it can be watched. Once a chapter, the first kill.
            if not replayed and "Kill shot" in clip["what"] and "hardest" not in clip["what"]:
                replayed = True
                at = clip.get("at", clip["from"])
                rc = {"from": max(0, at - 8), "to": min(c["lasted"][cd] - 1 + 3, at + 3), "at": at}
                frames_total += shoot(k + 100, cd, rc, "Replay at half speed: the kill shot", sub_n=2 * SUB, tiles=20.0, mind=False, hud=False)
        mind_doc.append({"chapter": ci + 1, "name": ch["name"], "label": ch["label"], "gen": ch["gen"], "island": ch["island"], "clips": minds})
        summary.append({"chapter": ci + 1, "name": ch["name"], "label": ch["label"], "island": ch["island"], "gen": ch["gen"],
                        "won": w_, "lost": l_, "drawn": d_, "followed": d, "followed_vs": tr.opp_of[d],
                        "followed_fitness": round(c["fit"][d], 3), "clips": [k for _, k in clips], "facts": fx})
    # ---- the last card: every chapter's wins in a column ----
    rows = ["%-10s gen %9s   %2d won  %2d lost  %2d drawn" % (s["name"] if s["name"] != "now" else "now", format(s["gen"], ","), s["won"], s["lost"], s["drawn"]) for s in summary]
    # Every chapter on the last card: twelve rows fit at 26 point.
    end = card(work, "end", None, "%d duels from one start, every chapter" % tr.nd,
               "the same opponents each time: %d milestones, and sparring partners of five styles" % len(opps), rows,
               *((26, 38) if len(rows) > 10 else (32, 48)))
    add(still(end, 5.0, seg_path()), 5.0, "Every chapter's duels")
    # ---- one film ----
    state(q, state="encoding", progress=0.93, said="joining %d pieces" % len(segs))
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as f:
        for s in segs:
            f.write("file '%s'\n" % s.replace("'", "'\\''"))
    md = os.path.join(adir, "%04d" % n)
    os.makedirs(md, exist_ok=True)
    mp4 = os.path.join(md, "montage.mp4")
    r = run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", mp4], 900)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg concat: %s" % r.stderr.strip()[-300:])
    shutil.copy(slide if summary else title, os.path.join(md, "poster.png"))
    if poster_ppm:
        with open(os.path.join(md, "poster.ppm"), "wb") as f:
            f.write(poster_ppm)
    dur = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4], 60).stdout.strip()
    doc = {"n": n, "at": now(), "home": homename, "since": last, "last": chapters[-1]["label"] if chapters[-1]["name"] != "now" else (chapters[-2]["label"] if len(chapters) > 1 else last),
           "chapters": summary, "opponents": [o["label"] for o in opps], "duels": tr.nd, "seed": seed, "traced_on": tracer, "trace": lines,
           "seconds": float(dur or 0), "frames": frames_total, "mp4": os.path.relpath(mp4, q), "bytes": os.path.getsize(mp4),
           "made_in": round(time.time() - t0), "spread": SPREAD, "line": story}
    # Its last milestone is the next montage's start; a chapter "now" is not a milestone and is filmed again.
    if chapters[-1]["name"] == "now":
        doc["last"] = next((c["label"] for c in reversed(chapters) if c["name"] != "now"), last)
    # The mind for orrery's Montage page: the steps of every clip, as the corners drew them.
    if mind_doc:
        save(os.path.join(md, "mind.json"), {"n": n, "inputs": tr.nin, "hidden": tr.nh, "outputs": tr.nout,
                                             "rows": list(DE_ROWS), "chapters": mind_doc})
        doc["mind"] = os.path.relpath(os.path.join(md, "mind.json"), q)
    doc["marks"] = [[round(a, 2), m] for a, m in marks]
    # THE OUTPUT FOLDER: the film and a description with its chapter marks, ready to upload.
    try:
        os.makedirs(OUTPUT, exist_ok=True)
        base = os.path.join(OUTPUT, "treadcore-montage-%04d" % n)
        shutil.copy2(mp4, base + ".mp4")
        with open(base + ".txt", "w") as f:
            f.write("Treadcore: crucible montage %d, %s\n\n" % (n, "generations %s to %s" % (format(chapters[0]["gen"], ","), format(chapters[-1]["gen"], ","))))
            if story:
                f.write("First, the game's own brain: the last %d generations committed by orrery's line, each followed from "
                        "its first read to its commit, every job on the machine that ran it and an arrow from each to the one it "
                        "followed.\n" % len(story["gens"]))
                for g in story["gens"]:
                    h = g.get("held")
                    f.write("  %s %s: %s; held out %s; %s on %s%s\n" % (
                        g["run"], g["trial"], "; ".join("%s %s -> %s" % (d["name"], d["old"], d["new"]) for d in g["dials"]),
                        "%+.2f +/- %.2f on %d seeds" % h if h else "-", g["commit"][:7], g["where"],
                        "" if len(g["tries"]) == 1 else " (%d tries)" % len(g["tries"])))
                f.write("  main is %s; the line reaches it when the hourly proof reads it past main at z %.1f.\n\n" % (story["main"], story["held_z"]))
            f.write("Then the champions of crucible's GPU islands, trained by neuroevolution under treadcore's rules, each playing "
                    "%d duels in one arena, each duel from a start moved up to %.0f tiles. The camera follows the duel each won best, "
                    "then its kill shot again at half speed, its hardest win and a loss; the faded tanks are the other duels at the "
                    "same moment, the lavender ones the champions before it in the same duel. In the corners, the champion's net "
                    "thinking: its inputs, its two hidden layers with the strongest currents lit, each wire in its node's colour, "
                    "its decisions over the last eight seconds, and the generation.\n\n" % (tr.nd, SPREAD))
            for a, m in marks:
                f.write("%s %s\n" % (stamp(a), m))
            f.write("\nMIT licensed: https://treadcore.org  Made by orrery (tools/montage.py) on %s.\n" % now()[:10])
        doc["output"] = base + ".mp4"
    except OSError as e:
        doc["output_error"] = str(e)
    save(os.path.join(md, "summary.json"), doc)
    # line_last: the newest line generation the film told, where the planner's trailer watch counts from.
    idx["montages"].append({k: doc[k] for k in ("n", "at", "home", "since", "last", "seconds", "mp4", "bytes")}
                           | {"chapters": len(summary), "line_last": story["gens"][-1]["run"] if story and story.get("gens") else None})
    save(os.path.join(adir, "index.json"), idx)
    with open(os.path.join(q, "events.jsonl"), "a") as f:
        f.write(json.dumps({"t": now(), "event": "montage", "n": n, "chapters": len(summary), "seconds": doc["seconds"], "mp4": doc["mp4"]}) + "\n")
    flag(q, "montage %d is ready: %d chapters, %s s, %s" % (n, len(summary), num(doc["seconds"], 0), doc["mp4"]), "montage:%d" % n)
    state(q, state="done", progress=1.0, said="montage %d: %d chapters, %s s; the trace and the frames deleted" % (n, len(summary), num(doc["seconds"], 0)),
          mp4=mp4, n=n)
    try:
        os.remove(preview)
    except OSError:
        pass
    print("montage %d: %s (%s s, %d chapters, %d frames, made in %d s)" % (n, mp4, num(doc["seconds"], 0), len(summary), frames_total, doc["made_in"]))
    return 0


# ---- the trailer -------------------------------------------------------------------------------
#
# Paul, 6 November, the morning r0209 put w12042 on the line and no film followed: "every 2 line
# generations, and make montage 5 now. perhaps we should create a shorter more specific montoge. like a
# quick trailor." A montage runs four and a half minutes (film 4: 275 s), and while the world ladder
# stands its world chapters are the same ones each time. THE TRAILER IS THE NEWS ALONE, under a minute: the
# plate, each generation the line committed since the last film told it -- its chain revealed at speed,
# the dials it moved -- one champion's duel from the GPU islands, and where the commits stand.
#
# The duel is not the line's brain. The line moves the game's scripted brain; the islands train nets; and
# nothing films the game's own brain playing (treadcore-vm's shots are taken by hand). So the duel comes
# after a card that says whose it is, and a trailer whose trace failed goes on without it rather than not
# at all: the generations are the news, the duel is the colour.

TRAILER_MOST = 3     # generations one trailer tells; more since the last film, the newest of them


def trailer(q, gens=None, duels=64, host=None, seed=7):
    global STATE
    STATE = "trailer.json"
    # The montage's lock: both trace in the same folder on the GPU island, and one would delete the other's.
    lock = os.path.join(q, "plan", "montage.lock")
    if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 3 * 3600:
        print("a film is being made (plan/montage.json or plan/trailer.json says which)")
        return 1
    open(lock, "w").close()
    work = os.path.join(q, "plan", "trailer-work")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    try:
        return _trailer(q, gens, duels, host, seed, work)
    except Exception as e:
        state(q, state="failed", said=str(e)[:400])
        print("trailer failed: %s" % e)
        return 1
    finally:
        shutil.rmtree(work, ignore_errors=True)
        try:
            os.remove(lock)
        except OSError:
            pass


def _trailer(q, gens, duels, host, seed, work):
    t0 = time.time()
    m, p = planner(q)
    told = m.Plan.line_filmed(q)
    new = [r for r in p.line_won() if m.Plan.run_no(r) > m.Plan.run_no(told)]
    k = gens or min(TRAILER_MOST, len(new))
    story = line_story(q, k) if k > 0 else None
    if not story:
        state(q, state="done", progress=1.0, said="no line generation since %s: nothing to tell" % told)
        print("no line generation since %s" % told)
        return 0
    gl = story["gens"]
    adir = os.path.join(q, "archive", "trailers")
    os.makedirs(adir, exist_ok=True)
    idx = load(os.path.join(adir, "index.json"), {"trailers": []}) or {"trailers": []}
    n = len(idx["trailers"]) + 1
    preview = os.path.join(q, "plan", "trailer-preview.ppm")
    segs, marks, clock, seg_n = [], [], [0.0], [0]

    def seg_path():
        seg_n[0] += 1
        return os.path.join(work, "seg-%04d.mp4" % seg_n[0])

    def add(path, seconds, mark=None):
        if mark:
            marks.append((clock[0], mark))
        segs.append(path)
        clock[0] += seconds
    # ---- the duel's trace first: the plate stands on its field ----
    homename, cfg = home_of(q)
    hd = os.path.join(q, homename)
    ms = milestones(hd)
    tr = ch = tracer = None
    if ms:
        try:
            chapters, opps, _ = choose(q, hd, ms[-1]["label"], 1)
            chapters = chapters or [dict(ms[-1], facts=facts_of(hd, ms[-1]["island"], ms[-1]["gen"]))]
            state(q, state="tracing", progress=0.05, said="the newest champion, %d duels, on a GPU island" % duels)
            tpath, tracer, _ = trace(q, chapters[:1], opps, cfg, duels, seed, host, work)
            tr, ch = Trace(tpath), chapters[0]
        except Exception as e:  # the generations are the news: a trailer without its duel still tells them
            state(q, said="the duel was left out: %s" % str(e)[:200])
            tr = None
    field = os.path.join(work, "field.ppm")
    if tr:
        with open(field, "wb") as f:
            f.write(b"P6\n%d %d\n255\n" % (W, H) + bytes(Film(tr, 0, follow(tr, 0)).frame(0, 0.0, [], bare=True)))
    else:
        field = os.path.join(work, "field.png")
        magick(["-size", "%dx%d" % (W, H), "xc:#0b100d", field])
    # ---- the plate ----
    state(q, state="rendering", progress=0.3, said="the plate")
    newest = gl[-1]
    h = newest.get("held")
    seg, sec = plate(work, field, "TRAILER %d  ·  THE LINE  ·  %s" % (n, time.strftime("%-d %B").upper()),
                     "> %d generation%s committed: %s" % (len(gl), "" if len(gl) == 1 else "s", ", ".join(g["trial"] for g in gl)),
                     "  newest %s%s, on %s" % (newest["trial"], ", held out %+.2f ± %.2f" % (h[0], h[1]) if h else "", newest["where"]),
                     [("#33f24d", 24, "%d generation%s" % (len(gl), "" if len(gl) == 1 else "s")), ("#ffbf4d", 190, "each chain from its first read"),
                      ("#73c7ff", 520, "the dials it moved"), ("#f23326", 880, "one champion's duel" if tr else "where the commits stand")], seg_path())
    add(seg, sec, "Title")
    whole = os.path.join(work, "t-35.png")
    # ---- each generation: its chain at speed, its dials ----
    for gi, g in enumerate(gl):
        state(q, state="rendering", progress=0.35 + 0.35 * gi / len(gl), said="%s %s" % (g["run"], g["trial"]))
        seg, sec = frames_to(chain_frames(work, gi, g, len(gl), story, step=0.25, hold=3.5), seg_path())
        add(seg, sec, "%s %s: its chain" % (g["run"], g["trial"]))
        add(still(dial_card(work, gi, g), 4.5, seg_path()), 4.5)
    # ---- the duel: whose it is, its kill shot and again at half speed, a pillbox fight, the hardest win ----
    duel = None
    if tr:
        state(q, state="rendering", progress=0.75, said="the duel")
        c = tr.champs[0]
        w_, l_, d_ = (sum(1 for o in c["outcome"] if o == v) for v in (1, -1, 0))
        name = ch["name"] if ch["name"] != "now" else "the newest champion"
        fx = ch.get("facts") or {}
        add(still(card(work, "duel", None, "Meanwhile, on the GPU islands",
                       "%s, %s generation %s" % (name, ch["island"].replace("-cuda", ""), format(ch["gen"], ",")),
                       ["%d won · %d lost · %d drawn, %d duels from one start" % (w_, l_, d_, tr.nd),
                        "a net of %s, grown by neuroevolution in crucible" % (fx.get("dims") or "%d > %d > %d > %d" % (tr.nin, tr.nh, tr.nh, tr.nout)).replace("-", " > "),
                        "not the line's brain: the line moves the game's own rules",
                        "the newest milestone it must beat: %s" % ms[-1]["name"]]), 3.0, seg_path()), 3.0, "Meanwhile, on the GPU islands")
        net = Net(ch["path"], tr.nin, tr.nh, tr.nout) if tr.version >= 2 else None
        labels, gen = hud_labels(work), gen_png(work, 0, ch, 1)
        ttl = os.path.join(work, "ttl.png")
        label_png(ttl, "Generation %s · %s" % (format(ch["gen"], ","), ch["name"] if ch["name"] != "now" else "now"), 48)
        d = follow(tr, 0)
        clips = moments(tr, 0, d)
        kill = next(((cd, cl) for cd, cl in clips if "Kill shot" in cl["what"] and "hardest" not in cl["what"]), None)
        pill = next(((cd, cl) for cd, cl in clips if "illbox" in cl["what"] and (cd, cl) != kill), None)
        hard = next(((cd, cl) for cd, cl in clips if cl["what"].startswith("The hardest win")), None)
        first = kill or (clips[0] if clips else None)
        shown = [x for x in (first, pill, hard) if x]
        for i, (cd, cl) in enumerate(shown):
            out = seg_path()
            nfr, _, _ = render_clip(tr, 0, cd, cl, cl["what"], net, opps, labels, gen, ttl if i == 0 else None, out, preview)
            add(out, nfr / float(FPS))
            if i == 0 and kill:
                at = cl.get("at", cl["from"])
                rc = {"from": max(0, at - 8), "to": min(c["lasted"][cd] - 1 + 3, at + 3), "at": at}
                out = seg_path()
                nfr, _, _ = render_clip(tr, 0, cd, rc, "Replay at half speed: the kill shot", net, opps, labels, gen, None, out, preview,
                                        sub_n=2 * SUB, tiles=20.0, mind=False, hud=False)
                add(out, nfr / float(FPS))
        duel = {"champion": ch.get("label"), "gen": ch["gen"], "island": ch["island"], "won": w_, "lost": l_, "drawn": d_,
                "duels": tr.nd, "followed": d, "traced_on": tracer, "clips": [x[1]["what"] for x in shown]}
    # ---- where they stand, and the plate again ----
    add(still(proof_card(work, story), 5.0, seg_path()), 5.0, "Committed, and where it stands")
    add(still(whole, 2.0, seg_path()), 2.0)
    # ---- one film ----
    state(q, state="encoding", progress=0.93, said="joining %d pieces" % len(segs))
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as f:
        for s in segs:
            f.write("file '%s'\n" % s.replace("'", "'\\''"))
    md = os.path.join(adir, "%04d" % n)
    os.makedirs(md, exist_ok=True)
    mp4 = os.path.join(md, "trailer.mp4")
    r = run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", mp4], 900)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg concat: %s" % r.stderr.strip()[-300:])
    shutil.copy(whole, os.path.join(md, "poster.png"))
    dur = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4], 60).stdout.strip()
    doc = {"n": n, "at": now(), "since": told, "runs": [g["run"] for g in gl], "trials": [g["trial"] for g in gl], "line_last": gl[-1]["run"],
           "duel": duel, "seconds": float(dur or 0), "mp4": os.path.relpath(mp4, q), "bytes": os.path.getsize(mp4),
           "made_in": round(time.time() - t0), "marks": [[round(a, 2), m_] for a, m_ in marks], "line": story}
    try:
        os.makedirs(OUTPUT, exist_ok=True)
        base = os.path.join(OUTPUT, "treadcore-trailer-%04d" % n)
        shutil.copy2(mp4, base + ".mp4")
        with open(base + ".txt", "w") as f:
            f.write("Treadcore: the line, trailer %d, %s\n\n" % (n, ", ".join(doc["trials"])))
            f.write("The game's own brain, the %s orrery's line committed since the last film: each chain of jobs from its "
                    "first read to its commit, and the dials it moved.%s\n\n" % (
                        "generation" if len(gl) == 1 else "%d generations" % len(gl),
                        " Then a duel of the newest champion of crucible's GPU islands, a net and not the line's brain, its kill "
                        "shot again at half speed and its hardest win." if duel else ""))
            for g in gl:
                hh = g.get("held")
                f.write("  %s %s: %s; held out %s; %s on %s\n" % (g["run"], g["trial"], "; ".join("%s %s -> %s" % (x["name"], x["old"], x["new"]) for x in g["dials"]),
                                                              "%+.2f +/- %.2f on %d seeds" % hh if hh else "-", g["commit"][:7], g["where"]))
            f.write("\n")
            for a, m_ in marks:
                f.write("%s %s\n" % (stamp(a), m_))
            f.write("\nMIT licensed: https://treadcore.org  Made by orrery (tools/montage.py trailer) on %s.\n" % now()[:10])
        doc["output"] = base + ".mp4"
    except OSError as e:
        doc["output_error"] = str(e)
    save(os.path.join(md, "summary.json"), doc)
    idx["trailers"].append({k_: doc[k_] for k_ in ("n", "at", "since", "runs", "line_last", "seconds", "mp4", "bytes")})
    save(os.path.join(adir, "index.json"), idx)
    with open(os.path.join(q, "events.jsonl"), "a") as f:
        f.write(json.dumps({"t": now(), "event": "trailer", "n": n, "runs": doc["runs"], "seconds": doc["seconds"], "mp4": doc["mp4"]}) + "\n")
    flag(q, "trailer %d is ready: %s, %s s, %s" % (n, ", ".join(doc["trials"]), num(doc["seconds"], 0), doc.get("output") or doc["mp4"]), "trailer:%d" % n)
    state(q, state="done", progress=1.0, said="trailer %d: %s, %s s" % (n, ", ".join(doc["trials"]), num(doc["seconds"], 0)), mp4=mp4, n=n)
    try:
        os.remove(preview)
    except OSError:
        pass
    print("trailer %d: %s (%s s, %s, made in %d s)" % (n, mp4, num(doc["seconds"], 0), ", ".join(doc["trials"]), doc["made_in"]))
    return 0


def flag(q, text, key):
    d = os.path.join(q, "flags")
    os.makedirs(d, exist_ok=True)
    fid = "%d-montage" % int(time.time() * 1000)
    save(os.path.join(d, fid + ".json"), {"id": fid, "t": now(), "kind": "montage", "text": text, "key": key, "ack": None, "progress": True})


def main(a):
    if len(a) < 2:
        print(__doc__)
        sys.exit(2)
    q, cmd, rest = os.path.abspath(a[0]), a[1], a[2:]

    def opt(k, d, f=int):
        return f(rest[rest.index(k) + 1]) if k in rest else d
    if cmd == "make":
        sys.exit(make(q, opt("--chapters", 12), opt("--duels", 128), opt("--host", None, str), opt("--seed", 7), opt("--since", None, str)))
    elif cmd == "trailer":
        sys.exit(trailer(q, opt("--gens", None), opt("--duels", 64), opt("--host", None, str), opt("--seed", 7)))
    elif cmd == "line":
        sys.exit(line_only(q, os.path.abspath(rest[0]) if rest else os.path.join(q, "plan", "montage-line.mp4")))
    elif cmd == "status":
        print(json.dumps(load(os.path.join(q, "plan", "montage.json"), {}), indent=1))
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
