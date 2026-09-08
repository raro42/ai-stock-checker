"""Promote A/B window glance (display only)."""

from __future__ import annotations

from datetime import date

from openbb_backend.desk import build_promote_ab_glance
from stock_checker.promote_ab import promote_ab_snapshot, weekday_trading_days


def test_weekday_trading_days_inclusive() -> None:
    # Wed Aug 12 → Fri Aug 14 = 3 weekdays
    assert weekday_trading_days(date(2026, 8, 12), date(2026, 8, 14)) == 3
    # Weekend alone
    assert weekday_trading_days(date(2026, 8, 15), date(2026, 8, 16)) == 0


def test_promote_ab_snapshot_window_a_target_met() -> None:
    snap = promote_ab_snapshot(False, as_of=date(2026, 9, 9))
    assert snap["window"] == "A"
    assert snap["promote_on"] is False
    assert snap["protocol_ok"] is True
    assert snap["target_met"] is True
    assert snap["trading_days"] >= 10


def test_promote_ab_glance_empty() -> None:
    assert build_promote_ab_glance(None)["ready"] is False


def test_promote_ab_glance_running() -> None:
    g = build_promote_ab_glance(
        {"promote_experiment_strategy": False},
        as_of=date(2026, 8, 18),
    )
    assert g["ready"] is True
    assert g["tone"] == "progress"
    assert g["window"] == "A"
    assert g["protocol_ok"] is True
    assert "running" in g["line"]
    assert "promote off" in g["line"]


def test_promote_ab_glance_target_met() -> None:
    g = build_promote_ab_glance(
        {"promote_experiment_strategy": False},
        as_of=date(2026, 9, 9),
    )
    assert g["ready"] is True
    assert g["tone"] == "ready"
    assert g["target_met"] is True
    assert "summarize before B" in g["line"]


def test_promote_ab_glance_protocol_break() -> None:
    g = build_promote_ab_glance(
        {"promote_experiment_strategy": True},
        as_of=date(2026, 9, 9),
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["protocol_ok"] is False
    assert "should be OFF" in g["line"]
