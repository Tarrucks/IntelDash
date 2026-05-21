# Aperture — Analyst Guide

> A walkthrough of a single investigation, touching all five dashboards
> and ending with a STIX 2.1 + PDF export. Every step works against the
> default mock data on a fresh clone — no API keys required.

If you're new to the platform, read [CLAUDE.md](./CLAUDE.md) first for
the architectural decisions and source-by-source TOS notes.

---

## Setting up

```bash
# 1. Clone + configure
git clone <repo> aperture && cd aperture
cp .env.example .env
bash scripts/setup.sh   # generates JWT_SECRET if blank

# 2. Bring up infra + backend + frontend
docker compose up -d db redis
# Backend in another terminal (uv-based):
cd backend && uv venv --python python3.12 .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
DATABASE_URL=postgresql+psycopg://aperture:aperture@localhost:5432/aperture \
  alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
# Frontend in another:
cd frontend && pnpm install && pnpm dev
# Open http://localhost:3000
```

The Kaggle seed migration loads 6 vessels (24 positions) into the
`vessel_positions` hypertable. With `KAGGLE_USERNAME` / `KAGGLE_KEY` in
`.env` you can pull the full Kattegat Strait dataset:

```bash
python scripts/seed_kaggle.py
# the anomaly model auto-retrains on first /maritime/anomalies request
```

## Roles

| Role     | Can do                                           |
| -------- | ------------------------------------------------ |
| viewer   | Read all dashboards.                             |
| analyst  | + create cases, pin entities, export STIX / PDF. |
| admin    | + see other analysts' cases.                     |

Self-register at `/register` (defaults to analyst). Promotion to admin
is currently a direct DB write — by design, no HTTP endpoint exposes it.

---

## The scenario

A partner agency tips us off about a suspicious bunkering operation in
the Kattegat Strait. Aperture connects four pieces of OSINT (host
infrastructure, vessel transit, overflight, public reporting) into a
single Case File the analyst can hand off.

---

## Step 1 — Cyber Surface: identify the host

The tip references a server at `203.0.113.10` running outdated nginx.
Open **Cyber Surface** and look it up.

```bash
# CLI equivalent:
curl -s -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/cyber/hosts/203.0.113.10 | jq
```

Expected (mock-mode):

```json
{
  "ip": "203.0.113.10",
  "hostnames": ["mock.example.com"],
  "ports": [22, 80, 443],
  "country_code": "US",
  "city": "Ashburn",
  "org": "MockHost LLC",
  "asn": "AS64500",
  "latitude": 39.0438,
  "longitude": -77.4874,
  "banners": [
    {"port": 22,  "product": "OpenSSH", "version": "9.3"},
    {"port": 443, "product": "nginx",   "version": "1.27.0"}
  ],
  "source": "mock"
}
```

The host upserts into the `hosts` table with a PostGIS POINT so it
lands on the global map. Click **Pin to active case** (Step 5 will set
up the case) or do it later.

Tip: the host search box accepts Shodan's own query language —
`product:"nginx" country:"US"` filters down to interesting matches.

## Step 2 — Saved monitor

We want to be alerted next time the banner on `:443` changes. Scroll
to the **Saved monitors** block at the bottom of the Cyber panel.

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"ip":"203.0.113.10","name":"Suspect edge","ports":[443]}' \
     http://localhost:8000/cyber/monitors
```

In mock mode this only persists locally; with `SHODAN_API_KEY` set
the backend also calls `POST /shodan/alert` and stores the upstream
alert id in the monitor's `extra`.

## Step 3 — Maritime: find vessels near the host's geo

The host's `latitude` / `longitude` put it in Northern Virginia, but
the *operation* we're chasing happens in the Kattegat. Pan the map to
roughly the Kattegat (centre near 56°N 11°E, zoom 7) and open the
**Maritime** dashboard. The shared map state means the vessel list
auto-refreshes for the new viewport.

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8000/maritime/live?latmin=55&latmax=58&lonmin=10&lonmax=13' \
  | jq '.vessels[] | {mmsi, name, sog, source}'
```

Mock mode returns the AISHub mock vessels plus any Kaggle-seeded
positions in the bbox. With `AISHUB_USERNAME` set, real AIS arrives —
respecting the strict **1 request / minute** token bucket.

Click `KATTEGAT STAR` (MMSI `219000123`). The detail card shows IMO,
call sign, dimensions, and a position-history count.

## Step 4 — Replay the last 24 hours

Click **Replay last 24h**. The map gains a BarentsWatch-mock path:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/maritime/vessels/219000123/tracks | jq '.tracks.type'
# "FeatureCollection"
```

With `BARENTSWATCH_CLIENT_ID` + `BARENTSWATCH_CLIENT_SECRET` set, the
OAuth2 client_credentials flow kicks in and the real GeoJSON arrives.

### Anomaly check

Toggle **Show anomalies**. The map recolours: flagged vessels go red,
normals fade. Score + flag come from an isolation-forest model trained
on (sog, cog, heading) plus heading-cog deviation.

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8000/maritime/anomalies?latmin=55&latmax=58&lonmin=10&lonmax=13' \
  | jq '.model_trained_on, .vessels[] | select(.is_anomaly==true) | .mmsi'
```

