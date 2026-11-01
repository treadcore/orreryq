//! The Pipeline: one process on one screen (Paul, 1 November: "a single coherent process ...
//! like a gantt chart, showing dependency, machine name, and expected duration, and their
//! sequence with arrows ... Agile Kanban ... the one with most dependencies denoted as next
//! essential").
//!
//! IT DRAWS AND DECIDES NOTHING. The planner writes `plan/pipeline.json` at each plan, its
//! durations the medians the fleet measured, and picks the next essential itself, so the board
//! and the queue cannot disagree. A task nobody has built says NOT BUILT, in the same place a
//! running one says who runs it: an honest gap on the chart is the point of having a chart.

use crate::draw::Rgb;
use crate::font::{F10X20, F6X10, F8X13};
use crate::json;
use crate::line;
use crate::nav;
use crate::ui::{rect, Rect, Ui};

/// The pages of the line, after the Queue's own keys in one column: order, data, time, why, how hard.
pub const PAGES: [&str; 5] = ["Board", "Flow", "Timeline", "Queued", "Values"];
/// The Queue's own pages, first in the same column.
pub const QUEUE_KEYS: [&str; 2] = ["Fleet", "Runs"];

pub fn column_keys(page: usize) -> Vec<nav::Key> {
    let mut k: Vec<nav::Key> = QUEUE_KEYS.iter().map(|p| nav::Key { label: p.to_string(), on: false, lamp: None }).collect();
    k.extend(PAGES.iter().enumerate().map(|(i, p)| nav::Key { label: p.to_string(), on: i == page, lamp: None }));
    k
}

