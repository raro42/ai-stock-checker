"""tradermonty #778: Finnhub RequestException paths never echo token= URLs."""

from __future__ import annotations

import pytest
import requests

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
