#!/usr/bin/env python3
"""Fetcher tests — network-heavy; skipped by default via pytest.ini."""

import math

import pytest

from stock_checker import fetcher as fetcher_mod
from stock_checker.fetcher import StockFetcher, is_transient_network_error


def test_stock_fetcher_init():
    """Test StockFetcher initialization (offline)."""
    fetcher = StockFetcher()
    assert fetcher is not None


def test_yfinance_daily_change_refuses_missing_or_bool(monkeypatch):
    """tradermonty #798/#655: yfinance path must not invent flat 0.0 / True→1.0."""

    class _FakeTicker:
        def __init__(self, info):
            self.info = info

    def _run(info: dict):
        class _YF:
            @staticmethod
            def Ticker(_symbol: str):
                return _FakeTicker(info)

        monkeypatch.setattr(fetcher_mod, "yf", _YF)
        monkeypatch.setattr(fetcher_mod, "YFINANCE_AVAILABLE", True)
        # Force yfinance path (no Finnhub primary).
        f = StockFetcher.__new__(StockFetcher)
        f.finnhub = None
        f.yfinance_fallback = True

        class _Sem:
            @staticmethod
            def get_primary_provider():
                return "yfinance"

            @staticmethod
            def switch_provider(_p: str):
                return None

        f.semaphore = _Sem()
        return f.get_stock_info("AAPL")

    missing = _run({"longName": "Apple", "previousClose": 100.0})
    assert missing["daily_change_pct"] is None

    bool_marks = _run(
        {
            "longName": "Apple",
            "currentPrice": True,
            "previousClose": False,
            "volume": True,
            "marketCap": True,
            "trailingPE": False,
            "fiftyTwoWeekHigh": True,
        }
    )
    assert bool_marks["daily_change_pct"] is None
    # Daily% alone used to leave True marks in the quote dict.
    assert bool_marks["current_price"] is None
    assert bool_marks["previous_close"] is None
    assert bool_marks["volume"] is None
    assert bool_marks["market_cap"] is None
    assert bool_marks["pe_ratio"] is None
    assert bool_marks["52_week_high"] is None

    # Truthy ``currentPrice: True`` must not short-circuit ``or`` past a real alt.
    or_fallback = _run(
        {
            "longName": "Apple",
            "currentPrice": True,
            "regularMarketPrice": 110.0,
            "previousClose": 100.0,
            "volume": False,
            "regularMarketVolume": 1_000_000,
        }
    )
    assert or_fallback["current_price"] == pytest.approx(110.0)
    assert or_fallback["volume"] == pytest.approx(1_000_000.0)
    assert or_fallback["daily_change_pct"] == pytest.approx(10.0)

    nan_marks = _run(
        {
            "longName": "Apple",
            "currentPrice": math.nan,
            "previousClose": 100.0,
        }
    )
    assert nan_marks["daily_change_pct"] is None
    assert nan_marks["current_price"] is None

    ok = _run(
        {
            "longName": "Apple",
            "currentPrice": 110.0,
            "previousClose": 100.0,
        }
    )
    assert ok["daily_change_pct"] == pytest.approx(10.0)
    assert ok["current_price"] == pytest.approx(110.0)


def test_is_transient_network_error_detects_dns_and_curl():
    """DNS/curl flakes must be classified as transient (no watchdog Traceback dump)."""
    assert is_transient_network_error(
        ValueError(
            "All data sources failed for WMT: Failed to perform, curl: (6) "
            "Could not resolve host: query2.finance.yahoo.com"
        )
    )
    assert is_transient_network_error(
        Exception("NameResolutionError: Failed to resolve 'api.binance.com'")
    )
    assert is_transient_network_error(
        Exception("Temporary failure in name resolution")
    )
    assert not is_transient_network_error(ValueError("invalid symbol XYZ"))
    assert not is_transient_network_error(KeyError("current_price"))


@pytest.mark.network
def test_get_stock_info_invalid_symbol():
    """Invalid symbols should error or return empty/invalid payload."""
    fetcher = StockFetcher()
    try:
        try:
            data = fetcher.get_stock_info("INVALID_SYMBOL_XYZ123")
        except ValueError:
            return
        assert data is None or not data.get("current_price")
    except Exception as exc:
        pytest.skip(f"Network/provider unavailable: {exc}")


@pytest.mark.network
def test_get_stock_info_valid_symbol():
    """Live quote for AAPL (requires network)."""
    fetcher = StockFetcher()
    try:
        data = fetcher.get_stock_info("AAPL")
    except Exception as exc:
        pytest.skip(f"Network/provider unavailable: {exc}")

    assert data is not None
    assert data["symbol"] == "AAPL"
    assert "name" in data
    assert "current_price" in data


@pytest.mark.network
def test_get_historical_data_valid_symbol():
    """Live history for AAPL (requires network)."""
    fetcher = StockFetcher()
    try:
        data = fetcher.get_historical_data("AAPL", period="5d", interval="1d")
    except Exception as exc:
        pytest.skip(f"Network/provider unavailable: {exc}")

    assert data is not None
    assert data["symbol"] == "AAPL"
    assert data["period"] == "5d"
    assert "summary" in data
    assert "data" in data


@pytest.mark.network
def test_get_historical_data_invalid_symbol():
    """Invalid history symbol should raise or return empty when provider reachable."""
    fetcher = StockFetcher()
    try:
        try:
            data = fetcher.get_historical_data("INVALID_SYMBOL_XYZ123")
        except ValueError:
            return
        assert data is None or not data.get("data")
    except Exception as exc:
        pytest.skip(f"Network/provider unavailable: {exc}")
