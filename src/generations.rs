//! Results, Generations: the lab report *Outgrowing Yourself*, live, a tab a figure.
//!
//! Paul, 6 November: "place each of the graphs about held out read of the generations of the map. use the
//! sequence of the Outgrowing Yourself lab report, and include their visualizations in the tabs of Orrery
//! ... scrollable generational inspections, growth observers dashboard. show scrolling sections (mouse
//! wheel, scroll bars).. All the graphs live with data. The Computer Hours and what they bought
//! calculated." The tabs follow the report: the roads from a computation to main (its Fig. 1), the nine
//! days in lanes (Fig. 2), every generation's turnaround (Fig. 3), what a generation claims and what main
//! keeps (Fig. 4), the GPU's ladder, exams and yardstick (Fig. 5), the forest home's elections on the CUDA
//! gauntlet -- the step it weighs, the bar it meets and the floors it holds -- and the hours with what
//! they bought (Fig. 6). The numbers are the report's own: tools/report/outgrowing.py --view writes them
//! to plan/generations.json, treadcore-view.py hands them here, and asks for a fresh copy when the one
//! it has is ten minutes old. A long list scrolls with the wheel or its bar; a mark says its numbers to
//! the pointer. THE PAGE DRAWS; it asks for nothing and moves nothing.
use crate::draw::Rgb;
use crate::font::{F6X10, F8X13};
use crate::json::Value;
use crate::ui::{rect, Rect, Ui};

/// What the page remembers between frames: the tab, and each tab's first row shown.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct State {
    pub tab: usize,
    pub off: [usize; 8],
}

pub const TABS: [&str; 7] = ["Roads", "Days", "Turnaround", "Kept", "GPU", "Gauntlet", "Hours"];

fn s(v: &Value, k: &str) -> String {
    match v.get(k) {
        Some(Value::Str(x)) => x.clone(),
        Some(Value::Num(x)) => format!("{}", x),
        Some(Value::Bool(b)) => format!("{}", b),
        _ => String::new(),
    }
}
fn n(v: &Value, k: &str) -> Option<f64> {
    v.get(k).and_then(|x| x.as_num())
}
fn arr<'a>(v: &'a Value, k: &str) -> &'a [Value] {
    v.get(k).and_then(|x| x.as_array()).map(|a| &a[..]).unwrap_or(&[])
}
/// An object's entries, in key order (json.rs keeps objects as a BTreeMap).
fn obj(v: &Value) -> Option<&std::collections::BTreeMap<String, Value>> {
    match v {
        Value::Obj(m) => Some(m),
        _ => None,
    }
}
fn at(v: &Value, i: usize) -> Option<&Value> {
    v.as_array().and_then(|a| a.get(i))
}
fn num_at(v: &Value, i: usize) -> Option<f64> {
    at(v, i).and_then(|x| x.as_num())
}
fn str_at(v: &Value, i: usize) -> String {
    match at(v, i) {
        Some(Value::Str(x)) => x.clone(),
        Some(Value::Num(x)) => format!("{}", x),
        _ => String::new(),
    }
}

