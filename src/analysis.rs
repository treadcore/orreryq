//! The Algorhythm page's analysis tabs (Paul, 30 October: "a terrain style 3d graph";
//! "something like a spectrogram"; "laying out the input sensor as it would be seen";
//! "redraw how the new fleet orchestrates").
//!
//! IT DRAWS AND DECIDES NOTHING: `tools/analysis.py` writes the numbers, in the background,
//! from the fleet's own ledger and nets. A terrain here is a kernel average of reads that
//! moved several dials at once, and says so, and dims where few reads stand: A PEAK ON NO
//! DATA IS THE EASIEST LIE A LANDSCAPE CAN TELL. It is a map of where to look. The census
//! is still what proves anything.

use crate::draw::Rgb;
use crate::font::{F10X20, F8X13};
use crate::json::Value;
use crate::ui::{rect, Rect, Ui};
use std::cell::RefCell;
use std::rc::Rc;
use std::time::SystemTime;

pub const TABS: [&str; 6] = ["Patch", "Terrain", "Spectrum", "Matrices", "Senses", "Fleet"];

#[derive(Debug, Clone, Default, PartialEq)]
pub struct State {
    pub tab: usize,
    pub pair: usize,
    /// Quarter-turns of a sixteenth each.
    pub yaw: i32,
    pub hybrid: bool,
    /// Which of the terrains' datasets.
    pub dataset: usize,
    /// The selected region, x0 x1 y0 y1 on the pair's axes, and the corner a drag began at.
    pub sel: Option<[f64; 4]>,
    /// The two dials it was drawn over.
    pub sel_on: String,
    pub drag: Option<(f64, f64)>,
    pub operator: bool,
    /// Arguments for tools/regions.py, for main to run; and what it last said.
    pub ask: Option<String>,
    pub said: String,
}

fn blend(a: Rgb, b: Rgb, t: f64) -> Rgb {
    let t = t.clamp(0.0, 1.0);
    let ch = |s: u32| {
        let (x, y) = (((a >> s) & 255) as f64, ((b >> s) & 255) as f64);
        ((x + (y - x) * t) as u32) << s
    };
    ch(16) | ch(8) | ch(0)
}

fn s(v: &Value, k: &str) -> String {
    v.get(k).and_then(|x| x.as_str()).unwrap_or("").to_string()
}
fn n(v: &Value, k: &str) -> f64 {
    v.get(k).and_then(|x| x.as_num()).unwrap_or(0.0)
}
fn arr<'a>(v: &'a Value, k: &str) -> &'a [Value] {
    v.get(k).and_then(|x| x.as_array()).map(|a| &a[..]).unwrap_or(&[])
}
fn nums(v: &Value) -> Vec<f64> {
    v.as_array().map(|a| a.iter().filter_map(|x| x.as_num()).collect()).unwrap_or_default()
}
fn grid(v: &[Value]) -> Vec<Vec<f64>> {
    v.iter().map(nums).collect()
}

/// A diverging colour: red under zero, green over, by the share of `max`.
fn heat(ui: &Ui, v: f64, max: f64) -> Rgb {
    let t = ui.t;
    let k = (v.abs() / max.max(1e-9)).sqrt();
    blend(t.tile, if v >= 0.0 { t.up } else { t.alarm }, k)
}

/// The tab strip; returns what is left under it.
pub fn tabs(ui: &mut Ui, at: Rect, st: &mut State) -> Rect {
    let w = 96;
    for (i, name) in TABS.iter().enumerate() {
        let r = rect(at.x + i as i32 * (w + 4), at.y, w, 24);
        let on = st.tab == i;
        if on {
            ui.c.rect(r.x + 4, r.bottom(), r.w - 8, 2, ui.t.up);
        }
        if ui.button(r, name, !on) {
            st.tab = i;
        }
    }
    rect(at.x, at.y + 32, at.w, at.h - 32)
}

/// A filled triangle, one row of pixels at a time: the canvas has rects and discs.
fn tri(ui: &mut Ui, p: [(f64, f64); 3], c: Rgb) {
    let y0 = p.iter().map(|q| q.1).fold(f64::MAX, f64::min).ceil() as i32;
    let y1 = p.iter().map(|q| q.1).fold(f64::MIN, f64::max).floor() as i32;
    for y in y0..=y1 {
        let (mut lo, mut hi) = (f64::MAX, f64::MIN);
        for i in 0..3 {
            let (a, b) = (p[i], p[(i + 1) % 3]);
            let yy = y as f64;
            if (a.1 <= yy && b.1 >= yy) || (b.1 <= yy && a.1 >= yy) {
                let x = if (b.1 - a.1).abs() < 1e-6 { a.0 } else { a.0 + (yy - a.1) * (b.0 - a.0) / (b.1 - a.1) };
                lo = lo.min(x.min(if (b.1 - a.1).abs() < 1e-6 { b.0 } else { x }));
                hi = hi.max(x.max(if (b.1 - a.1).abs() < 1e-6 { b.0 } else { x }));
            }
        }
        if hi >= lo {
            ui.c.rect(lo.floor() as i32, y, (hi - lo).ceil() as i32 + 1, 1, c);
        }
    }
}

/// Grid point to the screen: turned by the yaw, tipped back, raised by its height.
pub fn project(u: f64, v: f64, h: f64, yaw: f64, cx: f64, cy: f64, r: f64) -> (f64, f64, f64) {
    let (x, y) = (u * yaw.cos() - v * yaw.sin(), u * yaw.sin() + v * yaw.cos());
    (cx + x * r, cy + y * r * 0.5 - h, y)
}

/// The dataset's own file, read again only when it changes: this runs each frame, and a file is
/// tens of thousands of numbers. The document polled every few seconds carries only the index.
fn load_doc(path: &str) -> Option<Rc<Value>> {
    thread_local! {
        static DOC: RefCell<(String, Option<SystemTime>, Option<Rc<Value>>)> = const { RefCell::new((String::new(), None, None)) };
    }
    let when = std::fs::metadata(path).and_then(|m| m.modified()).ok();
    DOC.with(|d| {
        let mut d = d.borrow_mut();
        if d.0 != path || d.1 != when {
            let v = std::fs::read_to_string(path).ok().and_then(|t| crate::json::parse(&t).ok()).map(Rc::new);
            *d = (path.to_string(), when, v);
        }
        d.2.clone()
    })
}

/// Three figures: a peak's place needs no more, and the panel has no room for them.
fn sig(v: f64) -> String {
    if v.abs() >= 100.0 { format!("{:.0}", v) } else if v.abs() >= 10.0 { format!("{:.1}", v) } else { format!("{:.2}", v) }
}

/// Two corners as [x0, x1, y0, y1], least first.
pub fn corners(a: (f64, f64), b: (f64, f64)) -> [f64; 4] {
    [a.0.min(b.0), a.0.max(b.0), a.1.min(b.1), a.1.max(b.1)]
}

pub fn inside(b: &[f64; 4], x: f64, y: f64) -> bool {
    x >= b[0] && x <= b[1] && y >= b[2] && y <= b[3]
}

/// The word a maximum carries, and its colour: nothing working on it is the one to see.
fn word_of(ui: &Ui, q: &Value) -> (String, Rgb) {
    let t = ui.t;
    match (s(q, "word").as_str(), s(q, "says").as_str()) {
        ("read", "holds") => ("read: it holds".to_string(), t.up),
        ("read", "falls") => ("read: under today".to_string(), t.dim),
        ("read", _) => ("read: not settled".to_string(), t.ink),
        ("reading", _) => ("being worked on".to_string(), t.warn),
        _ => ("NOTHING ON IT".to_string(), t.alarm),
    }
}

