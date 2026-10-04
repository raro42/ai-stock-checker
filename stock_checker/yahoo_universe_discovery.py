"""
Yahoo Finance movers → curated universe discovery (not auto-buy).

Pulls day gainers / losers via yfinance screen presets and proposes symbols
for StockUniverseManager. Trading still goes through regime / RS / breadth /
fees gates.
"""

from __future__ import annotations

from typing import Any, List, Sequence

from stock_checker.symbol_filters import is_tradeable_symbol

# Keep discovery calm — we are not RyanJHamby's 3800-name firehose.
DEFAULT_MOVER_COUNT = 25
# Re-pull Yahoo movers when last discovery is older than this (desk shows age).
DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS = 24
DEFAULT_SCREENS: tuple[str, ...] = ("day_gainers", "day_losers", "most_actives")
# xang1234: a mostly empty snapshot is a failed fetch, not a quiet day.
EMPTY_SCREEN_FRACTION = 0.2


class YahooScreenEmptyError(Exception):
    """Yahoo screen returned nothing usable (block / empty payload)."""


def _quotes_from_screen_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        quotes = payload.get("quotes")
        if isinstance(quotes, list):
            return [q for q in quotes if isinstance(q, dict)]
    return []


def screen_payload_failed(payload: Any, *, expected: int) -> bool:
    """True when the screen looks blocked or mostly empty (do not stamp cache)."""
    quotes = _quotes_from_screen_payload(payload)
    if not quotes:
        return True
    want = max(1, int(expected))
    floor = max(1, int(want * EMPTY_SCREEN_FRACTION))
    return len(quotes) < floor


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

    want = max(1, min(100, int(count)))
    payload = yf.screen(screen, count=want)
    if screen_payload_failed(payload, expected=want):
        raise YahooScreenEmptyError(screen)
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


def discover_yahoo_mover_report(
    *,
    screens: Sequence[str] = DEFAULT_SCREENS,
    per_screen: int = DEFAULT_MOVER_COUNT,
) -> tuple[List[str], int, int]:
    """Symbols plus how many screens succeeded vs failed (empty/blocked)."""
    out: list[str] = []
    seen: set[str] = set()
    ok = 0
    failed = 0
    for name in screens:
        try:
            batch = fetch_yahoo_screen_symbols(name, count=per_screen)
            ok += 1
        except Exception:
            failed += 1
            continue
        for sym in batch:
            if sym in seen:
                continue
            if not is_tradeable_symbol(sym):
                continue
            seen.add(sym)
            out.append(sym)
    return out, ok, failed


def discover_yahoo_mover_symbols(
    *,
    screens: Sequence[str] = DEFAULT_SCREENS,
    per_screen: int = DEFAULT_MOVER_COUNT,
) -> List[str]:
    """Union of symbols across screens, stable order, de-duplicated."""
    symbols, _ok, _failed = discover_yahoo_mover_report(
        screens=screens, per_screen=per_screen
    )
    return symbols


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
