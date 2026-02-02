from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1.router import api_v1_router
from app.core.config import Settings, get_settings
from app.core.http import create_http_client, set_http_client
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create dev user if in dev mode
    if settings.dev_mode:
        from sqlalchemy import select
        from app.db.models.user import User
        from app.db.session import async_session_maker
        from app.api.v1.deps import DEV_USER_ID

        async with async_session_maker() as session:
            # Check if dev user exists
            result = await session.execute(
                select(User).where(User.id == DEV_USER_ID)
            )
            dev_user = result.scalar_one_or_none()

            if not dev_user:
                # Create dev user
                dev_user = User(
                    id=DEV_USER_ID,
                    email="dev@example.com",
                    hashed_password="",  # No password for dev user
                    is_active=True,
                    is_superuser=True,
                    is_verified=True,
                )
                session.add(dev_user)
                await session.commit()
                print(f"✓ Dev user created: {dev_user.email} (ID: {dev_user.id})")

    # Setup HTTP client
    client = create_http_client(settings)
    set_http_client(client)

    # Store settings in app state
    app.state.settings = settings

    try:
        yield
    finally:
        await client.aclose()
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()

    # Setup rate limiter
    limiter = Limiter(key_func=get_remote_address)

    app = FastAPI(
        title="assist me api",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(api_v1_router, prefix="/api/v1")
    return app


app = create_app()
