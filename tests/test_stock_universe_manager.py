"""Offline tests for curated universe seed merge."""

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

