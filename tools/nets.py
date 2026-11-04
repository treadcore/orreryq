#!/usr/bin/env python3
"""nets.py QUEUE [refresh | capture PATH [--as NAME] [--why TEXT] | promote NAME [--slot K]
                 | demote NAME | expire [--days N] [--do] | note NAME TEXT | forget NAME]

The register of every learned net the fleet has made or keeps -- the .bin files that travel
from a machine's train run to the queue's results, to treadcore's nets/, to a style's slot, to a
model slot, to a census -- with where each has been, what read it, and what it is for. Written
to QUEUE/plan/nets.json for orrery's Results, Nets page (src/nets.rs), which is the explorer.

THE VAULT KEEPS NOTHING UNASKED. Every net the fleet makes already lies in its run's results
directory, and every net the game ships lies in nets/; the register only POINTS at them. A copy
is made only by `capture`, into QUEUE/vault/, and that copy carries its sha, its origin and its
notes. `promote` marks a vault net a milestone, which `expire` never touches, and with --slot
puts it in a model slot (models/K.bin and models.tsv, the league's form, the planner's file).
`expire` lists what it would remove -- vault copies that are no milestone, no slot, no style,
older than N days (14) -- and removes them only with --do. (Paul, 3 November: "a way to save,
capture, and expire some of these .bin files ... by request only, with promotion abilities".)

Fast by the standard of a poll: the results tree has twenty thousand directories, and this
reads only the train and school runs' out directories, never the censuses'. Hashing every net
once a run is the cost; nets.json caches by (path, size, mtime), so a refresh touches new files.
"""
import glob
import hashlib
import json
import math
import os
import re
import shutil
import struct
import sys
import time

TC = os.path.expanduser(os.environ.get("TREADCORE", "~/code/treadcore"))
GROUPS = [("compass", 88), ("body", 12), ("nav", 6), ("contacts", 18), ("hints", 9), ("shells", 5), ("air", 5), ("economy", 17)]
HEADS = [("drive", 10), ("gun", 11), ("lead", 3), ("mortar", 11), ("drone", 5), ("squad", 4), ("signal", 3)]
MILESTONES = ["phase1", "phase3", "map4", "map7a", "map5", "map7"]
STYLE_NAMES = {0: "Fleet", 1: "Raider", 2: "Castle", 3: "Expander", 4: "Timid", 5: "Overrider", 6: "Scholar", 7: "Duelist",
               8: "Rome", 9: "China", 10: "Mongolia", 11: "Shoshone", 12: "Venice", 13: "Japan", 14: "Polynesia", 15: "Assyria",
               16: "Quartermaster"}


