"""Promote A/B window glance + fee-adjusted window stats (display only)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from openbb_backend.desk import build_promote_ab_glance
from stock_checker.promote_ab import (
    WINDOW_A_START_UTC,
    filter_trades_in_window,
    format_window_stats_bit,
    parse_trade_timestamp,
    promote_ab_snapshot,
    summarize_window_trades,
    weekday_trading_days,
)


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
    assert g["a_fill_progress_bit"] == ""


def test_promote_ab_glance_building_sample_while_running() -> None:
    """Days still short + thin fills → dual meter + building sample (not bare running)."""
    g = build_promote_ab_glance(
        {"promote_experiment_strategy": False},
        as_of=date(2026, 8, 18),
        window_stats={
            "trades": 3,
            "fees": 15.0,
            "realized_pnl": 40.0,
            "net_after_all_fees": 25.0,
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "progress"
    assert g["target_met"] is False
    assert g["sample_known"] is True
    assert g["sample_ready"] is False
    assert g["a_fill_progress_bit"] == "3/10 fills"
    assert "3/10 fills" in g["line"]
    assert "building sample" in g["line"]
    assert "running" not in g["line"]
    assert "sample ready" not in g["line"]
    assert "€15 fees" in g["line"]
    assert "+€25 net" in g["line"]
    # Dual progress owns the fill count — fees bit omits trailing "N fills".
    assert " · 3 fills" not in g["line"]
    assert "A thin" not in g["line"]  # thin bit only after day target


def test_promote_ab_glance_sample_ready_while_days_short() -> None:
    """Fills+closes ok but days short → sample ready · keep Window A (not bare running)."""
    g = build_promote_ab_glance(
        {"promote_experiment_strategy": False},
        as_of=date(2026, 8, 18),
        window_stats={
            "trades": 12,
            "fees": 40.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": 160.0,
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "progress"
    assert g["target_met"] is False
    assert g["sample_known"] is True
    assert g["sample_ready"] is True
    assert g["a_fill_progress_bit"] == "12/10 fills"
    assert "12/10 fills" in g["line"]
    assert "sample ready · keep Window A" in g["line"]
    assert "building sample" not in g["line"]
    assert "running" not in g["line"]
    assert "ready for B" not in g["line"]
    assert "€40 fees" in g["line"]
    assert "+€160 net" in g["line"]


def test_promote_ab_glance_building_closes_while_days_short() -> None:
    """Fills ok but sparse sells + days short → building closes + N/3 sells meter."""
    g = build_promote_ab_glance(
        {"promote_experiment_strategy": False},
        as_of=date(2026, 8, 18),
        window_stats={
            "trades": 12,
            "buys": 10,
            "sells": 2,
            "fees": 40.0,
            "realized_pnl": 50.0,
            "net_after_all_fees": 10.0,
            "last_sell": "2026-08-15T12:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "progress"
    assert g["target_met"] is False
    assert g["sample_known"] is True
    assert g["sample_ready"] is False
    assert g["sample_thin_closes"] is True
    assert g["a_fill_progress_bit"] == "12/10 fills · 2/3 sells"
    assert "2/3 sells" in g["line"]
    assert "building closes" in g["line"]
    assert "building sample" not in g["line"]
    assert "ready for B" not in g["line"]
    assert "sample ready" not in g["line"]


def test_format_window_a_fill_progress_bit() -> None:
    from stock_checker.promote_ab import (
        format_window_a_fill_progress_bit,
        format_window_a_sell_progress_bit,
        window_a_sample_readiness,
    )

    assert format_window_a_fill_progress_bit(None) == ""
    unknown = window_a_sample_readiness(None)
    assert format_window_a_fill_progress_bit(unknown) == ""
    assert format_window_a_sell_progress_bit(unknown) == ""
    thin = window_a_sample_readiness({"trades": 4})
    assert format_window_a_fill_progress_bit(thin) == "4/10 fills"
    assert format_window_a_sell_progress_bit(thin) == ""
    ok = window_a_sample_readiness({"trades": 12})
    assert format_window_a_fill_progress_bit(ok) == "12/10 fills"
    sided = window_a_sample_readiness({"trades": 12, "buys": 7, "sells": 5})
    assert format_window_a_sell_progress_bit(sided) == "5/3 sells"
    assert format_window_a_fill_progress_bit(sided) == "12/10 fills · 5/3 sells"


def test_promote_ab_glance_target_met_without_stats() -> None:
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


def test_parse_trade_timestamp_space_form() -> None:
    dt = parse_trade_timestamp("2026-08-13 06:24:32")
    assert dt is not None
    assert dt == datetime(2026, 8, 13, 6, 24, 32, tzinfo=timezone.utc)


def test_summarize_window_trades_filters_and_fees() -> None:
    trades = [
        {
            "timestamp": "2026-08-10 12:00:00",
            "type": "BUY",
            "symbol": "OLD",
            "commission": 9.0,
        },
        {
            "timestamp": "2026-08-13 06:24:32",
            "type": "BUY",
            "symbol": "JPM",
            "commission": 10.0,
        },
        {
            "timestamp": "2026-08-14 10:00:00",
            "type": "SELL",
            "symbol": "JPM",
            "commission": 5.0,
            "profit_loss": 100.0,
        },
        {
            "timestamp": "2026-08-15 11:00:00",
            "type": "BUY",
            "symbol": "BTC-USD",
            "commission": 3.0,
        },
    ]
    kept = filter_trades_in_window(trades, start=WINDOW_A_START_UTC)
    assert len(kept) == 3
    s = summarize_window_trades(trades, start=WINDOW_A_START_UTC)
    assert s["trades"] == 3
    assert s["buys"] == 2
    assert s["sells"] == 1
    assert s["fees"] == 18.0
    assert s["realized_pnl"] == 100.0
    assert s["net_after_sell_fees"] == 95.0
    assert s["net_after_all_fees"] == 82.0
    assert s["crypto_legs"] == 1
    assert s["stock_legs"] == 2
    assert s["wins"] == 1
    assert s["losses"] == 0
    assert s["avg_win"] == 100.0
    assert s["avg_loss"] is None
    assert s["payoff_ratio"] is None
    assert s["gross_wins"] == 100.0
    assert s["gross_losses"] is None
    assert s["profit_factor"] is None
    assert s["expectancy"] == 100.0
    assert s["win_rate"] == 100.0
    assert s["loss_streak"] == 0
    assert s["loss_streak_max"] == 0
    assert s["loss_streak_mean"] is None
    assert s["loss_streak_median"] is None
    assert s["loss_streak_runs"] == 0
    assert s["win_streak"] == 1
    assert s["win_streak_max"] == 1
    assert s["win_streak_mean"] == 1.0
    assert s["win_streak_runs"] == 1
    assert s["flat_closes"] == 0
    bit = format_window_stats_bit(s)
    assert "€18 fees" in bit
    assert "+€82 net" in bit
    assert "3 fills" in bit


def test_format_window_stats_bit_prefers_net_after_all_fees() -> None:
    bit = format_window_stats_bit(
        {
            "trades": 4,
            "fees": 50.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": 150.0,
        }
    )
    assert "€50 fees" in bit
    assert "+€150 net" in bit
    assert "4 fills" in bit
    assert "+€200" not in bit


def test_format_window_stats_bit_fallback_without_net_field() -> None:
    bit = format_window_stats_bit(
        {"trades": 2, "fees": 20.0, "realized_pnl": 250.0}
    )
    assert "€20 fees" in bit
    assert "+€230 net" in bit
    assert "2 fills" in bit


def test_promote_ab_glance_includes_window_stats(tmp_path: Path) -> None:
    trades_path = tmp_path / "trades.jsonl"
    # Day target met but only 2 fills → A thin (need ≥10 fills before ready for B).
    trades_path.write_text(
        "\n".join(
            [
                '{"timestamp":"2026-08-13 06:24:32","type":"BUY","symbol":"JPM","commission":12.5}',
                '{"timestamp":"2026-08-14 10:00:00","type":"SELL","symbol":"JPM","commission":7.5,"profit_loss":250.0}',
            ]
        )
        + "\n"
    )
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "ai_mode": "validate",
        },
        as_of=date(2026, 9, 13),
        data_dir=tmp_path,
        open_positions=2,
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["window_stats"]["trades"] == 2
    assert "€20 fees" in g["line"]
    assert "+€230 net" in g["line"]  # 250 realized − 20 all fees
    assert "2/10 fills" in g["line"]
    assert "1/3 sells" in g["line"]
    assert "A thin" in g["line"]
    assert "2 fills <10" in g["line"]
    assert "keep Window A" in g["line"]
    assert "ready for B" not in g["line"]
    assert g["sample_known"] is True
    assert g["sample_ready"] is False
    assert g["sample_fills"] == 2
    assert g["sample_buys"] == 1
    assert g["sample_sells"] == 1
    assert g["sample_open_only"] is False
    assert g["target_fills"] == 10
    assert g["a_fill_progress_bit"] == "2/10 fills · 1/3 sells"
    assert g["b_ready"] is False
    assert g["b_blockers"] == []


def test_window_a_sample_readiness_fill_floor() -> None:
    from stock_checker.promote_ab import (
        WINDOW_A_AGING_SELL_DAYS,
        WINDOW_A_MAX_SELL_STALE_DAYS,
        WINDOW_A_TARGET_FILLS,
        WINDOW_A_TARGET_SELLS,
        format_window_a_aging_closes_bit,
        format_window_a_fee_drag_bit,
        format_window_a_fees_ok_bit,
        format_window_a_fill_progress_bit,
        format_window_a_fresh_closes_bit,
        format_window_a_open_only_bit,
        format_window_a_side_bit,
        format_window_a_stale_closes_bit,
        format_window_a_thin_bit,
        format_window_a_thin_closes_bit,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(None)
    assert unknown["known"] is False
    assert unknown["ready"] is False
    assert unknown["thin"] is False
    assert unknown["open_only"] is False
    assert format_window_a_thin_bit(unknown) == ""
    assert format_window_a_open_only_bit(unknown) == ""
    assert format_window_a_side_bit(unknown) == ""

    thin = window_a_sample_readiness({"trades": 2, "fees": 20.0, "realized_pnl": 10.0})
    assert thin["known"] is True
    assert thin["ready"] is False
    assert thin["thin"] is True
    assert thin["sides_known"] is False
    assert thin["fills"] == 2
    assert thin["target_fills"] == WINDOW_A_TARGET_FILLS
    assert thin["thin_bit"] == "A thin · 2 fills <10"
    assert format_window_a_thin_bit(thin) == "A thin · 2 fills <10"
    assert format_window_a_side_bit(thin) == ""

    ok = window_a_sample_readiness({"trades": 10, "fees": 50.0, "realized_pnl": 100.0})
    assert ok["ready"] is True
    assert ok["thin"] is False
    assert ok["open_only"] is False
    assert ok["thin_bit"] == ""

    open_only = window_a_sample_readiness(
        {"trades": 12, "buys": 12, "sells": 0, "fees": 40.0, "realized_pnl": 0.0}
    )
    assert open_only["known"] is True
    assert open_only["sides_known"] is True
    assert open_only["ready"] is False
    assert open_only["thin"] is False
    assert open_only["open_only"] is True
    assert open_only["open_only_bit"] == "A open-only · 0 sells"
    assert format_window_a_open_only_bit(open_only) == "A open-only · 0 sells"
    assert format_window_a_side_bit(open_only) == "12b/0s"
    assert format_window_a_fill_progress_bit(open_only) == "12/10 fills · 0/3 sells"
    assert open_only["thin_closes"] is False

    thin_closes = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 11,
            "sells": 1,
            "fees": 40.0,
            "realized_pnl": 10.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert thin_closes["known"] is True
    assert thin_closes["sides_known"] is True
    assert thin_closes["ready"] is False
    assert thin_closes["thin"] is False
    assert thin_closes["open_only"] is False
    assert thin_closes["thin_closes"] is True
    assert thin_closes["target_sells"] == WINDOW_A_TARGET_SELLS
    assert thin_closes["thin_closes_bit"] == "A thin closes · 1 sells <3"
    assert format_window_a_thin_closes_bit(thin_closes) == (
        "A thin closes · 1 sells <3"
    )
    assert thin_closes["fresh_closes"] is False
    assert thin_closes["stale_closes"] is False

    closed_ok = window_a_sample_readiness(
        {"trades": 12, "buys": 8, "sells": 4, "fees": 40.0, "realized_pnl": 100.0}
    )
    assert closed_ok["ready"] is True
    assert closed_ok["open_only"] is False
    assert closed_ok["stale_closes"] is False
    assert format_window_a_side_bit(closed_ok) == "8b/4s"
    assert format_window_a_fill_progress_bit(closed_ok) == "12/10 fills · 4/3 sells"

    fresh = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": 100.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert fresh["ready"] is True
    assert fresh["stale_closes"] is False
    assert fresh["aging_closes"] is False
    assert fresh["fresh_closes"] is True
    assert fresh["closes_freshness"] == "fresh"
    assert fresh["sell_stale_days"] == 1
    assert format_window_a_aging_closes_bit(fresh) == ""
    assert "A fresh closes" in fresh["fresh_closes_bit"]
    assert format_window_a_fresh_closes_bit(fresh) == fresh["fresh_closes_bit"]

    aging = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": 100.0,
            "last_sell": "2026-09-08T12:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert aging["ready"] is True
    assert aging["stale_closes"] is False
    assert aging["aging_closes"] is True
    assert aging["fresh_closes"] is False
    assert aging["closes_freshness"] == "aging"
    assert aging["sell_stale_days"] == 4
    assert aging["sell_stale_days"] > WINDOW_A_AGING_SELL_DAYS
    assert aging["sell_stale_days"] <= WINDOW_A_MAX_SELL_STALE_DAYS
    assert "A aging closes" in aging["aging_closes_bit"]
    assert format_window_a_aging_closes_bit(aging) == aging["aging_closes_bit"]
    assert format_window_a_fresh_closes_bit(aging) == ""

    stale = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": 100.0,
            "last_sell": "2026-08-20T12:00:00+00:00",
        },
        as_of=date(2026, 9, 13),
    )
    assert stale["ready"] is False
    assert stale["thin"] is False
    assert stale["open_only"] is False
    assert stale["stale_closes"] is True
    assert stale["aging_closes"] is False
    assert stale["fresh_closes"] is False
    assert stale["closes_freshness"] == "stale"
    assert stale["sell_stale_days"] is not None
    assert stale["sell_stale_days"] > WINDOW_A_MAX_SELL_STALE_DAYS
    assert "A stale closes" in stale["stale_closes_bit"]
    assert format_window_a_stale_closes_bit(stale) == stale["stale_closes_bit"]
    assert format_window_a_aging_closes_bit(stale) == ""
    assert format_window_a_fresh_closes_bit(stale) == ""

    drag = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 80.0,
            "realized_pnl": 20.0,
            "net_after_all_fees": -60.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert drag["fee_drag"] is True
    assert drag["ready"] is True  # warn only — does not block
    assert drag["fees_ok"] is False
    assert drag["fee_drag_net"] == -60.0
    assert drag["fee_drag_ratio"] == 4.0
    assert drag["fee_drag_severity"] == "heavy"
    assert drag["fee_drag_bit"] == "A fee drag heavy · net −€60 · fees 4×"
    assert format_window_a_fee_drag_bit(drag) == drag["fee_drag_bit"]

    # Fallback when net is missing / non-negative but fees still > realized.
    drag_fallback = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 80.0,
            "realized_pnl": 20.0,
            "net_after_all_fees": 0.0,  # odd stats → keep fees N× wording
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert drag_fallback["fee_drag"] is True
    assert drag_fallback["fee_drag_ratio"] == 4.0
    assert drag_fallback["fee_drag_severity"] == "heavy"
    assert drag_fallback["fee_drag_bit"] == "A fee drag heavy · fees 4×"

    # Non-integer multiple keeps one decimal; ≥2× is heavy.
    drag_frac = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 50.0,
            "realized_pnl": 20.0,
            "net_after_all_fees": -30.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert drag_frac["fee_drag"] is True
    assert drag_frac["fee_drag_ratio"] == 2.5
    assert drag_frac["fee_drag_severity"] == "heavy"
    assert drag_frac["fee_drag_bit"] == "A fee drag heavy · net −€30 · fees 2.5×"

    # mild <2× · severe ≥5× · total when realized ≤0.
    drag_mild = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 30.0,
            "realized_pnl": 20.0,
            "net_after_all_fees": -10.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert drag_mild["fee_drag_severity"] == "mild"
    assert drag_mild["fee_drag_bit"] == "A fee drag mild · net −€10 · fees 1.5×"

    drag_severe = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 100.0,
            "realized_pnl": 20.0,
            "net_after_all_fees": -80.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert drag_severe["fee_drag_severity"] == "severe"
    assert drag_severe["fee_drag_bit"] == "A fee drag severe · net −€80 · fees 5×"

    drag_total = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": -10.0,
            "net_after_all_fees": -50.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert drag_total["fee_drag"] is True
    assert drag_total["fee_drag_ratio"] is None
    assert drag_total["fee_drag_severity"] == "total"
    assert drag_total["fee_drag_bit"] == "A fee drag total · net −€50"

    no_drag = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": 160.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert no_drag["fee_drag"] is False
    assert no_drag["fee_drag_ratio"] is None
    assert no_drag["fee_drag_severity"] == ""
    assert format_window_a_fee_drag_bit(no_drag) == ""
    assert no_drag["fees_ok"] is True
    assert no_drag["fees_ok_net"] == 160.0
    assert no_drag["fees_ok_ratio"] == 0.2
    assert no_drag["fees_ok_severity"] == "comfortable"
    assert no_drag["fees_ok_bit"] == "A fees comfortable · net +€160 · fees 0.2×"
    assert format_window_a_fees_ok_bit(no_drag) == no_drag["fees_ok_bit"]

    mid_fees = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 80.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": 120.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert mid_fees["fees_ok"] is True
    assert mid_fees["fee_drag"] is False
    assert mid_fees["fees_ok_ratio"] == 0.4
    assert mid_fees["fees_ok_severity"] == ""
    assert mid_fees["fees_ok_bit"] == "A fees ok · net +€120 · fees 0.4×"
    assert format_window_a_fees_ok_bit(mid_fees) == mid_fees["fees_ok_bit"]

    thin_fees = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 80.0,
            "realized_pnl": 100.0,
            "net_after_all_fees": 20.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert thin_fees["fees_ok"] is True
    assert thin_fees["fee_drag"] is False
    assert thin_fees["fees_ok_ratio"] == 0.8
    assert thin_fees["fees_ok_severity"] == "thin"
    assert thin_fees["fees_ok_bit"] == "A fees thin · net +€20 · fees 0.8×"
    assert format_window_a_fees_ok_bit(thin_fees) == thin_fees["fees_ok_bit"]

    open_fees = window_a_sample_readiness(
        {
            "trades": 10,
            "buys": 10,
            "sells": 0,
            "fees": 50.0,
            "realized_pnl": 0.0,
        }
    )
    assert open_fees["open_only"] is True
    assert open_fees["fee_drag"] is False  # open-only already covers −fees
    assert open_fees["fee_drag_ratio"] is None
    assert open_fees["fee_drag_severity"] == ""
    assert open_fees["fees_ok"] is False
    assert open_fees["fees_ok_severity"] == ""
    assert format_window_a_fees_ok_bit(open_fees) == ""


def test_promote_ab_glance_fee_drag_warns_but_ready_for_b() -> None:
    """Fills + sells ok but fees > realized → fee drag warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 80.0,
            "realized_pnl": 20.0,
            "net_after_all_fees": -60.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["target_met"] is True
    assert g["sample_known"] is True
    assert g["sample_ready"] is True
    assert g["sample_fee_drag"] is True
    assert g["fee_drag_severity"] == "heavy"
    assert g["sample_fees_ok"] is False
    assert g["sample_fresh_closes"] is True
    assert "A fee drag heavy · net −€60 · fees 4×" in g["line"]
    assert "A fees ok" not in g["line"]
    assert "A fresh closes" in g["line"]
    assert "ready for B" in g["line"]
    assert "keep Window A" not in g["line"]
    assert g["b_ready"] is True


