//! Results, Nets: the explorer of the learned nets -- every .bin the fleet made or keeps, in one
//! scrolling window, a card a net (Paul, 3 November: "an explorer of milestones that are
//! promoted ... to visually analyze and annotate the results and describe in the program why
//! it's useful for what and where. Make it a scroll window. We like complex visualization
//! techniques ... a way to save, capture, and expire some of these .bin files ... by request
//! only, with promotion abilities").
//!
//! The document is `tools/nets.py`'s (QUEUE/plan/nets.json): the register of where each net is
//! held and has been, its reads, its numbers and its notes. THIS PAGE DRAWS THE REGISTER AND
//! ASKS FOR CHANGES; IT NEVER COPIES, REMOVES OR RENAMES A FILE ITSELF. Every button is a verb
//! for `fleet-queue.py QUEUE nets ...`, run by main as the other queue controls are, and the
//! page redraws from the document the tool rewrites. A button that must not be pressable (a
//! viewer, not an operator) is not drawn.
//!
//! The card. A name and its badges (milestone, model slot, style, vault, where it is held); the
//! sentence of what it is for, said from its record; the JOURNEY, a ribbon of stations the bytes
//! have stood at (the run on its machine, the results, nets/, the vault, a slot, a style, the
//! runs that began from it); the READS, the seventeen gauntlets as a strip, the held-out courses
//! as bars, the training curve as a spark; the WEIGHTS, the first layer's |w| pooled to a
//! sixteen-square fingerprint, the listening by sense group, the speaking by head, each layer's
//! norm and its first singular values; the notes, and a field to add one. On the left, the
//! lineage: a rail from each parent card to the cards that began from it.
//!
//! The window clips: the canvas takes a clip rectangle while the cards draw (draw.rs), so a
//! card half scrolled off paints only its visible half, and the header keeps its own paint.
use crate::draw::Rgb;
use crate::font::{F10X20, F6X10, F8X13};
use crate::json::Value;
use crate::surface::Sym;
use crate::ui::{rect, Field, Light, Rect, Ui};

/// What the page remembers between frames.
#[derive(Debug, Clone, Default)]
pub struct State {
    /// The window's scroll, in pixels from the top of the first card.
    pub off: i32,
    /// 0 every net, 1 milestones and slots, 2 styles and clones, 3 the vault, 4 results only.
    pub filter: u8,
    /// The net whose note field is open, and the field.
    pub focus: Option<String>,
    pub note: Field,
    /// Expire was pressed once: the next press does it (the tool lists first, removes with --do).
    pub arm_expire: bool,
    /// A card clicked open: its sections drawn tall (the fingerprint and the bars at twice the size).
    pub open: Option<String>,
    /// A card to bring to the top of the window at the next draw: the one just opened.
    pub scroll_to: Option<String>,
}

// A Field has no PartialEq of its own; the page's state is compared (training::State derives it)
// so a frame with nothing changed is not redrawn, and the field's text and caret are what change.
impl PartialEq for State {
    fn eq(&self, o: &State) -> bool {
        self.off == o.off && self.filter == o.filter && self.focus == o.focus && self.arm_expire == o.arm_expire && self.open == o.open && self.scroll_to == o.scroll_to && self.note.text == o.note.text && self.note.caret == o.note.caret
    }
}

const FILTERS: [(&str, &str); 5] = [
    ("All", "every net the register points at"),
    ("Milestones", "the gauntlet's yardsticks and the model slots' nets"),
    ("Styles", "the nets a style plays, and the clones of the rules"),
    ("Vault", "the copies made on request, with their notes"),
    ("Results", "nets that lie only in their run's results directory, which no one has kept"),
];

const GAUNTLETS: usize = 17;

fn s(v: &Value, k: &str) -> String {
    v.get(k).and_then(|x| x.as_str()).unwrap_or("").to_string()
}
fn n(v: &Value, k: &str) -> f64 {
    v.get(k).and_then(|x| x.as_num()).unwrap_or(0.0)
}
fn arr<'a>(v: &'a Value, k: &str) -> &'a [Value] {
    v.get(k).and_then(|x| x.as_array()).map(|a| &a[..]).unwrap_or(&[])
}
fn has(v: &Value, k: &str) -> bool {
    matches!(v.get(k), Some(x) if !matches!(x, Value::Null))
}

fn blend(a: Rgb, b: Rgb, t: f64) -> Rgb {
    let t = t.clamp(0.0, 1.0);
    let ch = |s: u32| {
        let (x, y) = (((a >> s) & 255) as f64, ((b >> s) & 255) as f64);
        ((x + (y - x) * t) as u32) << s
    };
    ch(16) | ch(8) | ch(0)
}

fn wrap(text: &str, cols: usize) -> Vec<String> {
    let mut out = Vec::new();
    let mut line = String::new();
    for w in text.split_whitespace() {
        if !line.is_empty() && line.chars().count() + 1 + w.chars().count() > cols {
            out.push(std::mem::take(&mut line));
        }
        if !line.is_empty() {
            line.push(' ');
        }
        line.push_str(w);
    }
    if !line.is_empty() {
        out.push(line);
    }
    out
}

fn shown(net: &Value, filter: u8) -> bool {
    let milestone = net.get("milestone").and_then(|x| x.as_bool()).unwrap_or(false);
    let path = s(net, "path");
    let clone = std::path::Path::new(&path).file_stem().map(|x| x.to_string_lossy().starts_with("bc")).unwrap_or(false);
    match filter {
        1 => milestone || has(net, "slot"),
        2 => has(net, "style") || clone,
        3 => has(net, "vault"),
        4 => s(net, "held") == "result",
        _ => true,
    }
}

