"""Exa response models.

Shapes follow the documented ``POST /search`` and ``POST /answer``
responses (https://docs.exa.ai/reference/getting-started). Only fields
we consume are typed; extras are tolerated.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ExaResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    title: str | None = None
    url: str
    published_date: str | None = Field(default=None, alias="publishedDate")
    author: str | None = None
    score: float | None = None
    text: str | None = None


class ExaSearchResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: str | None = Field(default=None, alias="requestId")
    autoprompt_string: str | None = Field(default=None, alias="autopromptString")
    results: list[ExaResult] = Field(default_factory=list)


class ExaAnswerCitation(BaseModel):
    model_config = ConfigDict(extra="allow")

    url: str
    title: str | None = None


class ExaAnswerResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    answer: str
    citations: list[ExaAnswerCitation] = Field(default_factory=list)
