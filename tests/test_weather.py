import pytest
import respx
from httpx import Response

from app.main import create_app


@pytest.mark.asyncio
async def test_weather_current_success():
    app = create_app()

    with respx.mock:
        respx.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=Response(
                200,
                json={
                    "current": {
                        "temperature_2m": 12.3,
                        "apparent_temperature": 11.1,
                        "precipitation": 0.0,
                        "weather_code": 2,
                        "wind_speed_10m": 3.0,
                    }
                },
            )
        )

        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/v1/weather/current", params={"lat": 40.0, "lon": 29.0, "timezone": "UTC"})
            assert r.status_code == 200
            body = r.json()
            assert body["location"]["lat"] == 40.0
            assert body["current"]["temp_c"] == 12.3
            assert body["current"]["condition_text"]
