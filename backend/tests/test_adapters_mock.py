"""Phase 3 verification: every adapter returns valid shaped data in mock mode.

These are DB-free unit tests — adapters don't talk to Postgres. We
force mock mode by leaving all credential env vars unset (no key
populated = ``is_configured`` is False = ``mode == "mock"``).
"""

from __future__ import annotations

import os

import pytest

# Force mock mode for every adapter before app.config is imported.
os.environ.pop("SHODAN_API_KEY", None)
os.environ.pop("EXA_API_KEY", None)
os.environ.pop("AISHUB_USERNAME", None)
os.environ.pop("BARENTSWATCH_CLIENT_ID", None)
os.environ.pop("BARENTSWATCH_CLIENT_SECRET", None)
os.environ.pop("FR24_API_KEY", None)
os.environ.pop("KAGGLE_USERNAME", None)
os.environ.pop("KAGGLE_KEY", None)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    # ``get_settings`` is lru_cached; nuke it so the env-var changes
    # above take effect for each test.
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _make(name: str):
    """Construct an adapter directly (bucket=None bypasses Redis)."""
    from app.adapters.registry import ADAPTER_CLASSES
    from app.core.config import get_settings

    return ADAPTER_CLASSES[name](settings=get_settings(), bucket=None)


# ---- Shodan -----------------------------------------------------------------


def test_shodan_mock_host_shape():
    a = _make("shodan")
    assert a.mode == "mock"
    host = a.host("203.0.113.10")
    assert host.ip_str == "203.0.113.10"
    assert host.ports == [22, 80, 443]
    assert len(host.data) >= 1
    # The PostGIS pipeline expects lat/lon as floats.
    assert isinstance(host.latitude, float)
    assert isinstance(host.longitude, float)


def test_shodan_mock_search_shape():
    a = _make("shodan")
    resp = a.search("nginx", limit=3)
    assert resp.total == len(resp.matches)
    assert all(m.ip_str.startswith("203.0.113.") for m in resp.matches)


# ---- Exa --------------------------------------------------------------------


def test_exa_mock_search_shape():
    a = _make("exa")
    assert a.mode == "mock"
    r = a.search("missile defense system", num_results=4)
    assert len(r.results) == 4
    assert all(result.url.startswith("https://example.com/") for result in r.results)
    # Scores should be monotonically decreasing in our mock — useful invariant
    # for testing rank-aware UI later.
    scores = [result.score for result in r.results]
    assert scores == sorted(scores, reverse=True)


def test_exa_mock_answer_shape():
    a = _make("exa")
    r = a.answer("what is AIS")
    assert r.answer
    assert len(r.citations) >= 1
    assert all(c.url.startswith("http") for c in r.citations)


# ---- AISHub -----------------------------------------------------------------


def test_aishub_mock_bbox_shape():
    a = _make("aishub")
    assert a.mode == "mock"
    vessels = a.fetch_bbox(latmin=55.0, latmax=58.0, lonmin=10.0, lonmax=13.0)
    assert len(vessels) == 2
    # Returned vessels must lie inside the bbox.
    for v in vessels:
        assert 55.0 <= v.latitude <= 58.0, v.latitude
        assert 10.0 <= v.longitude <= 13.0, v.longitude
        assert v.mmsi.isdigit()


# ---- BarentsWatch -----------------------------------------------------------


def test_barentswatch_mock_tracks_geojson():
    a = _make("barentswatch")
    assert a.mode == "mock"
    fc = a.tracks_last_24h("219000123")
    assert fc.type == "FeatureCollection"
    assert len(fc.features) == 1
    feat = fc.features[0]
    assert feat.geometry["type"] == "LineString"
    coords = feat.geometry["coordinates"]
    assert len(coords) >= 2
    # GeoJSON is [lon, lat]; sanity check ranges.
    for lon, lat in coords:
        assert -180 <= lon <= 180
        assert -90 <= lat <= 90


# ---- MarineCadastre ---------------------------------------------------------


def test_marinecadastre_years_and_url():
    a = _make("marinecadastre")
    years = a.available_years()
    assert 2024 in years
    f = a.download_url(2024, zone=10)
    assert f.year == 2024
    assert f.format == "csv"
    assert "2024" in str(f.url)


# ---- Flightradar24 ----------------------------------------------------------


def test_fr24_mock_live_positions_shape():
    a = _make("fr24")
    assert a.mode == "mock"
    r = a.live_positions(bounds=(58.0, 54.0, 8.0, 14.0), limit=4)
    assert len(r.data) == 4
    for fp in r.data:
        assert len(fp.hex) == 6
        assert 54.0 - 1 <= fp.lat <= 58.0 + 1  # mock spreads around bbox centre
        assert fp.callsign and fp.callsign.startswith("SAS")


# ---- Kaggle -----------------------------------------------------------------


def test_kaggle_seed_status_detects_sample():
    a = _make("kaggle")
    status = a.seed_status()
    assert status.configured is False  # no keys in test env
    # The sample CSV ships in git — it must be detected.
    assert status.sample_present is True


# ---- OSINT Framework --------------------------------------------------------


def test_osintframework_tree_and_flat_leaves():
    a = _make("osintframework")
    tree = a.tree()
    assert tree.type == "folder"
    assert tree.name == "OSINT Framework"
    assert len(tree.children) >= 1

    leaves = a.flat_leaves()
    assert len(leaves) >= 4
    assert all(leaf.url.startswith("http") for leaf in leaves)


# ---- Wokwi ------------------------------------------------------------------


def test_wokwi_projects_shape():
    a = _make("wokwi")
    projects = a.projects()
    assert len(projects) >= 1
    for p in projects:
        assert p.id.isdigit()
        assert "wokwi.com/projects/" in str(p.url)


# ---- Cross-adapter properties ----------------------------------------------


def test_every_adapter_constructs_and_starts_in_mock():
    """Mock mode is the boot-without-keys contract."""
    from app.adapters.registry import ADAPTER_CLASSES

    for name in ADAPTER_CLASSES:
        a = _make(name)
        # OSINT Framework / Wokwi / MarineCadastre / Kaggle have no creds
        # and report themselves as "configured" (or fall back to True for
        # MarineCadastre). The rest must be mock when keys are absent.
        if name in {"osintframework", "wokwi", "marinecadastre"}:
            assert a.mode == "real"  # no creds needed; counts as configured
        else:
            assert a.mode == "mock", f"{name} should be mock without creds"


def test_every_adapter_name_matches_rate_limit_or_skips():
    """Adapter names that appear in SOURCE_LIMITS must match exactly.
    Adapters without a rate-limit policy (MarineCadastre, Kaggle, OSINT
    Framework, Wokwi) explicitly override ``acquire`` to bypass."""
    from app.adapters.registry import ADAPTER_CLASSES
    from app.core.rate_limit import SOURCE_LIMITS

    bucketed = {"shodan", "exa", "aishub", "barentswatch", "fr24"}
    bypassers = set(ADAPTER_CLASSES) - bucketed

    for name in bucketed:
        assert name in SOURCE_LIMITS, f"{name} must have a rate-limit policy"

    for name in bypassers:
        a = _make(name)
        ok, retry = a.acquire()
        # Bypass means always-allow + zero retry.
        assert ok is True
        assert retry == 0.0
