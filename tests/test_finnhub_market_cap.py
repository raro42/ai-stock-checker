"""tradermonty #810: Finnhub marketCapitalization is millions → dollars."""

from __future__ import annotations

import math

from stock_checker.finnhub_fetcher import finnhub_market_cap_dollars


def test_finnhub_market_cap_millions_to_dollars() -> None:
    # AAPL-scale ~3e6 millions → ~$3T
    assert finnhub_market_cap_dollars(3_000_000.0) == 3_000_000_000_000.0
    # Mid-cap 765.59 millions → $765_590_000 (same fixture shape as #810)
    assert finnhub_market_cap_dollars(765.59) == 765_590_000.0


def test_finnhub_market_cap_refuses_bool_gap_nonpositive() -> None:
    assert finnhub_market_cap_dollars(True) is None
    assert finnhub_market_cap_dollars(False) is None
    assert finnhub_market_cap_dollars(0) is None
    assert finnhub_market_cap_dollars(-1) is None
    assert finnhub_market_cap_dollars(math.nan) is None
    assert finnhub_market_cap_dollars(math.inf) is None
    assert finnhub_market_cap_dollars(None) is None
    assert finnhub_market_cap_dollars("765.59") is None
