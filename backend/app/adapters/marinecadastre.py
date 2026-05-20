"""MarineCadastre adapter — US public-domain bulk AIS.

Unlike the live sources, MarineCadastre is an **anonymous bulk download**
endpoint (US public domain). The adapter is therefore primarily a
metadata + URL provider; the heavy lift is a Celery ETL worker in
Phase 7 that streams CSV into the ``vessel_positions`` hypertable.

For Phase 3 we expose:
  - ``available_years()`` — known years (mock list; the real adapter
    would scrape the bulk index page or list an S3 bucket).
  - ``download_url(year, zone)`` — canonical URL pattern.

Order size cap ~2 GB per AccessAIS order is enforced upstream.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, HttpUrl

from app.adapters.base import SourceAdapter

# The bulk download index lives at marinecadastre.gov/ais/. Files use a
# year/zone pattern; CSVs from 2018+ and geodatabases before that.
BULK_BASE = "https://marinecadastre.gov/ais"


class MarineCadastreFile(BaseModel):
    model_config = ConfigDict(extra="allow")

    year: int
    zone: int
    format: str  # "csv" or "gdb"
    url: HttpUrl


class MarineCadastreAdapter(SourceAdapter):
    name = "marinecadastre"

    # MarineCadastre has no API key — it's anonymous. ``is_configured``
    # is always True; we have no rate-limit policy in SOURCE_LIMITS for
    # the same reason. ``acquire()`` is bypassed via the override below.
    @property
    def is_configured(self) -> bool:
        return True

    def acquire(self, scope: str = "default") -> tuple[bool, float]:  # noqa: ARG002
        # No bucket policy — public bulk endpoint, governed by US public domain.
        return True, 0.0

    # ---- Public surface --------------------------------------------------

    def available_years(self) -> list[int]:
        if self.mode == "mock":
            return self._mock_years()
        return self._real_years()

    def download_url(self, year: int, zone: int = 10) -> MarineCadastreFile:
        # The real URL pattern is stable; we surface it so the ETL worker
        # has a single source of truth.
        fmt = "csv" if year >= 2018 else "gdb"
        return MarineCadastreFile(
            year=year,
            zone=zone,
            format=fmt,
            url=f"{BULK_BASE}/{year}/AIS_{year}_{zone:02d}_Zone{zone:02d}.zip",  # type: ignore[arg-type]
        )

    # ---- Mock implementations -------------------------------------------

    @staticmethod
    def _mock_years() -> list[int]:
        return list(range(2018, 2026))

    # ---- Real implementations -------------------------------------------

    def _real_years(self) -> list[int]:
        # TODO(real-impl): scrape the marinecadastre.gov/ais index page
        # for actually available years; the mock list is sufficient for v1.
        return self._mock_years()
