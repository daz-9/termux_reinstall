# Desktop Performance Benchmarks

Isolated profiling scripts for comparing X11 (`bspwm` + `fastcompmgr`) and Wayland (`sway`, `labwc`, `swayfx`) desktop stacks across CPU (`software` / `pixman`) and GPU (`VirGL ANGLE` / `PanVK + Zink`) configurations.

> **Note:** Run these from a Termux shell when no desktop session is active — each script launches an isolated `termux-x11 :9` instance and cleans up desktop processes between runs.

## Scripts

1. **`profile_desktops.py`**
   - Measures cold startup latency, steady-state idle CPU% (`/proc/<pid>/stat`), peak RSS (`/proc/<pid>/status`), and active 2D scroll resource usage across all 6 X11 & Wayland configs.
   - Output JSON: `$TMPDIR/desktop_profile_results.json`

2. **`profile_fps_2d.py`**
   - Measures 3D OpenGL FPS (`glxgears` / `es2gears_x11` / `es2gears_wayland`) across CPU `llvmpipe`, VirGL ANGLE (`virpipe`), and PanVK/Zink (`zink`), plus Wayland `foot` 2D ANSI scroll throughput (`lines/s`).
   - Output JSON: `$TMPDIR/desktop_fps_results.json`

3. **`profile_quickshell_panel.py`**
   - Injects a Qt 6 `FrameAnimation` harness into a temporary copy of `shell.qml` / `wayland.qml` in `$TMPDIR` (never modifies `~/.config/quickshell`), toggles the `WidgetHub` side panel 8 times, and reports animation FPS, avg / p95 / max frame times (ms), CPU%, and RSS across all X11 & Wayland backend combinations.
   - Output JSON: `$TMPDIR/quickshell_panel_fps.json`

4. **`profile_realistic.py`**
   - Side-by-side realistic desktop workload comparing **Old Sway (all software)** vs **Current SwayFX (Zink/PanVK damage-clipped)** with `foot + nvim` (1,653-line C file) and **Firefox** tiled side-by-side at `2560×1600`, measuring loaded steady-state CPU/RSS, 30 Hz `nvim` scrolling, and Quickshell `WidgetHub` panel animation FPS with all apps open.
   - Output JSON: `$TMPDIR/realistic_profile_results.json`

## Usage

```bash
python3 ~/termux_reinstall/benchmarks/profile_desktops.py
python3 ~/termux_reinstall/benchmarks/profile_fps_2d.py
python3 ~/termux_reinstall/benchmarks/profile_quickshell_panel.py
python3 ~/termux_reinstall/benchmarks/profile_realistic.py
```
