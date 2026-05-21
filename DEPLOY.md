# Deploying Aperture

The local quickstart in [`README.md`](./README.md) covers the all-in-one
docker-compose path. This doc covers cloud deploys — specifically the
recommended split:

- **Frontend** on Vercel (native Next.js fit)
- **Backend** on Fly.io (or any container host: Railway, Render, ECS)
- **Database** on Timescale Cloud (PostGIS + TimescaleDB)
- **Redis** on Upstash

There's no Vercel-hosted-backend story here because Aperture relies on
TimescaleDB hypertables, PostGIS, Redis, and (in Phase 7+) Celery
workers — none of which fit Vercel's serverless model.

---

## 1. Database — Timescale Cloud

Aperture's Alembic 0001 migration calls
``CREATE EXTENSION timescaledb`` and ``create_hypertable(...)`` for
``vessel_positions`` and ``aircraft_positions``. **Neon, Supabase, and
RDS without the Timescale extension allowlist will fail this
migration.** Timescale Cloud (which also bundles PostGIS) is the path
of least resistance.

1. Create a free service at <https://www.timescale.com/cloud>.
2. In the SQL editor of the new service, run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS postgis;
   CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
   -- timescaledb is preinstalled.
   ```
3. Copy the service's connection string. SQLAlchemy needs the
   ``+psycopg`` driver prefix:
   ```
   postgresql+psycopg://tsdbadmin:<password>@<host>:<port>/tsdb?sslmode=require
   ```

## 2. Redis — Upstash

1. Create a database at <https://upstash.com/>.
2. Pick the "Endpoint over TLS" URL, which starts with ``rediss://``.

## 3. Backend — Fly.io

The repo ships [`fly.toml`](./fly.toml) at the root,
[`backend/Dockerfile`](./backend/Dockerfile), and a
[`.dockerignore`](./.dockerignore) tuned for the repo-root build
context (so the Kaggle-AIS seed CSV ends up in the image). The
container runs ``alembic upgrade head`` on boot so schema changes
auto-apply.

```bash
# From the repo root — fly.toml lives here, not in backend/:
fly launch --no-deploy --copy-config         # picks up fly.toml + Dockerfile
fly secrets set \
  DATABASE_URL='postgresql+psycopg://...timescale-cloud...?sslmode=require' \
  REDIS_URL='rediss://...upstash...' \
  JWT_SECRET="$(openssl rand -hex 32)" \
  APERTURE_CORS_ORIGINS='https://<your-app>.vercel.app,https://<your-team>.vercel.app'

# Optional adapter keys — add only the ones you actually use:
fly secrets set SHODAN_API_KEY=... EXA_API_KEY=... FR24_API_KEY=...
fly secrets set AISHUB_USERNAME=...
fly secrets set BARENTSWATCH_CLIENT_ID=... BARENTSWATCH_CLIENT_SECRET=...

