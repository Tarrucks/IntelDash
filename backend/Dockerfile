# Aperture backend — production container.
#
# Multi-stage so the runtime image ships without uv / build tools. Slim
# base, GeoAlchemy needs nothing native at runtime — psycopg[binary] and
# shapely both bundle the C bits.

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# uv is much faster than pip and respects pyproject.toml extras out of
# the box. Install it via the official static binary.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build
COPY pyproject.toml ./
# Pre-fetch all deps into a venv at /opt/venv. We pin sys.prefix into
# the runtime image so the venv layer is reusable across rebuilds.
RUN uv venv --python python3.12 /opt/venv \
    && . /opt/venv/bin/activate \
    && uv pip install -e .

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000

# Non-root user — small but free hardening win.
RUN useradd --create-home --uid 10001 aperture

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build /app

WORKDIR /app
RUN chown -R aperture:aperture /app
USER aperture

EXPOSE 8000

# Entrypoint runs migrations before serving so the container is
# self-healing on schema changes. If you'd rather gate migrations
# behind a manual ``alembic upgrade head`` step, drop the first line
# of the CMD.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
