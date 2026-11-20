use std::env;
use std::path::PathBuf;

/// Resolve the Termux:X11 Unix socket path (`$TMPDIR/.X11-unix/X<num>`) for pure-Rust `x11rb`.
#[allow(dead_code)]
pub fn termux_x11_socket_path(display: &str) -> Option<PathBuf> {
    let trimmed = display.strip_prefix(':')?;
    let num = trimmed.split('.').next()?;
    if num.is_empty() || !num.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let tmp = env::var("TMPDIR")
        .ok()
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "/data/data/com.termux/files/usr/tmp".to_string());
    Some(PathBuf::from(tmp).join(".X11-unix").join(format!("X{num}")))
}

pub fn cmd_hide_cursor() -> Result<(), String> {
    // TODO: Uncomment `x11rb` in Cargo.toml, connect via `termux_x11_socket_path`,
    // and port `XFixesHideCursor` / `XFixesShowCursor` idle logic from `daemons/native/qs_native.c`.
    Err("hide-cursor is not implemented in the Rust rewrite yet".to_string())
}

pub fn cmd_submenu_watch(_args: &[String]) -> Result<(), String> {
    // TODO: Uncomment `x11rb` in Cargo.toml, subscribe to `XI_RawButtonPress` via XInput2,
    // and print `CLOSE` when taps land outside the active popup/dock.
    Err("submenu-watch is not implemented in the Rust rewrite yet".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn resolves_display_number() {
        let path = termux_x11_socket_path(":0.0").expect("valid display");
        assert!(path.ends_with(".X11-unix/X0") || path.ends_with(r".X11-unix\X0"));
        assert_eq!(termux_x11_socket_path("invalid"), None);
    }
}
