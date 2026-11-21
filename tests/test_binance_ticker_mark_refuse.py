"""Binance 24hr ticker marks must refuse bool invents (tradermonty #700/#655)."""

from __future__ import annotations

import pytest

from stock_checker.binance_fetcher import (
    BinanceFetcher,
    _coerce_binance_mark,
    _coerce_binance_signed_pct,
    _coerce_binance_volume,
    _ticker_24hr_fields,
)


def test_coerce_binance_mark_refuses_bool_gap() -> None:
    assert _coerce_binance_mark(True) is None
    assert _coerce_binance_mark(False) is None
    assert _coerce_binance_mark(None) is None
    assert _coerce_binance_mark(0) is None
    assert _coerce_binance_mark("0") is None
    assert _coerce_binance_mark("bad") is None
    assert _coerce_binance_mark(110.5) == pytest.approx(110.5)
    assert _coerce_binance_mark("110.5") == pytest.approx(110.5)


def test_coerce_binance_signed_pct_and_volume() -> None:
    assert _coerce_binance_signed_pct(True) is None
    assert _coerce_binance_signed_pct(-2.5) == pytest.approx(-2.5)
    assert _coerce_binance_signed_pct("0") == pytest.approx(0.0)
    assert _coerce_binance_volume(True) is None
    assert _coerce_binance_volume(False) is None
    assert _coerce_binance_volume(0) == pytest.approx(0.0)
    assert _coerce_binance_volume("12.5") == pytest.approx(12.5)


def test_ticker_24hr_fields_refuses_bool_last() -> None:
    assert _ticker_24hr_fields({"lastPrice": True}) is None
    out = _ticker_24hr_fields(
        {
            "lastPrice": "42000.5",
            "priceChangePercent": True,
            "highPrice": False,
            "lowPrice": "0",
            "volume": True,
            "quoteVolume": "1e9",
            "count": True,
            "closeTime": 99,
        }
    )
    assert out is not None
    assert out["current_price"] == pytest.approx(42000.5)
    assert out["change_24h"] is None
    assert out["high_24h"] is None
    assert out["low_24h"] is None
    assert out["volume_24h"] is None
    assert out["volume_usdt"] == pytest.approx(1e9)
    assert out["trade_count_24h"] is None
    assert out["timestamp"] == 99


def test_get_crypto_price_refuses_bool_last(monkeypatch) -> None:
    fetcher = BinanceFetcher()

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "lastPrice": True,
                "priceChangePercent": "1.0",
                "highPrice": "2.0",
                "lowPrice": "0.5",
                "volume": "10",
                "closeTime": 1,
            }

    monkeypatch.setattr(fetcher.session, "get", lambda *a, **k: _Resp())
    assert fetcher.get_crypto_price("BTCUSDT") is None


def test_get_crypto_price_keeps_real_string_marks(monkeypatch) -> None:
    fetcher = BinanceFetcher()

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "lastPrice": "65000.1",
                "priceChangePercent": "-1.25",
                "highPrice": "66000",
                "lowPrice": "64000",
                "volume": "12.5",
                "closeTime": 42,
            }

    monkeypatch.setattr(fetcher.session, "get", lambda *a, **k: _Resp())
    out = fetcher.get_crypto_price("BTCUSDT")
    assert out is not None
    assert out["current_price"] == pytest.approx(65000.1)
    assert out["change_24h"] == pytest.approx(-1.25)
    assert out["high_24h"] == pytest.approx(66000)
    assert out["low_24h"] == pytest.approx(64000)
    assert out["volume_24h"] == pytest.approx(12.5)
    assert out["source"] == "binance"


def test_get_multiple_prices_skips_bool_last(monkeypatch) -> None:
    fetcher = BinanceFetcher()

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return [
                {
                    "symbol": "BTCUSDT",
                    "lastPrice": True,
                    "priceChangePercent": "1",
                    "highPrice": "2",
                    "lowPrice": "1",
                    "volume": "3",
                    "closeTime": 1,
                },
                {
                    "symbol": "ETHUSDT",
                    "lastPrice": "3000",
                    "priceChangePercent": "2",
                    "highPrice": "3100",
                    "lowPrice": "2900",
                    "volume": "4",
                    "closeTime": 2,
                },
            ]

    monkeypatch.setattr(fetcher.session, "get", lambda *a, **k: _Resp())
    out = fetcher.get_multiple_prices(["BTCUSDT", "ETHUSDT"])
    assert "BTCUSDT" not in out
    assert out["ETHUSDT"]["current_price"] == pytest.approx(3000)
