"""Curated ETFs and metal ETCs for the paper scan.

Not the full fund market. No leveraged or inverse lines.
.DE names use the Xetra session. US names use US cash hours.
"""

from __future__ import annotations

# sector "etf" = equity basket. sector "metal" = gold or silver note/fund.
LISTED_FUND_SEED: dict[str, dict[str, str]] = {
    "SPY": {"sector": "etf", "exchange": "NYSE"},
    "SXR8.DE": {"sector": "etf", "exchange": "XETRA"},
    "VWCE.DE": {"sector": "etf", "exchange": "XETRA"},
    "GLD": {"sector": "metal", "exchange": "NYSE"},
    "SLV": {"sector": "metal", "exchange": "NYSE"},
    "4GLD.DE": {"sector": "metal", "exchange": "XETRA"},
    "XAD6.DE": {"sector": "metal", "exchange": "XETRA"},
}


def is_listed_fund(symbol: str) -> bool:
    """True for a curated ETF or metal ETC (no company earnings)."""
    return str(symbol or "").upper().strip() in LISTED_FUND_SEED
