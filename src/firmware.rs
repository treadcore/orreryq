//! The Firmware view: every part's firmware on every machine, against what its maker publishes.
//!
//! Paul, 8 November: "I want copal to be able to scan and suggest or at least list version of SSD
//! nvme and all upgradable firmware and version numbers. I want a report ... the machine fleet
//! scripts and storage might need screens for this info." This is the report as a page: one row a
//! part, the parts that are behind or known bad first, with what each runs, the newest its maker
//! publishes, why, and what to type. It reads the Machines document (`tools/machines.py status`),
//! whose `firmware()` puts each part the probe read (`tools/fleet-firmware.sh`) against the table
//! of what is out, so the page and the Machines screen's Firmware line can never disagree.
//!
//! NOTHING HERE FLASHES FIRMWARE. Probe all reads every machine again, as the user; an update is a
//! person's act at the machine, and the row says which. "Not checked" is never "current": a part
//! with no entry in the table says so, and a part whose maker publishes nothing is current and says
//! that instead (docs/firmware-lab-report.md).

use crate::font::F8X13;
use crate::machines::{Firmware, Model};
use crate::nav;
use crate::ui::{rect, Ui};

const PAD: i32 = 10;

#[derive(Default)]
pub struct State {
    /// Every part, or only those behind, known bad and not checked (the default).
    pub all: bool,
    offset: usize,
    pub operator: bool,
    /// Probe all was pressed: the loop runs `machines.py probe all`.
    pub probe: bool,
    pub said: String,
}

impl State {
    pub fn new(operator: bool) -> State {
        State { operator, ..State::default() }
    }
}

/// The order a row is read in: the faults first, then what is behind, what nobody has checked, and
/// last what is current.
pub fn rank(state: &str) -> u8 {
    match state {
        "bad" => 0,
        "behind" => 1,
        "not checked" => 2,
        _ => 3,
    }
}

/// Every machine's parts, one machine a box: a CUDA lane is its machine's twin (the same target),
/// and the Mac reads no firmware. Sorted by rank, then machine, then the probe's own order.
pub fn rows(m: &Model, all: bool) -> Vec<(String, Firmware)> {
    let mut seen: Vec<&str> = Vec::new();
    let mut out: Vec<(String, Firmware, usize)> = Vec::new();
    for x in &m.machines {
        if x.firmware.is_empty() || seen.contains(&x.target.as_str()) {
            continue;
        }
        seen.push(&x.target);
        // The SMART report's own line is the summary's to say, not a part's.
        for (i, f) in x.firmware.iter().enumerate().filter(|(_, f)| f.part != "SMART report") {
            if all || f.state != "current" {
                out.push((x.name.clone(), f.clone(), i));
            }
        }
    }
    out.sort_by(|a, b| (rank(&a.1.state), &a.0, a.2).cmp(&(rank(&b.1.state), &b.0, b.2)));
    out.into_iter().map(|(n, f, _)| (n, f)).collect()
}

