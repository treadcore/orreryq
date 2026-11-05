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
//!
//! THE MIND PLAYS HERE TOO (Paul, 4 November: "This should really be animated within orrery or
//! treadcore"). A film made since version 2 of crucible's trace has a mind.json beside it: every step
//! of every clip, the champion's 55 inputs, its two layers of 48, its four outputs, what its tank did,
//! the shot it fired, and the strongest currents between the layers. The page draws the film's corners
//! from it, natively and at the console's own six frames a second, paced by the wall clock (a step is
//! 0.1 s), so the net can be watched thinking without the film. Paused, it rests on the first step whose
//! shell hit.
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
    /// The mind playing, since when, and where it was left (a step of the film's mind).
    pub mind_play: bool,
    pub mind_t0: Option<std::time::Instant>,
    pub mind_at: Option<usize>,
}

// ---- the mind: mind.json, drawn as the film's corners ----

/// The screens' colours, treadcore.org's (site.css): black glass, phosphor, amber, a dim rim.
const SCR: Rgb = 0x070807;
const PHOS: Rgb = 0x33f24d;
const PHOS_DIM: Rgb = 0x1d8a2c;
const AMBER: Rgb = 0xffbf4d;
const RED: Rgb = 0xf23326;
const SKY: Rgb = 0x73c7ff;

/// One step of one clip.
struct Step {
    ch: usize,
    clip: String,
    x: Vec<f32>,
    h1: Vec<f32>,
    h2: Vec<f32>,
    y: Vec<f32>,
    a: Vec<f32>,
    shot: String,
    cur: Vec<(u8, usize, usize, f32)>,
}

/// A film's mind, read once a change of its file.
struct Mind {
    path: String,
    stamp: std::time::SystemTime,
    chapters: Vec<(String, i64, String)>,
    steps: Vec<Step>,
}

static MIND: Mutex<Option<Mind>> = Mutex::new(None);

fn floats(v: Option<&Value>) -> Vec<f32> {
    v.and_then(|x| x.as_array()).map(|a| a.iter().map(|n| n.as_num().unwrap_or(0.0) as f32).collect()).unwrap_or_default()
}

fn read_mind(path: &str) -> Option<Mind> {
    let stamp = std::fs::metadata(path).and_then(|m| m.modified()).ok()?;
    let doc = crate::json::parse(&std::fs::read_to_string(path).ok()?).ok()?;
    let mut chapters = Vec::new();
    let mut steps = Vec::new();
    for (ci, ch) in arr(&doc, "chapters").iter().enumerate() {
        chapters.push((s(ch, "label"), n(ch, "gen") as i64, s(ch, "island")));
        for clip in arr(ch, "clips") {
            for st in arr(clip, "steps") {
                let cur = arr(st, "c")
                    .iter()
                    .filter_map(|e| e.as_array())
                    .filter(|e| e.len() == 4)
                    .map(|e| (e[0].as_num().unwrap_or(0.0) as u8, e[1].as_num().unwrap_or(0.0) as usize, e[2].as_num().unwrap_or(0.0) as usize, e[3].as_num().unwrap_or(0.0) as f32))
                    .collect();
                steps.push(Step { ch: ci, clip: s(clip, "what"), x: floats(st.get("x")), h1: floats(st.get("h1")), h2: floats(st.get("h2")), y: floats(st.get("y")), a: floats(st.get("a")), shot: s(st, "s"), cur });
            }
        }
    }
    Some(Mind { path: path.to_string(), stamp, chapters, steps })
}

/// A number as the screens show one: phosphor for +, amber for -, black at 0, the brightness its size.
fn shade(v: f32, signed: bool) -> Rgb {
    let a = if signed { v.clamp(-1.0, 1.0) } else { v.clamp(0.0, 1.0) };
    let k = (a.abs().powf(0.6) * 255.0) as u8;
    crate::draw::mix(SCR, if a >= 0.0 { PHOS } else { AMBER }, k)
}

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

