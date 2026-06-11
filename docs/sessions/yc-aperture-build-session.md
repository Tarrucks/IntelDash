# 29 Hours: Spec → Shipped

### A coding-agent session log — building and deploying Aperture, an analyst-grade OSINT fusion platform

> **2026-05-20, 12:20 UTC** — `git init`, empty repo, one spec file.
> **2026-05-21, 14:02 UTC** — v0.1.0 cut: 4 intelligence dashboards + analyst case file, 9 data-source adapters, ML anomaly detection, STIX 2.1 + PDF export, JWT auth, 106 tests.
> **2026-05-21, 17:12 UTC** — live in production on Vercel + Fly.io.
>
> One founder. One agent (Claude Code). **28 hours 52 minutes, 24 commits, every phase boundary green.**

| | |
|---|---|
| Elapsed, init → v0.1.0 | **25h 42m** |
| Elapsed, init → deployed | **28h 52m** |
| Code | 10,410 LOC (7,033 Python · 3,377 TypeScript) |
| Surface area | 29 API endpoints · 9 source adapters · 5 dashboards · 106 tests |
| API keys required to boot | **0** |

Every claim below has a receipt: a commit hash, an error string, or a line of code in the repo.

---

## The operating model (this is the actual product insight)

The session didn't start with "build me an app." It started with a 14 KB `CLAUDE.md` — a PRD the agent treats as a contract: architecture table, a phase plan with exit criteria, and hard rules like:

> - **Do not fabricate API endpoints, response shapes, auth flows, or rate limits.** If the docs aren't clear, ship a typed interface + a `TODO(real-impl)` and a mock that returns realistically shaped data.
> - **Every adapter has a mock.** Real implementations live behind a feature flag triggered by the presence of the relevant env var.
> - **Linters + relevant tests run at the end of every phase. Do not advance with a red build.**

The agent then ran the plan **phase-gated**: each phase ends with lint + tests green and a checkpoint commit; the human reviews at the boundaries, not over the shoulder. The compounding effect shows up in the timestamps — once Phase 4 landed the frontend scaffold and shared map context at 20:39, **five dashboards landed in the next sixteen minutes**:

```
3f57848  2026-05-20 20:39  Phase 4: frontend skeleton — Next.js, Tailwind, shared map context
ee75561  2026-05-20 20:45  Phase 5.1: Maritime Domain Awareness dashboard
2474681  2026-05-20 20:47  Phase 5.2: Aviation Tracking dashboard
f4a116e  2026-05-20 20:50  Phase 5.3: Cyber Surface dashboard
ff3473c  2026-05-20 20:52  Phase 5.4: AI Web Search dashboard
5618f72  2026-05-20 20:55  Phase 5.5: Analyst Case File dashboard
```

That's not the agent typing fast. That's architecture paying rent: the spec forced the map context, API client, and auth into shared layers in Phase 4, so each dashboard was composition, not construction.

What follows are the four moments from the session that I'd actually show an investor — the ones where the agent exercised judgment, not autocomplete.

---

## Moment 1 — A distribution decision disguised as an architecture decision

**Mock-first, zero keys.** Aperture fuses Shodan, AISHub, BarentsWatch, Flightradar24, Exa, MarineCadastre, Kaggle AIS — seven of those need credentials, two need paid plans. The naive build makes a stranger collect seven API keys before seeing a single pixel.

Instead, every adapter ships a mock returning realistically shaped data, with the real implementation behind a feature flag keyed on env-var presence:

```
$ git clone … && docker compose up
→ full platform, live-looking maritime/aviation/cyber data, no signup walls
```

For a product whose buyers are analysts inside organizations with procurement departments, **time-to-first-demo is the growth wedge**. Anyone can clone the repo and have the full experience in minutes; keys upgrade mock → real per-source with zero code changes. The agent didn't treat mocks as test scaffolding — it treated them as the top of the funnel.

## Moment 2 — Partner terms-of-service, encoded as code

AISHub's API has a brutal quirk: **poll it more than once per minute and it silently returns empty** — no error, no 429, your data just vanishes. Members also must contribute their own AIS feed, so a banned account is a real business loss.

The agent read the provider docs and encoded the constraint into the platform's token-bucket layer (`backend/app/core/rate_limit.py`):

```python
SOURCE_LIMITS: dict[str, RateLimitConfig] = {
    # AISHub: hard 1/min cap is from the official API page.
    "aishub": RateLimitConfig(capacity=1.0, refill_per_sec=1.0 / 60.0, name="aishub"),
    ...
}
```

…and documented the *why* at the top of the adapter so no future contributor "optimizes" it away:

```python
"""**The webservice silently returns empty if polled more than once per
minute.** Our token bucket (capacity=1, refill=1/60) enforces that. The
real adapter must not bypass it; the mock skips the bucket so tests run
fast."""
```

An agent that reads upstream docs and encodes partner constraints is the difference between a data platform and a cease-and-desist letter.

## Moment 3 — The one-character bug that would have inverted a feature

Phase 7.3: unsupervised vessel-anomaly detection (spoofed GPS, drifting, adrift) — IsolationForest over engineered features. The feature engineering is domain-correct: angles get **unit-circle decomposition** so 359° and 1° sit close in feature space, plus `|heading − cog|` with wrap-around — the angle between where a ship *points* and where it *moves*, the classic AIS spoofing tell.

The agent wrote the test before trusting the model — and the test asserted on **direction**, not just a threshold:

