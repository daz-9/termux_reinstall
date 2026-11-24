# GUI Design & Architecture Rules

All desktop GUI assets live under `dotfiles/` and `daemons/`, are deployed/compiled by `configure.py` (`configure_x11()`), and have their packages installed by `setup.py` (`install_x11()`). **Always update the source files under `dotfiles/`, `daemons/`, or `configure.py` first and run `python3 configure.py --x11`** rather than hand-editing files under `~/.config/`, `~/.local/`, or `$PREFIX/bin/`.

---

## 1. Palette (Catppuccin Mocha)

Use these exact tokens across Quickshell, Polybar, Rofi, `bspwm`, `sway`, `labwc`, `xfce4-terminal`, `foot`, and cursors:

| Token | Value | Usage |
| :--- | :--- | :--- |
| `base` | `#1e1e2e` | Opaque background (Polybar, Rofi, terminal, `touchdot` dark text) |
| `base-glass` | `rgba(30, 30, 46, 0.90)` / `#e61e1e2e` | Left dock container (`Theme.colBase`) |
| `popup-glass` | `rgba(30, 30, 46, 0.95)` / `#f21e1e2e` | Floating popups (`Theme.colPopupBase`) |
| `surface` | `#313244` | Pill/button resting fill, occupied workspace, borders, input bars |
| `surface1` | `#45475a` | Dividers, separators, inactive/occupied borders |
| `text` | `#cdd6f4` | Primary text and neutral icons |
| `subtext` | `#a6adc8` | Secondary labels, empty state, muted metadata |
| `blue` | `#89b4fa` | Primary accent: active workspace, `:active` press, focused window border, clock, launcher |
| `mauve` | `#cba6f7` | Monocle layout, RAM icon, window switcher, presel feedback |
| `teal` | `#94e2d5` | Terminal launcher, healthy CPU, Restart WM |
| `green` | `#a6e3a1` | Unmuted audio, charging/high battery |
| `peach` | `#fab387` | Medium load/warning (`50–79%` CPU, `15–34%` battery) |
| `red` | `#f38ba8` | Close, muted audio, urgent workspace, power/exit, critical (`>=80%` CPU, `<15%` battery) |

---

## 2. Typography & Iconography

- **Font family:** `JetBrainsMono Nerd Font` everywhere (`monospace` fallback only).
  - Terminal: `19pt`
  - Polybar: `14pt` (vertical offset `;3`)
  - Rofi: `14`
  - Dock pills (Quickshell): `25–34px` icons, `24px` workspace digits, `13–14px` sublabels; popups: `26px` icons, `20px` bold labels.
- **Icon consistency & centering:**
  - Prefer **Material Design Nerd Font glyphs (`\U000f0...`)** for uniform square bounds (especially volume controls: `\U000f0415`, `\U000f057e`, `\U000f075f`, `\U000f0374`). In QML files, store literal UTF-8 Nerd Font glyphs directly rather than Python `\U000...` escapes.

---

## 3. Geometry, Radii & Compositing

- **Radii scale:**
  - Windows (`swayfx`, `labwc`): `corner_radius 24` / `corner-radius = 24`, `2px` `#313244` border (matching the Quickshell left dock)
  - Dock container: `24px` (`2px` `#313244` border)
  - Popup container: `22px` (`2px` `#45475a` border)
  - Buttons / workspace pills / Rofi window: `16–18px`
  - Top Polybar: `height = 40pt`, `radius = 16`, `border-size = 8pt` transparent outer margin (`~73px` top strut)
  - `bspwm` / `sway` / `swayfx` / `labwc`: `window_gap = 12`, `border_width = 2`
