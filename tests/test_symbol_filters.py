#!/usr/bin/env python3
"""Unit tests for symbol filters (no network)."""

from stock_checker.symbol_filters import (
    filter_ranked_opportunities,
    filter_tradeable_symbols,
    is_stablecoin,
    is_tradeable_symbol,
)


def test_rejects_stablecoins():
    assert is_stablecoin("USDC-USD")
    assert is_stablecoin("USDT")
    assert is_stablecoin("DAI-USD")
    assert not is_stablecoin("BTC-USD")
    assert not is_stablecoin("AAPL")


def test_rejects_leveraged_tokens():
    assert not is_tradeable_symbol("BTCUPUSDT")
    assert not is_tradeable_symbol("ETHDOWN-USD")


def test_allows_major_assets():
    assert is_tradeable_symbol("AAPL")
    assert is_tradeable_symbol("BTC-USD")
    assert is_tradeable_symbol("ETHUSDT")


def test_filter_list_and_opportunities():
    symbols = ["AAPL", "USDC-USD", "BTC-USD", "USDC-USD", "DOGE-USD"]
    filtered = filter_tradeable_symbols(symbols)
    assert filtered == ["AAPL", "BTC-USD", "DOGE-USD"]

    opps = filter_ranked_opportunities(
        [
            {"symbol": "USDC-USD", "score": 99},
            {"symbol": "NVDA", "score": 10},
        ]
    )
    assert len(opps) == 1
    assert opps[0]["symbol"] == "NVDA"
