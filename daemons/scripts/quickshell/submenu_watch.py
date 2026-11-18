#!/data/data/com.termux/files/usr/bin/python3
"""Watch X11 clicks, focus changes, and foreign popups to auto-close Quickshell submenus."""

import os
import select
import signal
import sys
import time
from ctypes import CDLL, POINTER, Structure, byref, c_char, c_int, c_long, c_ubyte, c_uint, c_ulong, c_void_p


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


class XIEventMask(Structure):
    _fields_ = [("deviceid", c_int), ("mask_len", c_int), ("mask", POINTER(c_ubyte))]


def _point_in(px: int, py: int, rect) -> bool:
    x, y, w, h = rect
    return w > 0 and h > 0 and x <= px < x + w and y <= py < y + h


def _matches_rect(a, rect, tol: int = 16) -> bool:
    rx, ry, rw, rh = rect
    return rw > 0 and rh > 0 and abs(a.x - rx) <= tol and abs(a.y - ry) <= tol and abs(a.width - rw) <= tol and abs(a.height - rh) <= tol


def _has_foreign_popup(x11, dpy, root, own_rects) -> bool:
    r, p, ch, n = c_ulong(), c_ulong(), POINTER(c_ulong)(), c_uint()
    if not x11.XQueryTree(dpy, root, byref(r), byref(p), byref(ch), byref(n)):
        return False
    try:
        for i in range(n.value):
            a = XWA()
            if not x11.XGetWindowAttributes(dpy, ch[i], byref(a)) or a.map_state != 2:
                continue
            if a.override_redirect == 1 and a.width >= 200 and a.height >= 150:
                if not any(_matches_rect(a, rect) for rect in own_rects):
                    return True
    finally:
        if ch:
            x11.XFree(ch)
    return False


def main() -> int:
    # Args: dock_w dock_h sub_x sub_y sub_w sub_h
    args = [int(float(v)) for v in sys.argv[1:7]] if len(sys.argv) >= 7 else [128, 1508, 140, 80, 844, 1508]
    dock_w, dock_h, sub_x, sub_y, sub_w, sub_h = args
    dock_rect = (0, 80, dock_w, dock_h)
    sub_rect = (sub_x, sub_y, sub_w, sub_h)
    own_rects = [dock_rect, sub_rect]

    x11 = CDLL("libX11.so.6")
    xi = CDLL("libXi.so")

    x11.XOpenDisplay.restype = c_void_p
    x11.XOpenDisplay.argtypes = [c_void_p]
    x11.XDefaultRootWindow.restype = c_ulong
    x11.XDefaultRootWindow.argtypes = [c_void_p]
    x11.XConnectionNumber.restype = c_int
    x11.XConnectionNumber.argtypes = [c_void_p]
    x11.XPending.restype = c_int
    x11.XPending.argtypes = [c_void_p]
    x11.XNextEvent.argtypes = [c_void_p, c_void_p]
    x11.XFlush.argtypes = [c_void_p]
    x11.XQueryTree.restype = c_int
    x11.XQueryTree.argtypes = [c_void_p, c_ulong, POINTER(c_ulong), POINTER(c_ulong), POINTER(POINTER(c_ulong)), POINTER(c_uint)]
    x11.XGetWindowAttributes.restype = c_int
    x11.XGetWindowAttributes.argtypes = [c_void_p, c_ulong, POINTER(XWA)]
    x11.XGetInputFocus.argtypes = [c_void_p, POINTER(c_ulong), POINTER(c_int)]
    x11.XQueryPointer.restype = c_int
    x11.XQueryPointer.argtypes = [
        c_void_p, c_ulong, c_void_p, c_void_p,
        c_void_p, c_void_p, c_void_p, c_void_p, c_void_p,
    ]
    x11.XFree.argtypes = [c_void_p]
    x11.XCloseDisplay.argtypes = [c_void_p]

    xi.XIQueryVersion.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
    xi.XISelectEvents.argtypes = [c_void_p, c_ulong, POINTER(XIEventMask), c_int]

    dpy = x11.XOpenDisplay(os.environ.get("DISPLAY", ":0").encode())
    if not dpy:
        return 1
    root = x11.XDefaultRootWindow(dpy)
    xfd = x11.XConnectionNumber(dpy)

    maj, minv = c_int(2), c_int(2)
    xi.XIQueryVersion(dpy, byref(maj), byref(minv))

    # XIAllMasterDevices = 1; XI_RawButtonPress = 15 (1 << 15 -> byte 1 bit 7 = 0x80)
    ev_mask = (c_ubyte * 4)(0, 0x80, 0, 0)
    em = XIEventMask(deviceid=1, mask_len=4, mask=ev_mask)
    xi.XISelectEvents(dpy, root, byref(em), 1)
    x11.XFlush(dpy)

    running = True

    def stop(_sig, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    pid_path = os.path.join(
        os.environ.get("TMPDIR", "/data/data/com.termux/files/usr/tmp"),
        "qs-watch.pid",
    )
    try:
        with open(pid_path, "w") as pf:
            pf.write(str(os.getpid()))
    except OSError:
        pid_path = ""

    focus_win, revert_to = c_ulong(), c_int()
    x11.XGetInputFocus(dpy, byref(focus_win), byref(revert_to))
    initial_focus = focus_win.value

    r_win, c_win = c_ulong(), c_ulong()
    rx, ry, wx, wy = c_int(), c_int(), c_int(), c_int()
    mask = c_uint()
    ev_buf = (c_char * 192)()
    start_t = time.monotonic()

    while running:
        readable, _, _ = select.select([xfd], [], [], 0.12)
        clicked = False
        if readable:
            while x11.XPending(dpy) > 0:
                x11.XNextEvent(dpy, ev_buf)
                clicked = True

        x11.XGetInputFocus(dpy, byref(focus_win), byref(revert_to))
        if (focus_win.value != initial_focus and focus_win.value not in (0, 1)) or _has_foreign_popup(x11, dpy, root, own_rects):
            print("CLOSE", flush=True)
            break

        if clicked and (time.monotonic() - start_t) >= 0.08:
            if x11.XQueryPointer(dpy, root, byref(r_win), byref(c_win), byref(rx), byref(ry), byref(wx), byref(wy), byref(mask)):
                px, py = rx.value, ry.value
                in_sub = _point_in(px, py, sub_rect)
                in_dock = _point_in(px, py, dock_rect)
                on_toggle = in_dock and (
                    (80 + int(dock_h * 0.45) <= py <= 80 + int(dock_h * 0.70))
                    or (py >= 80 + dock_h - 90)
                )
                if not in_sub and not on_toggle:
                    print("CLOSE", flush=True)
                    break

    if pid_path:
        try:
            os.remove(pid_path)
        except OSError:
            pass
    x11.XCloseDisplay(dpy)
    return 0


if __name__ == "__main__":
    sys.exit(main())