def read(p):
    try:
        with open(p, errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def load_json(p, default):
    try:
        return json.loads(read(p))
    except ValueError:
        return default


# ---- the net file ---------------------------------------------------------------------------

def parse_net(path):
    """The header and the weights of a TCNET1 file: sizes, the layers' numbers, a fingerprint."""
    with open(path, "rb") as f:
        b = f.read()
    if len(b) < 12 or b[:8] != b"TCNET1\0\0":
        return None
    n = struct.unpack_from("<I", b, 8)[0]
    sizes = list(struct.unpack_from("<%dI" % n, b, 12))
    at = 12 + 4 * n
    layers = []
    for inp, out in zip(sizes, sizes[1:]):
        w = struct.unpack_from("<%df" % (inp * out), b, at)
        at += 4 * inp * out
        bias = struct.unpack_from("<%df" % out, b, at)
        at += 4 * out
        layers.append((inp, out, w, bias))
    return sizes, layers


def pooled(w, inp, out, rows, cols):
    """|W| (out x inp, row-major by output) pooled to rows x cols cells, each a mean."""
    grid = [[0.0] * cols for _ in range(rows)]
    count = [[0] * cols for _ in range(rows)]
    for o in range(out):
        r = o * rows // out
        base = o * inp
        for i in range(inp):
            c = i * cols // inp
            grid[r][c] += abs(w[base + i])
            count[r][c] += 1
    return [[g / c if c else 0.0 for g, c in zip(gr, cr)] for gr, cr in zip(grid, count)]


def top_singular(w, inp, out, k=3, steps=12):
    """The first k singular values by power iteration with deflation: an octave of a matrix's
    spectrum, enough to say whether a layer is one direction or many."""
    rows = [w[o * inp:(o + 1) * inp] for o in range(out)]
    found = []
    vecs = []
    for _ in range(k):
        v = [math.sin(1.7 * i + 0.3 * len(found)) for i in range(inp)]
        s = 0.0
        for _ in range(steps):
            for u in vecs:
                d = sum(a * b for a, b in zip(v, u))
                v = [a - d * b for a, b in zip(v, u)]
            y = [sum(a * b for a, b in zip(r, v)) for r in rows]
            v2 = [0.0] * inp
            for r, yy in zip(rows, y):
                if yy:
                    for i in range(inp):
                        v2[i] += r[i] * yy
            norm = math.sqrt(sum(a * a for a in v2)) or 1e-12
            v = [a / norm for a in v2]
            s = math.sqrt(norm)
        found.append(round(s, 3))
        vecs.append(v)
    return found


def numbers_of(parsed):
    sizes, layers = parsed
    out = {"sizes": sizes, "parameters": sum(len(l[2]) + len(l[3]) for l in layers), "layers": []}
    for inp, o, w, b in layers:
        fro = math.sqrt(sum(x * x for x in w))
        small = sum(1 for x in w if abs(x) < 1e-3)
        out["layers"].append({"inputs": inp, "outputs": o, "norm": round(fro, 3), "max_abs": round(max(abs(x) for x in w), 3),
                              "sparsity": round(small / len(w), 4), "singular": top_singular(w, inp, o)})
    inp, o, w, _ = layers[0]
    out["fingerprint"] = [[round(v, 4) for v in row] for row in pooled(w, inp, o, 16, 16)]
    # The first layer's listening by sense group: the mean |w| of the columns each group owns, as
    # the tank has its inputs laid out (analysis.py GROUPS, plus the economy's seventeen).
    groups, at = [], 0
    for name, n in GROUPS:
        if at >= inp:
            break
        cols = range(at, min(at + n, inp))
        groups.append([name, round(sum(abs(w[r * inp + c]) for r in range(o) for c in cols) / (o * len(cols)), 4)])
        at += n
    out["listening"] = groups
    # The last layer's speaking by head: the mean |w| of the rows each head owns.
    inp, o, w, _ = layers[-1]
    heads, at = [], 0
    for name, n in HEADS:
        if at >= o:
            break
        rows = range(at, min(at + n, o))
        heads.append([name, round(sum(abs(w[r * inp + c]) for r in rows for c in range(inp)) / (len(rows) * inp), 4)])
        at += n
    out["speaking"] = heads
    return out


def format_of(path, size):
    """What a file that is not a TCNET1 net is: a hybrid's raw floats (crucible), a TCP1 patch."""
    with open(path, "rb") as f:
        head = f.read(8)
    if head[:4] == b"TCP1":
        return "a TCP1 patch: a transform of %d bytes over the rules, not a net of its own (patch.rs)" % size
    if size % 4 == 0:
        return "raw floats, %d of them, no header: a crucible hybrid's weights, read by its own loader" % (size // 4)
    return "not a treadcore net"


def sha_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


# ---- where a net has been -------------------------------------------------------------------

def run_of(path, qdir):
    """results/rNNNN-kind/.../out/rNNNN-kind/NAME.bin -> (run id, kind, the run's record, the out dir)."""
    m = re.search(r"/results/(r\d+)-([a-z]+)/", path)
    if not m:
        return None
    rid, kind = m.group(1), m.group(2)
    rec = load_json(os.path.join(qdir, "runs", rid + ".json"), {})
    return {"id": rid, "kind": kind, "asked": rec.get("asked", ""), "by": rec.get("by", ""), "params": rec.get("params", {}), "out": os.path.dirname(path)}


def host_of(outdir, qdir):
    env = read(os.path.join(outdir, "run.env"))
    m = re.search(r"^HOST=(\S+)", env, re.M)
    if m:
        return m.group(1)
    # A train run writes no run.env; the keeper's log says who had the job.
    rid = re.search(r"(r\d+-[a-z]+)", outdir)
    if rid:
        for line in read(os.path.join(qdir, "keeper.log")).splitlines()[-20000:]:
            if rid.group(1) in line:
                h = re.search(r"\b(on|to) ([a-z]+(?:-cuda)?)\b", line)
                if h:
                    return h.group(2)
    return ""


def held_out(outdir):
    """The held-out lines at the end of a harness.log: course, passed, of, reward, verdict."""
    rows = []
    for line in read(os.path.join(outdir, "harness.log")).splitlines():
        m = re.match(r"train: held out (.+?) by the net: ([\d.]+) \+/- ([\d.]+) passed \((\d+) of (\d+)\), reward ([-\d.]+), floor ([\d.]+): (\w+)", line)
        if m:
            rows.append({"course": m.group(1), "share": float(m.group(2)), "passed": int(m.group(4)), "of": int(m.group(5)),
                         "reward": float(m.group(6)), "floor": float(m.group(7)), "verdict": m.group(8)})
    return rows


def train_curve(outdir):
    """The population's mean and the net's score every tenth of a train run: forty points."""
    pts = []
    for line in read(os.path.join(outdir, "harness.log")).splitlines():
        m = re.match(r"train: gen\s+(\d+) mean\s+([-\d.]+) best\s+([-\d.]+) net\s+([-\d.]+) passed ([\d.]+)", line)
        if m:
            pts.append((int(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)), float(m.group(5))))
    if not pts:
        return []
    step = max(1, len(pts) // 40)
    return [list(p) for p in pts[::step]] + ([list(pts[-1])] if (len(pts) - 1) % step else [])


def gauntlet_rows(name):
    rows = {}
    path = os.path.join(TC, "source/treadcore-brain/build/train/gauntlet.tsv")
    lines = read(path).splitlines()
    if not lines:
        return rows
    head = lines[0].split("\t")
    for l in lines[1:]:
        f = dict(zip(head, l.split("\t")))
        if f.get("brain") == name:
            try:
                rows[f["item"]] = float(f["share"])
            except (KeyError, ValueError):
                pass
    return rows


def lr_sections(name):
    """The lab report's sections that name the file: '## 131. ...' headings, by number."""
    text = read(os.path.join(TC, "documentation/LAB-REPORT-BRAIN.md"))
    out, current = [], None
    needle = re.compile(r"\b%s\.bin\b|`%s`" % (re.escape(name), re.escape(name)))
    for line in text.splitlines():
        m = re.match(r"## (\d+)\. (.*)", line)
        if m:
            current = (int(m.group(1)), m.group(2))
            continue
        if current and needle.search(line) and (not out or out[-1][0] != current[0]):
            out.append(list(current))
    return out[-8:]


# ---- the register -----------------------------------------------------------------------------

def vault_dir(qdir):
    d = os.path.join(qdir, "vault")
    os.makedirs(d, exist_ok=True)
    return d


def vault_load(qdir):
    return load_json(os.path.join(vault_dir(qdir), "vault.json"), {"nets": []})


def vault_save(qdir, v):
    p = os.path.join(vault_dir(qdir), "vault.json")
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(v, f, indent=1)
    os.replace(tmp, p)


def discover(qdir):
    """Every .bin the register points at, with how it is held: (path, held) where held is one of
    ships (treadcore nets/), slot (a model slot), vault, result (a run's out directory)."""
    found = []
    for p in sorted(glob.glob(os.path.join(TC, "nets", "*.bin")) + glob.glob(os.path.join(TC, "nets", "patches", "*.bin"))):
        found.append((p, "ships"))
    for p in sorted(glob.glob(os.path.join(qdir, "models", "*.bin"))):
        found.append((p, "slot"))
    for p in sorted(glob.glob(os.path.join(vault_dir(qdir), "*.bin"))):
        found.append((p, "vault"))
    for kind in ("train", "school"):
        for p in sorted(glob.glob(os.path.join(qdir, "results", "r*-%s" % kind, "fleet", "q-grove", "out", "*", "*.bin"))):
            base = os.path.basename(p)
            # A school's rounds are checkpoints; its best is the net. A train run's one file is the net.
            if kind == "school" and base != "best.bin":
                continue
            found.append((p, "result"))
    return found


def styles_rows():
    rows = {}
    lines = read(os.path.join(TC, "nets", "styles.tsv")).splitlines()
    for l in lines[1:]:
        f = l.split("\t")
        if len(f) >= 4:
            m = re.match(r"(\d+)", f[1])
            rows[os.path.join(TC, f[0])] = {"slot": int(m.group(1)) if m else None, "style": f[1], "from": f[2], "note": f[3]}
    return rows


def slots_rows(qdir):
    rows = {}
    lines = read(os.path.join(qdir, "models", "models.tsv")).splitlines()
    for l in lines[1:]:
        f = l.split("\t")
        if len(f) >= 5:
            rows[f[4]] = {"slot": int(f[0]), "name": f[1], "generation": int(f[2]), "source": f[3]}
    return rows


def refresh(qdir, quiet=False):
    t0 = time.time()
    old = load_json(os.path.join(qdir, "plan", "nets.json"), {})
    cache = {n["path"]: n for n in old.get("nets", []) if "path" in n}
    vault = vault_load(qdir)
    vault_by_sha = {n["sha"]: n for n in vault["nets"]}
    styles = styles_rows()
    slots = slots_rows(qdir)
    runs = {}
    for p in glob.glob(os.path.join(qdir, "runs", "r*.json")):
        runs[os.path.basename(p)[:-5]] = load_json(p, {})
    nets = []
    for path, held in discover(qdir):
        try:
            st = os.stat(path)
        except OSError:
            continue
        key = (st.st_size, int(st.st_mtime))
        prior = cache.get(path)
        if prior and (prior.get("bytes"), prior.get("mtime")) == key and "numbers" in prior:
            sha, numbers = prior["sha"], prior["numbers"]
        else:
            parsed = parse_net(path)
            sha = sha_of(path)
            numbers = numbers_of(parsed) if parsed else None
        name = os.path.splitext(os.path.basename(path))[0]
        if os.path.basename(os.path.dirname(path)) == "patches":
            name = "patch " + name
        run = run_of(path, qdir) if held == "result" else None
        if run:
            name = run["params"].get("name") or name
            if run["kind"] == "school":
                name = "%s-%s" % (run["id"], name)
        if held == "slot":
            name = slots.get(sha, {}).get("name") or ("slot-" + name)
        if held == "vault":
            v = vault_by_sha.get(sha)
            name = v["name"] if v else name
        entry = {
            "name": name, "path": path, "held": held, "sha": sha, "bytes": st.st_size, "mtime": int(st.st_mtime),
            "when": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)), "numbers": numbers,
        }
        if numbers is None:
            entry["format"] = format_of(path, st.st_size)
        if run:
            entry["run"] = {k: run[k] for k in ("id", "kind", "asked", "by")}
            entry["run"]["params"] = {k: v for k, v in run["params"].items() if k in ("gens", "pairs", "seeds", "held", "start", "name")}
            entry["run"]["ground"] = [os.path.splitext(os.path.basename(g))[0] for g in run["params"].get("ground", "").split(",") if g]
            entry["run"]["host"] = host_of(run["out"], qdir)
            entry["held_out"] = held_out(run["out"]) if prior is None or not prior.get("held_out") else prior["held_out"]
            entry["curve"] = train_curve(run["out"]) if prior is None or not prior.get("curve") else prior["curve"]
            start = run["params"].get("start", "")
            if start:
                entry["parent"] = os.path.splitext(os.path.basename(start))[0]
        nets.append(entry)
    # One record a sha: the same bytes in nets/, a slot and a result are one net that travelled.
    by_sha = {}
    for n in nets:
        rec = by_sha.get(n["sha"])
        if rec is None:
            rec = dict(n)
            rec["copies"] = []
            by_sha[n["sha"]] = rec
        rec["copies"].append({"path": n["path"], "held": n["held"], "when": n["when"]})
        # The shipped name wins, then the slot's, then the run's: that is the name people use.
        rank = {"ships": 0, "slot": 1, "vault": 2, "result": 3}
        if rank[n["held"]] < rank[rec["held"]]:
            rec["name"], rec["path"], rec["held"] = n["name"], n["path"], n["held"]
        for k in ("run", "held_out", "curve", "parent"):
            if k in n and k not in rec:
                rec[k] = n[k]
    out = []
    for sha, rec in by_sha.items():
        stem = os.path.splitext(os.path.basename(rec["path"]))[0]
        rec["milestone"] = stem in MILESTONES or bool(vault_by_sha.get(sha, {}).get("milestone"))
        rec["style"] = styles.get(rec["path"]) or next((styles[c["path"]] for c in rec["copies"] if c["path"] in styles), None)
        rec["slot"] = slots.get(sha)
        rec["vault"] = vault_by_sha.get(sha)
        rec["gauntlet"] = gauntlet_rows(stem)
        rec["sections"] = lr_sections(stem)
        rec["starts"] = sorted(rid for rid, r in runs.items() if os.path.splitext(os.path.basename(str(r.get("params", {}).get("start", ""))))[0] == stem)
        rec["why"] = why_of(rec)
        out.append(rec)
    # Children by parent name, so the page draws the lineage.
    names = {n["name"]: n for n in out}
    stems = {os.path.splitext(os.path.basename(n["path"]))[0]: n for n in out}
    for n in out:
        p = n.get("parent")
        if p:
            target = names.get(p) or stems.get(p)
            n["parent"] = target["name"] if target else p
    out.sort(key=lambda n: (-int(n["milestone"]), -int(bool(n["slot"])), -int(bool(n["style"])), -n["mtime"]))
    doc = {"at": time.strftime("%Y-%m-%dT%H:%M"), "took_s": round(time.time() - t0, 1), "nets": out,
           "vault": {"dir": vault_dir(qdir), "count": sum(1 for v in vault["nets"] if v.get("kept")), "bytes": sum(v.get("bytes", 0) for v in vault["nets"] if v.get("kept")),
                     "noted": sum(1 for v in vault["nets"] if not v.get("kept"))},
           "policy": "The register points; the vault copies only on capture. Expire removes vault copies that are no milestone, slot or style, older than 14 days, and only with --do."}
    os.makedirs(os.path.join(qdir, "plan"), exist_ok=True)
    p = os.path.join(qdir, "plan", "nets.json")
    with open(p + ".tmp", "w") as f:
        json.dump(doc, f)
    os.replace(p + ".tmp", p)
    if not quiet:
        print("%d nets (%d shipped, %d in slots, %d in the vault, %d in results), %.1f s -> %s" % (
            len(out), sum(1 for n in out if n["held"] == "ships"), sum(1 for n in out if n["slot"]), len(vault["nets"]),
            sum(1 for n in out if n["held"] == "result"), doc["took_s"], p))
    return doc


