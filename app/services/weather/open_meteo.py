from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

from fastapi import HTTPException

from app.core.cache import make_ttl_cache
from app.core.config import get_settings
from app.core.http import get_http_client, request_with_retries
from app.schemas.weather import WeatherCurrent, WeatherCurrentResponse, WeatherLocation


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


WEATHER_CODE_TEXT = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


_settings = get_settings()
_weather_cache = make_ttl_cache(maxsize=512, ttl_seconds=_settings.weather_ttl_seconds)


async def get_current_weather(*, lat: float, lon: float, timezone: str) -> WeatherCurrentResponse:
    key = (round(lat, 4), round(lon, 4), timezone)

    async def loader() -> WeatherCurrentResponse:
        client = get_http_client()
        settings = get_settings()
        params = {
            "latitude": lat,
            "longitude": lon,
            "timezone": timezone,
            "current": ",".join(
                [
                    "temperature_2m",
                    "apparent_temperature",
                    "precipitation",
                    "weather_code",
                    "wind_speed_10m",
                ]
            ),
        }

        try:
            resp = await request_with_retries(
                client,
                method="GET",
                url=OPEN_METEO_URL,
                params=params,
                retries=settings.http_retries,
                backoff_seconds=settings.http_retry_backoff_seconds,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Weather upstream error: {type(exc).__name__}")

        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Weather upstream status {resp.status_code}")

        data = resp.json()
        cur = data.get("current") or {}
        code = cur.get("weather_code")
        code_int = int(code) if code is not None else None

        wind_ms = cur.get("wind_speed_10m")
        wind_kph = float(wind_ms) * 3.6 if wind_ms is not None else None

        current = WeatherCurrent(
            temp_c=float(cur["temperature_2m"]),
            feels_like_c=float(cur["apparent_temperature"]) if cur.get("apparent_temperature") is not None else None,
            wind_kph=wind_kph,
            precipitation_mm=float(cur["precipitation"]) if cur.get("precipitation") is not None else None,
            condition_code=code_int,
            condition_text=WEATHER_CODE_TEXT.get(code_int) if code_int is not None else None,
        )

        return WeatherCurrentResponse(
            location=WeatherLocation(lat=lat, lon=lon, timezone=timezone),
            current=current,
            generated_at=datetime.now(dt_timezone.utc),
        )

    return await _weather_cache.get_or_set(key, loader)
