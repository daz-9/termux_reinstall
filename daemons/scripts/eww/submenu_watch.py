#!/data/data/com.termux/files/usr/bin/python3
"""Auto-close open Eww submenus on focus loss, popup/launcher open, or outside click."""

import os
import select
import signal
import subprocess
import sys
import time
from ctypes import CDLL, POINTER, Structure, byref, c_char, c_char_p, c_int, c_long, c_ubyte, c_uint, c_ulong, c_void_p, string_at


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


def _inspect_tree(x11, dpy, root):
    r, p, ch, n = c_ulong(), c_ulong(), POINTER(c_ulong)(), c_uint()
    rects = {}
    foreign_popup = False
    if not x11.XQueryTree(dpy, root, byref(r), byref(p), byref(ch), byref(n)):
        return rects, foreign_popup
    try:
        for i in range(n.value):
            a = XWA()
            if not x11.XGetWindowAttributes(dpy, ch[i], byref(a)) or a.map_state != 2:
                continue
            nm = c_void_p()
            name = b""
            if x11.XFetchName(dpy, ch[i], byref(nm)) and nm.value:
                name = string_at(nm.value)
                x11.XFree(nm)
            if name in (b"Eww - dock", b"Eww - widget_drawer", b"Eww - session_menu"):
                rects[name.decode()] = (a.x, a.y, a.width, a.height)
            elif a.override_redirect == 1 and a.width >= 200 and a.height >= 150 and not name.startswith(b"Eww"):
                foreign_popup = True
    finally:
        if ch:
            x11.XFree(ch)
    return rects, foreign_popup


def _point_in(px: int, py: int, rect) -> bool:
    if rect is None:
        return False
    x, y, w, h = rect
    return x <= px < x + w and y <= py < y + h


def _close_open(rects) -> None:
    toggle = os.path.expanduser("~/.config/eww/scripts/toggle_window.sh")
    targets = []
    if "Eww - widget_drawer" in rects:
        targets.append(("widget_drawer", "widgets_open"))
    if "Eww - session_menu" in rects:
        targets.append(("session_menu", "session_open"))
    procs = [subprocess.Popen([toggle, "close", win, var]) for win, var in targets]
    for proc in procs:
        proc.wait()


def main() -> int:
    x11 = CDLL("libX11.so.6")
    xi = CDLL("libXi.so")

    x11.XOpenDisplay.restype = c_void_p
    x11.XOpenDisplay.argtypes = [c_char_p]
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
    x11.XFetchName.restype = c_int
    x11.XFetchName.argtypes = [c_void_p, c_ulong, POINTER(c_void_p)]
    x11.XFree.argtypes = [c_void_p]
    x11.XGetInputFocus.argtypes = [c_void_p, POINTER(c_ulong), POINTER(c_int)]
    x11.XQueryPointer.restype = c_int
    x11.XQueryPointer.argtypes = [
        c_void_p, c_ulong, c_void_p, c_void_p,
        c_void_p, c_void_p, c_void_p, c_void_p, c_void_p,
    ]
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
        "eww-watch.pid",
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

    # Wait briefly for eww open before exiting on empty rects
    seen_submenu = False

    while running:
        readable, _, _ = select.select([xfd], [], [], 0.12)
        clicked = False
        if readable:
            while x11.XPending(dpy) > 0:
                x11.XNextEvent(dpy, ev_buf)
                clicked = True

        rects, foreign_popup = _inspect_tree(x11, dpy, root)
        has_sub = ("Eww - widget_drawer" in rects) or ("Eww - session_menu" in rects)
        if has_sub:
            seen_submenu = True
        elif seen_submenu or (time.monotonic() - start_t) > 1.0:
            break

        if not has_sub:
            continue

        x11.XGetInputFocus(dpy, byref(focus_win), byref(revert_to))
        if (focus_win.value != initial_focus and focus_win.value != 0) or foreign_popup:
            _close_open(rects)
            break

        if clicked and (time.monotonic() - start_t) >= 0.05:
            if x11.XQueryPointer(dpy, root, byref(r_win), byref(c_win), byref(rx), byref(ry), byref(wx), byref(wy), byref(mask)):
                px, py = rx.value, ry.value
                in_drawer = _point_in(px, py, rects.get("Eww - widget_drawer"))
                in_session = _point_in(px, py, rects.get("Eww - session_menu"))
                dock_r = rects.get("Eww - dock")
                on_toggle_btn = False
                if dock_r and _point_in(px, py, dock_r):
                    dx0, dy0, dw, dh = dock_r
                    on_spacer = (dy0 + 755 <= py <= dy0 + dh - 470)
                    on_power = (py >= dy0 + dh - 78)
                    on_toggle_btn = on_spacer or on_power
                if not in_drawer and not in_session and not on_toggle_btn:
                    _close_open(rects)
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
