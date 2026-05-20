"""Unit test for the Kaggle seed column resolver.

We can't easily exercise the full Alembic migration in pytest without a
running Postgres, but the column-name resolver is pure Python and the
piece most likely to silently break when upstream schemas drift.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

# Load the migration as a free-standing module — Alembic itself
# normally imports it dynamically.
_MIG_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "20260520_0002_seed_kaggle_ais.py"
)
spec = importlib.util.spec_from_file_location("seed_mig", _MIG_PATH)
assert spec and spec.loader
seed_mig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed_mig)


def test_resolver_marinecadastre_columns():
    header = [
        "MMSI",
        "BaseDateTime",
        "LAT",
        "LON",
        "SOG",
        "COG",
        "Heading",
        "VesselName",
        "IMO",
        "CallSign",
        "VesselType",
        "Status",
        "Length",
        "Width",
    ]
    out = seed_mig._resolve_columns(header)
    assert out["mmsi"] == "MMSI"
    assert out["time"] == "BaseDateTime"
    assert out["lat"] == "LAT"
    assert out["lon"] == "LON"
    assert out["nav_status"] == "Status"
    assert out["vessel_type"] == "VesselType"


def test_resolver_lowercase_kaggle_columns():
    header = ["mmsi", "timestamp", "latitude", "longitude", "speed"]
    out = seed_mig._resolve_columns(header)
    assert out["mmsi"] == "mmsi"
    assert out["time"] == "timestamp"
    assert out["lat"] == "latitude"
    assert out["lon"] == "longitude"
    assert out["sog"] == "speed"
    # Missing fields resolve to None instead of raising.
    assert out["heading"] is None


def test_parse_dt_handles_iso_and_z_suffix():
    dt1 = seed_mig._parse_dt("2024-01-15T08:00:00")
    dt2 = seed_mig._parse_dt("2024-01-15T08:00:00Z")
    dt3 = seed_mig._parse_dt("2024-01-15 08:00:00")
    assert dt1.year == dt2.year == dt3.year == 2024
    assert dt1.tzinfo is not None
    assert dt2.tzinfo is not None


def test_float_or_none_handles_empty():
    assert seed_mig._float_or_none("") is None
    assert seed_mig._float_or_none(None) is None
    assert seed_mig._float_or_none("3.14") == 3.14
    assert seed_mig._float_or_none("not a number") is None
