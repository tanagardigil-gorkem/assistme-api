from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.integration import IntegrationStatus


class BaseIntegrationService(ABC):
    """Abstract base class for all integration services."""

    provider_type: str

    @abstractmethod
    async def execute(
        self,
        session: "AsyncSession",
        integration_id: uuid.UUID,
        action: str,
        params: dict,
        integration_config: dict | None = None,
    ) -> Any:
        """Execute an action on the integration."""
        pass

    @abstractmethod
    async def refresh_token(self, session: "AsyncSession", integration_id: uuid.UUID) -> bool:
        """Refresh the access token if expired."""
        pass

    async def health_check(self, session: "AsyncSession", integration_id: uuid.UUID) -> bool:
        """Check if the integration is healthy."""
        return True
