import pytest
import respx
from httpx import Response

from app.core.config import DEFAULT_RSS_FEEDS
from app.main import create_app


@pytest.mark.asyncio
async def test_dashboard_morning_success():
    app = create_app()

    feed_xml = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<rss version='2.0'><channel><title>Example Feed</title>"
        "<item><title>Hello</title><link>https://example.com/1</link><description>World</description></item>"
        "</channel></rss>"
    )

    with respx.mock:
        respx.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=Response(
                200,
                json={
                    "current": {
                        "temperature_2m": 20.0,
                        "apparent_temperature": 19.5,
                        "precipitation": 0.0,
                        "weather_code": 0,
                        "wind_speed_10m": 2.0,
                    }
                },
            )
        )
        for url in DEFAULT_RSS_FEEDS:
            respx.get(url).mock(return_value=Response(200, content=feed_xml.encode("utf-8")))

        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                "/api/v1/dashboard/morning",
                params={"lat": 40.0, "lon": 29.0, "timezone": "UTC", "limit": 5},
            )
            assert r.status_code == 200
            body = r.json()
            assert "weather" in body
            assert "news" in body
            assert "mood" in body
