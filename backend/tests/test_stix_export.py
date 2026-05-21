"""STIX 2.1 export tests.

Validates the bundle shape against the STIX 2.1 minimum-required-fields
list. Doesn't run a full schema validator (too heavy for v1); the
asserts target the fields that matter for downstream tools.
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from app.auth.security import create_access_token, hash_password
from app.models.entities import User, UserRole

UUID_RE = re.compile(r"^[a-z0-9-]+--[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


@pytest.fixture()
def analyst(client: TestClient, db_session):
    u = User(
        email="stix@example.com",
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


def _populated_case(client: TestClient) -> str:
    case = client.post("/cases", json={"title": "STIX Export", "summary": "for test"}).json()
    client.post(
        f"/cases/{case['id']}/pins",
        json={
            "kind": "vessel",
            "ref_id": "219000123",
            "label": "KATTEGAT STAR",
            "extra": {"imo": "9123456", "lat": 56.15, "lon": 11.50, "vessel_type": "Cargo"},
            "notes": "matches profile",
        },
    )
    client.post(
        f"/cases/{case['id']}/pins",
        json={"kind": "host", "ref_id": "203.0.113.10", "label": "203.0.113.10"},
    )
    client.post(
        f"/cases/{case['id']}/pins",
        json={"kind": "url", "ref_id": "https://example.com/leak", "label": "leak"},
    )
    return case["id"]


def test_stix_export_requires_auth(client: TestClient):
    r = client.get("/cases/00000000-0000-0000-0000-000000000000/export.stix")
    assert r.status_code == 401


def test_stix_export_unknown_case_404(analyst):
    client, *_ = analyst
    r = client.get("/cases/00000000-0000-0000-0000-000000000000/export.stix")
    assert r.status_code == 404


def test_stix_export_returns_valid_bundle(analyst):
    client, *_ = analyst
    case_id = _populated_case(client)

    r = client.get(f"/cases/{case_id}/export.stix")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/stix+json")
    assert f"aperture-case-{case_id}.json" in r.headers["content-disposition"]

    bundle = json.loads(r.content)
    assert bundle["type"] == "bundle"
    assert UUID_RE.match(bundle["id"])
    assert bundle["id"].startswith("bundle--")
    assert isinstance(bundle["objects"], list)


def test_stix_export_includes_all_required_objects(analyst):
    client, *_ = analyst
    case_id = _populated_case(client)
    bundle = client.get(f"/cases/{case_id}/export.stix").json()

    types = [o["type"] for o in bundle["objects"]]
    # Exactly one identity (producer), one report.
    assert types.count("identity") == 1
    assert types.count("report") == 1
    # One observed-data per pin.
    assert types.count("observed-data") == 3
    # SCOs for each kind we pinned.
    assert "x-aperture-vessel" in types
    assert "ipv4-addr" in types
    assert "url" in types


def test_stix_observed_data_refs_resolve(analyst):
    """Every observed-data.object_refs entry must point at an SCO in the bundle."""
    client, *_ = analyst
    case_id = _populated_case(client)
    bundle = client.get(f"/cases/{case_id}/export.stix").json()
    ids = {o["id"] for o in bundle["objects"]}
    for obj in bundle["objects"]:
        if obj["type"] != "observed-data":
            continue
        for ref in obj["object_refs"]:
            assert ref in ids, f"dangling ref {ref}"


def test_stix_report_refs_observed_data(analyst):
    client, *_ = analyst
    case_id = _populated_case(client)
    bundle = client.get(f"/cases/{case_id}/export.stix").json()
    report = next(o for o in bundle["objects"] if o["type"] == "report")
    observed_ids = {o["id"] for o in bundle["objects"] if o["type"] == "observed-data"}
    report_refs = set(report["object_refs"])
    # Report should reference every observed-data SDO + the identity.
    assert observed_ids.issubset(report_refs)


def test_stix_required_fields_present(analyst):
    """Spot-check the required STIX 2.1 fields on each object."""
    client, *_ = analyst
    case_id = _populated_case(client)
    bundle = client.get(f"/cases/{case_id}/export.stix").json()

    for obj in bundle["objects"]:
        assert "type" in obj
        assert "id" in obj
        assert "spec_version" in obj
        assert obj["spec_version"] == "2.1"
        if obj["type"] in {"identity", "observed-data", "report"}:
            assert "created" in obj
            assert "modified" in obj
        if obj["type"] == "observed-data":
            assert obj["number_observed"] >= 1
            assert obj["first_observed"]
            assert obj["last_observed"]


def test_stix_export_with_empty_case_succeeds(analyst):
    client, *_ = analyst
    case = client.post("/cases", json={"title": "Empty"}).json()
    bundle = client.get(f"/cases/{case['id']}/export.stix").json()
    types = [o["type"] for o in bundle["objects"]]
    # Identity + report only; no SCOs.
    assert types == ["identity", "report"]
