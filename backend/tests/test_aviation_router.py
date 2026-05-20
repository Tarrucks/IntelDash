"""Aviation router integration tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.security import create_access_token, hash_password
from app.models.entities import User, UserRole


@pytest.fixture()
def authed_client(client: TestClient, db_session):
    user = User(
        email="aviation@example.com",
        password_hash=hash_password("supersecret"),
        role=UserRole.analyst,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    tok = create_access_token(user_id=user.id, role=user.role.value)
    client.headers.update({"Authorization": f"Bearer {tok}"})
    return client


def test_live_requires_auth(client: TestClient):
    assert client.get("/aviation/live").status_code == 401


def test_live_returns_mock_flights(authed_client):
    r = authed_client.get("/aviation/live?limit=5")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["bbox"] is None
    assert any(s.startswith("fr24") for s in body["sources"])
    assert len(body["flights"]) >= 1
    f = body["flights"][0]
    # FR24 hex is 6 lowercase chars; we don't lowercase in the mock so just
    # assert the length.
    assert len(f["hex"]) == 6
    assert f["source"] == "mock"


def test_live_partial_bbox_rejected(authed_client):
    r = authed_client.get("/aviation/live?latmin=50")
    assert r.status_code == 400


def test_live_inverted_bbox_rejected(authed_client):
    r = authed_client.get("/aviation/live?latmin=58&latmax=55&lonmin=10&lonmax=13")
    assert r.status_code == 400


def test_live_bbox_centres_flights(authed_client):
    r = authed_client.get("/aviation/live?latmin=55&latmax=58&lonmin=10&lonmax=13&limit=4")
    assert r.status_code == 200
    body = r.json()
    assert body["bbox"]["latmin"] == 55.0
    # Mock flights are spread around the bbox centre.
    assert len(body["flights"]) >= 1


def test_flight_detail_unknown_in_mock_synthesises(authed_client):
    r = authed_client.get("/aviation/flights/abcdef")
    assert r.status_code == 200
    body = r.json()
    assert body["hex"] == "abcdef"
    assert body["source"] == "mock"
