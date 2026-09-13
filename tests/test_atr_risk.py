"""Offline tests for ATR / R:R display helpers."""

from stock_checker.atr_risk import (
    atr_vol_coverage,
    average_true_range,
    note_from_day_range,
    note_from_ohlc_rows,
    risk_note_has_vol,
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


def test_risk_note_has_vol_and_coverage():
    assert risk_note_has_vol("stop atr €100.00 (−4.8%) · tgt +20%") is True
    assert risk_note_has_vol("risk n/a") is False
    assert risk_note_has_vol("risk n/a (stop ≥ entry)") is False
    assert risk_note_has_vol("") is False
    assert risk_note_has_vol(None) is False

    cov = atr_vol_coverage(
        [
            {"risk_note": "stop atr €10 (−5%) · tgt +20% · R:R 4.0 (ok)"},
            {"risk_note": "risk n/a"},
            {"risk_note": ""},
            {"symbol": "SKIP"},  # no risk_note / summary → ignore
        ]
    )
    assert cov["total"] == 3
    assert cov["with_vol"] == 1
    assert cov["missing"] == 2
    assert cov["coverage_pct"] == round(100.0 / 3, 1)
    assert atr_vol_coverage(None)["total"] == 0
    assert atr_vol_coverage([])["coverage_pct"] is None
