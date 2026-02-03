from __future__ import annotations

import re
from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TaskPresetTag(str, Enum):
    BRIEFING = "briefing"
    FAMILY = "family"
    PAYMENT = "payment"
    BILL = "bill"
    EMAIL = "email"
    WORK = "work"
    FOCUS = "focus"
    HEALTH = "health"
    ERRAND = "errand"
    HOME = "home"
    ADMIN = "admin"
    LEARNING = "learning"


class TaskStatus(str, Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    DELAYED = "delayed"
    SKIPPED = "skipped"


class TaskSourceType(str, Enum):
    MANUAL = "manual"
    GENERATED = "generated"
    EMAIL = "email"
    CALENDAR = "calendar"
    INTEGRATION = "integration"
    OTHER = "other"


class TaskBase(BaseModel):
    topic: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    badge: str | None = None
    status: TaskStatus = TaskStatus.SCHEDULED
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    is_all_day: bool = False
    scheduled_date: date | None = None
    delayed_until: datetime | None = None
    completed_at: datetime | None = None
    source_type: TaskSourceType = TaskSourceType.MANUAL
    source_id: str | None = None
    source_metadata: dict | None = None

    @field_validator("description")
    @classmethod
    def _validate_description_paragraphs(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            return value
        paragraphs = [p for p in re.split(r"\n\s*\n", stripped) if p.strip()]
        if len(paragraphs) > 2:
            raise ValueError("description must be no more than 2 paragraphs")
        return value

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for tag in value:
            trimmed = tag.strip()
            if not trimmed:
                raise ValueError("tags cannot contain empty values")
            cleaned.append(trimmed)
        return cleaned

    @model_validator(mode="after")
    def _validate_task_fields(self) -> "TaskBase":
        if self.status == TaskStatus.COMPLETED and self.completed_at is None:
            raise ValueError("completed_at is required when status is completed")
        if self.status == TaskStatus.DELAYED and self.delayed_until is None:
            raise ValueError("delayed_until is required when status is delayed")
        if self.scheduled_end is not None:
            if self.scheduled_start is None:
                raise ValueError("scheduled_start is required when scheduled_end is set")
            if self.scheduled_end < self.scheduled_start:
                raise ValueError("scheduled_end must be after scheduled_start")
        if self.is_all_day and self.scheduled_date is None:
            raise ValueError("scheduled_date is required when is_all_day is true")
        if self.scheduled_date is not None and not self.is_all_day:
            raise ValueError("is_all_day must be true when scheduled_date is set")
        return self


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    topic: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    badge: str | None = None
    status: TaskStatus | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    is_all_day: bool | None = None
    scheduled_date: date | None = None
    delayed_until: datetime | None = None
    completed_at: datetime | None = None
    source_type: TaskSourceType | None = None
    source_id: str | None = None
    source_metadata: dict | None = None

    @field_validator("description")
    @classmethod
    def _validate_description_paragraphs(cls, value: str | None) -> str | None:
        return TaskBase._validate_description_paragraphs(value)

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        return TaskBase._normalize_tags(value)


class TaskItem(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID


class TaskResponse(TaskItem):
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
