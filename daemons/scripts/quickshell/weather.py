#!/data/data/com.termux/files/usr/bin/python3
"""Fetch current weather via Open-Meteo with optional config/env overrides."""

import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Default location (override via ~/.config/quickshell/weather.json or WEATHER_* env vars)
DEFAULT_LATITUDE = 38.45772
DEFAULT_LONGITUDE = 27.1142
DEFAULT_LABEL = "İzmir/Karşıyaka"
DEFAULT_TIMEZONE = "Europe/Istanbul"

CONFIG_PATH = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
    "quickshell",
    "weather.json",
)
CACHE_DIR = os.path.join(
    os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
    "quickshell",
)
CACHE_PATH = os.path.join(CACHE_DIR, "weather.json")
LEGACY_CACHE_PATH = os.path.join(CACHE_DIR, "weather-karsiyaka.json")

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


def load_config() -> tuple[float, float, str, str]:
    """Load weather settings from defaults -> ~/.config/quickshell/weather.json -> WEATHER_* env vars."""
    lat = DEFAULT_LATITUDE
    lon = DEFAULT_LONGITUDE
    label = DEFAULT_LABEL
    tz = DEFAULT_TIMEZONE

    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            if isinstance(cfg, dict):
                if cfg.get("latitude") is not None:
                    lat = float(cfg["latitude"])
                if cfg.get("longitude") is not None:
                    lon = float(cfg["longitude"])
                if cfg.get("label"):
                    label = str(cfg["label"])
                if cfg.get("timezone"):
                    tz = str(cfg["timezone"])
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    try:
        if os.environ.get("WEATHER_LAT"):
            lat = float(os.environ["WEATHER_LAT"])
        if os.environ.get("WEATHER_LON"):
            lon = float(os.environ["WEATHER_LON"])
    except ValueError:
        pass
    if os.environ.get("WEATHER_LABEL"):
        label = os.environ["WEATHER_LABEL"]
    if os.environ.get("WEATHER_TIMEZONE"):
        tz = os.environ["WEATHER_TIMEZONE"]

    return lat, lon, label, tz


def build_api_url(lat: float, lon: float, tz: str) -> str:
    query = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,is_day,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min",
        "forecast_days": 4,
        "timezone": tz,
    })
    return f"https://api.open-meteo.com/v1/forecast?{query}"


def _format_forecast(daily: dict | None) -> list[dict]:
    if not isinstance(daily, dict):
        return []
    times = daily.get("time") or []
    codes = daily.get("weather_code") or []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []

    out = []
    # Index 0 is today; take indices 1..3 for the next 3 days
    for i in range(1, min(4, len(times))):
        raw_date = str(times[i] or "")
        try:
            dt = datetime.date.fromisoformat(raw_date)
            day_lbl = dt.strftime("%a")
            date_lbl = dt.strftime("%-d %b")
        except ValueError:
            day_lbl = raw_date
            date_lbl = ""

        code = int(codes[i] or 0) if i < len(codes) and codes[i] is not None else 0
        cond, icon_d, _icon_n, tone_d, _tone_n = WMO_MAP.get(
            code, ("Cloudy", "\U000f0590", "\U000f0590", "subtext", "subtext")
        )
        hi = f"{round(float(tmax[i]))}°" if i < len(tmax) and tmax[i] is not None else "--°"
        lo = f"{round(float(tmin[i]))}°" if i < len(tmin) and tmin[i] is not None else "--°"
        out.append({
            "day": day_lbl,
            "date": date_lbl,
            "icon": icon_d,
            "tone": tone_d,
            "cond": cond,
            "hi": hi,
            "lo": lo,
        })
    return out


def _format_payload(cur: dict, location_label: str, stale: bool = False, daily: dict | None = None) -> dict:
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
        "location": location_label,
        "temp": temp_str,
        "cond": cond,
        "detail": detail,
        "icon": icon,
        "tone": tone,
        "forecast": _format_forecast(daily),
        "ts": int(time.time()),
    }


def _load_cached(lat: float, lon: float, label: str) -> dict | None:
    for path in (CACHE_PATH, LEGACY_CACHE_PATH):
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                cached = json.load(f)
            if not isinstance(cached, dict) or not cached.get("current"):
                continue
            # Ignore cache if user switched coordinates
            if "latitude" in cached and "longitude" in cached:
                if abs(float(cached["latitude"]) - lat) > 0.05 or abs(float(cached["longitude"]) - lon) > 0.05:
                    continue
            return _format_payload(cached["current"], label, stale=True, daily=cached.get("daily"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    return None


def main() -> int:
    lat, lon, label, tz = load_config()
    api_url = build_api_url(lat, lon, tz)
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "quickshell-weather/1.0"})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        cur = raw.get("current") or {}
        daily = raw.get("daily") or {}
        if not cur:
            raise ValueError("missing current weather")
        payload = _format_payload(cur, label, stale=False, daily=daily)
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "latitude": lat,
                        "longitude": lon,
                        "label": label,
                        "current": cur,
                        "daily": daily,
                        "fetched_at": int(time.time()),
                    },
                    f,
                )
        except OSError:
            pass
        print(json.dumps(payload), flush=True)
        return 0
    except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError):
        cached = _load_cached(lat, lon, label)
        if cached:
            print(json.dumps(cached), flush=True)
            return 0
        print(json.dumps({
            "ok": False,
            "location": label,
            "temp": "--°C",
            "cond": "Offline",
            "detail": "Tap to retry Open-Meteo",
            "icon": "\U000f0590",
            "tone": "subtext",
            "forecast": [],
            "ts": 0,
        }), flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
