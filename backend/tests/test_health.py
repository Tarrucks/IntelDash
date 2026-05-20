"""Health endpoint smoke test."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["app"] == "ok"
    # db should be reachable in our test setup
    assert body["checks"]["db"] == "ok"
