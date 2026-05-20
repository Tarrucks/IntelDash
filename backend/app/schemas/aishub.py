"""AISHub response models.

AISHub's webservice returns an array-of-arrays envelope when format=json:
    [
      [{"ERROR": false, "USERNAME": "..."}],
      [ {vessel ...}, {vessel ...}, ... ]
    ]
We normalize this into a flat list of ``AisVessel`` objects in the adapter.
Mirrors the documented field names from http://www.aishub.net/api.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AisVessel(BaseModel):
    model_config = ConfigDict(extra="allow")

    mmsi: str
    time: datetime
    latitude: float
    longitude: float
    cog: float | None = None
    sog: float | None = None
    heading: float | None = None
    navstat: int | None = None
    imo: str | None = None
    name: str | None = None
    callsign: str | None = None
    type: int | None = None
    a: int | None = None
    b: int | None = None
    c: int | None = None
    d: int | None = None
    draught: float | None = None
    dest: str | None = None
    eta: str | None = None
