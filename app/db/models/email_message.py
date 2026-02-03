from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EmailMessage(Base):
    __tablename__ = "email_messages"
    __table_args__ = (
        UniqueConstraint("integration_id", "provider_message_id", name="uq_email_integration_message"),
        Index("ix_email_integration_date", "integration_id", "date_ts"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_message_id: Mapped[str] = mapped_column(String(256), nullable=False)
    thread_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    from_address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    to_address: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    date: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    labels: Mapped[list[str] | None] = mapped_column(JSONB, default=list)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw_payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    integration = relationship("Integration", backref="email_messages")
