"""Ops audit refuse window / retention / age bands must refuse bool invents."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from stock_checker.ops_audit import (
    OPS_ACTIONS_CAP,
    OPS_OUTCOME_AGING_HOURS,
    OPS_OUTCOME_FRESH_HOURS,
    OPS_PENDING_REFUSE_SECONDS,
    _coerce_ops_actions_cap,
    _coerce_ops_outcome_hours,
    _coerce_ops_refuse_seconds,
    append_ops_action,
    load_ops_actions,
    ops_outcome_age_band,
    ops_pending_freshness_band,
)


def test_coerce_ops_refuse_seconds_refuses_bool() -> None:
    """True→1s must not invent a thin double-click refuse window."""
    assert (
        _coerce_ops_refuse_seconds(True) == OPS_PENDING_REFUSE_SECONDS
    )
    assert (
        _coerce_ops_refuse_seconds(False) == OPS_PENDING_REFUSE_SECONDS
    )
    assert _coerce_ops_refuse_seconds(0) == OPS_PENDING_REFUSE_SECONDS
    assert _coerce_ops_refuse_seconds(30) == 30


def test_coerce_ops_actions_cap_refuses_bool() -> None:
    """True→1 must not invent a one-row Ops audit ring."""
    assert _coerce_ops_actions_cap(True) == OPS_ACTIONS_CAP
    assert _coerce_ops_actions_cap(False) == OPS_ACTIONS_CAP
    assert _coerce_ops_actions_cap(5) == 5
    assert _coerce_ops_actions_cap(0) == 0


def test_coerce_ops_outcome_hours_refuses_bool() -> None:
    """True→1h must not invent a thin audit age band."""
    assert (
        _coerce_ops_outcome_hours(True, OPS_OUTCOME_FRESH_HOURS)
        == OPS_OUTCOME_FRESH_HOURS
    )
    assert (
        _coerce_ops_outcome_hours(False, OPS_OUTCOME_AGING_HOURS)
        == OPS_OUTCOME_AGING_HOURS
    )
    assert _coerce_ops_outcome_hours(-3.0, 24.0) == 24.0
    assert _coerce_ops_outcome_hours(6.0, 24.0) == 6.0


def test_ops_pending_freshness_refuses_bool_window() -> None:
    """Bool refuse_seconds falls back to 120s (not True→1s)."""
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    stamp = (now - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = {"outcome": "requested", "at": stamp}
    # Without refuse, True→1 would mark 30s as stale.
    assert (
        ops_pending_freshness_band(row, now=now, refuse_seconds=True) == "fresh"
    )
    assert (
        ops_pending_freshness_band(row, now=now, refuse_seconds=False) == "fresh"
    )


def test_ops_outcome_age_refuses_bool_hours() -> None:
    """Bool fresh/aging knobs fall back to 24h/7d (not True→1h)."""
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = {"at": aging}
    assert (
        ops_outcome_age_band(row, now=now, fresh_hours=True, aging_hours=True)
        == "aging"
    )


def test_append_ops_action_refuses_bool_cap(tmp_path: Path) -> None:
    """True→1 must not shrink the Ops audit ring to a single row."""
    for i in range(5):
        assert append_ops_action(
            tmp_path,
            {
                "at": f"2026-11-20T12:0{i}:00Z",
                "kind": "save",
                "outcome": "accepted",
                "id": f"r{i}",
            },
            cap=True,
        )
    # Without refuse, int(True)→1 would keep only the newest event.
    assert len(load_ops_actions(tmp_path)) == 5

    for i in range(3):
        assert append_ops_action(
            tmp_path,
            {
                "at": f"2026-11-20T13:0{i}:00Z",
                "kind": "save",
                "outcome": "accepted",
                "id": f"f{i}",
            },
            cap=False,
        )
    # False→0 via int() then max(1,0)→1 would also invent a 1-row ring.
    assert len(load_ops_actions(tmp_path)) == 8

    for i, letter in enumerate("abc"):
        assert append_ops_action(
            tmp_path,
            {
                "at": f"2026-11-20T14:0{i}:00Z",
                "kind": "save",
                "outcome": "accepted",
                "id": letter,
            },
            cap=2,
        )
    assert len(load_ops_actions(tmp_path)) == 2
