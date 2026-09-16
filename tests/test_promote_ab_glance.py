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
    assert "A thin" in g["line"]
    assert "2 fills <10" in g["line"]
    assert "keep Window A" in g["line"]
    assert "ready for B" not in g["line"]
    assert g["sample_known"] is True
    assert g["sample_ready"] is False
    assert g["sample_fills"] == 2
    assert g["target_fills"] == 10
    assert g["b_ready"] is False
    assert g["b_blockers"] == []


def test_window_a_sample_readiness_fill_floor() -> None:
    from stock_checker.promote_ab import (
        WINDOW_A_TARGET_FILLS,
        format_window_a_thin_bit,
        window_a_sample_readiness,
    )

    unknown = window_a_sample_readiness(None)
    assert unknown["known"] is False
    assert unknown["ready"] is False
    assert unknown["thin"] is False
    assert format_window_a_thin_bit(unknown) == ""

    thin = window_a_sample_readiness({"trades": 2, "fees": 20.0, "realized_pnl": 10.0})
    assert thin["known"] is True
    assert thin["ready"] is False
    assert thin["thin"] is True
    assert thin["fills"] == 2
    assert thin["target_fills"] == WINDOW_A_TARGET_FILLS
    assert thin["thin_bit"] == "A thin · 2 fills <10"
    assert format_window_a_thin_bit(thin) == "A thin · 2 fills <10"

    ok = window_a_sample_readiness({"trades": 10, "fees": 50.0, "realized_pnl": 100.0})
    assert ok["ready"] is True
    assert ok["thin"] is False
    assert ok["thin_bit"] == ""


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
