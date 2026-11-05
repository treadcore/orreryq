//! Results, Videos: the films in orrery's output folder, as a list with their data. Not a player.
//!
//! Paul, 4 November: "can orrery help me get the mp4 in a list on a tab. its just a list with data,
//! not a player." tools/montage.py copies every film it makes into `output/` (or ORRERY_OUTPUT) with a
//! .txt beside it of its title, its description and its chapter marks, ready for a video site. The
//! document is treadcore-view.py's `videos`: every .mp4 there, newest first, its size and time, and,
//! for a montage, its length, chapters and generations from its summary in the archive (any other
//! film's length from ffprobe, once). A row is chosen to read its title, description, chapter marks
//! and path. Open plays it in the machine's own player and Show finds it in the file browser, both
//! verbs of `fleet-queue.py QUEUE videos`; THE PAGE DRAWS AND ASKS, it plays and moves nothing.
use crate::font::{F6X10, F8X13};
use crate::json::Value;
use crate::ui::{rect, Rect, Ui};

/// What the page remembers between frames.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct State {
    /// The film chosen, by its file name (empty: the newest).
    pub sel: String,
    pub off: usize,
}

fn s(v: &Value, k: &str) -> String {
    match v.get(k) {
        Some(Value::Str(x)) => x.clone(),
        Some(Value::Num(x)) => format!("{}", x),
        _ => String::new(),
    }
}

fn n(v: &Value, k: &str) -> Option<f64> {
    v.get(k).and_then(|x| x.as_num())
}

fn arr<'a>(v: &'a Value, k: &str) -> &'a [Value] {
    v.get(k).and_then(|x| x.as_array()).map(|a| &a[..]).unwrap_or(&[])
}

/// A length as minutes and seconds; a dash when it is not known.
pub fn clock(seconds: Option<f64>) -> String {
    match seconds {
        Some(x) if x.is_finite() && x >= 0.0 => {
            let t = x.round() as i64;
            format!("{}:{:02}", t / 60, t % 60)
        }
        _ => "-".to_string(),
    }
}

/// A file name the queue's verb may be given as it stands: letters, digits, dot, dash and underscore,
/// ending .mp4. Anything else (a space, a quote, a semicolon) would be read by the shell first, so such a
/// film's buttons are greyed and it is renamed by hand.
pub fn plain_name(name: &str) -> bool {
    name.ends_with(".mp4") && !name.starts_with('.') && name.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '-' | '_'))
}

/// A size as megabytes, one decimal.
pub fn megabytes(bytes: Option<f64>) -> String {
    bytes.map(|b| format!("{:.1} MB", b / 1e6)).unwrap_or_else(|| "-".to_string())
}

/// The columns: a name, its x and its width.
const COLS: [(&str, i32, i32); 6] = [("Video", 0, 250), ("Made", 256, 136), ("Length", 398, 60), ("Size", 464, 76), ("Chapters", 546, 70), ("Generations", 622, 170)];

