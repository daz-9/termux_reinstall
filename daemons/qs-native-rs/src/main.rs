mod proc_stats;
mod rish;
mod sys_diag;
mod wl_workspaces;
mod x11;

use std::env;
use std::process::ExitCode;

fn usage() {
    eprintln!(
        "usage: qs-native <cpu|sys-diag|hide-cursor|submenu-watch|wl-workspaces|media-stream|media-status|focus-status|focus-toggle|calendar>"
    );
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().collect();
    let Some(sub) = args.get(1).map(String::as_str) else {
        usage();
        return ExitCode::from(2);
    };

    let result = match sub {
        "cpu" => proc_stats::cmd_cpu(),
        "sys-diag" => sys_diag::cmd_sys_diag(),
        "hide-cursor" => x11::cmd_hide_cursor(),
        "submenu-watch" => x11::cmd_submenu_watch(&args[2..]),
        "wl-workspaces" => wl_workspaces::cmd_wl_workspaces(),
        "media-stream" => rish::cmd_media_stream(),
        "media-status" => rish::cmd_media_status(),
        "focus-status" => rish::cmd_focus_status(),
        "focus-toggle" => rish::cmd_focus_toggle(),
        "calendar" => rish::cmd_calendar(&args[2..]),
        other => {
            eprintln!("qs-native: unknown subcommand '{other}'");
            return ExitCode::from(2);
        }
    };

    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(err) => {
            eprintln!("qs-native {sub}: {err}");
            ExitCode::FAILURE
        }
    }
}