```python
samples = [(12.0, 45.0, 46.0)] * 30 + [(11.8, 45.0, 46.0)] * 20
samples.append((0.0, 0.0, 180.0))   # stationary, pointed 180° off course
...
assert outlier.score > normal.score
```

```
E       assert -0.1402 > 0.0488     ← FAILED
```

Diagnosis: the binary flag was right, but sklearn's `score_samples` returns *higher = more normal*. Exposed raw, the calmest cruise ship on the dashboard would have rendered reddest. The fix is one character, placed at the one boundary where the convention lives:

```python
# Negate so higher = more anomalous — matches the dashboard's
# "red is bad" colour convention.
return AnomalyResult(score=-raw, is_anomaly=flag)
```

Shipped unfixed, the feature would have worked in reverse and *looked* fine in a demo. The endpoint also returns `model_trained_on` — the row count the live model actually learned from — so an analyst is never shown a confident score from a model trained on almost nothing.

## Moment 4 — The last mile: a production deploy fight, blow by blow

v0.1.0 was tagged at 14:02. The next three hours were the unglamorous 10% that kills most side projects — and the agent debugged production platform behavior from nearly zero signal:

**Round 1 (`0bf6b06`):** Vercel kept running `vitepress build docs` — a command from nowhere. Root cause: an empty `docs/` placeholder directory was enough for Vercel's framework auto-detector to *guess VitePress* and cache the guess. Fix: delete the directory, add a root `vercel.json` that pins `framework: nextjs` with explicit install/build commands.

**Round 2 (`82f9a9a`):** Build now dies **in 2 seconds with no error output**. Diagnosis: Vercel's build starts at the repo root, where there was no `package.json` — so Corepack couldn't resolve a pnpm version, and `cd frontend && pnpm install` exited before pnpm-the-binary existed on PATH. Fix: a root `package.json` whose only real job is `"packageManager": "pnpm@10.33.0"`, plus `corepack enable` ahead of the install. Verified locally before pushing: install 8.8s, build ships all 13 static routes.

**Round 3 (`b7f8368`):** Vercel rejects the config itself:

```
Invalid request: should NOT have additional property `_comment`
```

The agent had left a JSON "comment" key explaining the overrides; Vercel's schema forbids extra keys. Removed — and the explanation was *moved into the commit message and DEPLOY.md* rather than deleted, because the next maintainer still deserves the why.

17:12 UTC: live. Three rounds, twenty-five minutes of actual fight, each fix verified rather than guessed.

---

## The receipts — full timeline, `git log --reverse`

```
6677666  05-20 12:20  Phase 0: repo scaffold for Aperture OSINT platform
fc39caf  05-20 14:46  Phase 1: data layer — schema, hypertables, Kaggle AIS seed
fe050e5  05-20 15:49  Phase 2: backend skeleton — FastAPI, JWT auth, token-bucket rate limit
4a91db8  05-20 15:55  Phase 3: source adapters with mocks for all nine data sources
3f57848  05-20 20:39  Phase 4: frontend skeleton — Next.js, Tailwind, shared map context
ee75561  05-20 20:45  Phase 5.1: Maritime Domain Awareness dashboard
2474681  05-20 20:47  Phase 5.2: Aviation Tracking dashboard
f4a116e  05-20 20:50  Phase 5.3: Cyber Surface dashboard
ff3473c  05-20 20:52  Phase 5.4: AI Web Search dashboard
5618f72  05-20 20:55  Phase 5.5: Analyst Case File dashboard
cccf412  05-20 21:37  Phase 6: supporting panels — Tooling Library + Sensor Sim
4f056c1  05-21 12:54  Phase 7.1: STIX 2.1 export for Case File
048453f  05-21 12:56  Phase 7.2: PDF export for Case File
ad9b6c7  05-21 13:01  Phase 7.3: vessel anomaly model (isolation forest)
318da76  05-21 13:06  Phase 7.4: saved Shodan monitors
055c0c7  05-21 13:58  Phase 8.1: WCAG 2.1 AA pass + cross-dashboard pin rollout
34f9337  05-21 14:00  Phase 8.2: light-mode toggle
c99a105  05-21 14:01  Phase 8.3: ANALYST_GUIDE.md walkthrough
3a98117  05-21 14:02  Phase 8.4: tag v0.1.0 + CHANGELOG
40baf2b  05-21 15:28  Add Vercel + Fly deploy artifacts
8e31c4c  05-21 16:24  Deploy fixes: env-driven CORS, repo-root Docker context, fly.toml
0bf6b06  05-21 16:47  Force Vercel to build the frontend, not phantom VitePress
82f9a9a  05-21 16:50  Fix Vercel build — add root package.json so Corepack finds pnpm
b7f8368  05-21 17:12  Strip _comment from vercel.json — schema validation rejects extras
```

---

## Why this session matters

The headline isn't "AI wrote 10,000 lines." It's that this is a **repeatable operating model**, and the session is the proof run:

1. **Spec as contract.** The PRD lives in the repo, the agent is bound by it, and "do not advance with a red build" is enforced, not aspirational.
2. **Judgment at every altitude.** Distribution strategy (mock-first funnel), partner relations (TOS as code), correctness (direction-asserting tests catching a sign flip), and production grit (debugging a 2-second silent build death) — in one continuous session.
3. **Velocity that compounds.** Spec → deployed in under 29 hours means the build-measure-learn loop runs in *days*. A solo founder operating this way iterates with users at a cadence that used to require a funded team.

The platform is real, the commits are public, and the next 29 hours are already spec'd.
