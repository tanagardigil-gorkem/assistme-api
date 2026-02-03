from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EmailSyncStatus(str, Enum):
    IDLE = "idle"
    SYNCING = "syncing"
    ERROR = "error"


class EmailSyncState(Base):
    __tablename__ = "email_sync_state"

    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integrations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_page_token: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[EmailSyncStatus] = mapped_column(
        SQLEnum(EmailSyncStatus), default=EmailSyncStatus.IDLE, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    integration = relationship("Integration", backref="email_sync_state", uselist=False)
