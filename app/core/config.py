from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://apnews.com/hub/ap-top-news?output=rss",
    "https://www.reutersagency.com/feed/?best-topics=top-news&post_type=best",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ASSISTME_",
        case_sensitive=False,
    )

    cors_origins: list[str] = Field(default_factory=list)
    http_timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)
    http_retries: int = Field(default=2, ge=0, le=5)
    http_retry_backoff_seconds: float = Field(default=0.35, ge=0.0, le=5.0)

    rss_feeds: list[str] = Field(default_factory=lambda: list(DEFAULT_RSS_FEEDS))
    rss_ttl_seconds: int = Field(default=1200, ge=60, le=86400)
    weather_ttl_seconds: int = Field(default=600, ge=60, le=86400)

    def model_post_init(self, __context: Any) -> None:
        # Allow ASSISTME_CORS_ORIGINS as JSON array or comma-separated string.
        raw_cors = getattr(self, "cors_origins", None)
        if isinstance(raw_cors, str):
            parsed = raw_cors.strip()
            if parsed.startswith("["):
                try:
                    self.cors_origins = [str(x).strip() for x in json.loads(parsed) if str(x).strip()]
                except Exception:
                    self.cors_origins = [s.strip() for s in parsed.split(",") if s.strip()]
            else:
                self.cors_origins = [s.strip() for s in parsed.split(",") if s.strip()]

        # Allow ASSISTME_RSS_FEEDS as JSON array or comma-separated string.
        raw = getattr(self, "rss_feeds", None)
        if isinstance(raw, str):
            parsed = raw.strip()
            if parsed.startswith("["):
                try:
                    self.rss_feeds = [str(x).strip() for x in json.loads(parsed) if str(x).strip()]
                except Exception:
                    self.rss_feeds = [s.strip() for s in parsed.split(",") if s.strip()]
            else:
                self.rss_feeds = [s.strip() for s in parsed.split(",") if s.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
