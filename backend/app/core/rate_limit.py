"""Per-source token-bucket rate limiter.

Why a token bucket and not a fixed window:
  Source APIs have very different shapes. AISHub explicitly publishes a
  hard 1-request-per-minute cap; Shodan rate-limits by monthly credits
  (no useful per-second cap, but we still keep a polite throttle);
  BarentsWatch / FR24 are credit-based with no documented RPS. A token
  bucket lets us express each as ``(capacity, refill_rate_per_sec)``
  and burst up to capacity without hammering a partner.

State layout in Redis (one HSET per ``bucket_key``):
    tokens  float    current bucket level
    ts      float    last refill timestamp (unix seconds)

Race notes:
  The refill/consume operation is *not* perfectly atomic — it does
  GET + SET, which can drift slightly under burst. For v1 this is fine:
  the per-source cap is a politeness floor, not a security boundary,
  and the small drift is far smaller than the partner's own jitter.
  If/when we need exactness we can swap in a Lua script.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RateLimitConfig:
    """Token-bucket configuration for a single source."""

    capacity: float
    """Burst capacity — also the starting fill on first acquire."""

    refill_per_sec: float
    """Tokens added per second of elapsed time."""

    name: str
    """Source name, used as a Redis key prefix."""


# ---- Known source policies --------------------------------------------------
# Documented values come from each provider's docs as of 2026-05-20 — see
# CLAUDE.md "Source Notes". Mock adapters share their source's config so
# the dashboard behaves identically when keys are added later.

SOURCE_LIMITS: dict[str, RateLimitConfig] = {
    # AISHub: hard 1/min cap is from the official API page.
    "aishub": RateLimitConfig(capacity=1.0, refill_per_sec=1.0 / 60.0, name="aishub"),
    # BarentsWatch: not documented RPS-wise; pick a polite default.
    "barentswatch": RateLimitConfig(capacity=10.0, refill_per_sec=1.0, name="barentswatch"),
    # Shodan: credit-limited, not RPS. Keep a polite throttle anyway.
    "shodan": RateLimitConfig(capacity=5.0, refill_per_sec=1.0, name="shodan"),
    # Exa: no documented RPS; default polite.
    "exa": RateLimitConfig(capacity=10.0, refill_per_sec=2.0, name="exa"),
    # FR24: also credit-based, polite default.
    "fr24": RateLimitConfig(capacity=10.0, refill_per_sec=2.0, name="fr24"),
}


class BucketStore(Protocol):
    """Tiny abstraction so unit tests can drive an in-memory store."""

    def get(self, key: str) -> tuple[float, float] | None: ...
    def put(self, key: str, tokens: float, ts: float, ttl_seconds: int) -> None: ...


class InMemoryBucketStore:
    """Process-local store. Tests only — never used in prod."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[float, float]] = {}

    def get(self, key: str) -> tuple[float, float] | None:
        return self._data.get(key)

    def put(self, key: str, tokens: float, ts: float, ttl_seconds: int) -> None:  # noqa: ARG002
        # TTL ignored for the in-memory store; only used by Redis.
        self._data[key] = (tokens, ts)


class RedisBucketStore:
    """Production store. One HSET per bucket; TTL is 4 * (capacity/refill)
    so idle buckets fade out and we don't accumulate keys forever."""

    def __init__(self, client) -> None:
        self._r = client

    def get(self, key: str) -> tuple[float, float] | None:
        data = self._r.hgetall(key)
        if not data:
            return None
        return float(data["tokens"]), float(data["ts"])

    def put(self, key: str, tokens: float, ts: float, ttl_seconds: int) -> None:
        # mapping kw to avoid the deprecated positional form.
        self._r.hset(key, mapping={"tokens": tokens, "ts": ts})
        self._r.expire(key, ttl_seconds)


class TokenBucket:
    """Acquire a token for ``(source, scope)``. Returns (allowed, retry_after)."""

    def __init__(self, store: BucketStore, *, clock=time.time) -> None:
        self._store = store
        self._clock = clock

    def _key(self, cfg: RateLimitConfig, scope: str) -> str:
        return f"ratelimit:{cfg.name}:{scope}"

    def acquire(self, cfg: RateLimitConfig, scope: str = "default") -> tuple[bool, float]:
        """Try to consume one token.

        Returns ``(True, 0.0)`` on success.
        Returns ``(False, retry_after_seconds)`` when the bucket is empty.
        """
        key = self._key(cfg, scope)
        now = self._clock()
        prev = self._store.get(key)

        if prev is None:
            # First call: start at capacity, immediately spend one.
            tokens = cfg.capacity - 1.0
            self._store.put(key, tokens, now, ttl_seconds=self._ttl(cfg))
            return True, 0.0

        last_tokens, last_ts = prev
        elapsed = max(0.0, now - last_ts)
        tokens = min(cfg.capacity, last_tokens + elapsed * cfg.refill_per_sec)

        if tokens >= 1.0:
            tokens -= 1.0
            self._store.put(key, tokens, now, ttl_seconds=self._ttl(cfg))
            return True, 0.0

        # Not enough — compute how long until 1 token regenerates.
        deficit = 1.0 - tokens
        retry_after = deficit / cfg.refill_per_sec if cfg.refill_per_sec > 0 else float("inf")
        # Persist the (refilled-but-not-spent) tokens so concurrent callers
        # see the same view.
        self._store.put(key, tokens, now, ttl_seconds=self._ttl(cfg))
        return False, retry_after

    @staticmethod
    def _ttl(cfg: RateLimitConfig) -> int:
        # Long enough that a bucket survives a normal idle period.
        # ``capacity/refill`` is the time to fully refill — keep 4x that.
        if cfg.refill_per_sec <= 0:
            return 3600
        return int(max(60, 4 * cfg.capacity / cfg.refill_per_sec))
