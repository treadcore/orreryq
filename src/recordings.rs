//! Results, Recordings: the behaviour-cloning recordings, what each costs on its store, whether its
//! recipe can make it again, who still reads it -- and a reader, one seed's samples, a tank at a time.
//!
//! Paul, 4 November: "can we have this feature not eat up my storage space, have it clean up when
//! done ... I like the idea of a mechanism to debug if necessary." The document is
//! `tools/recordings.py list` (QUEUE/plan/recordings.json). A RECORDING IS A FUNCTION OF ITS BINARY AND
//! ITS SEEDS, so a run whose recipe is complete (every shard hashed, every binary saved, one shard a
//! binary re-recorded equal) loses nothing when its shards go: the sweep drops them once nothing reads
//! them. Keep for analysis holds one run; Settings, Long run, "Keep every recording" holds them all.
//! THE PAGE DRAWS AND ASKS; the verbs are `fleet-queue.py QUEUE recordings ...`. Buttons are drawn
//! for an operator only, and Drop takes two presses, the second saying the gigabytes.
//!
//! THE READER is honest about what a sample is. A TCBC2 or TCBC3 sample carries its seed but not its
//! seat or its tick, so recordings.py follows each tank by where it is (the instruments' X and Y) and
//! counts a round when the nearest tank is one already seen. A respawn far from where the tank died
//! is a new track. The page says "reconstructed", and the tip says how.
use crate::draw::Rgb;
use crate::font::{F6X10, F8X13};
use crate::json::{self, Value};
use crate::ui::{rect, Rect, Ui};
use std::io::{Read, Seek, SeekFrom};
use std::sync::Mutex;

/// What the page remembers between frames.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct State {
    /// The run selected in the list, by name.
    pub sel: String,
    /// The list's scroll.
    pub off: usize,
    /// Drop pressed once, for this run: the second press drops.
    pub arm_drop: Option<String>,
    /// The seed the reader asks for next (None: the run's first).
    pub seed: Option<i64>,
    /// The reader's tank and its place along it.
    pub track: usize,
    pub step: usize,
    /// The reader's tank list scroll.
    pub toff: usize,
}

fn s(v: &Value, k: &str) -> String {
    match v.get(k) {
        Some(Value::Str(x)) => x.clone(),
        Some(Value::Num(x)) => format!("{}", x),
        _ => String::new(),
    }
}
fn n(v: &Value, k: &str) -> f64 {
    v.get(k).and_then(|x| x.as_num()).unwrap_or(0.0)
}
fn arr<'a>(v: &'a Value, k: &str) -> &'a [Value] {
    v.get(k).and_then(|x| x.as_array()).map(|a| &a[..]).unwrap_or(&[])
}
fn gb(b: f64) -> String {
    if b >= 1e9 {
        format!("{:.1} GB", b / 1e9)
    } else if b >= 1e6 {
        format!("{:.0} MB", b / 1e6)
    } else {
        format!("{:.0} KB", b / 1e3)
    }
}

