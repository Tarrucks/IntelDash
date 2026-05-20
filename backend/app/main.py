"""FastAPI app factory.

``create_app`` exists so tests can instantiate a fresh app with overrides
without touching module-level state.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, aviation, cases, cyber, health, maritime, sensors, tooling, web


def create_app() -> FastAPI:
    app = FastAPI(
        title="Aperture",
        version="0.1.0",
        description="OSINT fusion platform — cyber + maritime + aviation + open-web.",
    )

    # Local-dev CORS. Production deployments tighten this via env later.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(maritime.router)
    app.include_router(aviation.router)
    app.include_router(cyber.router)
    app.include_router(web.router)
    app.include_router(cases.router)
    app.include_router(tooling.router)
    app.include_router(sensors.router)
    return app


app = create_app()
