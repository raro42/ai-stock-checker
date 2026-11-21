"""Binance recent/agg trades must refuse bool invents and isolate bad prints."""

from __future__ import annotations

import pytest

from stock_checker.binance_fetcher import (
    BinanceFetcher,
    _parse_agg_trade,
    _parse_recent_trade,
)


def test_parse_recent_trade_refuses_bool_marks() -> None:
    assert _parse_recent_trade(
        {
            "id": 1,
            "price": True,
            "qty": "1",
            "quoteQty": "1",
            "time": 1,
            "isBuyerMaker": False,
        }
    ) is None
    assert _parse_recent_trade(
        {
            "id": 1,
            "price": "100",
            "qty": True,
            "quoteQty": "100",
            "time": 1,
            "isBuyerMaker": False,
        }
    ) is None
    assert _parse_recent_trade(
        {
            "id": 1,
            "price": "100",
            "qty": "1",
            "quoteQty": False,
            "time": 1,
            "isBuyerMaker": False,
        }
    ) is None
    # Maker side must be a real bool (not invent buy/sell from junk).
    assert _parse_recent_trade(
        {
            "id": 1,
            "price": "100",
            "qty": "1",
            "quoteQty": "100",
            "time": 1,
            "isBuyerMaker": "yes",
        }
    ) is None
    out = _parse_recent_trade(
        {
            "id": 7,
            "price": "100.5",
            "qty": "2.0",
            "quoteQty": "201",
            "time": 99,
            "isBuyerMaker": True,
        }
    )
    assert out is not None
    assert out["price"] == pytest.approx(100.5)
    assert out["qty"] == pytest.approx(2.0)
    assert out["quote_qty"] == pytest.approx(201.0)
    assert out["is_buyer_maker"] is True
    assert out["is_buy"] is False


def test_parse_agg_trade_refuses_bool_marks() -> None:
    assert _parse_agg_trade({"p": True, "q": "1", "f": 1, "l": 1, "T": 1, "m": False}) is None
    assert _parse_agg_trade({"p": "100", "q": False, "f": 1, "l": 1, "T": 1, "m": False}) is None
    assert _parse_agg_trade({"p": "100", "q": "1", "f": 1, "l": 1, "T": 1, "m": 1}) is None
    out = _parse_agg_trade({"p": "99.5", "q": "3", "f": 10, "l": 12, "T": 50, "m": False})
    assert out is not None
    assert out["price"] == pytest.approx(99.5)
    assert out["qty"] == pytest.approx(3.0)
    assert out["is_buy"] is True


def test_get_recent_trades_isolates_bool_prints(monkeypatch) -> None:
    fetcher = BinanceFetcher()

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return [
                {
                    "id": 1,
                    "price": True,
                    "qty": "1",
                    "quoteQty": "1",
                    "time": 1,
                    "isBuyerMaker": False,
                },
                {
                    "id": 2,
                    "price": "100",
                    "qty": "1.5",
                    "quoteQty": "150",
                    "time": 2,
                    "isBuyerMaker": False,
                },
                {
                    "id": 3,
                    "price": "99",
                    "qty": True,
                    "quoteQty": "99",
                    "time": 3,
                    "isBuyerMaker": True,
                },
            ]

    monkeypatch.setattr(fetcher.session, "get", lambda *a, **k: _Resp())
    out = fetcher.get_recent_trades("BTCUSDT")
    assert out is not None
    assert len(out) == 1
    assert out[0]["id"] == 2
    assert out[0]["price"] == pytest.approx(100.0)
    assert out[0]["is_buy"] is True


def test_get_agg_trades_isolates_bool_prints(monkeypatch) -> None:
    fetcher = BinanceFetcher()

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return [
                {"p": True, "q": "1", "f": 1, "l": 1, "T": 1, "m": False},
                {"p": "101", "q": "2", "f": 2, "l": 3, "T": 2, "m": True},
                {"p": "102", "q": False, "f": 4, "l": 4, "T": 3, "m": False},
            ]

    monkeypatch.setattr(fetcher.session, "get", lambda *a, **k: _Resp())
    out = fetcher.get_agg_trades("ETHUSDT")
    assert out is not None
    assert len(out) == 1
    assert out[0]["price"] == pytest.approx(101.0)
    assert out[0]["is_buy"] is False


def test_analyze_buy_sell_pressure_skips_bool_invent(monkeypatch) -> None:
    fetcher = BinanceFetcher()
    good = [
        {
            "id": i,
            "price": "100",
            "qty": "1",
            "quoteQty": "100",
            "time": i,
            "isBuyerMaker": i % 2 == 0,
        }
        for i in range(12)
    ]
    junk = [
        {
            "id": 99,
            "price": True,
            "qty": "1",
            "quoteQty": "1",
            "time": 99,
            "isBuyerMaker": False,
        }
    ]

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return junk + good

    monkeypatch.setattr(fetcher.session, "get", lambda *a, **k: _Resp())
    out = fetcher.analyze_buy_sell_pressure("BTCUSDT")
    assert out is not None
    assert out["total_trades"] == 12
    assert out["buy_count"] + out["sell_count"] == 12
