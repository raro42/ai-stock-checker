#!/usr/bin/env python3
"""Unit tests for backtester (synthetic OHLCV, no network)."""

from datetime import datetime, timedelta

from stock_checker.backtester import Backtester, momentum_cross_strategy


def _make_uptrend(n: int = 80, start: float = 100.0) -> list:
    bars = []
    price = start
    day0 = datetime(2024, 1, 1)
    for i in range(n):
        price *= 1.01  # steady uptrend
        bars.append(
            {
                "date": day0 + timedelta(days=i),
                "open": price * 0.99,
                "high": price * 1.01,
                "low": price * 0.98,
                "close": price,
                "volume": 1_000_000,
            }
        )
    return bars


def test_backtest_runs_and_produces_equity_curve():
    data = {"AAA": _make_uptrend()}
    bt = Backtester(initial_capital=10_000, commission_rate=0.001, slippage_pct=0.0)
    result = bt.backtest(data, momentum_cross_strategy)
    assert len(result.equity_curve) > 1
    metrics = result.calculate_metrics()
    assert "total_return_pct" in metrics
    assert metrics["final_capital"] > 0


def test_empty_data_returns_empty_result():
    bt = Backtester()
    result = bt.backtest({}, momentum_cross_strategy)
    assert result.trades == []
    assert result.calculate_metrics()["total_trades"] == 0


def test_max_positions_caps_book():
    def buy_all(bars_by_symbol, index, portfolio):
        if index < 5:
            return {}
        return {s: "BUY" for s in bars_by_symbol}

    data = {s: _make_uptrend() for s in ("A", "B", "C", "D")}
    bt = Backtester(
        initial_capital=10_000,
        commission_rate=0.0,
        slippage_pct=0.0,
        position_fraction=0.25,
        max_positions=2,
    )
    result = bt.backtest(data, buy_all)
    # Force-close creates trades for open names only — at most 2
    assert len(result.trades) <= 2


def test_min_hold_bars_blocks_early_exit():
    def flip_next_bar(bars_by_symbol, index, portfolio):
        positions = portfolio.get("positions", {})
        if "AAA" not in positions and index == 10:
            return {"AAA": "BUY"}
        if "AAA" in positions and index == 11:
            return {"AAA": "SELL"}
        return {}

    data = {"AAA": _make_uptrend(40)}
    bt = Backtester(
        initial_capital=10_000,
        commission_rate=0.0,
        slippage_pct=0.0,
        position_fraction=0.5,
        min_hold_bars=3,
    )
    result = bt.backtest(data, flip_next_bar)
    # Early SELL ignored → only end_of_data close
    assert len(result.trades) == 1
    assert result.trades[0].reason == "end_of_data"


def test_commission_min_floor_applied():
    from datetime import datetime

    from stock_checker.fees import FeeAllowanceLedger

    bt = Backtester(
        initial_capital=1_000,
        commission_rate=0.0001,
        commission_min_eur=5.0,
        slippage_pct=0.0,
        position_fraction=0.1,
        free_legs_per_month=0,
    )
    ledger = FeeAllowanceLedger(0)
    ts = datetime(2026, 1, 1)
    assert bt._fee(100.0, ts, ledger) == 5.0
    assert bt._fee(100_000.0, ts, ledger) == 10.0  # 0.01% of 100k = 10 > floor
