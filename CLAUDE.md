# Aperture — OSINT Fusion Platform

> Working notes for Claude / contributors. Read this before touching code.

## Mission

Aperture is an analyst-grade open-source intelligence platform that fuses
**cyber**, **maritime**, **aviation**, and **open-web** intelligence into a
single dashboard. A shared geospatial map is the unifying surface; an
Analyst Case File lets investigators pin cross-domain entities, build a
timeline, and export to PDF / STIX 2.1.

The product target is a working v0.1.0 that an analyst can boot from a
fresh clone with **zero API keys** (mock adapters) and add real keys later.

## Architecture Decisions

| Layer            | Choice                                                          | Why                                                                  |
| ---------------- | --------------------------------------------------------------- | -------------------------------------------------------------------- |
| Frontend         | Next.js 14 App Router + TypeScript + Tailwind + shadcn/ui       | Standard stack; App Router for nested layouts per dashboard.         |
| Map              | MapLibre GL JS as base + Deck.gl overlays + Kepler.gl for replay| Fully open; Kepler 3.x switched its default basemap to MapLibre.     |
| Backend          | FastAPI, one router module per source                            | Async, OpenAPI for free, fits the adapter pattern.                   |
| Workers          | Celery + Redis (RQ acceptable if Celery is heavyweight for v1)  | Batch ETL for MarineCadastre / Kaggle seed.                          |
| DB               | PostgreSQL + PostGIS + TimescaleDB                              | PostGIS for spatial, Timescale hypertables for AIS / flight tracks.  |
| Cache / Streams  | Redis + Redis Streams                                            | Live AIS + flight fan-out; per-source token-bucket rate limits.      |
| Auth             | JWT, 3 roles: Viewer / Analyst / Admin                          | Boring and sufficient. No external IdP for v1.                       |
| Deploy           | `docker compose` for dev; `deploy/k8s/` as a stub               | Single command boot; Kubernetes is post-v1.                          |
| Lint / format    | ruff + black (py), prettier + eslint (ts), pre-commit harness   | Run via pre-commit on every commit.                                  |

### Hard rules

- **Do not fabricate API endpoints, response shapes, auth flows, or rate limits.**
  If the docs aren't clear, ship a typed interface + a clearly labeled
  `TODO(real-impl)` and a mock that returns realistically shaped data.
- **Every adapter has a mock.** Real implementations live behind a feature
  flag triggered by the presence of the relevant env var.
- **Secrets only via env.** Never hardcode. `.env.example` is the contract.
- **No microservices, no operators, no custom IdP in v1.** Keep boring.
- **No TOS-violating data flows.** If a source's TOS restricts scraping or
  redistribution, comment it in the adapter and stop at the mock.
- **No paywalled content scraped or embedded.**
- **Geospatial / signal-processing code gets comments** — clarity beats
  cleverness. Elsewhere, prefer self-documenting code.
- **Linters + relevant tests run at the end of every phase.** Do not advance
  with a red build.

## Data Source Inventory

| #  | Source              | Powers                  | Auth                                | Free tier?               | TOS notes                                                                 |
| -- | ------------------- | ----------------------- | ----------------------------------- | ------------------------ | ------------------------------------------------------------------------- |
| 1  | Shodan              | Cyber Surface           | API key (`?key=`)                   | Free key, paid credits   | Standard ToU.                                                             |
| 2  | OSINT Framework     | Tooling Library panel   | none (static taxonomy)              | Yes                       | Mirror the public taxonomy; attribute upstream.                          |
| 3  | Exa                 | AI Web Search           | `x-api-key` header                  | Free tier exists         | Standard ToU.                                                             |
| 4  | AISHub              | Maritime Live           | HTTP Basic + `username` parameter   | Members only, 1 req/min  | **Strict 1/min poll cap.** Members must contribute their own AIS feed.   |
| 5  | BarentsWatch        | Maritime historic       | OAuth2 client_credentials, scope=ais| Yes (registered user)    | Norwegian govt service; usage subject to BarentsWatch ToS.                |
| 6  | MarineCadastre      | Bulk AIS ETL            | none (anonymous download)            | Yes, public domain        | US public-domain data via NOAA. Order size cap ~2 GB per AccessAIS order. |
| 7  | Kaggle AIS dataset  | Seed + anomaly training | Kaggle API token (one-shot download)| Yes                       | Respect Kaggle dataset license (open).                                    |
| 8  | Flightradar24       | Aviation Live           | Subscription API key                | Sandbox key for testing  | Paid for prod usage; **never scrape the consumer site**.                  |
| 9  | Kepler.gl / Deck.gl | Map layer               | n/a (library)                       | Open source              | MIT / Apache.                                                             |
| 10 | Wokwi               | Sensor Sim panel        | n/a (iframe embed by project id)    | Yes                      | Embed via documented `wokwi.com/projects/{id}` iframe.                    |

