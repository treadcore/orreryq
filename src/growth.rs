//! Results, Growth: crucible's generations as they grow, and the disks the fleet's generations fill
//! (Paul, 3 November: "the rules and simulation of generations, we want to sample its growth in an
//! inspector as well. also, place a purge button, and give warnings when sizes get above 20GB").
//!
//! The document is `tools/growth.py`'s (QUEUE/plan/growth.json): one SAMPLE A SEGMENT of each
//! island -- the generation reached, its fitness, yardstick and exam, and the champion's own
//! matrices (norm, stable rank, near-zero share, how much of the first layer listens to the rules
//! and to the world's senses) -- the sizes of every place the generations fill, and the purge's
//! list. THE PAGE DRAWS AND ASKS; IT NEVER MEASURES OR REMOVES A FILE ITSELF. Measure and Purge
//! are verbs for `fleet-queue.py QUEUE growth ...`, run by main as the other queue controls are.
//! A button that must not be pressable (a viewer, not an operator) is not drawn.
//!
//! SMALL MULTIPLES, NOT ONE CHART WITH A SELECTOR: the question is how the measures move together
//! (the norm climbing while the exam falls is the finding, and a selector shows one at a time).
//! One line an island, the same colour in every chart. The inspector is the sample: the pointer's
//! generation is a cursor through the chart, and its tip is every island's whole sample there.
//!
//! THE PURGE TAKES TWO PRESSES, AND THE SECOND WAITS FOR THE FIRST'S LIST. The first asks the tool
//! to list (a minute of ssh to every machine); the second is drawn only once a list newer than the
//! press has come back, and says the gigabytes it will free, so nobody removes what they have not
//! been shown.
use crate::draw::Rgb;
use crate::font::{F6X10, F8X13};
use crate::json::Value;
use crate::surface::Sym;
use crate::ui::{rect, Rect, Ui};

/// What the page remembers between frames.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct State {
    /// Which home's islands are drawn (crucible, crucible-hybrid, crucible-world...).
    pub home: usize,
    /// Purge was pressed once: the time of the list on screen then ("" for none). The second
    /// press is offered when a list newer than that has arrived.
    pub arm_purge: Option<String>,
}

/// The charts, in the order they are offered: (field, title, what it is). A home draws the first
/// eight its samples have numbers for, so a hybrid home shows the rules' share and a world home
/// the world's.
const METRICS: [(&str, &str, &str); 13] = [
    ("best", "best fitness", "the best individual's score in the generation: hits dealt less taken, a win +2, a loss -2"),
    ("mean", "mean fitness", "the population's mean score: the whole island, not its champion"),
    ("yard", "yardstick win share", "the champion against the scripted yardstick, every tenth generation: the fixed measure of learning"),
    ("exam", "exam: win less loss", "the segment's last champion against each milestone of the ladder, win share less loss share (-1 to 1)"),
    ("world", "share on the world's senses", "of the first layer's weight, the share on the twenty senses the world added (pillboxes, shells, reload): how much the net listens to them"),
    ("pill_taken", "pillbox damage a duel", "the pillbox shells a learner took a duel, in hits: the first-minute lesson of the game"),
    ("hit_rate", "hit rate", "hits a shot fired, both tanks"),
    ("rules", "share on the rules' answers", "of the first layer's weight, the share on the three inputs that carry the scripted tank's answer (hybrid)"),
    ("fro1", "first layer's norm", "the Frobenius norm of the first matrix: how large its weights have grown; tanh saturates when it is large"),
    ("srank1", "first layer's stable rank", "|W|^2 / sigma_max^2: how many directions the first layer really uses, of its hidden width"),
    ("srank2", "second layer's stable rank", "the same for the hidden-to-hidden matrix"),
    ("near0", "near-zero weights", "the share of weights under 2% of the net's largest: what it could lose unnoticed"),
    ("msteps", "speed, M steps/s", "tank-steps a second on the card, the segment's mean"),
];

fn s(v: &Value, k: &str) -> String {
    v.get(k).and_then(|x| x.as_str()).unwrap_or("").to_string()
}
fn n(v: &Value, k: &str) -> f64 {
    v.get(k).and_then(|x| x.as_num()).unwrap_or(0.0)
}
fn arr<'a>(v: &'a Value, k: &str) -> &'a [Value] {
    v.get(k).and_then(|x| x.as_array()).map(|a| &a[..]).unwrap_or(&[])
}

