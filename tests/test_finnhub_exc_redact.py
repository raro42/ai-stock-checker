"""tradermonty #778: Finnhub RequestException paths never echo token= URLs."""

from __future__ import annotations

import pytest
import requests

from stock_checker.fetcher import StockFetcher
from stock_checker.finnhub_fetcher import FinnhubFetcher


def test_finnhub_request_exception_is_class_only(monkeypatch):
    secret = "finnhubRaiseLeak99"  # pragma: allowlist secret
    monkeypatch.setenv("FINNHUB_API_KEY", secret)
    fetcher = FinnhubFetcher(api_key=secret)
    monkeypatch.setattr(fetcher, "_wait_for_rate_limit", lambda: None)

    def boom(*_a, **_k):
        raise requests.exceptions.Timeout(
            f"https://finnhub.io/api/v1/quote?symbol=MSFT&token={secret}"
        )

    monkeypatch.setattr(fetcher.session, "get", boom)

    with pytest.raises(ValueError) as caught:
        fetcher.get_stock_info("MSFT")

    msg = str(caught.value)
    assert secret not in msg
    assert "token=" not in msg
    assert "Timeout" in msg
    assert "MSFT" in msg


def test_historical_data_exception_is_redacted(monkeypatch):
    """StockFetcher history raises must not echo token= query strings."""
    secret = "histExcLeak99"  # pragma: allowlist secret

    class BoomTicker:
        def history(self, *_a, **_k):
            raise ConnectionError(
                f"Max retries with url: /v1/quote?symbol=AAPL&token={secret}"
            )

    monkeypatch.setattr(
        "stock_checker.fetcher.yf.Ticker", lambda *_a, **_k: BoomTicker()
    )

    with pytest.raises(ValueError) as caught:
        StockFetcher().get_historical_data("AAPL", period="1mo")

    msg = str(caught.value)
    assert secret not in msg
    assert "token=REDACTED" in msg
    assert "AAPL" in msg
