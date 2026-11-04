//! Results, Montage: the generations since the last film, as a film -- crucible's world duels, the
//! camera on the best winning tank, every other duel a ghost -- made by request and kept in the archive.
//!
//! Paul, 4 November: "make this repeatable via a button in Orrery, where all these steps show a
//! generation of and its progression like a story ... We need a way to replay those, while we
//! processing the recordings." The document is treadcore-view.py's `montage`: tools/montage.py's state
//! (QUEUE/plan/montage.json), the films in QUEUE/archive/montages/ with each one's chapters, and while
//! one is made, its newest frame (plan/montage-preview.ppm, 320 by 180), drawn here twice the size --
//! the replay while it is processed. Make and Play are verbs for `fleet-queue.py QUEUE montage ...`:
//! Make runs in the background (a few minutes: a trace on a GPU island, then the frames), Play opens
//! the film in the machine's own player. THE PAGE DRAWS AND ASKS; it never renders or deletes.
//!
//! A CHAPTER IS ITS WINS, LOSSES AND DRAWS FROM ONE START, against the same opponents in every
//! chapter: the bar is the comparison the film makes, so it is drawn beside each chapter's name.
use crate::draw::Rgb;
use crate::font::{F6X10, F8X13};
use crate::json::Value;
use crate::ui::{rect, Rect, Ui};
use std::sync::Mutex;

/// What the page remembers between frames.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct State {
    /// The film selected, by its number (0: the newest).
    pub sel: i64,
    pub off: usize,
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

/// A PPM (P6, 8-bit) read once a change of its file: (width, height, pixels).
struct Pic {
    path: String,
    stamp: std::time::SystemTime,
    w: usize,
    h: usize,
    px: Vec<u8>,
}

static PICS: Mutex<Vec<Pic>> = Mutex::new(Vec::new());

fn ppm(bytes: &[u8]) -> Option<(usize, usize, Vec<u8>)> {
    // "P6\n<w> <h>\n255\n" then w*h*3 bytes: the form montage.py writes.
    let mut fields = Vec::new();
    let mut i = 0;
    while fields.len() < 4 && i < bytes.len() {
        while i < bytes.len() && bytes[i].is_ascii_whitespace() {
            i += 1;
        }
        let st = i;
        while i < bytes.len() && !bytes[i].is_ascii_whitespace() {
            i += 1;
        }
        fields.push(String::from_utf8_lossy(&bytes[st..i]).to_string());
    }
    if fields.len() < 4 || fields[0] != "P6" || fields[3] != "255" {
        return None;
    }
    let (w, h): (usize, usize) = (fields[1].parse().ok()?, fields[2].parse().ok()?);
    let px = bytes.get(i + 1..i + 1 + w * h * 3)?.to_vec();
    Some((w, h, px))
}

/// Draw a PPM file at (x, y), each pixel `k` by `k`; false when it cannot be read.
fn picture(ui: &mut Ui, path: &str, x: i32, y: i32, k: i32) -> bool {
    let Ok(stamp) = std::fs::metadata(path).and_then(|m| m.modified()) else {
        return false;
    };
    let mut pics = PICS.lock().unwrap_or_else(|e| e.into_inner());
    if !pics.iter().any(|p| p.path == path && p.stamp == stamp) {
        let Some((w, h, px)) = std::fs::read(path).ok().and_then(|b| ppm(&b)) else {
            return false;
        };
        pics.retain(|p| p.path != path);
        if pics.len() > 16 {
            pics.remove(0);
        }
        pics.push(Pic { path: path.to_string(), stamp, w, h, px });
    }
    let p = pics.iter().find(|p| p.path == path).unwrap();
    for py in 0..p.h {
        for px in 0..p.w {
            let o = (py * p.w + px) * 3;
            let c: Rgb = ((p.px[o] as u32) << 16) | ((p.px[o + 1] as u32) << 8) | p.px[o + 2] as u32;
            ui.c.rect(x + px as i32 * k, y + py as i32 * k, k, k, c);
        }
    }
    true
}

