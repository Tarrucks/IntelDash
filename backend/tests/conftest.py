"""Shared pytest fixtures.

We test against the real Postgres container brought up by docker compose.
A separate ``aperture_test`` database is created on the fly and dropped
between sessions, so test runs don't pollute the dev DB.

Each test function gets a clean transaction that's rolled back at the
end — fast and predictable.

If Postgres isn't reachable (no docker), tests requiring ``db`` are
skipped with a clear message.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# Resolve test DB URL early. Default points at the docker compose Postgres.
DEFAULT_TEST_DB = "postgresql+psycopg://aperture:aperture@localhost:5432/aperture_test"
ADMIN_DB = "postgresql+psycopg://aperture:aperture@localhost:5432/aperture"

TEST_DATABASE_URL = os.environ.get("APERTURE_TEST_DATABASE_URL", DEFAULT_TEST_DB)


def _postgres_available() -> bool:
    try:
        eng = create_engine(ADMIN_DB, future=True)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# Set DATABASE_URL *before* importing app code so Settings picks it up.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
# Point Redis at the local daemon (compose service is "redis", not resolvable
# from the test host).
os.environ["REDIS_URL"] = os.environ.get("APERTURE_TEST_REDIS_URL", "redis://localhost:6379/0")
# Stable JWT secret for token tests.
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-prod")

PG_AVAILABLE = _postgres_available()


@pytest.fixture(scope="session")
def _test_db_engine() -> Engine:
    if not PG_AVAILABLE:
        pytest.skip("Postgres not reachable — start docker compose up -d db.")

    # Build the test database from the admin connection (autocommit so
    # CREATE DATABASE is permitted).
    admin = create_engine(ADMIN_DB, isolation_level="AUTOCOMMIT", future=True)
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS aperture_test"))
        conn.execute(text("CREATE DATABASE aperture_test"))
    admin.dispose()

    # Now run alembic against the new DB.
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(cfg, "head")

    engine = create_engine(TEST_DATABASE_URL, future=True)
    yield engine
    engine.dispose()

    admin = create_engine(ADMIN_DB, isolation_level="AUTOCOMMIT", future=True)
    with admin.connect() as conn:
        # Disconnect any lingering sessions so DROP DATABASE doesn't block.
        conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = 'aperture_test' AND pid <> pg_backend_pid()"
            )
        )
        conn.execute(text("DROP DATABASE IF EXISTS aperture_test"))
    admin.dispose()


@pytest.fixture()
def db_session(_test_db_engine: Engine) -> Session:
    """One savepoint per test; rolled back at teardown."""
    connection = _test_db_engine.connect()
    trans = connection.begin()
    SessionFactory = sessionmaker(bind=connection, autoflush=False, expire_on_commit=False)
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    """TestClient with ``get_db`` overridden to use the rolled-back session."""
    from app.core.db import get_db
    from app.main import create_app

    app = create_app()

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
