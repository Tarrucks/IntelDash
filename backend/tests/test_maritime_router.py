"""Maritime router integration tests.

Verifies the bbox → vessel-snapshot fusion of DB + AISHub mock, the
vessel-detail endpoint, and the per-vessel tracks (GeoJSON) endpoint.

Seed data: the Phase 1 Alembic seed loads 6 Kattegat vessels into
``vessel_positions``; the test creates a clone of those rows in the
test DB so the bbox query returns hits.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth.security import create_access_token, hash_password
from app.models.entities import User, UserRole


@pytest.fixture()
def authed_client(client: TestClient, db_session):
    user = User(
        email="maritime@example.com",
        password_hash=hash_password("supersecret"),
        role=UserRole.analyst,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    tok = create_access_token(user_id=user.id, role=user.role.value)
    client.headers.update({"Authorization": f"Bearer {tok}"})
    return client, db_session


def _seed_kattegat(db_session) -> None:
    """Insert two vessels + four positions inside the Kattegat bbox so
    the live endpoint has something concrete to return from the DB
    path (test DB doesn't replay the Phase 1 seed migration)."""
    db_session.execute(
        text(
            "INSERT INTO vessels (mmsi, name, vessel_type) "
            "VALUES ('219000999','KATTEGAT TEST','Cargo'),"
            "       ('266001999','GOTHIA TEST','Tanker') "
            "ON CONFLICT (mmsi) DO NOTHING"
        )
    )
    rows = [
        ("219000999", datetime(2024, 1, 15, 8, 0, tzinfo=UTC), 56.15, 11.50),
        ("219000999", datetime(2024, 1, 15, 8, 5, tzinfo=UTC), 56.16, 11.52),
        ("266001999", datetime(2024, 1, 15, 8, 0, tzinfo=UTC), 56.28, 11.70),
        ("266001999", datetime(2024, 1, 15, 8, 5, tzinfo=UTC), 56.27, 11.70),
    ]
    for mmsi, t, lat, lon in rows:
        db_session.execute(
            text(
                "INSERT INTO vessel_positions (time, mmsi, lat, lon, geom, source) "
                "VALUES (:t, :m, :lat, :lon, "
                "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 'kaggle') "
                "ON CONFLICT (time, mmsi) DO NOTHING"
            ),
            {"t": t, "m": mmsi, "lat": lat, "lon": lon},
        )
    db_session.commit()


def test_live_requires_auth(client: TestClient):
    r = client.get("/maritime/live?latmin=55&latmax=58&lonmin=10&lonmax=13")
    assert r.status_code == 401


def test_live_validates_bbox(authed_client):
    client, _ = authed_client
    r = client.get("/maritime/live?latmin=58&latmax=55&lonmin=10&lonmax=13")
    assert r.status_code == 400


def test_live_returns_db_plus_aishub_mock(authed_client):
    client, db = authed_client
    _seed_kattegat(db)
    r = client.get("/maritime/live?latmin=55&latmax=58&lonmin=10&lonmax=13&limit=50")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["bbox"]["latmin"] == 55.0
    assert "db" in body["sources"]
    assert any(s.startswith("aishub") for s in body["sources"])
    mmsis = {v["mmsi"] for v in body["vessels"]}
    # Two from the seed + two from AISHub mock.
    assert "219000999" in mmsis
    assert "266001999" in mmsis
    # AISHub mock vessels live at the bbox centre.
    assert "219000123" in mmsis or "266001234" in mmsis


def test_live_returns_only_in_bbox(authed_client):
    client, db = authed_client
    _seed_kattegat(db)
    # A tiny bbox far from Kattegat — only AISHub mock (which seeds
    # vessels at the bbox centre) should appear.
    r = client.get("/maritime/live?latmin=-1&latmax=1&lonmin=-1&lonmax=1")
    assert r.status_code == 200
    body = r.json()
    for v in body["vessels"]:
        assert -1.0 <= v["lat"] <= 1.0 + 0.1, v
        assert -1.0 <= v["lon"] <= 1.0 + 0.1, v


def test_vessel_detail_known(authed_client):
    client, db = authed_client
    _seed_kattegat(db)
    r = client.get("/maritime/vessels/219000999")
    assert r.status_code == 200
    body = r.json()
    assert body["mmsi"] == "219000999"
    assert body["name"] == "KATTEGAT TEST"
    assert body["last_position"] is not None
    assert body["position_history_count"] >= 2


def test_vessel_detail_unknown_returns_synthetic_in_mock(authed_client):
    client, _ = authed_client
    r = client.get("/maritime/vessels/999999999")
    # Mock mode degrades to an empty record rather than 404 so the
    # dashboard demo flow doesn't dead-end.
    assert r.status_code == 200
    assert r.json()["mmsi"] == "999999999"


def test_vessel_tracks_geojson(authed_client):
    client, _ = authed_client
    r = client.get("/maritime/vessels/219000123/tracks")
    assert r.status_code == 200
    body = r.json()
    assert body["mmsi"] == "219000123"
    assert body["tracks"]["type"] == "FeatureCollection"
    assert len(body["tracks"]["features"]) >= 1
    geom = body["tracks"]["features"][0]["geometry"]
    assert geom["type"] == "LineString"
    assert len(geom["coordinates"]) >= 2
