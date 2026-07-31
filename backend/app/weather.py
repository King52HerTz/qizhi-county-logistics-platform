from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx

from app.schemas import CurrentWeather


WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
QIDONG_CENTER = {"latitude": 26.769788, "longitude": 112.058674}
CACHE_TTL_SECONDS = 600

_cached_weather: CurrentWeather | None = None
_cached_at = 0.0


class WeatherServiceError(RuntimeError):
    pass


def weather_label(code: int) -> str:
    if code == 0:
        return "晴"
    if code in {1, 2}:
        return "少云"
    if code == 3:
        return "阴"
    if code in {45, 48}:
        return "有雾"
    if code in {51, 53, 55, 56, 57}:
        return "毛毛雨"
    if code in {61, 63, 65, 66, 67, 80, 81, 82}:
        return "有雨"
    if code in {71, 73, 75, 77, 85, 86}:
        return "有雪"
    if code in {95, 96, 99}:
        return "雷雨"
    return "天气变化"


async def get_current_weather() -> CurrentWeather:
    global _cached_at, _cached_weather
    now = time.monotonic()
    if _cached_weather is not None and now - _cached_at < CACHE_TTL_SECONDS:
        return _cached_weather.model_copy(update={"cached": True})

    params = {
        **QIDONG_CENTER,
        "current": (
            "temperature_2m,apparent_temperature,relative_humidity_2m,"
            "weather_code,wind_speed_10m"
        ),
        "timezone": "Asia/Shanghai",
    }
    try:
        async with httpx.AsyncClient(timeout=6, follow_redirects=True) as client:
            response = await client.get(WEATHER_API_URL, params=params)
            response.raise_for_status()
        current = response.json()["current"]
        result = CurrentWeather(
            location="祁东县",
            temperature_c=round(float(current["temperature_2m"]), 1),
            apparent_temperature_c=round(float(current["apparent_temperature"]), 1),
            humidity_percent=int(current["relative_humidity_2m"]),
            weather_code=int(current["weather_code"]),
            weather_label=weather_label(int(current["weather_code"])),
            wind_speed_kmh=round(float(current["wind_speed_10m"]), 1),
            observed_at=str(current["time"]),
            fetched_at=datetime.now(timezone.utc),
            source="Open-Meteo",
            cached=False,
            stale=False,
        )
        _cached_weather = result
        _cached_at = now
        return result
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        if _cached_weather is not None:
            return _cached_weather.model_copy(update={"cached": True, "stale": True})
        raise WeatherServiceError("实时天气服务暂不可用") from exc


def clear_weather_cache() -> None:
    global _cached_at, _cached_weather
    _cached_weather = None
    _cached_at = 0.0
