"""Shodan Saved Monitor schemas.

We persist monitors as ``entities`` rows with ``kind="shodan_monitor"``;
the entity's ``ref_id`` is the IP (or CIDR) being watched, and the
``extra`` jsonb holds the rest (ports, notes, name, upstream alert id
if a real Shodan alert was created).

This piggybacks on the existing Entity table so Case File can pin a
monitor like any other entity — no separate table.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MonitorCreate(BaseModel):
    ip: str = Field(min_length=1, max_length=128, description="IP or CIDR to watch")
    name: str = Field(min_length=1, max_length=128)
    ports: list[int] | None = None
    notes: str | None = None


class MonitorPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ip: str
    name: str
    ports: list[int] = []
    notes: str | None = None
    upstream_alert_id: str | None = None
    source: str = "mock"
    created_at: datetime