fn draw_terrain(ui: &mut Ui, at: Rect, a: &Value, st: &mut State) {
    let t = ui.t;
    let lh = F8X13.height as i32 + 5;
    let Some(idx) = a.get("terrains") else {
        ui.label_in(at.x, at.y, at.w, "The terrains are being worked out; it takes about a minute.", &F8X13, t.dim);
        return;
    };
    let sets = arr(idx, "datasets");
    if sets.is_empty() {
        ui.label_in(at.x, at.y, at.w, &format!("No terrain to draw. {}", s(idx, "error")), &F8X13, t.dim);
        return;
    }
    st.dataset = st.dataset.min(sets.len() - 1);

    // The datasets, each saying how many of its maxima have something on them.
    let rail = rect(at.x, at.y, 212, at.h);
    let mut y = rail.y;
    let mut group = String::new();
    for (i, d) in sets.iter().enumerate() {
        let g = s(d, "group");
        if g != group {
            let head = match g.as_str() {
                "reads" => "All the reads",
                "maps" => "By map",
                "parts" => "By what was scored",
                _ => "Nets, not dials",
            };
            y += if group.is_empty() { 0 } else { 5 };
            ui.label_in(rail.x, y, rail.w, head, &F8X13, t.dim);
            y += lh - 3;
            group = g;
        }
        let r = rect(rail.x, y, rail.w - 6, lh - 1);
        let on = i == st.dataset;
        ui.panel(r, if on { t.tile } else { t.base });
        if on {
            ui.outline(r, t.up);
        }
        let (peaks, bare, reading) = (n(d, "peaks"), n(d, "bare"), n(d, "reading"));
        let mark = if peaks == 0.0 { t.line } else if bare > 0.0 { t.alarm } else if reading > 0.0 { t.warn } else { t.up };
        ui.c.disc(r.x + 8, r.y + r.h / 2, 4, mark);
        ui.label_in(r.x + 17, r.y + 2, r.w - 62, &s(d, "label"), &F8X13, if on { t.ink } else { t.dim });
        ui.label_right(r.right() - 4, r.y + 2, &format!("{}/{}", peaks - bare, peaks), &F8X13, if bare > 0.0 { t.alarm } else { t.dim });
        ui.tip(r, || vec![
            format!("{}: {} maxima over {} pairs of dials", s(d, "label"), peaks, n(d, "pairs")),
            format!("{} read, {} being worked on, {} with nothing on them.", n(d, "read"), reading, bare),
            "Click to draw this dataset.".to_string(),
        ]);
        if ui.button_hit(r) && !on {
            st.dataset = i;
            st.pair = 0;
            st.sel = None;
        }
        y += lh;
    }
    if let Some(r) = idx.get("reads") {
        y += 6;
        ui.label_in(rail.x, y, rail.w - 6, &format!("{} reads used", n(r, "used")), &F8X13, t.dim);
        y += lh;
    }
    let bare_all: f64 = sets.iter().filter(|d| s(d, "group") != "nets").map(|d| n(d, "bare")).sum();
    if st.operator && bare_all > 0.0 && ui.button(rect(rail.x, y, rail.w - 6, 22), &format!("Read every bare: {}", bare_all), true) {
        st.ask = Some("cover-all".to_string());
    }

    let d = &sets[st.dataset];
    let Some(doc) = load_doc(&format!("{}/{}.json", s(idx, "dir"), s(d, "id"))) else {
        ui.label_in(rail.right() + 8, at.y, at.w - rail.w - 8, "This dataset's file cannot be read yet.", &F8X13, t.dim);
        return;
    };
    let pairs = arr(&doc, "pairs");
    if pairs.is_empty() {
        ui.label_in(rail.right() + 8, at.y, at.w - rail.w - 8, &format!("{}: too few reads to draw any pair of dials.", s(d, "label")), &F8X13, t.dim);
        return;
    }
    if st.pair >= pairs.len() {
        st.pair = 0;
        st.sel = None;
    }
    // The pairs are chosen afresh each reading: a box drawn over two dials is not a box over two others.
    let names = format!("{} {}", s(&pairs[st.pair], "a"), s(&pairs[st.pair], "b"));
    if st.sel_on != names {
        if !st.sel_on.is_empty() {
            st.sel = None;
            st.drag = None;
        }
        st.sel_on = names;
    }
    let can_send = doc.get("can_send").and_then(|v| v.as_bool()).unwrap_or(false);

    // The pairs, the maxima and what to do about them.
    let w = 240;
    let side = rect(at.right() - w, at.y, w, at.h);
    let mut y = side.y;
    for (i, p) in pairs.iter().enumerate() {
        let r = rect(side.x, y, w, lh - 1);
        let on = i == st.pair;
        ui.panel(r, if on { t.tile } else { t.base });
        if on {
            ui.outline(r, t.up);
        }
        let bare = arr(p, "peaks").iter().filter(|q| s(q, "word") == "bare").count();
        let wid = if bare > 0 { w - 28 } else { w - 10 };
        ui.label_in(r.x + 5, r.y + 2, wid, &format!("{} x {}", s(p, "a"), s(p, "b")), &F8X13, if on { t.ink } else { t.dim });
        if bare > 0 {
            ui.c.disc(r.right() - 10, r.y + r.h / 2, 4, t.alarm);
        }
        if ui.button_hit(r) && !on {
            st.pair = i;
            st.sel = None;
        }
        y += lh;
    }
    y += 3;
    if ui.button(rect(side.x, y, 66, 22), "Turn <", true) {
        st.yaw -= 1;
    }
    if ui.button(rect(side.x + 72, y, 66, 22), "Turn >", true) {
        st.yaw += 1;
    }
    y += 28;
    let p = &pairs[st.pair];
    let log = p.get("log").and_then(|v| v.as_bool()).unwrap_or(false);
    let h_box = n(p, "h");
    let peaks = arr(p, "peaks");
    ui.label(side.x, y, if peaks.is_empty() { "No local maximum here" } else { "Local maxima, highest first" }, &F8X13, if peaks.is_empty() { t.dim } else { t.ink });
    y += lh - 2;
    for (i, q) in peaks.iter().take(5).enumerate() {
        let r = rect(side.x, y, w, lh * 2 - 3);
        let (word, col) = word_of(ui, q);
        ui.c.disc(r.x + 7, r.y + 7, 7, col);
        ui.label(r.x + 4, r.y + 1, &(i + 1).to_string(), &F8X13, t.base);
        ui.label_in(r.x + 18, r.y, w - 18, &format!("{:+.2}  {}", n(q, "z"), word), &F8X13, col);
        let second = if s(q, "word") == "read" {
            format!("{}, {}: {:+.2} +/- {:.2}", sig(n(q, "a")), sig(n(q, "b")), n(q, "mean"), n(q, "err"))
        } else if !log && n(q, "jobs") > 0.0 {
            format!("{} is here", s(q, "says"))
        } else if n(q, "jobs") > 0.0 {
            format!("{}, {}: {} at work", sig(n(q, "a")), sig(n(q, "b")), n(q, "jobs"))
        } else {
            format!("{}, {}: {} near", sig(n(q, "a")), sig(n(q, "b")), n(q, "reads"))
        };
        ui.label_in(r.x + 18, r.y + lh - 4, w - 18, &second, &F8X13, t.dim);
        ui.tip(r, || vec![
            format!("Maximum {}: {:+.2} on the surface", i + 1, n(q, "z")),
            format!("{} reads, {} seeds and {} jobs within {:.2} of it.", n(q, "reads"), n(q, "seeds"), n(q, "jobs"), h_box),
            if s(q, "word") == "read" { format!("Those reads say {:+.2} +/- {:.2}, against today's defaults.", n(q, "mean"), n(q, "err")) } else { "Too few seeds yet to say.".to_string() },
            "Click to select the ground around it.".to_string(),
        ]);
        if ui.button_hit(r) {
            st.sel = Some([n(q, "x") - h_box, n(q, "x") + h_box, n(q, "y") - h_box, n(q, "y") + h_box]);
        }
        y += lh * 2 - 3;
    }

    // What is selected, and asking for work on it.
    y += 2;
    if let Some(b) = st.sel {
        let dots = arr(p, "dots").iter().filter(|v| { let c = nums(v); c.len() >= 2 && inside(&b, c[0], c[1]) }).count();
        let jobs = arr(p, "jobs").iter().filter(|v| { let c = v.as_array().unwrap_or(&[]); c.len() >= 2 && inside(&b, c[0].as_num().unwrap_or(9e9), c[1].as_num().unwrap_or(9e9)) }).count();
        let tops = peaks.iter().filter(|q| inside(&b, n(q, "x"), n(q, "y"))).count();
        let today = p.get("today").map(nums).unwrap_or_default();
        let value = |i: usize, x: f64| if log { today.get(i).copied().unwrap_or(1.0) * 2f64.powf(x) } else { x };
        ui.label_in(side.x, y, w, "Selected", &F8X13, t.warn);
        y += lh - 3;
        ui.label_in(side.x, y, w, &format!("{}: {:.3} to {:.3}", s(p, "a"), value(0, b[0]), value(0, b[1])), &F8X13, t.dim);
        y += lh - 3;
        ui.label_in(side.x, y, w, &format!("{}: {:.3} to {:.3}", s(p, "b"), value(1, b[2]), value(1, b[3])), &F8X13, t.dim);
        y += lh - 3;
        ui.label_in(side.x, y, w, &format!("{} reads, {} at work, {} maxima", dots, jobs, tops), &F8X13, t.ink);
        y += lh - 1;
        if can_send && st.operator && ui.button(rect(side.x, y, 134, 22), "Read here: 6", true) {
            st.ask = Some(format!("add {} {:.6} {:.6} {} {:.6} {:.6} 6", s(p, "a"), value(0, b[0]), value(0, b[1]), s(p, "b"), value(1, b[2]), value(1, b[3])));
        }
        if ui.button(rect(side.x + 140, y, 62, 22), "Clear", true) {
            st.sel = None;
        }
        y += 26;
    } else {
        ui.label_in(side.x, y, w, "Drag on the flat map.", &F8X13, t.dim);
        y += lh;
    }
    let bare_here = peaks.iter().filter(|q| s(q, "word") == "bare").count();
    if can_send && st.operator && bare_here > 0 {
        if ui.button(rect(side.x, y, 202, 22), &format!("Read the bare: {}", bare_here), true) {
            st.ask = Some(format!("cover {} {}", s(d, "id"), st.pair));
        }
        y += 26;
    }
    if !st.said.is_empty() {
        ui.label_in(side.x, y, w, &st.said, &F8X13, t.warn);
    }

    // The heading says the one thing this screen is for.
    let plot = rect(rail.right() + 6, at.y, at.w - rail.w - w - 18, at.h);
    let z = grid(arr(p, "z"));
    let sup = grid(arr(p, "support"));
    let rows = z.len();
    let cols = z.first().map(|r| r.len()).unwrap_or(0);
    if rows < 2 || cols < 2 {
        return;
    }
    ui.label_in(plot.x, plot.y, plot.w, &format!("{}: {}. {} reads over {} and {}", s(d, "label"), s(&doc, "unit"), n(p, "reads"), s(p, "a"), s(p, "b")), &F8X13, t.ink);
    let (read, doing, bare) = (
        peaks.iter().filter(|q| s(q, "word") == "read").count(),
        peaks.iter().filter(|q| s(q, "word") == "reading").count(),
        bare_here,
    );
    let verdict = if peaks.is_empty() {
        "No maximum stands out of this pair.".to_string()
    } else if bare == 0 {
        format!("Every maximum here has work on it: {} read, {} being worked on.", read, doing)
    } else {
        format!("{} of {} maxima have nothing on them: {} read, {} being worked on.", bare, peaks.len(), read, doing)
    };
    ui.label_in(plot.x, plot.y + lh - 2, plot.w, &verdict, &F8X13, if bare > 0 { t.alarm } else { t.up });

    let (ax, ay) = (p.get("ax").map(nums).unwrap_or_default(), p.get("ay").map(nums).unwrap_or_default());
    if ax.len() != 2 || ay.len() != 2 {
        return;
    }
    let top = plot.y + lh * 2 + 2;
    let body = rect(plot.x, top, plot.w, plot.bottom() - top);
    let flat_size = (body.w * 44 / 100).min(body.h - lh * 3).max(120);
    let flat = rect(body.right() - flat_size, body.y + 4, flat_size, flat_size);
    let land = rect(body.x, body.y, body.w - flat_size - 10, body.h - lh * 2);

    // A floor at three points under today: the valleys reach -7, and on their scale the ground
    // that matters, within a point of today, drew flat and black.
    let z: Vec<Vec<f64>> = z.iter().map(|row| row.iter().map(|v| v.max(-3.0)).collect()).collect();
    // Kills less deaths moves in tenths, where points move in points: its own scale, its own terraces.
    let zmax = z.iter().flatten().fold(0.05f64, |m, v| m.max(v.abs()));
    let sup_max = sup.iter().flatten().fold(1e-6f64, |m, v| m.max(*v));
    let colour = |ui: &Ui, ix: usize, iy: usize, v: f64, lit: f64| {
        // Terraces, a twelfth of the height: contour lines without drawing any.
        let step = zmax / 12.0;
        let base = heat(ui, (v / step).round() * step, zmax);
        let shaded = if lit > 0.5 { blend(base, ui.t.ink, (lit - 0.5) * 0.35) } else { blend(base, ui.t.base, (0.5 - lit) * 0.7) };
        blend(ui.t.tile, shaded, (sup[iy][ix] / (sup_max * 0.08)).clamp(0.12, 1.0))
    };
    let cell_x = |ix: usize| ax[0] + (ax[1] - ax[0]) * ix as f64 / (cols - 1) as f64;
    let cell_y = |iy: usize| ay[0] + (ay[1] - ay[0]) * iy as f64 / (rows - 1) as f64;

    // The surface, as before, with the selection lit on it.
    let yaw = 0.7 + st.yaw as f64 * std::f64::consts::PI / 8.0;
    let at_uv = |ix: usize, iy: usize| (2.0 * ix as f64 / (cols - 1) as f64 - 1.0, 2.0 * iy as f64 / (rows - 1) as f64 - 1.0);
    // Fitted to the panel: a deep valley hung off the bottom of a fixed scale. Measured at unit
    // size, then scaled so the whole surface, heights and all, sits between the text.
    let hu = 0.55 / zmax;
    let (mut x0, mut x1, mut y0, mut y1) = (f64::MAX, f64::MIN, f64::MAX, f64::MIN);
    for (j, row) in z.iter().enumerate() {
        for (i, v) in row.iter().enumerate() {
            let (u, w) = at_uv(i, j);
            let g = project(u, w, v * hu, yaw, 0.0, 0.0, 1.0);
            x0 = x0.min(g.0);
            x1 = x1.max(g.0);
            y0 = y0.min(g.1);
            y1 = y1.max(g.1);
        }
    }
    let area = rect(land.x, land.y + 30, land.w, land.h - 34);
    let r = (area.w as f64 / (x1 - x0).max(1e-6)).min(area.h as f64 / (y1 - y0).max(1e-6));
    let hs = hu * r;
    let cx = area.x as f64 + area.w as f64 / 2.0 - r * (x0 + x1) / 2.0;
    let cy = area.y as f64 + area.h as f64 / 2.0 - r * (y0 + y1) / 2.0;
    // Back to front, the painter's way.
    let mut cells: Vec<(f64, usize, usize)> = Vec::with_capacity(rows * cols);
    for iy in 0..rows - 1 {
        for ix in 0..cols - 1 {
            let (u, v) = at_uv(ix, iy);
            cells.push((project(u + 1.0 / cols as f64, v + 1.0 / rows as f64, 0.0, yaw, cx, cy, r).2, ix, iy));
        }
    }
    cells.sort_by(|a, b| a.0.total_cmp(&b.0));
    for (_, ix, iy) in cells {
        let c = [(ix, iy), (ix + 1, iy), (ix + 1, iy + 1), (ix, iy + 1)];
        let q: Vec<(f64, f64)> = c
            .iter()
            .map(|&(i, j)| {
                let (u, v) = at_uv(i, j);
                let g = project(u, v, z[j][i] * hs, yaw, cx, cy, r);
                (g.0, g.1)
            })
            .collect();
        let mean = c.iter().map(|&(i, j)| z[j][i]).sum::<f64>() / 4.0;
        // Lit from one side, so a slope shows on a surface of one colour.
        let slope = (z[iy][ix + 1] - z[iy][ix]) + (z[iy + 1][ix] - z[iy][ix]);
        let lit = (0.5 + slope / zmax * 4.0).clamp(0.0, 1.0);
        let mut col = colour(ui, ix, iy, mean, lit);
        if st.sel.is_some_and(|b| inside(&b, cell_x(ix), cell_y(iy))) {
            col = blend(col, t.warn, 0.45);
        }
        tri(ui, [q[0], q[1], q[2]], col);
        tri(ui, [q[0], q[2], q[3]], col);
    }
    let cell_of = |x: f64, a0: f64, a1: f64, m: usize| (m - 1) as f64 * (x - a0) / (a1 - a0).max(1e-9);
    if log {
        let (u, v) = (2.0 * (0.0 - ax[0]) / (ax[1] - ax[0]) - 1.0, 2.0 * (0.0 - ay[0]) / (ay[1] - ay[0]) - 1.0);
        let g = project(u, v, 0.0, yaw, cx, cy, r);
        ui.c.disc(g.0 as i32, g.1 as i32, 6, t.ink);
        ui.c.disc(g.0 as i32, g.1 as i32, 3, t.base);
        ui.tip(rect(g.0 as i32 - 8, g.1 as i32 - 8, 16, 16), || vec!["Today's defaults".to_string(), "Where the line is now: no doublings on either dial, and height zero by definition.".to_string()]);
    }
    for (i, q) in peaks.iter().take(5).enumerate() {
        let (ix, iy) = (n(q, "ix") as usize, n(q, "iy") as usize);
        let (u, v) = at_uv(ix, iy);
        let g = project(u, v, n(q, "z") * hs, yaw, cx, cy, r);
        let (_, col) = word_of(ui, q);
        ui.c.rect(g.0 as i32, g.1 as i32 - 24, 1, 24, col);
        ui.c.disc(g.0 as i32, g.1 as i32 - 28, 8, col);
        ui.label(g.0 as i32 - 3, g.1 as i32 - 34, &(i + 1).to_string(), &F8X13, t.base);
    }
    ui.tip(land, || vec![
        format!("The terrain over {} and {}", s(p, "a"), s(p, "b")),
        "Height is the smoothed gain over today's defaults, from the reads that moved one of these dials. Colour fades where there are few.".to_string(),
        "A place to look, never a result: only a census says what is there.".to_string(),
    ]);

    // The same ground from above, where a region can be drawn and what works on it seen.
    let cw = flat.w as f64 / cols as f64;
    let ch = flat.h as f64 / rows as f64;
    for iy in 0..rows {
        for ix in 0..cols {
            let x = flat.x + (ix as f64 * cw) as i32;
            let y = flat.bottom() - ((iy + 1) as f64 * ch) as i32;
            ui.c.rect(x, y, cw.ceil() as i32, ch.ceil() as i32, colour(ui, ix, iy, z[iy][ix], 0.5));
        }
    }
    ui.outline(flat, t.line);
    let px = |x: f64| flat.x + (((x - ax[0]) / (ax[1] - ax[0]).max(1e-9)) * flat.w as f64) as i32;
    let py = |y: f64| flat.bottom() - (((y - ay[0]) / (ay[1] - ay[0]).max(1e-9)) * flat.h as f64) as i32;
    for v in arr(p, "dots") {
        let c = nums(v);
        if c.len() >= 2 && inside(&[ax[0], ax[1], ay[0], ay[1]], c[0], c[1]) {
            ui.c.rect(px(c[0]), py(c[1]), 2, 2, blend(t.base, t.ink, 0.65));
        }
    }
    for g in arr(p, "regions") {
        let (a0, a1, b0, b1) = (px(n(g, "x0")), px(n(g, "x1")), py(n(g, "y1")), py(n(g, "y0")));
        ui.outline(rect(a0, b0, (a1 - a0).max(2), (b1 - b0).max(2)), t.warn);
    }
    for v in arr(p, "jobs") {
        let c = v.as_array().unwrap_or(&[]);
        if c.len() == 3 {
            let (x, y) = (c[0].as_num().unwrap_or(0.0), c[1].as_num().unwrap_or(0.0));
            if inside(&[ax[0], ax[1], ay[0], ay[1]], x, y) {
                if c[2].as_str() == Some("running") {
                    ui.c.disc(px(x), py(y), 4, t.base);
                    ui.c.disc(px(x), py(y), 3, t.warn);
                } else {
                    ui.c.frame(px(x) - 3, py(y) - 3, 7, 7, t.warn);
                }
            }
        }
    }
    if log {
        ui.c.disc(px(0.0), py(0.0), 6, t.ink);
        ui.c.disc(px(0.0), py(0.0), 3, t.base);
    }
    for (i, q) in peaks.iter().take(5).enumerate() {
        let (mx, my) = (px(n(q, "x")), py(n(q, "y")));
        let (_, col) = word_of(ui, q);
        ui.c.disc(mx, my, 8, t.base);
        ui.c.disc(mx, my, 7, col);
        ui.label(mx - 3, my - 7, &(i + 1).to_string(), &F8X13, t.base);
    }

    // Drawing a region: down on the map, across, up. A click alone takes the ground around it.
    let to_value = |x: i32, y: i32| {
        (ax[0] + (x - flat.x) as f64 / flat.w.max(1) as f64 * (ax[1] - ax[0]), ay[0] + (flat.bottom() - y) as f64 / flat.h.max(1) as f64 * (ay[1] - ay[0]))
    };
    let (mx, my) = ui.pointer();
    let here = to_value(mx.clamp(flat.x, flat.right()), my.clamp(flat.y, flat.bottom()));
    for ((x, y), b, down) in ui.f.button_events() {
        if b == crate::surface::Button::Left && down && flat.contains((x, y)) {
            st.drag = Some(to_value(x, y));
        }
    }
    if let Some(from) = st.drag {
        let b = corners(from, here);
        st.sel = Some(b);
        if !ui.s.down {
            st.drag = None;
            if b[1] - b[0] < h_box / 4.0 && b[3] - b[2] < h_box / 4.0 {
                st.sel = Some([here.0 - h_box / 2.0, here.0 + h_box / 2.0, here.1 - h_box / 2.0, here.1 + h_box / 2.0]);
            }
        }
    }
    if let Some(b) = st.sel {
        let (a0, a1, b0, b1) = (px(b[0].max(ax[0])), px(b[1].min(ax[1])), py(b[3].min(ay[1])), py(b[2].max(ay[0])));
        let frame = rect(a0, b0, (a1 - a0).max(2), (b1 - b0).max(2));
        ui.outline2(frame, t.warn);
    }
    if ui.is_hot(flat) {
        let (ix, iy) = (cell_of(here.0, ax[0], ax[1], cols).round() as usize, cell_of(here.1, ay[0], ay[1], rows).round() as usize);
        let (ix, iy) = (ix.min(cols - 1), iy.min(rows - 1));
        let today = p.get("today").map(nums).unwrap_or_default();
        let value = |i: usize, x: f64| if log { today.get(i).copied().unwrap_or(1.0) * 2f64.powf(x) } else { x };
        ui.tip(flat, || vec![
            format!("{:+.2} at {} {:.3}, {} {:.3}", z[iy][ix], s(p, "a"), value(0, here.0), s(p, "b"), value(1, here.1)),
            format!("Weight of reads under it: {:.0}. Dots are reads, amber are jobs: filled running, square queued.", sup[iy][ix]),
            "Drag to select a region; its cells light up on the surface too.".to_string(),
        ]);
    }

    // The legend and the axes.
    let lab = flat.bottom() + 4;
    let today = p.get("today").map(nums).unwrap_or_default();
    let value = |i: usize, x: f64| if log { today.get(i).copied().unwrap_or(1.0) * 2f64.powf(x) } else { x };
    ui.label_in(flat.x, lab, flat.w, &format!("{} across: {:.3} to {:.3}", s(p, "a"), value(0, ax[0]), value(0, ax[1])), &F8X13, t.dim);
    ui.label_in(flat.x, lab + lh - 3, flat.w, &format!("{} up: {:.3} to {:.3}", s(p, "b"), value(1, ay[0]), value(1, ay[1])), &F8X13, t.dim);
    let (first, second) = if log {
        ("Ring: today. Dim: few reads. Dots: reads. Amber: jobs, filled running, square queued.", "Flags: green read and holding, white unsettled, grey under today, amber worked on, red none.")
    } else {
        ("Each dot is a champion net, placed by its weights. Amber: where each island's net is now.", "Flags: amber an island is there, red none is. A net's ground has no dials to send trials to.")
    };
    ui.label_in(plot.x, plot.bottom() - lh * 2 + 2, plot.w, first, &F8X13, t.dim);
    ui.label_in(plot.x, plot.bottom() - lh + 1, plot.w, second, &F8X13, t.dim);
}

