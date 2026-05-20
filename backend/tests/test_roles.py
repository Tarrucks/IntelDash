"""Role-hierarchy authz tests."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import require_role
from app.auth.security import create_access_token
from app.models.entities import User, UserRole


@pytest.fixture()
def role_app(db_session):
    """Build a tiny app with role-gated endpoints, sharing the test session."""
    from app.core.db import get_db

    app = FastAPI()

    @app.get("/viewer-only")
    def viewer(_: User = Depends(require_role(UserRole.viewer))):
        return {"ok": True}

    @app.get("/analyst-only")
    def analyst(_: User = Depends(require_role(UserRole.analyst))):
        return {"ok": True}

    @app.get("/admin-only")
    def admin(_: User = Depends(require_role(UserRole.admin))):
        return {"ok": True}

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as c:
        yield c, db_session


def _make_user(db, role: UserRole, email: str) -> User:
    from app.auth.security import hash_password

    u = User(email=email, password_hash=hash_password("supersecret"), role=role, is_active=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_viewer_cannot_access_analyst_only(role_app):
    client, db = role_app
    u = _make_user(db, UserRole.viewer, "v@example.com")
    tok = create_access_token(user_id=u.id, role=u.role.value)
    r = client.get("/analyst-only", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


def test_analyst_can_access_analyst_and_viewer(role_app):
    client, db = role_app
    u = _make_user(db, UserRole.analyst, "a@example.com")
    tok = create_access_token(user_id=u.id, role=u.role.value)
    assert (
        client.get("/analyst-only", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    )
    assert client.get("/viewer-only", headers={"Authorization": f"Bearer {tok}"}).status_code == 200


def test_analyst_cannot_access_admin_only(role_app):
    client, db = role_app
    u = _make_user(db, UserRole.analyst, "a2@example.com")
    tok = create_access_token(user_id=u.id, role=u.role.value)
    assert client.get("/admin-only", headers={"Authorization": f"Bearer {tok}"}).status_code == 403


def test_admin_can_access_all(role_app):
    client, db = role_app
    u = _make_user(db, UserRole.admin, "admin@example.com")
    tok = create_access_token(user_id=u.id, role=u.role.value)
    for path in ("/viewer-only", "/analyst-only", "/admin-only"):
        r = client.get(path, headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200, path


def test_inactive_user_rejected(role_app):
    client, db = role_app
    u = _make_user(db, UserRole.analyst, "off@example.com")
    u.is_active = False
    db.commit()
    tok = create_access_token(user_id=u.id, role=u.role.value)
    r = client.get("/analyst-only", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401
