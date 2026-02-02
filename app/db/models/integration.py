from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum as SQLEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.integration_token import IntegrationToken
    from app.db.models.user import User


class ProviderType(str, Enum):
    GMAIL = "gmail"
    SLACK = "slack"
    NOTION = "notion"
    MICROSOFT = "microsoft"


class IntegrationStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider_type: Mapped[ProviderType] = mapped_column(
        SQLEnum(ProviderType), nullable=False
    )
    status: Mapped[IntegrationStatus] = mapped_column(
        SQLEnum(IntegrationStatus), default=IntegrationStatus.ACTIVE, nullable=False
    )
    config: Mapped[dict | None] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="integrations")
    tokens: Mapped[list["IntegrationToken"]] = relationship(
        "IntegrationToken", back_populates="integration", cascade="all, delete-orphan"
    )