pub fn draw(ui: &mut Ui, m: &Model, st: &mut State) -> Option<nav::View> {
    let t = ui.t;
    let (rest, go, _) = nav::header(ui, nav::View::Firmware, true, "every part's firmware, against what its maker publishes", None);
    let body = rest.inset(PAD);
    if !m.why.is_empty() {
        ui.label_in(body.x, body.y + 8, body.w, &m.why, &F8X13, t.dim);
        return go;
    }
    let lh = F8X13.height as i32 + 6;
    let every = rows(m, true);
    let machines: Vec<&str> = {
        let mut v: Vec<&str> = every.iter().map(|(n, _)| n.as_str()).collect();
        v.sort();
        v.dedup();
        v
    };
    let count = |s: &str| every.iter().filter(|(_, f)| f.state == s).count();
    let smart = m.machines.iter().filter(|x| x.firmware.iter().any(|f| f.part == "SMART report" && f.state == "current")).count();
    let mut y = body.y;

    // ---- the summary, and the two buttons -------------------------------------------------
    let mut line = format!("{} parts on {} machines", every.len(), machines.len());
    for (n, what) in [(count("bad"), "known bad"), (count("behind"), "behind"), (count("current"), "current"), (count("not checked"), "not checked")] {
        if n > 0 {
            line += &format!(" · {} {}", n, what);
        }
    }
    let c = if count("bad") > 0 { t.alarm } else if count("behind") > 0 { t.warn } else { t.ink };
    ui.label_in(body.x, y, body.w - 330, &line, &F8X13, c);
    if ui.button(rect(body.right() - 320, y - 4, 100, 22), if st.all { "Not current" } else { "Every part" }, true) {
        st.all = !st.all;
        st.offset = 0;
    }
    if st.operator && ui.button(rect(body.right() - 210, y - 4, 100, 22), "Probe all", !st.probe) {
        st.probe = true;
    }
    y += lh;
    ui.label_in(body.x, y, body.w, &format!(
        "SMART saved on {} of {} machines (the daily update's scan, as root). A row is behind its maker's newest, current, or not checked; its tip has why and what to type.",
        smart, machines.len()), &F8X13, t.dim);
    y += lh + 4;

    // ---- the table ---------------------------------------------------------------------------
    let cols = [(0, "Machine"), (110, "Part"), (400, "Runs"), (600, "Newest"), (760, "State"), (860, "Why, and what to do")];
    for (x, h) in cols {
        ui.label(body.x + x, y, h, &F8X13, t.ink);
    }
    y += lh;
    let shown = rows(m, st.all);
    let foot = lh * 2 + 6;
    let area = rect(body.x, y, body.w, body.bottom() - y - foot);
    let (area, first, fit) = ui.scroll_list(area, shown.len(), lh, &mut st.offset);
    if shown.is_empty() {
        ui.label_in(area.x, area.y, area.w, "Nothing behind, bad or unchecked: Every part shows the rest.", &F8X13, t.up);
    }
    for (i, (name, f)) in shown.iter().enumerate().skip(first).take(fit) {
        let ry = area.y + (i - first) as i32 * lh;
        let sc = match f.state.as_str() {
            "bad" => t.alarm,
            "behind" => t.warn,
            "current" => t.up,
            _ => t.dim,
        };
        let w = |from: i32, to: i32| (to - from - 8).max(10);
        ui.label_in(area.x, ry, w(0, 110), name, &F8X13, t.ink);
        ui.label_in(area.x + 110, ry, w(110, 400), &f.part, &F8X13, t.ink);
        ui.label_in(area.x + 400, ry, w(400, 600), if f.now.is_empty() { "-" } else { &f.now }, &F8X13, t.ink);
        let newest = if f.newest.is_empty() { "-" } else if f.newest == f.now { "same" } else { &f.newest };
        ui.label_in(area.x + 600, ry, w(600, 760), newest, &F8X13, if f.newest != f.now && !f.newest.is_empty() { sc } else { t.dim });
        ui.label_in(area.x + 760, ry, w(760, 860), &f.state, &F8X13, sc);
        let why = if !f.how.is_empty() && f.state != "current" { format!("{} · {}", f.how, f.why) } else { f.why.clone() };
        ui.label_in(area.x + 860, ry, (area.w - 860).max(10), &why, &F8X13, t.dim);
        ui.tip(rect(area.x, ry - 2, area.w, lh - 2), || {
            let mut v = vec![format!("{}: {}  {}{}", name, f.part, if f.now.is_empty() { "-" } else { &f.now }, if f.newest.is_empty() || f.newest == f.now { String::new() } else { format!(" -> {}", f.newest) })];
            v.push(format!("{}{}", f.state, if f.why.is_empty() { String::new() } else { format!(": {}", f.why) }));
            if !f.how.is_empty() {
                v.push(format!("How: {}", f.how));
            }
            v
        });
    }

    // ---- the foot: how each kind is updated, in a line -----------------------------------------
    let fy = body.bottom() - foot + 6;
    ui.label_in(body.x, fy, body.w, "How: microcode, the recipe on Machines · a BIOS, its maker's flash tool from a USB stick, at the console · a Samsung SSD, its ISO · fwupd's, sudo fwupdmgr update · Finish the machine first", &F8X13, t.dim);
    let said = if st.said.is_empty() { "Nothing here flashes firmware: it reads, and a row says what to type. The lab report: Every Part's Firmware (docs/firmware-lab-report.md).".to_string() } else { st.said.clone() };
    ui.label_in(body.x, fy + lh, body.w, &said, &F8X13, t.dim);
    go
}

#[cfg(test)]
mod tests {
    use super::*;

    fn doc() -> Model {
        Model::parse(r#"{"machines": [
            {"name": "boburner", "target": "user@boburner", "firmware": [
                {"part": "BIOS", "now": "F52h 07/27/2022", "newest": "F55d", "state": "behind", "why": "Gigabyte", "how": "Q-Flash"},
                {"part": "sda HGST HDN726040ALE614", "now": "APGNW7JH", "newest": "APGNW7JH", "state": "current", "why": "WD publishes none", "how": ""}]},
            {"name": "boburner-cuda", "target": "user@boburner", "firmware": [
                {"part": "BIOS", "now": "F52h 07/27/2022", "newest": "F55d", "state": "behind", "why": "Gigabyte", "how": "Q-Flash"}]},
            {"name": "jaguaribe", "target": "user@jaguaribe", "firmware": [
                {"part": "eth2 mlx4_core", "now": "2.9.1000", "newest": "", "state": "not checked", "why": "mstflint query", "how": ""},
                {"part": "sdk HGST HTS541010A9E680", "now": "JA0OA7J0", "newest": "", "state": "bad", "why": "SMART: smart FAILED!", "how": "back it up now"}]},
            {"name": "mac", "target": "-", "firmware": []}]}"#)
    }

    #[test]
    fn the_faults_come_first_then_what_is_behind_then_what_nobody_checked() {
        let r = rows(&doc(), false);
        let got: Vec<(&str, &str)> = r.iter().map(|(n, f)| (n.as_str(), f.state.as_str())).collect();
        assert_eq!(got, vec![("jaguaribe", "bad"), ("boburner", "behind"), ("jaguaribe", "not checked")]);
    }

    #[test]
    fn a_cuda_lane_is_its_machine_not_a_second_one_and_the_mac_has_no_rows() {
        let r = rows(&doc(), true);
        assert_eq!(r.len(), 4, "boburner-cuda's twin rows and the Mac's none are left out");
        let with_report = Model::parse(r#"{"machines": [{"name": "calber", "target": "user@calber", "firmware": [
            {"part": "SMART report", "now": "none", "newest": "", "state": "not checked", "why": "", "how": ""}]}]}"#);
        assert!(rows(&with_report, true).is_empty(), "the SMART report is the summary's line, not a part");
        assert!(r.iter().all(|(n, _)| n != "boburner-cuda" && n != "mac"));
        assert_eq!(r.last().map(|(_, f)| f.state.as_str()), Some("current"), "current parts come last, and only on Every part");
    }
}
