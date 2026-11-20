#!/usr/bin/env python3
"""Tests for multi-timeframe momentum strategy helper."""

from datetime import datetime, timedelta

import pytest

from stock_checker.backtester import Backtester, momentum_cross_strategy
from stock_checker.strategy_signals import (
    _valid_close_tail,
    multi_timeframe_momentum_strategy,
)


def _uptrend_bars(n: int = 120, start: float = 100.0) -> list[dict]:
    bars = []
    price = start
    day0 = datetime(2024, 1, 1)
    for i in range(n):
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
    return bars


def test_mtf_strategy_on_uptrend():
    bars = _uptrend_bars()
    bt = Backtester(initial_capital=10_000, commission_rate=0.001, slippage_pct=0.0)
    result = bt.backtest({"AAA": bars}, multi_timeframe_momentum_strategy)
    assert len(result.equity_curve) > 1
    metrics = result.calculate_metrics()
    assert metrics["final_capital"] > 0


def test_mtf_clean_history_still_buys():
    """Valid positive closes keep aligned-uptrend BUY (not unavailable)."""
    bars = _uptrend_bars(80)
    signals = multi_timeframe_momentum_strategy(
        {"AAA": bars}, index=79, portfolio={"positions": {}}
    )
    assert signals.get("AAA") == "BUY"


@pytest.mark.parametrize(
    "bad",
    [None, True, "100", 0, 0.0, -1, float("nan"), float("inf"), -float("inf")],
)
def test_mtf_invalid_close_in_sma_window_is_unavailable(bad):
    """tradermonty #655 + xang1234/portfolio AI: gap/zero/NaN ≠ a real MTF BUY."""
    bars = _uptrend_bars(80)
    bars[70]["close"] = bad
    signals = multi_timeframe_momentum_strategy(
        {"AAA": bars}, index=79, portfolio={"positions": {}}
    )
    assert "AAA" not in signals


@pytest.mark.parametrize(
    "bad",
    [None, True, "100", 0, 0.0, -1, float("nan"), float("inf")],
)
def test_momentum_cross_invalid_close_is_unavailable(bad):
    """Same price-bar gate on CLI momentum-cross SMA window / signal bar."""
    bars = _uptrend_bars(40)
    bars[30]["close"] = bad
    signals = momentum_cross_strategy(
        {"AAA": bars}, index=35, portfolio={"positions": {}}, lookback=20
    )
    assert "AAA" not in signals


def test_momentum_cross_clean_history_still_buys():
    bars = _uptrend_bars(40)
    signals = momentum_cross_strategy(
        {"AAA": bars}, index=35, portfolio={"positions": {}}, lookback=20
    )
    assert signals.get("AAA") == "BUY"


def test_valid_close_tail_refuses_gap():
    bars = _uptrend_bars(10)
    bars[8]["close"] = float("nan")
    assert _valid_close_tail(bars, index=9, n=5) is None
    bars[8]["close"] = 110.0
    assert _valid_close_tail(bars, index=9, n=5) is not None


@pytest.mark.parametrize("bad", [True, False, None, 0, -1, "5", float("nan")])
def test_mtf_bool_sma_window_is_unavailable(bad):
    """tradermonty #700/#655: True→SMA(1) must not invent an MTF BUY."""
    bars = _uptrend_bars(80)
    signals = multi_timeframe_momentum_strategy(
        {"AAA": bars},
        index=79,
        portfolio={"positions": {}},
        short=bad,
        medium=20,
        long=50,
    )
    assert "AAA" not in signals
    signals = multi_timeframe_momentum_strategy(
        {"AAA": bars},
        index=79,
        portfolio={"positions": {}},
        short=5,
        medium=bad,
        long=50,
    )
    assert "AAA" not in signals


@pytest.mark.parametrize("bad", [True, False, None, 0, -1, "20", float("nan")])
def test_momentum_cross_bool_lookback_is_unavailable(bad):
    """tradermonty #700/#655: True→SMA(1) must not invent a momentum-cross BUY."""
    bars = _uptrend_bars(40)
    signals = momentum_cross_strategy(
        {"AAA": bars}, index=35, portfolio={"positions": {}}, lookback=bad
    )
    assert "AAA" not in signals