/// What a heat map's cell under the pointer is: its row and column by name, its number, and what
/// the number means. The colours say which are large; only this says how large, and of what.
fn cell_tip(ui: &mut Ui, r: Rect, cells: &[Vec<f64>], title: &str, rows: &[String], cols: &[String], means: &str) {
    let (nr, nc) = (cells.len() as i32, cells.first().map(|c| c.len()).unwrap_or(0) as i32);
    if nr == 0 || nc == 0 || !ui.is_hot(r) {
        return;
    }
    let (px, py) = ui.pointer();
    let (y, x) = (((py - r.y) * nr / r.h.max(1)).clamp(0, nr - 1) as usize, ((px - r.x) * nc / r.w.max(1)).clamp(0, nc - 1) as usize);
    let v = cells[y][x];
    let name = |names: &[String], i: usize, word: &str| names.get(i).filter(|s| !s.is_empty()).cloned().unwrap_or_else(|| format!("{} {}", word, i + 1));
    let (rn, cn) = (name(rows, y, "row"), name(cols, x, "column"));
    ui.tip(r, || vec![format!("{}: {:.3}", title, v), format!("{}, {}", rn, cn), means.to_string()]);
}

fn words_of(v: &[Value]) -> Vec<String> {
    v.iter().map(|x| x.as_str().unwrap_or("").to_string()).collect()
}

