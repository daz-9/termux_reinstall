#!/data/data/com.termux/files/usr/bin/sh

export BSPWM_SOCKET="${BSPWM_SOCKET:-${TMPDIR:-/data/data/com.termux/files/usr/tmp}/bspwm_0_0-socket}"
export XCURSOR_THEME="${XCURSOR_THEME:-TouchDot-Mocha}"
export XCURSOR_SIZE="${XCURSOR_SIZE:-32}"

pkill -x polybar 2>/dev/null || true
while pgrep -u "$(id -u)" -x polybar >/dev/null 2>&1; do
  sleep 0.2
done

MONITOR="$(polybar -m 2>/dev/null | head -n1 | cut -d: -f1)"
export MONITOR="${MONITOR:-builtin}"

LOG="${TMPDIR:-/data/data/com.termux/files/usr/tmp}/polybar.log"
polybar main >> "$LOG" 2>&1 &