/// A card's height, as `card` lays it out: the title row, the sentence wrapped to `cols`, the
/// three columns, a line a note (six at most), the verbs' row. Taller when open.
fn card_h(net: &Value, open: bool, cols: usize) -> i32 {
    let notes = net.get("vault").map(|v| arr(v, "notes").len()).unwrap_or(0) as i32 + has(net, "style") as i32;
    let lh = F8X13.height as i32 + 3;
    let lines = wrap(&s(net, "why"), cols).len().min(if open { 6 } else { 3 }) as i32;
    8 + F10X20.height as i32 + 6 + lines * lh + 10 + if open { 230 } else { 118 } + 12 + notes.min(6) * lh + 36
}

/// The stations of a net's journey, in the order the bytes travelled: (short label, what it is,
/// where). A station absent from the record is not drawn, so the ribbon's length is the story.
fn journey(net: &Value) -> Vec<(String, String, String)> {
    let mut st = Vec::new();
    if let Some(r) = net.get("run") {
        let host = s(r, "host");
        st.push((
            format!("{} {}", s(r, "id"), if host.is_empty() { "fleet".to_string() } else { host }),
            format!("made by run {} ({}), asked {} by {}", s(r, "id"), s(r, "kind"), s(r, "asked").replace('T', " "), s(r, "by")),
            arr(r, "ground").iter().filter_map(|g| g.as_str()).collect::<Vec<_>>().join(", "),
        ));
    }
    for c in arr(net, "copies") {
        let held = s(c, "held");
        let (label, what) = match held.as_str() {
            "result" => ("results", "the run's out directory, where every made net lies until something keeps it"),
            "ships" => ("nets/", "shipped in treadcore's nets/, read by name"),
            "vault" => ("vault", "the vault's copy, made on request; expire respects a milestone"),
            "slot" => ("slot", "a model slot: whole teams of it in the league's censuses"),
            _ => ("copy", "a copy"),
        };
        st.push((label.to_string(), what.to_string(), s(c, "path")));
    }
    if let Some(sl) = net.get("slot").filter(|x| !matches!(x, Value::Null)) {
        st.push((format!("slot {}", n(sl, "slot") as i64), format!("model slot {} as {} (generation {})", n(sl, "slot") as i64, s(sl, "name"), n(sl, "generation") as i64), s(sl, "source")));
    }
    if let Some(sy) = net.get("style").filter(|x| !matches!(x, Value::Null)) {
        if s(sy, "style") == "(none)" {
            st.push(("listed".to_string(), format!("in styles.tsv without a slot: {}", s(sy, "from")), s(sy, "note")));
        } else {
            st.push((format!("style {}", s(sy, "style").split(' ').next().unwrap_or("")), format!("plays as style {}; {}", s(sy, "style"), s(sy, "from")), s(sy, "note")));
        }
    }
    for rid in arr(net, "starts") {
        st.push((format!("-> {}", rid.as_str().unwrap_or("")), format!("run {} began its search from this net", rid.as_str().unwrap_or("")), String::new()));
    }
    st
}

