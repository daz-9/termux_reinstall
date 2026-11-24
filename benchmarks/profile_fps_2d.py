#!/data/data/com.termux/files/usr/bin/env python3
"""
Targeted FPS & 2D throughput benchmark across X11 and Wayland (CPU vs GPU).
Uses pty/stdbuf so es2gears/glxgears flushes FPS lines immediately, and tracks
actual child PIDs (including termux-x11's PID and es2gears_waylan).
"""
import json
import os
import pty
import re
import select
import subprocess
import time
from pathlib import Path

PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
HOME = os.environ.get("HOME", "/data/data/com.termux/files/home")
TMPDIR = os.environ.get("TMPDIR", f"{PREFIX}/tmp")
PANVK_ICD = f"{PREFIX}/share/vulkan/icd.d/panfrost_icd.aarch64.json"
CLK_TCK = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
DISPLAY_NUM = ":9"


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
        "es2gears_x11", "es2gears_waylan", "glxgears", "foot", "xfce4-terminal",
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
    ]:
        env.pop(k, None)
    return env


def run_gears_pty(cmd, env, watch_pids, duration_s=6.5):
    """Run gears in a PTY so libc line-buffers stdout and prints FPS after 5s."""
    master, slave = pty.openpty()
    p = subprocess.Popen(cmd, env=env, stdin=slave, stdout=slave, stderr=slave, close_fds=True)
    os.close(slave)

    all_pids = list(watch_pids) + [p.pid]
    time.sleep(0.6)
    t0 = time.monotonic()
    s0 = {pid: read_proc(pid) for pid in all_pids}
    chunks = []
    peak_rss = {}
    while time.monotonic() - t0 < duration_s:
        r, _, _ = select.select([master], [], [], 0.25)
        if r:
            try:
                data = os.read(master, 4096)
                if data:
                    chunks.append(data.decode("utf-8", errors="ignore"))
            except OSError:
                break
        for pid in all_pids:
            m = read_proc(pid)
            if m:
                peak_rss[m[2]] = max(peak_rss.get(m[2], 0), m[1])
        if p.poll() is not None:
            break

    t1 = time.monotonic()
    s1 = {pid: read_proc(pid) for pid in all_pids}
    try:
        p.terminate()
        p.wait(timeout=1.5)
    except Exception:
        p.kill()
    # drain remaining bytes
    while True:
        r, _, _ = select.select([master], [], [], 0.1)
        if not r:
            break
        try:
            data = os.read(master, 4096)
            if not data:
                break
            chunks.append(data.decode("utf-8", errors="ignore"))
        except OSError:
            break
    os.close(master)

    txt = "".join(chunks)
    fps_vals = [float(m.group(1)) for m in re.finditer(r"=\s*([0-9]+\.[0-9]+)\s*FPS", txt)]
    dt = max(t1 - t0, 0.001)
    cpu = {}
    for pid in all_pids:
        if s0.get(pid) and s1.get(pid):
            dticks = max(0, s1[pid][0] - s0[pid][0])
            comm = s1[pid][2]
            cpu[comm] = round(cpu.get(comm, 0.0) + (dticks / CLK_TCK) / dt * 100.0, 1)
    rss_mb = {k: round(v / 1024.0, 1) for k, v in peak_rss.items()}
    return {
        "fps": round(sum(fps_vals) / len(fps_vals), 1) if fps_vals else None,
        "cpu_by_proc": cpu,
        "rss_mb_by_proc": rss_mb,
        "tail": " | ".join([l.strip() for l in txt.splitlines() if l.strip()][-3:]),
    }


