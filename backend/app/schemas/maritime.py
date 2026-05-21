"""Maritime dashboard schemas.

These are the shapes the frontend consumes. They intentionally do **not**
mirror raw adapter responses — the router merges and normalises across
the DB hypertable and the AISHub live feed, then returns a single flat
shape so the dashboard panel doesn't need to know where each vessel
came from.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.barentswatch import GeoJSONFeatureCollection


class VesselSnapshot(BaseModel):
    """One vessel + its most recent position."""

    model_config = ConfigDict(extra="ignore")

    mmsi: str
    name: str | None = None
    imo: str | None = None
    call_sign: str | None = None
    vessel_type: str | None = None
    time: datetime
    lat: float
    lon: float
    sog: float | None = None
    cog: float | None = None
    heading: float | None = None
    nav_status: str | None = None
    source: Literal["aishub", "barentswatch", "marinecadastre", "kaggle", "mock"] = "mock"


class LiveVesselsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bbox: dict = Field(description="latmin/latmax/lonmin/lonmax echoed back")
    fetched_at: datetime
    sources: list[str] = Field(description="Which sources contributed to this response")
    vessels: list[VesselSnapshot]


class VesselDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mmsi: str
    name: str | None = None
    imo: str | None = None
    call_sign: str | None = None
    vessel_type: str | None = None
    length_m: float | None = None
    width_m: float | None = None
    flag: str | None = None
    last_position: VesselSnapshot | None = None
    position_history_count: int = 0


class VesselTracksResponse(BaseModel):
    """Per-vessel track polyline(s) for replay."""

    model_config = ConfigDict(extra="ignore")

    mmsi: str
    source: Literal["barentswatch", "db", "mock"] = "mock"
    tracks: GeoJSONFeatureCollection


class VesselAnomaly(VesselSnapshot):
    """A vessel snapshot annotated with isolation-forest score + flag."""

    anomaly_score: float
    is_anomaly: bool


class VesselAnomaliesResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bbox: dict
    fetched_at: datetime
    sources: list[str]
    model_trained_on: int = Field(description="number of rows the model was fit on")
    vessels: list[VesselAnomaly]
