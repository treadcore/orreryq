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
pub const PAGES: [&str; 8] = ["Board", "Flow", "Timeline", "Queued", "Values", "Blame", "Lineup", "Hit Parade"];
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
    /// The chain the Timeline follows, kept by a click: a trial, a run, an island.
    pub chain: Option<String>,
    /// The Timeline's zoom, an index of ZOOMS; none is the six hours.
    pub zoom: Option<usize>,
    /// The Blame page's queues folded by a click; the rest stand open.
    pub blame_shut: Vec<String>,
    /// The machine, or the machine and job, a click keeps at the table.
    pub blame_keep: Option<(String, Option<String>)>,
    /// The Lineup: its zoom (0 the hour, 1 the six hours; none the six), the kind of chain, its
    /// scroll and the chains folded by a click.
    pub lineup_zoom: Option<usize>,
    pub lineup_kind: usize,
    pub lineup_off: usize,
    pub lineup_shut: Vec<String>,
    /// The Lineup's ending shown: 0 every one, 1 going, 2 won, 3 dead ends.
    pub lineup_end: usize,
    /// The Hit Parade's window: 0 today, 1 the last seven days, 2 since the log began.
    pub parade_win: usize,
    pub blame_off: usize,
}

/// The Timeline's zooms, nearest first. The hour and the six hours draw each job; a day and longer
/// draw the planner's bins of the event log.
pub const ZOOMS: [&str; 6] = ["hour", "hours", "day", "days", "weeks", "months"];

/// A zoom of a day or longer: its bins, a lane a machine, each bin its index from the left edge and
/// its stages' percentages, busiest first.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct ZoomLevel {
    pub name: String,
    pub bin_min: f64,
    /// The left edge, minutes from now.
    pub from_min: f64,
    /// Where the event log begins, minutes from now: nothing before it is known.
    pub begins: Option<f64>,
    pub lanes: Vec<(String, Vec<(usize, Vec<(String, f64)>)>)>,
    /// (minutes from now, what the axis says there; empty for a tick alone).
    pub ticks: Vec<(f64, String)>,
    /// (minutes from now, minutes the wall clock read more before it): each change of summer time.
    pub shifts: Vec<(f64, f64)>,
    /// Each lane's watts at the wall in each bin; none before the event log begins.
    pub watts: Vec<(String, Vec<Option<f64>>)>,
}

/// A chain as the planner's chain_meta says it: its kind, how it ended (good: a success; not: a dead
/// end; none: still going), that in words, and its queued jobs as the forecast deals them.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct ChainMeta {
    pub id: String,
    pub kind: String,
    pub good: Option<bool>,
    pub say: String,
    pub next: Vec<NextJob>,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct NextJob {
    pub from: Option<f64>,
    pub to: Option<f64>,
    pub stage: String,
    pub id: String,
    pub host: String,
}

/// A counter of the Hit Parade: jobs done, not done, their minutes and their watt-hours.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Tally {
    pub done: f64,
    pub failed: f64,
    pub minutes: f64,
    pub wh: f64,
}

/// A window of the Hit Parade: the hours it covers, and each machine's tally by kind of job.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct ParadeWindow {
    pub name: String,
    pub hours: f64,
    pub cells: Vec<(String, Vec<(String, Tally)>)>,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Parade {
    pub windows: Vec<ParadeWindow>,
    pub since: String,
    /// (day, done, not done, watt-hours).
    pub days: Vec<(String, f64, f64, f64)>,
}

/// THE FLEET'S WATTS AND WHAT THEY COST (Paul, 5 November), as the planner's power_view says from
/// tools/power.py's model and its samples: each lane's watts now, the fleet's now and at full tilt,
/// the last day's kilowatt-hours and their price, and each box's model and how much of it is measured.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Power {
    pub rate: f64,
    pub lanes_now: Vec<(String, f64)>,
    pub fleet_now: f64,
    pub fleet_full: f64,
    pub kwh_24h: f64,
    pub usd_24h: f64,
    pub usd_30d: f64,
    /// (lane, jobs handed off today, their watt-hours).
    pub jobs_today: Vec<(String, f64, f64)>,
    pub boxes: Vec<BoxPower>,
    pub sampled: String,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct BoxPower {
    pub name: String,
    pub cpu: String,
    pub gpu: String,
    pub full: f64,
    pub now: f64,
    pub busy_util: Option<f64>,
    pub gpu_busy: Option<f64>,
    pub cpu_samples: f64,
    pub gpu_samples: f64,
    pub why: String,
}

impl Power {
    pub fn lane_now(&self, lane: &str) -> Option<f64> {
        self.lanes_now.iter().find(|(h, _)| h == lane).map(|(_, w)| *w)
    }
    pub fn today(&self, lane: &str) -> Option<(f64, f64)> {
        self.jobs_today.iter().find(|(h, _, _)| h == lane).map(|(_, n, wh)| (*n, *wh))
    }
    /// The box a lane is part of: a GPU lane's is its name less "-cuda".
    pub fn box_of(&self, lane: &str) -> Option<&BoxPower> {
        let b = lane.strip_suffix("-cuda").unwrap_or(lane);
        self.boxes.iter().find(|x| x.name == b)
    }
}

impl ZoomLevel {
    /// The wall clock of `min` minutes from `checked`, as it read then: summer time and all.
    pub fn stamp(&self, checked: &str, min: f64) -> String {
        stamp(checked, min + self.shifts.iter().filter(|(at, _)| min < *at).map(|(_, d)| d).sum::<f64>())
    }
}

/// A GPU island's way back to the game: the milestone it must pass, how near its exams of the last
/// six hours came (errors; it needs +2), their median's climb a day, and the hours that climb needs.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct CudaReturn {
    pub top: String,
    pub top_made: String,
    pub segments: f64,
    pub best: Option<f64>,
    pub median: Option<f64>,
    pub per_day: Option<f64>,
    pub eta_h: Option<f64>,
    pub seg_min: Option<f64>,
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
    /// Each job alone, with its chain, for following one through the fleet.
    pub jobs: Vec<JobBar>,
}

/// One job on the Timeline: when it ran (minutes from now), its stage, how it ended, its id, and
/// the chain it is a link of (the planner's `chain_of`).
#[derive(Debug, Clone, Default, PartialEq)]
pub struct JobBar {
    pub from: f64,
    pub to: f64,
    pub stage: String,
    pub ok: i64,
    pub id: String,
    pub chain: String,
    /// The job it follows, where the planner knows it and the times cannot say; empty otherwise.
    pub after: String,
    /// Its energy, watt-hours at the wall: its lane's watts busy for the minutes it ran.
    pub wh: Option<f64>,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Mark {
    pub at: f64,
    pub kind: String,
    pub text: String,
    /// The date and clock it happened, as the planner says it.
    pub when: String,
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

/// A machine at the round table (the Blame page): what it runs, how busy it was, and how much of
/// that went to the small returnable reads it takes from the queue when its own line waits.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Seat {
    pub host: String,
    pub gpu: bool,
    pub state: String,
    pub job: String,
    pub stage: String,
    pub for_min: f64,
    pub busy: f64,
    pub help: f64,
    pub by_stage: Vec<(String, f64)>,
    pub backup: String,
}

/// Queued jobs dealt to `from` that wait on `to`: its turn, its build, or a job `to` runs.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Wait {
    pub from: String,
    pub to: String,
    pub kind: String,
    pub n: i64,
    pub jobs: Vec<String>,
}

/// A run handed back to the planner: its last job came back, its next is not asked yet.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Handed {
    pub run: String,
    pub kind: String,
    pub host: String,
    pub job: String,
    pub for_min: f64,
}

/// A chain's measured handoff: minutes for the planner, in the queue, and working, medians of a day.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Handoff {
    pub chain: String,
    pub n: f64,
    pub planner: f64,
    pub queue: f64,
    pub work: f64,
}

/// A job in a machine's queue on the Blame page: what it is, when the forecast starts it, and the
/// job it waits on and where that job is.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct QJob {
    pub id: String,
    pub title: String,
    pub stage: String,
    /// running, or queued.
    pub state: String,
    /// turn, build, after, or "no machine"; empty for the running one.
    pub wait: String,
    pub on: String,
    pub on_host: String,
    /// Minutes from now: when it began (running, negative), or the forecast's start and end.
    pub start: Option<f64>,
    pub end: Option<f64>,
    pub high: bool,
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Blame {
    /// Each machine's queue: what it runs, then what is dealt it, in order.
    pub queues: Vec<(String, Vec<QJob>)>,
    /// Queued jobs no machine that is up can take.
    pub unplaced: Vec<QJob>,
    pub seats: Vec<Seat>,
    pub waits: Vec<Wait>,
    pub planner: Vec<Handed>,
    pub handoffs: Vec<Handoff>,
    pub queued: f64,
    pub plan_s: f64,
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
    /// The dials a person holds (QUEUE/hold.json): a trial there waits for a person.
    pub held: Vec<(String, f64)>,
    pub flow: Vec<(String, Flowing)>,
    pub past_h: f64,
    /// When the planner measured the timeline, the moment its minutes count from; else `checked`.
    pub timeline_at: String,
    pub lanes: Vec<Lane>,
    pub marks: Vec<Mark>,
    pub zoom: Vec<ZoomLevel>,
    pub cuda: Vec<(String, CudaReturn)>,
    pub power: Power,
    pub chains: Vec<ChainMeta>,
    pub parade: Parade,
    pub queued: Vec<Waiting>,
    pub traces: Vec<Trace>,
    pub blame: Blame,
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
            held: match v.get("held") {
                Some(json::Value::Obj(m)) => m.iter().map(|(k, x)| (k.clone(), x.as_num().unwrap_or(0.0))).collect(),
                _ => Vec::new(),
            },
            flow: match v.get("flow") {
                Some(json::Value::Obj(m)) => m.iter().map(|(k, x)| (k.clone(), Flowing { jobs: n(x, "jobs"), hours: n(x, "hours"), queued: n(x, "queued"), running: n(x, "running") })).collect(),
                _ => Vec::new(),
            },
            past_h: v.get("timeline").map(|x| n(x, "past_h")).unwrap_or(0.0),
            timeline_at: v.get("timeline").map(|x| s(x, "at")).filter(|x| !x.is_empty()).unwrap_or_else(|| s(&v, "checked")),
            lanes: v.get("timeline").map(|t| list(t, "lanes").iter().map(|l| Lane {
                host: s(l, "host"),
                up: l.get("up").and_then(|b| b.as_bool()).unwrap_or(false),
                past: bars(l, "past"),
                next: bars(l, "next"),
                jobs: list(l, "jobs").iter().filter_map(|j| j.as_array()).filter_map(|j| Some(JobBar {
                    from: j.first()?.as_num()?,
                    to: j.get(1)?.as_num()?,
                    stage: j.get(2)?.as_str()?.to_string(),
                    ok: j.get(3)?.as_num()? as i64,
                    id: j.get(4)?.as_str()?.to_string(),
                    chain: j.get(5)?.as_str()?.to_string(),
                    after: j.get(6).and_then(|x| x.as_str()).unwrap_or("").to_string(),
                    wh: j.get(7).and_then(|x| x.as_num()),
                })).collect(),
            }).collect()).unwrap_or_default(),
            marks: v.get("timeline").map(|t| list(t, "marks").iter().map(|m| Mark { at: n(m, "at"), kind: s(m, "kind"), text: s(m, "text"), when: s(m, "when") }).collect()).unwrap_or_default(),
            zoom: v.get("timeline").map(|t| list(t, "zoom").iter().map(|z| ZoomLevel {
                name: s(z, "name"),
                bin_min: n(z, "bin_min"),
                from_min: n(z, "from_min"),
                begins: z.get("begins_min").and_then(|x| x.as_num()),
                lanes: list(z, "lanes").iter().map(|l| (s(l, "host"), list(l, "bins").iter().filter_map(|b| b.as_array()).filter_map(|b| {
                    let i = b.first()?.as_num()? as usize;
                    Some((i, b[1..].chunks(2).filter_map(|p| Some((p.first()?.as_str()?.to_string(), p.get(1)?.as_num()?))).collect()))
                }).collect())).collect(),
                ticks: list(z, "ticks").iter().filter_map(|k| k.as_array()).filter_map(|k| Some((k.first()?.as_num()?, k.get(1)?.as_str()?.to_string()))).collect(),
                shifts: list(z, "shifts").iter().filter_map(|k| k.as_array()).filter_map(|k| Some((k.first()?.as_num()?, k.get(1)?.as_num()?))).collect(),
                watts: match z.get("watts") {
                    Some(json::Value::Obj(w)) => w.iter().map(|(k, x)| (k.clone(), x.as_array().map(|a| a.iter().map(|y| y.as_num()).collect()).unwrap_or_default())).collect(),
                    _ => Vec::new(),
                },
            }).collect()).unwrap_or_default(),
            power: v.get("timeline").and_then(|t| t.get("power")).map(|p| Power {
                rate: n(p, "rate"),
                lanes_now: match p.get("lanes_now") {
                    Some(json::Value::Obj(w)) => w.iter().filter_map(|(k, x)| Some((k.clone(), x.as_num()?))).collect(),
                    _ => Vec::new(),
                },
                fleet_now: n(p, "fleet_now_w"),
                fleet_full: n(p, "fleet_full_w"),
                kwh_24h: n(p, "kwh_24h"),
                usd_24h: n(p, "usd_24h"),
                usd_30d: n(p, "usd_30d"),
                jobs_today: match p.get("jobs_today") {
                    Some(json::Value::Obj(w)) => w.iter().filter_map(|(k, x)| {
                        let a = x.as_array()?;
                        Some((k.clone(), a.first()?.as_num()?, a.get(1)?.as_num()?))
                    }).collect(),
                    _ => Vec::new(),
                },
                boxes: list(p, "boxes").iter().map(|b| BoxPower {
                    name: s(b, "box"), cpu: s(b, "cpu"), gpu: s(b, "gpu"), full: n(b, "full_w"), now: n(b, "now_w"),
                    busy_util: b.get("busy_util").and_then(|x| x.as_num()), gpu_busy: b.get("gpu_busy_w").and_then(|x| x.as_num()),
                    cpu_samples: b.get("samples").map(|x| n(x, "cpu")).unwrap_or(0.0), gpu_samples: b.get("samples").map(|x| n(x, "gpu")).unwrap_or(0.0),
                    why: s(b, "why"),
                }).collect(),
                sampled: s(p, "sampled"),
            }).unwrap_or_default(),
            chains: match v.get("timeline").and_then(|t| t.get("chains")) {
                Some(json::Value::Obj(c)) => c.iter().map(|(k, x)| ChainMeta {
                    id: k.clone(), kind: s(x, "kind"), good: x.get("good").and_then(|b| b.as_bool()), say: s(x, "say"),
                    next: list(x, "next").iter().filter_map(|a| a.as_array()).filter_map(|a| Some(NextJob {
                        from: a.first()?.as_num(), to: a.get(1)?.as_num(), stage: a.get(2)?.as_str()?.to_string(),
                        id: a.get(3)?.as_str()?.to_string(), host: a.get(4)?.as_str().unwrap_or("").to_string(),
                    })).collect(),
                }).collect(),
                _ => Vec::new(),
            },
            parade: v.get("timeline").and_then(|t| t.get("parade")).map(|p| Parade {
                windows: PARADE_WINDOWS.iter().filter_map(|w| p.get(w).map(|x| ParadeWindow {
                    name: w.to_string(),
                    hours: n(x, "hours"),
                    cells: match x.get("cells") {
                        Some(json::Value::Obj(c)) => c.iter().map(|(h, ks)| (h.clone(), match ks {
                            json::Value::Obj(k) => k.iter().filter_map(|(s_, a)| {
                                let a = a.as_array()?;
                                Some((s_.clone(), Tally { done: a.first()?.as_num()?, failed: a.get(1)?.as_num()?, minutes: a.get(2)?.as_num()?, wh: a.get(3)?.as_num()? }))
                            }).collect(),
                            _ => Vec::new(),
                        })).collect(),
                        _ => Vec::new(),
                    },
                })).collect(),
                since: s(p, "since"),
                days: list(p, "days").iter().filter_map(|d| d.as_array()).filter_map(|d| Some((d.first()?.as_str()?.to_string(), d.get(1)?.as_num()?, d.get(2)?.as_num()?, d.get(3)?.as_num()?))).collect(),
            }).unwrap_or_default(),
            cuda: match v.get("timeline").and_then(|t| t.get("cuda")) {
                Some(json::Value::Obj(c)) => c.iter().map(|(k, x)| (k.clone(), CudaReturn {
                    top: s(x, "top"), top_made: s(x, "top_made"), segments: n(x, "segments"),
                    best: x.get("best").and_then(|y| y.as_num()), median: x.get("median").and_then(|y| y.as_num()),
                    per_day: x.get("per_day").and_then(|y| y.as_num()), eta_h: x.get("eta_h").and_then(|y| y.as_num()),
                    seg_min: x.get("seg_min").and_then(|y| y.as_num()),
                })).collect(),
                _ => Vec::new(),
            },
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
            blame: v.get("blame").map(|b| Blame {
                seats: list(b, "nodes").iter().map(|x| Seat {
                    host: s(x, "host"), gpu: x.get("gpu").and_then(|g| g.as_bool()).unwrap_or(false), state: s(x, "state"),
                    job: s(x, "job"), stage: s(x, "stage"), for_min: n(x, "for_min"), busy: n(x, "busy_pct"), help: n(x, "help_pct"),
                    by_stage: list(x, "by_stage").iter().filter_map(|p| p.as_array()).filter_map(|p| Some((p.first()?.as_str()?.to_string(), p.get(1)?.as_num()?))).collect(),
                    backup: s(x, "backup"),
                }).collect(),
                waits: list(b, "edges").iter().map(|e| Wait { from: s(e, "from"), to: s(e, "to"), kind: s(e, "kind"), n: n(e, "n") as i64, jobs: words(e, "jobs") }).collect(),
                planner: list(b, "planner").iter().map(|h| Handed { run: s(h, "run"), kind: s(h, "kind"), host: s(h, "host"), job: s(h, "job"), for_min: n(h, "for_min") }).collect(),
                handoffs: match b.get("handoffs") {
                    Some(json::Value::Obj(m)) => m.iter().map(|(k, x)| Handoff { chain: k.clone(), n: n(x, "n"), planner: n(x, "planner_min"), queue: n(x, "queue_min"), work: n(x, "work_min") }).collect(),
                    _ => Vec::new(),
                },
                queued: n(b, "queued"),
                plan_s: n(b, "plan_s"),
                queues: match b.get("queues") {
                    Some(json::Value::Obj(q)) => q.iter().map(|(k, x)| (k.clone(), x.as_array().map(|a| a.iter().map(qjob).collect()).unwrap_or_default())).collect(),
                    _ => Vec::new(),
                },
                unplaced: list(b, "unplaced").iter().map(qjob).collect(),
            }).unwrap_or_default(),
        }
    }
}

