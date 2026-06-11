# Under a Day of Active Build: Spec → Green Deploy

### A coding-agent session log — building IntelDash (codename *Aperture*), an OSINT fusion platform scaffold

> **2026-05-20, 12:20 UTC** — `git init`, empty repo, one spec file (`CLAUDE.md`).
> **2026-05-21, 14:02 UTC** — v0.1.0 cut: 5 dashboards + analyst case file, 9 source adapters, ML anomaly detection, STIX 2.1 + PDF export, JWT auth, 106 test functions.
> **2026-05-21, 17:12 UTC** — Vercel + Fly deploy pipeline debugged to a green build.
>
> One founder, one agent (Claude Code). The honest frame: a 10,351-LOC platform scaffold, wired to a green deploy, in **well under a day of active agent-driven work** — spread across **a day and a half of calendar time, including a ~15-hour overnight break.**

| | |
|---|---|
| Calendar span, first → last commit | **28h 52m** wall-clock, across two days |
| — of which, large idle gaps | ~15h 17m overnight + ~4h 44m afternoon |
| **Active build windows** | **≈ 8h 51m** (elapsed minus those two gaps — an *upper* bound) |
| Code | 10,351 LOC (7,033 Python · 3,318 TS/TSX) |
| Surface area | 29 API endpoints · 9 adapters (mock-by-default) · 5 dashboards · 106 test functions |
| Keys required to boot | **0** |
| Repo | `Tarrucks/IntelDash` — **private** |

**The discipline of this piece: receipts, not adjectives.** Every number above is a command you can run against the repo; the exact outputs are pasted in the [Receipts](#receipts) section at the end. Where the work is mock rather than live, this says so. Where a thing was attempted but didn't land, this says that too.

---

## The operating model (this is the actual insight)

The session didn't start with "build me an app." It started with a 14 KB `CLAUDE.md` — a PRD the agent treats as a *contract*: an architecture table, a phase plan with exit criteria, and hard rules like:

> - **Do not fabricate API endpoints, response shapes, auth flows, or rate limits.** If the docs aren't clear, ship a typed interface + a `TODO(real-impl)` and a mock that returns realistically shaped data.
> - **Every adapter has a mock.** Real implementations live behind a feature flag triggered by the presence of the relevant env var.
> - **Linters + relevant tests run at the end of every phase. Do not advance with a red build.**

The agent ran the plan **phase-gated**: each phase ends with lint + tests green and a checkpoint commit; the human reviews at the boundaries, not over the shoulder. The compounding shows up in the timestamps — once Phase 4 landed the frontend scaffold and shared map context at 20:39, **all five dashboards landed within the next sixteen minutes**:

```
3f57848  2026-05-20 20:39  Phase 4: frontend skeleton — Next.js, Tailwind, shared map context
ee75561  2026-05-20 20:45  Phase 5.1: Maritime Domain Awareness dashboard
2474681  2026-05-20 20:47  Phase 5.2: Aviation Tracking dashboard
f4a116e  2026-05-20 20:50  Phase 5.3: Cyber Surface dashboard
ff3473c  2026-05-20 20:52  Phase 5.4: AI Web Search dashboard
5618f72  2026-05-20 20:55  Phase 5.5: Analyst Case File dashboard
```

That isn't the agent typing fast. It's architecture paying rent: the spec forced the map context, API client, and auth into shared layers in Phase 4, so each dashboard was composition, not construction.

**One calibration up front, because the whole piece depends on it.** This is a *scaffold*, and the data is *mock by default*. Of the nine adapters, six carry a real HTTP implementation gated behind env-var presence (`exa.py`, `shodan.py`, `fr24.py`, `aishub.py`, `barentswatch.py`, `kaggle.py`); the other three are static/embed/bulk-download by design (OSINT Framework is build-time JSON, Wokwi is an iframe embed, MarineCadastre is a bulk ETL pull). One `TODO(real-impl)` marker remains in the tree. **None of those real paths were exercised against a live endpoint in this build — there were zero keys present.** What the tests prove is *mock-shape conformance* (`test_adapters_mock.py`), so adding a key flips mock → real per-source with no code change. The mock-first decision is a strength, argued below — but a reader should never find daylight between "looks live" and "is live."

What follows are the four moments I'd actually show an investor — where the agent exercised judgment, not autocomplete.

---

## Moment 1 — A distribution decision disguised as an architecture decision

**Mock-first, zero keys.** IntelDash is built to fuse Shodan, AISHub, BarentsWatch, Flightradar24, Exa, MarineCadastre, Kaggle AIS — seven of those need credentials, two need paid plans. The naive build makes a stranger collect seven API keys before seeing a single pixel.

Instead, every adapter ships a mock returning realistically-shaped data, with the real implementation behind a feature flag keyed on env-var presence:

```
$ git clone … && docker compose up
→ full platform, live-looking maritime/aviation/cyber data, no signup walls
```

For a product whose buyers are analysts inside organizations with procurement departments, **time-to-first-demo is the growth wedge**. Anyone clones the repo and has the full experience in minutes; keys upgrade mock → real per-source with zero code changes. The agent didn't treat mocks as test scaffolding — it treated them as the top of the funnel. (To be precise about today's state: that demo is *mock data shaped like the real thing*, not live feeds — see the calibration above.)

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

Shipped unfixed, the feature would have worked in reverse and *looked* fine in a demo. The endpoint also returns `model_trained_on` — the row count the live model actually learned from — so an analyst is never shown a confident score from a model trained on almost nothing. That "refuse to mislead the analyst" instinct is the trust-building detail.

