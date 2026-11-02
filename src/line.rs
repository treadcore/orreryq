//! The line, in words: what each stage takes and gives, and what each screen is for (Paul,
//! 1 November: "an explanation on each screen (collapsed by default) of what this screen does,
//! where it ties into which process, and why a visualization and data is presented ... what to
//! look for. Say the conditions of what we are simulating at that step, why that step helps the
//! entire brain").
//!
//! ONE TABLE. `tools/plans/line.json` is baked in here, read by the planner at each plan, and
//! drawn from by the lab report, so a screen, the queue's reasons and the report cannot tell
//! three stories. Words about the work live there, not in the drawing code.
//!
//! COLLAPSED, AND ONE LINE TALL. A panel always open is a panel nobody reads by the third day and
//! pixels taken from the work. Shut, it says in one line what the screen does, which is what a
//! person lost on it needs first. It shuts itself on the way to another screen, so it never
//! follows anybody round.

use crate::draw::Rgb;
use crate::font::{Font, F6X10, F8X13};
use crate::json;
use crate::ui::{rect, Rect, Ui};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::OnceLock;

pub const TABLE: &str = include_str!("../tools/plans/line.json");

/// A frame for review draws the panel open: it exists only after a click otherwise.
pub static FRAME_OPEN: AtomicBool = AtomicBool::new(false);

fn table() -> &'static json::Value {
    static T: OnceLock<json::Value> = OnceLock::new();
    T.get_or_init(|| json::parse(TABLE).expect("tools/plans/line.json parses: a test proves it"))
}

fn word(v: &json::Value, k: &str) -> &'static str {
    // The table lives as long as the program; the borrow below is of that.
    let s: &str = v.get(k).and_then(|x| x.as_str()).unwrap_or("");
    unsafe { std::mem::transmute::<&str, &'static str>(s) }
}

fn list(k: &str) -> &'static [json::Value] {
    table().get(k).and_then(|x| x.as_array()).unwrap_or(&[])
}

#[derive(Debug, Clone, Copy)]
pub struct Stage {
    pub id: &'static str,
    pub title: &'static str,
    pub track: &'static str,
    pub col: i32,
    pub row: i32,
    pub input: &'static str,
    pub output: &'static str,
    pub simulates: &'static str,
    pub why: &'static str,
    pub adds: &'static str,
    pub queued: &'static str,
}

pub fn stages() -> Vec<Stage> {
    list("stages")
        .iter()
        .map(|s| Stage {
            id: word(s, "id"),
            title: word(s, "title"),
            track: word(s, "track"),
            col: s.get("col").and_then(|x| x.as_num()).unwrap_or(0.0) as i32,
            row: s.get("row").and_then(|x| x.as_num()).unwrap_or(0.0) as i32,
            input: word(s, "input"),
            output: word(s, "output"),
            simulates: word(s, "simulates"),
            why: word(s, "why"),
            adds: word(s, "adds"),
            queued: word(s, "queued"),
        })
        .collect()
}

/// (from, to, what passes).
pub fn edges() -> Vec<(&'static str, &'static str)> {
    list("edges")
        .iter()
        .filter_map(|e| {
            let a = e.as_array()?;
            let w = |i: usize| -> &'static str {
                let s: &str = a[i].as_str().unwrap_or("");
                unsafe { std::mem::transmute::<&str, &'static str>(s) }
            };
            Some((w(0), w(1)))
        })
        .collect()
}

#[derive(Debug, Clone, Copy)]
pub struct Value {
    /// On Settings, Long run, and not on Queue, Values.
    pub long: bool,
    pub up: &'static str,
    pub down: &'static str,
    pub key: &'static str,
    pub label: &'static str,
    pub default: f64,
    pub min: f64,
    pub max: f64,
    pub step: f64,
    pub unit: &'static str,
    pub what: &'static str,
}

pub fn values() -> Vec<Value> {
    list("values")
        .iter()
        .map(|v| {
            let n = |k: &str| v.get(k).and_then(|x| x.as_num()).unwrap_or(0.0);
            Value { long: v.get("long").and_then(|x| x.as_bool()).unwrap_or(false), up: word(v, "up"), down: word(v, "down"), key: word(v, "key"), label: word(v, "label"), default: n("default"), min: n("min"), max: n("max"), step: n("step"), unit: word(v, "unit"), what: word(v, "what") }
        })
        .collect()
}