/// The page. `ctl` takes a verb for `fleet-queue.py QUEUE nets ...`.
pub fn draw(ui: &mut Ui, at: Rect, doc: Option<&Value>, st: &mut State, operator: bool, ctl: &mut Option<String>) {
    let t = ui.t;
    let Some(doc) = doc.filter(|d| d.get("nets").is_some()) else {
        ui.label_in(at.x, at.y, at.w, "No register yet: tools/nets.py QUEUE writes plan/nets.json (the keeper starts it each five minutes, or run it by hand).", &F8X13, t.dim);
        return;
    };
    let nets: Vec<&Value> = arr(doc, "nets").iter().filter(|x| shown(x, st.filter)).collect();
    // ---- the strip: filters, the vault's size, the verbs that are everyone's ----
    let mut x = at.x;
    let y = at.y;
    for (i, (name, what)) in FILTERS.iter().enumerate() {
        let count = arr(doc, "nets").iter().filter(|x| shown(x, i as u8)).count();
        let label = format!("{} {}", name, count);
        let w = F8X13.measure(&label) as i32 + 18;
        if ui.rail_item(rect(x, y, w, 22), &label, None, st.filter == i as u8) {
            st.filter = i as u8;
            st.off = 0;
        }
        ui.tip(rect(x, y, w, 22), || vec![what.to_string()]);
        x += w + 4;
    }
    let vault = doc.get("vault");
    let vault_line = vault
        .map(|v| format!("vault: {} cop{}, {:.1} MB in {}", n(v, "count") as i64, if n(v, "count") as i64 == 1 { "y" } else { "ies" }, n(v, "bytes") / 1e6, s(v, "dir")))
        .unwrap_or_default();
    x += 10;
    let right = at.right();
    if operator {
        let bw = 86;
        if ui.button(rect(right - bw, y, bw, 22), "Refresh", true) {
            *ctl = Some("nets refresh".to_string());
        }
        ui.tip(rect(right - bw, y, bw, 22), || vec!["Read every net again: new results, new shas, the gauntlet's latest record.".to_string()]);
        let ew = 150;
        let label = if st.arm_expire { "Expire now: remove" } else { "Expire..." };
        if ui.button(rect(right - bw - 6 - ew, y, ew, 22), label, true) {
            if st.arm_expire {
                *ctl = Some("nets expire --do".to_string());
                st.arm_expire = false;
            } else {
                *ctl = Some("nets expire".to_string());
                st.arm_expire = true;
            }
        }
        ui.tip(rect(right - bw - 6 - ew, y, ew, 22), || vec![
            "Expire: vault copies that are no milestone, no slot and no style, older than 14 days.".to_string(),
            "The first press lists what would go (the line below says); the second removes them.".to_string(),
            "A milestone is never removed: demote it first.".to_string(),
        ]);
        ui.label_in(x, y + 4, right - bw - 6 - ew - 8 - x, &vault_line, &F8X13, t.dim);
    } else {
        ui.label_in(x, y + 4, right - x, &vault_line, &F8X13, t.dim);
    }
    let y = y + 22 + 6;
    let register = format!("Register {}: {} nets, {} shown; the wheel scrolls, a title opens a card. {}", s(doc, "at").replace('T', " "), arr(doc, "nets").len(), nets.len(), s(doc, "policy"));
    ui.label_in(at.x, y, at.w, &register, &F6X10, t.dim);
    let y = y + F6X10.height as i32 + 6;
    // ---- the window ----
    let win = rect(at.x, y, at.w, at.bottom() - y);
    if nets.is_empty() {
        ui.label_in(win.x, win.y, win.w, "Nothing under this filter.", &F8X13, t.dim);
        return;
    }
    let gap = 10;
    let rail_w = 34;
    let cols = ((win.w - 16 - rail_w - 4 - 24) / F8X13.width as i32).max(20) as usize;
    let heights: Vec<i32> = nets.iter().map(|x| card_h(x, st.open.as_deref() == Some(s(x, "name").as_str()), cols)).collect();
    let total: i32 = heights.iter().sum::<i32>() + gap * nets.len() as i32;
    let max_off = (total - win.h).max(0);
    if let Some(want) = st.scroll_to.take() {
        let mut y0 = 0;
        for (i, nm) in nets.iter().enumerate() {
            if s(nm, "name") == want {
                st.off = y0;
                break;
            }
            y0 += heights[i] + gap;
        }
    }
    let dy = ui.f.scroll.1;
    if dy != 0 && ui.is_hot(win) {
        st.off = (st.off - dy * 3).clamp(0, max_off);
    }
    if ui.f.pressed(Sym::Escape) {
        st.focus = None;
        st.arm_expire = false;
    }
    st.off = st.off.clamp(0, max_off);
    // The bar on the right, as scroll_list draws it.
    let bar = rect(win.right() - 12, win.y, 12, win.h);
    if max_off > 0 {
        ui.panel(bar, t.tile);
        ui.outline(bar, t.line);
        let th = ((bar.h as f64 * win.h as f64 / total as f64) as i32).clamp(18, bar.h);
        let ty = bar.y + ((bar.h - th) as f64 * st.off as f64 / max_off as f64) as i32;
        ui.c.rect(bar.x + 2, ty, bar.w - 4, th, t.dim);
        for (p, b, down) in ui.f.button_events() {
            if down && b == crate::surface::Button::Left && bar.contains(p) {
                let frac = (p.1 - bar.y) as f64 / bar.h.max(1) as f64;
                st.off = ((frac * total as f64) as i32 - win.h / 2).clamp(0, max_off);
            }
        }
    }
    let inner = rect(win.x, win.y, win.w - if max_off > 0 { 16 } else { 0 }, win.h);
    ui.c.clip = Some((inner.x, inner.y, inner.w, inner.h));
    // Card tops, for the lineage rail and the cards.
    let mut tops = Vec::with_capacity(nets.len());
    let mut cy = inner.y - st.off;
    for h in &heights {
        tops.push(cy);
        cy += h + gap;
    }
    // ---- the lineage rail: parent to child, a line a family, nested by depth ----
    let names: Vec<String> = nets.iter().map(|x| s(x, "name")).collect();
    let families = [t.accent, t.up, t.warn, blend(t.accent, t.ink, 0.5), blend(t.up, t.ink, 0.5)];
    let mut lane = 0;
    for (i, net) in nets.iter().enumerate() {
        let parent = s(net, "parent");
        if parent.is_empty() {
            continue;
        }
        let Some(j) = names.iter().position(|nm| *nm == parent) else {
            // The parent is not shown (another filter, or never registered): a stub says so.
            let y0 = tops[i] + 14;
            let c = t.dim;
            ui.c.rect(inner.x + 6, y0, rail_w - 12, 1, c);
            ui.label(inner.x + 2, y0 - F6X10.height as i32 - 1, "from", &F6X10, c);
            continue;
        };
        let c = families[lane % families.len()];
        let xr = inner.x + rail_w - 8 - (lane as i32 % 3) * 5;
        let (ya, yb) = (tops[j] + 14, tops[i] + 14);
        let (y0, y1) = (ya.min(yb), ya.max(yb));
        ui.c.rect(xr, y0, 2, y1 - y0, c);
        ui.c.rect(xr, ya, inner.x + rail_w - xr, 2, c);
        ui.c.rect(xr, yb, inner.x + rail_w - xr, 2, c);
        ui.c.disc(xr + 1, ya, 3, c);
        ui.c.ring(xr + 1, yb, 3, c);
        lane += 1;
    }
    // ---- the cards ----
    for (i, net) in nets.iter().enumerate() {
        let r = rect(inner.x + rail_w, tops[i], inner.w - rail_w - 4, heights[i]);
        if r.bottom() < inner.y || r.y > inner.bottom() {
            continue;
        }
        card(ui, r, net, st, operator, ctl);
    }
    ui.c.clip = None;
    // Which cards stand in the window, in the bar's tip.
    if max_off > 0 {
        let first = tops.iter().position(|y| *y + 20 >= inner.y).unwrap_or(0);
        let last = tops.iter().rposition(|y| *y < inner.bottom()).unwrap_or(0);
        let count = nets.len();
        ui.tip(bar, move || vec![format!("cards {} to {} of {}; the wheel scrolls, a press on the bar jumps", first + 1, last + 1, count)]);
    }
}

