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


def test_cli_backtest_history_timeout_exits_one(capsys):
    """CLI backtest must not hang forever on Yahoo history (tradermonty #904/#905)."""
    from types import SimpleNamespace

    from stock_checker.cli import cmd_backtest

    def _boom(*_a, **_k):
        raise TimeoutError("yfinance history AAPL timed out after 20s")

    args = SimpleNamespace(
        symbols=["AAPL"],
        period="1y",
        interval="1d",
        strategy="sma",
        capital=10_000.0,
        fee=0.001,
        slippage=0.0,
        position_size=0.1,
        json=False,
    )
    with patch(
        "stock_checker.yfinance_history.fetch_yfinance_history", _boom
    ):
        code = cmd_backtest(args)
    assert code == 1
    err = capsys.readouterr().err
    assert "timed out" in err.lower() or "history failed" in err.lower()


def test_desk_mark_fetch_history_timeout_fail_open():
    """Desk mark path must not hang forever on Yahoo history (#904/#905)."""
    from openbb_backend.desk import _fetch_yfinance_prices

    def _boom(*_a, **_k):
        raise TimeoutError("yfinance history AAPL timed out after 4s")

    with patch(
        "stock_checker.yfinance_history.fetch_yfinance_history", _boom
    ):
        assert _fetch_yfinance_prices(["AAPL"], timeout_s=4.0) == {}


def test_charts_price_history_timeout_fail_open(tmp_path):
    """Charts equity bars must not hang forever on Yahoo history (#904/#905)."""
    from openbb_backend.charts import fetch_price_history

    def _boom(*_a, **_k):
        raise TimeoutError("yfinance history AAPL timed out after 20s")

    with patch(
        "stock_checker.yfinance_history.fetch_yfinance_history", _boom
    ):
        assert fetch_price_history("AAPL", tmp_path, live=True) == []


def test_run_experiment_history_timeout_uses_synthetic(tmp_path, monkeypatch):
    """Overnight bar loader must not hang forever on Yahoo history (#904/#905)."""
    import scripts.run_experiment as re

    monkeypatch.setattr(re, "DATA_DIR", tmp_path)

    def _boom(*_a, **_k):
        raise TimeoutError("yfinance history SPY timed out after 20s")

    with patch(
        "stock_checker.yfinance_history.fetch_yfinance_history", _boom
    ):
        out = re.load_bars(["SPY"])
    assert "SPY" in out
    assert len(out["SPY"]) > 0
