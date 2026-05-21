"""Shodan adapter — Cyber Surface.

Auth: ``?key=`` query parameter on every request (no header auth).
Base URL: https://api.shodan.io

Endpoints we wire:
  - GET /shodan/host/{ip}
  - GET /shodan/host/search?query=...

Note Shodan rate-limits by monthly *credits*, not RPS. The token
bucket in SOURCE_LIMITS["shodan"] is a politeness floor only.
"""

from __future__ import annotations

import httpx

from app.adapters.base import SourceAdapter
from app.schemas.shodan import ShodanHost, ShodanSearchMatch, ShodanSearchResponse

BASE_URL = "https://api.shodan.io"


class ShodanAdapter(SourceAdapter):
    name = "shodan"

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.shodan_api_key)

    # ---- Public surface --------------------------------------------------

    def host(self, ip: str) -> ShodanHost:
        if self.mode == "mock":
            return self._mock_host(ip)
        return self._real_host(ip)

    def search(self, query: str, limit: int = 10) -> ShodanSearchResponse:
        if self.mode == "mock":
            return self._mock_search(query, limit)
        return self._real_search(query, limit)

    # ---- Mock implementations -------------------------------------------

    @staticmethod
    def _mock_host(ip: str) -> ShodanHost:
        return ShodanHost.model_validate(
            {
                "ip_str": ip,
                "hostnames": ["mock.example.com"],
                "ports": [22, 80, 443],
                "country_code": "US",
                "country_name": "United States",
                "city": "Ashburn",
                "org": "MockHost LLC",
                "isp": "MockNet",
                "asn": "AS64500",
                "latitude": 39.0438,
                "longitude": -77.4874,
                "last_update": "2026-05-19T12:00:00Z",
                "data": [
                    {
                        "port": 22,
                        "transport": "tcp",
                        "product": "OpenSSH",
                        "version": "9.3",
                        "data": "SSH-2.0-OpenSSH_9.3",
                        "timestamp": "2026-05-19T10:12:33Z",
                    },
                    {
                        "port": 443,
                        "transport": "tcp",
                        "product": "nginx",
                        "version": "1.27.0",
                        "data": "HTTP/1.1 200 OK\\r\\nServer: nginx/1.27.0",
                        "timestamp": "2026-05-19T11:01:18Z",
                    },
                ],
            }
        )

    @staticmethod
    def _mock_search(query: str, limit: int) -> ShodanSearchResponse:  # noqa: ARG004
        matches = [
            ShodanSearchMatch.model_validate(
                {
                    "ip_str": f"203.0.113.{i + 1}",
                    "port": 443 if i % 2 == 0 else 22,
                    "org": "MockHost LLC",
                    "product": "nginx" if i % 2 == 0 else "OpenSSH",
                    "location": {"country_code": "US", "city": "Ashburn"},
                    "timestamp": "2026-05-19T12:00:00Z",
                }
            )
            for i in range(min(limit, 5))
        ]
        return ShodanSearchResponse(total=len(matches), matches=matches, facets=None)

    # ---- Real implementations -------------------------------------------

    def _real_host(self, ip: str) -> ShodanHost:
        ok, retry = self.acquire(scope="host")
        if not ok:
            raise RuntimeError(f"Rate-limited; retry in {retry:.1f}s")
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                f"{BASE_URL}/shodan/host/{ip}",
                params={"key": self.settings.shodan_api_key},
            )
            resp.raise_for_status()
            return ShodanHost.model_validate(resp.json())

    def _real_search(self, query: str, limit: int) -> ShodanSearchResponse:
        ok, retry = self.acquire(scope="search")
        if not ok:
            raise RuntimeError(f"Rate-limited; retry in {retry:.1f}s")
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                f"{BASE_URL}/shodan/host/search",
                params={"key": self.settings.shodan_api_key, "query": query, "limit": limit},
            )
            resp.raise_for_status()
            return ShodanSearchResponse.model_validate(resp.json())

    # ---- Saved Monitors (Shodan Alerts API) ------------------------------

    def create_alert(self, *, name: str, ip: str) -> str | None:
        """Create an upstream Shodan alert.

        In mock mode this is a no-op returning ``None``; in real mode it
        calls ``POST /shodan/alert`` and returns the alert id.

        Docs: https://developer.shodan.io/api (Saved Monitors / Alerts).
        """
        if self.mode == "mock":
            return None
        ok, retry = self.acquire(scope="alert")
        if not ok:
            raise RuntimeError(f"Rate-limited; retry in {retry:.1f}s")
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{BASE_URL}/shodan/alert",
                params={"key": self.settings.shodan_api_key},
                json={"name": name, "filters": {"ip": ip}},
            )
            resp.raise_for_status()
            return resp.json().get("id")

    def delete_alert(self, alert_id: str) -> None:
        """Delete an upstream Shodan alert by id (no-op in mock mode)."""
        if self.mode == "mock":
            return
        ok, retry = self.acquire(scope="alert")
        if not ok:
            raise RuntimeError(f"Rate-limited; retry in {retry:.1f}s")
        with httpx.Client(timeout=15.0) as client:
            resp = client.delete(
                f"{BASE_URL}/shodan/alert/{alert_id}",
                params={"key": self.settings.shodan_api_key},
            )
            resp.raise_for_status()
