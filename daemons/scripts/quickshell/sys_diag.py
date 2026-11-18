#!/data/data/com.termux/files/usr/bin/python3
"""Stream CPU, RAM, battery/thermal, and Wi-Fi diagnostics as JSON lines for Quickshell."""

import json
import os
import shutil
import signal
import subprocess
import sys
import time


def _total_jiffies() -> int:
    total = 0
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat") as f:
                data = f.read()
            rp = data.rfind(")")
            if rp < 0:
                continue
            fields = data[rp + 2 :].split()
            total += int(fields[11]) + int(fields[12])
        except (OSError, IndexError, ValueError):
            pass
    return total


def _mem_info() -> tuple[str, str, int]:
    vals = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                k, _, rest = line.partition(":")
                if k in ("MemTotal", "MemAvailable", "MemFree"):
                    parts = rest.strip().split()
                    if parts:
                        vals[k] = int(parts[0])
    except OSError:
        return "0.0", "0.0", 0
    tot_kb = vals.get("MemTotal", 0)
    avail_kb = vals.get("MemAvailable", vals.get("MemFree", 0))
    if tot_kb <= 0:
        return "0.0", "0.0", 0
    used_kb = max(0, tot_kb - avail_kb)
    pct = min(100, max(0, round(used_kb / tot_kb * 100)))
    return f"{used_kb / 1048576:.1f}", f"{tot_kb / 1048576:.1f}", pct


def _run_json(cmd: list[str], timeout_s: float = 2.0) -> dict | None:
    if not shutil.which(cmd[0]):
        return None
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        if res.returncode == 0 and res.stdout.strip():
            return json.loads(res.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        pass
    return None


def main() -> int:
    running = True

    def stop(_sig, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    clk = os.sysconf("SC_CLK_TCK")
    ncpu = os.cpu_count() or 1
    j_prev = _total_jiffies()
    t_prev = time.monotonic()

    bat = {"bat_pct": -1, "bat_status": "UNKNOWN", "temp_c": None, "watts": ""}
    wifi = {"wifi_ok": False, "wifi_rate": 0, "wifi_rssi": 0, "ip": ""}

    time.sleep(0.25)
    tick = 0
    while running:
        j_now = _total_jiffies()
        t_now = time.monotonic()
        dt = max(0.05, t_now - t_prev)
        cpu_pct = min(100, max(0, round(((j_now - j_prev) / clk) / (dt * ncpu) * 100.0)))
        j_prev, t_prev = j_now, t_now

        mem_used, mem_total, mem_pct = _mem_info()

        # Refresh Termux:API battery & Wi-Fi every ~12s (and immediately on tick 0)
        if tick % 6 == 0:
            bdata = _run_json(["termux-battery-status"])
            if bdata:
                bat["bat_pct"] = int(bdata.get("percentage", -1))
                bat["bat_status"] = str(bdata.get("status", "UNKNOWN")).upper()
                if "temperature" in bdata:
                    try:
                        bat["temp_c"] = round(float(bdata["temperature"]), 1)
                    except (TypeError, ValueError):
                        pass
                try:
                    mv = float(bdata.get("voltage", 0))
                    ua = float(bdata.get("current", 0))
                    w = (mv / 1000.0) * (ua / 1_000_000.0)
                    bat["watts"] = f"{w:+.1f}W" if abs(w) >= 0.1 else ""
                except (TypeError, ValueError):
                    bat["watts"] = ""

            wdata = _run_json(["termux-wifi-connectioninfo"])
            if wdata:
                state = str(wdata.get("supplicant_state", "")).upper()
                wifi["wifi_ok"] = (state == "COMPLETED" and bool(wdata.get("ip")))
                wifi["wifi_rate"] = int(wdata.get("link_speed_mbps", 0) or 0)
                wifi["wifi_rssi"] = int(wdata.get("rssi", 0) or 0)
                wifi["ip"] = str(wdata.get("ip", "") or "")

        payload = {
            "cpu": cpu_pct,
            "mem_used": mem_used,
            "mem_total": mem_total,
            "mem_pct": mem_pct,
            **bat,
            **wifi,
        }
        print(json.dumps(payload), flush=True)

        tick += 1
        for _ in range(20):
            if not running:
                break
            time.sleep(0.1)

    return 0


if __name__ == "__main__":
    sys.exit(main())
