#!/data/data/com.termux/files/usr/bin/env python3
"""
Cold-start timing for the desktop launchers on an isolated termux-x11 :9 display.

Replicates what start-wayland.sh / start-x11.sh do (termux-x11 -xstartup
"dbus-launch --exit-with-session <wm>") and measures, in seconds from launch:
  - x11:        termux-x11 accepts X connections
  - wm:         compositor Wayland socket (Wayland) / bspwm socket (X11)
  - qs_spawned: quickshell process exists
  - qs_loaded:  quickshell logged "Configuration Loaded" (new log only)

Usage: profile_startup.py [swayfx|sway|x11 ...] [--runs N]
"""
import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
HOME = os.environ.get("HOME", "/data/data/com.termux/files/home")
TMPDIR = os.environ.get("TMPDIR", f"{PREFIX}/tmp")
PANVK_ICD = f"{PREFIX}/share/vulkan/icd.d/panfrost_icd.aarch64.json"
QS_LOG_ROOT = Path(TMPDIR, "quickshell", "by-id")
BSPWM_SOCK = f"{TMPDIR}/bspwm_startup_bench"

_x11 = ctypes.CDLL("libX11.so.6")
_x11.XOpenDisplay.restype = ctypes.c_void_p
_x11.XCloseDisplay.argtypes = [ctypes.c_void_p]


def x_ready():
    d = _x11.XOpenDisplay(b":9")
    if d:
        _x11.XCloseDisplay(d)
        return True
    return False


def cleanup():
    for c in ["quickshell", "qs-native", "swaybg", "swayfx", "sway", "Xwayland",
              "bspwm", "sxhkd", "polybar", "fastcompmgr"]:
        subprocess.run(["pkill", "-9", "-x", c], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-9", "-f", "com.termux.x11 :9"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.6)
    for f in [f"{TMPDIR}/.X11-unix/X9", f"{TMPDIR}/.X9-lock", BSPWM_SOCK]:
        try:
            os.unlink(f)
        except OSError:
            pass
    for f in list(Path(TMPDIR).glob("wayland-*")) + list(Path(TMPDIR).glob("sway-ipc.*")):
        try:
            f.unlink()
        except OSError:
            pass


def env_for(mode):
    env = os.environ.copy()
    for k in ["WAYLAND_DISPLAY", "SWAYSOCK", "GALLIUM_DRIVER", "LIBGL_ALWAYS_SOFTWARE",
              "WLR_RENDERER", "WLR_GLES2_NO_DMABUF", "VK_DRIVER_FILES", "VK_ICD_FILENAMES",
              "QT_QUICK_BACKEND", "QSG_RHI_BACKEND", "QSG_RENDER_LOOP", "LD_LIBRARY_PATH",
              "DBUS_SESSION_BUS_ADDRESS"]:
        env.pop(k, None)
    env.update({
        "PATH": f"{HOME}/.local/bin:{env.get('PATH', '')}",
        "DISPLAY": ":9", "TERMUX_X11_DISPLAY": ":9",
        "XDG_RUNTIME_DIR": TMPDIR, "TMPDIR": TMPDIR,
        "XDG_CONFIG_HOME": f"{HOME}/.config",
    })
    if mode == "x11":
        env["BSPWM_SOCKET"] = BSPWM_SOCK
        return env
    env.update({"XDG_SESSION_TYPE": "wayland", "WLR_BACKENDS": "x11", "WLR_NO_HARDWARE_CURSORS": "1"})
    if mode == "swayfx":  # mirrors start-wayland.sh
        env.update({"WLR_RENDERER": "gles2", "GALLIUM_DRIVER": "zink",
                    "VK_DRIVER_FILES": PANVK_ICD, "VK_ICD_FILENAMES": PANVK_ICD,
                    "WLR_GLES2_NO_DMABUF": "1"})
    else:
        env["WLR_RENDERER"] = "pixman"
    return env


def run_once(mode):
    cleanup()
    env = env_for(mode)
    if mode == "x11":
        wm_cmd = "bspwm"
    elif mode == "swayfx":
        wm_cmd = f"swayfx -c {HOME}/.config/swayfx/config"
    else:
        wm_cmd = f"sway -c {HOME}/.config/sway/config"
    before = {p.name for p in QS_LOG_ROOT.glob("*")} if QS_LOG_ROOT.exists() else set()

    t0 = time.monotonic()
    subprocess.Popen(["termux-x11", ":9", "-xstartup", f"dbus-launch --exit-with-session {wm_cmd}"],
                     env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    t = {"x11": None, "wm": None, "qs_spawned": None, "qs_loaded": None}
    while time.monotonic() - t0 < 30:
        now = time.monotonic() - t0
        if t["x11"] is None and x_ready():
            t["x11"] = now
        if t["wm"] is None:
            if mode == "x11":
                if os.path.exists(BSPWM_SOCK):
                    t["wm"] = now
            elif any(not p.name.endswith(".lock") for p in Path(TMPDIR).glob("wayland-*")):
                t["wm"] = now
        if t["qs_spawned"] is None and subprocess.run(["pgrep", "-x", "quickshell"],
                                                       capture_output=True).returncode == 0:
            t["qs_spawned"] = now
        if QS_LOG_ROOT.exists():
            for d in QS_LOG_ROOT.glob("*"):
                if d.name not in before and (d / "log.qslog").exists() \
                        and b"Configuration Loaded" in (d / "log.qslog").read_bytes():
                    t["qs_loaded"] = now
        if t["qs_loaded"] is not None:
            break
        time.sleep(0.02)

    cleanup()
    return {k: (round(v, 2) if v is not None else None) for k, v in t.items()}


def main():
    args = sys.argv[1:]
    runs = 2
    if "--runs" in args:
        i = args.index("--runs")
        runs = int(args[i + 1])
        del args[i:i + 2]
    modes = args or ["swayfx", "sway", "x11"]
    results = {}
    for mode in modes:
        results[mode] = [run_once(mode) for _ in range(runs)]
        print(mode, json.dumps(results[mode]), flush=True)
    Path(TMPDIR, "startup_profile_results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
