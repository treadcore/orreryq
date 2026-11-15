//! Queue, Heat: the fleet's heat as an energy balance (Paul, 15 November: "work on the orrery gui
//! with the start of the data, then start analysis of heat capacity, of expected fin temperature, and
//! current heat air extraction ... The end goal of this is to find something like a PID controller
//! to control the ambient air temperature. Through conservation of energy analysis screens").
//!
//! The document is `tools/thermal.py`'s (QUEUE/plan/thermal.json), written after each pull of the
//! machines' own five-second telemetry. THE PAGE DRAWS; IT MEASURES AND FITS NOTHING. Every watt a
//! machine draws leaves it as heat, so the top line is the fleet's watts and the air that carries
//! them off. A row a machine: what it reads against its limits, what it draws, six hours of its CPU
//! and its card on one scale with the limit ruled across, and what the steps the queue made say of
//! each part: its time constant, its degrees a watt, its joules a degree, where it settles at the
//! watts it draws now. A part no step has measured says so, and how to make the step.
//!
//! FOUR PANELS, each sorted as its buttons say (Paul, 15 November: "add more screens and live data to
//! orrery. more sub panels to sort by different aspects ... expand the row on click, less hover
//! information"). Machines: a row a machine, opened by a click to its record and THE SOAK, every other
//! thermometer overlaid as degrees above its own lowest, coloured by kind, a part picked out by a
//! click. Parts: every thermometer in the fleet that is not a CPU, with how slowly it follows its
//! machine's watts (heat_page.py's fit). Watts: the conservation, a bar a machine. Steps: every fit.
//! Nothing is said on hover.
//!
//! No dial yet. A target a machine and a throttle on its part in the queue wait for the model the
//! numbers here are the start of; the room's own temperature is read by nothing in the fleet, and the
//! page says what stands in its place.
use crate::draw::Rgb;
use crate::font::{F6X10, F8X13};
use crate::json::Value;
use crate::ui::{rect, Rect, Ui};
use std::cell::RefCell;

fn n(v: &Value, k: &str) -> Option<f64> {
    v.get(k).and_then(|x| x.as_num())
}
fn s<'a>(v: &'a Value, k: &str) -> &'a str {
    v.get(k).and_then(|x| x.as_str()).unwrap_or("")
}
fn arr<'a>(v: &'a Value, k: &str) -> &'a [Value] {
    v.get(k).and_then(|x| x.as_array()).unwrap_or(&[])
}

/// A line, one pixel wide (Bresenham's), as growth.rs draws its charts.
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

/// Seconds, as a person says them.
pub fn took(sec: f64) -> String {
    if sec < 120.0 {
        format!("{:.0} s", sec)
    } else if sec < 7200.0 {
        format!("{:.0} min", sec / 60.0)
    } else {
        format!("{:.1} h", sec / 3600.0)
    }
}

/// What the fits say of one part, in a line; or how to find out.
pub fn part_line(what: &str, model: Option<&Value>) -> String {
    match model {
        Some(d) => {
            let mut out = format!(
                "{}: tau {}, {:.2} C/W, {:.0} J/C; settles at {:.0} C at the watts now",
                what,
                took(n(d, "tau_s").unwrap_or(0.0)),
                n(d, "r_c_w").unwrap_or(0.0),
                n(d, "c_j_c").unwrap_or(0.0),
                n(d, "settles_c").unwrap_or(0.0)
            );
            if let Some(f) = n(d, "fin_c") {
                out.push_str(&format!("; the fin {:.0} C", f));
            }
            out
        }
        None => format!("{}: no step held three tau yet (Pause it, wait, Resume)", what),
    }
}

/// Series of numbers and gaps, drawn across `plot` between lo and hi.
fn trace(ui: &mut Ui, plot: Rect, v: &[Value], lo: f64, hi: f64, c: Rgb) {
    trace_n(ui, plot, &nums(v), lo, hi, c);
}

fn trace_n(ui: &mut Ui, plot: Rect, v: &[Option<f64>], lo: f64, hi: f64, c: Rgb) {
    let k = v.len().max(2) as f64 - 1.0;
    let mut last: Option<(i32, i32)> = None;
    for (i, x) in v.iter().enumerate() {
        match x {
            Some(y) => {
                let q = (plot.x + ((i as f64 / k) * (plot.w - 1) as f64).round() as i32, plot.bottom() - 1 - (((y - lo) / (hi - lo)).clamp(0.0, 1.0) * (plot.h - 1) as f64).round() as i32);
                match last {
                    Some(a) => seg(ui, a, q, c),
                    None => ui.c.set(q.0, q.1, c),
                }
                last = Some(q);
            }
            None => last = None,
        }
    }
}

