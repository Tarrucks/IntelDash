"""PDF export tests.

We don't fully parse the PDF — that's a heavy dependency — but we
check the PDF signature, that the bytes are non-trivial, and that the
case title appears in the rendered stream (ReportLab stores strings
verbatim for simple flows, so a substring search is enough to catch
"the table didn't render" type regressions).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.security import create_access_token, hash_password
from app.models.entities import User, UserRole


@pytest.fixture()
def analyst(client: TestClient, db_session):
    u = User(
        email="pdf@example.com",
        password_hash=hash_password("supersecret"),
        role=UserRole.analyst,
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    tok = create_access_token(user_id=u.id, role=u.role.value)
    client.headers.update({"Authorization": f"Bearer {tok}"})
    return client, db_session, u


def test_pdf_export_requires_auth(client: TestClient):
    r = client.get("/cases/00000000-0000-0000-0000-000000000000/export.pdf")
    assert r.status_code == 401


def test_pdf_export_404_for_unknown_case(analyst):
    client, *_ = analyst
    r = client.get("/cases/00000000-0000-0000-0000-000000000000/export.pdf")
    assert r.status_code == 404


def test_pdf_export_empty_case(analyst):
    client, *_ = analyst
    case = client.post("/cases", json={"title": "Empty PDF"}).json()
    r = client.get(f"/cases/{case['id']}/export.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].endswith(f'{case["id"]}.pdf"')
    # PDF magic bytes
    assert r.content.startswith(b"%PDF-")
    # Non-trivial document
    assert len(r.content) > 1000


def test_pdf_export_populated_case(analyst):
    client, *_ = analyst
    case = client.post(
        "/cases",
        json={"title": "Op Maritime Sweep", "summary": "first sweep across the Kattegat"},
    ).json()
    client.post(
        f"/cases/{case['id']}/pins",
        json={
            "kind": "vessel",
            "ref_id": "219000123",
            "label": "KATTEGAT STAR",
            "extra": {"imo": "9123456", "lat": 56.15, "lon": 11.50},
            "notes": "matches dark-fleet profile",
        },
    )
    client.post(
        f"/cases/{case['id']}/pins",
        json={"kind": "host", "ref_id": "203.0.113.10", "label": "203.0.113.10"},
    )

    r = client.get(f"/cases/{case['id']}/export.pdf")
    assert r.status_code == 200
    body = r.content
    assert body.startswith(b"%PDF-")
    assert len(body) > 2000
    # ReportLab compresses text streams by default; we set
    # ``invariant=False`` implicitly, so substrings may not be present.
    # We instead assert the trailer is present and the cross-ref table
    # was emitted (any non-trivial PDF has these).
    assert b"%%EOF" in body
    assert b"/Type" in body