def test_promote_ab_glance_fees_ok_ready_for_b() -> None:
    """Fills + sells ok + mid-band fees÷realized → A fees ok · ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 80.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": 120.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "ready"
    assert g["target_met"] is True
    assert g["sample_known"] is True
    assert g["sample_ready"] is True
    assert g["sample_fee_drag"] is False
    assert g["sample_fees_ok"] is True
    assert g["fees_ok_severity"] == ""
    assert g["sample_fresh_closes"] is True
    assert "A fees ok · net +€120 · fees 0.4×" in g["line"]
    assert "A fees comfortable" not in g["line"]
    assert "A fees thin" not in g["line"]
    assert "A fee drag" not in g["line"]
    assert "A fresh closes" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True


def test_promote_ab_glance_fees_comfortable_ready_for_b() -> None:
    """Fills + sells ok + fees÷realized <0.25 → A fees comfortable · ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": 160.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "ready"
    assert g["target_met"] is True
    assert g["sample_known"] is True
    assert g["sample_ready"] is True
    assert g["sample_fee_drag"] is False
    assert g["sample_fees_ok"] is True
    assert g["fees_ok_severity"] == "comfortable"
    assert g["sample_fresh_closes"] is True
    assert "A fees comfortable · net +€160 · fees 0.2×" in g["line"]
    assert "A fees ok" not in g["line"]
    assert "A fees thin" not in g["line"]
    assert "A fee drag" not in g["line"]
    assert "A fresh closes" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True


def test_promote_ab_glance_fees_thin_warns_but_ready_for_b() -> None:
    """Fills + sells ok + fees ≤ realized but ≥0.5× → A fees thin · warn · ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 80.0,
            "realized_pnl": 100.0,
            "net_after_all_fees": 20.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["target_met"] is True
    assert g["sample_known"] is True
    assert g["sample_ready"] is True
    assert g["sample_fee_drag"] is False
    assert g["sample_fees_ok"] is True
    assert g["fees_ok_severity"] == "thin"
    assert g["sample_fresh_closes"] is True
    assert "A fees thin · net +€20 · fees 0.8×" in g["line"]
    assert "A fees ok" not in g["line"]
    assert "A fee drag" not in g["line"]
    assert "A fresh closes" in g["line"]
    assert "ready for B" in g["line"]
    assert "keep Window A" not in g["line"]
    assert g["b_ready"] is True


def test_window_a_closes_polarity_triad() -> None:
    """Close win/lose polarity: all_win / mixed lean / all_loss (fail-open without keys)."""
    from stock_checker.promote_ab import (
        format_window_a_closes_polarity_bit,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": 200.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert unknown["closes_polarity_known"] is False
    assert unknown["closes_polarity"] == ""
    assert unknown["closes_polarity_lean"] == ""
    assert format_window_a_closes_polarity_bit(unknown) == ""

    all_win = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": 200.0,
            "wins": 4,
            "losses": 0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert all_win["closes_polarity_known"] is True
    assert all_win["closes_polarity"] == "all_win"
    assert all_win["closes_polarity_lean"] == ""
    assert all_win["closes_all_loss"] is False
    assert all_win["closes_loss_lean"] is False
    assert all_win["closes_polarity_bit"] == "A all-win · 4w/0l"
    assert format_window_a_closes_polarity_bit(all_win) == all_win["closes_polarity_bit"]

    even = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": 100.0,
            "wins": 2,
            "losses": 2,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert even["closes_polarity"] == "mixed"
    assert even["closes_polarity_lean"] == "even"
    assert even["closes_loss_lean"] is False
    assert even["closes_polarity_bit"] == "A mixed · even · 2w/2l"

    win_lean = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": 150.0,
            "wins": 3,
            "losses": 1,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert win_lean["closes_polarity"] == "mixed"
    assert win_lean["closes_polarity_lean"] == "win_lean"
    assert win_lean["closes_loss_lean"] is False
    assert win_lean["closes_polarity_bit"] == "A mixed · mostly wins · 3w/1l"

    loss_lean = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": 20.0,
            "wins": 1,
            "losses": 3,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert loss_lean["closes_polarity"] == "mixed"
    assert loss_lean["closes_polarity_lean"] == "loss_lean"
    assert loss_lean["closes_loss_lean"] is True
    assert loss_lean["closes_all_loss"] is False
    assert loss_lean["closes_polarity_bit"] == "A mixed · mostly losses · 1w/3l"
    assert loss_lean["ready"] is True  # warn only — does not block

    all_loss = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": -80.0,
            "net_after_all_fees": -120.0,
            "wins": 0,
            "losses": 4,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert all_loss["closes_polarity"] == "all_loss"
    assert all_loss["closes_polarity_lean"] == ""
    assert all_loss["closes_all_loss"] is True
    assert all_loss["closes_loss_lean"] is False
    assert all_loss["closes_polarity_bit"] == "A all-loss · 0w/4l"
    assert all_loss["ready"] is True  # warn only — does not block


def test_window_a_closes_payoff_triad() -> None:
    """Close payoff = avg_win ÷ avg_loss: strong / ok / thin (fail-open without avgs)."""
    from stock_checker.promote_ab import (
        WINDOW_A_PAYOFF_STRONG_RATIO,
        WINDOW_A_PAYOFF_THIN_RATIO,
        format_window_a_closes_payoff_bit,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": 100.0,
            "wins": 2,
            "losses": 2,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert unknown["closes_payoff_ratio"] is None
    assert unknown["closes_payoff_bit"] == ""
    assert unknown["closes_payoff_thin"] is False
    assert format_window_a_closes_payoff_bit(unknown) == ""

    strong = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 200.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert strong["closes_payoff_ratio"] == 2.0
    assert strong["closes_payoff_severity"] == "strong"
    assert strong["closes_payoff_thin"] is False
    assert strong["closes_payoff_bit"] == "A payoff strong · 2×"
    assert strong["closes_payoff_ratio"] >= WINDOW_A_PAYOFF_STRONG_RATIO
    assert format_window_a_closes_payoff_bit(strong) == strong["closes_payoff_bit"]

    mid = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 100.0,
            "wins": 2,
            "losses": 2,
            "avg_win": 60.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert mid["closes_payoff_ratio"] == 1.5
    assert mid["closes_payoff_severity"] == ""
    assert mid["closes_payoff_thin"] is False
    assert mid["closes_payoff_bit"] == "A payoff · 1.5×"
    assert mid["closes_payoff_ratio"] >= WINDOW_A_PAYOFF_THIN_RATIO

    thin = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 40.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 20.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert thin["closes_payoff_ratio"] == 0.5
    assert thin["closes_payoff_severity"] == "thin"
    assert thin["closes_payoff_thin"] is True
    assert thin["closes_payoff_bit"] == "A payoff thin · 0.5×"
    assert thin["closes_payoff_ratio"] < WINDOW_A_PAYOFF_THIN_RATIO
    assert thin["ready"] is True  # warn only — does not block
    # Count lean mostly wins but € payoff thin — count ≠ € lean.
    assert thin["closes_polarity_lean"] == "win_lean"

    from_ratio = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 100.0,
            "wins": 2,
            "losses": 2,
            "payoff_ratio": 2.5,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert from_ratio["closes_payoff_ratio"] == 2.5
    assert from_ratio["closes_payoff_severity"] == "strong"
    assert from_ratio["closes_payoff_bit"] == "A payoff strong · 2.5×"


def test_window_a_closes_expectancy() -> None:
    """Close expectancy €/close after payoff (portfolio AI; severity vs avg_loss)."""
    from stock_checker.promote_ab import (
        WINDOW_A_EXPECTANCY_STRONG_RATIO,
        WINDOW_A_EXPECTANCY_THIN_RATIO,
        format_window_a_closes_expectancy_bit,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 100.0,
            "wins": 3,
            "losses": 1,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert unknown["closes_expectancy"] is None
    assert unknown["closes_expectancy_bit"] == ""
    assert unknown["closes_expectancy_neg"] is False
    assert unknown["closes_expectancy_severity"] == ""
    assert unknown["closes_expectancy_thin"] is False
    assert unknown["closes_expectancy_ratio"] is None
    assert format_window_a_closes_expectancy_bit(unknown) == ""

    pos = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 100.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    # 0.75*80 − 0.25*40 = 50; ratio vs avg_loss = 50/40 = 1.25 ≥ strong
    assert pos["closes_expectancy"] == 50.0
    assert pos["closes_expectancy_neg"] is False
    assert pos["closes_expectancy_severity"] == "strong"
    assert pos["closes_expectancy_thin"] is False
    assert pos["closes_expectancy_ratio"] == 1.25
    assert pos["closes_expectancy_ratio"] >= WINDOW_A_EXPECTANCY_STRONG_RATIO
    assert pos["closes_expectancy_bit"] == "A expectancy strong · +€50"
    assert format_window_a_closes_expectancy_bit(pos) == pos["closes_expectancy_bit"]

    mid = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 50.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 30.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    # 0.75*30 − 0.25*40 = 12.5; ratio = 12.5/40 = 0.3125 (mid band)
    assert mid["closes_expectancy"] == 12.5
    assert mid["closes_expectancy_severity"] == ""
    assert mid["closes_expectancy_thin"] is False
    assert mid["closes_expectancy_ratio"] == 0.312
    assert WINDOW_A_EXPECTANCY_THIN_RATIO <= mid["closes_expectancy_ratio"] < WINDOW_A_EXPECTANCY_STRONG_RATIO
    assert mid["closes_expectancy_bit"] == "A expectancy · +€12"

    thin = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 20.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 15.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    # 0.75*15 − 0.25*40 = 1.25; ratio = 1.25/40 = 0.03125 < thin
    assert thin["closes_expectancy"] == 1.25
    assert thin["closes_expectancy_severity"] == "thin"
    assert thin["closes_expectancy_thin"] is True
    assert thin["closes_expectancy_ratio"] == 0.031
    assert thin["closes_expectancy_ratio"] < WINDOW_A_EXPECTANCY_THIN_RATIO
    assert thin["closes_expectancy_bit"] == "A expectancy thin · +€1"
    assert thin["ready"] is True  # warn only

    neg = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 40.0,
            "wins": 1,
            "losses": 3,
            "avg_win": 20.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    # 0.25*20 − 0.75*40 = −25
    assert neg["closes_expectancy"] == -25.0
    assert neg["closes_expectancy_neg"] is True
    assert neg["closes_expectancy_severity"] == ""
    assert neg["closes_expectancy_thin"] is False
    assert neg["closes_expectancy_bit"] == "A expectancy −€25"
    assert neg["ready"] is True  # warn only

    all_win = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 200.0,
            "wins": 4,
            "losses": 0,
            "avg_win": 50.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    # No avg_loss → signed € only (fail-open severity)
    assert all_win["closes_expectancy"] == 50.0
    assert all_win["closes_expectancy_severity"] == ""
    assert all_win["closes_expectancy_bit"] == "A expectancy +€50"

    all_loss = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 50.0,
            "realized_pnl": -120.0,
            "wins": 0,
            "losses": 4,
            "avg_loss": 30.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert all_loss["closes_expectancy"] == -30.0
    assert all_loss["closes_expectancy_neg"] is True
    assert all_loss["closes_expectancy_bit"] == "A expectancy −€30"

    from_key = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 100.0,
            "wins": 2,
            "losses": 2,
            "expectancy": 12.5,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert from_key["closes_expectancy"] == 12.5
    assert from_key["closes_expectancy_severity"] == ""
    assert from_key["closes_expectancy_bit"] == "A expectancy +€12"


def test_window_a_closes_profit_factor_triad() -> None:
    """Profit factor = gross wins ÷ gross losses (distinct from avg payoff)."""
    from stock_checker.promote_ab import (
        WINDOW_A_PROFIT_FACTOR_STRONG_RATIO,
        WINDOW_A_PROFIT_FACTOR_THIN_RATIO,
        format_window_a_closes_profit_factor_bit,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": 100.0,
            "wins": 2,
            "losses": 2,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert unknown["closes_profit_factor"] is None
    assert unknown["closes_profit_factor_bit"] == ""
    assert unknown["closes_profit_factor_thin"] is False
    assert format_window_a_closes_profit_factor_bit(unknown) == ""

    # Count lean win but avg thin: payoff 0.5× thin, PF = 60/40 = 1.5× ok.
    diverge = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 20.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 20.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert diverge["closes_payoff_ratio"] == 0.5
    assert diverge["closes_payoff_thin"] is True
    assert diverge["closes_profit_factor"] == 1.5
    assert diverge["closes_profit_factor_severity"] == ""
    assert diverge["closes_profit_factor_thin"] is False
    assert diverge["closes_profit_factor_bit"] == "A PF · 1.5×"
    assert diverge["closes_gross_wins"] == 60.0
    assert diverge["closes_gross_losses"] == 40.0
    assert format_window_a_closes_profit_factor_bit(diverge) == diverge[
        "closes_profit_factor_bit"
    ]

    strong = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 200.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert strong["closes_profit_factor"] == 6.0
    assert strong["closes_profit_factor_severity"] == "strong"
    assert strong["closes_profit_factor_thin"] is False
    assert strong["closes_profit_factor_bit"] == "A PF strong · 6×"
    assert strong["closes_profit_factor"] >= WINDOW_A_PROFIT_FACTOR_STRONG_RATIO

    thin = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": -40.0,
            "wins": 1,
            "losses": 3,
            "avg_win": 20.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert thin["closes_profit_factor"] == 0.17
    assert thin["closes_profit_factor_severity"] == "thin"
    assert thin["closes_profit_factor_thin"] is True
    assert thin["closes_profit_factor_bit"] == "A PF thin · 0.2×"
    assert thin["closes_profit_factor"] < WINDOW_A_PROFIT_FACTOR_THIN_RATIO
    assert thin["ready"] is True  # warn only

    from_key = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 100.0,
            "wins": 2,
            "losses": 2,
            "profit_factor": 2.5,
            "gross_wins": 200.0,
            "gross_losses": 80.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert from_key["closes_profit_factor"] == 2.5
    assert from_key["closes_profit_factor_severity"] == "strong"
    assert from_key["closes_profit_factor_bit"] == "A PF strong · 2.5×"
    assert from_key["closes_gross_wins"] == 200.0
    assert from_key["closes_gross_losses"] == 80.0

    all_win = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 200.0,
            "wins": 4,
            "losses": 0,
            "avg_win": 50.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert all_win["closes_profit_factor"] is None
    assert all_win["closes_profit_factor_bit"] == ""


def test_window_a_closes_win_rate_triad() -> None:
    """Win rate % severity triad after polarity (count lean ≠ hit rate)."""
    from stock_checker.promote_ab import (
        WINDOW_A_WIN_RATE_STRONG_PCT,
        WINDOW_A_WIN_RATE_THIN_PCT,
        format_window_a_closes_win_rate_bit,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 100.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert unknown["closes_win_rate_pct"] is None
    assert unknown["closes_win_rate_bit"] == ""
    assert unknown["closes_win_rate_thin"] is False
    assert format_window_a_closes_win_rate_bit(unknown) == ""

    strong = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 5,
            "fees": 20.0,
            "realized_pnl": 100.0,
            "wins": 3,
            "losses": 2,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert strong["closes_win_rate_pct"] == 60.0
    assert strong["closes_win_rate_severity"] == "strong"
    assert strong["closes_win_rate_thin"] is False
    assert strong["closes_win_rate_bit"] == "A win rate strong · 60%"
    assert strong["closes_win_rate_pct"] >= WINDOW_A_WIN_RATE_STRONG_PCT
    assert strong["closes_polarity_lean"] == "win_lean"
    assert format_window_a_closes_win_rate_bit(strong) == strong[
        "closes_win_rate_bit"
    ]

    mid = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 80.0,
            "wins": 2,
            "losses": 2,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert mid["closes_win_rate_pct"] == 50.0
    assert mid["closes_win_rate_severity"] == ""
    assert mid["closes_win_rate_thin"] is False
    assert mid["closes_win_rate_bit"] == "A win rate · 50%"
    assert WINDOW_A_WIN_RATE_THIN_PCT <= mid["closes_win_rate_pct"] < WINDOW_A_WIN_RATE_STRONG_PCT

    thin = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 40.0,
            "wins": 1,
            "losses": 3,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert thin["closes_win_rate_pct"] == 25.0
    assert thin["closes_win_rate_severity"] == "thin"
    assert thin["closes_win_rate_thin"] is True
    assert thin["closes_win_rate_bit"] == "A win rate thin · 25%"
    assert thin["closes_win_rate_pct"] < WINDOW_A_WIN_RATE_THIN_PCT
    assert thin["ready"] is True  # warn only

    from_key = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 100.0,
            "wins": 3,
            "losses": 1,
            "win_rate": 75.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert from_key["closes_win_rate_pct"] == 75.0
    assert from_key["closes_win_rate_severity"] == "strong"
    assert from_key["closes_win_rate_bit"] == "A win rate strong · 75%"

    all_loss = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": -80.0,
            "wins": 0,
            "losses": 4,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert all_loss["closes_win_rate_pct"] == 0.0
    assert all_loss["closes_win_rate_thin"] is True
    assert all_loss["closes_win_rate_bit"] == "A win rate thin · 0%"


def test_window_a_closes_wr_vs_be_triad() -> None:
    """WR vs breakeven from payoff — ±pp cushion + severity triad."""
    from stock_checker.promote_ab import (
        WINDOW_A_WR_BE_AT_PP,
        WINDOW_A_WR_EDGE_STRONG_PP,
        WINDOW_A_WR_EDGE_THIN_PP,
        format_window_a_closes_wr_vs_be_bit,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 100.0,
            "wins": 3,
            "losses": 2,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert unknown["closes_breakeven_wr_pct"] is None
    assert unknown["closes_wr_vs_be"] == ""
    assert unknown["closes_wr_vs_be_bit"] == ""
    assert unknown["closes_wr_below_be"] is False
    assert unknown["closes_wr_edge_pp"] is None
    assert unknown["closes_wr_edge_severity"] == ""
    assert unknown["closes_wr_edge_thin"] is False
    assert format_window_a_closes_wr_vs_be_bit(unknown) == ""

    above = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 5,
            "fees": 20.0,
            "realized_pnl": 100.0,
            "wins": 3,
            "losses": 2,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert above["closes_payoff_ratio"] == 2.0
    assert above["closes_breakeven_wr_pct"] == 33.3
    assert above["closes_win_rate_pct"] == 60.0
    assert above["closes_wr_vs_be"] == "above"
    assert above["closes_wr_below_be"] is False
    assert above["closes_wr_edge_pp"] == 26.7
    assert above["closes_wr_edge_pp"] >= WINDOW_A_WR_EDGE_STRONG_PP
    assert above["closes_wr_edge_severity"] == "strong"
    assert above["closes_wr_edge_thin"] is False
    assert above["closes_wr_vs_be_bit"] == "A WR above BE strong · +26.7pp"
    assert format_window_a_closes_wr_vs_be_bit(above) == above["closes_wr_vs_be_bit"]

    mid = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 7,
            "fees": 20.0,
            "realized_pnl": 80.0,
            "wins": 4,
            "losses": 3,
            "avg_win": 40.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert mid["closes_breakeven_wr_pct"] == 50.0
    assert mid["closes_win_rate_pct"] == round(100.0 * 4 / 7, 1)
    assert mid["closes_wr_vs_be"] == "above"
    assert mid["closes_wr_edge_pp"] is not None
    assert WINDOW_A_WR_EDGE_THIN_PP <= mid["closes_wr_edge_pp"] < WINDOW_A_WR_EDGE_STRONG_PP
    assert mid["closes_wr_edge_severity"] == ""
    assert mid["closes_wr_edge_thin"] is False
    assert mid["closes_wr_vs_be_bit"].startswith("A WR above BE · +")

    thin = window_a_sample_readiness(
        {
            "trades": 14,
            "buys": 8,
            "sells": 6,
            "fees": 20.0,
            "realized_pnl": 80.0,
            "wins": 27,
            "losses": 23,
            "avg_win": 40.0,
            "avg_loss": 40.0,
            "win_rate": 54.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert thin["closes_breakeven_wr_pct"] == 50.0
    assert thin["closes_win_rate_pct"] == 54.0
    assert thin["closes_wr_vs_be"] == "above"
    assert thin["closes_wr_edge_pp"] == 4.0
    assert thin["closes_wr_edge_pp"] < WINDOW_A_WR_EDGE_THIN_PP
    assert thin["closes_wr_edge_severity"] == "thin"
    assert thin["closes_wr_edge_thin"] is True
    assert thin["closes_wr_vs_be_bit"] == "A WR above BE thin · +4pp"
    assert thin["ready"] is True

    at = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 80.0,
            "wins": 2,
            "losses": 2,
            "avg_win": 40.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert at["closes_breakeven_wr_pct"] == 50.0
    assert at["closes_win_rate_pct"] == 50.0
    assert abs(at["closes_win_rate_pct"] - at["closes_breakeven_wr_pct"]) <= WINDOW_A_WR_BE_AT_PP
    assert at["closes_wr_vs_be"] == "at"
    assert at["closes_wr_below_be"] is False
    assert at["closes_wr_edge_pp"] == 0.0
    assert at["closes_wr_edge_severity"] == ""
    assert at["closes_wr_edge_thin"] is False
    assert at["closes_wr_vs_be_bit"] == "A WR at BE · ~0pp"

    below = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 40.0,
            "wins": 1,
            "losses": 3,
            "avg_win": 40.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert below["closes_breakeven_wr_pct"] == 50.0
    assert below["closes_win_rate_pct"] == 25.0
    assert below["closes_wr_vs_be"] == "below"
    assert below["closes_wr_below_be"] is True
    assert below["closes_wr_edge_pp"] == -25.0
    assert below["closes_wr_edge_thin"] is True
    assert below["closes_wr_vs_be_bit"] == "A WR below BE · -25pp"
    assert below["ready"] is True


def test_promote_ab_glance_closes_wr_below_be_warns_but_ready_for_b() -> None:
    """WR below BE → warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 80.0,
            "net_after_all_fees": 60.0,
            "wins": 1,
            "losses": 3,
            "avg_win": 40.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_wr_vs_be"] == "below"
    assert g["closes_wr_below_be"] is True
    assert g["closes_wr_edge_pp"] == -25.0
    assert g["closes_wr_edge_thin"] is True
    assert g["closes_breakeven_wr_pct"] == 50.0
    assert "A WR below BE · -25pp" in g["line"]
    assert "ready for B" in g["line"]
    assert "keep Window A" not in g["line"]
    assert g["b_ready"] is True


