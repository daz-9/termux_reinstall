#!/data/data/com.termux/files/usr/bin/env python3
"""
Profiles performance & resource usage across X11 and Wayland desktop configs
(CPU-only vs GPU-accelerated) on an isolated termux-x11 :9 display.
"""
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
HOME = os.environ.get("HOME", "/data/data/com.termux/files/home")
TMPDIR = os.environ.get("TMPDIR", f"{PREFIX}/tmp")
PANVK_ICD = f"{PREFIX}/share/vulkan/icd.d/panfrost_icd.aarch64.json"
CLK_TCK = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
DISPLAY_NUM = ":9"
RESULT_PATH = Path(TMPDIR) / "desktop_profile_results.json"

DESKTOP_PROCS = {
    "termux-x11", "bspwm", "sxhkd", "fastcompmgr", "polybar",
    "sway", "swayfx", "labwc", "swaybg", "Xwayland",
    "quickshell", "qs-native", "virgl_test_serv", "virgl_test_server_android",
    "foot", "xfce4-terminal", "es2gears_x11", "es2gears_wayland", "glxgears",
}


def list_pids_by_comm():
    """Return dict[pid] = comm for all readable /proc/<pid> entries."""
    out = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        try:
            with open(f"/proc/{pid}/comm", "r") as f:
                comm = f.read().strip()
            out[pid] = comm
        except OSError:
            pass
    return out


