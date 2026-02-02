from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

from app.schemas.dashboard import DashboardMorningResponse, MoodBlock
from app.services.news.rss import get_top_news
from app.services.weather.open_meteo import get_current_weather


def _mood_block() -> MoodBlock:
    # Intentionally short and action-oriented: it should feel supportive, not overwhelming.
    return MoodBlock(
        affirmation="You don't have to do everything today — just the next right thing.",
        focus_prompt="Pick one small win for the next 20 minutes. What is it?",
    )


async def get_daily_feed(*, lat: float, lon: float, timezone: str, news_limit: int, q: str | None):
    weather = await get_current_weather(lat=lat, lon=lon, timezone=timezone)
    news = await get_top_news(limit=news_limit, q=q, sources=None)
    return DashboardMorningResponse(
        generated_at=datetime.now(dt_timezone.utc),
        weather=weather,
        news=news.items,
        mood=_mood_block(),
    )