def test_promote_ab_glance_closes_wr_edge_thin_warns_but_ready_for_b() -> None:
    """Thin above-BE cushion → warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 14,
            "buys": 8,
            "sells": 6,
            "fees": 10.0,
            "realized_pnl": 80.0,
            "net_after_all_fees": 70.0,
            "wins": 27,
            "losses": 23,
            "avg_win": 40.0,
            "avg_loss": 40.0,
            "win_rate": 54.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_wr_vs_be"] == "above"
    assert g["closes_wr_edge_severity"] == "thin"
    assert g["closes_wr_edge_thin"] is True
    assert g["closes_wr_edge_pp"] == 4.0
    assert "A WR above BE thin · +4pp" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True


def test_window_a_closes_net_expectancy_triad() -> None:
    """Fee-adjusted net ÷ sells — gross €/close ≠ fee-adjusted €/close."""
    from stock_checker.promote_ab import (
        WINDOW_A_EXPECTANCY_STRONG_RATIO,
        WINDOW_A_EXPECTANCY_THIN_RATIO,
        format_window_a_closes_net_expectancy_bit,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert unknown["closes_net_expectancy"] is None
    assert unknown["closes_net_expectancy_bit"] == ""
    assert unknown["closes_net_expectancy_neg"] is False
    assert unknown["closes_net_expectancy_eats_edge"] is False
    assert format_window_a_closes_net_expectancy_bit(unknown) == ""

    strong = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": 180.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert strong["closes_net_expectancy"] == 45.0
    assert strong["closes_net_expectancy_neg"] is False
    assert strong["closes_net_expectancy_severity"] == "strong"
    assert strong["closes_net_expectancy_thin"] is False
    assert strong["closes_net_expectancy_ratio"] == 1.125
    assert strong["closes_net_expectancy_ratio"] >= WINDOW_A_EXPECTANCY_STRONG_RATIO
    assert strong["closes_net_expectancy_eats_edge"] is False
    assert strong["closes_net_expectancy_bit"] == "A net expect strong · +€45"
    assert format_window_a_closes_net_expectancy_bit(strong) == strong[
        "closes_net_expectancy_bit"
    ]

    thin = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 10.0,
            "realized_pnl": 20.0,
            "net_after_all_fees": 10.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert thin["closes_net_expectancy"] == 2.5
    assert thin["closes_net_expectancy_severity"] == "thin"
    assert thin["closes_net_expectancy_thin"] is True
    assert thin["closes_net_expectancy_ratio"] == 0.062
    assert thin["closes_net_expectancy_ratio"] < WINDOW_A_EXPECTANCY_THIN_RATIO
    assert thin["closes_net_expectancy_bit"] == "A net expect thin · +€2"
    assert thin["ready"] is True

    eats = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 120.0,
            "realized_pnl": 100.0,
            "net_after_all_fees": -20.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "expectancy": 50.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert eats["closes_expectancy"] == 50.0
    assert eats["closes_net_expectancy"] == -5.0
    assert eats["closes_net_expectancy_neg"] is True
    assert eats["closes_net_expectancy_eats_edge"] is True
    assert eats["closes_net_expectancy_bit"] == (
        "A net expect −€5 · fees eat edge"
    )
    assert eats["ready"] is True

    from_fees = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 5,
            "fees": 25.0,
            "realized_pnl": 85.0,
            "wins": 3,
            "losses": 2,
            "avg_win": 50.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert from_fees["closes_net_expectancy"] == 12.0
    assert from_fees["closes_net_expectancy_severity"] == ""
    assert from_fees["closes_net_expectancy_bit"] == "A net expect · +€12"


def test_window_a_closes_fee_take_triad() -> None:
    """Expectancy fee take = gross − net €/close (portfolio AI after net expect)."""
    from stock_checker.promote_ab import (
        WINDOW_A_FEES_COMFORTABLE_RATIO,
        WINDOW_A_FEES_THIN_RATIO,
        format_window_a_closes_fee_take_bit,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert unknown["closes_fee_take"] is None
    assert unknown["closes_fee_take_bit"] == ""
    assert unknown["closes_fee_take_thin"] is False
    assert format_window_a_closes_fee_take_bit(unknown) == ""

    # gross 50, net 45 → take 5; 5/50 = 0.1 < comfortable
    comfortable = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": 180.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert comfortable["closes_expectancy"] == 50.0
    assert comfortable["closes_net_expectancy"] == 45.0
    assert comfortable["closes_fee_take"] == 5.0
    assert comfortable["closes_fee_take_severity"] == "comfortable"
    assert comfortable["closes_fee_take_thin"] is False
    assert comfortable["closes_fee_take_ratio"] == 0.1
    assert comfortable["closes_fee_take_ratio"] < WINDOW_A_FEES_COMFORTABLE_RATIO
    assert comfortable["closes_fee_take_bit"] == (
        "A fee take comfortable · €5/close"
    )
    assert format_window_a_closes_fee_take_bit(comfortable) == comfortable[
        "closes_fee_take_bit"
    ]

    # gross 50, net 2.5 → take 47.5; 47.5/50 = 0.95 ≥ thin
    thin = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 10.0,
            "realized_pnl": 20.0,
            "net_after_all_fees": 10.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert thin["closes_expectancy"] == 50.0
    assert thin["closes_net_expectancy"] == 2.5
    assert thin["closes_fee_take"] == 47.5
    assert thin["closes_fee_take_severity"] == "thin"
    assert thin["closes_fee_take_thin"] is True
    assert thin["closes_fee_take_ratio"] == 0.95
    assert thin["closes_fee_take_ratio"] >= WINDOW_A_FEES_THIN_RATIO
    assert thin["closes_fee_take_bit"] == "A fee take thin · €48/close"
    assert thin["ready"] is True  # warn only

    # Mid band: take / gross in [0.25, 0.5)
    mid = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 60.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": 140.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    # gross 50, net 35 → take 15; 15/50 = 0.3 mid
    assert mid["closes_fee_take"] == 15.0
    assert mid["closes_fee_take_severity"] == ""
    assert mid["closes_fee_take_thin"] is False
    assert mid["closes_fee_take_ratio"] == 0.3
    assert (
        WINDOW_A_FEES_COMFORTABLE_RATIO
        <= mid["closes_fee_take_ratio"]
        < WINDOW_A_FEES_THIN_RATIO
    )
    assert mid["closes_fee_take_bit"] == "A fee take · €15/close"


def test_window_a_closes_net_vs_fee_triad() -> None:
    """Net ÷ fee take after fee take € (portfolio AI + xang1234 severity)."""
    from stock_checker.promote_ab import (
        WINDOW_A_PROFIT_FACTOR_STRONG_RATIO,
        WINDOW_A_PROFIT_FACTOR_THIN_RATIO,
        format_window_a_closes_net_vs_fee_bit,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
        }
    )
    assert unknown["closes_net_vs_fee"] is None
    assert unknown["closes_net_vs_fee_bit"] == ""
    assert unknown["closes_net_vs_fee_thin"] is False
    assert format_window_a_closes_net_vs_fee_bit(unknown) == ""

    strong = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": 180.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
        }
    )
    assert strong["closes_net_expectancy"] == 45.0
    assert strong["closes_fee_take"] == 5.0
    assert strong["closes_net_vs_fee"] == 9.0
    assert strong["closes_net_vs_fee"] >= WINDOW_A_PROFIT_FACTOR_STRONG_RATIO
    assert strong["closes_net_vs_fee_severity"] == "strong"
    assert strong["closes_net_vs_fee_thin"] is False
    assert strong["closes_net_vs_fee_bit"] == "A net/fee strong · 9×"
    assert format_window_a_closes_net_vs_fee_bit(strong) == strong[
        "closes_net_vs_fee_bit"
    ]

    thin = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 10.0,
            "realized_pnl": 20.0,
            "net_after_all_fees": 10.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
        }
    )
    assert thin["closes_net_vs_fee"] == 0.05
    assert thin["closes_net_vs_fee"] < WINDOW_A_PROFIT_FACTOR_THIN_RATIO
    assert thin["closes_net_vs_fee_severity"] == "thin"
    assert thin["closes_net_vs_fee_thin"] is True
    assert thin["closes_net_vs_fee_bit"] == "A net/fee thin · 0.1×"

    neg = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 120.0,
            "realized_pnl": 100.0,
            "net_after_all_fees": -20.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "expectancy": 50.0,
        }
    )
    assert neg["closes_net_expectancy"] == -5.0
    assert neg["closes_fee_take"] == 55.0
    assert neg["closes_net_vs_fee"] is None
    assert neg["closes_net_vs_fee_bit"] == ""


def test_window_a_closes_net_vs_fee_mid_band() -> None:
    from stock_checker.promote_ab import (
        WINDOW_A_PROFIT_FACTOR_STRONG_RATIO,
        WINDOW_A_PROFIT_FACTOR_THIN_RATIO,
        window_a_sample_readiness,
    )

    mid = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 80.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": 120.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
        }
    )
    assert mid["closes_net_expectancy"] == 30.0
    assert mid["closes_fee_take"] == 20.0
    assert mid["closes_net_vs_fee"] == 1.5
    assert (
        WINDOW_A_PROFIT_FACTOR_THIN_RATIO
        <= mid["closes_net_vs_fee"]
        < WINDOW_A_PROFIT_FACTOR_STRONG_RATIO
    )
    assert mid["closes_net_vs_fee_severity"] == ""
    assert mid["closes_net_vs_fee_thin"] is False
    assert mid["closes_net_vs_fee_bit"] == "A net/fee · 1.5×"


def test_promote_ab_glance_closes_net_vs_fee_thin_warns_but_ready() -> None:
    """Thin net/fee → warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 10.0,
            "realized_pnl": 20.0,
            "net_after_all_fees": 10.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_net_vs_fee"] == 0.05
    assert g["closes_net_vs_fee_thin"] is True
    assert g["closes_net_vs_fee_severity"] == "thin"
    assert "A net/fee thin · 0.1×" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True