fn pill(ui: &mut Ui, x: i32, y: i32, label: &str, fill: Rgb, ink: Rgb) -> i32 {
    let w = F6X10.measure(label) as i32 + 10;
    ui.c.rect(x, y, w, 14, fill);
    ui.label(x + 5, y + 2, label, &F6X10, ink);
    w + 5
}

fn bar(ui: &mut Ui, r: Rect, frac: f64, c: Rgb) {
    let t = ui.t;
    ui.c.rect(r.x, r.y, r.w, r.h, t.tile);
    ui.c.rect(r.x, r.y, ((r.w as f64) * frac.clamp(0.0, 1.0)) as i32, r.h, c);
}

fn card(ui: &mut Ui, r: Rect, net: &Value, st: &mut State, operator: bool, ctl: &mut Option<String>) {
    let t = ui.t;
    let lh = F8X13.height as i32 + 3;
    let name = s(net, "name");
    let open = st.open.as_deref() == Some(name.as_str());
    let milestone = net.get("milestone").and_then(|x| x.as_bool()).unwrap_or(false);
    // A black readout set into the metal, light text in it, as the house draws every reading.
    ui.well(r);
    ui.outline(r, if milestone { t.accent } else { t.line });
    // The left edge carries the family colour of a kept net, so a glance down the column sorts them.
    let edge = if milestone { t.accent } else if has(net, "slot") { t.up } else if has(net, "style") { t.warn } else if has(net, "vault") { blend(t.accent, t.ink, 0.5) } else { t.line };
    ui.c.rect(r.x, r.y, 4, r.h, edge);
    // ---- row 1: the name, the badges, the identity ----
    let mut x = r.x + 12;
    let y = r.y + 8;
    let title = rect(x, y, F10X20.measure(&name) as i32 + 8, F10X20.height as i32);
    x = ui.label(x, y, &name, &F10X20, t.ink) + 10;
    if ui.button_hit(title) {
        st.open = if open { None } else { Some(name.clone()) };
        if !open {
            st.scroll_to = Some(name.clone());
        }
    }
    ui.tip(title, || vec!["Click: open the card tall, with the fingerprint and the bars at twice the size.".to_string()]);
    let by = y + 4;
    if milestone {
        x += pill(ui, x, by, "milestone", t.accent, t.base);
    }
    if let Some(sl) = net.get("slot").filter(|x| !matches!(x, Value::Null)) {
        x += pill(ui, x, by, &format!("slot {}  g{}", n(sl, "slot") as i64, n(sl, "generation") as i64), t.up, t.base);
    }
    if let Some(sy) = net.get("style").filter(|x| !matches!(x, Value::Null)) {
        let label = s(sy, "style");
        if label != "(none)" {
            x += pill(ui, x, by, &format!("style {}", label), t.warn, t.base);
        } else {
            x += pill(ui, x, by, "clone", t.tile, t.ink);
        }
    }
    if has(net, "vault") {
        x += pill(ui, x, by, "vault", blend(t.accent, t.ink, 0.5), t.base);
    }
    let held = s(net, "held");
    x += pill(ui, x, by, &held, t.tile, t.dim);
    let _ = x;
    let ident = format!("{}  {} KB  {}  {}", s(net, "sha"), n(net, "bytes") as i64 / 1024, s(net, "when"), net.get("numbers").map(|nu| arr(nu, "sizes").iter().filter_map(|v| v.as_num()).map(|v| format!("{}", v as i64)).collect::<Vec<_>>().join("-")).unwrap_or_default());
    ui.label_right(r.right() - 8, y + 4, &ident, &F6X10, t.dim);
    ui.tip(rect(r.right() - 8 - F6X10.measure(&ident) as i32, y, F6X10.measure(&ident) as i32 + 8, 16), || vec![
        format!("sha256, first twelve: {}", s(net, "sha")),
        format!("{} bytes, written {}", n(net, "bytes") as i64, s(net, "when")),
        format!("sizes {}: inputs, hidden, hidden, outputs", net.get("numbers").map(|nu| arr(nu, "sizes").iter().filter_map(|v| v.as_num()).map(|v| format!("{}", v as i64)).collect::<Vec<_>>().join(" ")).unwrap_or_default()),
        format!("path {}", s(net, "path")),
    ]);
    // ---- row 2: what it is for ----
    let mut y = y + F10X20.height as i32 + 6;
    let why = s(net, "why");
    let cols = ((r.w - 24) / F8X13.width as i32).max(20) as usize;
    let lines = wrap(&why, cols);
    let shown_lines = if open { 6 } else { 3 };
    for l in lines.iter().take(shown_lines) {
        ui.label_in(r.x + 12, y, r.w - 24, l, &F8X13, t.ink);
        y += lh;
    }
    if lines.len() > shown_lines {
        ui.tip(rect(r.x + 12, y - lh * shown_lines as i32, r.w - 24, lh * shown_lines as i32), || lines.clone());
    }
    y += 4;
    ui.hrule(r.x + 8, y, r.w - 16);
    y += 6;
    // ---- row 3: three columns ----
    let col_w = (r.w - 24) / 3;
    let body_h = if open { 230 } else { 118 };
    let (c1, c2, c3) = (rect(r.x + 12, y, col_w - 8, body_h), rect(r.x + 12 + col_w, y, col_w - 8, body_h), rect(r.x + 12 + 2 * col_w, y, col_w - 8, body_h));
    draw_journey(ui, c1, net);
    draw_reads(ui, c2, net, open);
    draw_weights(ui, c3, net, open);
    y += body_h + 6;
    ui.hrule(r.x + 8, y, r.w - 16);
    y += 6;
    // ---- row 4: the notes, the field, the verbs ----
    let mut notes: Vec<(String, String)> = Vec::new();
    if let Some(sy) = net.get("style").filter(|x| !matches!(x, Value::Null)) {
        notes.push(("styles.tsv".to_string(), s(sy, "note")));
    }
    if let Some(v) = net.get("vault").filter(|x| !matches!(x, Value::Null)) {
        for nt in arr(v, "notes") {
            notes.push((s(nt, "at").replace('T', " "), s(nt, "text")));
        }
    }
    let verbs_w = if operator { 330 } else { 0 };
    for (when, text) in notes.iter().rev().take(6) {
        let wx = ui.label(r.x + 12, y, when, &F6X10, t.dim);
        ui.label_in(wx + 8, y, r.w - 24 - verbs_w - (wx + 8 - r.x), text, &F8X13, t.ink);
        y += lh;
    }
    if operator {
        let bw = 76;
        let mut bx = r.right() - 8 - bw;
        let vy = r.bottom() - 30;
        let q = |x: &str| format!("'{}'", x.replace('\'', "'\\''"));
        if st.focus.as_deref() == Some(name.as_str()) {
            let fr = rect(r.x + 12, vy, r.w - 24 - 2 * (bw + 6), 22);
            ui.field(fr, &st.note, "a note on this net; Return saves it to the vault's register");
            if st.note.feed(&ui.f) {
                let text = st.note.text.trim().to_string();
                if !text.is_empty() {
                    *ctl = Some(format!("nets note {} {}", q(&name), q(&text)));
                }
                st.note.clear();
                st.focus = None;
            }
            if ui.button(rect(bx, vy, bw, 22), "Cancel", true) {
                st.note.clear();
                st.focus = None;
            }
        } else {
            if ui.button(rect(bx, vy, bw, 22), "Note...", true) {
                st.focus = Some(name.clone());
                st.note.clear();
            }
            ui.tip(rect(bx, vy, bw, 22), || vec!["Write a line about this net. It goes to the vault's register beside the sha, copy or no copy.".to_string()]);
            bx -= bw + 6;
            if has(net, "vault") {
                let in_vault = net.get("vault").map(|v| !s(v, "kept").is_empty()).unwrap_or(false);
                if milestone {
                    if ui.button(rect(bx, vy, bw, 22), "Demote", in_vault) {
                        *ctl = Some(format!("nets demote {}", q(&name)));
                    }
                    ui.tip(rect(bx, vy, bw, 22), || vec!["Take the milestone back: expire may then remove the vault's copy.".to_string(), "A milestone named in the brain's code (phase1, map7 ...) stays one whatever this says.".to_string()]);
                } else {
                    if ui.button(rect(bx, vy, bw, 22), "Promote", true) {
                        *ctl = Some(format!("nets promote {}", q(&name)));
                    }
                    ui.tip(rect(bx, vy, bw, 22), || vec!["Make it a milestone: kept in the vault whatever expire says.".to_string(), "To put it in a model slot as well: fleet-queue.py QUEUE nets promote NAME --slot K.".to_string()]);
                }
                bx -= bw + 6;
                if !in_vault && ui.button(rect(bx, vy, bw, 22), "Capture", true) {
                    *ctl = Some(format!("nets capture {} --as {}", q(&s(net, "path")), q(&name)));
                }
            } else {
                if ui.button(rect(bx, vy, bw, 22), "Capture", true) {
                    *ctl = Some(format!("nets capture {} --as {}", q(&s(net, "path")), q(&name)));
                }
                ui.tip(rect(bx, vy, bw, 22), || vec![
                    "Copy the file into the vault with its sha and origin. Nothing is copied until this is pressed.".to_string(),
                    format!("From {}", s(net, "path")),
                ]);
                bx -= bw + 6;
                if ui.button(rect(bx, vy, bw, 22), "Promote", true) {
                    *ctl = Some(format!("nets promote {}", q(&name)));
                }
                ui.tip(rect(bx, vy, bw, 22), || vec!["Capture and make it a milestone in one: kept whatever expire says.".to_string()]);
            }
        }
    }
    let _ = y;
}

