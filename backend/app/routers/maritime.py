"""Maritime Domain Awareness router.

The brief mounts the AISHub live feed, the Kaggle-seeded
``vessel_positions`` hypertable, and BarentsWatch historic tracks
behind one dashboard. The router fuses those sources so the frontend
only has to know about three endpoints:

  GET /maritime/live                            -> snapshots in bbox
  GET /maritime/vessels/{mmsi}                  -> vessel detail
  GET /maritime/vessels/{mmsi}/tracks?from=&to= -> track polyline(s)

All endpoints work end-to-end in mock mode (no API keys).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.registry import get_adapter
from app.auth.dependencies import get_current_user
from app.core.db import get_db
from app.models.entities import User, Vessel
from app.models.positions import VesselPosition
from app.schemas.maritime import (
    LiveVesselsResponse,
    VesselDetail,
    VesselSnapshot,
    VesselTracksResponse,
)

router = APIRouter(prefix="/maritime", tags=["maritime"])


# ---- Helpers ---------------------------------------------------------------


def _latest_positions_in_bbox(
    db: Session,
    latmin: float,
    latmax: float,
    lonmin: float,
    lonmax: float,
    limit: int,
) -> list[VesselPosition]:
    """Per-vessel most recent position falling inside the bbox.

    The naive ``ORDER BY time DESC LIMIT N`` would lose vessels that
    moved out of view recently; we group by ``mmsi`` and take the
    latest sample for each.
    """
    # DISTINCT ON is Postgres-specific and gives us O(n log n) without
    # a subquery. Index ``ix_vessel_positions_mmsi_time`` already covers
    # the ordering.
    stmt = (
        select(VesselPosition)
        .where(
            VesselPosition.lat.between(latmin, latmax),
            VesselPosition.lon.between(lonmin, lonmax),
        )
        .distinct(VesselPosition.mmsi)
        .order_by(VesselPosition.mmsi, VesselPosition.time.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def _vessel_label(db: Session, mmsi: str) -> Vessel | None:
    return db.execute(select(Vessel).where(Vessel.mmsi == mmsi)).scalar_one_or_none()


# ---- Endpoints -------------------------------------------------------------


@router.get("/live", response_model=LiveVesselsResponse)
def live(
    latmin: float = Query(..., ge=-90, le=90),
    latmax: float = Query(..., ge=-90, le=90),
    lonmin: float = Query(..., ge=-180, le=180),
    lonmax: float = Query(..., ge=-180, le=180),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> LiveVesselsResponse:
    if latmin >= latmax or lonmin >= lonmax:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="latmin must be < latmax and lonmin must be < lonmax",
        )

    sources: list[str] = []
    by_mmsi: dict[str, VesselSnapshot] = {}

    # 1) The Kaggle / future-MarineCadastre data already in the hypertable.
    db_rows = _latest_positions_in_bbox(db, latmin, latmax, lonmin, lonmax, limit)
    if db_rows:
        sources.append("db")
        labels = {
            v.mmsi: v
            for v in db.execute(
                select(Vessel).where(Vessel.mmsi.in_({r.mmsi for r in db_rows}))
            ).scalars()
        }
        for r in db_rows:
            v = labels.get(r.mmsi)
            by_mmsi[r.mmsi] = VesselSnapshot(
                mmsi=r.mmsi,
                name=v.name if v else None,
                imo=v.imo if v else None,
                call_sign=v.call_sign if v else None,
                vessel_type=v.vessel_type if v else None,
                time=r.time,
                lat=r.lat,
                lon=r.lon,
                sog=r.sog,
                cog=r.cog,
                heading=r.heading,
                nav_status=r.nav_status,
                source=r.source,  # type: ignore[arg-type]
            )

    # 2) Layer the live AISHub feed on top. Live data wins on conflicts.
    adapter = get_adapter("aishub")
    try:
        live_vessels = adapter.fetch_bbox(latmin, latmax, lonmin, lonmax)
    except RuntimeError:
        # 1/min cap hit or upstream error — degrade gracefully to DB data.
        live_vessels = []
    if live_vessels:
        sources.append(f"aishub({adapter.mode})")
        for v in live_vessels:
            by_mmsi[v.mmsi] = VesselSnapshot(
                mmsi=v.mmsi,
                name=v.name,
                imo=v.imo,
                call_sign=v.callsign,
                vessel_type=str(v.type) if v.type is not None else None,
                time=v.time,
                lat=v.latitude,
                lon=v.longitude,
                sog=v.sog,
                cog=v.cog,
                heading=v.heading,
                nav_status=str(v.navstat) if v.navstat is not None else None,
                source="aishub" if adapter.mode == "real" else "mock",
            )

    return LiveVesselsResponse(
        bbox={"latmin": latmin, "latmax": latmax, "lonmin": lonmin, "lonmax": lonmax},
        fetched_at=datetime.now(UTC),
        sources=sources or ["empty"],
        vessels=list(by_mmsi.values()),
    )


@router.get("/vessels/{mmsi}", response_model=VesselDetail)
def vessel_detail(
    mmsi: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> VesselDetail:
    vessel = _vessel_label(db, mmsi)
    last_pos = db.execute(
        select(VesselPosition)
        .where(VesselPosition.mmsi == mmsi)
        .order_by(VesselPosition.time.desc())
        .limit(1)
    ).scalar_one_or_none()
    history_count = (
        db.execute(
            select(func.count()).select_from(VesselPosition).where(VesselPosition.mmsi == mmsi)
        ).scalar_one()
        or 0
    )

    if vessel is None and last_pos is None:
        # Unknown vessel — but still synthesise a record from the AISHub
        # adapter in mock mode so the dashboard's "Search by MMSI" flow
        # never dead-ends during demos.
        adapter = get_adapter("aishub")
        if adapter.mode == "mock":
            return VesselDetail(mmsi=mmsi)
        raise HTTPException(status_code=404, detail=f"vessel {mmsi} not found")

    snap: VesselSnapshot | None = None
    if last_pos is not None:
        snap = VesselSnapshot(
            mmsi=mmsi,
            name=vessel.name if vessel else None,
            imo=vessel.imo if vessel else None,
            call_sign=vessel.call_sign if vessel else None,
            vessel_type=vessel.vessel_type if vessel else None,
            time=last_pos.time,
            lat=last_pos.lat,
            lon=last_pos.lon,
            sog=last_pos.sog,
            cog=last_pos.cog,
            heading=last_pos.heading,
            nav_status=last_pos.nav_status,
            source=last_pos.source,  # type: ignore[arg-type]
        )

    return VesselDetail(
        mmsi=mmsi,
        name=vessel.name if vessel else None,
        imo=vessel.imo if vessel else None,
        call_sign=vessel.call_sign if vessel else None,
        vessel_type=vessel.vessel_type if vessel else None,
        length_m=vessel.length_m if vessel else None,
        width_m=vessel.width_m if vessel else None,
        flag=vessel.flag if vessel else None,
        last_position=snap,
        position_history_count=int(history_count),
    )


@router.get("/vessels/{mmsi}/tracks", response_model=VesselTracksResponse)
def vessel_tracks(
    mmsi: str,
    _: User = Depends(get_current_user),
) -> VesselTracksResponse:
    """Replay polyline(s) for a single vessel.

    Phase 5.1 uses BarentsWatch's last-24h endpoint via the adapter
    (mock by default). Later we'll also expose a DB-only path that
    builds a LineString from the hypertable for vessels with seeded
    history.
    """
    adapter = get_adapter("barentswatch")
    fc = adapter.tracks_last_24h(mmsi)
    return VesselTracksResponse(
        mmsi=mmsi,
        source="barentswatch" if adapter.mode == "real" else "mock",
        tracks=fc,
    )
