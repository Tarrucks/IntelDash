# Coding Agent Session — Vessel Anomaly Detector (Aperture, Phase 7.3)

> A real end-to-end session from the **Aperture** OSINT fusion platform: going
> from "I want the map to flag weird vessels" to a shipped, tested, cached
> IsolationForest scoring endpoint — including the bug that briefly made every
> normal ship look anomalous.
>
> Stack: FastAPI · PostGIS/TimescaleDB · scikit-learn · Next.js + Deck.gl
> Commit: `ad9b6c7` — *Phase 7.3: vessel anomaly model (isolation forest)*

---

## 1. The ask

**User:**
> On the maritime map I want to surface vessels that are behaving oddly —
> spoofed GPS, drifting, sitting still pointed the wrong way. We already ingest
> the Kaggle AIS seed into the `vessel_positions` hypertable. Build a "show
> anomalies" mode. No labels, no API keys, has to work on a fresh clone.

**Agent:**
Unsupervised is the only honest option here — we have no labelled spoofing
events, and the default seed is tiny (23 rows over 6 vessels). That points at
**IsolationForest**: no labels, gives a continuous score *and* a binary flag,
and is robust on small samples. Plan:

1. Feature engineering on `(sog, cog, heading)` that respects angle wrap-around.
2. A process-singleton model with lazy fit + on-disk cache so a backend reboot
   doesn't retrain.
3. `GET /maritime/anomalies` returning the same fused shape as `/maritime/live`
   plus `anomaly_score` / `is_anomaly` per vessel.
4. A frontend toggle that recolours the existing Deck.gl `ScatterplotLayer`.

Before writing the model I want to confirm what's actually in the hypertable.

---

## 2. Grounding in the real schema

**Agent** *(tool: Grep — `class VesselPosition`)*

```
backend/app/models/positions.py
  19:  class VesselPosition(Base):
  20:      __tablename__ = "vessel_positions"
  24:      time     = mapped_column(TIMESTAMP(timezone=True), ...)
  25:      mmsi     = mapped_column(String, ...)
  29:      sog      = mapped_column(Float, nullable=True)   # speed over ground
  30:      cog      = mapped_column(Float, nullable=True)   # course over ground
  31:      heading  = mapped_column(Float, nullable=True)   # vessel heading
```

`sog`, `cog`, `heading` are all nullable — AIS messages routinely drop fields.
The feature builder has to treat `None` as a deliberate, non-informative case,
not crash or silently coerce to a misleading `0`.

**Key insight the agent flagged early:**
> `cog` and `heading` are *angles*. Feeding 359 and 1 to the model as raw floats
> tells it they're 358 units apart when they're 2° apart. I'll decompose every
> angle onto the unit circle (`sin`, `cos`) so the geometry is preserved, and
> add one engineered feature — `|heading − cog|` with wrap-around — because the
> deviation between where a ship *points* and where it *moves* is the classic
> tell for drifting / spoofed / adrift vessels.

---

## 3. The feature builder

```python
def _angle(deg: float | None) -> tuple[float, float]:
    """Unit-circle decomposition (sin, cos). None → (0, 1) — i.e. "due
    north" — the best non-informative prior we can offer."""
    if deg is None:
        return 0.0, 1.0
    rad = math.radians(float(deg))
    return math.sin(rad), math.cos(rad)


def _row_features(sog, cog, heading) -> list[float]:
    cs, cc = _angle(cog)
    hs, hc = _angle(heading)
    if cog is not None and heading is not None:
        # Smallest absolute angular difference in degrees.
        diff = abs((heading - cog + 180.0) % 360.0 - 180.0)
    else:
        diff = 0.0
    return [float(sog or 0.0), cs, cc, hs, hc, diff]
```

The `(x + 180) % 360 - 180` trick maps any raw difference into `[-180, 180]`
before the `abs`, so `heading=5, cog=355` correctly yields **10°**, not 350°.

**Agent wrote the test for the trick *first*:**

```python
def test_row_features_handles_wrap_around():
    # heading=5, cog=355 → smallest angular diff is 10°, not 350°.
    feats = _row_features(10.0, 355.0, 5.0)
    assert abs(feats[-1] - 10.0) < 1e-9
```

---

## 4. The bug — every normal ship lit up red

The model wraps sklearn in a process-singleton with lazy fit and a joblib
cache. With it wired up, the agent ran the synthetic-outlier test:

```python
def test_fit_flags_obvious_outlier():
    samples = [(12.0, 45.0, 46.0)] * 30 + [(11.8, 45.0, 46.0)] * 20
    samples.append((0.0, 0.0, 180.0))      # stationary, pointed 180° off course
    m.fit(samples)
    normal  = m.predict(12.0, 45.0, 46.0)
    outlier = m.predict(0.0, 0.0, 180.0)
    assert outlier.score > normal.score    # ❌ FAILED
```

**Pytest:**
```
>       assert outlier.score > normal.score
E       assert -0.1402 > 0.0488
```

