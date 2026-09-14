#!/usr/bin/env python3
"""Tests for earnings blackout helper (offline)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from stock_checker.earnings_guard import (
    STATUS_DATED,
    STATUS_EMPTY_WINDOW,
    STATUS_MISSING,
    is_in_earnings_blackout,
    probe_earnings_calendar,
)
from stock_checker.gate_audit import is_soft_allow_reason


def test_crypto_never_blackout():
    blocked, _ = is_in_earnings_blackout("BTC-USD")
    assert blocked is False


@patch(
    "stock_checker.earnings_guard.probe_earnings_calendar",
    return_value=(1.0, STATUS_DATED),
)
def test_blackout_before_earnings(_mock):
    blocked, why = is_in_earnings_blackout("AAPL", days_before=2.0, days_after=1.0)
    assert blocked is True
    assert "blackout" in why


@patch(
    "stock_checker.earnings_guard.probe_earnings_calendar",
    return_value=(-0.5, STATUS_DATED),
)
def test_blackout_after_earnings(_mock):
    blocked, why = is_in_earnings_blackout("MSFT", days_before=2.0, days_after=1.0)
    assert blocked is True


@patch(
    "stock_checker.earnings_guard.probe_earnings_calendar",
    return_value=(10.0, STATUS_DATED),
)
def test_no_blackout_far_away(_mock):
    blocked, _ = is_in_earnings_blackout("NVDA")
    assert blocked is False


@patch(
    "stock_checker.earnings_guard.probe_earnings_calendar",
    return_value=(None, STATUS_MISSING),
)
def test_missing_calendar_fail_open_allows(_mock):
    """No Yahoo earnings date → allow (fail-open), not a silent block."""
    blocked, why = is_in_earnings_blackout("UNKNOWN")
    assert blocked is False
    assert why == ""


@patch(
    "stock_checker.earnings_guard.probe_earnings_calendar",
    return_value=(None, STATUS_EMPTY_WINDOW),
)
def test_empty_yahoo_window_fail_open_with_why(_mock):
    """Empty earnings_dates + no calendar → allow with explicit suspect why."""
    blocked, why = is_in_earnings_blackout("FAKE")
    assert blocked is False
    assert "empty Yahoo" in why
    assert "fail-open" in why
    assert is_soft_allow_reason(why)


def test_probe_detects_suspicious_empty_earnings_window():
    """Yahoo earnings_dates present but empty, calendar blank → empty_window."""
    empty = MagicMock()
    empty.empty = True
    ticker = SimpleNamespace(earnings_dates=empty, calendar={})

    with patch("yfinance.Ticker", return_value=ticker):
        days, status = probe_earnings_calendar("AAPL")

    assert days is None
    assert status == STATUS_EMPTY_WINDOW
