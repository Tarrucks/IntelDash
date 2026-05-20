"""Centralized settings, loaded from environment variables.

We use pydantic-settings so every env var is typed at the edge. Anything
that needs a secret (API keys, JWT secret) is optional — empty values
mean "run in mock mode". The presence/absence of a key is what flips a
source adapter from mock to real, gated by ``use_real_adapters``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core infra ----------------------------------------------------------
    database_url: str = "postgresql+psycopg://aperture:aperture@localhost:5432/aperture"
    redis_url: str = "redis://localhost:6379/0"

    # --- Auth ----------------------------------------------------------------
    jwt_secret: str = "dev-only-change-me"
    jwt_alg: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_ttl_minutes: int = 60

    # --- Source adapter credentials -----------------------------------------
    shodan_api_key: str | None = None
    exa_api_key: str | None = None
    aishub_username: str | None = None
    barentswatch_client_id: str | None = None
    barentswatch_client_secret: str | None = None
    fr24_api_key: str | None = None
    kaggle_username: str | None = Field(default=None, alias="KAGGLE_USERNAME")
    kaggle_key: str | None = Field(default=None, alias="KAGGLE_KEY")

    # --- Feature flags -------------------------------------------------------
    aperture_use_real_adapters: bool = True
    aperture_seed_on_boot: bool = True

    @computed_field  # type: ignore[misc]
    @property
    def kaggle_configured(self) -> bool:
        return bool(self.kaggle_username and self.kaggle_key)

    @computed_field  # type: ignore[misc]
    @property
    def barentswatch_configured(self) -> bool:
        return bool(self.barentswatch_client_id and self.barentswatch_client_secret)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Tests can clear the cache to re-read env."""
    return Settings()