/// The mind player: the film's corners on one screen, its buttons under it. Returns the height used.
fn draw_mind(ui: &mut Ui, at: Rect, path: &str, film_n: i64, st: &mut State, now: Option<std::time::Instant>) -> i32 {
    let mut guard = MIND.lock().unwrap_or_else(|e| e.into_inner());
    let fresh = std::fs::metadata(path).and_then(|m| m.modified()).ok();
    if guard.as_ref().map(|m| m.path != path || Some(m.stamp) != fresh).unwrap_or(true) {
        *guard = read_mind(path);
        st.mind_at = None;
    }
    let Some(m) = guard.as_ref().filter(|m| !m.steps.is_empty()) else {
        return 0;
    };
    let t = ui.t;
    let total = m.steps.len();
    let rest = st.mind_at.unwrap_or_else(|| m.steps.iter().position(|x| x.shot == "hit").unwrap_or(0));
    let i = match (st.mind_play, st.mind_t0, now) {
        (true, Some(t0), Some(now)) => (rest + (now.duration_since(t0).as_secs_f64() * 10.0) as usize) % total,
        _ => rest.min(total - 1),
    };
    let step = &m.steps[i];
    let h = 300;
    let screen = rect(at.x, at.y, at.w, h - 30);
    ui.c.rect(screen.x - 1, screen.y - 1, screen.w + 2, screen.h + 2, PHOS_DIM);
    ui.c.rect(screen.x, screen.y, screen.w, screen.h, SCR);
    for yy in (screen.y + 1..screen.bottom()).step_by(3) {
        ui.c.rect(screen.x, yy, screen.w, 1, 0x0b0e0b);
    }
    let (label, gen, island) = m.chapters.get(step.ch).cloned().unwrap_or_default();
    ui.label_in(screen.x + 10, screen.y + 6, screen.w - 20, &format!("MIND  montage {}  chapter {} of {}  {}  {}", film_n, step.ch + 1, m.chapters.len(), island.trim_end_matches("-cuda"), step.clip), &F6X10, PHOS);
    // The generation, the fourth corner.
    ui.label(screen.right() - 170, screen.y + 22, "GENERATION", &F6X10, PHOS_DIM);
    ui.label(screen.right() - 170, screen.y + 36, &format!("{}", gen), &F8X13, PHOS);
    ui.label_in(screen.right() - 170, screen.y + 54, 160, &label, &F6X10, AMBER);
    // The inputs, 11 a row.
    let (ix, iy) = (screen.x + 10, screen.y + 24);
    ui.label(ix, iy, "inputs", &F6X10, PHOS_DIM);
    for (k, v) in step.x.iter().enumerate() {
        ui.c.rect(ix + (k % 11) as i32 * 13, iy + 14 + (k / 11) as i32 * 13, 11, 11, shade(*v, true));
    }
    // The transform: h1, h2 and the outputs, the strongest currents between them.
    let (tx, ty) = (screen.x + 10, screen.y + 112);
    ui.label(tx, ty, "transform  55 > 48 > 48 > 4", &F6X10, PHOS_DIM);
    let g1 = |k: usize| (tx + (k % 8) as i32 * 12 + 5, ty + 16 + (k / 8) as i32 * 12 + 5);
    let g2 = |k: usize| (tx + 150 + (k % 8) as i32 * 12 + 5, ty + 16 + (k / 8) as i32 * 12 + 5);
    let go = |k: usize| (tx + 290 + 8, ty + 16 + k as i32 * 20 + 8);
    let top = step.cur.iter().fold(1e-6f32, |a, e| a.max(e.3.abs()));
    for &(layer, a, b, v) in step.cur.iter().rev() {
        let (p, q) = if layer == 0 { (g1(a), g2(b)) } else { (g2(a), go(b)) };
        let k = ((v.abs() / top).powf(0.8) * 200.0) as u8 + 40;
        seg(ui, p, q, crate::draw::mix(SCR, if v >= 0.0 { PHOS } else { AMBER }, k));
    }
    for (k, v) in step.h1.iter().enumerate() {
        let (cx, cy) = g1(k);
        ui.c.rect(cx - 5, cy - 5, 10, 10, shade(*v, true));
    }
    for (k, v) in step.h2.iter().enumerate() {
        let (cx, cy) = g2(k);
        ui.c.rect(cx - 5, cy - 5, 10, 10, shade(*v, true));
    }
    for (k, v) in step.y.iter().enumerate() {
        let (cx, cy) = go(k);
        ui.c.rect(cx - 8, cy - 8, 16, 16, shade(*v, true));
        ui.label(cx + 12, cy - 5, ["turn", "speed", "fire", "gate"].get(k).copied().unwrap_or(""), &F6X10, PHOS_DIM);
    }
    // The decisions: the clip's last eight seconds, newest at the right.
    let (dx, dy) = (screen.x + 360, screen.y + 112);
    ui.label(dx, dy, "decisions, the last 8 s", &F6X10, PHOS_DIM);
    let rows = ["turn", "speed", "fire", "net's say", "shots"];
    for (r, word) in rows.iter().enumerate() {
        ui.label(dx, dy + 16 + r as i32 * 14, word, &F6X10, PHOS_DIM);
    }
    let cx0 = dx + 64;
    let cols = ((screen.right() - 10 - cx0) / 3).min(80) as usize;
    for k in 0..cols {
        let back = cols - 1 - k;
        if back > i {
            continue;
        }
        let u = &m.steps[i - back];
        if u.ch != step.ch || u.clip != step.clip {
            continue;
        }
        let col = cx0 + k as i32 * 3;
        let vals = [shade(*u.a.first().unwrap_or(&0.0), true), shade(*u.a.get(1).unwrap_or(&0.0), false), shade(*u.a.get(2).unwrap_or(&0.0), true), shade(*u.y.last().unwrap_or(&0.0), true)];
        for (r, c) in vals.iter().enumerate() {
            ui.c.rect(col, dy + 16 + r as i32 * 14, 3, 12, *c);
        }
        let sc = match u.shot.as_str() {
            "hit" => Some(RED),
            "pillbox" => Some(AMBER),
            "shot" => Some(0xf0f8f0),
            "pillbox fired" => Some(SKY),
            _ => None,
        };
        if let Some(c) = sc {
            ui.c.rect(col, dy + 16 + 4 * 14, 3, 12, c);
        }
    }
    ui.c.rect(cx0 + cols as i32 * 3, dy + 14, 1, 5 * 14, PHOS);
    // The buttons.
    let by = screen.bottom() + 6;
    if ui.button(rect(at.x, by, 90, 22), if st.mind_play { "Pause" } else { "Play mind" }, true) {
        if st.mind_play {
            st.mind_at = Some(i);
            st.mind_play = false;
        } else {
            st.mind_at = Some(i);
            st.mind_t0 = now;
            st.mind_play = now.is_some();
        }
    }
    let first_of = |c: usize| m.steps.iter().position(|x| x.ch == c).unwrap_or(0);
    if ui.button(rect(at.x + 98, by, 90, 22), "< chapter", step.ch > 0) {
        st.mind_at = Some(first_of(step.ch - 1));
        st.mind_t0 = now;
    }
    if ui.button(rect(at.x + 196, by, 90, 22), "chapter >", step.ch + 1 < m.chapters.len()) {
        st.mind_at = Some(first_of(step.ch + 1));
        st.mind_t0 = now;
    }
    ui.label_in(at.x + 296, by + 5, at.w - 296, &format!("step {} of {}  green +, amber -, black 0; a step is 0.1 s", i + 1, total), &F6X10, t.dim);
    h
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
    // ---- the mind of the film chosen, when it has one and nothing is being made ----
    if st.sel == 0 {
        st.sel = n(&films[0], "n") as i64;
    }
    if !running {
        if let Some(f) = films.iter().find(|f| n(f, "n") as i64 == st.sel) {
            let mind = s(f, "mind");
            if !mind.is_empty() {
                // The console's frames for a screenshot (--frame) have no clock: the mind rests.
                let now = if std::env::var("ORRERY_FRAME_PAGE").is_ok() { None } else { Some(std::time::Instant::now()) };
                y += draw_mind(ui, rect(left.x, y, left.w, 300), &mind, st.sel, st, now) + 10;
            }
        }
    }
    let lh = F8X13.height as i32 + 8;
    let list = rect(left.x, y, left.w, left.bottom() - y);
    ui.well(list);
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
    // The bar shrinks to the room there is, and its words move into the tip when there is none (at 1280
    // pixels wide the column ran past the page's edge).
    let bar_w = (at.right() - (rx + 310) - 150).clamp(40, 180);
    let words = rx + 310 + bar_w + 8 + 140 <= at.right();
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
        if words {
            ui.label(bx + bar_w + 8, ry, &format!("{} won  {} lost  {} drawn", w, l, d), &F6X10, t.dim);
        }
        let clips: Vec<String> = arr(ch, "clips").iter().map(|c| s(c, "what")).collect();
        let (name, gen) = (s(ch, "label"), s(ch, "gen"));
        let score = format!("{} won, {} lost, {} drawn", w, l, d);
        ui.tip(rect(rx, ry, bx + bar_w - rx, 14), move || {
            let mut v = vec![format!("{} at generation {}: {}", name, gen, score), "Its clips:".to_string()];
            v.extend(clips);
            v
        });
        ry += 16;
    }
}
