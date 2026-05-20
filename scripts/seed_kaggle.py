#!/usr/bin/env python3
"""Pull the real Kaggle AIS dataset, if credentials are configured.

Idempotent. If the target CSV already exists and ``--force`` is not given,
it's a no-op. Writes ``schema.json`` next to the CSV so the seed migration
can introspect column names without hardcoding.

Usage:
    python scripts/seed_kaggle.py [--force]

Without ``KAGGLE_USERNAME`` and ``KAGGLE_KEY`` in env, this script exits
0 (the committed sample.csv keeps Aperture booting end-to-end).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile
from pathlib import Path

DATASET = "eminserkanerdonmez/ais-dataset"
SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seed" / "kaggle-ais"


def _credentials_present() -> bool:
    return bool(os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"))


def _download_with_kaggle_cli() -> Path:
    """Use the kaggle CLI (imported lazily so its absence is non-fatal)."""
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except Exception as exc:  # pragma: no cover - env-dependent
        print(f"[seed_kaggle] kaggle package not installed: {exc}", file=sys.stderr)
        print("[seed_kaggle] install with: pip install kaggle", file=sys.stderr)
        sys.exit(2)

    api = KaggleApi()
    api.authenticate()
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    api.dataset_download_files(DATASET, path=str(SEED_DIR), unzip=False, quiet=False)

    # Find the downloaded zip — Kaggle names it after the dataset slug.
    zips = sorted(SEED_DIR.glob("*.zip"))
    if not zips:
        print("[seed_kaggle] no zip downloaded — Kaggle returned no files.", file=sys.stderr)
        sys.exit(3)
    return zips[-1]


def _extract(zip_path: Path) -> list[Path]:
    extracted: list[Path] = []
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if member.endswith("/") or member.startswith("."):
                continue
            out = SEED_DIR / Path(member).name
            with zf.open(member) as src, out.open("wb") as dst:
                dst.write(src.read())
            extracted.append(out)
    return extracted


def _write_schema_sidecar(csvs: list[Path]) -> None:
    """Introspect column names + naive dtype guesses, store as schema.json."""
    import csv as _csv

    summary: dict[str, dict] = {}
    for path in csvs:
        if path.suffix.lower() != ".csv":
            continue
        with path.open("r", newline="") as f:
            reader = _csv.DictReader(f)
            headers = reader.fieldnames or []
            sample = next(reader, None)
        summary[path.name] = {
            "columns": headers,
            "sample": sample,
        }
    if summary:
        (SEED_DIR / "schema.json").write_text(json.dumps(summary, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-download even if data is present.")
    args = parser.parse_args()

    if not _credentials_present():
        print(
            "[seed_kaggle] KAGGLE_USERNAME/KAGGLE_KEY not set. "
            "Skipping (mock sample.csv will be used)."
        )
        return 0

    existing = list(SEED_DIR.glob("*.csv"))
    real_existing = [p for p in existing if p.name != "sample.csv"]
    if real_existing and not args.force:
        print(f"[seed_kaggle] {len(real_existing)} CSV(s) already present — skipping.")
        return 0

    print(f"[seed_kaggle] downloading {DATASET} ...")
    zip_path = _download_with_kaggle_cli()
    extracted = _extract(zip_path)
    zip_path.unlink(missing_ok=True)
    _write_schema_sidecar(extracted)
    print(f"[seed_kaggle] extracted {len(extracted)} file(s) into {SEED_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
