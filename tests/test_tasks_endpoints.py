import pytest

from app.main import create_app


@pytest.mark.asyncio
async def test_tasks_crud_flow():
    app = create_app()

    from httpx import ASGITransport, AsyncClient

    payload = {
        "topic": "Pay electricity bill",
        "description": "Schedule and pay the bill.",
        "tags": ["bill", "payment", "testtag"],
        "status": "scheduled",
        "scheduled_start": "2024-01-01T10:00:00Z",
        "scheduled_end": "2024-01-01T10:30:00Z",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/api/v1/tasks", json=payload)
        assert create_resp.status_code == 200
        created = create_resp.json()
        task_id = created["id"]

        get_resp = await client.get(f"/api/v1/tasks/{task_id}")
        assert get_resp.status_code == 200

        update_resp = await client.patch(
            f"/api/v1/tasks/{task_id}",
            json={
                "status": "completed",
                "completed_at": "2024-01-01T11:00:00Z",
            },
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == "completed"

        list_resp = await client.get(
            "/api/v1/tasks",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-01-01",
                "tags": ["testtag"],
            },
        )
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert any(item["id"] == task_id for item in items)

        delete_resp = await client.delete(f"/api/v1/tasks/{task_id}")
        assert delete_resp.status_code == 200

        missing_resp = await client.get(f"/api/v1/tasks/{task_id}")
        assert missing_resp.status_code == 404