fn qjob(x: &json::Value) -> QJob {
    QJob {
        id: s(x, "id"), title: s(x, "title"), stage: s(x, "stage"), state: s(x, "state"), wait: s(x, "wait"), on: s(x, "on"), on_host: s(x, "on_host"),
        start: x.get("start_min").and_then(|y| y.as_num()), end: x.get("end_min").and_then(|y| y.as_num()),
        high: x.get("high").and_then(|y| y.as_bool()).unwrap_or(false),
    }
}

impl Blame {
    /// A machine's queue, or none.
    pub fn queue_of(&self, host: &str) -> &[QJob] {
        self.queues.iter().find(|(h, _)| h == host).map(|(_, v)| v.as_slice()).unwrap_or(&[])
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
    } else if min < 2880.0 {
        format!("{:.1} h", min / 60.0)
    } else {
        format!("{:.1} days", min / 1440.0)
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
        2 => timeline(ui, at, m, st),
        3 => queued(ui, at, m, st),
        4 => values(ui, at, m, st),
        5 => blame(ui, at, m, st),
        6 => lineup(ui, at, m, st),
        7 => parade(ui, at, m, st),
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
fn timeline(ui: &mut Ui, at: Rect, m: &Model, st: &mut State) {
    let t = ui.t;
    if m.lanes.is_empty() {
        ui.label_in(at.x + 4, at.y + 4, at.w - 8, "The planner has not written the timeline yet: it does at each plan, about a minute.", &F8X13, t.dim);
        return;
    }
    // THE ZOOM (Paul, 5 November: "maybe we can zoom timeline in and out. months, weeks, days, day,
    // hours, hour"). The hour and the six hours draw each job; a day and longer draw the planner's
    // bins of the event log, a column a bin, filled by the share of it each stage took.
    let z = st.zoom.unwrap_or(1).min(ZOOMS.len() - 1);
    for (i, name) in ZOOMS.iter().enumerate() {
        let r = rect(at.x + 4 + i as i32 * 64, at.y, 60, 20);
        if i == z {
            ui.c.rect(r.x + 4, r.bottom(), r.w - 8, 2, t.up);
        }
        if ui.button(r, name, i != z) {
            st.zoom = Some(i);
        }
    }
    let buttons_end = at.x + 4 + ZOOMS.len() as i32 * 64;
    let level = if z >= 2 { m.zoom.iter().find(|l| l.name == ZOOMS[z]) } else { None };
    if z >= 2 && level.is_none() {
        ui.label_in(at.x + 4, at.y + 30, at.w - 8, &format!("The planner has not written the {} yet: it does at its next pass, about a minute.", ZOOMS[z]), &F8X13, t.dim);
        return;
    }
    let label_w = 130;
    let head = 72;
    let foot = 52;
    let plot = rect(at.x + label_w, at.y + head, at.w - label_w - 4, at.h - head - foot);
    let n_ = m.lanes.len() as i32;
    // Under the rows, the fleet's watts: room kept for it first.
    let graph_h = if m.power.fleet_full > 0.0 { 96 } else { 0 };
    let row = ((plot.h - if graph_h > 0 { graph_h + 22 } else { 0 }) / n_.max(1)).clamp(10, 46);
    let now_x = plot.x + plot.w * 7 / 10;
    let past_min = match (z, level) {
        (0, _) => 60.0,
        (_, Some(l)) => -l.from_min,
        _ => m.past_h.max(1.0) * 60.0,
    };
    let ahead_min = m.lanes.iter().flat_map(|l| l.next.iter().map(|b| b.to)).fold(30.0_f64, f64::max).min(240.0);
    let xof = |min: f64| -> i32 {
        if min <= 0.0 {
            now_x + ((min.max(-past_min) / past_min) * (now_x - plot.x) as f64) as i32
        } else {
            now_x + ((min.min(ahead_min) / ahead_min) * (plot.right() - now_x) as f64) as i32
        }
    };
    let plot_h = row * n_;
    // The axis: the hour by ten minutes, the six hours by the hour, the longer ones by the
    // planner's own ticks (midnights, on the local clock).
    match level {
        Some(l) => {
            for (min, say) in &l.ticks {
                let x = xof(*min);
                ui.c.vline(x, plot.y, plot_h, t.line);
                if !say.is_empty() && x + 50 < now_x {
                    ui.label(x + 2, plot.y - 14, say, &F8X13, t.dim);
                }
            }
        }
        None => {
            let every = if z == 0 { 10.0 } else { 60.0 };
            let mut k = -past_min;
            while k < -0.5 {
                let x = xof(k);
                ui.c.vline(x, plot.y, plot_h, t.line);
                let say = if z == 0 { format!("{} min", k as i32) } else { format!("{} h", (k / 60.0) as i32) };
                ui.label(x + 2, plot.y - 14, &say, &F8X13, t.dim);
                k += every;
            }
        }
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
    ui.label(at.x + 4, plot.y - 14, if level.is_some() { "measured, binned" } else { "measured" }, &F8X13, t.ink);
    ui.label(now_x + 4, at.y + 3, "forecast from medians", &F8X13, t.ink);
    for (i, l) in m.lanes.iter().enumerate() {
        let y = plot.y + i as i32 * row;
        let lw = m.power.lane_now(&l.host);
        let two = lw.is_some() && row >= 28;
        ui.label_in(at.x + 4, y + (row - 13) / 2 - if two { 6 } else { 0 }, label_w - 8, &l.host, &F8X13, if l.up { t.ink } else { t.alarm });
        if let (true, Some(w)) = (two, lw) {
            ui.c.rect(at.x + 4, y + row / 2 + 6, 8, 8, heat(w / lane_top(m)));
            ui.label(at.x + 16, y + row / 2 + 5, &format!("{:.0} W now", w), &F6X10, t.dim);
        }
        ui.c.hline(plot.x, y + row - 1, plot.w, t.line);
        if let Some(lv) = level {
            // Before the event log begins nothing is known, and it says so by a hatch.
            if let Some(b) = lv.begins.filter(|b| *b > -past_min) {
                let x1 = xof(b);
                for yy in (y + 1)..(y + row - 2) {
                    for xx in plot.x..x1 {
                        if (xx + yy) % 6 == 0 {
                            ui.c.set(xx, yy, t.line);
                        }
                    }
                }
            }
            let bins = lv.lanes.iter().find(|(h, _)| h == &l.host).map(|(_, b)| b.as_slice()).unwrap_or(&[]);
            let full = row - 3;
            for (bi, parts) in bins {
                let a = lv.from_min + *bi as f64 * lv.bin_min;
                if a >= 0.0 {
                    continue;
                }
                // The newest bin is still filling: it ends at now, not in the forecast.
                let (x0, x1) = (xof(a), xof((a + lv.bin_min).min(0.0)));
                let (w, mut top, mut used) = ((x1 - x0).max(1), y + row - 2, 0);
                for (stage, pct) in parts {
                    let h = (((pct / 100.0) * full as f64).round() as i32).min(full - used);
                    if h > 0 {
                        ui.c.rect(x0, top - h, w, h, if stage == "failed" { t.alarm } else { line::colour(stage) });
                        top -= h;
                        used += h;
                    }
                }
            }
        } else {
            for b in l.past.iter().filter(|b| b.to >= -past_min) {
                let (a, e) = (xof(b.from), xof(b.to));
                let r = rect(a, y + 1, (e - a).max(1), row - 3);
                ui.c.rect(r.x, r.y, r.w, r.h, if b.ok == 0 { t.alarm } else { line::colour(&b.stage) });
                ui.tip(r, || vec![
                    format!("{}: {}", l.host, line::short(&b.stage)),
                    format!("From {} to {}{}.", signed(b.from), if b.to >= 0.0 { "now".to_string() } else { signed(b.to) }, match b.ok { 0 => ", failed or sent back", 2 => ", still running", _ => "" }),
                    "Touching jobs of one stage are drawn as one bar. Point at it to follow its chain.".to_string(),
                    "Source: events.jsonl, as measured.".to_string(),
                ]);
            }
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
    // Each lane's watts along its foot, and the fleet's under the rows: a day's five-minute bins for
    // the hour and the six hours, the zoom's own bins for the rest.
    if let Some(src) = level.or_else(|| m.zoom.iter().find(|l| l.name == "day")).filter(|l| !l.watts.is_empty()) {
        for (i, l) in m.lanes.iter().enumerate() {
            let Some((_, ws)) = src.watts.iter().find(|(h, _)| h == &l.host) else { continue };
            let y = plot.y + i as i32 * row + row - 4;
            for (k, w) in ws.iter().enumerate() {
                let a = src.from_min + k as f64 * src.bin_min;
                let Some(w) = w else { continue };
                if a >= 0.0 || a + src.bin_min < -past_min {
                    continue;
                }
                let (x0, x1) = (xof(a.max(-past_min)), xof((a + src.bin_min).min(0.0)));
                ui.c.rect(x0, y, (x1 - x0).max(1), 3, heat(w / lane_top(m)));
            }
        }
        if graph_h > 0 {
            let g = rect(plot.x, plot.y + plot_h + 18, plot.w, graph_h);
            power_graph(ui, m, src, g, rect(at.x + 4, g.y, label_w - 8, g.h), now_x, past_min, &xof);
        }
    }
    if let Some(lv) = level {
        if let Some(b) = lv.begins.filter(|b| *b > -past_min) {
            let say = format!("before {}: the event log begins there", lv.stamp(&m.timeline_at, b));
            let w = F8X13.measure(&say) as i32 + 8;
            if xof(b) - plot.x > w + 8 {
                let r = rect(plot.x + (xof(b) - plot.x - w) / 2, plot.y + plot_h / 2 - 8, w, 16);
                ui.c.rect(r.x, r.y, r.w, r.h, t.base);
                ui.label(r.x + 4, r.y + 1, &say, &F8X13, t.dim);
            }
        }
        bin_tip(ui, m, lv, plot, row, now_x, past_min, &xof);
    }
    ui.c.vline(now_x, plot.y - 2, plot_h + 4, t.ink);
    ui.c.vline(now_x + 1, plot.y - 2, plot_h + 4, t.ink);
    ui.label(now_x - 12, plot.y + plot_h + 2, "now", &F8X13, t.ink);
    milestones(ui, m, plot, plot_h, row, past_min, &xof, true);
    cuda_return(ui, m, plot, row, now_x);
    if level.is_none() {
        follow_chain(ui, m, st, plot, row, now_x, past_min, (buttons_end + 8, at.y + 3), &xof);
    }
    // The key: every colour named, and what a line means.
    let mut x = at.x + 4;
    let y = at.bottom() - foot + 8;
    for k in ["first", "read", "held", "families", "build", "proof", "transform", "islands", "other"] {
        ui.c.rect(x, y + 2, 10, 10, line::colour(k));
        x = ui.label(x + 13, y, line::short(k), &F8X13, t.dim) + 10;
    }
    ui.label_in(at.x + 4, y + 14, at.w - 8, "Hollow: forecast. Red: failed or sent back. A day and longer: a column is a bin, filled by the share of it each stage took; the rest is idle.", &F8X13, t.dim);
    ui.label_in(at.x + 4, y + 28, at.w - 8, "Lines: green a generation, thick green the line on main, red tests stopped one, grey a GPU milestone, white a net into the game, cyan the game's rules.", &F8X13, t.dim);
}

/// Paul's scale for watts (5 November: "showing graph color from blue to white to purple to yellow to
/// red"), 0 to 1 of the most there can be.
pub fn heat(f: f64) -> Rgb {
    const STOPS: [Rgb; 5] = [0x2a5bd7, 0xf0f0f0, 0x9b4fd0, 0xf2c200, 0xe8332a];
    let f = if f.is_finite() { f.clamp(0.0, 1.0) * 4.0 } else { 0.0 };
    let i = (f.floor() as usize).min(3);
    mix(STOPS[i], STOPS[i + 1], f - i as f64)
}

fn mix(a: Rgb, b: Rgb, t: f64) -> Rgb {
    let ch = |s: u32| -> u32 {
        let (x, y) = (((a >> s) & 0xff) as f64, ((b >> s) & 0xff) as f64);
        ((x + (y - x) * t.clamp(0.0, 1.0)).round() as u32) << s
    };
    ch(16) | ch(8) | ch(0)
}

/// A lane's watts are coloured against the hungriest box's full tilt, so a red row is red anywhere.
fn lane_top(m: &Model) -> f64 {
    m.power.boxes.iter().map(|b| b.full).fold(100.0, f64::max)
}

/// THE FLEET'S WATTS UNDER THE TIMELINE (Paul, 5 November: "an underlay graph underneath timeline").
/// A column a bin, as high as the fleet's watts at the wall then and coloured by them, blue at none,
/// red at full tilt; beside it what they cost. Estimated, and said so: the CPUs' use and the GPUs'
/// draw measured, the CPUs' watts the model's (tools/plans/power.json).
#[allow(clippy::too_many_arguments)]
fn power_graph(ui: &mut Ui, m: &Model, lv: &ZoomLevel, g: Rect, label: Rect, now_x: i32, past_min: f64, xof: &dyn Fn(f64) -> i32) {
    let t = ui.t;
    let p = &m.power;
    let top = p.fleet_full.max(1.0);
    let n = lv.watts.iter().map(|(_, v)| v.len()).max().unwrap_or(0);
    let total = |k: usize| -> Option<f64> {
        let v: Vec<f64> = lv.watts.iter().filter_map(|(_, w)| w.get(k).copied().flatten()).collect();
        if v.is_empty() { None } else { Some(v.iter().sum()) }
    };
    let mut wv = 500.0;
    while wv < top {
        let y = g.bottom() - (wv / top * g.h as f64) as i32;
        for x in (g.x..now_x).step_by(4) {
            ui.c.set(x, y, t.line);
        }
        wv += 500.0;
    }
    ui.c.hline(g.x, g.bottom(), now_x - g.x, t.line);
    for k in 0..n {
        let a = lv.from_min + k as f64 * lv.bin_min;
        if a >= 0.0 || a + lv.bin_min < -past_min {
            continue;
        }
        let Some(tot) = total(k) else { continue };
        let (x0, x1) = (xof(a.max(-past_min)), xof((a + lv.bin_min).min(0.0)));
        let h = ((tot / top) * g.h as f64).round() as i32;
        ui.c.rect(x0, g.bottom() - h, (x1 - x0).max(1), h, heat(tot / top));
    }
    // The scale's lines named over the columns, on a dark ground so they read over any colour.
    let mut wv = 500.0;
    while wv < top {
        let y = g.bottom() - (wv / top * g.h as f64) as i32;
        let say = format!("{:.0} W", wv);
        ui.c.rect(g.x + 1, y - 11, F6X10.measure(&say) as i32 + 4, 10, t.base);
        ui.label(g.x + 3, y - 11, &say, &F6X10, t.dim);
        wv += 500.0;
    }
    ui.label_in(label.x, label.y, label.w, "fleet watts", &F8X13, t.ink);
    ui.label_in(label.x, label.y + 15, label.w, "at the wall,", &F6X10, t.dim);
    ui.label_in(label.x, label.y + 26, label.w, "estimated", &F6X10, t.dim);
    // The scale, blue to red.
    for i in 0..(label.w - 30) {
        ui.c.rect(label.x + i, label.y + 42, 1, 8, heat(i as f64 / (label.w - 31) as f64));
    }
    ui.label(label.x, label.y + 52, "0", &F6X10, t.dim);
    ui.label_right(label.x + label.w - 30, label.y + 52, &format!("{:.0} W", top), &F6X10, t.dim);
    // What it costs, over the forecast's side.
    let r = rect(now_x + 6, g.y, g.right() - now_x - 10, g.h);
    let lines = [
        (format!("now {:.0} W of {:.0} W at full tilt", p.fleet_now, p.fleet_full), heat(p.fleet_now / top)),
        (format!("last 24 h: {:.1} kWh, ${:.2}", p.kwh_24h, p.usd_24h), t.ink),
        (format!("a month like it: ~${:.0} at ${:.2}/kWh", p.usd_30d, p.rate), t.ink),
        (format!("sampled {}: CPU use and GPU watts measured,", p.sampled), t.dim),
        ("the CPUs' watts estimated from their parts".to_string(), t.dim),
    ];
    for (i, (l, c)) in lines.iter().enumerate() {
        ui.label_in(r.x, r.y + 2 + i as i32 * 14, r.w, l, if i == 0 { &F8X13 } else { &F6X10 }, *c);
    }
    ui.tip(r, || {
        let mut v = vec!["The fleet's watts at the wall, and what they cost".to_string(),
            "Each box: (the rest of it + its CPU at idle + the CPU's use x its full tilt less idle + its GPU) / its supply's efficiency (80 Plus Gold, 0.88).".to_string(),
            "Measured each five minutes: each CPU's use (/proc/stat; top on the Mac) and each GPU's draw (nvidia-smi). Estimated: the CPUs' watts, from their makers' figures (tools/plans/power.json). No box lets a user read its CPU's energy counter, and none has a meter at the wall.".to_string()];
        v.extend(p.boxes.iter().map(|b| format!("{}: {:.0} W now, {:.0} W at full tilt; {}{}", b.name, b.now, b.full,
            b.busy_util.map(|u| format!("busy at {:.0}% of its cores", u * 100.0)).unwrap_or_default(),
            b.gpu_busy.map(|g| format!(", its card {:.0} W in a segment", g)).unwrap_or_default())));
        v.push(format!("The price, ${:.2} a kWh, is Settings, Long run, power_usd_kwh.", p.rate));
        v
    });
    // The bin under the pointer.
    let (px, py) = ui.pointer();
    if px >= g.x && px < now_x && py >= g.y && py <= g.bottom() {
        let at_min = (px - now_x) as f64 / (now_x - g.x).max(1) as f64 * past_min;
        let k = ((at_min - lv.from_min) / lv.bin_min).floor();
        if k >= 0.0 {
            let k = k as usize;
            if let Some(tot) = total(k) {
                let a = lv.from_min + k as f64 * lv.bin_min;
                let mut by: Vec<(&str, f64)> = lv.watts.iter().filter_map(|(h, w)| Some((h.as_str(), w.get(k).copied().flatten()?))).collect();
                by.sort_by(|x, y| y.1.partial_cmp(&x.1).unwrap_or(std::cmp::Ordering::Equal));
                let hit = rect(xof(a.max(-past_min)), g.y, (xof((a + lv.bin_min).min(0.0)) - xof(a.max(-past_min))).max(2), g.h);
                ui.tip(hit, || {
                    let mut v = vec![format!("{} to {}: {:.0} W at the wall", lv.stamp(&m.timeline_at, a), lv.stamp(&m.timeline_at, (a + lv.bin_min).min(0.0)), tot),
                        format!("{:.2} kWh in it, ${:.3}; at this, ${:.2} a day", tot * lv.bin_min / 60.0 / 1000.0, tot * lv.bin_min / 60.0 / 1000.0 * p.rate, tot * 24.0 / 1000.0 * p.rate)];
                    v.extend(by.iter().map(|(h, w)| format!("  {}: {:.0} W", h, w)));
                    v.push("Each lane its watts busy for the share of the bin it ran a job, idle for the rest; a machine switched off counts as idle.".to_string());
                    v
                });
            }
        }
    }
}

/// What a bin holds, for the one under the pointer: a day and longer have thousands of them and
/// one pointer, so only that one is asked.
fn bin_tip(ui: &mut Ui, m: &Model, lv: &ZoomLevel, plot: Rect, row: i32, now_x: i32, past_min: f64, xof: &dyn Fn(f64) -> i32) {
    let (px, py) = ui.pointer();
    if px < plot.x || px >= now_x || py < plot.y || py >= plot.y + row * m.lanes.len() as i32 {
        return;
    }
    let i = ((py - plot.y) / row.max(1)) as usize;
    let at_min = (px - now_x) as f64 / (now_x - plot.x).max(1) as f64 * past_min;
    let bi = ((at_min - lv.from_min) / lv.bin_min).floor();
    let Some(l) = m.lanes.get(i) else { return };
    if bi < 0.0 {
        return;
    }
    let parts = lv.lanes.iter().find(|(h, _)| h == &l.host).and_then(|(_, b)| b.iter().find(|(k, _)| *k == bi as usize)).map(|(_, p)| p.clone()).unwrap_or_default();
    let a = lv.from_min + bi * lv.bin_min;
    let r = rect(xof(a), plot.y + i as i32 * row, (xof(a + lv.bin_min) - xof(a)).max(1), row);
    let busy: f64 = parts.iter().map(|(_, p)| p).sum();
    let before = lv.begins.map(|b| a + lv.bin_min <= b).unwrap_or(false);
    ui.tip(r, || {
        let mut v = vec![format!("{}, {} to {}", l.host, lv.stamp(&m.timeline_at, a), lv.stamp(&m.timeline_at, (a + lv.bin_min).min(0.0)))];
        if before {
            v.push("Before the event log begins: nothing is known of it.".to_string());
        } else {
            v.extend(parts.iter().map(|(k, p)| format!("{}: {:.0}%", if k == "failed" { "Failed or sent back" } else { line::short(k) }, p)));
            v.push(format!("Idle or between jobs: {:.0}%", (100.0 - busy).max(0.0)));
        }
        v.push(format!("A column is {} of the machine's time, filled by the share each stage took.", took(lv.bin_min)));
        v.push("Source: events.jsonl, binned by the planner (plan/timeline-bins.json).".to_string());
        v
    });
}

/// THE MILESTONES (Paul, 5 November: "show separation of major milestones of generation"): a line
/// through every machine where each happened, its name in a tag above, the most telling first
/// where tags would collide. The islands' rules run only through the GPU rows: a side channel.
#[allow(clippy::too_many_arguments)]
fn milestones(ui: &mut Ui, m: &Model, plot: Rect, plot_h: i32, row: i32, past_min: f64, xof: &dyn Fn(f64) -> i32, side: bool) {
    let t = ui.t;
    let style = |k: &str| -> (Rgb, usize) {
        match k {
            "main" | "game" | "ship" => (match k { "main" => t.up, "game" => 0x30c8e0, _ => t.ink }, 0),
            "milestone" | "rules" => (line::colour("islands"), 1),
            "generation" => (t.up, 2),
            "failed" => (t.alarm, 3),
            _ => (t.warn, 3),
        }
    };
    let gpu: Vec<usize> = m.lanes.iter().enumerate().filter(|(_, l)| m.cuda.iter().any(|(h, _)| h == &l.host)).map(|(i, _)| i).collect();
    let shown: Vec<&Mark> = m.marks.iter().filter(|mk| mk.at >= -past_min).collect();
    for mk in &shown {
        let x = xof(mk.at);
        let (c, p) = style(&mk.kind);
        if mk.kind == "rules" {
            if !side {
                continue;
            }
            for &i in &gpu {
                let y = plot.y + i as i32 * row;
                for yy in (y..y + row - 1).step_by(4) {
                    ui.c.rect(x - 1, yy, 3, 2, c);
                }
            }
            continue;
        }
        let w = if p == 0 { 2 } else { 1 };
        ui.c.rect(x - 1, plot.y - 2, w + 2, plot_h + 2, t.base);
        ui.c.rect(x, plot.y - 2, w, plot_h + 2, c);
    }
    let mut order = shown.clone();
    order.sort_by_key(|mk| style(&mk.kind).1);
    let mut used: [Vec<(i32, i32)>; 2] = [Vec::new(), Vec::new()];
    for mk in order {
        let x = xof(mk.at);
        let (c, _) = style(&mk.kind);
        let say = match mk.kind.as_str() {
            "milestone" => {
                let p: Vec<&str> = mk.text.split('-').collect();
                format!("{} {}", p.first().unwrap_or(&""), p.get(1).unwrap_or(&""))
            }
            "rules" => "islands' rules".to_string(),
            "ship" => mk.text.replace("into the game: ", "") + " into the game",
            "main" => {
                let ws: Vec<&str> = mk.text.trim_start_matches("main: ").split(", ").collect();
                if ws.len() > 2 { format!("main: {} +{}", ws[0], ws.len() - 1) } else { mk.text.clone() }
            }
            "failed" => format!("{} stopped", mk.text),
            "eases" => "easier".to_string(),
            "proof" => "proof".to_string(),
            _ => mk.text.clone(),
        };
        let w = F8X13.measure(&say) as i32 + 6;
        let x0 = (x - 1).min(plot.right() - w).max(plot.x);
        let mut tag = None;
        for (ri, row_used) in used.iter_mut().enumerate() {
            if row_used.iter().all(|(a, b)| x0 + w + 3 < *a || x0 > *b + 3) {
                row_used.push((x0, x0 + w));
                tag = Some(rect(x0, plot.y - 46 + ri as i32 * 16, w, 14));
                break;
            }
        }
        if let Some(r) = tag {
            ui.c.vline(x, r.bottom(), plot.y - 2 - r.bottom(), c);
            ui.c.rect(r.x, r.y, r.w, r.h, c);
            ui.label(r.x + 3, r.y, &say, &F8X13, t.base);
        } else {
            ui.c.rect(x - 1, plot.y - 6, 3, 4, c);
        }
        let why = match mk.kind.as_str() {
            "main" => "The line reached main: every machine builds main, so a read after it reads a newer brain.",
            "generation" => "A generation on the line: a promotion that passed its tests, families and gauntlet.",
            "failed" => "A candidate the tests stopped: its promotion failed; it is tried again when main moves.",
            "milestone" => "A GPU island's milestone: a segment's champion beat the ladder's newest by two errors. The bridge reads each as the Gladiator on a CPU machine.",
            "ship" => "A net shipped into the game: treadcore's nets/ changed on main.",
            "game" => "The game's rules or its score moved: a read of the old game is no evidence about the new one, so the fleet reads anew.",
            "rules" => "The islands' rules: each GPU segment is built with sixteen constants of treadcore's rules.rs at the fleet's commit; a move rebuilds them at their next segment.",
            "eases" => "The bars ease here, if nothing passes first.",
            _ => "The next read of the line against main.",
        };
        let hit = rect(x - 3, plot.y - 2, 7, plot_h + 2);
        let lines = || vec![say.clone(), format!("{}{}", if mk.when.is_empty() { String::new() } else { format!("{}, ", mk.when) }, signed(mk.at)), mk.text.clone(), why.to_string()];
        ui.tip(hit, lines);
        if let Some(r) = tag {
            ui.tip(r, || vec![say.clone(), format!("{}{}", if mk.when.is_empty() { String::new() } else { format!("{}, ", mk.when) }, signed(mk.at)), mk.text.clone(), why.to_string()]);
        }
    }
}

/// WHEN THE GPU HANDS ANYTHING ON (Paul, 5 November: "I don't understand when the CUDA will
/// return"): on each GPU row, over its forecast, what its next milestone must beat and the planner's
/// guess from the trend of its exams.
fn cuda_return(ui: &mut Ui, m: &Model, plot: Rect, row: i32, now_x: i32) {
    let t = ui.t;
    for (i, l) in m.lanes.iter().enumerate() {
        let Some((_, c)) = m.cuda.iter().find(|(h, _)| h == &l.host) else { continue };
        let y = plot.y + i as i32 * row;
        let two = row >= 34;
        let r = rect(now_x + 6, y + 3, plot.right() - now_x - 10, if two { 30 } else { (row - 6).max(8) });
        ui.c.rect(r.x, r.y, r.w, r.h, t.base);
        ui.outline(r, line::colour("islands"));
        let top = c.top.split('-').next().unwrap_or("").to_string();
        let when = match c.eta_h {
            Some(e) => format!("to the game past {} in ~{}", top, took(e * 60.0)),
            None => format!("to the game past {}: no date", top),
        };
        let near = match (c.best, c.median) {
            (Some(b), Some(md)) => format!("exams: best {:+.1}, median {:+.1} of +2", b, md),
            _ => "no exam against it in six hours".to_string(),
        };
        ui.label_in(r.x + 4, r.y + 1, r.w - 8, &when, &F8X13, line::colour("islands"));
        if two {
            ui.label_in(r.x + 4, r.y + 15, r.w - 8, &near, &F8X13, t.ink);
        }
        ui.tip(r, || vec![
            format!("{}: when it next gives the game anything", l.host),
            format!("A segment every {}: its champion meets the ladder's newest milestone, {} (made {}).",
                    c.seg_min.map(took).unwrap_or_else(|| "few minutes".to_string()), c.top, c.top_made.replace('T', " ")),
            format!("Since it: {:.0} segments here, none past it. Last six hours: best {}, median {} errors; it needs +2.",
                    c.segments, c.best.map(|b| format!("{:+.1}", b)).unwrap_or("-".into()), c.median.map(|b| format!("{:+.1}", b)).unwrap_or("-".into())),
            match (c.per_day, c.eta_h) {
                (Some(d), Some(e)) => format!("The median climbs {:+.1} errors a day: at that pace it crosses +2 in about {}. A guess from a trend.", d, took(e * 60.0)),
                (Some(d), None) => format!("The median moves {:+.1} errors a day: no date from that.", d),
                _ => "Too few hours of exams for a trend.".to_string(),
            },
            "Then: the bridge reads the milestone as the Gladiator on a CPU machine (2 x 48 seeds) against the shipped one, and ships it into the game if it reads better by two errors.".to_string(),
            "The rules: each segment is built with sixteen constants of treadcore's rules.rs at the fleet's commit (speed, turn, guns, armour, shells, vision, pillboxes). The economy and the score are not in the islands' world.".to_string(),
            "The six hollow boxes are a buffer, not a backlog: each island keeps six segments in line, one after another, topped up at every pass.".to_string(),
        ]);
    }
}

/// The clock time of `min` minutes from when the planner wrote the page (`checked`), as HH:MM.
fn clock(checked: &str, min: f64) -> String {
    let hm = checked.get(11..16).unwrap_or("00:00");
    let base = hm[..2].parse::<f64>().unwrap_or(0.0) * 60.0 + hm[3..].parse::<f64>().unwrap_or(0.0);
    let t = (base + min).rem_euclid(24.0 * 60.0);
    format!("{:02}:{:02}", (t / 60.0) as i32, (t % 60.0) as i32)
}

/// The date and clock of `min` minutes from `checked`, as "Nov 5 12:30": the longer zooms reach
/// back over midnights and months. Wall-clock arithmetic; ZoomLevel::stamp adds summer time.
fn stamp(checked: &str, min: f64) -> String {
    const MONTHS: [&str; 12] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    let num = |a: usize, b: usize| checked.get(a..b).and_then(|x| x.parse::<i64>().ok());
    let (Some(y), Some(mo), Some(d), Some(h), Some(mi)) = (num(0, 4), num(5, 7), num(8, 10), num(11, 13), num(14, 16)) else {
        return clock(checked, min);
    };
    let total = days_from_civil(y, mo, d) * 1440 + h * 60 + mi + min.round() as i64;
    let (_, m2, d2) = civil_from_days(total.div_euclid(1440));
    let rest = total.rem_euclid(1440);
    format!("{} {} {:02}:{:02}", MONTHS[(m2 - 1).clamp(0, 11) as usize], d2, rest / 60, rest % 60)
}

/// Days since 1970-01-01 of a date (Howard Hinnant's algorithm), and back.
fn days_from_civil(y: i64, m: i64, d: i64) -> i64 {
    let y = if m <= 2 { y - 1 } else { y };
    let era = y.div_euclid(400);
    let yoe = y - era * 400;
    let doy = (153 * ((m + 9) % 12) + 2) / 5 + d - 1;
    era * 146097 + yoe * 365 + yoe / 4 - yoe / 100 + doy - 719468
}

fn civil_from_days(z: i64) -> (i64, i64, i64) {
    let z = z + 719468;
    let era = z.div_euclid(146097);
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    (yoe + era * 400 + if m <= 2 { 1 } else { 0 }, m, d)
}

/// A chain's links in time order, each with the link it followed: the one the planner names
/// (`after`, where the titles cannot say: a bridge read after its milestone's segment), or else
/// the latest that ended by its start (several pieces begun together each follow the same read-on).
/// None for the first.
pub fn chain_links<'a>(m: &'a Model, chain: &str) -> Vec<(usize, &'a JobBar, Option<usize>)> {
    let mut links: Vec<(usize, &JobBar)> = m.lanes.iter().enumerate().flat_map(|(i, l)| l.jobs.iter().filter(move |j| j.chain == chain).map(move |j| (i, j))).collect();
    links.sort_by(|a, b| a.1.from.partial_cmp(&b.1.from).unwrap_or(std::cmp::Ordering::Equal));
    (0..links.len())
        .map(|k| {
            let b = links[k].1;
            let prev = if b.after.is_empty() {
                (0..k).filter(|&p| links[p].1.to <= b.from + 0.05).max_by(|&p, &q| links[p].1.to.partial_cmp(&links[q].1.to).unwrap_or(std::cmp::Ordering::Equal))
            } else {
                (0..links.len()).find(|&p| p != k && links[p].1.id == b.after)
            };
            (links[k].0, b, prev)
        })
        .collect()
}

/// FOLLOW A CHAIN (Paul, 5 November: "can we see arrows how the job moves from one to the other ...
/// On highlight of cell, highlight all the chain elements associated"). The job under the pointer
/// names its chain, a trial, a run or an island; every job of it is framed wherever it ran, and an
/// arrow goes to each from the link it followed, from that one's end to its own start. A click keeps
/// the chain while the pointer is elsewhere; a click on it again, or on no job, lets it go. Only
/// what the zoom shows: a link before its left edge is not drawn.
#[allow(clippy::too_many_arguments)]
fn follow_chain(ui: &mut Ui, m: &Model, st: &mut State, plot: Rect, row: i32, now_x: i32, past_min: f64, tag_at: (i32, i32), xof: &dyn Fn(f64) -> i32) {
    let t = ui.t;
    let row_of = |i: usize| plot.y + i as i32 * row;
    let job_rect = |i: usize, j: &JobBar| {
        let (a, e) = (xof(j.from), xof(j.to));
        rect(a, row_of(i) + 1, (e - a).max(2), row - 3)
    };
    let seen = |j: &JobBar| j.to >= -past_min;
    let (px, py) = ui.pointer();
    let measured = rect(plot.x, plot.y, now_x - plot.x + 2, row * m.lanes.len() as i32);
    let mut hovered: Option<(usize, &JobBar)> = None;
    if measured.contains((px, py)) {
        let i = ((py - plot.y) / row.max(1)) as usize;
        if let Some(l) = m.lanes.get(i) {
            hovered = l.jobs.iter().filter(|j| seen(j)).find(|j| {
                let r = job_rect(i, j);
                px >= r.x - 1 && px <= r.right() + 1
            }).map(|j| (i, j));
        }
    }
    if ui.button_hit(measured) {
        st.chain = match hovered {
            Some((_, j)) if st.chain.as_deref() != Some(j.chain.as_str()) => Some(j.chain.clone()),
            _ => None,
        };
    }
    let Some(chain) = hovered.map(|(_, j)| j.chain.clone()).or_else(|| st.chain.clone()) else { return };
    let links = chain_links(m, &chain);
    if !links.iter().any(|(_, j, _)| seen(j)) {
        return;
    }
    // The rest of the hours stepped back: every other pixel dark, the chain's own jobs drawn
    // again over it in their colours, so the chain is what the eye finds.
    for y in measured.y..measured.bottom() {
        for x in (measured.x + (y & 1))..measured.right() {
            if (x & 1) == 0 {
                ui.c.set(x, y, t.base);
            }
        }
    }
    for (i, j, _) in links.iter().filter(|(_, j, _)| seen(j)) {
        let r = job_rect(*i, j);
        ui.c.rect(r.x, r.y, r.w, r.h, if j.ok == 0 { t.alarm } else { line::colour(&j.stage) });
    }
    // The arrows, under the frames: dark under amber, so they read over any colour.
    for (i, b, prev) in &links {
        let Some(p) = prev else { continue };
        let (ia, a, _) = links[*p];
        if !seen(a) || !seen(b) || (ia == *i && b.from - a.to < 0.5) {
            continue; // the next link on the same machine, touching: the frames say it
        }
        let (x0, y0) = (xof(a.to), row_of(ia) + row / 2);
        let (x1, y1) = (xof(b.from).max(x0 + 3), row_of(*i) + row / 2);
        pointer(ui, (x0 + 1, y0 + 1), (x1 + 1, y1 + 1), t.base);
        pointer(ui, (x0 - 1, y0 - 1), (x1 - 1, y1 - 1), t.base);
        pointer(ui, (x0, y0), (x1, y1), t.warn);
    }
    for (i, j, _) in links.iter().filter(|(_, j, _)| seen(j)) {
        let r = job_rect(*i, j);
        ui.outline(rect(r.x - 3, r.y - 3, r.w + 6, r.h + 6), t.base);
        ui.outline2(rect(r.x - 2, r.y - 2, r.w + 4, r.h + 4), t.warn);
    }
    let hosts: std::collections::BTreeSet<&str> = links.iter().map(|(i, _, _)| m.lanes[*i].host.as_str()).collect();
    let kept = st.chain.as_deref() == Some(chain.as_str());
    let said = format!("following {}: {} job{}, {} machine{} {}", chain, links.len(), if links.len() == 1 { "" } else { "s" },
                       hosts.len(), if hosts.len() == 1 { "" } else { "s" }, if kept { "(kept)" } else { "(a click keeps it)" });
    let w = F8X13.measure(&said) as i32 + 10;
    let tag = rect((now_x - 8 - w).max(tag_at.0), tag_at.1 - 2, w, 15);
    ui.c.rect(tag.x, tag.y, tag.w, tag.h, t.warn);
    ui.label(tag.x + 5, tag.y + 1, &said, &F8X13, t.base);
    if let Some((i, j)) = hovered {
        let r = job_rect(i, j);
        let steps: Vec<String> = links.iter().map(|(li, lj, _)| {
            format!("{} {:<10} {:<14} {:<15} {}{}{}", clock(&m.timeline_at, lj.from), line::short(&lj.stage), lj.id, m.lanes[*li].host,
                    took(lj.to - lj.from), lj.wh.map(|w| format!(", {:.1} Wh", w)).unwrap_or_default(), match lj.ok { 0 => ", failed or sent back", 2 => ", running", _ => "" })
        }).collect();
        ui.tip(r, || {
            let wh: f64 = links.iter().filter_map(|(_, j, _)| j.wh).sum();
            let mut v = vec![format!("{}: its {} job{} in the last {:.0} h, in the order they began; {:.1} Wh, ${:.3}", chain, steps.len(), if steps.len() == 1 { "" } else { "s" }, m.past_h, wh, wh / 1000.0 * m.power.rate)];
            v.extend(steps.into_iter().take(24));
            v.push("An arrow runs from the job a link followed to it. Click to keep the chain lit; zoom to the hour for detail.".to_string());
            v
        });
    }
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

/// A line one pixel wide, Bresenham's: the canvas has rectangles and discs.
fn seg(ui: &mut Ui, (x0, y0): (i32, i32), (x1, y1): (i32, i32), c: Rgb) {
    let (dx, dy) = ((x1 - x0).abs(), -(y1 - y0).abs());
    let (sx, sy) = (if x0 < x1 { 1 } else { -1 }, if y0 < y1 { 1 } else { -1 });
    let (mut x, mut y, mut err) = (x0, y0, dx + dy);
    for _ in 0..8192 {
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

/// A line with a head at its end, two pixels wide so it reads at a glance.
fn pointer(ui: &mut Ui, a: (i32, i32), b: (i32, i32), c: Rgb) {
    let (dx, dy) = ((b.0 - a.0) as f64, (b.1 - a.1) as f64);
    let len = (dx * dx + dy * dy).sqrt().max(1.0);
    let (ux, uy) = (dx / len, dy / len);
    // The second pixel across the line: thick enough to see, thin enough to cross others.
    let (px, py) = (-uy, ux);
    let off = |p: (i32, i32)| (p.0 + px.round() as i32, p.1 + py.round() as i32);
    seg(ui, a, b, c);
    seg(ui, off(a), off(b), c);
    for side in [0.45_f64, -0.45] {
        let (cs, sn) = (side.cos(), side.sin());
        let (hx, hy) = (-(ux * cs - uy * sn), -(ux * sn + uy * cs));
        for k in 0..3 {
            let tip = (b.0, b.1 + k - 1);
            seg(ui, tip, (b.0 + (hx * 10.0) as i32, b.1 + k - 1 + (hy * 10.0) as i32), c);
        }
    }
}

/// Where a line from a box's centre toward `to` leaves the box.
fn edge_of(r: Rect, to: (i32, i32)) -> (i32, i32) {
    let (cx, cy) = (r.x + r.w / 2, r.y + r.h / 2);
    let (dx, dy) = ((to.0 - cx) as f64, (to.1 - cy) as f64);
    if dx == 0.0 && dy == 0.0 {
        return (cx, cy);
    }
    let t = ((r.w as f64 / 2.0 + 3.0) / dx.abs().max(1e-9)).min((r.h as f64 / 2.0 + 3.0) / dy.abs().max(1e-9));
    (cx + (dx * t) as i32, cy + (dy * t) as i32)
}

/// THE ROUND TABLE (Paul, 5 November: "a blame tab, where it shows the name of the computer and
/// the arrows pointing at each other in a ring round table fashion around the edges, where the
/// computers point at each other saying who they are waiting on. On their other hand, shows their
/// backup help, where it can reach out back to the queue to assist in small jobs of improvement,
/// piecemeal in returnable increments"). The machines sit round the edge; the queue and its planner
/// are the table. An arrow between two machines is work one of them waits on the other for; a loop
/// is work waiting its turn on its own machine; amber to the table is a run handed back to the
/// planner; green to the table is the machine's help, the small reads it takes from the queue.
/// THE PLANNER DECIDES ALL OF IT: the page draws `blame` from pipeline.json and counts nothing.
fn blame(ui: &mut Ui, at: Rect, m: &Model, st: &mut State) {
    let t = ui.t;
    let b = &m.blame;
    if b.seats.is_empty() {
        ui.label_in(at.x + 4, at.y + 4, at.w - 8, "The planner has not written the round table yet: it does at each plan, about a minute.", &F8X13, t.dim);
        return;
    }
    // The two lines that answer the question before the picture does.
    let cpu: Vec<&Seat> = b.seats.iter().filter(|x| !x.gpu).collect();
    let gpu: Vec<&Seat> = b.seats.iter().filter(|x| x.gpu).collect();
    let span = |v: &[&Seat]| -> String {
        if v.is_empty() {
            return "none".into();
        }
        let lo = v.iter().map(|x| x.busy).fold(f64::MAX, f64::min);
        let hi = v.iter().map(|x| x.busy).fold(f64::MIN, f64::max);
        format!("{:.0} to {:.0}%", lo, hi)
    };
    let across = b.waits.iter().filter(|w| w.from != w.to).map(|w| w.n).sum::<i64>();
    let said = format!(
        "Busy, last {:.0} h: CPUs {}, GPUs {}. {}",
        m.past_h.max(1.0),
        span(&cpu),
        span(&gpu),
        if across == 0 { "No machine waits on another: each wait is its own queue, its build, or the planner.".to_string() } else { format!("{} job(s) wait on another machine.", across) }
    );
    ui.label_in(at.x + 4, at.y + 2, at.w - 8, &said, &F8X13, t.ink);
    let hand: Vec<String> = b.handoffs.iter().map(|h| format!("{} {:.1} planner + {:.1} queue + {:.1} work", if h.chain == "transform" { "transform step" } else { "trial read" }, h.planner, h.queue, h.work)).collect();
    if !hand.is_empty() {
        ui.label_in(at.x + 4, at.y + 18, at.w - 8, &format!("Handoffs, minutes, medians of a day: {}.", hand.join("; ")), &F8X13, t.dim);
    }
    let legend_h = 34;
    let panel_w = 352;
    let panel = rect(at.right() - panel_w, at.y + 38, panel_w, at.h - 38 - legend_h);
    let room = rect(at.x, at.y + 38, at.w - panel_w - 8, at.h - 38 - legend_h);
    // The queues first: what the pointer is on there is what the table shows. Under them, what it
    // is on, written out.
    let pane_h = 128;
    let (mut hover, mut clicked) = queue_accordions(ui, rect(panel.x, panel.y, panel.w, panel.h - pane_h - 6), m, st);
    let (sw, sh) = (160, 58);
    let (cx, cy) = (room.x + room.w / 2, room.y + room.h / 2);
    let (rx, ry) = (((room.w - sw) / 2 - 24).max(40) as f64, ((room.h - sh) / 2 - 18).max(40) as f64);
    let hub = rect(cx - 150, cy - 46, 300, 92);
    let n = b.seats.len();
    let places: Vec<Rect> = (0..n)
        .map(|i| {
            let a = -std::f64::consts::FRAC_PI_2 + 2.0 * std::f64::consts::PI * i as f64 / n as f64;
            let (x, y) = (cx + (rx * a.cos()) as i32, cy + (ry * a.sin()) as i32);
            rect(x - sw / 2, y - sh / 2, sw, sh)
        })
        .collect();
    let at_host = |h: &str| b.seats.iter().position(|x| x.host == h).map(|i| places[i]);
    let p = ui.pointer();
    for (i, r) in places.iter().enumerate() {
        if hover.is_none() && r.contains(p) {
            hover = Some((b.seats[i].host.clone(), None));
        }
        if ui.button_hit(*r) {
            clicked = Some((b.seats[i].host.clone(), None));
        }
    }
    if let Some(c) = clicked {
        st.blame_keep = if st.blame_keep.as_ref() == Some(&c) { None } else { Some(c) };
    }
    let focus = hover.or_else(|| st.blame_keep.clone());
    let kept = focus.is_some() && focus == st.blame_keep;
    detail_pane(ui, rect(panel.x, panel.bottom() - pane_h, panel.w, pane_h), m, focus.as_ref(), kept);
    let mid = |r: Rect| (r.x + r.w / 2, r.y + r.h / 2);
    // Green first, under everything: each machine's hand back to the queue.
    for (i, x) in b.seats.iter().enumerate() {
        if x.help <= 0.0 {
            continue;
        }
        let r = places[i];
        let (a, z) = (edge_of(r, mid(hub)), edge_of(hub, mid(r)));
        // Beside the line a wait would take, so the two never hide each other.
        let (dx, dy) = ((z.0 - a.0) as f64, (z.1 - a.1) as f64);
        let l = (dx * dx + dy * dy).sqrt().max(1.0);
        let (ox, oy) = ((-dy / l * 7.0) as i32, (dx / l * 7.0) as i32);
        pointer(ui, (a.0 + ox, a.1 + oy), (z.0 + ox, z.1 + oy), t.up);
    }
    // Amber: a run handed back, waiting on the planner's next pass.
    for h in &b.planner {
        if let Some(r) = at_host(&h.host) {
            let (a, z) = (edge_of(r, mid(hub)), edge_of(hub, mid(r)));
            pointer(ui, a, z, t.warn);
            let lab = rect((a.0 + z.0) / 2 - 60, (a.1 + z.1) / 2 - 7, 120, 14);
            ui.c.rect(lab.x, lab.y, lab.w, lab.h, t.base);
            ui.label_in(lab.x + 2, lab.y, lab.w - 4, &format!("{} {}", h.run, took(h.for_min)), &F8X13, t.warn);
            ui.tip(lab, || vec![
                format!("{} ({}) is handed back to the planner", h.run, h.kind),
                format!("Its last job, {}, came back from {} {} ago; its next is asked at the planner's next pass.", h.job, h.host, took(h.for_min)),
                "The planner passes each plan_s, or sooner when the queue runs low: this is the handoff the line above measures.".to_string(),
            ]);
        }
    }
    // Red: work dealt to one machine that waits on a job another runs.
    for w in b.waits.iter().filter(|w| w.from != w.to) {
        let (Some(ra), Some(rb)) = (at_host(&w.from), at_host(&w.to)) else { continue };
        let (a, z) = (edge_of(ra, mid(rb)), edge_of(rb, mid(ra)));
        pointer(ui, a, z, t.alarm);
        let lab = rect((a.0 + z.0) / 2 - 16, (a.1 + z.1) / 2 - 7, 32, 14);
        ui.c.rect(lab.x, lab.y, lab.w, lab.h, t.base);
        ui.label(lab.x + 4, lab.y, &w.n.to_string(), &F8X13, t.alarm);
        ui.tip(lab, || vec![
            format!("{} waits on {}: {} job(s)", w.from, w.to, w.n),
            format!("Each runs after a job {} has in hand: {}.", w.to, w.jobs.join(", ")),
        ]);
    }
    // The table: the queue and its planner.
    ui.c.rect(hub.x, hub.y, hub.w, hub.h, t.tile);
    ui.outline(hub, t.ink);
    ui.label(hub.x + 10, hub.y + 6, "The queue and its planner", &F8X13, t.ink);
    ui.label_in(hub.x + 10, hub.y + 24, hub.w - 20, &format!("{:.0} queued; a plan each {}", b.queued, took(b.plan_s / 60.0)), &F8X13, t.dim);
    let handed = if b.planner.is_empty() { "nothing handed back".to_string() } else { format!("{} handed back: {}", b.planner.len(), b.planner.iter().map(|h| h.run.as_str()).collect::<Vec<_>>().join(", ")) };
    ui.label_in(hub.x + 10, hub.y + 42, hub.w - 20, &handed, &F8X13, if b.planner.is_empty() { t.dim } else { t.warn });
    ui.label_in(hub.x + 10, hub.y + 60, hub.w - 20, "green: each machine's help", &F8X13, t.up);
    ui.tip(hub, || vec![
        "The table: every queued job and the planner that asks for them".to_string(),
        "A free machine takes the next job it can run. When its own line has nothing, that is a small returnable read of the standing search: the backup.".to_string(),
    ]);
    // The seats.
    for (i, x) in b.seats.iter().enumerate() {
        let r = places[i];
        let busy = matches!(x.state.as_str(), "running" | "delivering" | "fetching" | "sending");
        ui.c.rect(r.x, r.y, r.w, r.h, t.tile);
        ui.outline(r, if busy { t.up } else if x.state == "idle" { t.warn } else { t.line });
        ui.c.rect(r.x + 1, r.y + 1, 5, r.h - 2, if x.stage.is_empty() { t.dim } else { line::colour(&x.stage) });
        ui.label_in(r.x + 10, r.y + 4, r.w - 14, &x.host, &F8X13, t.ink);
        let now = if x.job.is_empty() { format!("{} {}", x.state, took(x.for_min)) } else { format!("{} {}", line::short(&x.stage), took(x.for_min)) };
        ui.label_in(r.x + 10, r.y + 21, r.w - 14, &now, &F8X13, t.dim);
        ui.label_in(r.x + 10, r.y + 40, r.w - 14, &format!("busy {:.0}%  help {:.0}%", x.busy, x.help), &F6X10, if x.busy >= 90.0 { t.up } else { t.warn });
        // Its tip is the pane under the queues: here it would cover the jobs it lays out.
        // Its own waits: a loop on the outer side, turn in blue, build in amber.
        let mine: Vec<&Wait> = b.waits.iter().filter(|w| w.from == x.host && w.to == x.host).collect();
        let ox = mid(r).0 - cx;
        for (k, w) in mine.iter().enumerate() {
            let side = if ox >= 0 { 1 } else { -1 };
            let (lx, ly) = (if side > 0 { r.right() + 14 } else { r.x - 14 }, r.y + 14 + k as i32 * 24);
            let c = if w.kind == "build" { t.warn } else { t.ink };
            ui.c.ring(lx, ly, 10, c);
            ui.c.ring(lx, ly, 9, c);
            let s_ = w.n.to_string();
            ui.label(lx - 3 * s_.len() as i32, ly - 6, &s_, &F8X13, c);
            ui.tip(rect(lx - 11, ly - 11, 22, 22), || vec![
                format!("{}: {} job(s) {}", x.host, w.n, if w.kind == "build" { "wait for its build of the newest commit" } else { "wait their turn on it" }),
                w.jobs.join(", "),
                if x.gpu { "A GPU island keeps six segments ahead on purpose: the card never waits for the planner.".to_string() } else { "Its own queue: nothing to blame on anyone.".to_string() },
            ]);
        }
    }
    if let Some((host, job)) = &focus {
        job_arrows(ui, m, room, &places, hub, host, job.as_deref());
    }
    // The legend, for a first look.
    let ly = at.bottom() - legend_h + 8;
    let mut x = at.x + 6;
    for (c, word) in [
        (t.up, "help: small reads from the queue"),
        (t.warn, "handed back to the planner"),
        (t.alarm, "waits on another machine"),
        (t.ink, "loop: its own turn (amber: its build)"),
    ] {
        ui.c.rect(x, ly + 4, 18, 4, c);
        x = ui.label(x + 24, ly, word, &F8X13, t.dim) + 22;
    }
}

/// EACH MACHINE'S QUEUE, an accordion a machine (Paul, 5 November: "add more accordions to blame
/// ... a filtered job queue for each machine"): its header says what it runs and how many wait; open,
/// its jobs in the order they will run, each with what it waits on. A click on a header folds it.
/// What the pointer is on here is what the table shows: a machine's jobs, or one job's.
type Focus = (String, Option<String>);

fn queue_accordions(ui: &mut Ui, panel: Rect, m: &Model, st: &mut State) -> (Option<Focus>, Option<Focus>) {
    enum Row<'a> {
        Head(&'a Seat, &'a [QJob]),
        Job(&'a str, &'a QJob),
        Nothing,
        Lost,
    }
    let t = ui.t;
    let b = &m.blame;
    let mut rows = Vec::new();
    for x in &b.seats {
        let q = b.queue_of(&x.host);
        rows.push(Row::Head(x, q));
        if !st.blame_shut.contains(&x.host) {
            if q.is_empty() {
                rows.push(Row::Nothing);
            }
            rows.extend(q.iter().map(|j| Row::Job(&x.host, j)));
        }
    }
    if !b.unplaced.is_empty() {
        rows.push(Row::Lost);
        rows.extend(b.unplaced.iter().map(|j| Row::Job("", j)));
    }
    ui.label(panel.x + 2, panel.y, "Each machine's queue: point at one", &F8X13, t.ink);
    let area = rect(panel.x, panel.y + 18, panel.w, panel.h - 18);
    let rh = 18;
    let mut off = st.blame_off;
    let (list, first, count) = ui.scroll_list(area, rows.len(), rh, &mut off);
    st.blame_off = off;
    let p = ui.pointer();
    let (mut focus, mut clicked) = (None, None);
    for (k, row) in rows.iter().enumerate().skip(first).take(count) {
        let r = rect(list.x, list.y + (k - first) as i32 * rh, list.w, rh - 1);
        match row {
            Row::Head(x, q) => {
                let shut = st.blame_shut.contains(&x.host);
                ui.c.rect(r.x, r.y, r.w, r.h, t.tile);
                let busy = matches!(x.state.as_str(), "running" | "delivering" | "fetching" | "sending");
                ui.c.rect(r.x, r.y, 3, r.h, if busy { t.up } else if x.state == "idle" { t.warn } else { t.line });
                ui.label(r.x + 7, r.y + 2, &format!("{} {}", if shut { "+" } else { "-" }, x.host), &F8X13, t.ink);
                let waiting = q.iter().filter(|j| j.state != "running").count();
                let run = q.iter().find(|j| j.state == "running").map(|j| line::short(&j.stage).to_string()).unwrap_or_else(|| x.state.clone());
                let w = m.power.lane_now(&x.host).map(|w| format!(", {:.0} W", w)).unwrap_or_default();
                ui.label_right(r.right() - 6, r.y + 4, &format!("{}, {} waiting{}", run, waiting, w), &F6X10, t.dim);
                if ui.button_hit(r) {
                    if shut {
                        st.blame_shut.retain(|h| h != &x.host);
                    } else {
                        st.blame_shut.push(x.host.clone());
                    }
                }
                if r.contains(p) {
                    focus = Some((x.host.clone(), None));
                }
            }
            Row::Job(h, j) => {
                ui.c.rect(r.x + 12, r.y + 3, 4, r.h - 6, line::colour(&j.stage));
                ui.label_in(r.x + 20, r.y + 4, 150, &j.id, &F6X10, if j.state == "running" { t.up } else if j.high { t.warn } else { t.ink });
                ui.label_in(r.x + 172, r.y + 4, r.w - 176, &waits_on(j, h), &F6X10, t.dim);
                if r.contains(p) && !h.is_empty() {
                    focus = Some((h.to_string(), Some(j.id.clone())));
                }
                if ui.button_hit(r) && !h.is_empty() {
                    clicked = Some((h.to_string(), Some(j.id.clone())));
                }
                if job_is(st.blame_keep.as_ref(), h, &j.id) {
                    ui.outline(r, t.warn);
                }
            }
            Row::Nothing => {
                ui.label_in(r.x + 20, r.y + 4, r.w - 24, "nothing running or dealt to it", &F6X10, t.dim);
            }
            Row::Lost => {
                ui.c.rect(r.x, r.y, r.w, r.h, t.tile);
                ui.label(r.x + 7, r.y + 2, "no machine can take these now", &F8X13, t.alarm);
            }
        }
    }
    (focus, clicked)
}

fn job_is(f: Option<&Focus>, host: &str, id: &str) -> bool {
    f.map(|(h, j)| h == host && j.as_deref() == Some(id)).unwrap_or(false)
}

/// Words broken into lines of at most `n` characters.
fn wrap(text: &str, n: usize) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    let mut cur = String::new();
    for w in text.split_whitespace() {
        if !cur.is_empty() && cur.len() + 1 + w.len() > n {
            out.push(std::mem::take(&mut cur));
        }
        if !cur.is_empty() {
            cur.push(' ');
        }
        cur.push_str(w);
    }
    if !cur.is_empty() {
        out.push(cur);
    }
    out
}

/// What the pointer is on, or what a click keeps, written out under the queues: a tooltip there
/// would cover the very arrows it explains.
fn detail_pane(ui: &mut Ui, r: Rect, m: &Model, focus: Option<&Focus>, kept: bool) {
    let t = ui.t;
    let b = &m.blame;
    ui.c.rect(r.x, r.y, r.w, r.h, t.tile);
    ui.outline(r, if focus.is_some() { t.warn } else { t.line });
    let lines: Vec<String> = match focus {
        None => vec!["Point at a machine, at the table or in its queue above: its jobs are drawn at the table in the order they will run, an arrow from each to the job it waits on. Point at a job for its own. A click keeps it.".to_string()],
        Some((h, Some(id))) => match b.queue_of(h).iter().chain(b.unplaced.iter()).find(|j| &j.id == id) {
            Some(j) => job_tip(j, h),
            None => vec![format!("{} is no longer in {}'s queue.", id, h)],
        },
        Some((h, None)) => match b.seats.iter().find(|x| &x.host == h) {
            Some(x) => {
                let q = b.queue_of(h);
                let mut v = vec![
                    format!("{}: {}{}", x.host, x.state, if x.job.is_empty() { String::new() } else { format!(", {} for {}", x.job, took(x.for_min)) }),
                    format!("Busy {:.1}% of the last {:.0} h, {:.1}% of that the small returnable reads. {} waiting for it.", x.busy, m.past_h.max(1.0), x.help, q.iter().filter(|j| j.state != "running").count()),
                    format!("Its backup when its own line waits: {}.", x.backup),
                ];
                v.push(x.by_stage.iter().take(5).map(|(k, mins)| format!("{} {}", line::short(k), took(*mins))).collect::<Vec<_>>().join(", "));
                if let Some(w) = m.power.lane_now(h) {
                    let today = m.power.today(h).map(|(n, wh)| format!(" Today {:.0} jobs, {:.2} kWh, ${:.2}.", n, wh / 1000.0, wh / 1000.0 * m.power.rate)).unwrap_or_default();
                    v.push(format!("Power: {:.0} W at the wall now{}.{}", w, m.power.box_of(h).map(|b| format!(", its box {:.0} W at full tilt", b.full)).unwrap_or_default(), today));
                }
                v
            }
            None => vec![],
        },
    };
    let n = ((r.w - 12) / 6).max(10) as usize;
    let mut y = r.y + 4;
    for l in lines.iter().flat_map(|l| wrap(l, n)) {
        if y + 10 > r.bottom() - 12 {
            break;
        }
        ui.label(r.x + 6, y, &l, &F6X10, t.ink);
        y += 11;
    }
    let foot = if focus.is_none() { "" } else if kept { "kept: a click on it again lets go" } else { "a click keeps it" };
    ui.label(r.x + 6, r.bottom() - 12, foot, &F6X10, t.warn);
}

/// What a job waits on, in a few words: the running one says how long it has run.
fn waits_on(j: &QJob, host: &str) -> String {
    let when = match j.start {
        Some(s) if s > 0.5 => format!(", ~{}", took(s)),
        _ => String::new(),
    };
    match j.wait.as_str() {
        "" => format!("running, {} in", took(j.start.map(|s| -s).unwrap_or(0.0))),
        "turn" => format!("in turn{}", when),
        "build" => format!("its build {}{}", j.on, when),
        "after" if j.on_host != host => format!("after {} on {}{}", j.on, j.on_host, when),
        "after" => format!("after {}{}", j.on, when),
        _ => format!("no machine{}", if j.on.is_empty() { String::new() } else { format!(", after {}", j.on) }),
    }
}

fn job_tip(j: &QJob, host: &str) -> Vec<String> {
    vec![
        format!("{}: {}", j.id, line::short(&j.stage)),
        j.title.clone(),
        match j.wait.as_str() {
            "" => format!("Running on {} for {}.", host, took(j.start.map(|s| -s).unwrap_or(0.0))),
            "turn" => format!("Waits its turn on {}: it runs when the job ahead, {}, is done.", host, if j.on.is_empty() { "the running one" } else { &j.on }),
            "build" => format!("Waits for {}'s build of the newest commit, {}.", host, j.on),
            "after" => format!("Waits on {}, which {} has: the only wait between two machines.", j.on, if j.on_host.is_empty() { "no machine" } else { &j.on_host }),
            _ => "No machine that can run it is up, so the forecast deals it to none.".to_string(),
        },
        match (j.start, j.end) {
            (Some(s), Some(e)) if s >= 0.0 => format!("Forecast: starts in {}, ends in {}, at the medians of the last day.", took(s), took(e)),
            _ => String::new(),
        },
        if j.high { "High priority: it goes ahead of the search.".to_string() } else { String::new() },
    ]
    .into_iter()
    .filter(|x| !x.is_empty())
    .collect()
}

/// Everything in `area` but `keep` stepped back: every other pixel dark.
fn step_back(ui: &mut Ui, area: Rect, keep: &[Rect]) {
    let base = ui.t.base;
    for y in area.y..area.bottom() {
        for x in (area.x + (y & 1))..area.right() {
            if (x & 1) == 0 && !keep.iter().any(|r| r.contains((x, y))) {
                ui.c.set(x, y, base);
            }
        }
    }
}

/// JOBS AT THE TABLE (Paul, 5 November: "show the job dependency on hover ... job arrow amongst the
/// blame circle, with jobs shown"). The machine under the pointer, or in the queue beside, lays its
/// jobs out between its seat and the table, in the order they will run; each one's wait is an arrow:
/// grey to the job ahead of it, amber to its build, red to a job another machine has, drawn at that
/// machine's seat; and red from any job elsewhere that waits on one of these. The rest steps back.
fn job_arrows(ui: &mut Ui, m: &Model, room: Rect, places: &[Rect], hub: Rect, host: &str, job: Option<&str>) {
    let t = ui.t;
    let b = &m.blame;
    let Some(si) = b.seats.iter().position(|x| x.host == host) else { return };
    let jobs: Vec<&QJob> = b.queue_of(host).iter().take(14).collect();
    let seat_at = |h: &str| b.seats.iter().position(|x| x.host == h).map(|i| places[i]);
    let mid = |r: Rect| (r.x + r.w / 2, r.y + r.h / 2);
    let mine: Vec<&str> = jobs.iter().map(|j| j.id.as_str()).collect();
    // The others in it: (machine, its job, whether that job waits on one of these).
    let mut others: Vec<(String, String, bool, String)> = Vec::new();
    for j in &jobs {
        if !j.on.is_empty() && !mine.contains(&j.on.as_str()) && j.on_host != host && seat_at(&j.on_host).is_some() {
            others.push((j.on_host.clone(), j.on.clone(), false, j.id.clone()));
        }
    }
    for (h, q) in &b.queues {
        if h != host {
            for j in q.iter().filter(|j| mine.contains(&j.on.as_str())) {
                others.push((h.clone(), j.id.clone(), true, j.on.clone()));
            }
        }
    }
    let mut keep = vec![places[si]];
    keep.extend(others.iter().filter_map(|(h, ..)| seat_at(h)));
    step_back(ui, room, &keep);
    ui.outline2(rect(places[si].x - 3, places[si].y - 3, places[si].w + 6, places[si].h + 6), t.warn);
    // The stack, between its seat and the table.
    let (cw, ch, gap) = (184, 15, 4);
    let ((sx, sy), (hx, hy)) = (mid(places[si]), mid(hub));
    let n = jobs.len().max(1) as i32;
    let tot = n * (ch + gap);
    let x0 = (sx + (hx - sx) * 45 / 100 - cw / 2).clamp(room.x + 30, room.right() - cw - 4);
    let y0 = (sy + (hy - sy) * 45 / 100 - tot / 2).clamp(room.y + 2, (room.bottom() - tot - 2).max(room.y + 2));
    let chip = |k: usize| rect(x0, y0 + k as i32 * (ch + gap), cw, ch);
    let stack = rect(x0 - 4, y0 - 4, cw + 8, tot + 4);
    ui.c.rect(stack.x, stack.y, stack.w, stack.h, t.base);
    ui.outline(stack, t.warn);
    let (a, z) = (edge_of(places[si], mid(stack)), edge_of(stack, mid(places[si])));
    seg(ui, a, z, t.warn);
    // Chips of the others, beside their seats, toward the table.
    let mut count: Vec<(String, i32)> = Vec::new();
    let mut other_chip = Vec::new();
    for (h, id, _, _) in &others {
        let Some(r) = seat_at(h) else { continue };
        let k = match count.iter_mut().find(|(x, _)| x == h) {
            Some(c) => {
                c.1 += 1;
                c.1
            }
            None => {
                count.push((h.clone(), 0));
                0
            }
        };
        let (ox, oy) = mid(r);
        let (px, py) = (ox + (hx - ox) * 30 / 100, oy + (hy - oy) * 30 / 100);
        let c = rect((px - 70).clamp(room.x, room.right() - 140), py - 8 + k * (ch + gap), 140, ch);
        other_chip.push((id.clone(), c));
    }
    let chip_of = |id: &str| -> Option<Rect> {
        mine.iter().position(|x| *x == id).map(chip).or_else(|| other_chip.iter().find(|(x, _)| x == id).map(|(_, r)| *r))
    };
    let lit = |a: &str, z: &str| job.map(|f| f == a || f == z).unwrap_or(false);
    // The waits inside the stack: a bracket on its left from a job to the one it waits on.
    for (k, j) in jobs.iter().enumerate() {
        let Some(p) = mine.iter().position(|x| *x == j.on) else { continue };
        let c = if lit(&j.id, &j.on) { t.warn } else if j.wait == "build" { t.warn } else if j.wait == "after" { t.alarm } else { t.dim };
        let depth = (k as i32 - p as i32).abs().min(5);
        let x = x0 - 6 - depth * 4;
        let (ya, yz) = (chip(k).y + ch / 2, chip(p).y + ch / 2);
        seg(ui, (x0 - 1, ya), (x, ya), c);
        seg(ui, (x, ya), (x, yz), c);
        pointer(ui, (x, yz), (x0 - 1, yz), c);
    }
    // The waits between machines: from a job to the one it waits on, wherever that is.
    for (h, id, incoming, theirs) in &others {
        let _ = h;
        let (from, to) = if *incoming { (id.as_str(), theirs.as_str()) } else { (theirs.as_str(), id.as_str()) };
        let (Some(ra), Some(rz)) = (chip_of(from), chip_of(to)) else { continue };
        let (a, z) = (edge_of(ra, mid(rz)), edge_of(rz, mid(ra)));
        let c = if lit(from, to) { t.warn } else { t.alarm };
        pointer(ui, (a.0 + 1, a.1 + 1), (z.0 + 1, z.1 + 1), t.base);
        pointer(ui, a, z, c);
    }
    // The chips, over the lines.
    let draw_chip = |ui: &mut Ui, r: Rect, j: Option<&QJob>, id: &str, there: &str| {
        ui.c.rect(r.x, r.y, r.w, r.h, t.tile);
        ui.c.rect(r.x, r.y, 4, r.h, j.map(|j| line::colour(&j.stage)).unwrap_or(t.dim));
        let when = match j {
            Some(j) if j.state == "running" => "now".to_string(),
            Some(j) => j.start.map(|s| format!("+{}", took(s))).unwrap_or_default(),
            None => there.to_string(),
        };
        ui.label_in(r.x + 7, r.y + 3, r.w - 10, &format!("{} {}", id, when), &F6X10, if j.map(|j| j.state == "running").unwrap_or(false) { t.up } else { t.ink });
        if job == Some(id) {
            ui.outline2(rect(r.x - 2, r.y - 2, r.w + 4, r.h + 4), t.warn);
        }
    };
    for (k, j) in jobs.iter().enumerate() {
        draw_chip(ui, chip(k), Some(j), &j.id, host);
        ui.tip(chip(k), || job_tip(j, host));
    }
    if jobs.is_empty() {
        ui.label_in(x0 + 6, y0 + 3, cw - 10, "nothing running or dealt to it", &F6X10, t.dim);
    }
    for ((h, id, _, _), (_, r)) in others.iter().zip(other_chip.iter()) {
        let theirs = b.queue_of(h).iter().find(|j| &j.id == id);
        draw_chip(ui, *r, theirs, id, h);
        if let Some(j) = theirs {
            ui.tip(*r, || job_tip(j, h));
        }
    }
}

/// The Lineup's filters: what kind of chain stands in it, and how it ended.
pub const LINEUP_KINDS: [&str; 5] = ["trials", "runs", "builds", "islands", "all"];
pub const LINEUP_ENDS: [&str; 4] = ["every end", "going", "won", "dead ends"];

fn kind_group(kind: &str) -> usize {
    match kind {
        "trial" => 0,
        "build" => 2,
        "island" => 3,
        "other" => 4,
        _ => 1,
    }
}

struct Item<'a> {
    from: f64,
    to: f64,
    stage: &'a str,
    id: &'a str,
    host: &'a str,
    ok: i64,
    wh: Option<f64>,
    hollow: bool,
    after: &'a str,
}

struct Group<'a> {
    id: &'a str,
    meta: Option<&'a ChainMeta>,
    items: Vec<Item<'a>>,
    sub: Vec<usize>,
    subs: usize,
    last: f64,
    going: bool,
}

impl Group<'_> {
    /// Each item's link: the job the planner names it after, or the latest that ended by its start.
    fn prev(&self, k: usize) -> Option<usize> {
        let b = &self.items[k];
        if !b.after.is_empty() {
            return (0..self.items.len()).find(|&p| p != k && self.items[p].id == b.after);
        }
        (0..self.items.len())
            .filter(|&p| p != k && self.items[p].to <= b.from + 0.05 && self.items[p].from < b.from)
            .max_by(|&p, &q| self.items[p].to.partial_cmp(&self.items[q].to).unwrap_or(std::cmp::Ordering::Equal))
    }
}

/// THE LINEUP (Paul, 5 November: "it has all the same elements as the timeline does, but it rearranges
/// each chain into its own gantt chart, with the blocks of the chain reassembled on each row, with
/// machines' names in job block ... this would unscramble the net trace of arrows to have each dead
/// end and each success clearly shown, and forks looking like nested accordions already open, showing
/// arrows and sub-rows"). Named for The Lineup of 1954: every chain stands in its own row. A chain's
/// head row says how it ended or where it stands; under it its jobs in time, a fork (a held-out read's
/// pieces) on sub-rows of its own, an arrow from each job to the next, a red wall where it died, a
/// green tag where it won, hollow blocks where the forecast deals what it waits for.
fn lineup(ui: &mut Ui, at: Rect, m: &Model, st: &mut State) {
    let t = ui.t;
    if m.lanes.is_empty() {
        ui.label_in(at.x + 4, at.y + 4, at.w - 8, "The planner has not written the timeline yet: it does at each plan, about a minute.", &F8X13, t.dim);
        return;
    }
    // The hour, the six hours, or each chain its own Gantt: stretched across the width from its first
    // job to its last, so every block has room for its machine and its job.
    let z = st.lineup_zoom.unwrap_or(2).min(2);
    let fit = z == 2;
    for (i, name) in ["hour", "hours", "each its own"].iter().enumerate() {
        let r = rect(at.x + 4 + [0, 64, 128][i], at.y, [60, 60, 112][i], 20);
        if i == z {
            ui.c.rect(r.x + 4, r.bottom(), r.w - 8, 2, t.up);
        }
        if ui.button(r, name, i != z) {
            st.lineup_zoom = Some(i);
        }
    }
    let past_min = if z == 0 { 60.0 } else { m.past_h.max(1.0) * 60.0 };
    // The chains: every job of the hours, by the chain it is a link of, and what the forecast deals each.
    let mut by: Vec<Group> = Vec::new();
    let mut at_of: std::collections::HashMap<&str, usize> = std::collections::HashMap::new();
    for l in &m.lanes {
        for j in &l.jobs {
            let i = match at_of.get(j.chain.as_str()) {
                Some(&i) => i,
                None => {
                    by.push(Group { id: &j.chain, meta: m.chains.iter().find(|c| c.id == j.chain), items: Vec::new(), sub: Vec::new(), subs: 0, last: f64::MIN, going: false });
                    at_of.insert(&j.chain, by.len() - 1);
                    by.len() - 1
                }
            };
            by[i].items.push(Item { from: j.from, to: j.to, stage: &j.stage, id: &j.id, host: &l.host, ok: j.ok, wh: j.wh, hollow: false, after: &j.after });
        }
    }
    for c in &m.chains {
        for n in &c.next {
            let (Some(a), Some(b)) = (n.from, n.to) else { continue };
            let i = match at_of.get(c.id.as_str()) {
                Some(&i) => i,
                None => {
                    by.push(Group { id: &c.id, meta: Some(c), items: Vec::new(), sub: Vec::new(), subs: 0, last: f64::MIN, going: false });
                    at_of.insert(&c.id, by.len() - 1);
                    by.len() - 1
                }
            };
            by[i].items.push(Item { from: a, to: b, stage: &n.stage, id: &n.id, host: &n.host, ok: 3, wh: None, hollow: true, after: "" });
        }
    }
    fn kind_of<'a>(g: &Group<'a>) -> &'a str {
        g.meta.map(|c| c.kind.as_str()).unwrap_or("other")
    }
    let mut counts = [0usize; 5];
    for g in by.iter().filter(|g| g.items.iter().any(|i| i.hollow || i.to >= -past_min)) {
        counts[kind_group(kind_of(g))] += 1;
        counts[4] += 1;
    }
    let kind = st.lineup_kind.min(LINEUP_KINDS.len() - 1);
    let mut x = at.x + 4 + 128 + 112 + 16;
    for (i, name) in LINEUP_KINDS.iter().enumerate() {
        let n = if i == 4 { by.iter().filter(|g| g.items.iter().any(|it| it.hollow || it.to >= -past_min)).count() } else { counts[i] };
        let say = format!("{} {}", name, n);
        let w = F8X13.measure(&say) as i32 + 16;
        let r = rect(x, at.y, w, 20);
        if i == kind {
            ui.c.rect(r.x + 4, r.bottom(), r.w - 8, 2, t.up);
        }
        if ui.button(r, &say, i != kind) {
            st.lineup_kind = i;
            st.lineup_off = 0;
        }
        x += w + 4;
    }
    let mut groups: Vec<Group> = by
        .into_iter()
        .filter(|g| g.items.iter().any(|i| i.hollow || i.to >= -past_min))
        .filter(|g| kind == 4 || kind_group(kind_of(g)) == kind)
        .collect();
    // How it ended: each ending a button with its count, the chosen one the rows shown.
    let end_of = |g: &Group| -> usize { match g.meta.and_then(|c| c.good) { None => 1, Some(true) => 2, Some(false) => 3 } };
    let end = st.lineup_end.min(LINEUP_ENDS.len() - 1);
    let mut ex = at.right() - 4;
    for (i, name) in LINEUP_ENDS.iter().enumerate().rev() {
        let n = groups.iter().filter(|g| i == 0 || end_of(g) == i).count();
        let say = format!("{} {}", name, n);
        let w = F8X13.measure(&say) as i32 + 16;
        ex -= w;
        let r = rect(ex, at.y, w, 20);
        if i == end {
            ui.c.rect(r.x + 4, r.bottom(), r.w - 8, 2, [t.ink, t.warn, t.up, t.alarm][i]);
        }
        if ui.button(r, &say, i != end) {
            st.lineup_end = i;
            st.lineup_off = 0;
        }
        ex -= 4;
    }
    groups.retain(|g| end == 0 || end_of(g) == end);
    for g in groups.iter_mut() {
        g.items.sort_by(|a, b| a.from.partial_cmp(&b.from).unwrap_or(std::cmp::Ordering::Equal));
        let mut ends: Vec<f64> = Vec::new();
        for it in &g.items {
            let r = match ends.iter().position(|e| *e <= it.from + 0.05) {
                Some(r) => r,
                None => {
                    ends.push(f64::MIN);
                    ends.len() - 1
                }
            };
            ends[r] = it.to;
            g.sub.push(r);
        }
        g.subs = ends.len();
        g.last = g.items.iter().filter(|i| !i.hollow).map(|i| i.to).fold(f64::MIN, f64::max);
        g.going = g.meta.map(|c| c.good.is_none()).unwrap_or(true) && g.items.iter().any(|i| i.hollow || i.ok == 2);
    }
    // Going first, then the won, then the dead ends; each the newest first.
    let rank = |g: &Group| match g.meta.and_then(|c| c.good) { None => 0, Some(true) => 1, Some(false) => 2 };
    groups.sort_by(|a, b| rank(a).cmp(&rank(b)).then(b.going.cmp(&a.going)).then(b.last.partial_cmp(&a.last).unwrap_or(std::cmp::Ordering::Equal)));
    // The page's frame, as the Timeline's: rows, then the fleet's watts under them.
    let label_w = 268;
    let head = 72;
    let foot = 40;
    let graph_h = if m.power.fleet_full > 0.0 && z < 2 { 88 } else { 0 };
    let area = rect(at.x, at.y + head, at.w, at.h - head - foot - if graph_h > 0 { graph_h + 20 } else { 0 });
    let mut lines: Vec<(usize, Option<usize>)> = Vec::new();
    for (gi, g) in groups.iter().enumerate() {
        lines.push((gi, None));
        if !st.lineup_shut.iter().any(|s| s == g.id) {
            lines.extend((0..g.subs).map(|r| (gi, Some(r))));
        }
    }
    let rh = 18;
    let mut off = st.lineup_off;
    let (list, first, count) = ui.scroll_list(area, lines.len(), rh, &mut off);
    st.lineup_off = off;
    let plot = rect(list.x + label_w, list.y, list.w - label_w - 4, list.h);
    let now_x = plot.x + plot.w * 7 / 10;
    let ahead_min = groups.iter().flat_map(|g| g.items.iter().filter(|i| i.hollow).map(|i| i.to)).fold(30.0_f64, f64::max).min(240.0);
    let xof = |min: f64| -> i32 {
        if min <= 0.0 {
            now_x + ((min.max(-past_min) / past_min) * (now_x - plot.x) as f64) as i32
        } else {
            now_x + ((min.min(ahead_min) / ahead_min) * (plot.right() - now_x) as f64) as i32
        }
    };
    let shown = count.min(lines.len().saturating_sub(first));
    let list_h = shown as i32 * rh;
    // Each chain's own span, for "each its own": from its first job to its last, the forecast's with it.
    let span: Vec<(f64, f64)> = groups.iter().map(|g| {
        let v: Vec<&Item> = g.items.iter().filter(|i| i.hollow || i.to >= -past_min).collect();
        let a = v.iter().map(|i| i.from).fold(f64::MAX, f64::min);
        let b = v.iter().map(|i| i.to).fold(f64::MIN, f64::max);
        (a, b.max(a + 1.0))
    }).collect();
    let gx = |gi: usize, min: f64| -> i32 {
        if fit {
            let (a, b) = span[gi];
            plot.x + 2 + (((min - a) / (b - a)).clamp(0.0, 1.0) * (plot.w - 70) as f64) as i32
        } else {
            xof(min)
        }
    };
    if fit {
        ui.label(list.x + 4, plot.y - 14, "each chain, its jobs from its first to its last, stretched across", &F8X13, t.ink);
    } else {
        hour_ticks(ui, plot, list_h.max(rh), past_min, ahead_min, z, &xof);
        ui.label(list.x + 4, plot.y - 14, "each chain, its jobs in time", &F8X13, t.ink);
    }
    // Where each visible line is.
    let mut y_of: std::collections::HashMap<(usize, Option<usize>), i32> = std::collections::HashMap::new();
    for (k, line) in lines.iter().enumerate().skip(first).take(shown) {
        y_of.insert(*line, list.y + (k - first) as i32 * rh);
    }
    for (k, (gi, sub)) in lines.iter().enumerate().skip(first).take(shown) {
        let g = &groups[*gi];
        let y = list.y + (k - first) as i32 * rh;
        let good = g.meta.and_then(|c| c.good);
        let tone = match good { Some(true) => t.up, Some(false) => t.alarm, None => t.warn };
        match sub {
            None => {
                let r = rect(list.x, y, plot.right() - list.x, rh - 1);
                ui.c.rect(r.x, r.y, r.w, r.h, t.tile);
                ui.c.rect(r.x, r.y, 3, r.h, tone);
                let shut = st.lineup_shut.iter().any(|s| s == g.id);
                let name_end = ui.label(r.x + 7, y + 2, &format!("{} {}", if shut { "+" } else { "-" }, g.id), &F8X13, t.ink);
                let say = g.meta.map(|c| c.say.as_str()).unwrap_or("");
                ui.label_in(name_end + 8, y + 4, list.x + label_w - name_end - 12, say, &F6X10, tone);
                // Its span, and how it ended, on its own head row.
                let real: Vec<&Item> = g.items.iter().filter(|i| !i.hollow && i.to >= -past_min).collect();
                if let (Some(a), Some(_)) = (real.first(), real.last()) {
                    let x0 = gx(*gi, a.from);
                    let x1 = gx(*gi, g.last);
                    if fit {
                        let (s0, s1) = span[*gi];
                        ui.label(plot.x + 2, y + 4, &format!("{} to {}: {}", clock(&m.timeline_at, s0), if s1 > 0.0 { format!("+{} on", took(s1)) } else { clock(&m.timeline_at, s1) }, took(s1 - s0)), &F6X10, t.dim);
                    }
                    ui.c.hline(x0, y + rh / 2, (x1 - x0).max(1), t.line);
                    let (word, c) = match good {
                        Some(true) => ("won", t.up),
                        Some(false) => ("dead end", t.alarm),
                        None => ("going", t.warn),
                    };
                    let w = F6X10.measure(word) as i32 + 6;
                    let tx = if fit { (x1 + 3).min(plot.right() - w - 2) } else { (x1 + 3).min(now_x - w - 2) };
                    ui.c.rect(tx, y + 3, w, rh - 7, c);
                    ui.label(tx + 3, y + 4, word, &F6X10, t.base);
                }
                if ui.button_hit(r) {
                    if shut {
                        st.lineup_shut.retain(|s| s != g.id);
                    } else {
                        st.lineup_shut.push(g.id.to_string());
                    }
                }
                let wh: f64 = g.items.iter().filter_map(|i| i.wh).sum();
                let hosts: std::collections::BTreeSet<&str> = g.items.iter().filter(|i| !i.hollow).map(|i| i.host).collect();
                ui.tip(r, || vec![
                    format!("{}: {}", g.id, say),
                    format!("{} jobs on {} machines in the last {:.0} h{}; {:.1} Wh, ${:.3}", g.items.iter().filter(|i| !i.hollow).count(), hosts.len(), past_min / 60.0,
                            if g.items.iter().any(|i| i.hollow) { format!(", {} more dealt", g.items.iter().filter(|i| i.hollow).count()) } else { String::new() }, wh, wh / 1000.0 * m.power.rate),
                    "A click folds it. Its sub-rows are its forks: jobs of it that ran at once, a held-out read's pieces among them.".to_string(),
                ]);
            }
            Some(r_) => {
                // The fork's line from the head, as an accordion stands open.
                let first_item = g.items.iter().zip(&g.sub).find(|(_, s)| *s == r_).map(|(i, _)| i);
                let n = g.sub.iter().filter(|s| **s == *r_).count();
                let tx = list.x + 12;
                ui.c.vline(tx, y - 2, if *r_ + 1 == g.subs { rh / 2 + 2 } else { rh + 1 }, t.line);
                ui.c.hline(tx, y + rh / 2, 8, t.line);
                if let Some(fi) = first_item {
                    ui.label_in(tx + 12, y + 4, label_w - 30, &format!("{}{}", line::short(fi.stage), if n > 1 { format!(" and {} more", n - 1) } else { String::new() }), &F6X10, t.dim);
                }
                for (it, _) in g.items.iter().zip(&g.sub).filter(|(_, s)| *s == r_) {
                    if !it.hollow && it.to < -past_min {
                        continue;
                    }
                    let (a, e) = (gx(*gi, it.from), gx(*gi, it.to));
                    let b = rect(a, y + 2, (e - a).max(2), rh - 5);
                    if it.hollow {
                        ui.outline(b, line::colour(it.stage));
                    } else {
                        ui.c.rect(b.x, b.y, b.w, b.h, if it.ok == 0 { t.alarm } else { line::colour(it.stage) });
                    }
                    // Its machine first, then its job, as much as there is room for.
                    let both = format!("{} {}", it.host, it.id);
                    let say = if F6X10.measure(&both) as i32 + 6 <= b.w { both } else { it.host.to_string() };
                    if b.w > 14 {
                        ui.label_in(b.x + 3, b.y + 2, b.w - 5, &say, &F6X10, if it.hollow { line::colour(it.stage) } else { t.base });
                    }
                    ui.tip(b, || vec![
                        format!("{}: {}, on {}", it.id, line::short(it.stage), if it.host.is_empty() { "the next free machine" } else { it.host }),
                        if it.hollow { format!("Forecast: starts in {}, ends in {}.", took(it.from), took(it.to)) }
                        else { format!("{} to {}, {}{}", clock(&m.timeline_at, it.from), if it.ok == 2 { "now".to_string() } else { clock(&m.timeline_at, it.to) }, took(it.to - it.from),
                                       match it.ok { 0 => ", failed or sent back", 2 => ", running", _ => "" }) },
                        it.wh.map(|w| format!("{:.1} Wh at the wall, ${:.4}", w, w / 1000.0 * m.power.rate)).unwrap_or_default(),
                        format!("Chain {}.", g.id),
                    ]);
                }
                // A dead end's wall: where its last job stopped.
                if good == Some(false) {
                    if let Some((it, _)) = g.items.iter().zip(&g.sub).filter(|(i, s)| *s == r_ && !i.hollow).max_by(|a, b| a.0.to.partial_cmp(&b.0.to).unwrap_or(std::cmp::Ordering::Equal)) {
                        if (it.to - g.last).abs() < 0.01 {
                            let x = gx(*gi, it.to) + 2;
                            ui.c.rect(x, y + 1, 3, rh - 3, t.alarm);
                        }
                    }
                }
            }
        }
    }
    // The arrows, over the blocks: from the job each followed to its own start.
    for (gi, g) in groups.iter().enumerate() {
        for k in 0..g.items.len() {
            let Some(p) = g.prev(k) else { continue };
            let (a, b) = (&g.items[p], &g.items[k]);
            if (!a.hollow && a.to < -past_min) || (g.sub[p] == g.sub[k] && b.from - a.to < 0.5) {
                continue;
            }
            let (Some(&ya), Some(&yb)) = (y_of.get(&(gi, Some(g.sub[p]))), y_of.get(&(gi, Some(g.sub[k])))) else { continue };
            let (x0, y0) = (gx(gi, a.to), ya + rh / 2);
            let (x1, y1) = (gx(gi, b.from).max(x0 + 3), yb + rh / 2);
            pointer(ui, (x0 + 1, y0 + 1), (x1 + 1, y1 + 1), t.base);
            pointer(ui, (x0, y0), (x1, y1), if b.hollow { t.dim } else { t.warn });
        }
    }
    if !fit {
        milestones(ui, m, plot, list_h.max(rh), rh, past_min, &xof, false);
        ui.c.vline(now_x, plot.y - 2, list_h + 4, t.ink);
        ui.c.vline(now_x + 1, plot.y - 2, list_h + 4, t.ink);
    }
    if graph_h > 0 {
        if let Some(src) = m.zoom.iter().find(|l| l.name == "day").filter(|l| !l.watts.is_empty()) {
            let g = rect(plot.x, area.bottom() + 16, plot.w, graph_h);
            power_graph(ui, m, src, g, rect(at.x + 4, g.y, 120, g.h), now_x, past_min, &xof);
        }
    }
    let y = at.bottom() - foot + 6;
    ui.label_in(at.x + 4, y, at.w - 8, "Each chain on its own rows, its jobs where they ran in time, each block its machine and job. A fork stands open under it on sub-rows: jobs of the chain that ran at once.", &F8X13, t.dim);
    ui.label_in(at.x + 4, y + 15, at.w - 8, "Arrows: the job each followed. Green: won (promoted, built, shipped). Red wall: a dead end. Amber: still going. Hollow: what the forecast deals it next.", &F8X13, t.dim);
}

