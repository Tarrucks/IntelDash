"""Aviation Tracking router.

Wraps the Flightradar24 adapter. The brief gates real FR24 access
behind FR24_API_KEY; with no key the adapter ships realistic mock
positions so the dashboard demo flow runs key-free.

Endpoints:
  GET /aviation/live                        snapshots in optional bbox
  GET /aviation/flights/{hex}               flight detail (latest position)
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.adapters.registry import get_adapter
from app.auth.dependencies import get_current_user
from app.models.entities import User
from app.schemas.aviation import FlightSnapshot, LiveFlightsResponse

router = APIRouter(prefix="/aviation", tags=["aviation"])


def _to_snapshot(fp, *, source: str) -> FlightSnapshot:  # FlightPosition
    return FlightSnapshot(
        fr24_id=fp.fr24_id,
        hex=fp.hex,
        callsign=fp.callsign,
        lat=fp.lat,
        lon=fp.lon,
        track=fp.track,
        alt=fp.alt,
        gspeed=fp.gspeed,
        timestamp=fp.timestamp,
        reg=fp.reg,
        type=fp.type,
        flight=fp.flight,
        orig_iata=fp.orig_iata,
        dest_iata=fp.dest_iata,
        source=source,
    )


@router.get("/live", response_model=LiveFlightsResponse)
def live(
    latmin: float | None = Query(None, ge=-90, le=90),
    latmax: float | None = Query(None, ge=-90, le=90),
    lonmin: float | None = Query(None, ge=-180, le=180),
    lonmax: float | None = Query(None, ge=-180, le=180),
    limit: int = Query(100, ge=1, le=500),
    _: User = Depends(get_current_user),
) -> LiveFlightsResponse:
    # All four bounds are required together; partial bbox is a 400.
    parts = [latmin, latmax, lonmin, lonmax]
    bbox_payload: dict | None = None
    bounds_arg: tuple[float, float, float, float] | None = None
    if any(p is not None for p in parts):
        if any(p is None for p in parts):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="latmin/latmax/lonmin/lonmax must be supplied together",
            )
        assert latmin is not None and latmax is not None
        assert lonmin is not None and lonmax is not None
        if latmin >= latmax or lonmin >= lonmax:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="latmin must be < latmax and lonmin must be < lonmax",
            )
        # FR24 bounds order is (north, south, west, east).
        bounds_arg = (latmax, latmin, lonmin, lonmax)
        bbox_payload = {
            "latmin": latmin,
            "latmax": latmax,
            "lonmin": lonmin,
            "lonmax": lonmax,
        }

    adapter = get_adapter("fr24")
    resp = adapter.live_positions(bounds=bounds_arg, limit=limit)
    sources = [f"fr24({adapter.mode})"]
    src = "fr24" if adapter.mode == "real" else "mock"

    return LiveFlightsResponse(
        bbox=bbox_payload,
        fetched_at=datetime.now(UTC),
        sources=sources,
        flights=[_to_snapshot(fp, source=src) for fp in resp.data],
    )


@router.get("/flights/{hex_id}", response_model=FlightSnapshot)
def flight_detail(
    hex_id: str,
    _: User = Depends(get_current_user),
) -> FlightSnapshot:
    """Latest snapshot for an aircraft by its ICAO 24-bit hex.

    We do not maintain an FR24 single-flight cache in v1; the implementation
    pulls a fresh ``live`` page and returns the matching row. Mock mode
    fabricates one if no row matches so demos never 404.
    """
    adapter = get_adapter("fr24")
    src = "fr24" if adapter.mode == "real" else "mock"

    resp = adapter.live_positions(limit=500)
    hex_lc = hex_id.lower()
    for fp in resp.data:
        if fp.hex.lower() == hex_lc:
            return _to_snapshot(fp, source=src)

    if adapter.mode == "mock":
        # Stitch together a synthetic snapshot using the hex string.
        return FlightSnapshot(
            fr24_id=f"mock-{hex_lc}",
            hex=hex_lc,
            callsign="MOCKED",
            lat=0.0,
            lon=0.0,
            timestamp=datetime.now(UTC),
            type="UNK",
            source="mock",
        )
    raise HTTPException(status_code=404, detail=f"aircraft {hex_id} not found")
