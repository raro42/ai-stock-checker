"""Offline tests for Yahoo movers → universe discovery helpers."""

from stock_checker.yahoo_universe_discovery import (
    _quotes_from_screen_payload,
    discover_yahoo_mover_symbols,
)


def test_quotes_from_screen_payload():
    assert _quotes_from_screen_payload(None) == []
    assert _quotes_from_screen_payload({"quotes": [{"symbol": "AAPL"}]})[0]["symbol"] == "AAPL"


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
