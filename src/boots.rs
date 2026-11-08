//! Settings, After a cut: what a power cut did, read by the keeper instead of by hand (Paul, 8
//! November: "The actions we are doing after a power loss, should be done auto, with GUI buttons").
//!
//! The document is `tools/boots.py`'s (QUEUE/plan/boots.json): the last cut -- when the fleet went
//! quiet, the first machine up, this Mac, the keeper -- each machine's boot against THE BOOT BEFORE
//! IT, the GPU islands' saves read for zeros, and the jobs the cut interrupted read again when they
//! came back. THE PAGE DRAWS AND ASKS; IT READS NO MACHINE ITSELF. Check now and Accept are verbs for
//! `fleet-queue.py QUEUE boots ...`, run by main as the other queue controls are, and are not drawn
//! for a viewer.
//!
//! A CHANGE IS A SENTENCE, NOT A VERDICT. "CSM off -> on" may be the restore that missed a setting
//! (calber, 8 November) or the setting a person meant; the page says what changed and Accept says it
//! was meant, after which the next boot is compared with this one. A damaged save is the one red
//! here: the segment that loads it starts from a state the cut broke.
//!
//! WHAT IS NOT READ IS SAID: the memory's speed (dmidecode needs root) and AC BACK (kept where Linux
//! cannot see it), so nobody takes their absence for a pass.
use crate::font::F8X13;
use crate::json::Value;
use crate::ui::{rect, Light, Rect, Ui};

fn s<'a>(v: &'a Value, k: &str) -> &'a str {
    v.get(k).and_then(|x| x.as_str()).unwrap_or("")
}

fn n(v: &Value, k: &str) -> Option<f64> {
    v.get(k).and_then(|x| x.as_num())
}

fn arr<'a>(v: &'a Value, k: &str) -> &'a [Value] {
    v.get(k).and_then(|x| x.as_array()).unwrap_or(&[])
}

/// The record's own level: 2 for a damaged save or a queue file that does not read back, 1 for a
/// machine back different or a job's result with zeros in it, 0 otherwise. The column's key lamp.
pub fn level(doc: &Value) -> u8 {
    match arr(doc, "health").first().and_then(|l| l.as_str()) {
        Some("bad") => 2,
        Some("warn") => 1,
        _ => 0,
    }
}

const MONTHS: [&str; 12] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/// "2026-11-07T21:01:56" as "7 Nov 21:01".
fn when(iso: &str) -> String {
    let (d, t) = iso.split_once('T').unwrap_or((iso, ""));
    let p: Vec<&str> = d.split('-').collect();
    match (p.get(1).and_then(|m| m.parse::<usize>().ok()), p.get(2).and_then(|x| x.parse::<u32>().ok())) {
        (Some(m), Some(day)) if (1..=12).contains(&m) => format!("{} {} {}", day, MONTHS[m - 1], t.get(..5).unwrap_or(t)),
        _ => iso.to_string(),
    }
}

/// Seconds since 1970 of a local stamp, for the gaps between the cut's moments (both ends local).
fn secs(iso: &str) -> Option<i64> {
    let (d, t) = iso.split_once('T')?;
    let dp: Vec<i64> = d.split('-').filter_map(|x| x.parse().ok()).collect();
    let tp: Vec<i64> = t.get(..8)?.split(':').filter_map(|x| x.parse().ok()).collect();
    if dp.len() != 3 || tp.len() != 3 {
        return None;
    }
    // Days from the civil date (Howard Hinnant's algorithm).
    let (y, m, day) = (if dp[1] <= 2 { dp[0] - 1 } else { dp[0] }, dp[1], dp[2]);
    let era = y.div_euclid(400);
    let yoe = y - era * 400;
    let doy = (153 * (m + if m > 2 { -3 } else { 9 }) + 2) / 5 + day - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    Some((era * 146097 + doe - 719468) * 86400 + tp[0] * 3600 + tp[1] * 60 + tp[2])
}

fn span(s: i64) -> String {
    if s >= 3600 {
        format!("{} h {:02} m", s / 3600, s / 60 % 60)
    } else {
        format!("{} min", s / 60)
    }
}

