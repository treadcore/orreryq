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
//! FOUR PANELS OF WHAT IS, AND SINCE 16 NOVEMBER A FIFTH OF WHAT IS WANTED (Hearth, below). The four,
//! each sorted as its buttons say (Paul, 15 November: "add more screens and live data to
//! orrery. more sub panels to sort by different aspects ... expand the row on click, less hover
//! information"). Machines: a row a machine, opened by a click to its record and THE SOAK, every other
//! thermometer overlaid as degrees above its own lowest, coloured by kind, a part picked out by a
//! click. Parts: every thermometer in the fleet that is not a CPU, with how slowly it follows its
//! machine's watts (heat_page.py's fit). Watts: the conservation, a bar a machine. Steps: every fit.
//! Nothing is said on hover.
//!
//! THE HEARTH, A FIFTH PANEL AND THE FIRST IN THE ROW (Paul, 16 November: "the auto method on the fleet
//! screen with a regulate temperature, configurable on the heat screen, for target temp. use wattage
//! and use external temperature, our current configuration is at seatac airport temp"). It is the
//! controller's own two documents, QUEUE/hearth/plan.json and state.json (tools/hearth.py,
//! docs/hearth-controller.md), read here and not through the queue's document: the target with its
//! half-degree buttons, the mode, the room and its probes, the outside, the watts now against the
//! watts wanted with the law's terms, the ladder a rung a row, the last action, the plan's own
//! account. THE PANEL DECIDES NOTHING: every figure is the plan's. Its buttons run
//! `fleet-queue.py QUEUE hearth target C`, `hearth mode off|advise|act` and `hearth step`, and no
//! other; the switch that lets act power a machine off is shown and has no button here. The same
//! two documents give the Queue's Fleet page its one line and its off/advise switch (`fleet_switch`).
//! The four panels before it keep their numbers (ORRERY_HEAT=0..3), so a picture asked for by number
//! is the picture it was; the Hearth is 4, or `hearth`.
use crate::draw::Rgb;
use crate::font::{F6X10, F8X13};
use crate::json::Value;
use crate::ui::{rect, Field, Rect, Ui};
use std::cell::RefCell;
use std::rc::Rc;
use std::sync::OnceLock;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

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
pub fn draw_view(ui: &mut Ui, doc: Option<&Value>, operator: bool, said: &str, ctl: &mut Option<String>) -> Option<crate::nav::View> {
    let (rest, go, _) = crate::nav::header(ui, crate::nav::View::Heat, true, "the fleet's heat: the hearth's target and ladder, temperatures, watts, and what each part's steps say", None);
    draw(ui, rest.inset(10), doc, operator, said, ctl);
    go
}

/// What the page remembers between frames: which panel, how each is sorted, which machine is open,
/// which part is picked out of its overlay, and where each list is scrolled to.
#[derive(Default)]
struct St {
    panel: usize,
    sort: [usize; 5],
    open: Option<String>,
    pick: Option<String>,
    off: [usize; 5],
    /// The Hearth: a target being typed, act pressed once, and the last thing its buttons asked.
    typed: Field,
    arm_act: bool,
    asked: Option<String>,
}
thread_local! {
    static ST: RefCell<St> = RefCell::new(from_env());
}

/// A picture of one panel is asked for as the other pages' are, by the environment:
/// ORRERY_HEAT=PANEL[,MACHINE] (0 Machines, 1 Parts, 2 Watts, 3 Steps, 4 or `hearth` the Hearth; the
/// machine opened). ORRERY_HEAT_ARM=1 draws act pressed once, for review.
fn from_env() -> St {
    let mut st = St::default();
    if let Ok(v) = std::env::var("ORRERY_HEAT") {
        let mut it = v.split(',');
        st.panel = it.next().and_then(|p| if p == "hearth" { Some(HEARTH) } else { p.parse().ok() }).unwrap_or(0);
        st.arm_act = std::env::var("ORRERY_HEAT_ARM").is_ok();
        st.open = it.next().filter(|m| !m.is_empty()).map(String::from);
    }
    st
}

