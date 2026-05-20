"""Wokwi adapter — embedded-sensor simulator catalogue.

Wokwi has no API. The platform embeds Wokwi projects via iframe by
project ID. This adapter exposes a curated catalogue
(``frontend/data/wokwi_projects.json``) so analysts can pick from a
dropdown rather than typing IDs manually. The canonical embed URL
is ``https://wokwi.com/projects/{id}`` per Wokwi's documented embed
flow.

For Phase 3 we ship a small hand-curated fallback list. Phase 6 wires
the JSON file from the frontend.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.adapters.base import SourceAdapter
from app.schemas.wokwi import WokwiProject

_CANDIDATES = [
    Path("frontend/data/wokwi_projects.json"),
    Path("../frontend/data/wokwi_projects.json"),
]


_FALLBACK_PROJECTS: list[dict] = [
    {
        "id": "327463649664205394",
        "title": "ESP32 GPS Tracker",
        "description": (
            "ESP32 reading a NEO-6M GPS module over UART, printing position to "
            "the serial monitor. Useful for sensor-sim demos in the Maritime "
            "and Aviation dashboards."
        ),
        "url": "https://wokwi.com/projects/327463649664205394",
        "tags": ["esp32", "gps", "uart"],
    },
    {
        "id": "330914387835175508",
        "title": "Arduino Temperature & Humidity Logger",
        "description": "Arduino Uno + DHT22 sensor, logging to serial.",
        "url": "https://wokwi.com/projects/330914387835175508",
        "tags": ["arduino", "dht22"],
    },
    {
        "id": "340767670300935765",
        "title": "Raspberry Pi Pico LED matrix",
        "description": "RP2040 driving an 8x8 LED matrix via MAX7219.",
        "url": "https://wokwi.com/projects/340767670300935765",
        "tags": ["pico", "rp2040", "led"],
    },
]


class WokwiAdapter(SourceAdapter):
    name = "wokwi"

    @property
    def is_configured(self) -> bool:
        return True

    def acquire(self, scope: str = "default") -> tuple[bool, float]:  # noqa: ARG002
        return True, 0.0

    # ---- Public surface --------------------------------------------------

    def projects(self) -> list[WokwiProject]:
        path = next((p for p in _CANDIDATES if p.exists()), None)
        raw: list[dict]
        if path is not None:
            try:
                raw = json.loads(path.read_text())
            except json.JSONDecodeError:
                raw = _FALLBACK_PROJECTS
        else:
            raw = _FALLBACK_PROJECTS
        return [WokwiProject.model_validate(p) for p in raw]