/// The cut in a sentence: quiet from, the first machine up, this Mac, the keeper, and the wait.
pub fn cut_sentence(doc: &Value) -> String {
    let Some(c) = doc.get("cut").filter(|c| !matches!(c, Value::Null)) else {
        return "No cut on record yet: a keeper that starts after one that never ended writes one (QUEUE/cut.json).".into();
    };
    let mut parts = vec![format!("The last cut: quiet from {}", when(s(c, "quiet_since")))];
    let first = c.get("first_up").map(|f| (s(f, "at").to_string(), s(f, "machine").to_string()));
    if let Some((at, who)) = &first {
        parts.push(format!("the first machine up at {} ({})", when(at), who));
    }
    if !s(c, "mac_booted").is_empty() {
        parts.push(format!("this Mac at {}", when(s(c, "mac_booted"))));
    }
    let back = s(c, "keeper_back");
    let mut keeper = format!("the keeper at {}", when(back));
    let from = first.as_ref().map(|f| f.0.as_str()).filter(|x| !x.is_empty()).unwrap_or(s(c, "mac_booted"));
    if let (Some(a), Some(b)) = (secs(from), secs(back)) {
        if b > a {
            keeper = format!("{}, {} after the first machine", keeper, span(b - a));
        }
    }
    parts.push(keeper);
    let q = n(c, "requeued").unwrap_or(0.0) as i64;
    format!("{}. {} job{} went back on the queue.", parts.join("; "), q, if q == 1 { "" } else { "s" })
}

/// A boot's facts as the firmware column reads them.
fn firmware_words(f: &Value) -> String {
    let mut w = Vec::new();
    if !s(f, "firmware").is_empty() {
        w.push(s(f, "firmware").split_whitespace().collect::<Vec<_>>().join(" "));
    }
    match s(f, "uefi") {
        "yes" => w.push("UEFI".into()),
        "no" => w.push("BIOS".into()),
        _ => {}
    }
    if !s(f, "csm").is_empty() {
        w.push(format!("CSM {}", s(f, "csm")));
    }
    if !s(f, "secure_boot").is_empty() {
        w.push(format!("Secure Boot {}", s(f, "secure_boot")));
    }
    if !s(f, "boot_entry").is_empty() {
        w.push(format!("boots {} of {}", s(f, "boot_entry"), s(f, "boot_entries")));
    }
    if w.is_empty() && !s(f, "system").is_empty() {
        w.push(s(f, "system").to_string());
    }
    w.join(", ")
}

/// The start-up's stages in seconds, firmware first.
fn timing_words(t: Option<&Value>) -> String {
    let Some(t) = t else { return String::new() };
    let stages = [("firmware", "firmware"), ("loader", "loader"), ("kernel", "kernel"), ("initrd", "initrd"), ("userspace", "user")];
    let got: Vec<(f64, &str)> = stages.iter().filter_map(|(k, w)| n(t, k).map(|v| (v, *w))).collect();
    if got.is_empty() {
        return String::new();
    }
    let total: f64 = got.iter().map(|g| g.0).sum();
    format!("{:.0} s: {}", total, got.iter().map(|(v, w)| format!("{} {:.0}", w, v)).collect::<Vec<_>>().join(", "))
}

/// What a saved island's read says is wrong with it, or None (boots.py's island_harm).
fn harm(i: &Value) -> Option<String> {
    if n(i, "bytes").unwrap_or(0.0) == 0.0 {
        return Some("is empty".into());
    }
    let z = n(i, "zero").unwrap_or(0.0);
    (z > 0.0).then(|| format!("has {} zeroed blocks of {}", z, n(i, "blocks").unwrap_or(0.0)))
}

fn home_of(path: &str) -> &str {
    path.rsplit('/').nth(1).unwrap_or(path)
}

/// One machine's row, worked out before drawing: its lamp's level, and its words.
struct Row<'a> {
    name: &'a str,
    m: &'a Value,
    dark: bool,
    harmed: Vec<String>,
    changed: Vec<String>,
    accepted: bool,
}

