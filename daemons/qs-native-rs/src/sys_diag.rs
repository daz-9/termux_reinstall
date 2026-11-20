use serde::Serialize;

/// JSON payload emitted on each tick by `qs-native sys-diag` for Quickshell's Wayland topbar.
#[allow(dead_code)]
#[derive(Debug, Serialize)]
pub struct SysDiagPayload {
    pub cpu: u8,
    pub mem_used: String,
    pub mem_total: String,
    pub mem_pct: u8,
    pub bat_pct: i32,
    pub bat_status: String,
    pub temp_c: Option<f64>,
    pub watts: String,
    pub wifi_ok: bool,
    pub wifi_rate: i32,
    pub wifi_rssi: i32,
    pub ip: String,
}

pub fn cmd_sys_diag() -> Result<(), String> {
    // TODO:
    // 1. Loop every 2s reading CPU (`proc_stats::read_total_jiffies`) & RAM (`proc_stats::read_mem_info`).
    // 2. Every 6th tick (12s), spawn `termux-battery-status` and `termux-wifi-connectioninfo`
    //    with a ~2s timeout and deserialize their JSON into `serde_json::Value`.
    // 3. Serialize `SysDiagPayload` with `serde_json::to_string` and flush stdout.
    Err("sys-diag is not implemented in the Rust rewrite yet".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn serializes_expected_json_keys() {
        let payload = SysDiagPayload {
            cpu: 12,
            mem_used: "3.2".to_string(),
            mem_total: "8.0".to_string(),
            mem_pct: 40,
            bat_pct: 85,
            bat_status: "DISCHARGING".to_string(),
            temp_c: Some(31.4),
            watts: "-2.1W".to_string(),
            wifi_ok: true,
            wifi_rate: 866,
            wifi_rssi: -52,
            ip: "192.168.1.42".to_string(),
        };
        let json = serde_json::to_string(&payload).expect("serialize sys-diag");
        assert!(json.contains("\"mem_used\":\"3.2\""));
        assert!(json.contains("\"wifi_ok\":true"));
    }
}
