"""Alembic environment.

Loads the project's ``Settings`` so ``DATABASE_URL`` from .env wins over
alembic.ini. Imports every model so ``Base.metadata`` has the full schema
when ``--autogenerate`` runs.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings
from app.models import Base  # noqa: F401  -- side-effect: registers tables

config = context.config

# Override the sqlalchemy.url with whatever Settings says (env / .env).
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


_POSTGIS_TABLES = {
    "spatial_ref_sys",
    "geography_columns",
    "geometry_columns",
    "raster_columns",
    "raster_overviews",
}
_TIMESCALE_SCHEMAS = {
    "_timescaledb_internal",
    "_timescaledb_catalog",
    "_timescaledb_config",
    "_timescaledb_cache",
    "timescaledb_information",
    "timescaledb_experimental",
    "tiger",
    "tiger_data",
    "topology",
}


def _include_object(obj, name, type_, reflected, compare_to):  # noqa: ARG001
    """Skip TimescaleDB and PostGIS internal tables from autogen diffs.

    The extra positional args are required by Alembic's include_object hook
    signature even when we don't use them.
    """
    if type_ == "table" and name in _POSTGIS_TABLES:
        return False
    return not (type_ == "schema" and name in _TIMESCALE_SCHEMAS)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=_include_object,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
