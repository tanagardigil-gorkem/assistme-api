from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.http import create_http_client, set_http_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    client = create_http_client(settings)
    set_http_client(client)
    try:
        yield
    finally:
        await client.aclose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="assist me api",
        version="0.1.0",
        lifespan=lifespan,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )

    app.include_router(api_v1_router, prefix="/api/v1")
    return app


app = create_app()