/// The point on a line chart under the pointer.
fn line_tip(ui: &mut Ui, r: Rect, v: &[f64], title: &str, means: &str) {
    if v.is_empty() || !ui.is_hot(r) {
        return;
    }
    let (px, _) = ui.pointer();
    let i = (((px - r.x) * v.len() as i32) / r.w.max(1)).clamp(0, v.len() as i32 - 1) as usize;
    ui.tip(r, || vec![format!("{}: {:.1}", title, v[i]), format!("Champion {} of the {} shown.", i + 1, v.len()), means.to_string()]);
}

/// A heat map of `cells`, row 0 at the top.
fn heatmap(ui: &mut Ui, r: Rect, cells: &[Vec<f64>], colour: impl Fn(&Ui, f64) -> Rgb) {
    let rows = cells.len() as i32;
    let cols = cells.first().map(|c| c.len()).unwrap_or(0) as i32;
    if rows == 0 || cols == 0 {
        return;
    }
    for y in 0..rows {
        for x in 0..cols {
            let (x0, x1) = (r.x + x * r.w / cols, r.x + (x + 1) * r.w / cols);
            let (y0, y1) = (r.y + y * r.h / rows, r.y + (y + 1) * r.h / rows);
            let c = colour(ui, cells[y as usize][x as usize]);
            ui.c.rect(x0, y0, (x1 - x0).max(1), (y1 - y0).max(1), c);
        }
    }
    ui.outline(r, ui.t.line);
}

