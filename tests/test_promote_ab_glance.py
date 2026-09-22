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
    assert g["honesty_line"] == ""
    assert g["honesty_core"] == ""
    assert g["fees_line"] == ""
    assert g["polarity_line"] == ""
    assert g["kelly_line"] == ""
    assert g["streak_line"] == ""
    assert g["exit_mix_line"] == ""
    assert g["exit_euro_line"] == ""
    assert g["fee_pressure_line"] == ""
    assert g["align_nest_line"] == ""
    assert g["align_deep_line"] == ""
    assert g["edge_line"] == ""
    assert g["honesty_warns"] == []
    assert g["honesty_warn_count"] == 0
    assert g["honesty_folds"] == []
    assert g["honesty_fold_count"] == 0
    assert g["honesty_quiet_folds"] == []
    assert g["honesty_quiet_fold_count"] == 0
    assert g["summary_line"] == g["line"]
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
    assert s["loss_streak_min"] is None
    assert s["loss_streak_stdev"] is None
    assert s["loss_streak_cv"] is None
    assert s["loss_streak_runs"] == 0
    assert s["win_streak"] == 1
    assert s["win_streak_max"] == 1
    assert s["win_streak_mean"] == 1.0
    assert s["win_streak_median"] == 1.0
    assert s["win_streak_min"] == 1
    assert s["win_streak_stdev"] is None
    assert s["win_streak_cv"] is None
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
    assert "A fees ok" not in g["summary_line"]
    assert "A fresh closes" in g["summary_line"]
    assert "ready for B" in g["summary_line"]
    assert "A fees ok · net +€120 · fees 0.4×" in g["honesty_line"]
    assert "ready for B" not in g["honesty_line"]
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
    # Quiet fold inventory (portfolio AI speak-both-sides + xang1234).
    assert g["honesty_warns"] == []
    assert g["honesty_warn_count"] == 0
    assert g["fees_line"]
    fold_lines = [
        x
        for x in (
            g["fees_line"],
            g["polarity_line"],
            g["edge_line"],
            g["kelly_line"],
            g["streak_line"],
            g["exit_mix_line"],
            g["exit_euro_line"],
            g["fee_pressure_line"],
            g["align_nest_line"],
            g["align_deep_line"],
        )
        if (x or "").strip()
    ]
    assert g["honesty_fold_count"] == len(fold_lines)
    assert g["honesty_fold_count"] >= 1
    # Quiet names populated folds (MonsterDeveloper declutter after count).
    assert g["honesty_folds"]
    assert len(g["honesty_folds"]) == g["honesty_fold_count"]
    assert "fees" in g["honesty_folds"]
    assert all(isinstance(name, str) and name for name in g["honesty_folds"])
    # Fully calm: quiet folds == all populated folds.
    assert g["honesty_quiet_folds"] == g["honesty_folds"]
    assert g["honesty_quiet_fold_count"] == g["honesty_fold_count"]
    # Warn labels are a subset of populated fold labels when hot.
    assert set(g["honesty_warns"]).issubset(set(g["honesty_folds"]))


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
    assert "fees" in g["honesty_warns"]
    assert g["honesty_warn_count"] == len(g["honesty_warns"])
    assert g["honesty_warn_count"] >= 1
    assert g["honesty_fold_count"] >= g["honesty_warn_count"]
    assert g["honesty_fold_count"] >= 1
    assert g["honesty_folds"]
    assert "fees" in g["honesty_folds"]
    assert set(g["honesty_warns"]).issubset(set(g["honesty_folds"]))
    # Hot also names calm folds (speak-both-sides after quiet fold names).
    assert "fees" not in g["honesty_quiet_folds"]
    assert g["honesty_quiet_fold_count"] == len(g["honesty_quiet_folds"])
    assert g["honesty_quiet_fold_count"] == g["honesty_fold_count"] - g["honesty_warn_count"]
    assert set(g["honesty_quiet_folds"]).isdisjoint(set(g["honesty_warns"]))
    assert set(g["honesty_quiet_folds"]) | set(g["honesty_warns"]) == set(g["honesty_folds"])
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
    assert "A Kelly neg · −80%" in g["kelly_line"]
    assert "Kelly" not in g["honesty_core"]
    assert g["kelly_line"] in g["honesty_line"]
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
    assert "A payoff strong · 2×" in g["edge_line"]
    assert "A expectancy strong · +€50" in g["edge_line"]
    assert "A PF strong · 6×" in g["edge_line"]
    assert "A payoff" not in g["honesty_core"]
    assert "A expectancy" not in g["honesty_core"]
    assert "A fees comfortable" not in g["honesty_core"]
    assert "A mixed · mostly wins · 3w/1l" not in g["honesty_core"]
    assert "A fees comfortable" in g["fees_line"]
    assert "A mixed · mostly wins · 3w/1l" in g["polarity_line"]
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
    assert s["loss_streak_min"] == 1
    assert s2["loss_streak_min"] == 1
    assert s["loss_streak_stdev"] is None
    assert s2["loss_streak_stdev"] is None
    assert s["loss_streak_cv"] is None
    assert s2["loss_streak_cv"] is None
    assert s["loss_streak_runs"] == 1
    assert s2["loss_streak_runs"] == 1
    assert s["win_streak"] == 0
    assert s2["win_streak"] == 0
    assert s["win_streak_max"] == 1
    assert s2["win_streak_max"] == 1
    assert s["win_streak_mean"] == 1.0
    assert s2["win_streak_mean"] == 1.0
    assert s["win_streak_median"] == 1.0
    assert s2["win_streak_median"] == 1.0
    assert s["win_streak_min"] == 1
    assert s2["win_streak_min"] == 1
    assert s["win_streak_stdev"] is None
    assert s2["win_streak_stdev"] is None
    assert s["win_streak_cv"] is None
    assert s2["win_streak_cv"] is None
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
    assert "A loss streak hot · 2" in g["streak_line"]
    assert "streak" not in g["honesty_core"]
    assert g["streak_line"] in g["honesty_line"]
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
    assert "A flats · 2" in g["streak_line"]
    assert "A flats" not in g["honesty_core"]
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


def test_window_a_loss_streak_min_speaks_when_floor_is_under_peak() -> None:
    """Min speaks when ≥2 runs and the shortest run is under the peak."""
    from stock_checker.promote_ab import (
        WINDOW_A_LOSS_STREAK_HOT,
        WINDOW_A_LOSS_STREAK_MEAN_MIN_RUNS,
        format_window_a_closes_loss_streak_min_bit,
        min_loss_streak,
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
            "loss_streak_max": 3,
            "loss_streak_runs": 2,
        }
    )
    assert unknown["closes_loss_streak_min"] is None
    assert unknown["closes_loss_streak_min_bit"] == ""
    assert unknown["closes_loss_streak_min_hot"] is False
    assert format_window_a_closes_loss_streak_min_bit(None) == ""

    one = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "loss_streak": 2,
            "loss_streak_min": 2,
            "loss_streak_max": 2,
            "loss_streak_runs": 1,
        }
    )
    assert one["closes_loss_streak_min_bit"] == ""
    assert 1 < WINDOW_A_LOSS_STREAK_MEAN_MIN_RUNS

    same = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "loss_streak": 1,
            "loss_streak_min": 1,
            "loss_streak_max": 1,
            "loss_streak_runs": 2,
        }
    )
    assert same["closes_loss_streak_min_bit"] == ""

    quiet = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "loss_streak": 1,
            "loss_streak_min": 1,
            "loss_streak_max": 3,
            "loss_streak_runs": 2,
        }
    )
    assert quiet["closes_loss_streak_min"] == 1
    assert quiet["closes_loss_streak_min_hot"] is False
    assert quiet["closes_loss_streak_min"] < WINDOW_A_LOSS_STREAK_HOT
    assert quiet["closes_loss_streak_min_bit"] == "A loss streak min · 1"

    sells = [
        {"timestamp": "2026-08-12T10:00:00+00:00", "profit_loss": -4.0},
        {"timestamp": "2026-08-13T10:00:00+00:00", "profit_loss": -3.0},
        {"timestamp": "2026-08-14T10:00:00+00:00", "profit_loss": 5.0},
        {"timestamp": "2026-08-15T10:00:00+00:00", "profit_loss": -1.0},
    ]
    assert min_loss_streak(sells) == 1
    assert min_loss_streak([]) is None
    assert min_loss_streak(
        [{"timestamp": "2026-08-12T10:00:00+00:00", "profit_loss": 2.0}]
    ) is None


def test_promote_ab_glance_loss_streak_min_warns_but_ready() -> None:
    """A hot min loss streak warns. It does not block ready for B."""
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
            "loss_streak_min": 2,
            "loss_streak_max": 4,
            "loss_streak_runs": 2,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_loss_streak_min"] == 2
    assert g["closes_loss_streak_min_hot"] is True
    assert "A loss streak min · 2" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True


def test_window_a_loss_streak_stdev_speaks_when_runs_differ() -> None:
    """σ speaks when ≥3 loss runs and the sample stdev is at least 0.05."""
    from stock_checker.promote_ab import (
        WINDOW_A_LOSS_STREAK_HOT,
        WINDOW_A_LOSS_STREAK_STDEV_MIN,
        WINDOW_A_LOSS_STREAK_STDEV_MIN_RUNS,
        format_window_a_closes_loss_streak_stdev_bit,
        stdev_loss_streak,
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
            "loss_streak_runs": 3,
        }
    )
    assert unknown["closes_loss_streak_stdev"] is None
    assert unknown["closes_loss_streak_stdev_bit"] == ""
    assert unknown["closes_loss_streak_stdev_hot"] is False
    assert format_window_a_closes_loss_streak_stdev_bit(None) == ""

    two = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "loss_streak": 1,
            "loss_streak_stdev": 2.8,
            "loss_streak_runs": 2,
        }
    )
    assert two["closes_loss_streak_stdev_bit"] == ""
    assert 2 < WINDOW_A_LOSS_STREAK_STDEV_MIN_RUNS

    flat = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "loss_streak": 1,
            "loss_streak_stdev": 0.0,
            "loss_streak_runs": 3,
        }
    )
    assert flat["closes_loss_streak_stdev_bit"] == ""
    assert 0.0 < WINDOW_A_LOSS_STREAK_STDEV_MIN

    quiet = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "loss_streak": 1,
            "loss_streak_stdev": 1.0,
            "loss_streak_runs": 3,
        }
    )
    assert quiet["closes_loss_streak_stdev"] == 1.0
    assert quiet["closes_loss_streak_stdev_hot"] is False
    assert quiet["closes_loss_streak_stdev"] < WINDOW_A_LOSS_STREAK_HOT
    assert quiet["closes_loss_streak_stdev_bit"] == "A loss streak σ · 1.0 · 3 runs"

    sells = [
        {"timestamp": "2026-08-12T10:00:00+00:00", "profit_loss": -1.0},
        {"timestamp": "2026-08-13T10:00:00+00:00", "profit_loss": 2.0},
        {"timestamp": "2026-08-14T10:00:00+00:00", "profit_loss": -1.0},
        {"timestamp": "2026-08-15T10:00:00+00:00", "profit_loss": -1.0},
        {"timestamp": "2026-08-16T10:00:00+00:00", "profit_loss": 2.0},
        {"timestamp": "2026-08-17T10:00:00+00:00", "profit_loss": -1.0},
        {"timestamp": "2026-08-18T10:00:00+00:00", "profit_loss": -1.0},
        {"timestamp": "2026-08-19T10:00:00+00:00", "profit_loss": -1.0},
    ]
    assert abs(stdev_loss_streak(sells) - 1.0) < 1e-9
    assert stdev_loss_streak([]) is None
    assert (
        stdev_loss_streak(
            [{"timestamp": "2026-08-12T10:00:00+00:00", "profit_loss": -2.0}]
        )
        is None
    )


def test_promote_ab_glance_loss_streak_stdev_warns_but_ready() -> None:
    """A wide loss-streak σ warns. It does not block ready for B."""
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
            "loss_streak_stdev": 2.3,
            "loss_streak_runs": 3,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_loss_streak_stdev"] == 2.3
    assert g["closes_loss_streak_stdev_hot"] is True
    assert "A loss streak σ · 2.3 · 3 runs" in g["line"]
    assert "ready for B" in g["line"]
    assert g["b_ready"] is True


def test_window_a_loss_streak_cv_speaks_when_runs_differ() -> None:
    """CV speaks when ≥3 loss runs and σ/mean is at least 0.05."""
    from stock_checker.promote_ab import (
        WINDOW_A_LOSS_STREAK_HOT,
        WINDOW_A_LOSS_STREAK_STDEV_MIN,
        WINDOW_A_LOSS_STREAK_STDEV_MIN_RUNS,
        cv_loss_streak,
        format_window_a_closes_loss_streak_cv_bit,
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
            "loss_streak_runs": 3,
        }
    )
    assert unknown["closes_loss_streak_cv"] is None
    assert unknown["closes_loss_streak_cv_bit"] == ""
    assert unknown["closes_loss_streak_cv_hot"] is False
    assert format_window_a_closes_loss_streak_cv_bit(None) == ""

    two = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "loss_streak": 1,
            "loss_streak_cv": 1.4,
            "loss_streak_runs": 2,
        }
    )
    assert two["closes_loss_streak_cv_bit"] == ""
    assert 2 < WINDOW_A_LOSS_STREAK_STDEV_MIN_RUNS

    flat = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "loss_streak": 1,
            "loss_streak_cv": 0.0,
            "loss_streak_runs": 3,
        }
    )
    assert flat["closes_loss_streak_cv_bit"] == ""
    assert 0.0 < WINDOW_A_LOSS_STREAK_STDEV_MIN

    quiet = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "loss_streak": 1,
            "loss_streak_cv": 0.5,
            "loss_streak_runs": 3,
        }
    )
    assert quiet["closes_loss_streak_cv"] == 0.5
    assert quiet["closes_loss_streak_cv_hot"] is False
    assert quiet["closes_loss_streak_cv"] < WINDOW_A_LOSS_STREAK_HOT
    assert quiet["closes_loss_streak_cv_bit"] == "A loss streak CV · 0.5 · 3 runs"

    sells = [
        {"timestamp": "2026-08-12T10:00:00+00:00", "profit_loss": -1.0},
        {"timestamp": "2026-08-13T10:00:00+00:00", "profit_loss": 2.0},
        {"timestamp": "2026-08-14T10:00:00+00:00", "profit_loss": -1.0},
        {"timestamp": "2026-08-15T10:00:00+00:00", "profit_loss": -1.0},
        {"timestamp": "2026-08-16T10:00:00+00:00", "profit_loss": 2.0},
        {"timestamp": "2026-08-17T10:00:00+00:00", "profit_loss": -1.0},
        {"timestamp": "2026-08-18T10:00:00+00:00", "profit_loss": -1.0},
        {"timestamp": "2026-08-19T10:00:00+00:00", "profit_loss": -1.0},
    ]
    assert abs(cv_loss_streak(sells) - 0.5) < 1e-9
    assert cv_loss_streak([]) is None
    assert (
        cv_loss_streak(
            [{"timestamp": "2026-08-12T10:00:00+00:00", "profit_loss": -2.0}]
        )
        is None
    )


def test_promote_ab_glance_loss_streak_cv_warns_but_ready() -> None:
    """A wide loss-streak CV warns. It does not block ready for B."""
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
            "loss_streak_cv": 2.3,
            "loss_streak_runs": 3,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["closes_loss_streak_cv"] == 2.3
    assert g["closes_loss_streak_cv_hot"] is True
    assert "A loss streak CV · 2.3 · 3 runs" in g["line"]
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


def test_window_a_win_streak_median_speaks_when_mean_is_pulled() -> None:
    """Median win run speaks when ≥3 runs and it differs from the mean."""
    from stock_checker.promote_ab import (
        WINDOW_A_LOSS_STREAK_HOT,
        WINDOW_A_LOSS_STREAK_MEDIAN_MIN_RUNS,
        format_window_a_closes_win_streak_median_bit,
        median_win_streak,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 4,
            "losses": 2,
            "win_streak": 1,
            "win_streak_mean": 2.0,
            "win_streak_runs": 3,
        }
    )
    assert unknown["closes_win_streak_median"] is None
    assert unknown["closes_win_streak_median_bit"] == ""
    assert unknown["closes_win_streak_median_hot"] is False
    assert format_window_a_closes_win_streak_median_bit(None) == ""

    two = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 4,
            "losses": 2,
            "win_streak": 1,
            "win_streak_mean": 1.5,
            "win_streak_median": 1.0,
            "win_streak_runs": 2,
        }
    )
    assert two["closes_win_streak_median_bit"] == ""
    assert 2 < WINDOW_A_LOSS_STREAK_MEDIAN_MIN_RUNS

    same = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 4,
            "losses": 2,
            "win_streak": 1,
            "win_streak_mean": 1.0,
            "win_streak_median": 1.0,
            "win_streak_runs": 3,
        }
    )
    assert same["closes_win_streak_median_bit"] == ""

    quiet = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 4,
            "losses": 2,
            "win_streak": 1,
            "win_streak_mean": 2.0,
            "win_streak_median": 1.0,
            "win_streak_runs": 3,
        }
    )
    assert quiet["closes_win_streak_median"] == 1.0
    assert quiet["closes_win_streak_median_hot"] is False
    assert quiet["closes_win_streak_median"] < WINDOW_A_LOSS_STREAK_HOT
    assert quiet["closes_win_streak_median_bit"] == "A win streak med · 1.0 · 3 runs"

    sells = [
        {"timestamp": "2026-08-12T10:00:00+00:00", "profit_loss": 4.0},
        {"timestamp": "2026-08-13T10:00:00+00:00", "profit_loss": 3.0},
        {"timestamp": "2026-08-14T10:00:00+00:00", "profit_loss": 2.0},
        {"timestamp": "2026-08-15T10:00:00+00:00", "profit_loss": 1.0},
        {"timestamp": "2026-08-16T10:00:00+00:00", "profit_loss": -5.0},
        {"timestamp": "2026-08-18T10:00:00+00:00", "profit_loss": 1.0},
        {"timestamp": "2026-08-20T10:00:00+00:00", "profit_loss": -4.0},
        {"timestamp": "2026-08-22T10:00:00+00:00", "profit_loss": 1.0},
    ]
    assert median_win_streak(sells) == 1.0
    assert median_win_streak([]) is None