def why_of(n):
    """What the net is for, and where, said from its record. A sentence a person can check."""
    parts = []
    kind = "a milestone" if n["milestone"] else "a model slot's net" if n["slot"] else "a style's net" if n["style"] and n["style"]["style"] != "(none)" else \
        "a clone of the rules" if os.path.basename(n["path"]).startswith("bc") else "a trained net" if n.get("run") else "a net"
    where = {"ships": "shipped in treadcore's nets/", "slot": "in the queue's model slots", "vault": "kept in the vault", "result": "in its run's results only"}[n["held"]]
    parts.append("%s, %s." % (kind[0].upper() + kind[1:], where))
    r = n.get("run")
    if r:
        p = r.get("params", {})
        parts.append("Made by run %s (%s%s%s) on %s%s." % (r["id"], r["kind"], ", %s generations" % p["gens"] if p.get("gens") else "",
                                                           " from %s" % os.path.basename(p["start"]) if p.get("start") else "",
                                                           r.get("host") or "a fleet machine", " for the courses " + ", ".join(r["ground"]) if r.get("ground") else ""))
    if n["style"] and n["style"]["style"] == "(none)":
        parts.append("Listed in styles.tsv without a slot (%s): %s." % (n["style"]["from"], n["style"]["note"].rstrip(".")))
    elif n["style"]:
        parts.append("Plays as style %s in every census that asks for it; %s." % (n["style"]["style"], n["style"]["note"].rstrip(".")))
    if n["slot"]:
        parts.append("Holds model slot %d (generation %d) and plays whole teams in the league's censuses." % (n["slot"]["slot"], n["slot"]["generation"]))
    if n["milestone"] and not n["slot"]:
        parts.append("A milestone: the gauntlet reads it beside every new net, so it is the yardstick a new net is measured against.")
    g = n["gauntlet"]
    if g:
        strong = sorted((k for k, v in g.items() if v >= 0.9), key=lambda k: int(re.match(r"G(\d+)", k).group(1)))
        weak = sorted((k for k, v in g.items() if v == 0.0), key=lambda k: int(re.match(r"G(\d+)", k).group(1)))
        if strong:
            parts.append("On the gauntlet it holds %s." % ", ".join(k.split(" ")[0] for k in strong))
        if weak:
            parts.append("It has nothing on %s." % ", ".join(k.split(" ")[0] for k in weak))
    ho = n.get("held_out") or []
    if ho:
        passed = [h for h in ho if h["verdict"] == "PASS"]
        parts.append("Held out it passed %d of %d courses%s." % (len(passed), len(ho), "; not yet " + ", ".join(h["course"] for h in ho if h["verdict"] != "PASS") if len(passed) < len(ho) else ""))
    if n["starts"]:
        parts.append("Runs %s began from it." % ", ".join(n["starts"]))
    if n["sections"]:
        parts.append("Read in LR %s." % ", ".join(str(s[0]) for s in n["sections"]))
    return " ".join(parts)