fn span(vs: &[&[Value]]) -> Option<(f64, f64)> {
    let all = vs.iter().flat_map(|v| v.iter()).filter_map(|x| x.as_num());
    let (lo, hi) = all.fold((f64::INFINITY, f64::NEG_INFINITY), |(a, b), v| (a.min(v), b.max(v)));
    if lo.is_finite() { Some((lo, hi)) } else { None }
}

/// The page under the Machines' keys: the header, then the same drawing as Queue, Heat.
pub fn draw_view(ui: &mut Ui, doc: Option<&Value>) -> Option<crate::nav::View> {
    let (rest, go, _) = crate::nav::header(ui, crate::nav::View::Heat, true, "the fleet's heat: temperatures, watts, and what each part's steps say", None);
    draw(ui, rest.inset(10), doc);
    go
}

/// What the page remembers between frames: which panel, how each is sorted, which machine is open,
/// which part is picked out of its overlay, and where each list is scrolled to.
#[derive(Default)]
struct St {
    panel: usize,
    sort: [usize; 4],
    open: Option<String>,
    pick: Option<String>,
    off: [usize; 4],
}
thread_local! {
    static ST: RefCell<St> = RefCell::new(from_env());
}

/// A picture of one panel is asked for as the other pages' are, by the environment:
/// ORRERY_HEAT=PANEL[,MACHINE] (0 Machines, 1 Parts, 2 Watts, 3 Steps; the machine opened).
fn from_env() -> St {
    let mut st = St::default();
    if let Ok(v) = std::env::var("ORRERY_HEAT") {
        let mut it = v.split(',');
        st.panel = it.next().and_then(|p| p.parse().ok()).unwrap_or(0);
        st.open = it.next().filter(|m| !m.is_empty()).map(String::from);
    }
    st
}

const PANELS: [&str; 4] = ["Machines", "Parts", "Watts", "Steps"];
const SORTS: [&[&str]; 4] = [
    &["name", "nearest its limit", "watts", "CPU's tau", "slowest part"],
    &["hottest", "widest swing", "slowest to follow", "machine"],
    &["watts", "share of its limit", "name"],
    &["newest", "longest tau", "machine"],
];

/// A kind of part, its name, and its colour in the overlay (heat_page.py's kinds, the same order).
const KINDS: [(&str, &str, Rgb); 6] =
    [("disk", "disks", 0x1baf7a), ("nvme", "NVMe", 0xd99a00), ("memory", "memory", 0xe0679a), ("board", "the board", 0x7f70e0), ("port", "10 GbE", 0xe05050), ("card", "the card", 0xe8703a)];

fn kind_colour(k: &str) -> Rgb {
    KINDS.iter().find(|x| x.0 == k).map(|x| x.2).unwrap_or(0x888888)
}

/// A channel's key as a person reads it: `drivetemp_4.temp1` is disk 4, `gpu.c` the card.
pub fn part_name(k: &str) -> String {
    if k == "gpu.c" {
        return "card".to_string();
    }
    if let Some(rest) = k.strip_prefix("drivetemp_") {
        if let Some(i) = rest.strip_suffix(".temp1") {
            return format!("disk {}", i);
        }
    }
    let k = k.strip_prefix("ipmi.").unwrap_or(k);
    match k.strip_prefix("disk.") {
        Some(d) => format!("disk {}", d),
        None => k.replace(['_', '.'], " "),
    }
}

/// How slowly a part follows its machine's watts, or that the record does not say yet.
fn lag(p: &Value) -> String {
    match n(p, "tau_s") {
        Some(tau) if p.get("edge").and_then(|b| b.as_bool()).unwrap_or(false) => format!("over {}", took(tau)),
        Some(tau) => took(tau),
        None => "not yet told".to_string(),
    }
}

fn nums(v: &[Value]) -> Vec<Option<f64>> {
    v.iter().map(|x| x.as_num()).collect()
}

/// A row of buttons, the one in force underlined; returns the x after the last.
fn chips(ui: &mut Ui, x: i32, y: i32, names: &[&str], cur: &mut usize) -> i32 {
    let mut x = x;
    for (i, name) in names.iter().enumerate() {
        let r = rect(x, y, F8X13.measure(name) as i32 + 18, 22);
        if *cur == i {
            ui.c.rect(r.x + 4, r.bottom(), r.w - 8, 2, ui.t.up);
        }
        if ui.button(r, name, *cur != i) {
            *cur = i;
        }
        x = r.right() + 4;
    }
    x
}

