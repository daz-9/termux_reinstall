#!/data/data/com.termux/files/usr/bin/python3
"""Stream and control ext_workspace_manager_v1 virtual desktops (LabWC) over Wayland wire protocol."""

import json
import os
import select
import signal
import socket
import struct
import sys


def _pack_str(s: str) -> bytes:
    b = s.encode("utf-8") + b"\x00"
    pad = (-len(b)) & 3
    return struct.pack("<I", len(b)) + b + (b"\x00" * pad)


def _unpack_str(buf: bytes, off: int) -> tuple[str, int]:
    (slen,) = struct.unpack_from("<I", buf, off)
    raw = buf[off + 4 : off + 4 + max(0, slen - 1)]
    step = 4 + ((slen + 3) & ~3)
    return raw.decode("utf-8", errors="replace"), off + step


def _msg(obj_id: int, opcode: int, payload: bytes = b"") -> bytes:
    size = 8 + len(payload)
    return struct.pack("<II", obj_id, (size << 16) | opcode) + payload


def main() -> int:
    xdg = os.environ.get("XDG_RUNTIME_DIR", os.environ.get("TMPDIR", "/data/data/com.termux/files/usr/tmp"))
    wdisp = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
    sock_path = wdisp if os.path.isabs(wdisp) else os.path.join(xdg, wdisp)

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(sock_path)

    # 1 = wl_display, 2 = wl_registry, 3 = initial sync callback
    sock.sendall(_msg(1, 1, struct.pack("<I", 2)) + _msg(1, 0, struct.pack("<I", 3)))

    mgr_id = 0
    mgr_ver = 1
    workspaces: dict[int, dict] = {}
    groups: set[int] = set()
    rx = bytearray()
    in_buf = ""
    running = True

    def stop(_sig, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def emit_state() -> None:
        by_num: dict[int, dict] = {}
        ordered = []
        for ws in workspaces.values():
            name = ws.get("name", "")
            st = ws.get("state", 0)
            if st & 4:  # hidden
                continue
            item = {
                "name": name,
                "focused": bool(st & 1),
                "urgent": bool(st & 2),
                "occupied": False,
            }
            ordered.append(item)
            if name.isdigit():
                by_num[int(name)] = item
        out = []
        if by_num:
            for n in range(1, 7):
                w = by_num.get(n)
                out.append({
                    "num": n,
                    "focused": w["focused"] if w else False,
                    "occupied": False,
                    "urgent": w["urgent"] if w else False,
                })
        else:
            for idx, w in enumerate(ordered[:6], 1):
                out.append({
                    "num": idx,
                    "focused": w["focused"],
                    "occupied": False,
                    "urgent": w["urgent"],
                })
        if out:
            print(json.dumps(out), flush=True)

    stdin_fd = sys.stdin.fileno()
    os.set_blocking(stdin_fd, False)

    while running:
        rlist, _, _ = select.select([sock, stdin_fd], [], [], 0.5)
        if sock in rlist:
            chunk = sock.recv(8192)
            if not chunk:
                break
            rx.extend(chunk)
            while len(rx) >= 8:
                obj_id, size_op = struct.unpack_from("<II", rx, 0)
                size = size_op >> 16
                op = size_op & 0xFFFF
                if size < 8 or len(rx) < size:
                    break
                payload = bytes(rx[8:size])
                del rx[:size]

                if obj_id == 2 and op == 0:  # wl_registry::global
                    (gname,) = struct.unpack_from("<I", payload, 0)
                    iface, off = _unpack_str(payload, 4)
                    (gver,) = struct.unpack_from("<I", payload, off)
                    if iface == "ext_workspace_manager_v1" and mgr_id == 0:
                        mgr_id = 4
                        mgr_ver = min(1, gver)
                        sock.sendall(_msg(2, 0, struct.pack("<I", gname) + _pack_str(iface) + struct.pack("<II", mgr_ver, mgr_id)))
                elif obj_id == mgr_id:
                    if op == 0:  # workspace_group(new_id)
                        (gid,) = struct.unpack_from("<I", payload, 0)
                        groups.add(gid)
                    elif op == 1:  # workspace(new_id)
                        (wid,) = struct.unpack_from("<I", payload, 0)
                        workspaces[wid] = {"name": "", "state": 0}
                    elif op == 2:  # done
                        emit_state()
                    elif op == 3:  # finished
                        running = False
                        break
                elif obj_id in workspaces:
                    if op == 1:  # name(string)
                        name, _ = _unpack_str(payload, 0)
                        workspaces[obj_id]["name"] = name
                    elif op == 3:  # state(uint)
                        (st,) = struct.unpack_from("<I", payload, 0)
                        workspaces[obj_id]["state"] = st
                    elif op == 5:  # removed
                        workspaces.pop(obj_id, None)

        if stdin_fd in rlist:
            try:
                data = os.read(stdin_fd, 1024)
            except BlockingIOError:
                data = b""
            if not data:
                break
            in_buf += data.decode("utf-8", errors="ignore")
            while "\n" in in_buf:
                line, in_buf = in_buf.split("\n", 1)
                target = line.strip()
                if not target or not mgr_id:
                    continue
                for wid, ws in workspaces.items():
                    if ws.get("name") == target:
                        # activate (opcode 1) + manager::commit (opcode 0)
                        sock.sendall(_msg(wid, 1) + _msg(mgr_id, 0))
                        break

    sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