# ---- the verbs: capture, promote, demote, expire, note, forget -------------------------------

def find_net(qdir, name):
    doc = load_json(os.path.join(qdir, "plan", "nets.json"), {}) or refresh(qdir, quiet=True)
    for n in doc.get("nets", []):
        if n["name"] == name or n["sha"] == name or n["path"] == name or os.path.splitext(os.path.basename(n["path"]))[0] == name:
            return n
    return None


def capture(qdir, path, name=None, why=""):
    # A name in the register first, then a file: `capture first-minute` and `capture nets/x.bin`
    # from treadcore's directory both mean the registered net, wherever this is run from.
    net = find_net(qdir, path) or find_net(qdir, os.path.basename(path))
    if net:
        path = net["path"]
    else:
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isfile(path):
            sys.exit("capture: no such net %s" % path)
    if not parse_net(path):
        sys.exit("capture: %s is not a treadcore net" % path)
    sha = sha_of(path)
    v = vault_load(qdir)
    for n in v["nets"]:
        if n["sha"] == sha and n.get("kept"):
            print("already in the vault as %s (%s)" % (n["name"], n["kept"]))
            return
    name = name or os.path.splitext(os.path.basename(path))[0]
    noted = next((n for n in v["nets"] if n["sha"] == sha), None)
    if noted:
        # Notes were written on it before a copy was kept: the copy joins them.
        kept = os.path.join(vault_dir(qdir), "%s-%s.bin" % (noted["name"], sha))
        shutil.copy2(path, kept)
        noted.update({"kept": kept, "origin": path, "captured": time.strftime("%Y-%m-%dT%H:%M")})
        if why:
            noted.setdefault("notes", []).append({"at": time.strftime("%Y-%m-%dT%H:%M"), "text": why})
        vault_save(qdir, v)
        refresh(qdir, quiet=True)
        print("captured %s as %s (%s, %d bytes), its notes kept" % (path, noted["name"], sha, os.path.getsize(path)))
        return
    if any(n["name"] == name for n in v["nets"]):
        name = "%s-%s" % (name, sha[:6])
    kept = os.path.join(vault_dir(qdir), "%s-%s.bin" % (name, sha))
    shutil.copy2(path, kept)
    v["nets"].append({"name": name, "sha": sha, "kept": kept, "origin": path, "bytes": os.path.getsize(path),
                      "captured": time.strftime("%Y-%m-%dT%H:%M"), "milestone": False, "notes": ([{"at": time.strftime("%Y-%m-%dT%H:%M"), "text": why}] if why else [])})
    vault_save(qdir, v)
    refresh(qdir, quiet=True)
    print("captured %s as %s (%s, %d bytes)" % (path, name, sha, os.path.getsize(path)))