/// The journey: stations on a line, the present ones only, each a disc with its label under.
fn draw_journey(ui: &mut Ui, at: Rect, net: &Value) {
    let t = ui.t;
    ui.label(at.x, at.y, "JOURNEY", &F6X10, t.dim);
    let stations = journey(net);
    if stations.is_empty() {
        ui.label_in(at.x, at.y + 16, at.w, "no record of where it has been", &F8X13, t.dim);
        return;
    }
    let y = at.y + 34;
    let n_st = stations.len() as i32;
    let step = ((at.w - 16) / n_st.max(1)).clamp(28, 110);
    let x0 = at.x + 8;
    ui.c.rect(x0, y, step * (n_st - 1).max(0) + 1, 2, t.line);
    for (i, (label, what, where_)) in stations.iter().enumerate() {
        let cx = x0 + step * i as i32;
        let c = if label.starts_with("->") { t.up } else if label.starts_with("slot") || label.starts_with("style") { t.warn } else if label == "vault" { t.accent } else { t.ink };
        if label.starts_with("->") {
            ui.c.ring(cx, y + 1, 5, c);
        } else {
            ui.c.disc(cx, y + 1, 5, c);
        }
        // Labels alternate above and below the line so neighbours do not collide.
        let ly = if i % 2 == 0 { y + 10 } else { y - 10 - F6X10.height as i32 };
        let lw = F6X10.measure(label) as i32;
        ui.label(cx - lw / 2, ly, label, &F6X10, c);
        let hit = rect(cx - step / 2, y - 24, step, 48);
        let (what, where_) = (what.clone(), where_.clone());
        ui.tip(hit, move || {
            let mut v = vec![what];
            if !where_.is_empty() {
                v.push(where_);
            }
            v
        });
    }
    // The parent under the ribbon, and the number of runs that began here.
    let parent = s(net, "parent");
    let mut y2 = y + 30;
    if !parent.is_empty() {
        ui.label_in(at.x, y2, at.w, &format!("from {}", parent), &F8X13, t.dim);
        y2 += F8X13.height as i32 + 2;
    }
    if let Some(r) = net.get("run") {
        let p = r.get("params");
        let gens = p.map(|p| s(p, "gens")).unwrap_or_default();
        let line = if gens.is_empty() {
            "the run's record kept no numbers (before the planner wrote them)".to_string()
        } else {
            format!("{} gens, {} pairs, {} seeds, {} held", gens, p.map(|p| s(p, "pairs")).unwrap_or_default(), p.map(|p| s(p, "seeds")).unwrap_or_default(), p.map(|p| s(p, "held")).unwrap_or_default())
        };
        ui.label_in(at.x, y2, at.w, &line, &F8X13, t.dim);
        y2 += F8X13.height as i32 + 2;
        let ground: Vec<String> = arr(r, "ground").iter().filter_map(|g| g.as_str().map(str::to_string)).collect();
        if !ground.is_empty() {
            ui.label_in(at.x, y2, at.w, &format!("courses: {}", ground.join(", ")), &F6X10, t.dim);
        }
    }
    let sections: Vec<String> = arr(net, "sections").iter().filter_map(|x| x.as_array()).map(|a| format!("{}", a.first().and_then(|v| v.as_num()).unwrap_or(0.0) as i64)).collect();
    if !sections.is_empty() {
        ui.label_right(at.right(), at.bottom() - F6X10.height as i32, &format!("LR {}", sections.join(" ")), &F6X10, t.dim);
        let titles: Vec<String> = arr(net, "sections").iter().filter_map(|x| x.as_array()).map(|a| format!("{}. {}", a.first().and_then(|v| v.as_num()).unwrap_or(0.0) as i64, a.get(1).and_then(|v| v.as_str()).unwrap_or(""))).collect();
        ui.tip(rect(at.x, at.bottom() - F6X10.height as i32 - 2, at.w, F6X10.height as i32 + 4), move || titles.clone());
    }
}

