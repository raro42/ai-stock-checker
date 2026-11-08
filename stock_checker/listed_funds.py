"""Curated ETFs and metal ETCs for the paper scan.

Not the full fund market. No leveraged or inverse lines.
.DE names use the Xetra session. US names use US cash hours.

``theme`` groups overlapping exposure (tradermonty theme-detector merge
duplicate ETF holdings) so the desk can speak same-theme doubles without
treating SPY and VWCE as one basket.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

# sector "etf" = equity basket. sector "metal" = gold or silver note/fund.
# theme = economic overlap key (not venue).
LISTED_FUND_SEED: dict[str, dict[str, str]] = {
    "SPY": {"sector": "etf", "exchange": "NYSE", "theme": "us_equity"},
    "SXR8.DE": {"sector": "etf", "exchange": "XETRA", "theme": "us_equity"},
    "VWCE.DE": {"sector": "etf", "exchange": "XETRA", "theme": "world_equity"},
    "GLD": {"sector": "metal", "exchange": "NYSE", "theme": "gold"},
    "SLV": {"sector": "metal", "exchange": "NYSE", "theme": "silver"},
    "4GLD.DE": {"sector": "metal", "exchange": "XETRA", "theme": "gold"},
    "XAD6.DE": {"sector": "metal", "exchange": "XETRA", "theme": "silver"},
}

LISTED_FUND_THEME_LABELS: dict[str, str] = {
    "us_equity": "US equity",
    "world_equity": "world equity",
    "gold": "gold",
    "silver": "silver",
}


def is_listed_fund(symbol: str) -> bool:
    """True for a curated ETF or metal ETC (no company earnings)."""
    return str(symbol or "").upper().strip() in LISTED_FUND_SEED


def listed_fund_theme(symbol: str) -> str:
    """Overlap theme key for a curated fund; empty when unknown."""
    meta = LISTED_FUND_SEED.get(str(symbol or "").upper().strip())
    if not isinstance(meta, dict):
        return ""
    return str(meta.get("theme") or "").strip()


def listed_fund_theme_label(theme: str) -> str:
    """Human label for a theme key (falls back to the key)."""
    key = str(theme or "").strip()
    if not key:
        return ""
    return LISTED_FUND_THEME_LABELS.get(key) or key.replace("_", " ")


def group_listed_fund_themes(
    symbols: Iterable[str],
) -> dict[str, list[str]]:
    """Map theme → unique held symbols (order preserved; unknowns skipped)."""
    out: dict[str, list[str]] = defaultdict(list)
    seen: set[str] = set()
    for raw in symbols:
        sym = str(raw or "").upper().strip()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        theme = listed_fund_theme(sym)
        if theme:
            out[theme].append(sym)
    return dict(out)


def listed_fund_theme_overlaps(
    symbols: Iterable[str],
) -> list[tuple[str, list[str]]]:
    """Themes with ≥2 held names, largest group first (display / risk honesty)."""
    groups = group_listed_fund_themes(symbols)
    overlaps = [
        (theme, syms) for theme, syms in groups.items() if len(syms) >= 2
    ]
    overlaps.sort(key=lambda item: (-len(item[1]), item[0]))
    return overlaps