def promote(qdir, name, slot=None):
    v = vault_load(qdir)
    rec = next((n for n in v["nets"] if n["name"] == name or n["sha"] == name), None)
    if rec is None:
        # A net not yet in the vault is captured first: a milestone is kept.
        net = find_net(qdir, name)
        if not net:
            sys.exit("promote: no such net %s" % name)
        capture(qdir, net["path"], net["name"])
        v = vault_load(qdir)
        rec = next(n for n in v["nets"] if n["sha"] == net["sha"])
    if not rec.get("kept"):
        # Noted but never copied: a milestone is a kept thing, so the copy is made now.
        capture(qdir, rec["origin"], rec["name"])
        v = vault_load(qdir)
        rec = next(n for n in v["nets"] if n["sha"] == rec["sha"])
    rec["milestone"] = True
    rec.setdefault("notes", []).append({"at": time.strftime("%Y-%m-%dT%H:%M"), "text": "promoted to milestone" + (" and model slot %d" % slot if slot else "")})
    vault_save(qdir, v)
    if slot:
        models = os.path.join(qdir, "models")
        os.makedirs(models, exist_ok=True)
        tsv = os.path.join(models, "models.tsv")
        lines = read(tsv).splitlines() or ["slot\tname\tgeneration\tsource\tsha"]
        gens = [int(l.split("\t")[2]) for l in lines[1:] if l.count("\t") >= 4]
        gen = (max(gens) + 1) if gens else 1
        rows = [l for l in lines[1:] if not l.startswith("%d\t" % slot)]
        rows.append("%d\tg%d-%s\t%d\t%s\t%s" % (slot, gen, rec["name"], gen, rec["kept"], rec["sha"]))
        rows.sort(key=lambda l: int(l.split("\t")[0]))
        shutil.copy2(rec["kept"], os.path.join(models, "%d.bin" % slot))
        with open(tsv, "w") as f:
            f.write("\n".join([lines[0]] + rows) + "\n")
    refresh(qdir, quiet=True)
    print("%s is a milestone%s" % (rec["name"], "; model slot %d is it (generation %d)" % (slot, gen) if slot else ""))


