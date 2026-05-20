"""Analyst Case File router.

Owns case lifecycle (create / list / read / update / archive) and the
pin lifecycle (entity upsert + attach / detach to case). PDF and STIX
exports land in Phase 7 — this phase only ships the analyst-facing
CRUD plus the pin/unpin flow.

Case visibility is per-owner: an analyst sees their own cases unless
they're an admin.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user
from app.core.db import get_db
from app.models.entities import Case, CaseEntity, CaseStatus, Entity, User, UserRole
from app.schemas.cases import (
    CaseCreate,
    CaseDetail,
    CasePublic,
    CaseUpdate,
    PinCreate,
    PinPublic,
)

router = APIRouter(prefix="/cases", tags=["cases"])


def _ensure_visible(case: Case | None, user: User) -> Case:
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    if user.role != UserRole.admin and case.owner_id != user.id:
        # Hide the existence of other-users cases.
        raise HTTPException(status_code=404, detail="case not found")
    return case


def _to_public(case: Case, pin_count: int) -> CasePublic:
    return CasePublic(
        id=case.id,
        title=case.title,
        summary=case.summary,
        status=case.status.value,  # type: ignore[arg-type]
        owner_id=case.owner_id,
        created_at=case.created_at,
        updated_at=case.updated_at,
        pin_count=pin_count,
    )


@router.get("", response_model=list[CasePublic])
def list_cases(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CasePublic]:
    stmt = select(Case, func.count(CaseEntity.id)).outerjoin(CaseEntity).group_by(Case.id)
    if user.role != UserRole.admin:
        stmt = stmt.where(Case.owner_id == user.id)
    stmt = stmt.order_by(Case.updated_at.desc())
    return [_to_public(c, n) for c, n in db.execute(stmt).all()]


@router.post("", response_model=CasePublic, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CasePublic:
    case = Case(title=payload.title, summary=payload.summary, owner_id=user.id)
    db.add(case)
    db.commit()
    db.refresh(case)
    return _to_public(case, 0)


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaseDetail:
    case = db.execute(
        select(Case)
        .options(selectinload(Case.pins).selectinload(CaseEntity.entity))
        .where(Case.id == case_id)
    ).scalar_one_or_none()
    case = _ensure_visible(case, user)

    pins = [
        PinPublic(
            id=p.id,
            entity=p.entity,  # type: ignore[arg-type] — Pydantic v2 from_attributes
            notes=p.notes,
            pinned_at=p.pinned_at,
        )
        for p in sorted(case.pins, key=lambda x: x.pinned_at)
    ]
    return CaseDetail(
        id=case.id,
        title=case.title,
        summary=case.summary,
        status=case.status.value,  # type: ignore[arg-type]
        owner_id=case.owner_id,
        created_at=case.created_at,
        updated_at=case.updated_at,
        pin_count=len(pins),
        pins=pins,
    )


@router.patch("/{case_id}", response_model=CasePublic)
def update_case(
    case_id: uuid.UUID,
    payload: CaseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CasePublic:
    case = _ensure_visible(db.get(Case, case_id), user)
    if payload.title is not None:
        case.title = payload.title
    if payload.summary is not None:
        case.summary = payload.summary
    if payload.status is not None:
        case.status = CaseStatus(payload.status)
    db.commit()
    db.refresh(case)
    pin_count = db.execute(
        select(func.count(CaseEntity.id)).where(CaseEntity.case_id == case.id)
    ).scalar_one()
    return _to_public(case, int(pin_count or 0))


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    case = _ensure_visible(db.get(Case, case_id), user)
    db.delete(case)
    db.commit()


# ---- Pins ------------------------------------------------------------------


def _get_or_create_entity(
    db: Session, kind: str, ref_id: str, label: str, extra: dict | None
) -> Entity:
    """Upsert on (kind, ref_id) — the natural key enforced by uq_entity_kind_refid."""
    existing = db.execute(
        select(Entity).where(Entity.kind == kind, Entity.ref_id == ref_id)
    ).scalar_one_or_none()
    if existing is not None:
        # Refresh the label and extra so the canonical entity always
        # reflects the latest pin attempt.
        existing.label = label
        if extra is not None:
            existing.extra = extra
        return existing
    ent = Entity(kind=kind, ref_id=ref_id, label=label, extra=extra)
    db.add(ent)
    db.flush()
    return ent


@router.post(
    "/{case_id}/pins",
    response_model=PinPublic,
    status_code=status.HTTP_201_CREATED,
)
def pin_entity(
    case_id: uuid.UUID,
    payload: PinCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PinPublic:
    case = _ensure_visible(db.get(Case, case_id), user)
    entity = _get_or_create_entity(db, payload.kind, payload.ref_id, payload.label, payload.extra)

    # Idempotent: the uq_case_entity constraint lets us short-circuit if
    # the same entity is already pinned.
    existing_pin = db.execute(
        select(CaseEntity).where(CaseEntity.case_id == case.id, CaseEntity.entity_id == entity.id)
    ).scalar_one_or_none()
    if existing_pin is not None:
        if payload.notes is not None:
            existing_pin.notes = payload.notes
        db.commit()
        db.refresh(existing_pin)
        return PinPublic(
            id=existing_pin.id,
            entity=entity,  # type: ignore[arg-type]
            notes=existing_pin.notes,
            pinned_at=existing_pin.pinned_at,
        )

    pin = CaseEntity(case_id=case.id, entity_id=entity.id, notes=payload.notes)
    db.add(pin)
    db.commit()
    db.refresh(pin)
    return PinPublic(
        id=pin.id,
        entity=entity,  # type: ignore[arg-type]
        notes=pin.notes,
        pinned_at=pin.pinned_at,
    )


@router.delete(
    "/{case_id}/pins/{pin_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unpin_entity(
    case_id: uuid.UUID,
    pin_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    case = _ensure_visible(db.get(Case, case_id), user)
    pin = db.execute(
        select(CaseEntity).where(CaseEntity.id == pin_id, CaseEntity.case_id == case.id)
    ).scalar_one_or_none()
    if pin is None:
        raise HTTPException(status_code=404, detail="pin not found")
    db.delete(pin)
    db.commit()