def test_promote_ab_glance_win_streak_median_does_not_warn() -> None:
    """A hot median win streak speaks. It does not warn or block ready for B."""
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
        "win_streak_median": 1.0,
        "win_streak_runs": 3,
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
        window_stats={
            **base,
            "win_streak_mean": 1.0,
            "win_streak_median": 2.5,
        },
    )
    assert hot["ready"] is True
    assert hot["tone"] == quiet["tone"] == "ready"
    assert hot["closes_win_streak_median"] == 2.5
    assert hot["closes_win_streak_median_hot"] is True
    assert "A win streak med · 2.5 · 3 runs" in hot["line"]
    assert "ready for B" in hot["line"]
    assert hot["b_ready"] is True


def test_window_a_win_streak_min_speaks_when_floor_is_under_peak() -> None:
    """Min speaks when ≥2 win runs and the shortest run is under the peak."""
    from stock_checker.promote_ab import (
        WINDOW_A_LOSS_STREAK_HOT,
        WINDOW_A_LOSS_STREAK_MEAN_MIN_RUNS,
        format_window_a_closes_win_streak_min_bit,
        min_win_streak,
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
            "win_streak_max": 3,
            "win_streak_runs": 2,
        }
    )
    assert unknown["closes_win_streak_min"] is None
    assert unknown["closes_win_streak_min_bit"] == ""
    assert unknown["closes_win_streak_min_hot"] is False
    assert format_window_a_closes_win_streak_min_bit(None) == ""

    one = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "win_streak": 2,
            "win_streak_min": 2,
            "win_streak_max": 2,
            "win_streak_runs": 1,
        }
    )
    assert one["closes_win_streak_min_bit"] == ""
    assert 1 < WINDOW_A_LOSS_STREAK_MEAN_MIN_RUNS

    same = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "win_streak": 1,
            "win_streak_min": 1,
            "win_streak_max": 1,
            "win_streak_runs": 2,
        }
    )
    assert same["closes_win_streak_min_bit"] == ""

    quiet = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "win_streak": 1,
            "win_streak_min": 1,
            "win_streak_max": 3,
            "win_streak_runs": 2,
        }
    )
    assert quiet["closes_win_streak_min"] == 1
    assert quiet["closes_win_streak_min_hot"] is False
    assert quiet["closes_win_streak_min"] < WINDOW_A_LOSS_STREAK_HOT
    assert quiet["closes_win_streak_min_bit"] == "A win streak min · 1"

    sells = [
        {"timestamp": "2026-08-12T10:00:00+00:00", "profit_loss": 4.0},
        {"timestamp": "2026-08-13T10:00:00+00:00", "profit_loss": 3.0},
        {"timestamp": "2026-08-14T10:00:00+00:00", "profit_loss": -5.0},
        {"timestamp": "2026-08-15T10:00:00+00:00", "profit_loss": 1.0},
    ]
    assert min_win_streak(sells) == 1
    assert min_win_streak([]) is None
    assert min_win_streak(
        [{"timestamp": "2026-08-12T10:00:00+00:00", "profit_loss": -2.0}]
    ) is None


def test_promote_ab_glance_win_streak_min_does_not_warn() -> None:
    """A hot min win streak speaks. It does not warn or block ready for B."""
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
        "win_streak_max": 1,
        "win_streak_min": 1,
        "win_streak_runs": 2,
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
        window_stats={
            **base,
            "win_streak_min": 2,
            "win_streak_max": 4,
        },
    )
    assert hot["ready"] is True
    assert hot["tone"] == quiet["tone"] == "ready"
    assert hot["closes_win_streak_min"] == 2
    assert hot["closes_win_streak_min_hot"] is True
    assert "A win streak min · 2" in hot["line"]
    assert "ready for B" in hot["line"]
    assert hot["b_ready"] is True


def test_window_a_win_streak_stdev_speaks_when_runs_differ() -> None:
    """σ speaks when ≥3 win runs and the sample stdev is at least 0.05."""
    from stock_checker.promote_ab import (
        WINDOW_A_LOSS_STREAK_HOT,
        WINDOW_A_LOSS_STREAK_STDEV_MIN,
        WINDOW_A_LOSS_STREAK_STDEV_MIN_RUNS,
        format_window_a_closes_win_streak_stdev_bit,
        stdev_win_streak,
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
            "win_streak_runs": 3,
        }
    )
    assert unknown["closes_win_streak_stdev"] is None
    assert unknown["closes_win_streak_stdev_bit"] == ""
    assert unknown["closes_win_streak_stdev_hot"] is False
    assert format_window_a_closes_win_streak_stdev_bit(None) == ""

    two = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "win_streak": 1,
            "win_streak_stdev": 2.8,
            "win_streak_runs": 2,
        }
    )
    assert two["closes_win_streak_stdev_bit"] == ""
    assert 2 < WINDOW_A_LOSS_STREAK_STDEV_MIN_RUNS

    flat = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "win_streak": 1,
            "win_streak_stdev": 0.0,
            "win_streak_runs": 3,
        }
    )
    assert flat["closes_win_streak_stdev_bit"] == ""
    assert 0.0 < WINDOW_A_LOSS_STREAK_STDEV_MIN

    quiet = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "win_streak": 1,
            "win_streak_stdev": 1.0,
            "win_streak_runs": 3,
        }
    )
    assert quiet["closes_win_streak_stdev"] == 1.0
    assert quiet["closes_win_streak_stdev_hot"] is False
    assert quiet["closes_win_streak_stdev"] < WINDOW_A_LOSS_STREAK_HOT
    assert quiet["closes_win_streak_stdev_bit"] == "A win streak σ · 1.0 · 3 runs"

    sells = [
        {"timestamp": "2026-08-12T10:00:00+00:00", "profit_loss": 1.0},
        {"timestamp": "2026-08-13T10:00:00+00:00", "profit_loss": -2.0},
        {"timestamp": "2026-08-14T10:00:00+00:00", "profit_loss": 1.0},
        {"timestamp": "2026-08-15T10:00:00+00:00", "profit_loss": 1.0},
        {"timestamp": "2026-08-16T10:00:00+00:00", "profit_loss": -2.0},
        {"timestamp": "2026-08-17T10:00:00+00:00", "profit_loss": 1.0},
        {"timestamp": "2026-08-18T10:00:00+00:00", "profit_loss": 1.0},
        {"timestamp": "2026-08-19T10:00:00+00:00", "profit_loss": 1.0},
    ]
    assert abs(stdev_win_streak(sells) - 1.0) < 1e-9
    assert stdev_win_streak([]) is None
    assert (
        stdev_win_streak(
            [{"timestamp": "2026-08-12T10:00:00+00:00", "profit_loss": 2.0}]
        )
        is None
    )


def test_promote_ab_glance_win_streak_stdev_does_not_warn() -> None:
    """A wide win-streak σ speaks. It does not warn or block ready for B."""
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
        "win_streak_stdev": 1.0,
        "win_streak_runs": 3,
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
        window_stats={**base, "win_streak_stdev": 2.3},
    )
    assert hot["ready"] is True
    assert hot["tone"] == quiet["tone"] == "ready"
    assert hot["closes_win_streak_stdev"] == 2.3
    assert hot["closes_win_streak_stdev_hot"] is True
    assert "A win streak σ · 2.3 · 3 runs" in hot["line"]
    assert "ready for B" in hot["line"]
    assert hot["b_ready"] is True


def test_window_a_win_streak_cv_speaks_when_runs_differ() -> None:
    """CV speaks when ≥3 win runs and σ/mean is at least 0.05."""
    from stock_checker.promote_ab import (
        WINDOW_A_LOSS_STREAK_HOT,
        WINDOW_A_LOSS_STREAK_STDEV_MIN,
        WINDOW_A_LOSS_STREAK_STDEV_MIN_RUNS,
        cv_win_streak,
        format_window_a_closes_win_streak_cv_bit,
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
            "win_streak_runs": 3,
        }
    )
    assert unknown["closes_win_streak_cv"] is None
    assert unknown["closes_win_streak_cv_bit"] == ""
    assert unknown["closes_win_streak_cv_hot"] is False
    assert format_window_a_closes_win_streak_cv_bit(None) == ""

    two = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "win_streak": 1,
            "win_streak_cv": 1.4,
            "win_streak_runs": 2,
        }
    )
    assert two["closes_win_streak_cv_bit"] == ""
    assert 2 < WINDOW_A_LOSS_STREAK_STDEV_MIN_RUNS

    flat = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "win_streak": 1,
            "win_streak_cv": 0.0,
            "win_streak_runs": 3,
        }
    )
    assert flat["closes_win_streak_cv_bit"] == ""
    assert 0.0 < WINDOW_A_LOSS_STREAK_STDEV_MIN

    quiet = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
            "win_streak": 1,
            "win_streak_cv": 0.5,
            "win_streak_runs": 3,
        }
    )
    assert quiet["closes_win_streak_cv"] == 0.5
    assert quiet["closes_win_streak_cv_hot"] is False
    assert quiet["closes_win_streak_cv"] < WINDOW_A_LOSS_STREAK_HOT
    assert quiet["closes_win_streak_cv_bit"] == "A win streak CV · 0.5 · 3 runs"

    sells = [
        {"timestamp": "2026-08-12T10:00:00+00:00", "profit_loss": 1.0},
        {"timestamp": "2026-08-13T10:00:00+00:00", "profit_loss": -2.0},
        {"timestamp": "2026-08-14T10:00:00+00:00", "profit_loss": 1.0},
        {"timestamp": "2026-08-15T10:00:00+00:00", "profit_loss": 1.0},
        {"timestamp": "2026-08-16T10:00:00+00:00", "profit_loss": -2.0},
        {"timestamp": "2026-08-17T10:00:00+00:00", "profit_loss": 1.0},
        {"timestamp": "2026-08-18T10:00:00+00:00", "profit_loss": 1.0},
        {"timestamp": "2026-08-19T10:00:00+00:00", "profit_loss": 1.0},
    ]
    assert abs(cv_win_streak(sells) - 0.5) < 1e-9
    assert cv_win_streak([]) is None
    assert (
        cv_win_streak(
            [{"timestamp": "2026-08-12T10:00:00+00:00", "profit_loss": 2.0}]
        )
        is None
    )


def test_promote_ab_glance_win_streak_cv_does_not_warn() -> None:
    """A wide win-streak CV speaks. It does not warn or block ready for B."""
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
        "win_streak_cv": 0.5,
        "win_streak_runs": 3,
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
        window_stats={**base, "win_streak_cv": 2.3},
    )
    assert hot["ready"] is True
    assert hot["tone"] == quiet["tone"] == "ready"
    assert hot["closes_win_streak_cv"] == 2.3
    assert hot["closes_win_streak_cv_hot"] is True
    assert "A win streak CV · 2.3 · 3 runs" in hot["line"]
    assert "ready for B" in hot["line"]
    assert hot["b_ready"] is True


