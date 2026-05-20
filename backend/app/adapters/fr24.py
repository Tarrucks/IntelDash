"""Flightradar24 adapter — Aviation Live.

Auth: ``Authorization: Bearer <key>`` per the FR24 B2B API. Sandbox key
works for unbilled endpoint testing; production needs an Explorer+
subscription. **Never** scrape the consumer site — it violates ToS.

Endpoints we wire (https://fr24api.flightradar24.com/docs/endpoints/overview):
  - GET /api/live/flight-positions/full
  - GET /api/flight-summary/light  (Phase 7+)
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.adapters.base import SourceAdapter
from app.schemas.fr24 import FlightPosition, LiveFlightsResponse

BASE_URL = "https://fr24api.flightradar24.com"


class FR24Adapter(SourceAdapter):
    name = "fr24"

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.fr24_api_key)

    # ---- Public surface --------------------------------------------------

    def live_positions(
        self,
        *,
        bounds: tuple[float, float, float, float] | None = None,
        limit: int = 100,
    ) -> LiveFlightsResponse:
        """Live flight positions, optionally constrained to ``(N, S, W, E)``."""
        if self.mode == "mock":
            return self._mock_live(bounds, limit)
        return self._real_live(bounds, limit)

    # ---- Mock implementations -------------------------------------------

    @staticmethod
    def _mock_live(
        bounds: tuple[float, float, float, float] | None, limit: int
    ) -> LiveFlightsResponse:
        # Centre on bounds if given, else use a Northern-European default.
        if bounds is not None:
            n, s, w, e = bounds
            lat0 = (n + s) / 2
            lon0 = (w + e) / 2
        else:
            lat0, lon0 = 55.0, 12.0  # near Copenhagen

        now = datetime.now(UTC).isoformat()
        flights = [
            FlightPosition.model_validate(
                {
                    "fr24_id": f"mock-{i:04d}",
                    "hex": f"4{i:05x}",
                    "callsign": f"SAS{1000 + i}",
                    "lat": lat0 + 0.1 * (i - limit // 2),
                    "lon": lon0 + 0.1 * (i - limit // 2),
                    "track": 90.0,
                    "alt": 35000 - 500 * i,
                    "gspeed": 450 + 5 * i,
                    "vspeed": 0,
                    "squawk": "1000",
                    "timestamp": now,
                    "source": "MOCK",
                    "reg": f"SE-MO{i:02d}",
                    "type": "A320" if i % 2 == 0 else "B738",
                    "painted_as": "SAS",
                    "operating_as": "SAS",
                    "orig_iata": "CPH",
                    "orig_icao": "EKCH",
                    "dest_iata": "ARN",
                    "dest_icao": "ESSA",
                    "flight": f"SK{i + 100}",
                }
            )
            for i in range(min(limit, 5))
        ]
        return LiveFlightsResponse(data=flights)

    # ---- Real implementations -------------------------------------------

    def _real_live(
        self, bounds: tuple[float, float, float, float] | None, limit: int
    ) -> LiveFlightsResponse:
        ok, retry = self.acquire(scope="live")
        if not ok:
            raise RuntimeError(f"Rate-limited; retry in {retry:.1f}s")
        params: dict = {"limit": limit}
        if bounds is not None:
            n, s, w, e = bounds
            params["bounds"] = f"{n},{s},{w},{e}"
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                f"{BASE_URL}/api/live/flight-positions/full",
                headers={
                    "Authorization": f"Bearer {self.settings.fr24_api_key}",
                    "Accept": "application/json",
                    "Accept-Version": "v1",
                },
                params=params,
            )
            resp.raise_for_status()
            return LiveFlightsResponse.model_validate(resp.json())