/// The Lineup's and the Timeline's clock: the hour by ten minutes or the six hours by the hour, back
/// from now; the forecast by quarter, half or whole hours on.
fn hour_ticks(ui: &mut Ui, plot: Rect, h: i32, past_min: f64, ahead_min: f64, z: usize, xof: &dyn Fn(f64) -> i32) {
    let t = ui.t;
    let every = if z == 0 { 10.0 } else { 60.0 };
    let mut k = -past_min;
    while k < -0.5 {
        let x = xof(k);
        ui.c.vline(x, plot.y, h, t.line);
        let say = if z == 0 { format!("{} min", k as i32) } else { format!("{} h", (k / 60.0) as i32) };
        ui.label(x + 2, plot.y - 14, &say, &F8X13, t.dim);
        k += every;
    }
    let step = [15.0, 30.0, 60.0].into_iter().find(|s| ahead_min / s <= 4.0).unwrap_or(120.0);
    let mut k = step;
    while k <= ahead_min {
        let x = xof(k);
        ui.c.vline(x, plot.y, h, t.line);
        if x + 60 < plot.right() {
            ui.label(x + 2, plot.y - 14, &format!("+{}", took(k)), &F8X13, t.dim);
        }
        k += step;
    }
}

/// The Hit Parade's windows.
pub const PARADE_WINDOWS: [&str; 3] = ["today", "week", "all"];
/// The kinds of job, the columns of the wall, in the line's order.
const PARADE_KINDS: [&str; 10] = ["first", "read", "held", "families", "promote", "build", "proof", "transform", "islands", "other"];

