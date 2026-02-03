from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_async_session
from app.schemas.dashboard import DashboardMorningResponse, DashboardMyDayResponse
from app.services.dashboard.daily_feed import get_daily_feed
from app.services.dashboard.myday import get_myday_briefing


router = APIRouter()


@router.get("/daily-feed", response_model=DashboardMorningResponse)
async def daily_feed(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    timezone: str = Query(..., min_length=1, max_length=64),
    limit: int = Query(10, ge=1, le=50),
    q: str | None = Query(None, min_length=1, max_length=120),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await get_daily_feed(
        user_id=user.id,
        session=session,
        lat=lat,
        lon=lon,
        timezone=timezone,
        news_limit=limit,
        q=q,
    )


@router.get("/myday", response_model=DashboardMyDayResponse)
async def myday_briefing(
    timezone: str = Query(..., min_length=1, max_length=64),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await get_myday_briefing(
        user_id=user.id,
        timezone=timezone,
        start_date=start_date,
        end_date=end_date,
        session=session,
    )
