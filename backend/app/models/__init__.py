"""Aperture ORM models.

Importing this package side-effects every model into ``Base.metadata`` so
Alembic autogenerate sees the full schema.
"""

from app.models.base import Base, TimestampMixin
from app.models.entities import (
    Aircraft,
    Case,
    CaseEntity,
    CaseStatus,
    Entity,
    Host,
    User,
    UserRole,
    Vessel,
)
from app.models.positions import AircraftPosition, VesselPosition

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    "UserRole",
    "Vessel",
    "Aircraft",
    "Host",
    "Entity",
    "Case",
    "CaseStatus",
    "CaseEntity",
    "VesselPosition",
    "AircraftPosition",
]