/// A stage's colour on the timeline. Fixed by stage, never by rank, so a stage that is absent
/// does not repaint the others; the legend names each, so colour never stands alone.
pub fn colour(stage: &str) -> Rgb {
    match stage {
        "first" | "search" => 0x2a78d6,
        "read" => 0x1baf7a,
        "held" => 0xeb6834,
        "families" | "promote" => 0xeda100,
        "build" => 0x6250d6,
        "proof" | "anchor" => 0xe87ba4,
        "transform" => 0x008300,
        "islands" => 0xc0c0c0,
        _ => 0x707070,
    }
}

/// The name a stage goes by where there is room for only a word.
pub fn short(stage: &str) -> &'static str {
    match stage {
        "first" => "First read",
        "read" => "Read on",
        "held" => "Held-out",
        "families" => "Families",
        "promote" => "Tests",
        "build" => "Build",
        "proof" => "Proof",
        "anchor" => "Anchor",
        "transform" => "Transform",
        "islands" => "GPU island",
        _ => "Asked for",
    }
}

/// Lines of a text within a width, at a face.
pub fn wrap(text: &str, font: &Font, w: i32) -> Vec<String> {
    let mut out = Vec::new();
    let mut line = String::new();
    for word in text.split_whitespace() {
        let next = if line.is_empty() { word.to_string() } else { format!("{} {}", line, word) };
        if font.measure(&next) as i32 > w && !line.is_empty() {
            out.push(std::mem::replace(&mut line, word.to_string()));
        } else {
            line = next;
        }
    }
    if !line.is_empty() {
        out.push(line);
    }
    out
}

/// One screen's six answers, in the order a person asks them.
pub fn about(key: &str) -> Option<[(&'static str, &'static str); 6]> {
    let s = list("screens").iter().find(|s| word(s, "key") == key)?;
    Some([
        ("What this screen does", word(s, "does")),
        ("Where it ties in", word(s, "ties")),
        ("Why it is drawn this way", word(s, "drawn")),
        ("What to look for", word(s, "look")),
        ("What is being simulated", word(s, "sim")),
        ("Why it helps the brain", word(s, "helps")),
    ])
}

/// The bar, and under it the panel when open. Returns what is left for the screen.
pub fn about_bar(ui: &mut Ui, body: Rect, key: &str) -> Rect {
    let Some(a) = about(key) else { return body };
    let t = ui.t;
    if ui.s.about_key != key {
        ui.s.about_key = key.to_string();
        ui.s.about_open = false;
    }
    let open = ui.s.about_open || FRAME_OPEN.load(Ordering::Relaxed);
    // The inspector's switch, at the bar's end, where every screen has it. The chord too.
    let sw = rect(body.right() - 118, body.y + 1, 116, 18);
    let bar = rect(body.x, body.y, body.w - 120, 20);
    if ui.f.chord(crate::surface::Sym::Char('i')) {
        ui.s.inspect_off = !ui.s.inspect_off;
    }
    let hot = ui.is_hot(bar);
    ui.c.rect(bar.x, bar.y, bar.w, bar.h, if hot { t.tile } else { t.panel });
    ui.c.hline(bar.x, bar.bottom() - 1, bar.w, t.line);
    let sign = if open { "-" } else { "+" };
    let said = if open { format!("{} About this screen: close", sign) } else { format!("{} About this screen: {}", sign, a[0].1) };
    ui.label_in(bar.x + 8, bar.y + 3, bar.w - 16, &said, &F8X13, if t.metal { t.ink } else { t.dim });
    if ui.button_hit(bar) {
        ui.s.about_open = !ui.s.about_open;
    }
    ui.c.rect(sw.x - 2, body.y, sw.w + 4, 20, t.panel);
    ui.c.hline(sw.x - 2, body.y + 19, sw.w + 4, t.line);
    let on = ui.inspecting();
    ui.c.rect(sw.x + 4, sw.y + 5, 8, 8, if on { t.up } else { t.dim });
    ui.label(sw.x + 16, sw.y + 2, if on { "Inspector on" } else { "Inspector off" }, &F8X13, if t.metal { t.ink } else { t.dim });
    if ui.button_hit(sw) {
        ui.s.inspect_off = !ui.s.inspect_off;
    }
    ui.tip(sw, || vec![
        "The inspector".to_string(),
        "Hover over almost any number, bar, cell or row: it says what it is, where it came from and what it means. Cut-off text shows in full.".to_string(),
        "Press here, or the platform's command key and I, to turn it off or on.".to_string(),
    ]);
    let below = rect(body.x, bar.bottom(), body.w, body.h - bar.h);
    if !open {
        return below;
    }
    // Three columns where they fit, each read top to bottom in the order a person asks.
    let cols = if body.w >= 1000 { 3 } else { 2 };
    let gap = 16;
    let col_w = (body.w - 16 - gap * (cols - 1)) / cols;
    let lh = F8X13.height as i32 + 1;
    let wrapped: Vec<Vec<String>> = a.iter().map(|(_, text)| wrap(text, &F8X13, col_w)).collect();
    let per = (a.len() as i32 + cols - 1) / cols;
    let col_h = |c: i32| -> i32 {
        (0..per).filter_map(|r| wrapped.get((c * per + r) as usize)).map(|w| lh * (w.len() as i32 + 1) + 6).sum()
    };
    let h = ((0..cols).map(col_h).max().unwrap_or(0) + 10).min(below.h - 60).max(40);
    let panel = rect(below.x, below.y, below.w, h);
    ui.c.rect(panel.x, panel.y, panel.w, panel.h, t.tile);
    ui.c.hline(panel.x, panel.bottom() - 1, panel.w, t.line);
    for c in 0..cols {
        let x = panel.x + 8 + c * (col_w + gap);
        let mut y = panel.y + 6;
        for r in 0..per {
            let i = (c * per + r) as usize;
            let Some(w) = wrapped.get(i) else { continue };
            if y + lh > panel.bottom() {
                break;
            }
            ui.label_in(x, y, col_w, a[i].0, &F8X13, t.ink);
            y += lh;
            for l in w {
                if y + lh > panel.bottom() {
                    break;
                }
                ui.label_in(x, y, col_w, l, &F8X13, t.dim);
                y += lh;
            }
            y += 6;
        }
    }
    rect(below.x, panel.bottom(), below.w, below.h - h)
}

