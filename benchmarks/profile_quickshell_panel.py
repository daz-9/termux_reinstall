#!/data/data/com.termux/files/usr/bin/env python3
"""
Measures real Quickshell side widget panel (WidgetHub) open/close animation FPS,
frame time distribution (avg/p95/max ms), and CPU/RSS across X11 and Wayland configs
(CPU software vs GPU accelerated).
"""
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
HOME = os.environ.get("HOME", "/data/data/com.termux/files/home")
TMPDIR = os.environ.get("TMPDIR", f"{PREFIX}/tmp")
PANVK_ICD = f"{PREFIX}/share/vulkan/icd.d/panfrost_icd.aarch64.json"
CLK_TCK = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
DISPLAY_NUM = ":9"
BENCH_DIR = Path(TMPDIR) / "qs_panel_bench"

INJECT_QML = """
    // --- BENCHMARK HARNESS (auto-injected in temp copy) ---
    property int _benchToggleCount: 0
    property double _benchLastToggleMs: 0
    property bool _benchInAnim: false
    property var _benchAnimFrameMs: []
    property var _benchAllFrameMs: []

    FrameAnimation {
        id: _benchFrameAnim
        running: true
        onTriggered: {
            const ms = frameTime * 1000.0;
            if (ms > 0 && ms < 2000) {
                root._benchAllFrameMs.push(ms);
                const now = Date.now();
                if (root._benchInAnim && (now - root._benchLastToggleMs) <= 300) {
                    root._benchAnimFrameMs.push(ms);
                }
            }
        }
    }

    Timer {
        id: _benchTimer
        interval: 600
        repeat: true
        running: true
        onTriggered: {
            root._benchToggleCount += 1;
            if (root._benchToggleCount >= 2 && root._benchToggleCount <= 9) {
                root._benchLastToggleMs = Date.now();
                root._benchInAnim = true;
                root.toggleWidgets();
            } else if (root._benchToggleCount === 10) {
                running = false;
                const a = root._benchAnimFrameMs;
                const all = root._benchAllFrameMs;
                console.log("BENCH_RESULT=" + JSON.stringify({
                    anim_frames: a.length,
                    anim_ms: a,
                    total_frames: all.length,
                    toggles: 8
                }));
                Qt.quit();
            }
        }
    }
    // --- END BENCHMARK HARNESS ---
"""


def prepare_bench_qml():
    if BENCH_DIR.exists():
        shutil.rmtree(BENCH_DIR)
    BENCH_DIR.mkdir(parents=True)
    os.symlink(f"{HOME}/.config/quickshell/components", BENCH_DIR / "components")

    for fname in ("shell.qml", "wayland.qml"):
        src = Path(f"{HOME}/.config/quickshell/{fname}").read_text()
        # Inject right before the final closing brace of ShellRoot
        idx = src.rfind("}")
        patched = src[:idx] + INJECT_QML + "\n}\n"
        (BENCH_DIR / fname).write_text(patched)


def read_proc(pid):
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        rp = stat.rfind(")")
        comm = stat[stat.find("(") + 1 : rp]
        fields = stat[rp + 2 :].split()
        ticks = int(fields[11]) + int(fields[12])
        rss_kb = 0
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                rss_kb = int(line.split()[1])
                break
        return ticks, rss_kb, comm
    except OSError:
        return None


