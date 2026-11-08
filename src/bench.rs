//! The Bench view: a machine's spare disks, which layout of them is fastest, and a run as it happens.
//!
//! Paul, 7 November, after calber's six SATA SSDs were built thirteen ways and measured: "design the auto
//! report or the way which the information gets back to orrery in a new visualization screen. now we have
//! the data format, can we improve its usage." `tools/disk-bench.py` measures on the machine, as root, typed
//! by a person; `tools/disk-report.py status` brings each machine's results and its run's progress back as
//! one document; this draws it. The lab report's charts come from the same table (`disk-report.py draw`),
//! so the screen and the report cannot disagree.
//!
//! WHAT IT SHOWS, top to bottom: the run now (its layout, its step, done of planned, the time left); the
//! verdict for each use, a tile each; every layout on one chart, each measure a multiple of one disk; the
//! conclusion matrix, the best of each measure marked; and the machine's spare disks, with what each holds.
//!
//! COLOUR IS THE TECHNOLOGY, never the rank: mdadm blue, ZFS orange, btrfs aqua, one disk gray, the report's
//! three hues. The best is the theme's "up" green with a ●, the worst its alarm colour: status, never a
//! series colour.
//!
//! NOTHING HERE FORMATS A DISK. Orrery holds no root on a machine. Inspect and Run copy the bench there and
//! type its command into the machine's Sessions tile (the handoff Apply and the Storage view use); the
//! person types the sudo password, and Run asks twice and names the disks first. The bench itself refuses
//! a disk that is mounted, the system's or swap, and finds its disks by serial, never by device name.

use crate::draw::{mix, Rgb};
use crate::font::{F10X20, F6X10, F8X13};
use crate::json;
use crate::nav;
use crate::ui::{rect, Rect, Ui};

