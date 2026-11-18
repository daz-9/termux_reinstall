#!/data/data/com.termux/files/usr/bin/sh
vol=$(pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null | grep -oE '[0-9]+%' | head -n1 | tr -d '%')
mute=$(pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null)
case "$vol" in
  ''|*[!0-9]*) vol=50 ;;
esac
case "$mute" in
  *yes*) muted=true ;;
  *) muted=false ;;
esac
printf '{"pct":%s,"muted":%s}\n' "$vol" "$muted"
