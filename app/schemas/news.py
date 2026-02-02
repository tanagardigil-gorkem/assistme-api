from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    headline: str
    url: str
    source: str
    published_at: datetime | None = None
    summary: str | None = None


class NewsTopResponse(BaseModel):
    items: list[NewsItem]
    generated_at: datetime
    sources: list[str] = Field(default_factory=list)
