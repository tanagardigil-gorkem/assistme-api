from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_async_session
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskStatus, TaskUpdate
from app.services.tasks import (
    create_task,
    delete_task,
    get_task,
    list_tasks,
    update_task,
)


router = APIRouter()


@router.post("/", response_model=TaskResponse)
async def create_task_endpoint(
    payload: TaskCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    task = await create_task(user_id=user.id, data=payload, session=session)
    return TaskResponse.model_validate(task)


@router.get("/", response_model=TaskListResponse)
async def list_tasks_endpoint(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    timezone: str = Query("UTC", min_length=1, max_length=64),
    status: TaskStatus | None = Query(None),
    tags: list[str] | None = Query(None),
    include_unscheduled: bool = Query(False),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    tasks = await list_tasks(
        user_id=user.id,
        session=session,
        start_date=start_date,
        end_date=end_date,
        timezone=timezone,
        status=status,
        tags=tags,
        include_unscheduled=include_unscheduled,
    )
    return TaskListResponse(items=[TaskResponse.model_validate(task) for task in tasks])


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_endpoint(
    task_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    task = await get_task(user_id=user.id, task_id=task_id, session=session)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task_endpoint(
    task_id: UUID,
    payload: TaskUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    task = await update_task(
        user_id=user.id,
        task_id=task_id,
        updates=payload,
        session=session,
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}")
async def delete_task_endpoint(
    task_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    deleted = await delete_task(user_id=user.id, task_id=task_id, session=session)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True}