pub fn draw(ui: &mut Ui, at: Rect, doc: Option<&Value>, st: &mut State, operator: bool, ctl: &mut Option<String>) {
    let t = ui.t;
    let Some(doc) = doc.filter(|d| !matches!(d, Value::Null)) else {
        ui.label_in(at.x, at.y, at.w, "No montage yet, and no state: Make montage traces the generations since the last film on a GPU island and renders them (tools/montage.py).", &F8X13, t.dim);
        if operator && ui.button(rect(at.x, at.y + 24, 160, 22), "Make montage", true) {
            *ctl = Some("montage make".to_string());
        }
        return;
    };
    let state = doc.get("state").cloned().unwrap_or(Value::Null);
    let running = doc.get("running").and_then(|x| x.as_bool()).unwrap_or(false);
    // ---- what it is doing, and the press that begins it ----
    let mut x = at.x;
    if operator {
        let label = if running { "Making..." } else { "Make montage" };
        if ui.button(rect(x, at.y, 150, 22), label, !running) {
            *ctl = Some("montage make".to_string());
        }
        x += 160;
    }
    let said = format!("{}: {}", if s(&state, "state").is_empty() { "idle".to_string() } else { s(&state, "state") }, s(&state, "said"));
    let prog = n(&state, "progress").clamp(0.0, 1.0);
    if running {
        let bar = rect(x, at.y + 7, 200, 8);
        ui.c.rect(bar.x, bar.y, bar.w, bar.h, t.line);
        ui.c.rect(bar.x, bar.y, (bar.w as f64 * prog) as i32, bar.h, t.up);
        x += 212;
    }
    ui.label_in(x, at.y + 5, at.right() - x, &said, &F8X13, if s(&state, "state") == "failed" { t.alarm } else { t.dim });
    let mut y = at.y + 32;
    // ---- the replay while it is made: the newest frame ----
    let preview = s(doc, "preview");
    let left = rect(at.x, y, 660, at.bottom() - y);
    if running && !preview.is_empty() && picture(ui, &preview, left.x, y, 2) {
        ui.label(left.x, y + 364, "the newest frame, as it is rendered", &F6X10, t.dim);
        y += 380;
    }
    // ---- the films ----
    let films = arr(doc, "films");
    if films.is_empty() {
        ui.label_in(left.x, y, left.w, "No film yet.", &F8X13, t.dim);
        return;
    }
    let lh = F8X13.height as i32 + 8;
    let list = rect(left.x, y, left.w, left.bottom() - y);
    ui.well(list);
    if st.sel == 0 {
        st.sel = n(&films[0], "n") as i64;
    }
    let (area, first, count) = ui.scroll_list(list.inset(2), films.len(), lh, &mut st.off);
    for (i, f) in films.iter().enumerate().skip(first).take(count) {
        let row = rect(area.x, area.y + (i - first) as i32 * lh, area.w, lh);
        let num = n(f, "n") as i64;
        if num == st.sel {
            ui.c.rect(row.x, row.y, row.w, row.h, t.tile);
        }
        if ui.button_hit(rect(row.x, row.y, row.w - 70, row.h)) {
            st.sel = num;
        }
        let line = format!(
            "Montage {}  {}  {} chapters, {:.0} s, {:.0} MB  {} to {}",
            num,
            s(f, "at").replace('T', " "),
            arr(f, "chapters").len(),
            n(f, "seconds"),
            n(f, "bytes") / 1e6,
            if s(f, "since").is_empty() { "the start".to_string() } else { s(f, "since") },
            s(f, "last")
        );
        ui.label_in(row.x + 6, row.y + 4, row.w - 84, &line, &F8X13, t.ink);
        if ui.button(rect(row.right() - 64, row.y + 1, 60, lh - 2), "Play", true) {
            *ctl = Some(format!("montage open {}", num));
        }
    }
    // ---- the film chosen: its poster and its chapters ----
    let Some(f) = films.iter().find(|f| n(f, "n") as i64 == st.sel) else {
        return;
    };
    let rx = left.right() + 16;
    let mut ry = at.y + 32;
    let poster = s(f, "poster");
    if !poster.is_empty() && picture(ui, &poster, rx, ry, 1) {
        ry += 188;
    }
    ui.label(rx, ry, &format!("Montage {}: {} duels from one start in every chapter", s(f, "n"), s(f, "duels")), &F8X13, t.ink);
    ry += 20;
    let bar_w = 180;
    for ch in arr(f, "chapters") {
        if ry + 16 > at.bottom() {
            break;
        }
        let (w, l, d) = (n(ch, "won"), n(ch, "lost"), n(ch, "drawn"));
        let total = (w + l + d).max(1.0);
        let label = format!("{:<5} gen {:>9}  {}", s(ch, "name"), s(ch, "gen"), s(ch, "island").trim_end_matches("-cuda"));
        ui.label_in(rx, ry, 300, &label, &F8X13, t.ink);
        let bx = rx + 310;
        let ww = (bar_w as f64 * w / total) as i32;
        let lw = (bar_w as f64 * l / total) as i32;
        ui.c.rect(bx, ry + 2, bar_w, 10, t.line);
        ui.c.rect(bx, ry + 2, ww, 10, t.up);
        ui.c.rect(bx + bar_w - lw, ry + 2, lw, 10, t.alarm);
        ui.label(bx + bar_w + 8, ry, &format!("{} won  {} lost  {} drawn", w, l, d), &F6X10, t.dim);
        let clips: Vec<String> = arr(ch, "clips").iter().map(|c| s(c, "what")).collect();
        let (name, gen) = (s(ch, "label"), s(ch, "gen"));
        ui.tip(rect(rx, ry, bx + bar_w - rx, 14), move || {
            let mut v = vec![format!("{} at generation {}", name, gen), "Its clips:".to_string()];
            v.extend(clips);
            v
        });
        ry += 16;
    }
}
