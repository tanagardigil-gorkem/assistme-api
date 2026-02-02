from fastapi import APIRouter, Query

from app.schemas.dashboard import DashboardMorningResponse
from app.services.dashboard.daily_feed import get_daily_feed


router = APIRouter()


@router.get("/daily-feed", response_model=DashboardMorningResponse)
async def daily_feed(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    timezone: str = Query(..., min_length=1, max_length=64),
    limit: int = Query(10, ge=1, le=50),
    q: str | None = Query(None, min_length=1, max_length=120),
):
    return await get_daily_feed(lat=lat, lon=lon, timezone=timezone, news_limit=limit, q=q)
