#!/usr/bin/env python3
"""Tests for earnings blackout helper (offline)."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from stock_checker.earnings_guard import (
    EARNINGS_CLOCK,
    STATUS_DATED,
    STATUS_EMPTY_WINDOW,
    STATUS_MALFORMED,
    STATUS_MISSING,
    earnings_day_delta,
    is_in_earnings_blackout,
    probe_earnings_calendar,
)
from stock_checker.gate_audit import is_soft_allow_reason


def test_crypto_never_blackout():
    blocked, _ = is_in_earnings_blackout("BTC-USD")
    assert blocked is False


def test_listed_fund_skips_earnings():
    blocked, why = is_in_earnings_blackout("4GLD.DE")
    assert blocked is False
    assert "listed fund" in why


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


@patch(
    "stock_checker.earnings_guard.probe_earnings_calendar",
    return_value=(None, STATUS_MALFORMED),
)
def test_malformed_yahoo_fail_open_with_why(_mock):
    """Nonempty or junk Yahoo dates → allow, but not a silent 'no earnings'."""
    blocked, why = is_in_earnings_blackout("FAKE")
    assert blocked is False
    assert "malformed Yahoo" in why
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


def test_earnings_window_uses_new_york_date_not_utc():
    """02:00 UTC is still the prior US session date (EDT). Do not drop blackout."""
    # 2026-09-19 02:00 UTC = 2026-09-18 22:00 America/New_York.
    now = datetime(2026, 9, 19, 2, 0)
    assert earnings_day_delta(datetime(2026, 9, 18), now) == 0.0
    assert EARNINGS_CLOCK == "America/New_York"

    class _Index:
        def __iter__(self):
            yield datetime(2026, 9, 18)

    ed = SimpleNamespace(empty=False, index=_Index())
    ticker = SimpleNamespace(earnings_dates=ed, calendar={})
    with patch("yfinance.Ticker", return_value=ticker):
        days, status = probe_earnings_calendar("AAPL", now=now)
        blocked, why = is_in_earnings_blackout("AAPL", now=now)

    assert status == STATUS_DATED
    assert days == 0.0
    assert blocked is True
    assert "0.0d" in why


def test_nonempty_unparseable_earnings_is_malformed():
    """Nonempty Yahoo frame with no usable date is not a missing calendar."""

    class _Index:
        def __iter__(self):
            yield "not-a-date"
            yield datetime(1970, 1, 1)

    ed = SimpleNamespace(empty=False, index=_Index())
    ticker = SimpleNamespace(earnings_dates=ed, calendar={})
    with patch("yfinance.Ticker", return_value=ticker):
        days, status = probe_earnings_calendar("AAPL")

    assert days is None
    assert status == STATUS_MALFORMED


def test_epoch_calendar_date_is_malformed_not_dated():
    """1970-01-01 from an index fallback must not look like a real earnings date."""
    empty = MagicMock()
    empty.empty = True
    ticker = SimpleNamespace(
        earnings_dates=empty,
        calendar={"Earnings Date": datetime(1970, 1, 1)},
    )
    now = datetime(2026, 9, 19, 16, 0)
    assert earnings_day_delta(datetime(1970, 1, 1), now) is None
    with patch("yfinance.Ticker", return_value=ticker):
        days, status = probe_earnings_calendar("AAPL", now=now)

    assert days is None
    assert status == STATUS_MALFORMED


def test_valid_calendar_date_wins_over_junk_earnings_frame():
    """A real calendar date still counts when the dates frame is junk."""

    class _Index:
        def __iter__(self):
            yield datetime(1970, 1, 1)

    ed = SimpleNamespace(empty=False, index=_Index())
    ticker = SimpleNamespace(
        earnings_dates=ed,
        calendar={"Earnings Date": datetime(2026, 9, 21)},
    )
    now = datetime(2026, 9, 19, 16, 0)
    with patch("yfinance.Ticker", return_value=ticker):
        days, status = probe_earnings_calendar("AAPL", now=now)

    assert status == STATUS_DATED
    assert days == 2.0


def test_calendar_list_skips_nonscalar_and_keeps_later_date():
    """A nested list in Earnings Date must not hide a later real stamp."""
    empty = MagicMock()
    empty.empty = True
    ticker = SimpleNamespace(
        earnings_dates=empty,
        calendar={"Earnings Date": [[1, 2], datetime(2026, 9, 21)]},
    )
    now = datetime(2026, 9, 19, 16, 0)
    with patch("yfinance.Ticker", return_value=ticker):
        days, status = probe_earnings_calendar("AAPL", now=now)

    assert status == STATUS_DATED
    assert days == 2.0


def test_calendar_list_of_only_nonscalars_is_malformed():
    """List and dict cells are junk, not a crash and not a real date."""
    empty = MagicMock()
    empty.empty = True
    ticker = SimpleNamespace(
        earnings_dates=empty,
        calendar={"Earnings Date": [[1, 2], {"when": "soon"}]},
    )
    with patch("yfinance.Ticker", return_value=ticker):
        days, status = probe_earnings_calendar("AAPL")

    assert days is None
    assert status == STATUS_MALFORMED


def test_bad_earnings_row_does_not_abort_later_date():
    """One stamp that raises must not drop a later date in the same frame."""

    class _Boom:
        def to_pydatetime(self):
            raise ValueError("non-scalar")

    class _Index:
        def __iter__(self):
            yield _Boom()
            yield datetime(2026, 9, 21)

    ed = SimpleNamespace(empty=False, index=_Index())
    ticker = SimpleNamespace(earnings_dates=ed, calendar={})
    now = datetime(2026, 9, 19, 16, 0)
    with patch("yfinance.Ticker", return_value=ticker):
        days, status = probe_earnings_calendar("AAPL", now=now)

    assert status == STATUS_DATED
    assert days == 2.0


def test_aware_utc_stamp_converts_before_ny_date():
    """16:00 UTC on the 18th is still the 18th in New York (12:00 EDT)."""
    event = datetime(2026, 9, 18, 16, 0, tzinfo=timezone.utc)
    now = datetime(2026, 9, 19, 2, 0, tzinfo=timezone.utc)
    assert earnings_day_delta(event, now) == 0.0