def demote(qdir, name):
    v = vault_load(qdir)
    rec = next((n for n in v["nets"] if n["name"] == name or n["sha"] == name), None)
    if rec is None:
        sys.exit("demote: %s is not in the vault" % name)
    rec["milestone"] = False
    rec.setdefault("notes", []).append({"at": time.strftime("%Y-%m-%dT%H:%M"), "text": "milestone taken back; expire may remove it"})
    vault_save(qdir, v)
    refresh(qdir, quiet=True)
    print("%s is no longer a milestone" % rec["name"])


def expire(qdir, days=14, do=False):
    v = vault_load(qdir)
    slots = {s for s in slots_rows(qdir)}
    styles = {sha_of(p) for p in styles_rows() if os.path.exists(p)}
    cutoff = time.time() - days * 86400
    gone, kept = [], []
    for n in list(v["nets"]):
        if not n.get("kept"):
            # Notes without a copy: nothing to expire, and the words stay.
            continue
        t = time.mktime(time.strptime(n["captured"], "%Y-%m-%dT%H:%M")) if n.get("captured") else 0
        why = "milestone" if n.get("milestone") else "model slot" if n["sha"] in slots else "style" if n["sha"] in styles else \
            "newer than %d days" % days if t > cutoff else None
        if why:
            kept.append((n["name"], why))
            continue
        gone.append(n)
        if do:
            # The copy goes; the record stays with its notes and no copy, so what was learned of
            # the net outlives the bytes, and a later capture joins them.
            try:
                os.remove(n["kept"])
            except OSError:
                pass
            n["kept"] = ""
            n.setdefault("notes", []).append({"at": time.strftime("%Y-%m-%dT%H:%M"), "text": "expired: the copy removed after %d days" % days})
    if do:
        vault_save(qdir, v)
        refresh(qdir, quiet=True)
    print("%s %d vault cop%s older than %d days with no milestone, slot or style%s; %d kept (%s)" % (
        "removed" if do else "would remove", len(gone), "y" if len(gone) == 1 else "ies", days,
        ": " + ", ".join(n["name"] for n in gone) if gone else "", len(kept),
        ", ".join("%s: %s" % k for k in kept[:6]) + (", ..." if len(kept) > 6 else "")))
    if gone and not do:
        print("run again with --do to remove them")