def test_window_a_closes_kelly_triad() -> None:
    """Full Kelly from WR + payoff (portfolio AI size fraction; not half-Kelly)."""
    from stock_checker.promote_ab import (
        WINDOW_A_KELLY_STRONG_PCT,
        WINDOW_A_KELLY_THIN_PCT,
        format_window_a_closes_kelly_bit,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
        }
    )
    assert unknown["closes_kelly_pct"] is None
    assert unknown["closes_kelly_bit"] == ""
    assert unknown["closes_kelly_thin"] is False
    assert unknown["closes_kelly_neg"] is False
    assert format_window_a_closes_kelly_bit(unknown) == ""
    assert format_window_a_closes_kelly_bit(None) == ""

    # 75% WR · payoff 2 → f* = 0.75 − 0.25/2 = 62.5%
    strong = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
        }
    )
    assert strong["closes_kelly_pct"] == 62.5
    assert strong["closes_kelly_pct"] >= WINDOW_A_KELLY_STRONG_PCT
    assert strong["closes_kelly_severity"] == "strong"
    assert strong["closes_kelly_thin"] is False
    assert strong["closes_kelly_neg"] is False
    assert strong["closes_kelly_bit"] == "A Kelly strong · 62.5%"
    assert format_window_a_closes_kelly_bit(strong) == strong["closes_kelly_bit"]

    # 50% WR · payoff 1.1 → f* = 0.5 − 0.5/1.1 ≈ 4.5%
    thin = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 5,
            "losses": 5,
            "avg_win": 11.0,
            "avg_loss": 10.0,
        }
    )
    assert thin["closes_kelly_pct"] == 4.5
    assert thin["closes_kelly_pct"] < WINDOW_A_KELLY_THIN_PCT
    assert thin["closes_kelly_severity"] == "thin"
    assert thin["closes_kelly_thin"] is True
    assert thin["closes_kelly_bit"] == "A Kelly thin · 4.5%"

    # 50% WR · payoff 1.5 → f* = 0.5 − 0.5/1.5 ≈ 16.7%
    mid = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 5,
            "losses": 5,
            "avg_win": 15.0,
            "avg_loss": 10.0,
        }
    )
    assert mid["closes_kelly_pct"] == 16.7
    assert (
        WINDOW_A_KELLY_THIN_PCT
        <= mid["closes_kelly_pct"]
        < WINDOW_A_KELLY_STRONG_PCT
    )
    assert mid["closes_kelly_severity"] == ""
    assert mid["closes_kelly_thin"] is False
    assert mid["closes_kelly_bit"] == "A Kelly · 16.7%"

    # 50% WR · payoff 1 → f* = 0
    zero = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 2,
            "losses": 2,
            "avg_win": 10.0,
            "avg_loss": 10.0,
        }
    )
    assert zero["closes_kelly_pct"] == 0.0
    assert zero["closes_kelly_neg"] is True
    assert zero["closes_kelly_bit"] == "A Kelly neg · 0%"

    # 40% WR · payoff 0.5 → f* = 0.4 − 0.6/0.5 = −80%
    neg = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 2,
            "losses": 3,
            "avg_win": 20.0,
            "avg_loss": 40.0,
        }
    )
    assert neg["closes_kelly_pct"] == -80.0
    assert neg["closes_kelly_neg"] is True
    assert neg["closes_kelly_thin"] is False
    assert neg["closes_kelly_bit"] == "A Kelly neg · −80%"


def test_promote_ab_glance_closes_kelly_neg_warns_but_ready() -> None:
    """Negative Kelly → warn · still ready for B. Not a live sizer."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "fees": 4.0,
            "realized_pnl": 40.0,
            "net_after_all_fees": 36.0,
            "wins": 2,
            "losses": 3,
            "avg_win": 20.0,
            "avg_loss": 40.0,
            "gross_wins": 40.0,
            "gross_losses": 120.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_kelly_pct"] == -80.0
    assert g["closes_kelly_neg"] is True
    assert "A Kelly neg · −80%" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True


def test_window_a_half_kelly_vs_sizer() -> None:
    """Half of full Kelly vs the ~10% cash sizer (display only)."""
    from stock_checker.promote_ab import (
        WINDOW_A_HALF_KELLY_MATCH_PP,
        format_window_a_closes_half_kelly_bit,
        window_a_sample_readiness,
    )
    from stock_checker.risk_halts import DEFAULT_ENTRY_CASH_FRAC

    sizer = round(float(DEFAULT_ENTRY_CASH_FRAC) * 100.0, 1)
    assert sizer == 10.0
    assert WINDOW_A_HALF_KELLY_MATCH_PP == 5.0

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
        }
    )
    assert unknown["closes_half_kelly_pct"] is None
    assert unknown["closes_half_kelly_sizer_pct"] is None
    assert unknown["closes_half_kelly_vs"] == ""
    assert unknown["closes_half_kelly_bit"] == ""
    assert unknown["closes_half_kelly_under"] is False
    assert format_window_a_closes_half_kelly_bit(unknown) == ""
    assert format_window_a_closes_half_kelly_bit(None) == ""

    # 75% WR · payoff 2 → Kelly 62.5 → half 31.2 vs 10 → over
    over = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
        }
    )
    assert over["closes_kelly_pct"] == 62.5
    assert over["closes_half_kelly_pct"] == 31.2
    assert over["closes_half_kelly_sizer_pct"] == 10.0
    assert over["closes_half_kelly_vs"] == "over"
    assert over["closes_half_kelly_under"] is False
    assert over["closes_half_kelly_bit"] == "A half-Kelly vs sizer over · 31.2% vs 10%"

    # 50% WR · payoff 1.5 → Kelly 16.7 → half 8.3 vs 10 → match
    match = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 5,
            "losses": 5,
            "avg_win": 15.0,
            "avg_loss": 10.0,
        }
    )
    assert match["closes_half_kelly_pct"] == 8.3
    assert match["closes_half_kelly_vs"] == "match"
    assert match["closes_half_kelly_under"] is False
    assert match["closes_half_kelly_bit"] == "A half-Kelly vs sizer match · 8.3% vs 10%"
    assert format_window_a_closes_half_kelly_bit(match) == match["closes_half_kelly_bit"]

    # 60% WR · payoff 1 → Kelly 20 → half 10 vs 10 → match
    exact = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 3,
            "losses": 2,
            "avg_win": 10.0,
            "avg_loss": 10.0,
        }
    )
    assert exact["closes_kelly_pct"] == 20.0
    assert exact["closes_half_kelly_pct"] == 10.0
    assert exact["closes_half_kelly_vs"] == "match"
    assert exact["closes_half_kelly_bit"] == "A half-Kelly vs sizer match · 10% vs 10%"

    # 50% WR · payoff 1.1 → Kelly 4.5 → half 2.2 vs 10 → under
    under = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 5,
            "losses": 5,
            "avg_win": 11.0,
            "avg_loss": 10.0,
        }
    )
    assert under["closes_half_kelly_pct"] == 2.2
    assert under["closes_half_kelly_vs"] == "under"
    assert under["closes_half_kelly_under"] is True
    assert under["closes_half_kelly_bit"] == "A half-Kelly vs sizer under · 2.2% vs 10%"

    # 40% WR · payoff 0.5 → Kelly −80 → half −40 vs 10 → under
    neg = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 2,
            "losses": 3,
            "avg_win": 20.0,
            "avg_loss": 40.0,
        }
    )
    assert neg["closes_half_kelly_pct"] == -40.0
    assert neg["closes_half_kelly_under"] is True
    assert neg["closes_half_kelly_bit"] == "A half-Kelly vs sizer under · −40% vs 10%"


def test_window_a_half_kelly_vs_slot() -> None:
    """Half-Kelly vs equal-slot equity share (display only)."""
    from stock_checker.promote_ab import (
        WINDOW_A_EQUAL_SLOT_PCT,
        WINDOW_A_HALF_KELLY_MATCH_PP,
        format_window_a_closes_half_kelly_slot_bit,
        window_a_sample_readiness,
    )

    assert WINDOW_A_EQUAL_SLOT_PCT == 20.0
    assert WINDOW_A_HALF_KELLY_MATCH_PP == 5.0

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
        }
    )
    assert unknown["closes_half_kelly_slot_pct"] is None
    assert unknown["closes_half_kelly_vs_slot"] == ""
    assert unknown["closes_half_kelly_slot_bit"] == ""
    assert unknown["closes_half_kelly_slot_under"] is False
    assert format_window_a_closes_half_kelly_slot_bit(unknown) == ""
    assert format_window_a_closes_half_kelly_slot_bit(None) == ""

    # 75% WR · payoff 2 → Kelly 62.5 → half 31.2 vs 20 → over
    over = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
        }
    )
    assert over["closes_half_kelly_pct"] == 31.2
    assert over["closes_half_kelly_slot_pct"] == 20.0
    assert over["closes_half_kelly_vs_slot"] == "over"
    assert over["closes_half_kelly_slot_under"] is False
    assert over["closes_half_kelly_slot_bit"] == (
        "A half-Kelly vs slot over · 31.2% vs 20%"
    )

    # 50% WR · payoff 2 → Kelly 25 → half 12.5 vs 20 → under
    under = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 2,
            "losses": 2,
            "avg_win": 40.0,
            "avg_loss": 20.0,
        }
    )
    assert under["closes_kelly_pct"] == 25.0
    assert under["closes_half_kelly_pct"] == 12.5
    assert under["closes_half_kelly_vs_slot"] == "under"
    assert under["closes_half_kelly_slot_under"] is True
    assert under["closes_half_kelly_slot_bit"] == (
        "A half-Kelly vs slot under · 12.5% vs 20%"
    )
    assert format_window_a_closes_half_kelly_slot_bit(under) == under[
        "closes_half_kelly_slot_bit"
    ]

    # 60% WR · payoff 1 → Kelly 20 → half 10 vs 20 → under
    mid_under = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 3,
            "losses": 2,
            "avg_win": 40.0,
            "avg_loss": 40.0,
        }
    )
    assert mid_under["closes_kelly_pct"] == 20.0
    assert mid_under["closes_half_kelly_pct"] == 10.0
    assert mid_under["closes_half_kelly_vs_slot"] == "under"
    assert mid_under["closes_half_kelly_slot_under"] is True

    # 60% WR · payoff 50/30 → Kelly ~36 → half 18 vs 20 → match (±5pp)
    match = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 3,
            "losses": 2,
            "avg_win": 50.0,
            "avg_loss": 30.0,
        }
    )
    assert match["closes_half_kelly_pct"] == 18.0
    assert match["closes_half_kelly_vs_slot"] == "match"
    assert match["closes_half_kelly_slot_under"] is False
    assert match["closes_half_kelly_slot_bit"] == (
        "A half-Kelly vs slot match · 18% vs 20%"
    )


def test_promote_ab_glance_half_kelly_slot_under_warns_but_ready() -> None:
    """Half-Kelly below equal slot → warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "fees": 4.0,
            "realized_pnl": 40.0,
            "net_after_all_fees": 36.0,
            "wins": 2,
            "losses": 2,
            "avg_win": 40.0,
            "avg_loss": 20.0,
            "last_sell": "2026-09-12",
        },
    )
    assert g["closes_half_kelly_pct"] == 12.5
    assert g["closes_half_kelly_slot_under"] is True
    assert g["closes_half_kelly_vs_slot"] == "under"
    assert "A half-Kelly vs slot under · 12.5% vs 20%" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True
    assert g["tone"] == "warn"


def test_window_a_half_kelly_vs_cap() -> None:
    """Half-Kelly vs soft concentration cap (~30%; display only)."""
    from stock_checker.promote_ab import (
        WINDOW_A_CONC_CAP_PCT,
        WINDOW_A_HALF_KELLY_MATCH_PP,
        format_window_a_closes_half_kelly_cap_bit,
        window_a_sample_readiness,
    )

    assert WINDOW_A_CONC_CAP_PCT == 30.0
    assert WINDOW_A_HALF_KELLY_MATCH_PP == 5.0

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
        }
    )
    assert unknown["closes_half_kelly_cap_pct"] is None
    assert unknown["closes_half_kelly_vs_cap"] == ""
    assert unknown["closes_half_kelly_cap_bit"] == ""
    assert unknown["closes_half_kelly_cap_under"] is False
    assert format_window_a_closes_half_kelly_cap_bit(unknown) == ""
    assert format_window_a_closes_half_kelly_cap_bit(None) == ""

    # 90% WR · payoff 2 → Kelly 85 → half 42.5 vs 30 → over
    over = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 9,
            "losses": 1,
            "avg_win": 40.0,
            "avg_loss": 20.0,
        }
    )
    assert over["closes_kelly_pct"] == 85.0
    assert over["closes_half_kelly_pct"] == 42.5
    assert over["closes_half_kelly_cap_pct"] == 30.0
    assert over["closes_half_kelly_vs_cap"] == "over"
    assert over["closes_half_kelly_cap_under"] is False
    assert over["closes_half_kelly_cap_bit"] == (
        "A half-Kelly vs cap over · 42.5% vs 30%"
    )

    # 50% WR · payoff 2 → Kelly 25 → half 12.5 vs 30 → under
    under = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 2,
            "losses": 2,
            "avg_win": 40.0,
            "avg_loss": 20.0,
        }
    )
    assert under["closes_kelly_pct"] == 25.0
    assert under["closes_half_kelly_pct"] == 12.5
    assert under["closes_half_kelly_vs_cap"] == "under"
    assert under["closes_half_kelly_cap_under"] is True
    assert under["closes_half_kelly_cap_bit"] == (
        "A half-Kelly vs cap under · 12.5% vs 30%"
    )
    assert format_window_a_closes_half_kelly_cap_bit(under) == under[
        "closes_half_kelly_cap_bit"
    ]

    # 70% WR · payoff 2 → Kelly 55 → half 27.5 vs 30 → match (±5pp)
    match = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 7,
            "losses": 3,
            "avg_win": 40.0,
            "avg_loss": 20.0,
        }
    )
    assert match["closes_kelly_pct"] == 55.0
    assert match["closes_half_kelly_pct"] == 27.5
    assert match["closes_half_kelly_vs_cap"] == "match"
    assert match["closes_half_kelly_cap_under"] is False
    assert match["closes_half_kelly_cap_bit"] == (
        "A half-Kelly vs cap match · 27.5% vs 30%"
    )

    # 75% WR · payoff 2 → Kelly 62.5 → half 31.2 vs 30 → match
    near = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
        }
    )
    assert near["closes_half_kelly_pct"] == 31.2
    assert near["closes_half_kelly_vs_cap"] == "match"
    assert near["closes_half_kelly_cap_bit"] == (
        "A half-Kelly vs cap match · 31.2% vs 30%"
    )


