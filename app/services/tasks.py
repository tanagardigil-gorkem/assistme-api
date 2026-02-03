from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Iterable
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.task import (
    Task,
    TaskSourceType as DbTaskSourceType,
    TaskStatus as DbTaskStatus,
)
from app.schemas.task import TaskCreate, TaskStatus, TaskUpdate, TaskSourceType


def _resolve_timezone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except Exception:
        return ZoneInfo("UTC")


def _date_range_to_datetimes(
    *,
    start_date: date,
    end_date: date,
    timezone: str,
) -> tuple[datetime, datetime]:
    tz = _resolve_timezone(timezone)
    start_dt = datetime.combine(start_date, time.min, tzinfo=tz)
    end_dt = datetime.combine(end_date, time.min, tzinfo=tz) + timedelta(days=1)
    return start_dt, end_dt


def _merge_task_fields(task: Task, updates: TaskUpdate) -> dict:
    data = {
        "topic": task.topic,
        "description": task.description,
        "tags": list(task.tags or []),
        "badge": task.badge,
        "status": TaskStatus(task.status.value),
        "scheduled_start": task.scheduled_start,
        "scheduled_end": task.scheduled_end,
        "is_all_day": task.is_all_day,
        "scheduled_date": task.scheduled_date,
        "delayed_until": task.delayed_until,
        "completed_at": task.completed_at,
        "source_type": TaskSourceType(task.source_type.value),
        "source_id": task.source_id,
        "source_metadata": task.source_metadata,
    }
    update_data = updates.model_dump(exclude_unset=True)
    data.update(update_data)
    return data


async def create_task(*, user_id: UUID, data: TaskCreate, session: AsyncSession) -> Task:
    task = Task(
        user_id=user_id,
        topic=data.topic,
        description=data.description,
        tags=data.tags,
        badge=data.badge,
        status=DbTaskStatus(data.status.value),
        scheduled_start=data.scheduled_start,
        scheduled_end=data.scheduled_end,
        is_all_day=data.is_all_day,
        scheduled_date=data.scheduled_date,
        delayed_until=data.delayed_until,
        completed_at=data.completed_at,
        source_type=DbTaskSourceType(data.source_type.value),
        source_id=data.source_id,
        source_metadata=data.source_metadata,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def get_task(*, user_id: UUID, task_id: UUID, session: AsyncSession) -> Task | None:
    result = await session.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_task(
    *,
    user_id: UUID,
    task_id: UUID,
    updates: TaskUpdate,
    session: AsyncSession,
) -> Task | None:
    task = await get_task(user_id=user_id, task_id=task_id, session=session)
    if not task:
        return None

    merged = _merge_task_fields(task, updates)
    TaskCreate.model_validate(merged)

    update_data = updates.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] is not None:
        update_data["status"] = DbTaskStatus(update_data["status"].value)
    if "source_type" in update_data and update_data["source_type"] is not None:
        update_data["source_type"] = DbTaskSourceType(update_data["source_type"].value)

    for field, value in update_data.items():
        setattr(task, field, value)

    await session.commit()
    await session.refresh(task)
    return task


async def delete_task(*, user_id: UUID, task_id: UUID, session: AsyncSession) -> bool:
    task = await get_task(user_id=user_id, task_id=task_id, session=session)
    if not task:
        return False
    await session.delete(task)
    await session.commit()
    return True


