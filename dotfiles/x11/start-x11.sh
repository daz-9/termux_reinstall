#!/data/data/com.termux/files/usr/bin/bash
set -u

PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
export PATH="$HOME/.local/bin:$PATH"
export DISPLAY=":0"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-$PREFIX/tmp}"
export TMPDIR="${TMPDIR:-$XDG_RUNTIME_DIR}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
export BSPWM_SOCKET="$XDG_RUNTIME_DIR/bspwm_0_0-socket"
export XCURSOR_THEME="TouchDot-Mocha"
export XCURSOR_SIZE="32"

VIRGL_PID=""
kill_procs() {
  for proc in "$@"; do
    pkill -x "$proc" 2>/dev/null || true
  done
}

cleanup() {
  kill_procs quickshell qs-native polybar fastcompmgr sxhkd bspwm termux-x11
  [ -f "$TMPDIR/hide-cursor.pid" ] && kill "$(cat "$TMPDIR/hide-cursor.pid")" 2>/dev/null || true
  [ -f "$TMPDIR/qs-watch.pid" ] && kill "$(cat "$TMPDIR/qs-watch.pid")" 2>/dev/null || true
  [ -n "$VIRGL_PID" ] && kill "$VIRGL_PID" 2>/dev/null || true
  rm -f "$XDG_RUNTIME_DIR/.virgl_test" "$BSPWM_SOCKET" "$XDG_RUNTIME_DIR/.X11-unix/X0" "$TMPDIR/hide-cursor.pid" "$TMPDIR/qs-watch.pid"
}
trap cleanup EXIT INT TERM

# Clean up stale X11 / WM / VirGL processes from an earlier session
[ -f "$TMPDIR/qs-watch.pid" ] && kill "$(cat "$TMPDIR/qs-watch.pid")" 2>/dev/null || true
rm -f "$TMPDIR/qs-watch.pid"
kill_procs quickshell qs-native polybar fastcompmgr sxhkd bspwm termux-x11 virgl_test_serv
[ -f "$TMPDIR/hide-cursor.pid" ] && kill "$(cat "$TMPDIR/hide-cursor.pid")" 2>/dev/null || true
pkill -f '[v]irgl_test_server_android' 2>/dev/null || true
pkill -f "com.termux.x11" 2>/dev/null || true
rm -f "$XDG_RUNTIME_DIR/.virgl_test" "$BSPWM_SOCKET" "$XDG_RUNTIME_DIR/.X11-unix/X0"
if ! pgrep -x chrome >/dev/null 2>&1; then
  rm -f "$XDG_CONFIG_HOME/chromium/SingletonLock" "$XDG_CONFIG_HOME/chromium/SingletonSocket" "$XDG_CONFIG_HOME/chromium/SingletonCookie"
fi
sleep 0.5

# Hardware OpenGL ES -> Vulkan passthrough via ANGLE for Qt Quick / GL apps
if command -v virgl_test_server_android >/dev/null 2>&1; then
  virgl_test_server_android --multi-clients --angle-vulkan >/dev/null 2>&1 &
  VIRGL_PID=$!
  i=0
  while [ "$i" -lt 20 ] && [ ! -S "$XDG_RUNTIME_DIR/.virgl_test" ]; do
    i=$((i + 1))
    sleep 0.05
  done
fi

if command -v pulseaudio >/dev/null 2>&1; then
  pulseaudio --start --exit-idle-time=-1 2>/dev/null || true
fi

# Open the Termux:X11 Android activity
am start --user 0 -n com.termux.x11/com.termux.x11.MainActivity >/dev/null 2>&1 || true

# Launch X11 and start bspwm once :0 is ready
if command -v dbus-launch >/dev/null 2>&1; then
  termux-x11 :0 -xstartup "dbus-launch --exit-with-session bspwm"
else
  termux-x11 :0 -xstartup "bspwm"
fi
