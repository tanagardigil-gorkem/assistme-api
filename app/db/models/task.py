from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, Enum as SQLEnum, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


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


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("user_id", "source_type", "source_id", name="uq_tasks_source"),
        Index("ix_tasks_user_scheduled_start", "user_id", "scheduled_start"),
        Index("ix_tasks_user_scheduled_date", "user_id", "scheduled_date"),
        Index("ix_tasks_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    topic: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus), default=TaskStatus.SCHEDULED, nullable=False
    )
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    badge: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scheduled_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scheduled_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delayed_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_type: Mapped[TaskSourceType] = mapped_column(
        SQLEnum(TaskSourceType), default=TaskSourceType.MANUAL, nullable=False
    )
    source_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )
