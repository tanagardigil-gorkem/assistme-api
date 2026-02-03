import pytest

from app.main import create_app


@pytest.mark.asyncio
async def test_dashboard_myday_success():
    app = create_app()

    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/dashboard/myday", params={"timezone": "UTC"})
        assert r.status_code == 200
        body = r.json()
        assert "day" in body
        assert "timezone" in body
        assert "generated_at" in body
        assert "tasks" in body