/// "2026-11-06T05:20:51" as seconds since 1970, read as one clock: every time on the page is the
/// coordinator's local time, and only their differences are drawn.
pub fn secs(t: &str) -> Option<f64> {
    let b = t.as_bytes();
    if b.len() < 16 {
        return None;
    }
    let p = |a: usize, l: usize| t.get(a..a + l).and_then(|x| x.parse::<i64>().ok());
    let (y, mo, d, h, mi) = (p(0, 4)?, p(5, 2)?, p(8, 2)?, p(11, 2)?, p(14, 2)?);
    let sec = if b.len() >= 19 { p(17, 2).unwrap_or(0) } else { 0 };
    // Days from the civil date (Howard Hinnant's days_from_civil).
    let yy = if mo <= 2 { y - 1 } else { y };
    let era = if yy >= 0 { yy } else { yy - 399 } / 400;
    let yoe = yy - era * 400;
    let doy = (153 * (if mo > 2 { mo - 3 } else { mo + 9 }) + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    let days = era * 146097 + doe - 719468;
    Some((days * 86400 + h * 3600 + mi * 60 + sec) as f64)
}

fn dark(ui: &Ui) -> bool {
    let b = ui.t.base;
    ((b >> 16) & 255) + ((b >> 8) & 255) + (b & 255) < 384
}
/// The report's colours: blue the GPU, orange the line and its CPUs, the theme's green main.
fn gpu(ui: &Ui) -> Rgb {
    if dark(ui) { 0x3987e5 } else { 0x1c5cab }
}
fn cpu(ui: &Ui) -> Rgb {
    if dark(ui) { 0xd95926 } else { 0xc04a1c }
}

/// A line two pixels wide: the canvas has rects and discs, so this one is stepped.
fn line(ui: &mut Ui, x0: i32, y0: i32, x1: i32, y1: i32, c: Rgb) {
    let (dx, dy) = ((x1 - x0).abs(), -(y1 - y0).abs());
    let (sx, sy) = (if x0 < x1 { 1 } else { -1 }, if y0 < y1 { 1 } else { -1 });
    let (mut x, mut y, mut e) = (x0, y0, dx + dy);
    for _ in 0..4000 {
        ui.c.rect(x, y, 2, 2, c);
        if x == x1 && y == y1 {
            break;
        }
        let e2 = 2 * e;
        if e2 >= dy {
            e += dy;
            x += sx;
        }
        if e2 <= dx {
            e += dx;
            y += sy;
        }
    }
}
/// The same, dashed.
fn dashed(ui: &mut Ui, x0: i32, y0: i32, x1: i32, y1: i32, c: Rgb) {
    let len = (((x1 - x0) as f64).hypot((y1 - y0) as f64)).max(1.0);
    let k = (len / 8.0).ceil() as i32;
    for i in (0..k).step_by(2) {
        let a = i as f64 / k as f64;
        let b = ((i + 1) as f64 / k as f64).min(1.0);
        line(ui, x0 + ((x1 - x0) as f64 * a) as i32, y0 + ((y1 - y0) as f64 * a) as i32, x0 + ((x1 - x0) as f64 * b) as i32, y0 + ((y1 - y0) as f64 * b) as i32, c);
    }
}

/// The tab strip; returns what is left under it.
fn tabs(ui: &mut Ui, at: Rect, st: &mut State) -> Rect {
    let w = 104;
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

/// A chart's frame: its title, a box, the y grid at `ticks` with their labels; returns the plot area
/// and the y scale (value -> pixel).
fn frame(ui: &mut Ui, r: Rect, title: &str, lo: f64, hi: f64, ticks: &[f64], unit: &str) -> (Rect, impl Fn(f64) -> i32) {
    let t = ui.t;
    ui.label_in(r.x, r.y, r.w, title, &F8X13, t.ink);
    let plot = rect(r.x + 44, r.y + 20, r.w - 52, r.h - 38);
    ui.outline(plot, t.line);
    let (py, ph) = (plot.y, plot.h);
    let sy = move |v: f64| py + ph - ((v.clamp(lo, hi) - lo) / (hi - lo).max(1e-9) * ph as f64) as i32;
    for &v in ticks {
        let y = sy(v);
        ui.c.hline(plot.x + 1, y, plot.w - 2, t.line);
        ui.label_right(plot.x - 4, y - 5, &format!("{}{}", fmt_tick(v), unit), &F6X10, t.dim);
    }
    (plot, sy)
}
fn fmt_tick(v: f64) -> String {
    if v.fract().abs() < 1e-9 { format!("{:.0}", v) } else { format!("{:.2}", v) }
}
/// Day lines across a time span, labelled under the plot: returns the x scale.
fn days(ui: &mut Ui, plot: Rect, t0: f64, t1: f64) -> impl Fn(f64) -> i32 {
    let t = ui.t;
    let (px, pw) = (plot.x, plot.w);
    let sx = move |v: f64| px + ((v - t0) / (t1 - t0).max(1.0) * pw as f64) as i32;
    let mut d = (t0 / 86400.0).ceil() * 86400.0;
    while d <= t1 {
        let x = sx(d);
        ui.c.vline(x, plot.y + 1, plot.h - 2, t.line);
        let day = ((d / 86400.0) as i64 + 719468) as i64;
        let (_, m, dd) = civil(day);
        ui.label(x + 2, plot.bottom() + 3, &format!("{} {}", dd, ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][(m - 1) as usize]), &F6X10, t.dim);
        d += 86400.0;
    }
    sx
}
/// A day number back to its date (Hinnant's civil_from_days, from days + 719468).
fn civil(z: i64) -> (i64, i64, i64) {
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    (yoe + era * 400 + if m <= 2 { 1 } else { 0 }, m, d)
}

pub fn draw(ui: &mut Ui, at: Rect, doc: Option<&Value>, st: &mut State) {
    let t = ui.t;
    let Some(doc) = doc.filter(|d| !matches!(d, Value::Null)) else {
        ui.label_in(at.x, at.y, at.w, "Not read yet: the view asks tools/report/outgrowing.py for plan/generations.json; it comes within a minute.", &F8X13, t.dim);
        return;
    };
    let age = n(doc, "age_s").map(|a| format!(", {} min ago", (a / 60.0).round())).unwrap_or_default();
    ui.label_in(at.x, at.y, at.w, &format!("The lab report Outgrowing Yourself, live: read at {}{}. The tabs are its figures, in its order.", s(doc, "at").replace('T', " "), age), &F8X13, t.dim);
    let body = tabs(ui, rect(at.x, at.y + 20, at.w, at.h - 20), st);
    let tab = st.tab.min(TABS.len() - 1);
    let off = &mut st.off[tab];
    match tab {
        0 => roads(ui, body, doc),
        1 => lanes(ui, body, doc),
        2 => turnaround(ui, body, doc, off),
        3 => kept(ui, body, doc, off),
        4 => ladder(ui, body, doc),
        5 => elections(ui, body, doc, off),
        _ => hours(ui, body, doc, off),
    }
}

/// A box of the roads, its title and lines; returns its rect.
fn node(ui: &mut Ui, r: Rect, c: Rgb, title: &str, lines: &[String]) -> Rect {
    let t = ui.t;
    ui.panel(r, t.tile);
    ui.c.frame(r.x, r.y, r.w, r.h, c);
    ui.c.frame(r.x + 1, r.y + 1, r.w - 2, r.h - 2, c);
    ui.label_in(r.x + 8, r.y + 6, r.w - 16, title, &F8X13, t.ink);
    for (i, l) in lines.iter().enumerate() {
        ui.label_in(r.x + 8, r.y + 24 + i as i32 * 12, r.w - 16, l, &F6X10, t.dim);
    }
    r
}
fn arrow_down(ui: &mut Ui, x: i32, y0: i32, y1: i32, c: Rgb) {
    ui.c.rect(x - 1, y0, 2, y1 - y0 - 4, c);
    for k in 0..6 {
        ui.c.hline(x - 6 + k, y1 - 6 + k, 12 - 2 * k, c);
    }
}

/// Fig. 1: the roads, each gate's condition, and what stands on each road now.
fn roads(ui: &mut Ui, at: Rect, doc: &Value) {
    let t = ui.t;
    let (g, c, m) = (gpu(ui), cpu(ui), t.up);
    let w = ((at.w - 60) / 2).min(420);
    let (xg, xc) = (at.x, at.x + w + 60);
    let forest = doc.get("homes").and_then(|h| h.get("crucible-world-hybrid-forest"));
    let bar = forest.and_then(|f| n(f, "bar")).map(|b| format!("the bar now {:.2} z (eases when dry, tightens after each)", b)).unwrap_or_else(|| "the bar: 2 se head to head (the world home)".into());
    let floors = forest.map(|f| f.get("floors").and_then(|x| obj(x)).map(|o| o.len()).unwrap_or(0)).unwrap_or(0);
    let best = forest.and_then(|f| f.get("best")).filter(|b| !matches!(b, Value::Null));
    ui.label(xg, at.y, "GPU, three CUDA cards", &F8X13, g);
    ui.label(xc, at.y, "CPU fleet, the census", &F8X13, c);
    let h = 62;
    let gb: [(&str, Vec<String>); 4] = [
        ("Segment: 100 generations", vec!["trees, walls, the takeover; a quarter of".into(), "each individual's warps play the gauntlet's tasks".into(), "exam, yardstick, and the CUDA gauntlet".into()]),
        ("Generation (milestone)", vec!["every floor held; no worse on the yardstick;".into(), bar, format!("floors: {} files at today's success", floors)]),
        ("Bridge read (Gladiator)", vec!["the newest generation as style 17,".into(), "two censuses of 48 seeds, all maps".into(), "better by two errors: it ships itself".into()]),
        ("A net file on main", vec!["nets/gladiator.bin: styles tests, push".into(), "no proof: a style, not the dials".into(), best.map(|b| format!("the window's best: {} {:+.2} z", s(b, "job"), n(b, "zg").unwrap_or(0.0))).unwrap_or_else(|| "the window's best: none yet".into())]),
    ];
    let mut y = at.y + 22;
    for (i, (title, lines)) in gb.iter().enumerate() {
        node(ui, rect(xg, y, w, h), g, title, lines);
        if i + 1 < gb.len() {
            arrow_down(ui, xg + w / 2, y + h, y + h + 18, g);
        }
        y += h + 18;
    }
    let pf = doc.get("proof");
    let line_n = doc.get("line").map(|l| arr(l, "promotions").len()).unwrap_or(0);
    let cb: [(&str, Vec<String>); 5] = [
        ("Trial", vec!["a few dials, drawn by suggest.py".into(), "from the fit of every census so far".into()]),
        ("First read, read-ons, held-out", vec!["55 seeds, on to ~190 over the eased bar;".into(), "400 seeds no search has seen".into()]),
        ("Families, gauntlet, tests", vec!["9 families, 22 CPU gauntlets, 168 tests".into(), "each at its floor".into()]),
        ("The line", vec!["orrery/accepted: committed, built everywhere".into(), format!("{} generations on it now", line_n)]),
        ("Main: the proof", vec!["main's values vs the line, 800 seeds an hour,".into(), "pooled while the game's source stands; z >= 3".into(),
                               pf.map(|p| format!("last: {} {:+.2} ± {:.2}, z {:.2}", s(p, "head"), n(p, "d").unwrap_or(0.0), n(p, "se").unwrap_or(0.0), n(p, "z").unwrap_or(0.0))).unwrap_or_default()]),
    ];
    let mut y = at.y + 22;
    let hc = ((at.h - 30) / 5 - 16).clamp(44, 62);
    for (i, (title, lines)) in cb.iter().enumerate() {
        node(ui, rect(xc, y, w, hc), if i == 4 { m } else { c }, title, lines);
        if i + 1 < cb.len() {
            arrow_down(ui, xc + w / 2, y + hc, y + hc + 14, if i == 3 { m } else { c });
        }
        y += hc + 14;
    }
    // The connection that does not exist.
    dashed(ui, xg + w, at.y + 22 + h + 18 + h / 2, xc, at.y + 22 + hc + 14 + hc / 2, t.dim);
    ui.label(xg + w + 4, at.y + 22 + h + 18 + h / 2 + 6, "no wire", &F6X10, t.dim);
    ui.label_in(at.x, at.bottom() - 14, at.w, "Blue the GPU's road, orange the line, green main. Dashed: no GPU number reaches the line's dials; a GPU net plays as a style a person picks.", &F6X10, t.dim);
}

/// Fig. 2: the days in lanes, every mark with its numbers to the pointer.
fn lanes(ui: &mut Ui, at: Rect, doc: &Value) {
    let t = ui.t;
    let gens = arr(doc, "gens");
    let t1 = secs(&s(doc, "at")).unwrap_or(0.0);
    let t0 = gens.iter().filter_map(|g| secs(&s(g, "committed"))).fold(t1, f64::min) - 3600.0 * 6.0;
    let plot = rect(at.x + 150, at.y + 6, at.w - 160, at.h - 40);
    ui.outline(plot, t.line);
    let sx = days(ui, plot, t0, t1);
    let names = ["GPU generations", "GPU nets, clones", "Game versions", "Line commits", "Main moves", "Forest elections"];
    let lh = plot.h / names.len() as i32;
    for (i, nm) in names.iter().enumerate() {
        let y = plot.y + lh * i as i32 + lh / 2;
        ui.label(at.x, y - 6, nm, &F8X13, t.dim);
        ui.c.hline(plot.x + 1, y, plot.w - 2, t.line);
    }
    let ly = |i: usize| plot.y + lh * i as i32 + lh / 2;
    let (g, c) = (gpu(ui), cpu(ui));
    let mut marks: Vec<(Rect, Vec<String>)> = vec![];
    for m in arr(doc, "milestones") {
        if let Some(x) = secs(&s(m, "made")).filter(|x| *x >= t0) {
            let r = rect(sx(x) - 4, ly(0) - 4, 9, 9);
            ui.c.disc(sx(x), ly(0), 4, g);
            marks.push((r, vec![s(m, "id"), format!("made {}, {:.1} se over the one before", s(m, "made").replace('T', " "), n(m, "margin").unwrap_or(0.0))]));
        }
    }
    if let Some(f) = doc.get("homes").and_then(|h| h.get("crucible-world-hybrid-forest")) {
        // THE CARD ELECTS, THE GAME CREDITS: filled when the game's census confirmed it (the bridge shipped
        // it), a ring when the game read it and did not, a small dot while it waits for its read.
        for m in arr(f, "milestones").iter().filter(|m| !matches!(m.get("carried"), Some(Value::Bool(true)))) {
            if let Some(x) = secs(&s(m, "made")) {
                let gm = m.get("game").filter(|g| !matches!(g, Value::Null));
                let credited = gm.map(|g| matches!(g.get("credited"), Some(Value::Bool(true)))).unwrap_or(false);
                match (gm, credited) {
                    (Some(_), true) => ui.c.disc(sx(x), ly(0), 6, t.up),
                    (Some(_), false) => ui.c.ring(sx(x), ly(0), 5, t.up),
                    _ => ui.c.disc(sx(x), ly(0), 2, t.up),
                }
                let game = gm.map(|g| format!("in the game {:+.2} ± {:.2} over the shipped one: {}", n(g, "diff").unwrap_or(0.0), n(g, "se").unwrap_or(0.0),
                                              if credited { "credited, shipped" } else { "not confirmed" })).unwrap_or_else(|| "not yet read in the game".into());
                marks.push((rect(sx(x) - 6, ly(0) - 6, 13, 13), vec![s(m, "id"), format!("a forest generation, made {}", s(m, "made").replace('T', " ")), game]));
            }
        }
        for e in arr(f, "elections") {
            if let Some(x) = secs(&s(e, "time")) {
                let ok = s(e, "result").starts_with("milestone");
                let y = ly(5);
                if ok { ui.c.disc(sx(x), y, 4, t.up) } else { ui.c.ring(sx(x), y, 3, g) }
                marks.push((rect(sx(x) - 4, y - 4, 9, 9), vec![format!("{} {}, generation {}", s(e, "job"), s(e, "island"), s(e, "gen")), format!("gauntlet {} z, yardstick {} z, bar {}", s(e, "zg"), s(e, "zy"), s(e, "bar")), s(e, "result")]));
            }
        }
    }
    for sh in arr(doc, "ships") {
        if let Some(x) = secs(&s(sh, "at")) {
            ui.c.rect(sx(x) - 5, ly(1) - 8, 10, 8, g);
            marks.push((rect(sx(x) - 5, ly(1) - 8, 10, 8), vec![format!("{} {}", s(sh, "sha"), s(sh, "at").replace('T', " ")), s(sh, "subject").chars().take(90).collect()]));
        }
    }
    for cl in arr(doc, "clone") {
        if let Some(x) = secs(&s(cl, "asked")) {
            ui.c.frame(sx(x) - 5, ly(1) + 1, 10, 8, g);
            marks.push((rect(sx(x) - 5, ly(1) + 1, 10, 8), vec![format!("clone round {} asked {}", s(cl, "n"), s(cl, "asked").replace('T', " ")),
                                                                format!("against the Scholar {:+.2} ± {:.2}: {}", n(cl, "diff").unwrap_or(0.0), n(cl, "se").unwrap_or(0.0), if matches!(cl.get("holds"), Some(Value::Bool(true))) { "shipped" } else { "not shipped" })]));
        }
    }
    for v in arr(doc, "versions") {
        if let Some(x) = secs(&s(v, "at")) {
            ui.c.rect(sx(x) - 1, ly(2) - 7, 3, 14, t.dim);
            marks.push((rect(sx(x) - 3, ly(2) - 7, 7, 14), vec![format!("{} at {}", s(v, "what"), s(v, "at").replace('T', " "))]));
        }
    }
    for gg in gens {
        if let Some(x) = secs(&s(gg, "committed")) {
            let hand = s(gg, "by") != "auto";
            if hand { ui.c.ring(sx(x), ly(3), 4, c) } else { ui.c.disc(sx(x), ly(3), 4, c) }
            let held = gg.get("held").map(|h| format!("held out {:+.2} ± {:.2}", num_at(h, 0).unwrap_or(0.0), num_at(h, 1).unwrap_or(0.0))).unwrap_or_else(|| "no held-out read".into());
            marks.push((rect(sx(x) - 4, ly(3) - 4, 9, 9), vec![format!("{} {} committed {}", s(gg, "run"), s(gg, "trial"), s(gg, "committed").replace('T', " ")), held, s(gg, "status")]));
        }
    }
    for mv in arr(doc, "moves") {
        if let Some(x) = secs(&s(mv, "at")) {
            ui.c.rect(sx(x) - 4, ly(4) - 6, 8, 12, t.up);
            marks.push((rect(sx(x) - 4, ly(4) - 6, 8, 12), vec![format!("main moved {} to {}", s(mv, "at").replace('T', " "), s(mv, "sha")), format!("{} generations", arr(mv, "trials").len())]));
        }
    }
    for (r, lines) in marks {
        ui.tip(r, move || lines);
    }
    ui.label_in(at.x, at.bottom() - 14, at.w, "Hover a mark. Hollow dots: generations by hand. Forest elections: filled when a segment became a generation, a ring when it did not.", &F6X10, t.dim);
}

/// Fig. 3: every generation's turnaround, newest first, a row each; the wheel or the bar scrolls.
fn turnaround(ui: &mut Ui, at: Rect, doc: &Value, off: &mut usize) {
    let t = ui.t;
    let now = secs(&s(doc, "at")).unwrap_or(0.0);
    let gens: Vec<&Value> = arr(doc, "gens").iter().rev().collect();
    let cut = at.x + 150 + (at.w - 170) * 40 / 100;
    let (lw, rw) = (cut - (at.x + 150) - 6, at.right() - 20 - cut - 6);
    ui.label_right(cut - 6, at.y, "first read -> commit (hours before, to 36)", &F6X10, t.dim);
    ui.label(cut + 6, at.y, "commit -> main (hours after, to 24)", &F6X10, t.dim);
    let box_ = rect(at.x, at.y + 16, at.w, at.h - 34);
    let (area, first, shown) = ui.scroll_list(box_, gens.len(), 18, off);
    ui.c.vline(cut, area.y, area.h, t.ink);
    let (c, m) = (cpu(ui), t.up);
    for (i, g) in gens.iter().skip(first).take(shown).enumerate() {
        let y = area.y + i as i32 * 18;
        ui.label_in(area.x, y + 3, 146, &format!("{} {}", s(g, "run"), s(g, "trial")), &F6X10, t.ink);
        let com = secs(&s(g, "committed"));
        if let (Some(a), Some(b)) = (secs(&s(g, "first")), com) {
            let h = (b - a) / 3600.0;
            let px = ((h / 36.0).min(1.0) * lw as f64) as i32;
            ui.c.rect(cut - px, y + 3, px.max(2), 12, c);
            let r = rect(cut - px.max(4), y + 2, px.max(4), 14);
            let (f, cm) = (s(g, "first"), s(g, "committed"));
            ui.tip(r, move || vec![format!("first read {}", f.replace('T', " ")), format!("committed {}, {:.1} h", cm.replace('T', " "), h)]);
        }
        if let Some(b) = com {
            let (end, waiting) = match secs(&s(g, "main")) {
                Some(mn) => (mn, false),
                None if s(g, "status") == "self-modified" => (now, true),
                None => (b, false),
            };
            let h = (end - b) / 3600.0;
            let px = ((h / 24.0).min(1.0) * rw as f64) as i32;
            if waiting {
                ui.c.frame(cut + 1, y + 3, px.max(3), 12, m);
                ui.label(cut + px + 6, y + 3, &format!("waiting, {:.0} h", h), &F6X10, t.dim);
            } else if h > 0.05 {
                ui.c.rect(cut + 1, y + 3, px.max(2), 12, m);
                ui.label(cut + px + 6, y + 3, &format!("{:.1} h", h), &F6X10, t.dim);
            } else {
                ui.label(cut + 6, y + 3, "straight to main", &F6X10, t.dim);
            }
        }
    }
    ui.label_in(at.x, at.bottom() - 14, at.w, &format!("{} generations. Orange: the fleet's work on the question; green: the commit until main; a hollow bar still waits. Scroll with the wheel or the bar.", gens.len()), &F6X10, t.dim);
}

/// Fig. 4: what each line claimed against what the proof kept; the lines under it, scrolling.
fn kept(ui: &mut Ui, at: Rect, doc: &Value, off: &mut usize) {
    let t = ui.t;
    let pairs: Vec<&Value> = arr(doc, "pairs").iter().filter(|p| !arr(p, "gens").is_empty()).collect();
    let moved: Vec<String> = arr(doc, "moved_by").iter().filter_map(|v| v.as_str().map(|x| x.to_string())).collect();
    let ch = (at.h * 55 / 100).max(220);
    let chart = rect(at.x, at.y, at.w.min(640), ch);
    let (plot, sy) = frame(ui, chart, "Claimed (the sum of the held-out reads) against proven (the line over main, ± 1 se)", -1.0, 6.0, &[-1.0, 0.0, 2.0, 4.0, 6.0], "");
    let sx = |v: f64| plot.x + ((v.clamp(-1.0, 6.0) + 1.0) / 7.0 * plot.w as f64) as i32;
    dashed(ui, sx(-1.0), sy(-1.0), sx(6.0), sy(6.0), t.dim);
    let (c, m) = (cpu(ui), t.up);
    let (mut sc, mut sp, mut sw2) = (0.0, 0.0, 0.0);
    for p in &pairs {
        let (cl, ld, se) = (n(p, "claimed").unwrap_or(0.0), n(p, "lead").unwrap_or(0.0), n(p, "se").unwrap_or(1.0).max(1e-3));
        let w = 1.0 / (se * se);
        sc += w * cl * ld;
        sp += w * cl * cl;
        sw2 += w;
        let pass = moved.contains(&s(p, "head"));
        let x = sx(cl);
        ui.c.vline(x, sy(ld + se), (sy(ld - se) - sy(ld + se)).max(1), if pass { m } else { c });
        if pass { ui.c.disc(x, sy(ld), 5, m) } else { ui.c.ring(x, sy(ld), 5, c) }
        let lines = vec![format!("line {}: {}", s(p, "head"), arr(p, "gens").iter().map(|g| g.as_str().unwrap_or("").to_string()).collect::<Vec<_>>().join(", ")),
                         format!("claimed {:+.2}, proven {:+.2} ± {:.2} over {} seeds (z {:.1})", cl, ld, se, s(p, "seeds"), n(p, "z").unwrap_or(0.0)),
                         if pass { "passed: main moved".into() } else { String::new() }];
        ui.tip(rect(x - 6, sy(ld) - 6, 13, 13), move || lines);
    }
    let _ = sw2;
    let slope = if sp > 0.0 { sc / sp } else { 0.0 };
    ui.label_in(chart.x + 50, plot.bottom() + 4, chart.w, "claimed", &F6X10, t.dim);
    let side = rect(chart.right() + 16, at.y + 20, at.right() - chart.right() - 16, ch - 20);
    if side.w > 160 {
        ui.label_in(side.x, side.y, side.w, &format!("Kept: {:.2} of a claim", slope), &F8X13, t.ink);
        ui.label_in(side.x, side.y + 18, side.w, "(the slope of proven on claimed, each", &F6X10, t.dim);
        ui.label_in(side.x, side.y + 30, side.w, "read weighed by its error)", &F6X10, t.dim);
        ui.c.disc(side.x + 5, side.y + 56, 5, m);
        ui.label(side.x + 16, side.y + 51, "a proof that passed", &F6X10, t.dim);
        ui.c.ring(side.x + 5, side.y + 74, 5, c);
        ui.label(side.x + 16, side.y + 69, "a head read, not passed", &F6X10, t.dim);
    }
    // The heads, scrolling.
    let list = rect(at.x, chart.bottom() + 8, at.w, at.bottom() - chart.bottom() - 8);
    ui.label(list.x, list.y, "head      read at            claimed  proven          seeds   z     generations", &F6X10, t.dim);
    let (area, first, shown) = ui.scroll_list(rect(list.x, list.y + 14, list.w, list.h - 14), pairs.len(), 15, off);
    for (i, p) in pairs.iter().rev().skip(first).take(shown).enumerate() {
        let y = area.y + i as i32 * 15;
        let pass = moved.contains(&s(p, "head"));
        let row = format!("{:<9} {:<18} {:>+7.2}  {:>+6.2} ± {:<5.2} {:>6}  {:>5.1}  {}", s(p, "head"), s(p, "t0").replace('T', " ").chars().take(16).collect::<String>(),
                          n(p, "claimed").unwrap_or(0.0), n(p, "lead").unwrap_or(0.0), n(p, "se").unwrap_or(0.0), s(p, "seeds"), n(p, "z").unwrap_or(0.0),
                          arr(p, "gens").iter().map(|g| g.as_str().unwrap_or("").to_string()).collect::<Vec<_>>().join(" "));
        ui.label_in(area.x, y + 2, area.w, &row, &F6X10, if pass { m } else { t.ink });
    }
}

/// Fig. 5: the GPU's ladder (each generation's margin), the exams against the newest, the yardstick.
fn ladder(ui: &mut Ui, at: Rect, doc: &Value) {
    let t = ui.t;
    let g = gpu(ui);
    let h3 = (at.h - 12) / 3;
    // (a) margins
    let ms: Vec<&Value> = arr(doc, "milestones").iter().filter(|m| n(m, "margin").is_some() && s(m, "made") != "").collect();
    let (plot, sy) = frame(ui, rect(at.x, at.y, at.w, h3), "(a) Each generation's margin over the one before, se (dashed: the bar, 2)", 0.0, 55.0, &[0.0, 10.0, 25.0, 50.0], "");
    let bw = plot.w / ms.len().max(1) as i32;
    for (i, m) in ms.iter().enumerate() {
        let v = n(m, "margin").unwrap_or(0.0);
        let x = plot.x + i as i32 * bw + 2;
        let y = sy(v);
        ui.c.rect(x, y, (bw - 4).max(2), plot.bottom() - y, g);
        ui.label(x, y - 11, &format!("{:.1}", v), &F6X10, t.dim);
        let (id, made) = (s(m, "id"), s(m, "made"));
        ui.tip(rect(x, plot.y, bw, plot.h), move || vec![id.clone(), format!("made {}, {:.1} se", made.replace('T', " "), v)]);
    }
    dashed(ui, plot.x, sy(2.0), plot.right(), sy(2.0), t.ink);
    // (b) exams since the newest
    let ex = arr(doc, "exams");
    let r = rect(at.x, at.y + h3 + 6, at.w, h3);
    let (plot, sy) = frame(ui, r, "(b) The exams against the newest world generation: each hour's best (solid) and median (dots), se", -50.0, 5.0, &[-50.0, -25.0, 0.0], "");
    let ts: Vec<f64> = ex.iter().filter_map(|e| secs(&format!("{}:30:00", str_at(e, 0)))).collect();
    if ts.len() > 1 {
        let sx = days(ui, plot, ts[0], *ts.last().unwrap());
        let mut prev: Option<(i32, i32, i32)> = None;
        for (e, tt) in ex.iter().zip(ts.iter()) {
            let (x, yb, ym) = (sx(*tt), sy(num_at(e, 1).unwrap_or(0.0)), sy(num_at(e, 2).unwrap_or(0.0)));
            if let Some((px, pb, pm)) = prev {
                line(ui, px, pb, x, yb, g);
                ui.c.rect(x, ym, 2, 2, g);
                let _ = pm;
            }
            prev = Some((x, yb, ym));
            let (k, b, md, cnt) = (str_at(e, 0), num_at(e, 1).unwrap_or(0.0), num_at(e, 2).unwrap_or(0.0), num_at(e, 3).unwrap_or(0.0));
            ui.tip(rect(x - 3, plot.y, 7, plot.h), move || vec![format!("{}:00, {} exams", k.replace('T', " "), cnt), format!("best {:+.1}, median {:+.1} se", b, md)]);
        }
        dashed(ui, plot.x, sy(2.0), plot.right(), sy(2.0), t.ink);
    }
    // (c) the yardstick
    let yd = arr(doc, "yard");
    let r = rect(at.x, at.y + 2 * (h3 + 6), at.w, h3);
    let (lo, hi) = yd.iter().filter_map(|e| num_at(e, 1)).fold((1.0f64, 0.0f64), |(a, b), v| (a.min(v), b.max(v)));
    let (lo, hi) = ((lo - 0.01).max(0.0), (hi + 0.01).min(1.0));
    let (plot, sy) = frame(ui, r, "(c) The yardstick: the share of duels won against crucible's fixed opponent, a half-day's median", lo, hi.max(lo + 0.02), &[lo, hi], "");
    let step = plot.w / yd.len().max(2) as i32;
    let mut prev: Option<(i32, i32)> = None;
    for (i, e) in yd.iter().enumerate() {
        let (x, y) = (plot.x + step / 2 + i as i32 * step, sy(num_at(e, 1).unwrap_or(0.0)));
        ui.c.disc(x, y, 4, g);
        ui.label(x - 14, y - 16, &format!("{:.3}", num_at(e, 1).unwrap_or(0.0)), &F6X10, t.dim);
        ui.label(x - 24, plot.bottom() + 3, &str_at(e, 0).chars().skip(5).collect::<String>(), &F6X10, t.dim);
        if let Some((px, py)) = prev {
            line(ui, px, py, x, y, g);
        }
        prev = Some((x, y));
    }
}

/// The forest home's elections: each segment's weighed step on the CUDA gauntlet against the bar, the
/// newest champion's files against the newest generation's, the floors, the window's best.
fn elections(ui: &mut Ui, at: Rect, doc: &Value, off: &mut usize) {
    let t = ui.t;
    let Some(f) = doc.get("homes").and_then(|h| h.get("crucible-world-hybrid-forest")) else {
        ui.label_in(at.x, at.y, at.w, "No forest home yet: plan.json's crucible.forest turns it on.", &F8X13, t.dim);
        return;
    };
    let el = arr(f, "elections");
    let made: Vec<&Value> = arr(f, "milestones").iter().filter(|m| !matches!(m.get("carried"), Some(Value::Bool(true)))).collect();
    let best = f.get("best").filter(|b| !matches!(b, Value::Null));
    // Credit, and the replacement test: how far the newest net the game has read stands from the rules.
    let read: Vec<&Value> = made.iter().filter_map(|m| m.get("game").filter(|g| !matches!(g, Value::Null))).collect();
    let credited = read.iter().filter(|g| matches!(g.get("credited"), Some(Value::Bool(true)))).count();
    let rules = read.last().and_then(|g| g.get("vs_rules")).map(|v| format!("{:+.2} ± {:.2} a seat (z {:.1}; it replaces the brain at z 3)", num_at(v, 0).unwrap_or(0.0), num_at(v, 1).unwrap_or(0.0), num_at(v, 2).unwrap_or(0.0)))
        .unwrap_or_else(|| "not read yet".into());
    ui.label_in(at.x, at.bottom() - 14, at.w, &format!("The card elects, the game credits: {} of {} forest generations read in the game, {} credited. The newest read against the rules: {}.", read.len(), made.len(), credited, rules), &F6X10, t.ink);
    let at = rect(at.x, at.y, at.w, at.h - 18);
    ui.label_in(at.x, at.y, at.w, &format!("The bar now {:.2} z ({:.1} h since a generation; it eases {:.2} an hour dry and tightens after each). {} forest generations, {} segments read. The window's best: {}.",
        n(f, "bar").unwrap_or(2.0), n(f, "dry_h").unwrap_or(0.0), 0.25, made.len(), el.len(),
        best.map(|b| format!("{} {:+.2} z", s(b, "job"), n(b, "zg").unwrap_or(0.0))).unwrap_or_else(|| "none yet".into())), &F8X13, t.ink);
    let (g, m) = (gpu(ui), t.up);
    let half = (at.w - 16) / 2;
    // left: the steps over time against the bar
    let ch = rect(at.x, at.y + 22, half, (at.h - 22) / 2);
    let (lo, hi) = el.iter().filter_map(|e| s(e, "zg").parse::<f64>().ok()).fold((-2.0f64, 4.0f64), |(a, b), v| (a.min(v), b.max(v)));
    let (plot, sy) = frame(ui, ch, "Each segment's weighed step on the gauntlet (z) and the bar", lo.max(-20.0), hi.min(30.0), &[0.0, 2.0], "");
    let ts: Vec<f64> = el.iter().filter_map(|e| secs(&s(e, "time"))).collect();
    if let (Some(a), Some(b)) = (ts.first(), ts.last()) {
        let span = (b - a).max(3600.0);
        let sx = |x: f64| plot.x + ((x - a) / span * plot.w as f64) as i32;
        let mut pb: Option<(i32, i32)> = None;
        for e in el {
            let Some(x) = secs(&s(e, "time")) else { continue };
            let (zg, bar) = (s(e, "zg").parse::<f64>().unwrap_or(0.0), s(e, "bar").parse::<f64>().unwrap_or(2.0));
            let ok = s(e, "result").starts_with("milestone");
            let held = s(e, "holds") == "yes" && s(e, "guard") == "yes";
            let (px, py) = (sx(x), sy(zg));
            if ok { ui.c.disc(px, py, 5, m) } else if held { ui.c.disc(px, py, 3, g) } else { ui.c.ring(px, py, 3, t.alarm) }
            let yb = sy(bar);
            if let Some((qx, qy)) = pb {
                ui.c.hline(qx, qy, (px - qx).max(1), t.ink);
                ui.c.vline(px, qy.min(yb), (qy - yb).abs().max(1), t.ink);
            }
            pb = Some((px, yb));
            let lines = vec![format!("{} {} generation {}", s(e, "job"), s(e, "island"), s(e, "gen")), format!("gauntlet {} z, yardstick {} z, the bar {}", s(e, "zg"), s(e, "zy"), s(e, "bar")),
                             s(e, "result").chars().take(110).collect()];
            ui.tip(rect(px - 5, py - 5, 11, 11), move || lines);
        }
    }
    // right: the newest gauntlet's files
    let rr = rect(at.x + half + 16, at.y + 22, half, (at.h - 22) / 2);
    ui.label_in(rr.x, rr.y, rr.w, "The newest segment's gauntlet: champion (blue) and the newest generation (green), each file; the tick is its floor", &F8X13, t.ink);
    if let Some(rd) = f.get("latest").and_then(|l| l.get("read")) {
        let shares = rd.get("share");
        let champ = shares.and_then(|x| x.get("champion"));
        let other = shares.and_then(|x| obj(x)).and_then(|o| o.iter().find(|(k, _)| k.as_str() != "champion").map(|(_, v)| v));
        let floors = f.get("floors");
        if let Some(cm) = champ.and_then(|c| obj(c)) {
            let rows: Vec<(&String, &Value)> = cm.iter().collect();
            let rh = ((rr.h - 22) / rows.len().max(1) as i32).clamp(10, 18);
            for (i, (k, v)) in rows.iter().enumerate() {
                let y = rr.y + 20 + i as i32 * rh;
                let lw = 150;
                ui.label_in(rr.x, y, lw - 4, k, &F6X10, t.dim);
                let bw = rr.w - lw - 40;
                let a = v.as_num().unwrap_or(0.0);
                let b = other.and_then(|o| o.get(k.as_str())).and_then(|x| x.as_num()).unwrap_or(0.0);
                ui.c.rect(rr.x + lw, y + 1, (a * bw as f64) as i32 + 1, (rh / 2 - 1).max(3), g);
                ui.c.rect(rr.x + lw, y + rh / 2, (b * bw as f64) as i32 + 1, (rh / 2 - 1).max(3), m);
                if let Some(fl) = floors.and_then(|x| x.get(k.as_str())).and_then(|x| x.as_num()) {
                    ui.c.vline(rr.x + lw + (fl * bw as f64) as i32, y, rh - 1, t.ink);
                }
                ui.label(rr.x + lw + bw + 4, y, &format!("{:.2}", a), &F6X10, t.dim);
            }
        }
    } else {
        ui.label_in(rr.x, rr.y + 20, rr.w, "No forest segment has finished yet.", &F6X10, t.dim);
    }
    // the elections, scrolling
    let list = rect(at.x, at.y + 22 + (at.h - 22) / 2 + 8, at.w, at.h - (22 + (at.h - 22) / 2 + 8));
    ui.label(list.x, list.y, "time              segment              gen      gauntlet z  yardstick z  bar    floors  guard  head to head  result", &F6X10, t.dim);
    let rows: Vec<&Value> = el.iter().rev().collect();
    let (area, first, shown) = ui.scroll_list(rect(list.x, list.y + 14, list.w, list.h - 14), rows.len(), 15, off);
    for (i, e) in rows.iter().skip(first).take(shown).enumerate() {
        let y = area.y + i as i32 * 15;
        let ok = s(e, "result").starts_with("milestone");
        let row = format!("{:<17} {:<20} {:<8} {:>9}  {:>11}  {:<5}  {:<6}  {:<5}  {:>12}  {}", s(e, "time").replace('T', " ").chars().take(16).collect::<String>(), s(e, "job"), s(e, "gen"), s(e, "zg"), s(e, "zy"),
                          s(e, "bar"), s(e, "holds"), s(e, "guard"), s(e, "margin_se"), s(e, "result"));
        ui.label_in(area.x, y + 2, area.w, &row, &F6X10, if ok { m } else { t.ink });
    }
}

/// Fig. 6: the hours a day, their energy and cost, and what they bought.
fn hours(ui: &mut Ui, at: Rect, doc: &Value, off: &mut usize) {
    let t = ui.t;
    let hs = arr(doc, "hours");
    let (g, c) = (gpu(ui), cpu(ui));
    let ch = rect(at.x, at.y, at.w * 62 / 100, at.h - 10);
    let top = (hs.iter().filter_map(|h| num_at(h, 2)).fold(50.0f64, f64::max) / 20.0).ceil() * 20.0;
    let (plot, sy) = frame(ui, ch, "Job-hours a day: the three cards (blue, 72 at most) and the CPU machines (orange); hover a day for its kWh", 0.0, top, &[0.0, top / 2.0, top], " h");
    let gw = plot.w / hs.len().max(1) as i32;
    for (i, h) in hs.iter().enumerate() {
        let x = plot.x + i as i32 * gw + 4;
        let bw = (gw - 10) / 2;
        let (a, b) = (num_at(h, 1).unwrap_or(0.0), num_at(h, 2).unwrap_or(0.0));
        ui.c.rect(x, sy(a), bw, plot.bottom() - sy(a), g);
        ui.c.rect(x + bw + 2, sy(b), bw, plot.bottom() - sy(b), c);
        ui.label(x, sy(a) - 11, &format!("{:.0}", a), &F6X10, t.dim);
        ui.label(x + bw + 2, sy(b) - 11, &format!("{:.0}", b), &F6X10, t.dim);
        let d = str_at(h, 0);
        ui.label(x, plot.bottom() + 3, &d.chars().skip(5).collect::<String>(), &F6X10, t.dim);
        let (ge, ce) = (num_at(h, 3).unwrap_or(0.0), num_at(h, 4).unwrap_or(0.0));
        ui.tip(rect(x, plot.y, gw - 4, plot.h), move || vec![d.clone(), format!("GPU {:.1} card-hours, {:.1} kWh", a, ge), format!("CPU {:.1} machine-hours, {:.1} kWh", b, ce)]);
    }
    // the totals and what they bought
    let side = rect(ch.right() + 16, at.y, at.right() - ch.right() - 16, at.h);
    let tot = doc.get("totals");
    let rate = tot.and_then(|x| n(x, "rate")).unwrap_or(0.17);
    let mut lines: Vec<(String, Rgb)> = vec![];
    if let Some(x) = tot {
        let (gh, chh, ge, ce) = (n(x, "gpu_h").unwrap_or(0.0), n(x, "cpu_h").unwrap_or(0.0), n(x, "gpu_kwh").unwrap_or(0.0), n(x, "cpu_kwh").unwrap_or(0.0));
        lines.push(("Since 28 October".into(), t.ink));
        lines.push((format!("GPU {:.0} card-hours ({:.1}%)", gh, 100.0 * gh / (gh + chh).max(1.0)), g));
        lines.push((format!("    {:.1} kWh, ${:.2}", ge, ge * rate), g));
        lines.push((format!("CPU {:.0} machine-hours", chh), c));
        lines.push((format!("    {:.1} kWh, ${:.2}", ce, ce * rate), c));
        lines.push((format!("at {:.0}¢ a kWh (power.json)", rate * 100.0), t.dim));
        lines.push((String::new(), t.dim));
    }
    if let Some(b) = doc.get("bought") {
        lines.push(("What the GPU's hours bought".into(), t.ink));
        for r in arr(b, "gpu") {
            lines.push((format!("  {:<22} {}", str_at(r, 0), str_at(r, 1)), g));
        }
        lines.push(("What the CPUs' hours bought".into(), t.ink));
        for r in arr(b, "cpu") {
            lines.push((format!("  {:<22} {}", str_at(r, 0), str_at(r, 1)), c));
        }
    }
    let (area, first, shown) = ui.scroll_list(side, lines.len(), 15, off);
    for (i, (l, col)) in lines.iter().skip(first).take(shown).enumerate() {
        ui.label_in(area.x, area.y + i as i32 * 15, area.w, l, &F6X10, *col);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_time_reads_as_seconds_and_a_day_as_its_date() {
        let a = secs("2026-11-06T05:20:51").unwrap();
        let b = secs("2026-11-05T05:20:51").unwrap();
        assert_eq!(a - b, 86400.0);
        let day = (a / 86400.0).floor() as i64 + 719468;
        assert_eq!(civil(day), (2026, 11, 6));
        assert_eq!(secs("not a time"), None);
    }
}
