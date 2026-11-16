"""tradermonty #655/#754: scan marks refuse bool/gap/NaN (True→$1 invent)."""

from __future__ import annotations

import math

from stock_checker.market_scanner import breakout_from_high, coerce_scan_price


def test_coerce_scan_price_refuses_invalid():
    assert coerce_scan_price(100.5) == 100.5
    assert coerce_scan_price(True) is None
    assert coerce_scan_price(False) is None
    assert coerce_scan_price(0) is None
    assert coerce_scan_price(-1) is None
    assert coerce_scan_price(math.nan) is None
    assert coerce_scan_price(None) is None
    assert coerce_scan_price("12.5") is None


def test_breakout_from_high_refuses_bool_and_gap():
    assert breakout_from_high(95.0, 100.0) == (95.0, 100.0, -5.0)
    assert breakout_from_high(True, 100.0) is None
    assert breakout_from_high(95.0, True) is None
    assert breakout_from_high(0, 100.0) is None
    assert breakout_from_high(95.0, math.nan) is None
    assert breakout_from_high(95.0, None) is None
