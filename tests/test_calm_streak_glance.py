"""Paper-calm streak glance (display only)."""

from __future__ import annotations

from datetime import date

from openbb_backend.desk import (
    _calm_detail_is_promote_off_pause,
    build_calm_streak_glance,
)
from stock_checker.promote_ab import (
    WINDOW_A_TARGET_FILLS,
    WINDOW_A_TARGET_SELLS,
    WINDOW_A_TARGET_TRADING_DAYS,
    weekday_trading_days,
)


def test_calm_streak_glance_empty() -> None:
    assert build_calm_streak_glance(None)["ready"] is False
    assert build_calm_streak_glance({})["ready"] is False


def test_calm_detail_is_promote_off_pause() -> None:
    assert _calm_detail_is_promote_off_pause(
        "promote filter off — streak paused"
    )
    assert _calm_detail_is_promote_off_pause("Promote filter off")
    assert not _calm_detail_is_promote_off_pause("book overweight")
    assert not _calm_detail_is_promote_off_pause("")


def test_calm_streak_glance_blocked() -> None:
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "book overweight",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "blocked"
    assert g["promote_off_paused"] is False
    assert g["window_a_days"] is None
    assert g["window_a_fills"] is None
    assert g["streak"] == 0
    assert g["required"] == 30
    assert "0/30" in g["line"]
    assert "streak not started" in g["line"]
    assert "book overweight" in g["line"]


def test_calm_streak_glance_promote_off_paused() -> None:
    """Window A: promote off is intentional — not 'streak not started' failure."""
    as_of = date(2026, 8, 18)  # Window A running; day target not yet met
    a_days = weekday_trading_days(date(2026, 8, 12), as_of)
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
    )
    assert g["ready"] is True
    assert g["tone"] == "paused"
    assert g["promote_off_paused"] is True
    assert g["window_a_days"] == a_days
    assert g["window_a_target_days"] == WINDOW_A_TARGET_TRADING_DAYS
    assert g["window_a_fills"] is None  # no stats → fail-open silent
    assert "0/30" in g["line"]
    assert "promote off · streak paused" in g["line"]
    assert f"A {a_days}/{WINDOW_A_TARGET_TRADING_DAYS}d" in g["line"]
    assert "fills" not in g["line"]
    assert "streak not started" not in g["line"]
    # Compact status already names the why — do not repeat long detail.
    assert "promote filter off" not in g["line"]


def test_calm_streak_glance_promote_off_paused_window_a_days_ready() -> None:
    """Pause alone must not hide that Window A day floor is already met."""
    as_of = date(2026, 9, 9)
    a_days = weekday_trading_days(date(2026, 8, 12), as_of)
    assert a_days >= WINDOW_A_TARGET_TRADING_DAYS
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
    )
    assert g["promote_off_paused"] is True
    assert g["window_a_days"] == a_days
    assert f"A {a_days}/{WINDOW_A_TARGET_TRADING_DAYS}d" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_sample_meter() -> None:
    """Day meter alone must not hide a thin Window A fill/sell sample."""
    as_of = date(2026, 9, 9)
    a_days = weekday_trading_days(date(2026, 8, 12), as_of)
    assert a_days >= WINDOW_A_TARGET_TRADING_DAYS
    stats = {
        "trades": 4,
        "buys": 3,
        "sells": 1,
        "fees": 5.0,
        "realized_pnl": 2.0,
        "net_after_all_fees": -3.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["promote_off_paused"] is True
    assert g["window_a_days"] == a_days
    assert g["window_a_fills"] == 4
    assert g["window_a_target_fills"] == WINDOW_A_TARGET_FILLS
    assert g["window_a_sells"] == 1
    assert g["window_a_target_sells"] == WINDOW_A_TARGET_SELLS
    assert f"A {a_days}/{WINDOW_A_TARGET_TRADING_DAYS}d" in g["line"]
    assert f"4/{WINDOW_A_TARGET_FILLS} fills" in g["line"]
    assert f"1/{WINDOW_A_TARGET_SELLS} sells" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_progress() -> None:
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 12,
            "calm_required_days": 30,
            "calm_ready": False,
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "progress"
    assert g["calm_ready"] is False
    assert g["promote_off_paused"] is False
    assert g["window_a_days"] is None
    assert g["window_a_fills"] is None
    assert "12/30" in g["line"]
    assert "building" in g["line"]


def test_calm_streak_glance_ready() -> None:
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 30,
            "calm_required_days": 30,
            "calm_ready": True,
            "calm_detail": "should not appear when ready",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "ready"
    assert g["calm_ready"] is True
    assert g["promote_off_paused"] is False
    assert g["window_a_days"] is None
    assert g["window_a_fills"] is None
    assert "compose promote default ready" in g["line"]
    assert "should not appear" not in g["line"]


def test_calm_streak_glance_truncates_line() -> None:
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 1,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "x" * 80,
        }
    )
    assert g["ready"] is True
    assert len(g["line"]) <= 96
