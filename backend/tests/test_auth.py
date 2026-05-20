"""Auth: register → login → me round-trip + edge cases."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_register_creates_analyst(client: TestClient):
    r = client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "supersecret"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "alice@example.com"
    assert body["role"] == "analyst"
    assert body["is_active"] is True


def test_duplicate_register_conflicts(client: TestClient):
    payload = {"email": "bob@example.com", "password": "supersecret"}
    assert client.post("/auth/register", json=payload).status_code == 201
    again = client.post("/auth/register", json=payload)
    assert again.status_code == 409


def test_login_returns_jwt_and_me_round_trips(client: TestClient):
    client.post(
        "/auth/register",
        json={"email": "carol@example.com", "password": "supersecret"},
    )
    r = client.post(
        "/auth/login",
        json={"email": "carol@example.com", "password": "supersecret"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    assert token

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "carol@example.com"
    assert me.json()["role"] == "analyst"


def test_login_wrong_password_unauthorized(client: TestClient):
    client.post(
        "/auth/register",
        json={"email": "dave@example.com", "password": "supersecret"},
    )
    r = client.post(
        "/auth/login",
        json={"email": "dave@example.com", "password": "wrongpass1"},
    )
    assert r.status_code == 401


def test_me_without_token_unauthorized(client: TestClient):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_with_bad_token_unauthorized(client: TestClient):
    r = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert r.status_code == 401


def test_short_password_rejected(client: TestClient):
    r = client.post("/auth/register", json={"email": "x@example.com", "password": "short"})
    assert r.status_code == 422


def test_password_hash_roundtrip():
    """Unit test — no DB needed."""
    from app.auth.security import hash_password, verify_password

    hashed = hash_password("supersecret")
    assert verify_password("supersecret", hashed)
    assert not verify_password("wrongpass", hashed)


def test_jwt_encode_decode_roundtrip():
    """Unit test — no DB needed."""
    from app.auth.security import create_access_token, decode_access_token

    tok = create_access_token(user_id=42, role="analyst")
    claims = decode_access_token(tok)
    assert claims["sub"] == "42"
    assert claims["role"] == "analyst"


def test_jwt_rejects_tampered_signature():
    """Unit test — no DB needed."""
    import pytest

    from app.auth.security import TokenDecodeError, create_access_token, decode_access_token

    tok = create_access_token(user_id=1, role="viewer")
    tampered = tok[:-3] + ("aaa" if not tok.endswith("aaa") else "bbb")
    with pytest.raises(TokenDecodeError):
        decode_access_token(tampered)