def test_promote_ab_glance_half_kelly_cap_under_warns_but_ready() -> None:
    """Half-Kelly below concentration cap → warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "fees": 4.0,
            "realized_pnl": 40.0,
            "net_after_all_fees": 36.0,
            "wins": 2,
            "losses": 2,
            "avg_win": 40.0,
            "avg_loss": 20.0,
            "last_sell": "2026-09-12",
        },
    )
    assert g["closes_half_kelly_pct"] == 12.5
    assert g["closes_half_kelly_cap_under"] is True
    assert g["closes_half_kelly_vs_cap"] == "under"
    assert "A half-Kelly vs cap under · 12.5% vs 30%" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True
    assert g["tone"] == "warn"


def test_window_a_quarter_kelly_vs_sizer() -> None:
    """Quarter of full Kelly vs the ~10% cash sizer (display only)."""
    from stock_checker.promote_ab import (
        WINDOW_A_HALF_KELLY_MATCH_PP,
        WINDOW_A_QUARTER_KELLY_FRAC,
        format_window_a_closes_quarter_kelly_bit,
        window_a_sample_readiness,
    )
    from stock_checker.risk_halts import DEFAULT_ENTRY_CASH_FRAC

    sizer = round(float(DEFAULT_ENTRY_CASH_FRAC) * 100.0, 1)
    assert sizer == 10.0
    assert WINDOW_A_QUARTER_KELLY_FRAC == 0.25
    assert WINDOW_A_HALF_KELLY_MATCH_PP == 5.0

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
        }
    )
    assert unknown["closes_quarter_kelly_pct"] is None
    assert unknown["closes_quarter_kelly_sizer_pct"] is None
    assert unknown["closes_quarter_kelly_vs"] == ""
    assert unknown["closes_quarter_kelly_bit"] == ""
    assert unknown["closes_quarter_kelly_under"] is False
    assert format_window_a_closes_quarter_kelly_bit(unknown) == ""
    assert format_window_a_closes_quarter_kelly_bit(None) == ""

    # 75% WR · payoff 2 → Kelly 62.5 → quarter 15.6 vs 10 → over
    # (half 31.2 also over — quarter still above sizer when edge is strong)
    over = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
        }
    )
    assert over["closes_kelly_pct"] == 62.5
    assert over["closes_half_kelly_pct"] == 31.2
    assert over["closes_quarter_kelly_pct"] == 15.6
    assert over["closes_quarter_kelly_sizer_pct"] == 10.0
    assert over["closes_quarter_kelly_vs"] == "over"
    assert over["closes_quarter_kelly_under"] is False
    assert over["closes_quarter_kelly_bit"] == (
        "A quarter-Kelly vs sizer over · 15.6% vs 10%"
    )

    # 50% WR · payoff 1.5 → Kelly 16.7 → quarter 4.2 vs 10 → under
    # (half 8.3 matches sizer — quarter shows the conservative fraction is thin)
    under = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 5,
            "losses": 5,
            "avg_win": 15.0,
            "avg_loss": 10.0,
        }
    )
    assert under["closes_half_kelly_pct"] == 8.3
    assert under["closes_half_kelly_vs"] == "match"
    assert under["closes_quarter_kelly_pct"] == 4.2
    assert under["closes_quarter_kelly_vs"] == "under"
    assert under["closes_quarter_kelly_under"] is True
    assert under["closes_quarter_kelly_bit"] == (
        "A quarter-Kelly vs sizer under · 4.2% vs 10%"
    )
    assert format_window_a_closes_quarter_kelly_bit(under) == under[
        "closes_quarter_kelly_bit"
    ]

    # 80% WR · payoff 1 → Kelly 60 → half 30 over · quarter 15 over
    # 60% WR · payoff 1 → Kelly 20 → quarter 5.0 vs 10 → match (δ=-5 not < -5)
    match = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 3,
            "losses": 2,
            "avg_win": 10.0,
            "avg_loss": 10.0,
        }
    )
    assert match["closes_kelly_pct"] == 20.0
    assert match["closes_quarter_kelly_pct"] == 5.0
    assert match["closes_quarter_kelly_vs"] == "match"
    assert match["closes_quarter_kelly_under"] is False
    assert match["closes_quarter_kelly_bit"] == (
        "A quarter-Kelly vs sizer match · 5% vs 10%"
    )

    # 80% WR · payoff 1 → Kelly 60 → quarter 15 vs 10 → over
    # Better: Kelly 40 → quarter 10 exact match
    # 70% WR · payoff ~1.43 → use wins/losses + avgs for Kelly 40
    # Kelly = p - (1-p)/R; want 0.40 → try 60% WR payoff 2: 0.6 - 0.4/2 = 0.4
    exact = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 3,
            "losses": 2,
            "avg_win": 20.0,
            "avg_loss": 10.0,
        }
    )
    assert exact["closes_kelly_pct"] == 40.0
    assert exact["closes_half_kelly_pct"] == 20.0
    assert exact["closes_half_kelly_vs"] == "over"  # half well above sizer
    assert exact["closes_quarter_kelly_pct"] == 10.0
    assert exact["closes_quarter_kelly_vs"] == "match"
    assert exact["closes_quarter_kelly_bit"] == (
        "A quarter-Kelly vs sizer match · 10% vs 10%"
    )


def test_window_a_quarter_kelly_vs_equal_slot() -> None:
    """Quarter of full Kelly vs equal book slot ~20% (display only)."""
    from stock_checker.promote_ab import (
        WINDOW_A_EQUAL_SLOT_PCT,
        WINDOW_A_HALF_KELLY_MATCH_PP,
        format_window_a_closes_quarter_kelly_slot_bit,
        window_a_sample_readiness,
    )

    assert WINDOW_A_EQUAL_SLOT_PCT == 20.0
    assert WINDOW_A_HALF_KELLY_MATCH_PP == 5.0

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
        }
    )
    assert unknown["closes_quarter_kelly_slot_pct"] is None
    assert unknown["closes_quarter_kelly_vs_slot"] == ""
    assert unknown["closes_quarter_kelly_slot_bit"] == ""
    assert unknown["closes_quarter_kelly_slot_under"] is False
    assert format_window_a_closes_quarter_kelly_slot_bit(unknown) == ""
    assert format_window_a_closes_quarter_kelly_slot_bit(None) == ""

    # 75% WR · payoff 2 → Kelly 62.5 → quarter 15.6 vs 20 → match (δ=-4.4)
    # (quarter over sizer but still within ±5pp of equal slot)
    match_strong = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
        }
    )
    assert match_strong["closes_quarter_kelly_pct"] == 15.6
    assert match_strong["closes_quarter_kelly_vs"] == "over"  # vs sizer
    assert match_strong["closes_quarter_kelly_slot_pct"] == 20.0
    assert match_strong["closes_quarter_kelly_vs_slot"] == "match"
    assert match_strong["closes_quarter_kelly_slot_under"] is False
    assert match_strong["closes_quarter_kelly_slot_bit"] == (
        "A quarter-Kelly vs slot match · 15.6% vs 20%"
    )

    # 60% WR · payoff 2 → Kelly 40 → quarter 10 vs 20 → under
    under = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 3,
            "losses": 2,
            "avg_win": 20.0,
            "avg_loss": 10.0,
        }
    )
    assert under["closes_kelly_pct"] == 40.0
    assert under["closes_quarter_kelly_pct"] == 10.0
    assert under["closes_quarter_kelly_vs"] == "match"  # vs sizer exact
    assert under["closes_quarter_kelly_vs_slot"] == "under"
    assert under["closes_quarter_kelly_slot_under"] is True
    assert under["closes_quarter_kelly_slot_bit"] == (
        "A quarter-Kelly vs slot under · 10% vs 20%"
    )
    assert format_window_a_closes_quarter_kelly_slot_bit(under) == under[
        "closes_quarter_kelly_slot_bit"
    ]

    # 80% WR · payoff 1 → Kelly 60 → quarter 15 vs 20 → match (δ=-5)
    match = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 4,
            "losses": 1,
            "avg_win": 10.0,
            "avg_loss": 10.0,
        }
    )
    assert match["closes_kelly_pct"] == 60.0
    assert match["closes_quarter_kelly_pct"] == 15.0
    assert match["closes_quarter_kelly_vs_slot"] == "match"
    assert match["closes_quarter_kelly_slot_under"] is False
    assert match["closes_quarter_kelly_slot_bit"] == (
        "A quarter-Kelly vs slot match · 15% vs 20%"
    )

    # Kelly 80 → quarter 20 exact match vs slot
    # 80% WR · payoff 2: 0.8 - 0.2/2 = 0.7 → 70; need 80
    # p - (1-p)/R = 0.8 → try 90% WR payoff 1: 0.9 - 0.1/1 = 0.8
    exact = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 9,
            "losses": 1,
            "avg_win": 10.0,
            "avg_loss": 10.0,
        }
    )
    assert exact["closes_kelly_pct"] == 80.0
    assert exact["closes_quarter_kelly_pct"] == 20.0
    assert exact["closes_quarter_kelly_vs_slot"] == "match"
    assert exact["closes_quarter_kelly_slot_bit"] == (
        "A quarter-Kelly vs slot match · 20% vs 20%"
    )


def test_window_a_quarter_kelly_vs_conc_cap() -> None:
    """Quarter of full Kelly vs soft name cap ~30% (display only)."""
    from stock_checker.promote_ab import (
        WINDOW_A_CONC_CAP_PCT,
        WINDOW_A_HALF_KELLY_MATCH_PP,
        format_window_a_closes_quarter_kelly_cap_bit,
        window_a_sample_readiness,
    )

    assert WINDOW_A_CONC_CAP_PCT == 30.0
    assert WINDOW_A_HALF_KELLY_MATCH_PP == 5.0

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
        }
    )
    assert unknown["closes_quarter_kelly_cap_pct"] is None
    assert unknown["closes_quarter_kelly_vs_cap"] == ""
    assert unknown["closes_quarter_kelly_cap_bit"] == ""
    assert unknown["closes_quarter_kelly_cap_under"] is False
    assert format_window_a_closes_quarter_kelly_cap_bit(unknown) == ""
    assert format_window_a_closes_quarter_kelly_cap_bit(None) == ""

    # 75% WR · payoff 2 → Kelly 62.5 → quarter 15.6 vs 20 match, vs 30 under
    under = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
        }
    )
    assert under["closes_quarter_kelly_pct"] == 15.6
    assert under["closes_quarter_kelly_vs_slot"] == "match"
    assert under["closes_quarter_kelly_cap_pct"] == 30.0
    assert under["closes_quarter_kelly_vs_cap"] == "under"
    assert under["closes_quarter_kelly_cap_under"] is True
    assert under["closes_quarter_kelly_cap_bit"] == (
        "A quarter-Kelly vs cap under · 15.6% vs 30%"
    )
    assert format_window_a_closes_quarter_kelly_cap_bit(under) == under[
        "closes_quarter_kelly_cap_bit"
    ]

    # 100% WR · payoff 2 → Kelly 100 → quarter 25 vs 30 → match (δ=-5)
    match = window_a_sample_readiness(
        {
            "trades": 8,
            "buys": 4,
            "sells": 4,
            "wins": 4,
            "losses": 0,
            "payoff_ratio": 2.0,
        }
    )
    assert match["closes_kelly_pct"] == 100.0
    assert match["closes_quarter_kelly_pct"] == 25.0
    assert match["closes_quarter_kelly_vs_cap"] == "match"
    assert match["closes_quarter_kelly_cap_under"] is False
    assert match["closes_quarter_kelly_cap_bit"] == (
        "A quarter-Kelly vs cap match · 25% vs 30%"
    )


def test_promote_ab_glance_quarter_kelly_cap_under_warns_but_ready() -> None:
    """Quarter-Kelly below name cap → warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 4.0,
            "realized_pnl": 40.0,
            "net_after_all_fees": 36.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-12",
        },
    )
    assert g["closes_quarter_kelly_pct"] == 15.6
    assert g["closes_quarter_kelly_vs_slot"] == "match"
    assert g["closes_quarter_kelly_vs_cap"] == "under"
    assert g["closes_quarter_kelly_cap_under"] is True
    assert "A quarter-Kelly vs cap under · 15.6% vs 30%" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True
    assert g["tone"] == "warn"


def test_promote_ab_glance_quarter_kelly_under_warns_but_ready() -> None:
    """Quarter-Kelly below cash sizer → warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "fees": 4.0,
            "realized_pnl": 40.0,
            "net_after_all_fees": 36.0,
            "wins": 5,
            "losses": 5,
            "avg_win": 15.0,
            "avg_loss": 10.0,
            "last_sell": "2026-09-12",
        },
    )
    assert g["closes_quarter_kelly_pct"] == 4.2
    assert g["closes_quarter_kelly_under"] is True
    assert g["closes_quarter_kelly_vs"] == "under"
    assert "A quarter-Kelly vs sizer under · 4.2% vs 10%" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True
    assert g["tone"] == "warn"


def test_promote_ab_glance_quarter_kelly_slot_under_warns_but_ready() -> None:
    """Quarter-Kelly below equal slot → warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "fees": 4.0,
            "realized_pnl": 40.0,
            "net_after_all_fees": 36.0,
            "wins": 3,
            "losses": 2,
            "avg_win": 20.0,
            "avg_loss": 10.0,
            "last_sell": "2026-09-12",
        },
    )
    assert g["closes_quarter_kelly_pct"] == 10.0
    assert g["closes_quarter_kelly_vs"] == "match"  # vs sizer
    assert g["closes_quarter_kelly_vs_slot"] == "under"
    assert g["closes_quarter_kelly_slot_under"] is True
    assert "A quarter-Kelly vs slot under · 10% vs 20%" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True
    assert g["tone"] == "warn"


def test_promote_ab_glance_half_kelly_under_warns_but_ready() -> None:
    """Half-Kelly below the cash sizer → warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "fees": 4.0,
            "realized_pnl": 40.0,
            "net_after_all_fees": 36.0,
            "wins": 5,
            "losses": 5,
            "avg_win": 11.0,
            "avg_loss": 10.0,
            "gross_wins": 55.0,
            "gross_losses": 50.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_half_kelly_pct"] == 2.2
    assert g["closes_half_kelly_under"] is True
    assert g["closes_half_kelly_vs"] == "under"
    assert "A half-Kelly vs sizer under · 2.2% vs 10%" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True


def test_window_a_closes_net_profit_factor_triad() -> None:
    """Net PF = (gross_wins − fees) ÷ gross_losses (portfolio AI after gross PF)."""
    from stock_checker.promote_ab import (
        WINDOW_A_PROFIT_FACTOR_STRONG_RATIO,
        WINDOW_A_PROFIT_FACTOR_THIN_RATIO,
        format_window_a_closes_net_profit_factor_bit,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert unknown["closes_profit_factor"] == 6.0
    assert unknown["closes_net_profit_factor"] is None
    assert unknown["closes_net_profit_factor_bit"] == ""
    assert unknown["closes_net_profit_factor_thin"] is False
    assert format_window_a_closes_net_profit_factor_bit(unknown) == ""

    # gross 240/40 = 6×; fees 20 → net wins 220 → net PF 5.5× strong
    strong = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 200.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert strong["closes_profit_factor"] == 6.0
    assert strong["closes_net_gross_wins"] == 220.0
    assert strong["closes_net_profit_factor"] == 5.5
    assert strong["closes_net_profit_factor"] >= WINDOW_A_PROFIT_FACTOR_STRONG_RATIO
    assert strong["closes_net_profit_factor_severity"] == "strong"
    assert strong["closes_net_profit_factor_thin"] is False
    assert strong["closes_net_profit_factor_eats_edge"] is False
    assert strong["closes_net_profit_factor_bit"] == "A net PF strong · 5.5×"
    assert format_window_a_closes_net_profit_factor_bit(strong) == strong[
        "closes_net_profit_factor_bit"
    ]

    # gross 60/40 = 1.5×; fees 30 → net wins 30 → net PF 0.75× thin
    thin = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 30.0,
            "realized_pnl": 20.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 20.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert thin["closes_profit_factor"] == 1.5
    assert thin["closes_net_gross_wins"] == 30.0
    assert thin["closes_net_profit_factor"] == 0.75
    assert thin["closes_net_profit_factor"] < WINDOW_A_PROFIT_FACTOR_THIN_RATIO
    assert thin["closes_net_profit_factor_severity"] == "thin"
    assert thin["closes_net_profit_factor_thin"] is True
    assert thin["closes_net_profit_factor_bit"] == "A net PF thin · 0.8×"

    # mid: gross 60/40 = 1.5; fees 10 → net 50/40 = 1.25× ok
    mid = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 10.0,
            "realized_pnl": 20.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 20.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert mid["closes_net_profit_factor"] == 1.25
    assert (
        WINDOW_A_PROFIT_FACTOR_THIN_RATIO
        <= mid["closes_net_profit_factor"]
        < WINDOW_A_PROFIT_FACTOR_STRONG_RATIO
    )
    assert mid["closes_net_profit_factor_severity"] == ""
    assert mid["closes_net_profit_factor_thin"] is False
    assert mid["closes_net_profit_factor_bit"] == "A net PF · 1.2×"

    # gross PF strong, fees wipe wins → fees eat PF
    eats = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 250.0,
            "realized_pnl": 200.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert eats["closes_profit_factor"] == 6.0
    assert eats["closes_net_gross_wins"] == -10.0
    assert eats["closes_net_profit_factor"] is None
    assert eats["closes_net_profit_factor_eats_edge"] is True
    assert eats["closes_net_profit_factor_thin"] is True
    assert eats["closes_net_profit_factor_bit"] == "A net PF · fees eat PF"


def test_promote_ab_glance_closes_net_profit_factor_eats_edge_warns_but_ready() -> None:
    """Gross PF ok + fees wipe winners → warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 250.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": -50.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["sample_ready"] is True
    assert g["closes_net_profit_factor_eats_edge"] is True
    assert g["closes_net_profit_factor_thin"] is True
    assert "fees eat PF" in g["line"]
    assert g["tone"] == "warn"


