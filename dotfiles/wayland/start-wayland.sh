#!/data/data/com.termux/files/usr/bin/bash
set -u

PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
export PATH="$HOME/.local/bin:$PATH"
export DISPLAY="${DISPLAY:-:0}"
export TERMUX_X11_DISPLAY="$DISPLAY"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-$PREFIX/tmp}"
export TMPDIR="${TMPDIR:-$XDG_RUNTIME_DIR}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
export XDG_SESSION_TYPE="wayland"
export XCURSOR_THEME="TouchDot-Mocha"
export XCURSOR_SIZE="32"
export WLR_NO_HARDWARE_CURSORS="1"

BACKEND="x11"
WM="sway"
USER_RENDERER="${WLR_RENDERER:-}"
for arg in "$@"; do
  case "$arg" in
    --tgui) BACKEND="tgui" ;;
    --x11)  BACKEND="x11" ;;
    --renderer=*) USER_RENDERER="${arg#--renderer=}" ;;
    sway|labwc) WM="$arg" ;;
    -h|--help)
      echo "Usage: $(basename "$0") [sway|labwc] [--x11|--tgui] [--renderer=pixman|gles2|vulkan]"
      exit 0
      ;;
  esac
done

export WLR_BACKENDS="$BACKEND"
if [ -n "$USER_RENDERER" ]; then
  export WLR_RENDERER="$USER_RENDERER"
else
  # pixman works across both termux-x11 and tgui (tgui R/B + Y-flip fixed via libtgui_fix.so)
  export WLR_RENDERER="pixman"
fi

kill_procs() {
  for proc in "$@"; do
    pkill -x "$proc" 2>/dev/null || true
  done
}

cleanup() {
  kill_procs quickshell qs-native swaybg sway labwc Xwayland polybar sxhkd bspwm termux-x11
  rm -f "$XDG_RUNTIME_DIR"/.X11-unix/X* "$XDG_RUNTIME_DIR"/.X*-lock "$XDG_RUNTIME_DIR"/wayland-* "$XDG_RUNTIME_DIR"/sway-ipc.*
}
trap cleanup EXIT INT TERM

# Clean stale sessions before launching
kill_procs quickshell qs-native swaybg sway labwc Xwayland polybar fastcompmgr sxhkd bspwm termux-x11
pkill -f "com.termux.x11" 2>/dev/null || true
rm -f "$XDG_RUNTIME_DIR"/.X11-unix/X* "$XDG_RUNTIME_DIR"/.X*-lock "$XDG_RUNTIME_DIR"/wayland-* "$XDG_RUNTIME_DIR"/sway-ipc.*
if ! pgrep -x chrome >/dev/null 2>&1; then
  rm -f "$XDG_CONFIG_HOME/chromium/SingletonLock" "$XDG_CONFIG_HOME/chromium/SingletonSocket" "$XDG_CONFIG_HOME/chromium/SingletonCookie"
fi
sleep 0.5

if ! command -v "$WM" >/dev/null 2>&1; then
  if [ "$WM" = "sway" ] && command -v labwc >/dev/null 2>&1; then
    WM="labwc"
  elif [ "$WM" = "labwc" ] && command -v sway >/dev/null 2>&1; then
    WM="sway"
  else
    echo "[-] Neither sway nor labwc is installed"
    exit 1
  fi
fi

if command -v pulseaudio >/dev/null 2>&1; then
  pulseaudio --start --exit-idle-time=-1 2>/dev/null || true
fi

if [ "$WM" = "labwc" ]; then
  THEME_DIR="$HOME/.themes/Catppuccin-Mocha/openbox-3"
  mkdir -p "$THEME_DIR"
  cp -f "$XDG_CONFIG_HOME/labwc/themerc" "$THEME_DIR/themerc" 2>/dev/null || true
  WM_CMD="$WM -C $XDG_CONFIG_HOME/labwc"
else
  WM_CMD="$WM -c $XDG_CONFIG_HOME/sway/config"
fi

if [ "$BACKEND" = "tgui" ]; then
  TGUI_SHIM="$HOME/.local/lib/libtgui_fix.so"
  am start --user 0 -n com.termux.gui/.GUIActivity >/dev/null 2>&1 || true
  if [ -f "$TGUI_SHIM" ]; then
    if command -v dbus-launch >/dev/null 2>&1; then
      # shellcheck disable=SC2086
      exec dbus-launch --exit-with-session env LD_PRELOAD="$TGUI_SHIM" $WM_CMD
    else
      # shellcheck disable=SC2086
      exec env LD_PRELOAD="$TGUI_SHIM" $WM_CMD
    fi
  else
    if command -v dbus-launch >/dev/null 2>&1; then
      # shellcheck disable=SC2086
      exec dbus-launch --exit-with-session $WM_CMD
    else
      # shellcheck disable=SC2086
      exec $WM_CMD
    fi
  fi
fi

# Nested Wayland on Termux:X11
am start --user 0 -n com.termux.x11/com.termux.x11.MainActivity >/dev/null 2>&1 || true
if command -v dbus-launch >/dev/null 2>&1; then
  termux-x11 :0 -xstartup "dbus-launch --exit-with-session $WM_CMD"
else
  termux-x11 :0 -xstartup "$WM_CMD"
fi
