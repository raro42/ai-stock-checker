"""Offline: bounded yfinance history timeout (tradermonty #904/#905)."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from stock_checker.yfinance_history import (
    DEFAULT_YF_HISTORY_TIMEOUT_SEC,
    coerce_yf_history_timeout_sec,
    fetch_yfinance_history,
)
from stock_checker.promoted_strategy import load_daily_closes_yfinance


def test_coerce_yf_history_timeout_sec_refuses_bool_and_gap():
    assert coerce_yf_history_timeout_sec(True) == DEFAULT_YF_HISTORY_TIMEOUT_SEC
    assert coerce_yf_history_timeout_sec(False) == DEFAULT_YF_HISTORY_TIMEOUT_SEC
    assert coerce_yf_history_timeout_sec(None) == DEFAULT_YF_HISTORY_TIMEOUT_SEC
    assert coerce_yf_history_timeout_sec(0) == DEFAULT_YF_HISTORY_TIMEOUT_SEC
    assert coerce_yf_history_timeout_sec(-1) == DEFAULT_YF_HISTORY_TIMEOUT_SEC
    assert coerce_yf_history_timeout_sec(15) == 15


def test_fetch_yfinance_history_timeout_raises():
    """Hung worker after join ceiling → TimeoutError (not quiet empty)."""

    class _HangTicker:
        def history(self, period="1mo", interval="1d"):
            threading.Event().wait(30)
            return SimpleNamespace(empty=False)

    with patch("yfinance.Ticker", return_value=_HangTicker()):
        with pytest.raises(TimeoutError, match="timed out"):
            fetch_yfinance_history("AAPL", timeout_sec=1)


def test_fetch_yfinance_history_success():
    frame = SimpleNamespace(empty=False, Close=[1.0, 2.0])

    class _OkTicker:
        def history(self, period="1mo", interval="1d"):
            return frame

    with patch("yfinance.Ticker", return_value=_OkTicker()):
        out = fetch_yfinance_history("AAPL", timeout_sec=5)
    assert out is frame


def test_load_daily_closes_timeout_fail_open():
    def _boom(*_a, **_k):
        raise TimeoutError("yfinance history AAPL timed out after 1s")

    with patch(
        "stock_checker.yfinance_history.fetch_yfinance_history", _boom
    ):
        assert load_daily_closes_yfinance("AAPL") == []


def test_get_historical_data_timeout_raises_valueerror():
    from stock_checker.fetcher import StockFetcher

    def _boom(*_a, **_k):
        raise TimeoutError("yfinance history AAPL timed out after 1s")

    with patch(
        "stock_checker.yfinance_history.fetch_yfinance_history", _boom
    ):
        with pytest.raises(ValueError, match="timed out|Failed to fetch"):
            StockFetcher().get_historical_data("AAPL", period="5d")