def cleanup():
    for comm in [
        "quickshell", "qs-native", "swaybg", "swayfx", "sway", "labwc",
        "Xwayland", "polybar", "fastcompmgr", "sxhkd", "bspwm",
        "termux-x11", "virgl_test_serv",
    ]:
        subprocess.run(["pkill", "-x", comm], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "com.termux.x11 :9"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "virgl_test_server_android"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    time.sleep(0.4)
    for pat in [f"{TMPDIR}/.X11-unix/X9", f"{TMPDIR}/.X9-lock", f"{TMPDIR}/.virgl_test", f"{TMPDIR}/bspwm_prof_sock"]:
        try:
            os.unlink(pat)
        except OSError:
            pass
    for f in list(Path(TMPDIR).glob("wayland-*")) + list(Path(TMPDIR).glob("sway-ipc.*")):
        try:
            f.unlink()
        except OSError:
            pass


def base_env():
    env = os.environ.copy()
    env["PATH"] = f"{HOME}/.local/bin:{env.get('PATH', '')}"
    env["DISPLAY"] = DISPLAY_NUM
    env["TERMUX_X11_DISPLAY"] = DISPLAY_NUM
    env["XDG_RUNTIME_DIR"] = TMPDIR
    env["TMPDIR"] = TMPDIR
    env["XDG_CONFIG_HOME"] = f"{HOME}/.config"
    for k in [
        "WAYLAND_DISPLAY", "SWAYSOCK", "GALLIUM_DRIVER", "LIBGL_ALWAYS_SOFTWARE",
        "MESA_LOADER_DRIVER_OVERRIDE", "WLR_RENDERER", "WLR_BACKENDS",
        "WLR_GLES2_NO_DMABUF", "LD_LIBRARY_PATH", "QT_QUICK_BACKEND",
        "QSG_RHI_BACKEND", "QSG_RENDER_LOOP", "VK_DRIVER_FILES", "VK_ICD_FILENAMES",
        "QT_QPA_PLATFORM",
    ]:
        env.pop(k, None)
    return env


def start_x11(env):
    p = subprocess.Popen(["termux-x11", DISPLAY_NUM], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        if os.path.exists(f"{TMPDIR}/.X11-unix/X9"):
            break
        time.sleep(0.1)
    return p


def summarize_frames(ms_list):
    if not ms_list:
        return {"frames": 0, "avg_fps": 0.0, "avg_ms": None, "p95_ms": None, "max_ms": None}
    s = sorted(ms_list)
    avg_ms = sum(s) / len(s)
    p95 = s[min(len(s) - 1, int(len(s) * 0.95))]
    return {
        "frames": len(s),
        "avg_fps": round(1000.0 / avg_ms, 1) if avg_ms > 0 else 0.0,
        "avg_ms": round(avg_ms, 1),
        "p95_ms": round(p95, 1),
        "max_ms": round(s[-1], 1),
    }


def run_qs_bench(qml_path, qs_env, watch_pids):
    log_path = Path(TMPDIR) / "qs_panel_run.log"
    with open(log_path, "w") as lf:
        p = subprocess.Popen(
            ["quickshell", "-p", str(qml_path)],
            env=qs_env, stdout=lf, stderr=subprocess.STDOUT,
        )
    all_pids = list(watch_pids) + [p.pid]
    time.sleep(0.6)
    t0 = time.monotonic()
    s0 = {pid: read_proc(pid) for pid in all_pids}
    peak_rss = {}
    while time.monotonic() - t0 < 12.0:
        if p.poll() is not None:
            break
        for pid in all_pids:
            m = read_proc(pid)
            if m:
                peak_rss[m[2]] = max(peak_rss.get(m[2], 0), m[1])
        time.sleep(0.2)
    t1 = time.monotonic()
    s1 = {pid: read_proc(pid) for pid in all_pids}
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=2)
        except Exception:
            p.kill()

    dt = max(t1 - t0, 0.001)
    cpu = {}
    for pid in all_pids:
        if s0.get(pid) and s1.get(pid):
            dticks = max(0, s1[pid][0] - s0[pid][0])
            comm = s1[pid][2]
            cpu[comm] = round(cpu.get(comm, 0.0) + (dticks / CLK_TCK) / dt * 100.0, 1)

    txt = log_path.read_text(errors="ignore")
    m = re.search(r"BENCH_RESULT=(\{.*\})", txt)
    if not m:
        return {
            "error": "no BENCH_RESULT",
            "cpu_by_proc": cpu,
            "rss_mb": {k: round(v / 1024.0, 1) for k, v in peak_rss.items()},
            "log_tail": "\n".join(txt.splitlines()[-8:]),
        }
    data = json.loads(m.group(1))
    anim = summarize_frames(data["anim_ms"])
    return {
        "anim_fps": anim["avg_fps"],
        "anim_frames": anim["frames"],
        "anim_frames_per_toggle": round(anim["frames"] / 8.0, 1),
        "frame_avg_ms": anim["avg_ms"],
        "frame_p95_ms": anim["p95_ms"],
        "frame_max_ms": anim["max_ms"],
        "cpu_by_proc": cpu,
        "rss_mb": {k: round(v / 1024.0, 1) for k, v in peak_rss.items()},
    }


def bench_x11_panel(mode):
    cleanup()
    env = base_env()
    env["BSPWM_SOCKET"] = f"{TMPDIR}/bspwm_prof_sock"
    env["XDG_SESSION_TYPE"] = "x11"
    p_x11 = start_x11(env)
    watch = [p_x11.pid]

    if mode == "virgl":
        p_v = subprocess.Popen(
            ["virgl_test_server_android", "--multi-clients", "--angle-vulkan"],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        watch.append(p_v.pid)
        for _ in range(30):
            if os.path.exists(f"{TMPDIR}/.virgl_test"):
                break
            time.sleep(0.1)

    p_fcm = subprocess.Popen(["fastcompmgr"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    watch.append(p_fcm.pid)

    qs_env = env.copy()
    if mode == "cpu":
        qs_env["QT_QUICK_BACKEND"] = "software"
    elif mode == "virgl":
        qs_env["GALLIUM_DRIVER"] = "virpipe"
        qs_env["QSG_RHI_BACKEND"] = "opengl"
        qs_env["QSG_RENDER_LOOP"] = "basic"
    elif mode == "panvk":
        qs_env["GALLIUM_DRIVER"] = "zink"
        qs_env["VK_DRIVER_FILES"] = PANVK_ICD
        qs_env["VK_ICD_FILENAMES"] = PANVK_ICD
        qs_env["QSG_RHI_BACKEND"] = "opengl"
        qs_env["QSG_RENDER_LOOP"] = "basic"

    res = run_qs_bench(BENCH_DIR / "shell.qml", qs_env, watch)
    res["config"] = f"X11 (fastcompmgr) — {mode}"
    cleanup()
    return res


def bench_wayland_panel(wm, renderer, qs_backend="software"):
    cleanup()
    env = base_env()
    env["XDG_SESSION_TYPE"] = "wayland"
    env["WLR_BACKENDS"] = "x11"
    env["WLR_NO_HARDWARE_CURSORS"] = "1"
    env["WLR_RENDERER"] = renderer
    if renderer == "gles2":
        env["GALLIUM_DRIVER"] = "zink"
        env["VK_DRIVER_FILES"] = PANVK_ICD
        env["VK_ICD_FILENAMES"] = PANVK_ICD
        env["WLR_GLES2_NO_DMABUF"] = "1"
        if wm != "swayfx":
            env["LD_LIBRARY_PATH"] = f"{HOME}/.local/lib"

    p_x11 = start_x11(env)
    # Launch compositor with a minimal config that does NOT auto-spawn the normal quickshell
    if wm == "labwc":
        cmd = ["labwc", "-C", f"{HOME}/.config/labwc"]
    elif wm == "swayfx":
        tmp_cfg = Path(TMPDIR) / "swayfx_bench.conf"
        lines = [l for l in Path(f"{HOME}/.config/swayfx/config").read_text().splitlines() if "launch-wayland.sh" not in l]
        tmp_cfg.write_text("\n".join(lines) + "\n")
        cmd = [f"{HOME}/.local/bin/swayfx", "-c", str(tmp_cfg)]
    else:
        tmp_cfg = Path(TMPDIR) / "sway_bench.conf"
        lines = [l for l in Path(f"{HOME}/.config/sway/config").read_text().splitlines() if "launch-wayland.sh" not in l]
        tmp_cfg.write_text("\n".join(lines) + "\n")
        cmd = ["sway", "-c", str(tmp_cfg)]

    p_wm = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    wl_sock = None
    for _ in range(80):
        for p in sorted(Path(TMPDIR).glob("wayland-*")):
            if not p.name.endswith(".lock"):
                wl_sock = p.name
                break
        if wl_sock:
            break
        time.sleep(0.1)

    if wm == "labwc":
        # Kill auto-started quickshell from labwc autostart if any
        time.sleep(1.0)
        subprocess.run(["pkill", "-x", "quickshell"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        time.sleep(0.3)

    qs_env = env.copy()
    qs_env["WAYLAND_DISPLAY"] = wl_sock
    qs_env["QT_QPA_PLATFORM"] = "wayland"
    if wm in ("sway", "swayfx"):
        for _ in range(40):
            socks = sorted(Path(TMPDIR).glob("sway-ipc.*.sock"))
            if socks:
                qs_env["SWAYSOCK"] = str(socks[0])
                subprocess.run(["swaymsg", "-s", str(socks[0]), "output", "X11-1", "resolution", "2560x1600"],
                               env=qs_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                break
            time.sleep(0.1)

    if qs_backend == "software":
        qs_env["QT_QUICK_BACKEND"] = "software"
    else:
        qs_env.pop("QT_QUICK_BACKEND", None)
        qs_env["QSG_RHI_BACKEND"] = "opengl"
        qs_env["QSG_RENDER_LOOP"] = "basic"
        qs_env["GALLIUM_DRIVER"] = "zink"
        qs_env["VK_DRIVER_FILES"] = PANVK_ICD
        qs_env["VK_ICD_FILENAMES"] = PANVK_ICD

    time.sleep(0.8)
    res = run_qs_bench(BENCH_DIR / "wayland.qml", qs_env, [p_x11.pid, p_wm.pid])
    res["config"] = f"Wayland ({wm} {renderer}) — QS {qs_backend}"
    cleanup()
    return res


def main():
    prepare_bench_qml()
    results = [
        bench_x11_panel("cpu"),
        bench_x11_panel("virgl"),
        bench_x11_panel("panvk"),
        bench_wayland_panel("sway", "pixman", "software"),
        bench_wayland_panel("labwc", "pixman", "software"),
        bench_wayland_panel("sway", "gles2", "software"),
        bench_wayland_panel("swayfx", "gles2", "software"),
        bench_wayland_panel("sway", "pixman", "opengl_zink"),
    ]
    Path(TMPDIR, "quickshell_panel_fps.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    main()
