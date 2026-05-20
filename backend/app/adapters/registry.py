"""Adapter registry.

Resolves source name -> adapter instance. Adapters share a single
``TokenBucket`` so per-source rate limits are honoured across callers.
"""

from __future__ import annotations

from functools import cache, lru_cache

from app.adapters.aishub import AISHubAdapter
from app.adapters.barentswatch import BarentsWatchAdapter
from app.adapters.base import SourceAdapter
from app.adapters.exa import ExaAdapter
from app.adapters.fr24 import FR24Adapter
from app.adapters.kaggle import KaggleAdapter
from app.adapters.marinecadastre import MarineCadastreAdapter
from app.adapters.osintframework import OsintFrameworkAdapter
from app.adapters.shodan import ShodanAdapter
from app.adapters.wokwi import WokwiAdapter
from app.core.config import get_settings
from app.core.rate_limit import RedisBucketStore, TokenBucket
from app.core.redis import get_redis

ADAPTER_CLASSES: dict[str, type[SourceAdapter]] = {
    "shodan": ShodanAdapter,
    "exa": ExaAdapter,
    "aishub": AISHubAdapter,
    "barentswatch": BarentsWatchAdapter,
    "marinecadastre": MarineCadastreAdapter,
    "fr24": FR24Adapter,
    "kaggle": KaggleAdapter,
    "osintframework": OsintFrameworkAdapter,
    "wokwi": WokwiAdapter,
}


@lru_cache(maxsize=1)
def _shared_bucket() -> TokenBucket:
    """One bucket per process; backed by Redis."""
    return TokenBucket(RedisBucketStore(get_redis()))


@cache
def get_adapter(name: str) -> SourceAdapter:
    cls = ADAPTER_CLASSES.get(name)
    if cls is None:
        raise KeyError(f"Unknown adapter: {name}")
    return cls(settings=get_settings(), bucket=_shared_bucket())


def all_adapters() -> list[SourceAdapter]:
    return [get_adapter(n) for n in ADAPTER_CLASSES]
