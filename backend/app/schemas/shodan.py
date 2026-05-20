"""Shodan response models.

Shapes follow the documented ``/shodan/host/{ip}`` response and the
``/shodan/host/search`` envelope (see https://developer.shodan.io/api).
Only the fields we actually consume in v1 are typed; extra keys from
the upstream are tolerated via ``model_config = {"extra": "allow"}``
so mock and real responses pass the same validation.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ShodanBanner(BaseModel):
    model_config = ConfigDict(extra="allow")

    port: int
    transport: str = "tcp"
    product: str | None = None
    version: str | None = None
    banner: str | None = Field(default=None, alias="data")
    timestamp: datetime | None = None


class ShodanHost(BaseModel):
    model_config = ConfigDict(extra="allow")

    ip_str: str
    hostnames: list[str] = Field(default_factory=list)
    ports: list[int] = Field(default_factory=list)
    country_code: str | None = None
    country_name: str | None = None
    city: str | None = None
    org: str | None = None
    isp: str | None = None
    asn: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    last_update: datetime | None = None
    data: list[ShodanBanner] = Field(default_factory=list)


class ShodanSearchMatch(BaseModel):
    model_config = ConfigDict(extra="allow")

    ip_str: str
    port: int
    org: str | None = None
    product: str | None = None
    location: dict | None = None
    timestamp: datetime | None = None


class ShodanSearchResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    total: int
    matches: list[ShodanSearchMatch]
    facets: dict | None = None