/// The reads: the gauntlet strip, the held-out courses, the training curve.
fn draw_reads(ui: &mut Ui, at: Rect, net: &Value, open: bool) {
    let t = ui.t;
    ui.label(at.x, at.y, "READS", &F6X10, t.dim);
    let mut y = at.y + 14;
    // The strip: G1 to G17, a cell each; the share passed as colour, red at nothing, grey unread.
    let cell = ((at.w - 2) / GAUNTLETS as i32).clamp(6, 22);
    let ch = if open { 22 } else { 14 };
    let gauntlet = net.get("gauntlet");
    let mut read_any = false;
    for g in 1..=GAUNTLETS {
        let x = at.x + (g as i32 - 1) * cell;
        let found = gauntlet.and_then(|m| match m {
            Value::Obj(o) => o.iter().find(|(k, _)| k.starts_with(&format!("G{} ", g))).map(|(k, v)| (k.clone(), v.as_num().unwrap_or(0.0))),
            _ => None,
        });
        let c = match &found {
            Some((_, v)) if *v >= 0.9 => t.up,
            Some((_, v)) if *v > 0.0 => blend(t.alarm, t.up, *v),
            Some(_) => t.alarm,
            None => t.tile,
        };
        read_any |= found.is_some();
        ui.c.rect(x, y, cell - 1, ch, c);
        if cell >= 12 && found.is_some() {
            ui.label(x + 1, y + ch + 1, &format!("{}", g), &F6X10, t.dim);
        }
        let label = found.clone();
        ui.tip(rect(x, y, cell, ch + 10), move || match &label {
            Some((k, v)) => vec![format!("{}: {:.0}% of its seeds passed", k, 100.0 * v), "Source: build/train/gauntlet.tsv, the last gauntlet record.".to_string()],
            None => vec![format!("G{}: no read of this net in the last gauntlet record", g)],
        });
    }
    y += ch + 12;
    if !read_any {
        ui.label_in(at.x, y - 10, at.w, "not in the last gauntlet record: GAUNTLET_NETS=name reads it", &F6X10, t.dim);
        y += 2;
    }
    // The held-out courses: a bar each, green past its floor.
    let held = arr(net, "held_out");
    let bh = if open { 12 } else { 8 };
    let name_w = (at.w / 2).min(170);
    for h in held.iter().take(if open { 10 } else { 5 }) {
        let (share, floor) = (n(h, "share"), n(h, "floor"));
        let course = s(h, "course");
        let short = course.trim_start_matches(|c: char| c.is_ascii_digit() || c == '-').replace("the-first-minute-", "first minute ").replace('-', " ");
        ui.label_in(at.x, y, name_w - 4, &short, &F6X10, t.ink);
        let br = rect(at.x + name_w, y + 1, at.w - name_w - 36, bh);
        bar(ui, br, share, if share >= floor { t.up } else { t.alarm });
        ui.c.rect(br.x + ((br.w as f64) * floor) as i32, br.y - 1, 1, bh + 2, t.ink);
        ui.label_right(at.right(), y, &format!("{}/{}", n(h, "passed") as i64, n(h, "of") as i64), &F6X10, t.dim);
        let tipline = format!("{}: {:.0}% passed ({} of {}), reward {:.2}, floor {:.0}%: {}", course, 100.0 * share, n(h, "passed") as i64, n(h, "of") as i64, n(h, "reward"), 100.0 * floor, s(h, "verdict"));
        ui.tip(rect(at.x, y, at.w, bh + 2), move || vec![tipline.clone(), "Held out by the harness at the end of the run; the tick is the floor.".to_string()]);
        y += bh + 3;
    }
    if held.len() > 5 && !open {
        ui.label_right(at.right(), y, &format!("+{} courses; open the card", held.len() - 5), &F6X10, t.dim);
        y += F6X10.height as i32;
    }
    // The curve: the population's mean (dim) and the net's own score (ink) by generation.
    let curve: Vec<Vec<f64>> = arr(net, "curve").iter().filter_map(|p| p.as_array()).map(|a| a.iter().filter_map(|v| v.as_num()).collect()).collect();
    if curve.len() >= 2 && y + 24 <= at.bottom() {
        let cr = rect(at.x, y + 2, at.w, (at.bottom() - y - 4).min(if open { 70 } else { 30 }));
        ui.outline(cr, t.line);
        let (lo, hi) = curve.iter().flat_map(|p| [p[1], p[3]]).fold((f64::MAX, f64::MIN), |(a, b), v| (a.min(v), b.max(v)));
        let span = (hi - lo).max(1e-6);
        let px = |i: usize| cr.x + 1 + (i as i32) * (cr.w - 3) / (curve.len() as i32 - 1).max(1);
        let py = |v: f64| cr.bottom() - 2 - ((v - lo) / span * (cr.h - 4) as f64) as i32;
        for (k, c) in [(1usize, t.dim), (3usize, t.ink)] {
            for i in 0..curve.len() - 1 {
                let ((x0, y0), (x1, y1)) = ((px(i), py(curve[i][k])), (px(i + 1), py(curve[i + 1][k])));
                let steps = (x1 - x0).abs().max((y1 - y0).abs()).max(1);
                for sgm in 0..=steps {
                    ui.c.rect(x0 + (x1 - x0) * sgm / steps, y0 + (y1 - y0) * sgm / steps, 1, 1, c);
                }
            }
        }
        let last = curve.last().unwrap();
        let first = curve.first().unwrap();
        let line = format!("train: mean {:.2} -> {:.2}, net {:.2} -> {:.2} over {} generations", first[1], last[1], first[3], last[3], last[0] as i64);
        ui.tip(cr, move || vec![line.clone(), "The population's mean is the dim line, the net's own score the dark one; the box is the run's range.".to_string()]);
    }
}

