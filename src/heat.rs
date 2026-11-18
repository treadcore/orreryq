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
    sort: [usize; 6],
    open: Option<String>,
    pick: Option<String>,
    off: [usize; 6],
    /// The Hearth: a target being typed, act pressed once, and the last thing its buttons asked.
    typed: Field,
    arm_act: bool,
    /// The machine whose Off was pressed once.
    arm_off: Option<String>,
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
        st.panel = it.next().and_then(|p| if p == "hearth" { Some(HEARTH) } else if p == "diagram" { Some(DIAGRAM) } else { p.parse().ok() }).unwrap_or(0);
        st.arm_act = std::env::var("ORRERY_HEAT_ARM").is_ok();
        st.open = it.next().filter(|m| !m.is_empty()).map(String::from);
    }
    st
}

const PANELS: [&str; 6] = ["Machines", "Parts", "Watts", "Steps", "Hearth", "Diagram"];
/// The Hearth's number, and the row as it is drawn: the Hearth first, because it is the one panel
/// that is set and not only read; the other four keep the numbers a picture was asked by.
const HEARTH: usize = 4;
/// The heat's flow as one picture: the weather, the apartment's two zones, every machine, the walls,
/// the thermal mass and the thermometers (18 November).
const DIAGRAM: usize = 5;
const ORDER: [usize; 6] = [HEARTH, DIAGRAM, 0, 1, 2, 3];
const SORTS: [&[&str]; 6] = [
    &["name", "nearest its limit", "watts", "CPU's tau", "slowest part"],
    &["hottest", "widest swing", "slowest to follow", "machine"],
    &["watts", "share of its limit", "name"],
    &["newest", "longest tau", "machine"],
    &[],
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
    let mut chip = ORDER.iter().position(|i| *i == st.panel.min(DIAGRAM)).unwrap_or(1);
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
        st.arm_off = None;
    }
    match (p, doc) {
        (HEARTH, _) => hearth_panel(ui, body, &mut st, operator, said, ctl),
        (DIAGRAM, _) => diagram(ui, body, doc),
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
    // Where the hold is the law the watts wanted are its budget, an energy calculation and not gains.
    if let Some(b) = plan.get("budget").filter(|b| !matches!(b, Value::Null)) {
        return format!(
            "the hold's budget: -(UA {:.0} W/C x the error + C {:.1} MJ/C x {:+.2} C an hour) = {:+.0} W",
            n(b, "ua_w_c").unwrap_or(0.0),
            n(b, "c_mj_c").unwrap_or(0.0),
            n(b, "slope_c_h").unwrap_or(0.0),
            n(b, "w").unwrap_or(0.0)
        );
    }
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

// ---- the diagram: the heat's flow as one picture ------------------------------------------------
// Paul, 18 November: "draw a model of the heat flow in orrery. in a new diagram heat tab. In it we have
// two zones inside the weather. Draw a thermo heat flow process diagram like 3blue1brown. Show the
// time constant of each computer case and their HDs and sensors, collect them together, show
// graphically like a SCADA-like display of Heat in, Heat flow through walls, Heat soak in thermal mass
// (it's an apartment). These numbers dynamically update. Also show thermometers on screen prominently."
//
// One balance, the same one tools/hearth_regulator.py works its budget from:
//     C dT/dt = P + P0 - UA (T - To)
// P is read (the fleet's watts), T and To are read (the probes, the airport), dT/dt is the last
// hour's slope. C was measured by a step; UA is a figure in use and NOT a measurement, and is said to
// be so on the picture. P0, the heat that is not the fleet's, is what is left over: it is drawn as
// implied, never as read. Zone 2, the rest of the apartment, has no thermometer and says so.

const SKY: Rgb = 0x58c4dd;
const SUN: Rgb = 0xf7d96f;
const LEAF: Rgb = 0x83c167;
const EMBER: Rgb = 0xff8c5a;
const ROSE: Rgb = 0xfc6255;
const DUSK: Rgb = 0xb9a6e8;

/// The four flows of the balance, in watts, from a plan; None where the plan cannot give them.
#[derive(Debug, PartialEq)]
pub struct Flows {
    pub fleet_w: f64,
    pub walls_w: f64,
    pub soak_w: f64,
    pub other_w: f64,
    pub over_c: f64,
}

pub fn flows(plan: &Value) -> Option<Flows> {
    let b = plan.get("budget").filter(|b| !matches!(b, Value::Null))?;
    let (room, out, fleet) = (n(b, "room_c").or(n(plan, "temp_c"))?, n(plan, "outside_c")?, n(plan, "now_w")?);
    let walls = n(b, "ua_w_c")? * (room - out);
    let soak = n(b, "c_mj_c")? * 1e6 * n(b, "slope_c_h")? / 3600.0;
    Some(Flows { fleet_w: fleet, walls_w: walls, soak_w: soak, other_w: walls + soak - fleet, over_c: room - out })
}

/// A machine's line of the diagram: its watts, its CPU and its time constant, its drives and theirs.
struct Box7 {
    name: String,
    on: bool,
    wall_w: f64,
    cpu_c: Option<f64>,
    cpu_tau_s: Option<f64>,
    card_c: Option<f64>,
    drives: usize,
    drive_c: Option<f64>,
    drive_lag_s: Option<f64>,
    sensors: usize,
}

fn boxes_of(doc: &Value) -> Vec<Box7> {
    let mut out: Vec<Box7> = arr(doc, "machines")
        .iter()
        .map(|m| {
            let mut taus: Vec<f64> = arr(m, "steps").iter().filter_map(|x| n(x, "tau_s")).collect();
            taus.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
            let drives: Vec<f64> = arr(m, "parts").iter().filter(|p| matches!(s(p, "kind"), "disk" | "nvme")).filter_map(|p| n(p, "now")).collect();
            Box7 {
                name: s(m, "name").to_string(),
                on: n(m, "age_s").map(|a| a < 900.0).unwrap_or(false) && n(m, "wall_w").is_some(),
                wall_w: n(m, "wall_w").unwrap_or(0.0),
                cpu_c: n(m, "cpu_c"),
                cpu_tau_s: taus.get(taus.len() / 2).copied(),
                card_c: n(m, "gpu_c"),
                drives: drives.len(),
                drive_c: if drives.is_empty() { None } else { Some(drives.iter().sum::<f64>() / drives.len() as f64) },
                drive_lag_s: m.get("slow").and_then(|z| n(z, "tau_s")),
                sensors: arr(m, "channels").len(),
            }
        })
        .collect();
    out.sort_by(|a, b| b.on.cmp(&a.on).then(b.wall_w.partial_cmp(&a.wall_w).unwrap_or(std::cmp::Ordering::Equal)));
    out
}

/// How thick a flow of so many watts is drawn: a pixel for each 70 W, never less than 2 nor more than 26.
fn thick(w: f64) -> i32 {
    ((w.abs() / 70.0).round() as i32).clamp(2, 26)
}

fn minutes(sec: f64) -> String {
    if sec < 90.0 {
        format!("{:.0} s", sec)
    } else if sec < 5400.0 {
        format!("{:.0} min", sec / 60.0)
    } else {
        format!("{:.1} h", sec / 3600.0)
    }
}

/// Lettering k times its size: the page's fonts are bitmaps of one size, and on a wide screen a
/// diagram drawn at that size is a postage stamp in a field. Returns the x after the last letter.
fn tx(ui: &mut Ui, x: i32, y: i32, text: &str, font: &crate::font::Font, k: i32, c: Rgb) -> i32 {
    if k <= 1 {
        return ui.c.text(x, y, text, font, c);
    }
    let mut at = x;
    for ch in text.chars() {
        if ch != ' ' {
            for (dy, bits) in font.glyph(ch).iter().enumerate() {
                for dx in 0..font.width {
                    if (bits >> dx) & 1 == 1 {
                        ui.c.rect(at + dx as i32 * k, y + dy as i32 * k, k, k, c);
                    }
                }
            }
        }
        at += font.width as i32 * k;
    }
    at
}

/// The same, cut to a width with two dots where it had to be.
fn tx_in(ui: &mut Ui, x: i32, y: i32, max_w: i32, text: &str, font: &crate::font::Font, k: i32, c: Rgb) -> i32 {
    let fit = (max_w / (font.width as i32 * k)).max(0) as usize;
    if text.chars().count() <= fit {
        return tx(ui, x, y, text, font, k, c);
    }
    let cut: String = text.chars().take(fit.saturating_sub(2)).collect();
    tx(ui, x, y, &format!("{}..", cut), font, k, c)
}

fn tx_w(text: &str, font: &crate::font::Font, k: i32) -> i32 {
    text.chars().count() as i32 * font.width as i32 * k
}

/// A pipe through its corners: a dark casing, the flow's colour inside, bright marks that walk along
/// it the way it flows, and a head at its end. Each leg runs along one axis.
fn pipe(ui: &mut Ui, pts: &[(i32, i32)], th: i32, c: Rgb) {
    let case = crate::draw::mix(c, 0x000000, 150);
    let lit = crate::draw::mix(c, 0xffffff, 110);
    let phase = ((epoch() * 40.0) as i64 % 28) as i32;
    let h = th / 2;
    for (i, w) in pts.windows(2).enumerate() {
        let ((x0, y0), (x1, y1)) = (w[0], w[1]);
        let last = i + 2 == pts.len();
        let head = if last { th + 8 } else { 0 };
        if y0 == y1 {
            let (a, b, dir) = if x1 >= x0 { (x0, x1, 1) } else { (x1, x0, -1) };
            let (bx, bw) = if dir > 0 { (a - if i > 0 { h } else { 0 }, b - a - head + if i > 0 { h } else { 0 }) } else { (a + head, b - a - head + if i > 0 { h } else { 0 }) };
            ui.c.rect(bx, y0 - h - 1, bw.max(0), th + 2, case);
            ui.c.rect(bx, y0 - h, bw.max(0), th, c);
            let mut k = phase;
            while k < bw - 5 {
                let x = if dir > 0 { bx + k } else { bx + bw - k - 5 };
                ui.c.rect(x, y0 - (h - 1).max(0), 5, (th - 2).max(1), lit);
                k += 28;
            }
            for j in 0..head {
                let half = (h + 6) * (head - j) / head.max(1);
                ui.c.vline(if dir > 0 { b - head + j } else { a + head - j }, y0 - half, 2 * half + 1, c);
            }
        } else {
            let (a, b, dir) = if y1 >= y0 { (y0, y1, 1) } else { (y1, y0, -1) };
            let (by, bh) = if dir > 0 { (a - if i > 0 { h } else { 0 }, b - a - head + if i > 0 { h } else { 0 }) } else { (a + head, b - a - head + if i > 0 { h } else { 0 }) };
            ui.c.rect(x0 - h - 1, by, th + 2, bh.max(0), case);
            ui.c.rect(x0 - h, by, th, bh.max(0), c);
            let mut k = phase;
            while k < bh - 5 {
                let y = if dir > 0 { by + k } else { by + bh - k - 5 };
                ui.c.rect(x0 - (h - 1).max(0), y, (th - 2).max(1), 5, lit);
                k += 28;
            }
            for j in 0..head {
                let half = (h + 6) * (head - j) / head.max(1);
                ui.c.hline(x0 - half, if dir > 0 { b - head + j } else { a + head - j }, 2 * half + 1, c);
            }
        }
    }
}

/// An instrument, as a process diagram draws one: a ring with its two letters (TI a temperature, JI a
/// power), and beside it what it reads. Dashed where nothing reads it.
fn bubble(ui: &mut Ui, cx: i32, cy: i32, k: i32, tag: &str, c: Rgb, read: bool) {
    let r = 11 * k;
    ui.c.disc(cx, cy, r, ui.t.base);
    ui.c.ring(cx, cy, r, c);
    if read {
        ui.c.ring(cx, cy, r - 1, c);
    }
    tx(ui, cx - tx_w(tag, &F6X10, k) / 2, cy - 5 * k, tag, &F6X10, k, c);
}

/// A frame of dashes: the edge of something that is there and is not measured.
fn dashed(ui: &mut Ui, r: Rect, c: Rgb) {
    let mut x = r.x;
    while x < r.right() {
        ui.c.hline(x, r.y, 8.min(r.right() - x), c);
        ui.c.hline(x, r.bottom() - 1, 8.min(r.right() - x), c);
        x += 14;
    }
    let mut y = r.y;
    while y < r.bottom() {
        ui.c.vline(r.x, y, 8.min(r.bottom() - y), c);
        ui.c.vline(r.right() - 1, y, 8.min(r.bottom() - y), c);
        y += 14;
    }
}

/// A wall, hatched: what the heat has to cross.
fn hatch(ui: &mut Ui, r: Rect, c: Rgb) {
    ui.c.rect(r.x, r.y, r.w, r.h, crate::draw::mix(ui.t.base, c, 60));
    let mut x = r.x - r.h;
    while x < r.right() {
        for d in 0..r.h {
            let px = x + d;
            if px >= r.x && px < r.right() {
                ui.c.set(px, r.bottom() - 1 - d, c);
            }
        }
        x += 7;
    }
    ui.c.frame(r.x, r.y, r.w, r.h, c);
}

/// A trend: a strip of a series, its lowest and highest said, and lines across it at values to hold.
#[allow(clippy::too_many_arguments)]
fn trend(ui: &mut Ui, r: Rect, k: i32, title: &str, ys: &[f64], unit: &str, c: Rgb, lines: &[(f64, Rgb)]) {
    let t = ui.t;
    ui.c.frame(r.x, r.y, r.w, r.h, t.line);
    tx_in(ui, r.x + 5 * k, r.y + 4 * k, r.w - 10 * k, title, &F6X10, k, t.dim);
    if ys.len() < 3 {
        tx_in(ui, r.x + 5 * k, r.y + r.h / 2, r.w - 10 * k, "no record yet", &F6X10, k, t.dim);
        return;
    }
    let (mut lo, mut hi) = ys.iter().fold((f64::MAX, f64::MIN), |(a, b), v| (a.min(*v), b.max(*v)));
    for (v, _) in lines {
        lo = lo.min(*v);
        hi = hi.max(*v);
    }
    let pad = ((hi - lo) * 0.1).max(1e-6);
    let (lo, hi) = (lo - pad, hi + pad);
    let plot = rect(r.x + 4 * k, r.y + 17 * k, r.w - 8 * k, r.h - 32 * k);
    let yof = |v: f64| plot.bottom() - (((v - lo) / (hi - lo)) * plot.h as f64).round() as i32;
    for (v, lc) in lines {
        let mut x = plot.x;
        while x < plot.right() {
            ui.c.hline(x, yof(*v), 4, *lc);
            x += 9;
        }
    }
    let mut prev: Option<(i32, i32)> = None;
    for (i, v) in ys.iter().enumerate() {
        let p = (plot.x + (i as i32 * (plot.w - 1)) / (ys.len() as i32 - 1), yof(*v));
        if let Some(q) = prev {
            seg(ui, q, p, c);
            if k > 1 {
                seg(ui, (q.0, q.1 + 1), (p.0, p.1 + 1), c);
            }
        }
        prev = Some(p);
    }
    if let Some(p) = prev {
        ui.c.disc(p.0, p.1, 2 * k, c);
    }
    let (a, b) = (ys.iter().cloned().fold(f64::MAX, f64::min), ys.iter().cloned().fold(f64::MIN, f64::max));
    tx_in(ui, r.x + 5 * k, r.bottom() - 13 * k, r.w - 10 * k, &if b - a < 20.0 { format!("{:.1}-{:.1} now {:.1} {}", a, b, ys[ys.len() - 1], unit) } else { format!("{:.0}-{:.0} now {:.0} {}", a, b, ys[ys.len() - 1], unit) }, &F6X10, k, t.ink);
}

/// A thermometer: a glass, its mercury, a scale in Fahrenheit, marks, and the reading large under it.
#[allow(clippy::too_many_arguments)]
fn thermometer(ui: &mut Ui, x: i32, top: i32, h: i32, k: i32, name: &str, c: Option<f64>, col: Rgb, lo_f: f64, hi_f: f64, marks: &[(f64, &str, Rgb)]) {
    let t = ui.t;
    let (gx, gw) = (x + 30 * k, 20 * k);
    let yof = |f: f64| top + h - (((f - lo_f) / (hi_f - lo_f)).clamp(0.0, 1.0) * h as f64).round() as i32;
    tx(ui, x, top - 26 * k, name, &F8X13, k, t.ink);
    let mut f = lo_f;
    while f <= hi_f + 0.01 {
        let ten = (f as i32) % 10 == 0;
        ui.c.rect(gx - if ten { 9 * k } else { 5 * k }, yof(f), if ten { 8 * k } else { 4 * k }, k, t.dim);
        if ten {
            let word = format!("{:.0}", f);
            tx(ui, gx - 11 * k - tx_w(&word, &F6X10, k), yof(f) - 5 * k, &word, &F6X10, k, t.dim);
        }
        f += 5.0;
    }
    for i in 0..k {
        ui.c.frame(gx - i, top - 6 * k - i, gw + 2 * i, h + 12 * k + 2 * i, t.dim);
    }
    let by = top + h + 6 * k + 15 * k;
    ui.c.disc(gx + gw / 2, by, 17 * k, t.dim);
    ui.c.disc(gx + gw / 2, by, 15 * k, col);
    if let Some(c) = c {
        let y = yof(f_of(c));
        ui.c.rect(gx + 3 * k, y, gw - 6 * k, by - y, col);
        ui.c.rect(gx - 2 * k, y, gw + 4 * k, k, 0xffffff);
    }
    let top_mark = marks.iter().map(|m| m.0).fold(f64::MIN, f64::max);
    for (c, what, mc) in marks {
        let y = yof(f_of(*c));
        ui.c.rect(gx + gw + 2 * k, y, 10 * k, 2 * k, *mc);
        tx(ui, gx + gw + 14 * k, if *c >= top_mark && marks.len() > 1 { y - 11 * k } else { y + 3 * k }, what, &F6X10, k, *mc);
    }
    let (big, small) = match c {
        Some(c) => (format!("{:.1} F", f_of(c)), format!("{:.1} C", c)),
        None => ("no reading".to_string(), String::new()),
    };
    tx(ui, x, by + 22 * k, &big, &crate::font::F10X20, k, if c.is_some() { col } else { t.dim });
    tx(ui, x, by + 44 * k, &small, &F8X13, k, t.dim);
}

/// The diagram. Laid out in shares of the room it is given, and lettered twice or three times the
/// size on a wide screen, so that it fills an iMac as it fills a laptop.
fn diagram(ui: &mut Ui, at: Rect, doc: Option<&Value>) {
    let t = ui.t;
    let h = hearth();
    let plan = h.as_ref().and_then(|h| h.plan.as_ref());
    let Some(plan) = plan else {
        ui.label_in(at.x, at.y, at.w, "No plan to draw from: the controller's pass writes hearth/plan.json (tools/hearth.py QUEUE step).", &F8X13, t.dim);
        return;
    };
    let k = ((at.w / 1000).min(at.h / 470)).clamp(1, 3);
    let big = &crate::font::F10X20;
    let fl = flows(plan);
    let bud = plan.get("budget").filter(|b| !matches!(b, Value::Null));
    let room = bud.and_then(|b| n(b, "room_c")).or(n(plan, "temp_c"));
    let out = n(plan, "outside_c");
    let target = h.as_ref().and_then(|h| h.target());
    let ceiling = bud.and_then(|b| n(b, "ceiling_c"));
    let age = (epoch() - n(plan, "t").unwrap_or(0.0)).max(0.0);

    // ---- the thermometers, on the right, as tall as the panel
    let tw = (at.w * 20 / 100).max(250 * k);
    let therm = rect(at.right() - tw, at.y, tw, at.h);
    ui.c.frame(therm.x, therm.y, therm.w, therm.h, t.line);
    tx(ui, therm.x + 10 * k, therm.y + 7 * k, "THERMOMETERS", &F8X13, k, t.dim);
    let probes = arr(plan, "probes");
    let list_h = (probes.len() as i32 + 1) * 12 * k + 8 * k;
    let th = (therm.h - 60 * k - 110 * k - list_h).max(90 * k);
    let mut marks: Vec<(f64, &str, Rgb)> = Vec::new();
    if let Some(c) = target {
        marks.push((c, "target", LEAF));
    }
    if let Some(c) = ceiling {
        marks.push((c, "ceiling", ROSE));
    }
    let half = therm.w / 2;
    thermometer(ui, therm.x + 12 * k, therm.y + 60 * k, th, k, "THE ROOM", room, EMBER, 30.0, 90.0, &marks);
    thermometer(ui, therm.x + half + 6 * k, therm.y + 60 * k, th, k, "THE WEATHER", out, SKY, 30.0, 90.0, &[]);
    let mut py = therm.bottom() - list_h;
    for p in probes {
        let (name, c) = (s(p, "key").trim_end_matches(".c"), n(p, "c"));
        let ok = p.get("ok").and_then(|b| b.as_bool()).unwrap_or(false);
        let line = match c {
            Some(c) => format!("{:<14} {:>5.1} C {:>5.1} F", name, c, f_of(c)),
            None => format!("{:<14} no reading", name),
        };
        tx_in(ui, therm.x + 10 * k, py, therm.w - 16 * k, &line, &F6X10, k, if ok { t.ink } else { t.warn });
        py += 12 * k;
    }
    tx_in(ui, therm.x + 10 * k, py, therm.w - 16 * k, "zone 2: no thermometer", &F6X10, k, t.dim);

    // ---- the weather round everything; the apartment in it behind its walls; two zones in the apartment
    let main = rect(at.x, at.y, at.w - tw - 10 * k, at.h);
    for i in 0..k {
        ui.c.frame(main.x + i, main.y + i, main.w - 2 * i, main.h - 2 * i, SKY);
    }
    let wx = tx(ui, main.x + 10 * k, main.y + 7 * k, "THE WEATHER", &F8X13, k, SKY) + 10 * k;
    let weather = match out {
        Some(c) => format!("SeaTac airport, {}, observed {} ago", both(c), took(n(plan, "outside_age_s").unwrap_or(0.0))),
        None => "no outside reading".to_string(),
    };
    let old = format!("the plan is {} old", took(age));
    tx_in(ui, wx, main.y + 7 * k, main.right() - wx - tx_w(&old, &F8X13, k) - 20 * k, &weather, &F8X13, k, t.ink);
    tx(ui, main.right() - 10 * k - tx_w(&old, &F8X13, k), main.y + 7 * k, &old, &F8X13, k, if age > 900.0 { t.warn } else { t.dim });
    let wall = 9 * k;
    let outer = rect(main.x + 12 * k, main.y + 28 * k, main.w - 24 * k, main.h - 28 * k - 62 * k);
    // The walls: hatched, all the way round, which is where the loss is.
    hatch(ui, rect(outer.x, outer.y, outer.w, wall), t.dim);
    hatch(ui, rect(outer.x, outer.bottom() - wall, outer.w, wall), t.dim);
    hatch(ui, rect(outer.x, outer.y, wall, outer.h), t.dim);
    hatch(ui, rect(outer.right() - wall, outer.y, wall, outer.h), t.dim);
    let apt = rect(outer.x + wall, outer.y + wall, outer.w - 2 * wall, outer.h - 2 * wall);
    let z2w = (apt.w * 24 / 100).max(200 * k);
    let z1 = rect(apt.x + 6 * k, apt.y + 6 * k, apt.w - z2w - 18 * k, apt.h - 12 * k);
    let z2 = rect(z1.right() + 6 * k, apt.y + 6 * k, z2w, apt.h - 12 * k);
    for i in 0..k {
        ui.c.frame(z1.x + i, z1.y + i, z1.w - 2 * i, z1.h - 2 * i, EMBER);
    }
    dashed(ui, z2, DUSK);
    let zx = tx(ui, z1.x + 8 * k, z1.y + 6 * k, "ZONE 1  THE FLEET'S ROOM", &F8X13, k, EMBER) + 10 * k;
    let zline = match (room, target) {
        (Some(c), Some(tg)) => format!("{}, {:+.1} C from its target", both(c), c - tg),
        (Some(c), None) => both(c),
        _ => "no fresh probe".to_string(),
    };
    tx_in(ui, zx, z1.y + 6 * k, z1.right() - zx - 6 * k, &zline, &F8X13, k, t.ink);

    // The machines, each with its own clocks, on one collector.
    let boxes = doc.map(boxes_of).unwrap_or_default();
    let cols = 4.min(boxes.len().max(1)) as i32;
    let rows = ((boxes.len() as i32 + cols - 1) / cols).max(1);
    let gap = 10 * k;
    let (tw_, thh) = ((z1.w - 16 * k - (cols - 1) * gap) / cols, 66 * k);
    let top = z1.y + 26 * k;
    let bus_y = top + rows * (thh + 12 * k) + 4 * k;
    for (i, b) in boxes.iter().enumerate() {
        let (cx, ry) = ((i as i32) % cols, (i as i32) / cols);
        let r = rect(z1.x + 8 * k + cx * (tw_ + gap), top + ry * (thh + 12 * k), tw_, thh);
        let col = if b.on { SUN } else { t.dim };
        let ink = if b.on { t.ink } else { t.dim };
        ui.c.rect(r.x, r.y, r.w, r.h, crate::draw::mix(t.base, col, if b.on { 26 } else { 10 }));
        ui.c.frame(r.x, r.y, r.w, r.h, if b.on { col } else { t.dim });
        // The name has the first row to itself; the watts, as a bar and a number, the second.
        let watts = if b.on { format!("{:.0} W", b.wall_w) } else { "off".to_string() };
        tx_in(ui, r.x + 6 * k, r.y + 3 * k, r.w - 10 * k, &b.name, &F8X13, k, ink);
        tx(ui, r.right() - 6 * k - tx_w(&watts, &F6X10, k), r.y + 17 * k, &watts, &F6X10, k, col);
        let bw = r.w - 18 * k - tx_w(&watts, &F6X10, k);
        ui.c.rect(r.x + 6 * k, r.y + 20 * k, ((b.wall_w / 320.0).clamp(0.0, 1.0) * bw as f64) as i32, 4 * k, col);
        let cpu = match (b.cpu_c, b.cpu_tau_s) {
            (Some(c), Some(tau)) => format!("CPU {:.0}C tau {}", c, minutes(tau)),
            (Some(c), None) => format!("CPU {:.0}C tau ?", c),
            _ => "CPU not read".to_string(),
        };
        tx_in(ui, r.x + 6 * k, r.y + 30 * k, r.w - 10 * k, &cpu, &F6X10, k, ink);
        let drv = match (b.drive_c, b.drive_lag_s) {
            (Some(c), Some(lag)) => format!("HD {:.0}C lag {}", c, minutes(lag)),
            (Some(c), None) => format!("HD {:.0}C lag ?", c),
            _ => "no drive read".to_string(),
        };
        tx_in(ui, r.x + 6 * k, r.y + 41 * k, r.w - 10 * k, &drv, &F6X10, k, ink);
        let rest = match b.card_c {
            Some(c) => format!("card {:.0}C {}HD {}sens", c, b.drives, b.sensors),
            None => format!("{} HD {} sensors", b.drives, b.sensors),
        };
        tx_in(ui, r.x + 6 * k, r.y + 52 * k, r.w - 10 * k, &rest, &F6X10, k, t.dim);
        if b.on && b.wall_w > 1.0 {
            // To the collector: straight down where nothing stands below, else out by the gap beside it.
            let th_ = thick(b.wall_w).min(6) * k / 2 + 1;
            if i + cols as usize >= boxes.len() {
                pipe(ui, &[(r.x + r.w / 2, r.bottom()), (r.x + r.w / 2, bus_y - 2 * k)], th_, SUN);
            } else {
                let gx = r.right() + gap / 2;
                pipe(ui, &[(r.right(), r.y + r.h / 2), (gx, r.y + r.h / 2), (gx, bus_y - 2 * k)], th_, SUN);
            }
        }
    }
    let fleet = fl.as_ref().map(|f| f.fleet_w).or(n(plan, "now_w")).unwrap_or(0.0);
    ui.c.rect(z1.x + 8 * k, bus_y - 3 * k, z1.w - 16 * k, 6 * k, crate::draw::mix(SUN, 0x000000, 150));
    ui.c.rect(z1.x + 8 * k, bus_y - 2 * k, z1.w - 16 * k, 4 * k, SUN);

    // Below the collector: a trend, the tank, a trend.
    let low = rect(z1.x + 8 * k, bus_y + 8 * k, z1.w - 16 * k, z1.bottom() - bus_y - 16 * k);
    let side = low.w * 27 / 100;
    let tank_h = (low.h - 46 * k).clamp(70 * k, 190 * k);
    let tank = rect(low.x + side + 14 * k, low.y + 40 * k + (low.h - 46 * k - tank_h) / 2, low.w - 2 * side - 28 * k, tank_h);
    let tcx = tank.x + tank.w / 2;
    pipe(ui, &[(tcx, bus_y + 2 * k), (tcx, tank.y - k)], thick(fleet) * k.min(2), SUN);
    bubble(ui, tcx - 34 * k, bus_y + 22 * k, k, "JI", SUN, true);
    tx(ui, tcx + 24 * k, bus_y + 8 * k, &format!("HEAT IN  {:.0} W", fleet), big, k, SUN);
    tx(ui, tcx + 24 * k, bus_y + 29 * k, "every watt the fleet draws", &F6X10, k, t.dim);
    // The tank: the room's air and everything in it that warms with the air.
    for i in 0..(2 * k) {
        ui.c.frame(tank.x + i, tank.y + i, tank.w - 2 * i, tank.h - 2 * i, EMBER);
    }
    if let Some(c) = room {
        // The level stands under the words, never through them.
        let lev = (((f_of(c) - 60.0) / 30.0).clamp(0.05, 1.0) * (tank.h - 6 * k) as f64).min((tank.h - 76 * k).max(8) as f64) as i32;
        ui.c.rect(tank.x + 3 * k, tank.bottom() - 3 * k - lev, tank.w - 6 * k, lev, crate::draw::mix(t.base, EMBER, 70));
        ui.c.rect(tank.x + 3 * k, tank.bottom() - 3 * k - lev, tank.w - 6 * k, k, EMBER);
    }
    tx_in(ui, tank.x + 8 * k, tank.y + 7 * k, tank.w - 14 * k, "AIR AND THERMAL MASS", &F8X13, k, t.ink);
    bubble(ui, tank.right() - 18 * k, tank.bottom() - 18 * k, k, "TI", EMBER, room.is_some());
    let hist: Vec<f64> = bud.map(|b| arr(b, "trend")).unwrap_or(&[]).iter().filter_map(|v| v.as_num()).map(f_of).collect();
    let mut lines: Vec<(f64, Rgb)> = Vec::new();
    if let Some(c) = target {
        lines.push((f_of(c), LEAF));
    }
    if let Some(c) = ceiling {
        lines.push((f_of(c), ROSE));
    }
    // The room's strip stands above where the other heat's pipe comes across to the tank.
    let other_y = tank.y + tank.h * 2 / 3;
    trend(ui, rect(low.right() - side, low.y + 36 * k, side, (other_y - 20 * k - low.y - 36 * k).max(50 * k)), k, "THE ROOM, 3 HOURS, F", &hist, "F", EMBER, &lines);
    let wser: Vec<f64> = doc.and_then(|d| d.get("fleet")).and_then(|f| f.get("series")).map(|z| arr(z, "w")).unwrap_or(&[]).iter().filter_map(|v| v.as_num()).collect();
    trend(ui, rect(low.x, low.y + 36 * k, side, low.h - 36 * k), k, "HEAT IN, 6 HOURS, W", &wser, "W", SUN, &[]);

    tx(ui, z2.x + 8 * k, z2.y + 6 * k, "ZONE 2  THE REST", &F8X13, k, DUSK);
    tx_in(ui, z2.x + 8 * k, z2.y + 21 * k, z2.w - 14 * k, "of the apartment", &F6X10, k, t.dim);
    bubble(ui, z2.x + z2.w / 2, z2.y + 58 * k, k, "TI", DUSK, false);
    tx_in(ui, z2.x + 8 * k, z2.y + 76 * k, z2.w - 14 * k, "NO THERMOMETER", &F8X13, k, t.warn);
    let mut ly = z2.y + 94 * k;
    for l in ["people, cooking,", "appliances, the sun,", "the other rooms' air"] {
        tx_in(ui, z2.x + 8 * k, ly, z2.w - 14 * k, l, &F6X10, k, t.dim);
        ly += 11 * k;
    }
    if let Some(f) = &fl {
        let (c_mj, slope, ua) = (bud.and_then(|b| n(b, "c_mj_c")).unwrap_or(0.0), bud.and_then(|b| n(b, "slope_c_h")).unwrap_or(0.0), bud.and_then(|b| n(b, "ua_w_c")).unwrap_or(0.0));
        let word = if f.soak_w > 15.0 { "SOAKING UP" } else if f.soak_w < -15.0 { "GIVING BACK" } else { "HOLDING" };
        tx_in(ui, tank.x + 8 * k, tank.y + 24 * k, tank.w - 14 * k, &format!("{}  {:.0} W", word, f.soak_w.abs()), big, k, EMBER);
        tx_in(ui, tank.x + 8 * k, tank.y + 47 * k, tank.w - 14 * k, &format!("C {:.1} MJ/C (measured) x {:+.2} C/h", c_mj, slope), &F6X10, k, t.ink);
        tx_in(ui, tank.x + 8 * k, tank.y + 59 * k, tank.w - 14 * k, "walls, floor, furniture", &F6X10, k, t.dim);
        // Through the walls: down out of the tank, across the hatched wall, into the weather.
        let wx0 = tank.x + tank.w / 4;
        let wy = outer.bottom() + 34 * k;
        pipe(ui, &[(wx0, tank.bottom()), (wx0, wy)], thick(f.walls_w) * k.min(2), SKY);
        bubble(ui, wx0 - 36 * k, outer.bottom() + 20 * k, k, "JI", SKY, false);
        tx(ui, wx0 + 26 * k, outer.bottom() + 8 * k, &format!("THROUGH THE WALLS  {:.0} W", f.walls_w), big, k, SKY);
        // Where UA is from: a person, the steady stretches, or the figure in use. Only the last is a warning.
        let measured = bud.and_then(|b| b.get("ua_measured")).and_then(|v| v.as_bool()).unwrap_or(false);
        let from = bud.map(|b| s(b, "ua_from")).filter(|w| !w.is_empty()).unwrap_or("a figure in use, not a measurement");
        let words = if measured { format!("UA {:.0} W/C x {:.1} C over the weather. UA is from {}", ua, f.over_c, from) } else { format!("UA {:.0} W/C x {:.1} C over the weather. UA IS A FIGURE IN USE, NOT A MEASUREMENT", ua, f.over_c) };
        tx_in(ui, wx0 + 26 * k, outer.bottom() + 30 * k, main.right() - wx0 - 36 * k, &words, &F6X10, k, if measured { t.ink } else { t.warn });
        // The other heat: from zone 2's side, through the partition, into the tank.
        let oy = other_y;
        pipe(ui, &[(z2.x + z2.w / 2, z2.bottom() - 46 * k), (z2.x + z2.w / 2, oy), (tank.right() + k, oy)], thick(f.other_w) * k.min(2), DUSK);
        tx(ui, z2.x + 8 * k, ly + 10 * k, "OTHER HEAT", &F8X13, k, DUSK);
        tx_in(ui, z2.x + 8 * k, ly + 26 * k, z2.w - 14 * k, &format!("{:+.0} W", f.other_w), big, k, DUSK);
        let mut ny = z2.bottom() - 40 * k;
        for l in ["IMPLIED, not read:", "walls + soak - fleet.", "As wrong as UA is."] {
            tx_in(ui, z2.x + 8 * k, ny, z2.w - 14 * k, l, &F6X10, k, t.warn);
            ny += 11 * k;
        }
        let line = format!(
            "in: fleet {:.0} W + other {:+.0} W (implied)  =  out: walls {:.0} W + soak {:+.0} W      C dT/dt = P + P0 - UA (T - To)",
            f.fleet_w, f.other_w, f.walls_w, f.soak_w
        );
        tx_in(ui, main.x + 10 * k, main.bottom() - 14 * k, main.w - 20 * k, &line, &F6X10, k, t.dim);
    } else {
        tx_in(ui, tank.x + 8 * k, tank.y + 26 * k, tank.w - 14 * k, "No balance: the law in force is the ladder, or the room or the weather is not read.", &F6X10, k, t.warn);
    }
}

/// The hold's one line, and whether it is acting: its budget, what it holds paused, and the last
/// thing it said. Without a budget in the plan the law is the ladder's, and the line says so.
fn hold_line(plan: &Value) -> (String, bool) {
    let Some(b) = plan.get("budget").filter(|b| !matches!(b, Value::Null)) else {
        return ("not the law in force: the ladder below is (tools/hearth.py QUEUE set law hold makes the hold the law).".to_string(), false);
    };
    let h = plan.get("hold");
    let running = h.and_then(|h| h.get("running")).and_then(|b| b.as_bool()).unwrap_or(false);
    let held: Vec<&str> = h.map(|h| arr(h, "held")).unwrap_or(&[]).iter().filter_map(|l| l.as_str()).collect();
    let mut line = format!(
        "{}: budget {:+.0} W (the room {:.2} C, moving {:+.2} C an hour; UA {:.0} W/C, C {:.1} MJ/C); ceiling {}; lanes it holds paused: {}",
        if running { "the law, and acting" } else { "the law, and only saying (not in act)" },
        n(b, "w").unwrap_or(0.0),
        n(b, "room_c").unwrap_or(0.0),
        n(b, "slope_c_h").unwrap_or(0.0),
        n(b, "ua_w_c").unwrap_or(0.0),
        n(b, "c_mj_c").unwrap_or(0.0),
        n(b, "ceiling_c").map(both).unwrap_or_default(),
        if held.is_empty() { "none".to_string() } else { held.join(", ") }
    );
    let last = h.map(|h| s(h, "last")).unwrap_or("");
    if !last.is_empty() {
        line.push_str(&format!(". It last said: {}", last));
    }
    (line, running)
}

/// One machine a person can switch, as the plan lists it.
struct PowerCell {
    name: String,
    state: String,
    note: &'static str,
    on: bool,
    can_on: bool,
    can_off: bool,
}

/// The plan's `power` list as cells. A machine that carries a room probe, or has no power-off
/// rule, has no Off; one with no address recorded has no On.
fn power_cells(plan: &Value) -> Vec<PowerCell> {
    let flag = |p: &Value, k: &str| p.get(k).and_then(|b| b.as_bool());
    arr(plan, "power")
        .iter()
        .map(|p| {
            let on = flag(p, "on").unwrap_or(false);
            let mac = flag(p, "mac").unwrap_or(false);
            let note = if flag(p, "carries_probe").unwrap_or(false) {
                ", carries the room's probes"
            } else {
                match (flag(p, "wol"), mac) {
                    (Some(true), _) => ", wakes by the packet",
                    (Some(false), _) => ", did not wake by the packet",
                    (None, true) => ", wake untried",
                    (None, false) => ", no address",
                }
            };
            PowerCell { name: s(p, "name").to_string(), state: s(p, "state").to_string(), note, on, can_on: !on && mac, can_off: on && flag(p, "can_off").unwrap_or(false) }
        })
        .collect()
}

/// The orders still on their way, or ended within the half hour: (the line, whether it failed).
fn power_orders(plan: &Value, now: f64) -> Vec<(String, bool)> {
    arr(plan, "power")
        .iter()
        .filter_map(|p| {
            let o = p.get("order").filter(|o| !matches!(o, Value::Null))?;
            if n(o, "done").map(|d| now - d > 1800.0).unwrap_or(false) {
                return None;
            }
            let bad = o.get("ok").and_then(|b| b.as_bool()) == Some(false);
            Some((format!("{}, asked {} {} ago: {}", s(p, "name"), s(o, "what"), took((now - n(o, "t").unwrap_or(now)).max(0.0)), s(o, "state")), bad))
        })
        .collect()
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
    let hold_law = h.plan.as_ref().and_then(|p| p.get("budget")).map(|b| !matches!(b, Value::Null)).unwrap_or(false);
    let does = if hold_law {
        if power {
            "Act holds the room by the hold's law, one change a pass and no two within 40 minutes (at the ceiling, at once). Too warm: a machine known to wake by the packet finishes its task, leaves the queue and is POWERED OFF; any other has a lane take nothing new. Too cold: a paused lane works again, or a machine is woken and put in the queue. Machines without a card go first and come back last, and among equals the one that spends most energy on a job. The power switch is ON; it is set from the command line (tools/hearth.py QUEUE set power off)."
        } else {
            "Act holds the room by the hold's law, one change a pass and no two within 40 minutes (at the ceiling, at once): lanes take nothing new when it is too warm and work again when it is cold, machines without a card first. It does NOT power a machine off and does NOT wake one: the power switch is off (tools/hearth.py QUEUE set power on)."
        }
    } else if power {
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

    // The hold: the law that acts when the controller's law is `hold` (tools/hearth_regulator.py).
    // It runs with the pass, so it has no button of its own: act above is its switch.
    {
        let (line, running) = hold_line(plan);
        let mut x = ui.label(at.x, y + 5, "hold", &F8X13, t.dim) + 18;
        if running {
            ui.c.rect(x, y + 7, 8, 8, t.up);
            x += 14;
        }
        y = para(ui, x, y + 5, at.right() - x, &line, if running { t.ink } else { t.dim }).max(y + 22) + 2;
    }

    // The machines a person can switch, a cell each, flowed across (17 November, the day bosporus
    // first came up from a packet: "Add the buttons to turn on and off"). On sends the wake packet
    // and, when the machine answers, puts it in the queue; Off lets it finish its jobs, leave the
    // queue and power off, and asks twice. A person's order, whatever the mode.
    let switches = power_cells(plan);
    if !switches.is_empty() {
        let x0 = ui.label(at.x, y + 5, "power", &F8X13, t.dim) + 10;
        let mut x = x0;
        for c in &switches {
            let text = format!("{}: {}{}", c.name, c.state, c.note);
            let armed = st.arm_off.as_deref() == Some(c.name.as_str());
            let label = if !c.on { "On" } else if armed { "Press again: off" } else { "Off" };
            let can = operator && if c.on { c.can_off } else { c.can_on };
            let bw = if can { F8X13.measure(label) as i32 + 22 } else { 0 };
            let w = F8X13.measure(&text) as i32 + 8 + bw + 20;
            if x + w > at.right() && x > x0 {
                x = x0;
                y += 26;
            }
            let bx = ui.label(x, y + 5, &text, &F8X13, if c.on { t.ink } else { t.dim }) + 8;
            if can {
                let r = rect(bx, y + 1, bw, 22);
                if c.on && armed {
                    ui.c.frame(r.x - 2, r.y - 2, r.w + 4, r.h + 4, t.alarm);
                }
                if ui.button(r, label, true) {
                    if c.on && !armed {
                        st.arm_off = Some(c.name.clone());
                    } else {
                        let verb = format!("hearth power-{} {}", if c.on { "off" } else { "on" }, c.name);
                        st.asked = Some(verb.clone());
                        *ctl = Some(verb);
                        st.arm_off = None;
                    }
                }
            }
            x += w;
        }
        y += 26;
        for (line, bad) in power_orders(plan, epoch()) {
            y = para(ui, x0, y, at.right() - x0, &line, if bad { t.alarm } else { t.accent });
        }
        y += 4;
    }

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
    fn a_machine_gets_the_button_it_can_use_and_an_order_is_said_until_half_an_hour_after() {
        let plan = json::parse(
            r#"{"power": [
            {"name": "bosporus", "state": "off, or not read", "on": false, "mac": true, "wol": true, "can_off": true, "carries_probe": false,
             "order": {"what": "on", "t": 1000, "state": "the wake packet was sent; waiting for it to answer", "ok": null}},
            {"name": "jaguaribe", "state": "in the queue", "on": true, "mac": true, "wol": null, "can_off": true, "carries_probe": false,
             "order": {"what": "off", "t": 100, "done": 200, "state": "out of the queue; its power-off was sent", "ok": true}},
            {"name": "saskatchewan", "state": "in the queue", "on": true, "mac": true, "wol": null, "can_off": false, "carries_probe": true, "order": null},
            {"name": "nasser", "state": "off, or not read", "on": false, "mac": false, "wol": null, "can_off": true, "carries_probe": false, "order": null}]}"#,
        )
        .unwrap();
        let c = power_cells(&plan);
        assert_eq!(c.len(), 4);
        assert!(c[0].can_on && !c[0].can_off && c[0].note == ", wakes by the packet");
        assert!(!c[1].can_on && c[1].can_off && c[1].note == ", wake untried");
        assert!(!c[2].can_on && !c[2].can_off && c[2].note == ", carries the room's probes");
        assert!(!c[3].can_on && !c[3].can_off && c[3].note == ", no address");
        let o = power_orders(&plan, 1060.0);
        assert_eq!(o.len(), 2);
        assert_eq!(o[0], ("bosporus, asked on 60 s ago: the wake packet was sent; waiting for it to answer".to_string(), false));
        assert_eq!(power_orders(&plan, 3000.0).len(), 1);
        assert!(power_cells(&json::parse("{}").unwrap()).is_empty());
        // The hold's line: the ladder's law; the hold saying; the hold acting, with what it holds and last said.
        assert!(hold_line(&json::parse("{}").unwrap()).0.starts_with("not the law in force"));
        let doc = r#"{"budget": {"w": -120, "room_c": 26.9, "slope_c_h": 0.1, "ua_w_c": 120, "c_mj_c": 4.2, "ceiling_c": 27.2}, "hold": {"running": RUN, "held": ["whitewolf-cuda"], "last": "12:00:00  room 26.90 C"}}"#;
        let (line, on) = hold_line(&json::parse(&doc.replace("RUN", "false")).unwrap());
        assert!(!on && line.starts_with("the law, and only saying"));
        let (line, on) = hold_line(&json::parse(&doc.replace("RUN", "true")).unwrap());
        assert!(on && line.contains("budget -120 W") && line.contains("27.2 C (81.0 F)") && line.contains("whitewolf-cuda") && line.ends_with("It last said: 12:00:00  room 26.90 C"));
        assert!(terms_line(&json::parse(&doc.replace("RUN", "true")).unwrap()).starts_with("the hold's budget"));
        // The diagram's four flows: walls = UA x the room over the weather, soak = C x the slope, and the
        // other heat is what is left over. No budget, no flows.
        assert!(flows(&json::parse("{}").unwrap()).is_none());
        let f = flows(&json::parse(r#"{"outside_c": 6.0, "now_w": 1400, "budget": {"room_c": 26.0, "ua_w_c": 120, "c_mj_c": 3.6, "slope_c_h": 0.1}}"#).unwrap()).unwrap();
        assert_eq!(f, Flows { fleet_w: 1400.0, walls_w: 2400.0, soak_w: 100.0, other_w: 1100.0, over_c: 20.0 });
        assert_eq!((thick(30.0), thick(700.0), thick(9000.0)), (2, 10, 26));
        assert_eq!((minutes(64.0), minutes(2595.0), minutes(35776.0)), ("64 s".to_string(), "43 min".to_string(), "9.9 h".to_string()));
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
