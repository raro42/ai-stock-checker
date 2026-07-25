#!/usr/bin/env python3
"""Filters for tradeable symbols — exclude noise that burns fees."""

from __future__ import annotations

import re
from typing import Iterable, List, Set

# Stablecoins and pegged assets (no directional edge for our strategy)
STABLECOIN_BASES: Set[str] = {
    "USDT",
    "USDC",
    "BUSD",
    "DAI",
    "TUSD",
    "FDUSD",
    "USDP",
    "USDD",
    "GUSD",
    "FRAX",
    "EURC",
    "EUR",
    "USD1",
    "PYUSD",
    "USDE",
    "USD",
}

# High-churn / leveraged / synthetic noise often returned by “top movers”
EXCLUDED_BASES: Set[str] = {
    "COMP",  # often confuses with compound vs other tickers in mixed universes
}

LEVERAGED_TOKEN_RE = re.compile(
    r"(UP|DOWN|BULL|BEAR|3L|3S|2L|2S)$",
    re.IGNORECASE,
)


def _base_symbol(symbol: str) -> str:
    """Normalize to base ticker: BTC-USD -> BTC, BTCUSDT -> BTC, AAPL -> AAPL."""
    s = symbol.upper().strip()
    # Exact stable / fiat tickers (do not strip to empty)
    if s in STABLECOIN_BASES:
        return s
    for suffix in ("-USD", "-USDT", "USDT", "USD", "/USDT", "/USD"):
        if s.endswith(suffix) and len(s) > len(suffix):
            return s[: -len(suffix)]
    return s


def is_stablecoin(symbol: str) -> bool:
    """Return True if symbol is a stablecoin or pegged USD/EUR asset."""
    s = symbol.upper().strip()
    if s in STABLECOIN_BASES:
        return True
    base = _base_symbol(s)
    return base in STABLECOIN_BASES


def is_leveraged_token(symbol: str) -> bool:
    """Return True for leveraged / inverse crypto tokens."""
    base = _base_symbol(symbol)
    return bool(LEVERAGED_TOKEN_RE.search(base))


def is_tradeable_symbol(symbol: str, *, allow_crypto: bool = True) -> bool:
    """
    Return True if the symbol is allowed in scans and paper trades.

    Stocks (no -USD / USDT suffix) pass. Crypto must not be stable/leveraged/excluded.
    """
    if not symbol or not str(symbol).strip():
        return False

    s = symbol.upper().strip()
    base = _base_symbol(s)

    if base in EXCLUDED_BASES:
        return False
    if is_stablecoin(s):
        return False
    if is_leveraged_token(s):
        return False

    is_crypto = s.endswith(("-USD", "-USDT", "USDT")) or "/" in s
    if is_crypto and not allow_crypto:
        return False

    return True


def filter_tradeable_symbols(
    symbols: Iterable[str],
    *,
    allow_crypto: bool = True,
) -> List[str]:
    """Filter an iterable of symbols to tradeable ones (order preserved)."""
    seen: Set[str] = set()
    out: List[str] = []
    for raw in symbols:
        if not is_tradeable_symbol(raw, allow_crypto=allow_crypto):
            continue
        key = raw.upper().strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(raw)
    return out


def filter_ranked_opportunities(
    opportunities: List[dict],
    *,
    symbol_key: str = "symbol",
    allow_crypto: bool = True,
) -> List[dict]:
    """Drop non-tradeable rows from ranked opportunity dicts."""
    filtered: List[dict] = []
    for row in opportunities:
        sym = row.get(symbol_key, "")
        if is_tradeable_symbol(str(sym), allow_crypto=allow_crypto):
            filtered.append(row)
    return filtered
