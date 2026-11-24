#!/data/data/com.termux/files/usr/bin/env python3
"""
Realistic desktop performance profile:
  Current SwayFX (Zink/PanVK GLES2 + damage-clipped glReadPixels, corner_radius 24)
  vs
  Old Sway (all software rendering: WLR_RENDERER=pixman, no Zink/GPU)

Both run at 2560x1600 on isolated termux-x11 :9 with:
  - Quickshell (wayland.qml, software backend)
  - foot + nvim (1,653-line C source file)
  - Firefox (isolated temp profile, tiled side-by-side with foot+nvim)

Measures:
  1. Loaded idle CPU% & RSS (all apps open & visible)
  2. Active nvim scrolling (30 Hz <C-d>/<C-u>) while Firefox is open side-by-side
  3. Quickshell WidgetHub side panel open/close FPS & frame times WITH foot+nvim+Firefox behind it
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
NVIM_FILE = f"{HOME}/termux_reinstall/daemons/native/qs_native.c"
BENCH_DIR = Path(TMPDIR) / "realistic_bench"

INJECT_QML = """
    property int _benchToggleCount: 0
    property double _benchLastToggleMs: 0
    property bool _benchInAnim: false
    property var _benchAnimFrameMs: []
    property bool _benchTriggered: false

    FrameAnimation {
        id: _benchFrameAnim
        running: root._benchTriggered
        onTriggered: {
            const ms = frameTime * 1000.0;
            if (ms > 0 && ms < 2000) {
                const now = Date.now();
                if (root._benchInAnim && (now - root._benchLastToggleMs) <= 300) {
                    root._benchAnimFrameMs.push(ms);
                }
            }
        }
    }

    Process {
        id: _benchTriggerPoll
        command: ["sh", "-c", "test -f '" + Quickshell.env("BENCH_TRIGGER_FILE") + "' && echo GO || true"]
        stdout: SplitParser {
            onRead: line => {
                if (line.trim() === "GO" && !root._benchTriggered) {
                    root._benchTriggered = true;
                    _benchTimer.start();
                }
            }
        }
    }

    Timer {
        interval: 250
        repeat: true
        running: !root._benchTriggered
        onTriggered: {
            if (!_benchTriggerPoll.running) _benchTriggerPoll.running = true;
        }
    }

    Timer {
        id: _benchTimer
        interval: 600
        repeat: true
        running: false
        onTriggered: {
            root._benchToggleCount += 1;
            if (root._benchToggleCount >= 1 && root._benchToggleCount <= 8) {
                root._benchLastToggleMs = Date.now();
                root._benchInAnim = true;
                root.toggleWidgets();
            } else if (root._benchToggleCount === 9) {
                running = false;
                console.log("BENCH_RESULT=" + JSON.stringify({
                    anim_frames: root._benchAnimFrameMs.length,
                    anim_ms: root._benchAnimFrameMs,
                    toggles: 8
                }));
            }
        }
    }
"""

TEST_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Realistic Desktop Benchmark</title>
<style>
body { background: #1e1e2e; color: #cdd6f4; font-family: sans-serif; margin: 24px; }
.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.card { background: #313244; border-radius: 16px; padding: 18px; border: 1px solid #45475a; }
.bar { height: 10px; border-radius: 5px; background: linear-gradient(90deg, #cba6f7, #89b4fa); animation: pulse 2s infinite alternate; }
@keyframes pulse { from { opacity: 0.45; transform: scaleX(0.7); } to { opacity: 1.0; transform: scaleX(1.0); } }
</style></head>
<body>
<h2>Firefox Realistic Tab — Catppuccin Mocha</h2>
<div class="grid">
""" + "".join(
    f'<div class="card"><h3>Panel {i}</h3><div class="bar"></div><p>Realistic web content layout with CSS gradients, rounded cards, and subtle animation.</p></div>'
    for i in range(1, 13)
) + """
</div></body></html>
"""


def prepare_assets():
    if BENCH_DIR.exists():
        shutil.rmtree(BENCH_DIR)
    BENCH_DIR.mkdir(parents=True)
    os.symlink(f"{HOME}/.config/quickshell/components", BENCH_DIR / "components")
    src = Path(f"{HOME}/.config/quickshell/wayland.qml").read_text()
    idx = src.rfind("}")
    (BENCH_DIR / "wayland.qml").write_text(src[:idx] + INJECT_QML + "\n}\n")
    (BENCH_DIR / "test.html").write_text(TEST_HTML)


