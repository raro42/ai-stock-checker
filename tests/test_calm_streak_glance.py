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
    assert g["window_a_closes_expectancy_bit"] == ""
    assert g["window_a_closes_expectancy"] is None
    assert g["window_a_closes_expectancy_neg"] is False
    assert g["window_a_closes_profit_factor_bit"] == ""
    assert g["window_a_closes_profit_factor"] is None
    assert g["window_a_closes_profit_factor_thin"] is False
    assert g["window_a_closes_win_rate_bit"] == ""
    assert g["window_a_closes_win_rate_pct"] is None
    assert g["window_a_closes_win_rate_thin"] is False
    assert g["window_a_closes_wr_vs_be_bit"] == ""
    assert g["window_a_closes_wr_vs_be"] == ""
    assert g["window_a_closes_wr_edge_pp"] is None
    assert g["window_a_closes_wr_edge_thin"] is False
    assert g["window_a_closes_wr_below_be"] is False
    assert g["window_a_closes_net_expectancy_bit"] == ""
    assert g["window_a_closes_net_expectancy"] is None
    assert g["window_a_closes_net_expectancy_neg"] is False
    assert g["window_a_closes_net_expectancy_thin"] is False
    assert g["window_a_closes_net_expectancy_eats_edge"] is False
    assert g["window_a_closes_fee_take_bit"] == ""
    assert g["window_a_closes_fee_take"] is None
    assert g["window_a_closes_fee_take_thin"] is False
    assert g["window_a_closes_fee_take_severity"] == ""
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
    assert g["window_a_closes_expectancy_bit"] == ""  # no avgs → silent
    assert g["window_a_closes_profit_factor_bit"] == ""  # no both sides → silent
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
    # 0.6·8 − 0.4·4 = 3.2 → strong vs avg_loss
    assert g["window_a_closes_expectancy_bit"] == "exp strong · +€3"
    assert g["window_a_closes_expectancy"] == 3.2
    assert g["window_a_closes_expectancy_severity"] == "strong"
    assert g["window_a_closes_expectancy_thin"] is False
    assert g["window_a_closes_expectancy_neg"] is False
    # gross 24÷8 = 3× → strong PF (expectancy €/close ≠ total €)
    assert g["window_a_closes_profit_factor_bit"] == "PF strong · 3×"
    assert g["window_a_closes_profit_factor"] == 3.0
    assert g["window_a_closes_profit_factor_severity"] == "strong"
    assert g["window_a_closes_profit_factor_thin"] is False
    # 3/5 = 60% → strong WR (PF ≠ hit rate)
    assert g["window_a_closes_win_rate_bit"] == "WR strong · 60%"
    assert g["window_a_closes_win_rate_pct"] == 60.0
    assert g["window_a_closes_win_rate_severity"] == "strong"
    assert g["window_a_closes_win_rate_thin"] is False
    # BE = 100/(1+2) = 33.3%; cushion +26.7pp → above strong
    assert g["window_a_closes_wr_vs_be_bit"] == "WR above BE strong · +26.7pp"
    assert g["window_a_closes_wr_vs_be"] == "above"
    assert g["window_a_closes_breakeven_wr_pct"] == 33.3
    assert g["window_a_closes_wr_edge_pp"] == 26.7
    assert g["window_a_closes_wr_edge_severity"] == "strong"
    assert g["window_a_closes_wr_edge_thin"] is False
    assert g["window_a_closes_wr_below_be"] is False
    # net 12÷5 = 2.4 → strong vs avg_loss (gross exp ≠ fee-adjusted)
    assert g["window_a_closes_net_expectancy_bit"] == "net exp strong · +€2"
    assert g["window_a_closes_net_expectancy"] == 2.4
    assert g["window_a_closes_net_expectancy_severity"] == "strong"
    assert g["window_a_closes_net_expectancy_thin"] is False
    assert g["window_a_closes_net_expectancy_neg"] is False
    assert g["window_a_closes_net_expectancy_eats_edge"] is False
    # take 3.2−2.4 = 0.8 → mid · €1 (0.25 ratio; net ≠ fee take)
    assert g["window_a_closes_fee_take_bit"] == "fee take · €1"
    assert g["window_a_closes_fee_take"] == 0.8
    assert g["window_a_closes_fee_take_ratio"] == 0.25
    assert g["window_a_closes_fee_take_thin"] is False
    assert g["window_a_closes_fee_take_severity"] == ""
    assert g["tone"] == "paused"  # days short — not warn
    # sample ready + payoff + exp + PF + WR% + WR/BE + net stay in fields;
    # fee take owns clip
    assert g["window_a_sample_status"] == "sample ready"
    assert "sample ready" not in g["line"]
    assert "pay strong" not in g["line"]
    assert "€8" in g["line"]
    assert "+€12" in g["line"]
    assert "fees ok" in g["line"]
    assert "3w/2l" not in g["line"]  # polarity stays in fields
    assert f" · {g['window_a_closes_expectancy_bit']}" not in g["line"]
    assert "PF strong" not in g["line"]  # PF stays in fields
    assert "WR strong · 60%" not in g["line"]  # WR% stays in fields
    assert "WR above BE strong" not in g["line"]  # WR/BE stays in fields
    assert "net exp strong" not in g["line"]  # net stays in fields
    assert "fee take · €1" in g["line"]
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
    # 0.4·8 − 0.6·4 = 0.8 → thin vs avg_loss (payoff strong ≠ €/close strong)
    assert g["window_a_closes_expectancy_bit"] == "exp thin · +€1"
    assert g["window_a_closes_expectancy"] == 0.8
    assert g["window_a_closes_expectancy_thin"] is True
    # gross 16÷12 ≈ 1.3× mid PF
    assert g["window_a_closes_profit_factor_bit"] == "PF · 1.3×"
    assert g["window_a_closes_profit_factor"] == 1.33
    assert g["window_a_closes_profit_factor_thin"] is False
    # 2/5 = 40% → mid WR (not thin); BE 33.3% → above mid +6.7pp
    assert g["window_a_closes_win_rate_bit"] == "WR · 40%"
    assert g["window_a_closes_win_rate_pct"] == 40.0
    assert g["window_a_closes_win_rate_thin"] is False
    assert g["window_a_closes_wr_vs_be_bit"] == "WR above BE · +6.7pp"
    assert g["window_a_closes_wr_vs_be"] == "above"
    assert g["window_a_closes_wr_edge_pp"] == 6.7
    assert g["window_a_closes_wr_edge_thin"] is False
    # net −5÷5 = −1; gross exp +0.8 → fees eat edge
    assert g["window_a_closes_net_expectancy_bit"] == "net exp −€1 · fees eat"
    assert g["window_a_closes_net_expectancy"] == -1.0
    assert g["window_a_closes_net_expectancy_neg"] is True
    assert g["window_a_closes_net_expectancy_eats_edge"] is True
    # take 0.8−(−1) = 1.8 → thin · €2 (1.8/0.8 ≥ 0.5; net ≠ fee take)
    assert g["window_a_closes_fee_take_bit"] == "fee take thin · €2"
    assert g["window_a_closes_fee_take"] == 1.8
    assert g["window_a_closes_fee_take_thin"] is True
    assert g["window_a_closes_fee_take_severity"] == "thin"
    assert g["tone"] == "warn"
    assert g["window_a_sample_status"] == "sample ready"
    assert "sample ready" not in g["line"]
    assert "drag mild" in g["line"]
    # Compact € dropped when fees eat so the adverse take bit fits.
    assert "€15" not in g["line"]
    assert "2w/3l" not in g["line"]  # polarity stays in fields
    assert "pay strong" not in g["line"]
    assert f" · {g['window_a_closes_expectancy_bit']}" not in g["line"]
    assert "PF ·" not in g["line"]
    assert "WR · 40%" not in g["line"]  # WR% stays in fields
    assert "WR above BE · +6.7pp" not in g["line"]  # WR/BE stays in fields
    assert "net exp −€1" not in g["line"]  # net stays in fields
    assert "fees eat" not in g["line"]
    assert "fee take thin · €2" in g["line"]
    # Mood + fee take before meters.
    mood_pos = g["line"].find("drag mild")
    take_pos = g["line"].find("fee take")
    fill_pos = g["line"].find("fills")
    assert mood_pos > 0
    assert take_pos > mood_pos
    if fill_pos > 0:
        assert take_pos < fill_pos
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
    # 0.8·6 − 0.2·4 = 4.0 → strong vs avg_loss
    assert g["window_a_closes_expectancy_bit"] == "exp strong · +€4"
    assert g["window_a_closes_expectancy"] == 4.0
    assert g["window_a_closes_expectancy_severity"] == "strong"
    # gross 24÷4 = 6× → strong PF
    assert g["window_a_closes_profit_factor_bit"] == "PF strong · 6×"
    assert g["window_a_closes_profit_factor"] == 6.0
    assert g["window_a_closes_profit_factor_severity"] == "strong"
    # 4/5 = 80% → strong WR; BE 40% → above strong +40pp
    assert g["window_a_closes_win_rate_bit"] == "WR strong · 80%"
    assert g["window_a_closes_win_rate_pct"] == 80.0
    assert g["window_a_closes_win_rate_severity"] == "strong"
    assert g["window_a_closes_wr_vs_be_bit"] == "WR above BE strong · +40pp"
    assert g["window_a_closes_wr_vs_be"] == "above"
    assert g["window_a_closes_breakeven_wr_pct"] == 40.0
    assert g["window_a_closes_wr_edge_pp"] == 40.0
    assert g["window_a_closes_wr_edge_severity"] == "strong"
    # net 18÷5 = 3.6 → strong vs avg_loss
    assert g["window_a_closes_net_expectancy_bit"] == "net exp strong · +€4"
    assert g["window_a_closes_net_expectancy"] == 3.6
    assert g["window_a_closes_net_expectancy_severity"] == "strong"
    assert g["window_a_closes_net_expectancy_neg"] is False
    # take 4.0−3.6 = 0.4 → calm · €0 (0.1 < comfortable; clip rounds €)
    assert g["window_a_closes_fee_take_bit"] == "fee take calm · €0"
    assert g["window_a_closes_fee_take"] == 0.4
    assert g["window_a_closes_fee_take_severity"] == "comfortable"
    assert g["window_a_closes_fee_take_thin"] is False
    assert g["window_a_closes_fee_take_ratio"] == 0.1
    assert g["tone"] == "paused"
    assert "fees calm" in g["line"]
    assert "4w/1l" not in g["line"]  # polarity stays in fields
    assert "pay · 1.5×" not in g["line"]
    assert f" · {g['window_a_closes_expectancy_bit']}" not in g["line"]
    assert "PF strong" not in g["line"]
    assert "WR strong · 80%" not in g["line"]  # WR% stays in fields
    assert "WR above BE strong" not in g["line"]  # WR/BE stays in fields
    assert "net exp strong" not in g["line"]  # net stays in fields
    assert "fee take calm · €0" in g["line"]
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
    # 0.75·20 − 0.25·40 = 5.0 → thin vs avg_loss (5/40 < 0.25)
    assert g["window_a_closes_expectancy_bit"] == "exp thin · +€5"
    assert g["window_a_closes_expectancy"] == 5.0
    assert g["window_a_closes_expectancy_thin"] is True
    # gross 60÷40 = 1.5× mid PF
    assert g["window_a_closes_profit_factor_bit"] == "PF · 1.5×"
    assert g["window_a_closes_profit_factor"] == 1.5
    assert g["window_a_closes_profit_factor_thin"] is False
    # 3/4 = 75% → strong WR; BE 66.7% → above mid +8.3pp
    assert g["window_a_closes_win_rate_bit"] == "WR strong · 75%"
    assert g["window_a_closes_win_rate_pct"] == 75.0
    assert g["window_a_closes_win_rate_severity"] == "strong"
    assert g["window_a_closes_wr_vs_be_bit"] == "WR above BE · +8.3pp"
    assert g["window_a_closes_wr_vs_be"] == "above"
    assert g["window_a_closes_wr_edge_pp"] == 8.3
    # net 35÷4 = 8.75 → thin vs avg_loss 40 (8.75/40 < 0.25)
    assert g["window_a_closes_net_expectancy_bit"] == "net exp thin · +€9"
    assert g["window_a_closes_net_expectancy"] == 8.75
    assert g["window_a_closes_net_expectancy_thin"] is True
    # take 5−8.75 = −3.75 → signed −€4 (net > gross; fee take owns clip)
    assert g["window_a_closes_fee_take_bit"] == "fee take −€4"
    assert g["window_a_closes_fee_take"] == -3.75
    assert g["window_a_closes_fee_take_thin"] is False
    assert g["tone"] == "warn"
    assert "3w/1l" not in g["line"]  # polarity stays in fields
    assert "pay thin" not in g["line"]
    assert f" · {g['window_a_closes_expectancy_bit']}" not in g["line"]
    assert "PF ·" not in g["line"]
    assert "WR strong · 75%" not in g["line"]  # WR% stays in fields
    assert "WR above BE · +8.3pp" not in g["line"]  # WR/BE stays in fields
    assert "net exp thin" not in g["line"]  # net stays in fields
    assert "fee take −€4" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_expectancy_neg() -> None:
    """Payoff alone must not hide negative €/close expectancy."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 2.0,
        "realized_pnl": 20.0,
        "net_after_all_fees": 18.0,
        "wins": 1,
        "losses": 4,
        "avg_win": 10.0,
        "avg_loss": 20.0,
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
    # 0.2·10 − 0.8·20 = −14 → neg (payoff thin 0.5× also)
    assert g["window_a_closes_payoff_bit"] == "pay thin · 0.5×"
    assert g["window_a_closes_expectancy_bit"] == "exp −€14"
    assert g["window_a_closes_expectancy"] == -14.0
    assert g["window_a_closes_expectancy_neg"] is True
    assert g["window_a_closes_expectancy_thin"] is False
    # gross 10÷80 = 0.125 → thin PF
    assert g["window_a_closes_profit_factor_bit"] == "PF thin · 0.1×"
    assert g["window_a_closes_profit_factor"] == 0.12
    assert g["window_a_closes_profit_factor_thin"] is True
    # 1/5 = 20% → thin WR; BE 66.7% → below −46.7pp
    assert g["window_a_closes_win_rate_bit"] == "WR thin · 20%"
    assert g["window_a_closes_win_rate_pct"] == 20.0
    assert g["window_a_closes_win_rate_thin"] is True
    assert g["window_a_closes_wr_vs_be_bit"] == "WR below BE · -46.7pp"
    assert g["window_a_closes_wr_vs_be"] == "below"
    assert g["window_a_closes_wr_edge_pp"] == -46.7
    assert g["window_a_closes_wr_below_be"] is True
    assert g["window_a_closes_wr_edge_thin"] is True
    # net 18÷5 = 3.6 → thin vs avg_loss 20 (gross− / net+ still speaks)
    assert g["window_a_closes_net_expectancy_bit"] == "net exp thin · +€4"
    assert g["window_a_closes_net_expectancy"] == 3.6
    assert g["window_a_closes_net_expectancy_thin"] is True
    # take −14−3.6 = −17.6 → signed −€18 (gross−; fee take owns clip)
    assert g["window_a_closes_fee_take_bit"] == "fee take −€18"
    assert g["window_a_closes_fee_take"] == -17.6
    assert g["window_a_closes_fee_take_thin"] is False
    assert g["tone"] == "warn"
    assert "WR below BE · -46.7pp" not in g["line"]  # WR/BE stays in fields
    assert "WR thin · 20%" not in g["line"]  # WR% stays in fields
    assert "PF thin" not in g["line"]
    assert "exp −€14" not in g["line"]
    assert "pay thin" not in g["line"]
    assert "sample ready" not in g["line"]
    assert "net exp thin" not in g["line"]  # net stays in fields
    assert "fee take −€18" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_profit_factor_thin() -> None:
    """Expectancy alone must not hide thin total-€ profit factor."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 2.0,
        "realized_pnl": 20.0,
        "net_after_all_fees": 18.0,
        "wins": 2,
        "losses": 3,
        "avg_win": 4.0,
        "avg_loss": 10.0,
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
    # payoff 0.4× thin; expectancy 0.4·4−0.6·10 = −4.4 neg
    # gross 8÷30 ≈ 0.27 → thin PF (avg ratio ≠ total € ownership)
    assert g["window_a_closes_payoff_bit"] == "pay thin · 0.4×"
    assert g["window_a_closes_expectancy_neg"] is True
    assert g["window_a_closes_profit_factor_bit"] == "PF thin · 0.3×"
    assert g["window_a_closes_profit_factor"] == 0.27
    assert g["window_a_closes_profit_factor_severity"] == "thin"
    assert g["window_a_closes_profit_factor_thin"] is True
    # 2/5 = 40% → mid WR; BE ≈71.4% → below −31.4pp
    assert g["window_a_closes_win_rate_bit"] == "WR · 40%"
    assert g["window_a_closes_win_rate_pct"] == 40.0
    assert g["window_a_closes_win_rate_thin"] is False
    assert g["window_a_closes_wr_vs_be_bit"] == "WR below BE · -31.4pp"
    assert g["window_a_closes_wr_vs_be"] == "below"
    assert g["window_a_closes_wr_below_be"] is True
    # net 18÷5 = 3.6 → mid vs avg_loss 10 (0.36; not thin <0.25)
    assert g["window_a_closes_net_expectancy_bit"] == "net exp · +€4"
    assert g["window_a_closes_net_expectancy"] == 3.6
    assert g["window_a_closes_net_expectancy_thin"] is False
    # take −4.4−3.6 = −8 → signed −€8 (gross−; fee take owns clip)
    assert g["window_a_closes_fee_take_bit"] == "fee take −€8"
    assert g["window_a_closes_fee_take"] == -8.0
    assert g["window_a_closes_fee_take_thin"] is False
    assert g["tone"] == "warn"
    assert "WR below BE · -31.4pp" not in g["line"]
    assert "WR · 40%" not in g["line"]
    assert "PF thin" not in g["line"]
    assert "exp −" not in g["line"]  # gross expectancy stays in fields
    assert "pay thin" not in g["line"]
    assert "net exp · +€4" not in g["line"]  # net stays in fields
    assert "fee take −€8" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_rate_thin() -> None:
    """PF alone must not hide thin hit rate (total-€ ≠ win%)."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 8,
        "sells": 4,
        "fees": 2.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 38.0,
        "wins": 1,
        "losses": 3,
        "avg_win": 40.0,
        "avg_loss": 5.0,
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
    # payoff 8× strong; PF 40÷15 ≈ 2.7× strong; WR 25% thin
    # but BE ≈11.1% → above strong +13.9pp (hit rate thin ≠ below BE)
    assert g["window_a_closes_payoff_bit"] == "pay strong · 8×"
    assert g["window_a_closes_profit_factor_bit"] == "PF strong · 2.7×"
    assert g["window_a_closes_profit_factor_thin"] is False
    assert g["window_a_closes_win_rate_bit"] == "WR thin · 25%"
    assert g["window_a_closes_win_rate_pct"] == 25.0
    assert g["window_a_closes_win_rate_severity"] == "thin"
    assert g["window_a_closes_win_rate_thin"] is True
    assert g["window_a_closes_wr_vs_be_bit"] == "WR above BE strong · +13.9pp"
    assert g["window_a_closes_wr_vs_be"] == "above"
    assert g["window_a_closes_wr_edge_pp"] == 13.9
    assert g["window_a_closes_wr_edge_severity"] == "strong"
    assert g["window_a_closes_wr_below_be"] is False
    # net 38÷4 = 9.5 → strong vs avg_loss 5
    assert g["window_a_closes_net_expectancy_bit"] == "net exp strong · +€10"
    assert g["window_a_closes_net_expectancy"] == 9.5
    assert g["window_a_closes_net_expectancy_severity"] == "strong"
    # exp = 0.25·40 − 0.75·5 = 6.25; take 6.25−9.5 = −3.25 → −€3
    assert g["window_a_closes_fee_take_bit"] == "fee take −€3"
    assert g["window_a_closes_fee_take"] == -3.25
    assert g["window_a_closes_fee_take_thin"] is False
    assert g["tone"] == "warn"  # thin WR still warns
    assert "WR above BE strong" not in g["line"]  # WR/BE stays in fields
    assert "WR thin · 25%" not in g["line"]  # WR% stays in fields
    assert "PF strong" not in g["line"]
    assert "pay strong" not in g["line"]
    assert "sample ready" not in g["line"]
    assert "net exp strong" not in g["line"]  # net stays in fields
    assert "fee take −€3" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_wr_below_be() -> None:
    """WR% alone must not hide WR below breakeven (payoff-adjusted)."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 2.0,
        "realized_pnl": 20.0,
        "net_after_all_fees": 18.0,
        "wins": 3,
        "losses": 2,
        "avg_win": 2.0,
        "avg_loss": 10.0,
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
    # WR 60% mid/strong band but payoff 0.2× → BE ≈83.3% → below −23.3pp
    assert g["window_a_closes_win_rate_bit"] == "WR strong · 60%"
    assert g["window_a_closes_win_rate_pct"] == 60.0
    assert g["window_a_closes_win_rate_thin"] is False
    assert g["window_a_closes_wr_vs_be_bit"] == "WR below BE · -23.3pp"
    assert g["window_a_closes_wr_vs_be"] == "below"
    assert g["window_a_closes_breakeven_wr_pct"] == 83.3
    assert g["window_a_closes_wr_edge_pp"] == -23.3
    assert g["window_a_closes_wr_below_be"] is True
    assert g["window_a_closes_wr_edge_thin"] is True
    # net 18÷5 = 3.6 → mid vs avg_loss 10 (WR/BE ≠ fee-adjusted €/close)
    assert g["window_a_closes_net_expectancy_bit"] == "net exp · +€4"
    assert g["window_a_closes_net_expectancy"] == 3.6
    assert g["window_a_closes_net_expectancy_thin"] is False
    # exp = 0.6·2 − 0.4·10 = −2.8; take −2.8−3.6 = −6.4 → −€6
    assert g["window_a_closes_fee_take_bit"] == "fee take −€6"
    assert g["window_a_closes_fee_take"] == -6.4
    assert g["window_a_closes_fee_take_thin"] is False
    assert g["tone"] == "warn"
    assert "WR below BE · -23.3pp" not in g["line"]  # WR/BE stays in fields
    assert "WR strong · 60%" not in g["line"]
    assert "pay thin" not in g["line"]
    assert "sample ready" not in g["line"]
    assert "net exp · +€4" not in g["line"]  # net stays in fields
    assert "fee take −€6" in g["line"]
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
    # all_loss → payoff / PF fail-open (needs both sides with positive avgs)
    assert g["window_a_closes_payoff_bit"] == ""
    assert g["window_a_closes_payoff_thin"] is False
    assert g["window_a_closes_profit_factor_bit"] == ""
    assert g["window_a_closes_profit_factor_thin"] is False
    # all-loss → expectancy = −avg_loss; WR 0% thin; no payoff → WR vs BE
    # silent; net 18÷5 = 3.6 → strong owns the clip (gross− ≠ fee-adj net)
    assert g["window_a_closes_expectancy_bit"] == "exp −€4"
    assert g["window_a_closes_expectancy"] == -4.0
    assert g["window_a_closes_expectancy_neg"] is True
    assert g["window_a_closes_win_rate_bit"] == "WR thin · 0%"
    assert g["window_a_closes_win_rate_pct"] == 0.0
    assert g["window_a_closes_win_rate_thin"] is True
    assert g["window_a_closes_wr_vs_be_bit"] == ""
    assert g["window_a_closes_wr_vs_be"] == ""
    assert g["window_a_closes_wr_below_be"] is False
    assert g["window_a_closes_net_expectancy_bit"] == "net exp strong · +€4"
    assert g["window_a_closes_net_expectancy"] == 3.6
    assert g["window_a_closes_net_expectancy_severity"] == "strong"
    # take −4−3.6 = −7.6 → signed −€8 (gross−; fee take owns clip)
    assert g["window_a_closes_fee_take_bit"] == "fee take −€8"
    assert g["window_a_closes_fee_take"] == -7.6
    assert g["window_a_closes_fee_take_thin"] is False
    assert g["tone"] == "warn"  # all-loss / thin WR escalate
    assert "0w/5l" not in g["line"]  # polarity stays in fields
    assert "fees calm" in g["line"]
    assert "WR thin · 0%" not in g["line"]  # WR% stays in fields
    assert "WR above BE" not in g["line"]
    assert "WR below BE" not in g["line"]
    assert "exp −€4" not in g["line"]
    assert "net exp strong" not in g["line"]  # net stays in fields
    assert "fee take −€8" in g["line"]
    assert "sample ready" not in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_fee_take_thin() -> None:
    """Net expect alone must not hide thin fee take (gross − net €/close)."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 8,
        "sells": 4,
        "fees": 190.0,
        "realized_pnl": 200.0,
        "net_after_all_fees": 10.0,
        "wins": 3,
        "losses": 1,
        "avg_win": 80.0,
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
    # gross 50, net 2.5 → take 47.5 thin (0.95 ≥ 0.5)
    assert g["window_a_closes_net_expectancy_bit"] == "net exp thin · +€2"
    assert g["window_a_closes_net_expectancy"] == 2.5
    assert g["window_a_closes_fee_take_bit"] == "fee take thin · €48"
    assert g["window_a_closes_fee_take"] == 47.5
    assert g["window_a_closes_fee_take_thin"] is True
    assert g["window_a_closes_fee_take_severity"] == "thin"
    assert g["window_a_closes_fee_take_ratio"] == 0.95
    assert g["tone"] == "warn"
    assert "net exp thin" not in g["line"]
    assert "fee take thin · €48" in g["line"]
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
