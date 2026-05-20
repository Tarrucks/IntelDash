"""Time-series position tables, backed by Timescale hypertables.

Why a composite (time, identifier) key:
  Timescale requires the partitioning column (``time``) to be part of any
  unique constraint or primary key. Using (time, mmsi) / (time, icao24)
  gives us a natural PK without an extra surrogate ID.

Why two tables instead of one polymorphic table:
  Indices and the spatial geometry behave differently for the two domains,
  and the volume difference between vessels (millions of MMSIs) and
  aircraft (a few hundred thousand ICAO24s) makes co-partitioning awkward.

Schema is created by SQLAlchemy via Alembic. ``create_hypertable()`` is
called in the same migration, after CREATE TABLE, before any inserts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class VesselPosition(Base):
    __tablename__ = "vessel_positions"

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    mmsi: Mapped[str] = mapped_column(String(16), primary_key=True, nullable=False)

    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    # Derived POINT for PostGIS queries (within/near/clip). Filled by the
    # ingest path so we don't pay an ST_MakePoint cost on every SELECT.
    geom: Mapped[Any | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )

    sog: Mapped[float | None] = mapped_column(Float, nullable=True)  # speed over ground (kts)
    cog: Mapped[float | None] = mapped_column(Float, nullable=True)  # course over ground (deg)
    heading: Mapped[float | None] = mapped_column(Float, nullable=True)
    nav_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Source provenance: aishub | barentswatch | marinecadastre | kaggle | mock
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="mock")

    __table_args__ = (
        Index("ix_vessel_positions_mmsi_time", "mmsi", "time"),
        Index("ix_vessel_positions_geom", "geom", postgresql_using="gist"),
    )


class AircraftPosition(Base):
    __tablename__ = "aircraft_positions"

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    icao24: Mapped[str] = mapped_column(String(6), primary_key=True, nullable=False)

    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    geom: Mapped[Any | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )

    altitude_ft: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed_kts: Mapped[float | None] = mapped_column(Float, nullable=True)
    heading_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    callsign: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Source provenance: fr24 | mock
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="mock")

    __table_args__ = (
        Index("ix_aircraft_positions_icao_time", "icao24", "time"),
        Index("ix_aircraft_positions_geom", "geom", postgresql_using="gist"),
    )
