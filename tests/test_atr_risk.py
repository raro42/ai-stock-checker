"""Offline tests for ATR / R:R display helpers."""

from stock_checker.atr_risk import (
    average_true_range,
    note_from_day_range,
    note_from_ohlc_rows,
    risk_reward_note,
)


def test_average_true_range_simple():
    # Flat then one wide bar
    highs = [10.0] * 15 + [12.0]
    lows = [9.0] * 15 + [8.0]
    closes = [9.5] * 15 + [11.0]
    atr = average_true_range(highs, lows, closes, period=14)
    assert atr is not None
    assert atr > 0


def test_risk_reward_prefer_higher_stop():
    note = risk_reward_note(entry=100.0, atr=2.0, swing_low=90.0, atr_mult=2.0)
    # ATR stop = 96; swing stop = 88.2 → prefer ATR (higher)
    assert note["stop_type"] == "atr"
    assert note["stop"] == 96.0
    assert note["rr_ok"] is True
    assert note["rr"] is not None and note["rr"] >= 2.0


def test_note_from_day_range_and_ohlc():
    day = note_from_day_range(entry=50.0, day_high=52.0, day_low=48.0)
    assert day["stop"] is not None
    assert "stop" in day["summary"]

    rows = [
        {"high": 11, "low": 9, "close": 10},
        {"high": 12, "low": 9.5, "close": 11},
    ] + [{"high": 12, "low": 10, "close": 11}] * 14
    ohlc = note_from_ohlc_rows(rows, entry=11.0)
    assert ohlc["entry"] == 11.0
