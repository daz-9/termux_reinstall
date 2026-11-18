#!/data/data/com.termux/files/usr/bin/python3
"""Auto-hide the X11 cursor when idle or right after simulated touch taps."""

import os
import signal
import sys
import time
from ctypes import CDLL, byref, c_char_p, c_int, c_uint, c_ulong, c_void_p


def main() -> int:
    x11 = CDLL("libX11.so.6")
    xf = CDLL("libXfixes.so")

    x11.XOpenDisplay.restype = c_void_p
    x11.XOpenDisplay.argtypes = [c_char_p]
    x11.XDefaultRootWindow.restype = c_ulong
    x11.XDefaultRootWindow.argtypes = [c_void_p]
    x11.XSync.argtypes = [c_void_p, c_int]
    x11.XQueryPointer.restype = c_int
    x11.XQueryPointer.argtypes = [
        c_void_p, c_ulong, c_void_p, c_void_p,
        c_void_p, c_void_p, c_void_p, c_void_p, c_void_p,
    ]
    x11.XCloseDisplay.argtypes = [c_void_p]

    xf.XFixesQueryExtension.argtypes = [c_void_p, c_void_p, c_void_p]
    xf.XFixesQueryVersion.argtypes = [c_void_p, c_void_p, c_void_p]
    xf.XFixesHideCursor.argtypes = [c_void_p, c_ulong]
    xf.XFixesShowCursor.argtypes = [c_void_p, c_ulong]

    disp_name = os.environ.get("DISPLAY", ":0").encode()
    dpy = x11.XOpenDisplay(disp_name)
    if not dpy:
        return 1

    ev, er = c_int(), c_int()
    if not xf.XFixesQueryExtension(dpy, byref(ev), byref(er)):
        return 1
    maj, minv = c_int(5), c_int(0)
    xf.XFixesQueryVersion(dpy, byref(maj), byref(minv))

    root = x11.XDefaultRootWindow(dpy)
    r_win, c_win = c_ulong(), c_ulong()
    rx, ry, wx, wy = c_int(), c_int(), c_int(), c_int()
    mask = c_uint()

    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    pid_path = os.path.join(
        os.environ.get("TMPDIR", "/data/data/com.termux/files/usr/tmp"),
        "hide-cursor.pid",
    )
    try:
        with open(pid_path, "w") as pf:
            pf.write(str(os.getpid()))
    except OSError:
        pid_path = ""

    x11.XQueryPointer(dpy, root, byref(r_win), byref(c_win), byref(rx), byref(ry), byref(wx), byref(wy), byref(mask))
    last_x, last_y = rx.value, ry.value
    was_pressed = bool(mask.value & 0x1F00)
    hidden = True
    xf.XFixesHideCursor(dpy, root)
    x11.XSync(dpy, 0)
    hide_at = 0.0

    while running:
        time.sleep(0.08)
        if not x11.XQueryPointer(
            dpy, root, byref(r_win), byref(c_win), byref(rx), byref(ry), byref(wx), byref(wy), byref(mask)
        ):
            break

        now = time.monotonic()
        moved = (rx.value != last_x) or (ry.value != last_y)
        pressed = bool(mask.value & 0x1F00)
        last_x, last_y = rx.value, ry.value

        if pressed:
            was_pressed = True
            hide_at = now + 0.5
        elif was_pressed and not pressed:
            # Touch tap / click finished: hide quickly so no stray cursor lingers
            was_pressed = False
            hide_at = now + 0.15
            if not hidden:
                xf.XFixesHideCursor(dpy, root)
                x11.XSync(dpy, 0)
                hidden = True
        elif moved:
            if hidden:
                xf.XFixesShowCursor(dpy, root)
                x11.XSync(dpy, 0)
                hidden = False
            hide_at = now + 0.6
        elif not hidden and now >= hide_at:
            xf.XFixesHideCursor(dpy, root)
            x11.XSync(dpy, 0)
            hidden = True

    if hidden:
        xf.XFixesShowCursor(dpy, root)
        x11.XSync(dpy, 0)
    if pid_path:
        try:
            os.remove(pid_path)
        except OSError:
            pass
    x11.XCloseDisplay(dpy)
    return 0


if __name__ == "__main__":
    sys.exit(main())
