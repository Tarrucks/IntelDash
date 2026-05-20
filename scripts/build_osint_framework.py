#!/usr/bin/env python3
"""Mirror the OSINT Framework taxonomy at build time.

The canonical source is ``lockfale/OSINT-Framework`` on GitHub. We fetch
its ``arf.json`` mind-map, normalize it into the shape Aperture's
``OsintNode`` schema expects, and write the result to
``frontend/data/osint-framework.json``.

Idempotent. Network-optional: if GitHub is unreachable, the script
prints a warning and exits 0 — the adapter falls back to its built-in
tiny taxonomy and the platform still boots.

Run manually before a release:
    python scripts/build_osint_framework.py
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ARF_URL = "https://raw.githubusercontent.com/lockfale/OSINT-Framework/master/public/arf.json"
OUT = Path(__file__).resolve().parent.parent / "frontend" / "data" / "osint-framework.json"


def _normalize(node: dict) -> dict:
    """Convert lockfale's ``arf.json`` node into Aperture's OsintNode shape.

    Upstream nodes have ``{"name", "children": [...]}`` for folders and
    ``{"name", "url"}`` for leaves. We add ``type`` and pass ``url``
    leaves through cleanly.
    """
    if "url" in node and node.get("url"):
        return {
            "name": node.get("name", ""),
            "type": "url",
            "url": node["url"],
            "tags": node.get("tags", []),
        }
    return {
        "name": node.get("name", ""),
        "type": "folder",
        "children": [_normalize(c) for c in node.get("children", [])],
    }


def main() -> int:
    try:
        with urllib.request.urlopen(ARF_URL, timeout=15) as resp:
            raw = json.load(resp)
    except Exception as exc:  # pragma: no cover - network-dependent
        print(
            f"[build_osint_framework] WARN: could not fetch upstream: {exc}",
            file=sys.stderr,
        )
        print(
            "[build_osint_framework] adapter will use its built-in fallback taxonomy.",
            file=sys.stderr,
        )
        return 0

    normalized = _normalize(raw)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(normalized, indent=2))
    print(f"[build_osint_framework] wrote {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