/// How near its limit a machine's hottest part is, in degrees; far where nothing is read.
fn headroom(m: &Value) -> f64 {
    let one = |k: &str| Some(n(m, &format!("{}_hot", k))? - n(m, &format!("{}_c", k))?);
    [one("cpu"), one("gpu")].iter().flatten().cloned().fold(1e9, f64::min)
}

pub fn draw(ui: &mut Ui, at: Rect, doc: Option<&Value>) {
    let t = ui.t;
    let Some(doc) = doc.filter(|d| d.get("machines").is_some()) else {
        ui.label_in(at.x, at.y, at.w, "No record yet: tools/telemetry.py QUEUE pull writes plan/thermal.json (the keeper's housekeeping asks each five minutes).", &F8X13, t.dim);
        return;
    };
    let mut st = ST.with(|s| std::mem::take(&mut *s.borrow_mut()));
    let lh = F8X13.height as i32;
    let mut y = at.y;
    // The fleet: what goes in comes out.
    if let Some(fl) = doc.get("fleet") {
        let head = format!(
            "The fleet's heat now: {:.0} W from {:.0} machines ({:.0} BTU/h). {:.0} m3/h of air carries it off at a ten-degree rise.",
            n(fl, "heat_w").unwrap_or(0.0),
            n(fl, "machines").unwrap_or(0.0),
            n(fl, "btu_h").unwrap_or(0.0),
            n(fl, "air_m3h").unwrap_or(0.0)
        );
        ui.label_in(at.x, y, at.w, &head, &F8X13, t.ink);
        y += lh + 2;
        let room = match n(fl, "coldest_c") {
            Some(c) => format!("The room: read by nothing. It is no warmer than {:.1} C, the coldest reading in the fleet ({}).", c, s(fl, "coldest_from")),
            None => "The room: read by nothing, and no machine's coldest reading stands in for it yet.".to_string(),
        };
        ui.label_in(at.x, y, at.w, &room, &F8X13, t.dim);
        y += lh + 6;
    }
    // The panels, and how the one shown is sorted.
    let x = chips(ui, at.x, y, &PANELS, &mut st.panel);
    let p = st.panel.min(3);
    let x = ui.label(x + 16, y + 5, "sorted by", &F8X13, t.dim) + 8;
    chips(ui, x, y, SORTS[p], &mut st.sort[p]);
    y += 22 + 8;
    let body = rect(at.x, y, at.w, at.bottom() - y);
    match p {
        0 => machines(ui, body, doc, &mut st),
        1 => parts(ui, body, doc, &mut st),
        2 => watts(ui, body, doc, &mut st),
        _ => steps(ui, body, doc, &mut st),
    }
    ST.with(|s| *s.borrow_mut() = st);
}