fn line(ui: &mut Ui, r: Rect, v: &[f64], c: Rgb) {
    let max = v.iter().fold(1e-6f64, |m, x| m.max(*x));
    let at = |i: usize| {
        let px = r.x + i as i32 * (r.w - 2) / (v.len() as i32 - 1).max(1);
        (px, r.bottom() - 2 - (v[i] / max * (r.h - 4) as f64) as i32)
    };
    // Joined point to point: a rect a point read as a dashed line once the points ran sparse.
    for i in 0..v.len().saturating_sub(1) {
        let ((x0, y0), (x1, y1)) = (at(i), at(i + 1));
        let steps = (x1 - x0).abs().max((y1 - y0).abs()).max(1);
        for k in 0..=steps {
            ui.c.rect(x0 + (x1 - x0) * k / steps, y0 + (y1 - y0) * k / steps, 2, 2, c);
        }
    }
}

fn draw_spectrum(ui: &mut Ui, at: Rect, a: &Value, st: &mut State) {
    let t = ui.t;
    let lh = F8X13.height as i32 + 5;
    let mut y = at.y;
    if ui.button(rect(at.x, y, 90, 22), "Hybrid", !st.hybrid) {
        st.hybrid = true;
    }
    if ui.button(rect(at.x + 96, y, 90, 22), "Plain", st.hybrid) {
        st.hybrid = false;
    }
    let spec = a.get("spectrum").and_then(|x| x.get(if st.hybrid { "hybrid" } else { "plain" }));
    ui.label_in(at.x + 200, y + 4, at.w - 200, "A net's spectrogram: its middle layer's singular values, a column a champion, oldest at the left", &F8X13, t.dim);
    y += 30;
    let h = (at.h - 30) / 2 - lh;
    match spec.filter(|x| !arr(x, "columns").is_empty()) {
        None => {
            ui.label_in(at.x, y, at.w, "No champions of this kind yet.", &F8X13, t.dim);
        }
        Some(sp) => {
            let cols = grid(arr(sp, "columns"));
            let rows = cols.first().map(|c| c.len()).unwrap_or(0);
            let flip: Vec<Vec<f64>> = (0..rows).map(|r| cols.iter().map(|c| c[r]).collect()).collect();
            let max = flip.iter().flatten().fold(1e-6f64, |m, v| m.max(*v));
            let w = at.w * 3 / 5;
            ui.label_in(at.x, y, w, &format!("{} champions, {} shown; strongest direction at the top", n(sp, "champions"), n(sp, "shown")), &F8X13, t.ink);
            let r = rect(at.x, y + lh, w, h - lh);
            heatmap(ui, r, &flip, move |u, v| blend(u.t.tile, u.t.up, (v / max).sqrt()));
            cell_tip(ui, r, &flip, "Singular value", &[], &[], "How strong this direction of the middle layer is in this champion. Top is the strongest. New bright rows are new directions learned; a flat picture means the island has stopped learning.");
            let rx = r.right() + 14;
            let rw = at.right() - rx;
            let (norm, drift) = (nums(sp.get("norm").unwrap_or(&Value::Null)), nums(sp.get("drift").unwrap_or(&Value::Null)));
            ui.label_in(rx, y, rw, &format!("size of all its weights: now {:.0}", norm.last().copied().unwrap_or(0.0)), &F8X13, t.up);
            let c1 = rect(rx, y + lh, rw, (h - lh) / 2 - lh);
            ui.panel(c1, t.tile);
            line(ui, c1, &norm, t.up);
            line_tip(ui, c1, &norm, "Size of all its weights", "The norm of the whole net. Steady growth can mean confidence or only drift.");
            let y2 = c1.bottom() + 4;
            ui.label_in(rx, y2, rw, &format!("distance from where it began: now {:.0}", drift.last().copied().unwrap_or(0.0)), &F8X13, t.accent);
            let c2 = rect(rx, y2 + lh, rw, r.bottom() - y2 - lh);
            ui.panel(c2, t.tile);
            line(ui, c2, &drift, t.accent);
            line_tip(ui, c2, &drift, "Distance from where it began", "How far this champion's weights are from the first champion's.");
        }
    }
    y += h + 6;
    // The dials, promotion by promotion.
    if let Some(d) = a.get("dials") {
        let cells = grid(arr(d, "cells"));
        let names = arr(d, "dials");
        let commits = arr(d, "commits");
        ui.label_in(at.x, y, at.w, "The dials over the promotions, in doublings from before the first: left to right, oldest first", &F8X13, t.ink);
        y += lh;
        let lw = 150;
        let r = rect(at.x + lw, y, at.w - lw, (at.bottom() - y - lh).max(20));
        let max = cells.iter().flatten().fold(0.1f64, |m, v| m.max(v.abs()));
        heatmap(ui, r, &cells, move |u, v| heat(u, v, max));
        cell_tip(ui, r, &cells, "Doublings from before the first promotion", &words_of(names), &words_of(commits), "+1 is twice the value, -1 half. Read a row left to right: a dial that keeps moving one way is one the fleet keeps finding.");
        let rows = cells.len().max(1) as i32;
        for (i, nm) in names.iter().enumerate() {
            if r.h / rows >= F8X13.height as i32 {
                ui.label_in(at.x, r.y + i as i32 * r.h / rows, lw - 6, nm.as_str().unwrap_or(""), &F8X13, t.dim);
            }
        }
        for (i, c) in commits.iter().enumerate() {
            ui.label_in(r.x + i as i32 * r.w / commits.len().max(1) as i32 + 2, r.bottom() + 2, r.w / commits.len().max(1) as i32, c.as_str().unwrap_or(""), &F8X13, t.dim);
        }
    }
}

