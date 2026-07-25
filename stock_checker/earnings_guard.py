#!/usr/bin/env python3
"""Earnings calendar blackout — avoid new entries near earnings."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Tuple


def days_to_next_earnings(symbol: str) -> Optional[float]:
    """
    Return days until next earnings (can be negative if just reported), or None.
    Crypto / unknown → None (no blackout).
    """
    if not symbol or "-USD" in symbol.upper() or symbol.upper().endswith("USDT"):
        return None

    try:
        import yfinance as yf
    except ImportError:
        return None

    try:
        ticker = yf.Ticker(symbol)
        # Prefer earnings_dates if available
        ed = getattr(ticker, "earnings_dates", None)
        if ed is not None and hasattr(ed, "empty") and not ed.empty:
            now = datetime.utcnow()
            # index is usually DatetimeIndex
            future = []
            past = []
            for ts in ed.index:
                dt = ts.to_pydatetime().replace(tzinfo=None) if hasattr(ts, "to_pydatetime") else ts
                if getattr(dt, "tzinfo", None) is not None:
                    dt = dt.replace(tzinfo=None)
                delta = (dt - now).total_seconds() / 86400.0
                if delta >= 0:
                    future.append(delta)
                else:
                    past.append(delta)
            if future:
                return min(future)
            if past:
                return max(past)  # most recent past (least negative)

        cal = getattr(ticker, "calendar", None)
        if isinstance(cal, dict):
            raw = cal.get("Earnings Date") or cal.get("Earnings Date", None)
            if raw is not None:
                # can be list/Timestamp
                if isinstance(raw, (list, tuple)) and raw:
                    raw = raw[0]
                if hasattr(raw, "to_pydatetime"):
                    raw = raw.to_pydatetime()
                if isinstance(raw, datetime):
                    dt = raw.replace(tzinfo=None)
                    return (dt - datetime.utcnow()).total_seconds() / 86400.0
    except Exception:
        return None

    return None


def is_in_earnings_blackout(
    symbol: str,
    *,
    days_before: float = 2.0,
    days_after: float = 1.0,
) -> Tuple[bool, str]:
    """
    True if we should block NEW entries near earnings.

    Window: [-days_after, +days_before] around the event in day units
    where positive days_to means earnings in the future.
    """
    days = days_to_next_earnings(symbol)
    if days is None:
        return False, ""

    # Upcoming earnings within days_before
    if 0 <= days <= days_before:
        return True, f"earnings in {days:.1f}d (blackout {days_before:.0f}d before)"

    # Just reported within days_after
    if -days_after <= days < 0:
        return True, f"earnings {-days:.1f}d ago (blackout {days_after:.0f}d after)"

    return False, ""
