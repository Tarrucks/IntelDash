"""Saved Shodan monitors CRUD + idempotency tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.security import create_access_token, hash_password
from app.models.entities import Entity, User, UserRole


@pytest.fixture()
def authed(client: TestClient, db_session):
    user = User(
        email="mon@example.com",
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


def test_monitors_require_auth(client: TestClient):
    assert client.get("/cyber/monitors").status_code == 401


def test_create_invalid_ip_400(authed):
    client, _ = authed
    r = client.post(
        "/cyber/monitors",
        json={"ip": "not-an-ip", "name": "x"},
    )
    assert r.status_code == 400


def test_create_then_list(authed):
    client, _ = authed
    r = client.post(
        "/cyber/monitors",
        json={
            "ip": "203.0.113.10",
            "name": "Edge router",
            "ports": [22, 443],
            "notes": "watch for new banners",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["ip"] == "203.0.113.10"
    assert body["name"] == "Edge router"
    assert body["ports"] == [22, 443]
    assert body["source"] == "mock"
    # In mock mode there's no upstream alert.
    assert body["upstream_alert_id"] is None

    lst = client.get("/cyber/monitors").json()
    assert any(m["id"] == body["id"] for m in lst)


def test_create_is_idempotent_on_ip(authed):
    client, db = authed
    p = {"ip": "198.51.100.5", "name": "first"}
    client.post("/cyber/monitors", json=p).json()
    again = client.post("/cyber/monitors", json={**p, "name": "second"}).json()
    # Same row, updated label.
    assert again["name"] == "second"
    rows = (
        db.execute(
            select(Entity).where(Entity.kind == "shodan_monitor", Entity.ref_id == "198.51.100.5")
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


def test_delete_monitor(authed):
    client, _ = authed
    created = client.post("/cyber/monitors", json={"ip": "203.0.113.99", "name": "tmp"}).json()
    assert client.delete(f"/cyber/monitors/{created['id']}").status_code == 204
    assert client.delete(f"/cyber/monitors/{created['id']}").status_code == 404


def test_cidr_accepted(authed):
    client, _ = authed
    r = client.post("/cyber/monitors", json={"ip": "192.0.2.0/24", "name": "test-net"})
    assert r.status_code == 201
    assert r.json()["ip"] == "192.0.2.0/24"
