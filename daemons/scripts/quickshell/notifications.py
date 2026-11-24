#!/data/data/com.termux/files/usr/bin/python3
"""Lightweight Android notifications list, app launcher, and snooze helper for Quickshell."""

import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import sys


_APP_NAMES = {
    "com.termux": "Termux",
    "com.termux.x11": "Termux:X11",
    "com.android.systemui": "System UI",
    "com.google.android.gm": "Gmail",
    "com.google.android.apps.messaging": "Messages",
    "com.google.android.googlequicksearchbox": "Google",
    "org.mozilla.firefox": "Firefox",
    "org.fdroid.fdroid": "F-Droid",
    "ch.protonmail.android": "Proton Mail",
    "com.spotify.music": "Spotify",
    "com.whatsapp": "WhatsApp",
    "com.discord": "Discord",
    "org.telegram.messenger": "Telegram",
    "com.samsung.android.forest": "Digital Wellbeing",
    "com.osp.app.signin": "Samsung Account",
}


def _app_label(pkg: str) -> str:
    if pkg in _APP_NAMES:
        return _APP_NAMES[pkg]
    if not pkg:
        return "Android"
    parts = [p for p in pkg.split(".") if p and p not in ("com", "org", "net", "io", "android", "apps", "app")]
    return (parts[-1] if parts else pkg).replace("_", " ").title()


def _fmt_when(when_str: str) -> str:
    if not when_str:
        return ""
    try:
        dt = datetime.datetime.strptime(when_str[:19], "%Y-%m-%d %H:%M:%S")
        today = datetime.date.today()
        if dt.date() == today:
            return dt.strftime("%H:%M")
        return dt.strftime("%-d %b %H:%M")
    except ValueError:
        return when_str[:16]


def _list_via_termux_api() -> list[dict] | None:
    bin_path = shutil.which("termux-notification-list")
    if not bin_path:
        return None
    try:
        res = subprocess.run([bin_path], capture_output=True, text=True, timeout=3.0)
        if res.returncode != 0 or not res.stdout.strip():
            return None
        raw = json.loads(res.stdout)
        if not isinstance(raw, list):
            return None
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        return None

    seen: set[tuple[str, str, str]] = set()
    items: list[dict] = []
    for n in raw:
        if not isinstance(n, dict):
            continue
        pkg = str(n.get("packageName", "") or "").strip()
        title = str(n.get("title", "") or "").strip()
        body = str(n.get("content", "") or "").strip()
        if not title and not body:
            continue
        sig = (pkg, title, body)
        if sig in seen:
            continue
        seen.add(sig)
        when_raw = str(n.get("when", "") or "").strip()
        items.append({
            "key": str(n.get("key", "") or "").strip(),
            "pkg": pkg,
            "app": _app_label(pkg),
            "title": title or _app_label(pkg),
            "body": body,
            "time": _fmt_when(when_raw),
            "sort_ts": when_raw,
        })

    items.sort(key=lambda x: x["sort_ts"], reverse=True)
    for item in items:
        item.pop("sort_ts", None)
    return items[:25]


def _list_via_rish() -> list[dict]:
    rish = os.path.expanduser("~/.local/bin/rish")
    if not os.path.exists(rish):
        return []
    try:
        res = subprocess.run(
            [rish, "-c", "dumpsys notification --noredact"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=4.0,
        )
        out = (res.stdout or "") + "\n" + (res.stderr or "")
    except (OSError, subprocess.SubprocessError):
        return []

    items: list[dict] = []
    cur: dict | None = None
    seen: set[tuple[str, str, str]] = set()

    def flush():
        nonlocal cur
        if not cur:
            return
        if cur["title"] or cur["body"]:
            sig = (cur["pkg"], cur["title"], cur["body"])
            if sig not in seen:
                seen.add(sig)
                items.append({
                    "key": cur["key"],
                    "pkg": cur["pkg"],
                    "app": _app_label(cur["pkg"]),
                    "title": cur["title"] or _app_label(cur["pkg"]),
                    "body": cur["body"],
                    "time": "",
                })
        cur = None

    for line in out.splitlines():
        if "NotificationRecord(" in line:
            flush()
            m_pkg = re.search(r"pkg=(\S+)", line)
            m_key = re.search(r"key=(\S+?)(?::|\s|$)", line)
            cur = {
                "pkg": m_pkg.group(1) if m_pkg else "",
                "key": m_key.group(1) if m_key else "",
                "title": "",
                "body": "",
            }
        elif cur is not None:
            s = line.strip()
            if s.startswith("android.title="):
                m = re.search(r"\((.*)\)$", s)
                if m and m.group(1) != "null":
                    cur["title"] = m.group(1)
            elif s.startswith("android.text="):
                m = re.search(r"\((.*)\)$", s)
                if m and m.group(1) != "null":
                    cur["body"] = m.group(1)
    flush()
    return items[:25]


def _get_notifications() -> dict:
    items = _list_via_termux_api()
    source = "termux-api"
    if items is None:
        items = _list_via_rish()
        source = "rish"
    return {"ok": True, "notifications": items, "source": source}


def _snooze(key: str) -> int:
    rish = os.path.expanduser("~/.local/bin/rish")
    if not key or not os.path.exists(rish):
        return 1
    try:
        res = subprocess.run(
            [rish, "-c", f"cmd notification snooze --for 3600000 {shlex.quote(key)}"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        return 0 if res.returncode == 0 else 1
    except (OSError, subprocess.SubprocessError):
        return 1


def _open_pkg(pkg: str) -> int:
    if not pkg:
        return 1
    monkey = shutil.which("monkey") or "/system/bin/monkey"
    if os.path.exists(monkey):
        try:
            subprocess.Popen(
                [monkey, "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return 0
        except OSError:
            pass
    return 1


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "snooze":
        return _snooze(sys.argv[2] if len(sys.argv) > 2 else "")
    if cmd == "open":
        return _open_pkg(sys.argv[2] if len(sys.argv) > 2 else "")
    print(json.dumps(_get_notifications()), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
