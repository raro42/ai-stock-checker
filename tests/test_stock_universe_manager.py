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
    assert added >= 1