const PANELS: [&str; 5] = ["Machines", "Parts", "Watts", "Steps", "Hearth"];
/// The Hearth's number, and the row as it is drawn: the Hearth first, because it is the one panel
/// that is set and not only read; the other four keep the numbers a picture was asked by.
const HEARTH: usize = 4;
const ORDER: [usize; 5] = [HEARTH, 0, 1, 2, 3];
const SORTS: [&[&str]; 5] = [
    &["name", "nearest its limit", "watts", "CPU's tau", "slowest part"],
    &["hottest", "widest swing", "slowest to follow", "machine"],
    &["watts", "share of its limit", "name"],
    &["newest", "longest tau", "machine"],
    &[],
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

pub fn draw(ui: &mut Ui, at: Rect, doc: Option<&Value>, operator: bool, said: &str, ctl: &mut Option<String>) {
    let t = ui.t;
    let doc = doc.filter(|d| d.get("machines").is_some());
    let mut st = ST.with(|s| std::mem::take(&mut *s.borrow_mut()));
    let lh = F8X13.height as i32;
    let mut y = at.y;
    // The fleet: what goes in comes out.
    if let Some(fl) = doc.and_then(|d| d.get("fleet")) {
        let head = format!(
            "The fleet's heat now: {:.0} W from {:.0} machines ({:.0} BTU/h). {:.0} m3/h of air carries it off at a ten-degree rise.",
            n(fl, "heat_w").unwrap_or(0.0),
            n(fl, "machines").unwrap_or(0.0),
            n(fl, "btu_h").unwrap_or(0.0),
            n(fl, "air_m3h").unwrap_or(0.0)
        );
        ui.label_in(at.x, y, at.w, &head, &F8X13, t.ink);
        y += lh + 2;
        // The room: since 16 November two counters' own thermometers read it, and the hearth's plan
        // says what they say; without a plan, the coldest reading in the fleet stands in as before.
        let h = hearth();
        let room = match h.as_ref().and_then(|h| h.plan.as_ref()).and_then(|p| Some((n(p, "temp_c")?, arr(p, "temp_from").len()))) {
            Some((c, k)) => format!("The room: {}, the mean of {} probe{} at the hearth's last plan (Hearth).", both(c), k, if k == 1 { "" } else { "s" }),
            None => match n(fl, "coldest_c") {
                Some(c) => format!("The room: no fresh probe in a plan. It is no warmer than {:.1} C, the coldest reading in the fleet ({}).", c, s(fl, "coldest_from")),
                None => "The room: no fresh probe in a plan, and no machine's coldest reading stands in for it yet.".to_string(),
            },
        };
        ui.label_in(at.x, y, at.w, &room, &F8X13, t.dim);
        y += lh + 6;
    }
    // The panels, the Hearth first, and how the one shown is sorted.
    let names: Vec<&str> = ORDER.iter().map(|i| PANELS[*i]).collect();
    let mut chip = ORDER.iter().position(|i| *i == st.panel.min(HEARTH)).unwrap_or(1);
    let x = chips(ui, at.x, y, &names, &mut chip);
    st.panel = ORDER[chip];
    let p = st.panel;
    if !SORTS[p].is_empty() {
        let x = ui.label(x + 16, y + 5, "sorted by", &F8X13, t.dim) + 8;
        chips(ui, x, y, SORTS[p], &mut st.sort[p]);
    }
    y += 22 + 8;
    let body = rect(at.x, y, at.w, at.bottom() - y);
    if p != HEARTH {
        st.arm_act = false;
    }
    match (p, doc) {
        (HEARTH, _) => hearth_panel(ui, body, &mut st, operator, said, ctl),
        (_, None) => {
            ui.label_in(body.x, body.y, body.w, "No record yet: tools/telemetry.py QUEUE pull writes plan/thermal.json (the keeper's housekeeping asks each five minutes).", &F8X13, t.dim);
        }
        (0, Some(doc)) => machines(ui, body, doc, &mut st),
        (1, Some(doc)) => parts(ui, body, doc, &mut st),
        (2, Some(doc)) => watts(ui, body, doc, &mut st),
        (_, Some(doc)) => steps(ui, body, doc, &mut st),
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

// ------------------------------------------------------------------------------------ the hearth

/// The controller's two documents as they stand on disk: the plan of its last pass and its state.
/// Either may be absent: no pass has been made yet, or none ever.
#[derive(Default)]
pub struct Hearth {
    pub plan: Option<Value>,
    pub state: Option<Value>,
}

static QUEUE: OnceLock<String> = OnceLock::new();

/// The queue's directory, told once by main: the hearth's documents are QUEUE/hearth/*.json.
pub fn set_queue(dir: &str) {
    let _ = QUEUE.set(dir.to_string());
}

thread_local! {
    static DOCS: RefCell<(Option<Instant>, Option<Rc<Hearth>>)> = const { RefCell::new((None, None)) };
}

/// The two documents, read again when the last reading is two seconds old: a button's answer shows
/// at the next frames, and sixty frames a second do not open sixty files. None where no queue is
/// known. ORRERY_HEARTH=QUEUE names one for a picture, before the one main told.
pub fn hearth() -> Option<Rc<Hearth>> {
    let dir = std::env::var("ORRERY_HEARTH").ok().or_else(|| QUEUE.get().cloned())?;
    DOCS.with(|d| {
        let mut d = d.borrow_mut();
        if d.1.is_none() || d.0.map(|at| at.elapsed().as_secs() >= 2).unwrap_or(true) {
            let read = |name: &str| std::fs::read_to_string(format!("{}/hearth/{}.json", dir, name)).ok().and_then(|text| crate::json::parse(&text).ok());
            *d = (Some(Instant::now()), Some(Rc::new(Hearth { plan: read("plan"), state: read("state") })));
        }
        d.1.clone()
    })
}

pub fn f_of(c: f64) -> f64 {
    c * 9.0 / 5.0 + 32.0
}

/// A temperature in both scales, Celsius first: the controller works in it.
pub fn both(c: f64) -> String {
    format!("{:.1} C ({:.1} F)", c, f_of(c))
}

/// The target a half degree up or down, kept to a tenth and inside what hearth.py accepts.
pub fn nudged(c: f64, by: f64) -> f64 {
    (((c + by) * 10.0).round() / 10.0).clamp(5.0, 35.0)
}

/// What was typed, as a target in degrees C: `21`, `21.5 C`, or `70 F`, which is converted. Outside
/// 5 to 35 C it is refused here, with hearth.py's own reason, before anything is run.
pub fn typed_target(text: &str) -> Result<f64, String> {
    let text = text.trim();
    let (num, fahrenheit) = match text.chars().last() {
        Some('f') | Some('F') => (&text[..text.len() - 1], true),
        Some('c') | Some('C') => (&text[..text.len() - 1], false),
        _ => (text, false),
    };
    let v: f64 = num.trim().parse().map_err(|_| format!("\"{}\" is not a number of degrees: 21.5, or 70 F", text))?;
    let c = ((if fahrenheit { (v - 32.0) * 5.0 / 9.0 } else { v }) * 10.0).round() / 10.0;
    if !(5.0..=35.0).contains(&c) {
        return Err(format!("a target is between 5 and 35 C: {:.1} C was not taken (for Fahrenheit, end it with F)", c));
    }
    Ok(c)
}

impl Hearth {
    /// The mode in force: the state's, which a button changes at once, before the plan's, which is
    /// as old as the last pass. hearth.py's own default is advise.
    pub fn mode(&self) -> &str {
        fn of(v: &Option<Value>) -> Option<&str> {
            v.as_ref().and_then(|v| v.get("mode")).and_then(|m| m.as_str()).filter(|m| !m.is_empty())
        }
        of(&self.state).or(of(&self.plan)).unwrap_or("advise")
    }

    /// The target in force, the state's before the plan's; None when none is set.
    pub fn target(&self) -> Option<f64> {
        self.state.as_ref().and_then(|v| n(v, "target_c")).or(self.plan.as_ref().and_then(|v| n(v, "target_c")))
    }

    /// Whether act may power a machine off and wake it (`set power on`, from the command line only).
    pub fn power(&self) -> bool {
        self.state.as_ref().and_then(|v| v.get("set")).map(|z| s(z, "power") == "on").unwrap_or(false)
    }

    /// How many lanes and machines the controller holds now (state.json's `held`).
    pub fn held(&self) -> usize {
        match self.state.as_ref().and_then(|v| v.get("held")) {
            Some(Value::Obj(ms)) => ms.values().map(|h| if let Value::Obj(k) = h { k.len() } else { 0 }).sum(),
            _ => 0,
        }
    }
}

/// A probe in a word: fresh when it is a temperature, else the first word of why it is not
/// (suspect, stale, missing), or that it gave no reading.
pub fn probe_word(p: &Value) -> &'static str {
    if p.get("ok").and_then(|b| b.as_bool()).unwrap_or(false) {
        return "fresh";
    }
    let why = s(p, "why");
    ["suspect", "stale", "missing"].into_iter().find(|w| why.starts_with(w)).unwrap_or(if why.contains("no reading") { "no reading" } else { "not taken" })
}

/// Where a rung stands.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Standing {
    /// The controller holds it: it was shed, and is on the ladder's other side to be given back.
    Taken,
    /// It can be taken at a pass.
    Available,
    /// It opens by itself, or once another rung is taken.
    Waits,
    /// It is never taken: keep, by hand, on the bench, absent, or power is off.
    No,
}

/// A rung's standing and the words for it, from the plan's `side` and `state`.
pub fn rung_word(r: &Value) -> (Standing, String) {
    let state = s(r, "state");
    let (head, rest) = state.split_once(": ").unwrap_or((state, ""));
    let why = |word: &str| if rest.is_empty() { word.to_string() } else { format!("{}: {}", word, rest) };
    if s(r, "side") == "add" {
        return (Standing::Taken, match head {
            "open" => "taken; it can be given back".to_string(),
            "wait" => why("taken; given back after a wait"),
            "after" => why("taken; given back after"),
            _ => format!("taken; not given back here: {}", state),
        });
    }
    match head {
        "open" => (Standing::Available, "available".to_string()),
        "wait" => (Standing::Waits, why("waits")),
        "after" => (Standing::Waits, why("after another rung")),
        "not allowed" => (Standing::No, state.to_string()),
        _ => (Standing::No, format!("not allowed: {}", state)),
    }
}

/// A rung in two or three words, by its kind: the plan's own sentence is in its account.
pub fn rung_name(r: &Value) -> &'static str {
    match (s(r, "kind"), s(r, "id").rsplit(':').next().unwrap_or("")) {
        ("cpu", _) | ("resume", "cpu") => "pause CPU lanes",
        ("card", _) | ("resume", "card") => "pause card's lane",
        ("off", _) | ("wake", _) => "power off",
        _ => "",
    }
}

