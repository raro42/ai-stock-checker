"""CLI + history summary must not invent flat 0 / True→1 marks."""

from __future__ import annotations

import pandas as pd

from stock_checker.cli import (
    format_historical_summary,
    format_stock_info,
    _fmt_signed_pct,
    _fmt_signed_money,
    _fmt_volume,
)
from stock_checker.fetcher import StockFetcher


def test_cli_fmt_helpers_refuse_none_bool():
    assert _fmt_signed_pct(None) == "n/a"
    assert _fmt_signed_pct(True) == "n/a"
    assert _fmt_signed_pct(1.5) == "+1.50%"
    assert _fmt_signed_pct(-2.0) == "-2.00%"
    assert _fmt_signed_money(None) == "n/a"
    assert _fmt_signed_money(False) == "n/a"
    assert _fmt_signed_money(-3.2) == "$-3.20"
    assert _fmt_volume(None) == "n/a"
    assert _fmt_volume(True) == "n/a"
    assert _fmt_volume(0) == "0"
    assert _fmt_volume(1_500) == "1,500"


def test_format_historical_summary_speaks_na_on_missing():
    text = format_historical_summary(
        {
            "symbol": "AAPL",
            "period": "1mo",
            "interval": "1d",
            "summary": {
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "num_records": 20,
                "avg_volume": None,
                "price_change": None,
                "price_change_pct": None,
            },
        }
    )
    assert "Avg Volume:       n/a" in text
    assert "Price Change:     n/a" in text
    assert "Change %:         n/a" in text
    assert "+0.00" not in text
    assert "$0.00" not in text


def test_format_stock_info_refuses_bool_marks():
    text = format_stock_info(
        {
            "name": "Apple",
            "symbol": "AAPL",
            "current_price": True,
            "previous_close": False,
            "day_low": True,
            "day_high": True,
            "52_week_low": None,
            "52_week_high": None,
            "volume": True,
            "market_cap": True,
            "pe_ratio": False,
            "dividend_yield": None,
        }
    )
    assert "Current Price:    n/a" in text
    assert "Previous Close:   n/a" in text
    assert "Volume:           n/a" in text
    assert "Market Cap:       n/a" in text
    assert "P/E Ratio:        n/a" in text
    assert "Dividend Yield:   n/a" in text


def test_historical_summary_refuses_bool_closes(monkeypatch):
    """tradermonty #655/#798: bool closes must not invent $1 / flat %."""
    idx = pd.to_datetime(["2026-01-01", "2026-01-02"])
    hist = pd.DataFrame(
        {
            "Close": [True, False],
            "Volume": [True, False],
        },
        index=idx,
    )
    monkeypatch.setattr(
        "stock_checker.yfinance_history.fetch_yfinance_history",
        lambda *_a, **_k: hist,
    )
    out = StockFetcher().get_historical_data("AAPL", period="5d")
    summary = out["summary"]
    assert summary["avg_volume"] is None
    assert summary["price_change"] is None
    assert summary["price_change_pct"] is None


def test_historical_summary_keeps_real_flat_zero(monkeypatch):
    """Real flat closes still speak 0 change (not unavailable)."""
    idx = pd.to_datetime(["2026-01-01", "2026-01-02"])
    hist = pd.DataFrame(
        {
            "Close": [100.0, 100.0],
            "Volume": [0.0, 0.0],
        },
        index=idx,
    )
    monkeypatch.setattr(
        "stock_checker.yfinance_history.fetch_yfinance_history",
        lambda *_a, **_k: hist,
    )
    out = StockFetcher().get_historical_data("AAPL", period="5d")
    summary = out["summary"]
    assert summary["avg_volume"] == 0.0
    assert summary["price_change"] == 0.0
    assert summary["price_change_pct"] == 0.0
    text = format_historical_summary(out)
    assert "Avg Volume:       0" in text
    assert "Price Change:     $+0.00" in text
    assert "Change %:         0.00%" in text
