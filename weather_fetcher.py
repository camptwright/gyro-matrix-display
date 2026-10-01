"""
Simple weather data fetcher
Uses Open-Meteo (open-meteo.com) - free, no API key or signup required.
Replaces the previous OpenWeatherMap implementation, which needed a key
that was never actually configured (weather mode was silently non-functional
before this).
"""

import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# WMO weather codes (https://open-meteo.com/en/docs) mapped to strings that
# display_assets.py's get_weather_icon() can match, either exactly or via
# its substring fallback ('rain' in condition_lower, etc.)
_WMO_CONDITIONS = {
    0: "Clear", 1: "Clear",
    2: "Partly Cloudy",
    3: "Overcast",
    45: "Fog", 48: "Fog",
    51: "Rain", 53: "Rain", 55: "Rain",
    56: "Rain", 57: "Rain",
    61: "Rain", 63: "Rain", 65: "Rain",
    66: "Rain", 67: "Rain",
    71: "Snow", 73: "Snow", 75: "Snow", 77: "Snow",
    80: "Rain", 81: "Rain", 82: "Rain",
    85: "Snow", 86: "Snow",
    95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm",
}

_WMO_DESCRIPTIONS = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    56: "light freezing drizzle", 57: "dense freezing drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain",
    66: "light freezing rain", 67: "heavy freezing rain",
    71: "slight snow fall", 73: "moderate snow fall", 75: "heavy snow fall",
    77: "snow grains",
    80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
    85: "slight snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with slight hail", 99: "thunderstorm with heavy hail",
}

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# In-process cache for city/state -> (lat, lon): geocoding results never
# change, no reason to re-resolve them every poll.
_geocode_cache: Dict[str, tuple] = {}


def _geocode(city: str, state: str) -> Optional[tuple]:
    cache_key = f"{city},{state}".lower()
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]
    try:
        response = requests.get(
            _GEOCODE_URL,
            params={"name": city, "count": 5, "language": "en", "format": "json"},
            timeout=5,
        )
        response.raise_for_status()
        results = response.json().get("results") or []
        if not results:
            logger.error(f"Open-Meteo geocoding found no match for city={city!r}")
            return None
        # Prefer a result whose admin1 (state) matches, when we have one to
        # compare against - avoids picking a same-named city in another state.
        match = results[0]
        if state:
            for r in results:
                admin1 = (r.get("admin1") or "")
                if state.lower() in admin1.lower() or admin1.lower().startswith(state.lower()):
                    match = r
                    break
        coords = (match["latitude"], match["longitude"])
        _geocode_cache[cache_key] = coords
        return coords
    except Exception as e:
        logger.error(f"Error geocoding {city}, {state}: {e}")
        return None


def fetch_weather(city: str, state: str, api_key: str = "") -> Optional[Dict[str, Any]]:
    """
    Fetch current weather via Open-Meteo. `api_key` is accepted but unused -
    kept so existing call sites don't need to change; Open-Meteo needs no key.

    Returns the same dict shape the old OpenWeatherMap-based version did, so
    matrix_display_controller.py's rendering code needs no changes.
    """
    try:
        coords = _geocode(city, state)
        if not coords:
            return None
        lat, lon = coords

        response = requests.get(
            _FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                           "wind_speed_10m,weather_code,is_day",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": "auto",
            },
            timeout=5,
        )
        response.raise_for_status()
        current = response.json().get("current", {})

        code = current.get("weather_code", 0)
        is_day = bool(current.get("is_day", 1))

        return {
            "city": city,
            "temp": round(current.get("temperature_2m", 0)),
            "feels_like": round(current.get("apparent_temperature", 0)),
            "condition": _WMO_CONDITIONS.get(code, "Unknown"),
            "description": _WMO_DESCRIPTIONS.get(code, ""),
            "humidity": round(current.get("relative_humidity_2m", 0)),
            "wind_speed": round(current.get("wind_speed_10m", 0)),
            "is_day": is_day,
            "sunrise": None,
            "sunset": None,
        }

    except Exception as e:
        logger.error(f"Error fetching weather for {city}, {state}: {e}")
        return None