/// A row a machine, the CPU first. A click on a row opens it: its record large, and beside it the
/// soak, every other thermometer overlaid as degrees above its own lowest.
fn machines(ui: &mut Ui, at: Rect, doc: &Value, st: &mut St) {
    let t = ui.t;
    let lh = F8X13.height as i32;
    let mut ms: Vec<&Value> = arr(doc, "machines").iter().collect();
    let tau = |m: &Value| m.get("model").and_then(|z| z.get("cpu")).and_then(|c| n(c, "tau_s"));
    let slow = |m: &Value| m.get("slow").and_then(|z| n(z, "tau_s"));
    match st.sort[0] {
        1 => ms.sort_by(|a, b| headroom(a).total_cmp(&headroom(b))),
        2 => ms.sort_by(|a, b| n(b, "wall_w").unwrap_or(0.0).total_cmp(&n(a, "wall_w").unwrap_or(0.0))),
        3 => ms.sort_by(|a, b| tau(b).unwrap_or(-1.0).total_cmp(&tau(a).unwrap_or(-1.0))),
        4 => ms.sort_by(|a, b| slow(b).unwrap_or(-1.0).total_cmp(&slow(a).unwrap_or(-1.0))),
        _ => {}
    }
    if ms.is_empty() {
        return;
    }
    let is_open = |m: &Value, st: &St| st.open.as_deref() == Some(s(m, "name"));
    let any_open = ms.iter().any(|m| is_open(m, st));
    let small = lh * 3 + 12;
    let closed_h = if any_open { small } else { ((at.h / ms.len() as i32) - 4).clamp(small, 96) };
    let open_h = (at.h - (ms.len() as i32 - 1) * (small + 4) - 4).clamp(220, 420);
    let (left_w, chart_w) = (300.min(at.w / 4), (at.w * 3 / 10).max(160));
    let mut y = at.y;
    for m in ms {
        let open = is_open(m, st);
        let row_h = if open { open_h.min(at.bottom() - y) } else { closed_h };
        if y + row_h > at.bottom() || row_h < small {
            break;
        }
        let row = rect(at.x, y, at.w, row_h);
        ui.c.frame(row.x, row.y, row.w, row.h, if open { t.accent } else { t.line });
        let head = rect(row.x, row.y, row.w, small);
        if ui.button_hit(if open { head } else { row }) {
            st.open = if open { None } else { Some(s(m, "name").to_string()) };
            st.pick = None;
        }
        let fresh = n(m, "age_s").unwrap_or(1e9) < 600.0;
        let x = row.x + 8;
        ui.label(x, row.y + 4, s(m, "name"), &F8X13, if fresh { t.ink } else { t.dim });
        if !fresh {
            ui.label(x + 120, row.y + 4, &format!("last heard {} ago", took(n(m, "age_s").unwrap_or(0.0))), &F8X13, t.warn);
        } else if !m.get("in_queue").and_then(|b| b.as_bool()).unwrap_or(true) {
            ui.label(x + 120, row.y + 4, "not in the queue", &F8X13, t.dim);
        }
        // What it reads against its limits; amber within five degrees.
        let mut tx = x;
        for (what, k) in [("CPU", "cpu"), ("card", "gpu")] {
            if let Some(c) = n(m, &format!("{}_c", k)) {
                let hot = n(m, &format!("{}_hot", k));
                let say = match hot {
                    Some(h) => format!("{} {:.0} C of {:.0}", what, c, h),
                    None => format!("{} {:.0} C", what, c),
                };
                let near = hot.map(|h| c >= h - 5.0).unwrap_or(false);
                tx = ui.label(tx, row.y + 4 + lh + 2, &say, &F8X13, if near { t.warn } else { t.ink }) + 14;
            }
        }
        if tx == x {
            ui.label(x, row.y + 4 + lh + 2, "no CPU sensor read", &F8X13, t.dim);
        }
        if let Some(w) = n(m, "wall_w") {
            let say = format!("{:.0} W at the wall; {:.0} m3/h of air", w, n(m, "air_m3h").unwrap_or(0.0));
            ui.label_in(x, row.y + 4 + 2 * (lh + 2), left_w - 12, &say, &F8X13, t.dim);
        }
        // What the steps say of each part, and the slowest part found.
        let rx = if open { row.x + left_w } else { row.x + left_w + chart_w + 12 };
        let rw = row.right() - rx - 8;
        let model = m.get("model");
        let mut ry = row.y + 4;
        if n(m, "cpu_c").is_some() {
            let d = model.and_then(|z| z.get("cpu"));
            ui.label_in(rx, ry, rw, &part_line("CPU", d), &F8X13, if d.is_some() { t.ink } else { t.dim });
            ry += lh + 2;
        }
        if n(m, "gpu_c").is_some() {
            let d = model.and_then(|z| z.get("gpu"));
            ui.label_in(rx, ry, rw, &part_line("card", d), &F8X13, if d.is_some() { t.ink } else { t.dim });
            ry += lh + 2;
        }
        if ry + lh <= row.y + small {
            let say = match m.get("slow").filter(|z| n(z, "tau_s").is_some()) {
                Some(z) => format!("slowest part found: {}, following the watts by {}", part_name(s(z, "key")), lag(z)),
                None => "no part's lag behind the watts is told yet".to_string(),
            };
            ui.label_in(rx, ry, rw, &say, &F8X13, t.dim);
        }
        let rec = m.get("record");
        let pick = |k: &str| rec.map(|z| nums(arr(z, k))).unwrap_or_default();
        let (cpu, gpu) = (pick("cpu"), pick("card"));
        if !open {
            let well = rect(row.x + left_w, row.y + 4, chart_w, row_h - 8);
            temps_chart(ui, well, m, &cpu, &gpu);
            y += row_h + 4;
            continue;
        }
        // Open: the record large, the soak beside it, the parts in a list.
        let top = row.y + small + lh + 4;
        let h = row.bottom() - top - lh - 10;
        let cw = (row.w - 32) * 35 / 100;
        let hours = n(doc, "record_h").unwrap_or(0.0);
        ui.label_in(row.x + 8, top - lh - 2, cw, &format!("CPU (green) and card (amber), {} hours, the limit dashed", hours), &F8X13, t.dim);
        temps_chart(ui, rect(row.x + 8, top, cw, h), m, &cpu, &gpu);
        let ps = arr(m, "parts");
        let sx = row.x + 16 + cw;
        ui.label_in(sx, top - lh - 2, cw, &format!("the soak: {} other thermometers, degrees above each one's lowest", ps.len()), &F8X13, t.dim);
        let well = rect(sx, top, cw, h);
        ui.well(well);
        let plot = rect(well.x + 3, well.y + 3, well.w - 6 - 26, well.h - 6);
        let rises: Vec<(&Value, Vec<Option<f64>>)> = ps.iter().map(|p| (p, nums(arr(p, "y")).iter().map(|v| v.map(|v| v - n(p, "lo").unwrap_or(0.0))).collect())).collect();
        let hi = rises.iter().flat_map(|r| r.1.iter().flatten()).cloned().fold(1.0, f64::max) * 1.05;
        for (p, r) in &rises {
            if st.pick.as_deref() != Some(s(p, "key")) {
                trace_n(ui, plot, r, 0.0, hi, kind_colour(s(p, "kind")));
            }
        }
        for (p, r) in &rises {
            if st.pick.as_deref() == Some(s(p, "key")) {
                trace_n(ui, plot, r, 0.0, hi, t.ink);
                trace_n(ui, rect(plot.x, plot.y + 1, plot.w, plot.h), r, 0.0, hi, t.ink);
            }
        }
        ui.label(plot.right() + 3, plot.y, &format!("{:.0}", hi), &F6X10, t.dim);
        ui.label(plot.right() + 3, plot.bottom() - F6X10.height as i32, "0", &F6X10, t.dim);
        let mut kx = sx;
        for (k, name, c) in KINDS {
            let count = ps.iter().filter(|p| s(p, "kind") == k).count();
            if count > 0 {
                ui.c.rect(kx, well.bottom() + 9, 10, 3, c);
                kx = ui.label(kx + 14, well.bottom() + 4, &format!("{} ({})", name, count), &F8X13, t.dim) + 12;
            }
        }
        // The parts, slowest first; a click picks one's line out.
        let lx = sx + cw + 12;
        let lw = row.right() - lx - 8;
        ui.label_in(lx, top - lh - 2, lw, "part, now, how slowly it follows the watts (click one)", &F8X13, t.dim);
        let mut sorted: Vec<&Value> = ps.iter().collect();
        sorted.sort_by(|a, b| n(b, "tau_s").unwrap_or(-1.0).total_cmp(&n(a, "tau_s").unwrap_or(-1.0)));
        let (area, first, fit) = ui.scroll_list(rect(lx, top, lw, h + lh + 4), sorted.len(), lh + 2, &mut st.off[0]);
        for (i, p) in sorted.iter().skip(first).take(fit).enumerate() {
            let r = rect(area.x, area.y + i as i32 * (lh + 2), area.w, lh + 2);
            let on = st.pick.as_deref() == Some(s(p, "key"));
            if ui.button_hit(r) {
                st.pick = if on { None } else { Some(s(p, "key").to_string()) };
            }
            ui.c.rect(r.x, r.y + 4, 8, 8, kind_colour(s(p, "kind")));
            let c = if on { t.ink } else if n(p, "tau_s").is_some() { t.ink } else { t.dim };
            ui.label_in(r.x + 14, r.y, r.w * 45 / 100, &part_name(s(p, "key")), &F8X13, c);
            ui.label(r.x + 14 + r.w * 45 / 100, r.y, &format!("{:.0} C", n(p, "now").unwrap_or(0.0)), &F8X13, c);
            ui.label_right(r.right() - 2, r.y, &lag(p), &F8X13, c);
            if on {
                ui.c.hline(r.x + 14, r.bottom() - 1, r.w - 16, t.ink);
            }
        }
        y += row_h + 4;
    }
}

