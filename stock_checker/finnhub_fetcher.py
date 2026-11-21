#!/usr/bin/env python3

from __future__ import annotations

import math
import numbers
import os
import time
from collections import deque
from typing import Dict, Optional

import requests

from .technical_indicators import _valid_close, daily_pct_change


def _coerce_finnhub_mark(raw: object) -> Optional[float]:
    """Finite positive quote mark, else None (never ``float(True)→$1``)."""
    if not _valid_close(raw):
        return None
    return float(raw)  # type: ignore[arg-type]


def finnhub_market_cap_dollars(raw: object) -> Optional[float]:
    """Finnhub profile ``marketCapitalization`` is millions USD → full dollars.

    tradermonty #810 unit honesty (Elite Market Cap millions): raw millions must
    not be scored/displayed as dollars — mega-caps otherwise look mid-cap under
    Yahoo-scale thresholds (e.g. recommender ``<$5B``). Bool/gap/NaN/≤0 → None.
    """
    if isinstance(raw, bool) or not isinstance(raw, numbers.Real):
        return None
    millions = float(raw)
    if not math.isfinite(millions) or millions <= 0.0:
        return None
    dollars = millions * 1_000_000.0
    if not math.isfinite(dollars):
        return None
    return dollars


class FinnhubFetcher:
    """Fetch stock data from Finnhub API (stable alternative to Yahoo Finance)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY")
        if not self.api_key:
            raise ValueError("Finnhub API key required. Set FINNHUB_API_KEY env var or pass to constructor.")

        self.base_url = "https://finnhub.io/api/v1"
        self.session = requests.Session()

        # Rate limiting: 30 calls/minute = 1 call per 2 seconds (more conservative to avoid IP blocking)
        self.rate_limit = 30  # calls per minute
        self.call_history = deque(maxlen=self.rate_limit)  # Track last N calls
        self.min_delay = 2.0  # Minimum 2 seconds between calls

    def _wait_for_rate_limit(self):
        """Ensure we respect the 30 calls/minute rate limit (minimum 2 seconds between calls)."""
        now = time.time()

        # Minimum 2 seconds between calls to avoid IP blocking
        if len(self.call_history) > 0:
            last_call = self.call_history[-1]
            time_since_last = now - last_call
            if time_since_last < self.min_delay:
                wait_time = self.min_delay - time_since_last + 0.1
                print(f"   ⏳ Rate limit: waiting {wait_time:.1f}s (min 2s between calls)")
                time.sleep(wait_time)
                now = time.time()  # Update time after sleep

        # If we've made 30 calls already
        if len(self.call_history) >= self.rate_limit:
            # Check the oldest call timestamp
            oldest_call = self.call_history[0]
            elapsed = now - oldest_call

            # If less than 60 seconds have passed, wait
            if elapsed < 60:
                wait_time = 60 - elapsed + 0.1  # Add small buffer
                print(f"   ⏳ Rate limit: waiting {wait_time:.1f}s (30 calls/min)")
                time.sleep(wait_time)

        # Record this call
        self.call_history.append(time.time())

    def get_stock_info(self, symbol: str) -> Dict:
        """
        Get current stock information for a given symbol.
        Returns dict matching StockFetcher format for compatibility.
        """
        try:
            # Get quote data
            self._wait_for_rate_limit()
            quote_url = f"{self.base_url}/quote"
            params = {"symbol": symbol, "token": self.api_key}

            print(f"   🌐  GET {quote_url}?symbol={symbol}&token=***")

            response = self.session.get(quote_url, params=params, timeout=10)
            response.raise_for_status()
            quote = response.json()

            # Get company profile
            self._wait_for_rate_limit()
            profile_url = f"{self.base_url}/stock/profile2"
            profile_params = {"symbol": symbol, "token": self.api_key}

            print(f"   🌐  GET {profile_url}?symbol={symbol}&token=***")

            profile_response = self.session.get(profile_url, params=profile_params, timeout=10)
            profile_response.raise_for_status()
            profile = profile_response.json()

            # tradermonty #700/#655 + xang1234/portfolio AI: refuse bool/gap
            # quote marks so ``float(True)→$1`` cannot invent Finnhub context
            # after MarketAnalyzer / yfinance Daily% already refused invents.
            current_price = _coerce_finnhub_mark(quote.get("c"))
            prev_close = _coerce_finnhub_mark(quote.get("pc"))

            # Map to StockFetcher format
            return {
                "symbol": symbol.upper(),
                "name": profile.get("name", "N/A"),
                "current_price": current_price,
                "previous_close": prev_close,
                "daily_change_pct": daily_pct_change(current_price, prev_close),
                "open": None,
                "day_high": _coerce_finnhub_mark(quote.get("h")),
                "day_low": _coerce_finnhub_mark(quote.get("l")),
                "volume": None,
                # profile2 marketCapitalization is millions — normalize to dollars
                "market_cap": finnhub_market_cap_dollars(
                    profile.get("marketCapitalization")
                ),
                "pe_ratio": None,
                "dividend_yield": None,
                "52_week_high": _coerce_finnhub_mark(profile.get("52WeekHigh")),
                "52_week_low": _coerce_finnhub_mark(profile.get("52WeekLow")),
                "source": "finnhub"
            }

        except requests.exceptions.RequestException as e:
            # tradermonty #778: RequestException str often embeds token= URL.
            raise ValueError(
                f"Failed to fetch Finnhub data for {symbol}: {type(e).__name__}"
            ) from e
        except (KeyError, TypeError) as e:
            raise ValueError(
                f"Failed to parse Finnhub response for {symbol}: {type(e).__name__}"
            ) from e
