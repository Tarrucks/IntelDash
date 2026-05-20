"""AI Web Search router integration tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.security import create_access_token, hash_password
from app.models.entities import User, UserRole


@pytest.fixture()
def authed_client(client: TestClient, db_session):
    user = User(
        email="web@example.com",
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


def test_search_requires_auth(client: TestClient):
    assert client.get("/web/search?q=AIS").status_code == 401


def test_search_short_query_rejected(authed_client):
    r = authed_client.get("/web/search?q=a")
    assert r.status_code == 422


def test_search_invalid_mode_rejected(authed_client):
    r = authed_client.get("/web/search?q=AIS&mode=blazing")
    assert r.status_code == 422


def test_search_returns_results_in_descending_score_order(authed_client):
    r = authed_client.get("/web/search?q=missile+defense&num_results=4")
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "missile defense"
    assert len(body["results"]) == 4
    scores = [r["score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)


def test_answer_returns_citations(authed_client):
    r = authed_client.get("/web/answer?q=what+is+AIS")
    assert r.status_code == 200
    body = r.json()
    assert body["answer"]
    assert len(body["citations"]) >= 1
    assert all(c["url"].startswith("http") for c in body["citations"])