def list_tracked_procs():
    """Return dict[pid] = (ticks, rss_kb, bucket) for all desktop/app processes."""
    out = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        try:
            stat = Path(f"/proc/{pid}/stat").read_text()
            rp = stat.rfind(")")
            comm = stat[stat.find("(") + 1 : rp]
            cmdline = Path(f"/proc/{pid}/cmdline").read_text(errors="ignore").replace("\x00", " ")
            bucket = None
            if comm in ("sway", "swayfx", "swaybg", "quickshell", "qs-native", "foot", "nvim", "Xwayland"):
                bucket = comm
            elif "firefox" in comm.lower() or "gecko" in comm.lower() or "web content" in comm.lower() or "isolated web" in comm.lower() or "firefox" in cmdline.lower():
                if "profile_realistic" not in cmdline:
                    bucket = "firefox(all)"
            elif "termux.x11" in cmdline or comm == "termux-x11":
                bucket = "termux-x11"
            if not bucket:
                continue
            fields = stat[rp + 2 :].split()
            ticks = int(fields[11]) + int(fields[12])
            rss_kb = 0
            for line in Path(f"/proc/{pid}/status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    rss_kb = int(line.split()[1])
                    break
            out[pid] = (ticks, rss_kb, bucket)
        except OSError:
            pass
    return out


def sample_window(duration_s, interval_s=0.4):
    t0 = time.monotonic()
    s0 = list_tracked_procs()
    peak_total_rss = 0
    peak_by_bucket = {}

    def record_rss(snap):
        nonlocal peak_total_rss
        tot = sum(v[1] for v in snap.values())
        if tot > peak_total_rss:
            peak_total_rss = tot
        agg = {}
        for _, rss, b in snap.values():
            agg[b] = agg.get(b, 0) + rss
        for b, r in agg.items():
            if r > peak_by_bucket.get(b, 0):
                peak_by_bucket[b] = r

    record_rss(s0)
    while time.monotonic() - t0 < duration_s:
        time.sleep(min(interval_s, max(0.05, duration_s - (time.monotonic() - t0))))
        record_rss(list_tracked_procs())

    t1 = time.monotonic()
    s1 = list_tracked_procs()
    dt = max(t1 - t0, 0.001)

    cpu_by_bucket = {}
    total_cpu = 0.0
    for pid, (ticks1, _, b) in s1.items():
        dticks = max(0, ticks1 - s0[pid][0]) if pid in s0 else ticks1
        pct = (dticks / CLK_TCK) / dt * 100.0
        cpu_by_bucket[b] = cpu_by_bucket.get(b, 0.0) + pct
        total_cpu += pct

    return {
        "duration_s": round(dt, 2),
        "total_cpu_pct": round(total_cpu, 1),
        "total_rss_mb": round(peak_total_rss / 1024.0, 1),
        "cpu_by_proc": {k: round(v, 1) for k, v in sorted(cpu_by_bucket.items(), key=lambda x: -x[1])},
        "rss_mb_by_proc": {k: round(v / 1024.0, 1) for k, v in sorted(peak_by_bucket.items(), key=lambda x: -x[1])},
    }


def cleanup():
    for comm in [
        "firefox", "foot", "nvim", "quickshell", "qs-native",
        "swaybg", "swayfx", "sway", "Xwayland", "termux-x11",
    ]:
        subprocess.run(["pkill", "-x", comm], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "firefox.*realistic_bench"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "com.termux.x11 :9"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    time.sleep(0.7)
    for pat in [f"{TMPDIR}/.X11-unix/X9", f"{TMPDIR}/.X9-lock", f"{TMPDIR}/nvim_bench.sock"]:
        try:
            os.unlink(pat)
        except OSError:
            pass
    for f in list(Path(TMPDIR).glob("wayland-*")) + list(Path(TMPDIR).glob("sway-ipc.*")):
        try:
            f.unlink()
        except OSError:
            pass
    time.sleep(0.3)


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


def run_profile(label, wm, use_gpu):
    print(f"\n>>> Profiling: {label}", flush=True)
    cleanup()

    env = os.environ.copy()
    env["PATH"] = f"{HOME}/.local/bin:{env.get('PATH', '')}"
    env["DISPLAY"] = DISPLAY_NUM
    env["TERMUX_X11_DISPLAY"] = DISPLAY_NUM
    env["XDG_RUNTIME_DIR"] = TMPDIR
    env["TMPDIR"] = TMPDIR
    env["XDG_CONFIG_HOME"] = f"{HOME}/.config"
    env["XDG_SESSION_TYPE"] = "wayland"
    env["WLR_BACKENDS"] = "x11"
    env["WLR_NO_HARDWARE_CURSORS"] = "1"
    for k in [
        "WAYLAND_DISPLAY", "SWAYSOCK", "GALLIUM_DRIVER", "LIBGL_ALWAYS_SOFTWARE",
        "MESA_LOADER_DRIVER_OVERRIDE", "WLR_RENDERER", "WLR_GLES2_NO_DMABUF",
        "LD_LIBRARY_PATH", "QT_QUICK_BACKEND", "QSG_RHI_BACKEND", "QSG_RENDER_LOOP",
        "VK_DRIVER_FILES", "VK_ICD_FILENAMES", "QT_QPA_PLATFORM", "MOZ_ENABLE_WAYLAND",
    ]:
        env.pop(k, None)

    if use_gpu:
        env["WLR_RENDERER"] = "gles2"
        env["GALLIUM_DRIVER"] = "zink"
        env["VK_DRIVER_FILES"] = PANVK_ICD
        env["VK_ICD_FILENAMES"] = PANVK_ICD
        env["WLR_GLES2_NO_DMABUF"] = "1"
    else:
        env["WLR_RENDERER"] = "pixman"
        env["LIBGL_ALWAYS_SOFTWARE"] = "1"
        env["GALLIUM_DRIVER"] = "llvmpipe"

    try:
        # 1. termux-x11 :9
        subprocess.Popen(["termux-x11", DISPLAY_NUM], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            if os.path.exists(f"{TMPDIR}/.X11-unix/X9"):
                break
            time.sleep(0.1)

        # 2. Launch compositor (using real user config minus auto-launch quickshell so we control the bench quickshell)
        src_cfg = f"{HOME}/.config/{wm}/config"
        tmp_cfg = BENCH_DIR / f"{wm}.conf"
        lines = [l for l in Path(src_cfg).read_text().splitlines() if "launch-wayland.sh" not in l]
        tmp_cfg.write_text("\n".join(lines) + "\n")
        wm_bin = f"{HOME}/.local/bin/swayfx" if wm == "swayfx" else "sway"
        subprocess.Popen([wm_bin, "-c", str(tmp_cfg)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        wl_sock = None
        for _ in range(80):
            for p in sorted(Path(TMPDIR).glob("wayland-*")):
                if not p.name.endswith(".lock"):
                    wl_sock = p.name
                    break
            if wl_sock:
                break
            time.sleep(0.1)

        swaysock = None
        for _ in range(50):
            socks = sorted(Path(TMPDIR).glob("sway-ipc.*.sock"))
            if socks:
                swaysock = str(socks[0])
                break
            time.sleep(0.1)

        cenv = env.copy()
        cenv["WAYLAND_DISPLAY"] = wl_sock
        if swaysock:
            cenv["SWAYSOCK"] = swaysock
            subprocess.run(["swaymsg", "-s", swaysock, "output", "X11-1", "resolution", "2560x1600"],
                           env=cenv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 3. Launch Quickshell (software backend, with panel trigger)
        trigger_file = BENCH_DIR / f"trigger_{wm}"
        trigger_file.unlink(missing_ok=True)
        qs_log = BENCH_DIR / f"qs_{wm}.log"
        qs_env = cenv.copy()
        qs_env["QT_QPA_PLATFORM"] = "wayland"
        qs_env["QT_QUICK_BACKEND"] = "software"
        qs_env["BENCH_TRIGGER_FILE"] = str(trigger_file)
        with open(qs_log, "w") as lf:
            subprocess.Popen(["quickshell", "-p", str(BENCH_DIR / "wayland.qml")],
                             env=qs_env, stdout=lf, stderr=subprocess.STDOUT)

        # 4. Launch foot + nvim (real 1,653-line C file, listening on socket for scripted scrolling)
        nvim_sock = f"{TMPDIR}/nvim_bench.sock"
        subprocess.Popen(
            ["foot", "-e", "nvim", "--listen", nvim_sock, NVIM_FILE],
            env=cenv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        # 5. Launch Firefox (temp profile, Wayland native, tiled next to foot+nvim)
        ff_prof = BENCH_DIR / f"ff_profile_{wm}"
        if ff_prof.exists():
            shutil.rmtree(ff_prof)
        ff_prof.mkdir(parents=True)
        # Copy user's performance prefs if desired, plus disable first-run/telemetry noise
        user_js = [
            'user_pref("browser.startup.homepage_override.mstone", "ignore");',
            'user_pref("datareporting.policy.firstRunURL", "");',
            'user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);',
            'user_pref("browser.shell.checkDefaultBrowser", false);',
        ]
        if not use_gpu:
            user_js += [
                'user_pref("gfx.webrender.software", true);',
                'user_pref("gfx.webrender.all", false);',
                'user_pref("layers.acceleration.disabled", true);',
            ]
        (ff_prof / "user.js").write_text("\n".join(user_js) + "\n")

        ff_env = cenv.copy()
        ff_env["MOZ_ENABLE_WAYLAND"] = "1"
        if not use_gpu:
            ff_env["MOZ_WEBRENDER"] = "0"
        subprocess.Popen(
            ["firefox", "--no-remote", "--profile", str(ff_prof), f"file://{BENCH_DIR / 'test.html'}"],
            env=ff_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        # Wait for nvim socket and Firefox to settle & render
        for _ in range(80):
            if os.path.exists(nvim_sock):
                break
            time.sleep(0.1)
        time.sleep(5.5)  # let Firefox fully load & render the HTML page

        # Verify visible windows in sway tree
        tree_count = 0
        if swaysock:
            tr = subprocess.run(["swaymsg", "-s", swaysock, "-t", "get_tree"],
                                env=cenv, capture_output=True, text=True)
            tree_count = tr.stdout.count('"app_id":')

        # Phase 1: Loaded steady-state (foot+nvim + Firefox + Quickshell all open & animating CSS bar)
        loaded_idle = sample_window(5.0, interval_s=0.4)

        # Phase 2: Realistic active nvim scrolling (30 Hz <C-d> / <C-u>) while Firefox is side-by-side
        scroll_stop = False
        t_scroll = time.monotonic()
        # Run a background Python helper to send 30Hz scroll keys to nvim for 5.0s
        scroller = subprocess.Popen(
            ["python3", "-c", (
                f"import subprocess, time; t0=time.monotonic(); i=0\n"
                f"while time.monotonic()-t0 < 5.0:\n"
                f"  key = '<C-d>' if (i // 35) % 2 == 0 else '<C-u>'\n"
                f"  subprocess.run(['nvim', '--server', '{nvim_sock}', '--remote-send', key], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
                f"  i += 1; time.sleep(0.033)\n"
            )],
            env=cenv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        active_nvim = sample_window(4.5, interval_s=0.4)
        scroller.wait(timeout=3)

        # Phase 3: Quickshell WidgetHub side panel toggle animation WITH foot+nvim + Firefox open behind it
        trigger_file.write_text("GO\n")
        panel_metrics = sample_window(5.8, interval_s=0.4)
        txt = qs_log.read_text(errors="ignore")
        m = re.search(r"BENCH_RESULT=(\{.*\})", txt)
        if m:
            d = json.loads(m.group(1))
            panel_anim = summarize_frames(d["anim_ms"])
        else:
            panel_anim = {"error": "no BENCH_RESULT", "log_tail": txt[-300:]}

        return {
            "label": label,
            "wm": wm,
            "gpu": use_gpu,
            "visible_app_nodes": tree_count,
            "loaded_steady": loaded_idle,
            "active_nvim_scroll": active_nvim,
            "panel_with_apps_fps": panel_anim,
            "panel_with_apps_sys": panel_metrics,
        }
    finally:
        cleanup()


def main():
    prepare_assets()
    results = [
        run_profile("Old Sway — All Software (pixman + FF SW WebRender)", "sway", False),
        run_profile("Current SwayFX — GPU Zink/PanVK (damage-clipped, r=24)", "swayfx", True),
    ]
    out_path = Path(TMPDIR) / "realistic_profile_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2), flush=True)
    print(f"\nSaved to {out_path}", flush=True)


if __name__ == "__main__":
    main()