pub fn draw(ui: &mut Ui, at: Rect, doc: Option<&Value>, st: &mut State, ctl: &mut Option<String>) {
    let t = ui.t;
    let Some(doc) = doc.filter(|d| !matches!(d, Value::Null)) else {
        ui.label_in(at.x, at.y, at.w, "No list yet: the view has not read the output folder.", &F8X13, t.dim);
        return;
    };
    let videos = arr(doc, "videos");
    let head = format!(
        "{} {} in {}, {} in all. Open plays one in this machine's own player; Show finds it in the file browser.",
        videos.len(),
        if videos.len() == 1 { "video" } else { "videos" },
        s(doc, "dir"),
        megabytes(n(doc, "bytes"))
    );
    ui.label_in(at.x, at.y, at.w, &head, &F8X13, t.dim);
    if videos.is_empty() {
        ui.label_in(at.x, at.y + 24, at.w, "None yet. Results, Montage makes a film, and each one is copied here with its description.", &F8X13, t.dim);
        return;
    }
    if st.sel.is_empty() || !videos.iter().any(|v| s(v, "name") == st.sel) {
        st.sel = s(&videos[0], "name");
    }
    // ---- the list ----
    let mut y = at.y + 24;
    for (name, x, _) in COLS {
        ui.label(at.x + 8 + x, y, name, &F6X10, t.dim);
    }
    y += 14;
    let lh = F8X13.height as i32 + 9;
    let list_h = (lh * videos.len() as i32 + 6).min((at.bottom() - y) / 2).max(lh * 3);
    let list = rect(at.x, y, at.w, list_h);
    ui.well(list);
    let (area, first, count) = ui.scroll_list(list.inset(2), videos.len(), lh, &mut st.off);
    for (i, v) in videos.iter().enumerate().skip(first).take(count) {
        let row = rect(area.x, area.y + (i - first) as i32 * lh, area.w, lh);
        let name = s(v, "name");
        if name == st.sel {
            ui.c.rect(row.x, row.y, row.w, row.h, t.tile);
        }
        let buttons_x = row.right() - 136;
        if ui.button_hit(rect(row.x, row.y, buttons_x - row.x, row.h)) {
            st.sel = name.clone();
        }
        let cells = [
            name.clone(),
            s(v, "at"),
            clock(n(v, "seconds")),
            megabytes(n(v, "bytes")),
            n(v, "chapters").map(|c| format!("{}", c)).unwrap_or_else(|| "-".to_string()),
            if s(v, "gens").is_empty() { "-".to_string() } else { s(v, "gens") },
        ];
        for ((_, x, w), text) in COLS.iter().zip(cells.iter()) {
            if row.x + 6 + x + w <= buttons_x {
                ui.label_in(row.x + 6 + x, row.y + 5, *w - 6, text, &F8X13, t.ink);
            }
        }
        // The verb reaches the queue through a shell: only a plain name is offered to it.
        let plain = plain_name(&name);
        if ui.button(rect(buttons_x, row.y + 1, 64, lh - 2), "Open", plain) {
            *ctl = Some(format!("videos open {}", name));
        }
        if ui.button(rect(buttons_x + 68, row.y + 1, 64, lh - 2), "Show", plain) {
            *ctl = Some(format!("videos show {}", name));
        }
    }
    // ---- the one chosen: its words, its marks, where it is ----
    let Some(v) = videos.iter().find(|v| s(v, "name") == st.sel) else {
        return;
    };
    let mut y = list.bottom() + 14;
    let title = if s(v, "title").is_empty() { s(v, "name") } else { s(v, "title") };
    ui.label_in(at.x, y, at.w, &title, &F8X13, t.ink);
    y += 20;
    for line in crate::line::wrap(&s(v, "description"), &F8X13, at.w.min(900)).iter().take(4) {
        ui.label_in(at.x, y, at.w, line, &F8X13, t.dim);
        y += 16;
    }
    y += 6;
    ui.label_in(at.x, y, at.w, &format!("file  {}", s(v, "path")), &F6X10, t.dim);
    y += 13;
    if !s(v, "txt").is_empty() {
        ui.label_in(at.x, y, at.w, &format!("text  {}  (the title, description and chapter marks, to paste)", s(v, "txt")), &F6X10, t.dim);
        y += 13;
    }
    let marks = arr(v, "marks");
    if marks.is_empty() {
        return;
    }
    y += 8;
    ui.label(at.x, y, "Chapter marks", &F6X10, t.dim);
    y += 15;
    let per = ((at.bottom() - y) / 15).max(1) as usize;
    for (k, m) in marks.iter().enumerate() {
        let Some(pair) = m.as_array().filter(|p| p.len() == 2) else { continue };
        let (col, row) = (k / per, k % per);
        let x = at.x + col as i32 * 330;
        if x + 320 > at.right() {
            break;
        }
        let when = clock(pair[0].as_num());
        let what = pair[1].as_str().unwrap_or("");
        ui.label_in(x, y + row as i32 * 15, 320, &format!("{:>5}  {}", when, what), &F8X13, t.ink);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A length reads as minutes and seconds, rounded; an unknown one, or a nonsense one, as a dash.
    #[test]
    fn a_length_reads_as_minutes_and_seconds() {
        assert_eq!(clock(Some(99.0)), "1:39");
        assert_eq!(clock(Some(3.6)), "0:04");
        assert_eq!(clock(Some(3600.4)), "60:00");
        assert_eq!(clock(None), "-");
        assert_eq!(clock(Some(f64::NAN)), "-");
        assert_eq!(megabytes(Some(4_186_250.0)), "4.2 MB");
    }

    /// Only a plain file name reaches the shell: a space, a quote or a semicolon greys the buttons.
    #[test]
    fn only_a_plain_name_is_offered_to_the_shell() {
        assert!(plain_name("treadcore-montage-0003.mp4"));
        assert!(!plain_name("my film.mp4"));
        assert!(!plain_name("a;rm -rf x.mp4"));
        assert!(!plain_name("it's.mp4"));
        assert!(!plain_name("notes.txt"));
        assert!(!plain_name(".hidden.mp4"));
    }
}
