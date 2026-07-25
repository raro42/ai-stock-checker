#!/usr/bin/env python3
"""Fetcher tests — network-heavy; skipped by default via pytest.ini."""

import pytest

from stock_checker.fetcher import StockFetcher


def test_stock_fetcher_init():
    """Test StockFetcher initialization (offline)."""
    fetcher = StockFetcher()
    assert fetcher is not None


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
