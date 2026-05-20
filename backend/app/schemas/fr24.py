"""Flightradar24 response models.

Shapes follow https://fr24api.flightradar24.com/docs/endpoints/overview
— specifically ``/live/flight-positions/full`` which returns a
``{"data": [...]}`` envelope. We type the fields we actually use and
allow extras through.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FlightPosition(BaseModel):
    model_config = ConfigDict(extra="allow")

    fr24_id: str
    hex: str  # ICAO 24-bit, lower-case hex
    callsign: str | None = None
    lat: float
    lon: float
    track: float | None = None
    alt: int | None = None
    gspeed: int | None = None
    vspeed: int | None = None
    squawk: str | None = None
    timestamp: datetime
    source: str | None = None
    reg: str | None = None
    type: str | None = None  # ICAO aircraft type code, e.g. A320
    painted_as: str | None = None
    operating_as: str | None = None
    orig_iata: str | None = None
    orig_icao: str | None = None
    dest_iata: str | None = None
    dest_icao: str | None = None
    flight: str | None = None


class LiveFlightsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    data: list[FlightPosition] = Field(default_factory=list)
