"""Database engine, session factory, and FastAPI dependency.

SQLAlchemy 2.x style. We expose:
- ``engine``: a sync engine. (Async is overkill for v1; FastAPI handles
  concurrency at the request layer, and our queries are short.)
- ``SessionLocal``: a session factory.
- ``get_db()``: a generator dependency for FastAPI routes.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _build_engine():
    settings = get_settings()
    # ``future=True`` is the 2.x default, kept explicit for clarity.
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        future=True,
    )


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