fn rows_of(doc: &Value) -> Vec<Row<'_>> {
    let mut out = Vec::new();
    if let Some(Value::Obj(ms)) = doc.get("machines") {
        for (name, m) in ms {
            let boot = m.get("boot");
            let harmed = boot.map(|b| arr(b, "islands").iter().filter_map(|i| harm(i).map(|h| format!("{} {}", home_of(s(i, "path")), h))).collect()).unwrap_or_default();
            let changed: Vec<String> = boot
                .map(|b| arr(b, "changed").iter().filter_map(|c| c.as_array()).filter(|c| c.len() == 3)
                    .map(|c| format!("{} {} → {}", nice(c[0].as_str().unwrap_or("")), c[1].as_str().unwrap_or(""), c[2].as_str().unwrap_or("")))
                    .collect())
                .unwrap_or_default();
            let accepted = boot.map(|b| !s(b, "id").is_empty() && s(m, "accepted") == s(b, "id")).unwrap_or(false);
            out.push(Row { name: name.as_str(), m, dark: m.get("reach").and_then(|r| r.as_bool()) == Some(false), harmed, changed, accepted });
        }
    }
    // The machines that want a look come first: a damaged save, then the dark, then back different.
    out.sort_by_key(|r| (r.harmed.is_empty(), !r.dark, r.changed.is_empty() || r.accepted, r.name.to_string()));
    out
}

fn nice(k: &str) -> &str {
    match k {
        "uefi" => "UEFI",
        "csm" => "CSM",
        "secure_boot" => "Secure Boot",
        "boot_entry" => "booted from",
        "boot_entries" => "boot entries",
        "gpu" => "GPU",
        other => other,
    }
}

