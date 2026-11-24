#!/data/data/com.termux/files/usr/bin/sh

export QT_QPA_PLATFORM=wayland
export QT_QUICK_BACKEND=software
export XCURSOR_THEME="${XCURSOR_THEME:-TouchDot-Mocha}"
export XCURSOR_SIZE="${XCURSOR_SIZE:-32}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-${TMPDIR:-/data/data/com.termux/files/usr/tmp}}"

# Quickshell renders in software; don't make it load Zink/PanVK (inherited from the
# swayfx GPU environment), which only slows down its startup.
unset GALLIUM_DRIVER VK_DRIVER_FILES VK_ICD_FILENAMES WLR_GLES2_NO_DMABUF LD_LIBRARY_PATH \
  QSG_RHI_BACKEND QSG_RENDER_LOOP

# Match nested wlroots X11-1 window to the full outer Termux:X11 display size
# (runs in the background so it never delays Quickshell startup)
if [ "${WLR_BACKENDS:-x11}" = "x11" ]; then
  python3 - <<'PY' >/dev/null 2>&1 &
import os, subprocess
from ctypes import CDLL, POINTER, Structure, byref, c_int, c_long, c_uint, c_ulong, c_void_p

class XWA(Structure):
    _fields_ = [
        ("x", c_int), ("y", c_int), ("width", c_int), ("height", c_int),
        ("border_width", c_int), ("depth", c_int), ("visual", c_void_p),
        ("root", c_ulong), ("c_class", c_int), ("bit_gravity", c_int),
        ("win_gravity", c_int), ("backing_store", c_int),
        ("backing_planes", c_long), ("backing_pixel", c_long),
        ("save_under", c_int), ("colormap", c_ulong), ("map_installed", c_int),
        ("map_state", c_int), ("all_event_masks", c_long), ("your_event_mask", c_long),
        ("do_not_propagate_mask", c_long), ("override_redirect", c_int), ("screen", c_void_p),
    ]

disp = os.environ.get("TERMUX_X11_DISPLAY") or os.environ.get("DISPLAY") or ":0"
x11 = CDLL("libX11.so.6")
x11.XOpenDisplay.restype = c_void_p
dpy = x11.XOpenDisplay(disp.encode())
if dpy:
    x11.XDefaultRootWindow.restype = c_ulong
    x11.XDefaultRootWindow.argtypes = [c_void_p]
    x11.XGetWindowAttributes.argtypes = [c_void_p, c_ulong, POINTER(XWA)]
    x11.XQueryTree.argtypes = [c_void_p, c_ulong, POINTER(c_ulong), POINTER(c_ulong), POINTER(POINTER(c_ulong)), POINTER(c_uint)]
    x11.XMoveResizeWindow.argtypes = [c_void_p, c_ulong, c_int, c_int, c_uint, c_uint]
    x11.XFree.argtypes = [c_void_p]
    x11.XFlush.argtypes = [c_void_p]
    x11.XCloseDisplay.argtypes = [c_void_p]
    root = x11.XDefaultRootWindow(dpy)
    ra = XWA()
    if x11.XGetWindowAttributes(dpy, root, byref(ra)) and ra.width > 0 and ra.height > 0:
        if os.environ.get("SWAYSOCK"):
            subprocess.run(["swaymsg", "output", "X11-1", "resolution", f"{ra.width}x{ra.height}"], check=False)
        else:
            r, p, ch, n = c_ulong(), c_ulong(), POINTER(c_ulong)(), c_uint()
            if x11.XQueryTree(dpy, root, byref(r), byref(p), byref(ch), byref(n)):
                try:
                    for i in range(n.value):
                        a = XWA()
                        if x11.XGetWindowAttributes(dpy, ch[i], byref(a)) and a.map_state == 2 and a.width == 1024 and a.height == 768:
                            x11.XMoveResizeWindow(dpy, ch[i], 0, 0, ra.width, ra.height)
                            x11.XFlush(dpy)
                finally:
                    if ch:
                        x11.XFree(ch)
    x11.XCloseDisplay(dpy)
PY
fi

pkill -x quickshell 2>/dev/null || true
while pgrep -u "$(id -u)" -x quickshell >/dev/null 2>&1; do
  sleep 0.2
done
pkill -f "qs-native (media-stream|submenu-watch|sys-diag|wl-workspaces)" 2>/dev/null || true

LOG="${TMPDIR:-/data/data/com.termux/files/usr/tmp}/quickshell-wayland.log"
quickshell -p "${XDG_CONFIG_HOME:-$HOME/.config}/quickshell/wayland.qml" >> "$LOG" 2>&1 &
