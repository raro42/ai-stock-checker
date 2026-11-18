"""Offline tests for ATR / R:R display helpers."""

import pytest

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


def test_average_true_range_wilder_matches_indicators():
    """Screener ATR delegates to TechnicalIndicators Wilder RMA (xang1234 #749)."""
    from stock_checker.technical_indicators import TechnicalIndicators

    n = 30
    highs = [10.5] * n
    lows = [9.5] * n
    closes = [10.0] * n
    highs[3] = 18.0
    closes[3] = 14.0
    desk = average_true_range(highs, lows, closes, period=14)
    core = TechnicalIndicators.calculate_atr(highs, lows, closes, period=14)
    assert desk is not None and core is not None
    assert desk == pytest.approx(core, rel=1e-12)


def test_average_true_range_inverted_ohlc_unavailable():
    """Screener ATR must not invent stops from high < low bars."""
    highs = [10.0] * 15 + [12.0]
    lows = [9.0] * 15 + [8.0]
    closes = [9.5] * 15 + [11.0]
    highs[5], lows[5] = 8.0, 10.0
    assert average_true_range(highs, lows, closes, period=14) is None


def test_average_true_range_close_outside_range_unavailable():
    highs = [10.0] * 15 + [12.0]
    lows = [9.0] * 15 + [8.0]
    closes = [9.5] * 15 + [11.0]
    closes[3] = 10.5  # above high
    assert average_true_range(highs, lows, closes, period=14) is None


def test_average_true_range_refuses_bool_before_float():
    """tradermonty #655/#798: True→1.0 must not invent Screener ATR."""
    highs = [10.0] * 15 + [12.0]
    lows = [9.0] * 15 + [8.0]
    closes = [9.5] * 15 + [11.0]
    highs[4] = True
    assert average_true_range(highs, lows, closes, period=14) is None


def test_risk_reward_refuses_bool_entry_and_atr():
    """Bool entry/ATR/swing must speak risk n/a — never invent €1 stops."""
    bad_entry = risk_reward_note(entry=True, atr=2.0)  # type: ignore[arg-type]
    assert bad_entry["stop"] is None
    assert str(bad_entry["summary"]).startswith("risk n/a")

    bad_atr = risk_reward_note(entry=100.0, atr=True)  # type: ignore[arg-type]
    assert bad_atr["stop"] is None
    assert str(bad_atr["summary"]).startswith("risk n/a")

    bad_swing = risk_reward_note(entry=100.0, atr=None, swing_low=True)  # type: ignore[arg-type]
    assert bad_swing["stop"] is None


def test_risk_reward_prefer_higher_stop():
    note = risk_reward_note(entry=100.0, atr=2.0, swing_low=90.0, atr_mult=2.0)
    # ATR stop = 96; swing stop = 88.2 → prefer ATR (higher)
    assert note["stop_type"] == "atr"
    assert note["stop"] == 96.0
    assert note["rr_ok"] is True
    assert note["rr"] is not None and note["rr"] >= 2.0


def test_risk_reward_uses_reported_cent_stop():
    """tradermonty #813: −risk% from rounded €stop, not raw atr×mult."""
    # entry 5 · atr 0.024 · mult 1.5 → raw 4.964 → report 4.96 · risk 0.04
    note = risk_reward_note(entry=5.0, atr=0.024, atr_mult=1.5)
    assert note["stop_type"] == "atr"
    assert note["stop"] == 4.96
    assert note["risk_pct"] == pytest.approx(0.8, rel=1e-9)
    assert "€4.96" in str(note["summary"])
    assert "−0.8%" in str(note["summary"])


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


def test_note_from_day_range_entry_outside_range_unavailable():
    """Day-range ATR proxy must not invent vol when entry is outside OHLC."""
    bad = note_from_day_range(entry=60.0, day_high=52.0, day_low=48.0)
    assert bad["stop"] is None
    assert str(bad["summary"]).startswith("risk n/a")


def test_note_from_ohlc_rows_refuses_bad_bar_without_compress():
    """Do not drop inverted/out-of-range bars into a shorter ATR window."""
    rows = [{"high": 11, "low": 9, "close": 10}] * 16
    rows[4] = {"high": 8, "low": 10, "close": 9}  # inverted
    note = note_from_ohlc_rows(rows, entry=10.0)
    assert note["stop"] is None
    assert str(note["summary"]).startswith("risk n/a")


def test_note_from_ohlc_rows_refuses_bool_bar_and_entry():
    """Bool OHLC/entry must not invent a Wilder ATR R:R note."""
    rows = [{"high": 11, "low": 9, "close": 10}] * 16
    rows[2] = {"high": True, "low": 9, "close": 10}
    assert str(note_from_ohlc_rows(rows, entry=10.0)["summary"]).startswith("risk n/a")

    clean = [{"high": 11, "low": 9, "close": 10}] * 16
    assert str(note_from_ohlc_rows(clean, entry=True)["summary"]).startswith("risk n/a")  # type: ignore[arg-type]


def test_note_from_day_range_refuses_bool_marks():
    bad = note_from_day_range(entry=True, day_high=52.0, day_low=48.0)  # type: ignore[arg-type]
    assert bad["stop"] is None
    bad_hi = note_from_day_range(entry=50.0, day_high=True, day_low=48.0)  # type: ignore[arg-type]
    assert bad_hi["stop"] is None


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
