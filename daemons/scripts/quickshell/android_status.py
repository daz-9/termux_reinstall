#!/data/data/com.termux/files/usr/bin/python3
"""Probe Termux:API and Shizuku (rish / adbd) status and print one JSON object."""

import concurrent.futures
import json
import os
import shutil
import socket
import subprocess
import sys
import time


def _getprop(name: str) -> str:
    try:
        res = subprocess.run(["getprop", name], capture_output=True, text=True, timeout=0.8)
        return res.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _tcp_open(host: str, port: int, timeout_s: float = 0.2) -> bool:
    sock = socket.socket()
    sock.settimeout(timeout_s)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        try:
            sock.close()
        except OSError:
            pass


def _probe_termux_api() -> dict:
    bat_bin = shutil.which("termux-battery-status")
    ver = os.environ.get("TERMUX_API_VERSION", "")
    if not bat_bin:
        return {
            "api_ok": False,
            "api_state": "Missing",
            "api_ver": ver,
            "api_ms": 0,
            "api_detail": "Install termux-api pkg",
        }
    t0 = time.monotonic()
    try:
        res = subprocess.run([bat_bin], capture_output=True, text=True, timeout=2.5)
        ms = round((time.monotonic() - t0) * 1000)
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            pct = data.get("percentage")
            temp = data.get("temperature")
            parts = []
            if pct is not None:
                parts.append(f"Bat {int(pct)}%")
            if temp is not None:
                parts.append(f"{float(temp):.1f}°C")
            parts.append(f"{ms}ms")
            return {
                "api_ok": True,
                "api_state": "Ready",
                "api_ver": ver,
                "api_ms": ms,
                "api_detail": " · ".join(parts),
            }
        return {
            "api_ok": False,
            "api_state": "Offline",
            "api_ver": ver,
            "api_ms": ms,
            "api_detail": "Open Termux:API app",
        }
    except subprocess.TimeoutExpired:
        return {
            "api_ok": False,
            "api_state": "Timeout",
            "api_ver": ver,
            "api_ms": 2500,
            "api_detail": "Bridge timed out (>2.5s)",
        }
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {
            "api_ok": False,
            "api_state": "Offline",
            "api_ver": ver,
            "api_ms": 0,
            "api_detail": "Bridge error",
        }


