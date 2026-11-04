#!/usr/bin/env python3
"""montage.py QUEUE make [--chapters N] [--duels N] [--host NAME] [--seed S] | status -- the generations
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
X264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]

# The look is treadcore's clip renderer's (site.css, night): dark grass, the learner in sky blue with its
# armour bar, the foe in red, shells in orange, a hit as a white ring; the pillboxes neutral sand.
GRASS, GRID, OUT = (27, 41, 30), (34, 52, 37), (12, 18, 14)
WALL, ROCK, ROCK_E = (90, 107, 92), (104, 94, 79), (70, 63, 54)
PB, PB_DEAD, PB_BAR = (216, 194, 122), (60, 58, 51), (120, 200, 110)
ME, FOE, ME_G, FOE_G = (108, 196, 255), (232, 88, 79), (44, 84, 108), (88, 46, 44)
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
        _, _, self.nc, self.nd, self.steps, trec, self.npl, self.npb, _ = hdr
        if trec != TREC:
            raise RuntimeError("a trace of %d floats a step, not %d" % (trec, TREC))
        off = 36
        self.dt, self.arena, self.hp, self.pb_hp, self.gun, self.pb_range = struct.unpack_from("<6f", b, off)
        off += 24
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
            self.champs.append({"outcome": out, "lasted": last, "fit": fit, "rec": rec})

    def at(self, c, d, t):
        """Duel d's step t of champion c, as a tuple of TREC floats; past its end, its last step."""
        ch = self.champs[c]
        t = max(0, min(t, ch["lasted"][d] - 1))
        i = (d * self.steps + t) * TREC
        return ch["rec"][i:i + TREC]


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


class Film:
    """The frames of one chapter's clips: the followed duel solid, every other duel a ghost."""

    def __init__(self, tr, c, d):
        self.tr, self.c, self.d = tr, c, d
        self.scale = W / 30.0          # 30 tiles across: the camera's window
        self.blank = bytes(OUT) * (W * H)
        self.cam = None

    def to_px(self, x, y):
        return int((x - self.cam[0]) * self.scale + W / 2), int((y - self.cam[1]) * self.scale + H / 2)

    def frame(self, t, f, flash):
        tr, c, d = self.tr, self.c, self.d
        s0, s1 = tr.at(c, d, t), tr.at(c, d, t + 1)
        ax, ay = lerp(s0[0], s1[0], f), lerp(s0[1], s1[1], f)
        want = (min(max(ax, 15.0), tr.arena - 15.0), min(max(ay, 8.4), tr.arena - 8.4))
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
        # The ghosts: every other duel at this moment, dim, and touching nothing.
        gr = max(3, int(0.45 * S))
        for e in range(tr.nd):
            if e == d:
                continue
            g0 = tr.at(c, e, t)
            if t >= tr.champs[c]["lasted"][e] + 8:
                continue
            for (k, col) in ((7, FOE_G), (0, ME_G)):
                if g0[k + 3] > 0:
                    sx, sy = self.to_px(g0[k], g0[k + 1])
                    if -40 < sx < W + 40 and -40 < sy < H + 40:
                        cv.disc(sx, sy, gr, col)
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
        # The arena whole, small, bottom right: every duel's learner a dot, the camera's window a frame.
        mm, ms = 168, 168 / tr.arena
        mx, my = W - mm - 18, H - mm - 18
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


def card(work, name, bg_png, title, sub, facts):
    """A slide: a picture (orrery's) on the left or behind, a title in 48 point, facts in 32."""
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
        args += ["-font", FONT, "-pointsize", "32", "-fill", "#e8e8e8", "-annotate", "+%d+%d" % (x, y), f]
        y += 48
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


# ---- the film --------------------------------------------------------------------------------

def make(q, most=12, duels=64, host=None, seed=7):
    lock = os.path.join(q, "plan", "montage.lock")
    if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 3 * 3600:
        print("a montage is being made (plan/montage.json says where it is)")
        return 1
    open(lock, "w").close()
    work = os.path.join(q, "plan", "montage-work")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    try:
        return _make(q, most, duels, host, seed, work)
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


