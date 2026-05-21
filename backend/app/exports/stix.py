"""STIX 2.1 bundle builder for Case File exports.

We hand-construct the JSON rather than pulling in the ``stix2`` package
— the schema we need is small, hand-built JSON is easier to audit, and
the dep tree on ``stix2`` is non-trivial for what amounts to ~10 SDO
shapes.

References:
  - STIX 2.1 spec: https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html
  - Bundle:        §4
  - Report SDO:    §4.16
  - Domain/URL/IP/Identity SCOs: §6

Pin-kind → STIX mapping:
  vessel    -> x-aperture-vessel (custom SCO; STIX 2.1 lacks a
                                  maritime-vessel primitive)
  aircraft  -> x-aperture-aircraft (custom SCO)
  host      -> ipv4-addr | ipv6-addr (parsed)
  url       -> url
  domain    -> domain-name
  *         -> identity (best-effort fallback)

Every non-trivial entity is also wrapped in an ``observed-data`` SDO so
the bundle is downstream-friendly with tools that expect SCOs to be
referenced from SDOs rather than free-standing in the bundle.

A ``report`` SDO ties the whole thing to the analyst's case.
"""

from __future__ import annotations

import ipaddress
import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.entities import Case, CaseEntity, User

STIX_VERSION = "2.1"


def _iso(dt: datetime) -> str:
    # STIX timestamps must be UTC ISO-8601 with a trailing Z and millis.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _stix_id(typ: str) -> str:
    return f"{typ}--{uuid.uuid4()}"


def _identity(user: User | None, created: str) -> dict:
    """The producing identity. Pinned to the case owner."""
    return {
        "type": "identity",
        "spec_version": STIX_VERSION,
        "id": _stix_id("identity"),
        "created": created,
        "modified": created,
        "name": (user.email if user else "aperture"),
        "identity_class": "individual" if user else "system",
    }


def _host_object(pin: CaseEntity) -> dict:
    """``host`` kind → ``ipv4-addr`` or ``ipv6-addr``."""
    ref = pin.entity.ref_id
    try:
        ip = ipaddress.ip_address(ref)
    except ValueError:
        # Not a parseable address — degrade to ``url``.
        return {
            "type": "url",
            "spec_version": STIX_VERSION,
            "id": _stix_id("url"),
            "value": ref,
        }
    typ = "ipv4-addr" if ip.version == 4 else "ipv6-addr"
    return {
        "type": typ,
        "spec_version": STIX_VERSION,
        "id": _stix_id(typ),
        "value": str(ip),
    }


def _vessel_object(pin: CaseEntity) -> dict:
    """Custom SCO (``x-aperture-vessel``).

    STIX 2.1 supports custom object types prefixed with ``x-``; we keep
    the mandatory fields (``type``, ``spec_version``, ``id``) and add
    domain-specific MMSI / IMO / name.
    """
    extra = pin.entity.extra or {}
    return {
        "type": "x-aperture-vessel",
        "spec_version": STIX_VERSION,
        "id": _stix_id("x-aperture-vessel"),
        "mmsi": pin.entity.ref_id,
        "name": pin.entity.label,
        "imo": extra.get("imo"),
        "vessel_type": extra.get("vessel_type"),
        "lat": extra.get("lat") or extra.get("latitude"),
        "lon": extra.get("lon") or extra.get("longitude"),
    }


def _aircraft_object(pin: CaseEntity) -> dict:
    extra = pin.entity.extra or {}
    return {
        "type": "x-aperture-aircraft",
        "spec_version": STIX_VERSION,
        "id": _stix_id("x-aperture-aircraft"),
        "icao24": pin.entity.ref_id,
        "registration": extra.get("registration"),
        "aircraft_type": extra.get("type") or extra.get("aircraft_type"),
        "callsign": extra.get("callsign") or pin.entity.label,
    }


def _simple_object(pin: CaseEntity, stix_type: str, value_key: str = "value") -> dict:
    return {
        "type": stix_type,
        "spec_version": STIX_VERSION,
        "id": _stix_id(stix_type),
        value_key: pin.entity.ref_id,
    }


def _identity_for_pin(pin: CaseEntity) -> dict:
    return {
        "type": "identity",
        "spec_version": STIX_VERSION,
        "id": _stix_id("identity"),
        "created": _iso(pin.pinned_at),
        "modified": _iso(pin.pinned_at),
        "name": pin.entity.label,
        "identity_class": pin.entity.kind,
    }


def _pin_to_object(pin: CaseEntity) -> dict:
    """Dispatch by ``pin.entity.kind``."""
    kind = pin.entity.kind
    if kind == "vessel":
        return _vessel_object(pin)
    if kind == "aircraft":
        return _aircraft_object(pin)
    if kind == "host":
        return _host_object(pin)
    if kind == "url":
        return _simple_object(pin, "url")
    if kind == "domain":
        return _simple_object(pin, "domain-name")
    return _identity_for_pin(pin)


def _observed_data(
    sco_id: str,
    *,
    identity_ref: str,
    first_seen: datetime,
    last_seen: datetime,
) -> dict:
    """Wrap a single SCO in an ``observed-data`` SDO.

    STIX 2.1 ``observed-data`` requires ``first_observed`` and
    ``last_observed`` plus ``number_observed >= 1``. Two-tool
    investigations often look for SCOs as members of an
    ``object_refs`` list rather than free-standing in the bundle.
    """
    now = _iso(datetime.now(UTC))
    return {
        "type": "observed-data",
        "spec_version": STIX_VERSION,
        "id": _stix_id("observed-data"),
        "created": now,
        "modified": now,
        "created_by_ref": identity_ref,
        "first_observed": _iso(first_seen),
        "last_observed": _iso(last_seen),
        "number_observed": 1,
        "object_refs": [sco_id],
    }


def build_bundle(case: Case, owner: User | None) -> dict[str, Any]:
    """Build a STIX 2.1 ``bundle`` for ``case``.

    Layout:
      identity (producer)
      one SCO per pin
      one observed-data per pin (refs the SCO)
      report (refs identity + all observed-data)
    """
    created = _iso(case.created_at)
    identity = _identity(owner, created)
    objects: list[dict] = [identity]

    observed_refs: list[str] = []
    for pin in sorted(case.pins, key=lambda p: p.pinned_at):
        sco = _pin_to_object(pin)
        obs = _observed_data(
            sco["id"],
            identity_ref=identity["id"],
            first_seen=pin.pinned_at,
            last_seen=pin.pinned_at,
        )
        if pin.notes:
            obs["x_aperture_notes"] = pin.notes
        objects.append(sco)
        objects.append(obs)
        observed_refs.append(obs["id"])

    report = {
        "type": "report",
        "spec_version": STIX_VERSION,
        "id": _stix_id("report"),
        "created": created,
        "modified": _iso(case.updated_at),
        "created_by_ref": identity["id"],
        "name": case.title,
        "description": case.summary or "",
        "published": _iso(case.updated_at),
        "report_types": ["threat-report"],
        "object_refs": [identity["id"], *observed_refs],
    }
    objects.append(report)

    return {
        "type": "bundle",
        "id": _stix_id("bundle"),
        "objects": objects,
    }