/// A machine's CPU and card on one scale, each limit dashed across.
fn temps_chart(ui: &mut Ui, well: Rect, m: &Value, cpu: &[Option<f64>], gpu: &[Option<f64>]) {
    let t = ui.t;
    ui.well(well);
    let plot = rect(well.x + 3, well.y + 3, well.w - 6 - 26, well.h - 6);
    let all = cpu.iter().chain(gpu.iter()).flatten().cloned();
    let (lo, hi) = all.fold((f64::INFINITY, f64::NEG_INFINITY), |(a, b), v| (a.min(v), b.max(v)));
    if !lo.is_finite() {
        ui.label_in(plot.x + 4, plot.y + 4, plot.w - 8, "no CPU or card reading in the record", &F6X10, t.dim);
        return;
    }
    let limits: Vec<f64> = [n(m, "cpu_hot").filter(|_| cpu.iter().any(|v| v.is_some())), n(m, "gpu_hot")].iter().flatten().cloned().collect();
    let hi = limits.iter().cloned().fold(hi, f64::max) + 2.0;
    let lo = (lo - 2.0).min(hi - 10.0);
    for l in &limits {
        let ly = plot.bottom() - 1 - (((l - lo) / (hi - lo)) * (plot.h - 1) as f64).round() as i32;
        let mut dx = 0;
        while dx < plot.w {
            ui.c.hline(plot.x + dx, ly, 4.min(plot.w - dx), t.alarm);
            dx += 8;
        }
    }
    trace_n(ui, plot, gpu, lo, hi, t.warn);
    trace_n(ui, plot, cpu, lo, hi, t.up);
    ui.label(plot.right() + 3, plot.y, &format!("{:.0}", hi), &F6X10, t.dim);
    ui.label(plot.right() + 3, plot.bottom() - F6X10.height as i32, &format!("{:.0}", lo), &F6X10, t.dim);
}