/// The page. `ctl` takes a verb for `fleet-queue.py QUEUE boots ...`; `said` is the last answer.
pub fn draw(ui: &mut Ui, at: Rect, doc: Option<&Value>, operator: bool, said: &str, ctl: &mut Option<String>) {
    let t = ui.t;
    let lh = F8X13.height as i32 + 3;
    let Some(doc) = doc.filter(|d| d.get("machines").is_some()) else {
        ui.label_in(at.x, at.y, at.w, "No record yet: the keeper asks tools/boots.py at its start (or run fleet-queue.py QUEUE boots check).", &F8X13, t.dim);
        return;
    };
    let side = if operator { 230 } else { 0 };
    let mut y = at.y;
    // The cut, then the record's own line.
    for l in crate::line::wrap(&cut_sentence(doc), &F8X13, at.w - side - 10) {
        ui.label_in(at.x, y, at.w - side - 10, &l, &F8X13, t.ink);
        y += lh;
    }
    if operator {
        if ui.button(rect(at.right() - side + 10, at.y, side - 10, 26), "Check every machine now", true) {
            *ctl = Some("boots check --force".into());
        }
        if !said.is_empty() {
            ui.label_in(at.right() - side + 10, at.y + 32, side - 10, said, &F8X13, t.dim);
        }
    }
    let health = arr(doc, "health");
    let (lv, text) = (health.first().and_then(|x| x.as_str()).unwrap_or("ok"), health.get(1).and_then(|x| x.as_str()).unwrap_or(""));
    let c = match lv {
        "bad" => t.alarm,
        "warn" => t.warn,
        _ => t.up,
    };
    y += 4;
    for (i, l) in crate::line::wrap(text, &F8X13, at.w - side - 28).iter().enumerate() {
        if i == 0 {
            ui.c.disc(at.x + 6, y + lh / 2 - 1, 5, c);
        }
        ui.label_in(at.x + 18, y, at.w - side - 28, l, &F8X13, if lv == "ok" { t.dim } else { t.ink });
        y += lh;
    }
    y = y.max(at.y + 64) + 10;

    // The machines: a row each -- its boot, start-up, GPU and islands; under it the firmware as read;
    // under that what changed since the boot before, and Accept.
    let cols = [("machine", 140), ("booted", 170), ("start-up", 400), ("GPU", 220), ("islands", 0)];
    let fixed: i32 = cols.iter().map(|c| c.1).sum();
    let widths: Vec<i32> = cols.iter().map(|c| if c.1 == 0 { (at.w - fixed).max(160) } else { c.1 }).collect();
    let mut x = at.x;
    for (i, (h, _)) in cols.iter().enumerate() {
        ui.label_in(x + if i == 0 { 18 } else { 0 }, y, widths[i] - 10, h, &F8X13, t.dim);
        x += widths[i];
    }
    y += lh + 2;
    ui.hrule(at.x, y - 3, at.w);
    for r in rows_of(doc) {
        if y + 2 * lh > at.bottom() - 4 * lh {
            break;
        }
        let boot = r.m.get("boot");
        let facts = boot.and_then(|b| b.get("facts"));
        let want = !r.changed.is_empty() && !r.accepted;
        let (light, colour) = if !r.harmed.is_empty() {
            (Light::Full, t.alarm)
        } else if r.dark {
            (Light::Hollow, t.warn)
        } else if want {
            (Light::Full, t.warn)
        } else {
            (Light::Full, t.up)
        };
        let row_y = y;
        ui.light(at.x + 6, y + lh / 2 - 1, 4, light, colour);
        let state = if r.dark {
            format!("dark since {}", when(s(r.m, "dark_since")))
        } else {
            match boot.map(|b| s(b, "booted_at")).filter(|b| !b.is_empty()) {
                Some(at) => format!("booted {}", when(at)),
                None => "up".into(),
            }
        };
        let gpu = facts.map(|f| s(f, "gpu").replace("NVIDIA GeForce ", "")).unwrap_or_default();
        let islands = boot.map(|b| {
            let is = arr(b, "islands");
            if is.is_empty() {
                String::new()
            } else if !r.harmed.is_empty() {
                r.harmed.join("; ")
            } else {
                let gen = is.iter().filter_map(|i| n(i, "gen")).fold(0.0f64, f64::max);
                format!("{} saves whole{}", is.len(), if gen > 0.0 { format!(", newest gen {}", thousands(gen as i64)) } else { String::new() })
            }
        }).unwrap_or_default();
        let cells = [r.name.to_string(), state, timing_words(boot.and_then(|b| b.get("timing"))), gpu, islands];
        let mut x = at.x;
        for (i, cell) in cells.iter().enumerate() {
            let col = if i == 1 && r.dark { t.warn } else if i == 4 && !r.harmed.is_empty() { t.alarm } else if i == 0 { t.ink } else { t.dim };
            let cell = if cell.is_empty() && i > 0 { "—".to_string() } else { cell.clone() };
            let inset = if i == 0 { 18 } else { 0 };
            ui.label_in(x + inset, y, widths[i] - 12 - inset, &cell, &F8X13, col);
            x += widths[i];
        }
        y += lh;
        if let Some(f) = facts {
            let mut fw = firmware_words(f);
            if !s(f, "system").is_empty() && s(f, "firmware").is_empty() == false {
                fw = format!("{}; {}", fw, s(f, "system"));
            }
            ui.label_in(at.x + 18, y, at.w - 30, &fw, &F8X13, t.dim);
            y += lh;
        }
        if !r.changed.is_empty() {
            let before = r.m.get("before");
            let since = before.map(|b| s(b, "booted_at")).filter(|v| !v.is_empty()).map(|at| format!("since the boot of {}", when(at))).unwrap_or_else(|| "since the boot before".into());
            let line = format!("{}: {}{}", since, r.changed.join(", "), if r.accepted { "; accepted as its normal" } else { "" });
            let bw = 90;
            ui.label_in(at.x + 18, y, at.w - 30 - bw, &line, &F8X13, if want { t.warn } else { t.dim });
            if operator && want && ui.button(rect(at.right() - bw, y - 3, bw, 20), "Accept", true) {
                *ctl = Some(format!("boots accept {}", r.name));
            }
            y += lh + 3;
        }
        let name = r.name.to_string();
        let m = r.m;
        ui.tip(rect(at.x, row_y, at.w - if operator && want { 100 } else { 0 }, y - row_y), || tip_lines(&name, m));
        y += 6;
    }

    // The jobs the cut interrupted, and what is not read.
    let mut foot = Vec::new();
    let jobs = arr(doc, "cut_jobs");
    if !jobs.is_empty() {
        let bad: Vec<String> = jobs
            .iter()
            .flat_map(|j| arr(j, "bad").iter().map(move |b| format!("{}: {} carries {} zero bytes from line {}", s(j, "job"), s(b, "file").rsplit('/').next().unwrap_or(""), n(b, "zero").unwrap_or(0.0), n(b, "line").unwrap_or(0.0))))
            .collect();
        foot.push((format!("The jobs the cut interrupted ({}), read again when they came back: {}", jobs.len(), if bad.is_empty() { "none carries zeros".into() } else { bad.join("; ") }), !bad.is_empty()));
    }
    let qf = doc.get("queue_files");
    if let Some(qf) = qf {
        let bad = arr(qf, "bad");
        foot.push((format!("The queue's own files: {} read back, {}.", n(qf, "read").unwrap_or(0.0), if bad.is_empty() { "none bad".to_string() } else { format!("these do not: {}", bad.iter().filter_map(|b| b.as_str()).collect::<Vec<_>>().join(", ")) }), !bad.is_empty()));
    }
    foot.push(("Not read: the memory's speed (dmidecode needs root) and AC BACK (the firmware keeps it out of Linux's sight).".into(), false));
    foot.push((format!("Read {} by tools/boots.py: the keeper asks at its start, when a machine it could not reach answers, and every ten minutes; a machine is read once a boot.", when(s(doc, "checked"))), false));
    let mut fy = (y + 8).max(at.bottom() - foot.len() as i32 * lh);
    for (text, warn) in foot {
        if fy + lh > at.bottom() + 2 {
            break;
        }
        ui.label_in(at.x, fy, at.w, &text, &F8X13, if warn { t.warn } else { t.dim });
        fy += lh;
    }
}

