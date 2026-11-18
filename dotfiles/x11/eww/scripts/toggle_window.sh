#!/data/data/com.termux/files/usr/bin/sh
mode="toggle"
if [ "$1" = "close" ] || [ "$1" = "open" ]; then
  mode="$1"
  shift
fi
win="$1"
var="$2"

close_win() {
  eww close "$win" >/dev/null 2>&1 || true
  eww update "$var=false" >/dev/null 2>&1 || true
}

open_win() {
  eww update "$var=true" >/dev/null 2>&1 || true
  eww open "$win" >/dev/null 2>&1 || true
  watch_pid="${TMPDIR:-/data/data/com.termux/files/usr/tmp}/eww-watch.pid"
  if [ ! -f "$watch_pid" ] || ! kill -0 "$(cat "$watch_pid" 2>/dev/null)" 2>/dev/null; then
    if [ -x "${XDG_CONFIG_HOME:-$HOME/.config}/eww/scripts/submenu_watch.py" ]; then
      "${XDG_CONFIG_HOME:-$HOME/.config}/eww/scripts/submenu_watch.py" >/dev/null 2>&1 &
    fi
  fi
}

if [ "$mode" = "close" ]; then
  close_win
elif [ "$mode" = "open" ]; then
  open_win
elif eww active-windows 2>/dev/null | grep -q "$win"; then
  close_win
else
  open_win
fi
