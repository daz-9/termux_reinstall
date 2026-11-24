#!/data/data/com.termux/files/usr/bin/sh

export BSPWM_SOCKET="${BSPWM_SOCKET:-${TMPDIR:-/data/data/com.termux/files/usr/tmp}/bspwm_0_0-socket}"
export XCURSOR_THEME="${XCURSOR_THEME:-TouchDot-Mocha}"
export XCURSOR_SIZE="${XCURSOR_SIZE:-32}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-${TMPDIR:-/data/data/com.termux/files/usr/tmp}}"

# Software Qt Quick backend on X11 avoids VirGL socket stalls (~56 FPS vs ~37 FPS
# on the WidgetHub panel) and cuts Quickshell RSS in half (~67 MB vs ~148 MB).
unset QSG_RHI_BACKEND QSG_RENDER_LOOP GALLIUM_DRIVER
export QT_QUICK_BACKEND="${QT_QUICK_BACKEND:-software}"

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
