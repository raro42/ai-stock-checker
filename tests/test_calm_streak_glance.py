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
    assert g["window_a_fee_net_bit"] == ""
    assert g["window_a_fee_mood_bit"] == ""
    assert g["window_a_fee_drag"] is False
    assert g["window_a_fee_drag_severity"] == ""
    assert g["window_a_closes_polarity_bit"] == ""
    assert g["window_a_closes_polarity"] == ""
    assert g["window_a_closes_all_loss"] is False
    assert "0/30" in g["line"]
    assert "promote off · streak paused" in g["line"]
    assert f"A {a_days}/{WINDOW_A_TARGET_TRADING_DAYS}d" in g["line"]
    assert "fills" not in g["line"]
    assert "fees" not in g["line"]
    assert "drag" not in g["line"]
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
    assert g["window_a_sample_status"] == "building sample"
    assert g["window_a_fee_net_bit"] == "€5 fees · −€3 net"
    assert g["window_a_fee_mood_bit"] == "drag heavy"
    assert g["window_a_fee_drag"] is True
    assert g["window_a_fee_drag_severity"] == "heavy"
    assert g["window_a_closes_polarity_bit"] == ""  # no wins/losses → silent
    assert g["window_a_closes_payoff_bit"] == ""  # no avgs → silent
    assert g["tone"] == "warn"  # day floor met + thin sample / fee drag
    assert f"A {a_days}/{WINDOW_A_TARGET_TRADING_DAYS}" in g["line"]
    assert "building sample" in g["line"]
    assert "€5" in g["line"]
    assert "−€3" in g["line"]
    assert "drag heavy" in g["line"]
    # Mood + compact € before meters — clip may drop fill counts.
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_sample_ready() -> None:
    """Fill/sell meters alone must not hide that the sample floors are met."""
    as_of = date(2026, 8, 18)  # days still short
    a_days = weekday_trading_days(date(2026, 8, 12), as_of)
    assert a_days < WINDOW_A_TARGET_TRADING_DAYS
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 8.0,
        "realized_pnl": 20.0,
        "net_after_all_fees": 12.0,
        "wins": 3,
        "losses": 2,
        "avg_win": 8.0,
        "avg_loss": 4.0,
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
    assert g["window_a_sample_status"] == "sample ready"
    assert g["window_a_fee_net_bit"] == "€8 fees · +€12 net"
    assert g["window_a_fee_mood_bit"] == "fees ok"
    assert g["window_a_fee_drag"] is False
    assert g["window_a_fees_ok_severity"] == "ok"
    assert g["window_a_fees_thin"] is False
    assert g["window_a_closes_polarity_bit"] == "3w/2l"
    assert g["window_a_closes_polarity"] == "mixed"
    assert g["window_a_closes_loss_lean"] is False
    assert g["window_a_closes_payoff_bit"] == "pay strong · 2×"
    assert g["window_a_closes_payoff_severity"] == "strong"
    assert g["window_a_closes_payoff_thin"] is False
    assert g["window_a_closes_payoff_ratio"] == 2.0
    assert g["tone"] == "paused"  # days short — not warn
    # sample ready stays in fields; dropped from line when payoff spoke
    assert g["window_a_sample_status"] == "sample ready"
    assert "sample ready" not in g["line"]
    assert "€8" in g["line"]
    assert "+€12" in g["line"]
    assert "fees ok" in g["line"]
    assert "3w/2l" in g["line"]
    assert "pay strong · 2×" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_building_closes() -> None:
    """Fills ok but sparse sells → building closes (not bare meters)."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 11,
        "sells": 1,
        "fees": 8.0,
        "realized_pnl": 2.0,
        "net_after_all_fees": -6.0,
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
    assert g["window_a_sample_status"] == "building closes"
    assert g["window_a_fee_net_bit"] == "€8 fees · −€6 net"
    assert g["window_a_fee_mood_bit"] == "drag heavy"
    assert g["window_a_fee_drag"] is True
    assert g["window_a_fee_drag_severity"] == "heavy"
    assert g["tone"] == "warn"  # fee drag escalates even when days short
    assert "building closes" in g["line"]
    assert "€8" in g["line"]
    assert "drag heavy" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_fee_net() -> None:
    """Sample status alone must not hide fee-adjusted Window A net."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 15.0,
        "realized_pnl": 10.0,
        "net_after_all_fees": -5.0,
        "wins": 2,
        "losses": 3,
        "avg_win": 8.0,
        "avg_loss": 4.0,
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
    assert g["window_a_sample_status"] == "sample ready"
    assert g["window_a_fee_net_bit"] == "€15 fees · −€5 net"
    assert g["window_a_fee_mood_bit"] == "drag mild"
    assert g["window_a_fee_drag"] is True
    assert g["window_a_fee_drag_severity"] == "mild"
    assert g["window_a_closes_polarity_bit"] == "2w/3l"
    assert g["window_a_closes_polarity"] == "mixed"
    assert g["window_a_closes_loss_lean"] is True
    assert g["window_a_closes_payoff_bit"] == "pay strong · 2×"
    assert g["window_a_closes_payoff_severity"] == "strong"
    assert g["tone"] == "warn"
    assert g["window_a_sample_status"] == "sample ready"
    assert "sample ready" not in g["line"]
    assert "€15" in g["line"]
    assert "−€5" in g["line"]
    assert "drag mild" in g["line"]
    assert "2w/3l" in g["line"]
    assert "pay strong · 2×" in g["line"]
    # Mood + compact € + polarity + payoff before meters.
    mood_pos = g["line"].find("drag mild")
    fee_pos = g["line"].find("€15")
    pol_pos = g["line"].find("2w/3l")
    pay_pos = g["line"].find("pay strong")
    fill_pos = g["line"].find("fills")
    assert mood_pos > 0
    assert fee_pos > mood_pos
    assert pol_pos > fee_pos
    assert pay_pos > pol_pos
    if fill_pos > 0:
        assert fee_pos < fill_pos
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_fee_mood_comfortable() -> None:
    """€/net alone must not hide comfortable fee mood (speak-both-sides)."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 2.0,
        "realized_pnl": 20.0,
        "net_after_all_fees": 18.0,
        "wins": 4,
        "losses": 1,
        "avg_win": 6.0,
        "avg_loss": 4.0,
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
    assert g["window_a_fee_net_bit"] == "€2 fees · +€18 net"
    # Line uses "fees calm" (clip); field keeps the band token.
    assert g["window_a_fee_mood_bit"] == "fees calm"
    assert g["window_a_fees_ok_severity"] == "comfortable"
    assert g["window_a_fee_drag"] is False
    assert g["window_a_closes_polarity_bit"] == "4w/1l"
    assert g["window_a_closes_polarity"] == "mixed"
    assert g["window_a_closes_payoff_bit"] == "pay · 1.5×"
    assert g["window_a_closes_payoff_severity"] == ""
    assert g["window_a_closes_payoff_thin"] is False
    assert g["tone"] == "paused"
    assert "fees calm" in g["line"]
    assert "4w/1l" in g["line"]
    assert "pay · 1.5×" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_payoff_thin() -> None:
    """Nw/Nl alone must not hide thin € payoff (count lean ≠ € lean)."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 8,
        "sells": 4,
        "fees": 5.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 35.0,
        "wins": 3,
        "losses": 1,
        "avg_win": 20.0,
        "avg_loss": 40.0,
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
    assert g["window_a_closes_polarity_bit"] == "3w/1l"
    assert g["window_a_closes_polarity"] == "mixed"
    # Count lean mostly wins but € payoff thin.
    assert g["window_a_closes_payoff_bit"] == "pay thin · 0.5×"
    assert g["window_a_closes_payoff_severity"] == "thin"
    assert g["window_a_closes_payoff_thin"] is True
    assert g["window_a_closes_payoff_ratio"] == 0.5
    assert g["tone"] == "warn"
    assert "3w/1l" in g["line"]
    assert "pay thin · 0.5×" in g["line"]
    assert g["line"].find("pay thin") > g["line"].find("3w/1l")
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_polarity_all_loss() -> None:
    """Fee mood alone must not hide an all-loss Window A control book."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 2.0,
        "realized_pnl": 20.0,
        "net_after_all_fees": 18.0,
        "wins": 0,
        "losses": 5,
        "avg_win": 0.0,
        "avg_loss": 4.0,
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
    assert g["window_a_closes_polarity_bit"] == "0w/5l"
    assert g["window_a_closes_polarity"] == "all_loss"
    assert g["window_a_closes_all_loss"] is True
    # all_loss → payoff fail-open (needs both sides with positive avgs)
    assert g["window_a_closes_payoff_bit"] == ""
    assert g["window_a_closes_payoff_thin"] is False
    assert g["tone"] == "warn"  # all-loss escalates even when fees calm
    assert "0w/5l" in g["line"]
    assert "fees calm" in g["line"]
    assert "sample ready" in g["line"]  # no payoff → status stays on line
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