def _make(q, most, duels, host, seed, work):
    t0 = time.time()
    adir = os.path.join(q, "archive", "montages")
    os.makedirs(adir, exist_ok=True)
    idx = load(os.path.join(adir, "index.json"), {"montages": []}) or {"montages": []}
    last = idx["montages"][-1]["last"] if idx["montages"] else None
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

    def seg_path():
        seg_n[0] += 1
        return os.path.join(work, "seg-%04d.mp4" % seg_n[0])

    # ---- the opening: a title, then orrery's flowchart, history, terrain, spectrum ----
    state(q, state="rendering", progress=0.1, said="the opening")
    title = card(work, "title", None, "Crucible, montage %d" % n,
                 "%s: %s to %s, %d chapters" % (homename, chapters[0]["label"], chapters[-1]["label"], len(chapters)),
                 ["The world duels: treadcore's rules, four neutral pillboxes.",
                  "Each chapter: one champion, %d duels from one start." % tr.nd,
                  "The camera follows the duel it won best;",
                  "every other duel is a ghost.",
                  "Clips: 1 s before each shot, 0.5 s after."])
    segs.append(still(title, 3.5, seg_path()))
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
        segs.append(still(comp, 2.5, seg_path()))
    # ---- the chapters ----
    summary = []
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
        segs.append(still(slide, 3.0, seg_path()))
        ttl = os.path.join(work, "ttl-%02d.png" % ci)
        label_png(ttl, "Generation %s · %s" % (format(ch["gen"], ","), ch["name"] if ch["name"] != "now" else "now"), 48)
        for k, (cd, clip) in enumerate(clips):
            film = Film(tr, ci, cd)
            clip["duel"] = cd
            cap = os.path.join(work, "cap-%02d-%d.png" % (ci, k))
            label_png(cap, "%s  ·  duel %d of %d, %s" % (clip["what"], cd + 1, tr.nd, "won" if c["outcome"][cd] == 1 else "lost" if c["outcome"][cd] == -1 else "drawn"), 28, font=FONT)
            out = seg_path()
            inputs = ["-i", cap] + (["-i", ttl] if k == 0 else [])
            filt = "[0][1]overlay=24:H-h-24" + ("[a];[a][2]overlay=W-w-24:24:enable='lt(t,%.2f)'" % TITLE_S if k == 0 else "")
            p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-"]
                                 + inputs + ["-filter_complex", filt] + X264 + [out], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            film.cam = None
            nfr = 0
            for t in range(clip["from"], clip["to"] + 1):
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
            segs.append(out)
            frames_total += nfr
            clip["frames"] = nfr
        summary.append({"chapter": ci + 1, "name": ch["name"], "label": ch["label"], "island": ch["island"], "gen": ch["gen"],
                        "won": w_, "lost": l_, "drawn": d_, "followed": d, "followed_vs": tr.opp_of[d],
                        "followed_fitness": round(c["fit"][d], 3), "clips": [k for _, k in clips], "facts": fx})
    # ---- the last card: every chapter's wins in a column ----
    rows = ["%-10s gen %9s   %2d won  %2d lost  %2d drawn" % (s["name"] if s["name"] != "now" else "now", format(s["gen"], ","), s["won"], s["lost"], s["drawn"]) for s in summary]
    end = card(work, "end", None, "%d duels from one start, every chapter" % tr.nd, "the same opponents each time: %s, and sparring partners" % ", ".join(o["name"] for o in opps), rows[:10])
    segs.append(still(end, 5.0, seg_path()))
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
        sys.exit(make(q, opt("--chapters", 12), opt("--duels", 64), opt("--host", None, str), opt("--seed", 7)))
    elif cmd == "status":
        print(json.dumps(load(os.path.join(q, "plan", "montage.json"), {}), indent=1))
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
