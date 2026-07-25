#!/usr/bin/env python3
"""Tests for multi-timeframe momentum strategy helper."""

from datetime import datetime, timedelta

from stock_checker.backtester import Backtester
from stock_checker.strategy_signals import multi_timeframe_momentum_strategy


def test_mtf_strategy_on_uptrend():
    bars = []
    price = 100.0
    day0 = datetime(2024, 1, 1)
    for i in range(120):
        price *= 1.008
        bars.append(
            {
                "date": day0 + timedelta(days=i),
                "close": price,
                "open": price,
                "high": price,
                "low": price,
                "volume": 1e6,
            }
        )
    bt = Backtester(initial_capital=10_000, commission_rate=0.001, slippage_pct=0.0)
    result = bt.backtest({"AAA": bars}, multi_timeframe_momentum_strategy)
    assert len(result.equity_curve) > 1
    metrics = result.calculate_metrics()
    assert metrics["final_capital"] > 0
