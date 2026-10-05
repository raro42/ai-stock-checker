#!/usr/bin/env python3
"""Unit tests for market hours helpers (no network)."""

from datetime import datetime, timezone
from pathlib import Path

import pytz

from stock_checker.german_universe import GERMAN_XETRA_SEED
from stock_checker.market_hours import (
    is_equity_session_closed,
    is_german_equity,
    is_us_cash_session_closed,
    is_xetra_session_closed,
    last_us_cash_session_close,
    last_xetra_session_close,
)
from stock_checker.market_scanner import MarketScanner
from stock_checker.stock_universe_manager import StockUniverseManager


def test_german_equity_suffix():
    assert is_german_equity("SAP.DE")
    assert is_german_equity("vow3.de")
    assert not is_german_equity("SAP")
    assert not is_german_equity("AAPL")


def test_xetra_open_while_us_premarket():
    # Monday 10:00 Europe/Berlin = 04:00 US/Eastern — Xetra open, US closed
    berlin = pytz.timezone("Europe/Berlin")
    now = berlin.localize(datetime(2026, 7, 20, 10, 0))
    assert is_xetra_session_closed(now=now) is False
    assert is_us_cash_session_closed(now=now) is True
    assert is_equity_session_closed("SAP.DE", now=now) is False
    assert is_equity_session_closed("AAPL", now=now) is True


def test_xetra_closed_us_open():
    # Wednesday 15:00 US/Eastern = 21:00 Berlin — US open, Xetra closed
    et = pytz.timezone("US/Eastern")
    now = et.localize(datetime(2026, 7, 22, 15, 0))
    assert is_us_cash_session_closed(now=now) is False
    assert is_xetra_session_closed(now=now) is True
    assert is_equity_session_closed("AAPL", now=now) is False
    assert is_equity_session_closed("SIE.DE", now=now) is True


def test_last_session_close_after_hours():
    et = pytz.timezone("US/Eastern")
    now = et.localize(datetime(2026, 9, 8, 21, 30))
    got = last_us_cash_session_close(now=now)
    want = et.localize(datetime(2026, 9, 8, 16, 0)).astimezone(timezone.utc)
    assert got == want


def test_last_session_close_before_open_uses_prior_weekday():
    berlin = pytz.timezone("Europe/Berlin")
    now = berlin.localize(datetime(2026, 9, 9, 10, 0))
    got = last_us_cash_session_close(now=now)
    et = pytz.timezone("US/Eastern")
    want = et.localize(datetime(2026, 9, 8, 16, 0)).astimezone(timezone.utc)
    assert got == want
    xetra = last_xetra_session_close(now=now)
    want_x = berlin.localize(datetime(2026, 9, 8, 17, 30)).astimezone(timezone.utc)
    assert xetra == want_x


def test_last_session_close_weekend_is_friday():
    et = pytz.timezone("US/Eastern")
    sat = et.localize(datetime(2026, 9, 12, 12, 0))
    got = last_us_cash_session_close(now=sat)
    want = et.localize(datetime(2026, 9, 11, 16, 0)).astimezone(timezone.utc)
    assert got == want


def test_crypto_never_session_closed():
    et = pytz.timezone("US/Eastern")
    sat = et.localize(datetime(2026, 7, 25, 12, 0))
    assert is_equity_session_closed("BTC-USD", now=sat) is False


def test_scanner_us_helpers_delegate():
    scanner = MarketScanner.__new__(MarketScanner)
    assert hasattr(scanner, "is_symbol_session_closed")


def test_ensure_curated_seed_adds_german(tmp_path: Path):
    mgr = StockUniverseManager(data_dir=str(tmp_path))
    mgr.universe = {
        "last_updated": "",
        "total_stocks": 1,
        "stocks": {"AAPL": {"sector": "technology", "exchange": "NASDAQ", "added": "x"}},
        "sectors": {"technology": ["AAPL"]},
        "exchanges": {"NASDAQ": ["AAPL"]},
    }
    mgr._save_universe()
    added = mgr.ensure_curated_seed()
    assert "SAP.DE" in mgr.universe["stocks"]
    assert "BMW.DE" in mgr.universe["stocks"]
    assert added >= 30
    assert all(s.endswith(".DE") for s in GERMAN_XETRA_SEED)
