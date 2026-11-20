use std::fs;
use std::io::{self, Write};
use std::thread;
use std::time::{Duration, Instant};

/// Linux/Android USER_HZ for /proc/<pid>/stat jiffies.
const CLK_TCK: f64 = 100.0;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MemInfo {
    pub used_gb: String,
    pub total_gb: String,
    pub pct: u8,
}

/// Parse `utime + stime` (fields 14 & 15, i.e., index 11 & 12 after `)` ) from `/proc/<pid>/stat`.
pub fn parse_proc_stat_jiffies(content: &str) -> Option<u64> {
    let (_, rest) = content.rsplit_once(')')?;
    let mut fields = rest.split_whitespace();
    let utime: u64 = fields.nth(11)?.parse().ok()?;
    let stime: u64 = fields.next()?.parse().ok()?;
    Some(utime.saturating_add(stime))
}

/// Sum CPU jiffies across all readable `/proc/<pid>/stat` entries.
/// Needed on Android/Termux because SELinux denies unprivileged reads of `/proc/stat`.
pub fn read_total_jiffies() -> u64 {
    let Ok(entries) = fs::read_dir("/proc") else {
        return 0;
    };
    let mut total: u64 = 0;
    for entry in entries.flatten() {
        let name = entry.file_name();
        let Some(name_str) = name.to_str() else {
            continue;
        };
        if !name_str.bytes().all(|b| b.is_ascii_digit()) {
            continue;
        }
        let stat_path = entry.path().join("stat");
        if let Some(j) = fs::read_to_string(stat_path)
            .ok()
            .as_deref()
            .and_then(parse_proc_stat_jiffies)
        {
            total = total.saturating_add(j);
        }
    }
    total
}

/// Compute clamped CPU percentage `[0..=100]` safely without unsigned underflow.
pub fn compute_cpu_pct(j_prev: u64, j_now: u64, dt_secs: f64, ncpu: usize) -> u8 {
    let dt = dt_secs.max(0.05);
    let cores = ncpu.max(1) as f64;
    let dj = j_now.saturating_sub(j_prev) as f64;
    let raw = ((dj / CLK_TCK) / (dt * cores)) * 100.0;
    raw.round().clamp(0.0, 100.0) as u8
}

/// Format a Polybar CPU status line using Catppuccin Mocha thresholds.
pub fn format_polybar_cpu(pct: u8) -> String {
    let color = if pct >= 80 {
        "#f38ba8"
    } else if pct >= 50 {
        "#fab387"
    } else {
        "#94e2d5"
    };
    format!("%{{F{color}}}\u{f4bc}%{{F-}} {pct}%")
}

/// Parse `/proc/meminfo` text into GB strings and percentage used.
pub fn parse_meminfo(content: &str) -> MemInfo {
    let mut mem_total: i64 = 0;
    let mut mem_avail: Option<i64> = None;
    let mut mem_free: i64 = 0;

    for line in content.lines() {
        if let Some(val) = line
            .strip_prefix("MemTotal:")
            .and_then(|r| r.split_whitespace().next())
            .and_then(|s| s.parse().ok())
        {
            mem_total = val;
        } else if let Some(val) = line
            .strip_prefix("MemAvailable:")
            .and_then(|r| r.split_whitespace().next())
            .and_then(|s| s.parse().ok())
        {
            mem_avail = Some(val);
        } else if let Some(val) = line
            .strip_prefix("MemFree:")
            .and_then(|r| r.split_whitespace().next())
            .and_then(|s| s.parse().ok())
        {
            mem_free = val;
        }
    }

    if mem_total <= 0 {
        return MemInfo {
            used_gb: "0.0".to_string(),
            total_gb: "0.0".to_string(),
            pct: 0,
        };
    }

    let avail = mem_avail.unwrap_or(mem_free);
    let used_kb = (mem_total - avail).max(0);
    let pct = ((used_kb as f64 * 100.0) / mem_total as f64).round().clamp(0.0, 100.0) as u8;

    MemInfo {
        used_gb: format!("{:.1}", used_kb as f64 / 1_048_576.0),
        total_gb: format!("{:.1}", mem_total as f64 / 1_048_576.0),
        pct,
    }
}

#[allow(dead_code)]
pub fn read_mem_info() -> MemInfo {
    match fs::read_to_string("/proc/meminfo") {
        Ok(text) => parse_meminfo(&text),
        Err(_) => parse_meminfo(""),
    }
}

pub fn cmd_cpu() -> Result<(), String> {
    let ncpu = thread::available_parallelism().map(|n| n.get()).unwrap_or(1);
    let mut j_prev = read_total_jiffies();
    let mut t_prev = Instant::now();
    thread::sleep(Duration::from_millis(350));

    let mut stdout = io::stdout().lock();
    loop {
        let j_now = read_total_jiffies();
        let t_now = Instant::now();
        let dt = t_now.duration_since(t_prev).as_secs_f64();
        let pct = compute_cpu_pct(j_prev, j_now, dt, ncpu);
        j_prev = j_now;
        t_prev = t_now;

        if writeln!(stdout, "{}", format_polybar_cpu(pct)).is_err() || stdout.flush().is_err() {
            break;
        }
        thread::sleep(Duration::from_secs(3));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_proc_stat_with_spaces_and_parens_in_comm() {
        let sample = "1234 (my (weird) proc) S 1 2 3 4 5 6 7 8 9 10 42 58 0 0 20 0";
        assert_eq!(parse_proc_stat_jiffies(sample), Some(100));
    }

    #[test]
    fn cpu_pct_never_underflows_when_process_exits() {
        assert_eq!(compute_cpu_pct(5000, 4200, 1.0, 8), 0);
        assert_eq!(compute_cpu_pct(100, 500, 1.0, 8), 50);
    }

    #[test]
    fn polybar_cpu_uses_mocha_thresholds() {
        assert!(format_polybar_cpu(20).contains("#94e2d5"));
        assert!(format_polybar_cpu(50).contains("#fab387"));
        assert!(format_polybar_cpu(85).contains("#f38ba8"));
    }

    #[test]
    fn parses_meminfo_correctly() {
        let sample = "\
MemTotal:        8388608 kB
MemFree:         1048576 kB
MemAvailable:    2097152 kB
";
        let info = parse_meminfo(sample);
        assert_eq!(info.total_gb, "8.0");
        assert_eq!(info.used_gb, "6.0");
        assert_eq!(info.pct, 75);
    }
}
