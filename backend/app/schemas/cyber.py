"""Cyber Surface dashboard schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CyberBanner(BaseModel):
    model_config = ConfigDict(extra="ignore")

    port: int
    transport: str = "tcp"
    product: str | None = None
    version: str | None = None
    banner: str | None = None
    timestamp: datetime | None = None


class CyberHost(BaseModel):
    """Normalised view of a Shodan host record."""

    model_config = ConfigDict(extra="ignore")

    ip: str
    hostnames: list[str] = Field(default_factory=list)
    ports: list[int] = Field(default_factory=list)
    country_code: str | None = None
    city: str | None = None
    org: str | None = None
    isp: str | None = None
    asn: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    last_update: datetime | None = None
    banners: list[CyberBanner] = Field(default_factory=list)
    source: str = "mock"


class CyberSearchMatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ip: str
    port: int
    org: str | None = None
    product: str | None = None
    location: dict[str, Any] | None = None
    timestamp: datetime | None = None


class CyberSearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total: int
    query: str
    sources: list[str]
    matches: list[CyberSearchMatch]