def test_window_a_exit_mix_speaks_and_warns() -> None:
    """Exit mix says why closes happened. Stops and churn leading TP warn only."""
    from stock_checker.promote_ab import (
        WINDOW_A_START_UTC,
        exit_reason_bucket,
        format_window_a_closes_exit_mix_bit,
        format_window_a_closes_exit_tp_share_bit,
        format_window_a_closes_exit_sl_share_bit,
        format_window_a_closes_exit_rot_share_bit,
        format_window_a_closes_exit_trim_share_bit,
        format_window_a_closes_exit_lead_bit,
        format_window_a_closes_exit_unknown_bit,
        sell_exit_counts,
        summarize_window_trades,
        window_a_sample_readiness,
    )

    assert exit_reason_bucket("take_profit") == "tp"
    assert exit_reason_bucket("rotation") == "rot"
    assert exit_reason_bucket("mystery") is None
    assert exit_reason_bucket("") is None

    unknown = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 6,
            "wins": 3,
            "losses": 3,
        }
    )
    assert unknown["closes_exit_tp"] is None
    assert unknown["closes_exit_mix_bit"] == ""
    assert unknown["closes_exit_mix_hot"] is False
    assert unknown["closes_exit_unknown"] is None
    assert unknown["closes_exit_unknown_bit"] == ""
    assert unknown["closes_exit_unknown_warn"] is False
    assert unknown["closes_exit_tp_share_pct"] is None
    assert unknown["closes_exit_tp_share_bit"] == ""
    assert unknown["closes_exit_tp_share_thin"] is False
    assert unknown["closes_exit_sl_share_pct"] is None
    assert unknown["closes_exit_sl_share_bit"] == ""
    assert unknown["closes_exit_sl_share_hot"] is False
    assert unknown["closes_exit_rot_share_pct"] is None
    assert unknown["closes_exit_rot_share_bit"] == ""
    assert unknown["closes_exit_rot_share_hot"] is False
    assert unknown["closes_exit_trim_share_pct"] is None
    assert unknown["closes_exit_trim_share_bit"] == ""
    assert unknown["closes_exit_trim_share_hot"] is False
    assert unknown["closes_exit_lead"] is None
    assert unknown["closes_exit_lead_pct"] is None
    assert unknown["closes_exit_lead_bit"] == ""
    assert unknown["closes_exit_lead_hot"] is False
    assert format_window_a_closes_exit_mix_bit(unknown) == ""
    assert format_window_a_closes_exit_mix_bit(None) == ""
    assert format_window_a_closes_exit_unknown_bit(None) == ""
    assert format_window_a_closes_exit_tp_share_bit(None) == ""
    assert format_window_a_closes_exit_sl_share_bit(None) == ""
    assert format_window_a_closes_exit_rot_share_bit(None) == ""
    assert format_window_a_closes_exit_trim_share_bit(None) == ""
    assert format_window_a_closes_exit_lead_bit(None) == ""

    silent = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 2,
            "losses": 2,
            "exit_tp": 0,
            "exit_sl": 0,
            "exit_rot": 0,
            "exit_trim": 0,
        }
    )
    assert silent["closes_exit_mix_bit"] == ""
    assert silent["closes_exit_mix_hot"] is False
    assert silent["closes_exit_unknown"] == 4
    assert silent["closes_exit_unknown_bit"] == "A exits unknown · 4"
    assert silent["closes_exit_unknown_warn"] is True
    assert silent["closes_exit_tp_share_pct"] is None
    assert silent["closes_exit_tp_share_bit"] == ""
    assert silent["closes_exit_sl_share_pct"] is None
    assert silent["closes_exit_sl_share_bit"] == ""
    assert silent["closes_exit_sl_share_hot"] is False
    assert silent["closes_exit_rot_share_pct"] is None
    assert silent["closes_exit_rot_share_bit"] == ""
    assert silent["closes_exit_rot_share_hot"] is False
    assert silent["closes_exit_trim_share_pct"] is None
    assert silent["closes_exit_trim_share_bit"] == ""
    assert silent["closes_exit_trim_share_hot"] is False
    assert silent["closes_exit_lead"] is None
    assert silent["closes_exit_lead_bit"] == ""
    assert silent["closes_exit_lead_hot"] is False
    assert format_window_a_closes_exit_unknown_bit(silent) == "A exits unknown · 4"

    led = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
        }
    )
    assert led["closes_exit_tp"] == 3
    assert led["closes_exit_sl"] == 1
    assert led["closes_exit_mix_hot"] is False
    assert led["closes_exit_mix_bit"] == "A exits tp 3 · sl 1"
    assert led["closes_exit_unknown"] is None
    assert led["closes_exit_unknown_bit"] == ""
    assert format_window_a_closes_exit_mix_bit(led) == "A exits tp 3 · sl 1"
    assert led["closes_exit_tp_share_pct"] == 75.0
    assert led["closes_exit_tp_share_severity"] == "strong"
    assert led["closes_exit_tp_share_thin"] is False
    assert led["closes_exit_tp_share_bit"] == "A exits tp share strong · 75%"
    assert format_window_a_closes_exit_tp_share_bit(led) == "A exits tp share strong · 75%"
    assert led["closes_exit_sl_share_pct"] == 25.0
    assert led["closes_exit_sl_share_severity"] == "quiet"
    assert led["closes_exit_sl_share_hot"] is False
    assert led["closes_exit_sl_share_bit"] == "A exits sl share quiet · 25%"
    assert format_window_a_closes_exit_sl_share_bit(led) == "A exits sl share quiet · 25%"
    assert led["closes_exit_rot_share_pct"] == 0.0
    assert led["closes_exit_rot_share_severity"] == "quiet"
    assert led["closes_exit_rot_share_hot"] is False
    assert led["closes_exit_rot_share_bit"] == "A exits rot share quiet · 0%"
    assert format_window_a_closes_exit_rot_share_bit(led) == "A exits rot share quiet · 0%"
    assert led["closes_exit_trim_share_pct"] == 0.0
    assert led["closes_exit_trim_share_severity"] == "quiet"
    assert led["closes_exit_trim_share_hot"] is False
    assert led["closes_exit_trim_share_bit"] == "A exits trim share quiet · 0%"
    assert format_window_a_closes_exit_trim_share_bit(led) == "A exits trim share quiet · 0%"
    assert led["closes_exit_lead"] == "tp"
    assert led["closes_exit_lead_pct"] == 75.0
    assert led["closes_exit_lead_hot"] is False
    assert led["closes_exit_lead_bit"] == "A exits lead tp · 75%"
    assert format_window_a_closes_exit_lead_bit(led) == "A exits lead tp · 75%"

    hot_sample = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 1,
            "losses": 3,
            "exit_tp": 1,
            "exit_sl": 2,
            "exit_rot": 1,
            "exit_trim": 0,
        }
    )
    assert hot_sample["closes_exit_mix_hot"] is True
    assert hot_sample["closes_exit_mix_bit"] == "A exits tp 1 · sl 2 · rot 1"
    assert hot_sample["closes_exit_tp_share_pct"] == 25.0
    assert hot_sample["closes_exit_tp_share_severity"] == "thin"
    assert hot_sample["closes_exit_tp_share_thin"] is True
    assert hot_sample["closes_exit_tp_share_bit"] == "A exits tp share thin · 25%"
    assert hot_sample["closes_exit_sl_share_pct"] == 50.0
    assert hot_sample["closes_exit_sl_share_severity"] == ""
    assert hot_sample["closes_exit_sl_share_hot"] is False
    assert hot_sample["closes_exit_sl_share_bit"] == "A exits sl share · 50%"
    assert hot_sample["closes_exit_rot_share_pct"] == 25.0
    assert hot_sample["closes_exit_rot_share_severity"] == "quiet"
    assert hot_sample["closes_exit_rot_share_hot"] is False
    assert hot_sample["closes_exit_rot_share_bit"] == "A exits rot share quiet · 25%"
    assert hot_sample["closes_exit_trim_share_pct"] == 0.0
    assert hot_sample["closes_exit_trim_share_severity"] == "quiet"
    assert hot_sample["closes_exit_trim_share_hot"] is False
    assert hot_sample["closes_exit_trim_share_bit"] == "A exits trim share quiet · 0%"

    mid = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 2,
            "losses": 2,
            "exit_tp": 2,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
        }
    )
    assert mid["closes_exit_mix_hot"] is False
    assert mid["closes_exit_tp_share_pct"] == 50.0
    assert mid["closes_exit_tp_share_severity"] == ""
    assert mid["closes_exit_tp_share_thin"] is False
    assert mid["closes_exit_tp_share_bit"] == "A exits tp share · 50%"
    assert mid["closes_exit_sl_share_pct"] == 50.0
    assert mid["closes_exit_sl_share_severity"] == ""
    assert mid["closes_exit_sl_share_hot"] is False
    assert mid["closes_exit_sl_share_bit"] == "A exits sl share · 50%"
    assert mid["closes_exit_rot_share_pct"] == 0.0
    assert mid["closes_exit_rot_share_bit"] == "A exits rot share quiet · 0%"
    assert mid["closes_exit_trim_share_pct"] == 0.0
    assert mid["closes_exit_trim_share_bit"] == "A exits trim share quiet · 0%"

    rot_led = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 2,
            "losses": 2,
            "exit_tp": 1,
            "exit_sl": 0,
            "exit_rot": 3,
            "exit_trim": 0,
        }
    )
    assert rot_led["closes_exit_mix_hot"] is True
    assert rot_led["closes_exit_sl_share_pct"] == 0.0
    assert rot_led["closes_exit_sl_share_severity"] == "quiet"
    assert rot_led["closes_exit_sl_share_hot"] is False
    assert rot_led["closes_exit_sl_share_bit"] == "A exits sl share quiet · 0%"
    assert rot_led["closes_exit_rot_share_pct"] == 75.0
    assert rot_led["closes_exit_rot_share_severity"] == "hot"
    assert rot_led["closes_exit_rot_share_hot"] is True
    assert rot_led["closes_exit_rot_share_bit"] == "A exits rot share hot · 75%"
    assert rot_led["closes_exit_trim_share_pct"] == 0.0
    assert rot_led["closes_exit_trim_share_severity"] == "quiet"
    assert rot_led["closes_exit_trim_share_hot"] is False
    assert rot_led["closes_exit_trim_share_bit"] == "A exits trim share quiet · 0%"

    trades = [
        {
            "type": "SELL",
            "symbol": "AAPL",
            "timestamp": "2026-08-15T10:00:00+00:00",
            "profit_loss": 10.0,
            "exit_reason": "tp",
        },
        {
            "type": "SELL",
            "symbol": "MSFT",
            "timestamp": "2026-08-16T10:00:00+00:00",
            "profit_loss": -4.0,
            "exit_reason": "sl",
        },
        {
            "type": "SELL",
            "symbol": "NVDA",
            "timestamp": "2026-08-17T10:00:00+00:00",
            "profit_loss": 6.0,
            "exit_reason": "rotation",
        },
        {
            "type": "SELL",
            "symbol": "SAP.DE",
            "timestamp": "2026-08-18T10:00:00+00:00",
            "profit_loss": 2.0,
        },
    ]
    s = summarize_window_trades(trades, start=WINDOW_A_START_UTC)
    assert s["exit_tp"] == 1
    assert s["exit_sl"] == 1
    assert s["exit_rot"] == 1
    assert s["exit_trim"] == 0
    assert s["exit_unknown"] == 1
    assert s["exit_pnl_tp"] == 10.0
    assert s["exit_pnl_sl"] == -4.0
    assert s["exit_pnl_rot"] == 6.0
    assert s["exit_pnl_trim"] == 0.0
    assert sell_exit_counts([]) is None
    assert sell_exit_counts([{"exit_reason": "nope"}]) == {
        "tp": 0,
        "sl": 0,
        "rot": 0,
        "trim": 0,
    }

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
        "exit_tp": 4,
        "exit_sl": 1,
        "exit_rot": 0,
        "exit_trim": 1,
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
        window_stats={
            **base,
            "exit_tp": 1,
            "exit_sl": 2,
            "exit_rot": 2,
            "exit_trim": 1,
        },
    )
    assert quiet["ready"] is True
    assert quiet["tone"] == "ready"
    assert quiet["closes_exit_mix_hot"] is False
    assert "A exits tp 4 · sl 1 · trim 1" in quiet["line"]
    assert "A exits tp share strong · 66.7%" in quiet["line"]
    assert "A exits sl share quiet · 16.7%" in quiet["line"]
    assert "A exits rot share quiet · 0%" in quiet["line"]
    assert "A exits trim share quiet · 16.7%" in quiet["line"]
    assert quiet["closes_exit_sl_share_hot"] is False
    assert quiet["closes_exit_rot_share_hot"] is False
    assert quiet["closes_exit_trim_share_hot"] is False
    assert hot["ready"] is True
    assert hot["tone"] == "warn"
    assert hot["closes_exit_tp"] == 1
    assert hot["closes_exit_sl"] == 2
    assert hot["closes_exit_rot"] == 2
    assert hot["closes_exit_trim"] == 1
    assert hot["closes_exit_mix_hot"] is True
    assert "A exits tp 1 · sl 2 · rot 2 · trim 1" in hot["line"]
    assert "A exits tp share thin · 16.7%" in hot["line"]
    assert "A exits sl share quiet · 33.3%" in hot["line"]
    assert "A exits rot share quiet · 33.3%" in hot["line"]
    assert "A exits trim share quiet · 16.7%" in hot["line"]
    assert hot["closes_exit_sl_share_hot"] is False
    assert hot["closes_exit_rot_share_hot"] is False
    assert hot["closes_exit_trim_share_hot"] is False
    assert "ready for B" in hot["line"]
    assert hot["b_ready"] is True
    assert "A exits unknown" not in quiet["line"]
    assert "A exits unknown" not in hot["line"]

    unk = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            **base,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
        },
    )
    assert unk["ready"] is True
    assert unk["tone"] == "warn"
    assert unk["closes_exit_unknown"] == 2
    assert unk["closes_exit_unknown_warn"] is True
    assert unk["closes_exit_mix_hot"] is False
    assert "A exits tp 3 · sl 1" in unk["line"]
    assert "A exits tp share strong · 75%" in unk["line"]
    assert "A exits unknown · 2" in unk["line"]
    assert "A exits sl share quiet · 25%" in unk["line"]
    assert "A exits rot share quiet · 0%" in unk["line"]
    assert "A exits trim share quiet · 0%" in unk["line"]
    assert "ready for B" in unk["line"]
    assert unk["b_ready"] is True

    stop_led = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            **base,
            "sells": 5,
            "exit_tp": 1,
            "exit_sl": 4,
            "exit_rot": 0,
            "exit_trim": 0,
        },
    )
    assert stop_led["ready"] is True
    assert stop_led["tone"] == "warn"
    assert stop_led["closes_exit_sl_share_pct"] == 80.0
    assert stop_led["closes_exit_sl_share_hot"] is True
    assert "A exits sl share hot · 80%" in stop_led["line"]
    assert "A exits rot share quiet · 0%" in stop_led["line"]
    assert "A exits trim share quiet · 0%" in stop_led["line"]
    assert "ready for B" in stop_led["line"]
    assert stop_led["b_ready"] is True

    chase = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            **base,
            "sells": 5,
            "exit_tp": 1,
            "exit_sl": 0,
            "exit_rot": 4,
            "exit_trim": 0,
        },
    )
    assert chase["ready"] is True
    assert chase["tone"] == "warn"
    assert chase["closes_exit_rot_share_pct"] == 80.0
    assert chase["closes_exit_rot_share_hot"] is True
    assert chase["closes_exit_sl_share_hot"] is False
    assert "A exits rot share hot · 80%" in chase["line"]
    assert "A exits trim share quiet · 0%" in chase["line"]
    assert "ready for B" in chase["line"]
    assert chase["b_ready"] is True

    trim_led = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            **base,
            "sells": 5,
            "exit_tp": 1,
            "exit_sl": 0,
            "exit_rot": 0,
            "exit_trim": 4,
        },
    )
    assert trim_led["ready"] is True
    assert trim_led["tone"] == "warn"
    assert trim_led["closes_exit_trim_share_pct"] == 80.0
    assert trim_led["closes_exit_trim_share_hot"] is True
    assert trim_led["closes_exit_rot_share_hot"] is False
    assert trim_led["closes_exit_sl_share_hot"] is False
    assert "A exits trim share hot · 80%" in trim_led["line"]
    assert trim_led["closes_exit_lead"] == "trim"
    assert trim_led["closes_exit_lead_pct"] == 80.0
    assert trim_led["closes_exit_lead_hot"] is True
    assert "A exits lead trim · 80%" in trim_led["line"]
    assert "ready for B" in trim_led["line"]
    assert trim_led["b_ready"] is True

    tie = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            **base,
            "sells": 4,
            "exit_tp": 0,
            "exit_sl": 2,
            "exit_rot": 2,
            "exit_trim": 0,
        },
    )
    assert tie["ready"] is True
    assert tie["tone"] == "warn"
    assert tie["closes_exit_lead"] == "tie"
    assert tie["closes_exit_lead_pct"] == 50.0
    assert tie["closes_exit_lead_hot"] is True
    assert "A exits lead tie · sl=rot · 50%" in tie["line"]
    assert "ready for B" in tie["line"]
    assert tie["b_ready"] is True

    tp_tie = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 2,
            "losses": 2,
            "exit_tp": 2,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
        }
    )
    assert tp_tie["closes_exit_lead"] == "tie"
    assert tp_tie["closes_exit_lead_hot"] is False
    assert tp_tie["closes_exit_lead_bit"] == "A exits lead tie · tp=sl · 50%"



def test_window_a_exit_euro_lead_speaks_when_count_differs() -> None:
    """Euro mover speaks only when it is not the count lead. Warn does not block B."""
    from openbb_backend.desk import build_promote_ab_glance
    from stock_checker.promote_ab import (
        format_window_a_closes_exit_euro_lead_bit,
        sell_exit_pnl,
        window_a_sample_readiness,
    )

    assert sell_exit_pnl([]) is None
    assert sell_exit_pnl([{"exit_reason": "nope", "profit_loss": 9}]) == {
        "tp": 0.0,
        "sl": 0.0,
        "rot": 0.0,
        "trim": 0.0,
    }
    assert format_window_a_closes_exit_euro_lead_bit(None) == ""

    missing = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
        }
    )
    assert missing["closes_exit_euro_lead"] is None
    assert missing["closes_exit_euro_lead_bit"] == ""
    assert missing["closes_exit_euro_lead_hot"] is False

    match = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 80.0,
            "exit_pnl_sl": -10.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert match["closes_exit_lead"] == "tp"
    assert match["closes_exit_euro_lead"] is None
    assert match["closes_exit_euro_lead_bit"] == ""
    assert match["closes_exit_euro_lead_hot"] is False
    assert match["ready"] is True

    disagree = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 12.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert disagree["closes_exit_lead"] == "tp"
    assert disagree["closes_exit_euro_lead"] == "sl"
    assert disagree["closes_exit_euro_pnl"] == -200.0
    assert disagree["closes_exit_euro_lead_hot"] is True
    assert disagree["closes_exit_euro_lead_bit"] == "A exits € lead sl · −€200"
    assert (
        format_window_a_closes_exit_euro_lead_bit(disagree)
        == "A exits € lead sl · −€200"
    )
    assert disagree["ready"] is True

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
    glance = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "fees": 4.0,
            "realized_pnl": -188.0,
            "net_after_all_fees": -192.0,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 12.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert glance["tone"] == "warn"
    assert glance["b_ready"] is True
    assert "A exits € lead sl · −€200" in glance["line"]
    assert "A exits € lead sl · −€200" in glance["honesty_line"]
    assert "A exits € lead" not in glance["summary_line"]
    assert "ready for B" in glance["line"]
    assert "ready for B" in glance["summary_line"]

    speak = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 1,
            "losses": 3,
            "exit_tp": 1,
            "exit_sl": 3,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 90.0,
            "exit_pnl_sl": -8.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert speak["closes_exit_lead"] == "sl"
    assert speak["closes_exit_euro_lead"] == "tp"
    assert speak["closes_exit_euro_lead_hot"] is False
    assert speak["closes_exit_euro_lead_bit"] == "A exits € lead tp · +€90"

    tied = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 2,
            "wins": 1,
            "losses": 1,
            "exit_tp": 1,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 40.0,
            "exit_pnl_sl": -40.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert tied["closes_exit_euro_lead"] is None
    assert tied["closes_exit_euro_lead_bit"] == ""


def test_window_a_exit_euro_offset_speaks_when_lead_matches() -> None:
    """Runner-up euro speaks only when the euro lead matches the count lead."""
    from openbb_backend.desk import build_promote_ab_glance
    from stock_checker.promote_ab import (
        format_window_a_closes_exit_euro_offset_bit,
        window_a_sample_readiness,
    )

    assert format_window_a_closes_exit_euro_offset_bit(None) == ""

    missing = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
        }
    )
    assert missing["closes_exit_euro_offset"] is None
    assert missing["closes_exit_euro_offset_bit"] == ""
    assert missing["closes_exit_euro_offset_hot"] is False

    small = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 80.0,
            "exit_pnl_sl": -10.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert small["closes_exit_lead"] == "tp"
    assert small["closes_exit_euro_lead"] is None
    assert small["closes_exit_euro_offset"] is None
    assert small["ready"] is True

    hot = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -60.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert hot["closes_exit_lead"] == "tp"
    assert hot["closes_exit_euro_lead"] is None
    assert hot["closes_exit_euro_offset"] == "sl"
    assert hot["closes_exit_euro_offset_pnl"] == -60.0
    assert hot["closes_exit_euro_offset_ratio"] == 0.6
    assert hot["closes_exit_euro_offset_hot"] is True
    bit = 'A exits € offset hot · sl −€60 · 0.6×'
    assert hot["closes_exit_euro_offset_bit"] == bit
    assert format_window_a_closes_exit_euro_offset_bit(hot) == bit
    assert hot["ready"] is True

    quiet = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 1,
            "losses": 3,
            "exit_tp": 1,
            "exit_sl": 3,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 60.0,
            "exit_pnl_sl": -100.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert quiet["closes_exit_lead"] == "sl"
    assert quiet["closes_exit_euro_offset"] == "tp"
    assert quiet["closes_exit_euro_offset_hot"] is False
    qbit = 'A exits € offset quiet · tp +€60 · 0.6×'
    assert quiet["closes_exit_euro_offset_bit"] == qbit

    disagree = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 12.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert disagree["closes_exit_euro_lead"] == "sl"
    assert disagree["closes_exit_euro_offset"] is None

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
    glance = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "fees": 4.0,
            "realized_pnl": 40.0,
            "net_after_all_fees": 36.0,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -60.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert glance["tone"] == "warn"
    assert glance["b_ready"] is True
    assert bit in glance["line"]
    assert bit in glance["honesty_line"]
    assert 'A exits € offset' not in glance["summary_line"]
    assert "ready for B" in glance["summary_line"]


def test_window_a_exit_euro_gap_speaks_when_leads_disagree() -> None:
    """€ gap speaks only when count and € leads disagree by ≥2×. Warn does not block B."""
    from openbb_backend.desk import build_promote_ab_glance
    from stock_checker.promote_ab import (
        format_window_a_closes_exit_euro_gap_bit,
        window_a_sample_readiness,
    )

    assert format_window_a_closes_exit_euro_gap_bit(None) == ""

    missing = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
        }
    )
    assert missing["closes_exit_euro_gap_ratio"] is None
    assert missing["closes_exit_euro_gap_bit"] == ""
    assert missing["closes_exit_euro_gap_hot"] is False

    match = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -60.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert match["closes_exit_euro_lead"] is None
    assert match["closes_exit_euro_gap_ratio"] is None
    assert match["closes_exit_euro_gap_bit"] == ""

    thin = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 50.0,
            "exit_pnl_sl": -80.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert thin["closes_exit_euro_lead"] == "sl"
    assert thin["closes_exit_euro_gap_ratio"] is None
    assert thin["closes_exit_euro_gap_bit"] == ""
    assert thin["ready"] is True

    hot = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 12.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert hot["closes_exit_lead"] == "tp"
    assert hot["closes_exit_euro_lead"] == "sl"
    assert hot["closes_exit_euro_gap_ratio"] == 16.67
    assert hot["closes_exit_euro_gap_vs"] == "tp"
    assert hot["closes_exit_euro_gap_hot"] is True
    bit = "A exits € gap hot · 16.7× vs tp"
    assert hot["closes_exit_euro_gap_bit"] == bit
    assert format_window_a_closes_exit_euro_gap_bit(hot) == bit
    assert hot["ready"] is True

    quiet = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 1,
            "losses": 3,
            "exit_tp": 1,
            "exit_sl": 3,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 90.0,
            "exit_pnl_sl": -8.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert quiet["closes_exit_lead"] == "sl"
    assert quiet["closes_exit_euro_lead"] == "tp"
    assert quiet["closes_exit_euro_gap_ratio"] == 11.25
    assert quiet["closes_exit_euro_gap_vs"] == "sl"
    assert quiet["closes_exit_euro_gap_hot"] is False
    qbit = "A exits € gap quiet · 11.2× vs sl"
    assert quiet["closes_exit_euro_gap_bit"] == qbit

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
    glance = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "fees": 4.0,
            "realized_pnl": -188.0,
            "net_after_all_fees": -192.0,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 12.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert glance["tone"] == "warn"
    assert glance["b_ready"] is True
    assert bit in glance["line"]
    assert bit in glance["honesty_line"]
    assert "A exits € gap" not in glance["summary_line"]
    assert "ready for B" in glance["summary_line"]