def _probe_shizuku() -> dict:
    prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    dex_path = os.path.join(prefix, "share", "rish-shizuku.dex")
    adbd_svc = _getprop("init.svc.adbd") or "unknown"
    tcp_prop = _getprop("service.adb.tcp.port")
    adb_port = int(tcp_prop) if tcp_prop.isdigit() and int(tcp_prop) > 0 else 5555
    adb_tcp_open = _tcp_open("127.0.0.1", adb_port)

    if not os.path.exists(dex_path):
        detail = f"adbd {adbd_svc}" + (f" · :{adb_port} open" if adb_tcp_open else "")
        return {
            "shizuku_ok": False,
            "shizuku_state": "No rish",
            "shizuku_ver": "",
            "shizuku_uid": -1,
            "shizuku_pid": 0,
            "adb_tcp_open": adb_tcp_open,
            "adb_port": adb_port,
            "shizuku_detail": f"No rish · {detail}",
            "api_ver_pkg": "",
        }

    # Android 14+ aborts app_process if the dex file is writable by owner.
    try:
        mode = os.stat(dex_path).st_mode & 0o777
        if mode & 0o222:
            os.chmod(dex_path, 0o400)
    except OSError:
        pass

    env = os.environ.copy()
    env.pop("LD_LIBRARY_PATH", None)
    env.pop("LD_PRELOAD", None)
    env["RISH_APPLICATION_ID"] = "com.termux"

    probe_cmd = (
        "echo UID:$(id -u); "
        "ps -A -o PID,NAME 2>/dev/null | grep -m1 shizuku_server | sed 's/^/SHZ_PS:/'; "
        "dumpsys package moe.shizuku.privileged.api 2>/dev/null | grep -m1 versionName= | sed 's/^/SHZ_VER:/'; "
        "dumpsys package com.termux.api 2>/dev/null | grep -m1 versionName= | sed 's/^/API_VER:/'"
    )
    app_proc = "/system/bin/app_process"
    if not os.path.exists(app_proc):
        app_proc = shutil.which("app_process") or "app_process"

    try:
        res = subprocess.run(
            [
                app_proc,
                f"-Djava.class.path={dex_path}",
                "/system/bin",
                "--nice-name=rish",
                "rikka.shizuku.shell.ShizukuShellLoader",
                "-c",
                probe_cmd,
            ],
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=2.8,
        )
        out = (res.stdout or "") + "\n" + (res.stderr or "")
    except subprocess.TimeoutExpired:
        detail = f"adbd {adbd_svc}" + (f" · :{adb_port}" if adb_tcp_open else "")
        return {
            "shizuku_ok": False,
            "shizuku_state": "Stopped",
            "shizuku_ver": "",
            "shizuku_uid": -1,
            "shizuku_pid": 0,
            "adb_tcp_open": adb_tcp_open,
            "adb_port": adb_port,
            "shizuku_detail": f"Timed out · {detail}",
            "api_ver_pkg": "",
        }
    except OSError as e:
        return {
            "shizuku_ok": False,
            "shizuku_state": "Error",
            "shizuku_ver": "",
            "shizuku_uid": -1,
            "shizuku_pid": 0,
            "adb_tcp_open": adb_tcp_open,
            "adb_port": adb_port,
            "shizuku_detail": str(e)[:42],
            "api_ver_pkg": "",
        }

    uid = -1
    pid = 0
    shizuku_ver = ""
    api_ver_pkg = ""
    for raw_line in out.splitlines():
        line = raw_line.strip()
        if line.startswith("UID:"):
            val = line[4:].strip()
            if val.isdigit():
                uid = int(val)
        elif line.startswith("SHZ_PS:") and "shizuku_server" in line:
            toks = line[7:].strip().split()
            if toks and toks[0].isdigit():
                pid = int(toks[0])
        elif line.startswith("SHZ_VER:") and "versionName=" in line:
            shizuku_ver = line.split("versionName=", 1)[1].strip()
        elif line.startswith("API_VER:") and "versionName=" in line:
            api_ver_pkg = line.split("versionName=", 1)[1].strip()

    if res.returncode == 0 and uid in (0, 2000):
        mode_lbl = "Root" if uid == 0 else "ADB"
        detail_parts = [f"UID {uid}"]
        if pid > 0:
            detail_parts.append(f"PID {pid}")
        if adb_tcp_open:
            detail_parts.append(f"TCP :{adb_port}")
        return {
            "shizuku_ok": True,
            "shizuku_state": f"Active · {mode_lbl}",
            "shizuku_ver": shizuku_ver,
            "shizuku_uid": uid,
            "shizuku_pid": pid,
            "adb_tcp_open": adb_tcp_open,
            "adb_port": adb_port,
            "shizuku_detail": " · ".join(detail_parts),
            "api_ver_pkg": api_ver_pkg,
        }

    low = out.lower()
    if "permission" in low or "denied" in low or "unauthorized" in low:
        state = "Denied"
        detail = "Grant Termux in Shizuku"
    else:
        state = "Stopped"
        detail = f"adbd {adbd_svc}" + (f" · :{adb_port} open" if adb_tcp_open else "")

    return {
        "shizuku_ok": False,
        "shizuku_state": state,
        "shizuku_ver": shizuku_ver,
        "shizuku_uid": uid,
        "shizuku_pid": pid,
        "adb_tcp_open": adb_tcp_open,
        "adb_port": adb_port,
        "shizuku_detail": detail,
        "api_ver_pkg": api_ver_pkg,
    }


def main() -> int:
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        f_api = pool.submit(_probe_termux_api)
        f_shz = pool.submit(_probe_shizuku)
        api = f_api.result()
        shz = f_shz.result()
    if shz.get("api_ver_pkg") and not api.get("api_ver"):
        api["api_ver"] = shz["api_ver_pkg"]
    shz.pop("api_ver_pkg", None)
    print(json.dumps({**api, **shz}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
