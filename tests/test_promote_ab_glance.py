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
    assert drag["fee_drag_net"] == -60.0
    assert drag["fee_drag_bit"] == "A fee drag · net −€60"
    assert format_window_a_fee_drag_bit(drag) == drag["fee_drag_bit"]

    # Fallback when net is missing / non-negative but fees still > realized.
    drag_fallback = window_a_sample_readiness(
        {
            "trades": 12,
            "buys": 8,
            "sells": 4,
            "fees": 80.0,
            "realized_pnl": 20.0,
            "net_after_all_fees": 0.0,  # odd stats → keep fees > realized wording
            "last_sell": "2026-09-11T15:00:00+00:00",
        },
        as_of=date(2026, 9, 14),
    )
    assert drag_fallback["fee_drag"] is True
    assert drag_fallback["fee_drag_bit"] == "A fee drag · fees > realized"

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
    assert format_window_a_fee_drag_bit(no_drag) == ""

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
    assert g["sample_fresh_closes"] is True
    assert "A fee drag · net −€60" in g["line"]
    assert "A fresh closes" in g["line"]
    assert "ready for B" in g["line"]
    assert "keep Window A" not in g["line"]
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
    assert g["closes_freshness"] == "aging"
    assert "A aging closes" in g["line"]
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
    assert g["closes_freshness"] == "fresh"
    assert "A fresh closes" in g["line"]
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
