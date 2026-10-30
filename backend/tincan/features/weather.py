"""Current weather from Open-Meteo (no API key), cached for 30 minutes."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import httpx

from tincan.features.base import Feature
from tincan.tts import prompts

if TYPE_CHECKING:
    from tincan.runtime import Runtime

log = logging.getLogger(__name__)

CACHE_SECONDS = 30 * 60
API = "https://api.open-meteo.com/v1/forecast"

WMO_CONDITIONS = {
    0: "sunny",
    1: "mostly sunny",
    2: "partly cloudy",
    3: "cloudy",
    45: "foggy",
    48: "foggy",
    51: "drizzly",
    53: "drizzly",
    55: "drizzly",
    61: "rainy",
    63: "rainy",
    65: "very rainy",
    71: "snowy",
    73: "snowy",
    75: "very snowy",
    80: "showery",
    81: "showery",
    82: "stormy",
    95: "stormy",
    96: "stormy",
    99: "stormy",
}


class WeatherFeature(Feature):
    kind = "weather"

    def __init__(self) -> None:
        self._cache: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}
        self.fetch = self._fetch  # tests swap this

    async def _fetch(self, lat: float, lon: float) -> dict[str, Any]:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weather_code",
            "daily": "temperature_2m_max",
            "temperature_unit": "fahrenheit",
            "forecast_days": 1,
            "timezone": "auto",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(API, params=params)
            r.raise_for_status()
            return r.json()

    async def data(self, lat: float, lon: float) -> dict[str, Any]:
        key = (round(lat, 2), round(lon, 2))
        hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
            return hit[1]
        data = await self.fetch(lat, lon)
        self._cache[key] = (time.monotonic(), data)
        return data

    async def text(self, rt: Runtime, config: dict[str, Any]) -> str:
        loc = rt.settings().weather_location
        try:
            d = await self.data(loc.lat, loc.lon)
            current = d["current"]
            temp = round(current["temperature_2m"])
            condition = WMO_CONDITIONS.get(int(current.get("weather_code", 0)), "cloudy")
            high = round(d["daily"]["temperature_2m_max"][0])
        except Exception as exc:  # noqa: BLE001 - network is optional
            log.warning("weather unavailable: %s", exc)
            return prompts.WEATHER_UNAVAILABLE
        place = config.get("place") or loc.name or "home"
        return prompts.WEATHER.format(place=place, temp=temp, condition=condition, high=high)