/// The small face: for a box on the flow, where a line of the big face would not fit.
pub fn small(ui: &mut Ui, x: i32, y: i32, w: i32, s: &str, c: Rgb) {
    ui.label_in(x, y, w, s, &F6X10, c);
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::nav::View;

    #[test]
    fn the_table_parses_and_every_word_in_it_has_a_glyph() {
        assert!(json::parse(TABLE).is_ok());
        assert!(!stages().is_empty() && !values().is_empty());
        // A character no font has is a blank cell, found only by looking.
        for c in TABLE.chars().filter(|c| !c.is_whitespace()) {
            assert!(F8X13.glyph(c).iter().any(|r| *r != 0), "{:?} draws nothing", c);
        }
    }

    #[test]
    fn every_screen_has_all_six_answers() {
        let mut keys: Vec<String> = Vec::new();
        for v in View::ALL {
            match v {
                View::Queue => keys.extend(["Queue/Fleet", "Queue/Runs"].map(String::from)),
                View::Pipeline => keys.extend(crate::pipeline::PAGES.iter().map(|p| format!("Pipeline/{}", p))),
                View::Results => {
                    keys.extend(["Results/Candidates", "Results/Found", "Results/Net", "Results/Flags"].map(String::from));
                    keys.extend(crate::analysis::TABS.iter().map(|t| format!("Results/Algorhythm/{}", t)));
                }
                View::Settings => keys.extend(["Settings/Keeper", "Settings/Long run", "Settings/Commits"].map(String::from)),
                other => keys.push(other.title().to_string()),
            }
        }
        for k in &keys {
            let a = about(k).unwrap_or_else(|| panic!("{} is not explained", k));
            for (q, text) in a {
                assert!(!text.is_empty(), "{}: {} is empty", k, q);
            }
        }
    }

    #[test]
    fn an_edge_joins_two_stages_that_exist() {
        let ids: Vec<&str> = stages().iter().map(|s| s.id).collect();
        for (a, b) in edges() {
            assert!(ids.contains(&a) && ids.contains(&b), "{} to {}", a, b);
        }
    }

    #[test]
    fn a_value_starts_inside_its_range_and_can_step() {
        for v in values() {
            assert!(v.min <= v.default && v.default <= v.max && v.step > 0.0, "{}", v.key);
        }
    }

    #[test]
    fn a_line_never_outruns_its_width_unless_one_word_does() {
        for l in wrap("what each stage takes and gives", &F8X13, 90) {
            assert!(F8X13.measure(&l) as i32 <= 90 || !l.contains(' '), "{}", l);
        }
    }
}
