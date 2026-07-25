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
