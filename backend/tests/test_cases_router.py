"""Analyst Case File router tests.

Covers case CRUD, visibility (per-owner unless admin), and the
pin/unpin flow with entity upsert + idempotency on (case_id, entity_id).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.security import create_access_token, hash_password
from app.models.entities import User, UserRole


def _mk_user(db, email: str, role: UserRole = UserRole.analyst) -> tuple[User, str]:
    u = User(email=email, password_hash=hash_password("supersecret"), role=role, is_active=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u, create_access_token(user_id=u.id, role=u.role.value)


@pytest.fixture()
def analyst(client: TestClient, db_session):
    user, tok = _mk_user(db_session, "case-analyst@example.com")
    client.headers.update({"Authorization": f"Bearer {tok}"})
    return client, db_session, user, tok


def test_unauthenticated_list_rejected(client: TestClient):
    assert client.get("/cases").status_code == 401


def test_create_and_list_case(analyst):
    client, _, _, _ = analyst
    r = client.post("/cases", json={"title": "Op North Sea", "summary": "first sweep"})
    assert r.status_code == 201, r.text
    case_id = r.json()["id"]

    lst = client.get("/cases").json()
    assert any(c["id"] == case_id for c in lst)


def test_other_analyst_cannot_see_case(client: TestClient, db_session):
    alice, alice_tok = _mk_user(db_session, "alice@example.com")
    bob, bob_tok = _mk_user(db_session, "bob@example.com")

    client.headers.update({"Authorization": f"Bearer {alice_tok}"})
    case = client.post("/cases", json={"title": "Alice case"}).json()

    client.headers.update({"Authorization": f"Bearer {bob_tok}"})
    assert client.get(f"/cases/{case['id']}").status_code == 404
    assert all(c["id"] != case["id"] for c in client.get("/cases").json())


def test_admin_can_see_any_case(client: TestClient, db_session):
    alice, alice_tok = _mk_user(db_session, "alice2@example.com")
    admin, admin_tok = _mk_user(db_session, "admin@example.com", role=UserRole.admin)

    client.headers.update({"Authorization": f"Bearer {alice_tok}"})
    case = client.post("/cases", json={"title": "Alice"}).json()

    client.headers.update({"Authorization": f"Bearer {admin_tok}"})
    assert client.get(f"/cases/{case['id']}").status_code == 200


def test_update_case_status(analyst):
    client, _, _, _ = analyst
    case = client.post("/cases", json={"title": "open case"}).json()
    r = client.patch(f"/cases/{case['id']}", json={"status": "closed"})
    assert r.status_code == 200
    assert r.json()["status"] == "closed"


def test_delete_case(analyst):
    client, _, _, _ = analyst
    case = client.post("/cases", json={"title": "doomed"}).json()
    assert client.delete(f"/cases/{case['id']}").status_code == 204
    assert client.get(f"/cases/{case['id']}").status_code == 404


def test_pin_entity_idempotent(analyst):
    client, _, _, _ = analyst
    case = client.post("/cases", json={"title": "Pinning"}).json()
    payload = {
        "kind": "vessel",
        "ref_id": "219000123",
        "label": "KATTEGAT STAR",
        "extra": {"flag": "DK"},
        "notes": "matches profile",
    }
    r1 = client.post(f"/cases/{case['id']}/pins", json=payload)
    assert r1.status_code == 201, r1.text
    pin_id = r1.json()["id"]

    # Pinning the same (kind, ref_id) again must NOT create a duplicate.
    r2 = client.post(f"/cases/{case['id']}/pins", json={**payload, "notes": "updated note"})
    assert r2.status_code == 201
    assert r2.json()["id"] == pin_id
    assert r2.json()["notes"] == "updated note"

    detail = client.get(f"/cases/{case['id']}").json()
    assert detail["pin_count"] == 1
    assert detail["pins"][0]["entity"]["label"] == "KATTEGAT STAR"


def test_pin_then_unpin(analyst):
    client, _, _, _ = analyst
    case = client.post("/cases", json={"title": "Pinning"}).json()
    pin = client.post(
        f"/cases/{case['id']}/pins",
        json={"kind": "host", "ref_id": "203.0.113.10", "label": "203.0.113.10"},
    ).json()
    assert client.delete(f"/cases/{case['id']}/pins/{pin['id']}").status_code == 204
    detail = client.get(f"/cases/{case['id']}").json()
    assert detail["pin_count"] == 0


def test_entity_is_shared_across_cases(analyst):
    """Two cases pinning the same vessel reference one Entity row."""
    client, db, _, _ = analyst
    c1 = client.post("/cases", json={"title": "A"}).json()
    c2 = client.post("/cases", json={"title": "B"}).json()
    common = {"kind": "vessel", "ref_id": "266001234", "label": "GOTHIA TANKER"}
    p1 = client.post(f"/cases/{c1['id']}/pins", json=common).json()
    p2 = client.post(f"/cases/{c2['id']}/pins", json=common).json()
    assert p1["entity"]["id"] == p2["entity"]["id"]


def test_unpin_unknown_pin_404(analyst):
    client, _, _, _ = analyst
    case = client.post("/cases", json={"title": "x"}).json()
    assert client.delete(f"/cases/{case['id']}/pins/9999").status_code == 404