def test_promote_ab_glance_closes_fee_take_thin_warns_but_ready() -> None:
    """Thin fee take → warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 10.0,
            "realized_pnl": 20.0,
            "net_after_all_fees": 10.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_fee_take"] == 47.5
    assert g["closes_fee_take_thin"] is True
    assert g["closes_fee_take_severity"] == "thin"
    assert "A fee take thin · €48/close" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True


def test_promote_ab_glance_closes_net_expectancy_eats_edge_warns_but_ready() -> None:
    """Gross+ / net− → fees eat edge warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 120.0,
            "realized_pnl": 100.0,
            "net_after_all_fees": -20.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "expectancy": 50.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_net_expectancy"] == -5.0
    assert g["closes_net_expectancy_neg"] is True
    assert g["closes_net_expectancy_eats_edge"] is True
    assert "A net expect −€5 · fees eat edge" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True


def test_promote_ab_glance_closes_win_rate_thin_warns_but_ready_for_b() -> None:
    """Thin win rate → warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 80.0,
            "net_after_all_fees": 60.0,
            "wins": 1,
            "losses": 3,
            "avg_win": 100.0,
            "avg_loss": 20.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_win_rate_pct"] == 25.0
    assert g["closes_win_rate_thin"] is True
    assert g["closes_win_rate_severity"] == "thin"
    assert "A win rate thin · 25%" in g["line"]
    assert "ready for B" in g["line"]
    assert "keep Window A" not in g["line"]
    assert g["b_ready"] is True


def test_promote_ab_glance_closes_profit_factor_thin_warns_but_ready_for_b() -> None:
    """Thin profit factor → warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 40.0,
            "net_after_all_fees": 20.0,
            "wins": 1,
            "losses": 3,
            "avg_win": 20.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_profit_factor"] == 0.17
    assert g["closes_profit_factor_thin"] is True
    assert g["closes_profit_factor_severity"] == "thin"
    assert "A PF thin · 0.2×" in g["line"]
    assert "ready for B" in g["line"]
    assert "keep Window A" not in g["line"]
    assert g["b_ready"] is True


def test_promote_ab_glance_closes_expectancy_neg_warns_but_ready_for_b() -> None:
    """Negative €/close expectancy → warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 40.0,
            "net_after_all_fees": 20.0,
            "wins": 1,
            "losses": 3,
            "avg_win": 20.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_expectancy"] == -25.0
    assert g["closes_expectancy_neg"] is True
    assert g["closes_expectancy_thin"] is False
    assert "A expectancy −€25" in g["line"]
    assert "A mixed · mostly losses" in g["line"]
    assert "ready for B" in g["line"]
    assert "keep Window A" not in g["line"]
    assert g["b_ready"] is True


def test_promote_ab_glance_closes_expectancy_thin_warns_but_ready_for_b() -> None:
    """Tiny positive €/close vs avg_loss → thin warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 10.0,
            "realized_pnl": 50.0,
            "net_after_all_fees": 40.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 15.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_expectancy"] == 1.25
    assert g["closes_expectancy_neg"] is False
    assert g["closes_expectancy_thin"] is True
    assert g["closes_expectancy_severity"] == "thin"
    assert "A expectancy thin · +€1" in g["line"]
    assert "ready for B" in g["line"]
    assert "keep Window A" not in g["line"]
    assert g["b_ready"] is True


def test_promote_ab_glance_closes_payoff_thin_warns_but_ready_for_b() -> None:
    """Mostly wins by count but thin € payoff → warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 100.0,
            "net_after_all_fees": 80.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 20.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_polarity"] == "mixed"
    assert g["closes_polarity_lean"] == "win_lean"
    assert g["closes_payoff_thin"] is True
    assert g["closes_payoff_severity"] == "thin"
    assert g["closes_payoff_ratio"] == 0.5
    assert "A mixed · mostly wins · 3w/1l" in g["line"]
    assert "A payoff thin · 0.5×" in g["line"]
    assert "A fresh closes" in g["line"]
    assert "ready for B" in g["line"]
    assert "keep Window A" not in g["line"]
    assert g["b_ready"] is True


def test_promote_ab_glance_closes_payoff_strong_ready_for_b() -> None:
    """Strong € payoff + fees comfortable → still ready for B.

    Quarter-Kelly vs the 30% name cap is under on this book, so tone warns.
    Payoff itself is not thin.
    """
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": 160.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_quarter_kelly_cap_under"] is True
    assert "A quarter-Kelly vs cap under" in g["line"]
    assert g["closes_payoff_thin"] is False
    assert g["closes_payoff_severity"] == "strong"
    assert g["closes_payoff_ratio"] == 2.0
    assert g["closes_expectancy"] == 50.0
    assert g["closes_expectancy_neg"] is False
    assert g["closes_expectancy_thin"] is False
    assert g["closes_expectancy_severity"] == "strong"
    assert "A payoff strong · 2×" in g["line"]
    assert "A expectancy strong · +€50" in g["line"]
    assert "A PF strong · 6×" in g["line"]
    assert g["closes_profit_factor"] == 6.0
    assert g["closes_profit_factor_severity"] == "strong"
    assert g["closes_profit_factor_thin"] is False
    assert "A mixed · mostly wins · 3w/1l" in g["line"]
    assert "A fees comfortable" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True


def test_promote_ab_glance_closes_loss_lean_warns_but_ready_for_b() -> None:
    """Mixed mostly losses → A mixed · mostly losses · warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 20.0,
            "realized_pnl": 40.0,
            "net_after_all_fees": 20.0,
            "wins": 1,
            "losses": 3,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_polarity"] == "mixed"
    assert g["closes_polarity_lean"] == "loss_lean"
    assert g["closes_loss_lean"] is True
    assert g["closes_all_loss"] is False
    assert g["fees_ok_severity"] == "thin"  # 20/40 = 0.5×
    assert "A mixed · mostly losses · 1w/3l" in g["line"]
    assert "A fees thin" in g["line"]
    assert "A fresh closes" in g["line"]
    assert "ready for B" in g["line"]
    assert "keep Window A" not in g["line"]
    assert g["b_ready"] is True


def test_promote_ab_glance_closes_all_loss_warns_but_ready_for_b() -> None:
    """All closed rounds red → A all-loss · warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": -80.0,
            "net_after_all_fees": -120.0,
            "wins": 0,
            "losses": 4,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["target_met"] is True
    assert g["sample_known"] is True
    assert g["sample_ready"] is True
    assert g["closes_polarity"] == "all_loss"
    assert g["closes_all_loss"] is True
    assert g["sample_fee_drag"] is True  # fees > realized (negative)
    assert "A all-loss · 0w/4l" in g["line"]
    assert "A fee drag" in g["line"]
    assert "A fresh closes" in g["line"]
    assert "ready for B" in g["line"]
    assert "keep Window A" not in g["line"]
    assert g["b_ready"] is True


def test_promote_ab_glance_closes_mixed_with_fees_comfortable() -> None:
    """Mixed mostly wins + fees comfortable → speak both · ready for B (no warn)."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": 160.0,
            "wins": 3,
            "losses": 1,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "ready"
    assert g["closes_polarity"] == "mixed"
    assert g["closes_polarity_lean"] == "win_lean"
    assert g["closes_loss_lean"] is False
    assert g["closes_all_loss"] is False
    assert g["fees_ok_severity"] == "comfortable"
    assert "A mixed · mostly wins · 3w/1l" in g["line"]
    assert "A fees comfortable · net +€160 · fees 0.2×" in g["line"]
    assert "A fresh closes" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True


def test_promote_ab_glance_aging_closes_warns_but_ready_for_b() -> None:
    """Fills + sells ok but last sell aging → warn · still ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": 160.0,
            "last_sell": "2026-09-08T12:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["target_met"] is True
    assert g["sample_known"] is True
    assert g["sample_ready"] is True
    assert g["sample_aging_closes"] is True
    assert g["sample_stale_closes"] is False
    assert g["sample_fees_ok"] is True
    assert g["closes_freshness"] == "aging"
    assert "A aging closes" in g["line"]
    assert "A fees comfortable · net +€160 · fees 0.2×" in g["line"]
    assert "ready for B" in g["line"]
    assert "keep Window A" not in g["line"]
    assert g["b_ready"] is True


def test_promote_ab_glance_fresh_closes_ready_for_b() -> None:
    """Fills + sells ok + last sell fresh → A fresh closes · ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": 160.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "ready"
    assert g["target_met"] is True
    assert g["sample_known"] is True
    assert g["sample_ready"] is True
    assert g["sample_fresh_closes"] is True
    assert g["sample_aging_closes"] is False
    assert g["sample_stale_closes"] is False
    assert g["sample_fees_ok"] is True
    assert g["closes_freshness"] == "fresh"
    assert "A fresh closes" in g["line"]
    assert "A fees comfortable" in g["line"]
    assert "ready for B" in g["line"]
    assert "keep Window A" not in g["line"]
    assert g["b_ready"] is True


def test_promote_ab_glance_stale_closes_keeps_window_a() -> None:
    """Fills + sells ok but last sell old → stale closes · keep Window A."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 13),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": 160.0,
            "last_sell": "2026-08-20T12:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["target_met"] is True
    assert g["sample_known"] is True
    assert g["sample_ready"] is False
    assert g["sample_stale_closes"] is True
    assert g["sample_open_only"] is False
    assert "A stale closes" in g["line"]
    assert "keep Window A" in g["line"]
    assert "ready for B" not in g["line"]
    assert g["b_ready"] is False


def test_summarize_window_trades_tracks_last_sell() -> None:
    from stock_checker.promote_ab import WINDOW_A_START_UTC, summarize_window_trades

    trades = [
        {
            "type": "BUY",
            "symbol": "AAPL",
            "timestamp": "2026-08-13T10:00:00+00:00",
            "commission": 1.0,
        },
        {
            "type": "SELL",
            "symbol": "AAPL",
            "timestamp": "2026-08-15T10:00:00+00:00",
            "commission": 1.0,
            "profit_loss": 10.0,
        },
        {
            "type": "SELL",
            "symbol": "MSFT",
            "timestamp": "2026-08-18T10:00:00+00:00",
            "commission": 1.0,
            "profit_loss": -5.0,
        },
        {
            "type": "BUY",
            "symbol": "MSFT",
            "timestamp": "2026-08-20T10:00:00+00:00",
            "commission": 1.0,
        },
    ]
    s = summarize_window_trades(trades, start=WINDOW_A_START_UTC)
    assert s["sells"] == 2
    assert s["last_sell"] == "2026-08-18T10:00:00+00:00"
    shuffled = [trades[0], trades[2], trades[1], trades[3]]
    s2 = summarize_window_trades(shuffled, start=WINDOW_A_START_UTC)
    assert s2["last_sell"] == "2026-08-18T10:00:00+00:00"
    assert s["loss_streak"] == 1
    assert s2["loss_streak"] == 1
    assert s["loss_streak_max"] == 1
    assert s2["loss_streak_max"] == 1
    assert s["loss_streak_mean"] == 1.0
    assert s2["loss_streak_mean"] == 1.0
    assert s["loss_streak_median"] == 1.0
    assert s2["loss_streak_median"] == 1.0
    assert s["loss_streak_runs"] == 1
    assert s2["loss_streak_runs"] == 1
    assert s["win_streak"] == 0
    assert s2["win_streak"] == 0
    assert s["win_streak_max"] == 1
    assert s2["win_streak_max"] == 1
    assert s["win_streak_mean"] == 1.0
    assert s2["win_streak_mean"] == 1.0
    assert s["win_streak_runs"] == 1
    assert s2["win_streak_runs"] == 1
    assert s["flat_closes"] == 0
    assert s2["flat_closes"] == 0


def test_promote_ab_glance_open_only_keeps_window_a() -> None:
    """Fills ≥10 but 0 sells → open-only · keep Window A (net needs closes)."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 13),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 12,
            "sells": 0,
            "fees": 40.0,
            "realized_pnl": 0.0,
            "net_after_all_fees": -40.0,
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["target_met"] is True
    assert g["sample_known"] is True
    assert g["sample_ready"] is False
    assert g["sample_open_only"] is True
    assert g["sample_thin_closes"] is False
    assert g["sample_buys"] == 12
    assert g["sample_sells"] == 0
    assert g["a_fill_progress_bit"] == "12/10 fills · 0/3 sells"
    assert "0/3 sells" in g["line"]
    assert "A open-only" in g["line"]
    assert "0 sells" in g["line"]
    assert "keep Window A" in g["line"]
    assert "ready for B" not in g["line"]
    assert "sample ready" not in g["line"]
    assert g["b_ready"] is False


