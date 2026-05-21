# Changelog

All notable changes to Aperture land here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions
follow [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-05-21

**Initial public release.** Analyst-grade OSINT fusion platform —
cyber, maritime, aviation, and open-web on a single geospatial map,
with a cross-domain Case File that exports to STIX 2.1 and PDF. Boots
end-to-end on a fresh clone with **zero API keys** (mock-mode
adapters). Real adapters activate when the matching env var is set.

### Built across 8 phases (22 commits on the trunk)

| Phase | Deliverable |
|-------|-------------|
| 0 | Scaffold + `.env.example` + docker-compose + pre-commit |
| 1 | Data layer — Postgres + PostGIS + TimescaleDB, Alembic, Kaggle AIS seed (introspecting CSV loader) |
| 2 | Backend skeleton — FastAPI, JWT auth + 3 roles, token-bucket rate limiter (AISHub 1/min enforced), `SourceAdapter` ABC |
| 3 | 9 adapters with mocks: Shodan, Exa, AISHub, BarentsWatch, MarineCadastre, Flightradar24, Kaggle, OSINT Framework, Wokwi — every endpoint shape / auth flow / rate limit pulled from live docs, not invented |
| 4 | Frontend skeleton — Next.js 14 App Router, Tailwind, shared MapLibre + Deck.gl context, typed Zod API client, auth pages |
| 5 | 5 dashboards (one commit each): Maritime, Aviation, Cyber, Web, Case File |
| 6 | Supporting panels — Tooling Library (OSINT Framework tree) + Sensor Sim (Wokwi iframe) |
| 7 | Cross-cutting: STIX 2.1 export, PDF export, isolation-forest anomaly model, Saved Shodan monitors |
| 8 | Polish — WCAG 2.1 AA pass + cross-dashboard pin rollout, light-mode toggle with flash-free init, `ANALYST_GUIDE.md` walkthrough |

### Verification at release

- 106 backend tests green (ruff + black clean)
- 13 frontend routes built statically, ESLint zero warnings, 87.2 kB shared First Load JS
- Live register → login → `/auth/me` round-trip against the running backend
- End-to-end STIX bundle + PDF export from a populated case

### What v0.1.0 is *not*

- Not a microservices deploy — single docker-compose, single backend process. Kubernetes manifests are stubs under `deploy/k8s/`.
- Not multi-tenant — owner-scoped cases, but no orgs / workspaces.
- Not OIDC — JWT + 3 roles by design, per the "keep auth boring" rule in `CLAUDE.md`.
- PDF / STIX exports inline (no signed URLs).
- Frontend stores JWT in `localStorage`; HttpOnly-cookie auth is a follow-up.

### Where to read more

- Source-by-source TOS notes and integration captures: [`CLAUDE.md`](./CLAUDE.md)
- End-to-end investigation walkthrough: [`ANALYST_GUIDE.md`](./ANALYST_GUIDE.md)

[0.1.0]: https://github.com/Tarrucks/IntelDash/releases/tag/v0.1.0
