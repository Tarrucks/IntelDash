"""Cyber Surface router integration tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.security import create_access_token, hash_password
from app.models.entities import Host, User, UserRole


@pytest.fixture()
def authed_client(client: TestClient, db_session):
    user = User(
        email="cyber@example.com",
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


def test_host_requires_auth(client: TestClient):
    assert client.get("/cyber/hosts/1.1.1.1").status_code == 401


def test_host_invalid_ip(authed_client):
    client, _ = authed_client
    r = client.get("/cyber/hosts/not-an-ip")
    assert r.status_code == 400


def test_host_lookup_persists_to_db(authed_client):
    client, db = authed_client
    r = client.get("/cyber/hosts/203.0.113.10")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ip"] == "203.0.113.10"
    assert body["source"] == "mock"
    assert 22 in body["ports"]
    assert any(b["port"] == 443 for b in body["banners"])

    # Verify the upsert landed.
    host = db.execute(select(Host).where(Host.ip == "203.0.113.10")).scalar_one()
    assert host.org == "MockHost LLC"
    assert host.raw is not None
    # And the PostGIS POINT was populated.
    assert host.location is not None


def test_host_lookup_is_idempotent(authed_client):
    client, db = authed_client
    client.get("/cyber/hosts/203.0.113.20")
    client.get("/cyber/hosts/203.0.113.20")
    rows = db.execute(select(Host).where(Host.ip == "203.0.113.20")).scalars().all()
    assert len(rows) == 1


def test_search_returns_matches(authed_client):
    client, _ = authed_client
    r = client.get("/cyber/search?q=nginx&limit=3")
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "nginx"
    assert body["total"] >= 1
    assert all(m["ip"].startswith("203.0.113.") for m in body["matches"])


def test_search_validates_query_length(authed_client):
    client, _ = authed_client
    r = client.get("/cyber/search?q=")
    assert r.status_code == 422
