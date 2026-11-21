"""CoinMarketCap quote marks must refuse bool invents (tradermonty #700/#655)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from stock_checker.coinmarketcap_fetcher import (
    CoinMarketCapFetcher,
    _coerce_cmc_mark,
    _coerce_cmc_signed_pct,
    _coerce_cmc_volume,
    _parse_cmc_coin,
)


def test_coerce_cmc_mark_refuses_bool_gap() -> None:
    assert _coerce_cmc_mark(True) is None
    assert _coerce_cmc_mark(False) is None
    assert _coerce_cmc_mark(None) is None
    assert _coerce_cmc_mark(0) is None
    assert _coerce_cmc_mark("0") is None
    assert _coerce_cmc_mark("bad") is None
    assert _coerce_cmc_mark(110.5) == pytest.approx(110.5)
    assert _coerce_cmc_mark("110.5") == pytest.approx(110.5)


def test_coerce_cmc_signed_pct_and_volume() -> None:
    assert _coerce_cmc_signed_pct(True) is None
    assert _coerce_cmc_signed_pct(-2.5) == pytest.approx(-2.5)
    assert _coerce_cmc_signed_pct("0") == pytest.approx(0.0)
    assert _coerce_cmc_volume(True) is None
    assert _coerce_cmc_volume(False) is None
    assert _coerce_cmc_volume(0) == pytest.approx(0.0)
    assert _coerce_cmc_volume("12.5") == pytest.approx(12.5)


def test_parse_cmc_coin_refuses_bool_price_or_change() -> None:
    assert _parse_cmc_coin({"symbol": "BTC"}, {"price": True, "percentChange24h": 1}) is None
    assert _parse_cmc_coin({"symbol": "BTC"}, {"price": 100, "percentChange24h": True}) is None
    assert _parse_cmc_coin({"symbol": "BTC"}, {"price": 100, "percentChange24h": None}) is None
    # True > 0 would have invented a gainer before refuse.
    assert _parse_cmc_coin({"symbol": "X"}, {"price": False, "percentChange24h": False}) is None
    out = _parse_cmc_coin(
        {"symbol": "ETH", "name": "Ethereum"},
        {
            "price": "2500.5",
            "percentChange24h": 3.25,
            "volume24h": True,
            "marketCap": "1e11",
        },
    )
    assert out is not None
    assert out["symbol"] == "ETH"
    assert out["price"] == pytest.approx(2500.5)
    assert out["change_24h"] == pytest.approx(3.25)
    assert out["volume_24h"] is None
    assert out["market_cap"] == pytest.approx(1e11)
    assert out["source"] == "coinmarketcap"


def test_get_top_movers_isolates_bool_prints(monkeypatch) -> None:
    payload = {
        "data": {
            "cryptoCurrencyList": [
                {
                    "symbol": "BAD",
                    "name": "Bad",
                    "quotes": [{"price": True, "percentChange24h": 10.0}],
                },
                {
                    "symbol": "FAKE",
                    "name": "Fake",
                    "quotes": [{"price": 1.0, "percentChange24h": True}],
                },
                {
                    "symbol": "OK",
                    "name": "Ok",
                    "quotes": [
                        {
                            "price": 42.0,
                            "percentChange24h": 8.0,
                            "volume24h": 1e6,
                            "marketCap": 1e9,
                        }
                    ],
                },
                {
                    "symbol": "DOWN",
                    "name": "Down",
                    "quotes": [
                        {
                            "price": "9.5",
                            "percentChange24h": -6.0,
                            "volume24h": 0,
                            "marketCap": 100,
                        }
                    ],
                },
            ]
        }
    }
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=payload)
    session = MagicMock()
    session.get = MagicMock(return_value=resp)

    fetcher = CoinMarketCapFetcher()
    fetcher.session = session
    out = fetcher.get_top_movers()
    assert [c["symbol"] for c in out["gainers"]] == ["OK"]
    assert [c["symbol"] for c in out["losers"]] == ["DOWN"]
    assert out["gainers"][0]["price"] == pytest.approx(42.0)
    assert out["losers"][0]["change_24h"] == pytest.approx(-6.0)


def test_get_trending_isolates_bool_prints(monkeypatch) -> None:
    payload = {
        "data": {
            "trendingList": [
                {
                    "symbol": "JUNK",
                    "name": "Junk",
                    "priceChange": {},
                    "quotes": [{"price": True, "percentChange24h": 2}],
                },
                {
                    "symbol": "UP",
                    "name": "Up",
                    "priceChange": {},
                    "quotes": [{"price": 10.0, "percentChange24h": 1.5}],
                },
                {
                    "symbol": "FLAT",
                    "name": "Flat",
                    "priceChange": {},
                    "quotes": [{"price": 5.0, "percentChange24h": 0.0}],
                },
            ]
        },
        "status": {"timestamp": "t"},
    }
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=payload)
    session = MagicMock()
    session.get = MagicMock(return_value=resp)

    fetcher = CoinMarketCapFetcher()
    fetcher.session = session
    out = fetcher.get_trending_gainers_losers()
    assert [c["symbol"] for c in out["gainers"]] == ["UP"]
    assert [c["symbol"] for c in out["losers"]] == ["FLAT"]
    assert out["timestamp"] == "t"