/// The weights: the fingerprint, the listening, the speaking, the layers.
fn draw_weights(ui: &mut Ui, at: Rect, net: &Value, open: bool) {
    let t = ui.t;
    ui.label(at.x, at.y, "WEIGHTS", &F6X10, t.dim);
    let Some(nu) = net.get("numbers").filter(|x| !matches!(x, Value::Null)) else {
        let f = s(net, "format");
        let cols = ((at.w) / F8X13.width as i32).max(10) as usize;
        let mut yy = at.y + 14;
        for l in wrap(if f.is_empty() { "not a TCNET1 file: no numbers read" } else { &f }, cols).iter().take(5) {
            ui.label_in(at.x, yy, at.w, l, &F8X13, t.dim);
            yy += F8X13.height as i32 + 3;
        }
        return;
    };
    let y = at.y + 14;
    // The fingerprint: |W1| pooled, rows the hidden units, columns the inputs in the tank's order.
    let side = if open { 128 } else { 72 };
    let fp: Vec<Vec<f64>> = arr(nu, "fingerprint").iter().filter_map(|r| r.as_array()).map(|a| a.iter().filter_map(|v| v.as_num()).collect()).collect();
    let fr = rect(at.x, y, side, side);
    if !fp.is_empty() {
        let max = fp.iter().flatten().fold(1e-9f64, |m, v| m.max(*v));
        let (rows, cols) = (fp.len() as i32, fp[0].len() as i32);
        for (ry, row) in fp.iter().enumerate() {
            for (cx, v) in row.iter().enumerate() {
                let (x0, x1) = (fr.x + cx as i32 * side / cols, fr.x + (cx as i32 + 1) * side / cols);
                let (y0, y1) = (fr.y + ry as i32 * side / rows, fr.y + (ry as i32 + 1) * side / rows);
                // Two ramps, dark to the accent to white: a wash of middling cells reads as texture,
                // the few loud cells as points, where one ramp made the whole square one green.
                let k = (v / max).powf(0.7);
                let c = if k < 0.6 { blend(t.tile, t.accent, k / 0.6) } else { blend(t.accent, t.ink, (k - 0.6) / 0.4) };
                ui.c.rect(x0, y0, (x1 - x0).max(1), (y1 - y0).max(1), c);
            }
        }
        ui.outline(fr, t.line);
        ui.tip(fr, move || vec![
            "The first layer's |w|, pooled to sixteen by sixteen: columns are the inputs in the tank's order (compass first, the economy last), rows the hidden units.".to_string(),
            format!("Brightest cell {:.3} mean |w|. A net that listens to one sense group shows a bright column; one that spread shows a wash.", max),
        ]);
    }
    // Listening by group, as bars to the right of the fingerprint.
    let lx = fr.right() + 8;
    let lw = at.right() - lx;
    let groups: Vec<(String, f64)> = arr(nu, "listening").iter().filter_map(|g| g.as_array()).filter_map(|a| Some((a.first()?.as_str()?.to_string(), a.get(1)?.as_num()?))).collect();
    let gmax = groups.iter().fold(1e-9f64, |m, g| m.max(g.1));
    let gmin = groups.iter().fold(f64::MAX, |m, g| m.min(g.1)).min(gmax);
    let bh = if open { 11 } else { 7 };
    let mut yy = y;
    for (name, v) in &groups {
        if yy + bh > fr.bottom() {
            break;
        }
        let nw = F6X10.measure("contacts ") as i32;
        ui.label(lx, yy - 1, name, &F6X10, t.dim);
        // The bar runs from half the quietest group to the loudest: the ear's differences are
        // tenths, and bars from zero all look full.
        let floor = gmin * 0.5;
        bar(ui, rect(lx + nw, yy, (lw - nw).max(10), bh), (v - floor) / (gmax - floor).max(1e-9), t.accent);
        let tipl = format!("{}: mean |w| {:.4} over its inputs in the first layer; the bars run from half the quietest group ({:.4}) to the loudest ({:.4})", name, v, gmin, gmax);
        ui.tip(rect(lx, yy, lw, bh + 1), move || vec![tipl.clone()]);
        yy += bh + 2;
    }
    // Speaking by head, under the fingerprint; then each layer's norm and singular values.
    let mut y2 = fr.bottom() + 6;
    let heads: Vec<(String, f64)> = arr(nu, "speaking").iter().filter_map(|g| g.as_array()).filter_map(|a| Some((a.first()?.as_str()?.to_string(), a.get(1)?.as_num()?))).collect();
    let hmax = heads.iter().fold(1e-9f64, |m, g| m.max(g.1));
    let hmin = heads.iter().fold(f64::MAX, |m, g| m.min(g.1)).min(hmax) * 0.5;
    let hw = (at.w - 2) / heads.len().max(1) as i32;
    let hh = if open { 28 } else { 16 };
    for (i, (name, v)) in heads.iter().enumerate() {
        let x = at.x + i as i32 * hw;
        let h = ((hh as f64) * ((v - hmin) / (hmax - hmin).max(1e-9))).max(1.0) as i32;
        ui.c.rect(x, y2 + hh - h, hw - 2, h, t.up);
        if hw >= 24 {
            ui.label_in(x, y2 + hh + 1, hw - 2, name, &F6X10, t.dim);
        }
        let tipl = format!("head {}: mean |w| {:.4} in the last layer; how hard the net speaks through it", name, v);
        ui.tip(rect(x, y2, hw, hh + 10), move || vec![tipl.clone()]);
    }
    y2 += hh + F6X10.height as i32 + 4;
    let layers: Vec<String> = arr(nu, "layers")
        .iter()
        .map(|l| {
            let sv: Vec<String> = arr(l, "singular").iter().filter_map(|v| v.as_num()).map(|v| format!("{:.1}", v)).collect();
            format!("{}x{} |W| {:.1}  s {}  zero {:.0}%", n(l, "inputs") as i64, n(l, "outputs") as i64, n(l, "norm"), sv.join(" "), 100.0 * n(l, "sparsity"))
        })
        .collect();
    for l in &layers {
        if y2 + F6X10.height as i32 > at.bottom() {
            break;
        }
        ui.label_in(at.x, y2, at.w, l, &F6X10, t.dim);
        y2 += F6X10.height as i32 + 1;
    }
    let params = n(nu, "parameters") as i64;
    ui.tip(rect(at.x, fr.bottom() + 6 + hh + F6X10.height as i32 + 4, at.w, (y2 - (fr.bottom() + 6 + hh + F6X10.height as i32 + 4)).max(1)), move || vec![
        format!("{} parameters. A row a layer: its shape, its Frobenius norm, its first three singular values (power iteration), the share of weights under 0.001.", params),
        "A layer whose first singular value dwarfs the second is one direction; a near-flat trio is many.".to_string(),
    ]);
    let _ = Light::Full;
}