/// Text in columns: each cell at its column's left, or flush to its right edge where `right`.
fn cells(ui: &mut Ui, r: Rect, cols: &[(i32, bool)], text: &[String], c: Rgb) {
    let mut x = r.x;
    for ((w, right), s) in cols.iter().zip(text) {
        let w = *w * r.w / 1000;
        if *right {
            ui.label_right(x + w - 10, r.y, s, &F8X13, c);
        } else {
            ui.label_in(x, r.y, w - 8, s, &F8X13, c);
        }
        x += w;
    }
}

/// Every thermometer in the fleet that is not a CPU, in one list. A click goes to its machine, opened,
/// with the part's line picked out.
fn parts(ui: &mut Ui, at: Rect, doc: &Value, st: &mut St) {
    let t = ui.t;
    let lh = F8X13.height as i32 + 3;
    let mut all: Vec<(&str, &Value)> = arr(doc, "machines").iter().flat_map(|m| arr(m, "parts").iter().map(move |p| (s(m, "name"), p))).collect();
    let swing = |p: &Value| n(p, "hi").unwrap_or(0.0) - n(p, "lo").unwrap_or(0.0);
    match st.sort[1] {
        0 => all.sort_by(|a, b| n(b.1, "now").unwrap_or(0.0).total_cmp(&n(a.1, "now").unwrap_or(0.0))),
        1 => all.sort_by(|a, b| swing(b.1).total_cmp(&swing(a.1))),
        2 => all.sort_by(|a, b| n(b.1, "tau_s").unwrap_or(-1.0).total_cmp(&n(a.1, "tau_s").unwrap_or(-1.0))),
        _ => {}
    }
    let cols = [(130, false), (200, false), (110, false), (70, true), (70, true), (70, true), (70, true), (150, true), (70, true), (60, true)];
    let head = ["machine", "part", "kind", "now", "lowest", "highest", "swing", "follows the watts by", "C a watt", "fit"].map(String::from);
    cells(ui, rect(at.x + 4, at.y, at.w - 24, lh), &cols, &head, t.dim);
    ui.hrule(at.x, at.y + lh, at.w);
    if all.is_empty() {
        ui.label_in(at.x + 4, at.y + lh + 6, at.w, "No part is in the record yet: the next pull writes them.", &F8X13, t.dim);
        return;
    }
    let (area, first, fit) = ui.scroll_list(rect(at.x, at.y + lh + 4, at.w, at.h - lh - 4), all.len(), lh, &mut st.off[1]);
    for (i, (name, p)) in all.iter().skip(first).take(fit).enumerate() {
        let r = rect(area.x + 4, area.y + i as i32 * lh, area.w - 8, lh);
        if ui.button_hit(r) {
            st.open = Some(name.to_string());
            st.pick = Some(s(p, "key").to_string());
            st.panel = 0;
        }
        let kind = KINDS.iter().find(|k| k.0 == s(p, "kind")).map(|k| k.1).unwrap_or("");
        let deg = |k: &str| format!("{:.0}", n(p, k).unwrap_or(0.0));
        let row = [
            name.to_string(),
            part_name(s(p, "key")),
            kind.to_string(),
            deg("now"),
            deg("lo"),
            deg("hi"),
            format!("{:.0}", swing(p)),
            lag(p),
            n(p, "c_w").map(|v| format!("{:.3}", v)).unwrap_or_default(),
            n(p, "r2").map(|v| format!("{:.0}%", v * 100.0)).unwrap_or_default(),
        ];
        cells(ui, r, &cols, &row, if n(p, "tau_s").is_some() { t.ink } else { t.dim });
        ui.c.rect(r.x + cols[0].0 * r.w / 1000 + cols[1].0 * r.w / 1000 - 14, r.y + 4, 8, 8, kind_colour(s(p, "kind")));
    }
}

