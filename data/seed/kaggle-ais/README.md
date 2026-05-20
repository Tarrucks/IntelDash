# Kaggle AIS seed data

This directory holds the seed sample loaded by Alembic migration
`0002_seed_kaggle_ais` into the `vessels` and `vessel_positions` tables
on first boot.

## What ships in git

- `sample.csv` — a small synthetic Kattegat-area AIS sample (~24 rows
  across 6 vessels). Realistic column shape (matching MarineCadastre /
  Kaggle conventions: MMSI, BaseDateTime, LAT, LON, SOG, COG, Heading,
  VesselName, IMO, CallSign, VesselType, Status, Length, Width) so
  downstream code can be developed without the real download.
- `README.md` — this file.

Anything else here is gitignored.

## Pulling the real Kaggle dataset

The full
[eminserkanerdonmez/ais-dataset](https://www.kaggle.com/datasets/eminserkanerdonmez/ais-dataset)
covers transits in the Kattegat Strait. With Kaggle credentials in
`.env` (`KAGGLE_USERNAME` and `KAGGLE_KEY`), run:

```bash
python scripts/seed_kaggle.py
```

That script will:

1. Download the dataset zip via the Kaggle CLI (one-shot).
2. Extract the CSV(s) into `data/seed/kaggle-ais/`.
3. Write `schema.json` next to the CSV with column names and inferred
   dtypes. The seed migration **introspects** column names at load
   time — it does not assume a fixed schema — so the migration keeps
   working if the upstream schema shifts.

## License

The upstream dataset license applies. Do not redistribute the full
CSV; the synthetic sample committed here is hand-written and not
derived from upstream rows.