/// THE HIT PARADE (Paul, 5 November: "generate a graph, a rate of type per machine, and keep the
/// statistic in a chart: a new screen, it's like a success counter matrix, a wall of success.
/// Approved by Von Glurt"). Named for Your Hit Parade, the countdown of the 1950s. Every machine a
/// row, every kind of job a column: each cell the jobs it did, the share that came back done, its
/// rate an hour and its energy a job. Beside the wall each machine's rate by kind as one bar; under
/// it a bar a day since the event log began. The planner keeps the tally by day (plan/timeline-bins.json).
fn parade(ui: &mut Ui, at: Rect, m: &Model, st: &mut State) {
    let t = ui.t;
    let p = &m.parade;
    if p.windows.is_empty() {
        ui.label_in(at.x + 4, at.y + 4, at.w - 8, "The planner has not written the Hit Parade yet: it does at its next pass, about a minute.", &F8X13, t.dim);
        return;
    }
    let wi = st.parade_win.min(PARADE_WINDOWS.len() - 1);
    let since = format!("since {}", p.since.get(5..10).unwrap_or(&p.since));
    for (i, name) in ["today", "the last 7 days", since.as_str()].iter().enumerate() {
        let r = rect(at.x + 4 + i as i32 * 152, at.y, 148, 20);
        if i == wi {
            ui.c.rect(r.x + 4, r.bottom(), r.w - 8, 2, t.up);
        }
        if ui.button(r, name, i != wi) {
            st.parade_win = i;
        }
    }
    let Some(w) = p.windows.iter().find(|x| x.name == PARADE_WINDOWS[wi]) else { return };
    let cell_of = |h: &str, k: &str| -> Option<&Tally> { w.cells.iter().find(|(x, _)| x == h).and_then(|(_, v)| v.iter().find(|(s, _)| s == k)).map(|(_, c)| c) };
    let all: Vec<&Tally> = w.cells.iter().flat_map(|(_, v)| v.iter().map(|(_, c)| c)).collect();
    let (done, failed): (f64, f64) = all.iter().fold((0.0, 0.0), |a, c| (a.0 + c.done, a.1 + c.failed));
    let wh: f64 = all.iter().map(|c| c.wh).sum();
    // The scoreboard: the counters that answer first.
    let board = [
        (format!("{:.0}", done), "jobs done".to_string(), t.up),
        (format!("{:.0}", failed), "not done".to_string(), if failed > 0.0 { t.alarm } else { t.dim }),
        (format!("{:.1}%", if done + failed > 0.0 { 100.0 * done / (done + failed) } else { 0.0 }), "came back done".to_string(), t.up),
        (format!("{:.0}", done / w.hours.max(0.01)), "jobs an hour".to_string(), t.ink),
        (format!("{:.1}", wh / 1000.0), format!("kWh, ${:.2}", wh / 1000.0 * m.power.rate), heat(0.75)),
    ];
    let mut x = at.x + 4;
    for (big, small, c) in &board {
        let r = rect(x, at.y + 28, 150, 44);
        ui.c.rect(r.x, r.y, r.w, r.h, t.tile);
        ui.outline(r, t.line);
        ui.label(r.x + 8, r.y + 4, big, &F10X20, *c);
        ui.label(r.x + 8, r.y + 28, small, &F6X10, t.dim);
        x += 156;
    }
    ui.label(x + 6, at.y + 32, &format!("over {:.0} h", w.hours), &F8X13, t.dim);
    if wi == 2 {
        ui.label(x + 6, at.y + 48, &format!("since {}", p.since), &F6X10, t.dim);
    }
    // The seal, top right: approved.
    von_glurt_seal(ui, at.right() - 62, at.y + 54, 50);
    // The wall.
    let kinds: Vec<&str> = PARADE_KINDS.iter().copied().filter(|k| all_kind(w, k)).collect();
    let hosts: Vec<&str> = m.lanes.iter().map(|l| l.host.as_str()).filter(|h| w.cells.iter().any(|(x, _)| x == h)).collect();
    let hist_h = 96;
    let top = at.y + 84;
    let rate_w = 260;
    let label_w = 120;
    let wall = rect(at.x + 4, top, at.w - rate_w - 16, at.h - (top - at.y) - hist_h - 22);
    let cw = ((wall.w - label_w) / (kinds.len() as i32 + 1).max(1)).min(112);
    let ch = (wall.h / (hosts.len() as i32 + 2).max(1)).clamp(24, 52);
    for (i, k) in kinds.iter().enumerate() {
        let r = rect(wall.x + label_w + i as i32 * cw, wall.y, cw - 3, 16);
        ui.c.rect(r.x, r.y + 12, r.w, 3, line::colour(k));
        ui.label_in(r.x + 2, r.y, r.w - 4, line::short(k), &F6X10, t.ink);
    }
    ui.label_in(wall.x + label_w + kinds.len() as i32 * cw + 2, wall.y, cw - 4, "every kind", &F6X10, t.ink);
    let col_max: Vec<f64> = kinds.iter().map(|k| hosts.iter().filter_map(|h| cell_of(h, k)).map(|c| c.done).fold(1.0, f64::max)).collect();
    let row_y = |r: usize| wall.y + 20 + r as i32 * ch;
    for (r, h) in hosts.iter().enumerate() {
        let y = row_y(r);
        ui.label_in(wall.x, y + 4, label_w - 6, h, &F8X13, t.ink);
        let mut tot = Tally::default();
        for (i, k) in kinds.iter().enumerate() {
            let c = cell_of(h, k);
            let r_ = rect(wall.x + label_w + i as i32 * cw, y, cw - 3, ch - 3);
            cell(ui, r_, c, col_max[i], w.hours, m.power.rate, k);
            if let Some(c) = c {
                tot.done += c.done;
                tot.failed += c.failed;
                tot.minutes += c.minutes;
                tot.wh += c.wh;
                let say = (h.to_string(), line::short(k));
                ui.tip(r_, || tally_tip(&say.0, say.1, c, w.hours, m.power.rate));
            }
        }
        let r_ = rect(wall.x + label_w + kinds.len() as i32 * cw, y, cw - 3, ch - 3);
        cell(ui, r_, Some(&tot), f64::MAX, w.hours, m.power.rate, "other");
    }
    // The totals of each kind, the wall's floor.
    let y = row_y(hosts.len());
    ui.label_in(wall.x, y + 4, label_w - 6, "every machine", &F8X13, t.ink);
    for (i, k) in kinds.iter().enumerate() {
        let mut tot = Tally::default();
        for h in &hosts {
            if let Some(c) = cell_of(h, k) {
                tot.done += c.done;
                tot.failed += c.failed;
                tot.minutes += c.minutes;
                tot.wh += c.wh;
            }
        }
        cell(ui, rect(wall.x + label_w + i as i32 * cw, y, cw - 3, ch - 3), Some(&tot), f64::MAX, w.hours, m.power.rate, k);
    }
    // Each machine's rate by kind, one bar: jobs an hour.
    let rr = rect(at.right() - rate_w - 4, top, rate_w, wall.h);
    ui.label(rr.x, rr.y, "jobs an hour, by kind", &F8X13, t.ink);
    let rate_of = |h: &str| -> f64 { kinds.iter().filter_map(|k| cell_of(h, k)).map(|c| c.done).sum::<f64>() / w.hours.max(0.01) };
    let most = hosts.iter().map(|h| rate_of(h)).fold(1.0, f64::max);
    for (r, h) in hosts.iter().enumerate() {
        let y = row_y(r) + ch / 2 - 6;
        let mut x = rr.x;
        let full = rr.w - 48;
        for k in &kinds {
            if let Some(c) = cell_of(h, k) {
                let bw = ((c.done / w.hours.max(0.01)) / most * full as f64).round() as i32;
                if bw > 0 {
                    ui.c.rect(x, y, bw, 12, line::colour(k));
                    x += bw;
                }
            }
        }
        ui.label(x + 4, y, &format!("{:.1}", rate_of(h)), &F6X10, t.ink);
    }
    // The history: a bar a day, done in green with what was not done in red on top.
    let hr = rect(at.x + 4, at.bottom() - hist_h - 4, at.w - 8, hist_h);
    ui.label(hr.x, hr.y, &format!("a bar a day since {}: jobs done, not done in red (each bar's kWh on the inspector)", p.since.get(..10).unwrap_or(&p.since)), &F8X13, t.ink);
    let bars = rect(hr.x, hr.y + 18, hr.w - 4, hr.h - 34);
    let most = p.days.iter().map(|d| d.1 + d.2).fold(1.0, f64::max);
    let n = p.days.len().max(1) as i32;
    let bw = (bars.w / n).clamp(6, 60);
    for (i, (d, ok, bad, whd)) in p.days.iter().enumerate() {
        let x = bars.x + i as i32 * bw;
        let h_ok = ((ok / most) * bars.h as f64).round() as i32;
        let h_bad = ((bad / most) * bars.h as f64).round().max(if *bad > 0.0 { 1.0 } else { 0.0 }) as i32;
        ui.c.rect(x, bars.bottom() - h_ok, bw - 3, h_ok, t.up);
        ui.c.rect(x, bars.bottom() - h_ok - h_bad, bw - 3, h_bad, t.alarm);
        if bw >= 40 {
            ui.label_in(x, bars.bottom() + 2, bw - 3, d.get(5..).unwrap_or(d), &F6X10, t.dim);
        }
        let r = rect(x, bars.y, bw - 3, bars.h);
        ui.tip(r, || vec![d.clone(), format!("{:.0} jobs done, {:.0} not", ok, bad), format!("{:.1} kWh drawn by them, ${:.2}", whd / 1000.0, whd / 1000.0 * m.power.rate)]);
    }
}

