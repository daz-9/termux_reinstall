#!/data/data/com.termux/files/usr/bin/sh

export BSPWM_SOCKET="${BSPWM_SOCKET:-${TMPDIR:-/data/data/com.termux/files/usr/tmp}/bspwm_0_0-socket}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-${TMPDIR:-/data/data/com.termux/files/usr/tmp}}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"
export GDK_BACKEND=x11
export XCURSOR_THEME="${XCURSOR_THEME:-TouchDot-Mocha}"
export XCURSOR_SIZE="${XCURSOR_SIZE:-32}"

eww kill >/dev/null 2>&1 || true
[ -f "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/eww-watch.pid" ] && kill "$(cat "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/eww-watch.pid")" 2>/dev/null || true
rm -f "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/eww-watch.pid"
pkill -x eww 2>/dev/null || true
while pgrep -u "$(id -u)" -x eww >/dev/null 2>&1; do
  sleep 0.15
done

LOG="${TMPDIR:-/data/data/com.termux/files/usr/tmp}/eww.log"
# Give picom a moment on cold X11 boot so GTK3 sees compositor RGBA visual
if pgrep -x picom >/dev/null 2>&1; then
  sleep 0.2
fi
eww daemon >> "$LOG" 2>&1 &

i=0
while [ "$i" -lt 25 ]; do
  if eww ping >/dev/null 2>&1; then
    break
  fi
  i=$((i + 1))
  sleep 0.1
done

eww open dock >> "$LOG" 2>&1 || true
bspc config left_padding 128 >/dev/null 2>&1 || true
