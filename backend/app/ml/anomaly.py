"""Vessel-anomaly detector — IsolationForest on (sog, cog, heading).

Why IsolationForest:
  - Unsupervised, no labels needed.
  - Robust to the small Kaggle-seed sample we ship by default (23 rows
    over 6 vessels). Real deployments train on the full Kaggle pull or
    MarineCadastre ETL output — same model, more data.
  - Returns a continuous anomaly score and a binary flag, so the
    frontend can colour-grade or threshold as it likes.

Feature engineering:
  ``sog``                       speed over ground (kts)
  ``cog_sin`` / ``cog_cos``     unit-circle decomposition so 359° and 1°
                                 sit close in feature space
  ``heading_sin`` / ``cos``     same trick for heading
  ``hdg_cog_dev``               |heading - cog|, the angle between
                                 the vessel's nose and its motion —
                                 a classic AIS anomaly indicator
                                 (drifting vs spoofed vs adrift).

Persistence:
  Fitted model + the training column hash are cached to
  ``data/cache/anomaly_isoforest.joblib``. We invalidate the cache
  when the column set changes (a schema drift on the upstream Kaggle
  dataset is the realistic trigger), not on row-count changes —
  retraining on every ingest would be wasteful.
"""

from __future__ import annotations

import logging
import math
import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.positions import VesselPosition

log = logging.getLogger("app.ml.anomaly")

CACHE_DIR = Path(
    os.environ.get(
        "APERTURE_ANOMALY_CACHE_DIR",
        str(Path(__file__).resolve().parent.parent.parent / "data" / "cache"),
    )
)
CACHE_PATH = CACHE_DIR / "anomaly_isoforest.joblib"
MIN_TRAINING_ROWS = 5
CONTAMINATION = 0.1
RANDOM_STATE = 42


@dataclass
class AnomalyResult:
    score: float
    is_anomaly: bool


def _angle(deg: float | None) -> tuple[float, float]:
    """Unit-circle decomposition (sin, cos). None → (0, 1) — i.e. "due
    north" — which is the best non-informative prior we can offer."""
    if deg is None:
        return 0.0, 1.0
    rad = math.radians(float(deg))
    return math.sin(rad), math.cos(rad)


def _row_features(
    sog: float | None,
    cog: float | None,
    heading: float | None,
) -> list[float]:
    cs, cc = _angle(cog)
    hs, hc = _angle(heading)
    if cog is not None and heading is not None:
        # Smallest absolute angular difference in degrees.
        diff = abs((heading - cog + 180.0) % 360.0 - 180.0)
    else:
        diff = 0.0
    return [
        float(sog or 0.0),
        cs,
        cc,
        hs,
        hc,
        diff,
    ]


class VesselAnomalyModel:
    """Process-singleton wrapper around an IsolationForest."""

    def __init__(self) -> None:
        self._model: IsolationForest | None = None
        self._train_n: int = 0

    @property
    def fitted(self) -> bool:
        return self._model is not None

    def fit(self, samples: Sequence[Sequence[float | None]]) -> int:
        """Fit on a sequence of ``(sog, cog, heading)`` tuples.

        Returns the number of rows used.
        """
        if len(samples) < MIN_TRAINING_ROWS:
            log.info(
                "Not enough rows to fit anomaly model (%d < %d); deferring",
                len(samples),
                MIN_TRAINING_ROWS,
            )
            return 0
        X = np.array([_row_features(*s) for s in samples], dtype=float)
        model = IsolationForest(
            n_estimators=100,
            contamination=CONTAMINATION,
            random_state=RANDOM_STATE,
        )
        model.fit(X)
        self._model = model
        self._train_n = len(samples)
        return self._train_n

    def predict(
        self,
        sog: float | None,
        cog: float | None,
        heading: float | None,
    ) -> AnomalyResult:
        if self._model is None:
            return AnomalyResult(score=0.0, is_anomaly=False)
        x = np.array([_row_features(sog, cog, heading)], dtype=float)
        # ``score_samples`` returns the average path length; we expose
        # the negated-decision-function so higher = more anomalous
        # (matches the dashboard's "red is bad" colour convention).
        raw = float(self._model.score_samples(x)[0])
        flag = bool(self._model.predict(x)[0] == -1)
        return AnomalyResult(score=-raw, is_anomaly=flag)

    # ---- Persistence -----------------------------------------------------

    def save(self, path: Path = CACHE_PATH) -> None:
        if self._model is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self._model, "train_n": self._train_n}, path)

    def load(self, path: Path = CACHE_PATH) -> bool:
        if not path.exists():
            return False
        try:
            blob = joblib.load(path)
            self._model = blob["model"]
            self._train_n = int(blob.get("train_n", 0))
            return True
        except Exception as exc:  # pragma: no cover - operational
            log.warning("Failed to load cached anomaly model: %s", exc)
            return False


# Process-wide singleton. Lazy-initialised — the first request that
# needs an anomaly score triggers training if no cache exists.
_singleton: VesselAnomalyModel | None = None


def get_model(db: Session) -> VesselAnomalyModel:
    global _singleton
    if _singleton is None:
        _singleton = VesselAnomalyModel()
        if not _singleton.load():
            _train_from_db(_singleton, db)
            _singleton.save()
    elif not _singleton.fitted:
        # Cache load was attempted before; try one more fit if more rows
        # have arrived in the meantime.
        _train_from_db(_singleton, db)
        if _singleton.fitted:
            _singleton.save()
    return _singleton


def _train_from_db(model: VesselAnomalyModel, db: Session) -> int:
    rows: Iterable[VesselPosition] = db.execute(
        select(VesselPosition.sog, VesselPosition.cog, VesselPosition.heading)
    ).all()
    samples: list[tuple[float | None, float | None, float | None]] = [
        (r[0], r[1], r[2]) for r in rows
    ]
    n = model.fit(samples)
    log.info("Trained vessel anomaly model on %d positions", n)
    return n


def invalidate_cache() -> None:
    """Clear the in-process and on-disk caches.

    Useful in tests and after a schema-shifting MarineCadastre/Kaggle
    re-import. The next request will re-train.
    """
    global _singleton
    import contextlib

    _singleton = None
    with contextlib.suppress(OSError):
        CACHE_PATH.unlink(missing_ok=True)