def read_proc_metrics(pid):
    """Return (cpu_ticks, rss_kb, comm) or None if process exited."""
    try:
        with open(f"/proc/{pid}/stat", "r") as f:
            stat = f.read()
        rp = stat.rfind(")")
        comm = stat[stat.find("(") + 1 : rp]
        fields = stat[rp + 2 :].split()
        utime = int(fields[11])
        stime = int(fields[12])
        rss_kb = 0
        with open(f"/proc/{pid}/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    rss_kb = int(line.split()[1])
                    break
        return (utime + stime, rss_kb, comm)
    except OSError:
        return None


def snapshot_desktop_procs():
    """Snapshot all running desktop-related processes."""
    snap = {}
    for pid, comm in list_pids_by_comm().items():
        if comm in DESKTOP_PROCS or comm.startswith("virgl_test"):
            m = read_proc_metrics(pid)
            if m:
                snap[pid] = m
    return snap


def sample_window(duration_s, interval_s=0.5):
    """Measure exact CPU% and peak/avg RSS across desktop processes over duration_s."""
    t0 = time.monotonic()
    s0 = snapshot_desktop_procs()
    peak_total_rss_kb = sum(v[1] for v in s0.values())
    peak_per_comm_rss_kb = {}
    for _, (_, rss, comm) in s0.items():
        peak_per_comm_rss_kb[comm] = peak_per_comm_rss_kb.get(comm, 0) + rss

    elapsed = 0.0
    while elapsed < duration_s:
        time.sleep(min(interval_s, duration_s - elapsed))
        elapsed = time.monotonic() - t0
        sc = snapshot_desktop_procs()
        tot = sum(v[1] for v in sc.values())
        if tot > peak_total_rss_kb:
            peak_total_rss_kb = tot
        by_comm = {}
        for _, (_, rss, comm) in sc.items():
            by_comm[comm] = by_comm.get(comm, 0) + rss
        for comm, r in by_comm.items():
            if r > peak_per_comm_rss_kb.get(comm, 0):
                peak_per_comm_rss_kb[comm] = r

    t1 = time.monotonic()
    s1 = snapshot_desktop_procs()
    dt = max(t1 - t0, 0.001)

    cpu_by_comm = {}
    total_cpu = 0.0
    for pid, (ticks1, rss1, comm) in s1.items():
        if pid in s0:
            dticks = max(0, ticks1 - s0[pid][0])
        else:
            dticks = ticks1
        pct = (dticks / CLK_TCK) / dt * 100.0
        cpu_by_comm[comm] = cpu_by_comm.get(comm, 0.0) + pct
        total_cpu += pct

    rss_by_comm_mb = {k: round(v / 1024.0, 1) for k, v in sorted(peak_per_comm_rss_kb.items(), key=lambda x: -x[1])}
    cpu_by_comm = {k: round(v, 1) for k, v in sorted(cpu_by_comm.items(), key=lambda x: -x[1])}
    return {
        "duration_s": round(dt, 2),
        "total_cpu_pct": round(total_cpu, 1),
        "total_rss_mb": round(peak_total_rss_kb / 1024.0, 1),
        "cpu_by_proc": cpu_by_comm,
        "rss_mb_by_proc": rss_by_comm_mb,
    }


def cleanup_all(procs):
    """Terminate spawned processes and clean up :9 / wayland / virgl sockets."""
    for p in reversed(procs):
        try:
            p.terminate()
        except Exception:
            pass
    for comm in [
        "es2gears_x11", "es2gears_wayland", "glxgears", "foot", "xfce4-terminal",
        "quickshell", "qs-native", "swaybg", "swayfx", "sway", "labwc",
        "Xwayland", "polybar", "fastcompmgr", "sxhkd", "bspwm",
        "termux-x11", "virgl_test_serv",
    ]:
        subprocess.run(["pkill", "-x", comm], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "virgl_test_server_android"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "com.termux.x11 :9"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    time.sleep(0.5)
    for p in reversed(procs):
        try:
            p.kill()
            p.wait(timeout=1)
        except Exception:
            pass
    for pat in [
        f"{TMPDIR}/.X11-unix/X9", f"{TMPDIR}/.X9-lock",
        f"{TMPDIR}/.virgl_test", f"{TMPDIR}/bspwm_prof_sock",
        f"{TMPDIR}/hide-cursor.pid", f"{TMPDIR}/qs-watch.pid",
    ]:
        try:
            os.unlink(pat)
        except OSError:
            pass
    for f in Path(TMPDIR).glob("wayland-*"):
        try:
            f.unlink()
        except OSError:
            pass
    for f in Path(TMPDIR).glob("sway-ipc.*"):
        try:
            f.unlink()
        except OSError:
            pass
    time.sleep(0.3)


def wait_for_file(path, timeout=8.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if os.path.exists(path):
            return True
        time.sleep(0.1)
    return False


def wait_for_wayland_socket(timeout=10.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        for p in sorted(Path(TMPDIR).glob("wayland-*")):
            if not p.name.endswith(".lock"):
                return p.name
        time.sleep(0.1)
    return None


def wait_for_swaysock(timeout=8.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        for p in sorted(Path(TMPDIR).glob("sway-ipc.*.sock")):
            return str(p)
        time.sleep(0.1)
    return None


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
    ]:
        env.pop(k, None)
    return env


def run_gears_bench(cmd, env, duration_s=6.0):
    """Run es2gears_x11 or es2gears_wayland for duration_s, return FPS + CPU/RSS."""
    log_path = Path(TMPDIR) / "gears_bench.log"
    with open(log_path, "w") as lf:
        p = subprocess.Popen(cmd, env=env, stdout=lf, stderr=subprocess.STDOUT)
    time.sleep(0.8)  # warmup
    metrics = sample_window(duration_s, interval_s=0.5)
    try:
        p.terminate()
        p.wait(timeout=2)
    except Exception:
        p.kill()
    txt = log_path.read_text(errors="ignore") if log_path.exists() else ""
    fps_vals = [float(m.group(1)) for m in re.finditer(r"=\s*([0-9]+\.[0-9]+)\s*FPS", txt)]
    renderer = ""
    for line in txt.splitlines():
        if "GL_RENDERER" in line:
            renderer = line.split("=", 1)[-1].strip()
            break
    metrics["fps_avg"] = round(sum(fps_vals) / len(fps_vals), 1) if fps_vals else None
    metrics["fps_samples"] = [round(v, 1) for v in fps_vals]
    metrics["gl_renderer"] = renderer
    if not fps_vals:
        metrics["log_tail"] = "\n".join(txt.splitlines()[-6:])
    return metrics


def run_2d_scroll_workload(is_wayland, env, duration_s=4.5):
    """Run an active 2D redraw workload (terminal scrolling ANSI text at high rate)."""
    script = (
        "python3 -c '"
        "import sys, time; t0=time.monotonic(); i=0\n"
        "while time.monotonic()-t0 < 6.0:\n"
        "    i += 1\n"
        "    sys.stdout.write(f\"\\x1b[38;5;{(i%200)+16}m[frame {i:06d}] \" + \"#\"*80 + \"\\x1b[0m\\n\")\n"
        "    if i % 30 == 0:\n"
        "        sys.stdout.flush(); time.sleep(0.016)\n"
        "'"
    )
    if is_wayland:
        cmd = ["foot", "-e", "sh", "-c", script]
    else:
        if subprocess.run(["which", "xfce4-terminal"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            cmd = ["xfce4-terminal", "--disable-server", "-e", f"sh -c \"{script}\""]
        else:
            return {"skipped": "no x11 terminal"}
    p = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    metrics = sample_window(duration_s, interval_s=0.5)
    try:
        p.terminate()
        p.wait(timeout=2)
    except Exception:
        p.kill()
    return metrics


def profile_x11(use_gpu):
    name = "X11 (bspwm + fastcompmgr) — GPU (VirGL/PanVK)" if use_gpu else "X11 (bspwm + fastcompmgr) — CPU (Software)"
    print(f"\n>>> Profiling: {name}", flush=True)
    procs = []
    cleanup_all(procs)
    env = base_env()
    env["BSPWM_SOCKET"] = f"{TMPDIR}/bspwm_prof_sock"
    env["XDG_SESSION_TYPE"] = "x11"

    t_start = time.monotonic()
    try:
        # 1. Start termux-x11 :9
        p_x11 = subprocess.Popen(
            ["termux-x11", DISPLAY_NUM],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        procs.append(p_x11)
        if not wait_for_file(f"{TMPDIR}/.X11-unix/X9", timeout=6.0):
            return {"name": name, "error": "termux-x11 :9 failed to start"}

        # 2. Optionally start VirGL ANGLE server
        if use_gpu:
            p_virgl = subprocess.Popen(
                ["virgl_test_server_android", "--multi-clients", "--angle-vulkan"],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            procs.append(p_virgl)
            wait_for_file(f"{TMPDIR}/.virgl_test", timeout=4.0)
        else:
            env["QT_QUICK_BACKEND"] = "software"
            env["LIBGL_ALWAYS_SOFTWARE"] = "1"

        # 3. Start bspwm (which runs bspwmrc -> fastcompmgr, quickshell, qs-native, etc.)
        p_wm = subprocess.Popen(
            ["bspwm"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        procs.append(p_wm)

        # Wait for quickshell to spawn
        qs_up = False
        for _ in range(60):
            if "quickshell" in list_pids_by_comm().values():
                qs_up = True
                break
            time.sleep(0.1)
        startup_s = round(time.monotonic() - t_start, 2)

        # Settle
        time.sleep(3.0)
        idle = sample_window(5.0, interval_s=0.5)
        active_2d = run_2d_scroll_workload(False, env, duration_s=4.5)

        gl_results = {}
        if not use_gpu:
            gl_env = env.copy()
            gl_env["LIBGL_ALWAYS_SOFTWARE"] = "1"
            gl_results["cpu_llvmpipe"] = run_gears_bench(["es2gears_x11"], gl_env, duration_s=6.0)
        else:
            # Measure VirGL (virpipe)
            v_env = env.copy()
            v_env["GALLIUM_DRIVER"] = "virpipe"
            gl_results["virgl_angle"] = run_gears_bench(["es2gears_x11"], v_env, duration_s=6.0)
            # Measure PanVK/Zink
            z_env = env.copy()
            z_env["GALLIUM_DRIVER"] = "zink"
            z_env["VK_DRIVER_FILES"] = PANVK_ICD
            z_env["VK_ICD_FILENAMES"] = PANVK_ICD
            gl_results["panvk_zink"] = run_gears_bench(["es2gears_x11"], z_env, duration_s=6.0)

        return {
            "name": name,
            "stack": "x11",
            "gpu": use_gpu,
            "startup_s": startup_s,
            "quickshell_up": qs_up,
            "idle": idle,
            "active_2d": active_2d,
            "gl_bench": gl_results,
        }
    finally:
        cleanup_all(procs)


def profile_wayland(wm, renderer):
    use_gpu = (renderer == "gles2")
    label_r = "GPU (Zink/PanVK GLES2)" if use_gpu else "CPU (pixman)"
    name = f"Wayland ({wm}) — {label_r}"
    print(f"\n>>> Profiling: {name}", flush=True)
    procs = []
    cleanup_all(procs)
    env = base_env()
    env["XDG_SESSION_TYPE"] = "wayland"
    env["WLR_BACKENDS"] = "x11"
    env["WLR_NO_HARDWARE_CURSORS"] = "1"
    env["WLR_RENDERER"] = renderer

    if use_gpu:
        env["GALLIUM_DRIVER"] = "zink"
        env["VK_DRIVER_FILES"] = PANVK_ICD
        env["VK_ICD_FILENAMES"] = PANVK_ICD
        env["WLR_GLES2_NO_DMABUF"] = "1"
        if wm != "swayfx":
            env["LD_LIBRARY_PATH"] = f"{HOME}/.local/lib"
    else:
        env["LIBGL_ALWAYS_SOFTWARE"] = "1"

    t_start = time.monotonic()
    try:
        # 1. Start termux-x11 :9
        p_x11 = subprocess.Popen(
            ["termux-x11", DISPLAY_NUM],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        procs.append(p_x11)
        if not wait_for_file(f"{TMPDIR}/.X11-unix/X9", timeout=6.0):
            return {"name": name, "error": "termux-x11 :9 failed to start"}

        # 2. Launch Wayland compositor
        if wm == "labwc":
            cmd = ["labwc", "-C", f"{HOME}/.config/labwc"]
        elif wm == "swayfx":
            cmd = [f"{HOME}/.local/bin/swayfx", "-c", f"{HOME}/.config/swayfx/config"]
        else:
            cmd = ["sway", "-c", f"{HOME}/.config/sway/config"]

        wm_log = Path(TMPDIR) / f"wm_{wm}_{renderer}.log"
        with open(wm_log, "w") as lf:
            p_wm = subprocess.Popen(cmd, env=env, stdout=lf, stderr=subprocess.STDOUT)
        procs.append(p_wm)

        wl_sock = wait_for_wayland_socket(timeout=10.0)
        if not wl_sock:
            tail = wm_log.read_text(errors="ignore")[-400:]
            return {"name": name, "error": f"Wayland socket not created. Log: {tail}"}

        client_env = env.copy()
        client_env["WAYLAND_DISPLAY"] = wl_sock
        if wm in ("sway", "swayfx"):
            swaysock = wait_for_swaysock(timeout=5.0)
            if swaysock:
                client_env["SWAYSOCK"] = swaysock
                # Force standard 2560x1600 resolution so every Wayland config renders identical pixel count
                subprocess.run(
                    ["swaymsg", "-s", swaysock, "output", "X11-1", "resolution", "2560x1600"],
                    env=client_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )

        # Wait for quickshell
        qs_up = False
        for _ in range(60):
            if "quickshell" in list_pids_by_comm().values():
                qs_up = True
                break
            time.sleep(0.1)
        startup_s = round(time.monotonic() - t_start, 2)

        # Settle
        time.sleep(3.0)
        idle = sample_window(5.0, interval_s=0.5)
        active_2d = run_2d_scroll_workload(True, client_env, duration_s=4.5)

        gl_results = {}
        if use_gpu:
            z_env = client_env.copy()
            z_env["GALLIUM_DRIVER"] = "zink"
            z_env["VK_DRIVER_FILES"] = PANVK_ICD
            z_env["VK_ICD_FILENAMES"] = PANVK_ICD
            gl_results["panvk_zink"] = run_gears_bench(["es2gears_wayland"], z_env, duration_s=6.0)
        else:
            c_env = client_env.copy()
            c_env["LIBGL_ALWAYS_SOFTWARE"] = "1"
            gl_results["cpu_llvmpipe"] = run_gears_bench(["es2gears_wayland"], c_env, duration_s=6.0)
            # Also test PanVK/Zink client on pixman compositor!
            z_env = client_env.copy()
            z_env.pop("LIBGL_ALWAYS_SOFTWARE", None)
            z_env["GALLIUM_DRIVER"] = "zink"
            z_env["VK_DRIVER_FILES"] = PANVK_ICD
            z_env["VK_ICD_FILENAMES"] = PANVK_ICD
            gl_results["panvk_zink_client"] = run_gears_bench(["es2gears_wayland"], z_env, duration_s=6.0)

        return {
            "name": name,
            "stack": "wayland",
            "wm": wm,
            "renderer": renderer,
            "gpu": use_gpu,
            "startup_s": startup_s,
            "quickshell_up": qs_up,
            "idle": idle,
            "active_2d": active_2d,
            "gl_bench": gl_results,
        }
    finally:
        cleanup_all(procs)


def main():
    results = []
    configs = [
        ("x11", False),
        ("x11", True),
        ("wl", "sway", "pixman"),
        ("wl", "sway", "gles2"),
        ("wl", "labwc", "pixman"),
        ("wl", "swayfx", "gles2"),
    ]
    for cfg in configs:
        if cfg[0] == "x11":
            res = profile_x11(cfg[1])
        else:
            res = profile_wayland(cfg[1], cfg[2])
        results.append(res)
        print(json.dumps(res, indent=2), flush=True)

    RESULT_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nSaved full results to {RESULT_PATH}", flush=True)


if __name__ == "__main__":
    main()
