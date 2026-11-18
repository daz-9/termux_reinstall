#!/data/data/com.termux/files/usr/bin/python3
"""Query and control Android MediaSession playback via rish (Shizuku)."""

import json
import os
import re
import shutil
import subprocess
import sys


def _rish_cmd() -> tuple[list[str], dict[str, str]] | tuple[None, None]:
    prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    dex_path = os.path.join(prefix, "share", "rish-shizuku.dex")
    env = os.environ.copy()
    env.pop("LD_LIBRARY_PATH", None)
    env.pop("LD_PRELOAD", None)
    env["RISH_APPLICATION_ID"] = "com.termux"

    if os.path.exists(dex_path):
        try:
            if (os.stat(dex_path).st_mode & 0o777) & 0o222:
                os.chmod(dex_path, 0o400)
        except OSError:
            pass
        app_proc = "/system/bin/app_process"
        if not os.path.exists(app_proc):
            app_proc = shutil.which("app_process") or "app_process"
        return [
            app_proc,
            f"-Djava.class.path={dex_path}",
            "/system/bin",
            "--nice-name=rish",
            "rikka.shizuku.shell.ShizukuShellLoader",
            "-c",
        ], env

    rish_bin = shutil.which("rish")
    if rish_bin:
        return [rish_bin, "-c"], env
    return None, None