fn draw_matrices(ui: &mut Ui, at: Rect, a: &Value) {
    let t = ui.t;
    let lh = F8X13.height as i32 + 5;
    let Some(net) = a.get("net") else {
        ui.label_in(at.x, at.y, at.w, "No net to read yet.", &F8X13, t.dim);
        return;
    };
    let mut y = at.y;
    ui.label_in(at.x, y, at.w, &format!("The tables of {}, read as linear maps", s(net, "name")), &F8X13, t.ink);
    y += lh + 2;
    let cols = [(0, "layer"), (120, "size"), (200, "largest stretch"), (330, "total size"), (430, "stable rank"), (540, "effective rank"), (670, "near zero")];
    for (x, h) in cols {
        ui.label(at.x + x, y, h, &F8X13, t.dim);
    }
    y += lh;
    let layers = arr(net, "layers");
    for (i, l) in layers.iter().enumerate() {
        let vals = [
            format!("{}", i + 1),
            format!("{} x {}", n(l, "cols"), n(l, "rows")),
            format!("{:.1}", n(l, "spectral")),
            format!("{:.1}", n(l, "fro")),
            format!("{:.1}", n(l, "stable_rank")),
            format!("{:.0} of {:.0}", n(l, "effective_rank"), n(l, "rows").min(n(l, "cols"))),
            format!("{:.0}%", 100.0 * n(l, "sparsity")),
        ];
        for ((x, _), v) in cols.iter().zip(vals.iter()) {
            ui.label(at.x + x, y, v, &F8X13, t.ink);
        }
        y += lh;
    }
    y += 6;
    let half = (at.w - 16) / 2;
    let h = at.bottom() - y - lh;
    // The singular values, a scree plot a layer.
    ui.label_in(at.x, y, half, "Singular values by layer: how many directions each uses", &F8X13, t.dim);
    let scree = rect(at.x, y + lh, half, h);
    ui.panel(scree, t.tile);
    ui.tip(scree, || vec![
        "Singular values, one line a layer".to_string(),
        "How many independent directions a layer uses, largest first, on a log scale of three decades. A long flat tail means the layer has room it is not using, so a slot could be smaller.".to_string(),
    ]);
    let colours = [t.up, t.accent, t.warn];
    for (i, l) in layers.iter().enumerate() {
        let sv = l.get("sv").map(nums).unwrap_or_default();
        let max = sv.first().copied().unwrap_or(1.0).max(1e-6);
        let mut last = None;
        for (k, v) in sv.iter().enumerate() {
            let px = scree.x + 6 + k as i32 * (scree.w - 12) / sv.len().max(1) as i32;
            // A log scale, 3 decades: the tail is the story.
            let f = ((v / max).max(1e-3).log10() + 3.0) / 3.0;
            let py = scree.bottom() - 6 - (f * (scree.h - 12) as f64) as i32;
            if let Some((ox, oy)) = last {
                let steps = ((px - ox as i32).abs()).max((py - oy as i32).abs()).max(1);
                for s in 0..=steps {
                    ui.c.rect(ox + (px - ox) * s / steps, oy + (py - oy) * s / steps, 2, 2, colours[i % 3]);
                }
            }
            last = Some((px, py));
        }
    }
    // The transform end to end.
    let rx = at.x + half + 16;
    ui.label_in(rx, y, half, "W3 W2 W1: what each group of senses reaches, unbent", &F8X13, t.dim);
    let cells = grid(arr(net, "end_grid"));
    let (ins, outs) = (arr(net, "inputs"), arr(net, "outputs"));
    let lw = 56; // room for "signal"
    let r = rect(rx + lw, y + lh, half - lw, h - lh);
    let max = cells.iter().flatten().fold(1e-6f64, |m, v| m.max(*v));
    heatmap(ui, r, &cells, move |u, v| blend(u.t.tile, u.t.up, (v / max).sqrt()));
    cell_tip(ui, r, &cells, "Reach, senses to action", &words_of(outs), &words_of(ins), "The product W3 W2 W1, reduced to groups: what could reach this action from these senses if nothing bent. It ignores the activations, so it is an upper picture and not a measurement.");
    for (i, o) in outs.iter().enumerate() {
        let py = r.y + i as i32 * r.h / outs.len().max(1) as i32 + 3;
        ui.label_in(rx, py, lw - 4, o.as_str().unwrap_or(""), &F8X13, t.dim);
    }
    for (i, o) in ins.iter().enumerate() {
        let w = r.w / ins.len().max(1) as i32;
        ui.label_in(r.x + i as i32 * w + 2, r.bottom() + 2, w - 2, o.as_str().unwrap_or(""), &F8X13, t.dim);
    }
}

