#! /bin/bash

termux-x11 :1 &
env DISPLAY=:1 dbus-launch --exit-with-session i3

