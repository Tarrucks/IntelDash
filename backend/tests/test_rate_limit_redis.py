"""Redis-backed token-bucket smoke test.

Verifies the RedisBucketStore reads what it writes and that the bucket
behaves the same as with the in-memory store. Skipped automatically if
Redis isn't reachable.
"""

from __future__ import annotations

import pytest

from app.core.rate_limit import RateLimitConfig, RedisBucketStore, TokenBucket


def _redis_or_skip():
    try:
        from app.core.redis import get_redis

        r = get_redis()
        r.ping()
        return r
    except Exception:  # pragma: no cover - operational
        pytest.skip("Redis not reachable for rate-limit integration test.")


def test_redis_bucket_first_acquire_then_block_then_refill():
    r = _redis_or_skip()
    # Use a unique scope so parallel test runs don't collide.
    import uuid

    scope = f"test-{uuid.uuid4().hex[:8]}"
    cfg = RateLimitConfig(capacity=1, refill_per_sec=1.0, name="aishub")

    fake_t = [1_000_000.0]

    def clock() -> float:
        return fake_t[0]

    store = RedisBucketStore(r)
    bucket = TokenBucket(store, clock=clock)

    try:
        assert bucket.acquire(cfg, scope=scope)[0] is True
        assert bucket.acquire(cfg, scope=scope)[0] is False
        fake_t[0] += 1.0
        assert bucket.acquire(cfg, scope=scope)[0] is True
    finally:
        # Cleanup so the test is repeatable.
        r.delete(f"ratelimit:{cfg.name}:{scope}")
