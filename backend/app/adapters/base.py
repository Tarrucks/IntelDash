"""SourceAdapter ABC.

Every external data source (Shodan, Exa, AISHub, BarentsWatch, FR24, ...)
ships a class that subclasses this. Each adapter:

  - declares its source name (matches the rate-limit policy key)
  - knows whether it is configured (real credentials present)
  - exposes ``mode`` so callers can show "mock" vs "real" in the UI
  - asks the shared token bucket before every outbound request

The domain-specific methods (``search_host``, ``live_positions`` …) live
on each concrete adapter — there's no point unifying them at the base.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from app.core.config import Settings, get_settings
from app.core.rate_limit import SOURCE_LIMITS, RateLimitConfig, TokenBucket

Mode = Literal["real", "mock"]


class SourceAdapter(ABC):
    """Common base for all source adapters.

    Subclasses set ``name`` (matches ``SOURCE_LIMITS``) and implement
    ``is_configured``. They get ``acquire()`` for free.
    """

    name: str

    def __init__(self, settings: Settings | None = None, bucket: TokenBucket | None = None) -> None:
        self.settings = settings or get_settings()
        self._bucket = bucket  # injected in app startup; tests can pass a fake

    # ---- Identity --------------------------------------------------------

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """True when real credentials for this source are in the environment."""

    @property
    def mode(self) -> Mode:
        if not self.settings.aperture_use_real_adapters:
            return "mock"
        return "real" if self.is_configured else "mock"

    # ---- Rate limiting ---------------------------------------------------

    @property
    def rate_limit(self) -> RateLimitConfig:
        return SOURCE_LIMITS[self.name]

    def acquire(self, scope: str = "default") -> tuple[bool, float]:
        """Try to consume a token for this source. ``(ok, retry_after)``."""
        if self._bucket is None:
            return True, 0.0  # tests + mock mode can skip the bucket
        return self._bucket.acquire(self.rate_limit, scope=scope)
