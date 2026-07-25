#!/usr/bin/env python3
"""Tests for earnings blackout helper (offline)."""

from unittest.mock import MagicMock, patch

from stock_checker.earnings_guard import is_in_earnings_blackout


def test_crypto_never_blackout():
    blocked, _ = is_in_earnings_blackout("BTC-USD")
    assert blocked is False


@patch("stock_checker.earnings_guard.days_to_next_earnings", return_value=1.0)
def test_blackout_before_earnings(_mock):
    blocked, why = is_in_earnings_blackout("AAPL", days_before=2.0, days_after=1.0)
    assert blocked is True
    assert "blackout" in why


@patch("stock_checker.earnings_guard.days_to_next_earnings", return_value=-0.5)
def test_blackout_after_earnings(_mock):
    blocked, why = is_in_earnings_blackout("MSFT", days_before=2.0, days_after=1.0)
    assert blocked is True


@patch("stock_checker.earnings_guard.days_to_next_earnings", return_value=10.0)
def test_no_blackout_far_away(_mock):
    blocked, _ = is_in_earnings_blackout("NVDA")
    assert blocked is False
