"""Analyst Case File schemas.

The Case File is the cross-domain glue: an analyst pins entities
(vessels, aircraft, hosts, URLs, …) from any dashboard onto a case,
adds notes, and later exports the case to PDF / STIX 2.1.

The pin model dereferences to ``entities`` (kind + ref_id + label) so
two cases can independently reference the same real-world entity
without duplicating it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CaseStatus = Literal["open", "closed", "archived"]


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    summary: str | None = None


class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    summary: str | None = None
    status: CaseStatus | None = None


class EntityRef(BaseModel):
    """A handle on a cross-domain entity. Stable across cases."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    ref_id: str
    label: str
    extra: dict | None = None
    created_at: datetime


class PinCreate(BaseModel):
    """Pin an entity to a case.

    The entity is upserted on its (kind, ref_id) natural key. If the
    pin already exists, the endpoint is a no-op — pinning is idempotent
    so dashboards can pin freely without checking first.
    """

    kind: str = Field(min_length=1, max_length=32)
    ref_id: str = Field(min_length=1, max_length=256)
    label: str = Field(min_length=1, max_length=256)
    extra: dict | None = None
    notes: str | None = None


class PinPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity: EntityRef
    notes: str | None = None
    pinned_at: datetime


class CasePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    summary: str | None = None
    status: CaseStatus
    owner_id: int | None = None
    created_at: datetime
    updated_at: datetime
    pin_count: int = 0


class CaseDetail(CasePublic):
    pins: list[PinPublic] = Field(default_factory=list)