/// The law's terms as the plan gives them, in one line of numbers.
pub fn terms_line(plan: &Value) -> String {
    let term = |k: &str| plan.get("terms").and_then(|z| n(z, k)).unwrap_or(0.0);
    let (ff, raw, wanted) = (n(plan, "feedforward_w").unwrap_or(0.0), n(plan, "unclamped_w").unwrap_or(0.0), n(plan, "wanted_w").unwrap_or(0.0));
    let mut out = format!(
        "the law: feedforward {:.0} + bias {:.0} + proportional {:+.0} + integral {:+.0} + derivative {:+.0} = {:.0} W",
        ff,
        term("bias_w"),
        term("p_w"),
        term("i_w"),
        term("d_w"),
        raw
    );
    match s(plan, "clamped") {
        "" => {}
        at => out.push_str(&format!(", held {}: {:.0} W", at, wanted)),
    }
    if plan.get("integral_held").and_then(|b| b.as_bool()).unwrap_or(false) {
        out.push_str("; the integral stands");
    }
    out
}

/// The regulation in one line, for the Queue's Fleet page: the mode, the room against its target,
/// the watts now against the watts wanted.
pub fn fleet_line(h: &Hearth) -> String {
    let mode = h.mode();
    let target = h.target().map(|c| format!("target {:.1} C", c)).unwrap_or("no target set".to_string());
    if mode == "off" {
        return format!("Regulate temperature OFF: nothing is read or planned ({}).", target);
    }
    let plan = h.plan.as_ref();
    let room = match plan.and_then(|p| n(p, "temp_c")) {
        Some(c) => format!("room {:.1} C", c),
        None => "room not read".to_string(),
    };
    let watts = match plan.and_then(|p| Some((n(p, "now_w")?, n(p, "wanted_w")?))) {
        Some((now, wanted)) => format!("{:.0} W now, {:.0} W wanted", now, wanted),
        None => match plan.map(|p| s(p, "stopped")).filter(|w| !w.is_empty()) {
            Some(why) => format!("nothing planned: {}", why),
            None => "no plan yet".to_string(),
        },
    };
    let tail = match (mode, h.held()) {
        ("act", 0) => "Lanes are paused and resumed to hold it.".to_string(),
        ("act", k) => format!("Lanes are paused and resumed; {} held now.", k),
        (_, 0) => "Nothing is changed.".to_string(),
        (_, k) => format!("Nothing is changed; {} still held from act.", k),
    };
    format!("Regulate temperature {}: {}, {}; {}. {}", mode.to_uppercase(), room, target, watts, tail)
}

/// What came of a button: the words, and whether it was done. hearth.py answers a target with "the
/// target is", a mode with the mode's name and a colon, a pass with its account. ANYTHING ELSE IS
/// SHOWN AS NOT DONE, in its own words: a fleet-queue.py that does not know the verb answers with
/// its usage, whose last line says nothing of the hearth, and a button whose failure looks like
/// nothing is a button a person presses twice.
pub fn answer(asked: &str, said: &str) -> (String, bool) {
    if said.is_empty() || said == format!("{}...", asked) {
        return (format!("{}: asked, no answer yet", asked), true);
    }
    let verb = asked.split_whitespace().nth(1).unwrap_or("");
    let done = match verb {
        "target" => said.starts_with("the target is"),
        "mode" => ["off:", "advise:", "act:", "still held"].iter().any(|w| said.starts_with(w)),
        // A pass ends its account with what it did, or that it did nothing, or why nothing is planned.
        _ => !said.contains("stop-now") && !said.starts_with("hearth "),
    };
    if done {
        (format!("{}: {}", asked, said), true)
    } else {
        (format!("NOT DONE. `{}` was answered: \"{}\". If that is not the hearth's own refusal, fleet-queue.py does not know the verb: it is `hearth` in tools/fleet-verbs.py.", asked, said), false)
    }
}

fn epoch() -> f64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs_f64()).unwrap_or(0.0)
}

/// Lines of words, wrapped, down from y; returns the y after the last.
fn para(ui: &mut Ui, x: i32, y: i32, w: i32, text: &str, c: Rgb) -> i32 {
    let lh = F8X13.height as i32 + 2;
    let mut y = y;
    for l in crate::line::wrap(text, &F8X13, w) {
        ui.label_in(x, y, w, &l, &F8X13, c);
        y += lh;
    }
    y
}