### API Key Requirements

`.env.example` will enumerate these (none required to boot with mocks):

```
SHODAN_API_KEY=
EXA_API_KEY=
AISHUB_USERNAME=
BARENTSWATCH_CLIENT_ID=
BARENTSWATCH_CLIENT_SECRET=
FR24_API_KEY=
KAGGLE_USERNAME=
KAGGLE_KEY=
JWT_SECRET=          # required (generated in setup script if absent)
POSTGRES_*           # standard DSN parts
REDIS_URL=
```

## Source Notes

Captured from live docs on 2026-05-20. Re-check before integrating each.

### Shodan
Base URL `https://api.shodan.io`. Auth is a `key` query parameter on every
request — there is **no header auth**. Shodan does not use traditional
RPS rate limits; it uses **monthly credits** (query, scan, alert). The
adapter must surface the user's remaining credits and refuse to spend
them in mock mode. Methods we need: `/shodan/host/{ip}`, `/shodan/host/search`,
`/shodan/host/search/facets`, and the Monitor endpoints for "Saved Monitors"
(Phase 7). Docs: https://developer.shodan.io/api.

### OSINT Framework
The site itself is just a static tree; the canonical source is
`lockfale/OSINT-Framework` on GitHub with an `arf.json` mind-map file.
We will **fetch that JSON at build time**, normalize it into a typed
tree, and ship it as `frontend/data/osint-framework.json`. No runtime
HTTP to the upstream. Attribution required.

### Exa
Auth via `x-api-key` HTTP header. Base URL `https://api.exa.ai`. Core
endpoints we will wire: `POST /search`, `POST /contents`, `POST /findsimilar`,
`POST /answer`. As of Exa 2.x, search modes include `fast`, `instant`,
`deep`, and `deep-reasoning` — pick `fast` for interactive UI and `deep`
for Case File research. Docs: https://docs.exa.ai/reference/getting-started.

### AISHub
Endpoint: `http://data.aishub.net/ws.php`. Auth is a `username` query
parameter (issued to contributing members). **The webservice silently
returns empty if polled more often than once per minute** — the adapter
must enforce a 60s floor with a token bucket. Supported params: `format`
(xml/json), `output` (raw/aggregated), `compress`, bounding box
(`latmin/latmax/lonmin/lonmax`), `mmsi`, `imo`, `interval`. We default
to JSON + bounding-box queries.

### BarentsWatch Historic AIS
OAuth2 client_credentials flow. Token endpoint
`https://id.barentswatch.no/connect/token` with `client_id`,
`client_secret`, `scope=ais`, `grant_type=client_credentials`. Historic
AIS API exposes `/v1/historic/trackslast24hours/{mmsi}` and
`/v1/historic/tracks/{mmsi}/{fromDate}/{toDate}` returning **GeoJSON
FeatureCollection**. Cache tokens until 60s before expiry.

### MarineCadastre
Anonymous bulk download. Annual lists at `https://marinecadastre.gov/ais/`
provide CSV (new) or geodatabase (old) per-year, per-zone files.
AccessAIS allows custom clip-and-ship orders (zipped CSV, ~2 GB cap).
The ETL worker in Phase 1/3 will download a small sample by default
(documented in the seed script) and stream-parse into the `vessel_positions`
TimescaleDB hypertable. US public domain.

### Kaggle AIS Dataset
`eminserkanerdonmez/ais-dataset` covers Kattegat Strait transits.
Schema details aren't fully exposed in search results, so the seed
script will **introspect column names at load time** and write the
inferred schema into a sidecar JSON file rather than hardcoding.
Download requires the Kaggle API (`KAGGLE_USERNAME` + `KAGGLE_KEY`),
performed once on first boot; the CSV is then stored under
`data/seed/kaggle-ais/`.

### Flightradar24
The official B2B API portal is `https://fr24api.flightradar24.com/`.
There is a **sandbox key** for unbilled endpoint testing — use it in
CI. Paid tiers start at Explorer ($9/mo, 60k credits). **Never** scrape
`flightradar24.com` directly; that violates ToS. Endpoints we need:
live flight positions (`/live/flight-positions/full`), flight summary,
airport/airline metadata.

