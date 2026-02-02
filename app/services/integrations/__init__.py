from __future__ import annotations

# Import to register providers
from app.services.integrations import gmail  # noqa: F401
from app.services.integrations.base import BaseIntegrationService
from app.services.integrations.oauth import OAuthService
from app.services.integrations.registry import (
    get_provider_service,
    list_available_providers,
    register_provider,
)

__all__ = [
    "BaseIntegrationService",
    "OAuthService",
    "register_provider",
    "get_provider_service",
    "list_available_providers",
]
