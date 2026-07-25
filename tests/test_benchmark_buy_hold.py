"""Offline tests for buy-and-hold benchmark helpers."""

from scripts.benchmark_buy_hold import buy_and_hold_equal_weight, buy_and_hold_spy


def test_buy_hold_spy_once():
    bars = {"SPY": [{"close": 100.0}, {"close": 101.0}]}
    assert buy_and_hold_spy(bars, 1, {"positions": {}}) == {"SPY": "BUY"}
    assert buy_and_hold_spy(bars, 1, {"positions": {"SPY": {}}}) == {}


def test_buy_hold_equal_weight_fills_missing():
    bars = {"A": [{"close": 1}, {"close": 2}], "B": [{"close": 1}, {"close": 2}]}
    sig = buy_and_hold_equal_weight(bars, 1, {"positions": {"A": {}}})
    assert sig == {"B": "BUY"}
