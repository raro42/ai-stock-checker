"""Offline tests for Yahoo movers → universe discovery helpers."""

from stock_checker.yahoo_universe_discovery import (
    YahooScreenEmptyError,
    _quotes_from_screen_payload,
    discover_yahoo_mover_report,
    discover_yahoo_mover_symbols,
    screen_payload_failed,
    screens_bundle_failed,
)


def test_quotes_from_screen_payload():
    assert _quotes_from_screen_payload(None) == []
    assert _quotes_from_screen_payload({"quotes": [{"symbol": "AAPL"}]})[0]["symbol"] == "AAPL"


def test_screen_payload_failed_empty_or_thin():
    assert screen_payload_failed(None, expected=25) is True
    assert screen_payload_failed({"quotes": []}, expected=25) is True
    assert screen_payload_failed(
        {"quotes": [{"symbol": "AAPL"}, {"symbol": "MSFT"}]}, expected=25
    ) is True
    fat = {"quotes": [{"symbol": f"S{i}"} for i in range(10)]}
    assert screen_payload_failed(fat, expected=25) is False


def test_discover_yahoo_mover_symbols_mocked(monkeypatch):
    def fake_fetch(screen: str, *, count: int = 25):
        if screen == "day_gainers":
            return ["AAPL", "USDT"]  # USDT filtered by is_tradeable
        if screen == "day_losers":
            return ["MSFT", "AAPL"]
        return ["NVDA"]

    monkeypatch.setattr(
        "stock_checker.yahoo_universe_discovery.fetch_yahoo_screen_symbols",
        fake_fetch,
    )
    syms = discover_yahoo_mover_symbols(
        screens=("day_gainers", "day_losers", "most_actives"), per_screen=5
    )
    assert syms == ["AAPL", "MSFT", "NVDA"]


def test_discover_yahoo_mover_report_all_empty_is_failed(monkeypatch):
    def boom(screen: str, *, count: int = 25):
        raise YahooScreenEmptyError(screen)

    monkeypatch.setattr(
        "stock_checker.yahoo_universe_discovery.fetch_yahoo_screen_symbols",
        boom,
    )
    symbols, ok, failed = discover_yahoo_mover_report(
        screens=("day_gainers", "day_losers"), per_screen=5
    )
    assert symbols == []
    assert ok == 0
    assert failed == 2
    assert screens_bundle_failed(ok, failed) is True


def test_screens_bundle_failed_majority_or_empty():
    assert screens_bundle_failed(0, 3) is True
    assert screens_bundle_failed(1, 2) is True
    assert screens_bundle_failed(2, 1) is False
    assert screens_bundle_failed(3, 0) is False


def test_yahoo_cache_freshness_seed_age_bands():
    from stock_checker.yahoo_universe_discovery import yahoo_cache_freshness

    assert yahoo_cache_freshness(None) == "never"
    assert yahoo_cache_freshness(0, parsed=False) == "unknown"
    assert yahoo_cache_freshness(6 * 3600) == "fresh"
    assert yahoo_cache_freshness(30 * 3600) == "aging"
    assert yahoo_cache_freshness(50 * 3600) == "stale"


def test_fetch_yahoo_screen_403_is_empty_error(monkeypatch):
    import pytest

    from stock_checker.yahoo_universe_discovery import fetch_yahoo_screen_symbols

    class _YF:
        @staticmethod
        def screen(screen, count=25):
            raise RuntimeError("HTTP Error 403: Forbidden")

    monkeypatch.setitem(__import__("sys").modules, "yfinance", _YF)
    with pytest.raises(YahooScreenEmptyError):
        fetch_yahoo_screen_symbols("day_gainers", count=5)
