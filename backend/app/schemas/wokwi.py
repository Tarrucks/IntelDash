"""Wokwi sensor-sim catalogue.

Wokwi has no API — projects are embedded via iframe by project ID. We
ship a curated catalogue (``frontend/data/wokwi_projects.json``) so
analysts can pick from a dropdown rather than typing IDs.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, HttpUrl


class WokwiProject(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    description: str
    url: HttpUrl  # canonical wokwi.com/projects/{id}
    tags: list[str] = []
