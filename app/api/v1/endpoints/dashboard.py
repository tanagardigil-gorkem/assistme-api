from fastapi import APIRouter, Query

from app.schemas.dashboard import DashboardMorningResponse
from app.services.dashboard.morning import get_morning_dashboard


router = APIRouter()


@router.get("/morning", response_model=DashboardMorningResponse)
async def morning_dashboard(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    timezone: str = Query(..., min_length=1, max_length=64),
    limit: int = Query(10, ge=1, le=50),
    q: str | None = Query(None, min_length=1, max_length=120),
):
    return await get_morning_dashboard(lat=lat, lon=lon, timezone=timezone, news_limit=limit, q=q)
