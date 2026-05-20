"""Kaggle adapter — seed-only.

Kaggle is a one-shot data source: the platform downloads the AIS
dataset on first boot via ``scripts/seed_kaggle.py`` and never calls
the API again. This adapter exposes:

  - ``is_configured`` — whether KAGGLE_USERNAME / KAGGLE_KEY are set
  - ``seed_status()`` — whether a seed CSV (real or sample) is present
    on disk, with the inferred column schema if available.

No rate-limit policy because we don't make recurring requests.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.adapters.base import SourceAdapter

# scripts/ is at the repo root; backend code is one level down.
_SEED_DIR_CANDIDATES = [
    Path("data/seed/kaggle-ais"),
    Path("../data/seed/kaggle-ais"),
]


class KaggleSeedStatus(BaseModel):
    model_config = ConfigDict(extra="allow")

    configured: bool
    seed_dir: str | None = None
    sample_present: bool = False
    real_csvs: list[str] = []
    inferred_schema: dict | None = None


class KaggleAdapter(SourceAdapter):
    name = "kaggle"

    @property
    def is_configured(self) -> bool:
        return self.settings.kaggle_configured

    def acquire(self, scope: str = "default") -> tuple[bool, float]:  # noqa: ARG002
        # One-shot, no rate limit.
        return True, 0.0

    # ---- Public surface --------------------------------------------------

    def seed_status(self) -> KaggleSeedStatus:
        seed_dir = next((p for p in _SEED_DIR_CANDIDATES if p.exists()), None)
        if seed_dir is None:
            return KaggleSeedStatus(configured=self.is_configured)

        sample = (seed_dir / "sample.csv").exists()
        # Real Kaggle CSVs land here when scripts/seed_kaggle.py runs.
        real = [p.name for p in seed_dir.glob("*.csv") if p.name != "sample.csv"]

        schema_path = seed_dir / "schema.json"
        schema: dict | None = None
        if schema_path.exists():
            try:
                schema = json.loads(schema_path.read_text())
            except json.JSONDecodeError:
                schema = None

        return KaggleSeedStatus(
            configured=self.is_configured,
            seed_dir=str(seed_dir),
            sample_present=sample,
            real_csvs=real,
            inferred_schema=schema,
        )