/// The regulation's line and its switch on the Queue's Fleet page, in the manner of auto mode's on
/// the Candidates page: the state in words, one button at the right. FROM HERE IT GOES BETWEEN OFF
/// AND ADVISE ONLY. Act is set on Heat, Hearth, where what it does is spelled out; from act the
/// button here is the way back to advise. Absent where no queue is known or the controller has
/// never been run. Returns the height it took.
pub fn fleet_switch(ui: &mut Ui, at: Rect, operator: bool, ctl: &mut Option<String>) -> i32 {
    let t = ui.t;
    let Some(h) = hearth().filter(|h| h.plan.is_some() || h.state.is_some()) else { return 0 };
    let mode = h.mode();
    let bw = if operator { 190 } else { 0 };
    let c = match mode {
        "act" => t.warn,
        "off" => t.dim,
        _ => t.up,
    };
    ui.label_in(at.x, at.y + 4, at.w - bw - 10, &fleet_line(&h), &F8X13, c);
    let how = match mode {
        "act" => "Set on Heat, Hearth. Back to advise stops the changes; what is held stays held until act or a person gives it back.",
        "off" => "On is advise: it reads the room, says what it would do, and changes nothing. Act is set on Heat, Hearth, beside what it does.",
        _ => "Off and advise are switched here. Act is set on Heat, Hearth, beside what it does.",
    };
    ui.label_in(at.x, at.y + 6 + F8X13.height as i32, at.w - bw - 10, how, &F8X13, t.dim);
    let (label, verb) = match mode {
        "off" => ("Turn regulation on", "hearth mode advise"),
        "act" => ("Back to advise", "hearth mode advise"),
        _ => ("Turn regulation off", "hearth mode off"),
    };
    if operator && ui.button(rect(at.right() - bw, at.y + 4, bw, 24), label, true) {
        *ctl = Some(verb.to_string());
    }
    44
}

