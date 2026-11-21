#!/usr/bin/env python3

from __future__ import annotations

import math
import numbers
from typing import Dict, List, Optional

import requests

from .secret_redact import safe_exc_text
from .technical_indicators import _finite_signed, _valid_close, coerce_nonneg_int


DEFAULT_TRENDING_LIMIT = 20
DEFAULT_GAINERS_LOSERS_SLICE = 10
DEFAULT_TOP_MOVERS_LISTING_LIMIT = 100
DEFAULT_TOP_MOVERS_SLICE = 15


def _coerce_cmc_limit(value: object, default: int) -> int:
    """Positive CMC strip length, or ``default`` when bool/gap.

    tradermonty #700/#655 + xang1234/portfolio AI: ``int(True)→1`` /
    ``[:True]→1-row`` must not invent a one-coin trending strip after
    BinanceFetcher strip knobs already refused thin candle/trade packaging.
    """
    n = coerce_nonneg_int(value)
    if n is None or n < 1:
        return int(default)
    return n


def _cmc_json_float(raw: object) -> Optional[float]:
    """Parse CMC JSON number (Real or numeric str); never ``float(True)→1``."""
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, numbers.Real):
        n = float(raw)
    elif isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            n = float(text)
        except ValueError:
            return None
    else:
        return None
    if not math.isfinite(n):
        return None
    return n


def _coerce_cmc_mark(raw: object) -> Optional[float]:
    """Finite positive last mark, else None (never ``True→$1``)."""
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, str):
        n = _cmc_json_float(raw)
        return n if n is not None and n > 0.0 else None
    if not _valid_close(raw):
        return None
    return float(raw)  # type: ignore[arg-type]


def _coerce_cmc_signed_pct(raw: object) -> Optional[float]:
    """Finite signed % change (0 / negative ok), else None."""
    if isinstance(raw, str):
        return _cmc_json_float(raw)
    if raw is None or not _finite_signed(raw):
        return None
    return float(raw)  # type: ignore[arg-type]


def _coerce_cmc_volume(raw: object) -> Optional[float]:
    """Non-negative volume/cap (zero prints ok), else None."""
    n = _cmc_json_float(raw)
    if n is None or n < 0.0:
        return None
    return n


def _parse_cmc_coin(item: object, quote: object) -> Optional[Dict]:
    """One CMC coin row; None when price or 24h% is unreadable.

    tradermonty #700/#655 + xang1234/portfolio AI after Binance trade refuse:
    ``quote.get('price', 0)`` / ``percentChange24h`` still accepted ``True``
    (``True > 0`` → fake gainer, ``True→$1``). Isolate bad prints — one junk
    coin must not invent a mover strip.
    """
    if not isinstance(item, dict) or not isinstance(quote, dict):
        return None
    price = _coerce_cmc_mark(quote.get("price"))
    if price is None:
        return None
    change = _coerce_cmc_signed_pct(quote.get("percentChange24h"))
    if change is None:
        return None
    symbol = item.get("symbol", "")
    name = item.get("name", "")
    return {
        "symbol": symbol if isinstance(symbol, str) else "",
        "name": name if isinstance(name, str) else "",
        "price": price,
        "change_24h": change,
        "volume_24h": _coerce_cmc_volume(quote.get("volume24h")),
        "market_cap": _coerce_cmc_volume(quote.get("marketCap")),
        "source": "coinmarketcap",
    }


def _quote_from_item(item: object) -> Optional[dict]:
    if not isinstance(item, dict):
        return None
    quotes = item.get("quotes")
    if not isinstance(quotes, list) or not quotes:
        return None
    first = quotes[0]
    return first if isinstance(first, dict) else None


class CoinMarketCapFetcher:
    """
    Fetch top gainers/losers from CoinMarketCap.

    Uses the public API (no key required for basic data).
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

    def get_trending_gainers_losers(
        self, limit: object = DEFAULT_TRENDING_LIMIT
    ) -> Dict[str, List[Dict]]:
        """
        Get top gainers and losers from CoinMarketCap.

        Returns:
            Dict with 'gainers' and 'losers' lists containing:
            - symbol: Coin symbol
            - name: Coin name
            - price: Current price
            - change_24h: 24h % change
            - volume_24h: 24h volume
            - market_cap: Market cap
        """
        limit = _coerce_cmc_limit(limit, DEFAULT_TRENDING_LIMIT)
        try:
            # CoinMarketCap API endpoint for trending coins
            url = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/spotlight"

            print(f"   🌐 GET {url}")

            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            gainers = []
            losers = []

            # Extract gainers
            if 'data' in data and 'trendingList' in data['data']:
                for item in data['data']['trendingList'][:limit]:
                    if not isinstance(item, dict) or 'priceChange' not in item:
                        continue
                    quote = _quote_from_item(item)
                    if quote is None:
                        continue
                    coin_data = _parse_cmc_coin(item, quote)
                    if coin_data is None:
                        continue

                    if coin_data['change_24h'] > 0:
                        gainers.append(coin_data)
                    else:
                        losers.append(coin_data)

            # Sort by absolute change
            gainers.sort(key=lambda x: x['change_24h'], reverse=True)
            losers.sort(key=lambda x: x['change_24h'])

            slice_n = DEFAULT_GAINERS_LOSERS_SLICE
            return {
                'gainers': gainers[:slice_n],
                'losers': losers[:slice_n],
                'timestamp': data.get('status', {}).get('timestamp', '')
            }

        except Exception as e:
            print(f"[ERROR] Failed to fetch CoinMarketCap data: {safe_exc_text(e)}")
            return {'gainers': [], 'losers': [], 'timestamp': ''}

    def get_top_movers(
        self, *, listing_limit: object = DEFAULT_TOP_MOVERS_LISTING_LIMIT
    ) -> Dict[str, List[Dict]]:
        """
        Alternative method using CoinMarketCap's listings API.
        """
        listing_limit = _coerce_cmc_limit(
            listing_limit, DEFAULT_TOP_MOVERS_LISTING_LIMIT
        )
        try:
            url = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing"
            params = {
                'start': 1,
                'limit': listing_limit,
                'sortBy': 'percent_change_24h',
                'sortType': 'desc',
                'convert': 'USD'
            }

            full_url = f"{url}?start={params['start']}&limit={params['limit']}&sortBy={params['sortBy']}"
            print(f"   🌐 GET {full_url}")

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            gainers = []
            losers = []

            if 'data' in data and 'cryptoCurrencyList' in data['data']:
                for item in data['data']['cryptoCurrencyList']:
                    quote = _quote_from_item(item)
                    if quote is None:
                        continue
                    coin_data = _parse_cmc_coin(item, quote)
                    if coin_data is None:
                        continue

                    if coin_data['change_24h'] > 5.0:  # Significant gainers
                        gainers.append(coin_data)
                    elif coin_data['change_24h'] < -5.0:  # Significant losers
                        losers.append(coin_data)

            slice_n = DEFAULT_TOP_MOVERS_SLICE
            return {
                'gainers': gainers[:slice_n],
                'losers': losers[:slice_n]
            }

        except Exception as e:
            print(f"[ERROR] Failed to fetch CoinMarketCap top movers: {safe_exc_text(e)}")
            return {'gainers': [], 'losers': []}
