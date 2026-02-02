from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Hashable, TypeVar

from cachetools import TTLCache

T = TypeVar("T")


@dataclass
class AsyncTTLCache:
    cache: TTLCache
    lock: asyncio.Lock

    async def get_or_set(self, key: Hashable, loader: Callable[[], Any]) -> Any:
        async with self.lock:
            if key in self.cache:
                return self.cache[key]
        value = await loader()
        async with self.lock:
            self.cache[key] = value
        return value


def make_ttl_cache(*, maxsize: int, ttl_seconds: int) -> AsyncTTLCache:
    return AsyncTTLCache(cache=TTLCache(maxsize=maxsize, ttl=ttl_seconds), lock=asyncio.Lock())