def test_promote_ab_glance_thin_closes_keeps_window_a() -> None:
    """Fills ≥10 but sparse sells → thin closes · keep Window A."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 10,
            "sells": 2,
            "fees": 40.0,
            "realized_pnl": 50.0,
            "net_after_all_fees": 10.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["target_met"] is True
    assert g["sample_known"] is True
    assert g["sample_ready"] is False
    assert g["sample_open_only"] is False
    assert g["sample_thin_closes"] is True
    assert g["sample_fresh_closes"] is False
    assert g["sample_sells"] == 2
    assert g["a_fill_progress_bit"] == "12/10 fills · 2/3 sells"
    assert "A thin closes" in g["line"]
    assert "2/3 sells" in g["line"]
    assert "2 sells" in g["line"]
    assert "keep Window A" in g["line"]
    assert "building closes" not in g["line"]  # day target met → thin-closes warn
    assert "ready for B" not in g["line"]
    assert "A fresh closes" not in g["line"]
    assert g["b_ready"] is False


def test_promote_ab_glance_ready_for_b_when_fills_meet_floor() -> None:
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 13),
        open_positions=2,
        window_stats={
            "trades": 12,
            "fees": 40.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": 160.0,
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "ready"
    assert g["sample_ready"] is True
    assert g["sample_fills"] == 12
    assert g["a_fill_progress_bit"] == "12/10 fills"
    assert "12/10 fills" in g["line"]
    assert "ready for B" in g["line"]
    assert "A thin" not in g["line"]
    assert g["b_ready"] is True
    assert g["b_blockers"] == []


def test_window_b_readiness_protocol_drift() -> None:
    from stock_checker.promote_ab import (
        format_window_b_block_bit,
        window_b_readiness,
    )

    ok = window_b_readiness(
        max_positions=5,
        open_positions=3,
        min_hold_hours=24,
        fee_preset="revolut_standard",
    )
    assert ok["ready"] is True
    assert ok["blockers"] == []
    assert format_window_b_block_bit(ok["blockers"]) == ""

    drift = window_b_readiness(max_positions=8, open_positions=8)
    assert drift["ready"] is False
    assert "max pos 8≠5" in drift["blockers"]
    assert "8 open >5" in drift["blockers"]
    bit = format_window_b_block_bit(drift["blockers"])
    assert bit.startswith("B blocked ·")
    assert "max pos 8≠5" in bit

    knobs = window_b_readiness(
        max_positions=5,
        open_positions=3,
        min_hold_hours=4,
        fee_preset="revolut_ultra",
    )
    assert knobs["ready"] is False
    assert "hold 4h≠24h" in knobs["blockers"]
    assert "fee revolut_ultra≠standard" in knobs["blockers"]

    gates = window_b_readiness(
        max_positions=5,
        open_positions=3,
        min_hold_hours=24,
        fee_preset="revolut_standard",
        regime_gate=False,
        rs_gate=True,
        breadth_gate=False,
        ai_mode="validate",
    )
    assert gates["ready"] is False
    assert "regime off≠on" in gates["blockers"]
    assert "breadth off≠on" in gates["blockers"]
    assert "RS off≠on" not in gates["blockers"]
    assert not any(b.startswith("AI ") for b in gates["blockers"])

    ai = window_b_readiness(
        max_positions=5,
        open_positions=3,
        min_hold_hours=24,
        fee_preset="revolut_standard",
        regime_gate=True,
        rs_gate=True,
        breadth_gate=True,
        ai_mode="full",
    )
    assert ai["ready"] is False
    assert "AI full≠validate" in ai["blockers"]
    assert format_window_b_block_bit(ai["blockers"]) == "B blocked · AI full≠validate"

    ai_ok = window_b_readiness(
        max_positions=5,
        open_positions=3,
        min_hold_hours=24,
        fee_preset="revolut_standard",
        ai_mode="validate",
        ai_multi_role=True,
    )
    assert ai_ok["ready"] is True
    assert ai_ok["protocol_ai_mode"] == "validate"
    assert ai_ok["protocol_ai_multi_role"] is True

    multi = window_b_readiness(
        max_positions=5,
        open_positions=3,
        min_hold_hours=24,
        fee_preset="revolut_standard",
        regime_gate=True,
        rs_gate=True,
        breadth_gate=True,
        ai_mode="validate",
        ai_multi_role=False,
    )
    assert multi["ready"] is False
    assert "multi-role off≠on" in multi["blockers"]
    assert (
        format_window_b_block_bit(multi["blockers"])
        == "B blocked · multi-role off≠on"
    )

    cadence = window_b_readiness(
        max_positions=5,
        open_positions=3,
        min_hold_hours=24,
        fee_preset="revolut_standard",
        regime_gate=True,
        rs_gate=True,
        breadth_gate=True,
        ai_mode="validate",
        ai_multi_role=True,
        scan_interval_min=5,
        trade_interval_min=1,
    )
    assert cadence["ready"] is False
    assert "scan 5m<15m" in cadence["blockers"]
    assert "trade 1m<5m" in cadence["blockers"]
    assert cadence["protocol_scan_interval_min"] == 15
    assert cadence["protocol_trade_interval_min"] == 5

    cadence_ok = window_b_readiness(
        max_positions=5,
        open_positions=3,
        scan_interval_min=15,
        trade_interval_min=5,
    )
    assert cadence_ok["ready"] is True
    assert not any(b.startswith("scan ") for b in cadence_ok["blockers"])
    assert not any(b.startswith("trade ") for b in cadence_ok["blockers"])


def test_promote_ab_glance_b_blocked_on_max_pos_drift() -> None:
    g = build_promote_ab_glance(
        {"promote_experiment_strategy": False, "max_positions": 8},
        as_of=date(2026, 9, 13),
        open_positions=8,
        window_stats={
            "trades": 30,
            "fees": 575.0,
            "realized_pnl": 2788.0,
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["target_met"] is True
    assert g["b_ready"] is False
    assert "B blocked" in g["line"]
    assert "max pos 8≠5" in g["line"]
    assert "ready for B" not in g["line"]


def test_promote_ab_glance_b_blocked_on_hold_or_fee_drift() -> None:
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 12,
            "fee_preset": "spot_like",
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 30,
            "fees": 575.0,
            "realized_pnl": 2788.0,
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["b_ready"] is False
    assert "B blocked" in g["line"]
    assert "hold 12h≠24h" in g["b_blockers"]
    assert "fee spot_like≠standard" in g["b_blockers"]
    assert "hold 12h≠24h" in g["line"]
    assert "ready for B" not in g["line"]


def test_promote_ab_glance_b_blocked_on_gate_drift() -> None:
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": False,
            "breadth_gate": True,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 30,
            "fees": 575.0,
            "realized_pnl": 2788.0,
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["b_ready"] is False
    assert "B blocked" in g["line"]
    assert "RS off≠on" in g["b_blockers"]
    assert "ready for B" not in g["line"]


def test_promote_ab_glance_b_blocked_on_ai_mode_drift() -> None:
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "off",
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 30,
            "fees": 575.0,
            "realized_pnl": 2788.0,
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["b_ready"] is False
    assert "B blocked" in g["line"]
    assert "AI off≠validate" in g["b_blockers"]
    assert "AI off≠validate" in g["line"]
    assert "ready for B" not in g["line"]


def test_promote_ab_glance_b_blocked_on_multi_role_drift() -> None:
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": False,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 30,
            "fees": 575.0,
            "realized_pnl": 2788.0,
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["b_ready"] is False
    assert "B blocked" in g["line"]
    assert "multi-role off≠on" in g["b_blockers"]
    assert "multi-role off≠on" in g["line"]
    assert "ready for B" not in g["line"]


def test_promote_ab_glance_b_blocked_on_cadence_drift() -> None:
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 5,
            "trade_interval_min": 1,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 30,
            "fees": 575.0,
            "realized_pnl": 2788.0,
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["b_ready"] is False
    assert "B blocked" in g["line"]
    assert "scan 5m<15m" in g["b_blockers"]
    assert "trade 1m<5m" in g["b_blockers"]
    assert "scan 5m<15m" in g["line"]
    assert "ready for B" not in g["line"]


def test_window_a_practical_kelly_pick() -> None:
    """One practical Kelly pick after the half/quarter comparisons."""
    from stock_checker.promote_ab import (
        format_window_a_closes_practical_kelly_bit,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
        }
    )
    assert unknown["closes_practical_kelly"] == ""
    assert unknown["closes_practical_kelly_pct"] is None
    assert unknown["closes_practical_kelly_bit"] == ""
    assert unknown["closes_practical_kelly_cut"] is False
    assert format_window_a_closes_practical_kelly_bit(unknown) == ""
    assert format_window_a_closes_practical_kelly_bit(None) == ""

    # 45% WR · payoff 1.5 → Kelly 8.3 → half 4.2 under sizer → cut
    cut = window_a_sample_readiness(
        {
            "trades": 20,
            "buys": 10,
            "sells": 10,
            "wins": 9,
            "losses": 11,
            "avg_win": 15.0,
            "avg_loss": 10.0,
        }
    )
    assert cut["closes_half_kelly_pct"] == 4.2
    assert cut["closes_half_kelly_vs"] == "under"
    assert cut["closes_practical_kelly"] == "half"
    assert cut["closes_practical_kelly_pct"] == 4.2
    assert cut["closes_practical_kelly_cut"] is True
    assert cut["closes_practical_kelly_bit"] == (
        "A practical Kelly half · cut · 4.2%"
    )

    # 50% WR · payoff 1.5 → half 8.3 matches sizer
    half = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 5,
            "losses": 5,
            "avg_win": 15.0,
            "avg_loss": 10.0,
        }
    )
    assert half["closes_half_kelly_vs"] == "match"
    assert half["closes_practical_kelly"] == "half"
    assert half["closes_practical_kelly_pct"] == 8.3
    assert half["closes_practical_kelly_cut"] is False
    assert half["closes_practical_kelly_bit"] == "A practical Kelly half · 8.3%"
    assert format_window_a_closes_practical_kelly_bit(half) == half[
        "closes_practical_kelly_bit"
    ]

    # 60% WR · payoff 2 → half 20 over · quarter 10 fits
    quarter = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 3,
            "losses": 2,
            "avg_win": 20.0,
            "avg_loss": 10.0,
        }
    )
    assert quarter["closes_half_kelly_vs"] == "over"
    assert quarter["closes_quarter_kelly_vs"] == "match"
    assert quarter["closes_practical_kelly"] == "quarter"
    assert quarter["closes_practical_kelly_pct"] == 10.0
    assert quarter["closes_practical_kelly_cut"] is False
    assert quarter["closes_practical_kelly_bit"] == (
        "A practical Kelly quarter · 10%"
    )

    # 75% WR · payoff 2 → quarter 15.6 over sizer → cash slice binds
    sizer = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "avg_win": 80.0,
            "avg_loss": 40.0,
        }
    )
    assert sizer["closes_quarter_kelly_vs"] == "over"
    assert sizer["closes_practical_kelly"] == "sizer"
    assert sizer["closes_practical_kelly_pct"] == 10.0
    assert sizer["closes_practical_kelly_cut"] is False
    assert sizer["closes_practical_kelly_bit"] == "A practical Kelly sizer · 10%"

    # Payoff below breakeven → f* ≤ 0
    none = window_a_sample_readiness(
        {
            "trades": 8,
            "buys": 4,
            "sells": 4,
            "wins": 1,
            "losses": 3,
            "avg_win": 10.0,
            "avg_loss": 20.0,
        }
    )
    assert none["closes_kelly_neg"] is True
    assert none["closes_practical_kelly"] == "none"
    assert none["closes_practical_kelly_pct"] is None
    assert none["closes_practical_kelly_cut"] is True
    assert none["closes_practical_kelly_bit"] == "A practical Kelly none"


def test_promote_ab_glance_practical_kelly_quarter_ready() -> None:
    """Quarter pick speaks on the glance and does not block ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "fees": 10.0,
            "realized_pnl": 80.0,
            "net_after_all_fees": 70.0,
            "wins": 3,
            "losses": 2,
            "avg_win": 20.0,
            "avg_loss": 10.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["closes_practical_kelly"] == "quarter"
    assert g["closes_practical_kelly_cut"] is False
    assert "A practical Kelly quarter · 10%" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True


def test_promote_ab_glance_practical_kelly_cut_warns_but_ready() -> None:
    """Half · cut warns. It does not block ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 20,
            "buys": 10,
            "sells": 10,
            "fees": 10.0,
            "realized_pnl": 40.0,
            "net_after_all_fees": 30.0,
            "wins": 9,
            "losses": 11,
            "avg_win": 15.0,
            "avg_loss": 10.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_practical_kelly"] == "half"
    assert g["closes_practical_kelly_cut"] is True
    assert "A practical Kelly half · cut · 4.2%" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True


def test_window_a_kelly_sample_size() -> None:
    """Kelly from few closes is thin. Ten or more decided closes is ok."""
    from stock_checker.promote_ab import (
        WINDOW_A_KELLY_SAMPLE_MIN,
        format_window_a_closes_kelly_sample_bit,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
        }
    )
    assert unknown["closes_kelly_sample"] == ""
    assert unknown["closes_kelly_sample_n"] is None
    assert unknown["closes_kelly_sample_bit"] == ""
    assert unknown["closes_kelly_sample_thin"] is False
    assert format_window_a_closes_kelly_sample_bit(unknown) == ""
    assert format_window_a_closes_kelly_sample_bit(None) == ""

    thin = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "wins": 3,
            "losses": 2,
            "avg_win": 20.0,
            "avg_loss": 10.0,
        }
    )
    assert thin["closes_kelly_pct"] is not None
    assert thin["closes_kelly_sample_n"] == 5
    assert thin["closes_kelly_sample_n"] < WINDOW_A_KELLY_SAMPLE_MIN
    assert thin["closes_kelly_sample"] == "thin"
    assert thin["closes_kelly_sample_thin"] is True
    assert thin["closes_kelly_sample_bit"] == "A Kelly sample thin · 5 closes <10"
    assert format_window_a_closes_kelly_sample_bit(thin) == thin[
        "closes_kelly_sample_bit"
    ]

    ok = window_a_sample_readiness(
        {
            "trades": 24,
            "buys": 12,
            "sells": 12,
            "wins": 8,
            "losses": 4,
            "avg_win": 20.0,
            "avg_loss": 10.0,
        }
    )
    assert ok["closes_kelly_sample_n"] == 12
    assert ok["closes_kelly_sample"] == "ok"
    assert ok["closes_kelly_sample_thin"] is False
    assert ok["closes_kelly_sample_bit"] == "A Kelly sample ok · 12 closes"


def test_promote_ab_glance_kelly_sample_thin_warns_but_ready() -> None:
    """A thin Kelly sample warns. It does not block ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 7,
            "sells": 5,
            "fees": 10.0,
            "realized_pnl": 80.0,
            "net_after_all_fees": 70.0,
            "wins": 3,
            "losses": 2,
            "avg_win": 20.0,
            "avg_loss": 10.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_kelly_sample"] == "thin"
    assert g["closes_kelly_sample_thin"] is True
    assert "A Kelly sample thin · 5 closes <10" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True


def test_window_a_loss_streak_quiet_and_hot() -> None:
    """Win/lose counts ≠ a current losing run. Hot warns. It does not block B."""
    from stock_checker.promote_ab import (
        WINDOW_A_LOSS_STREAK_HOT,
        ending_loss_streak,
        format_window_a_closes_loss_streak_bit,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 2,
            "losses": 2,
        }
    )
    assert unknown["closes_loss_streak"] is None
    assert unknown["closes_loss_streak_bit"] == ""
    assert unknown["closes_loss_streak_hot"] is False
    assert format_window_a_closes_loss_streak_bit(unknown) == ""
    assert format_window_a_closes_loss_streak_bit(None) == ""

    quiet = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "loss_streak": 0,
        }
    )
    assert quiet["closes_loss_streak"] == 0
    assert quiet["closes_loss_streak"] < WINDOW_A_LOSS_STREAK_HOT
    assert quiet["closes_loss_streak_hot"] is False
    assert quiet["closes_loss_streak_bit"] == "A loss streak quiet · 0"
    assert format_window_a_closes_loss_streak_bit(quiet) == quiet[
        "closes_loss_streak_bit"
    ]

    one = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 2,
            "losses": 2,
            "loss_streak": 1,
        }
    )
    assert one["closes_loss_streak_bit"] == "A loss streak quiet · 1"
    assert one["closes_loss_streak_hot"] is False

    hot = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 2,
            "losses": 4,
            "loss_streak": 3,
        }
    )
    assert hot["closes_loss_streak"] == 3
    assert hot["closes_loss_streak"] >= WINDOW_A_LOSS_STREAK_HOT
    assert hot["closes_loss_streak_hot"] is True
    assert hot["closes_loss_streak_bit"] == "A loss streak hot · 3"

    # Newest two losses after an older win. List order is not time order.
    streak = ending_loss_streak(
        [
            {
                "timestamp": "2026-08-20T10:00:00+00:00",
                "profit_loss": -4.0,
            },
            {
                "timestamp": "2026-08-14T10:00:00+00:00",
                "profit_loss": 8.0,
            },
            {
                "timestamp": "2026-08-18T10:00:00+00:00",
                "profit_loss": 0.0,
            },
            {
                "timestamp": "2026-08-22T10:00:00+00:00",
                "profit_loss": -2.0,
            },
        ]
    )
    assert streak == 2
    assert ending_loss_streak([]) is None


def test_promote_ab_glance_loss_streak_hot_warns_but_ready() -> None:
    """A hot loss streak warns. It does not block ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "fees": 10.0,
            "realized_pnl": 80.0,
            "net_after_all_fees": 70.0,
            "wins": 3,
            "losses": 3,
            "avg_win": 40.0,
            "avg_loss": 10.0,
            "loss_streak": 2,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_loss_streak"] == 2
    assert g["closes_loss_streak_hot"] is True
    assert "A loss streak hot · 2" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True


def test_window_a_loss_streak_max_speaks_when_peak_exceeds_ending() -> None:
    """A later win hides an earlier loss run. Peak speaks only when max > ending."""
    from stock_checker.promote_ab import (
        WINDOW_A_LOSS_STREAK_HOT,
        format_window_a_closes_loss_streak_max_bit,
        max_loss_streak,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "loss_streak": 0,
        }
    )
    assert unknown["closes_loss_streak_max"] is None
    assert unknown["closes_loss_streak_max_bit"] == ""
    assert unknown["closes_loss_streak_max_hot"] is False
    assert format_window_a_closes_loss_streak_max_bit(unknown) == ""
    assert format_window_a_closes_loss_streak_max_bit(None) == ""

    same = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "loss_streak": 2,
            "loss_streak_max": 2,
        }
    )
    assert same["closes_loss_streak_max"] is None
    assert same["closes_loss_streak_max_bit"] == ""
    assert same["closes_loss_streak_max_hot"] is False

    quiet_peak = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "loss_streak": 0,
            "loss_streak_max": 1,
        }
    )
    assert quiet_peak["closes_loss_streak_max"] == 1
    assert quiet_peak["closes_loss_streak_max"] < WINDOW_A_LOSS_STREAK_HOT
    assert quiet_peak["closes_loss_streak_max_hot"] is False
    assert quiet_peak["closes_loss_streak_max_bit"] == "A loss streak max · 1"

    # Older three-loss storm, then a win. List order is not time order.
    peak = max_loss_streak(
        [
            {
                "timestamp": "2026-08-20T10:00:00+00:00",
                "profit_loss": -4.0,
            },
            {
                "timestamp": "2026-08-12T10:00:00+00:00",
                "profit_loss": -3.0,
            },
            {
                "timestamp": "2026-08-14T10:00:00+00:00",
                "profit_loss": -1.0,
            },
            {
                "timestamp": "2026-08-16T10:00:00+00:00",
                "profit_loss": 0.0,
            },
            {
                "timestamp": "2026-08-22T10:00:00+00:00",
                "profit_loss": 6.0,
            },
        ]
    )
    assert peak == 3
    assert max_loss_streak([]) is None


def test_promote_ab_glance_loss_streak_max_warns_but_ready() -> None:
    """A hot peak loss streak warns. It does not block ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "fees": 10.0,
            "realized_pnl": 80.0,
            "net_after_all_fees": 70.0,
            "wins": 4,
            "losses": 2,
            "avg_win": 30.0,
            "avg_loss": 10.0,
            "loss_streak": 0,
            "loss_streak_max": 3,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_loss_streak"] == 0
    assert g["closes_loss_streak_hot"] is False
    assert g["closes_loss_streak_max"] == 3
    assert g["closes_loss_streak_max_hot"] is True
    assert "A loss streak quiet · 0" in g["line"]
    assert "A loss streak max · 3" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True