fn all_kind(w: &ParadeWindow, k: &str) -> bool {
    w.cells.iter().any(|(_, v)| v.iter().any(|(s, c)| s == k && c.done + c.failed > 0.0))
}

/// A counter on the wall: its count large, the share done, the rate an hour and the energy a job;
/// its lamp, along the top, as bright as its count is against its column's most.
fn cell(ui: &mut Ui, r: Rect, c: Option<&Tally>, col_max: f64, hours: f64, rate: f64, kind: &str) {
    let t = ui.t;
    ui.c.rect(r.x, r.y, r.w, r.h, t.tile);
    let Some(c) = c.filter(|c| c.done + c.failed > 0.0) else {
        ui.outline(r, t.line);
        return;
    };
    let lit = if col_max.is_finite() { (c.done / col_max).clamp(0.0, 1.0) } else { 1.0 };
    ui.c.rect(r.x, r.y, ((r.w as f64) * lit).round().max(2.0) as i32, 3, line::colour(kind));
    let share = 100.0 * c.done / (c.done + c.failed);
    ui.label(r.x + 4, r.y + 5, &format!("{:.0}", c.done), if r.h >= 44 { &F10X20 } else { &F8X13 }, t.ink);
    let tone = if share >= 99.0 { t.up } else if share >= 90.0 { t.warn } else { t.alarm };
    if r.h >= 44 {
        ui.label_right(r.right() - 4, r.y + 8, &format!("{:.0}%", share), &F6X10, tone);
        ui.label_in(r.x + 4, r.y + r.h - 13, r.w - 8, &format!("{:.1}/h {:.1}Wh", c.done / hours.max(0.01), c.wh / (c.done + c.failed)), &F6X10, t.dim);
    } else {
        ui.label_right(r.right() - 4, r.y + 6, &format!("{:.0}%", share), &F6X10, tone);
    }
    let _ = rate;
}

