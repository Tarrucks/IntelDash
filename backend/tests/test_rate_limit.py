"""Token-bucket rate-limiter tests.

These are intentionally unit-style with a deterministic clock and an
in-memory store. The Redis-backed store is exercised separately under
``tests/test_rate_limit_redis.py`` (skipped if Redis isn't available).
"""

from __future__ import annotations

from app.core.rate_limit import (
    SOURCE_LIMITS,
    InMemoryBucketStore,
    RateLimitConfig,
    TokenBucket,
)


class FakeClock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def test_first_acquire_succeeds():
    clock = FakeClock()
    bucket = TokenBucket(InMemoryBucketStore(), clock=clock)
    cfg = RateLimitConfig(capacity=2, refill_per_sec=1.0, name="t")

    ok, retry = bucket.acquire(cfg)
    assert ok is True
    assert retry == 0.0


def test_capacity_caps_burst_at_capacity():
    clock = FakeClock()
    bucket = TokenBucket(InMemoryBucketStore(), clock=clock)
    cfg = RateLimitConfig(capacity=3, refill_per_sec=0.5, name="t")

    assert bucket.acquire(cfg)[0] is True  # 3 -> 2
    assert bucket.acquire(cfg)[0] is True  # 2 -> 1
    assert bucket.acquire(cfg)[0] is True  # 1 -> 0
    ok, retry = bucket.acquire(cfg)
    assert ok is False
    # With 0.5/s refill, recovering 1 token takes 2 seconds.
    assert abs(retry - 2.0) < 1e-6


def test_refill_after_wait():
    clock = FakeClock()
    bucket = TokenBucket(InMemoryBucketStore(), clock=clock)
    cfg = RateLimitConfig(capacity=1, refill_per_sec=1.0, name="t")

    assert bucket.acquire(cfg)[0] is True
    assert bucket.acquire(cfg)[0] is False

    clock.advance(1.0)
    ok, _ = bucket.acquire(cfg)
    assert ok is True


def test_scopes_are_independent():
    clock = FakeClock()
    bucket = TokenBucket(InMemoryBucketStore(), clock=clock)
    cfg = RateLimitConfig(capacity=1, refill_per_sec=1.0, name="t")

    assert bucket.acquire(cfg, scope="alice")[0] is True
    # alice's bucket is empty, bob's hasn't been touched.
    assert bucket.acquire(cfg, scope="alice")[0] is False
    assert bucket.acquire(cfg, scope="bob")[0] is True


def test_aishub_one_per_minute_policy():
    """AISHub's published cap is 1 request / minute. Verify our config matches."""
    cfg = SOURCE_LIMITS["aishub"]
    clock = FakeClock()
    bucket = TokenBucket(InMemoryBucketStore(), clock=clock)

    assert bucket.acquire(cfg)[0] is True
    assert bucket.acquire(cfg)[0] is False  # rate-limited

    clock.advance(59.0)
    assert bucket.acquire(cfg)[0] is False  # still locked

    clock.advance(1.0)  # 60s total elapsed
    assert bucket.acquire(cfg)[0] is True


def test_capacity_does_not_overflow():
    """Letting time pass for an hour doesn't grant infinite tokens."""
    clock = FakeClock()
    bucket = TokenBucket(InMemoryBucketStore(), clock=clock)
    cfg = RateLimitConfig(capacity=2, refill_per_sec=1.0, name="t")

    bucket.acquire(cfg)
    clock.advance(3600.0)
    # Should be capped at 2, so 3 acquires in a row consume them.
    assert bucket.acquire(cfg)[0] is True
    assert bucket.acquire(cfg)[0] is True
    assert bucket.acquire(cfg)[0] is False
