# Aperture backend — production container.
#
# This Dockerfile expects to be built from the REPO ROOT so it can
# include the small Kaggle-AIS seed CSV that lives at
# ``data/seed/kaggle-ais/sample.csv``. Fly does this automatically when
# ``fly.toml`` sits at the repo root with ``dockerfile = "backend/Dockerfile"``.
#
# Local equivalent:
#   docker build -f backend/Dockerfile -t aperture-backend .

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# uv is much faster than pip and respects pyproject.toml extras out of
# the box. Install via the official static binary.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build
COPY backend/pyproject.toml ./
RUN uv venv --python python3.12 /opt/venv \
    && . /opt/venv/bin/activate \
    && uv pip install -e .

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000

# Non-root user — small but free hardening win.
RUN useradd --create-home --uid 10001 aperture

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build /app

# Ship the hand-curated Kattegat AIS sample so the platform has data on
# first boot even before scripts/seed_kaggle.py runs. The seed migration
# (alembic 0002) looks for this file and skips cleanly when it's absent.
COPY data/seed /app/data/seed

WORKDIR /app
RUN chown -R aperture:aperture /app
USER aperture

EXPOSE 8000

# Run migrations before serving so the container is self-healing on
# schema changes. Single Fly machine = no race on concurrent migrate.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