fn tally_tip(h: &str, k: &str, c: &Tally, hours: f64, rate: f64) -> Vec<String> {
    vec![
        format!("{}: {}", h, k),
        format!("{:.0} done, {:.0} not (failed, stopped or sent back): {:.1}% came back done", c.done, c.failed, 100.0 * c.done / (c.done + c.failed).max(1.0)),
        format!("{:.2} an hour over {:.0} h; {} a job on average", c.done / hours.max(0.01), hours, took(c.minutes / (c.done + c.failed).max(1.0))),
        format!("{:.1} Wh a job at the wall, {:.2} kWh in all, ${:.2}", c.wh / (c.done + c.failed).max(1.0), c.wh / 1000.0, c.wh / 1000.0 * rate),
    ]
}

/// THE VON GLURT SEAL OF APPROVAL, as the lab report's, in the console's few strokes: navy cloth, a
/// gold rim and a satin ring, the house's name and its word.
pub fn von_glurt_seal(ui: &mut Ui, cx: i32, cy: i32, r: i32) {
    let gold = 0xd4a640;
    let deep = 0x8a6418;
    ui.c.disc(cx, cy, r, deep);
    ui.c.disc(cx, cy, r - 3, gold);
    ui.c.disc(cx, cy, r - 6, 0x1c2747);
    for k in [r - 9, r - 10] {
        ui.c.ring(cx, cy, k, gold);
    }
    // The stitches round the rim.
    for i in 0..36 {
        let a = i as f64 * std::f64::consts::PI / 18.0;
        let (x, y) = (cx + ((r - 1) as f64 * a.cos()) as i32, cy + ((r - 1) as f64 * a.sin()) as i32);
        ui.c.rect(x, y, 2, 2, 0xf3d27a);
    }
    let w1 = F6X10.measure("VON GLURT") as i32;
    ui.label(cx - w1 / 2, cy - 15, "VON GLURT", &F6X10, gold);
    let w2 = F8X13.measure("APPROVED") as i32;
    ui.label(cx - w2 / 2, cy - 4, "APPROVED", &F8X13, 0xf3d27a);
    ui.c.hline(cx - 22, cy + 11, 44, gold);
    let w3 = F6X10.measure("MMXXVI XI V") as i32;
    ui.label(cx - w3 / 2, cy + 14, "MMXXVI XI V", &F6X10, gold);
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
    let table: Vec<line::Value> = line::values().into_iter().filter(|v| !v.long).collect();
    let operator = st.operator;
    // THE HOLD, A ROW WITH A BUTTON (the plan of 2 November, chapter 14: it was a file with none). Each
    // dial a person holds, its value, and Release, which runs `fleet-tune.py hold DIAL off`.
    let held_h = if m.held.is_empty() { 0 } else { 22 + 24 * m.held.len() as i32 };
    let body = rect(at.x, at.y + 36, at.w, at.h - 36 - held_h);
    value_rows(ui, body, &table, &m.values, operator, &mut st.tune);
    if !m.held.is_empty() {
        let mut y = body.bottom() + 2;
        ui.label_in(at.x + 4, y, at.w - 8, "Held by a person (hold.json): a trial that sets a dial to its held value does not promote itself; its reads go on.", &F8X13, t.dim);
        y += 20;
        for (dial, v) in &m.held {
            ui.label(at.x + 8, y + 4, &format!("{} at {}", dial, v), &F8X13, t.warn);
            if operator && ui.button(rect(at.x + 300, y, 72, 22), "Release", true) {
                st.tune = Some(format!("hold {} off", dial));
            }
            ui.tip(rect(at.x, y, at.w, 24), || vec![
                format!("{} is held at {}: w_pos_fortify 0.4 was held on 1 November by rules written before its read (A Stale Dial).", dial, v),
                "Release takes it out of hold.json; a trial there may then promote by the ordinary road.".to_string(),
                "Hold another with `tools/fleet-tune.py QUEUE hold DIAL VALUE`.".to_string(),
            ]);
            y += 24;
        }
    }
}

