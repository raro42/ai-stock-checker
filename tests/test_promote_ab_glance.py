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
    assert s["crypto_legs"] == 1
    assert s["stock_legs"] == 2
    assert s["wins"] == 1
    bit = format_window_stats_bit(s)
    assert "€18 fees" in bit
    assert "3 fills" in bit


def test_promote_ab_glance_includes_window_stats(tmp_path: Path) -> None:
    trades_path = tmp_path / "trades.jsonl"
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
        {"promote_experiment_strategy": False},
        as_of=date(2026, 9, 13),
        data_dir=tmp_path,
    )
    assert g["ready"] is True
    assert g["tone"] == "ready"
    assert g["window_stats"]["trades"] == 2
    assert "€20 fees" in g["line"]
    assert "ready for B" in g["line"]
    assert "summarize before B" not in g["line"]