> On the small seed dataset (≤30 rows) the model has limited signal.
> Run `python scripts/seed_kaggle.py` with credentials, restart the
> backend (cache invalidates on first request), and re-query for a
> statistically meaningful read.

## Step 5 — Open the Case File

Switch to **Analyst Case File**, click **New case**:

- Title: `Op North Sea Bunkering`
- Summary: `Suspicious vessel transit + cyber footprint, May 2026.`

Clicking the new case in the list sets it as the **active case** (the
selection persists in localStorage and surfaces a banner on every
other dashboard with a "Pin to '<case>'" button).

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"title":"Op North Sea Bunkering","summary":"Suspicious vessel transit + cyber footprint, May 2026."}' \
     http://localhost:8000/cases | jq '.id'
```

## Step 6 — Pin entities from every dashboard

Walk back through the dashboards and click **Pin to "Op North Sea
Bunkering"** on each detail card:

- **Cyber:** `host` / `203.0.113.10`
- **Maritime:** `vessel` / `219000123` (KATTEGAT STAR), then
  optionally a second flagged vessel from the anomaly view
- **Aviation:** open `/aviation`, click a flight near Copenhagen, pin
  `aircraft` / its ICAO hex
- **Web:** open `/web`, search `dark fleet maritime sanctions evasion`,
  pin a result URL

## Step 7 — Cross-check the open web

In **AI Web Search**, switch to **Answer** mode and ask:

> `What is dark-fleet bunkering and how is it detected via AIS?`

The mock returns a synthesised paragraph + two citations. With
`EXA_API_KEY` set, Exa's real answer endpoint takes over.

## Step 8 — Export

Back on the **Case File** detail card, click **Export STIX 2.1** and
**Export PDF**. The buttons fire authed downloads:

```bash
# STIX 2.1 bundle
curl -s -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/cases/$CASE_ID/export.stix \
     -o aperture-op-north-sea.stix.json

# PDF dossier
curl -s -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/cases/$CASE_ID/export.pdf \
     -o aperture-op-north-sea.pdf
```

The STIX bundle includes:

- one `identity` SDO (the case owner),
- one SCO per pinned entity (`x-aperture-vessel`, `x-aperture-aircraft`,
  `ipv4-addr`, `url`, …),
- one `observed-data` SDO per SCO (downstream tools like MISP /
  OpenCTI expect SCOs to appear as object_refs, not free-standing),
- one `report` SDO referencing the entire set.

The PDF is a single dossier with a header (title, owner, dates,
status), summary, and a table of pins with kind-coloured chips,
labels, ref_ids, pinned-at timestamps, and an `extras` line picking
out high-signal fields (lat/lon, imo, registration, country).

---

## Supporting panels

**Tooling Library** (`/tooling`) is a mirror of the OSINT Framework
taxonomy. The build-time script
`python scripts/build_osint_framework.py` pulls the upstream
`arf.json` into `frontend/data/osint-framework.json`; without it, the
panel falls back to a small built-in taxonomy so the page still works.

**Sensor Sim** (`/sensors`) embeds Wokwi projects via iframe (e.g.
ESP32 GPS, DHT22 logger). Useful for prototyping the sensors that
feed Aperture in the field.

---

## Keyboard navigation

- `Tab` cycles through interactive elements. The skip-link visible at
  the top-left on first `Tab` jumps past the header and sidebar.
- All buttons and inputs show a visible focus ring (`:focus-visible`).
- The active sidebar item announces as `aria-current="page"`.
- The dashboard panels carry `aria-label`s for screen-reader landmark
  navigation (`Dashboard panel`, `Geospatial map`).

## Theme

The header carries a sun/moon toggle. The preference persists in
`localStorage("aperture.theme")` and is applied **before first paint**
via an inline `<head>` script — no flash of wrong theme. With no
preference set, the platform respects `prefers-color-scheme`,
defaulting to dark.

## Troubleshooting

- **`/health` reports `db: down`** — Postgres container isn't up.
  `docker compose up -d db && docker compose logs db | tail -20`.
- **`/maritime/live` returns empty** — bbox is too tight or the
  Kaggle seed didn't run. Run `alembic upgrade head` from `backend/`.
- **AISHub returns nothing for a real request** — you're inside the
  1/min cap. Wait 60 seconds.
- **PDF / STIX export 404s** — case belongs to another analyst.
  Promote your user to admin via direct DB write or sign in as the
  owner.
- **The map is blank** — `NEXT_PUBLIC_MAP_STYLE_URL` points at an
  unreachable host. The default is MapLibre's public demotiles style
  and needs only outbound internet.

## Where next

- Wire your real API keys in `.env` to flip adapters off mock.
- Run `python scripts/seed_kaggle.py` and bring up the anomaly model
  on a meaningful dataset.
- Stand up a Celery beat + worker to schedule Shodan Monitor sweeps.