/// A row for each value, with a press to move it a step: here, and on Settings, Long run.
pub fn value_rows(ui: &mut Ui, at: Rect, table: &[line::Value], values: &[(String, f64, bool)], operator: bool, tune: &mut Option<String>) {
    let t = ui.t;
    let mut y = at.y;
    let row_h = (at.h / table.len().max(1) as i32).clamp(30, 46);
    let (lab, val, btn) = (220, 104, 28);
    for v in table {
        let r = rect(at.x, y, at.w, row_h - 3);
        ui.c.rect(r.x, r.y, r.w, r.h, t.tile);
        let now_ = values.iter().find(|x| x.0 == v.key);
        let (cur, moved) = now_.map(|x| (x.1, x.2)).unwrap_or((v.default, false));
        ui.label_in(r.x + 8, r.y + 3, lab - 10, v.label, &F8X13, t.ink);
        ui.label_in(r.x + 8, r.y + 17, lab - 10, &format!("from {} to {}, default {}", number(v.min, v.step), number(v.max, v.step), number(v.default, v.step)), &F6X10, t.dim);
        let mut x = r.x + lab;
        ui.label_right(x + val - 8, r.y + 3, &format!("{} {}", number(cur, v.step), v.unit), &F8X13, if moved { t.warn } else { t.ink });
        if moved {
            ui.label_right(x + val - 8, r.y + 17, "moved", &F6X10, t.warn);
        }
        x += val;
        if operator {
            let by = r.y + (r.h - 22) / 2;
            let down = (cur - v.step).max(v.min);
            let up = (cur + v.step).min(v.max);
            if ui.button(rect(x, by, btn, 22), "-", cur > v.min) {
                *tune = Some(format!("{} {}", v.key, down));
            }
            if ui.button(rect(x + btn + 3, by, btn, 22), "+", cur < v.max) {
                *tune = Some(format!("{} {}", v.key, up));
            }
            if moved && ui.button(rect(x + 2 * btn + 6, by, 62, 22), "Default", true) {
                *tune = Some(format!("{} default", v.key));
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
    fn a_chain_links_each_job_to_the_one_it_followed_across_machines() {
        let doc = r#"{"checked":"2026-11-05T13:50:00","timeline":{"past_h":6,"lanes":[
          {"host":"a","up":true,"jobs":[[-90,-80,"first",1,"w1","w1"],[-60,-50,"held",1,"h1-p1","w1"],[-40,-30,"other",1,"r9-k1","r9"]]},
          {"host":"b","up":true,"jobs":[[-79.98,-61,"read",1,"e1","w1"],[-60,-52,"held",0,"h1-p2","w1"]]}]}}"#;
        let m = Model::parse(doc);
        assert_eq!((m.lanes[1].jobs[0].id.as_str(), m.lanes[1].jobs[1].ok), ("e1", 0));
        let l = chain_links(&m, "w1");
        let shape: Vec<(&str, Option<&str>)> = l.iter().map(|(_, j, p)| (j.id.as_str(), p.map(|p| l[p].1.id.as_str()))).collect();
        // The read-on begins a moment before the first read is logged done; both pieces follow it.
        assert_eq!(shape, vec![("w1", None), ("e1", Some("w1")), ("h1-p1", Some("e1")), ("h1-p2", Some("e1"))]);
        assert!(chain_links(&m, "r9").iter().all(|(_, _, p)| p.is_none()));
        assert_eq!((clock(&m.checked, -90.0), clock(&m.checked, 15.0), clock("2026-11-05T00:20:00", -30.0)), ("12:20".to_string(), "14:05".to_string(), "23:50".to_string()));
    }

    #[test]
    fn a_zoom_reads_its_bins_and_dates_a_time_by_the_clock_then_on_the_wall() {
        let doc = r#"{"checked":"2026-11-05T13:00:00","timeline":{"past_h":6,"at":"2026-11-05T13:20:00","lanes":[{"host":"a","up":true}],
          "zoom":[{"name":"days","bin_min":30,"from_min":-10070,"begins_min":-11796,"lanes":[{"host":"a","bins":[[3,"first",60,"failed",5]]}],
                   "ticks":[[-6611,"Nov 1"]],"shifts":[[-6498.5,60]]}],
          "cuda":{"g1":{"top":"M0015-c-g1","best":-1.5,"median":-5.4,"per_day":7.6,"eta_h":23.2,"segments":211,"seg_min":8.6}}}}"#;
        let m = Model::parse(doc);
        let z = &m.zoom[0];
        assert_eq!((z.lanes[0].1[0].0, z.lanes[0].1[0].1.clone()), (3, vec![("first".to_string(), 60.0), ("failed".to_string(), 5.0)]));
        assert_eq!((z.ticks[0].1.as_str(), z.begins), ("Nov 1", Some(-11796.0)));
        // Minutes count from when the timeline was measured; before 1 November the clock read summer time.
        assert_eq!(z.stamp(&m.timeline_at, -11796.0), "Oct 28 09:44");
        assert_eq!(z.stamp(&m.timeline_at, -60.0), "Nov 5 12:20");
        assert_eq!((m.cuda[0].0.as_str(), m.cuda[0].1.eta_h, m.cuda[0].1.seg_min), ("g1", Some(23.2), Some(8.6)));
        assert_eq!(stamp("2024-03-01T00:10:00", -20.0), "Feb 29 23:50");
        assert_eq!(stamp("2026-01-01T00:00:00", -1.0), "Dec 31 23:59");
        assert_eq!(ZOOMS.iter().position(|z| *z == "hours"), Some(1), "none chosen is the six hours");
    }

    #[test]
    fn a_link_the_planner_names_is_followed_before_the_clock() {
        let doc = r#"{"timeline":{"past_h":6,"lanes":[
          {"host":"g","up":true,"jobs":[[-40,-30,"islands",1,"x-g-0007","island g",""],[-30,-20,"islands",1,"x-g-0008","island g",""]]},
          {"host":"c","up":true,"jobs":[[-15,-5,"other",1,"bridge-001-c","island g","x-g-0007"]]}]}}"#;
        let m = Model::parse(doc);
        let l = chain_links(&m, "island g");
        let by: Vec<(&str, Option<&str>)> = l.iter().map(|(_, j, p)| (j.id.as_str(), p.map(|p| l[p].1.id.as_str()))).collect();
        // By the clock the read would follow segment 8, the last ended; the planner says 7 made the milestone.
        assert_eq!(by[2], ("bridge-001-c", Some("x-g-0007")));
    }

    #[test]
    fn each_machine_has_its_queue_and_each_job_says_what_it_waits_on() {
        let doc = r#"{"blame":{"nodes":[{"host":"a"},{"host":"b"}],"queues":{
          "a":[{"id":"e1","stage":"read","state":"running","wait":"","on":"","on_host":"","start_min":-4,"end_min":null},
               {"id":"h1","stage":"held","state":"queued","wait":"after","on":"e2","on_host":"b","start_min":3,"end_min":11,"high":true}],
          "b":[{"id":"e2","stage":"read","state":"running","wait":"","start_min":-1}]},
          "unplaced":[{"id":"x-c-1","stage":"islands","state":"queued","wait":"no machine"}]}}"#;
        let m = Model::parse(doc);
        let q = m.blame.queue_of("a");
        assert_eq!((q.len(), q[1].on_host.as_str(), q[1].high, q[1].end), (2, "b", true, Some(11.0)));
        assert!(m.blame.queue_of("nobody").is_empty());
        assert_eq!(waits_on(&q[0], "a"), "running, 4 min in");
        assert_eq!(waits_on(&q[1], "a"), "after e2 on b, ~3 min");
        assert_eq!(waits_on(&m.blame.unplaced[0], ""), "no machine");
        assert!(job_tip(&q[1], "a").iter().any(|l| l.contains("between two machines")));
        assert_eq!(wrap("one two three four", 9), vec!["one two", "three", "four"]);
        assert!(job_is(Some(&("a".to_string(), Some("h1".to_string()))), "a", "h1") && !job_is(None, "a", "h1"));
    }

    #[test]
    fn the_fleets_watts_are_read_and_coloured_blue_to_red() {
        let doc = r#"{"timeline":{"past_h":6,"lanes":[{"host":"boburner","up":true,"jobs":[[-10,-4,"read",1,"e1","w1","",13.2]]}],
          "zoom":[{"name":"day","bin_min":5,"from_min":-1435,"lanes":[],"watts":{"boburner":[null,120,140]}}],
          "power":{"rate":0.17,"lanes_now":{"boburner":140,"boburner-cuda":80},"fleet_now_w":220,"fleet_full_w":1724,"kwh_24h":38.6,
                   "usd_24h":6.56,"usd_30d":196.7,"jobs_today":{"boburner":[316,1869.8]},"sampled":"14:26",
                   "boxes":[{"box":"boburner","cpu":"AMD Ryzen 7 3700X","gpu":"GeForce GTX 1070 Ti","full_w":220,"now_w":220,"busy_util":0.9,"gpu_busy_w":70.5,"samples":{"cpu":3,"gpu":3}}]}}}"#;
        let m = Model::parse(doc);
        assert_eq!(m.lanes[0].jobs[0].wh, Some(13.2));
        assert_eq!(m.zoom[0].watts[0].1, vec![None, Some(120.0), Some(140.0)], "none before the log begins");
        assert_eq!((m.power.fleet_full, m.power.lane_now("boburner-cuda"), m.power.today("boburner")), (1724.0, Some(80.0), Some((316.0, 1869.8))));
        assert_eq!(m.power.box_of("boburner-cuda").map(|b| b.full), Some(220.0), "a GPU lane is part of its box");
        assert_eq!((heat(0.0), heat(0.25), heat(0.5), heat(0.75), heat(1.0)), (0x2a5bd7, 0xf0f0f0, 0x9b4fd0, 0xf2c200, 0xe8332a));
        assert_eq!((heat(-1.0), heat(9.0), heat(f64::NAN)), (0x2a5bd7, 0xe8332a, 0x2a5bd7));
        assert_eq!(mix(0x000000, 0xffffff, 0.5), 0x808080);
    }

    #[test]
    fn the_lineup_reads_each_chains_end_and_the_hit_parade_its_tally() {
        let doc = r#"{"timeline":{"past_h":6,"lanes":[],
          "chains":{"w1":{"kind":"trial","good":false,"say":"dead end: dropped after 2 reads","next":[]},
                    "w2":{"kind":"trial","good":null,"say":"reading on","next":[[2.5,9,"read","e5","calber"],[null,null,"held","h1",""]]}},
          "parade":{"since":"2026-10-28 09:34","days":[["2026-11-05",2679,3,24043.8]],
                    "today":{"hours":14.8,"cells":{"macmini":{"first":[300,1,410.5,190.2]}}},"week":{"hours":159.8,"cells":{}},"all":{"hours":198.2,"cells":{}}}}}"#;
        let m = Model::parse(doc);
        let w1 = m.chains.iter().find(|c| c.id == "w1").unwrap();
        let w2 = m.chains.iter().find(|c| c.id == "w2").unwrap();
        assert_eq!((w1.good, w2.good, w2.next.len()), (Some(false), None, 2));
        assert_eq!((w2.next[0].host.as_str(), w2.next[1].from), ("calber", None), "a job no machine is dealt yet has no time");
        assert_eq!(m.parade.windows.iter().map(|w| w.name.as_str()).collect::<Vec<_>>(), vec!["today", "week", "all"]);
        assert_eq!(m.parade.windows[0].cells[0].1[0].1, Tally { done: 300.0, failed: 1.0, minutes: 410.5, wh: 190.2 });
        assert_eq!(m.parade.days[0].1, 2679.0);
        assert_eq!((kind_group("trial"), kind_group("patch"), kind_group("island"), kind_group("other")), (0, 1, 3, 4));
        let it = |id: &'static str, from: f64, to: f64, after: &'static str| Item { from, to, stage: "read", id, host: "a", ok: 1, wh: None, hollow: false, after };
        let g = Group { id: "w1", meta: None, items: vec![it("w1", -10.0, -8.0, ""), it("e1", -8.0, -5.0, ""), it("h1-p1", -5.0, -2.0, ""), it("h1-p2", -5.0, -3.0, "")], sub: vec![0, 0, 0, 1], subs: 2, last: -2.0, going: false };
        assert_eq!((g.prev(0), g.prev(1), g.prev(2), g.prev(3)), (None, Some(0), Some(1), Some(1)), "both pieces of the fork follow the read-on");
    }

    #[test]
    fn machines_that_will_not_fit_are_counted_not_cut() {
        let ms: Vec<String> = ["saskatchewan", "boburner", "calber"].iter().map(|x| x.to_string()).collect();
        assert_eq!(who(&ms, 20), "saskatchewan +2");
        assert_eq!(who(&[], 20), "no machine");
    }
}
