"""Finnhub quote marks must refuse bool invents (tradermonty #700/#655)."""

from __future__ import annotations

import pytest

from stock_checker.finnhub_fetcher import FinnhubFetcher, _coerce_finnhub_mark


def test_coerce_finnhub_mark_refuses_bool_gap() -> None:
    assert _coerce_finnhub_mark(True) is None
    assert _coerce_finnhub_mark(False) is None
    assert _coerce_finnhub_mark(None) is None
    assert _coerce_finnhub_mark(0) is None
    assert _coerce_finnhub_mark(110.5) == pytest.approx(110.5)


def test_get_stock_info_refuses_bool_quote_marks(monkeypatch) -> None:
    """True→$1 quote fields must not invent Finnhub context."""
    fetcher = FinnhubFetcher.__new__(FinnhubFetcher)
    fetcher.api_key = "test"
    fetcher.base_url = "https://finnhub.io/api/v1"
    fetcher.session = object()
    monkeypatch.setattr(fetcher, "_wait_for_rate_limit", lambda: None)

    class _Resp:
        def __init__(self, payload: dict):
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    calls = {"n": 0}

    def _get(url, params=None, timeout=10):
        calls["n"] += 1
        if "quote" in url:
            return _Resp(
                {
                    "c": True,
                    "pc": False,
                    "h": True,
                    "l": 0,
                }
            )
        return _Resp(
            {
                "name": "Acme",
                "marketCapitalization": True,
                "52WeekHigh": True,
                "52WeekLow": False,
            }
        )

    fetcher.session = type("S", (), {"get": staticmethod(_get)})()
    out = fetcher.get_stock_info("ACME")
    assert out["symbol"] == "ACME"
    assert out["current_price"] is None
    assert out["previous_close"] is None
    assert out["daily_change_pct"] is None
    assert out["day_high"] is None
    assert out["day_low"] is None
    assert out["market_cap"] is None
    assert out["52_week_high"] is None
    assert out["52_week_low"] is None
    assert calls["n"] == 2


def test_get_stock_info_keeps_real_marks(monkeypatch) -> None:
    fetcher = FinnhubFetcher.__new__(FinnhubFetcher)
    fetcher.api_key = "test"
    fetcher.base_url = "https://finnhub.io/api/v1"
    monkeypatch.setattr(fetcher, "_wait_for_rate_limit", lambda: None)

    class _Resp:
        def __init__(self, payload: dict):
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    def _get(url, params=None, timeout=10):
        if "quote" in url:
            return _Resp({"c": 110.0, "pc": 100.0, "h": 112.0, "l": 99.0})
        return _Resp(
            {
                "name": "Acme",
                "marketCapitalization": 5_000.0,  # millions → $5B
                "52WeekHigh": 150.0,
                "52WeekLow": 80.0,
            }
        )

    fetcher.session = type("S", (), {"get": staticmethod(_get)})()
    out = fetcher.get_stock_info("ACME")
    assert out["current_price"] == pytest.approx(110.0)
    assert out["previous_close"] == pytest.approx(100.0)
    assert out["daily_change_pct"] == pytest.approx(10.0)
    assert out["day_high"] == pytest.approx(112.0)
    assert out["day_low"] == pytest.approx(99.0)
    assert out["market_cap"] == pytest.approx(5_000_000_000.0)
    assert out["52_week_high"] == pytest.approx(150.0)
    assert out["52_week_low"] == pytest.approx(80.0)
