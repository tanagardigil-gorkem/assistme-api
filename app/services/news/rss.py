from __future__ import annotations

import time
from datetime import datetime, timezone as dt_timezone
from urllib.parse import urlparse

import feedparser
from fastapi import HTTPException

from app.core.cache import make_ttl_cache
from app.core.config import get_settings
from app.core.http import get_http_client, request_with_retries
from app.schemas.news import NewsItem, NewsTopResponse


_settings = get_settings()
_rss_cache = make_ttl_cache(maxsize=256, ttl_seconds=_settings.rss_ttl_seconds)


def _best_source_name(feed_url: str, parsed: feedparser.FeedParserDict) -> str:
    title = (parsed.feed.get("title") or "").strip()
    if title:
        return title
    host = urlparse(feed_url).hostname or "source"
    return host


def _parse_datetime(entry: feedparser.FeedParserDict) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            return datetime.fromtimestamp(time.mktime(st), tz=dt_timezone.utc)
    return None


def _normalize_entry(entry: feedparser.FeedParserDict, source: str) -> NewsItem | None:
    title = (entry.get("title") or "").strip()
    link = (entry.get("link") or "").strip()
    if not title or not link:
        return None
    summary = (entry.get("summary") or "").strip() or None
    return NewsItem(
        headline=title,
        url=link,
        source=source,
        published_at=_parse_datetime(entry),
        summary=summary,
    )


def _matches_filters(item: NewsItem, *, q: str | None, sources: list[str] | None) -> bool:
    if sources:
        hay = item.source.casefold()
        if not any(s.casefold() in hay for s in sources):
            return False
    if q:
        needle = q.casefold()
        hay = (item.headline + " " + (item.summary or "")).casefold()
        if needle not in hay:
            return False
    return True


async def _fetch_feed(url: str) -> list[NewsItem]:
    client = get_http_client()
    settings = get_settings()
    try:
        resp = await request_with_retries(
            client,
            method="GET",
            url=url,
            retries=settings.http_retries,
            backoff_seconds=settings.http_retry_backoff_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"News upstream error: {type(exc).__name__}")

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"News upstream status {resp.status_code}")

    parsed = feedparser.parse(resp.content)
    source = _best_source_name(url, parsed)
    items: list[NewsItem] = []
    for entry in parsed.entries or []:
        item = _normalize_entry(entry, source)
        if item:
            items.append(item)
    return items


async def get_top_news(*, limit: int, q: str | None, sources: list[str] | None) -> NewsTopResponse:
    settings = get_settings()
    feeds = settings.rss_feeds
    if not feeds:
        return NewsTopResponse(items=[], generated_at=datetime.now(dt_timezone.utc), sources=[])

    async def loader() -> list[NewsItem]:
        all_items: list[NewsItem] = []
        for feed_url in feeds:
            try:
                all_items.extend(await _fetch_feed(feed_url))
            except HTTPException:
                # One bad feed shouldn't kill the whole dashboard.
                continue

        # Sort newest first when published_at present.
        all_items.sort(key=lambda x: x.published_at or datetime(1970, 1, 1, tzinfo=dt_timezone.utc), reverse=True)
        return all_items

    cache_key = tuple(feeds)
    items = await _rss_cache.get_or_set(cache_key, loader)

    filtered = [it for it in items if _matches_filters(it, q=q, sources=sources)]
    return NewsTopResponse(
        items=filtered[:limit],
        generated_at=datetime.now(dt_timezone.utc),
        sources=sorted({it.source for it in filtered}),
    )
