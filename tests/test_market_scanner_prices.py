"""tradermonty #655/#754/#798: scan marks/% refuse bool/gap/NaN invent."""

from __future__ import annotations

import math

from stock_checker.market_scanner import (
    breakout_from_high,
    coerce_scan_price,
    coerce_signed_pct,
    stock_pulse_side,
)


def test_coerce_scan_price_refuses_invalid():
    assert coerce_scan_price(100.5) == 100.5
    assert coerce_scan_price(True) is None
    assert coerce_scan_price(False) is None
    assert coerce_scan_price(0) is None
    assert coerce_scan_price(-1) is None
    assert coerce_scan_price(math.nan) is None
    assert coerce_scan_price(None) is None
    assert coerce_scan_price("12.5") is None


def test_coerce_signed_pct_refuses_invalid_and_keeps_signed():
    assert coerce_signed_pct(-1.5) == -1.5
    assert coerce_signed_pct(0.0) == 0.0
    assert coerce_signed_pct(2.25) == 2.25
    assert coerce_signed_pct(True) is None
    assert coerce_signed_pct(False) is None
    assert coerce_signed_pct(math.nan) is None
    assert coerce_signed_pct(None) is None
    assert coerce_signed_pct("1.2") is None


def test_stock_pulse_side_refuses_invalid_no_invent_flat():
    """xang1234 breadth: unavailable % must not count as flat in stock_scan_n."""
    assert stock_pulse_side(1.5) == "up"
    assert stock_pulse_side(-0.25) == "down"
    assert stock_pulse_side(0.0) == "flat"
    assert stock_pulse_side(True) is None
    assert stock_pulse_side(False) is None
    assert stock_pulse_side(math.nan) is None
    assert stock_pulse_side(None) is None
    assert stock_pulse_side("1.2") is None


def test_breakout_from_high_refuses_bool_and_gap():
    assert breakout_from_high(95.0, 100.0) == (95.0, 100.0, -5.0)
    assert breakout_from_high(True, 100.0) is None
    assert breakout_from_high(95.0, True) is None
    assert breakout_from_high(0, 100.0) is None
    assert breakout_from_high(95.0, math.nan) is None
    assert breakout_from_high(95.0, None) is None
