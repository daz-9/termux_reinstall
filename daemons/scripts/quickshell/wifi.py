#!/data/data/com.termux/files/usr/bin/python3
"""Lightweight Wi-Fi status, scan, toggle, connect, and settings helper for Quickshell."""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys


_SCAN_LINE_RE = re.compile(
    r"^\s*([0-9a-fA-F:]{17})\s+(\d+)\s+(-?\d+)\s+\S+\s*(.*?)\s*(\[.*\])?\s*$"
)


def _band_from_freq(freq: int) -> str:
    if freq >= 5925:
        return "6 GHz"
    if freq >= 4900:
        return "5 GHz"
    if freq >= 2400:
        return "2.4 GHz"
    return ""


def _get_status() -> dict:
    bin_path = shutil.which("termux-wifi-connectioninfo")
    if not bin_path:
        return {
            "ok": False,
            "enabled": False,
            "ssid": "",
            "ip": "",
            "rssi": 0,
            "rate_mbps": 0,
            "freq_mhz": 0,
            "band": "",
        }
    try:
        res = subprocess.run([bin_path], capture_output=True, text=True, timeout=2.0)
        if res.returncode != 0 or not res.stdout.strip():
            raise ValueError("empty")
        d = json.loads(res.stdout)
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        return {
            "ok": False,
            "enabled": False,
            "ssid": "",
            "ip": "",
            "rssi": 0,
            "rate_mbps": 0,
            "freq_mhz": 0,
            "band": "",
        }

    state = str(d.get("supplicant_state", "")).upper()
    ip = str(d.get("ip", "") or "").strip()
    raw_ssid = str(d.get("ssid", "") or "").strip()
    ssid = "" if raw_ssid in ("", "<unknown ssid>") else raw_ssid
    rssi = int(d.get("rssi", 0) or 0)
    rate = int(d.get("link_speed_mbps", 0) or 0)
    freq = int(d.get("frequency_mhz", 0) or 0)
    enabled = state not in ("UNINITIALIZED", "INTERFACE_DISABLED")
    ok = state == "COMPLETED" and bool(ip)

    return {
        "ok": ok,
        "enabled": enabled,
        "ssid": ssid,
        "ip": ip,
        "rssi": rssi,
        "rate_mbps": rate,
        "freq_mhz": freq,
        "band": _band_from_freq(freq),
    }


def _dedup_sort(entries: list[dict]) -> list[dict]:
    by_ssid: dict[str, dict] = {}
    for item in entries:
        ssid = item["ssid"]
        if not ssid:
            continue
        prev = by_ssid.get(ssid)
        if prev is None or item["rssi"] > prev["rssi"]:
            by_ssid[ssid] = item
    return sorted(by_ssid.values(), key=lambda x: x["rssi"], reverse=True)[:12]


