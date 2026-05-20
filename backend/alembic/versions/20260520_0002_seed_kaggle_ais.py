"""Kaggle AIS seed (idempotent).

Revision ID: 0002_seed_kaggle_ais
Revises: 0001_init
Create Date: 2026-05-20

Loads ``data/seed/kaggle-ais/sample.csv`` into vessels + vessel_positions.

Design choices:
  - Idempotent: skips rows whose (time, mmsi) primary key already exists,
    so re-running the migration after partial failure is safe.
  - Column-name introspection per CLAUDE.md "Kaggle AIS Dataset" note —
    the migration does not hard-code column positions. It normalizes
    common AIS column-name variants seen across MarineCadastre / Kaggle.
  - Mock-safe: if the CSV is missing (e.g. someone cleared the data dir),
    the migration logs and proceeds. The platform must still upgrade
    cleanly so the rest of the schema is available.
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_seed_kaggle_ais"
down_revision: Union[str, None] = "0001_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

log = logging.getLogger("alembic.seed.kaggle")

# Column-name aliases. Different AIS sources spell the same field
# differently (MarineCadastre uses ``BaseDateTime``; some Kaggle dumps use
# ``timestamp`` or ``ts``). Resolve at load time, not in SQL.
ALIASES = {
    "mmsi": ("mmsi", "MMSI"),
    "time": ("BaseDateTime", "timestamp", "ts", "time", "DateTime"),
    "lat": ("LAT", "lat", "latitude", "Latitude"),
    "lon": ("LON", "lon", "longitude", "Longitude"),
    "sog": ("SOG", "sog", "speed", "Speed"),
    "cog": ("COG", "cog", "course", "Course"),
    "heading": ("Heading", "heading", "hdg"),
    "name": ("VesselName", "vessel_name", "name", "ShipName"),
    "imo": ("IMO", "imo"),
    "call_sign": ("CallSign", "call_sign", "callsign"),
    "vessel_type": ("VesselType", "vessel_type", "type", "ShipType"),
    "nav_status": ("Status", "status", "navigational_status", "NavStatus"),
    "length": ("Length", "length", "length_m"),
    "width": ("Width", "width", "width_m"),
}


def _resolve_columns(header: Sequence[str]) -> dict[str, str | None]:
    """Map our canonical field names to the CSV's actual column header."""
    header_set = {h: h for h in header}
    out: dict[str, str | None] = {}
    for canonical, aliases in ALIASES.items():
        out[canonical] = next((header_set[a] for a in aliases if a in header_set), None)
    return out


def _parse_dt(s: str) -> datetime:
    # MarineCadastre: 2024-01-15T08:00:00; Kaggle: occasionally with space.
    s = s.strip().replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _float_or_none(s: str | None) -> float | None:
    if s is None or s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _seed_path() -> Path:
    # alembic runs from backend/, repo root is one level up.
    candidates = [
        Path("data/seed/kaggle-ais/sample.csv"),
        Path("../data/seed/kaggle-ais/sample.csv"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def _rows(csv_path: Path) -> Iterable[dict[str, str]]:
    with csv_path.open("r", newline="") as f:
        yield from csv.DictReader(f)


def upgrade() -> None:
    path = _seed_path()
    if not path.exists():
        log.warning("Kaggle AIS seed CSV not found at %s — skipping seed.", path)
        return

    bind = op.get_bind()
    rows = list(_rows(path))
    if not rows:
        log.warning("Seed CSV %s is empty — skipping.", path)
        return

    cols = _resolve_columns(list(rows[0].keys()))
    if not cols["mmsi"] or not cols["time"] or not cols["lat"] or not cols["lon"]:
        log.error(
            "Seed CSV %s is missing required columns (mmsi/time/lat/lon). "
            "Resolved: %s. Skipping seed.",
            path,
            cols,
        )
        return

    # --- vessels (one row per MMSI) -----------------------------------------
    vessels: dict[str, dict] = {}
    for r in rows:
        mmsi = r[cols["mmsi"]].strip()
        if not mmsi:
            continue
        vessels.setdefault(
            mmsi,
            {
                "mmsi": mmsi,
                "imo": (r.get(cols["imo"]) or None) if cols["imo"] else None,
                "name": (r.get(cols["name"]) or None) if cols["name"] else None,
                "call_sign": (r.get(cols["call_sign"]) or None) if cols["call_sign"] else None,
                "vessel_type": (
                    (r.get(cols["vessel_type"]) or None) if cols["vessel_type"] else None
                ),
                "length_m": _float_or_none(r.get(cols["length"])) if cols["length"] else None,
                "width_m": _float_or_none(r.get(cols["width"])) if cols["width"] else None,
            },
        )

    # ON CONFLICT keeps the migration idempotent across replays.
    bind.execute(
        sa.text("""
            INSERT INTO vessels
                (mmsi, imo, name, call_sign, vessel_type, length_m, width_m)
            VALUES
                (:mmsi, :imo, :name, :call_sign, :vessel_type, :length_m, :width_m)
            ON CONFLICT (mmsi) DO NOTHING
            """),
        list(vessels.values()),
    )

    # --- vessel_positions ---------------------------------------------------
    positions = []
    for r in rows:
        mmsi = r[cols["mmsi"]].strip()
        time_raw = r[cols["time"]].strip()
        lat = _float_or_none(r[cols["lat"]])
        lon = _float_or_none(r[cols["lon"]])
        if not mmsi or not time_raw or lat is None or lon is None:
            continue
        positions.append(
            {
                "time": _parse_dt(time_raw),
                "mmsi": mmsi,
                "lat": lat,
                "lon": lon,
                "sog": _float_or_none(r.get(cols["sog"])) if cols["sog"] else None,
                "cog": _float_or_none(r.get(cols["cog"])) if cols["cog"] else None,
                "heading": _float_or_none(r.get(cols["heading"])) if cols["heading"] else None,
                "nav_status": (r.get(cols["nav_status"]) or None) if cols["nav_status"] else None,
                "source": "kaggle",
            }
        )

    if positions:
        # PostGIS POINT geometry built server-side. ST_MakePoint takes (lon, lat).
        bind.execute(
            sa.text("""
                INSERT INTO vessel_positions
                    (time, mmsi, lat, lon, geom, sog, cog, heading, nav_status, source)
                VALUES
                    (:time, :mmsi, :lat, :lon,
                     ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                     :sog, :cog, :heading, :nav_status, :source)
                ON CONFLICT (time, mmsi) DO NOTHING
                """),
            positions,
        )

    log.info(
        "Seeded %d vessels and %d positions from %s.",
        len(vessels),
        len(positions),
        path,
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM vessel_positions WHERE source = 'kaggle'"))
    # Vessels could have been touched by other sources, so we only drop the
    # specific MMSIs the seed introduced.
    bind.execute(
        sa.text(
            "DELETE FROM vessels WHERE mmsi IN "
            "('219000123','266001234','211000456','220011223','257098765','244987654')"
        )
    )
