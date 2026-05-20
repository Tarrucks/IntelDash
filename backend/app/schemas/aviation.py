"""Aviation dashboard schemas.

Trimmed/renamed subset of the FR24 ``FlightPosition`` shape, keeping
only the fields the dashboard actually surfaces. ``extra="ignore"``
means upstream additions don't break validation.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FlightSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fr24_id: str
    hex: str
    callsign: str | None = None
    lat: float
    lon: float
    track: float | None = None
    alt: int | None = None
    gspeed: int | None = None
    timestamp: datetime
    reg: str | None = None
    type: str | None = None
    flight: str | None = None
    orig_iata: str | None = None
    dest_iata: str | None = None
    source: str = "mock"


class LiveFlightsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bbox: dict | None = Field(default=None, description="echoed bbox if provided")
    fetched_at: datetime
    sources: list[str]
    flights: list[FlightSnapshot]