def _scan_via_rish(rescan: bool) -> dict | None:
    rish = os.path.expanduser("~/.local/bin/rish")
    if not os.path.exists(rish):
        return None
    scan_prefix = "cmd wifi start-scan >/dev/null 2>&1; " if rescan else ""
    cmd = f"{scan_prefix}cmd wifi list-scan-results; echo __NETS__; cmd wifi list-networks"
    try:
        res = subprocess.run(
            [rish, "-c", cmd],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=4.0,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    combined = (res.stdout or "") + "\n" + (res.stderr or "")
    if res.returncode != 0 or not combined.strip():
        return None

    saved: set[str] = set()
    raw_items: list[dict] = []
    for line in combined.splitlines():
        s = line.strip()
        if not s or s.startswith("BSSID") or s.startswith("Network Id"):
            continue
        m_net = re.match(r"^\d+\s+(.+?)\s+(open|owe|wpa\S*|wep\S*)\s*$", s, re.IGNORECASE)
        if m_net:
            saved.add(m_net.group(1).strip())
            continue
        m = _SCAN_LINE_RE.match(line)
        if not m:
            continue
        freq = int(m.group(2))
        rssi = int(m.group(3))
        ssid = (m.group(4) or "").strip()
        flags = (m.group(5) or "").upper()
        if not ssid:
            continue
        secure = any(tok in flags for tok in ("WPA", "RSN", "WEP", "EAP", "SAE", "PSK"))
        if not secure:
            sec_type = "owe" if "OWE" in flags else "open"
        else:
            sec_type = "wpa3" if "SAE" in flags else "wpa2"
        raw_items.append({
            "ssid": ssid,
            "rssi": rssi,
            "freq": freq,
            "band": _band_from_freq(freq),
            "secure": secure,
            "sec_type": sec_type,
            "saved": False,
        })

    for item in raw_items:
        item["saved"] = item["ssid"] in saved

    return {"networks": _dedup_sort(raw_items), "note": "", "source": "rish"}


def _scan_via_termux_api() -> dict:
    bin_path = shutil.which("termux-wifi-scaninfo")
    if not bin_path:
        return {"networks": [], "note": "Install Termux:API or start Shizuku", "source": "none"}
    try:
        res = subprocess.run([bin_path], capture_output=True, text=True, timeout=3.5)
        data = json.loads(res.stdout or "[]")
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        return {"networks": [], "note": "Wi-Fi scan failed", "source": "none"}

    if isinstance(data, dict) and data.get("API_ERROR"):
        return {"networks": [], "note": str(data["API_ERROR"]), "source": "termux-api"}
    if not isinstance(data, list):
        return {"networks": [], "note": "No nearby networks found", "source": "termux-api"}

    raw_items: list[dict] = []
    for ap in data:
        if not isinstance(ap, dict):
            continue
        ssid = str(ap.get("ssid", "") or "").strip()
        if not ssid or ssid == "<unknown ssid>":
            continue
        freq = int(ap.get("frequency_mhz", 0) or 0)
        rssi = int(ap.get("rssi", -99) or -99)
        caps = str(ap.get("capabilities", "") or "").upper()
        secure = any(tok in caps for tok in ("WPA", "RSN", "WEP", "EAP", "SAE", "PSK"))
        sec_type = "owe" if (not secure and "OWE" in caps) else ("open" if not secure else "wpa2")
        raw_items.append({
            "ssid": ssid,
            "rssi": rssi,
            "freq": freq,
            "band": _band_from_freq(freq),
            "secure": secure,
            "sec_type": sec_type,
            "saved": False,
        })
    nets = _dedup_sort(raw_items)
    note = "" if nets else "No nearby networks found"
    return {"networks": nets, "note": note, "source": "termux-api"}


def _scan_networks(rescan: bool) -> dict:
    rish_res = _scan_via_rish(rescan)
    if rish_res is not None:
        if not rish_res["networks"]:
            rish_res["note"] = "No nearby networks found"
        return rish_res
    return _scan_via_termux_api()


def _toggle_wifi(target: str) -> int:
    enable = target == "on"
    rish = os.path.expanduser("~/.local/bin/rish")
    if os.path.exists(rish):
        arg = "enabled" if enable else "disabled"
        try:
            res = subprocess.run(
                [rish, "-c", f"cmd wifi set-wifi-enabled {arg}"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=3.0,
            )
            if res.returncode == 0:
                return 0
        except (OSError, subprocess.SubprocessError):
            pass

    t_bin = shutil.which("termux-wifi-enable")
    if t_bin:
        try:
            subprocess.run([t_bin, "true" if enable else "false"], timeout=2.5, check=False)
            return 0
        except (OSError, subprocess.SubprocessError):
            pass
    return 1


def _connect_open(ssid: str, sec_type: str) -> int:
    rish = os.path.expanduser("~/.local/bin/rish")
    if not ssid or not os.path.exists(rish):
        return _open_settings()
    sec = sec_type if sec_type in ("open", "owe") else "open"
    cmd = f"cmd wifi connect-network {shlex.quote(ssid)} {sec}"
    try:
        res = subprocess.run(
            [rish, "-c", cmd],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=4.0,
        )
        return 0 if res.returncode == 0 else 1
    except (OSError, subprocess.SubprocessError):
        return 1


def _open_settings() -> int:
    am_bin = shutil.which("am") or "/system/bin/am"
    try:
        subprocess.Popen(
            [am_bin, "start", "-a", "android.settings.WIFI_SETTINGS"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return 0
    except OSError:
        return 1


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "toggle":
        target = sys.argv[2] if len(sys.argv) > 2 else "on"
        return _toggle_wifi(target)
    if cmd == "scan":
        rescan = "--rescan" in sys.argv[2:]
        print(json.dumps(_scan_networks(rescan)), flush=True)
        return 0
    if cmd == "connect":
        ssid = sys.argv[2] if len(sys.argv) > 2 else ""
        sec_type = sys.argv[3] if len(sys.argv) > 3 else "open"
        return _connect_open(ssid, sec_type)
    if cmd == "settings":
        return _open_settings()
    print(json.dumps(_get_status()), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
