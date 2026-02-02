from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WeatherLocation(BaseModel):
    lat: float
    lon: float
    timezone: str


class WeatherCurrent(BaseModel):
    temp_c: float = Field(..., description="Air temperature (C).")
    feels_like_c: float | None = Field(None, description="Apparent temperature (C).")
    wind_kph: float | None = Field(None, description="Wind speed (km/h).")
    precipitation_mm: float | None = Field(None, description="Precipitation (mm).")
    condition_code: int | None = Field(None, description="Open-Meteo weather code.")
    condition_text: str | None = Field(None, description="Human-friendly condition.")


class WeatherCurrentResponse(BaseModel):
    location: WeatherLocation
    current: WeatherCurrent
    generated_at: datetime