- **Transparency & compositors:**
  - X11 (`bspwmrc`) uses `fastcompmgr` for lightweight Termux:X11 compositing.
  - Ensure a compositor is running before launching `quickshell` so translucent ARGB dock/popup surfaces render cleanly.
  - Wayland (`start-wayland.sh`) defaults to hardware-accelerated `swayfx` (`WLR_RENDERER=gles2`, `GALLIUM_DRIVER=zink`, PanVK ICD, `WLR_GLES2_NO_DMABUF=1`, `corner_radius 24`, blur/shadows disabled) and also supports `sway` and `labwc` over `--x11` (nested Termux:X11) or `--tgui` (Termux:GUI with `~/.local/lib/libtgui_fix.so` fixing ABGR format and `WL_OUTPUT_TRANSFORM_FLIPPED_180`). Prebuilt patched `wlroots`/`scenefx`/`swayfx` binaries and PanVK tooling live in [`daz-9/termux-swayfx-panvk`](https://github.com/daz-9/termux-swayfx-panvk) and install into `~/.local`.

---

## 4. Bar Responsibilities & Spatial Separation

- **Top bar (Polybar on X11; Quickshell topbar on Wayland) = read-only statusbar:**
  - Left: active window title (`xwindow` / toplevel title, truncated at 60 chars)
  - Right: `cpu`, `memory` (`%gb_used% (%percentage_used%%)`), `battery` (+ thermals/Wi-Fi on Wayland), `date`
  - **Do not** place workspace lists, launchers, or interactive click menus on the top bar.
- **Left dock (Quickshell) = touch control surface:**
  - Anchored `top left` at `x=0px, y=80px`, `width=128px`, reserving `128px` left padding (`bspwm` struts + `bspc config left_padding 128`, or layer-shell exclusive zone on Wayland).
  - Top-to-bottom grouping separated by `60×2px` `#45475a` dividers:
    1. **Launchers:** App drawer (`rofi -show drun`), Terminal (`xfce4-terminal` on X11 / `foot` on Wayland), Window switcher (`rofi -show window`)
    2. **Workspaces `1`–`6` & Layout:** Live `bspc subscribe report` / Sway IPC / `ext_workspace_manager_v1` state (`focused` blue pill, `occupied` surface pill + `8px` blue dot, `empty` transparent), followed by Monocle/Tiled toggle (`M`/`T`) on X11
    3. **Widgets & Notifications toggle:** 1-finger tap opens the two-part floating Widget Hub (`WidgetsDrawerContent.qml`: upper part with Open-Meteo Weather + 3-day forecast, Focus/DND, Termux:API & Shizuku diagnostics, and Wi-Fi status/metrics/scanner; lower part with MediaSession and Calendar + merged Agenda; hold any card to expand, tap non-button area to collapse, swipe left to close, or swipe left/right on Calendar to step months). 2-finger tap or `380ms` hold opens the Android Notifications drawer (`NotificationsDrawerContent.qml`, powered by `notifications.py` via Termux:API + `rish`)
    4. **Spacer** (`Layout.fillHeight: true`)
    5. **Window actions:** Float toggle, Fullscreen toggle, Close window
    6. **Audio:** `+`, Mute/`%` badge, `-` (instant visual update on tap)
    7. **Session toggle:** Opens the bottom-left `session_menu` popup at `x=140px` (**Reload Bars**, **Restart WM**, **Exit**)

---

## 5. Tablet & Touch Interaction Rules (Termux:X11 Touchscreen Mode)

Termux:X11 is configured in **Touchscreen mode** (direct touch input rather than simulated trackpad/mouse). Design all UI surfaces and interactions around direct touch ergonomics:

- **Direct-touch gestures supported:**
  - **Drags:** Interactive controls and overlays may use direct drag/swipe gestures (e.g., dragging sliders/scrubbers, swiping to dismiss or pull open drawers/popups, drag-scrolling lists/agendas, dragging/resizing windows).
  - **Pinch gestures:** Pinch-in / pinch-out gestures are supported where natural (e.g., zooming content, scaling views, or triggering compact/overview transitions).
  - **One-hand-only multitouch:** Any multitouch gesture **must** be comfortably executable with **one hand** (e.g., thumb + index/middle finger within a natural single-hand span near the screen edge). Never design gestures that require two hands, wide two-finger reaches across opposite edges, or awkward 4–5 finger chords.
- **No right-click or hover dependencies:** Every primary control must remain discoverable and triggerable with a single tap (or a simple one-handed drag/pinch enhancement). Never require right-click bindings, hover-to-reveal menus, or keyboard-only shortcuts for UI chrome.
- **No sticky `:hover` visuals:** Style active/pressed feedback only (`#89b4fa` background + `#1e1e2e` foreground); leave hover states unstyled so direct touch taps never leave buttons stuck highlighted.
- **Enlarged invisible hitboxes:** Keep visible pills `92×50–66px` inside `128px`-wide edge-to-edge transparent touch targets (with split-gap vertical padding and zero dead pixels between controls) so thumb taps and edge drags register reliably.
- **Cursor coherence:** Keep the `TouchDot-Mocha` (`32px`) translucent frosted circle Xcursor (`~/.icons/TouchDot-Mocha`, `xsetroot -cursor_name left_ptr`) alongside `qs-native hide-cursor`, hiding the cursor immediately after tap release and after `0.6s` idle so direct touch feels native while external pointer/stylus use remains clear.

---

## 6. Termux / Android Runtime Constraints

- **SELinux `/proc` & `/sys` limits:** `/proc/stat`, `/proc/loadavg`, `/proc/uptime`, `/sys/class/power_supply`, `/sys/class/net`, and `/sys/class/thermal` return `Permission denied` from unprivileged Termux processes. Never enable Polybar's `internal/cpu`, `internal/battery`, or `internal/temperature`:
  - Read CPU via readable `/proc/<pid>/stat` (`qs-native cpu` / `qs-native sys-diag`).
  - Read battery via `timeout 4 termux-battery-status` (`battery.sh` / `qs-native sys-diag`).
  - Read RAM via `/proc/meminfo` (`internal/memory` / `qs-native sys-diag`).
  - Query Android services (MediaSession, Focus/DND, Calendar) via the hardened `~/.local/bin/rish` / persistent `RishPipe` in `qs-native media-stream` (keeping `rish-shizuku.dex` chmod `0400` for Android 14+).
- **Hotkeys (`sxhkd 0.6.3`):** Never combine `{alt,super}` with a second `{...}` brace group when the command also expands `{...}`—keep separate `alt + ...` and `super + ...` stanzas.
- **Safe X11 verification:** Test GUI changes headlessly on `DISPLAY=:9` (`termux-x11 :9` without `am start`) and kill all `:9` processes/sockets afterward so the foreground Android screen is never hijacked.
