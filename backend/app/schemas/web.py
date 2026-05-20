"""AI Web Search dashboard schemas (Exa-backed)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WebResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    title: str | None = None
    url: str
    published_date: str | None = None
    author: str | None = None
    score: float | None = None
    text: str | None = None


class WebSearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str
    autoprompt: str | None = None
    sources: list[str]
    results: list[WebResult] = Field(default_factory=list)


class WebAnswerCitation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str
    title: str | None = None


class WebAnswerResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str
    sources: list[str]
    answer: str
    citations: list[WebAnswerCitation] = Field(default_factory=list)
