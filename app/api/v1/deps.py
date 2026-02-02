from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import Depends

from app.core.config import get_settings

if TYPE_CHECKING:
    from app.db.models.user import User

_settings = get_settings()

# Development user - used when dev_mode is enabled
DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def get_dev_user() -> "User":
    """Return a mock user for development."""
    from app.db.models.user import User

    return User(
        id=DEV_USER_ID,
        email="dev@example.com",
        hashed_password="",
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )


async def get_current_user():
    """Get current user - returns dev user in dev mode, otherwise requires JWT."""
    from app.api.v1.endpoints.auth import current_active_user

    if _settings.dev_mode:
        return await get_dev_user()

    return await current_active_user()