def test_window_a_exit_euro_conc_speaks_share_of_abs_pnl() -> None:
    """€ concentration speaks top reason share of |exit €|. Hot warn does not block B."""
    from openbb_backend.desk import build_promote_ab_glance
    from stock_checker.promote_ab import (
        format_window_a_closes_exit_euro_conc_bit,
        window_a_sample_readiness,
    )

    assert format_window_a_closes_exit_euro_conc_bit(None) == ""

    missing = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
        }
    )
    assert missing["closes_exit_euro_conc"] is None
    assert missing["closes_exit_euro_conc_bit"] == ""
    assert missing["closes_exit_euro_conc_hot"] is False

    hot = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 12.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    # |sl| 200 / 212 ≈ 94.3%
    assert hot["closes_exit_euro_conc"] == "sl"
    assert hot["closes_exit_euro_conc_pct"] == 94.3
    assert hot["closes_exit_euro_conc_hot"] is True
    bit = "A exits € conc hot · sl · 94.3%"
    assert hot["closes_exit_euro_conc_bit"] == bit
    assert format_window_a_closes_exit_euro_conc_bit(hot) == bit
    assert hot["ready"] is True

    strong = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -20.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    # |tp| 100 / 120 ≈ 83.3%
    assert strong["closes_exit_euro_conc"] == "tp"
    assert strong["closes_exit_euro_conc_pct"] == 83.3
    assert strong["closes_exit_euro_conc_hot"] is False
    sbit = "A exits € conc strong · tp · 83.3%"
    assert strong["closes_exit_euro_conc_bit"] == sbit

    quiet = window_a_sample_readiness(
        {
            "trades": 14,
            "buys": 7,
            "sells": 4,
            "wins": 2,
            "losses": 2,
            "exit_tp": 1,
            "exit_sl": 1,
            "exit_rot": 1,
            "exit_trim": 1,
            "exit_pnl_tp": 30.0,
            "exit_pnl_sl": -28.0,
            "exit_pnl_rot": -25.0,
            "exit_pnl_trim": 22.0,
        }
    )
    # |tp| 30 / 105 ≈ 28.6%
    assert quiet["closes_exit_euro_conc"] == "tp"
    assert quiet["closes_exit_euro_conc_pct"] == 28.6
    assert quiet["closes_exit_euro_conc_hot"] is False
    qbit = "A exits € conc quiet · tp · 28.6%"
    assert quiet["closes_exit_euro_conc_bit"] == qbit

    tied = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 2,
            "losses": 2,
            "exit_tp": 2,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 50.0,
            "exit_pnl_sl": -50.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert tied["closes_exit_euro_conc"] is None
    assert tied["closes_exit_euro_conc_bit"] == ""

    mid = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "wins": 2,
            "losses": 2,
            "exit_tp": 2,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 55.0,
            "exit_pnl_sl": -45.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    # |tp| 55 / 100 = 55% mid band
    assert mid["closes_exit_euro_conc"] == "tp"
    assert mid["closes_exit_euro_conc_pct"] == 55.0
    assert mid["closes_exit_euro_conc_hot"] is False
    assert mid["closes_exit_euro_conc_bit"] == "A exits € conc · tp · 55%"

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
    glance = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 6,
            "sells": 4,
            "fees": 4.0,
            "realized_pnl": -188.0,
            "net_after_all_fees": -192.0,
            "wins": 3,
            "losses": 1,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 12.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert glance["tone"] == "warn"
    assert glance["b_ready"] is True
    assert bit in glance["line"]
    assert bit in glance["honesty_line"]
    assert "A exits € conc" not in glance["summary_line"]
    assert "ready for B" in glance["summary_line"]


def test_window_a_exit_euro_count_skew_speaks_when_shares_diverge() -> None:
    """Same reason owns count and €; share gap ≥20pp speaks. Hot warn does not block B."""
    from openbb_backend.desk import build_promote_ab_glance
    from stock_checker.promote_ab import (
        WINDOW_A_EXIT_CONC_SKEW_PP,
        format_window_a_closes_exit_euro_count_skew_bit,
        window_a_sample_readiness,
    )

    assert WINDOW_A_EXIT_CONC_SKEW_PP == 20.0
    assert format_window_a_closes_exit_euro_count_skew_bit(None) == ""

    missing = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
        }
    )
    assert missing["closes_exit_euro_count_skew_pp"] is None
    assert missing["closes_exit_euro_count_skew_bit"] == ""
    assert missing["closes_exit_euro_count_skew_hot"] is False

    # Count lead tp 75%; € conc tp 95.2% → gap 20.2pp quiet.
    quiet = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert quiet["closes_exit_lead"] == "tp"
    assert quiet["closes_exit_lead_pct"] == 75.0
    assert quiet["closes_exit_euro_conc"] == "tp"
    assert quiet["closes_exit_euro_conc_pct"] == 95.2
    assert quiet["closes_exit_euro_count_skew_pp"] == 20.2
    assert quiet["closes_exit_euro_count_skew_hot"] is False
    qbit = "A exits € skew quiet · tp · n 75% · € 95.2%"
    assert quiet["closes_exit_euro_count_skew_bit"] == qbit
    assert format_window_a_closes_exit_euro_count_skew_bit(quiet) == qbit
    assert quiet["ready"] is True

    # Count lead sl 75%; € conc sl 95.2% → hot.
    hot = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 2,
            "losses": 6,
            "exit_tp": 2,
            "exit_sl": 6,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 10.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert hot["closes_exit_lead"] == "sl"
    assert hot["closes_exit_euro_conc"] == "sl"
    assert hot["closes_exit_euro_count_skew_pp"] == 20.2
    assert hot["closes_exit_euro_count_skew_hot"] is True
    hbit = "A exits € skew hot · sl · n 75% · € 95.2%"
    assert hot["closes_exit_euro_count_skew_bit"] == hbit
    assert hot["ready"] is True

    # Same reason, thin gap stays silent.
    thin = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 80.0,
            "exit_pnl_sl": -20.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert thin["closes_exit_lead"] == "tp"
    assert thin["closes_exit_euro_conc"] == "tp"
    assert thin["closes_exit_euro_conc_pct"] == 80.0
    assert thin["closes_exit_euro_count_skew_pp"] is None
    assert thin["closes_exit_euro_count_skew_bit"] == ""

    # Reason disagree → euro lead speaks; skew stays silent.
    disagree = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 20.0,
            "exit_pnl_sl": -100.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert disagree["closes_exit_lead"] == "tp"
    assert disagree["closes_exit_euro_conc"] == "sl"
    assert disagree["closes_exit_euro_lead"] == "sl"
    assert disagree["closes_exit_euro_count_skew_bit"] == ""

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
    glance = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": -190.0,
            "net_after_all_fees": -194.0,
            "wins": 2,
            "losses": 6,
            "exit_tp": 2,
            "exit_sl": 6,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 10.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert glance["tone"] == "warn"
    assert glance["b_ready"] is True
    assert hbit in glance["line"]
    assert hbit in glance["honesty_line"]
    assert "A exits € skew" not in glance["summary_line"]
    assert "ready for B" in glance["summary_line"]


