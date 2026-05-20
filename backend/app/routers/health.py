"""Health probe.

Three checks:
  - process is up   → always 200
  - db reachable    → SELECT 1
  - redis reachable → PING

Returns 200 if the process is up; ``checks`` shows component status. A
shallow probe that's still useful to humans reading the response.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.redis import get_redis

router = APIRouter(tags=["meta"])
log = logging.getLogger("app.health")


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    checks: dict[str, str] = {"app": "ok"}

    try:
        db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:  # pragma: no cover - operational
        log.warning("db health check failed: %s", exc)
        checks["db"] = "down"

    try:
        get_redis().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # pragma: no cover - operational
        log.warning("redis health check failed: %s", exc)
        checks["redis"] = "down"

    return {"status": "ok", "checks": checks}