### Kepler.gl + Deck.gl
Kepler 3.x uses MapLibre by default. Deck.gl integrates with MapLibre
in three modes; we will use **interleaved mode** so Deck layers
participate in the WebGL2 depth buffer. Kepler.gl is a React+Redux
component; in Next.js we will mount it client-only via dynamic import
to avoid SSR.

### Wokwi
No API; iframe embed by project ID:
`<iframe src="https://wokwi.com/projects/{PROJECT_ID}"></iframe>`.
We will ship a curated `wokwi_projects.json` of demo projects (e.g.
ESP32 + GPS, sensor logger) and let the analyst pick from a dropdown.
Document each project ID's upstream link.

## Phase Plan (v0.1.0)

Sequential. Each phase ends with linters + tests green and a
`git commit` checkpoint with a descriptive message.

- **Phase 0 — Scaffold.** Repo skeleton, this `CLAUDE.md`, `.env.example`,
  `.gitignore`, `docker-compose.yml` skeleton, pre-commit config,
  `README.md` quickstart. _Commit._
- **Phase 1 — Data layer.** Postgres + PostGIS + Timescale containers,
  Alembic, base schemas (vessels, aircraft, hosts, cases, entities,
  vessel_positions, aircraft_positions). Kaggle seed migration.
  _Verify: `alembic upgrade head` + seed query returns rows. Commit._
- **Phase 2 — Backend skeleton.** FastAPI, `/health`, JWT auth,
  role middleware, per-source token-bucket rate-limit middleware,
  Adapter interface ABC. _Verify: pytest on auth + rate-limit. Commit._
- **Phase 3 — Adapters with mocks.** One adapter per source. Real impl
  behind a feature flag gated on env var presence. _Verify: every
  adapter returns valid shaped data in mock mode. Commit._
- **Phase 4 — Frontend skeleton.** Next.js + Tailwind + shadcn,
  global layout, map context provider, global entity search, auth
  pages. _Verify: `npm run build` green, login E2E. Commit._
- **Phase 5 — Dashboards** (one at a time, commit after each):
  1. Maritime Domain Awareness
  2. Aviation Tracking
  3. Cyber Surface
  4. AI Web Search
  5. Analyst Case File
- **Phase 6 — Supporting panels.** Tooling Library tree, Sensor Sim
  iframe. _Commit._
- **Phase 7 — Cross-cutting.** STIX 2.1 + PDF export for Case File,
  isolation-forest anomaly model on Kaggle AIS, Saved Monitors for
  Shodan. _Commit._
- **Phase 8 — Polish.** WCAG 2.1 AA pass, dark mode default with light
  toggle, `ANALYST_GUIDE.md` walkthrough. _Final commit, tag `v0.1.0`._

## Rules of Engagement

- **Pause and ask** before any destructive action (drop DB, force push,
  delete >1 file at once).
- **Lint + test at each phase boundary.** Red build blocks advance.
- **No microservices, no Kubernetes operators, no custom auth provider** in v1.
- **Read docs first; never invent endpoints.**
- **Mock-first.** Platform boots end-to-end with zero API keys on a fresh clone.
- **Comment the non-obvious bits**, especially in geospatial and signal-processing code.

## Repository Layout (target)

```
.
├── CLAUDE.md                   # this file
├── README.md                   # quickstart
├── ANALYST_GUIDE.md            # Phase 8 walkthrough
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── docker-compose.yml
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── auth/
│   │   ├── core/               # config, db, redis, rate-limit
│   │   ├── adapters/           # one module per source
│   │   ├── routers/            # one router per source + cases
│   │   ├── workers/            # celery tasks (ETL, anomaly)
│   │   └── schemas/            # pydantic models
│   ├── alembic/
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── app/                    # Next.js App Router
│   │   ├── (auth)/
│   │   ├── (dashboards)/
│   │   │   ├── maritime/
│   │   │   ├── aviation/
│   │   │   ├── cyber/
│   │   │   ├── web/
│   │   │   └── case/
│   │   └── layout.tsx
│   ├── components/
│   ├── lib/                    # api client, map context
│   └── data/                   # osint-framework.json, wokwi_projects.json
├── data/
│   └── seed/                   # downloaded Kaggle + sample MarineCadastre
└── deploy/
    └── k8s/                    # stubs only for v1
```
