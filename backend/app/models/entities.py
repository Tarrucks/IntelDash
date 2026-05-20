"""Canonical entity registries: vessels, aircraft, hosts, users.

These are the "directory" tables. Time-varying observations (positions,
banner snapshots) live in their own hypertables and reference these rows
loosely by identifier string (mmsi/icao24/ip), not by FK — that keeps
ingest cheap and lets late-binding fill the directory.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class UserRole(enum.StrEnum):
    viewer = "viewer"
    analyst = "analyst"
    admin = "admin"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # bcrypt produces 60-char hashes; 255 leaves room for future algs.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda e: [v.value for v in e]),
        nullable=False,
        default=UserRole.analyst,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    cases: Mapped[list[Case]] = relationship(back_populates="owner")


class Vessel(Base, TimestampMixin):
    """One row per real vessel. Keyed by MMSI (9-digit maritime ID)."""

    __tablename__ = "vessels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mmsi: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    imo: Mapped[str | None] = mapped_column(String(16), index=True, nullable=True)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    call_sign: Mapped[str | None] = mapped_column(String(32), nullable=True)
    vessel_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    length_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    width_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    flag: Mapped[str | None] = mapped_column(String(8), nullable=True)


class Aircraft(Base, TimestampMixin):
    """One row per real aircraft. Keyed by ICAO 24-bit transponder hex."""

    __tablename__ = "aircraft"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    icao24: Mapped[str] = mapped_column(String(6), unique=True, index=True, nullable=False)
    registration: Mapped[str | None] = mapped_column(String(16), nullable=True)
    aircraft_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    operator: Mapped[str | None] = mapped_column(String(128), nullable=True)
    flag: Mapped[str | None] = mapped_column(String(8), nullable=True)


class Host(Base, TimestampMixin):
    """Cyber asset (Shodan banner). Keyed by IP. Optional last-known geo."""

    __tablename__ = "hosts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip: Mapped[str] = mapped_column(String(45), unique=True, index=True, nullable=False)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    org: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asn: Mapped[str | None] = mapped_column(String(16), index=True, nullable=True)
    country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # SRID 4326 = WGS84, the only sane default for a global dashboard.
    location: Mapped[Any | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
    )
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Entity(Base):
    """Cross-domain reference. An Entity is a stable handle the Case File pins.

    ``kind`` is intentionally a free-form string (vessel / aircraft / host /
    url / domain / person / org / file_hash / etc) so we can grow it
    without migrations. ``ref_id`` is the natural key in that domain
    (mmsi, icao24, ip, URL...).
    """

    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("kind", "ref_id", name="uq_entity_kind_refid"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    ref_id: Mapped[str] = mapped_column(String(256), nullable=False)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    extra: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CaseStatus(enum.StrEnum):
    open = "open"
    closed = "closed"
    archived = "archived"


class Case(Base, TimestampMixin):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus, name="case_status", values_callable=lambda e: [v.value for v in e]),
        nullable=False,
        default=CaseStatus.open,
    )
    owner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    owner: Mapped[User | None] = relationship(back_populates="cases")
    pins: Mapped[list[CaseEntity]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class CaseEntity(Base):
    """Pin: an entity attached to a case, with optional analyst note."""

    __tablename__ = "case_entities"
    __table_args__ = (UniqueConstraint("case_id", "entity_id", name="uq_case_entity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    pinned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    case: Mapped[Case] = relationship(back_populates="pins")
    entity: Mapped[Entity] = relationship()


# JSON is imported for future portability (e.g. SQLite tests). Keep it.
_ = JSON
