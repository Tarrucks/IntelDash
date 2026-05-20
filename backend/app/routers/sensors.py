"""Sensor Sim router — curated Wokwi project catalogue.

Wokwi has no API; the catalogue lives in
``frontend/data/wokwi_projects.json`` and is exposed read-only.
Embedding happens client-side via iframe to ``wokwi.com/projects/{id}``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.adapters.registry import get_adapter
from app.auth.dependencies import get_current_user
from app.models.entities import User
from app.schemas.wokwi import WokwiProject

router = APIRouter(prefix="/sensors", tags=["sensors"])


@router.get("/projects", response_model=list[WokwiProject])
def projects(_: User = Depends(get_current_user)) -> list[WokwiProject]:
    return get_adapter("wokwi").projects()