## Moment 4 — The last mile: a deploy fight, blow by blow

v0.1.0 was cut at 14:02. The next three hours were the unglamorous 10% that kills most side projects — and the agent debugged platform behavior from nearly zero signal:

**Round 1 (`0bf6b06`):** Vercel kept running `vitepress build docs` — a command from nowhere. Root cause: an empty `docs/` placeholder directory was enough for Vercel's framework auto-detector to *guess VitePress* and cache the guess. Fix: delete the directory, add a root `vercel.json` pinning `framework: nextjs` with explicit install/build commands.

**Round 2 (`82f9a9a`):** Build now dies **in 2 seconds with no error output**. Diagnosis: Vercel's build starts at the repo root, where there was no `package.json` — so Corepack couldn't resolve a pnpm version, and `cd frontend && pnpm install` exited before pnpm-the-binary existed on PATH. Fix: a root `package.json` whose only real job is `"packageManager": "pnpm@10.33.0"`, plus `corepack enable` ahead of the install. Verified locally before pushing: install 8.8s, build ships all 13 static routes.

**Round 3 (`b7f8368`):** Vercel rejects the config itself:

```
Invalid request: should NOT have additional property `_comment`
```

The agent had left a JSON "comment" key explaining the overrides; Vercel's schema forbids extra keys. Removed — and the explanation was *moved into the commit message and DEPLOY.md* rather than deleted, because the next maintainer still deserves the why.

17:12 UTC: the build goes green. Three rounds, twenty-five minutes of actual fight, each fix verified rather than guessed. (What's receipted here is a **green build pipeline plus Vercel + Fly deploy config** — not a confirmation that a public URL is currently serving traffic.)

---

## A note where the receipts contradict the commit messages

Two places where holding to "check the hashes" means correcting the optimistic version of events:

- **There is no `v0.1.0` git tag.** `git tag -l` is empty locally *and* on the remote. The Phase 8.4 commit (`3a98117`) is honest about why: the container's git remote 403s every tag push, so the release notes were mirrored into `CHANGELOG.md` as a `[0.1.0]` block instead. "v0.1.0" is a CHANGELOG entry and a commit, not a tag. The user can `git push origin v0.1.0` from a normal client.
- **The repo is private.** Earlier drafts of this writeup claimed "the commits are public" — they aren't (`visibility: private`). The receipts below are inlined precisely *because* you can't click through to verify them yourself today.

This section exists on purpose: a builder piece that corrects its own headline is more credible than one that doesn't have to.

---

## Receipts

**Active build time** — derived from `git log --reverse --date=format:'%Y-%m-%d %H:%M'`:

```
elapsed, first → last commit (12:20 day 1 → 17:12 day 2)   28h 52m
minus  Phase 6 → 7.1 overnight gap (21:37 → 12:54 next day) -15h 17m
minus  Phase 3 → 4 afternoon gap   (15:55 → 20:39)          - 4h 44m
                                                            ─────────
active build windows (upper bound)                          ≈ 8h 51m
```
This is an *upper* bound: the remaining windows still contain think-time, and we can't see the work that preceded the first commit at all.

**Code, endpoints, tests, adapters** — exact commands and outputs:

```
$ git ls-files 'backend/**/*.py'              | xargs wc -l | tail -1
  7033 total
$ git ls-files 'frontend/**/*.ts' '...*.tsx'  | xargs wc -l | tail -1
  3318 total                                          # → 10,351 LOC total
$ git grep -hE '@router\.(get|post|put|delete|patch)\(' -- 'backend/app/routers/*.py' | wc -l
  29                                                  # API endpoints
$ git grep -hE '^\s*def test_' -- 'backend/tests/*.py' | wc -l
  106                                                 # test functions
$ git ls-files 'backend/app/adapters/*.py' | grep -vE '__init__|base|registry' | wc -l
  9                                                   # source adapters
$ git grep -lE 'httpx|requests\.|aiohttp' -- 'backend/app/adapters/*.py' | wc -l
  6                                                   # adapters w/ real HTTP path
$ git grep -nE 'TODO\(real-impl\)' -- 'backend/app/adapters/*.py' | wc -l
  1
```

*Note on the test number:* 106 is the **collected count** (`grep 'def test_'`), not a live "106 passed" — the suite runs against a Postgres + Redis container per `conftest.py`, and green-at-each-phase-boundary is the gate that lets the agent advance. It is not reproducible inside this writeup's sandbox (no DB, sklearn absent), so it's reported as a count, not a pass.

**Repo visibility** — `GET /repos/Tarrucks/IntelDash` → `"visibility": "private"`, `"name": "IntelDash"`, default branch `claude/build-aperture-osint-bprmS`.

**Full timeline** — `git log --reverse`:

```
6677666  05-20 12:20  Phase 0: repo scaffold
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
3a98117  05-21 14:02  Phase 8.4: v0.1.0 release notes + CHANGELOG (tag push 403'd — see above)
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
2. **Judgment at every altitude.** Distribution strategy (mock-first funnel), partner relations (TOS as code), correctness (a direction-asserting test catching a sign flip), and last-mile grit (debugging a 2-second silent build death) — in one operating model.
3. **Velocity that compounds.** A 10k-LOC scaffold wired to a green deploy in **under nine hours of active build time** means the build-measure-learn loop runs in *days*. A solo founder operating this way iterates at a cadence that used to require a funded team.

What it is today: a deploy-ready scaffold with real architecture and mock-by-default data. What it isn't yet: live feeds, a public repo, traffic. Both halves of that sentence are in the receipts — which is the point.
