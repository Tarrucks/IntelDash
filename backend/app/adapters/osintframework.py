"""OSINT Framework adapter — build-time mirror of the taxonomy tree.

The upstream is a static mind-map served from
``lockfale/OSINT-Framework`` on GitHub (``arf.json``). Per CLAUDE.md,
we mirror the taxonomy **at build time** into
``frontend/data/osint-framework.json`` and never fetch it at runtime.

This adapter exposes the in-memory tree — for the build script, see
``scripts/build_osint_framework.py``. If the file is missing (fresh
clone, build not yet run), we fall back to a small built-in taxonomy
so the platform still boots in mock mode.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.adapters.base import SourceAdapter
from app.schemas.osintframework import OsintLeaf, OsintNode

_CANDIDATES = [
    Path("frontend/data/osint-framework.json"),
    Path("../frontend/data/osint-framework.json"),
]


# Fallback taxonomy — tiny but realistically shaped. Used when the
# build-time mirror hasn't been generated yet. Real fetch lands a few
# hundred categories with hundreds of leaves.
_FALLBACK_TREE: dict = {
    "name": "OSINT Framework",
    "type": "folder",
    "children": [
        {
            "name": "Username",
            "type": "folder",
            "children": [
                {
                    "name": "Sherlock",
                    "type": "url",
                    "url": "https://github.com/sherlock-project/sherlock",
                    "tags": ["username", "social"],
                },
                {
                    "name": "WhatsMyName",
                    "type": "url",
                    "url": "https://whatsmyname.app/",
                    "tags": ["username"],
                },
            ],
        },
        {
            "name": "Email Address",
            "type": "folder",
            "children": [
                {
                    "name": "Hunter.io",
                    "type": "url",
                    "url": "https://hunter.io/",
                    "tags": ["email"],
                },
                {
                    "name": "Have I Been Pwned",
                    "type": "url",
                    "url": "https://haveibeenpwned.com/",
                    "tags": ["email", "breach"],
                },
            ],
        },
        {
            "name": "Domain Name",
            "type": "folder",
            "children": [
                {
                    "name": "Whois",
                    "type": "url",
                    "url": "https://who.is/",
                    "tags": ["domain", "whois"],
                },
                {
                    "name": "crt.sh",
                    "type": "url",
                    "url": "https://crt.sh/",
                    "tags": ["domain", "ct-logs"],
                },
            ],
        },
        {
            "name": "Maritime",
            "type": "folder",
            "children": [
                {
                    "name": "MarineTraffic",
                    "type": "url",
                    "url": "https://www.marinetraffic.com/",
                    "tags": ["maritime", "ais"],
                },
                {
                    "name": "VesselFinder",
                    "type": "url",
                    "url": "https://www.vesselfinder.com/",
                    "tags": ["maritime", "ais"],
                },
            ],
        },
    ],
}


class OsintFrameworkAdapter(SourceAdapter):
    """No external auth needed; static taxonomy."""

    name = "osintframework"

    @property
    def is_configured(self) -> bool:
        return True

    def acquire(self, scope: str = "default") -> tuple[bool, float]:  # noqa: ARG002
        return True, 0.0

    # ---- Public surface --------------------------------------------------

    def tree(self) -> OsintNode:
        path = next((p for p in _CANDIDATES if p.exists()), None)
        if path is not None:
            try:
                return OsintNode.model_validate(json.loads(path.read_text()))
            except (json.JSONDecodeError, ValueError):
                # Corrupt file — fall through to the fallback.
                pass
        return OsintNode.model_validate(_FALLBACK_TREE)

    def flat_leaves(self) -> list[OsintLeaf]:
        """Flatten the tree to a list of URL leaves (for global search)."""
        out: list[OsintLeaf] = []

        def walk(node: OsintNode | OsintLeaf) -> None:
            if isinstance(node, OsintLeaf) or getattr(node, "type", None) == "url":
                out.append(OsintLeaf.model_validate(node.model_dump()))
                return
            for child in getattr(node, "children", []):
                walk(child)

        walk(self.tree())
        return out
