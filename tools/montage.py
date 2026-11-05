#!/usr/bin/env python3
"""montage.py QUEUE make [--chapters N] [--duels N] [--host NAME] [--seed S] [--since start|LABEL] | status -- the generations
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
~/fleet/q-NAME/montage): every chapter's champion plays --duels (64) duels in ONE ARENA FROM ONE START, the
opponents drawn by the duel's index -- half sparring partners of drawn skill, half milestones spread over the
ladder -- so duel d is the same contest in every chapter and the film compares like with like. The trace
writes every step (0.1 s) of every duel.

THE CLIPS. In each chapter the camera follows the duel the champion won best (the highest fitness among its
wins; with no win, its best duel), and cuts its kill shot and its pillbox fights -- a pillbox struck, taken,
or shooting at it -- from 1.0 s before to 0.5 s after each, a step drawn as three frames at 30 a second.
Every other duel is drawn at the same moment as a ghost: dim, and no thing in one duel touches another. The
pillboxes are the followed duel's. When the generation changes, a title holds the upper right for 0.25 s.

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
CRUCIBLE = os.path.expanduser("~/code/crucible")


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
SHELL, RING, ZAP = (255, 160, 64), (255, 255, 255), (255, 224, 138)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def state(q, **kw):
    p = os.path.join(q, "plan", "montage.json")
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
    return "crucible" + ("-world" if c.get("world") else "") + ("-hybrid" if c.get("hybrid") else ""), c


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
    flags = ("HYBRID=1 " if cfg.get("hybrid") else "") + ("WORLD=1 " if cfg.get("world") else "")
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
            "./crucible --trace trace.bin --champions %(c)s %(o)s --trace-duels %(d)d --trace-seed %(s)d | grep '^# trace'"
        ) % {"h": home, "f": flags.strip(), "ren": ren, "d": duels, "s": seed,
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
        na = 3 * self.npl + 2 * self.npb
        ar = struct.unpack_from("<%df" % na, b, off)
        off += 4 * na
        p = self.npl
        self.pillars = [(ar[i], ar[p + i], ar[2 * p + i]) for i in range(p)]
        self.boxes = [(ar[3 * p + k], ar[3 * p + self.npb + k]) for k in range(self.npb)]
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
    for (k_in, k_out) in ((32, 3), (35, 4), (52, 3), (55, 4)):
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
    rules = k_in in (35, 55)
    at = 35 if rules else 32

    def to(i):
        if i < 32:
            return i
        if rules and i < 35:
            return i
        return 35 + (i - at)
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
    if k_out < nout:
        out[b3 + nout - 1] = -0.5
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


def moments(tr, c, d, most=4):
    """The clips of a chapter, as (duel, clip): the followed duel's kill shot and its pillbox fights --
    and when it fought no pillbox, the pillbox fight of the next best duel the champion won, the camera on
    that duel's learner for that clip. A plain hit fills in only when there is room, once."""
    ch = tr.champs[c]
    ev = events(tr, c, d)
    pill = [e for e in ev if 2 <= e[0] <= 4]
    keep = [e for e in ev if e[0] == 5] + sorted(pill, key=lambda e: -e[0])[:2]
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
    return sorted(out, key=lambda x: (x[0] != d, x[1]["from"]))


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

    def line(self, x0, y0, x1, y1, c, w=1):
        cb = bytes(c)
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err, n = dx + dy, 0
        while n < 4000:
            n += 1
            if w == 1:
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
P_TX = (16, H - 16 - 154, 476, 154)
P_DE = (W - 16 - 436, H - 16 - 122, 436, 122)
P_GEN = (W - 16 - 300, 16, 300, 96)
MAP = (W - 16 - 150, 124, 150)
DE_ROWS = ("turn", "speed", "fire", "net's say", "shots")


