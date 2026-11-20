"""Offline tests for buy-and-hold benchmark helpers."""

from scripts.benchmark_buy_hold import (
    benchmark_score,
    buy_and_hold_equal_weight,
    buy_and_hold_spy,
    run_equal_weight_buy_hold,
)


def test_buy_hold_spy_once():
    bars = {"SPY": [{"close": 100.0}, {"close": 101.0}]}
    assert buy_and_hold_spy(bars, 1, {"positions": {}}) == {"SPY": "BUY"}
    assert buy_and_hold_spy(bars, 1, {"positions": {"SPY": {}}}) == {}


def test_buy_hold_equal_weight_fills_missing():
    bars = {"A": [{"close": 1}, {"close": 2}], "B": [{"close": 1}, {"close": 2}]}
    sig = buy_and_hold_equal_weight(bars, 1, {"positions": {"A": {}}})
    assert sig == {"B": "BUY"}


def test_benchmark_score_refuses_bool_metrics():
    """True→1.0 Sharpe / True→1 trade must not invent a baseline beat."""
    assert benchmark_score({"sharpe_ratio": 2.0, "total_trades": True}) == -100.0
    assert benchmark_score({"sharpe_ratio": True, "total_trades": False}) == -100.0
    score = benchmark_score(
        {
            "sharpe_ratio": True,
            "max_drawdown": 0.0,
            "total_return_pct": 0.0,
            "fees_pct": 0.0,
            "total_trades": 1,
        }
    )
    assert score == 0.0
    ok = benchmark_score(
        {
            "sharpe_ratio": 1.0,
            "max_drawdown": 10.0,
            "total_return_pct": 20.0,
            "fees_pct": 2.0,
            "total_trades": 1,
        }
    )
    assert ok == 1.0 * 10.0 + 20.0 * 0.05 - 10.0 * 0.15 - 2.0 * 0.5


def test_equal_weight_refuses_bool_closes():
    """True→$1 close must not invent an EW baseline fill."""
    data = {
        "A": [{"close": 100.0, "date": "2023-01-01"}, {"close": True, "date": "2023-01-02"}],
        "B": [{"close": 100.0, "date": "2023-01-01"}, {"close": True, "date": "2023-01-02"}],
    }
    metrics = run_equal_weight_buy_hold(data)
    # No readable entry closes → inactive fail score (not invent True→$1 lots).
    assert metrics["total_trades"] == 0
    assert metrics["val_score"] == -100.0