def start_x11(env):
    p = subprocess.Popen(["termux-x11", DISPLAY_NUM], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        if os.path.exists(f"{TMPDIR}/.X11-unix/X9"):
            break
        time.sleep(0.1)
    return p


def bench_x11_gl():
    cleanup()
    env = base_env()
    p_x11 = start_x11(env)
    p_virgl = subprocess.Popen(
        ["virgl_test_server_android", "--multi-clients", "--angle-vulkan"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        if os.path.exists(f"{TMPDIR}/.virgl_test"):
            break
        time.sleep(0.1)

    res = {}
    # 1. CPU llvmpipe (glxgears)
    e = env.copy()
    e["GALLIUM_DRIVER"] = "llvmpipe"
    e["LIBGL_ALWAYS_SOFTWARE"] = "1"
    res["x11_glxgears_llvmpipe"] = run_gears_pty(["glxgears"], e, [p_x11.pid])

    # 2. VirGL ANGLE (glxgears)
    e = env.copy()
    e["GALLIUM_DRIVER"] = "virpipe"
    res["x11_glxgears_virgl"] = run_gears_pty(["glxgears"], e, [p_x11.pid, p_virgl.pid])

    # 3. PanVK/Zink (glxgears)
    e = env.copy()
    e["GALLIUM_DRIVER"] = "zink"
    e["VK_DRIVER_FILES"] = PANVK_ICD
    e["VK_ICD_FILENAMES"] = PANVK_ICD
    res["x11_glxgears_panvk_zink"] = run_gears_pty(["glxgears"], e, [p_x11.pid])

    # 4. PanVK/Zink (es2gears_x11)
    res["x11_es2gears_panvk_zink"] = run_gears_pty(["es2gears_x11"], e, [p_x11.pid])

    cleanup()
    return res


def bench_wayland_gl_and_2d(wm, renderer):
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
    if wm == "labwc":
        cmd = ["labwc", "-C", f"{HOME}/.config/labwc"]
    elif wm == "swayfx":
        cmd = [f"{HOME}/.local/bin/swayfx", "-c", f"{HOME}/.config/swayfx/config"]
    else:
        cmd = ["sway", "-c", f"{HOME}/.config/sway/config"]
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

    cenv = env.copy()
    cenv["WAYLAND_DISPLAY"] = wl_sock
    if wm in ("sway", "swayfx"):
        for _ in range(40):
            socks = sorted(Path(TMPDIR).glob("sway-ipc.*.sock"))
            if socks:
                subprocess.run(["swaymsg", "-s", str(socks[0]), "output", "X11-1", "resolution", "2560x1600"],
                               env=cenv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                break
            time.sleep(0.1)
    time.sleep(1.5)

    out = {"wm": wm, "renderer": renderer}
    # Measure foot 2D scroll throughput (how many lines rendered in 3.0s)
    t_log = Path(TMPDIR) / "foot_thru.txt"
    t_log.unlink(missing_ok=True)
    script = (
        f"python3 -c 'import sys,time; t0=time.monotonic(); i=0\n"
        f"while time.monotonic()-t0<3.0:\n"
        f" i+=1; sys.stdout.write(f\"\\x1b[38;5;{{(i%200)+16}}m[line {{i:06d}}] \"+\"#\"*80+\"\\x1b[0m\\n\")\n"
        f" if i%20==0: sys.stdout.flush()\n"
        f"open(\"{t_log}\",\"w\").write(str(i))'"
    )
    t0 = time.monotonic()
    s0 = {pid: read_proc(pid) for pid in [p_x11.pid, p_wm.pid]}
    pf = subprocess.Popen(["foot", "-e", "sh", "-c", script], env=cenv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pf.wait(timeout=8)
    dt = max(time.monotonic() - t0, 0.001)
    s1 = {pid: read_proc(pid) for pid in [p_x11.pid, p_wm.pid]}
    lines = int(t_log.read_text().strip()) if t_log.exists() else 0
    out["foot_3s_lines"] = lines
    out["foot_lines_per_sec"] = round(lines / 3.0, 0)
    out["foot_wm_cpu_pct"] = round(((s1[p_wm.pid][0] - s0[p_wm.pid][0]) / CLK_TCK) / dt * 100.0, 1) if s0[p_wm.pid] and s1[p_wm.pid] else None
    out["foot_x11_cpu_pct"] = round(((s1[p_x11.pid][0] - s0[p_x11.pid][0]) / CLK_TCK) / dt * 100.0, 1) if s0[p_x11.pid] and s1[p_x11.pid] else None

    # Measure es2gears_wayland with PanVK/Zink
    zenv = cenv.copy()
    zenv.pop("LIBGL_ALWAYS_SOFTWARE", None)
    zenv["GALLIUM_DRIVER"] = "zink"
    zenv["VK_DRIVER_FILES"] = PANVK_ICD
    zenv["VK_ICD_FILENAMES"] = PANVK_ICD
    out["es2gears_panvk_zink"] = run_gears_pty(["es2gears_wayland"], zenv, [p_x11.pid, p_wm.pid])

    # Measure es2gears_wayland with CPU llvmpipe (only on pixman)
    if renderer == "pixman" and wm == "sway":
        lenv = cenv.copy()
        lenv["GALLIUM_DRIVER"] = "llvmpipe"
        lenv["LIBGL_ALWAYS_SOFTWARE"] = "1"
        out["es2gears_llvmpipe"] = run_gears_pty(["es2gears_wayland"], lenv, [p_x11.pid, p_wm.pid])

    cleanup()
    return out


def main():
    results = {
        "x11_gl": bench_x11_gl(),
        "wayland": [
            bench_wayland_gl_and_2d("sway", "pixman"),
            bench_wayland_gl_and_2d("sway", "gles2"),
            bench_wayland_gl_and_2d("labwc", "pixman"),
            bench_wayland_gl_and_2d("swayfx", "gles2"),
        ],
    }
    Path(TMPDIR, "desktop_fps_results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    main()
