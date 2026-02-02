from __future__ import annotations

import asyncio
from typing import Optional

import httpx

from app.core.config import Settings


_client: Optional[httpx.AsyncClient] = None


def create_http_client(settings: Settings) -> httpx.AsyncClient:
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
    timeout = httpx.Timeout(settings.http_timeout_seconds)
    return httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        headers={"User-Agent": "assistme-api/0.1"},
        follow_redirects=True,
    )


def set_http_client(client: httpx.AsyncClient) -> None:
    global _client
    _client = client


def get_http_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("HTTP client not initialized. Did you start the FastAPI app?")
    return _client


async def request_with_retries(
    client: httpx.AsyncClient,
    *,
    method: str,
    url: str,
    retries: int,
    backoff_seconds: float,
    **kwargs,
) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = await client.request(method, url, **kwargs)
            if resp.status_code in {429, 500, 502, 503, 504} and attempt < retries:
                await asyncio.sleep(backoff_seconds * (2**attempt))
                continue
            return resp
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc
            if attempt >= retries:
                raise
            await asyncio.sleep(backoff_seconds * (2**attempt))
    if last_exc:
        raise last_exc
    raise RuntimeError("request_with_retries failed unexpectedly")
