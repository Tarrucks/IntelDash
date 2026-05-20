"""Tooling Library router — mirrors the OSINT Framework taxonomy.

Read-only. The adapter caches its tree in process; the upstream
``arf.json`` is fetched at build time via ``scripts/build_osint_framework.py``
and falls back to a small bundled tree if the build step was skipped.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.adapters.registry import get_adapter
from app.auth.dependencies import get_current_user
from app.models.entities import User
from app.schemas.osintframework import OsintLeaf, OsintNode

router = APIRouter(prefix="/tooling", tags=["tooling"])


@router.get("/tree", response_model=OsintNode)
def tree(_: User = Depends(get_current_user)) -> OsintNode:
    return get_adapter("osintframework").tree()


@router.get("/leaves", response_model=list[OsintLeaf])
def leaves(
    q: str | None = Query(None, max_length=128),
    _: User = Depends(get_current_user),
) -> list[OsintLeaf]:
    """Flat list of URL leaves, optionally filtered by substring on
    name, url, or tags. Used by the global entity search bar."""
    adapter = get_adapter("osintframework")
    all_leaves = adapter.flat_leaves()
    if not q:
        return all_leaves
    needle = q.lower()
    return [
        leaf
        for leaf in all_leaves
        if needle in leaf.name.lower()
        or needle in leaf.url.lower()
        or any(needle in t.lower() for t in leaf.tags)
    ]
