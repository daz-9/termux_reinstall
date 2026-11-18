#!/data/data/com.termux/files/usr/bin/python3
"""Fetch current weather exclusively for İzmir / Karşıyaka via Open-Meteo."""

import json
import os
import sys
import time
import urllib.error
import urllib.request

# Locked coordinates for İzmir / Karşıyaka only
LATITUDE = 38.45772
LONGITUDE = 27.1142
LOCATION_LABEL = "İzmir/Karşıyaka"
API_URL = (
    f"https://api.open-meteo.com/v1/forecast"
    f"?latitude={LATITUDE}&longitude={LONGITUDE}"
    "&current=temperature_2m,apparent_temperature,relative_humidity_2m,is_day,weather_code,wind_speed_10m"
    "&timezone=Europe%2FIstanbul"
)
CACHE_PATH = os.path.expanduser("~/.cache/quickshell/weather-karsiyaka.json")

WMO_MAP = {
    0: ("Clear Sky", "\U000f0599", "\U000f0594", "peach", "blue"),
    1: ("Mostly Clear", "\U000f0595", "\U000f0594", "peach", "blue"),
    2: ("Partly Cloudy", "\U000f0595", "\U000f0595", "peach", "subtext"),
    3: ("Overcast", "\U000f0590", "\U000f0590", "subtext", "subtext"),
    45: ("Foggy", "\U000f0591", "\U000f0591", "subtext", "subtext"),
    48: ("Rime Fog", "\U000f0591", "\U000f0591", "subtext", "subtext"),
    51: ("Light Drizzle", "\U000f0597", "\U000f0597", "blue", "blue"),
    53: ("Drizzle", "\U000f0597", "\U000f0597", "blue", "blue"),
    55: ("Dense Drizzle", "\U000f0597", "\U000f0597", "blue", "blue"),
    56: ("Freezing Drizzle", "\U000f0597", "\U000f0597", "teal", "teal"),
    57: ("Freezing Drizzle", "\U000f0597", "\U000f0597", "teal", "teal"),
    61: ("Light Rain", "\U000f0597", "\U000f0597", "blue", "blue"),
    63: ("Rain", "\U000f0597", "\U000f0597", "blue", "blue"),
    65: ("Heavy Rain", "\U000f0596", "\U000f0596", "blue", "blue"),
    66: ("Freezing Rain", "\U000f0597", "\U000f0597", "teal", "teal"),
    67: ("Heavy Freezing Rain", "\U000f0596", "\U000f0596", "teal", "teal"),
    71: ("Light Snow", "\U000f0598", "\U000f0598", "text", "text"),
    73: ("Snow", "\U000f0598", "\U000f0598", "text", "text"),
    75: ("Heavy Snow", "\U000f0598", "\U000f0598", "text", "text"),
    77: ("Snow Grains", "\U000f0598", "\U000f0598", "text", "text"),
    80: ("Light Showers", "\U000f0597", "\U000f0597", "blue", "blue"),
    81: ("Showers", "\U000f0597", "\U000f0597", "blue", "blue"),
    82: ("Heavy Showers", "\U000f0596", "\U000f0596", "blue", "blue"),
    85: ("Snow Showers", "\U000f0598", "\U000f0598", "text", "text"),
    86: ("Heavy Snow Showers", "\U000f0598", "\U000f0598", "text", "text"),
    95: ("Thunderstorm", "\U000f0593", "\U000f0593", "mauve", "mauve"),
    96: ("Thunderstorm + Hail", "\U000f0593", "\U000f0593", "mauve", "mauve"),
    99: ("Severe Thunderstorm", "\U000f0593", "\U000f0593", "red", "red"),
}


def _format_payload(cur: dict, stale: bool = False) -> dict:
    temp = cur.get("temperature_2m")
    feels = cur.get("apparent_temperature")
    code = int(cur.get("weather_code", 0) or 0)
    is_day = bool(cur.get("is_day", 1))
    hum = cur.get("relative_humidity_2m")
    wind = cur.get("wind_speed_10m")

    cond, icon_d, icon_n, tone_d, tone_n = WMO_MAP.get(
        code, ("Cloudy", "\U000f0590", "\U000f0590", "subtext", "subtext")
    )
    icon = icon_d if is_day else icon_n
    tone = tone_d if is_day else tone_n

    temp_str = f"{round(float(temp))}°C" if temp is not None else "--°C"
    feels_str = f"Feels {round(float(feels))}°C" if feels is not None else ""
    extra = []
    if feels_str:
        extra.append(feels_str)
    if wind is not None:
        extra.append(f"{round(float(wind))} km/h")
    if hum is not None and not extra:
        extra.append(f"{int(hum)}%")

    detail = cond if not extra else f"{cond} · {' · '.join(extra)}"
    if stale:
        detail = f"{detail} (cached)"

    return {
        "ok": True,
        "location": LOCATION_LABEL,
        "temp": temp_str,
        "cond": cond,
        "detail": detail,
        "icon": icon,
        "tone": tone,
        "ts": int(time.time()),
    }


def main() -> int:
    try:
        req = urllib.request.Request(API_URL, headers={"User-Agent": "quickshell-weather/1.0"})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        cur = raw.get("current") or {}
        if not cur:
            raise ValueError("missing current weather")
        payload = _format_payload(cur, stale=False)
        try:
            os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
            with open(CACHE_PATH, "w") as f:
                json.dump({"current": cur, "fetched_at": int(time.time())}, f)
        except OSError:
            pass
        print(json.dumps(payload), flush=True)
        return 0
    except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError):
        if os.path.exists(CACHE_PATH):
            try:
                with open(CACHE_PATH) as f:
                    cached = json.load(f)
                payload = _format_payload(cached.get("current") or {}, stale=True)
                print(json.dumps(payload), flush=True)
                return 0
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        print(json.dumps({
            "ok": False,
            "location": LOCATION_LABEL,
            "temp": "--°C",
            "cond": "Offline",
            "detail": "Tap to retry Open-Meteo",
            "icon": "\U000f0590",
            "tone": "subtext",
            "ts": 0,
        }), flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
