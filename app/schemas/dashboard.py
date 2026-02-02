from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.news import NewsItem
from app.schemas.weather import WeatherCurrentResponse


class MoodBlock(BaseModel):
    affirmation: str
    focus_prompt: str


class DashboardMorningResponse(BaseModel):
    generated_at: datetime
    weather: WeatherCurrentResponse
    news: list[NewsItem]
    mood: MoodBlock
