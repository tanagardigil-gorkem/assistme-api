import pytest
import respx
from httpx import Response

from app.core.config import DEFAULT_RSS_FEEDS
from app.main import create_app


@pytest.mark.asyncio
async def test_news_top_success():
    app = create_app()

    feed_xml = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<rss version='2.0'><channel><title>Example Feed</title>"
        "<item><title>Hello</title><link>https://example.com/1</link><description>World</description></item>"
        "</channel></rss>"
    )

    with respx.mock:
        # Mock all default feeds with same payload.
        for url in DEFAULT_RSS_FEEDS:
            respx.get(url).mock(return_value=Response(200, content=feed_xml.encode("utf-8")))

        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/v1/news/top", params={"limit": 5})
            assert r.status_code == 200
            body = r.json()
            assert body["items"]
            assert body["items"][0]["headline"]
            assert body["items"][0]["url"].startswith("https://")