pub fn draw(ui: &mut Ui, at: Rect, doc: Option<&Value>, st: &mut State, operator: bool, ctl: &mut Option<String>) {
    let t = ui.t;
    let Some(doc) = doc.filter(|d| !matches!(d, Value::Null)) else {
        ui.label_in(at.x, at.y, at.w, "No list yet: tools/recordings.py QUEUE list writes plan/recordings.json (treadcore-view.py starts it each half hour, or run it by hand).", &F8X13, t.dim);
        return;
    };
    let runs = arr(doc, "runs");
    let keep_all = doc.get("keep_all").and_then(|x| x.as_bool()).unwrap_or(false);
    let head = format!(
        "{} runs; {} of shards on the stores; {} of binaries keep every recipe; {}",
        runs.len(),
        gb(n(doc, "bytes_now")),
        gb(n(doc, "bytes_recipe")),
        if keep_all { "KEEP EVERY RECORDING is on (Settings, Long run)" } else { "a run's shards go once nothing reads them" }
    );
    let mut right = at.right();
    if operator {
        for (label, verb) in [("Sweep now", "recordings sweep --do"), ("List again", "recordings list")] {
            let w = F8X13.measure(label) as i32 + 24;
            if ui.button(rect(right - w, at.y, w, 22), label, true) {
                *ctl = Some(verb.to_string());
            }
            right -= w + 6;
        }
    }
    ui.label_in(at.x, at.y + 5, right - at.x - 8, &head, &F8X13, if keep_all { t.warn } else { t.dim });
    // ---- the list ----
    let lh = F8X13.height as i32 + 6;
    let list_h = (lh * (runs.len() as i32 + 1) + 4).min(at.h / 3).max(lh * 3);
    let list = rect(at.x, at.y + 28, at.w, list_h);
    ui.well(list);
    let cols = [("run", 0), ("state", 110), ("now", 260), ("made", 340), ("kind", 480), ("seeds", 590), ("recipe", 680), ("why kept", 980)];
    for (h, x) in cols {
        ui.label(list.x + 6 + x, list.y + 3, h, &F6X10, t.dim);
    }
    let body = rect(list.x, list.y + lh, list.w, list.h - lh);
    let (area, first, count) = ui.scroll_list(body, runs.len(), lh, &mut st.off);
    if st.sel.is_empty() {
        st.sel = runs.first().map(|r| s(r, "run")).unwrap_or_default();
    }
    for (i, r) in runs.iter().enumerate().skip(first).take(count) {
        let y = area.y + (i - first) as i32 * lh;
        let row = rect(area.x, y, area.w, lh);
        let name = s(r, "run");
        if name == st.sel {
            ui.c.rect(row.x + 1, row.y, row.w - 2, row.h, t.tile);
        }
        if ui.button_hit(row) {
            st.sel = name.clone();
            st.arm_drop = None;
            st.seed = None;
        }
        let state = s(r, "state");
        let sc: Rgb = match state.as_str() {
            "on the store" => t.ink,
            "read now" => t.up,
            s if s.starts_with("kept") => t.warn,
            _ => t.dim,
        };
        let recipe = s(r, "recipe");
        let kind = format!("{} {}", s(r, "format"), if n(r, "senses") > 0.0 { format!("{} senses", n(r, "senses")) } else { String::new() });
        let seeds = if n(r, "seeds") > 0.0 { format!("{}", n(r, "seeds")) } else { "-".to_string() };
        let why = arr(r, "readers").iter().filter_map(|x| x.as_str()).collect::<Vec<_>>().join("; ");
        let cells: [(String, i32, Rgb); 8] = [
            (name.clone(), 0, t.ink),
            (state.clone(), 110, sc),
            (if n(r, "bytes_now") > 0.0 { gb(n(r, "bytes_now")) } else { "-".into() }, 260, t.ink),
            (s(r, "made").replace('T', " "), 340, t.dim),
            (kind, 480, t.dim),
            (seeds, 590, t.dim),
            (if recipe.is_empty() { "none yet".into() } else { recipe.clone() }, 680, if recipe == "complete" { t.up } else { t.dim }),
            (why, 980, t.dim),
        ];
        for (k, (text, x, c)) in cells.iter().enumerate() {
            let w = cells.get(k + 1).map(|n| n.1 - x - 8).unwrap_or(row.w - x - 12);
            ui.label_in(row.x + 6 + x, y + 3, w, text, &F8X13, *c);
        }
        let (rname, rc, rs, bytes, proofs, bins) = (name.clone(), recipe.clone(), state.clone(), n(r, "bytes"), n(r, "proofs"), n(r, "binaries"));
        let commit = s(r, "commit");
        ui.tip(row, move || vec![
            format!("{}: {}", rname, rs),
            format!("Recipe: {} -- {} binaries, {} proved by a re-recording; {} when it was whole; commit {}", if rc.is_empty() { "none yet".to_string() } else { rc }, bins, proofs, gb(bytes), commit),
            "A recipe is complete when every shard is hashed, every binary is saved in the archive, and one shard a binary has been re-recorded equal. Only then is a shard dropped.".to_string(),
        ]);
    }
    // ---- the selected run's verbs ----
    let mut y = list.bottom() + 8;
    let Some(r) = runs.iter().find(|r| s(r, "run") == st.sel) else {
        return;
    };
    let name = s(r, "run");
    let kept = r.get("kept").and_then(|x| x.as_bool()).unwrap_or(false);
    let now = if n(r, "shards_now") > 0.0 { n(r, "bytes_now") } else { 0.0 };
    let complete = s(r, "recipe") == "complete";
    let (lo, hi) = (n(r, "seed_lo") as i64, n(r, "seed_hi") as i64);
    let seed = st.seed.unwrap_or(lo).clamp(lo, hi.max(lo));
    let mut x = at.x;
    ui.label(x, y + 5, &format!("{}:", name), &F8X13, t.ink);
    x += F8X13.measure(&name) as i32 + 16;
    if operator {
        let mut verbs: Vec<(String, String, bool)> = vec![(
            if kept { "Unkeep".to_string() } else { "Keep for analysis".to_string() },
            format!("recordings {} {}", if kept { "unkeep" } else { "keep" }, name),
            true,
        )];
        if now > 0.0 && !kept {
            let armed = st.arm_drop.as_deref() == Some(name.as_str());
            verbs.push((if armed { format!("Drop now: {}", gb(now)) } else { "Drop shards...".to_string() }, if armed { format!("recordings drop {} --do", name) } else { String::new() }, complete));
        }
        if now == 0.0 && complete {
            verbs.push(("Re-record".to_string(), format!("recordings rerecord {}", name), true));
        }
        for (label, verb, enabled) in verbs {
            let w = F8X13.measure(&label) as i32 + 24;
            if ui.button(rect(x, y, w, 22), &label, enabled) {
                if verb.is_empty() {
                    st.arm_drop = Some(name.clone());
                } else {
                    *ctl = Some(verb);
                    st.arm_drop = None;
                }
            }
            x += w + 6;
        }
    }
    // The reader's seed, and the press that reads it.
    if hi >= lo && lo > 0 {
        x += 12;
        for (label, d) in [("<", -1i64), (">", 1)] {
            if ui.button(rect(x, y, 26, 22), label, true) {
                st.seed = Some((seed + d).clamp(lo, hi));
            }
            x += 30;
        }
        let label = format!("Read seed {}", seed);
        let w = F8X13.measure(&label) as i32 + 24;
        if ui.button(rect(x, y, w, 22), &label, true) {
            *ctl = Some(format!("recordings read {} {}", name, seed));
            st.track = 0;
            st.step = 0;
        }
        x += w + 8;
        let note = if now > 0.0 { "from the shard on its store" } else { "its shard re-recorded from the recipe, read, and deleted (a minute)" };
        ui.label_in(x, y + 5, at.right() - x, note, &F6X10, t.dim);
    }
    y += 30;
    // ---- the reader ----
    let read = doc.get("read").filter(|v| !matches!(v, Value::Null));
    if let Some(rd) = read {
        let path = s(rd, "json");
        reader(ui, rect(at.x, y, at.w, at.bottom() - y), &path, st);
    } else {
        ui.label_in(at.x, y, at.w, "No seed read yet: pick a run with a recipe or shards, and Read seed.", &F8X13, t.dim);
    }
}

