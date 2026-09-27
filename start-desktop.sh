#!/bin/bash
set -e
termux-x11 :1 &
X11_PID=$!
trap "kill $X11_PID 2>/dev/null" EXIT
env DISPLAY=:1 dbus-launch --exit-with-session i3