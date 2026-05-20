"""Exa adapter — AI Web Search.

Auth: ``x-api-key`` HTTP header.
Base URL: https://api.exa.ai

Endpoints we wire:
  - POST /search    (mode=fast for interactive, mode=deep for case research)
  - POST /answer

Exa 2.x ships ``instant``, ``fast``, ``deep``, ``deep-reasoning`` search
modes. We default to ``fast`` (sub-350ms P50) for the dashboard search bar.
"""

from __future__ import annotations

import httpx

from app.adapters.base import SourceAdapter
from app.schemas.exa import ExaAnswerResponse, ExaResult, ExaSearchResponse

BASE_URL = "https://api.exa.ai"


class ExaAdapter(SourceAdapter):
    name = "exa"

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.exa_api_key)

    # ---- Public surface --------------------------------------------------

    def search(self, query: str, *, mode: str = "fast", num_results: int = 5) -> ExaSearchResponse:
        if self.mode == "mock":
            return self._mock_search(query, num_results)
        return self._real_search(query, mode=mode, num_results=num_results)

    def answer(self, query: str) -> ExaAnswerResponse:
        if self.mode == "mock":
            return self._mock_answer(query)
        return self._real_answer(query)

    # ---- Mock implementations -------------------------------------------

    @staticmethod
    def _mock_search(query: str, num_results: int) -> ExaSearchResponse:
        results = [
            ExaResult.model_validate(
                {
                    "id": f"mock-{i}",
                    "title": f"Mock result {i + 1} for: {query}",
                    "url": f"https://example.com/mock/{i + 1}",
                    "publishedDate": "2026-05-15T00:00:00Z",
                    "author": "Mock Author",
                    "score": round(0.95 - 0.05 * i, 2),
                    "text": (
                        f"This is mock body text for query '{query}'. Real Exa responses "
                        "include parsed article content here."
                    ),
                }
            )
            for i in range(num_results)
        ]
        return ExaSearchResponse(
            requestId="mock-req-0001",
            autopromptString=f"Improved query: {query}",
            results=results,
        )

    @staticmethod
    def _mock_answer(query: str) -> ExaAnswerResponse:
        return ExaAnswerResponse.model_validate(
            {
                "answer": (
                    f"Mock answer to: {query}. In production this would be a synthesized "
                    "response sourced from real web pages."
                ),
                "citations": [
                    {"url": "https://example.com/mock/1", "title": "Mock source 1"},
                    {"url": "https://example.com/mock/2", "title": "Mock source 2"},
                ],
            }
        )

    # ---- Real implementations -------------------------------------------

    def _real_search(self, query: str, *, mode: str, num_results: int) -> ExaSearchResponse:
        ok, retry = self.acquire(scope="search")
        if not ok:
            raise RuntimeError(f"Rate-limited; retry in {retry:.1f}s")
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{BASE_URL}/search",
                headers={"x-api-key": self.settings.exa_api_key},
                json={"query": query, "type": mode, "numResults": num_results},
            )
            resp.raise_for_status()
            return ExaSearchResponse.model_validate(resp.json())

    def _real_answer(self, query: str) -> ExaAnswerResponse:
        ok, retry = self.acquire(scope="answer")
        if not ok:
            raise RuntimeError(f"Rate-limited; retry in {retry:.1f}s")
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{BASE_URL}/answer",
                headers={"x-api-key": self.settings.exa_api_key},
                json={"query": query},
            )
            resp.raise_for_status()
            return ExaAnswerResponse.model_validate(resp.json())
