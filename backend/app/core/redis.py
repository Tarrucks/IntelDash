"""Redis client + a small helper for short-circuiting in tests.

We don't use ``aioredis`` because the rest of the app is sync — keeping
one paradigm avoids accidental blocking inside an async route.
"""

from __future__ import annotations

from functools import lru_cache

import redis

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    settings = get_settings()
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)
