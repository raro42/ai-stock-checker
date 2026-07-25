#!/usr/bin/env python3
"""Unit tests for market hours helpers (no network)."""

from datetime import datetime
from unittest.mock import patch

import pytz

from stock_checker.market_scanner import MarketScanner


def _scanner() -> MarketScanner:
    return MarketScanner.__new__(MarketScanner)


def test_weekend_is_closed():
    scanner = _scanner()
    et = pytz.timezone("US/Eastern")
    saturday_noon = et.localize(datetime(2026, 7, 25, 12, 0, 0))

    with patch("stock_checker.market_scanner.datetime") as mock_dt:
        mock_dt.now.return_value = saturday_noon
        # Keep real datetime.time / constructors used elsewhere if needed
        mock_dt.side_effect = None
        assert scanner.is_market_closed() is True
        assert scanner.is_weekend() is True


def test_weekday_midday_is_open():
    scanner = _scanner()
    et = pytz.timezone("US/Eastern")
    wed_10 = et.localize(datetime(2026, 7, 22, 10, 0, 0))

    with patch("stock_checker.market_scanner.datetime") as mock_dt:
        mock_dt.now.return_value = wed_10
        assert scanner.is_market_closed() is False
        assert scanner.is_weekend() is False


def test_weekday_after_close_is_closed():
    scanner = _scanner()
    et = pytz.timezone("US/Eastern")
    wed_18 = et.localize(datetime(2026, 7, 22, 18, 0, 0))

    with patch("stock_checker.market_scanner.datetime") as mock_dt:
        mock_dt.now.return_value = wed_18
        assert scanner.is_market_closed() is True