def test_window_a_exit_euro_size_speaks_fat_thin() -> None:
    """€/close of €-conc vs rest: fat ≥2× / thin ≤0.5×. Hot warn does not block B."""
    from openbb_backend.desk import build_promote_ab_glance
    from stock_checker.promote_ab import (
        format_window_a_closes_exit_euro_size_bit,
        format_window_a_closes_exit_euro_size_n_bit,
        format_window_a_closes_exit_euro_size_rest_n_bit,
        format_window_a_closes_exit_euro_size_sign_bit,
        format_window_a_closes_exit_euro_size_rest_sign_bit,
        format_window_a_closes_exit_euro_size_sign_clash_bit,
        format_window_a_closes_exit_euro_size_sign_clash_net_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit,
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit,
        window_a_sample_readiness,
    )

    assert format_window_a_closes_exit_euro_size_bit(None) == ""
    assert format_window_a_closes_exit_euro_size_n_bit(None) == ""
    assert format_window_a_closes_exit_euro_size_rest_n_bit(None) == ""
    assert format_window_a_closes_exit_euro_size_sign_bit(None) == ""
    assert format_window_a_closes_exit_euro_size_rest_sign_bit(None) == ""
    assert format_window_a_closes_exit_euro_size_sign_clash_bit(None) == ""
    assert format_window_a_closes_exit_euro_size_sign_clash_net_bit(None) == ""
    assert format_window_a_closes_exit_euro_size_sign_clash_keep_bit(None) == ""
    assert format_window_a_closes_exit_euro_size_sign_clash_keep_fees_bit(None) == ""
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit(None)
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit(
            None
        )
        == ""
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit(
            None
        )
        == ""
    )

    missing = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
        }
    )
    assert missing["closes_exit_euro_size_ratio"] is None
    assert missing["closes_exit_euro_size_bit"] == ""
    assert missing["closes_exit_euro_size_hot"] is False
    assert missing["closes_exit_euro_size_n"] == ""
    assert missing["closes_exit_euro_size_n_bit"] == ""
    assert missing["closes_exit_euro_size_n_thin"] is False
    assert missing["closes_exit_euro_size_rest_n"] == ""
    assert missing["closes_exit_euro_size_rest_n_bit"] == ""
    assert missing["closes_exit_euro_size_rest_n_thin"] is False
    assert missing["closes_exit_euro_size_sign"] == ""
    assert missing["closes_exit_euro_size_sign_pnl"] is None
    assert missing["closes_exit_euro_size_sign_bit"] == ""
    assert missing["closes_exit_euro_size_sign_loss"] is False
    assert missing["closes_exit_euro_size_rest_sign"] == ""
    assert missing["closes_exit_euro_size_rest_sign_pnl"] is None
    assert missing["closes_exit_euro_size_rest_sign_bit"] == ""
    assert missing["closes_exit_euro_size_rest_sign_loss"] is False
    assert missing["closes_exit_euro_size_sign_clash"] == ""
    assert missing["closes_exit_euro_size_sign_clash_bit"] == ""
    assert missing["closes_exit_euro_size_sign_clash_loss"] is False
    assert missing["closes_exit_euro_size_sign_clash_net"] == ""
    assert missing["closes_exit_euro_size_sign_clash_net_pnl"] is None
    assert missing["closes_exit_euro_size_sign_clash_net_bit"] == ""
    assert missing["closes_exit_euro_size_sign_clash_net_loss"] is False
    assert missing["closes_exit_euro_size_sign_clash_keep"] == ""
    assert missing["closes_exit_euro_size_sign_clash_keep_ratio"] is None
    assert missing["closes_exit_euro_size_sign_clash_keep_bit"] == ""
    assert missing["closes_exit_euro_size_sign_clash_keep_thin"] is False
    assert missing["closes_exit_euro_size_sign_clash_keep_fees"] == ""
    assert missing["closes_exit_euro_size_sign_clash_keep_fees_ratio"] is None
    assert missing["closes_exit_euro_size_sign_clash_keep_fees_bit"] == ""
    assert missing["closes_exit_euro_size_sign_clash_keep_fees_warn"] is False
    assert missing["closes_exit_euro_size_sign_clash_keep_fees_vs"] == ""
    assert missing["closes_exit_euro_size_sign_clash_keep_fees_vs_window"] == ""
    assert missing["closes_exit_euro_size_sign_clash_keep_fees_vs_bit"] == ""
    assert missing["closes_exit_euro_size_sign_clash_keep_fees_vs_warn"] is False
    assert missing["closes_exit_euro_size_sign_clash_keep_fees_vs_gap"] == ""
    assert (
        missing["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_ratio"] is None
    )
    assert missing["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit"] == ""
    assert missing["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn"] is False
    assert missing["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir"] == ""
    assert (
        missing["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_ratio"]
        is None
    )
    assert (
        missing["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit"] == ""
    )
    assert (
        missing["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn"]
        is False
    )
    assert (
        missing[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover"
        ]
        is None
    )
    assert (
        missing[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window"
        ]
        is None
    )
    assert (
        missing["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit"]
        == ""
    )
    assert (
        missing["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn"]
        is False
    )
    assert (
        missing["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta"]
        == ""
    )
    assert (
        missing[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_ratio"
        ]
        is None
    )
    assert (
        missing[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"
        ]
        == ""
    )
    assert (
        missing[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn"
        ]
        is False
    )
    assert (
        missing[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
        ]
        == ""
    )
    assert (
        missing[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit"
        ]
        == ""
    )
    assert (
        missing[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta"
        ]
        == ""
    )
    assert (
        missing[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn"
        ]
        is False
    )

    # tp avg €16.67 vs sl avg €2.5 → 6.67× fat quiet; rest n=2 thin.
    quiet = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert quiet["closes_exit_euro_conc"] == "tp"
    assert quiet["closes_exit_euro_size_ratio"] == 6.67
    assert quiet["closes_exit_euro_size_hot"] is False
    qbit = "A exits € size fat quiet · tp · 6.7×"
    assert quiet["closes_exit_euro_size_bit"] == qbit
    assert format_window_a_closes_exit_euro_size_bit(quiet) == qbit
    assert quiet["closes_exit_euro_size_n"] == "ok"
    assert quiet["closes_exit_euro_size_n_count"] == 6
    assert quiet["closes_exit_euro_size_n_thin"] is False
    qn = "A exits € size n ok · tp · 6 closes"
    assert quiet["closes_exit_euro_size_n_bit"] == qn
    assert quiet["closes_exit_euro_size_rest_n"] == "thin"
    assert quiet["closes_exit_euro_size_rest_n_count"] == 2
    assert quiet["closes_exit_euro_size_rest_n_thin"] is True
    qrn = "A exits € size rest n thin · 2 closes <3"
    assert quiet["closes_exit_euro_size_rest_n_bit"] == qrn
    assert format_window_a_closes_exit_euro_size_rest_n_bit(quiet) == qrn
    assert quiet["closes_exit_euro_size_sign"] == "win"
    assert quiet["closes_exit_euro_size_sign_pnl"] == 100.0
    assert quiet["closes_exit_euro_size_sign_loss"] is False
    qsign = "A exits € size sign win · tp · +€100"
    assert quiet["closes_exit_euro_size_sign_bit"] == qsign
    assert format_window_a_closes_exit_euro_size_sign_bit(quiet) == qsign
    assert quiet["closes_exit_euro_size_rest_sign"] == "loss"
    assert quiet["closes_exit_euro_size_rest_sign_pnl"] == -5.0
    assert quiet["closes_exit_euro_size_rest_sign_loss"] is True
    qrest = "A exits € size rest sign loss · −€5"
    assert quiet["closes_exit_euro_size_rest_sign_bit"] == qrest
    assert format_window_a_closes_exit_euro_size_rest_sign_bit(quiet) == qrest
    qclash = "A exits € size clash · lead win · rest loss"
    assert quiet["closes_exit_euro_size_sign_clash"] == "clash"
    assert quiet["closes_exit_euro_size_sign_clash_bit"] == qclash
    assert quiet["closes_exit_euro_size_sign_clash_loss"] is False
    assert format_window_a_closes_exit_euro_size_sign_clash_bit(quiet) == qclash
    qnet = "A exits € size clash net win · +€95"
    assert quiet["closes_exit_euro_size_sign_clash_net"] == "win"
    assert quiet["closes_exit_euro_size_sign_clash_net_pnl"] == 95.0
    assert quiet["closes_exit_euro_size_sign_clash_net_loss"] is False
    assert quiet["closes_exit_euro_size_sign_clash_net_bit"] == qnet
    assert format_window_a_closes_exit_euro_size_sign_clash_net_bit(quiet) == qnet
    assert quiet["closes_exit_euro_size_sign_clash_keep"] == "strong"
    assert quiet["closes_exit_euro_size_sign_clash_keep_ratio"] == 0.9
    assert quiet["closes_exit_euro_size_sign_clash_keep_thin"] is False
    qkeep = "A exits € size clash keep strong · 0.9×"
    assert quiet["closes_exit_euro_size_sign_clash_keep_bit"] == qkeep
    assert format_window_a_closes_exit_euro_size_sign_clash_keep_bit(quiet) == qkeep
    assert quiet["closes_exit_euro_size_sign_clash_keep_fees"] == ""
    assert quiet["closes_exit_euro_size_sign_clash_keep_fees_bit"] == ""
    assert quiet["closes_exit_euro_size_sign_clash_keep_fees_warn"] is False
    assert quiet["ready"] is True

    # Both sides ≥3: fat quiet + rest ok.
    both_ok = window_a_sample_readiness(
        {
            "trades": 14,
            "buys": 6,
            "sells": 8,
            "wins": 5,
            "losses": 3,
            "exit_tp": 5,
            "exit_sl": 3,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -15.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert both_ok["closes_exit_euro_conc"] == "tp"
    assert both_ok["closes_exit_euro_size_ratio"] == 4.0
    assert both_ok["closes_exit_euro_size_n"] == "ok"
    assert both_ok["closes_exit_euro_size_n_count"] == 5
    assert both_ok["closes_exit_euro_size_rest_n"] == "ok"
    assert both_ok["closes_exit_euro_size_rest_n_count"] == 3
    assert both_ok["closes_exit_euro_size_rest_n_thin"] is False
    assert both_ok["closes_exit_euro_size_rest_n_bit"] == (
        "A exits € size rest n ok · 3 closes"
    )
    assert both_ok["closes_exit_euro_size_rest_sign"] == "loss"
    assert both_ok["closes_exit_euro_size_rest_sign_pnl"] == -15.0
    assert both_ok["closes_exit_euro_size_rest_sign_bit"] == (
        "A exits € size rest sign loss · −€15"
    )
    assert both_ok["closes_exit_euro_size_sign_clash_bit"] == (
        "A exits € size clash · lead win · rest loss"
    )
    assert both_ok["closes_exit_euro_size_sign_clash_loss"] is False
    assert both_ok["closes_exit_euro_size_sign_clash_net_bit"] == (
        "A exits € size clash net win · +€85"
    )
    assert both_ok["closes_exit_euro_size_sign_clash_net_loss"] is False
    assert both_ok["closes_exit_euro_size_sign_clash_keep"] == "strong"
    assert both_ok["closes_exit_euro_size_sign_clash_keep_ratio"] == 0.74
    assert both_ok["closes_exit_euro_size_sign_clash_keep_thin"] is False
    assert both_ok["closes_exit_euro_size_sign_clash_keep_bit"] == (
        "A exits € size clash keep strong · 0.7×"
    )
    assert both_ok["ready"] is True

    # sl avg €33.33 vs tp avg €5 → 6.67× fat hot; rest n=2 thin.
    hot = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 2,
            "losses": 6,
            "exit_tp": 2,
            "exit_sl": 6,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 10.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert hot["closes_exit_euro_conc"] == "sl"
    assert hot["closes_exit_euro_size_ratio"] == 6.67
    assert hot["closes_exit_euro_size_hot"] is True
    hbit = "A exits € size fat hot · sl · 6.7×"
    assert hot["closes_exit_euro_size_bit"] == hbit
    assert hot["closes_exit_euro_size_n"] == "ok"
    assert hot["closes_exit_euro_size_n_count"] == 6
    assert hot["closes_exit_euro_size_n_bit"] == (
        "A exits € size n ok · sl · 6 closes"
    )
    assert hot["closes_exit_euro_size_rest_n"] == "thin"
    assert hot["closes_exit_euro_size_rest_n_count"] == 2
    assert hot["closes_exit_euro_size_rest_n_thin"] is True
    assert hot["closes_exit_euro_size_rest_n_bit"] == (
        "A exits € size rest n thin · 2 closes <3"
    )
    assert hot["closes_exit_euro_size_sign"] == "loss"
    assert hot["closes_exit_euro_size_sign_pnl"] == -200.0
    assert hot["closes_exit_euro_size_sign_loss"] is True
    hsign = "A exits € size sign loss · sl · −€200"
    assert hot["closes_exit_euro_size_sign_bit"] == hsign
    assert format_window_a_closes_exit_euro_size_sign_bit(hot) == hsign
    assert hot["closes_exit_euro_size_rest_sign"] == "win"
    assert hot["closes_exit_euro_size_rest_sign_pnl"] == 10.0
    assert hot["closes_exit_euro_size_rest_sign_loss"] is False
    hrest = "A exits € size rest sign win · +€10"
    assert hot["closes_exit_euro_size_rest_sign_bit"] == hrest
    hclash = "A exits € size clash · lead loss · rest win"
    assert hot["closes_exit_euro_size_sign_clash"] == "clash"
    assert hot["closes_exit_euro_size_sign_clash_bit"] == hclash
    assert hot["closes_exit_euro_size_sign_clash_loss"] is True
    assert format_window_a_closes_exit_euro_size_sign_clash_bit(hot) == hclash
    hnet = "A exits € size clash net loss · −€190"
    assert hot["closes_exit_euro_size_sign_clash_net"] == "loss"
    assert hot["closes_exit_euro_size_sign_clash_net_pnl"] == -190.0
    assert hot["closes_exit_euro_size_sign_clash_net_loss"] is True
    assert hot["closes_exit_euro_size_sign_clash_net_bit"] == hnet
    assert format_window_a_closes_exit_euro_size_sign_clash_net_bit(hot) == hnet
    assert hot["closes_exit_euro_size_sign_clash_keep"] == "strong"
    assert hot["closes_exit_euro_size_sign_clash_keep_ratio"] == 0.9
    assert hot["closes_exit_euro_size_sign_clash_keep_thin"] is False
    assert hot["closes_exit_euro_size_sign_clash_keep_bit"] == (
        "A exits € size clash keep strong · 0.9×"
    )
    assert hot["ready"] is True

    # Mid ratio stays silent (tp avg €13.33 vs sl €10 → 1.33×).
    mid = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 80.0,
            "exit_pnl_sl": -20.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert mid["closes_exit_euro_size_ratio"] is None
    assert mid["closes_exit_euro_size_bit"] == ""
    assert mid["closes_exit_euro_size_n"] == ""
    assert mid["closes_exit_euro_size_n_bit"] == ""
    assert mid["closes_exit_euro_size_rest_n"] == ""
    assert mid["closes_exit_euro_size_rest_n_bit"] == ""
    assert mid["closes_exit_euro_size_sign"] == ""
    assert mid["closes_exit_euro_size_sign_bit"] == ""
    assert mid["closes_exit_euro_size_sign_loss"] is False
    assert mid["closes_exit_euro_size_rest_sign"] == ""
    assert mid["closes_exit_euro_size_rest_sign_bit"] == ""
    assert mid["closes_exit_euro_size_rest_sign_loss"] is False
    assert mid["closes_exit_euro_size_sign_clash"] == ""
    assert mid["closes_exit_euro_size_sign_clash_bit"] == ""
    assert mid["closes_exit_euro_size_sign_clash_loss"] is False
    assert mid["closes_exit_euro_size_sign_clash_net"] == ""
    assert mid["closes_exit_euro_size_sign_clash_net_bit"] == ""
    assert mid["closes_exit_euro_size_sign_clash_net_loss"] is False
    assert mid["closes_exit_euro_size_sign_clash_keep"] == ""
    assert mid["closes_exit_euro_size_sign_clash_keep_bit"] == ""
    assert mid["closes_exit_euro_size_sign_clash_keep_thin"] is False

    # Many small tp vs one large sl: tp owns |€| but avg is thin (0.4×).
    thin = window_a_sample_readiness(
        {
            "trades": 16,
            "buys": 8,
            "sells": 8,
            "wins": 7,
            "losses": 1,
            "exit_tp": 7,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 280.0,
            "exit_pnl_sl": -100.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert thin["closes_exit_euro_conc"] == "tp"
    assert thin["closes_exit_euro_size_ratio"] == 0.4
    assert thin["closes_exit_euro_size_hot"] is False
    tbit = "A exits € size thin quiet · tp · 0.4×"
    assert thin["closes_exit_euro_size_bit"] == tbit
    assert thin["closes_exit_euro_size_n"] == "ok"
    assert thin["closes_exit_euro_size_n_count"] == 7
    assert thin["closes_exit_euro_size_rest_n"] == "thin"
    assert thin["closes_exit_euro_size_rest_n_count"] == 1
    assert thin["closes_exit_euro_size_rest_n_thin"] is True
    assert thin["closes_exit_euro_size_rest_sign"] == "loss"
    assert thin["closes_exit_euro_size_rest_sign_pnl"] == -100.0
    assert thin["closes_exit_euro_size_sign_clash_keep"] == ""
    assert thin["closes_exit_euro_size_sign_clash_keep_bit"] == ""
    assert thin["closes_exit_euro_size_sign_clash_keep_thin"] is False

    # Fat from one close: size speaks, size-n thin warns; rest ok (still ready).
    sparse = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 1,
            "losses": 7,
            "exit_tp": 1,
            "exit_sl": 7,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -14.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert sparse["closes_exit_euro_conc"] == "tp"
    assert sparse["closes_exit_euro_size_ratio"] == 50.0
    assert sparse["closes_exit_euro_size_n"] == "thin"
    assert sparse["closes_exit_euro_size_n_count"] == 1
    assert sparse["closes_exit_euro_size_n_thin"] is True
    sn = "A exits € size n thin · tp · 1 closes <3"
    assert sparse["closes_exit_euro_size_n_bit"] == sn
    assert format_window_a_closes_exit_euro_size_n_bit(sparse) == sn
    assert sparse["closes_exit_euro_size_rest_n"] == "ok"
    assert sparse["closes_exit_euro_size_rest_n_count"] == 7
    assert sparse["closes_exit_euro_size_rest_n_thin"] is False
    assert sparse["closes_exit_euro_size_rest_n_bit"] == (
        "A exits € size rest n ok · 7 closes"
    )
    assert sparse["closes_exit_euro_size_rest_sign"] == "loss"
    assert sparse["closes_exit_euro_size_rest_sign_pnl"] == -14.0
    assert sparse["ready"] is True
    assert sparse["closes_exit_euro_size_sign_clash_keep"] == "strong"
    assert sparse["closes_exit_euro_size_sign_clash_keep_ratio"] == 0.75
    assert sparse["closes_exit_euro_size_sign_clash_keep_bit"] == (
        "A exits € size clash keep strong · 0.8×"
    )
    assert sparse["closes_exit_euro_size_sign_clash_keep_thin"] is False

    # Profitable rotation is fat and hot (reason ≠ tp) but the euros won.
    rot_win = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 8,
            "losses": 0,
            "exit_tp": 4,
            "exit_sl": 0,
            "exit_rot": 4,
            "exit_trim": 0,
            "exit_pnl_tp": 20.0,
            "exit_pnl_sl": 0.0,
            "exit_pnl_rot": 80.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert rot_win["closes_exit_euro_conc"] == "rot"
    assert rot_win["closes_exit_euro_size_hot"] is True
    assert rot_win["closes_exit_euro_size_sign"] == "win"
    assert rot_win["closes_exit_euro_size_sign_pnl"] == 80.0
    assert rot_win["closes_exit_euro_size_sign_loss"] is False
    assert rot_win["closes_exit_euro_size_sign_bit"] == (
        "A exits € size sign win · rot · +€80"
    )
    assert rot_win["closes_exit_euro_size_rest_sign"] == "win"
    assert rot_win["closes_exit_euro_size_rest_sign_pnl"] == 20.0
    assert rot_win["closes_exit_euro_size_rest_sign_loss"] is False
    assert rot_win["closes_exit_euro_size_sign_clash"] == ""
    assert rot_win["closes_exit_euro_size_sign_clash_bit"] == ""
    assert rot_win["closes_exit_euro_size_sign_clash_loss"] is False
    assert rot_win["closes_exit_euro_size_sign_clash_net"] == ""
    assert rot_win["closes_exit_euro_size_sign_clash_net_bit"] == ""
    assert rot_win["closes_exit_euro_size_sign_clash_net_loss"] is False
    assert rot_win["closes_exit_euro_size_sign_clash_keep"] == ""
    assert rot_win["closes_exit_euro_size_sign_clash_keep_bit"] == ""
    assert rot_win["ready"] is True

    # Fat lead, rest euros cancel. Size speaks; rest sign stays silent.
    rest_flat = window_a_sample_readiness(
        {
            "trades": 14,
            "buys": 4,
            "sells": 10,
            "wins": 8,
            "losses": 2,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 2,
            "exit_trim": 0,
            "exit_pnl_tp": 300.0,
            "exit_pnl_sl": -50.0,
            "exit_pnl_rot": 50.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert rest_flat["closes_exit_euro_size_ratio"] is not None
    assert rest_flat["closes_exit_euro_size_rest_sign"] == ""
    assert rest_flat["closes_exit_euro_size_rest_sign_bit"] == ""
    assert rest_flat["closes_exit_euro_size_rest_sign_loss"] is False
    assert rest_flat["closes_exit_euro_size_sign"] == "win"
    assert rest_flat["closes_exit_euro_size_sign_clash"] == ""
    assert rest_flat["closes_exit_euro_size_sign_clash_bit"] == ""
    assert rest_flat["closes_exit_euro_size_sign_clash_loss"] is False
    assert rest_flat["closes_exit_euro_size_sign_clash_net"] == ""
    assert rest_flat["closes_exit_euro_size_sign_clash_net_bit"] == ""
    assert rest_flat["closes_exit_euro_size_sign_clash_keep"] == ""
    assert rest_flat["closes_exit_euro_size_sign_clash_keep_bit"] == ""

    # Lead wins on sign, but the other reasons lose more. Net is a loss.
    net_loss = window_a_sample_readiness(
        {
            "trades": 14,
            "buys": 4,
            "sells": 10,
            "wins": 6,
            "losses": 4,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 2,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -80.0,
            "exit_pnl_rot": -70.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert net_loss["closes_exit_euro_size_sign"] == "win"
    assert net_loss["closes_exit_euro_size_rest_sign"] == "loss"
    assert net_loss["closes_exit_euro_size_sign_clash"] == "clash"
    assert net_loss["closes_exit_euro_size_sign_clash_loss"] is False
    assert net_loss["closes_exit_euro_size_sign_clash_net"] == "loss"
    assert net_loss["closes_exit_euro_size_sign_clash_net_pnl"] == -50.0
    assert net_loss["closes_exit_euro_size_sign_clash_net_loss"] is True
    assert net_loss["closes_exit_euro_size_sign_clash_net_bit"] == (
        "A exits € size clash net loss · −€50"
    )
    assert net_loss["closes_exit_euro_size_sign_clash_keep"] == "thin"
    assert net_loss["closes_exit_euro_size_sign_clash_keep_ratio"] == 0.2
    assert net_loss["closes_exit_euro_size_sign_clash_keep_thin"] is True
    assert net_loss["closes_exit_euro_size_sign_clash_keep_bit"] == (
        "A exits € size clash keep thin · 0.2×"
    )
    assert net_loss["ready"] is True

    # Opposite signs that sum to zero stay silent on the net bit.
    cancel = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "exit_tp": 6,
            "exit_sl": 1,
            "exit_rot": 1,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -60.0,
            "exit_pnl_rot": -40.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert cancel["closes_exit_euro_size_sign_clash"] == "clash"
    assert cancel["closes_exit_euro_size_sign_clash_net"] == ""
    assert cancel["closes_exit_euro_size_sign_clash_net_bit"] == ""
    assert cancel["closes_exit_euro_size_sign_clash_net_loss"] is False
    assert cancel["closes_exit_euro_size_sign_clash_keep"] == "thin"
    assert cancel["closes_exit_euro_size_sign_clash_keep_ratio"] == 0.0
    assert cancel["closes_exit_euro_size_sign_clash_keep_thin"] is True
    ckeep = "A exits € size clash keep thin · 0×"
    assert cancel["closes_exit_euro_size_sign_clash_keep_bit"] == ckeep
    assert format_window_a_closes_exit_euro_size_sign_clash_keep_bit(cancel) == ckeep
    assert cancel["ready"] is True

    # Fat lead, rest close in total: leftover share sits in the mid band.
    keep_mid = window_a_sample_readiness(
        {
            "trades": 14,
            "buys": 5,
            "sells": 9,
            "wins": 5,
            "losses": 4,
            "exit_tp": 5,
            "exit_sl": 4,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -40.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert keep_mid["closes_exit_euro_size_sign_clash"] == "clash"
    assert keep_mid["closes_exit_euro_size_sign_clash_net"] == "win"
    assert keep_mid["closes_exit_euro_size_sign_clash_keep"] == ""
    assert keep_mid["closes_exit_euro_size_sign_clash_keep_bit"] == ""
    assert keep_mid["closes_exit_euro_size_sign_clash_keep_thin"] is False
    assert keep_mid["ready"] is True

    # Fat lead, rest almost as large: leftover share is thin. Warn only.
    keep_thin = window_a_sample_readiness(
        {
            "trades": 16,
            "buys": 4,
            "sells": 12,
            "wins": 5,
            "losses": 7,
            "exit_tp": 5,
            "exit_sl": 7,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -70.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert keep_thin["closes_exit_euro_size_ratio"] == 2.0
    assert keep_thin["closes_exit_euro_size_sign_clash_net"] == "win"
    assert keep_thin["closes_exit_euro_size_sign_clash_keep"] == "thin"
    assert keep_thin["closes_exit_euro_size_sign_clash_keep_ratio"] == 0.18
    assert keep_thin["closes_exit_euro_size_sign_clash_keep_thin"] is True
    assert keep_thin["closes_exit_euro_size_sign_clash_keep_bit"] == (
        "A exits € size clash keep thin · 0.2×"
    )
    assert keep_thin["ready"] is True

    def _keep_fees(fees: float | None) -> dict:
        stats = {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
        if fees is not None:
            stats["fees"] = fees
        return window_a_sample_readiness(stats)

    # Strong win leftover €95. Fees vs that leftover, not vs all realized.
    comfortable = _keep_fees(4.0)
    assert comfortable["closes_exit_euro_size_sign_clash_keep"] == "strong"
    assert comfortable["closes_exit_euro_size_sign_clash_net"] == "win"
    assert comfortable["closes_exit_euro_size_sign_clash_keep_fees"] == "comfortable"
    assert comfortable["closes_exit_euro_size_sign_clash_keep_fees_ratio"] == 0.04
    assert comfortable["closes_exit_euro_size_sign_clash_keep_fees_warn"] is False
    cfees = "A exits € size clash keep fees comfortable · 0.04×"
    assert comfortable["closes_exit_euro_size_sign_clash_keep_fees_bit"] == cfees
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_bit(comfortable)
        == cfees
    )
    assert comfortable["ready"] is True
    # No realized in the helper: fees > 0 vs realized 0 is fee-drag total.
    # Leftover stays comfortable. Moods differ. Warn only.
    assert comfortable["closes_exit_euro_size_sign_clash_keep_fees_vs"] == "worse"
    assert (
        comfortable["closes_exit_euro_size_sign_clash_keep_fees_vs_window"]
        == "total"
    )
    assert comfortable["closes_exit_euro_size_sign_clash_keep_fees_vs_warn"] is True
    cvs = "A exits € size clash keep fees vs drag worse · comfortable · total"
    assert comfortable["closes_exit_euro_size_sign_clash_keep_fees_vs_bit"] == cvs
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit(
            comfortable
        )
        == cvs
    )
    # Fee-drag total has no window ratio → gap stays silent.
    assert comfortable["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit"] == ""
    assert comfortable["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn"] is False
    assert (
        comfortable["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit"]
        == ""
    )
    assert (
        comfortable["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn"]
        is False
    )
    assert (
        comfortable[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit"
        ]
        == ""
    )
    assert (
        comfortable[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn"
        ]
        is False
    )
    assert (
        comfortable[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"
        ]
        == ""
    )
    assert (
        comfortable[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn"
        ]
        is False
    )
    assert (
        comfortable[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
        ]
        == ""
    )
    assert (
        comfortable[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit"
        ]
        == ""
    )
    assert (
        comfortable[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit"
        ]
        == ""
    )

    fees_ok = _keep_fees(30.0)
    assert fees_ok["closes_exit_euro_size_sign_clash_keep_fees"] == "ok"
    assert fees_ok["closes_exit_euro_size_sign_clash_keep_fees_ratio"] == 0.32
    assert fees_ok["closes_exit_euro_size_sign_clash_keep_fees_warn"] is False
    assert fees_ok["closes_exit_euro_size_sign_clash_keep_fees_bit"] == (
        "A exits € size clash keep fees ok · 0.32×"
    )
    assert fees_ok["ready"] is True

    fees_thin = _keep_fees(50.0)
    assert fees_thin["closes_exit_euro_size_sign_clash_keep_fees"] == "thin"
    assert fees_thin["closes_exit_euro_size_sign_clash_keep_fees_ratio"] == 0.53
    assert fees_thin["closes_exit_euro_size_sign_clash_keep_fees_warn"] is True
    assert fees_thin["closes_exit_euro_size_sign_clash_keep_fees_bit"] == (
        "A exits € size clash keep fees thin · 0.53×"
    )
    assert fees_thin["ready"] is True

    fees_eat = _keep_fees(200.0)
    assert fees_eat["closes_exit_euro_size_sign_clash_keep_fees"] == "eat"
    assert fees_eat["closes_exit_euro_size_sign_clash_keep_fees_ratio"] == 2.11
    assert fees_eat["closes_exit_euro_size_sign_clash_keep_fees_warn"] is True
    assert fees_eat["closes_exit_euro_size_sign_clash_keep_fees_bit"] == (
        "A exits € size clash keep fees eat · 2.1×"
    )
    assert fees_eat["ready"] is True
    # Thin and eat leftovers are hot. Missing realized is fee-drag total (hot).
    # Same mood stays silent.
    assert fees_thin["closes_exit_euro_size_sign_clash_keep_fees_vs_bit"] == ""
    assert fees_eat["closes_exit_euro_size_sign_clash_keep_fees_vs_bit"] == ""
    assert fees_eat["closes_exit_euro_size_sign_clash_keep_fees_vs_warn"] is False

    assert _keep_fees(0.0)["closes_exit_euro_size_sign_clash_keep_fees_bit"] == ""
    assert _keep_fees(0.0)["closes_exit_euro_size_sign_clash_keep_fees_vs_bit"] == ""

    # Hot leftover, calm book: fees eat the leftover but fees-ok is comfortable.
    better = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "fees": 200.0,
            "realized_pnl": 1000.0,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert better["closes_exit_euro_size_sign_clash_keep_fees"] == "eat"
    assert better["fees_ok_severity"] == "comfortable"
    assert better["closes_exit_euro_size_sign_clash_keep_fees_vs"] == "better"
    assert (
        better["closes_exit_euro_size_sign_clash_keep_fees_vs_window"]
        == "comfortable"
    )
    assert better["closes_exit_euro_size_sign_clash_keep_fees_vs_warn"] is False
    assert better["closes_exit_euro_size_sign_clash_keep_fees_vs_bit"] == (
        "A exits € size clash keep fees vs drag better · eat · comfortable"
    )
    # leftover eat 2.11× vs fees-ok 0.2× → gap 10.55× wide; better does not warn.
    assert better["closes_exit_euro_size_sign_clash_keep_fees_vs_gap"] == "wide"
    assert better["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_ratio"] == 10.55
    assert better["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn"] is False
    gap_better = "A exits € size clash keep fees vs drag gap wide · 10.5×"
    assert better["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit"] == gap_better
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit(
            better
        )
        == gap_better
    )
    # Directed leftover÷window = same 10.55× → above (leftover hotter).
    assert better["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir"] == "above"
    assert better["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_ratio"] == 10.55
    assert better["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn"] is False
    gap_dir_better = (
        "A exits € size clash keep fees vs drag gap dir above · 10.5×"
    )
    assert (
        better["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit"]
        == gap_dir_better
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit(
            better
        )
        == gap_dir_better
    )
    # leftover 2.11× · window 0.20× — audit the directed 10.55×.
    assert (
        better[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover"
        ]
        == 2.11
    )
    assert (
        better[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window"
        ]
        == 0.2
    )
    assert better["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn"] is False
    gap_dir_sides_better = (
        "A exits € size clash keep fees vs drag gap dir sides · "
        "leftover 2.1× · window 0.20×"
    )
    assert (
        better["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit"]
        == gap_dir_sides_better
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit(
            better
        )
        == gap_dir_sides_better
    )
    # leftover 2.11 − window 0.20 = +1.91× wide (ratio gap ≠ additive Δ).
    assert better[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta"
    ] == "wide"
    assert better[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_ratio"
    ] == 1.91
    assert better[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn"
    ] is False
    gap_dir_sides_delta_better = (
        "A exits € size clash keep fees vs drag gap dir sides Δ wide · +1.9×"
    )
    assert (
        better[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"
        ]
        == gap_dir_sides_delta_better
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit(
            better
        )
        == gap_dir_sides_delta_better
    )
    assert better[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_leftover"
    ] == 91.3
    assert better[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_window"
    ] == 8.7
    gap_dir_sides_share_better = (
        "A exits € size clash keep fees vs drag gap dir sides share · "
        "leftover 91.3% · window 8.7%"
    )
    assert (
        better[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
        ]
        == gap_dir_sides_share_better
    )
    assert better[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta"
    ] == "wide"
    assert better[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_ratio"
    ] == 82.6
    assert better[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_warn"
    ] is False
    gap_dir_sides_share_delta_better = (
        "A exits € size clash keep fees vs drag gap dir sides share Δ wide · +82.6pp"
    )
    assert (
        better[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit"
        ]
        == gap_dir_sides_share_delta_better
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit(
            better
        )
        == gap_dir_sides_share_delta_better
    )
    # Both leans are wide. Same story stays silent.
    assert (
        better[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit"
        ]
        == ""
    )
    assert better["ready"] is True

    # Same calm mood: leftover comfortable and fees-ok comfortable stay silent.
    same = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "fees": 4.0,
            "realized_pnl": 95.0,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert same["closes_exit_euro_size_sign_clash_keep_fees"] == "comfortable"
    assert same["fees_ok_severity"] == "comfortable"
    assert same["closes_exit_euro_size_sign_clash_keep_fees_vs_bit"] == ""
    assert same["closes_exit_euro_size_sign_clash_keep_fees_vs_warn"] is False
    assert same["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit"] == ""
    assert same["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit"] == ""
    assert same["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit"] == ""
    assert (
        same["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"]
        == ""
    )
    assert (
        same["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"]
        == ""
    )
    assert (
        same[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit"
        ]
        == ""
    )
    assert (
        same[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit"
        ]
        == ""
    )

    # Barely-across worse: leftover ok 0.45× vs fees-ok thin 0.5× → gap thin.
    thin_gap = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "fees": 42.75,
            "realized_pnl": 85.5,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert thin_gap["closes_exit_euro_size_sign_clash_keep_fees"] == "ok"
    assert thin_gap["fees_ok_severity"] == "thin"
    assert thin_gap["closes_exit_euro_size_sign_clash_keep_fees_vs"] == "worse"
    assert thin_gap["closes_exit_euro_size_sign_clash_keep_fees_vs_gap"] == "thin"
    assert thin_gap["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_ratio"] == 1.11
    assert thin_gap["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn"] is True
    assert thin_gap["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit"] == (
        "A exits € size clash keep fees vs drag gap thin · 1.1×"
    )
    # leftover÷window 0.45/0.5 = 0.9 → below (book hotter); worse warns.
    assert thin_gap["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir"] == "below"
    assert thin_gap["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_ratio"] == 0.9
    assert thin_gap["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn"] is True
    assert thin_gap["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit"] == (
        "A exits € size clash keep fees vs drag gap dir below · 0.90×"
    )
    assert (
        thin_gap[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover"
        ]
        == 0.45
    )
    assert (
        thin_gap[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window"
        ]
        == 0.5
    )
    assert thin_gap[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn"
    ] is True
    assert thin_gap[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit"
    ] == (
        "A exits € size clash keep fees vs drag gap dir sides · "
        "leftover 0.45× · window 0.50×"
    )
    # 0.45 − 0.50 = −0.05× thin (ratio gap 1.1× ≠ tiny additive Δ).
    assert thin_gap[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta"
    ] == "thin"
    assert thin_gap[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_ratio"
    ] == -0.05
    assert thin_gap[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn"
    ] is True
    assert thin_gap[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"
    ] == (
        "A exits € size clash keep fees vs drag gap dir sides Δ thin · −0.05×"
    )
    assert thin_gap[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
    ] == (
        "A exits € size clash keep fees vs drag gap dir sides share · "
        "leftover 47.4% · window 52.6%"
    )
    assert thin_gap[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta"
    ] == "thin"
    assert thin_gap[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_ratio"
    ] == -5.2
    assert thin_gap[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_warn"
    ] is True
    assert thin_gap[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit"
    ] == (
        "A exits € size clash keep fees vs drag gap dir sides share Δ thin · −5.2pp"
    )
    # Both leans are thin. Same story stays silent.
    assert (
        thin_gap[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit"
        ]
        == ""
    )
    assert thin_gap["ready"] is True

    # Mid × gap, wide share: leftover comfortable 0.01× vs fees-ok thin 0.50×.
    # |0.01−0.50| = 0.49× is mid, but ownership is wide.
    clash = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "fees": 0.5,
            "realized_pnl": 1.0,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert clash["closes_exit_euro_size_sign_clash_keep_fees"] == "comfortable"
    assert clash["fees_ok_severity"] == "thin"
    assert clash["closes_exit_euro_size_sign_clash_keep_fees_vs"] == "worse"
    assert (
        clash["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta"]
        == ""
    )
    assert clash[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta"
    ] == "wide"
    assert (
        clash[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta"
        ]
        == "clash"
    )
    assert (
        clash[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn"
        ]
        is True
    )
    clash_bit = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "clash · × mid · % wide"
    )
    assert (
        clash[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit"
        ]
        == clash_bit
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit(
            clash
        )
        == clash_bit
    )
    assert clash["ready"] is True

    # Thin × gap, mid share. Worse still warns.
    clash_thin = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "fees": 38.5,
            "realized_pnl": 75.075,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert clash_thin[
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta"
    ] == "thin"
    assert (
        clash_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta"
        ]
        == ""
    )
    clash_thin_bit = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "clash · × thin · % mid"
    )
    assert (
        clash_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit"
        ]
        == clash_thin_bit
    )
    assert (
        clash_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn"
        ]
        is True
    )
    assert clash_thin["ready"] is True

    # Hot leftover, calm book: same × mid / % wide clash, but better does not warn.
    clash_better = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "fees": 47.5,
            "realized_pnl": 194.75,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert clash_better["closes_exit_euro_size_sign_clash_keep_fees"] == "thin"
    assert clash_better["fees_ok_severity"] == "comfortable"
    assert clash_better["closes_exit_euro_size_sign_clash_keep_fees_vs"] == "better"
    assert (
        clash_better[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn"
        ]
        is False
    )
    assert (
        clash_better[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit"
        ]
        == clash_bit
    )
    assert clash_better["ready"] is True

    # Both × and % thin: align speaks; clash stays silent. Worse warns.
    align_thin = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "fees": 39.0,
            "realized_pnl": 77.75,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta"
        ]
        == "thin"
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta"
        ]
        == "thin"
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta"
        ]
        == ""
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align"
        ]
        == "align"
    )
    align_thin_bit = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align · thin"
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit"
        ]
        == align_thin_bit
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit(
            align_thin
        )
        == align_thin_bit
    )
    align_thin_size = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align size · −0.09× · −9.8pp"
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size"
        ]
        == "size"
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit"
        ]
        == align_thin_size
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit(
            align_thin
        )
        == align_thin_size
    )
    align_thin_lead = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align lead · %"
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead"
        ]
        == "%"
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit"
        ]
        == align_thin_lead
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit(
            align_thin
        )
        == align_thin_lead
    )
    align_thin_lead_size = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align lead size · 2.7×"
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size"
        ]
        == "size"
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_ratio"
        ]
        == 2.72
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit"
        ]
        == align_thin_lead_size
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit(
            align_thin
        )
        == align_thin_lead_size
    )
    align_thin_lead_size_sides = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align lead size sides · louder 0.49× · quieter 0.18×"
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_louder"
        ]
        == 0.49
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_quieter"
        ]
        == 0.18
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit"
        ]
        == align_thin_lead_size_sides
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit(
            align_thin
        )
        == align_thin_lead_size_sides
    )
    # Mid louder−quieter (0.49−0.18 = 0.31×) stays silent.
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta"
        ]
        == ""
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit"
        ]
        == ""
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_warn"
        ]
        is False
    )
    # Absolute sides already spoke: ownership % still speaks (Δ mid ≠ no share).
    align_thin_lead_size_sides_share = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align lead size sides share · louder 73.1% · quieter 26.9%"
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_louder_pct"
        ]
        == 73.1
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_quieter_pct"
        ]
        == 26.9
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit"
        ]
        == align_thin_lead_size_sides_share
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit(
            align_thin
        )
        == align_thin_lead_size_sides_share
    )
    # Ownership Δ: 73.1 − 26.9 = 46.2pp → wide. Worse warns.
    align_thin_lead_size_sides_share_delta = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align lead size sides share Δ wide · +46.2pp"
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta"
        ]
        == "wide"
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_ratio"
        ]
        == 46.2
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
        ]
        == align_thin_lead_size_sides_share_delta
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit(
            align_thin
        )
        == align_thin_lead_size_sides_share_delta
    )
    align_thin_lead_size_sides_share_vs_delta = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align lead size sides share vs Δ clash · × mid · % wide"
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta"
        ]
        == "clash"
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit"
        ]
        == align_thin_lead_size_sides_share_vs_delta
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit(
            align_thin
        )
        == align_thin_lead_size_sides_share_vs_delta
    )
    # Mid × / wide % → clash; align stays silent.
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align"
        ]
        == ""
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit"
        ]
        == ""
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit"
        ]
        == ""
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead"
        ]
        == ""
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size"
        ]
        == ""
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit"
        ]
        == ""
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta"
        ]
        == ""
    )
    assert (
        align_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit"
        ]
        == ""
    )
    assert align_thin["ready"] is True

    # Wide louder−quieter floor-units: sides Δ speaks. Worse warns.
    align_wide = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "fees": 0.5,
            "realized_pnl": 0.75,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta"
        ]
        == "wide"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_ratio"
        ]
        == 3.53
    )
    align_wide_sides_delta = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align lead size sides Δ wide · +3.5×"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit"
        ]
        == align_wide_sides_delta
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit(
            align_wide
        )
        == align_wide_sides_delta
    )
    align_wide_sides_share = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align lead size sides share · louder 78.6% · quieter 21.4%"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_louder_pct"
        ]
        == 78.6
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_quieter_pct"
        ]
        == 21.4
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit"
        ]
        == align_wide_sides_share
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit(
            align_wide
        )
        == align_wide_sides_share
    )
    align_wide_sides_share_delta = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align lead size sides share Δ wide · +57.2pp"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta"
        ]
        == "wide"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_ratio"
        ]
        == 57.2
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
        ]
        == align_wide_sides_share_delta
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit(
            align_wide
        )
        == align_wide_sides_share_delta
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta"
        ]
        == ""
    )
    # Wide × / wide % → align confirm. Worse warns.
    align_wide_sides_share_vs_delta_align = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align lead size sides share vs Δ align · wide"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align"
        ]
        == "align"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit"
        ]
        == align_wide_sides_share_vs_delta_align
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit(
            align_wide
        )
        == align_wide_sides_share_vs_delta_align
    )
    align_wide_sides_share_vs_delta_align_size = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align lead size sides share vs Δ align size · +3.5× · +57.2pp"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size"
        ]
        == "size"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit"
        ]
        == align_wide_sides_share_vs_delta_align_size
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit(
            align_wide
        )
        == align_wide_sides_share_vs_delta_align_size
    )
    # Nested size shows both spreads; lead names the louder one (×).
    align_wide_sides_share_vs_delta_align_lead = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align lead size sides share vs Δ align lead · ×"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead"
        ]
        == "×"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_bit"
        ]
        == align_wide_sides_share_vs_delta_align_lead
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_bit(
            align_wide
        )
        == align_wide_sides_share_vs_delta_align_lead
    )
    # Nested lead names ×; size is louder÷quieter floor-units.
    align_wide_sides_share_vs_delta_align_lead_size = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align lead size sides share vs Δ align lead size · 2.5×"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size"
        ]
        == "size"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_ratio"
        ]
        == 2.47
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit"
        ]
        == align_wide_sides_share_vs_delta_align_lead_size
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit(
            align_wide
        )
        == align_wide_sides_share_vs_delta_align_lead_size
    )
    # Nested lead size is the margin; sides name both floor-units.
    align_wide_sides_share_vs_delta_align_lead_size_sides = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align lead size sides share vs Δ align lead size sides · "
        "louder 7.1× · quieter 2.9×"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_louder"
        ]
        == 7.06
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_quieter"
        ]
        == 2.86
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit"
        ]
        == align_wide_sides_share_vs_delta_align_lead_size_sides
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit(
            align_wide
        )
        == align_wide_sides_share_vs_delta_align_lead_size_sides
    )
    # Nested sides name both floor-units; Δ is the additive spread.
    align_wide_sides_share_vs_delta_align_lead_size_sides_delta = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align lead size sides share vs Δ align lead size sides Δ wide · +4.2×"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta"
        ]
        == "wide"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_ratio"
        ]
        == 4.2
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit"
        ]
        == align_wide_sides_share_vs_delta_align_lead_size_sides_delta
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit(
            align_wide
        )
        == align_wide_sides_share_vs_delta_align_lead_size_sides_delta
    )
    # Nested sides name both floor-units; share speaks ownership %.
    align_wide_sides_share_vs_delta_align_lead_size_sides_share = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align lead size sides share vs Δ align lead size sides share · "
        "louder 71.2% · quieter 28.8%"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_louder_pct"
        ]
        == 71.2
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_quieter_pct"
        ]
        == 28.8
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit"
        ]
        == align_wide_sides_share_vs_delta_align_lead_size_sides_share
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit(
            align_wide
        )
        == align_wide_sides_share_vs_delta_align_lead_size_sides_share
    )
    # Nested share names both %; Δ speaks the pp spread.
    align_wide_sides_share_vs_delta_align_lead_size_sides_share_delta = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align lead size sides share vs Δ align lead size sides share Δ "
        "wide · +42.4pp"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta"
        ]
        == "wide"
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_ratio"
        ]
        == 42.4
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
        ]
        == align_wide_sides_share_vs_delta_align_lead_size_sides_share_delta
    )
    assert (
        align_wide[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_warn"
        ]
        is True
    )
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit(
            align_wide
        )
        == align_wide_sides_share_vs_delta_align_lead_size_sides_share_delta
    )
    # Nested sides Δ wide / share Δ wide → clash silent; align confirm.
    assert align_wide["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta"] == ""
    assert align_wide["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit"] == ""
    assert align_wide["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_warn"] is False
    align_wide_nested_share_vs_delta_align = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align lead size sides share vs Δ align lead size sides share vs Δ "
        "align · wide"
    )
    assert align_wide["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align"] == "align"
    assert (
        align_wide["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit"]
        == align_wide_nested_share_vs_delta_align
    )
    assert align_wide["closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn"] is True
    assert (
        format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit(align_wide)
        == align_wide_nested_share_vs_delta_align
    )
    assert align_wide["ready"] is True

    # Thin louder−quieter floor-units: sides Δ speaks. Worse warns.
    align_sides_thin = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "fees": 40.4,
            "realized_pnl": 80.25,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }
    )
    assert (
        align_sides_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta"
        ]
        == "thin"
    )
    assert (
        align_sides_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_warn"
        ]
        is True
    )
    assert "align lead size sides Δ thin" in (
        align_sides_thin[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit"
        ]
    )
    assert align_sides_thin["ready"] is True
    glance_lead_size = build_promote_ab_glance(
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
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "fees": 39.0,
            "realized_pnl": 77.75,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert align_thin_lead_size in glance_lead_size["align_nest_line"]
    assert align_thin_lead_size not in glance_lead_size["fee_pressure_line"]
    assert align_thin_lead_size in glance_lead_size["honesty_line"]
    assert align_thin_lead_size_sides in glance_lead_size["align_nest_line"]
    assert align_thin_lead_size_sides in glance_lead_size["honesty_line"]
    assert align_thin_lead_size_sides_share in glance_lead_size["align_nest_line"]
    assert align_thin_lead_size_sides_share in glance_lead_size["honesty_line"]
    assert align_thin_lead_size_sides_share_delta in glance_lead_size["align_nest_line"]
    assert align_thin_lead_size_sides_share_delta in glance_lead_size["honesty_line"]
    assert align_thin_lead_size_sides_share_vs_delta in glance_lead_size["align_nest_line"]
    assert (
        glance_lead_size[
            "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit"
        ]
        == align_thin_lead_size_sides_share_vs_delta
    )
    assert "align lead size sides Δ" not in glance_lead_size["fee_pressure_line"]
    assert "align lead size" not in glance_lead_size["honesty_core"]
    assert glance_lead_size["tone"] == "warn"
    assert glance_lead_size["b_ready"] is True

    glance_sides_delta = build_promote_ab_glance(
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
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "fees": 0.5,
            "realized_pnl": 0.75,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert align_wide_sides_delta in glance_sides_delta["align_nest_line"]
    assert align_wide_sides_delta not in glance_sides_delta["fee_pressure_line"]
    assert align_wide_sides_delta in glance_sides_delta["honesty_line"]
    assert align_wide_sides_delta not in glance_sides_delta["honesty_core"]
    assert align_wide_sides_share in glance_sides_delta["align_nest_line"]
    assert align_wide_sides_share in glance_sides_delta["honesty_line"]
    assert align_wide_sides_share_delta in glance_sides_delta["align_nest_line"]
    assert align_wide_sides_share_delta in glance_sides_delta["honesty_line"]
    assert (
        glance_sides_delta[
            "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit"
        ]
        == align_wide_sides_delta
    )
    assert (
        glance_sides_delta[
            "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit"
        ]
        == align_wide_sides_share
    )
    assert (
        glance_sides_delta[
            "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
        ]
        == align_wide_sides_share_delta
    )
    assert align_wide_sides_share_vs_delta_align in glance_sides_delta["align_nest_line"]
    assert align_wide_sides_share_vs_delta_align in glance_sides_delta["honesty_line"]
    assert align_wide_sides_share_vs_delta_align_size in glance_sides_delta["align_deep_line"]
    assert align_wide_sides_share_vs_delta_align_size not in glance_sides_delta["align_nest_line"]
    assert align_wide_sides_share_vs_delta_align_size in glance_sides_delta["honesty_line"]
    assert (
        glance_sides_delta[
            "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit"
        ]
        == align_wide_sides_share_vs_delta_align
    )
    assert (
        glance_sides_delta[
            "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit"
        ]
        == align_wide_sides_share_vs_delta_align_size
    )
    assert align_wide_sides_share_vs_delta_align_lead in glance_sides_delta["align_deep_line"]
    assert align_wide_sides_share_vs_delta_align_lead not in glance_sides_delta["align_nest_line"]
    assert align_wide_sides_share_vs_delta_align_lead in glance_sides_delta["honesty_line"]
    assert (
        glance_sides_delta[
            "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_bit"
        ]
        == align_wide_sides_share_vs_delta_align_lead
    )
    assert align_wide_sides_share_vs_delta_align_lead_size in glance_sides_delta["align_deep_line"]
    assert align_wide_sides_share_vs_delta_align_lead_size not in glance_sides_delta["align_nest_line"]
    assert align_wide_sides_share_vs_delta_align_lead_size in glance_sides_delta["honesty_line"]
    assert (
        glance_sides_delta[
            "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit"
        ]
        == align_wide_sides_share_vs_delta_align_lead_size
    )
    assert align_wide_sides_share_vs_delta_align_lead_size_sides in glance_sides_delta[
        "align_deep_line"
    ]
    assert align_wide_sides_share_vs_delta_align_lead_size_sides not in glance_sides_delta[
        "align_nest_line"
    ]
    assert align_wide_sides_share_vs_delta_align_lead_size_sides in glance_sides_delta[
        "honesty_line"
    ]
    assert (
        glance_sides_delta[
            "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit"
        ]
        == align_wide_sides_share_vs_delta_align_lead_size_sides
    )
    assert align_wide_sides_share_vs_delta_align_lead_size_sides_delta in glance_sides_delta[
        "align_deep_line"
    ]
    assert align_wide_sides_share_vs_delta_align_lead_size_sides_delta not in glance_sides_delta[
        "align_nest_line"
    ]
    assert align_wide_sides_share_vs_delta_align_lead_size_sides_delta in glance_sides_delta[
        "honesty_line"
    ]
    assert (
        glance_sides_delta[
            "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit"
        ]
        == align_wide_sides_share_vs_delta_align_lead_size_sides_delta
    )
    assert align_wide_sides_share_vs_delta_align_lead_size_sides_share in glance_sides_delta[
        "align_deep_line"
    ]
    assert align_wide_sides_share_vs_delta_align_lead_size_sides_share not in glance_sides_delta[
        "align_nest_line"
    ]
    assert align_wide_sides_share_vs_delta_align_lead_size_sides_share in glance_sides_delta[
        "honesty_line"
    ]
    assert (
        glance_sides_delta[
            "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit"
        ]
        == align_wide_sides_share_vs_delta_align_lead_size_sides_share
    )
    assert align_wide_sides_share_vs_delta_align_lead_size_sides_share_delta in glance_sides_delta[
        "align_deep_line"
    ]
    assert align_wide_sides_share_vs_delta_align_lead_size_sides_share_delta not in glance_sides_delta[
        "align_nest_line"
    ]
    assert align_wide_sides_share_vs_delta_align_lead_size_sides_share_delta in glance_sides_delta[
        "honesty_line"
    ]
    assert (
        glance_sides_delta[
            "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
        ]
        == align_wide_sides_share_vs_delta_align_lead_size_sides_share_delta
    )
    assert align_wide_nested_share_vs_delta_align in glance_sides_delta[
        "align_deep_line"
    ]
    assert align_wide_nested_share_vs_delta_align not in glance_sides_delta[
        "align_nest_line"
    ]
    assert align_wide_nested_share_vs_delta_align in glance_sides_delta[
        "honesty_line"
    ]
    assert (
        glance_sides_delta["a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit"]
        == align_wide_nested_share_vs_delta_align
    )
    assert "align deep" in glance_sides_delta["honesty_warns"]
    assert glance_sides_delta["tone"] == "warn"
    assert glance_sides_delta["b_ready"] is True

    from stock_checker.promote_ab import (
        _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead as _align_lead,
        _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size as _align_lead_size,
        _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides as _align_lead_size_sides,
        _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta as _align_lead_size_sides_delta,
        _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share as _align_lead_size_sides_share,
        _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta as _align_lead_size_sides_share_delta,
        _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta as _align_lead_size_sides_share_vs_delta,
        _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align as _align_lead_size_sides_share_vs_delta_align,
        _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size as _nested_align_size,
        _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead as _nested_align_lead,
        _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size as _nested_align_lead_size,
        _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides as _nested_align_lead_size_sides,
        _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta as _nested_align_lead_size_sides_delta,
        _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share as _nested_align_lead_size_sides_share,
        _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta as _nested_align_lead_size_sides_share_delta,
        _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta as _nested_align_lead_size_sides_share_vs_delta,
        _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align as _nested_align_lead_size_sides_share_vs_delta_align,
        _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size as _align_size,
    )

    nested_size, nested_size_bit, nested_size_warn = _nested_align_size(
        "align", "worse", 3.53, 57.2
    )
    assert nested_size == "size"
    assert nested_size_warn is True
    assert "align lead size sides share vs Δ align size · +3.5× · +57.2pp" in (
        nested_size_bit
    )
    nested_lead, nested_lead_bit, nested_lead_warn = _nested_align_lead(
        "size", "worse", 3.53, 57.2
    )
    assert nested_lead == "×"
    assert nested_lead_warn is True
    assert "align lead size sides share vs Δ align lead · ×" in nested_lead_bit
    nested_lead_pct, nested_lead_pct_bit, nested_lead_pct_warn = _nested_align_lead(
        "size", "worse", 0.09, 57.2
    )
    assert nested_lead_pct == "%"
    assert nested_lead_pct_warn is True
    assert "align lead size sides share vs Δ align lead · %" in nested_lead_pct_bit
    nested_lead_even = _nested_align_lead("size", "worse", 2.0, 96.0)
    assert nested_lead_even == ("", "", False)
    nested_lead_silent = _nested_align_lead("clash", "worse", 3.53, 57.2)
    assert nested_lead_silent == ("", "", False)
    nested_ls, nested_lr, nested_lsb, nested_lsw = _nested_align_lead_size(
        "×", "worse", 3.53, 57.2
    )
    assert nested_ls == "size"
    assert nested_lr == 2.47
    assert nested_lsw is True
    assert "align lead size sides share vs Δ align lead size · 2.5×" in nested_lsb
    nested_ls_pct, nested_lr_pct, nested_lsb_pct, nested_lsw_pct = _nested_align_lead_size(
        "%", "worse", 0.09, 57.2
    )
    assert nested_ls_pct == "size"
    assert nested_lr_pct == 15.89
    assert nested_lsw_pct is True
    assert "align lead size sides share vs Δ align lead size · 15.9×" in nested_lsb_pct
    nested_ls_even = _nested_align_lead_size("", "worse", 3.53, 57.2)
    assert nested_ls_even == ("", None, "", False)
    nested_ls_silent = _nested_align_lead_size("clash", "worse", 3.53, 57.2)
    assert nested_ls_silent == ("", None, "", False)
    nested_lss_l, nested_lss_q, nested_lss_b, nested_lss_w = (
        _nested_align_lead_size_sides("size", "×", "worse", 3.53, 57.2)
    )
    assert nested_lss_l == 7.06
    assert nested_lss_q == 2.86
    assert nested_lss_w is True
    assert (
        "align lead size sides share vs Δ align lead size sides · "
        "louder 7.1× · quieter 2.9×"
    ) in nested_lss_b
    nested_lss_pct_l, nested_lss_pct_q, nested_lss_pct_b, nested_lss_pct_w = (
        _nested_align_lead_size_sides("size", "%", "worse", 0.09, 57.2)
    )
    assert nested_lss_pct_l == 2.86
    assert nested_lss_pct_q == 0.18
    assert nested_lss_pct_w is True
    assert (
        "align lead size sides share vs Δ align lead size sides · "
        "louder 2.9× · quieter 0.18×"
    ) in nested_lss_pct_b
    nested_lss_silent = _nested_align_lead_size_sides("", "×", "worse", 3.53, 57.2)
    assert nested_lss_silent == (None, None, "", False)
    nested_lssd, nested_lssdr, nested_lssdb, nested_lssdw = (
        _nested_align_lead_size_sides_delta(
            "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
            "align lead size sides share vs Δ align lead size sides · "
            "louder 7.1× · quieter 2.9×",
            "worse",
            7.06,
            2.86,
        )
    )
    assert nested_lssd == "wide"
    assert nested_lssdr == 4.2
    assert nested_lssdw is True
    assert "align lead size sides share vs Δ align lead size sides Δ wide · +4.2×" in (
        nested_lssdb
    )
    nested_lssd_thin, nested_lssdr_thin, nested_lssdb_thin, nested_lssdw_thin = (
        _nested_align_lead_size_sides_delta(
            "sides spoke",
            "worse",
            0.3,
            0.2,
        )
    )
    assert nested_lssd_thin == "thin"
    assert nested_lssdr_thin == 0.1
    assert nested_lssdw_thin is True
    assert "align lead size sides share vs Δ align lead size sides Δ thin · +0.10×" in (
        nested_lssdb_thin
    )
    nested_lssd_silent = _nested_align_lead_size_sides_delta("", "worse", 7.06, 2.86)
    assert nested_lssd_silent == ("", None, "", False)
    nested_lssd_mid = _nested_align_lead_size_sides_delta(
        "sides spoke", "worse", 0.5, 0.2
    )
    assert nested_lssd_mid == ("", None, "", False)
    nested_lsss_l, nested_lsss_q, nested_lsss_b, nested_lsss_w = (
        _nested_align_lead_size_sides_share(
            "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
            "align lead size sides share vs Δ align lead size sides · "
            "louder 7.1× · quieter 2.9×",
            "worse",
            7.06,
            2.86,
        )
    )
    assert nested_lsss_l == 71.2
    assert nested_lsss_q == 28.8
    assert nested_lsss_w is True
    assert (
        "align lead size sides share vs Δ align lead size sides share · "
        "louder 71.2% · quieter 28.8%"
    ) in nested_lsss_b
    nested_lsss_pct_l, nested_lsss_pct_q, nested_lsss_pct_b, nested_lsss_pct_w = (
        _nested_align_lead_size_sides_share(
            "sides spoke",
            "worse",
            2.86,
            0.18,
        )
    )
    assert nested_lsss_pct_l == 94.1
    assert nested_lsss_pct_q == 5.9
    assert nested_lsss_pct_w is True
    assert (
        "align lead size sides share vs Δ align lead size sides share · "
        "louder 94.1% · quieter 5.9%"
    ) in nested_lsss_pct_b
    nested_lsss_silent = _nested_align_lead_size_sides_share("", "worse", 7.06, 2.86)
    assert nested_lsss_silent == (None, None, "", False)
    nested_lsss_better = _nested_align_lead_size_sides_share(
        "sides spoke", "better", 7.06, 2.86
    )
    assert nested_lsss_better[3] is False
    assert nested_lsss_better[0] == 71.2
    nested_lsssd, nested_lsssd_r, nested_lsssd_b, nested_lsssd_w = (
        _nested_align_lead_size_sides_share_delta(
            nested_lsss_b,
            "worse",
            71.2,
            28.8,
        )
    )
    assert nested_lsssd == "wide"
    assert nested_lsssd_r == 42.4
    assert nested_lsssd_w is True
    assert (
        "align lead size sides share vs Δ align lead size sides share Δ "
        "wide · +42.4pp"
    ) in nested_lsssd_b
    nested_lsssd_pct, nested_lsssd_pct_r, nested_lsssd_pct_b, nested_lsssd_pct_w = (
        _nested_align_lead_size_sides_share_delta(
            nested_lsss_pct_b,
            "worse",
            94.1,
            5.9,
        )
    )
    assert nested_lsssd_pct == "wide"
    assert nested_lsssd_pct_r == 88.2
    assert nested_lsssd_pct_w is True
    assert (
        "align lead size sides share vs Δ align lead size sides share Δ "
        "wide · +88.2pp"
    ) in nested_lsssd_pct_b
    nested_lsssd_thin, nested_lsssd_thin_r, nested_lsssd_thin_b, nested_lsssd_thin_w = (
        _nested_align_lead_size_sides_share_delta(
            "share spoke",
            "worse",
            52.0,
            48.0,
        )
    )
    assert nested_lsssd_thin == "thin"
    assert nested_lsssd_thin_r == 4.0
    assert nested_lsssd_thin_w is True
    assert (
        "align lead size sides share vs Δ align lead size sides share Δ "
        "thin · +4pp"
    ) in nested_lsssd_thin_b
    nested_lsssd_mid = _nested_align_lead_size_sides_share_delta(
        "share spoke", "worse", 57.0, 43.0
    )
    assert nested_lsssd_mid == ("", None, "", False)
    nested_lsssd_silent = _nested_align_lead_size_sides_share_delta(
        "", "worse", 71.2, 28.8
    )
    assert nested_lsssd_silent == ("", None, "", False)
    nested_lsssd_better = _nested_align_lead_size_sides_share_delta(
        "share spoke", "better", 71.2, 28.8
    )
    assert nested_lsssd_better[3] is False
    assert nested_lsssd_better[0] == "wide"
    nested_share_clash, nested_share_clash_bit, nested_share_clash_warn = (
        _nested_align_lead_size_sides_share_vs_delta("", "wide", "worse")
    )
    assert nested_share_clash == "clash"
    assert nested_share_clash_warn is True
    assert (
        "align lead size sides share vs Δ align lead size sides share vs Δ "
        "clash · × mid · % wide"
    ) in nested_share_clash_bit
    same_nested_vs = _nested_align_lead_size_sides_share_vs_delta(
        "wide", "wide", "worse"
    )
    assert same_nested_vs == ("", "", False)
    silent_nested_vs = _nested_align_lead_size_sides_share_vs_delta("", "", "worse")
    assert silent_nested_vs == ("", "", False)
    nested_share_align, nested_share_align_bit, nested_share_align_warn = (
        _nested_align_lead_size_sides_share_vs_delta_align("wide", "wide", "worse")
    )
    assert nested_share_align == "align"
    assert nested_share_align_warn is True
    assert (
        "align lead size sides share vs Δ align lead size sides share vs Δ "
        "align · wide"
    ) in nested_share_align_bit
    thin_nested_align, thin_nested_align_bit, thin_nested_align_warn = (
        _nested_align_lead_size_sides_share_vs_delta_align("thin", "thin", "better")
    )
    assert thin_nested_align == "align"
    assert thin_nested_align_warn is False
    assert (
        "align lead size sides share vs Δ align lead size sides share vs Δ "
        "align · thin"
    ) in thin_nested_align_bit
    clash_no_nested_align = _nested_align_lead_size_sides_share_vs_delta_align(
        "", "wide", "worse"
    )
    assert clash_no_nested_align == ("", "", False)
    mismatch_nested_align = _nested_align_lead_size_sides_share_vs_delta_align(
        "wide", "thin", "worse"
    )
    assert mismatch_nested_align == ("", "", False)
    nested_clash, nested_clash_bit, nested_clash_warn = _nested_align_size(
        "clash", "worse", 3.53, 57.2
    )
    assert nested_clash == ""
    assert nested_clash_bit == ""
    assert nested_clash_warn is False
    better_label, better_bit, better_warn = _align_size("align", "better", -0.09, -9.8)
    assert better_label == "size"
    assert better_warn is False
    assert "align size · −0.09× · −9.8pp" in better_bit
    silent_label, silent_bit, silent_warn = _align_size("clash", "worse", -0.09, -9.8)
    assert silent_label == ""
    assert silent_bit == ""
    assert silent_warn is False
    lead_pct, lead_pct_bit, lead_pct_warn = _align_lead("size", "worse", -0.09, -9.8)
    assert lead_pct == "%"
    assert lead_pct_warn is True
    assert "align lead · %" in lead_pct_bit
    lead_x, lead_x_bit, lead_x_warn = _align_lead("size", "better", -2.0, -10.0)
    assert lead_x == "×"
    assert lead_x_warn is False
    assert "align lead · ×" in lead_x_bit
    even_label, even_bit, even_warn = _align_lead("size", "worse", -2.0, -96.0)
    assert even_label == ""
    assert even_bit == ""
    assert even_warn is False
    clash_lead, clash_lead_bit, clash_lead_warn = _align_lead(
        "clash", "worse", -0.09, -9.8
    )
    assert clash_lead == ""
    assert clash_lead_bit == ""
    assert clash_lead_warn is False
    pct_size, pct_ratio, pct_size_bit, pct_size_warn = _align_lead_size(
        "%", "worse", -0.09, -9.8
    )
    assert pct_size == "size"
    assert pct_ratio == 2.72
    assert pct_size_warn is True
    assert "align lead size · 2.7×" in pct_size_bit
    x_size, x_ratio, x_size_bit, x_size_warn = _align_lead_size(
        "×", "better", -2.0, -10.0
    )
    assert x_size == "size"
    assert x_ratio == 8.0
    assert x_size_warn is False
    assert "align lead size · 8×" in x_size_bit
    even_size, even_ratio, even_size_bit, even_size_warn = _align_lead_size(
        "", "worse", -2.0, -96.0
    )
    assert even_size == ""
    assert even_ratio is None
    assert even_size_bit == ""
    assert even_size_warn is False
    pct_louder, pct_quieter, pct_sides_bit, pct_sides_warn = _align_lead_size_sides(
        "size", "%", "worse", -0.09, -9.8
    )
    assert pct_louder == 0.49
    assert pct_quieter == 0.18
    assert pct_sides_warn is True
    assert "align lead size sides · louder 0.49× · quieter 0.18×" in pct_sides_bit
    x_louder, x_quieter, x_sides_bit, x_sides_warn = _align_lead_size_sides(
        "size", "×", "better", -2.0, -10.0
    )
    assert x_louder == 4.0
    assert x_quieter == 0.5
    assert x_sides_warn is False
    assert "align lead size sides · louder 4× · quieter 0.50×" in x_sides_bit
    silent_sides = _align_lead_size_sides("", "%", "worse", -0.09, -9.8)
    assert silent_sides == (None, None, "", False)
    pct_delta, pct_delta_r, pct_delta_bit, pct_delta_warn = _align_lead_size_sides_delta(
        pct_sides_bit, "worse", 0.49, 0.18
    )
    assert pct_delta == ""
    assert pct_delta_r is None
    assert pct_delta_bit == ""
    assert pct_delta_warn is False
    x_delta, x_delta_r, x_delta_bit, x_delta_warn = _align_lead_size_sides_delta(
        x_sides_bit, "better", 4.0, 0.5
    )
    assert x_delta == "wide"
    assert x_delta_r == 3.5
    assert x_delta_warn is False
    assert "align lead size sides Δ wide · +3.5×" in x_delta_bit
    thin_delta, thin_delta_r, thin_delta_bit, thin_delta_warn = (
        _align_lead_size_sides_delta("sides", "worse", 0.38, 0.14)
    )
    assert thin_delta == "thin"
    assert thin_delta_r == 0.24
    assert thin_delta_warn is True
    assert "align lead size sides Δ thin · +0.24×" in thin_delta_bit
    silent_delta = _align_lead_size_sides_delta("", "worse", 4.0, 0.5)
    assert silent_delta == ("", None, "", False)
    pct_share_l, pct_share_q, pct_share_bit, pct_share_warn = (
        _align_lead_size_sides_share(pct_sides_bit, "worse", 0.49, 0.18)
    )
    assert pct_share_l == 73.1
    assert pct_share_q == 26.9
    assert pct_share_warn is True
    assert "align lead size sides share · louder 73.1% · quieter 26.9%" in (
        pct_share_bit
    )
    x_share_l, x_share_q, x_share_bit, x_share_warn = _align_lead_size_sides_share(
        x_sides_bit, "better", 4.0, 0.5
    )
    assert x_share_l == 88.9
    assert x_share_q == 11.1
    assert x_share_warn is False
    assert "align lead size sides share · louder 88.9% · quieter 11.1%" in x_share_bit
    silent_share = _align_lead_size_sides_share("", "worse", 4.0, 0.5)
    assert silent_share == (None, None, "", False)
    pct_share_d, pct_share_dr, pct_share_db, pct_share_dw = (
        _align_lead_size_sides_share_delta(pct_share_bit, "worse", 73.1, 26.9)
    )
    assert pct_share_d == "wide"
    assert pct_share_dr == 46.2
    assert pct_share_dw is True
    assert "align lead size sides share Δ wide · +46.2pp" in pct_share_db
    x_share_d, x_share_dr, x_share_db, x_share_dw = _align_lead_size_sides_share_delta(
        x_share_bit, "better", 88.9, 11.1
    )
    assert x_share_d == "wide"
    assert x_share_dr == 77.8
    assert x_share_dw is False
    assert "align lead size sides share Δ wide · +77.8pp" in x_share_db
    thin_share_d, thin_share_dr, thin_share_db, thin_share_dw = (
        _align_lead_size_sides_share_delta("share", "worse", 52.0, 48.0)
    )
    assert thin_share_d == "thin"
    assert thin_share_dr == 4.0
    assert thin_share_dw is True
    assert "align lead size sides share Δ thin · +4pp" in thin_share_db
    mid_share_d = _align_lead_size_sides_share_delta("share", "worse", 55.0, 45.0)
    assert mid_share_d == ("", None, "", False)
    silent_share_d = _align_lead_size_sides_share_delta("", "worse", 73.1, 26.9)
    assert silent_share_d == ("", None, "", False)
    lead_clash_vs, lead_clash_bit, lead_clash_warn = (
        _align_lead_size_sides_share_vs_delta("", "wide", "worse")
    )
    assert lead_clash_vs == "clash"
    assert lead_clash_warn is True
    assert "align lead size sides share vs Δ clash · × mid · % wide" in lead_clash_bit
    same_vs, same_bit, same_warn = _align_lead_size_sides_share_vs_delta(
        "wide", "wide", "worse"
    )
    assert same_vs == ""
    silent_vs = _align_lead_size_sides_share_vs_delta("", "", "worse")
    assert silent_vs == ("", "", False)
    lead_align_vs, lead_align_bit, lead_align_warn = (
        _align_lead_size_sides_share_vs_delta_align("wide", "wide", "worse")
    )
    assert lead_align_vs == "align"
    assert lead_align_warn is True
    assert "align lead size sides share vs Δ align · wide" in lead_align_bit
    thin_align_vs, thin_align_bit, thin_align_warn = (
        _align_lead_size_sides_share_vs_delta_align("thin", "thin", "better")
    )
    assert thin_align_vs == "align"
    assert thin_align_warn is False
    assert "align lead size sides share vs Δ align · thin" in thin_align_bit
    clash_no_align = _align_lead_size_sides_share_vs_delta_align("", "wide", "worse")
    assert clash_no_align == ("", "", False)
    mismatch_align = _align_lead_size_sides_share_vs_delta_align(
        "wide", "thin", "worse"
    )
    assert mismatch_align == ("", "", False)

    # Mid × / wide % clash: align stays silent (not a same-lean confirm).
    assert (
        clash[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align"
        ]
        == ""
    )
    assert (
        clash[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size"
        ]
        == ""
    )
    assert (
        clash[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead"
        ]
        == ""
    )
    assert (
        clash[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size"
        ]
        == ""
    )
    assert (
        clash[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit"
        ]
        == ""
    )
    assert (
        clash[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta"
        ]
        == ""
    )
    assert (
        clash[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit"
        ]
        == ""
    )
    assert (
        clash[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta"
        ]
        == ""
    )
    assert (
        clash[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta"
        ]
        == ""
    )
    assert (
        clash[
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align"
        ]
        == ""
    )

    glance_clash = build_promote_ab_glance(
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
            "buys": 4,
            "sells": 8,
            "wins": 6,
            "losses": 2,
            "fees": 0.5,
            "realized_pnl": 1.0,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert clash_bit in glance_clash["fee_pressure_line"]
    assert clash_bit in glance_clash["honesty_line"]
    assert "share vs Δ" not in glance_clash["honesty_core"]
    assert glance_clash["tone"] == "warn"
    assert glance_clash["b_ready"] is True

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
    glance = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": -190.0,
            "net_after_all_fees": -194.0,
            "wins": 2,
            "losses": 6,
            "exit_tp": 2,
            "exit_sl": 6,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 10.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert glance["tone"] == "warn"
    assert glance["b_ready"] is True
    assert hbit in glance["line"]
    assert hbit in glance["honesty_line"]
    assert "A exits € size n ok · sl · 6 closes" in glance["honesty_line"]
    assert "A exits € size rest n thin · 2 closes <3" in glance["honesty_line"]
    assert hsign in glance["honesty_line"]
    assert hsign in glance["line"]
    assert hrest in glance["honesty_line"]
    assert hrest in glance["line"]
    assert hclash in glance["honesty_line"]
    assert hclash in glance["line"]
    assert hnet in glance["honesty_line"]
    assert hnet in glance["line"]
    assert "A exits € size clash keep strong · 0.9×" in glance["honesty_line"]
    assert "A exits € size clash keep strong · 0.9×" in glance["line"]
    assert "clash keep fees" not in glance["honesty_line"]
    assert "A exits € size" not in glance["summary_line"]
    assert "ready for B" in glance["summary_line"]

    glance_fees = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": 95.0,
            "net_after_all_fees": 91.0,
            "wins": 6,
            "losses": 2,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert (
        "A exits € size clash keep fees comfortable · 0.04×"
        in glance_fees["honesty_line"]
    )
    assert (
        "A exits € size clash keep fees comfortable · 0.04×" in glance_fees["line"]
    )
    assert "clash keep fees" not in glance_fees["summary_line"]
    assert "vs drag" not in glance_fees["honesty_line"]
    assert glance_fees["b_ready"] is True

    glance_worse = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": 2.0,
            "net_after_all_fees": -2.0,
            "wins": 6,
            "losses": 2,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    worse_bit = (
        "A exits € size clash keep fees vs drag worse · comfortable · heavy"
    )
    assert worse_bit in glance_worse["honesty_line"]
    assert worse_bit in glance_worse["line"]
    # leftover 0.04× vs fee-drag heavy 2× → gap 50× wide; worse warns.
    gap_worse = "A exits € size clash keep fees vs drag gap wide · 50×"
    assert gap_worse in glance_worse["honesty_line"]
    assert gap_worse in glance_worse["line"]
    gap_dir_worse = (
        "A exits € size clash keep fees vs drag gap dir below · 0.02×"
    )
    assert gap_dir_worse in glance_worse["honesty_line"]
    assert gap_dir_worse in glance_worse["line"]
    gap_dir_sides_worse = (
        "A exits € size clash keep fees vs drag gap dir sides · "
        "leftover 0.04× · window 2×"
    )
    assert gap_dir_sides_worse in glance_worse["honesty_line"]
    assert gap_dir_sides_worse in glance_worse["line"]
    gap_dir_sides_delta_worse = (
        "A exits € size clash keep fees vs drag gap dir sides Δ wide · −2×"
    )
    assert gap_dir_sides_delta_worse in glance_worse["honesty_line"]
    assert gap_dir_sides_delta_worse in glance_worse["line"]
    gap_dir_sides_share_worse = (
        "A exits € size clash keep fees vs drag gap dir sides share · "
        "leftover 2% · window 98%"
    )
    assert gap_dir_sides_share_worse in glance_worse["honesty_line"]
    assert (
        glance_worse[
            "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
        ]
        == gap_dir_sides_share_worse
    )
    gap_dir_sides_share_delta_worse = (
        "A exits € size clash keep fees vs drag gap dir sides share Δ wide · −96pp"
    )
    assert gap_dir_sides_share_delta_worse in glance_worse["honesty_line"]
    assert gap_dir_sides_share_delta_worse in glance_worse["fee_pressure_line"]
    align_worse = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align · wide"
    )
    assert align_worse in glance_worse["honesty_line"]
    assert align_worse in glance_worse["fee_pressure_line"]
    assert (
        glance_worse[
            "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit"
        ]
        == align_worse
    )
    align_size_worse = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        "align size · −2× · −96pp"
    )
    assert align_size_worse in glance_worse["honesty_line"]
    assert align_size_worse in glance_worse["align_nest_line"]
    assert align_size_worse not in glance_worse["fee_pressure_line"]
    assert align_size_worse not in glance_worse["honesty_core"]
    assert "align nest" in glance_worse["honesty_warns"]
    assert (
        glance_worse[
            "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit"
        ]
        == align_size_worse
    )
    assert "align size" not in glance_worse["fee_pressure_line"]
    assert "align lead" not in glance_worse["fee_pressure_line"]
    assert "align lead size" not in glance_worse["fee_pressure_line"]
    assert "align lead size sides" not in glance_worse["fee_pressure_line"]
    assert "align lead size sides Δ" not in glance_worse["fee_pressure_line"]
    assert "align lead size sides share" not in glance_worse["fee_pressure_line"]
    assert "align lead size sides share Δ" not in glance_worse["fee_pressure_line"]
    assert "align lead size sides share vs Δ clash" not in glance_worse["fee_pressure_line"]
    assert "share vs Δ align lead size sides share Δ" not in glance_worse["fee_pressure_line"]
    assert "share vs Δ clash" not in glance_worse["fee_pressure_line"]
    assert "clash keep fees" not in glance_worse["honesty_core"]
    assert "A exits €" not in glance_worse["honesty_core"]
    assert "A exits €" in glance_worse["exit_euro_line"]
    assert "clash keep fees" not in glance_worse["exit_euro_line"]
    assert "A exits" not in glance_worse["honesty_core"]
    assert "A exits" in glance_worse["exit_mix_line"]
    assert "A exits €" not in glance_worse["exit_mix_line"]
    assert glance_worse["exit_mix_line"] in glance_worse["honesty_line"]
    assert (
        glance_worse[
            "a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit"
        ]
        == gap_dir_sides_share_delta_worse
    )
    # Full `line` may truncate past ~1149 chars; honesty_line keeps the bit.
    assert "vs drag gap dir sides" not in glance_worse["summary_line"]
    assert "vs drag gap dir" not in glance_worse["summary_line"]
    assert glance_worse["tone"] == "warn"
    assert glance_worse["b_ready"] is True

    glance_thin_n = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": 80.0,
            "net_after_all_fees": 76.0,
            "wins": 1,
            "losses": 7,
            "exit_tp": 1,
            "exit_sl": 7,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -14.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert glance_thin_n["tone"] == "warn"
    assert glance_thin_n["b_ready"] is True
    assert sn in glance_thin_n["honesty_line"]
    assert sn in glance_thin_n["line"]
    assert "A exits € size rest n ok · 7 closes" in glance_thin_n["honesty_line"]
    assert "A exits € size sign win · tp · +€100" in glance_thin_n["honesty_line"]
    assert (
        "A exits € size rest sign loss · −€14" in glance_thin_n["honesty_line"]
    )
    assert (
        "A exits € size clash · lead win · rest loss"
        in glance_thin_n["honesty_line"]
    )
    assert (
        "A exits € size clash net win · +€86" in glance_thin_n["honesty_line"]
    )
    assert (
        "A exits € size clash keep strong · 0.8×" in glance_thin_n["honesty_line"]
    )
    assert "A exits € size clash keep" not in glance_thin_n["summary_line"]

    glance_cancel = build_promote_ab_glance(
        knobs,
        as_of=date(2026, 9, 14),
        open_positions=2,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": 0.0,
            "net_after_all_fees": -4.0,
            "wins": 6,
            "losses": 2,
            "exit_tp": 6,
            "exit_sl": 1,
            "exit_rot": 1,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -60.0,
            "exit_pnl_rot": -40.0,
            "exit_pnl_trim": 0.0,
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
    )
    assert glance_cancel["tone"] == "warn"
    assert glance_cancel["b_ready"] is True
    assert ckeep in glance_cancel["honesty_line"]
    assert ckeep in glance_cancel["line"]
    assert "A exits € size clash net" not in glance_cancel["honesty_line"]
    assert "A exits € size clash keep" not in glance_cancel["summary_line"]
    assert "ready for B" in glance_cancel["summary_line"]
