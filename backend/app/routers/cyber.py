"""Cyber Surface router.

Wraps the Shodan adapter. The host lookup additionally upserts the
result into the ``hosts`` table so the analyst can later pin it from
the Case File without another Shodan credit being spent.

Endpoints:
  GET /cyber/hosts/{ip}              host lookup (+ persist)
  GET /cyber/search?q=&limit=        Shodan host search
"""

from __future__ import annotations

import ipaddress

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.registry import get_adapter
from app.auth.dependencies import get_current_user
from app.core.db import get_db
from app.models.entities import Host, User
from app.schemas.cyber import (
    CyberBanner,
    CyberHost,
    CyberSearchMatch,
    CyberSearchResponse,
)

router = APIRouter(prefix="/cyber", tags=["cyber"])


def _validate_ip(ip: str) -> str:
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"not a valid IP address: {ip}",
        ) from exc


def _persist_host(db: Session, host: CyberHost, raw: dict) -> None:
    """Upsert a host record so the Case File can reference it later.

    We persist only the high-level fields here; the full Shodan payload
    lives in ``raw`` (jsonb) so analysts can drill into details later
    without another API call.
    """
    from sqlalchemy import text

    existing = db.execute(select(Host).where(Host.ip == host.ip)).scalar_one_or_none()
    if existing is None:
        existing = Host(ip=host.ip)
        db.add(existing)
    existing.hostname = host.hostnames[0] if host.hostnames else existing.hostname
    existing.org = host.org or existing.org
    existing.asn = host.asn or existing.asn
    existing.country = host.country_code or existing.country
    existing.last_seen = host.last_update or existing.last_seen
    existing.raw = raw

    # Flush so the row exists for the raw geom UPDATE below; the
    # PostGIS POINT can't be set via the ORM mapper without a custom
    # type comparator, so we route it through a small UPDATE.
    db.flush()

    if host.latitude is not None and host.longitude is not None:
        db.execute(
            text(
                "UPDATE hosts SET location = "
                "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography "
                "WHERE ip = :ip"
            ),
            {"lat": host.latitude, "lon": host.longitude, "ip": host.ip},
        )
    db.commit()


@router.get("/hosts/{ip}", response_model=CyberHost)
def host_lookup(
    ip: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CyberHost:
    ip = _validate_ip(ip)
    adapter = get_adapter("shodan")
    raw = adapter.host(ip)

    cyber = CyberHost(
        ip=raw.ip_str,
        hostnames=raw.hostnames,
        ports=raw.ports,
        country_code=raw.country_code,
        city=raw.city,
        org=raw.org,
        isp=raw.isp,
        asn=raw.asn,
        latitude=raw.latitude,
        longitude=raw.longitude,
        last_update=raw.last_update,
        banners=[
            CyberBanner(
                port=b.port,
                transport=b.transport,
                product=b.product,
                version=b.version,
                banner=b.banner,
                timestamp=b.timestamp,
            )
            for b in raw.data
        ],
        source="shodan" if adapter.mode == "real" else "mock",
    )
    _persist_host(db, cyber, raw.model_dump(mode="json"))
    return cyber


@router.get("/search", response_model=CyberSearchResponse)
def search(
    q: str = Query(..., min_length=1, max_length=512),
    limit: int = Query(10, ge=1, le=100),
    _: User = Depends(get_current_user),
) -> CyberSearchResponse:
    adapter = get_adapter("shodan")
    raw = adapter.search(q, limit=limit)
    return CyberSearchResponse(
        total=raw.total,
        query=q,
        sources=[f"shodan({adapter.mode})"],
        matches=[
            CyberSearchMatch(
                ip=m.ip_str,
                port=m.port,
                org=m.org,
                product=m.product,
                location=m.location,
                timestamp=m.timestamp,
            )
            for m in raw.matches
        ],
    )
