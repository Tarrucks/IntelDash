"""BarentsWatch Historic AIS adapter.

OAuth2 client_credentials flow. Token endpoint:
    POST https://id.barentswatch.no/connect/token
    body: client_id, client_secret, scope=ais, grant_type=client_credentials

Historic AIS API returns GeoJSON FeatureCollection from:
  - /v1/historic/trackslast24hours/{mmsi}
  - /v1/historic/tracks/{mmsi}/{fromDate}/{toDate}

We cache the access token in memory until 60s before expiry. (A
multi-process deploy should move this to Redis, but v1 stays simple.)
"""

from __future__ import annotations

import time
from datetime import datetime

import httpx

from app.adapters.base import SourceAdapter
from app.schemas.barentswatch import GeoJSONFeature, GeoJSONFeatureCollection

TOKEN_URL = "https://id.barentswatch.no/connect/token"
API_BASE = "https://historic.ais.barentswatch.no"


class BarentsWatchAdapter(SourceAdapter):
    name = "barentswatch"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # (access_token, expires_at_epoch)
        self._token: tuple[str, float] | None = None

    @property
    def is_configured(self) -> bool:
        return self.settings.barentswatch_configured

    # ---- Public surface --------------------------------------------------

    def tracks_last_24h(self, mmsi: str) -> GeoJSONFeatureCollection:
        if self.mode == "mock":
            return self._mock_tracks(mmsi)
        return self._real_tracks_last_24h(mmsi)

    def tracks_range(
        self, mmsi: str, from_dt: datetime, to_dt: datetime
    ) -> GeoJSONFeatureCollection:
        if self.mode == "mock":
            return self._mock_tracks(mmsi)
        return self._real_tracks_range(mmsi, from_dt, to_dt)

    # ---- Mock implementations -------------------------------------------

    @staticmethod
    def _mock_tracks(mmsi: str) -> GeoJSONFeatureCollection:
        # A synthetic 4-point Kattegat-area track for the requested MMSI.
        coords = [
            [11.500, 56.150],
            [11.521, 56.162],
            [11.542, 56.174],
            [11.563, 56.186],
        ]
        return GeoJSONFeatureCollection(
            features=[
                GeoJSONFeature(
                    geometry={"type": "LineString", "coordinates": coords},
                    properties={
                        "mmsi": mmsi,
                        "source": "mock",
                        "fromDate": "2026-05-19T08:00:00Z",
                        "toDate": "2026-05-19T08:15:00Z",
                    },
                )
            ]
        )

    # ---- Real implementations -------------------------------------------

    def _get_token(self) -> str:
        now = time.time()
        if self._token and self._token[1] - 60 > now:
            return self._token[0]
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                TOKEN_URL,
                data={
                    "client_id": self.settings.barentswatch_client_id,
                    "client_secret": self.settings.barentswatch_client_secret,
                    "scope": "ais",
                    "grant_type": "client_credentials",
                },
            )
            resp.raise_for_status()
            payload = resp.json()
        access = payload["access_token"]
        # ``expires_in`` is seconds; fall back to 5min if absent.
        expires_in = int(payload.get("expires_in", 300))
        self._token = (access, now + expires_in)
        return access

    def _get(self, path: str) -> dict:
        ok, retry = self.acquire(scope=path)
        if not ok:
            raise RuntimeError(f"Rate-limited; retry in {retry:.1f}s")
        token = self._get_token()
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                f"{API_BASE}{path}",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.json()

    def _real_tracks_last_24h(self, mmsi: str) -> GeoJSONFeatureCollection:
        data = self._get(f"/v1/historic/trackslast24hours/{mmsi}")
        return GeoJSONFeatureCollection.model_validate(data)

    def _real_tracks_range(
        self, mmsi: str, from_dt: datetime, to_dt: datetime
    ) -> GeoJSONFeatureCollection:
        # The endpoint expects ISO8601 dates in the URL path.
        path = f"/v1/historic/tracks/{mmsi}/" f"{from_dt.isoformat()}/{to_dt.isoformat()}"
        return GeoJSONFeatureCollection.model_validate(self._get(path))
