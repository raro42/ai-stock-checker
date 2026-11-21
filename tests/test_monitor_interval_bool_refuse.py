"""ContinuousMonitor check_interval must refuse bool invents."""

from __future__ import annotations

from stock_checker.monitor import (
    DEFAULT_CHECK_INTERVAL_SEC,
    ContinuousMonitor,
    _coerce_check_interval,
)


def test_coerce_check_interval_refuses_bool() -> None:
    assert _coerce_check_interval(True) == DEFAULT_CHECK_INTERVAL_SEC
    assert _coerce_check_interval(False) == DEFAULT_CHECK_INTERVAL_SEC
    assert _coerce_check_interval(0) == DEFAULT_CHECK_INTERVAL_SEC
    assert _coerce_check_interval(None) == DEFAULT_CHECK_INTERVAL_SEC
    assert _coerce_check_interval(120) == 120


def test_continuous_monitor_refuses_bool_interval() -> None:
    m = ContinuousMonitor(watch_list=["AAPL"], check_interval=True)
    assert m.check_interval == DEFAULT_CHECK_INTERVAL_SEC
    m2 = ContinuousMonitor(watch_list=["AAPL"], check_interval=45)
    assert m2.check_interval == 45
