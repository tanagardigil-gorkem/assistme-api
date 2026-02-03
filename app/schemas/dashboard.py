from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.news import NewsItem
from app.schemas.task import TaskItem
from app.schemas.weather import WeatherCurrentResponse


class MoodBlock(BaseModel):
    affirmation: str
    focus_prompt: str


class DashboardMyDayResponse(BaseModel):
    day: date
    timezone: str
    generated_at: datetime
    title: str = "Generated Day"
    subtitle: str | None = "AI-Optimized Schedule"
    flow_label: str | None = None
    tasks: list[TaskItem] = Field(default_factory=list)


class DashboardMorningResponse(BaseModel):
    generated_at: datetime
    weather: WeatherCurrentResponse
    news: list[NewsItem]
    mood: MoodBlock
    myday: DashboardMyDayResponse