/// What a person has chosen here, across frames.
#[derive(Debug, Default)]
pub struct State {
    pub page: usize,
    pub operator: bool,
    /// The box open on the Flow page, and the trial traced under it.
    pub node: Option<usize>,
    pub trace: usize,
    pub queued_off: usize,
    /// "KEY VALUE" for fleet-tune.py, for main to run.
    pub tune: Option<String>,
    /// What it said.
    pub said: String,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Bar {
    pub from: f64,
    pub to: f64,
    pub stage: String,
    /// 1 finished, 0 failed or sent back, 2 running.
    pub ok: i64,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Lane {
    pub host: String,
    pub up: bool,
    pub past: Vec<Bar>,
    pub next: Vec<Bar>,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Mark {
    pub at: f64,
    pub kind: String,
    pub text: String,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Waiting {
    pub stage: String,
    pub title: String,
    pub state: String,
    pub host: String,
    pub age: f64,
    pub high: bool,
    pub why: String,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Read {
    pub stage: String,
    pub job: String,
    pub host: String,
    pub ended: String,
    pub seeds: f64,
    pub d: f64,
    pub se: f64,
    pub z: f64,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Trace {
    pub trial: String,
    pub note: String,
    pub moved: String,
    pub reads: Vec<Read>,
    pub run: String,
    pub status: String,
    pub why: String,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Flowing {
    pub jobs: f64,
    pub hours: f64,
    pub queued: f64,
    pub running: f64,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Task {
    pub id: String,
    pub title: String,
    pub state: String,
    pub deps: Vec<String>,
    pub machines: Vec<String>,
    pub dur: f64,
    pub start: f64,
    pub end: f64,
    pub dependents: i64,
    pub essential: bool,
    pub note: String,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Model {
    pub tasks: Vec<Task>,
    pub checked: String,
    pub commit: String,
    pub held_z: f64,
    pub generations: i64,
    pub dry_min: f64,
    pub eases_at_min: f64,
    pub line: i64,
    pub down: Vec<String>,
    /// (key, value now, moved by a person).
    pub values: Vec<(String, f64, bool)>,
    pub flow: Vec<(String, Flowing)>,
    pub past_h: f64,
    pub lanes: Vec<Lane>,
    pub marks: Vec<Mark>,
    pub queued: Vec<Waiting>,
    pub traces: Vec<Trace>,
}

fn s(v: &json::Value, k: &str) -> String {
    v.get(k).and_then(|x| x.as_str()).unwrap_or("").to_string()
}
fn n(v: &json::Value, k: &str) -> f64 {
    v.get(k).and_then(|x| x.as_num()).unwrap_or(0.0)
}
fn words(v: &json::Value, k: &str) -> Vec<String> {
    v.get(k).and_then(|x| x.as_array()).map(|a| a.iter().filter_map(|x| x.as_str().map(String::from)).collect()).unwrap_or_default()
}

impl Model {
    pub fn parse(text: &str) -> Model {
        let Ok(v) = json::parse(text) else { return Model::default() };
        let d = v.get("difficulty");
        let dn = |k: &str| d.and_then(|x| x.get(k)).and_then(|x| x.as_num()).unwrap_or(0.0);
        let tasks = v.get("tasks").and_then(|x| x.as_array()).map(|a| {
            a.iter().map(|t| Task {
                id: s(t, "id"),
                title: s(t, "title"),
                state: s(t, "state"),
                deps: words(t, "deps"),
                machines: words(t, "machines"),
                dur: n(t, "dur_min"),
                start: n(t, "start_min"),
                end: n(t, "end_min"),
                dependents: n(t, "dependents") as i64,
                essential: t.get("essential").and_then(|x| x.as_bool()).unwrap_or(false),
                note: s(t, "note"),
            }).collect()
        }).unwrap_or_default();
        Model {
            tasks,
            checked: s(&v, "checked"),
            commit: s(&v, "commit"),
            held_z: dn("held_z"),
            generations: dn("generations") as i64,
            dry_min: dn("dry_min"),
            eases_at_min: dn("eases_at_min"),
            line: v.get("line").and_then(|x| x.get("promotions")).and_then(|x| x.as_num()).unwrap_or(0.0) as i64,
            down: words(&v, "down"),
            values: list(&v, "values").iter().map(|x| (s(x, "key"), n(x, "value"), x.get("moved").and_then(|b| b.as_bool()).unwrap_or(false))).collect(),
            flow: match v.get("flow") {
                Some(json::Value::Obj(m)) => m.iter().map(|(k, x)| (k.clone(), Flowing { jobs: n(x, "jobs"), hours: n(x, "hours"), queued: n(x, "queued"), running: n(x, "running") })).collect(),
                _ => Vec::new(),
            },
            past_h: v.get("timeline").map(|x| n(x, "past_h")).unwrap_or(0.0),
            lanes: v.get("timeline").map(|t| list(t, "lanes").iter().map(|l| Lane {
                host: s(l, "host"),
                up: l.get("up").and_then(|b| b.as_bool()).unwrap_or(false),
                past: bars(l, "past"),
                next: bars(l, "next"),
            }).collect()).unwrap_or_default(),
            marks: v.get("timeline").map(|t| list(t, "marks").iter().map(|m| Mark { at: n(m, "at"), kind: s(m, "kind"), text: s(m, "text") }).collect()).unwrap_or_default(),
            queued: list(&v, "queued").iter().map(|q| Waiting {
                stage: s(q, "stage"), title: s(q, "title"), state: s(q, "state"), host: s(q, "host"), age: n(q, "age_min"),
                high: q.get("high").and_then(|b| b.as_bool()).unwrap_or(false), why: s(q, "why"),
            }).collect(),
            traces: list(&v, "traces").iter().map(|t| {
                let e = t.get("ended");
                let es = |k: &str| e.and_then(|x| x.get(k)).and_then(|x| x.as_str()).unwrap_or("").to_string();
                Trace {
                    trial: s(t, "trial"), note: s(t, "note"), moved: s(t, "moved"),
                    reads: list(t, "reads").iter().map(|r| Read {
                        stage: s(r, "stage"), job: s(r, "job"), host: s(r, "host"), ended: s(r, "ended"),
                        seeds: n(r, "seeds"), d: n(r, "d"), se: n(r, "se"), z: n(r, "z"),
                    }).collect(),
                    run: es("run"), status: es("status"), why: es("why"),
                }
            }).collect(),
        }
    }
}

fn list<'a>(v: &'a json::Value, k: &str) -> &'a [json::Value] {
    v.get(k).and_then(|x| x.as_array()).unwrap_or(&[])
}

fn bars(l: &json::Value, k: &str) -> Vec<Bar> {
    list(l, k).iter().filter_map(|b| {
        let a = b.as_array()?;
        Some(Bar {
            from: a.first()?.as_num()?,
            to: a.get(1)?.as_num()?,
            stage: a.get(2)?.as_str()?.to_string(),
            ok: a.get(3).and_then(|x| x.as_num()).unwrap_or(1.0) as i64,
        })
    }).collect()
}

/// Minutes as a person reads them.
pub fn took(min: f64) -> String {
    if min < 1.0 {
        "<1 min".to_string()
    } else if min < 90.0 {
        format!("{:.0} min", min)
    } else {
        format!("{:.1} h", min / 60.0)
    }
}

/// Machines in the width of a card: the first few, then how many more.
pub fn who(machines: &[String], room: usize) -> String {
    if machines.is_empty() {
        return "no machine".to_string();
    }
    let mut out = String::new();
    for (i, m) in machines.iter().enumerate() {
        let next = if out.is_empty() { m.clone() } else { format!("{}, {}", out, m) };
        if next.len() + 8 > room && i > 0 {
            return format!("{} +{}", out, machines.len() - i);
        }
        out = next;
    }
    out
}

fn colour(ui: &Ui, state: &str) -> Rgb {
    let t = ui.t;
    match state {
        "running" => t.up,
        "blocked" | "not built" => t.alarm,
        "done" => t.line,
        "ready" => t.accent,
        _ => t.dim,
    }
}

/// An arrow from the end of one bar to the start of a later one: out, down or up, in, a head.
fn arrow(ui: &mut Ui, (x0, y0): (i32, i32), (x1, y1): (i32, i32), c: Rgb) {
    let mid = if x1 - x0 >= 14 { x1 - 8 } else { x0 + 6 };
    ui.c.hline(x0, y0, (mid - x0).max(0) + 1, c);
    let (top, bot) = (y0.min(y1), y0.max(y1));
    ui.c.vline(mid, top, bot - top + 1, c);
    if mid <= x1 {
        ui.c.hline(mid, y1, x1 - mid + 1, c);
    } else {
        ui.c.hline(x1, y1, mid - x1 + 1, c);
    }
    // The point at the bar it enters: a head with its wide end there points the wrong way.
    for k in 0..5 {
        ui.c.vline(x1 - 1 - k, y1 - k, 2 * k + 1, c);
    }
}

fn gantt(ui: &mut Ui, at: Rect, m: &Model) {
    let t = ui.t;
    // The words in a column of their own: an arrow leaves a bar's end, and a label there is
    // struck through by the first one.
    let label_w = (at.w * 2 / 5).clamp(320, 520);
    let dur_w = 80;
    let n_ = m.tasks.len().max(1) as i32;
    let row = ((at.h - 20) / n_).clamp(14, 30);
    let span = m.tasks.iter().map(|x| x.end).fold(60.0_f64, f64::max);
    let past = m.tasks.iter().map(|x| x.start).fold(0.0_f64, f64::min).max(-15.0);
    let (x0, w) = (at.x + label_w, at.w - label_w - 12);
    let px = |min: f64| x0 + (((min.max(past) - past) / (span - past)) * w as f64) as i32;
    // The axis, every quarter of an hour or so, and now.
    let step = [15.0, 30.0, 60.0, 120.0, 240.0, 480.0].into_iter().find(|s| span / s <= 8.0).unwrap_or(960.0);
    let mut k = 0.0;
    while k <= span {
        let x = px(k);
        ui.c.vline(x, at.y + 16, row * n_, t.line);
        ui.label(x + 2, at.y, &if k == 0.0 { "now".to_string() } else { took(k) }, &F8X13, t.dim);
        k += step;
    }
    let y_of = |i: usize| at.y + 18 + row * i as i32;
    // Arrows under the bars, so a bar is never struck through.
    for (i, x) in m.tasks.iter().enumerate() {
        for d in &x.deps {
            if let Some(j) = m.tasks.iter().position(|o| &o.id == d) {
                let from = (px(m.tasks[j].end).max(x0) + 1, y_of(j) + row / 2);
                let to = (px(x.start).max(x0), y_of(i) + row / 2);
                arrow(ui, from, to, t.accent);
            }
        }
    }
    for (i, x) in m.tasks.iter().enumerate() {
        let y = y_of(i);
        let fg = if x.state == "done" { t.dim } else { t.ink };
        let lab = if x.state == "not built" { "NOT BUILT".to_string() } else if x.state == "done" { "done".to_string() } else { took(x.dur) };
        let right = at.x + label_w - 8;
        ui.label_right(right, y + (row - 13) / 2, &lab, &F8X13, if x.essential || x.state == "not built" { t.alarm } else { t.dim });
        ui.label_in(at.x + 4, y + (row - 13) / 2, label_w - dur_w - 12, &format!("{}  {}", x.title, who(&x.machines, 14)), &F8X13, fg);
        let (a, b) = (px(x.start), px(x.end));
        let c = colour(ui, &x.state);
        let bar = rect(a, y + 3, (b - a).max(4), (row - 6).max(4));
        ui.c.rect(bar.x, bar.y, bar.w, bar.h, c);
        if x.essential {
            ui.outline2(rect(bar.x - 3, bar.y - 2, bar.w + 6, bar.h + 4), t.alarm);
        }
        ui.tip(rect(at.x, y, at.w, row), || task_tip(x));
    }
}

/// A task, in full: the words a bar or a card has no room for.
fn task_tip(x: &Task) -> Vec<String> {
    let mut out = vec![x.title.clone(), format!("State: {}{}", x.state, if x.essential { ". NEXT ESSENTIAL: free this first" } else { "" })];
    if !x.note.is_empty() {
        out.push(x.note.clone());
    }
    out.push(format!("Machines: {}", if x.machines.is_empty() { "none".to_string() } else { x.machines.join(", ") }));
    if x.dur > 0.0 {
        out.push(format!("Takes about {}: the median the fleet measured in the last day. Starts {}, ends {} from now.", took(x.dur), signed(x.start), signed(x.end)));
    }
    if !x.deps.is_empty() {
        out.push(format!("Waits on: {}", x.deps.join(", ")));
    }
    out.push(format!("{} later tasks depend on it. Source: plan/pipeline.json, written at each plan.", x.dependents));
    out
}

fn signed(min: f64) -> String {
    if min < 0.0 { format!("{} ago", took(-min)) } else if min == 0.0 { "now".to_string() } else { format!("in {}", took(min)) }
}

const COLUMNS: [(&str, &[&str]); 4] =
    [("Blocked or not built", &["blocked", "not built"]), ("Waiting", &["waiting", "ready"]), ("Running", &["running"]), ("Done", &["done"])];

fn kanban(ui: &mut Ui, at: Rect, m: &Model) {
    let t = ui.t;
    let gap = 8;
    let w = (at.w - gap * 3) / 4;
    for (i, (name, states)) in COLUMNS.iter().enumerate() {
        let col = rect(at.x + (w + gap) * i as i32, at.y, w, at.h);
        ui.c.rect(col.x, col.y, col.w, col.h, t.panel);
        let cards: Vec<&Task> = m.tasks.iter().filter(|x| states.contains(&x.state.as_str())).collect();
        ui.label(col.x + 8, col.y + 5, &format!("{}  {}", name, cards.len()), &F8X13, t.ink);
        let card_h = 62;
        let room = ((col.h - 26) / (card_h + 5)).max(1) as usize;
        let mut y = col.y + 24;
        for x in cards.iter().take(room) {
            let c = rect(col.x + 6, y, col.w - 12, card_h);
            ui.c.rect(c.x, c.y, c.w, c.h, t.tile);
            ui.c.rect(c.x, c.y, 4, c.h, colour(ui, &x.state));
            if x.essential {
                ui.outline2(c, t.alarm);
            }
            ui.label_in(c.x + 10, c.y + 3, c.w - 14, &x.title, &F8X13, t.ink);
            let cols = ((c.w - 14) / 8).max(8) as usize;
            ui.label_in(c.x + 10, c.y + 17, c.w - 14, &format!("{} | {}", who(&x.machines, cols.saturating_sub(10)), if x.dur > 0.0 { took(x.dur) } else { "no estimate".into() }), &F8X13, t.dim);
            ui.label_in(c.x + 10, c.y + 31, c.w - 14, &x.note, &F8X13, t.dim);
            let foot = if x.essential { format!("NEXT ESSENTIAL: {} depend on it", x.dependents) } else { format!("{} depend on it", x.dependents) };
            ui.label_in(c.x + 10, c.y + 45, c.w - 14, &foot, &F8X13, if x.essential { t.alarm } else { t.dim });
            ui.tip(c, || task_tip(x));
            y += card_h + 5;
        }
        if cards.len() > room {
            ui.label_right(col.right() - 8, col.y + 5, &format!("{} more", cards.len() - room), &F8X13, t.ink);
        }
    }
}

/// The Board: the essential task's line, the chart, and the cards.
fn board(ui: &mut Ui, at: Rect, m: &Model) {
    let t = ui.t;
    ui.c.rect(at.x, at.y, at.w, at.h, t.base);
    if m.tasks.is_empty() {
        ui.label(at.x + 8, at.y + 8, "The planner has not written the board yet: it does at each plan, about a minute.", &F8X13, t.dim);
        return;
    }
    let next = m.tasks.iter().find(|x| x.essential);
    let line = next.map(|x| format!("Next essential: {}. {} depend on it", x.title, x.dependents)).unwrap_or_else(|| "Nothing is holding the line".into());
    ui.label_in(at.x + 4, at.y + 2, at.w - 8, &line, &F10X20, t.alarm);
    let z = format!(
        "generation {} at {}: passes at held z {:.2}; {} since the last, easier at {}; {} carried, unproven{}",
        m.generations, m.commit, m.held_z, took(m.dry_min), took(m.eases_at_min), m.line,
        if m.down.is_empty() { String::new() } else { format!("; down: {}", m.down.join(", ")) },
    );
    ui.label_in(at.x + 4, at.y + 25, at.w - 8, &z, &F8X13, t.dim);
    let (_, rest) = at.cut_top(44);
    // As tall as its rows need, and the board takes the rest: a card hidden is a task hidden.
    let chart_h = (20 + 24 * m.tasks.len() as i32).min(rest.h * 3 / 5).max(180);
    let (chart, board) = rest.cut_top(chart_h);
    gantt(ui, chart, m);
    kanban(ui, rect(board.x, board.y + 6, board.w, board.h - 6), m);
}

/// The screen: whichever page of the line.
pub fn draw(ui: &mut Ui, at: Rect, m: &Model, st: &mut State) {
    let at = at.inset(10);
    let t = ui.t;
    ui.c.rect(at.x, at.y, at.w, at.h, t.base);
    match st.page {
        1 => flow(ui, at, m, st),
        2 => timeline(ui, at, m),
        3 => queued(ui, at, m, st),
        4 => values(ui, at, m, st),
        _ => board(ui, at, m),
    }
}

fn flowing<'a>(m: &'a Model, id: &str) -> Option<&'a Flowing> {
    m.flow.iter().find(|(k, _)| k == id).map(|(_, f)| f)
}

/// The Flow: every stage as a box, the road between them, and under them the box chosen and one
/// real trial's numbers as they moved. A BOX NOTHING FLOWS OUT OF IS THE POINT OF THE PICTURE: the
/// red ones are where the fleet's work stops short of treadcore.
fn flow(ui: &mut Ui, at: Rect, m: &Model, st: &mut State) {
    let t = ui.t;
    let stages = line::stages();
    let (cols, rows) = (8, 4);
    let top = (at.h * 11 / 20).clamp(240, 330);
    let (grid, rest) = at.cut_top(top);
    let (gx, gy) = (12, 12);
    let w = (grid.w - gx * (cols - 1)) / cols;
    let h = (grid.h - 12 - gy * (rows - 1)) / rows;
    let cell = |s: &line::Stage| rect(grid.x + s.col * (w + gx), grid.y + 12 + s.row * (h + gy), w, h);
    let at_id = |id: &str| stages.iter().find(|s| s.id == id).map(cell);
    // The road, under the boxes.
    for (a, b) in line::edges() {
        let (Some(ra), Some(rb)) = (at_id(a), at_id(b)) else { continue };
        let c = if a == "bridge" || a == "slot" || b == "slot" || b == "bridge" { t.alarm } else { t.accent };
        if rb.x <= ra.x && rb.y == ra.y {
            // Round the top and back: the new generation is the next one's baseline.
            let y = ra.y - 7;
            ui.c.vline(ra.x + ra.w / 2, y, 8, c);
            ui.c.hline(rb.x + rb.w / 2, y, ra.x + ra.w / 2 - rb.x - rb.w / 2, c);
            ui.c.vline(rb.x + rb.w / 2, y, 8, c);
        } else if rb.x > ra.x {
            arrow(ui, (ra.right(), ra.y + ra.h / 2), (rb.x, rb.y + rb.h / 2), c);
        } else if rb.y > ra.y {
            ui.c.vline(ra.x + ra.w / 2, ra.bottom(), rb.y - ra.bottom(), c);
        } else {
            // Up and back: the anchor's old values re-enter at the first read.
            let y = ra.y + ra.h / 2;
            ui.c.hline(rb.x + rb.w / 2, y, ra.x - rb.x - rb.w / 2, c);
            ui.c.vline(rb.x + rb.w / 2, rb.bottom(), y - rb.bottom(), c);
        }
    }
    for (i, s) in stages.iter().enumerate() {
        let r = cell(s);
        let f = flowing(m, s.id);
        let gap = s.output.starts_with("NOT BUILT");
        let chosen = st.node == Some(i);
        ui.c.rect(r.x, r.y, r.w, r.h, if chosen { t.panel } else { t.tile });
        ui.c.rect(r.x, r.y, 4, r.h, line::colour(s.id));
        if gap {
            ui.outline2(r, t.alarm);
        } else if chosen {
            ui.outline2(r, t.accent);
        } else {
            ui.outline(r, t.line);
        }
        let mut y = r.y + 3;
        for l in line::wrap(s.title, &F8X13, r.w - 10).iter().take(2) {
            ui.label_in(r.x + 8, y, r.w - 10, l, &F8X13, t.ink);
            y += 13;
        }
        let word = if gap {
            "NOT BUILT".to_string()
        } else if let Some(f) = f {
            format!("{:.0} jobs, {:.0} h", f.jobs, f.hours)
        } else {
            match s.id {
                "search" => "the fit, the A/B".to_string(),
                "main" | "brain" => "the game".to_string(),
                _ => String::new(),
            }
        };
        if y + 10 <= r.bottom() {
            ui.label_in(r.x + 8, y, r.w - 10, &word, &F6X10, if gap { t.alarm } else { t.dim });
            y += 10;
        }
        if let Some(f) = f.filter(|f| f.running + f.queued > 0.0) {
            if y + 10 <= r.bottom() {
                ui.label_in(r.x + 8, y, r.w - 10, &format!("{:.0} on, {:.0} waiting", f.running, f.queued), &F6X10, t.dim);
            }
        }
        if ui.button_hit(r) {
            st.node = Some(i);
        }
        ui.tip(r, || {
            let mut v = vec![s.title.to_string(), format!("Takes: {}", s.input), format!("Gives: {}", s.output), format!("Simulates: {}", s.simulates), format!("For treadcore: {}", s.adds)];
            if let Some(f) = f {
                v.push(format!("Last day: {:.0} jobs, {:.1} machine-hours. Now: {:.0} running, {:.0} waiting.", f.jobs, f.hours, f.running, f.queued));
            }
            v.push("Click to pin these words below.".to_string());
            v
        });
    }
    // Under it: the box, and one trial.
    let rest = rect(rest.x, rest.y + 6, rest.w, rest.h - 6);
    let lw = rest.w * 2 / 5;
    let left = rect(rest.x, rest.y, lw - 8, rest.h);
    let right = rect(rest.x + lw, rest.y, rest.w - lw, rest.h);
    ui.c.rect(left.x, left.y, left.w, left.h, t.tile);
    let i = st.node.unwrap_or_else(|| stages.iter().position(|s| s.id == "held").unwrap_or(0));
    if let Some(s) = stages.get(i) {
        let mut y = left.y + 5;
        ui.label_in(left.x + 8, y, left.w - 16, s.title, &F8X13, t.ink);
        y += 16;
        for (q, a) in [("Takes", s.input), ("Gives", s.output), ("Simulates", s.simulates), ("Why", s.why), ("For treadcore", s.adds)] {
            let text = format!("{}: {}", q, a);
            for l in line::wrap(&text, &F8X13, left.w - 16) {
                if y + 13 > left.bottom() {
                    break;
                }
                ui.label_in(left.x + 8, y, left.w - 16, &l, &F8X13, if q == "For treadcore" { t.ink } else { t.dim });
                y += 14;
            }
            y += 2;
        }
    }
    trace(ui, right, m, st);
}

/// One trial through the line: each read, its machine and time, and the z it stood at, then how
/// it ended. A number going from question to commit, or to nothing, is the whole story of the fleet.
fn trace(ui: &mut Ui, at: Rect, m: &Model, st: &mut State) {
    let t = ui.t;
    ui.c.rect(at.x, at.y, at.w, at.h, t.tile);
    if m.traces.is_empty() {
        ui.label_in(at.x + 8, at.y + 6, at.w - 16, "No trial has reached a held-out read in the last day.", &F8X13, t.dim);
        return;
    }
    let cw = 60;
    for (i, tr) in m.traces.iter().enumerate() {
        let r = rect(at.x + 6 + i as i32 * (cw + 3), at.y + 4, cw, 20);
        if r.right() > at.right() {
            break;
        }
        if ui.button(r, &tr.trial, st.trace != i) {
            st.trace = i;
        }
    }
    let tr = &m.traces[st.trace.min(m.traces.len() - 1)];
    let mut y = at.y + 28;
    ui.label_in(at.x + 8, y, at.w - 16, &tr.note, &F8X13, t.ink);
    y += 14;
    ui.label_in(at.x + 8, y, at.w - 16, &tr.moved, &F8X13, t.dim);
    y += 17;
    let c = [10, 92, 152, 258, 304, 352, 472];
    for (x, h) in c.iter().zip(["stage", "job", "machine", "at", "seeds", "reads", "z"]) {
        ui.label(at.x + x, y, h, &F8X13, t.dim);
    }
    y += 14;
    for r in &tr.reads {
        if y + 14 > at.bottom() - 16 {
            break;
        }
        ui.c.rect(at.x + 2, y + 2, 4, 9, line::colour(&r.stage));
        ui.label_in(at.x + c[0], y, 80, line::short(&r.stage), &F8X13, t.ink);
        ui.label_in(at.x + c[1], y, 58, &r.job, &F8X13, t.dim);
        ui.label_in(at.x + c[2], y, 102, &r.host, &F8X13, t.dim);
        ui.label(at.x + c[3], y, &r.ended, &F8X13, t.dim);
        ui.label(at.x + c[4], y, &format!("{:.0}", r.seeds), &F8X13, t.dim);
        ui.label(at.x + c[5], y, &format!("{:+.2} +/- {:.2}", r.d, r.se), &F8X13, t.dim);
        let zx = at.x + c[6];
        ui.label(zx, y, &format!("{:+.2}", r.z), &F8X13, t.ink);
        // A bar from nothing, to its side: right is for the trial.
        let w = (at.right() - zx - 60).max(0);
        if w > 20 {
            let mid = zx + 50 + w / 2;
            let len = ((r.z.abs() / 3.0).min(1.0) * (w / 2) as f64) as i32;
            ui.c.vline(mid, y, 12, t.line);
            if r.z >= 0.0 {
                ui.c.rect(mid + 1, y + 3, len, 7, t.up);
            } else {
                ui.c.rect(mid - len, y + 3, len, 7, t.alarm);
            }
        }
        ui.tip(rect(at.x, y, at.w, 14), || vec![
            format!("{}: {}", line::short(&r.stage), r.job),
            format!("Read on {}, finished at {}: {:.0} seeds gave {:+.2} +/- {:.2} points a seat, trial less baseline.", r.host, r.ended, r.seeds, r.d, r.se),
            if r.stage == "held" { format!("z {:+.2} is this read alone, on seeds no search has seen.", r.z) } else { format!("z {:+.2} pools every read so far, by inverse variance.", r.z) },
            format!("Source: results/{}/.../pooled.txt.", r.job),
        ]);
        y += 14;
    }
    let end = match tr.status.as_str() {
        "" => "Ended: dropped at its read, or still waiting on a bar.".to_string(),
        "failed" => format!("Ended: {} failed. {}", tr.run, tr.why),
        s => format!("Ended: {} {}.", tr.run, s),
    };
    ui.label_in(at.x + 8, at.bottom() - 15, at.w - 16, &end, &F8X13, if tr.status == "failed" { t.alarm } else { t.ink });
}

/// The Timeline: measured on the left of now, forecast on the right, each at its own scale,
/// because six hours past and an hour ahead on one scale leave the forecast too thin to read.
fn timeline(ui: &mut Ui, at: Rect, m: &Model) {
    let t = ui.t;
    if m.lanes.is_empty() {
        ui.label_in(at.x + 4, at.y + 4, at.w - 8, "The planner has not written the timeline yet: it does at each plan, about a minute.", &F8X13, t.dim);
        return;
    }
    let label_w = 130;
    let head = 30;
    let foot = 40;
    let plot = rect(at.x + label_w, at.y + head, at.w - label_w - 4, at.h - head - foot);
    let n_ = m.lanes.len() as i32;
    let row = (plot.h / n_.max(1)).clamp(10, 46);
    let now_x = plot.x + plot.w * 7 / 10;
    let past_min = m.past_h.max(1.0) * 60.0;
    let ahead_min = m.lanes.iter().flat_map(|l| l.next.iter().map(|b| b.to)).fold(30.0_f64, f64::max).min(240.0);
    let xof = |min: f64| -> i32 {
        if min <= 0.0 {
            now_x + ((min.max(-past_min) / past_min) * (now_x - plot.x) as f64) as i32
        } else {
            now_x + ((min.min(ahead_min) / ahead_min) * (plot.right() - now_x) as f64) as i32
        }
    };
    let plot_h = row * n_;
    // The axis: hours back, and minutes on.
    let mut h = -(m.past_h as i32);
    while h < 0 {
        let x = xof(h as f64 * 60.0);
        ui.c.vline(x, plot.y, plot_h, t.line);
        ui.label(x + 2, plot.y - 14, &format!("{} h", h), &F8X13, t.dim);
        h += 1;
    }
    let step = [15.0, 30.0, 60.0].into_iter().find(|s| ahead_min / s <= 4.0).unwrap_or(120.0);
    let mut k = step;
    while k <= ahead_min {
        let x = xof(k);
        ui.c.vline(x, plot.y, plot_h, t.line);
        if x + 60 < plot.right() {
            ui.label(x + 2, plot.y - 14, &format!("+{}", took(k)), &F8X13, t.dim);
        }
        k += step;
    }
    ui.label(at.x + 4, at.y, "measured, each machine", &F8X13, t.ink);
    ui.label(now_x + 4, at.y, "forecast from medians", &F8X13, t.ink);
    for (i, l) in m.lanes.iter().enumerate() {
        let y = plot.y + i as i32 * row;
        ui.label_in(at.x + 4, y + (row - 13) / 2, label_w - 8, &l.host, &F8X13, if l.up { t.ink } else { t.alarm });
        ui.c.hline(plot.x, y + row - 1, plot.w, t.line);
        for b in &l.past {
            let (a, e) = (xof(b.from), xof(b.to));
            let r = rect(a, y + 1, (e - a).max(1), row - 3);
            ui.c.rect(r.x, r.y, r.w, r.h, if b.ok == 0 { t.alarm } else { line::colour(&b.stage) });
            ui.tip(r, || vec![
                format!("{}: {}", l.host, line::short(&b.stage)),
                format!("From {} to {}{}.", signed(b.from), if b.to >= 0.0 { "now".to_string() } else { signed(b.to) }, match b.ok { 0 => ", failed or sent back", 2 => ", still running", _ => "" }),
                "Touching jobs of one stage are drawn as one bar.".to_string(),
                "Source: events.jsonl, as measured.".to_string(),
            ]);
        }
        for b in &l.next {
            // Hollow: it has not happened.
            let (a, e) = (xof(b.from), xof(b.to));
            let r = rect(a, y + 2, (e - a - 1).max(2), row - 5);
            ui.outline(r, line::colour(&b.stage));
            ui.tip(r, || vec![
                format!("{}: {}, forecast", l.host, line::short(&b.stage)),
                format!("Would start {} and end {}, at the median of the last day.", signed(b.from), signed(b.to)),
                "No job is given to a machine until it is free, so this is a guess at the order, not a plan.".to_string(),
            ]);
        }
    }
    ui.c.vline(now_x, plot.y - 2, plot_h + 4, t.ink);
    ui.c.vline(now_x + 1, plot.y - 2, plot_h + 4, t.ink);
    ui.label(now_x - 12, plot.y + plot_h + 2, "now", &F8X13, t.ink);
    for mk in &m.marks {
        let x = xof(mk.at);
        let c = match mk.kind.as_str() {
            "generation" => t.up,
            "failed" => t.alarm,
            _ => t.warn,
        };
        ui.c.vline(x, plot.y - 2, plot_h + 2, c);
        ui.c.rect(x - 2, plot.y - 5, 5, 5, c);
        ui.tip(rect(x - 3, plot.y - 6, 7, plot_h + 6), || vec![
            match mk.kind.as_str() {
                "generation" => format!("A generation: {}", mk.text),
                "failed" => format!("A passed candidate stopped: {}", mk.text),
                "eases" => "The bars ease here, if nothing passes first".to_string(),
                _ => "The next read of the line against main".to_string(),
            },
            signed(mk.at),
        ]);
    }
    // The key: every colour named, and what a mark means.
    let mut x = at.x + 4;
    let y = at.bottom() - foot + 18;
    for k in ["first", "read", "held", "families", "build", "proof", "transform", "islands", "other"] {
        ui.c.rect(x, y + 2, 10, 10, line::colour(k));
        x = ui.label(x + 13, y, line::short(k), &F8X13, t.dim) + 10;
    }
    let say = "Red bar: failed or sent back. Hollow: forecast. Green line: a generation. Red line: tests stopped one. Amber: bars ease, or the next proof.";
    ui.label_in(at.x + 4, y + 14, at.w - 8, say, &F8X13, t.dim);
}

/// The Queued page: what runs and what waits, in order, each with why it is there.
fn queued(ui: &mut Ui, at: Rect, m: &Model, st: &mut State) {
    let t = ui.t;
    if m.queued.is_empty() {
        ui.label_in(at.x + 4, at.y + 4, at.w - 8, "Nothing is running or waiting that the planner has reported.", &F8X13, t.dim);
        return;
    }
    let running = m.queued.iter().filter(|q| q.state == "running").count();
    ui.label_in(at.x + 4, at.y, at.w - 8, &format!("{} running, then {} waiting in the order they will go. Each says why it is here.", running, m.queued.len() - running), &F8X13, t.ink);
    let area = rect(at.x, at.y + 18, at.w, at.h - 18);
    let row_h = 34;
    let mut off = st.queued_off;
    let (list_at, first, count) = ui.scroll_list(area, m.queued.len(), row_h, &mut off);
    st.queued_off = off;
    for (i, q) in m.queued.iter().enumerate().skip(first).take(count) {
        let y = list_at.y + (i - first) as i32 * row_h;
        let r = rect(list_at.x, y, list_at.w, row_h - 2);
        ui.c.rect(r.x, r.y, r.w, r.h, t.tile);
        ui.c.rect(r.x, r.y, 4, r.h, line::colour(&q.stage));
        let who = if q.state == "running" { format!("{} for {}", q.host, took(q.age)) } else if q.host.is_empty() { "next free machine".to_string() } else { format!("waits for {}", q.host) };
        let right = 240;
        ui.label_in(r.x + 10, r.y + 2, 90, line::short(&q.stage), &F8X13, t.ink);
        ui.label_in(r.x + 100, r.y + 2, r.w - 100 - right, &q.title, &F8X13, if q.state == "running" { t.up } else { t.ink });
        ui.label_right(r.right() - 8, r.y + 2, &format!("{}{}", if q.high { "first: " } else { "" }, who), &F8X13, t.dim);
        ui.label_in(r.x + 100, r.y + 17, r.w - 110, &q.why, &F8X13, t.dim);
        ui.tip(r, || vec![
            q.title.clone(),
            format!("Stage: {}. {}", line::short(&q.stage), who),
            q.why.clone(),
            if q.high { "High priority: it goes ahead of the search, because it decides.".to_string() } else { "Takes its turn in the queue.".to_string() },
        ]);
    }
}

fn number(v: f64, step: f64) -> String {
    if step >= 1.0 { format!("{:.0}", v) } else if step >= 0.1 { format!("{:.2}", v) } else { format!("{:.2}", v) }
}

/// The Values: one row each, with a press to move it a step. HELD TO THE TABLE'S RANGE HERE, at the
/// tool and in the planner, so a number cannot be pressed past where it was simulated.
fn values(ui: &mut Ui, at: Rect, m: &Model, st: &mut State) {
    let t = ui.t;
    let head = "What sets how hard a generation is. A press is live at the next plan, about a minute; no job restarts.";
    ui.label_in(at.x + 4, at.y, at.w - 8, head, &F8X13, t.ink);
    let say = if st.said.is_empty() { format!("Held z now {:.2}. tools/plans/difficulty-sim.py simulates what a value buys.", m.held_z) } else { st.said.clone() };
    ui.label_in(at.x + 4, at.y + 15, at.w - 8, &say, &F8X13, t.dim);
    let table = line::values();
    let mut y = at.y + 36;
    let row_h = ((at.h - 36) / table.len().max(1) as i32).clamp(30, 46);
    let (lab, val, btn) = (220, 104, 28);
    for v in &table {
        let r = rect(at.x, y, at.w, row_h - 3);
        ui.c.rect(r.x, r.y, r.w, r.h, t.tile);
        let now_ = m.values.iter().find(|x| x.0 == v.key);
        let (cur, moved) = now_.map(|x| (x.1, x.2)).unwrap_or((v.default, false));
        ui.label_in(r.x + 8, r.y + 3, lab - 10, v.label, &F8X13, t.ink);
        ui.label_in(r.x + 8, r.y + 17, lab - 10, &format!("from {} to {}, default {}", number(v.min, v.step), number(v.max, v.step), number(v.default, v.step)), &F6X10, t.dim);
        let mut x = r.x + lab;
        ui.label_right(x + val - 8, r.y + 3, &format!("{} {}", number(cur, v.step), v.unit), &F8X13, if moved { t.warn } else { t.ink });
        if moved {
            ui.label_right(x + val - 8, r.y + 17, "moved", &F6X10, t.warn);
        }
        x += val;
        if st.operator {
            let by = r.y + (r.h - 22) / 2;
            let down = (cur - v.step).max(v.min);
            let up = (cur + v.step).min(v.max);
            if ui.button(rect(x, by, btn, 22), "-", cur > v.min) {
                st.tune = Some(format!("{} {}", v.key, down));
            }
            if ui.button(rect(x + btn + 3, by, btn, 22), "+", cur < v.max) {
                st.tune = Some(format!("{} {}", v.key, up));
            }
            if moved && ui.button(rect(x + 2 * btn + 6, by, 62, 22), "Default", true) {
                st.tune = Some(format!("{} default", v.key));
            }
        }
        x += 2 * btn + 6 + 70;
        let lines = line::wrap(v.what, &F8X13, r.right() - x - 8);
        let room = ((r.h - 2) / 14).max(1) as usize;
        for (i, l) in lines.iter().take(room).enumerate() {
            ui.label_in(x, r.y + 1 + i as i32 * 14, r.right() - x - 8, l, &F8X13, t.dim);
        }
        ui.tip(r, || vec![
            format!("{}: {} {}{}", v.label, number(cur, v.step), v.unit, if moved { ", moved by a person" } else { "" }),
            v.what.to_string(),
            format!("Raise it: {}.", v.up),
            format!("Lower it: {}.", v.down),
            format!("Key: {}. Default {}, from {} to {}, a step of {}. Kept in QUEUE/tuning.json.", v.key, number(v.default, v.step), number(v.min, v.step), number(v.max, v.step), v.step),
        ]);
        y += row_h;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const DOC: &str = r#"{"commit":"abc1234","checked":"t","difficulty":{"held_z":0.5,"generations":3,"dry_min":12,"eases_at_min":240},
      "line":{"promotions":2},"down":["jaguaribe"],
      "tasks":[{"id":"a","title":"A","state":"running","deps":[],"machines":["m1"],"dur_min":5,"start_min":-1,"end_min":4,"dependents":1,"essential":false,"note":""},
               {"id":"b","title":"B","state":"not built","deps":["a"],"machines":[],"dur_min":0,"start_min":4,"end_min":4,"dependents":0,"essential":true,"note":"gap"}]}"#;

    #[test]
    fn a_page_of_the_line_and_its_data_reach_the_model() {
        let doc = r#"{"tasks":[],"values":[{"key":"harden","value":0.07,"moved":true}],
          "flow":{"held":{"jobs":3,"hours":1.5,"queued":1,"running":0}},
          "timeline":{"past_h":6,"lanes":[{"host":"m","up":true,"past":[[-5,-4,"first",1],[-4,-3,"read",0]],"next":[[0,2,"held"]]}],"marks":[{"at":-3,"kind":"generation","text":"r1"}]},
          "queued":[{"stage":"held","title":"T","state":"queued","host":"","age_min":0,"high":true,"why":"W"}],
          "traces":[{"trial":"w1","note":"n","moved":"a = 1","reads":[{"stage":"first","job":"w1","host":"m","ended":"09:00","seeds":55,"d":1.0,"se":0.5,"z":2.0}],"ended":{"run":"r1","status":"failed","why":"tests"}}]}"#;
        let m = Model::parse(doc);
        assert_eq!(m.values[0], ("harden".to_string(), 0.07, true));
        assert_eq!(m.lanes[0].past[1].ok, 0);
        assert_eq!(m.lanes[0].next[0].stage, "held");
        assert_eq!(m.marks[0].kind, "generation");
        assert!(m.queued[0].high);
        assert_eq!((m.traces[0].reads[0].z, m.traces[0].status.as_str()), (2.0, "failed"));
    }

    #[test]
    fn the_columns_keys_are_the_queues_then_the_lines_and_one_is_lit() {
        let k = column_keys(2);
        assert_eq!(k.len(), QUEUE_KEYS.len() + PAGES.len());
        assert_eq!(k.iter().filter(|x| x.on).count(), 1);
        assert_eq!(k[QUEUE_KEYS.len() + 2].label, "Timeline");
    }

    #[test]
    fn the_board_reads_what_the_planner_wrote_and_chooses_nothing() {
        let m = Model::parse(DOC);
        assert_eq!(m.tasks.len(), 2);
        assert_eq!(m.tasks[1].deps, vec!["a".to_string()]);
        assert!(m.tasks[1].essential && !m.tasks[0].essential);
        assert_eq!((m.generations, m.line), (3, 2));
    }

    #[test]
    fn a_board_that_is_not_there_is_an_empty_board_not_a_panic() {
        assert!(Model::parse("no fleet").tasks.is_empty());
    }

    #[test]
    fn a_duration_is_said_as_a_person_says_it() {
        assert_eq!(took(0.4), "<1 min");
        assert_eq!(took(30.0), "30 min");
        assert_eq!(took(180.0), "3.0 h");
    }

    #[test]
    fn machines_that_will_not_fit_are_counted_not_cut() {
        let ms: Vec<String> = ["saskatchewan", "boburner", "calber"].iter().map(|x| x.to_string()).collect();
        assert_eq!(who(&ms, 20), "saskatchewan +2");
        assert_eq!(who(&[], 20), "no machine");
    }
}