/// Conservation: each machine's watts at the wall as a bar (its CPU, its card, the rest), its share
/// of the fleet's heat, and the air that carries it off.
fn watts(ui: &mut Ui, at: Rect, doc: &Value, st: &mut St) {
    let t = ui.t;
    let lh = F8X13.height as i32;
    let mut y = at.y;
    let fl = doc.get("fleet");
    let w = fl.and_then(|f| f.get("series")).map(|z| arr(z, "w")).unwrap_or(&[]);
    if let Some((_, hi)) = span(&[w]) {
        ui.label_in(at.x, y, at.w, &format!("the fleet's watts at the wall over the last {} hours: all of it heat into the room", n(doc, "hours").unwrap_or(6.0)), &F8X13, t.dim);
        y += lh + 2;
        let strip = rect(at.x, y, at.w - 60, 64);
        ui.well(strip);
        trace(ui, strip.inset(3), w, 0.0, hi * 1.08, t.accent);
        ui.label(strip.right() + 4, strip.y, &format!("{:.0} W", hi * 1.08), &F6X10, t.dim);
        ui.label(strip.right() + 4, strip.bottom() - F6X10.height as i32, "0", &F6X10, t.dim);
        y += strip.h + 10;
    }
    let mut ms: Vec<&Value> = arr(doc, "machines").iter().collect();
    let wall = |m: &Value| n(m, "wall_w").unwrap_or(0.0);
    match st.sort[2] {
        0 => ms.sort_by(|a, b| wall(b).total_cmp(&wall(a))),
        1 => ms.sort_by(|a, b| headroom(a).total_cmp(&headroom(b))),
        _ => {}
    }
    let total: f64 = ms.iter().map(|m| wall(m)).sum();
    let top = ms.iter().map(|m| wall(m)).fold(1.0, f64::max);
    let cols = [(220, false), (120, true), (120, true), (120, true), (120, true), (150, true), (150, true)];
    let head = ["machine", "wall W", "CPU W", "card W", "share", "air m3/h", "BTU/h"].map(String::from);
    let tw = at.w * 52 / 100;
    cells(ui, rect(at.x + 4, y, tw, lh), &cols, &head, t.dim);
    ui.label(at.x + tw + 12, y, "CPU (green), card (amber), the rest and the supply's loss (grey)", &F8X13, t.dim);
    y += lh + 2;
    ui.hrule(at.x, y, at.w);
    y += 4;
    for m in &ms {
        if y + lh + 8 > at.bottom() {
            break;
        }
        let (cw, gw, ww) = (n(m, "cpu_w").unwrap_or(0.0), n(m, "gpu_w").unwrap_or(0.0), wall(m));
        let row = [
            s(m, "name").to_string(),
            format!("{:.0}", ww),
            format!("{:.0}", cw),
            if n(m, "gpu_c").is_some() { format!("{:.0}", gw) } else { String::new() },
            format!("{:.0}%", 100.0 * ww / total.max(1.0)),
            format!("{:.0}", n(m, "air_m3h").unwrap_or(0.0)),
            format!("{:.0}", ww * 3.412),
        ];
        cells(ui, rect(at.x + 4, y + 2, tw, lh), &cols, &row, t.ink);
        let bar = rect(at.x + tw + 12, y, at.w - tw - 20, lh + 4);
        let px = |v: f64| ((v / top) * bar.w as f64).round() as i32;
        ui.c.rect(bar.x, bar.y, px(ww), bar.h, t.line);
        ui.c.rect(bar.x, bar.y, px(cw), bar.h, t.up);
        ui.c.rect(bar.x + px(cw) + 1, bar.y, px(gw), bar.h, t.warn);
        y += lh + 10;
    }
    ui.hrule(at.x, y, at.w);
    y += 4;
    if y + lh <= at.bottom() {
        let row = ["the fleet".to_string(), format!("{:.0}", total), String::new(), String::new(), "100%".to_string(), format!("{:.0}", fl.and_then(|f| n(f, "air_m3h")).unwrap_or(0.0)), format!("{:.0}", total * 3.412)];
        cells(ui, rect(at.x + 4, y, tw, lh), &cols, &row, t.ink);
        ui.label_in(at.x + tw + 12, y, at.w - tw - 20, "A watt in is a watt of heat out; the air figure is at a ten-degree rise.", &F8X13, t.dim);
    }
}