fn thousands(v: i64) -> String {
    let s = v.to_string();
    let mut out = String::new();
    for (i, c) in s.chars().enumerate() {
        if i > 0 && (s.len() - i) % 3 == 0 {
            out.push(',');
        }
        out.push(c);
    }
    out
}

fn tip_lines(name: &str, m: &Value) -> Vec<String> {
    let mut v = vec![name.to_string()];
    if let Some(b) = m.get("boot") {
        let f = b.get("facts");
        for k in ["system", "kernel", "board", "firmware", "gpu"] {
            if let Some(x) = f.map(|f| s(f, k)).filter(|x| !x.is_empty()) {
                v.push(format!("{}: {}", k, x));
            }
        }
        for i in arr(b, "islands") {
            v.push(format!("{}: {} bytes{}{}", home_of(s(i, "path")), thousands(n(i, "bytes").unwrap_or(0.0) as i64),
                n(i, "gen").map(|g| format!(", gen {}", thousands(g as i64))).unwrap_or_default(),
                harm(i).map(|h| format!(", {}", h)).unwrap_or_default()));
        }
        v.push(format!("read {}", when(s(b, "read"))));
    }
    if let Some(src) = m.get("before").map(|b| s(b, "source")).filter(|x| !x.is_empty()) {
        v.push(format!("the boot before: {}", src));
    }
    v.push("Source: tools/boots.py (QUEUE/plan/boots.json).".into());
    v
}

#[cfg(test)]
mod tests {
    use super::*;

