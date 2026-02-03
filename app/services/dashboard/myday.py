from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.dashboard import DashboardMyDayResponse
from app.schemas.task import TaskItem
from app.services.tasks import ensure_generated_tasks, list_tasks_for_range


def _resolve_timezone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except Exception:
        return ZoneInfo("UTC")


async def get_myday_briefing(
    *,
    user_id: UUID,
    timezone: str,
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> DashboardMyDayResponse:
    tz = _resolve_timezone(timezone)
    now_utc = datetime.now(dt_timezone.utc)
    local_day = now_utc.astimezone(tz).date()
    effective_start = start_date or local_day
    effective_end = end_date or effective_start

    tasks = await list_tasks_for_range(
        user_id=user_id,
        start_date=effective_start,
        end_date=effective_end,
        timezone=timezone,
        session=session,
    )
    if not tasks:
        await ensure_generated_tasks(
            user_id=user_id,
            day=effective_start,
            timezone=timezone,
            session=session,
        )
        tasks = await list_tasks_for_range(
            user_id=user_id,
            start_date=effective_start,
            end_date=effective_end,
            timezone=timezone,
            session=session,
        )

    return DashboardMyDayResponse(
        day=effective_start,
        timezone=timezone,
        generated_at=now_utc,
        title="Generated Day",
        subtitle="AI-Optimized Schedule",
        flow_label="BEST FLOW DETECTED",
        tasks=[TaskItem.model_validate(task) for task in tasks],
    )