async def list_tasks(
    *,
    user_id: UUID,
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
    timezone: str = "UTC",
    status: TaskStatus | None = None,
    tags: Iterable[str] | None = None,
    include_unscheduled: bool = False,
) -> list[Task]:
    stmt = select(Task).where(Task.user_id == user_id)

    if status is not None:
        stmt = stmt.where(Task.status == DbTaskStatus(status.value))

    if tags:
        for tag in tags:
            stmt = stmt.where(Task.tags.contains([tag]))

    if start_date or end_date:
        effective_start = start_date or end_date
        effective_end = end_date or start_date
        if effective_start is not None and effective_end is not None:
            start_dt, end_dt = _date_range_to_datetimes(
                start_date=effective_start,
                end_date=effective_end,
                timezone=timezone,
            )
            timed_range = and_(
                Task.scheduled_start.is_not(None),
                Task.scheduled_start >= start_dt,
                Task.scheduled_start < end_dt,
            )
            all_day_range = and_(
                Task.is_all_day.is_(True),
                Task.scheduled_date.is_not(None),
                Task.scheduled_date >= effective_start,
                Task.scheduled_date <= effective_end,
            )
            if include_unscheduled:
                unscheduled = and_(
                    Task.is_all_day.is_(False),
                    Task.scheduled_start.is_(None),
                )
                stmt = stmt.where(or_(timed_range, all_day_range, unscheduled))
            else:
                stmt = stmt.where(or_(timed_range, all_day_range))
    elif not include_unscheduled:
        stmt = stmt.where(
            or_(
                Task.scheduled_start.is_not(None),
                Task.is_all_day.is_(True),
            )
        )

    stmt = stmt.order_by(
        Task.scheduled_start.asc().nulls_last(),
        Task.scheduled_date.asc().nulls_last(),
        Task.created_at.asc(),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_tasks_for_range(
    *,
    user_id: UUID,
    start_date: date,
    end_date: date,
    timezone: str,
    session: AsyncSession,
) -> list[Task]:
    return await list_tasks(
        user_id=user_id,
        session=session,
        start_date=start_date,
        end_date=end_date,
        timezone=timezone,
        include_unscheduled=False,
    )


async def ensure_generated_tasks(
    *,
    user_id: UUID,
    day: date,
    timezone: str,
    session: AsyncSession,
) -> None:
    existing = await list_tasks_for_range(
        user_id=user_id,
        start_date=day,
        end_date=day,
        timezone=timezone,
        session=session,
    )
    if existing:
        return

    tz = _resolve_timezone(timezone)
    stub_tasks = [
        TaskCreate(
            topic="Coffee & AI Briefing",
            description="Summary of 14 emails and 3 curated news updates.",
            tags=["briefing", "email"],
            badge="AI BRIEFING",
            status=TaskStatus.SCHEDULED,
            scheduled_start=datetime.combine(day, time(8, 0), tzinfo=tz),
            scheduled_end=datetime.combine(day, time(8, 30), tzinfo=tz),
            source_type=TaskSourceType.GENERATED,
            source_id=f"myday:{day.isoformat()}:briefing",
        ),
        TaskCreate(
            topic="Project Focus: Design Sprint",
            description="Deep work block. Auto-silencing notifications.",
            tags=["work", "focus"],
            badge="HIGH ENERGY",
            status=TaskStatus.SCHEDULED,
            scheduled_start=datetime.combine(day, time(9, 0), tzinfo=tz),
            scheduled_end=datetime.combine(day, time(11, 0), tzinfo=tz),
            source_type=TaskSourceType.GENERATED,
            source_id=f"myday:{day.isoformat()}:focus",
        ),
        TaskCreate(
            topic="School Pickup",
            tags=["family", "errand"],
            status=TaskStatus.SCHEDULED,
            scheduled_start=datetime.combine(day, time(15, 0), tzinfo=tz),
            scheduled_end=datetime.combine(day, time(15, 30), tzinfo=tz),
            source_type=TaskSourceType.GENERATED,
            source_id=f"myday:{day.isoformat()}:pickup",
        ),
    ]

    tasks = [
        Task(
            user_id=user_id,
            topic=task.topic,
            description=task.description,
            tags=task.tags,
            badge=task.badge,
            status=DbTaskStatus(task.status.value),
            scheduled_start=task.scheduled_start,
            scheduled_end=task.scheduled_end,
            is_all_day=task.is_all_day,
            scheduled_date=task.scheduled_date,
            delayed_until=task.delayed_until,
            completed_at=task.completed_at,
            source_type=DbTaskSourceType(task.source_type.value),
            source_id=task.source_id,
            source_metadata=task.source_metadata,
        )
        for task in stub_tasks
    ]
    session.add_all(tasks)
    await session.commit()
