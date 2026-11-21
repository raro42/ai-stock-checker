"""Binance orderbook/klines must refuse bool invents and isolate bad rows."""

from __future__ import annotations

import pytest

from stock_checker.binance_fetcher import (
    BinanceFetcher,
    _parse_extended_kline_candle,
    _parse_kline_candle,
    _parse_orderbook_level,
    _parse_orderbook_side,
)


def test_parse_orderbook_level_refuses_bool() -> None:
    assert _parse_orderbook_level([True, 1.0]) is None
    assert _parse_orderbook_level([100.0, True]) is None
    assert _parse_orderbook_level([False, False]) is None
    assert _parse_orderbook_level(["bad", "1"]) is None
    assert _parse_orderbook_level(["100.5", "2.0"]) == [pytest.approx(100.5), pytest.approx(2.0)]


def test_parse_orderbook_side_isolates_bad_levels() -> None:
    rows = [
        [True, 1.0],
        ["99.0", "1.5"],
        [False, "2"],
        ["98.5", "3.0"],
        ["junk", "1"],
    ]
    out = _parse_orderbook_side(rows, take=5)
    assert out == [
        [pytest.approx(99.0), pytest.approx(1.5)],
        [pytest.approx(98.5), pytest.approx(3.0)],
    ]


def test_parse_kline_candle_refuses_bool_ohlc() -> None:
    assert _parse_kline_candle([0, True, 2, 1, 1.5, 10, 1]) is None
    assert _parse_kline_candle([0, 1, 2, 0.5, 1.5, True, 1]) is None
    out = _parse_kline_candle([10, "1", "2", "0.5", "1.5", "10", 20])
    assert out is not None
    assert out["open"] == pytest.approx(1.0)
    assert out["high"] == pytest.approx(2.0)
    assert out["low"] == pytest.approx(0.5)
    assert out["close"] == pytest.approx(1.5)
    assert out["volume"] == pytest.approx(10.0)


def test_parse_extended_kline_refuses_bool_num_trades() -> None:
    row = [0, "1", "2", "0.5", "1.5", "10", 1, "100", True, "5", "50"]
    assert _parse_extended_kline_candle(row) is None
    good = [0, "1", "2", "0.5", "1.5", "10", 1, "100", 7, "5", "50"]
    out = _parse_extended_kline_candle(good)
    assert out is not None
    assert out["num_trades"] == 7
    assert out["quote_volume"] == pytest.approx(100.0)


def test_get_orderbook_depth_isolates_bool_levels(monkeypatch) -> None:
    fetcher = BinanceFetcher()

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "bids": [[True, "1"], ["100", "2"], ["99", True]],
                "asks": [[False, "1"], ["101", "3"]],
            }

    monkeypatch.setattr(fetcher.session, "get", lambda *a, **k: _Resp())
    out = fetcher.get_orderbook_depth("BTCUSDT")
    assert out is not None
    assert out["best_bid"] == pytest.approx(100.0)
    assert out["best_ask"] == pytest.approx(101.0)
    assert out["bids"] == [[pytest.approx(100.0), pytest.approx(2.0)]]
    assert out["asks"] == [[pytest.approx(101.0), pytest.approx(3.0)]]


def test_get_orderbook_depth_empty_after_refuse(monkeypatch) -> None:
    fetcher = BinanceFetcher()

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"bids": [[True, True]], "asks": [["101", "1"]]}

    monkeypatch.setattr(fetcher.session, "get", lambda *a, **k: _Resp())
    assert fetcher.get_orderbook_depth("BTCUSDT") is None


def test_get_klines_skips_bool_bars(monkeypatch) -> None:
    fetcher = BinanceFetcher()

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return [
                [0, True, 2, 1, 1.5, 10, 1],
                [1, "10", "11", "9", "10.5", "20", 2],
            ]

    monkeypatch.setattr(fetcher.session, "get", lambda *a, **k: _Resp())
    out = fetcher.get_klines("BTCUSDT", limit=2)
    assert out is not None
    assert len(out) == 1
    assert out[0]["close"] == pytest.approx(10.5)


def test_check_liquidity_refuses_bool_book(monkeypatch) -> None:
    fetcher = BinanceFetcher()

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "bids": [[True, "5"], ["100", "5"]],
                "asks": [["100.1", "5"]],
            }

    monkeypatch.setattr(fetcher.session, "get", lambda *a, **k: _Resp())
    out = fetcher.check_liquidity("BTCUSDT")
    assert out is not None
    assert out["best_bid"] == pytest.approx(100.0)
    assert out["best_ask"] == pytest.approx(100.1)
