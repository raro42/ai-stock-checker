#!/usr/bin/env python3
"""Earnings calendar blackout — avoid new entries near earnings."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Tuple

# Live entry blackout window (stocks only; crypto exempt).
DEFAULT_DAYS_BEFORE = 2.0
DEFAULT_DAYS_AFTER = 1.0

# Probe statuses — tradermonty empty-window honesty (display / fail-open why).
STATUS_CRYPTO = "crypto"
STATUS_DATED = "dated"
STATUS_EMPTY_WINDOW = "empty_window"
STATUS_MISSING = "missing"
STATUS_ERROR = "error"


def _as_naive(dt: Any) -> Optional[datetime]:
    if dt is None:
        return None
    if hasattr(dt, "to_pydatetime"):
        dt = dt.to_pydatetime()
    if not isinstance(dt, datetime):
        return None
    if getattr(dt, "tzinfo", None) is not None:
        return dt.replace(tzinfo=None)
    return dt


def _days_from_earnings_dates(ed: Any, now: datetime) -> Optional[float]:
    future: list[float] = []
    past: list[float] = []
    for ts in ed.index:
        dt = _as_naive(ts)
        if dt is None:
            continue
        delta = (dt - now).total_seconds() / 86400.0
        if delta >= 0:
            future.append(delta)
        else:
            past.append(delta)
    if future:
        return min(future)
    if past:
        return max(past)  # most recent past (least negative)
    return None


def _days_from_calendar(cal: Any, now: datetime) -> Optional[float]:
    if not isinstance(cal, dict):
        return None
    raw = cal.get("Earnings Date")
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)) and raw:
        raw = raw[0]
    dt = _as_naive(raw)
    if dt is None:
        return None
    return (dt - now).total_seconds() / 86400.0


def probe_earnings_calendar(symbol: str) -> Tuple[Optional[float], str]:
    """Return (days_to_next, status).

    ``empty_window`` means Yahoo exposed ``earnings_dates`` but it was empty
    and calendar also had no date — suspicious empty window (tradermonty #379
    pattern). Fail-open still allows; status is for honesty / soft-allow why.
    """
    if not symbol or "-USD" in symbol.upper() or symbol.upper().endswith("USDT"):
        return None, STATUS_CRYPTO

    try:
        import yfinance as yf
    except ImportError:
        return None, STATUS_MISSING

    try:
        ticker = yf.Ticker(symbol)
        now = datetime.utcnow()
        empty_dates = False

        ed = getattr(ticker, "earnings_dates", None)
        if ed is not None and hasattr(ed, "empty"):
            if ed.empty:
                empty_dates = True
            else:
                days = _days_from_earnings_dates(ed, now)
                if days is not None:
                    return days, STATUS_DATED

        days = _days_from_calendar(getattr(ticker, "calendar", None), now)
        if days is not None:
            return days, STATUS_DATED

        if empty_dates:
            return None, STATUS_EMPTY_WINDOW
        return None, STATUS_MISSING
    except Exception:
        return None, STATUS_ERROR


def days_to_next_earnings(symbol: str) -> Optional[float]:
    """
    Return days until next earnings (can be negative if just reported), or None.
    Crypto / unknown → None (no blackout).
    """
    days, _ = probe_earnings_calendar(symbol)
    return days


def is_in_earnings_blackout(
    symbol: str,
    *,
    days_before: float = DEFAULT_DAYS_BEFORE,
    days_after: float = DEFAULT_DAYS_AFTER,
) -> Tuple[bool, str]:
    """
    True if we should block NEW entries near earnings.

    Window: [-days_after, +days_before] around the event in day units
    where positive days_to means earnings in the future.

    Missing Yahoo calendar fail-opens: allow entry.
    Empty Yahoo ``earnings_dates`` with no calendar date also fail-opens, but
    returns an explicit why so Ops soft-allow memory can show the suspect case.
    """
    days, status = probe_earnings_calendar(symbol)
    if days is None:
        if status == STATUS_EMPTY_WINDOW:
            return False, "empty Yahoo earnings window · fail-open"
        return False, ""

    # Upcoming earnings within days_before
    if 0 <= days <= days_before:
        return True, f"earnings in {days:.1f}d (blackout {days_before:.0f}d before)"

    # Just reported within days_after
    if -days_after <= days < 0:
        return True, f"earnings {-days:.1f}d ago (blackout {days_after:.0f}d after)"

    return False, ""
