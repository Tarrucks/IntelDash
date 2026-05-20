"""SQLAlchemy declarative base + small shared mixins.

Aperture stores three classes of records:
  1. canonical registries (one row per real-world thing): vessels, aircraft,
     hosts, users — these get integer PKs and timestamp mixins.
  2. analyst artefacts (cases, entities) — UUID PKs so they can be exported
     and linked across systems without collisions.
  3. time-series positions (vessel_positions, aircraft_positions) — composite
     keys (time, identifier), stored in Timescale hypertables. No surrogate ID
     because the partition column has to be in every unique constraint.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Project-wide declarative base."""


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