/// Every fitted step in the fleet: what stepped, the part that answered, and what the answer says.
fn steps(ui: &mut Ui, at: Rect, doc: &Value, st: &mut St) {
    let t = ui.t;
    let lh = F8X13.height as i32 + 3;
    let now = n(doc, "t").unwrap_or(0.0);
    let mut all: Vec<(&str, &Value)> = arr(doc, "machines").iter().flat_map(|m| arr(m, "fits").iter().map(move |f| (s(m, "name"), f))).collect();
    match st.sort[3] {
        0 => all.sort_by(|a, b| n(b.1, "at").unwrap_or(0.0).total_cmp(&n(a.1, "at").unwrap_or(0.0))),
        1 => all.sort_by(|a, b| n(b.1, "tau_s").unwrap_or(0.0).total_cmp(&n(a.1, "tau_s").unwrap_or(0.0))),
        _ => {}
    }
    let cols = [(100, false), (100, false), (170, false), (180, false), (60, true), (60, true), (55, true), (70, true), (65, true), (140, true)];
    let head = ["machine", "when", "part", "the step", "tau", "from C", "to C", "C a watt", "J a C", "tau held"].map(String::from);
    cells(ui, rect(at.x + 4, at.y, at.w - 24, lh), &cols, &head, t.dim);
    ui.hrule(at.x, at.y + lh, at.w);
    if all.is_empty() {
        ui.label_in(at.x + 4, at.y + lh + 6, at.w, "No step is fitted yet: Pause a lane, wait for its job and five tau more, Resume.", &F8X13, t.dim);
        return;
    }
    let (area, first, fit) = ui.scroll_list(rect(at.x, at.y + lh + 4, at.w, at.h - lh - 4), all.len(), lh, &mut st.off[3]);
    for (i, (name, f)) in all.iter().skip(first).take(fit).enumerate() {
        let r = rect(area.x + 4, area.y + i as i32 * lh, area.w - 8, lh);
        let held = n(f, "taus_held").unwrap_or(0.0);
        let row = [
            name.to_string(),
            format!("{} ago", took((now - n(f, "at").unwrap_or(now)).max(0.0))),
            part_name(s(f, "channel")),
            s(f, "step").to_string(),
            took(n(f, "tau_s").unwrap_or(0.0)),
            format!("{:.0}", n(f, "start_c").unwrap_or(0.0)),
            format!("{:.0}", n(f, "end_c").unwrap_or(0.0)),
            n(f, "r_c_w").map(|v| format!("{:.3}", v)).unwrap_or_default(),
            n(f, "c_j_c").map(|v| format!("{:.0}", v)).unwrap_or_default(),
            if held < 3.0 { format!("{:.1}, a projection", held) } else { format!("{:.1}", held) },
        ];
        let main = f.get("main").and_then(|b| b.as_bool()).unwrap_or(false);
        cells(ui, r, &cols, &row, if main && held >= 3.0 { t.ink } else { t.dim });
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::json;

    #[test]
    fn a_part_says_its_numbers_or_how_to_get_them() {
        let d = json::parse(r#"{"tau_s": 82, "r_c_w": 0.089, "c_j_c": 920, "settles_c": 66.1, "fin_c": 58.2}"#).unwrap();
        let line = part_line("card", Some(&d));
        assert!(line.contains("tau 82 s") && line.contains("0.09 C/W") && line.contains("920 J/C") && line.contains("the fin 58 C"));
        assert!(part_line("CPU", None).contains("Pause"));
        assert_eq!(took(300.0), "5 min");
        assert_eq!(part_name("drivetemp_4.temp1"), "disk 4");
        assert_eq!(part_name("ipmi.P1_DIMM1A_Temp"), "P1 DIMM1A Temp");
        assert_eq!(part_name("gpu.c"), "card");
        let p = json::parse(r#"{"tau_s": 5701, "edge": true}"#).unwrap();
        assert_eq!(lag(&p), "over 95 min");
        assert_eq!(lag(&json::parse("{}").unwrap()), "not yet told");
    }
}