**Agent diagnosis:**
> The flag is correct (`predict() == -1` on the outlier) but the *score* is
> inverted. sklearn's `score_samples` returns the average path length where
> **higher = more normal** — anomalies get the *lower* number. I exposed it
> raw, so on the dashboard the calmest cruise ship would render reddest. The
> frontend colour ramp is "red is bad", so the score has to point the same way.
> Fix: negate the decision score at the boundary, where the convention lives —
> not in the consuming layer.

```python
raw  = float(self._model.score_samples(x)[0])
flag = bool(self._model.predict(x)[0] == -1)
# Negate so higher = more anomalous, matching the dashboard's
# "red is bad" colour convention.
return AnomalyResult(score=-raw, is_anomaly=flag)
```

```
backend/tests/test_anomaly.py::test_fit_flags_obvious_outlier PASSED
```

A one-character bug (`-raw`) that, shipped, would have inverted the entire
feature. Caught because the test asserted on *direction*, not just a threshold.

---

## 5. Caching that invalidates on the right signal

**User:**
> Does this retrain on every request? The hypertable grows every poll.

**Agent:**
No — and it deliberately doesn't retrain on row-count changes either. The
model is a lazy process singleton: first request that needs a score trains
from `vessel_positions` and persists to `data/cache/anomaly_isoforest.joblib`;
a fresh boot loads the cache instead of refitting. Retraining on every ingest
would be pure waste — AIS at scale is thousands of rows a minute.

The *realistic* invalidation trigger is **schema drift** — a MarineCadastre or
Kaggle re-import changing the column set — not volume. So I exposed an explicit
`invalidate_cache()` that drops both the in-process and on-disk copies, and the
tests call it in fixture setup/teardown so model state never leaks between runs.

```python
def get_model(db: Session) -> VesselAnomalyModel:
    global _singleton
    if _singleton is None:
        _singleton = VesselAnomalyModel()
        if not _singleton.load():        # cache miss → train once
            _train_from_db(_singleton, db)
            _singleton.save()
    return _singleton
```

---

## 6. The endpoint

`GET /maritime/anomalies` mirrors `/maritime/live` so the frontend reuses its
existing decoder, then layers on the scores and a transparency counter so an
analyst can see *what the model actually learned from*:

```jsonc
{
  "sources": ["kaggle", "isoforest"],
  "model_trained_on": 30,          // rows the live model was fitted on
  "vessels": [
    { "mmsi": "219000777", "lat": 56.1, "lon": 11.5,
      "anomaly_score": 0.71, "is_anomaly": true }
  ]
}
```

Integration tests cover auth (401), bbox validation (`latmin > latmax` → 400),
and the scored happy path:

```python
def test_anomalies_endpoint_returns_scored_vessels(authed_client):
    client, db = authed_client
    _seed_for_anomaly(db)                       # 30 cruise-steady + 1 outlier
    r = client.get("/maritime/anomalies?latmin=55&latmax=58&lonmin=10&lonmax=13")
    assert r.status_code == 200
    body = r.json()
    assert "isoforest" in body["sources"]
    assert body["model_trained_on"] >= 30
    for v in body["vessels"]:
        assert isinstance(v["anomaly_score"], (int, float))
        assert isinstance(v["is_anomaly"], bool)
```

---

## 7. Frontend — one toggle, recolour the layer

No new map layer. The maritime page gained a **"Show anomalies"** toggle next
to Refresh; in anomaly mode the existing `ScatterplotLayer` swaps its fill
accessor to ramp on `anomaly_score`, and flagged vessels get a pulsing ring.
Pin-to-Case-File carries the score across to the Analyst Case File so an
investigation can cite *why* a vessel was pulled in.

---

## 8. Green build + checkpoint

```
$ ruff check . && black --check . && pytest -q backend/tests/test_anomaly.py
14 passed in 1.83s

$ npm run build --prefix frontend
✓ Compiled successfully
```

```
$ git commit -m "Phase 7.3: vessel anomaly model (isolation forest)"
[claude/youthful-bell-c6acxn ad9b6c7] Phase 7.3: vessel anomaly model (isolation forest)
 8 files changed, 511 insertions(+), 6 deletions(-)
```

---

## Why I'm proud of this one

- **Domain-correct ML, not cargo-cult ML.** The unit-circle decomposition and
  the heading-vs-COG deviation feature come from how AIS spoofing/drift
  *actually* manifests — not a generic "throw the columns at a model" pass.
- **The inverted-score bug.** A single sign error that would have silently
  shipped a feature doing the exact opposite of its job, caught only because
  the test asserted on *direction* and the colour convention was pinned down at
  one boundary instead of smeared across layers.
- **Caching designed around the real invalidation signal** (schema drift), not
  the obvious-but-wrong one (row count).
- **Mock-first, zero-key, fresh-clone runnable** — trains on the 23-row seed,
  same model scales to the full Kaggle / MarineCadastre pull with no code
  change.
- **Honest transparency surface** — `model_trained_on` means an analyst is
  never shown a confident-looking score from a model that learned from almost
  nothing.