fly deploy
fly status                       # confirm the app is healthy
fly open                         # opens https://<app>.fly.dev
```

Sanity check:
```bash
curl https://<app>.fly.dev/health
# {"status":"ok","checks":{"app":"ok","db":"ok","redis":"ok"}}
```

### CORS — env-driven

CORS allow-origins is read from ``APERTURE_CORS_ORIGINS`` at boot
(comma-separated list). To allow your Vercel domain plus its preview
deployments, set:

```bash
fly secrets set APERTURE_CORS_ORIGINS='https://aperture.vercel.app,https://aperture-git-main-tarruck.vercel.app'
fly deploy   # secret change triggers a restart automatically
```

Add ``http://localhost:3000`` to the list if you also run the
frontend locally against the deployed backend.

## 4. Frontend — Vercel

From the Vercel dashboard, **Add New… → Project** → pick this repo.
The Vercel "monorepo wizard" will auto-detect both apps; ignore the
backend service (FastAPI doesn't fit Vercel — see the intro).

| Setting              | Value                              |
| -------------------- | ---------------------------------- |
| Root Directory       | ``frontend``                       |
| Framework Preset     | Next.js (auto-detected once Root Directory is right) |
| Build Command        | ``pnpm build``                     |
| Install Command      | ``pnpm install --frozen-lockfile`` |
| Output Directory     | ``.next``                          |
| Node.js Version      | 20.x                               |

**If Vercel guesses "VitePress" as the Application Preset,** the Root
Directory is still at the repo root. Change Root Directory to
``frontend`` first; the preset will flip to Next.js automatically.
[`frontend/vercel.json`](./frontend/vercel.json) pins the rest.

Environment variables (Settings → Environment Variables, both
Production and Preview scopes):

```
NEXT_PUBLIC_API_BASE_URL = https://<your-fly-app>.fly.dev
NEXT_PUBLIC_MAP_STYLE_URL = https://demotiles.maplibre.org/style.json
```

> ``NEXT_PUBLIC_*`` are inlined at **build** time, not runtime —
> changing them in the dashboard requires a redeploy.

Deploy. Open the resulting ``https://<your-app>.vercel.app``, copy
the domain back into ``APERTURE_CORS_ORIGINS`` on the Fly app if you
hadn't yet, register an analyst, and walk
[`ANALYST_GUIDE.md`](./ANALYST_GUIDE.md).

## 5. Optional bits

**Real Kaggle seed.** SSH into the Fly machine and run
``python scripts/seed_kaggle.py`` once — the bundled mock 24-row CSV
gets the platform booting, but the anomaly model is only meaningful
on the full Kattegat dataset.

**Celery worker.** Phase 7 ships the anomaly model with lazy fit + a
disk cache, so a worker isn't strictly required. If you want
scheduled Shodan-monitor sweeps (Phase 7.4 carry-over), add a second
Fly app from the same image with the start command overridden:
```bash
fly launch --copy-config --name aperture-worker
# Inside the new fly.toml override [processes] or start command to:
#   celery -A app.workers.celery_app worker -l info
```

**HttpOnly cookies instead of localStorage.** The frontend currently
stores JWTs in ``localStorage`` for simplicity. For production, swap
``lib/auth.ts`` for a same-origin cookie strategy and adjust the
backend to set the cookie on ``/auth/login``. This is a deliberate
v0.1.0 deferral, not a bug.

**Custom MapLibre tiles.** The ``demotiles.maplibre.org`` style is
fine for demos; for production traffic point ``NEXT_PUBLIC_MAP_STYLE_URL``
at a self-hosted style or a MapTiler / Stadia key.

---

## Cost ballpark (May 2026)

| Service         | Tier                  | Approx /mo |
| --------------- | --------------------- | ---------- |
| Vercel          | Hobby                 | $0         |
| Fly.io          | 1× shared-cpu-1x      | ~$2-5      |
| Timescale Cloud | Free dev tier         | $0         |
| Upstash Redis   | Free tier             | $0         |

So the demo is effectively free. Production needs a paid Vercel team
seat and a Fly machine that doesn't autosuspend — call it $30–50/mo
before any Shodan / Exa / FR24 credits.

## Troubleshooting

- **Migration fails with ``extension "timescaledb" is not allowed``**
  — you're not on Timescale Cloud. Move the DB.
- **``connect: connection refused`` on Fly boot** — the Fly app's
  internal DNS resolved before the secret was set. ``fly secrets list``
  to verify, then ``fly deploy`` to re-roll.
- **CORS errors in the browser console** — the Vercel domain isn't in
  ``allow_origins``. See section 3.
- **PDF / STIX endpoints time out** — Fly's default 60s request
  timeout is fine; if you've added Deep Exa research to the export
  flow, bump ``fly.toml``'s ``services.concurrency.hard_limit`` and
  the route timeout.
- **Map is blank** — Vercel domain doesn't allow outbound to
  ``demotiles.maplibre.org`` (rare). Swap ``NEXT_PUBLIC_MAP_STYLE_URL``
  for a hosted alternative.