def test_window_a_win_streak_quiet_and_hot() -> None:
    """Loss counts ≠ a current win run. Hot speaks. It does not warn or block B."""
    from stock_checker.promote_ab import (
        WINDOW_A_LOSS_STREAK_HOT,
        ending_win_streak,
        format_window_a_closes_win_streak_bit,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 2,
            "losses": 2,
        }
    )
    assert unknown["closes_win_streak"] is None
    assert unknown["closes_win_streak_bit"] == ""
    assert unknown["closes_win_streak_hot"] is False
    assert format_window_a_closes_win_streak_bit(unknown) == ""
    assert format_window_a_closes_win_streak_bit(None) == ""

    quiet = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "win_streak": 0,
        }
    )
    assert quiet["closes_win_streak"] == 0
    assert quiet["closes_win_streak"] < WINDOW_A_LOSS_STREAK_HOT
    assert quiet["closes_win_streak_hot"] is False
    assert quiet["closes_win_streak_bit"] == "A win streak quiet · 0"
    assert format_window_a_closes_win_streak_bit(quiet) == quiet[
        "closes_win_streak_bit"
    ]

    one = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "wins": 2,
            "losses": 2,
            "win_streak": 1,
        }
    )
    assert one["closes_win_streak_bit"] == "A win streak quiet · 1"
    assert one["closes_win_streak_hot"] is False

    hot = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 4,
            "losses": 2,
            "win_streak": 3,
        }
    )
    assert hot["closes_win_streak"] == 3
    assert hot["closes_win_streak"] >= WINDOW_A_LOSS_STREAK_HOT
    assert hot["closes_win_streak_hot"] is True
    assert hot["closes_win_streak_bit"] == "A win streak hot · 3"

    streak = ending_win_streak(
        [
            {
                "timestamp": "2026-08-20T10:00:00+00:00",
                "profit_loss": 4.0,
            },
            {
                "timestamp": "2026-08-14T10:00:00+00:00",
                "profit_loss": -8.0,
            },
            {
                "timestamp": "2026-08-18T10:00:00+00:00",
                "profit_loss": 0.0,
            },
            {
                "timestamp": "2026-08-22T10:00:00+00:00",
                "profit_loss": 2.0,
            },
        ]
    )
    assert streak == 2
    assert ending_win_streak([]) is None


def test_promote_ab_glance_win_streak_hot_speaks_but_ready() -> None:
    """A hot win streak speaks. It does not warn and does not block ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 40.0,
            "realized_pnl": 200.0,
            "net_after_all_fees": 160.0,
            "wins": 3,
            "losses": 1,
            "win_streak": 2,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "ready"
    assert g["closes_win_streak"] == 2
    assert g["closes_win_streak_hot"] is True
    assert "A win streak hot · 2" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True


def test_window_a_win_streak_max_speaks_when_peak_exceeds_ending() -> None:
    """A later loss hides an earlier win run. Peak speaks only when max > ending."""
    from stock_checker.promote_ab import (
        WINDOW_A_LOSS_STREAK_HOT,
        format_window_a_closes_win_streak_max_bit,
        max_win_streak,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 4,
            "losses": 2,
            "win_streak": 0,
        }
    )
    assert unknown["closes_win_streak_max"] is None
    assert unknown["closes_win_streak_max_bit"] == ""
    assert format_window_a_closes_win_streak_max_bit(None) == ""

    same = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 4,
            "losses": 2,
            "win_streak": 2,
            "win_streak_max": 2,
        }
    )
    assert same["closes_win_streak_max_bit"] == ""

    peak = max_win_streak(
        [
            {"timestamp": "2026-08-12T10:00:00+00:00", "profit_loss": 3.0},
            {"timestamp": "2026-08-14T10:00:00+00:00", "profit_loss": 1.0},
            {"timestamp": "2026-08-22T10:00:00+00:00", "profit_loss": -6.0},
        ]
    )
    assert peak == 2
    assert peak >= WINDOW_A_LOSS_STREAK_HOT
    assert max_win_streak([]) is None


def test_promote_ab_glance_win_streak_max_does_not_warn() -> None:
    """A hot peak win streak speaks. It does not warn or block ready for B."""
    knobs = {
        "promote_experiment_strategy": False,
        "max_positions": 5,
        "min_hold_hours": 24,
        "fee_preset": "revolut_standard",
        "regime_gate": True,
        "rs_gate": True,
        "breadth_gate": True,
        "ai_mode": "validate",
        "ai_multi_role": True,
        "scan_interval_min": 15,
        "trade_interval_min": 5,
    }
    base = {
        "trades": 12,
        "buys": 8,
        "sells": 4,
        "fees": 40.0,
        "realized_pnl": 200.0,
        "net_after_all_fees": 160.0,
        "wins": 3,
        "losses": 1,
        "win_streak": 0,
        "last_sell": "2026-09-11T15:00:00+00:00",
    }
    quiet = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats=base,
    )
    hot = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={**base, "win_streak_max": 3},
    )
    assert hot["ready"] is True
    assert hot["tone"] == quiet["tone"] == "ready"
    assert hot["closes_win_streak_max"] == 3
    assert "A win streak max · 3" in hot["line"]
    assert hot["b_ready"] is True


def test_window_a_flat_closes_warn_but_ready() -> None:
    """Zero-P&L sells inflate the sell meter. They warn and do not block B."""
    from stock_checker.promote_ab import (
        WINDOW_A_START_UTC,
        format_window_a_closes_flat_bit,
        summarize_window_trades,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
        }
    )
    assert unknown["closes_flat"] is None
    assert unknown["closes_flat_bit"] == ""
    assert unknown["closes_flat_warn"] is False
    assert format_window_a_closes_flat_bit(unknown) == ""
    assert format_window_a_closes_flat_bit(None) == ""

    quiet = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "flat_closes": 0,
        }
    )
    assert quiet["closes_flat"] is None
    assert quiet["closes_flat_bit"] == ""
    assert quiet["closes_flat_warn"] is False

    warned = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 2,
            "losses": 2,
            "flat_closes": 2,
        }
    )
    assert warned["closes_flat"] == 2
    assert warned["closes_flat_warn"] is True
    assert warned["closes_flat_bit"] == "A flats · 2"
    assert format_window_a_closes_flat_bit(warned) == "A flats · 2"

    trades = [
        {
            "type": "SELL",
            "symbol": "AAPL",
            "timestamp": "2026-08-15T10:00:00+00:00",
            "profit_loss": 10.0,
        },
        {
            "type": "SELL",
            "symbol": "MSFT",
            "timestamp": "2026-08-16T10:00:00+00:00",
            "profit_loss": 0.0,
        },
    ]
    s = summarize_window_trades(trades, start=WINDOW_A_START_UTC)
    assert s["sells"] == 2
    assert s["wins"] == 1
    assert s["losses"] == 0
    assert s["flat_closes"] == 1

    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "fees": 10.0,
            "realized_pnl": 80.0,
            "net_after_all_fees": 70.0,
            "wins": 3,
            "losses": 1,
            "flat_closes": 2,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_flat"] == 2
    assert g["closes_flat_warn"] is True
    assert "A flats · 2" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True

def test_window_a_loss_streak_mean_speaks_when_two_runs() -> None:
    """Typical loss-run length speaks only when there are two or more runs."""
    from stock_checker.promote_ab import (
        WINDOW_A_LOSS_STREAK_HOT,
        WINDOW_A_LOSS_STREAK_MEAN_MIN_RUNS,
        format_window_a_closes_loss_streak_mean_bit,
        loss_streak_run_count,
        mean_loss_streak,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "loss_streak": 1,
        }
    )
    assert unknown["closes_loss_streak_mean"] is None
    assert unknown["closes_loss_streak_mean_bit"] == ""
    assert unknown["closes_loss_streak_mean_hot"] is False
    assert format_window_a_closes_loss_streak_mean_bit(None) == ""

    one = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "loss_streak": 2,
            "loss_streak_mean": 2.0,
            "loss_streak_runs": 1,
        }
    )
    assert one["closes_loss_streak_mean_bit"] == ""
    assert 1 < WINDOW_A_LOSS_STREAK_MEAN_MIN_RUNS

    quiet = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "loss_streak": 1,
            "loss_streak_mean": 1.5,
            "loss_streak_runs": 2,
        }
    )
    assert quiet["closes_loss_streak_mean"] == 1.5
    assert quiet["closes_loss_streak_runs"] == 2
    assert quiet["closes_loss_streak_mean_hot"] is False
    assert quiet["closes_loss_streak_mean"] < WINDOW_A_LOSS_STREAK_HOT
    assert quiet["closes_loss_streak_mean_bit"] == "A loss streak mean · 1.5 · 2 runs"

    sells = [
        {"timestamp": "2026-08-12T10:00:00+00:00", "profit_loss": -2.0},
        {"timestamp": "2026-08-14T10:00:00+00:00", "profit_loss": 4.0},
        {"timestamp": "2026-08-16T10:00:00+00:00", "profit_loss": -1.0},
        {"timestamp": "2026-08-18T10:00:00+00:00", "profit_loss": -3.0},
        {"timestamp": "2026-08-20T10:00:00+00:00", "profit_loss": 0.0},
        {"timestamp": "2026-08-22T10:00:00+00:00", "profit_loss": 5.0},
    ]
    assert loss_streak_run_count(sells) == 2
    assert mean_loss_streak(sells) == 1.5
    assert mean_loss_streak([]) is None
    assert loss_streak_run_count([]) is None


def test_promote_ab_glance_loss_streak_mean_warns_but_ready() -> None:
    """A hot mean loss streak warns. It does not block ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "fees": 10.0,
            "realized_pnl": 80.0,
            "net_after_all_fees": 70.0,
            "wins": 3,
            "losses": 3,
            "avg_win": 40.0,
            "avg_loss": 10.0,
            "loss_streak": 1,
            "loss_streak_mean": 2.5,
            "loss_streak_runs": 2,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_loss_streak_mean"] == 2.5
    assert g["closes_loss_streak_runs"] == 2
    assert g["closes_loss_streak_mean_hot"] is True
    assert "A loss streak mean · 2.5 · 2 runs" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True

def test_window_a_loss_streak_median_speaks_when_mean_is_pulled() -> None:
    """Median speaks when ≥3 runs and it differs from the mean."""
    from stock_checker.promote_ab import (
        WINDOW_A_LOSS_STREAK_HOT,
        WINDOW_A_LOSS_STREAK_MEDIAN_MIN_RUNS,
        format_window_a_closes_loss_streak_median_bit,
        median_loss_streak,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "loss_streak": 1,
            "loss_streak_mean": 2.0,
            "loss_streak_runs": 3,
        }
    )
    assert unknown["closes_loss_streak_median"] is None
    assert unknown["closes_loss_streak_median_bit"] == ""
    assert unknown["closes_loss_streak_median_hot"] is False
    assert format_window_a_closes_loss_streak_median_bit(None) == ""

    two = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "loss_streak": 1,
            "loss_streak_mean": 1.5,
            "loss_streak_median": 1.0,
            "loss_streak_runs": 2,
        }
    )
    assert two["closes_loss_streak_median_bit"] == ""
    assert 2 < WINDOW_A_LOSS_STREAK_MEDIAN_MIN_RUNS

    same = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "loss_streak": 1,
            "loss_streak_mean": 1.0,
            "loss_streak_median": 1.0,
            "loss_streak_runs": 3,
        }
    )
    assert same["closes_loss_streak_median_bit"] == ""

    quiet = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "loss_streak": 1,
            "loss_streak_mean": 2.0,
            "loss_streak_median": 1.0,
            "loss_streak_runs": 3,
        }
    )
    assert quiet["closes_loss_streak_median"] == 1.0
    assert quiet["closes_loss_streak_median_hot"] is False
    assert quiet["closes_loss_streak_median"] < WINDOW_A_LOSS_STREAK_HOT
    assert quiet["closes_loss_streak_median_bit"] == "A loss streak med · 1.0 · 3 runs"

    sells = [
        {"timestamp": "2026-08-12T10:00:00+00:00", "profit_loss": -4.0},
        {"timestamp": "2026-08-13T10:00:00+00:00", "profit_loss": -3.0},
        {"timestamp": "2026-08-14T10:00:00+00:00", "profit_loss": -2.0},
        {"timestamp": "2026-08-15T10:00:00+00:00", "profit_loss": -1.0},
        {"timestamp": "2026-08-16T10:00:00+00:00", "profit_loss": 5.0},
        {"timestamp": "2026-08-18T10:00:00+00:00", "profit_loss": -1.0},
        {"timestamp": "2026-08-20T10:00:00+00:00", "profit_loss": 4.0},
        {"timestamp": "2026-08-22T10:00:00+00:00", "profit_loss": -1.0},
    ]
    assert median_loss_streak(sells) == 1.0
    assert median_loss_streak([]) is None


def test_promote_ab_glance_loss_streak_median_warns_but_ready() -> None:
    """A hot median loss streak warns. It does not block ready for B."""
    g = build_promote_ab_glance(
        {
            "promote_experiment_strategy": False,
            "max_positions": 5,
            "min_hold_hours": 24,
            "fee_preset": "revolut_standard",
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "ai_mode": "validate",
            "ai_multi_role": True,
            "scan_interval_min": 15,
            "trade_interval_min": 5,
        },
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "fees": 10.0,
            "realized_pnl": 80.0,
            "net_after_all_fees": 70.0,
            "wins": 3,
            "losses": 3,
            "avg_win": 40.0,
            "avg_loss": 10.0,
            "loss_streak": 1,
            "loss_streak_mean": 1.0,
            "loss_streak_median": 2.5,
            "loss_streak_runs": 3,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_loss_streak_median"] == 2.5
    assert g["closes_loss_streak_median_hot"] is True
    assert "A loss streak med · 2.5 · 3 runs" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True

def test_window_a_win_streak_mean_speaks_when_two_runs() -> None:
    """Typical win-run length speaks only when there are two or more runs."""
    from stock_checker.promote_ab import (
        WINDOW_A_LOSS_STREAK_HOT,
        WINDOW_A_LOSS_STREAK_MEAN_MIN_RUNS,
        format_window_a_closes_win_streak_mean_bit,
        mean_win_streak,
        win_streak_run_count,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "win_streak": 1,
        }
    )
    assert unknown["closes_win_streak_mean"] is None
    assert unknown["closes_win_streak_mean_bit"] == ""
    assert unknown["closes_win_streak_mean_hot"] is False
    assert format_window_a_closes_win_streak_mean_bit(None) == ""

    one = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "win_streak": 2,
            "win_streak_mean": 2.0,
            "win_streak_runs": 1,
        }
    )
    assert one["closes_win_streak_mean_bit"] == ""
    assert 1 < WINDOW_A_LOSS_STREAK_MEAN_MIN_RUNS

    quiet = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "win_streak": 1,
            "win_streak_mean": 1.5,
            "win_streak_runs": 2,
        }
    )
    assert quiet["closes_win_streak_mean"] == 1.5
    assert quiet["closes_win_streak_runs"] == 2
    assert quiet["closes_win_streak_mean_hot"] is False
    assert quiet["closes_win_streak_mean"] < WINDOW_A_LOSS_STREAK_HOT
    assert quiet["closes_win_streak_mean_bit"] == "A win streak mean · 1.5 · 2 runs"

    sells = [
        {"timestamp": "2026-08-12T10:00:00+00:00", "profit_loss": 2.0},
        {"timestamp": "2026-08-14T10:00:00+00:00", "profit_loss": -4.0},
        {"timestamp": "2026-08-16T10:00:00+00:00", "profit_loss": 1.0},
        {"timestamp": "2026-08-18T10:00:00+00:00", "profit_loss": 3.0},
        {"timestamp": "2026-08-20T10:00:00+00:00", "profit_loss": 0.0},
        {"timestamp": "2026-08-22T10:00:00+00:00", "profit_loss": -5.0},
    ]
    assert win_streak_run_count(sells) == 2
    assert mean_win_streak(sells) == 1.5
    assert mean_win_streak([]) is None
    assert win_streak_run_count([]) is None


def test_promote_ab_glance_win_streak_mean_does_not_warn() -> None:
    """A hot mean win streak speaks. It does not warn or block ready for B."""
    knobs = {
        "promote_experiment_strategy": False,
        "max_positions": 5,
        "min_hold_hours": 24,
        "fee_preset": "revolut_standard",
        "regime_gate": True,
        "rs_gate": True,
        "breadth_gate": True,
        "ai_mode": "validate",
        "ai_multi_role": True,
        "scan_interval_min": 15,
        "trade_interval_min": 5,
    }
    base = {
        "trades": 12,
        "buys": 6,
        "sells": 6,
        "fees": 10.0,
        "realized_pnl": 80.0,
        "net_after_all_fees": 70.0,
        "wins": 4,
        "losses": 2,
        "win_streak": 1,
        "win_streak_mean": 1.0,
        "win_streak_runs": 1,
        "last_sell": "2026-09-11T15:00:00+00:00",
    }
    quiet = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats=base,
    )
    hot = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={**base, "win_streak_mean": 2.5, "win_streak_runs": 2},
    )
    assert hot["ready"] is True
    assert hot["tone"] == quiet["tone"] == "ready"
    assert hot["closes_win_streak_mean"] == 2.5
    assert hot["closes_win_streak_runs"] == 2
    assert hot["closes_win_streak_mean_hot"] is True
    assert "A win streak mean · 2.5 · 2 runs" in hot["line"]
    assert "ready for B" in hot["line"]
    assert hot["b_ready"] is True