def _run_rish(shell_cmd: str, stdin_text: str = "", timeout_s: float = 2.8) -> tuple[int, str]:
    base, env = _rish_cmd()
    if not base:
        return 127, ""
    try:
        res = subprocess.run(
            base + [shell_cmd],
            env=env,
            input=stdin_text if stdin_text else None,
            stdin=None if stdin_text else subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return res.returncode, (res.stdout or "") + "\n" + (res.stderr or "")
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def _uptime_ms() -> int:
    try:
        with open("/proc/uptime") as f:
            first = f.read().split()[0]
        return int(float(first) * 1000.0)
    except (OSError, IndexError, ValueError):
        return 0


def _app_label(pkg: str) -> str:
    known = {
        "com.spotify.music": "Spotify",
        "com.spotify.lite": "Spotify Lite",
        "com.google.android.apps.youtube.music": "YT Music",
        "app.morphe.android.apps.youtube.music": "YT Music",
        "com.google.android.youtube": "YouTube",
        "app.revanced.android.youtube": "YouTube",
        "org.videolan.vlc": "VLC",
        "com.apple.android.music": "Apple Music",
    }
    if pkg in known:
        return known[pkg]
    parts = [p for p in pkg.split(".") if p and p not in ("com", "org", "app", "android", "apps", "music")]
    return parts[-1].capitalize() if parts else (pkg or "Media")


def _fmt_time(sec: int) -> str:
    sec = max(0, sec)
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _parse_description(desc: str) -> tuple[str, str, str]:
    if not desc or desc == "null":
        return "", "", ""
    parts = [p.strip() for p in desc.split(", ")]
    clean = [("" if p == "null" else p) for p in parts]
    if len(clean) == 1:
        return clean[0], "", ""
    if len(clean) == 2:
        return clean[0], clean[1], ""
    album = clean[-1]
    artist = clean[-2]
    title = ", ".join(clean[:-2]).strip()
    return title, artist, album


def get_status() -> dict:
    rc, out = _run_rish("echo UPTIME:$(cat /proc/uptime 2>/dev/null); dumpsys media_session 2>/dev/null")
    if rc != 0:
        return {
            "available": False,
            "playing": False,
            "state": "SHIZUKU OFF",
            "package": "",
            "app": "Media Control",
            "tag": "",
            "title": "Shizuku inactive",
            "artist": "Start Shizuku to control media",
            "album": "",
            "pos_sec": 0,
            "pos_text": "--:--",
        }

    uptime_ms = 0
    for raw in out.splitlines():
        if raw.startswith("UPTIME:"):
            toks = raw[7:].strip().split()
            if toks:
                try:
                    uptime_ms = int(float(toks[0]) * 1000.0)
                except ValueError:
                    uptime_ms = 0
            break
    if uptime_ms <= 0:
        uptime_ms = _uptime_ms()

    btn_tag = ""
    btn_pkg = ""
    m_btn = re.search(r"Media button session is\s+([^/\s]+)/([^/\s]+)/", out)
    if m_btn:
        btn_pkg, btn_tag = m_btn.group(1), m_btn.group(2)

    sessions = []
    in_stack = False
    cur = None
    for raw in out.splitlines():
        line = raw.rstrip("\r\n")
        if "Sessions Stack - have" in line:
            in_stack = True
            continue
        if not in_stack:
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if not stripped:
            continue
        if indent <= 2:
            break
        if indent == 4:
            if cur:
                sessions.append(cur)
            # Example: spotify-media-session com.spotify.music/spotify-media-session/485 (userId=0)
            m_hdr = re.match(r"^(.+?)\s+([^/\s]+)/([^/\s]+)/\d+\s+\(userId=", stripped)
            cur = {
                "tag": m_hdr.group(3) if m_hdr else stripped.split()[0],
                "package": m_hdr.group(2) if m_hdr else "",
                "active": False,
                "state_name": "NONE",
                "state_code": 0,
                "pos_ms": 0,
                "speed": 0.0,
                "updated_ms": 0,
                "title": "",
                "artist": "",
                "album": "",
            }
        elif cur and indent >= 6:
            if stripped.startswith("package="):
                cur["package"] = stripped.split("=", 1)[1].strip()
            elif stripped.startswith("active="):
                cur["active"] = stripped.split("=", 1)[1].strip().lower() == "true"
            elif stripped.startswith("state=PlaybackState"):
                ms = re.search(r"state=([A-Z_]+)\((\d+)\)", stripped)
                if ms:
                    cur["state_name"] = ms.group(1)
                    cur["state_code"] = int(ms.group(2))
                mp = re.search(r"position=(\d+)", stripped)
                if mp:
                    cur["pos_ms"] = int(mp.group(1))
                mv = re.search(r"speed=([0-9.]+)", stripped)
                if mv:
                    try:
                        cur["speed"] = float(mv.group(1))
                    except ValueError:
                        cur["speed"] = 0.0
                mu = re.search(r"updated=(\d+)", stripped)
                if mu:
                    cur["updated_ms"] = int(mu.group(1))
            elif stripped.startswith("metadata:") and "description=" in stripped:
                desc = stripped.split("description=", 1)[1].strip()
                cur["title"], cur["artist"], cur["album"] = _parse_description(desc)

    if cur:
        sessions.append(cur)

    # Ignore sessions with neither title nor active playback unless nothing else exists.
    usable = [s for s in sessions if s["title"] or s["state_code"] in (2, 3, 6)]
    if not usable:
        return {
            "available": True,
            "playing": False,
            "state": "IDLE",
            "package": "",
            "app": "Media Control",
            "tag": "",
            "title": "Nothing Playing",
            "artist": "Open Spotify or a media app",
            "album": "",
            "pos_sec": 0,
            "pos_text": "0:00",
        }

    def _score(s: dict) -> tuple[int, int, int, int]:
        return (
            1 if s["state_code"] == 3 else 0,
            1 if "spotify" in s["package"] else 0,
            1 if (s["package"] == btn_pkg and s["tag"] == btn_tag) else 0,
            1 if s["active"] else 0,
        )

    chosen = max(usable, key=_score)
    playing = chosen["state_code"] in (3, 6)
    pos_ms = chosen["pos_ms"]
    if chosen["state_code"] == 3 and chosen["updated_ms"] > 0 and chosen["speed"] > 0:
        if uptime_ms >= chosen["updated_ms"]:
            pos_ms = max(0, int(pos_ms + (uptime_ms - chosen["updated_ms"]) * chosen["speed"]))
    pos_sec = pos_ms // 1000

    return {
        "available": True,
        "playing": playing,
        "state": chosen["state_name"],
        "package": chosen["package"],
        "app": _app_label(chosen["package"]),
        "tag": chosen["tag"],
        "title": chosen["title"] or _app_label(chosen["package"]),
        "artist": chosen["artist"],
        "album": chosen["album"],
        "pos_sec": pos_sec,
        "pos_text": _fmt_time(pos_sec),
    }


def dispatch_action(action: str, tag: str = "", is_playing: str = "") -> int:
    allowed = {"play", "pause", "play-pause", "next", "previous", "stop"}
    if action not in allowed:
        return 2

    if tag and re.fullmatch(r"[A-Za-z0-9._ -]+", tag):
        mon_cmd = action
        if action == "play-pause":
            mon_cmd = "pause" if is_playing == "1" else "play"
        if mon_cmd in ("play", "pause", "next", "previous"):
            rc, _ = _run_rish(f"cmd media_session monitor '{tag}'", stdin_text=f"{mon_cmd}\nq\n", timeout_s=2.5)
            if rc == 0:
                return 0

    rc, _ = _run_rish(f"cmd media_session dispatch {action}", timeout_s=2.5)
    return 0 if rc == 0 else 1


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        print(json.dumps(get_status()), flush=True)
        return 0
    tag = sys.argv[2] if len(sys.argv) > 2 else ""
    is_playing = sys.argv[3] if len(sys.argv) > 3 else ""
    return dispatch_action(cmd, tag, is_playing)


if __name__ == "__main__":
    sys.exit(main())