    const DOC: &str = r#"{"checked": "2026-11-08T09:27:40",
      "cut": {"quiet_since": "2026-11-07T21:01:56", "keeper_back": "2026-11-08T07:47:58", "requeued": 12,
              "mac_booted": "2026-11-08T05:49:42", "first_up": {"at": "2026-11-08T04:48:14", "machine": "macmini"}},
      "health": ["warn", "calber came back different (CSM off -> on)"],
      "cut_jobs": [{"job": "x-calber-cuda-3345", "done": true, "bad": [{"file": "results/x/gens.tsv", "zero": 116, "at": 3380, "line": 30}]}],
      "queue_files": {"read": 44, "bad": []},
      "machines": {
        "calber": {"reach": true, "boot": {"id": "b2", "booted": 1794157990, "booted_at": "2026-11-08T08:13:10", "read": "2026-11-08T09:27:40",
                   "timing": {"firmware": 31.3, "loader": 14.3, "kernel": 5.5, "userspace": 10.0},
                   "facts": {"firmware": "F15 11/13/2021", "uefi": "yes", "csm": "on", "boot_entry": "ubuntu", "boot_entries": "11", "gpu": "NVIDIA GeForce GTX 1080 Ti, 580.178.04"},
                   "islands": [{"path": "/home/user/fleet/q-grove/crucible-world-hybrid-forest-nav/island.state", "bytes": 141705260, "zero": 0, "blocks": 34597, "gen": 282900}],
                   "changed": [["csm", "off", "on"], ["boot_entries", "2", "11"]]},
                   "before": {"id": "b1", "booted": null, "facts": {"csm": "off"}, "source": "the F15 report"}},
        "whitewolf": {"reach": true, "boot": {"id": "w1", "booted": 1794146940, "booted_at": "2026-11-08T05:49:00", "read": "2026-11-08T09:20:00",
                   "islands": [{"path": "/h/crucible-world-hybrid-forest-nav/island.state", "bytes": 141705260, "zero": 3, "blocks": 34597, "gen": 197600}],
                   "changed": []}},
        "saskatchewan": {"reach": false, "dark_since": "2026-11-08T07:48:28"}
      }}"#;

    fn doc() -> Value {
        crate::json::parse(DOC).unwrap()
    }

    #[test]
    fn the_cut_reads_as_one_sentence_with_the_wait_from_the_first_machine_up() {
        let s = cut_sentence(&doc());
        assert_eq!(s, "The last cut: quiet from 7 Nov 21:01; the first machine up at 8 Nov 04:48 (macmini); this Mac at 8 Nov 05:49; the keeper at 8 Nov 07:47, 2 h 59 m after the first machine. 12 jobs went back on the queue.");
    }

    #[test]
    fn a_record_with_no_cut_says_where_one_would_come_from() {
        let d = crate::json::parse(r#"{"machines": {}}"#).unwrap();
        assert!(cut_sentence(&d).starts_with("No cut on record yet"));
    }

    #[test]
    fn a_damaged_save_comes_first_then_the_dark_then_a_machine_back_different() {
        let d = doc();
        let rows = rows_of(&d);
        let names: Vec<&str> = rows.iter().map(|r| r.name).collect();
        assert_eq!(names, ["whitewolf", "saskatchewan", "calber"]);
        assert_eq!(rows[0].harmed, ["crucible-world-hybrid-forest-nav has 3 zeroed blocks of 34597"]);
        assert_eq!(rows[2].changed, ["CSM off → on", "boot entries 2 → 11"]);
        assert!(!rows[2].accepted);
    }

    #[test]
    fn the_firmware_column_says_what_was_read_and_nothing_it_was_not() {
        let d = doc();
        let f = d.get("machines").and_then(|m| m.get("calber")).and_then(|m| m.get("boot")).and_then(|b| b.get("facts")).unwrap();
        assert_eq!(firmware_words(f), "F15 11/13/2021, UEFI, CSM on, boots ubuntu of 11");
        let t = d.get("machines").and_then(|m| m.get("calber")).and_then(|m| m.get("boot")).and_then(|b| b.get("timing"));
        assert_eq!(timing_words(t), "61 s: firmware 31, loader 14, kernel 6, user 10");
    }

    #[test]
    fn the_key_lamp_is_the_records_own_level() {
        assert_eq!(level(&doc()), 1);
        assert_eq!(level(&crate::json::parse(r#"{"health": ["bad", "x"]}"#).unwrap()), 2);
        assert_eq!(level(&crate::json::parse(r#"{"health": ["ok", "x"]}"#).unwrap()), 0);
    }

    #[test]
    fn a_stamp_reads_as_day_month_and_minute_and_two_stamps_make_a_wait() {
        assert_eq!(when("2026-11-08T08:13:10"), "8 Nov 08:13");
        assert_eq!(secs("1970-01-02T00:00:01"), Some(86401));
        assert_eq!(secs("2026-11-08T07:47:58").zip(secs("2026-11-08T04:48:14")).map(|(a, b)| span(a - b)), Some("2 h 59 m".to_string()));
    }
}
