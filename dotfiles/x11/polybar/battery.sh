#!/data/data/com.termux/files/usr/bin/sh
if ! command -v termux-battery-status >/dev/null 2>&1; then
  printf "BAT --\n"
  exit 0
fi

out="$(timeout 4 termux-battery-status 2>/dev/null)" || true
if [ -z "$out" ]; then
  printf "BAT --\n"
  exit 0
fi

eval "$(printf '%s\n' "$out" | awk -F: '
  /"percentage"/ { gsub(/[^0-9]/, "", $2); pct=$2 }
  /"status"/     { gsub(/[^A-Za-z]/, "", $2); st=$2 }
  END { printf "pct=%s\nst=%s\n", pct, st }
')"

if [ -z "$pct" ]; then
  printf "BAT --\n"
  exit 0
fi

if [ "$st" = "CHARGING" ]; then
  icon=""
  color="#a6e3a1"
elif [ "$pct" -ge 85 ]; then
  icon=""
  color="#a6e3a1"
elif [ "$pct" -ge 60 ]; then
  icon=""
  color="#94e2d5"
elif [ "$pct" -ge 35 ]; then
  icon=""
  color="#cdd6f4"
elif [ "$pct" -ge 15 ]; then
  icon=""
  color="#fab387"
else
  icon=""
  color="#f38ba8"
fi

printf "%%{F%s}%s %s%%%%{F-}\n" "$color" "$icon" "$pct"
