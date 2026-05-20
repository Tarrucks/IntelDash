"""Initial schema: extensions, registries, hypertables.

Revision ID: 0001_init
Revises:
Create Date: 2026-05-20

This single migration:
  1. enables postgis + timescaledb extensions
  2. creates the canonical registry tables (users, vessels, aircraft, hosts)
  3. creates the analyst tables (entities, cases, case_entities)
  4. creates the position tables, then promotes them to Timescale hypertables

We do not split this into multiple migrations because the position tables
must exist before ``create_hypertable`` is called, and we want a single
clean rollback path for the v1 schema.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001_init"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Extensions ----------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # --- Enums ---------------------------------------------------------------
    # ``create_type`` lives on ``postgresql.ENUM``, not generic ``sa.Enum`` —
    # the latter silently ignores the flag, which is why we explicitly use
    # the PG dialect type and create it once up front.
    user_role = PG_ENUM("viewer", "analyst", "admin", name="user_role", create_type=False)
    case_status = PG_ENUM("open", "closed", "archived", name="case_status", create_type=False)
    op.execute("CREATE TYPE user_role AS ENUM ('viewer', 'analyst', 'admin')")
    op.execute("CREATE TYPE case_status AS ENUM ('open', 'closed', 'archived')")

    # --- users ---------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="analyst"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- vessels -------------------------------------------------------------
    op.create_table(
        "vessels",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("mmsi", sa.String(16), nullable=False, unique=True, index=True),
        sa.Column("imo", sa.String(16), nullable=True, index=True),
        sa.Column("name", sa.String(128), nullable=True),
        sa.Column("call_sign", sa.String(32), nullable=True),
        sa.Column("vessel_type", sa.String(64), nullable=True),
        sa.Column("length_m", sa.Float, nullable=True),
        sa.Column("width_m", sa.Float, nullable=True),
        sa.Column("flag", sa.String(8), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- aircraft ------------------------------------------------------------
    op.create_table(
        "aircraft",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("icao24", sa.String(6), nullable=False, unique=True, index=True),
        sa.Column("registration", sa.String(16), nullable=True),
        sa.Column("aircraft_type", sa.String(32), nullable=True),
        sa.Column("operator", sa.String(128), nullable=True),
        sa.Column("flag", sa.String(8), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- hosts ---------------------------------------------------------------
    op.create_table(
        "hosts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ip", sa.String(45), nullable=False, unique=True, index=True),
        sa.Column("hostname", sa.String(255), nullable=True),
        sa.Column("org", sa.String(255), nullable=True),
        sa.Column("asn", sa.String(16), nullable=True, index=True),
        sa.Column("country", sa.String(8), nullable=True),
        sa.Column(
            "location",
            Geography(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- entities ------------------------------------------------------------
    op.create_table(
        "entities",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("kind", sa.String(32), nullable=False, index=True),
        sa.Column("ref_id", sa.String(256), nullable=False),
        sa.Column("label", sa.String(256), nullable=False),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("kind", "ref_id", name="uq_entity_kind_refid"),
    )

    # --- cases ---------------------------------------------------------------
    op.create_table(
        "cases",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("status", case_status, nullable=False, server_default="open"),
        sa.Column(
            "owner_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- case_entities -------------------------------------------------------
    op.create_table(
        "case_entities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "pinned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("case_id", "entity_id", name="uq_case_entity"),
    )

    # --- vessel_positions ----------------------------------------------------
    # Composite PK (time, mmsi): Timescale partitions on ``time``, so the
    # partitioning column must be part of every unique constraint.
    op.create_table(
        "vessel_positions",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mmsi", sa.String(16), nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("geom", Geography(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("sog", sa.Float, nullable=True),
        sa.Column("cog", sa.Float, nullable=True),
        sa.Column("heading", sa.Float, nullable=True),
        sa.Column("nav_status", sa.String(32), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="mock"),
        sa.PrimaryKeyConstraint("time", "mmsi", name="pk_vessel_positions"),
    )
    op.create_index("ix_vessel_positions_mmsi_time", "vessel_positions", ["mmsi", "time"])
    op.create_index(
        "ix_vessel_positions_geom",
        "vessel_positions",
        ["geom"],
        postgresql_using="gist",
    )
    # Promote to hypertable. ``if_not_exists`` makes the migration replay-safe.
    op.execute(
        "SELECT create_hypertable('vessel_positions', 'time', "
        "if_not_exists => TRUE, migrate_data => TRUE)"
    )

    # --- aircraft_positions --------------------------------------------------
    op.create_table(
        "aircraft_positions",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("icao24", sa.String(6), nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("geom", Geography(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("altitude_ft", sa.Float, nullable=True),
        sa.Column("speed_kts", sa.Float, nullable=True),
        sa.Column("heading_deg", sa.Float, nullable=True),
        sa.Column("callsign", sa.String(16), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="mock"),
        sa.PrimaryKeyConstraint("time", "icao24", name="pk_aircraft_positions"),
    )
    op.create_index("ix_aircraft_positions_icao_time", "aircraft_positions", ["icao24", "time"])
    op.create_index(
        "ix_aircraft_positions_geom",
        "aircraft_positions",
        ["geom"],
        postgresql_using="gist",
    )
    op.execute(
        "SELECT create_hypertable('aircraft_positions', 'time', "
        "if_not_exists => TRUE, migrate_data => TRUE)"
    )


def downgrade() -> None:
    # Hypertables drop with their parent table.
    op.drop_index("ix_aircraft_positions_geom", table_name="aircraft_positions")
    op.drop_index("ix_aircraft_positions_icao_time", table_name="aircraft_positions")
    op.drop_table("aircraft_positions")

    op.drop_index("ix_vessel_positions_geom", table_name="vessel_positions")
    op.drop_index("ix_vessel_positions_mmsi_time", table_name="vessel_positions")
    op.drop_table("vessel_positions")

    op.drop_table("case_entities")
    op.drop_table("cases")
    op.drop_table("entities")
    op.drop_table("hosts")
    op.drop_table("aircraft")
    op.drop_table("vessels")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS case_status")
    op.execute("DROP TYPE IF EXISTS user_role")
    # Leave PostGIS / TimescaleDB / uuid-ossp installed; they're cluster-level.