def note(qdir, name, text):
    v = vault_load(qdir)
    rec = next((n for n in v["nets"] if n["name"] == name or n["sha"] == name), None)
    if rec is None:
        # A note on a net that is not in the vault is kept in the vault's register all the same,
        # without a copy: the words are small and the net stays where it is.
        net = find_net(qdir, name)
        if not net:
            sys.exit("note: no such net %s" % name)
        rec = {"name": net["name"], "sha": net["sha"], "kept": "", "origin": net["path"], "bytes": net["bytes"],
               "captured": "", "milestone": False, "notes": []}
        v["nets"].append(rec)
    rec.setdefault("notes", []).append({"at": time.strftime("%Y-%m-%dT%H:%M"), "text": text})
    vault_save(qdir, v)
    refresh(qdir, quiet=True)
    print("noted on %s: %s" % (rec["name"], text))


def forget(qdir, name):
    v = vault_load(qdir)
    rec = next((n for n in v["nets"] if n["name"] == name or n["sha"] == name), None)
    if rec is None:
        sys.exit("forget: %s is not in the vault" % name)
    if rec.get("milestone"):
        sys.exit("forget: %s is a milestone; demote it first" % name)
    if rec.get("kept") and os.path.exists(rec["kept"]):
        os.remove(rec["kept"])
    v["nets"].remove(rec)
    vault_save(qdir, v)
    refresh(qdir, quiet=True)
    print("forgot %s" % rec["name"])


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    qdir = os.path.abspath(os.path.expanduser(argv[1]))
    cmd = argv[2] if len(argv) > 2 else "refresh"
    rest = argv[3:]

    def opt(flag, default=None):
        if flag in rest:
            i = rest.index(flag)
            val = rest[i + 1] if i + 1 < len(rest) else default
            del rest[i:i + 2]
            return val
        return default

    if cmd == "refresh":
        refresh(qdir)
    elif cmd == "capture":
        name, why = opt("--as"), opt("--why", "")
        if not rest:
            sys.exit("capture PATH [--as NAME] [--why TEXT]")
        capture(qdir, rest[0], name, why)
    elif cmd == "promote":
        slot = opt("--slot")
        if not rest:
            sys.exit("promote NAME [--slot K]")
        promote(qdir, rest[0], int(slot) if slot else None)
    elif cmd == "demote":
        demote(qdir, rest[0])
    elif cmd == "expire":
        days = int(opt("--days", "14"))
        do = "--do" in rest
        expire(qdir, days, do)
    elif cmd == "note":
        if len(rest) < 2:
            sys.exit("note NAME TEXT")
        note(qdir, rest[0], " ".join(rest[1:]))
    elif cmd == "forget":
        forget(qdir, rest[0])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
