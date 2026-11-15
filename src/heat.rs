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
//! No dial yet. A target a machine and a throttle on its part in the queue wait for the model the
//! numbers here are the start of; the room's own temperature is read by nothing in the fleet, and the
//! page says what stands in its place.
use crate::draw::Rgb;
use crate::font::{F6X10, F8X13};
use crate::json::Value;
use crate::ui::{rect, Rect, Ui};

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
    let k = v.len().max(2) as f64 - 1.0;
    let mut last: Option<(i32, i32)> = None;
    for (i, x) in v.iter().enumerate() {
        match x.as_num() {
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

pub fn draw(ui: &mut Ui, at: Rect, doc: Option<&Value>) {
    let t = ui.t;
    let Some(doc) = doc.filter(|d| d.get("machines").is_some()) else {
        ui.label_in(at.x, at.y, at.w, "No record yet: tools/telemetry.py QUEUE pull writes plan/thermal.json (the keeper's housekeeping asks each five minutes).", &F8X13, t.dim);
        return;
    };
    let lh = F8X13.height as i32;
    let hours = n(doc, "hours").unwrap_or(6.0);
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
        // Its watts over the window, a strip.
        let w = fl.get("series").map(|z| arr(z, "w")).unwrap_or(&[]);
        if let Some((_, hi)) = span(&[w]) {
            let strip = rect(at.x, y, at.w - 60, 40);
            ui.well(strip);
            let plot = strip.inset(3);
            trace(ui, plot, w, 0.0, hi * 1.08, t.accent);
            ui.label(strip.right() + 4, strip.y, &format!("{:.0} W", hi * 1.08), &F6X10, t.dim);
            ui.label(strip.right() + 4, strip.bottom() - F6X10.height as i32, "0", &F6X10, t.dim);
            ui.tip(strip, || vec![format!("The fleet's watts at the wall over the last {} hours: each machine's model at the CPUs' use measured, the cards' watts measured. All of it is heat into the room.", hours)]);
            y += strip.h + 4;
        }
    }
    ui.label_in(at.x, y, at.w, &format!("each machine: its CPU (green) and its card (amber) over the last {} hours, the limit ruled in red; then what its steps say", hours), &F8X13, t.dim);
    y += lh + 4;
    let ms = arr(doc, "machines");
    if ms.is_empty() {
        return;
    }
    let row_h = (((at.bottom() - y) / ms.len() as i32) - 4).clamp(lh * 3 + 8, 96);
    let (left_w, chart_w) = (300.min(at.w / 4), (at.w * 3 / 10).max(160));
    for m in ms {
        if y + row_h > at.bottom() {
            break;
        }
        let row = rect(at.x, y, at.w, row_h);
        ui.c.frame(row.x, row.y, row.w, row.h, t.line);
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
        // Six hours, one scale: the CPU, the card, the limits.
        let ser = m.get("series");
        let (cpu, gpu) = (ser.map(|z| arr(z, "cpu")).unwrap_or(&[]), ser.map(|z| arr(z, "gpu")).unwrap_or(&[]));
        let well = rect(row.x + left_w, row.y + 4, chart_w, row_h - 8);
        ui.well(well);
        let plot = rect(well.x + 3, well.y + 3, well.w - 6 - 26, well.h - 6);
        if let Some((lo, hi)) = span(&[cpu, gpu]) {
            let limits: Vec<f64> = [n(m, "cpu_hot").filter(|_| !cpu.is_empty()), n(m, "gpu_hot")].iter().flatten().cloned().collect();
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
            trace(ui, plot, gpu, lo, hi, t.warn);
            trace(ui, plot, cpu, lo, hi, t.up);
            ui.label(plot.right() + 3, plot.y, &format!("{:.0}", hi), &F6X10, t.dim);
            ui.label(plot.right() + 3, plot.bottom() - F6X10.height as i32, &format!("{:.0}", lo), &F6X10, t.dim);
        } else {
            ui.label_in(plot.x + 4, plot.y + 4, plot.w - 8, "no CPU or card reading in the window", &F6X10, t.dim);
        }
        // What the steps say of each part.
        let rx = well.right() + 12;
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
        let fans: Vec<String> = arr(m, "fans").iter().filter_map(|f| f.as_array()).filter_map(|f| Some(format!("{:.0}", f.get(1)?.as_num()?))).collect();
        if !fans.is_empty() && ry + lh <= row.bottom() {
            ui.label_in(rx, ry, rw, &format!("fans, rpm: {}", fans.join("  ")), &F8X13, t.dim);
        }
        ui.tip(row, || {
            let mut v = vec![format!("{}: every channel it reports now, degrees C", s(m, "name"))];
            let ch: Vec<String> = arr(m, "channels").iter().filter_map(|c| c.as_array()).filter_map(|c| Some(format!("{} {:.0}", c.first()?.as_str()?, c.get(1)?.as_num()?))).collect();
            for line in ch.chunks(4) {
                v.push(line.join("   "));
            }
            v.push(format!("Its watts are {}.", s(m, "watts_from")));
            for f in arr(m, "fits").iter().take(6) {
                let mut line = format!("step {}: {} tau {}, to {:.0} C, held {:.1} tau", s(f, "step"), s(f, "channel"), took(n(f, "tau_s").unwrap_or(0.0)), n(f, "end_c").unwrap_or(0.0), n(f, "taus_held").unwrap_or(0.0));
                if n(f, "taus_held").unwrap_or(0.0) < 3.0 {
                    line.push_str(" (a projection)");
                }
                v.push(line);
            }
            v
        });
        y += row_h + 4;
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
    }
}