/// The Hearth: the target and the mode with their buttons, the room and its probes, the outside,
/// the watts now against the watts wanted, the ladder, the last action, the plan's own account.
fn hearth_panel(ui: &mut Ui, at: Rect, st: &mut St, operator: bool, said: &str, ctl: &mut Option<String>) {
    let t = ui.t;
    let lh = F8X13.height as i32 + 3;
    let Some(h) = hearth() else {
        ui.label_in(at.x, at.y, at.w, "No queue is known to this console, so there is no hearth to read: start it with --queue DIR.", &F8X13, t.dim);
        return;
    };
    let (mode, target, power) = (h.mode(), h.target(), h.power());
    let mut ask: Option<String> = None;
    let mut y = at.y;

    // The target, and its buttons: a half degree down, a half degree up, or a number typed.
    let mut x = ui.label(at.x, y + 5, "target", &F8X13, t.dim) + 10;
    let big = match target {
        Some(c) => format!("{:.1} C   {:.1} F", c, f_of(c)),
        None => "not set".to_string(),
    };
    x = ui.label(x, y + 1, &big, &crate::font::F10X20, t.ink) + 14;
    if operator {
        let from = target.unwrap_or(21.0);
        for (label, by) in [("- 0.5", -0.5), ("+ 0.5", 0.5)] {
            let r = rect(x, y, 62, 24);
            if ui.button(r, label, true) {
                ask = Some(format!("hearth target {:.1}", if target.is_some() { nudged(from, by) } else { from }));
            }
            x = r.right() + 4;
        }
        let fr = rect(x + 4, y, 200, 24);
        ui.field(fr, &st.typed, "degrees C, Return");
        if st.typed.feed(&ui.f) && !st.typed.text.trim().is_empty() {
            match typed_target(&st.typed.text) {
                Ok(c) => ask = Some(format!("hearth target {:.1}", c)),
                Err(why) => st.asked = Some(format!("!{}", why)),
            }
            st.typed.clear();
        }
        x = fr.right() + 22;
    }
    // The mode: three buttons, the one in force underlined. Act asks twice, and wears the alarm's
    // colour whether or not it is in force: it is the one that changes the fleet.
    x = ui.label(x, y + 5, "mode", &F8X13, t.dim) + 10;
    for name in ["off", "advise", "act"] {
        let on = mode == name;
        let label = if name == "act" && st.arm_act && !on { "Press again: act" } else { name };
        let r = rect(x, y + 1, F8X13.measure(label) as i32 + 22, 22);
        if name == "act" {
            ui.c.frame(r.x - 2, r.y - 2, r.w + 4, r.h + 4, t.alarm);
            if on {
                ui.c.frame(r.x - 3, r.y - 3, r.w + 6, r.h + 6, t.alarm);
            }
        }
        if on {
            ui.c.rect(r.x + 4, r.bottom(), r.w - 8, 2, if name == "act" { t.alarm } else { t.up });
        }
        if operator || on {
            if ui.button(r, label, operator && !on) {
                if name == "act" && !st.arm_act {
                    st.arm_act = true;
                } else {
                    ask = Some(format!("hearth mode {}", name));
                    st.arm_act = false;
                }
            }
            x = r.right() + 8;
        }
    }
    x += 10;
    if mode == "act" {
        let say = "ACT: THE FLEET IS BEING CHANGED";
        let w = F8X13.measure(say) as i32 + 12;
        ui.c.rect(x, y + 2, w, 20, t.alarm);
        ui.label(x + 6, y + 5, say, &F8X13, t.base);
        x += w + 12;
    }
    ui.label_in(x, y + 5, at.right() - x, &format!("power switch: {}", if power { "ON" } else { "off" }), &F8X13, if power { t.alarm } else { t.dim });
    y += 24 + 8;

    // What act does, in words, whatever the mode: read before the press, not after.
    let does = if power {
        "Act changes the fleet, one rung a pass and no two within 15 minutes: a machine's CPU lanes, then its card's lane, take nothing new (the job in hand finishes), and are resumed when the room is cold. THE POWER SWITCH IS ON: with every lane of a machine held and nothing in hand, act also powers it off, and wakes it by a packet when the room is cold. The switch is set from the command line (tools/hearth.py QUEUE set power off) and has no button here."
    } else {
        "Act changes the fleet, one rung a pass and no two within 15 minutes: a machine's CPU lanes, then its card's lane, take nothing new (the job in hand finishes), and are resumed when the room is cold. It does NOT power a machine off and does NOT wake one: the power switch is off. That switch is set from the command line (tools/hearth.py QUEUE set power on) and has no button here. Off and advise change nothing; what act holds stays held through them."
    };
    y = para(ui, at.x, y, at.w, does, if mode == "act" { t.warn } else { t.dim }) + 2;

    // What the last button came to. A failure stays on the panel until the next press.
    if let Some(asked) = &st.asked {
        let (line, ok) = match asked.strip_prefix('!') {
            Some(why) => (format!("NOT ASKED: {}", why), false),
            None => answer(asked, said),
        };
        y = para(ui, at.x, y, at.w, &line, if ok { t.ink } else { t.alarm }) + 2;
    }
    if let Some(verb) = ask {
        st.asked = Some(verb.clone());
        *ctl = Some(verb);
    }

    let Some(plan) = h.plan.as_ref() else {
        let how = if mode == "off" {
            "No plan: the mode is off, and off reads nothing and writes nothing. In advise a pass (`python3 tools/hearth.py QUEUE step`) writes hearth/plan.json and changes nothing."
        } else {
            "No plan yet. `python3 tools/hearth.py QUEUE target 21.0` sets a target and `python3 tools/hearth.py QUEUE step` makes one pass, which writes hearth/plan.json; in advise it changes nothing. docs/hearth-controller.md is the guide."
        };
        para(ui, at.x, y + 4, at.w, how, t.dim);
        return;
    };

    // The plan: when it was made, and a pass on request while a pass changes nothing.
    let age = (epoch() - n(plan, "t").unwrap_or(0.0)).max(0.0);
    let old = age > 900.0;
    let mut made = format!("The plan: made {} ({} ago) in {}", s(plan, "made").replace('T', " "), took(age), s(plan, "mode"));
    if let (Some(a), Some(b)) = (n(plan, "target_c"), target) {
        if (a - b).abs() > 0.04 {
            made.push_str(&format!(", for a target of {:.1} C: the target has changed since", a));
        }
    }
    if s(plan, "mode") != mode {
        made.push_str(&format!("; the mode is now {}", mode));
    }
    made.push_str(if old { ". Older than three passes: no pass is scheduled yet." } else { "." });
    let bw = if operator && mode == "advise" { 150 } else { 0 };
    ui.label_in(at.x, y + 4, at.w - bw - 10, &made, &F8X13, if old { t.warn } else { t.dim });
    if bw > 0 && ui.button(rect(at.right() - bw, y, bw, 22), "Plan again now", true) {
        st.asked = Some("hearth step".to_string());
        *ctl = Some("hearth step".to_string());
    }
    y += 22 + 6;

    // Every rung used and the room still cold: the plan's suggestion, across the panel, before all else.
    let short = plan.get("shortfall").filter(|z| !matches!(z, Value::Null)).map(|z| {
        let who: Vec<String> = arr(z, "would_cover").iter().map(|m| format!("{} (about {:.0} W at work, an estimate; {})", s(m, "machine"), n(m, "about_w").unwrap_or(0.0), s(m, "how"))).collect();
        let covers = z.get("covers").and_then(|b| b.as_bool()).unwrap_or(false);
        format!(
            "EVERY RUNG IS USED AND THE ROOM IS STILL COLD: the fleet is {:.0} W short of what the law asks. START ANOTHER COMPUTER: {}. Nothing is started from here.",
            n(z, "w").unwrap_or(0.0),
            if who.is_empty() { "no machine on the bench is known that would cover it".to_string() } else { format!("{} {}", who.join(" and "), if covers { "would cover it" } else { "would not cover it alone" }) }
        )
    });
    if let Some(w) = &short {
        let h = crate::line::wrap(w, &F8X13, at.w - 16).len() as i32 * (F8X13.height as i32 + 2) + 8;
        ui.c.frame(at.x, y, at.w, h, t.alarm);
        para(ui, at.x + 8, y + 4, at.w - 16, w, t.alarm);
        y += h + 8;
    }
    let mid = rect(at.x, y, at.w, at.bottom() - y);
    let left = rect(mid.x, mid.y, mid.w * 49 / 100, mid.h);
    let right = rect(left.right() + 18, mid.y, mid.right() - left.right() - 18, mid.h);

    // ---- the left: the room, the outside, the balance, the last action
    let mut ly = left.y;
    let stopped = s(plan, "stopped");
    let room = match (n(plan, "temp_c"), n(plan, "error_c")) {
        (Some(c), Some(e)) => format!("The room: {}, the mean of {} probe{}; {:.1} {} the target", both(c), arr(plan, "temp_from").len(), if arr(plan, "temp_from").len() == 1 { "" } else { "s" }, e.abs(), if e < 0.0 { "over" } else { "under" }),
        (Some(c), None) => format!("The room: {}, the mean of {} probes", both(c), arr(plan, "temp_from").len()),
        _ => "The room: no fresh probe, so there is no temperature to hold".to_string(),
    };
    ui.label_in(left.x, ly, left.w, &room, &F8X13, if n(plan, "temp_c").is_some() { t.ink } else { t.alarm });
    ly += lh + 2;
    let cols = [(205, false), (300, false), (180, false), (105, true), (100, true), (110, false)];
    cells(ui, rect(left.x + 4, ly, left.w - 4, lh), &cols, &["probe", "place", "on", "reads", "age", ""].map(String::from), t.dim);
    ly += lh;
    ui.hrule(left.x, ly - 2, left.w);
    let mut ps: Vec<&Value> = arr(plan, "probes").iter().collect();
    ps.sort_by_key(|p| s(p, "role") != "room");
    for p in ps.iter().take(8) {
        let word = probe_word(p);
        let fresh = word == "fresh";
        let used = arr(plan, "temp_from").iter().chain(arr(plan, "outside_from")).any(|k| k.as_str() == Some(s(p, "key")));
        let row = [
            s(p, "key").to_string(),
            if s(p, "place").is_empty() { "(no place named)".to_string() } else { s(p, "place").to_string() },
            if s(p, "machine").is_empty() { "weather.gov".to_string() } else { s(p, "machine").to_string() },
            n(p, "c").map(|c| format!("{:.1} C", c)).unwrap_or("-".to_string()),
            n(p, "age_s").map(took).unwrap_or("-".to_string()),
            word.to_string(),
        ];
        cells(ui, rect(left.x + 4, ly, left.w - 4, lh), &cols, &row, if fresh && used { t.ink } else { t.dim });
        let wx = left.x + 4 + cols[..5].iter().map(|c| c.0 * (left.w - 4) / 1000).sum::<i32>();
        ui.label(wx, ly, word, &F8X13, if fresh { t.up } else { t.warn });
        ly += lh;
        if !fresh && !s(p, "why").is_empty() {
            ly = para(ui, left.x + 24, ly, left.w - 24, s(p, "why"), t.warn) + 1;
        }
    }
    ly += 4;
    let outside = match n(plan, "outside_c") {
        Some(c) => {
            let from = arr(plan, "outside_from").first().and_then(|k| k.as_str()).unwrap_or("");
            let place = arr(plan, "probes").iter().find(|p| s(p, "key") == from).map(|p| s(p, "place")).filter(|w| !w.is_empty()).unwrap_or(from);
            format!("Outside: {}, {}, observed {} ago", both(c), place, took(n(plan, "outside_age_s").unwrap_or(0.0)))
        }
        None => "Outside: not known (no fresh outside probe; `hearth.py QUEUE outside` fetches the airport's)".to_string(),
    };
    ui.label_in(left.x, ly, left.w, &outside, &F8X13, if n(plan, "outside_c").is_some() { t.ink } else { t.warn });
    ly += lh;
    let ua = match (n(plan, "ua_w_per_c"), s(plan, "feedforward_why")) {
        (Some(ua), "") => format!("UA {:.0} W/C: the feedforward is in use, {:.0} W", ua, n(plan, "feedforward_w").unwrap_or(0.0)),
        (Some(ua), why) => format!("UA {:.0} W/C, and the feedforward is not in use: {}", ua, why),
        (None, _) => "UA unknown: no feedforward until it is set (tools/hearth.py QUEUE fit-ua, then set ua N).".to_string(),
    };
    ly = para(ui, left.x, ly, left.w, &ua, t.dim) + 8;

    // The balance: the watts now as a bar, the watts wanted as a mark on it, between the least the
    // ladder can shed to and the most it can give.
    if !stopped.is_empty() {
        ly = para(ui, left.x, ly, left.w, &format!("Nothing is planned and nothing is done: {}", stopped), t.alarm) + 6;
    } else if let (Some(now), Some(wanted)) = (n(plan, "now_w"), n(plan, "wanted_w")) {
        let diff = n(plan, "diff_w").unwrap_or(wanted - now);
        let head = format!("The balance: the fleet draws {:.0} W; {:.0} W wanted; {}", now, wanted, if diff.abs() < 1.0 { "nothing to change".to_string() } else { format!("{:.0} W to {}", diff.abs(), if diff < 0.0 { "shed" } else { "add" }) });
        ui.label_in(left.x, ly, left.w, &head, &F8X13, t.ink);
        ly += lh + 2;
        let (lo, hi) = (n(plan, "floor_w").unwrap_or(0.0), n(plan, "max_w").unwrap_or(now));
        let top = now.max(wanted).max(hi).max(1.0) * 1.12;
        let bar = rect(left.x, ly, left.w - 70, 18);
        ui.well(bar);
        let px = |w: f64| bar.x + 2 + ((w / top).clamp(0.0, 1.0) * (bar.w - 4) as f64).round() as i32;
        ui.c.rect(bar.x + 2, bar.y + 2, px(now) - bar.x - 2, bar.h - 4, t.up);
        // What the ladder can reach, ruled under the bar; the watts wanted, a mark through it.
        ui.c.rect(px(lo), bar.bottom() + 2, (px(hi) - px(lo)).max(1), 2, t.dim);
        ui.c.rect(px(wanted) - 1, bar.y - 3, 3, bar.h + 6, t.ink);
        ui.label(bar.right() + 4, bar.y + 3, &format!("{:.0} W", top), &F6X10, t.dim);
        ly += bar.h + 6;
        let key = format!("green: now. The mark: wanted. Ruled under: what the ladder reaches, {:.0} to {:.0} W.", lo, hi);
        ly = para(ui, left.x, ly, left.w, &key, t.dim);
        ly = para(ui, left.x, ly, left.w, &terms_line(plan), t.ink);
        let pend = arr(plan, "pending");
        if !pend.is_empty() {
            let each: Vec<String> = pend.iter().map(|p| format!("{} {:+.0} W ({})", s(p, "rung"), n(p, "w").unwrap_or(0.0), s(p, "why"))).collect();
            ly = para(ui, left.x, ly, left.w, &format!("on its way and counted: {}; expected {:.0} W", each.join("; "), n(plan, "expected_w").unwrap_or(now)), t.dim);
        }
        ly += 6;
    }
    // What this pass would take, and the last thing done.
    let would = plan.get("would").filter(|w| !matches!(w, Value::Null));
    let next = match would {
        Some(w) => {
            let cmds: Vec<&str> = arr(w, "cmds").iter().filter_map(|c| c.as_str()).collect();
            format!("The next pass would take: {}, about {:.0} W ({}){}", s(w, "what"), n(w, "watts").unwrap_or(0.0), cmds.join("; then "), if mode == "act" { "" } else { ". Not in this mode: nothing is done" })
        }
        None if stopped.is_empty() => format!("The next pass would take no rung: {}", s(plan, "why_not")),
        None => String::new(),
    };
    let room_for = |text: &str, ly: i32| ly + crate::line::wrap(text, &F8X13, left.w).len() as i32 * (F8X13.height as i32 + 2) <= left.bottom();
    if !next.is_empty() && room_for(&next, ly) {
        ly = para(ui, left.x, ly, left.w, &next, if would.is_some() { t.accent } else { t.dim });
    }
    let last = match h.state.as_ref().and_then(|v| v.get("last_action")).filter(|a| !matches!(a, Value::Null)) {
        Some(a) => format!("The last action: {}, {} ago ({}){}", s(a, "what"), took((epoch() - n(a, "t").unwrap_or(0.0)).max(0.0)), s(a, "at").replace('T', " "), if a.get("ok").and_then(|b| b.as_bool()).unwrap_or(true) { "" } else { ", which FAILED" }),
        None => "The last action: none, ever. This controller has not changed a machine.".to_string(),
    };
    if room_for(&last, ly) {
        ly = para(ui, left.x, ly, left.w, &last, t.dim);
    }
    // The plan's own account, as hearth.py wrote it, for as many lines as the column has left.
    ly += 6;
    let account: Vec<(i32, String)> = arr(plan, "said")
        .iter()
        .filter_map(|l| l.as_str())
        .flat_map(|l| {
            let dent = if l.starts_with(' ') { 24 } else { 0 };
            crate::line::wrap(l.trim_start(), &F8X13, left.w - dent - 12).into_iter().map(move |w| (dent, w))
        })
        .collect();
    let fit = ((left.bottom() - ly) / lh - 1).max(0) as usize;
    if fit > 0 && !account.is_empty() {
        ui.hrule(left.x, ly - 3, left.w);
        ui.label_in(left.x, ly, left.w, "the plan's own account:", &F8X13, t.dim);
        ly += lh;
        let cut = account.len() > fit;
        for (i, (dent, l)) in account.iter().take(fit).enumerate() {
            if cut && i + 1 == fit {
                ui.label_in(left.x + 12, ly, left.w - 12, &format!("... {} more lines: tools/hearth.py QUEUE status says it all", account.len() + 1 - fit), &F8X13, t.dim);
                break;
            }
            ui.label_in(left.x + 12 + dent, ly, left.w - 12 - dent, l, &F8X13, if *dent > 0 { t.accent } else { t.ink });
            ly += lh;
        }
    }

    // ---- the right: the ladder, every rung in the plan's order, and the shortfall under it
    let rungs = arr(plan, "ladder");
    let taken = rungs.iter().filter(|r| s(r, "side") == "add").count();
    ui.label_in(right.x, right.y, right.w, &format!("The ladder, least drastic first: {} rungs to shed, {} taken and held", rungs.len() - taken, taken), &F8X13, t.ink);
    let hy = right.y + lh + 2;
    let rcols = [(30, false), (170, false), (255, false), (90, true), (455, false)];
    cells(ui, rect(right.x + 4, hy, right.w - 22, lh), &rcols, &["", "machine", "the rung", "watts", "where it stands, and why"].map(String::from), t.dim);
    ui.hrule(right.x, hy + lh - 2, right.w);
    // A line a rung, and under it, where the plan gives one, the reason in full: a reason cut short
    // at the column's edge is a reason not given. The list scrolls by lines.
    let rl = F8X13.height as i32 + 2;
    let next_id = would.map(|w| (s(w, "rung"), s(w, "side")));
    let mut lines: Vec<(usize, Option<String>)> = Vec::new();
    let state_w = rcols[4].0 * (right.w - 30) / 1000 - 8;
    let two = |r: &Value| F8X13.measure(&rung_word(r).1) as i32 > state_w || next_id == Some((s(r, "id"), s(r, "side")));
    for (i, r) in rungs.iter().enumerate() {
        lines.push((i, None));
        if let Some((_, why)) = rung_word(r).1.split_once(": ").filter(|_| two(r)) {
            lines.push((i, Some(why.to_string())));
        }
    }
    let list = rect(right.x, hy + lh, right.w, (right.bottom() - hy - lh).max(3 * rl));
    let (area, first, fit) = ui.scroll_list(list, lines.len(), rl, &mut st.off[HEARTH]);
    for (k, (i, why)) in lines.iter().skip(first).take(fit).enumerate() {
        let r = &rungs[*i];
        let row = rect(area.x + 4, area.y + k as i32 * rl, area.w - 8, rl);
        let (standing, word) = rung_word(r);
        let is_next = next_id == Some((s(r, "id"), s(r, "side")));
        let c = match standing {
            Standing::Taken => t.warn,
            Standing::Available => t.ink,
            _ => t.dim,
        };
        if is_next {
            ui.c.rect(row.x - 4, row.y, 2, row.h, t.accent);
        }
        if let Some(why) = why {
            ui.label_in(row.x + rcols[0].0 * row.w / 1000 + 16, row.y, row.w - rcols[0].0 * row.w / 1000 - 16, why, &F8X13, if standing == Standing::Taken { t.warn } else { t.dim });
            continue;
        }
        match standing {
            Standing::Taken => ui.c.rect(row.x + 4, row.y + 3, 8, 8, t.warn),
            Standing::Available => ui.c.rect(row.x + 4, row.y + 3, 8, 8, t.up),
            Standing::Waits => ui.c.frame(row.x + 4, row.y + 3, 8, 8, t.dim),
            Standing::No => {}
        }
        let head = if two(r) { word.split_once(": ").map(|(h, _)| h.to_string()).unwrap_or(word) } else { word };
        let text = [
            String::new(),
            s(r, "machine").to_string(),
            rung_name(r).to_string(),
            n(r, "watts").map(|w| format!("{:.0} W", w)).unwrap_or("?".to_string()),
            if is_next { format!("{}: the next to be taken", head) } else { head },
        ];
        cells(ui, row, &rcols, &text, if is_next { t.accent } else { c });
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
    const PLAN: &str = r#"{"t": 1794879438.9, "made": "2026-11-16T17:37:18", "mode": "advise", "target_c": 21.0, "stopped": "",
      "temp_c": 26.4, "temp_from": ["room.rad7F7E.c", "room.radC2EA.c"], "error_c": -5.4, "outside_c": 9.0, "outside_age_s": 2239,
      "ua_w_per_c": null, "feedforward_w": 0, "feedforward_why": "UA is unknown", "unclamped_w": -826, "floor_w": 258, "max_w": 704,
      "wanted_w": 258, "clamped": "at the least it can shed to", "integral_held": true, "now_w": 704, "diff_w": -446,
      "terms": {"bias_w": 704, "p_w": -1530, "i_w": 0.0, "d_w": 0.0},
      "probes": [{"key": "room.rad7F7E.c", "role": "room", "ok": true, "why": ""},
                 {"key": "room.radC2EA.c", "role": "room", "ok": false, "why": "suspect: it jumped +5.0 in 5 min (from 21.0), more than 3 degrees in five minutes"},
                 {"key": "outside.ksea.c", "role": "outside", "ok": false, "why": "stale: observed 3.0 h ago"},
                 {"key": "room.x.c", "role": "room", "ok": false, "why": "85.0 is what a counter says when its thermometer has no reading"},
                 {"key": "room.y.c", "role": "room", "ok": false, "why": "missing: calber has no telemetry"}],
      "ladder": [{"id": "mac:cpu", "side": "shed", "state": "keep: this Mac runs the keeper"},
                 {"id": "columbia:cpu", "side": "shed", "state": "open"},
                 {"id": "calber:card", "side": "shed", "state": "wait: its CPU lanes go first"},
                 {"id": "calber:off", "side": "shed", "state": "not allowed: power is off (`set power on`)"},
                 {"id": "boburner:cpu", "side": "add", "kind": "resume", "state": "open"},
                 {"id": "whitewolf:cpu", "side": "add", "state": "wait: changed 5 min ago, 25 min of its dwell left"}]}"#;

    fn hearth_of(plan: Option<&str>, state: Option<&str>) -> Hearth {
        Hearth { plan: plan.map(|p| json::parse(p).unwrap()), state: state.map(|p| json::parse(p).unwrap()) }
    }

    #[test]
    fn a_target_is_said_in_both_scales_and_moved_by_halves() {
        assert_eq!(both(21.0), "21.0 C (69.8 F)");
        assert_eq!(both(-40.0), "-40.0 C (-40.0 F)");
        assert_eq!(nudged(21.0, 0.5), 21.5);
        assert_eq!(nudged(21.3, -0.5), 20.8);
        // hearth.py accepts 5 to 35, and a button does not ask for what it would refuse.
        assert_eq!(nudged(35.0, 0.5), 35.0);
        assert_eq!(nudged(5.0, -0.5), 5.0);
    }

    #[test]
    fn a_typed_target_is_degrees_c_or_f_and_a_slip_is_refused() {
        assert_eq!(typed_target("21.5"), Ok(21.5));
        assert_eq!(typed_target(" 21 C "), Ok(21.0));
        assert_eq!(typed_target("70F"), Ok(21.1));
        assert_eq!(typed_target("70 f"), Ok(21.1));
        // 70 alone is taken for Celsius, as hearth.py takes it, and refused.
        assert!(typed_target("70").unwrap_err().contains("between 5 and 35"));
        assert!(typed_target("warm").unwrap_err().contains("not a number"));
        assert!(typed_target("").is_err());
        assert!(typed_target("F").is_err());
    }

    #[test]
    fn the_state_says_the_mode_and_target_before_the_plan_does() {
        // A button changes state.json at once; the plan is as old as the last pass.
        let h = hearth_of(Some(PLAN), Some(r#"{"mode": "act", "target_c": 22.5, "set": {"power": "on"}, "held": {"calber": {"cpu": {"t": 1, "w": 60}, "card": {"t": 2, "w": 50}}, "boburner": {"cpu": {"t": 3, "w": 80}}}}"#));
        assert_eq!((h.mode(), h.target(), h.power(), h.held()), ("act", Some(22.5), true, 3));
        let h = hearth_of(Some(PLAN), None);
        assert_eq!((h.mode(), h.target(), h.power(), h.held()), ("advise", Some(21.0), false, 0));
        // Nothing on disk: hearth.py's own default, and no target.
        let h = hearth_of(None, None);
        assert_eq!((h.mode(), h.target(), h.power()), ("advise", None, false));
        // Power is off unless the state says on in so many words.
        assert!(!hearth_of(None, Some(r#"{"mode": "act", "target_c": null, "set": {"power": "off"}}"#)).power());
    }

    #[test]
    fn a_probe_is_fresh_or_says_why_not_in_a_word() {
        let plan = json::parse(PLAN).unwrap();
        let words: Vec<&str> = arr(&plan, "probes").iter().map(probe_word).collect();
        assert_eq!(words, ["fresh", "suspect", "stale", "no reading", "missing"]);
    }

    #[test]
    fn a_rung_is_taken_available_waiting_or_not_allowed_and_says_why() {
        let plan = json::parse(PLAN).unwrap();
        let got: Vec<(Standing, String)> = arr(&plan, "ladder").iter().map(rung_word).collect();
        assert_eq!(got[0], (Standing::No, "not allowed: keep: this Mac runs the keeper".to_string()));
        assert_eq!(got[1], (Standing::Available, "available".to_string()));
        assert_eq!(got[2], (Standing::Waits, "waits: its CPU lanes go first".to_string()));
        assert_eq!(got[3], (Standing::No, "not allowed: power is off (`set power on`)".to_string()));
        assert_eq!(got[4], (Standing::Taken, "taken; it can be given back".to_string()));
        assert_eq!(got[5].0, Standing::Taken);
        assert!(got[5].1.contains("25 min of its dwell left"));
        assert_eq!(rung_name(&arr(&plan, "ladder")[4]), "pause CPU lanes");
        assert_eq!(rung_name(&json::parse(r#"{"id": "calber:off", "kind": "wake"}"#).unwrap()), "power off");
        assert_eq!(rung_name(&json::parse(r#"{"id": "calber:card", "kind": "card"}"#).unwrap()), "pause card's lane");
    }

    #[test]
    fn the_law_is_a_line_of_its_terms_and_says_where_it_is_held() {
        let plan = json::parse(PLAN).unwrap();
        assert_eq!(
            terms_line(&plan),
            "the law: feedforward 0 + bias 704 + proportional -1530 + integral +0 + derivative +0 = -826 W, held at the least it can shed to: 258 W; the integral stands"
        );
        let free = json::parse(r#"{"feedforward_w": 960, "unclamped_w": 1105, "wanted_w": 1105, "clamped": "", "integral_held": false, "terms": {"bias_w": 100, "p_w": 30, "i_w": 15.4, "d_w": 0}}"#).unwrap();
        assert_eq!(terms_line(&free), "the law: feedforward 960 + bias 100 + proportional +30 + integral +15 + derivative +0 = 1105 W");
    }

    #[test]
    fn the_fleet_page_has_the_regulation_in_one_line() {
        let h = hearth_of(Some(PLAN), Some(r#"{"mode": "advise", "target_c": 21.0, "set": {}, "held": {}}"#));
        assert_eq!(fleet_line(&h), "Regulate temperature ADVISE: room 26.4 C, target 21.0 C; 704 W now, 258 W wanted. Nothing is changed.");
        let h = hearth_of(Some(PLAN), Some(r#"{"mode": "off", "target_c": 21.0}"#));
        assert_eq!(fleet_line(&h), "Regulate temperature OFF: nothing is read or planned (target 21.0 C).");
        let h = hearth_of(Some(PLAN), Some(r#"{"mode": "act", "target_c": 21.0, "held": {"calber": {"cpu": {"t": 1, "w": 60}}}}"#));
        assert!(fleet_line(&h).starts_with("Regulate temperature ACT: room 26.4 C") && fleet_line(&h).ends_with("1 held now."));
        // A plan that stopped says why in place of the watts; no plan says so.
        let h = hearth_of(Some(r#"{"mode": "advise", "target_c": 21.0, "temp_c": null, "now_w": null, "wanted_w": null, "stopped": "no fresh room probe: none is known"}"#), None);
        assert!(fleet_line(&h).contains("room not read") && fleet_line(&h).contains("nothing planned: no fresh room probe"));
        assert!(fleet_line(&hearth_of(None, Some(r#"{"mode": "advise", "target_c": null}"#))).contains("no target set; no plan yet"));
    }

    #[test]
    fn a_button_that_failed_says_so_in_the_answer_it_got() {
        assert_eq!(answer("hearth target 21.5", "the target is 21.5 C (70.7 F)"), ("hearth target 21.5: the target is 21.5 C (70.7 F)".to_string(), true));
        assert!(answer("hearth mode advise", "advise: step computes and says, and changes nothing").1);
        assert!(answer("hearth mode off", "still held from before, and given back only by act or by hand: calber (cpu)").1);
        assert!(answer("hearth step", "advise: nothing was done").1);
        // While it runs, main puts the verb and three dots where the answer will be.
        assert!(answer("hearth mode act", "hearth mode act...").0.contains("no answer yet"));
        // A fleet-queue.py that does not know the verb answers with its usage; its last line is this one.
        let (line, ok) = answer("hearth mode advise", "so `stop-now` can stop all of it.");
        assert!(!ok && line.starts_with("NOT DONE") && line.contains("stop-now") && line.contains("fleet-verbs.py"));
        // hearth.py's own refusal, and the verb's.
        assert!(!answer("hearth target 50.0", "a target is between 5 and 35 C; 50.0 was taken for a slip").1);
        assert!(!answer("hearth step", "hearth target C | mode off|advise|act | step | status: the Heat page's buttons, and no other").1);
    }
}
