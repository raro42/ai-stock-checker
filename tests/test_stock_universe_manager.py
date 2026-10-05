"""Offline tests for curated universe seed merge."""

from datetime import datetime
from pathlib import Path

from stock_checker.stock_universe_manager import StockUniverseManager


def test_ensure_curated_seed_adds_missing_and_drops_pxd(tmp_path: Path):
    mgr = StockUniverseManager(data_dir=str(tmp_path))
    # Seed already ran on empty; force a thin universe with dead ticker.
    mgr.universe = {
        "last_updated": "",
        "total_stocks": 1,
        "stocks": {
            "PXD": {"sector": "energy", "exchange": "NASDAQ", "added": "x"},
            "AAPL": {"sector": "technology", "exchange": "NASDAQ", "added": "x"},
        },
        "sectors": {"energy": ["PXD"], "technology": ["AAPL"]},
        "exchanges": {"NASDAQ": ["PXD", "AAPL"]},
    }
    mgr._save_universe()
    added = mgr.ensure_curated_seed()
    assert "PXD" not in mgr.universe["stocks"]
    assert "IBM" in mgr.universe["stocks"]
    assert "AAPL" in mgr.universe["stocks"]
    assert "SAP.DE" in mgr.universe["stocks"]
    assert "4GLD.DE" in mgr.universe["stocks"]
    assert "VWCE.DE" in mgr.universe["stocks"]
    assert mgr.universe["stocks"]["4GLD.DE"]["sector"] == "metal"
    assert added >= 1


def test_discover_yahoo_movers_empty_does_not_stamp_cache(tmp_path: Path, monkeypatch):
    mgr = StockUniverseManager(data_dir=str(tmp_path))
    prior = "2026-09-01T00:00:00"
    mgr.universe.setdefault("meta", {})
    mgr.universe["meta"]["last_yahoo_discovery"] = prior
    mgr.universe["meta"]["last_yahoo_added"] = 3
    mgr._save_universe()
    names = list(mgr.universe["stocks"].keys())[:5]

    def empty_report(*, per_screen: int = 25):
        return [], 0, 3

    monkeypatch.setattr(
        "stock_checker.yahoo_universe_discovery.discover_yahoo_mover_report",
        empty_report,
    )
    added = mgr.discover_yahoo_movers()
    assert added == 0
    meta = mgr.universe["meta"]
    assert meta["last_yahoo_discovery"] == prior
    assert meta["last_yahoo_discovery_status"] == "failed"
    assert meta["last_yahoo_added"] == 3
    assert "last_yahoo_discovery_fail" in meta
    for n in names:
        assert n in mgr.universe["stocks"]
    assert meta.get("last_yahoo_screens_ok") == 0
    assert meta.get("last_yahoo_screens_failed") == 3


def test_discover_yahoo_movers_majority_fail_discards_leftovers(
    tmp_path: Path, monkeypatch
):
    mgr = StockUniverseManager(data_dir=str(tmp_path))
    prior = "2026-09-01T00:00:00"
    mgr.universe.setdefault("meta", {})
    mgr.universe["meta"]["last_yahoo_discovery"] = prior
    mgr.universe["meta"]["last_yahoo_added"] = 3
    mgr._save_universe()

    def thin_report(*, per_screen: int = 25):
        return ["ZZZZFAKE"], 1, 2

    monkeypatch.setattr(
        "stock_checker.yahoo_universe_discovery.discover_yahoo_mover_report",
        thin_report,
    )
    added = mgr.discover_yahoo_movers()
    assert added == 0
    meta = mgr.universe["meta"]
    assert meta["last_yahoo_discovery"] == prior
    assert meta["last_yahoo_discovery_status"] == "failed"
    assert "ZZZZFAKE" not in mgr.universe["stocks"]
    assert meta["last_yahoo_screens_ok"] == 1
    assert meta["last_yahoo_screens_failed"] == 2


def test_discover_yahoo_movers_403_does_not_raise(tmp_path: Path, monkeypatch):
    mgr = StockUniverseManager(data_dir=str(tmp_path))
    prior = "2026-09-01T00:00:00"
    mgr.universe.setdefault("meta", {})
    mgr.universe["meta"]["last_yahoo_discovery"] = prior
    mgr._save_universe()

    def boom(*, per_screen: int = 25):
        raise RuntimeError("HTTP Error 403: Forbidden")

    monkeypatch.setattr(
        "stock_checker.yahoo_universe_discovery.discover_yahoo_mover_report",
        boom,
    )
    added = mgr.discover_yahoo_movers()
    assert added == 0
    assert mgr.universe["meta"]["last_yahoo_discovery"] == prior
    assert mgr.universe["meta"]["last_yahoo_discovery_status"] == "failed"


def test_yahoo_discovery_due_failed_skips_success_age_throttle(tmp_path: Path):
    mgr = StockUniverseManager(data_dir=str(tmp_path))
    mgr.universe.setdefault("meta", {})
    mgr.universe["meta"]["last_yahoo_discovery"] = datetime.now().isoformat()
    mgr.universe["meta"]["last_yahoo_discovery_status"] = "ok"
    assert mgr.yahoo_discovery_due(max_age_hours=24) is False
    # Failed without fail stamp → retry immediately.
    mgr.universe["meta"]["last_yahoo_discovery_status"] = "failed"
    assert mgr.yahoo_discovery_due(max_age_hours=24) is True
    # Fresh fail stamp → cool down inside 1h backoff.
    mgr.universe["meta"]["last_yahoo_discovery_fail"] = datetime.now().isoformat()
    assert mgr.yahoo_discovery_due(max_age_hours=24) is False