/// A number as wide as it needs: 381, 9.27, 0.264.
fn num(v: f64) -> String {
    let a = v.abs();
    if a >= 1000.0 {
        format!("{:.0}", v)
    } else if a >= 100.0 {
        format!("{:.1}", v)
    } else if a >= 10.0 {
        format!("{:.2}", v)
    } else {
        format!("{:.3}", v)
    }
}

pub fn gb(b: f64) -> String {
    if b >= 1e9 {
        format!("{:.1} GB", b / 1e9)
    } else {
        format!("{:.0} MB", b / 1e6)
    }
}

/// A line, one pixel wide, Bresenham's: the canvas has rectangles and discs, and a chart needs this.
fn seg(ui: &mut Ui, (x0, y0): (i32, i32), (x1, y1): (i32, i32), c: Rgb) {
    let (dx, dy) = ((x1 - x0).abs(), -(y1 - y0).abs());
    let (sx, sy) = (if x0 < x1 { 1 } else { -1 }, if y0 < y1 { 1 } else { -1 });
    let (mut x, mut y, mut err) = (x0, y0, dx + dy);
    for _ in 0..4096 {
        ui.c.set(x, y, c);
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

/// One island's samples: (generation, the whole row).
struct Island<'a> {
    name: String,
    count: i64,
    first: String,
    last: String,
    rows: Vec<&'a [Value]>,
}

fn col(fields: &[String], k: &str) -> Option<usize> {
    fields.iter().position(|f| f == k)
}

fn val(row: &[Value], i: Option<usize>) -> Option<f64> {
    i.and_then(|i| row.get(i)).and_then(|x| x.as_num()).filter(|v| v.is_finite())
}

/// A sample in words, for the inspector: the island and generation, then each number it carries.
fn sample_line(fields: &[String], island: &str, row: &[Value]) -> String {
    let get = |k: &str| val(row, col(fields, k));
    let word = |k: &str| col(fields, k).and_then(|i| row.get(i)).and_then(|x| x.as_str()).unwrap_or("").to_string();
    let mut parts = vec![format!("{} g{}", island.trim_end_matches("-cuda"), get("gen").unwrap_or(0.0) as i64)];
    for (k, label) in [
        ("best", "best"),
        ("mean", "mean"),
        ("yard", "yard"),
        ("exam", "exam"),
        ("srank1", "srank1"),
        ("fro1", "|W1|"),
        ("near0", "near0"),
        ("rules", "rules"),
        ("world", "world"),
        ("pill_taken", "pill"),
        ("hit_rate", "hit"),
        ("msteps", "Msteps/s"),
    ] {
        if let Some(v) = get(k) {
            parts.push(format!("{} {}", label, num(v)));
        }
    }
    let dims = word("dims");
    format!("{}   {}  {}  {}", parts.join("  "), dims, word("job"), word("time").replace('T', " "))
}

/// The page. `ctl` takes a verb for `fleet-queue.py QUEUE growth ...`.
pub fn draw(ui: &mut Ui, at: Rect, doc: Option<&Value>, st: &mut State, operator: bool, ctl: &mut Option<String>) {
    let t = ui.t;
    let Some(doc) = doc.filter(|d| d.get("homes").is_some() || d.get("sizes").is_some()) else {
        ui.label_in(at.x, at.y, at.w, "No record yet: tools/growth.py QUEUE refresh writes plan/growth.json (treadcore-view.py starts it when the file is old, or run it by hand).", &F8X13, t.dim);
        return;
    };
    if ui.f.pressed(Sym::Escape) {
        st.arm_purge = None;
    }
    // The sizes take the lower part: what the page warns about is never scrolled away.
    let sizes_h = (at.h * 2 / 5).clamp(170, 340).min(at.h - 160).max(120);
    let (upper, lower) = (rect(at.x, at.y, at.w, at.h - sizes_h - 8), rect(at.x, at.bottom() - sizes_h, at.w, sizes_h));
    draw_growth(ui, upper, doc, st);
    draw_sizes(ui, lower, doc, st, operator, ctl);
}

fn draw_growth(ui: &mut Ui, at: Rect, doc: &Value, st: &mut State) {
    let t = ui.t;
    let lh = F8X13.height as i32;
    let fields: Vec<String> = arr(doc, "fields").iter().filter_map(|f| f.as_str().map(str::to_string)).collect();
    let homes = arr(doc, "homes");
    if homes.is_empty() {
        ui.label_in(at.x, at.y, at.w, "No island has finished a segment yet: each one's numbers are sampled when its results come back.", &F8X13, t.dim);
        return;
    }
    st.home = st.home.min(homes.len() - 1);
    // ---- the homes, and the sampling's sentence ----
    let mut x = at.x;
    for (i, h) in homes.iter().enumerate() {
        let dims: Vec<String> = arr(h, "dims").iter().filter_map(|d| d.as_str().map(str::to_string)).collect();
        let label = format!("{}  {}", s(h, "home"), dims.join(", "));
        let w = F8X13.measure(&label) as i32 + 18;
        if ui.rail_item(rect(x, at.y, w, 22), &label, None, st.home == i) {
            st.home = i;
        }
        let (segs, name) = (n(h, "segments") as i64, s(h, "home"));
        ui.tip(rect(x, at.y, w, 22), move || vec![
            format!("{}: {} segments sampled", name, segs),
            "A home is one kind of net: its population, hall of fame, ladder and record live apart, because a net of another size does not load in it.".to_string(),
            format!("Its record is QUEUE/{}/growth.tsv: a row a segment, kept when the raw segments are purged.", name),
        ]);
        x += w + 4;
    }
    let home = &homes[st.home];
    let sentence = format!(
        "sampled {}: a point a segment (each 50 to 100 generations on one card), thinned to 480 an island; the pointer's generation is a cursor, and the inspector holds every island's sample there",
        s(doc, "at").replace('T', " ")
    );
    ui.label_in(x + 8, at.y + 5, at.right() - x - 8, &sentence, &F6X10, t.dim);
    let mut y = at.y + 28;
    // ---- the islands, one colour each in every chart ----
    // Fixed hues, not the theme's: its accent and its "up" are both green in the metal theme, and
    // two islands in one colour is one island. The charts sit in dark wells in every theme.
    let palette: [Rgb; 6] = [0x4a9ae8, 0xeb6834, 0x1baf7a, 0xb48cf0, 0xe87ba4, 0xeda100];
    let islands: Vec<Island> = arr(home, "islands")
        .iter()
        .map(|i| Island {
            name: s(i, "island"),
            count: n(i, "count") as i64,
            first: s(i, "first"),
            last: s(i, "last"),
            rows: arr(i, "samples").iter().filter_map(|r| r.as_array()).map(|r| &r[..]).collect(),
        })
        .collect();
    let mut lx = at.x;
    for (k, isl) in islands.iter().enumerate() {
        let c = palette[k % palette.len()];
        let label = format!("{} ({} segments)", isl.name.trim_end_matches("-cuda"), isl.count);
        let w = F8X13.measure(&label) as i32 + 22;
        ui.c.rect(lx, y + 4, 12, 4, c);
        ui.label(lx + 16, y, &label, &F8X13, t.ink);
        let (name, first, last, count) = (isl.name.clone(), isl.first.clone(), isl.last.clone(), isl.count);
        let newest = isl.rows.last().map(|r| sample_line(&fields, &isl.name, r)).unwrap_or_default();
        ui.tip(rect(lx, y - 2, w, lh + 4), move || vec![
            format!("Island {}", name),
            format!("{} segments, {} to {}", count, first.replace('T', " "), last.replace('T', " ")),
            format!("Newest: {}", newest),
            "Each card is an island: its own population, which meets the others' champions and the ladder's milestones.".to_string(),
        ]);
        lx += w + 14;
    }
    y += lh + 8;
    // ---- the charts: the first eight measures this home has numbers for ----
    let shown: Vec<&(&str, &str, &str)> = METRICS
        .iter()
        .filter(|(k, _, _)| islands.iter().any(|i| i.rows.iter().any(|r| val(r, col(&fields, k)).is_some())))
        .take(8)
        .collect();
    if shown.is_empty() {
        return;
    }
    let ncol = if at.w > 1100 { 4 } else { 2 };
    let nrow = (shown.len() as i32 + ncol - 1) / ncol;
    let gap = 8;
    let cw = (at.w - gap * (ncol - 1)) / ncol;
    let ch = ((at.bottom() - y - gap * (nrow - 1)) / nrow).max(60);
    let gmax = islands.iter().flat_map(|i| i.rows.iter().filter_map(|r| val(r, col(&fields, "gen")))).fold(1.0f64, f64::max);
    for (k, m) in shown.iter().enumerate() {
        let (cx, cy) = (k as i32 % ncol, k as i32 / ncol);
        let r = rect(at.x + cx * (cw + gap), y + cy * (ch + gap), cw, ch);
        chart(ui, r, m, &fields, &islands, &palette, gmax);
    }
}

/// The generation a frame marks, and the island whose sample it rings: ORRERY_FRAME_GEN and
/// ORRERY_FRAME_ISLAND, read once. Absent in a window: only `--frame` sets them.
fn frame_gen() -> Option<(f64, String)> {
    static G: std::sync::OnceLock<Option<(f64, String)>> = std::sync::OnceLock::new();
    G.get_or_init(|| {
        let g = std::env::var("ORRERY_FRAME_GEN").ok()?.parse::<f64>().ok()?;
        Some((g, std::env::var("ORRERY_FRAME_ISLAND").unwrap_or_default()))
    })
    .clone()
}

fn chart(ui: &mut Ui, r: Rect, m: &(&str, &str, &str), fields: &[String], islands: &[Island], palette: &[Rgb], gmax: f64) {
    let t = ui.t;
    let (key, title, what) = *m;
    ui.well(r);
    ui.label_in(r.x + 6, r.y + 3, r.w - 12, title, &F8X13, t.ink);
    let plot = rect(r.x + 6, r.y + F8X13.height as i32 + 8, r.w - 12 - 44, r.h - F8X13.height as i32 - 14 - F6X10.height as i32);
    if plot.h < 12 || plot.w < 40 {
        return;
    }
    let (gi, vi) = (col(fields, "gen"), col(fields, key));
    let pts: Vec<Vec<(f64, f64)>> = islands.iter().map(|i| i.rows.iter().filter_map(|r| Some((val(r, gi)?, val(r, vi)?))).collect()).collect();
    let all = pts.iter().flatten().map(|p| p.1);
    let (mut lo, mut hi) = all.fold((f64::INFINITY, f64::NEG_INFINITY), |(a, b), v| (a.min(v), b.max(v)));
    if !lo.is_finite() {
        ui.label_in(plot.x, plot.y, plot.w, "no numbers", &F6X10, t.dim);
        return;
    }
    // Shares and win rates on their own scale, so two homes read alike.
    if matches!(key, "yard" | "world" | "rules" | "near0" | "hit_rate") {
        lo = lo.min(0.0);
        hi = hi.max(if key == "yard" || key == "hit_rate" { 1.0 } else { hi });
    }
    if key == "exam" {
        lo = lo.min(-1.0);
        hi = hi.max(1.0);
    }
    if hi - lo < 1e-9 {
        hi += 0.5;
        lo -= 0.5;
    }
    let pad = (hi - lo) * 0.06;
    let (lo, hi) = (lo - pad, hi + pad);
    let px = |g: f64| plot.x + ((g / gmax) * (plot.w - 1) as f64).round() as i32;
    let py = |v: f64| plot.bottom() - 1 - (((v - lo) / (hi - lo)) * (plot.h - 1) as f64).round() as i32;
    // The scale: top and bottom on the right, zero as a rule when it is inside.
    ui.label(plot.right() + 4, plot.y, &num(hi), &F6X10, t.dim);
    ui.label(plot.right() + 4, plot.bottom() - F6X10.height as i32, &num(lo), &F6X10, t.dim);
    if lo < 0.0 && hi > 0.0 {
        ui.c.hline(plot.x, py(0.0), plot.w, t.line);
    }
    ui.c.frame(plot.x - 1, plot.y - 1, plot.w + 2, plot.h + 2, t.line);
    ui.label(plot.x, plot.bottom() + 2, "g0", &F6X10, t.dim);
    ui.label_right(plot.right(), plot.bottom() + 2, &format!("g{}", gmax as i64), &F6X10, t.dim);
    for (k, p) in pts.iter().enumerate() {
        let c = palette[k % palette.len()];
        let mut last: Option<(i32, i32)> = None;
        for &(g, v) in p {
            let q = (px(g), py(v));
            match last {
                Some(a) => seg(ui, a, q, c),
                None => ui.c.set(q.0, q.1, c),
            }
            last = Some(q);
        }
    }
    // A frame's generation (ORRERY_FRAME_GEN=g, ORRERY_FRAME_ISLAND=name): montage.py's chapter
    // slides mark the chapter's generation on every chart, and the island's sample there, as the
    // pointer would -- a picture has no pointer.
    if let Some((g, island)) = frame_gen() {
        if g <= gmax {
            ui.c.vline(px(g), plot.y, plot.h, 0xffffff);
        }
        for (k, isl) in islands.iter().enumerate() {
            if !island.is_empty() && isl.name != island {
                continue;
            }
            let near = isl.rows.iter().filter(|r| val(r, vi).is_some()).min_by(|a, b| {
                let da = (val(a, gi).unwrap_or(0.0) - g).abs();
                let db = (val(b, gi).unwrap_or(0.0) - g).abs();
                da.partial_cmp(&db).unwrap_or(std::cmp::Ordering::Equal)
            });
            if let Some(r) = near {
                let (gx, v) = (val(r, gi).unwrap_or(0.0), val(r, vi).unwrap_or(0.0));
                ui.c.disc(px(gx), py(v), 5, 0xffffff);
                ui.c.disc(px(gx), py(v), 3, palette[k % palette.len()]);
            }
        }
    }
    // The cursor: the pointer's generation, each island's nearest sample marked, all of it in the tip.
    if ui.is_hot(plot) {
        let (mx, _) = ui.pointer();
        let g = ((mx - plot.x) as f64 / (plot.w - 1).max(1) as f64 * gmax).clamp(0.0, gmax);
        ui.c.vline(mx, plot.y, plot.h, t.dim);
        let mut lines = vec![format!("{} at generation {}", title, g as i64), what.to_string()];
        for (k, isl) in islands.iter().enumerate() {
            let near = isl.rows.iter().filter(|r| val(r, vi).is_some()).min_by(|a, b| {
                let da = (val(a, gi).unwrap_or(0.0) - g).abs();
                let db = (val(b, gi).unwrap_or(0.0) - g).abs();
                da.partial_cmp(&db).unwrap_or(std::cmp::Ordering::Equal)
            });
            if let Some(r) = near {
                let (gx, v) = (val(r, gi).unwrap_or(0.0), val(r, vi).unwrap_or(0.0));
                ui.c.disc(px(gx), py(v), 3, palette[k % palette.len()]);
                lines.push(format!("{}: {}", isl.name.trim_end_matches("-cuda"), num(v)));
                lines.push(format!("  {}", sample_line(fields, &isl.name, r)));
            }
        }
        ui.tip(plot, move || lines);
    }
}

fn draw_sizes(ui: &mut Ui, at: Rect, doc: &Value, st: &mut State, operator: bool, ctl: &mut Option<String>) {
    let t = ui.t;
    let lh = F8X13.height as i32 + 4;
    ui.c.hline(at.x, at.y - 4, at.w, t.line);
    let sz = doc.get("sizes").filter(|x| !matches!(x, Value::Null));
    let limit = sz.map(|x| n(x, "limit_gb")).filter(|v| *v > 0.0).unwrap_or(20.0);
    let head = match sz {
        Some(x) => format!("Sizes, measured {}: a place over {:.0} GB is red and raises a flag (Settings, Long run moves the limit)", s(x, "at").replace('T', " "), limit),
        None => "Sizes: not measured yet (Measure asks every machine over ssh, a minute)".to_string(),
    };
    // The verbs, operators only.
    let mut right = at.right();
    if operator {
        let list_at = doc.get("purge").map(|p| s(p, "at")).unwrap_or_default();
        let listed = doc.get("purge").map(|p| s(p, "state") == "listed").unwrap_or(false);
        let bytes = doc.get("purge").map(|p| n(p, "bytes")).unwrap_or(0.0);
        let pw = 210;
        let ready = matches!(&st.arm_purge, Some(seen) if listed && *seen != list_at);
        let (label, enabled) = match &st.arm_purge {
            None => ("Purge...".to_string(), true),
            Some(_) if ready => (format!("Purge now: {}", gb(bytes)), bytes > 0.0),
            Some(_) => ("Listing what would go...".to_string(), false),
        };
        let b = rect(right - pw, at.y, pw, 22);
        if ui.button(b, &label, enabled) {
            if ready {
                *ctl = Some("growth purge --do".to_string());
                st.arm_purge = None;
            } else {
                *ctl = Some("growth purge".to_string());
                st.arm_purge = Some(list_at.clone());
            }
        }
        ui.tip(b, || vec![
            "Purge: old commit builds on every machine, finished jobs' outputs the Mac has fetched, and census game logs (packed first).".to_string(),
            "The first press lists what would go, here, beside the sizes; the second removes it. Escape takes the first back.".to_string(),
            "Never purged: recordings, a run's results, crucible's populations and champions, the vault, anything younger than the keep.".to_string(),
        ]);
        let mw = 96;
        let m = rect(right - pw - 6 - mw, at.y, mw, 22);
        if ui.button(m, "Measure", true) {
            *ctl = Some("growth sizes".to_string());
        }
        ui.tip(m, || vec!["Measure every place now: the Mac's queue and build, and each machine's ~/fleet over ssh, read only.".to_string()]);
        right = m.x - 8;
    }
    ui.label_in(at.x, at.y + 4, right - at.x, &head, &F8X13, if sz.map(|x| !arr(x, "warnings").is_empty()).unwrap_or(false) { t.alarm } else { t.ink });
    let mut y = at.y + 28;
    let Some(sz) = sz else { return };
    for w in arr(sz, "warnings") {
        if y + lh > at.bottom() {
            break;
        }
        ui.label_in(at.x, y, at.w, &format!("WARNING  {}", w.as_str().unwrap_or("")), &F8X13, t.alarm);
        y += lh;
    }
    y += 2;
    // ---- left: the places; right: the purge's list ----
    let lw = at.w * 11 / 20;
    let left = rect(at.x, y, lw, at.bottom() - y);
    let rightr = rect(at.x + lw + 16, y, at.w - lw - 16, at.bottom() - y);
    let places = arr(sz, "places");
    let top = places.iter().filter_map(|p| p.get("bytes").and_then(|b| b.as_num())).fold(limit * 1e9 * 1.25, f64::max);
    let name_w = 110;
    let where_w = 230;
    let size_w = 74;
    let bar_x = left.x + name_w + where_w;
    let bar_w = (left.w - name_w - where_w - size_w).max(40);
    let row_h = (F8X13.height as i32 + 3).max(14);
    for p in places {
        if y + row_h > left.bottom() {
            break;
        }
        let bytes = p.get("bytes").and_then(|b| b.as_num());
        let over = p.get("over").and_then(|o| o.as_bool()).unwrap_or(false);
        let ink = if over { t.alarm } else { t.ink };
        ui.label_in(left.x, y, name_w - 6, &s(p, "place"), &F8X13, ink);
        ui.label_in(left.x + name_w, y, where_w - 6, &s(p, "where"), &F8X13, t.dim);
        let bar = rect(bar_x, y + 2, bar_w, row_h - 5);
        ui.c.rect(bar.x, bar.y, bar.w, bar.h, t.tile);
        if let Some(b) = bytes {
            let frac = (b / top).clamp(0.0, 1.0);
            let c = if over { t.alarm } else if b > limit * 1e9 * 0.75 { t.warn } else { t.accent };
            ui.c.rect(bar.x, bar.y, ((bar.w as f64) * frac).round() as i32, bar.h, c);
            ui.label_right(left.right(), y, &gb(b), &F8X13, ink);
        } else {
            ui.label_right(left.right(), y, "no answer", &F8X13, t.dim);
        }
        // The limit, as a mark across every bar at the same place.
        let lx = bar.x + ((limit * 1e9 / top) * bar.w as f64).round() as i32;
        ui.c.vline(lx, bar.y - 2, bar.h + 4, t.alarm);
        let mut lines = vec![format!("{}: {} ({})", s(p, "place"), s(p, "where"), s(p, "path"))];
        lines.push(match bytes {
            Some(b) => format!("{} of a {:.0} GB limit{}", gb(b), limit, if over { ": OVER" } else { "" }),
            None => format!("not measured: {}", s(p, "error")),
        });
        if let Some(d) = p.get("disk").filter(|d| !matches!(d, Value::Null)) {
            lines.push(format!("its disk: {} free of {}", gb(n(d, "free")), gb(n(d, "size"))));
        }
        for part in arr(p, "parts") {
            let rebuilt = match part.get("rebuilt").and_then(|r| r.as_bool()) {
                Some(true) => "  (rebuilt on demand)",
                Some(false) if s(part, "what").contains("not rebuilt") => "",
                _ => "",
            };
            lines.push(format!("  {}  {}  {}{}", gb(n(part, "bytes")), s(part, "path"), s(part, "what"), rebuilt));
        }
        ui.tip(rect(left.x, y, left.w, row_h), move || lines);
        y += row_h;
    }
    draw_purge(ui, rightr, doc);
}

fn draw_purge(ui: &mut Ui, at: Rect, doc: &Value) {
    let t = ui.t;
    let lh = F8X13.height as i32 + 3;
    let Some(p) = doc.get("purge").filter(|x| !matches!(x, Value::Null)) else {
        ui.label_in(at.x, at.y, at.w, "Purge lists first: nothing is listed yet.", &F8X13, t.dim);
        return;
    };
    let mut y = at.y;
    let done = s(p, "state") == "done";
    let head = if done {
        format!("Purged {} at {}:", gb(n(p, "bytes")), s(p, "at").replace('T', " "))
    } else {
        format!("A purge would free {} (listed {}, keeping {} days):", gb(n(p, "bytes")), s(p, "at").replace('T', " "), n(p, "keep_days") as i64)
    };
    ui.label_in(at.x, y, at.w, &head, &F8X13, if done { t.up } else { t.ink });
    y += lh + 2;
    if done {
        for d in arr(p, "did") {
            if y + lh > at.bottom() {
                return;
            }
            ui.label_in(at.x + 8, y, at.w - 8, d.as_str().unwrap_or(""), &F8X13, t.dim);
            y += lh;
        }
    } else {
        let mut items: Vec<&Value> = arr(p, "items").iter().collect();
        items.sort_by(|a, b| n(b, "bytes").partial_cmp(&n(a, "bytes")).unwrap_or(std::cmp::Ordering::Equal));
        for it in items {
            if y + lh > at.bottom() {
                return;
            }
            ui.label_in(at.x + 8, y, 92, &s(it, "place"), &F8X13, t.ink);
            ui.label_right(at.x + 8 + 92 + 70, y, &gb(n(it, "bytes")), &F8X13, t.ink);
            ui.label_in(at.x + 8 + 92 + 80, y, at.w - 188, &s(it, "what"), &F8X13, t.dim);
            let (place, what, count, bytes) = (s(it, "place"), s(it, "what"), n(it, "count") as i64, n(it, "bytes"));
            ui.tip(rect(at.x, y, at.w, lh), move || vec![format!("{}: {} items, {}", place, count, gb(bytes)), what]);
            y += lh;
        }
    }
    for k in arr(p, "kept") {
        if y + lh > at.bottom() {
            return;
        }
        ui.label_in(at.x + 8, y, at.w - 8, &format!("kept  {}  {} {}: {}", s(k, "place"), gb(n(k, "bytes")), s(k, "what"), s(k, "why")), &F8X13, t.dim);
        y += lh;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_size_reads_in_the_unit_a_person_would_say() {
        assert_eq!(gb(114.3e9), "114.3 GB");
        assert_eq!(gb(560e6), "560 MB");
    }

    #[test]
    fn a_number_keeps_the_digits_its_size_deserves() {
        assert_eq!(num(381.296), "381.3");
        assert_eq!(num(9.218), "9.218");
        assert_eq!(num(-0.574), "-0.574");
        assert_eq!(num(234500.0), "234500");
    }

    #[test]
    fn a_sample_line_names_its_island_generation_and_the_numbers_it_has() {
        let fields: Vec<String> = ["gen", "best", "yard", "world", "job", "time", "dims"].iter().map(|s| s.to_string()).collect();
        let row = vec![Value::Num(161200.0), Value::Num(2.293), Value::Null, Value::Num(0.12), Value::Str("x-whitewolf-cuda-1980".into()), Value::Str("2026-11-03T22:39:14".into()), Value::Str("55-48-48-4".into())];
        let l = sample_line(&fields, "whitewolf-cuda", &row);
        assert!(l.starts_with("whitewolf g161200  best 2.293  world 0.120"), "{}", l);
        assert!(!l.contains("yard"), "a missing number is not said: {}", l);
        assert!(l.contains("55-48-48-4") && l.contains("x-whitewolf-cuda-1980") && l.contains("2026-11-03 22:39:14"), "{}", l);
    }

    #[test]
    fn every_measure_is_a_field_the_tool_writes() {
        let tool = include_str!("../tools/growth.py");
        for (k, _, _) in METRICS {
            assert!(tool.contains(&format!("\"{}\"", k)), "{} is drawn but growth.py never writes it", k);
        }
    }
}