// ---- the reader ------------------------------------------------------------------------------

struct Cache {
    path: String,
    stamp: std::time::SystemTime,
    doc: Value,
    cur: Option<(usize, Vec<f32>)>,
}

static CACHE: Mutex<Option<Cache>> = Mutex::new(None);

const SECTOR: [&str; 8] = ["ahead", "ahead right", "right", "behind right", "behind", "behind left", "left", "ahead left"];
const DRONE: [&str; 5] = ["-", "interceptor", "recon", "strike", "other"];
const SQUAD: [&str; 7] = ["-", "capture", "build", "repair", "harvest", "mine", "return"];
const LEAD: [&str; 3] = ["at the tank", "at its lead", "between"];

fn sector(v: i64) -> String {
    if v >= 1 && v <= 8 {
        SECTOR[(v - 1) as usize].to_string()
    } else {
        "-".to_string()
    }
}

fn bits(m: i64, names: &[&str]) -> String {
    let v: Vec<&str> = (0..names.len()).filter(|k| m & (1 << k) != 0).map(|k| names[k]).collect();
    if v.is_empty() { "none".to_string() } else { v.join(", ") }
}

fn reader(ui: &mut Ui, at: Rect, path: &str, st: &mut State) {
    let t = ui.t;
    let mut guard = CACHE.lock().unwrap_or_else(|e| e.into_inner());
    let stamp = std::fs::metadata(path).and_then(|m| m.modified()).ok();
    let fresh = matches!((&*guard, stamp), (Some(c), Some(s)) if c.path == path && c.stamp == s);
    if !fresh {
        let Some(stamp) = stamp else {
            ui.label_in(at.x, at.y, at.w, &format!("The read is not on this machine ({}).", path), &F8X13, t.dim);
            return;
        };
        let doc = std::fs::read_to_string(path).ok().and_then(|x| json::parse(&x).ok()).unwrap_or(Value::Null);
        *guard = Some(Cache { path: path.to_string(), stamp, doc, cur: None });
    }
    let c = guard.as_mut().unwrap();
    let doc = &c.doc;
    let tracks = arr(doc, "tracks");
    let samples = arr(doc, "samples");
    let names: Vec<String> = arr(doc, "names").iter().filter_map(|x| x.as_str().map(str::to_string)).collect();
    let senses = n(doc, "senses") as usize;
    if tracks.is_empty() || samples.is_empty() {
        ui.label_in(at.x, at.y, at.w, "The read holds no samples.", &F8X13, t.dim);
        return;
    }
    let title = format!(
        "{} seed {}: {} samples, {} tanks followed over about {} ticks -- RECONSTRUCTED: a {} sample has no seat or tick, so a tank is followed by where it is; {}",
        s(doc, "run"),
        s(doc, "seed"),
        samples.len(),
        tracks.len(),
        s(doc, "rounds"),
        s(doc, "format"),
        s(doc, "where")
    );
    ui.label_in(at.x, at.y, at.w, &title, &F6X10, t.dim);
    let y0 = at.y + 16;
    // The tanks.
    let lh = F8X13.height as i32 + 4;
    let list = rect(at.x, y0, 190, at.bottom() - y0);
    ui.well(list);
    st.track = st.track.min(tracks.len() - 1);
    let (area, first, count) = ui.scroll_list(list.inset(2), tracks.len(), lh, &mut st.toff);
    for (k, tr) in tracks.iter().enumerate().skip(first).take(count) {
        let row = rect(area.x, area.y + (k - first) as i32 * lh, area.w, lh);
        if k == st.track {
            ui.c.rect(row.x, row.y, row.w, row.h, t.tile);
        }
        if ui.button_hit(row) {
            st.track = k;
            st.step = 0;
        }
        let len = tr.as_array().map(|a| a.len()).unwrap_or(0);
        ui.label_in(row.x + 4, row.y + 2, row.w - 8, &format!("tank {}: {} samples", k + 1, len), &F8X13, if k == st.track { t.ink } else { t.dim });
    }
    let track: Vec<usize> = tracks[st.track].as_array().map(|a| a.iter().filter_map(|x| x.as_num()).map(|x| x as usize).collect()).unwrap_or_default();
    if track.is_empty() {
        return;
    }
    st.step = st.step.min(track.len() - 1);
    // Steps through the tank's samples.
    let mut x = list.right() + 12;
    let mut y = y0;
    for (label, d) in [("<< 25", -25i64), ("<", -1), (">", 1), (">> 25", 25)] {
        let w = F8X13.measure(label) as i32 + 18;
        if ui.button(rect(x, y, w, 22), label, true) {
            st.step = (st.step as i64 + d).clamp(0, track.len() as i64 - 1) as usize;
        }
        x += w + 4;
    }
    let i = track[st.step];
    let sx = list.right() + 400;
    ui.label_in(x + 8, y + 5, at.right() - x - 8, &format!("sample {} of the tank's {} (row {} of the seed); about {:.1} s into its track", st.step + 1, track.len(), i, st.step as f64 * 0.2), &F8X13, t.ink);
    y += 30;
    // The choices the scripted brain made in that fifth of a second, and what it was allowed.
    let smp: Vec<i64> = samples[i].as_array().map(|a| a.iter().map(|x| x.as_num().unwrap_or(0.0) as i64).collect()).unwrap_or_default();
    let pos = samples[i].as_array().map(|a| (a[0].as_num().unwrap_or(0.0), a[1].as_num().unwrap_or(0.0))).unwrap_or((0.0, 0.0));
    let g = |k: usize| smp.get(k).copied().unwrap_or(0);
    let lines = [
        format!("where: {:.3} across, {:.3} down the map", pos.0, pos.1),
        format!("drive: {}", if g(2) == 9 { "holding still".to_string() } else { sector(g(2)) }),
        format!("gun: {}{}", sector(g(3)), if g(3) > 0 { format!(", aimed {}", LEAD.get(g(4) as usize).unwrap_or(&"-")) } else { String::new() }),
        format!("mortar: {}", sector(g(5))),
        format!("drone: {}", DRONE.get(g(6) as usize).unwrap_or(&"-")),
        format!("squad: {}", SQUAD.get(g(7) as usize).unwrap_or(&"-")),
        format!("gun allowed: {}", bits(g(9), &SECTOR)),
        format!("mortar allowed: {}", bits(g(10), &SECTOR)),
        format!("drones allowed: {}", bits(g(11), &DRONE[1..])),
        if smp.len() > 12 { format!("squad allowed: {}", bits(g(12), &SQUAD[1..])) } else { "squad allowed: not in a TCBC2 sample".to_string() },
    ];
    for l in &lines {
        ui.label(list.right() + 12, y, l, &F8X13, t.ink);
        y += lh;
    }
    // The senses, from the read's floats.
    let bin = s(doc, "bin");
    if c.cur.as_ref().map(|x| x.0) != Some(i) {
        let mut buf = vec![0u8; senses * 4];
        let ok = std::fs::File::open(&bin).and_then(|mut f| {
            f.seek(SeekFrom::Start((i * senses * 4) as u64))?;
            f.read_exact(&mut buf)
        });
        if ok.is_ok() {
            c.cur = Some((i, buf.chunks(4).map(|b| f32::from_le_bytes([b[0], b[1], b[2], b[3]])).collect()));
        }
    }
    let Some((_, xs)) = &c.cur else {
        return;
    };
    let sw = at.right() - sx;
    if sw < 200 {
        return;
    }
    // The compass: a column a sector, a row a channel, brighter the stronger.
    let chans = names.iter().take_while(|n| n.starts_with("s0 ")).count().max(1);
    let sectors = 8usize;
    let cell_w = ((sw - 140) / sectors as i32).clamp(14, 40);
    let cell_h = 12;
    let mut yy = y0 + 30;
    ui.label(sx, yy, "the compass (columns: ahead, then clockwise)", &F6X10, t.dim);
    yy += 14;
    for ch in 0..chans {
        let cname = names.get(ch).map(|n| n.trim_start_matches("s0 ").to_string()).unwrap_or_default();
        ui.label_in(sx, yy, 136, &cname, &F6X10, t.dim);
        for sec in 0..sectors {
            let k = sec * chans + ch;
            let v = xs.get(k).copied().unwrap_or(0.0).clamp(0.0, 1.0);
            let g = (40.0 + 200.0 * v) as u32;
            let col: Rgb = (((g / 4) << 16) | (g << 8) | (g / 3)) as Rgb;
            let r = rect(sx + 140 + sec as i32 * cell_w, yy, cell_w - 2, cell_h - 2);
            ui.c.rect(r.x, r.y, r.w, r.h, col);
            let label = format!("{} = {:.3}", names.get(k).cloned().unwrap_or_default(), xs.get(k).copied().unwrap_or(0.0));
            ui.tip(r, move || vec![label]);
        }
        yy += cell_h;
    }
    // The rest as bars, a row each.
    yy += 8;
    let start = sectors * chans;
    let per_row = ((at.bottom() - yy) / 11).max(1) as usize;
    let cols = ((senses.saturating_sub(start)) + per_row - 1) / per_row.max(1);
    let colw = (sw / cols.max(1) as i32).max(120);
    for k in start..senses {
        let j = k - start;
        let (cx, cy) = (sx + (j / per_row) as i32 * colw, yy + (j % per_row) as i32 * 11);
        let v = xs.get(k).copied().unwrap_or(0.0);
        let name = names.get(k).cloned().unwrap_or_else(|| format!("sense {}", k));
        ui.label_in(cx, cy, colw - 64, &name, &F6X10, t.dim);
        let bw = ((v.abs().min(1.0)) * 50.0) as i32;
        ui.c.rect(cx + colw - 60, cy + 2, 52, 7, t.line);
        ui.c.rect(cx + colw - 60, cy + 2, bw.max(1), 7, if v < 0.0 { t.warn } else { t.up });
        let label = format!("{} = {:.3}", name, v);
        ui.tip(rect(cx, cy, colw - 4, 11), move || vec![label]);
    }
}
