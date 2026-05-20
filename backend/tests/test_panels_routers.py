"""Phase 6 router smoke tests — tooling + sensors panels."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.security import create_access_token, hash_password
from app.models.entities import User, UserRole


@pytest.fixture()
def authed_client(client: TestClient, db_session):
    user = User(
        email="panels@example.com",
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


def test_tooling_tree_requires_auth(client: TestClient):
    assert client.get("/tooling/tree").status_code == 401


def test_tooling_tree_shape(authed_client):
    r = authed_client.get("/tooling/tree")
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "folder"
    assert body["name"] == "OSINT Framework"
    assert len(body["children"]) >= 1


def test_tooling_leaves_filter(authed_client):
    # Unfiltered returns everything.
    all_leaves = authed_client.get("/tooling/leaves").json()
    assert len(all_leaves) >= 4

    # Filter by a tag known to exist in the fallback taxonomy.
    maritime = authed_client.get("/tooling/leaves?q=maritime").json()
    assert len(maritime) >= 1
    assert all(
        "maritime" in leaf["name"].lower()
        or "maritime" in leaf["url"].lower()
        or any("maritime" in t.lower() for t in leaf["tags"])
        for leaf in maritime
    )


def test_sensors_projects_shape(authed_client):
    r = authed_client.get("/sensors/projects")
    assert r.status_code == 200
    projects = r.json()
    assert len(projects) >= 1
    for p in projects:
        assert p["id"].isdigit()
        assert "wokwi.com/projects/" in p["url"]
