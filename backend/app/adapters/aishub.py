"""AISHub adapter — Maritime Live.

Endpoint: http://data.aishub.net/ws.php
Auth: ``username`` query parameter (issued to contributing members).

**The webservice silently returns empty if polled more than once per
minute.** Our token bucket (capacity=1, refill=1/60) enforces that. The
real adapter must not bypass it; the mock skips the bucket so tests run
fast.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.adapters.base import SourceAdapter
from app.schemas.aishub import AisVessel

ENDPOINT = "http://data.aishub.net/ws.php"


class AISHubAdapter(SourceAdapter):
    name = "aishub"

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.aishub_username)

    # ---- Public surface --------------------------------------------------

    def fetch_bbox(
        self,
        latmin: float,
        latmax: float,
        lonmin: float,
        lonmax: float,
    ) -> list[AisVessel]:
        """Vessels currently inside the given lat/lon bounding box."""
        if self.mode == "mock":
            return self._mock_bbox(latmin, latmax, lonmin, lonmax)
        return self._real_bbox(latmin, latmax, lonmin, lonmax)

    # ---- Mock implementations -------------------------------------------

    @staticmethod
    def _mock_bbox(latmin: float, latmax: float, lonmin: float, lonmax: float) -> list[AisVessel]:
        # Sprinkle a few synthetic vessels inside the requested bbox.
        # Coordinates are deterministic so dashboard snapshots are stable.
        now = datetime.now(UTC).isoformat()
        lat_mid = (latmin + latmax) / 2
        lon_mid = (lonmin + lonmax) / 2
        return [
            AisVessel.model_validate(
                {
                    "mmsi": "219000123",
                    "time": now,
                    "latitude": lat_mid + 0.05,
                    "longitude": lon_mid + 0.05,
                    "cog": 45.0,
                    "sog": 12.4,
                    "heading": 46,
                    "navstat": 0,
                    "imo": "9123456",
                    "name": "KATTEGAT STAR",
                    "callsign": "OZAB",
                    "type": 70,
                }
            ),
            AisVessel.model_validate(
                {
                    "mmsi": "266001234",
                    "time": now,
                    "latitude": lat_mid - 0.04,
                    "longitude": lon_mid + 0.01,
                    "cog": 180.0,
                    "sog": 8.2,
                    "heading": 180,
                    "navstat": 0,
                    "imo": "9234567",
                    "name": "GOTHIA TANKER",
                    "callsign": "SBCD",
                    "type": 80,
                }
            ),
        ]

    # ---- Real implementations -------------------------------------------

    def _real_bbox(
        self, latmin: float, latmax: float, lonmin: float, lonmax: float
    ) -> list[AisVessel]:
        ok, retry = self.acquire(scope="bbox")
        if not ok:
            raise RuntimeError(f"AISHub poll cap (1/min) hit; retry in {retry:.1f}s")
        params = {
            "username": self.settings.aishub_username,
            "format": "1",  # json
            "output": "json",
            "compress": "0",
            "latmin": latmin,
            "latmax": latmax,
            "lonmin": lonmin,
            "lonmax": lonmax,
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(ENDPOINT, params=params)
            resp.raise_for_status()
            payload = resp.json()
        # AISHub returns [[meta], [vessels...]] when format=json.
        if not isinstance(payload, list) or len(payload) < 2:
            return []
        meta = payload[0][0] if payload[0] else {}
        if isinstance(meta, dict) and meta.get("ERROR"):
            raise RuntimeError(f"AISHub error: {meta.get('ERROR_MESSAGE', 'unknown')}")
        vessels = payload[1]
        return [AisVessel.model_validate({k.lower(): v for k, v in row.items()}) for row in vessels]
