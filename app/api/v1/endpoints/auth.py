from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi_users import FastAPIUsers

from app.db.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.auth.backend import auth_backend
from app.services.auth.users import UserManager, get_user_manager

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

router = APIRouter()

# Auth endpoints
router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/jwt",
    tags=["auth"],
)

# Register endpoint
router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    tags=["auth"],
)

# Verify endpoint
router.include_router(
    fastapi_users.get_verify_router(UserRead),
    tags=["auth"],
)

# Reset password endpoint
router.include_router(
    fastapi_users.get_reset_password_router(),
    tags=["auth"],
)

# Current user dependency
current_active_user = fastapi_users.current_user(active=True)
