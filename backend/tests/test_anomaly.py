"""Vessel anomaly detector — unit + integration tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth.security import create_access_token, hash_password
from app.ml.anomaly import (
    MIN_TRAINING_ROWS,
    VesselAnomalyModel,
    _angle,
    _row_features,
    invalidate_cache,
)
from app.models.entities import User, UserRole

# ---- Pure-Python unit tests (no DB) ---------------------------------------


def test_angle_handles_none():
    s, c = _angle(None)
    assert s == 0.0 and c == 1.0


def test_angle_decomposes_correctly():
    s, c = _angle(0.0)
    assert abs(s - 0.0) < 1e-9
    assert abs(c - 1.0) < 1e-9

    s, c = _angle(90.0)
    assert abs(s - 1.0) < 1e-9
    assert abs(c) < 1e-9


def test_row_features_length_is_six():
    feats = _row_features(12.0, 90.0, 95.0)
    assert len(feats) == 6
    # Heading-COG deviation is 5°.
    assert abs(feats[-1] - 5.0) < 1e-9


def test_row_features_handles_wrap_around():
    # heading=5, cog=355 → smallest angular diff is 10°, not 350°.
    feats = _row_features(10.0, 355.0, 5.0)
    assert abs(feats[-1] - 10.0) < 1e-9


def test_model_returns_false_when_not_fitted():
    m = VesselAnomalyModel()
    r = m.predict(10.0, 90.0, 95.0)
    assert r.is_anomaly is False
    assert r.score == 0.0


def test_fit_requires_minimum_rows():
    m = VesselAnomalyModel()
    n = m.fit([(1.0, 0.0, 0.0)] * (MIN_TRAINING_ROWS - 1))
    assert n == 0
    assert m.fitted is False


def test_fit_flags_obvious_outlier():
    m = VesselAnomalyModel()
    # Cluster of "normal" steady-cruise vessels…
    samples = [(12.0, 45.0, 46.0)] * 30 + [(11.8, 45.0, 46.0)] * 20
    # …and one absurd anomaly: stationary but heading=180° away from cog.
    samples.append((0.0, 0.0, 180.0))
    n = m.fit(samples)
    assert n == len(samples)

    normal = m.predict(12.0, 45.0, 46.0)
    outlier = m.predict(0.0, 0.0, 180.0)
    # The outlier should score strictly higher.
    assert outlier.score > normal.score


# ---- Endpoint integration tests ------------------------------------------


@pytest.fixture()
def authed_client(client: TestClient, db_session):
    user = User(
        email="anom@example.com",
        password_hash=hash_password("supersecret"),
        role=UserRole.analyst,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    tok = create_access_token(user_id=user.id, role=user.role.value)
    client.headers.update({"Authorization": f"Bearer {tok}"})
    invalidate_cache()
    yield client, db_session
    invalidate_cache()


def _seed_for_anomaly(db) -> None:
    """Insert 30 cruise-steady positions + 1 obvious outlier for training."""
    db.execute(
        text(
            "INSERT INTO vessels (mmsi, name, vessel_type) "
            "VALUES ('219000777','TEST CRUISE','Cargo') "
            "ON CONFLICT (mmsi) DO NOTHING"
        )
    )
    for i in range(30):
        db.execute(
            text(
                "INSERT INTO vessel_positions (time, mmsi, lat, lon, sog, cog, heading, source) "
                "VALUES (now() - (:i || ' minutes')::interval, '219000777', 56.1, 11.5, "
                "12.0, 45.0, 46.0, 'kaggle') "
                "ON CONFLICT (time, mmsi) DO NOTHING"
            ),
            {"i": i},
        )
    db.commit()


def test_anomalies_endpoint_requires_auth(client: TestClient):
    r = client.get("/maritime/anomalies?latmin=55&latmax=58&lonmin=10&lonmax=13")
    assert r.status_code == 401


def test_anomalies_endpoint_validates_bbox(authed_client):
    client, _ = authed_client
    r = client.get("/maritime/anomalies?latmin=58&latmax=55&lonmin=10&lonmax=13")
    assert r.status_code == 400


def test_anomalies_endpoint_returns_scored_vessels(authed_client):
    client, db = authed_client
    _seed_for_anomaly(db)
    r = client.get("/maritime/anomalies?latmin=55&latmax=58&lonmin=10&lonmax=13")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "isoforest" in body["sources"]
    assert body["model_trained_on"] >= 30
    assert len(body["vessels"]) >= 1
    for v in body["vessels"]:
        assert isinstance(v["anomaly_score"], (int, float))
        assert isinstance(v["is_anomaly"], bool)
