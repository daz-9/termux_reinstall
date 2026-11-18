#!/data/data/com.termux/files/usr/bin/sh

export BSPWM_SOCKET="${BSPWM_SOCKET:-${TMPDIR:-/data/data/com.termux/files/usr/tmp}/bspwm_0_0-socket}"
export XCURSOR_THEME="${XCURSOR_THEME:-TouchDot-Mocha}"
export XCURSOR_SIZE="${XCURSOR_SIZE:-32}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-${TMPDIR:-/data/data/com.termux/files/usr/tmp}}"
export GALLIUM_DRIVER="${GALLIUM_DRIVER:-virpipe}"

# Wait briefly for VirGL socket on cold X11 startup, then use GPU OpenGL RHI (-> ANGLE -> Vulkan)
if pgrep -x virgl_test_serv >/dev/null 2>&1; then
  i=0
  while [ "$i" -lt 20 ] && [ ! -S "$XDG_RUNTIME_DIR/.virgl_test" ]; do
    i=$((i + 1))
    sleep 0.05
  done
fi

if [ -S "$XDG_RUNTIME_DIR/.virgl_test" ]; then
  unset QT_QUICK_BACKEND
  export QSG_RHI_BACKEND="${QSG_RHI_BACKEND:-opengl}"
  # Mesa virpipe is not thread-safe across concurrent Qt Quick render threads
  export QSG_RENDER_LOOP="${QSG_RENDER_LOOP:-basic}"
else
  export QT_QUICK_BACKEND="${QT_QUICK_BACKEND:-software}"
fi

[ -f "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/qs-watch.pid" ] && kill "$(cat "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/qs-watch.pid")" 2>/dev/null || true
rm -f "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/qs-watch.pid"

pkill -x quickshell 2>/dev/null || true
while pgrep -u "$(id -u)" -x quickshell >/dev/null 2>&1; do
  sleep 0.2
done
pkill -f "qs-native (media-stream|submenu-watch|sys-diag|wl-workspaces)" 2>/dev/null || true

LOG="${TMPDIR:-/data/data/com.termux/files/usr/tmp}/quickshell.log"
quickshell >> "$LOG" 2>&1 &
bspc config left_padding 128 >/dev/null 2>&1 || true
