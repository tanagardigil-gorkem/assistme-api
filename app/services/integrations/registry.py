from __future__ import annotations

from typing import Type

from app.services.integrations.base import BaseIntegrationService

# Registry mapping provider types to service classes
_provider_registry: dict[str, Type[BaseIntegrationService]] = {}


def register_provider(provider_type: str):
    """Decorator to register a provider service."""

    def decorator(cls: Type[BaseIntegrationService]):
        _provider_registry[provider_type] = cls
        cls.provider_type = provider_type
        return cls

    return decorator


def get_provider_service(provider_type: str) -> Type[BaseIntegrationService] | None:
    """Get the service class for a provider type."""
    return _provider_registry.get(provider_type)


def list_available_providers() -> list[dict]:
    """List all available provider types with metadata."""
    providers = []
    for provider_type in _provider_registry.keys():
        providers.append(
            {
                "provider_type": provider_type,
                "name": provider_type.capitalize(),
                "description": f"Connect to {provider_type.capitalize()}",
            }
        )
    return providers
