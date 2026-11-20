"""Universe scan batch / discovery knobs must refuse bool invents."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from stock_checker.stock_universe_manager import (
    DEFAULT_SCAN_BATCH_LIMIT,
    DEFAULT_SCAN_MAX_AGE_HOURS,
    DEFAULT_YAHOO_MAX_NEW,
    StockUniverseManager,
    _coerce_scan_batch_limit,
    _coerce_scan_max_age_hours,
    _coerce_yahoo_max_new,
)
from stock_checker.yahoo_universe_discovery import (
    DEFAULT_MOVER_COUNT,
    DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS,
)


def test_coerce_scan_batch_limit_refuses_bool() -> None:
    """True→1 must not invent a one-name breakout cycle."""
    assert _coerce_scan_batch_limit(True) == DEFAULT_SCAN_BATCH_LIMIT
    assert _coerce_scan_batch_limit(False) == DEFAULT_SCAN_BATCH_LIMIT
    assert _coerce_scan_batch_limit(0) == DEFAULT_SCAN_BATCH_LIMIT
    assert _coerce_scan_batch_limit(12) == 12


def test_coerce_scan_max_age_hours_refuses_bool() -> None:
    """True→1h must not invent a thin re-scan band."""
    assert _coerce_scan_max_age_hours(True) == DEFAULT_SCAN_MAX_AGE_HOURS
    assert _coerce_scan_max_age_hours(False) == DEFAULT_SCAN_MAX_AGE_HOURS
    assert _coerce_scan_max_age_hours(0) == DEFAULT_SCAN_MAX_AGE_HOURS
    assert _coerce_scan_max_age_hours(48) == 48


def test_coerce_yahoo_max_new_refuses_bool() -> None:
    """True→1 must not invent a one-name universe grow."""
    assert _coerce_yahoo_max_new(True) == DEFAULT_YAHOO_MAX_NEW
    assert _coerce_yahoo_max_new(False) == DEFAULT_YAHOO_MAX_NEW
    assert _coerce_yahoo_max_new(0) == DEFAULT_YAHOO_MAX_NEW
    assert _coerce_yahoo_max_new(7) == 7


def test_get_stocks_to_scan_refuses_bool_limit(tmp_path) -> None:
    """Bool limit falls back to 30 (not True→1 name batch)."""
    mgr = StockUniverseManager(data_dir=str(tmp_path))
    # Minimal universe so batch size is observable.
    mgr.universe["stocks"] = {
        f"S{i}": {"sector": "test", "exchange": "US"} for i in range(10)
    }
    mgr.scan_history["scanned"] = {}
    batch, _ = mgr.get_stocks_to_scan(limit=True, max_age_hours=False)
    assert len(batch) == min(10, DEFAULT_SCAN_BATCH_LIMIT)
    batch2, _ = mgr.get_stocks_to_scan(limit=3, max_age_hours=24)
    assert len(batch2) == 3


def test_yahoo_discovery_due_manager_refuses_bool_max_age(tmp_path) -> None:
    """Manager must not pre-int(True)→1 past due_from_meta refuse."""
    mgr = StockUniverseManager(data_dir=str(tmp_path))
    now = datetime.now(timezone.utc)
    stamp = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    mgr.universe.setdefault("meta", {})
    mgr.universe["meta"]["last_yahoo_discovery"] = stamp
    mgr.universe["meta"]["last_yahoo_discovery_status"] = "ok"
    # Without refuse, True→1h would mark a 2h-old success as due.
    assert mgr.yahoo_discovery_due(max_age_hours=True) is False
    assert mgr.yahoo_discovery_due(max_age_hours=False) is False
    assert mgr.yahoo_discovery_due(max_age_hours=1) is True
    assert (
        mgr.yahoo_discovery_due(max_age_hours=DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS)
        is False
    )


def test_discover_yahoo_movers_refuses_bool_per_screen_cap(
    tmp_path, monkeypatch
) -> None:
    """Bool per_screen/max_new fall back before dispatch (not True→1)."""
    mgr = StockUniverseManager(data_dir=str(tmp_path))
    captured: dict[str, object] = {}

    def _fake_report(*, per_screen=25):
        captured["per_screen"] = per_screen
        return ([], 0, 3, 0, 0, 0, 0, 0, 0)

    monkeypatch.setattr(
        "stock_checker.yahoo_universe_discovery.discover_yahoo_mover_report",
        _fake_report,
    )
    monkeypatch.setattr(
        mgr,
        "yahoo_discovery_due",
        lambda **_kw: True,
    )
    # Empty/fail bundle returns 0 adds — still proves coerce at the call site.
    assert mgr.discover_yahoo_movers(per_screen=True, max_new=False) == 0
    assert captured["per_screen"] == DEFAULT_MOVER_COUNT
