"""
briefing.py — morning briefing data assembly.

Returns RAW data (datetime, weather, today's calendar); Claude composes the
spoken summary itself, so phrasing stays natural and vault to-dos can be
mixed in via the existing vault tools when asked.

Weather: Open-Meteo — free, no API key. Coordinates in config.py
(BRIEFING_LAT/LON) — update those when relocating (e.g. Stockholm on Aug 15).
"""

import json
import urllib.request
from datetime import datetime

from config import BRIEFING_LAT, BRIEFING_LON, BRIEFING_PLACE

_WMO = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
        45: "fog", 48: "fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
        61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain",
        67: "freezing rain", 71: "light snow", 73: "snow", 75: "heavy snow",
        80: "rain showers", 81: "rain showers", 82: "violent rain showers",
        95: "thunderstorm", 96: "thunderstorm w/ hail", 99: "thunderstorm w/ hail"}


def get_datetime() -> str:
    now = datetime.now().astimezone()
    return now.strftime("%A, %B %d, %Y, %I:%M %p %Z")


def get_weather() -> str:
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={BRIEFING_LAT}"
               f"&longitude={BRIEFING_LON}&current=temperature_2m,apparent_temperature,"
               f"precipitation,weather_code,wind_speed_10m"
               f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
               f"&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto&forecast_days=1")
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read().decode())
        cur, day = data["current"], data["daily"]
        cond = _WMO.get(cur.get("weather_code", -1), "unknown conditions")
        return (f"{BRIEFING_PLACE}: {cond}, {round(cur['temperature_2m'])}F "
                f"(feels {round(cur['apparent_temperature'])}F), wind {round(cur['wind_speed_10m'])} mph. "
                f"Today: high {round(day['temperature_2m_max'][0])}F, low {round(day['temperature_2m_min'][0])}F, "
                f"{day['precipitation_probability_max'][0]}% precip chance.")
    except Exception as e:
        return f"Weather unavailable ({e})."


def morning_briefing() -> str:
    """Raw briefing data — Claude turns this into the spoken summary."""
    import google_tools
    parts = [
        f"NOW: {get_datetime()}",
        f"WEATHER: {get_weather()}",
        "CALENDAR (next 2 days):",
        google_tools.list_events(days_ahead=2, max_results=10),
    ]
    return "\n".join(parts)