const PAD: i32 = 10;

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Measure {
    pub key: String,
    pub label: String,
    pub unit: String,
    pub higher: bool,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Layout {
    pub name: String,
    pub tech: String,
    pub values: Vec<Option<f64>>,
    pub ratios: Vec<Option<f64>>,
    /// Repeated trials: (lowest, highest, trials) a measure.
    pub spread: Vec<Option<(f64, f64, i64)>>,
    pub usable_gb: f64,
    pub can_lose: i64,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Progress {
    pub state: String,
    pub kind: String,
    pub current: String,
    pub step: String,
    pub done: usize,
    pub plan: usize,
    pub failed: Vec<String>,
    pub eta: f64,
    pub updated: f64,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Spare {
    pub serial: String,
    pub dev: String,
    pub gb: i64,
    pub model: String,
    pub holds: Vec<String>,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Machine {
    pub host: String,
    pub error: String,
    pub progress: Progress,
    pub spare: Vec<Spare>,
    pub chosen: Vec<String>,
    pub measures: Vec<Measure>,
    pub layouts: Vec<Layout>,
    /// The best layout of each measure, by key.
    pub best: Vec<(String, String)>,
    /// (use, layout, multiple of one disk).
    pub winners: Vec<(String, String, f64)>,
    /// (layout, MB/s each second, GB written when the fast cache ran out).
    pub cliffs: Vec<(String, Vec<f64>, Option<f64>)>,
    pub runs: Vec<String>,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Model {
    pub machines: Vec<Machine>,
    /// Why there is nothing to show, when there is nothing.
    pub why: String,
}

fn s(v: &json::Value, k: &str) -> String {
    v.get(k).and_then(|x| x.as_str()).unwrap_or("").to_string()
}

fn n(v: &json::Value, k: &str) -> f64 {
    v.get(k).and_then(|x| x.as_num()).unwrap_or(0.0)
}

fn arr<'a>(v: &'a json::Value, k: &str) -> &'a [json::Value] {
    v.get(k).and_then(|x| x.as_array()).unwrap_or(&[])
}

impl Model {
    pub fn parse(text: &str) -> Model {
        let doc = match json::parse(text.trim()) {
            Ok(d) => d,
            Err(_) if text.trim().is_empty() => return Model { why: "asking disk-report.py for the benches...".into(), ..Model::default() },
            Err(_) => return Model { why: text.lines().last().unwrap_or("").to_string(), ..Model::default() },
        };
        let mut m = Model::default();
        for x in arr(&doc, "machines") {
            let p = x.get("progress");
            let progress = p
                .map(|p| Progress {
                    state: s(p, "state"),
                    kind: s(p, "kind"),
                    current: s(p, "current"),
                    step: s(p, "step"),
                    done: arr(p, "done").len(),
                    plan: arr(p, "plan").len(),
                    failed: arr(p, "failed").iter().filter_map(|f| f.as_str().map(String::from)).collect(),
                    eta: n(p, "eta"),
                    updated: n(p, "updated"),
                })
                .unwrap_or_default();
            let mut mc = Machine {
                host: s(x, "host"),
                error: s(x, "error"),
                progress,
                spare: arr(x, "spare")
                    .iter()
                    .map(|d| Spare {
                        serial: s(d, "serial"),
                        dev: s(d, "dev"),
                        gb: n(d, "GB") as i64,
                        model: s(d, "model"),
                        holds: arr(d, "holds").iter().filter_map(|h| h.as_str().map(String::from)).collect(),
                    })
                    .collect(),
                chosen: arr(x, "chosen").iter().filter_map(|c| c.as_str().map(String::from)).collect(),
                ..Machine::default()
            };
            if let Some(sm) = x.get("summary") {
                mc.measures = arr(sm, "measures")
                    .iter()
                    .map(|q| Measure { key: s(q, "key"), label: s(q, "label"), unit: s(q, "unit"), higher: q.get("higher").and_then(|b| b.as_bool()).unwrap_or(true) })
                    .collect();
                let nums = |v: &json::Value, k: &str| -> Vec<Option<f64>> { arr(v, k).iter().map(|e| e.as_num()).collect() };
                mc.layouts = arr(sm, "layouts")
                    .iter()
                    .map(|l| Layout {
                        name: s(l, "name"),
                        tech: s(l, "tech"),
                        values: nums(l, "values"),
                        ratios: nums(l, "ratios"),
                        spread: arr(l, "spread")
                            .iter()
                            .map(|e| e.as_array().filter(|a| a.len() == 3).map(|a| (a[0].as_num().unwrap_or(0.0), a[1].as_num().unwrap_or(0.0), a[2].as_i64().unwrap_or(0))))
                            .collect(),
                        usable_gb: n(l, "usable_GB"),
                        can_lose: n(l, "can_lose") as i64,
                    })
                    .collect();
                if let Some(json::Value::Obj(b)) = sm.get("best") {
                    mc.best = b.iter().map(|(k, v)| (k.clone(), v.as_str().unwrap_or("").to_string())).collect();
                }
                mc.winners = arr(sm, "winners").iter().map(|w| (s(w, "use"), s(w, "layout"), n(w, "score"))).collect();
                mc.cliffs = arr(sm, "cliffs")
                    .iter()
                    .map(|c| (s(c, "layout"), arr(c, "MBps").iter().filter_map(|v| v.as_num()).collect(), c.get("cliff_GB").and_then(|v| v.as_num())))
                    .collect();
                mc.runs = arr(sm, "runs").iter().filter_map(|r| r.as_str().map(String::from)).collect();
            }
            m.machines.push(mc);
        }
        if m.machines.is_empty() {
            m.why = "No bench has run yet. Put tools/disk-bench.py on a machine (Inspect below, once a machine has disks.txt) and run it.".into();
        }
        m
    }
}

/// What the person asked for: the bench copied to a machine and its command typed in its Sessions tile.
#[derive(Debug, Clone, PartialEq)]
pub enum Ask {
    Stage { host: String, what: String },
}

#[derive(Debug, Clone, Default)]
pub struct State {
    pub sel: String,
    pub operator: bool,
    /// Run pressed once: the disks it would erase are named, and a second press stages it.
    pub armed: bool,
    pub said: String,
    pub ask: Option<Ask>,
}

impl State {
    pub fn new(operator: bool) -> State {
        State { operator, ..State::default() }
    }
}

/// The report's three hues and its gray, the light or the dark steps by the theme's base.
fn hue(ui: &Ui, tech: &str) -> Rgb {
    let b = ui.t.base;
    let lum = ((b >> 16) & 255) * 3 + ((b >> 8) & 255) * 6 + (b & 255);
    let dark = lum < 1280;
    match (tech, dark) {
        ("md", false) => 0x2a78d6,
        ("md", true) => 0x3987e5,
        ("zfs", false) => 0xeb6834,
        ("zfs", true) => 0xd95926,
        ("btrfs", false) => 0x1baf7a,
        ("btrfs", true) => 0x199e70,
        (_, false) => 0x6f6d66,
        (_, true) => 0xa3a197,
    }
}

/// A line two pixels wide, Bresenham's (growth.rs has the one-pixel one).
fn seg(ui: &mut Ui, (x0, y0): (i32, i32), (x1, y1): (i32, i32), c: Rgb, dashed: bool) {
    let (dx, dy) = ((x1 - x0).abs(), -(y1 - y0).abs());
    let (sx, sy) = (if x0 < x1 { 1 } else { -1 }, if y0 < y1 { 1 } else { -1 });
    let (mut x, mut y, mut err) = (x0, y0, dx + dy);
    for i in 0..4096 {
        if !dashed || (i / 5) % 2 == 0 {
            ui.c.set(x, y, c);
            ui.c.set(x, y + 1, c);
        }
        if x == x1 && y == y1 {
            break;
        }
        let e2 = 2 * err;
        if e2 >= dy {
            err += dy;
            x += sx;
        }
        if e2 <= dx {
            err += dx;
            y += sy;
        }
    }
}

fn fmt(v: f64, unit: &str) -> String {
    if unit == "s" {
        format!("{:.2} s", v)
    } else if v >= 10000.0 {
        format!("{:.0}k {}", v / 1000.0, unit)
    } else {
        format!("{:.0} {}", v, unit)
    }
}

fn short(v: f64, unit: &str) -> String {
    if unit == "s" {
        format!("{:.2}", v)
    } else if v >= 10000.0 {
        format!("{:.0}k", v / 1000.0)
    } else {
        format!("{:.0}", v)
    }
}

/// The bench's step, as a person says it: fio's job names are short codes.
fn step_words(s: &str) -> &str {
    match s {
        "build" => "building the layout",
        "seqw" => "sequential write",
        "seqr" => "sequential read",
        "wr" => "write, then read back",
        "rr" => "4K reads, many threads",
        "rw" => "4K writes",
        "mx" => "70/30 mix",
        "sw" => "sync writes",
        "front" | "back" => "two streams",
        "b" => "block sizes",
        "q" => "queue depths",
        "w" | "r" => "each disk, raw",
        other => other,
    }
}

fn now() -> f64 {
    std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_secs_f64()).unwrap_or(0.0)
}

pub fn draw(ui: &mut Ui, m: &Model, st: &mut State) -> Option<nav::View> {
    let t = ui.t;
    let (rest, go, _) = nav::header(ui, nav::View::Bench, !st.armed, "which layout of a machine's spare disks is fastest", None);
    let body = rest.inset(PAD);
    if m.machines.is_empty() {
        ui.label_in(body.x, body.y + 8, body.w, &m.why, &F8X13, t.dim);
        return go;
    }
    if st.sel.is_empty() || !m.machines.iter().any(|x| x.host == st.sel) {
        st.sel = m.machines[0].host.clone();
    }
    let mc = m.machines.iter().find(|x| x.host == st.sel).unwrap_or(&m.machines[0]);
    let mut y = body.y;
    // The machines, a button each, when there is more than one.
    let mut x = body.x;
    ui.label(x, y + 2, "Bench:", &F10X20, t.ink);
    x += F10X20.measure("Bench: ") as i32 + 4;
    for other in &m.machines {
        let w = F8X13.measure(&other.host) as i32 + 20;
        if ui.button(rect(x, y, w, 24), &other.host, other.host != mc.host) {
            st.sel = other.host.clone();
            st.armed = false;
        }
        x += w + 6;
    }
    let runs = if mc.runs.is_empty() { "no runs yet".to_string() } else { format!("{} run(s): {}", mc.runs.len(), mc.runs.join(", ")) };
    ui.label_in(x + 8, y + 6, body.right() - x - 8, &runs, &F8X13, t.dim);
    y += 32;
    y = live(ui, rect(body.x, y, body.w, 40), mc) + 8;
    if mc.layouts.is_empty() {
        ui.label_in(body.x, y, body.w, "No results yet for this machine.", &F8X13, t.dim);
        spares(ui, rect(body.x, y + 24, body.w, body.bottom() - y - 24), mc, st);
        return go;
    }
    y = tiles(ui, rect(body.x, y, body.w, 56), mc) + 10;
    let left = (body.w * 58 / 100).max(420);
    let ch = 250.min(body.bottom() - y - 140).max(160);
    overlay(ui, rect(body.x, y, left, ch), mc);
    cliff(ui, rect(body.x + left + 12, y, body.w - left - 12, ch), mc);
    y += ch + 12;
    let mh = 52 + 17 * mc.layouts.len() as i32;
    let mh = mh.min(body.bottom() - y - 70).max(80);
    matrix(ui, rect(body.x, y, body.w, mh), mc);
    y += mh + 10;
    spares(ui, rect(body.x, y, body.w, body.bottom() - y), mc, st);
    go
}

/// The run now: its layout, its step, done of planned, the time left. Gone quiet for a minute is said.
fn live(ui: &mut Ui, r: Rect, mc: &Machine) -> i32 {
    let t = ui.t;
    let p = &mc.progress;
    ui.c.rect(r.x, r.y, r.w, r.h, t.tile);
    let running = p.state == "running";
    let serving = p.state == "serving";
    let lamp = if running || serving { t.up } else { t.dim };
    ui.c.disc(r.x + 12, r.y + 13, 5, lamp);
    let line = if running {
        let left = ((p.eta - now()) / 60.0).max(0.0);
        let quiet = now() - p.updated;
        format!(
            "{} on {}: {} · {} · {} of {} done · about {:.0} min left{}",
            if p.kind == "barrage" { "Barrage" } else { "Running" },
            mc.host,
            p.current,
            step_words(&p.step),
            p.done,
            p.plan,
            left,
            if quiet > 120.0 { format!(" · no word for {:.0} min", quiet / 60.0) } else { String::new() }
        )
    } else if serving {
        // The disks hold a share other machines have mounted: a run now would erase it under them, so the
        // Run button below is held while this line is lit, and the share is ended on the machine itself.
        format!("Sharing on {}: {} at {}:/mnt/bench, measured from the machines that mount it (nfs-client-bench.py)",
                mc.host, p.current, mc.host)
    } else if p.state.is_empty() {
        format!("Nothing running on {}.{}", mc.host, if mc.error.is_empty() { String::new() } else { format!(" {}", mc.error) })
    } else {
        format!("Last run on {}: {}, {} of {} done{}.", mc.host, p.state, p.done, p.plan,
                if p.failed.is_empty() { String::new() } else { format!(", failed: {}", p.failed.join(", ")) })
    };
    ui.label_in(r.x + 24, r.y + 6, r.w - 32, &line, &F8X13, if running || serving { t.ink } else { t.dim });
    if p.plan > 0 {
        let w = r.w - 32;
        let y = r.y + r.h - 12;
        ui.c.rect(r.x + 24, y, w, 5, mix(t.tile, t.line, 160));
        ui.c.rect(r.x + 24, y, w * p.done as i32 / p.plan as i32, 5, if running { t.up } else { t.dim });
    }
    r.bottom()
}

/// A tile a use: its winner and how many times one disk it is.
fn tiles(ui: &mut Ui, r: Rect, mc: &Machine) -> i32 {
    let t = ui.t;
    let k = mc.winners.len().max(1) as i32;
    let w = (r.w - 10 * (k - 1)) / k;
    for (i, (u, l, sc)) in mc.winners.iter().enumerate() {
        let x = r.x + i as i32 * (w + 10);
        ui.c.rect(x, r.y, w, r.h, t.tile);
        ui.c.rect(x, r.y, 4, r.h, t.up);
        ui.label_in(x + 12, r.y + 6, w - 16, &format!("Best for {}", u), &F8X13, t.dim);
        // label() returns where the next letter would go, not a width.
        let end = ui.label(x + 12, r.y + 24, l, &F10X20, t.ink);
        ui.label(end + 10, r.y + 30, &format!("{:.2}× one disk", sc), &F8X13, t.up);
        let tip_u = u.clone();
        let tip_l = l.clone();
        ui.tip(rect(x, r.y, w, r.h), move || {
            vec![
                format!("{}: {}", tip_u, tip_l),
                "A weighted geometric mean of the measures this use leans on, each as a multiple of one disk.".into(),
                "A share must survive a lost disk, so layouts without redundancy cannot win it.".into(),
            ]
        });
    }
    r.bottom()
}

/// Every layout on one chart: each measure a multiple of one disk, log scale, above the line better.
fn overlay(ui: &mut Ui, r: Rect, mc: &Machine) {
    let t = ui.t;
    ui.c.rect(r.x, r.y, r.w, r.h, t.tile);
    ui.label(r.x + 8, r.y + 4, "Every layout, each measure as a multiple of one disk", &F8X13, t.ink);
    let (l, rt, top, bot) = (r.x + 44, r.right() - 12, r.y + 24, r.bottom() - 56);
    let ms = mc.measures.len().max(2);
    let (mut lo, mut hi) = (-2i32, 3i32);
    for la in &mc.layouts {
        for v in la.ratios.iter().flatten() {
            lo = lo.min(v.log2().floor() as i32);
            hi = hi.max(v.log2().ceil() as i32);
        }
    }
    let xof = |i: usize| l + (i as i32) * (rt - l) / (ms as i32 - 1);
    let yof = |v: f64| top + (((hi as f64) - v.log2()) / ((hi - lo) as f64) * (bot - top) as f64) as i32;
    for e in lo..=hi {
        let y = yof(2f64.powi(e));
        ui.c.hline(l, y, rt - l, if e == 0 { t.dim } else { mix(t.tile, t.line, 140) });
        let lab = if e >= 0 { format!("{}×", 1i64 << e) } else { format!("1/{}", 1i64 << -e) };
        ui.c.text_right(l - 4, y - 5, &lab, &F6X10, t.dim);
    }
    for (i, q) in mc.measures.iter().enumerate() {
        let x = xof(i);
        ui.c.vline(x, top, bot - top, mix(t.tile, t.line, 100));
        let w = F6X10.measure(&q.label) as i32;
        ui.c.text(x - w / 2, bot + 6 + (i as i32 % 2) * 12, &q.label, &F6X10, t.dim);
    }
    for la in &mc.layouts {
        let c = hue(ui, &la.tech);
        let dashed = la.name.starts_with("pair") || la.name == "single";
        let pts: Vec<(i32, i32, usize)> = la.ratios.iter().enumerate().filter_map(|(i, v)| v.map(|v| (xof(i), yof(v), i))).collect();
        for w in pts.windows(2) {
            seg(ui, (w[0].0, w[0].1), (w[1].0, w[1].1), c, dashed);
        }
        for &(x, y, i) in &pts {
            ui.c.disc(x, y, 3, c);
            let (name, q, v, rt_) = (la.name.clone(), mc.measures[i].clone(), la.values[i], la.ratios[i]);
            ui.tip(rect(x - 5, y - 5, 11, 11), move || {
                vec![format!("{}, {}: {} ({:.2}× one disk)", name, q.label, v.map(|v| fmt(v, &q.unit)).unwrap_or_default(), rt_.unwrap_or(0.0))]
            });
        }
    }
    // The legend: the technologies, which is all the colour says.
    // text() returns where the next letter would go: each label starts after the last one ends.
    let mut x = r.x + 8;
    for (tech, word) in [("md", "mdadm"), ("zfs", "ZFS"), ("btrfs", "btrfs"), ("one", "one disk")] {
        let c = hue(ui, tech);
        ui.c.rect(x, r.bottom() - 9, 14, 3, c);
        x = ui.c.text(x + 18, r.bottom() - 14, word, &F6X10, t.dim) + 14;
    }
    ui.c.text(x + 6, r.bottom() - 14, "dashed: one disk and the pairs. Hover a point for its layout and value.", &F6X10, t.dim);
}

/// Where each layout's fast write cache ran out, from the barrage.
fn cliff(ui: &mut Ui, r: Rect, mc: &Machine) {
    let t = ui.t;
    ui.c.rect(r.x, r.y, r.w, r.h, t.tile);
    ui.label(r.x + 8, r.y + 4, "The cache cliff: MB/s each second of writing", &F8X13, t.ink);
    if mc.cliffs.is_empty() {
        ui.label_in(r.x + 8, r.y + 28, r.w - 16, "No barrage yet. It measures how many GB these drives take at full speed before their fast cache runs out.", &F6X10, t.dim);
        return;
    }
    let (l, rt, top, bot) = (r.x + 40, r.right() - 10, r.y + 24, r.bottom() - 18 - 12 * mc.cliffs.len() as i32);
    let top_v = mc.cliffs.iter().flat_map(|c| c.1.iter().cloned()).fold(1.0, f64::max) * 1.08;
    let longest = mc.cliffs.iter().map(|c| c.1.len()).max().unwrap_or(1).max(2);
    for k in 0..=4 {
        let v = top_v * k as f64 / 4.0;
        let y = bot - ((bot - top) as f64 * k as f64 / 4.0) as i32;
        ui.c.hline(l, y, rt - l, mix(t.tile, t.line, 140));
        ui.c.text_right(l - 4, y - 5, &format!("{:.0}", v), &F6X10, t.dim);
    }
    for (i, (name, per, gb)) in mc.cliffs.iter().enumerate() {
        let tech = if name == "raw" { "one" } else { name.split('@').next().map(|n| if n.contains("zfs") { "zfs" } else if n.contains("btrfs") { "btrfs" } else { "md" }).unwrap_or("md") };
        let c = hue(ui, tech);
        let pts: Vec<(i32, i32)> = per.iter().enumerate().map(|(k, v)| (l + k as i32 * (rt - l) / (longest as i32 - 1), bot - ((bot - top) as f64 * v / top_v) as i32)).collect();
        for w in pts.windows(2) {
            seg(ui, w[0], w[1], c, name == "raw");
        }
        let y = bot + 8 + 12 * i as i32;
        ui.c.rect(r.x + 8, y + 4, 12, 3, c);
        ui.c.text(r.x + 24, y, &format!("{}: {}", name, gb.map(|g| format!("fast for {:.1} GB", g)).unwrap_or("no cliff seen".into())), &F6X10, t.dim);
    }
}

/// The conclusion matrix: a row a layout, a column a measure, the best marked ● on green.
fn matrix(ui: &mut Ui, r: Rect, mc: &Machine) {
    let t = ui.t;
    ui.c.rect(r.x, r.y, r.w, r.h, t.tile);
    let name_w = 150;
    let extra = 2;
    let cols = mc.measures.len() as i32 + extra;
    let cw = ((r.w - name_w - 8) / cols.max(1)).max(36);
    let (hy, rh) = (r.y + 6, 17);
    for (i, q) in mc.measures.iter().enumerate() {
        let x = r.x + name_w + i as i32 * cw;
        ui.c.text_in(x + 2, hy, cw - 4, &q.label, &F6X10, t.dim);
        ui.c.text_in(x + 2, hy + 11, cw - 4, if q.higher { &q.unit } else { "s, less" }, &F6X10, t.dim);
    }
    let xu = r.x + name_w + mc.measures.len() as i32 * cw;
    ui.c.text(xu + 2, hy, "usable", &F6X10, t.dim);
    ui.c.text(xu + cw + 2, hy, "can lose", &F6X10, t.dim);
    let best: std::collections::HashMap<&str, &str> = mc.best.iter().map(|(k, v)| (k.as_str(), v.as_str())).collect();
    let mut y = r.y + 34;
    for la in &mc.layouts {
        if y + rh > r.bottom() {
            break;
        }
        ui.c.disc(r.x + 10, y + 7, 3, hue(ui, &la.tech));
        ui.c.text_in(r.x + 18, y + 3, name_w - 22, &la.name, &F8X13, t.ink);
        for (i, q) in mc.measures.iter().enumerate() {
            let x = r.x + name_w + i as i32 * cw;
            let Some(v) = la.values.get(i).copied().flatten() else { continue };
            let vals: Vec<f64> = mc.layouts.iter().filter_map(|o| o.values.get(i).copied().flatten()).collect();
            let top = if q.higher { vals.iter().cloned().fold(f64::MIN, f64::max) } else { vals.iter().cloned().fold(f64::MAX, f64::min) };
            let rel = if q.higher { v / top } else { top / v };
            let is_best = best.get(q.key.as_str()) == Some(&la.name.as_str());
            let fill = if is_best || rel >= 0.9 { mix(t.tile, t.up, 70) } else if rel <= 0.5 { mix(t.tile, t.alarm, 45) } else { t.tile };
            ui.c.rect(x + 1, y, cw - 2, rh - 2, fill);
            let txt = format!("{}{}", short(v, &q.unit), if is_best { " ●" } else { "" });
            ui.c.text_in(x + 4, y + 3, cw - 6, &txt, &F6X10, if is_best { t.ink } else { t.dim });
            let (name, q2, sp) = (la.name.clone(), q.clone(), la.spread.get(i).copied().flatten());
            ui.tip(rect(x, y, cw, rh), move || {
                let mut l = vec![format!("{}, {}: {}", name, q2.label, fmt(v, &q2.unit))];
                if let Some((a, b, k)) = sp {
                    l.push(format!("median of {} trials, {} to {}", k, fmt(a, &q2.unit), fmt(b, &q2.unit)));
                }
                if is_best {
                    l.push("the best of every layout".into());
                }
                l
            });
        }
        ui.c.text(xu + 4, y + 3, &format!("{:.0} GB", la.usable_gb), &F6X10, t.dim);
        ui.c.text(xu + cw + 4, y + 3, &format!("{}", la.can_lose), &F6X10, if la.can_lose == 0 { t.alarm } else { t.dim });
        y += rh;
    }
}

/// The machine's spare disks, what each holds, and the two ways to start the bench there.
fn spares(ui: &mut Ui, r: Rect, mc: &Machine, st: &mut State) {
    let t = ui.t;
    if r.h < 30 {
        return;
    }
    ui.label(r.x, r.y, &format!("Spare disks on {} (unmounted, not the system's), and the {} in its disks.txt", mc.host, mc.chosen.len()), &F8X13, t.ink);
    let mut y = r.y + 18;
    for d in &mc.spare {
        if y + 14 > r.bottom() - 30 {
            break;
        }
        let holds = if d.holds.is_empty() { "nothing a filesystem tool recognises".to_string() } else { format!("HOLDS {}", d.holds.join(", ")) };
        let chosen = if mc.chosen.contains(&d.serial) { "  in disks.txt" } else { "" };
        ui.c.text_in(r.x + 8, y, r.w - 16, &format!("{} {:>5} GB  {}  {}  {}{}", d.dev, d.gb, d.serial, d.model, holds, chosen), &F6X10,
                     if d.holds.is_empty() { t.dim } else { t.warn });
        y += 13;
    }
    if mc.spare.is_empty() {
        ui.c.text(r.x + 8, y, "none: every disk is mounted or the system's (a running bench holds its disks)", &F6X10, t.dim);
        y += 13;
    }
    if !st.operator {
        return;
    }
    let by = (y + 6).min(r.bottom() - 24);
    if ui.button(rect(r.x, by, F8X13.measure("Inspect (read only)") as i32 + 24, 22), "Inspect (read only)", true) {
        st.ask = Some(Ask::Stage { host: mc.host.clone(), what: "inspect".into() });
        st.armed = false;
    }
    let busy = mc.progress.state == "running" || mc.progress.state == "serving";
    let label = if st.armed { "Press again: erase and run" } else { "Run every layout" };
    let ix = r.x + F8X13.measure("Inspect (read only)") as i32 + 34;
    if ui.button(rect(ix, by, F8X13.measure("Press again: erase and run") as i32 + 24, 22), label, !busy && !mc.chosen.is_empty()) {
        if st.armed {
            st.ask = Some(Ask::Stage { host: mc.host.clone(), what: "run".into() });
            st.armed = false;
        } else {
            st.armed = true;
        }
    }
    let note = if st.armed {
        format!("Erases the {} disks in {}'s disks.txt: {}. The command goes to its Sessions tile; you type the password there.", mc.chosen.len(), mc.host, mc.chosen.join(", "))
    } else if !st.said.is_empty() {
        st.said.clone()
    } else if mc.progress.state == "serving" {
        format!("The disks are shared: unmount them on the clients, then on {} `sudo sh ~/fleet/disk-bench/nfs.sh stop`; Run waits.", mc.host)
    } else if busy {
        "A run is going: Run waits for it.".into()
    } else {
        "Orrery holds no root: both buttons copy the bench there and type its command in the machine's Sessions tile, for your password.".into()
    };
    let nx = ix + F8X13.measure("Press again: erase and run") as i32 + 34;
    ui.label_in(nx, by + 5, r.right() - nx, &note, &F6X10, if st.armed { t.warn } else { t.dim });
}

#[cfg(test)]
mod tests {
    use super::*;

    const DOC: &str = r#"{"at": 1, "machines": [{"host": "calber", "error": "",
      "progress": {"state": "running", "kind": "run", "current": "md10-ext4#1", "step": "seqr", "done": ["a"], "plan": ["a","b","c"], "failed": [], "eta": 0, "updated": 0},
      "spare": [{"serial": "S1", "dev": "nvme0n1", "GB": 1024, "tran": "nvme", "model": "HP SSD EX900 1TB", "holds": ["crypto_LUKS"]}],
      "chosen": ["S2", "S3"],
      "summary": {"disks": 6, "disk_GB": 480, "runs": ["v1-2026-11-07"],
        "measures": [{"key": "seq-read", "label": "seq read", "unit": "MB/s", "higher": true}, {"key": "find_s", "label": "find", "unit": "s", "higher": false}],
        "layouts": [{"name": "single", "tech": "one", "values": [558, 0.05], "ratios": [1, 1], "spread": [null, null], "usable_GB": 480, "can_lose": 0},
                    {"name": "md10-ext4", "tech": "md", "values": [1923, 0.04], "ratios": [3.4, 1.25], "spread": [[1800, 2000, 2], null], "usable_GB": 1440, "can_lose": 1}],
        "best": {"seq-read": "md10-ext4", "find_s": "md10-ext4"},
        "winners": [{"use": "Blu-ray working disk", "layout": "md10-ext4", "score": 1.53}],
        "cliffs": [{"layout": "raw", "MBps": [500, 480, 160], "cliff_GB": 1.0}]}}]}"#;

    #[test]
    fn a_bench_document_reads_into_its_machine_layouts_and_verdicts() {
        let m = Model::parse(DOC);
        assert!(m.why.is_empty());
        let c = &m.machines[0];
        assert_eq!(c.host, "calber");
        assert_eq!((c.progress.done, c.progress.plan, c.progress.state.as_str()), (1, 3, "running"));
        assert_eq!(c.layouts.len(), 2);
        assert_eq!(c.layouts[1].spread[0], Some((1800.0, 2000.0, 2)));
        assert_eq!(c.winners[0].1, "md10-ext4");
        assert_eq!(c.spare[0].holds, vec!["crypto_LUKS".to_string()]);
        assert_eq!(c.cliffs[0].2, Some(1.0));
    }

    #[test]
    fn nothing_to_read_says_why_rather_than_drawing_an_empty_chart() {
        assert!(!Model::parse("").why.is_empty());
        assert!(!Model::parse("disk-report.py: no such file").why.is_empty());
        assert!(!Model::parse(r#"{"machines": []}"#).why.is_empty());
    }
}