/// The senses as the tank has them: the compass round it, its own forward at the top, a ring
/// a channel, and the rest of the inputs as the instruments they are.
fn draw_senses(ui: &mut Ui, at: Rect, a: &Value) {
    let t = ui.t;
    let lh = F8X13.height as i32 + 5;
    let Some(net) = a.get("net") else {
        ui.label_in(at.x, at.y, at.w, "No net to read yet.", &F8X13, t.dim);
        return;
    };
    let listen = net.get("listen").map(nums).unwrap_or_default();
    if listen.len() < 143 {
        return;
    }
    let names = arr(a, "channels");
    ui.label_in(at.x, at.y, at.w, &format!("What {} listens to, laid out as the tank has it: brighter is a stronger first layer", s(net, "name")), &F8X13, t.ink);
    let max = listen.iter().fold(1e-6f64, |m, v| m.max(*v));
    let size = (at.h - lh * 2).min(at.w * 3 / 5);
    let (cx, cy) = (at.x + size / 2, at.y + lh * 2 + size / 2 - lh / 2);
    let rmax = (size / 2 - 14) as f64;
    let rings = 11;
    let inner = rmax * 0.14;
    // The polar grid, a dot at a time: sectors a wedge, channels a ring, the first one inside.
    let (mut py, ph) = (-(size / 2), size / 2);
    while py < ph {
        let mut px = -(size / 2);
        while px < size / 2 {
            let d = ((px * px + py * py) as f64).sqrt();
            if d >= inner && d < rmax {
                let ring = (((d - inner) / (rmax - inner)) * rings as f64) as usize;
                // Forward up, and clockwise on screen as the bearing grows.
                let ang = (px as f64).atan2(-(py as f64));
                let k = ((ang / (std::f64::consts::TAU / 8.0)).round() as i32).rem_euclid(8) as usize;
                let v = listen[k * 11 + ring.min(10)];
                ui.c.rect(cx + px, cy + py, 2, 2, blend(t.tile, t.up, (v / max).sqrt()));
            }
            px += 2;
        }
        py += 2;
    }
    {
        // The dot under the pointer: which sector, which ring, how much the net listens there.
        let (ppx, ppy) = ui.pointer();
        let (dx, dy) = (ppx - cx, ppy - cy);
        let d = ((dx * dx + dy * dy) as f64).sqrt();
        if d >= inner && d < rmax {
            let ring = ((((d - inner) / (rmax - inner)) * rings as f64) as usize).min(10);
            let ang = (dx as f64).atan2(-(dy as f64));
            let k = ((ang / (std::f64::consts::TAU / 8.0)).round() as i32).rem_euclid(8) as usize;
            let v = listen[k * 11 + ring];
            let bearing = ["ahead", "ahead right", "right", "behind right", "behind", "behind left", "left", "ahead left"][k];
            let rn = names.get(ring).and_then(|x| x.as_str()).unwrap_or("").to_string();
            ui.tip(rect(cx - rmax as i32, cy - rmax as i32, 2 * rmax as i32, 2 * rmax as i32), || vec![
                format!("{}: {}", rn, bearing),
                format!("Sense number {}. The first layer's weight on it: {:.3}.", k * 11 + ring, v),
                "Bright means the net listens to this channel from this direction. Dark all round means nobody uses it, and it could go.".to_string(),
            ]);
        }
    }
    // The tank, pointing forward.
    ui.c.disc(cx, cy, 7, t.ink);
    ui.c.rect(cx - 1, cy - 16, 3, 12, t.ink);
    ui.label(cx - 20, cy - (size / 2) - 2, "ahead", &F8X13, t.dim);
    // The rings' names, and the rest of the inputs.
    let x = at.x + size + 18;
    let w = at.right() - x;
    let mut y = at.y + lh;
    ui.label_in(x, y, w, "Rings, from the tank outward", &F8X13, t.dim);
    y += lh - 2;
    let per: Vec<f64> = (0..11).map(|c| (0..8).map(|k| listen[k * 11 + c]).sum::<f64>() / 8.0).collect();
    let ring_max = per.iter().fold(1e-6f64, |m, v| m.max(*v));
    for (c, nm) in names.iter().enumerate().take(11) {
        ui.label_in(x, y, 146, &format!("{} {}", c + 1, nm.as_str().unwrap_or("")), &F8X13, t.ink);
        let bw = ((w - 150) as f64 * per[c] / ring_max) as i32;
        ui.c.rect(x + 150, y + 3, bw.max(1), 9, t.up);
        ui.tip(rect(x, y, w, lh - 3), || vec![format!("Ring {}: {}", c + 1, nm.as_str().unwrap_or("")), format!("The first layer's weight on this channel, over all eight directions: {:.3}.", per[c])]);
        y += lh - 3;
    }
    y += 6;
    ui.label_in(x, y, w, "The instruments, each number a bar", &F8X13, t.dim);
    y += lh - 2;
    let mut from = 88;
    for (nm, count) in [("body", 12), ("navigation", 6), ("contacts", 18), ("hints", 9), ("shells", 5), ("air", 5)] {
        ui.label_in(x, y + 2, 90, nm, &F8X13, t.ink);
        let bw = ((w - 96) / count).clamp(2, 18);
        for i in 0..count {
            let v = listen[from + i as usize];
            let h = (v / max * (lh - 2) as f64).max(1.0) as i32;
            ui.c.rect(x + 96 + i * bw, y + lh - 2 - h, (bw - 1).max(1), h, t.up);
            ui.tip(rect(x + 96 + i * bw, y, bw, lh), || vec![format!("{}, number {} of {}", nm, i + 1, count), format!("Sense number {}. The first layer's weight on it: {:.3}.", from + i as usize, v)]);
        }
        from += count as usize;
        y += lh + 2;
    }
}

/// How the fleet orchestrates now: the three roads to a better brain, and the one way onto main.
fn draw_fleet(ui: &mut Ui, at: Rect, a: &Value) {
    let t = ui.t;
    let lh = F8X13.height as i32 + 5;
    let null = Value::Null;
    let f = a.get("fleet").unwrap_or(&null);
    let box_ = |ui: &mut Ui, r: Rect, title: &str, l1: String, l2: String, hot: bool| {
        ui.panel(r, t.tile);
        ui.outline(r, if hot { t.up } else { t.line });
        ui.label_in(r.x + 8, r.y + 5, r.w - 16, title, &F8X13, t.ink);
        ui.label_in(r.x + 8, r.y + 5 + lh, r.w - 16, &l1, &F8X13, t.dim);
        ui.label_in(r.x + 8, r.y + 5 + lh * 2, r.w - 16, &l2, &F8X13, t.dim);
        ui.tip(r, || vec![title.to_string(), l1.clone(), l2.clone(), "Queue, Flow draws this road in full, with what each stage takes and gives.".to_string()]);
    };
    let arrow = |ui: &mut Ui, x0: i32, y0: i32, x1: i32, y1: i32| {
        let steps = (x1 - x0).abs().max((y1 - y0).abs()).max(1);
        for s in 0..=steps {
            ui.c.rect(x0 + (x1 - x0) * s / steps, y0 + (y1 - y0) * s / steps, 2, 2, ui.t.accent);
        }
        ui.c.disc(x1, y1, 4, ui.t.accent);
    };
    ui.label_in(at.x, at.y, at.w, "One planner on this Mac, the machines working what it asks, and one way onto main", &F8X13, t.ink);
    let top = at.y + lh + 4;
    let bh = lh * 3 + 12;
    let gap = 26;
    // The rows share what height there is, leaving room for the line under them.
    let vgap = ((at.h - lh * 3 - 16 - bh * 4) / 3).max(12);
    let w = (at.w - gap * 4) / 5;
    let col = |i: i32| at.x + i * (w + gap);
    // Where trials come from.
    let rows = [
        ("The fit (suggest.py)", "dials: curves over reads".to_string(), "a new generation when low".to_string()),
        ("A/B (ab_trials)", "each switch and version".to_string(), "whole numbers only".to_string()),
        ("Transform (patch runs)", format!("step {:.0} of {:.0}", n(f, "transform_step"), n(f, "transform_of")), format!("{:.0} slots filled", n(f, "patches"))),
    ];
    let mut src = Vec::new();
    for (i, (ti, a1, b1)) in rows.iter().enumerate() {
        let r = rect(col(0), top + i as i32 * (bh + vgap), w, bh);
        box_(ui, r, ti, a1.clone(), b1.clone(), true);
        src.push(r);
    }
    let mid = top + bh + vgap;
    let road = [
        ("First read: 55 seeds", format!("{:.0} waiting on a read", n(f, "reading")), format!("{:.0} dropped", n(f, "dropped"))),
        ("Read on: to 418 seeds", format!("{:.0} reading on", n(f, "read_on")), format!("{:.0} passed", n(f, "passed"))),
        ("Held out: 400 + 400", "second read only if the".to_string(), format!("first is 0+; {:.0} waiting", n(f, "held_waiting"))),
        ("Families and tests", "on a branch first".to_string(), format!("{:.0} promoted to main", n(f, "promotions"))),
    ];
    let mut prev: Option<Rect> = None;
    for (i, (ti, a1, b1)) in road.iter().enumerate() {
        let r = rect(col(i as i32 + 1), mid, w, bh);
        box_(ui, r, ti, a1.clone(), b1.clone(), i == 3);
        if let Some(p) = prev {
            arrow(ui, p.right() + 2, p.y + p.h / 2, r.x - 5, r.y + r.h / 2);
        }
        prev = Some(r);
    }
    for r in &src {
        arrow(ui, r.right() + 2, r.y + r.h / 2, col(1) - 5, mid + bh / 2);
    }
    // Under it: the rest of the machine.
    let y2 = top + (bh + vgap) * 3;
    let lower = [
        ("Crucible, GPU islands", format!("{:.0} islands, {:.0} segments", n(f, "islands"), n(f, "segments")), format!("milestones: {:.0}; not treadcore", n(f, "milestones"))),
        ("Fleet Chat and verbs", "certificates, forced command".to_string(), "orrery hosts the room".to_string()),
        ("Keeper and lanes", "a lane a machine; retried".to_string(), "new code restarts it".to_string()),
        ("Retired from rotation", "train school record spsa tune".to_string(), "parts switches round robin".to_string()),
    ];
    let lw = (at.w - gap * 3) / 4;
    for (i, (ti, a1, b1)) in lower.iter().enumerate() {
        let r = rect(at.x + i as i32 * (lw + gap), y2, lw, bh);
        box_(ui, r, ti, a1.clone(), b1.clone(), i < 3);
    }
    if let Some(l) = a.get("limits") {
        let decrees: Vec<String> = arr(l, "decrees").iter().filter_map(|d| d.as_str().map(String::from)).collect();
        let line = format!("By decree, part of the game: {}. {} numbers have a range.", if decrees.is_empty() { "none".to_string() } else { decrees.join(", ") }, n(l, "limited"));
        ui.label_in(at.x, y2 - lh - 2, at.w, &line, &F8X13, t.warn);
    }
    ui.label_in(at.x, y2 + bh + 8, at.w, &format!("Counted at {} from {} reads in the ledger.", s(a, "at"), n(a, "reads")), &F10X20, t.dim);
}

