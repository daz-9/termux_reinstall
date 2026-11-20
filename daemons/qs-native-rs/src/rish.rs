use serde::Serialize;

#[allow(dead_code)]
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct CalendarEvent {
    pub title: String,
    pub begin_ms: i64,
    pub end_ms: i64,
    pub all_day: bool,
    pub cal_id: i32,
}

#[allow(dead_code)]
#[derive(Debug, Serialize)]
pub struct MediaPayload {
    pub kind: &'static str,
    pub available: bool,
    pub playing: bool,
    pub state: String,
    pub package: String,
    pub app: String,
    pub tag: String,
    pub title: String,
    pub artist: String,
    pub album: String,
    pub pos_sec: i64,
    pub pos_text: String,
}

#[allow(dead_code)]
#[derive(Debug, Serialize)]
pub struct FocusPayload {
    pub kind: &'static str,
    pub available: bool,
    pub zen: i32,
    pub dnd: bool,
    pub notif_count: i32,
    pub label: String,
}

/// Split Android's `MediaDescription.toString()` (`title, artist, album`) from the right.
#[allow(dead_code)]
pub fn parse_media_description(desc: &str) -> (String, String, String) {
    if desc.is_empty() || desc == "null" {
        return (String::new(), String::new(), String::new());
    }
    let clean = |s: &str| {
        if s == "null" {
            String::new()
        } else {
            s.to_string()
        }
    };
    let Some((before_last, last)) = desc.rsplit_once(", ") else {
        return (clean(desc), String::new(), String::new());
    };
    let Some((first, middle)) = before_last.rsplit_once(", ") else {
        return (clean(before_last), clean(last), String::new());
    };
    (clean(first), clean(middle), clean(last))
}

/// Parse one row from `content query --uri content://com.android.calendar/instances/when/...`
/// matching fields from the right so titles containing `, begin=` etc. still parse cleanly.
#[allow(dead_code)]
pub fn parse_calendar_row(line: &str) -> Option<CalendarEvent> {
    let (_, after_title) = line.split_once("title=")?;
    let (before_cal, cal_str) = after_title.rsplit_once(", calendar_id=")?;
    let (before_all_day, all_day_str) = before_cal.rsplit_once(", allDay=")?;
    let (before_end, end_str) = before_all_day.rsplit_once(", end=")?;
    let (title, begin_str) = before_end.rsplit_once(", begin=")?;

    let begin_ms = begin_str.trim().parse().ok()?;
    let end_ms = if end_str.trim() == "NULL" {
        0
    } else {
        end_str.trim().parse().ok()?
    };
    let all_day = all_day_str.trim().parse::<i32>().unwrap_or(0) != 0;
    let cal_id = cal_str.trim().parse().unwrap_or(0);

    Some(CalendarEvent {
        title: title.to_string(),
        begin_ms,
        end_ms,
        all_day,
        cal_id,
    })
}

pub fn cmd_media_stream() -> Result<(), String> {
    // TODO: Maintain a persistent `/system/bin/app_process` (`rish`) child process,
    // read commands from stdin on a worker thread, and emit framed JSON responses.
    Err("media-stream is not implemented in the Rust rewrite yet".to_string())
}

pub fn cmd_media_status() -> Result<(), String> {
    Err("media-status is not implemented in the Rust rewrite yet".to_string())
}

pub fn cmd_focus_status() -> Result<(), String> {
    Err("focus-status is not implemented in the Rust rewrite yet".to_string())
}

pub fn cmd_focus_toggle() -> Result<(), String> {
    Err("focus-toggle is not implemented in the Rust rewrite yet".to_string())
}

pub fn cmd_calendar(_args: &[String]) -> Result<(), String> {
    Err("calendar is not implemented in the Rust rewrite yet".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_media_description_with_commas_in_title() {
        let (title, artist, album) =
            parse_media_description("Hello, World, Some Artist, Best Album");
        assert_eq!(title, "Hello, World");
        assert_eq!(artist, "Some Artist");
        assert_eq!(album, "Best Album");
    }

    #[test]
    fn parses_calendar_row_with_tricky_title() {
        let row = "Row: 0 title=Plan, begin=soon, begin=1700000000000, end=1700003600000, allDay=0, calendar_id=3";
        let ev = parse_calendar_row(row).expect("parse calendar row");
        assert_eq!(ev.title, "Plan, begin=soon");
        assert_eq!(ev.begin_ms, 1_700_000_000_000);
        assert_eq!(ev.end_ms, 1_700_003_600_000);
        assert!(!ev.all_day);
        assert_eq!(ev.cal_id, 3);
    }
}
