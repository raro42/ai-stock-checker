"""
Yahoo Finance movers → curated universe discovery (not auto-buy).

Pulls day gainers / losers via yfinance screen presets and proposes symbols
for StockUniverseManager. Trading still goes through regime / RS / breadth /
fees gates.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Sequence

from stock_checker.symbol_filters import is_tradeable_symbol

# Keep discovery calm — we are not RyanJHamby's 3800-name firehose.
DEFAULT_MOVER_COUNT = 25
DEFAULT_SCREENS: tuple[str, ...] = ("day_gainers", "day_losers", "most_actives")


def _quotes_from_screen_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        quotes = payload.get("quotes")
        if isinstance(quotes, list):
            return [q for q in quotes if isinstance(q, dict)]
    return []


def fetch_yahoo_screen_symbols(
    screen: str,
    *,
    count: int = DEFAULT_MOVER_COUNT,
) -> List[str]:
    """
    Return tradeable equity symbols from a yfinance predefined screen.

    Network call — wrap in try/except at call sites. Offline tests should mock.
    """
    import yfinance as yf

    payload = yf.screen(screen, count=max(1, min(100, int(count))))
    out: list[str] = []
    seen: set[str] = set()
    for q in _quotes_from_screen_payload(payload):
        sym = str(q.get("symbol") or "").strip().upper()
        if not sym or sym in seen:
            continue
        if not is_tradeable_symbol(sym):
            continue
        # Skip obvious non-common noise (warrants / units) if any slip through.
        if any(ch in sym for ch in ("=", "^", "/")):
            continue
        seen.add(sym)
        out.append(sym)
    return out


def discover_yahoo_mover_symbols(
    *,
    screens: Sequence[str] = DEFAULT_SCREENS,
    per_screen: int = DEFAULT_MOVER_COUNT,
) -> List[str]:
    """Union of symbols across screens, stable order, de-duplicated."""
    out: list[str] = []
    seen: set[str] = set()
    for name in screens:
        try:
            batch = fetch_yahoo_screen_symbols(name, count=per_screen)
        except Exception:
            continue
        for sym in batch:
            if sym in seen:
                continue
            if not is_tradeable_symbol(sym):
                continue
            seen.add(sym)
            out.append(sym)
    return out


def sector_hint_from_quote(quote: dict[str, Any] | None) -> str:
    if not isinstance(quote, dict):
        return "unknown"
    sector = quote.get("sector")
    if isinstance(sector, str) and sector.strip():
        return sector.strip().lower().replace(" ", "_")
    return "unknown"


def exchange_hint_from_quote(quote: dict[str, Any] | None) -> str:
    if not isinstance(quote, dict):
        return "unknown"
    for key in ("fullExchangeName", "exchange"):
        val = quote.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().upper()
    return "unknown"
