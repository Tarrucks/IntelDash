"""AI Web Search router.

Wraps the Exa adapter. ``fast`` mode for the interactive search bar,
``deep`` left available for Case File research in Phase 7.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.adapters.registry import get_adapter
from app.auth.dependencies import get_current_user
from app.models.entities import User
from app.schemas.web import (
    WebAnswerCitation,
    WebAnswerResponse,
    WebResult,
    WebSearchResponse,
)

router = APIRouter(prefix="/web", tags=["web"])


@router.get("/search", response_model=WebSearchResponse)
def search(
    q: str = Query(..., min_length=2, max_length=2048),
    num_results: int = Query(5, ge=1, le=25),
    mode: str = Query("fast", pattern="^(fast|instant|deep|deep-reasoning)$"),
    _: User = Depends(get_current_user),
) -> WebSearchResponse:
    adapter = get_adapter("exa")
    raw = adapter.search(q, mode=mode, num_results=num_results)
    return WebSearchResponse(
        query=q,
        autoprompt=raw.autoprompt_string,
        sources=[f"exa({adapter.mode})"],
        results=[
            WebResult(
                id=r.id,
                title=r.title,
                url=r.url,
                published_date=r.published_date,
                author=r.author,
                score=r.score,
                text=r.text,
            )
            for r in raw.results
        ],
    )


@router.get("/answer", response_model=WebAnswerResponse)
def answer(
    q: str = Query(..., min_length=2, max_length=1024),
    _: User = Depends(get_current_user),
) -> WebAnswerResponse:
    adapter = get_adapter("exa")
    raw = adapter.answer(q)
    return WebAnswerResponse(
        query=q,
        sources=[f"exa({adapter.mode})"],
        answer=raw.answer,
        citations=[WebAnswerCitation(url=c.url, title=c.title) for c in raw.citations],
    )