class Film:
    """The frames of one chapter's clips: the followed duel solid, every other duel a ghost, and in the
    corners the champion's net thinking."""

    def __init__(self, tr, c, d, net=None):
        self.tr, self.c, self.d, self.net = tr, c, d, net
        self.scale = W / 30.0          # 30 tiles across: the camera's window
        self.blank = bytes(OUT) * (W * H)
        self.cam = None

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
            ax, ay = ax + (bx_ - ax) / 3.0, ay + (by_ - ay) / 3.0
        want = (min(max(ax, 9.0), tr.arena - 9.0), min(max(ay, 2.4), tr.arena - 2.4))
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
        for (px, py, pr) in tr.pillars:
            sx, sy = self.to_px(px, py)
            cv.disc(sx, sy, int(pr * S) + 3, ROCK_E)
            cv.disc(sx, sy, int(pr * S), ROCK)
        # The pillboxes, as they stand in the followed duel.
        for k, (bx, by) in enumerate(tr.boxes):
            sx, sy = self.to_px(bx, by)
            hp = s0[14 + k]
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
        # finish (the first film's kill shots stood alone: by then most of the 64 were done).
        gr = max(4, int(0.62 * S))
        for e in range(tr.nd):
            if e == d:
                continue
            last = tr.champs[c]["lasted"][e]
            over = t - (last - 1)
            fade = 1.0 if over <= 0 else max(0.0, 1.0 - over / 30.0)
            if fade <= 0:
                continue
            te = min(t, last - 1)
            g0 = tr.at(c, e, te)
            g1 = tr.at(c, e, te + 1) if over <= 0 else g0
            for (k, col) in ((7, FOE), (0, ME)):
                if g0[k + 3] <= 0:
                    continue
                x, y = lerp(g0[k], g1[k], f), lerp(g0[k + 1], g1[k + 1], f)
                sx, sy = self.to_px(x, y)
                if not (-60 < sx < W + 60 and -60 < sy < H + 60):
                    continue
                a = 0.36 * fade
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
        wx, wy = mx + int((self.cam[0] - 15) * ms), my + int((self.cam[1] - 8.4) * ms)
        for (a, b, w, h) in ((wx, wy, int(30 * ms), 1), (wx, wy + int(16.8 * ms), int(30 * ms), 1), (wx, wy, 1, int(16.8 * ms)), (wx + int(30 * ms), wy, 1, int(16.8 * ms))):
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
    g2 = [(bx + 187 + (i % 8) * 15 + 6, by + (i // 8) * 15 + 6) for i in range(net.nh)]
    go = [(bx + 362 + 10, by + k * 28 + 10) for k in range(net.nout)]
    cur = net.circuits(h1, h2)
    top = max((e[0] for e in cur), default=1.0) or 1.0
    for (mag, layer, i, j, v) in reversed(cur):
        a, b = (g1[i], g2[j]) if layer == 0 else (g2[i], go[j])
        k = (mag / top) ** 0.8
        cv.line(a[0], a[1], b[0], b[1], mix(SCR, PHOS if v >= 0 else AMBER, 0.25 + 0.75 * k), w=2 if k > 0.6 else 1)
    for (cx, cy), v in zip(g1, h1):
        cv.rect(cx - 6, cy - 6, 12, 12, shade(v))
    for (cx, cy), v in zip(g2, h2):
        cv.rect(cx - 6, cy - 6, 12, 12, shade(v))
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
    args += ["-annotate", "+%d+%d" % (P_TX[0] + 12, P_TX[1] + 20), "TRANSFORM  55 > 48 > 48 > 4, tanh; brightest currents lit"]
    args += ["-annotate", "+%d+%d" % (P_DE[0] + 12, P_DE[1] + 20), "DECISIONS  the last 8 s, newest at the right"]
    bx, by = P_TX[0] + 12, P_TX[1] + 34
    for k, word in enumerate(("turn", "speed", "fire", "gate")):
        args += ["-annotate", "+%d+%d" % (bx + 390, by + k * 28 + 15), word]
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
    base = os.path.join(work, "t-base.png")
    px, py, pw, ph = 190, 120, 900, 360
    first, lastc = chapters[0], chapters[-1]
    gens = "generations %s to %s" % (format(first["gen"], ","), format(lastc["gen"], ","))
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
            "-annotate", "+%d+%d" % (px + 60, py + 62), "CRUCIBLE  ·  MONTAGE %d  ·  %s" % (n, home.upper().replace("CRUCIBLE-", "").replace("-", " ")),
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
            "-font", MONO, "-pointsize", "16",
            "-fill", "#33f24d", "-annotate", "+24+%d" % (H - 34), "%d chapters" % len(chapters),
            "-fill", "#ffbf4d", "-annotate", "+190+%d" % (H - 34), "%d duels from one start each" % tr.nd,
            "-fill", "#73c7ff", "-annotate", "+520+%d" % (H - 34), "the camera follows the best win",
            "-fill", "#f23326", "-annotate", "+880+%d" % (H - 34), "every other duel a ghost",
            base])
    line1 = "> %s, %s" % (home.replace("crucible-", ""), gens)
    line2 = "  the net's inputs, layers and decisions in the corners"
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
            "-annotate", "+820+305", "two layers of 48, the",
            "-annotate", "+820+335", "strongest currents lit.",
            "-annotate", "+820+390", "Bottom right: its decisions,",
            "-annotate", "+820+420", "8 s of turn, speed, fire.",
            "-annotate", "+820+475", "Top right: the generation,",
            "-annotate", "+820+505", "and the arena's map.",
            "-fill", "#33f24d", "-annotate", "+820+560", "Green +, amber -,",
            "-annotate", "+820+590", "black zero.",
            "-fill", "#9fd4ff", "-annotate", "+40+640", "Faded tanks: the other duels at the same moment, the same start.",
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


# ---- the film --------------------------------------------------------------------------------

def make(q, most=12, duels=64, host=None, seed=7, since=None):
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
        for k, (cd, clip) in enumerate(clips):
            film = Film(tr, ci, cd, nets[ci])
            clip["duel"] = cd
            cap = os.path.join(work, "cap-%02d-%d.png" % (ci, k))
            o = tr.opp_of[cd]
            vs = ("a " + ("scripted tank", "Raider", "Castle", "Expander", "Timid")[min(4, -1 - o)]) if o < 0 else opps[o]["name"] if o < len(opps) else "a milestone"
            label_png(cap, "%s  ·  duel %d of %d against %s, %s" % (clip["what"], cd + 1, tr.nd, vs, "won" if c["outcome"][cd] == 1 else "lost" if c["outcome"][cd] == -1 else "drawn"), 22, font=FONT)
            out = seg_path()
            # The corners' labels, the generation, the caption at the top's middle; on the chapter's first
            # clip the generation's 0.25 s title over the upper right.
            inputs = ["-i", labels, "-i", gen, "-i", cap] + (["-i", ttl] if k == 0 else [])
            filt = ("[0][1]overlay=0:0[a];[a][2]overlay=%d:%d[b];[b][3]overlay=(W-w)/2:16" % (P_GEN[0], P_GEN[1])
                    + ("[c];[c][4]overlay=W-w-24:24:enable='lt(t,%.2f)'" % TITLE_S if k == 0 else ""))
            p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-"]
                                 + inputs + ["-filter_complex", filt] + X264 + [out], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            film.cam = None
            nfr = 0
            steps = []
            for t in range(clip["from"], clip["to"] + 1):
                if nets[ci] is not None:
                    sc = shot_of(tr, ci, cd, t)
                    steps.append(pack_mind(nets[ci], tr, ci, cd, t, {RED_HUD: "hit", AMBER: "pillbox", SKY: "pillbox fired", (240, 248, 240): "shot"}.get(sc, "") if sc else ""))
                for sub in range(SUB):
                    fr = film.frame(t, sub / SUB, flashes(tr, ci, cd, t, sub / SUB))
                    p.stdin.write(fr)
                    nfr += 1
                    if nfr % 15 == 1:
                        with open(preview + ".part", "wb") as pf:
                            pf.write(small(fr))
                        os.replace(preview + ".part", preview)
                    if k == 0 and t == clip.get("at", clip["from"]) and sub == 0:
                        poster_ppm = small(fr)
            p.stdin.close()
            err = p.stderr.read().decode(errors="replace")
            if p.wait() != 0:
                raise RuntimeError("ffmpeg: %s" % err.strip()[-300:])
            add(out, nfr / float(FPS))
            frames_total += nfr
            clip["frames"] = nfr
            minds.append({"what": clip["what"], "duel": cd, "from": clip["from"], "to": clip["to"], "steps": steps})
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
           "made_in": round(time.time() - t0)}
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
            f.write("Champions of crucible's GPU islands, trained by neuroevolution under treadcore's rules, each playing "
                    "%d duels from one start. The camera follows the duel each won best; the faded tanks are the other duels "
                    "at the same moment. In the corners, the champion's net thinking: its inputs, its two hidden layers with "
                    "the strongest currents lit, its decisions over the last eight seconds, and the generation.\n\n" % tr.nd)
            for a, m in marks:
                f.write("%s %s\n" % (stamp(a), m))
            f.write("\nMIT licensed: https://treadcore.org  Made by orrery (tools/montage.py) on %s.\n" % now()[:10])
        doc["output"] = base + ".mp4"
    except OSError as e:
        doc["output_error"] = str(e)
    save(os.path.join(md, "summary.json"), doc)
    idx["montages"].append({k: doc[k] for k in ("n", "at", "home", "since", "last", "seconds", "mp4", "bytes")} | {"chapters": len(summary)})
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
        sys.exit(make(q, opt("--chapters", 12), opt("--duels", 64), opt("--host", None, str), opt("--seed", 7), opt("--since", None, str)))
    elif cmd == "status":
        print(json.dumps(load(os.path.join(q, "plan", "montage.json"), {}), indent=1))
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