/// The tab shown, in `at`. False: the caller draws the Patch tab.
pub fn draw(ui: &mut Ui, at: Rect, a: Option<&Value>, st: &mut State) -> bool {
    if st.tab == 0 {
        return false;
    }
    let Some(a) = a else {
        ui.label_in(at.x, at.y, at.w, "The analysis is being worked out; it takes about a minute.", &F8X13, ui.t.dim);
        return true;
    };
    match st.tab {
        1 => draw_terrain(ui, at, a, st),
        2 => draw_spectrum(ui, at, a, st),
        3 => draw_matrices(ui, at, a),
        4 => draw_senses(ui, at, a),
        _ => draw_fleet(ui, at, a),
    }
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_higher_point_draws_higher_and_a_turn_keeps_the_centre() {
        let low = project(0.2, 0.3, 0.0, 0.7, 100.0, 100.0, 50.0);
        let high = project(0.2, 0.3, 20.0, 0.7, 100.0, 100.0, 50.0);
        assert_eq!(high.1, low.1 - 20.0);
        assert_eq!(project(0.0, 0.0, 0.0, 2.1, 100.0, 80.0, 50.0).0, 100.0);
    }

    /// One frame of the terrain, over a dataset written to a file, with these events.
    fn frame(st: &mut State, doc: &Value, ev: &[crate::surface::Input], ui_state: &mut crate::ui::UiState) {
        let (w, h) = (1200usize, 700usize);
        let mut px = vec![0u8; w * h * 4];
        let mut c = crate::draw::Canvas::new(&mut px, w, h);
        let mut ui = Ui::begin(&mut c, crate::draw::LIGHT, ev, ui_state);
        draw_terrain(&mut ui, rect(0, 0, w as i32, h as i32), doc, st);
        ui.finish();
    }

    #[test]
    fn a_region_is_drawn_on_the_flat_map_and_asks_for_trials() {
        use crate::surface::{Button, Input};
        let dir = std::env::temp_dir().join(format!("orrery-terrain-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let row = format!("[{}]", vec!["0.5"; 30].join(","));
        let table = format!("[{}]", vec![row; 30].join(","));
        let pair = format!(r#"{{"a":"w_a","b":"w_b","ax":[-1,1],"ay":[-1,1],"h":0.2,"today":[2,8],"reads":40,"z":{t},"support":{t},"log":true,"peaks":[{{"ix":15,"iy":15,"z":0.5,"x":0.0,"y":0.0,"a":2,"b":8,"word":"bare","reads":1,"seeds":55,"jobs":0}}],"dots":[[0.1,0.1,0.2],[0.9,0.9,0.1]],"jobs":[],"regions":[]}}"#, t = table);
        std::fs::write(dir.join("every.json"), format!(r#"{{"id":"every","unit":"points","can_send":true,"pairs":[{}]}}"#, pair)).unwrap();
        let idx = crate::json::parse(&format!(r#"{{"terrains":{{"dir":"{}","datasets":[{{"id":"every","label":"Every map","group":"reads","peaks":1,"bare":1,"reading":0,"read":0,"pairs":1}}],"reads":{{"used":40}}}}}}"#, dir.display())).unwrap();
        let mut st = State { operator: true, ..Default::default() };
        let mut us = crate::ui::UiState::default();
        frame(&mut st, &idx, &[], &mut us);
        assert!(st.sel.is_none());
        // The plot and the flat map, by the screen's own sums.
        let lh = F8X13.height as i32 + 5;
        let plot_w = 1200 - 212 - 240 - 18;
        let plot_right = 212 + 6 + plot_w;
        let size = (plot_w * 44 / 100).min(700 - lh * 2 - 2 - lh * 3);
        let (fx, fy) = (plot_right - size, lh * 2 + 2 + 4);
        // Down at the middle of the map, across a quarter of it and up a quarter, and let go.
        let (mx, my) = (fx + size / 2, fy + size / 2);
        frame(&mut st, &idx, &[Input::Button { x: mx, y: my, button: Button::Left, down: true }], &mut us);
        assert!(st.drag.is_some(), "a press on the map begins a region");
        frame(&mut st, &idx, &[Input::Motion { x: mx + size / 4, y: my - size / 4 }], &mut us);
        frame(&mut st, &idx, &[Input::Button { x: mx + size / 4, y: my - size / 4, button: Button::Left, down: false }], &mut us);
        let b = st.sel.expect("a region");
        assert!(st.drag.is_none());
        assert!(b[0].abs() < 0.03 && (b[1] - 0.5).abs() < 0.03 && b[2].abs() < 0.03 && (b[3] - 0.5).abs() < 0.03, "{:?}", b);
        // Its button: the side panel, under the pair, turn, one maximum and four lines.
        let by = (0..700).step_by(2).find_map(|y| {
            let mut probe = st.clone();
            let mut u2 = crate::ui::UiState::default();
            frame(&mut probe, &idx, &[Input::Button { x: 1200 - 240 + 40, y, button: Button::Left, down: true }], &mut u2);
            frame(&mut probe, &idx, &[Input::Button { x: 1200 - 240 + 40, y, button: Button::Left, down: false }], &mut u2);
            probe.ask.clone()
        });
        let ask = by.expect("a press finds the button");
        // Real values, not doublings: a quarter of a map two doublings wide is half a doubling from today's 2 and 8.
        let f: Vec<&str> = ask.split(' ').collect();
        let num = |i: usize| f[i].parse::<f64>().unwrap();
        assert!(f[0] == "add" && f[1] == "w_a" && f[4] == "w_b" && f[7] == "6", "{}", ask);
        assert!((num(2) - 2.0).abs() < 0.05 && (num(3) - 2.83).abs() < 0.05 && (num(5) - 8.0).abs() < 0.1 && (num(6) - 11.31).abs() < 0.1, "{}", ask);
        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn a_region_is_its_corners_either_way_round() {
        assert_eq!(corners((2.0, -1.0), (1.0, 3.0)), [1.0, 2.0, -1.0, 3.0]);
        let b = corners((0.0, 0.0), (1.0, 1.0));
        assert!(inside(&b, 0.5, 1.0) && !inside(&b, 1.5, 0.5) && !inside(&b, 0.5, -0.1));
    }

    #[test]
    fn a_blend_runs_from_one_colour_to_the_other() {
        assert_eq!(blend(0x000000, 0xffffff, 0.0), 0x000000);
        assert_eq!(blend(0x000000, 0xffffff, 1.0), 0xffffff);
        assert_eq!(blend(0x102030, 0x102030, 0.5), 0x102030);
    }
}
