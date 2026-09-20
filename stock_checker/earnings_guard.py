#!/usr/bin/env python3
"""Earnings calendar blackout — avoid new entries near earnings."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional, Tuple

import pytz

from .market_hours import US_TZ

# Live entry blackout window (stocks only; crypto exempt).
DEFAULT_DAYS_BEFORE = 2.0
DEFAULT_DAYS_AFTER = 1.0

# tradermonty #426: blackout uses the US session date, not UTC.
# US/Eastern is the same zone as America/New_York (see market_hours.US_TZ).
EARNINGS_CLOCK = "America/New_York"

# Probe statuses — tradermonty empty-window honesty (display / fail-open why).
STATUS_CRYPTO = "crypto"
STATUS_DATED = "dated"
STATUS_EMPTY_WINDOW = "empty_window"
STATUS_MALFORMED = "malformed"
STATUS_MISSING = "missing"
STATUS_ERROR = "error"

# xang1234 e433265: index-as-date parses as 1970-01-01. That is not an earnings date.
EARNINGS_MIN_YEAR = 2000


def earnings_session_now(now: Optional[datetime] = None) -> datetime:
    """US session clock for the earnings window.

    Naive ``now`` is UTC (legacy ``utcnow``). Aware stamps convert to
    US/Eastern. After the US close, UTC is often already the next date.
    """
    tz = pytz.timezone(US_TZ)
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return pytz.utc.localize(now).astimezone(tz)
    return now.astimezone(tz)


def _is_nonscalar_cell(raw: Any) -> bool:
    """True for list-like or mapping cells. Those are not one earnings date.

    xang1234 21194ec: a non-scalar cell must be skipped, not parsed as a stamp.
    """
    return isinstance(raw, (list, tuple, dict, set))


def _event_session_date(raw: Any) -> Optional[date]:
    """Calendar date of a Yahoo earnings stamp on the US session clock.

    Naive stamps keep their calendar date (Yahoo date-only). Aware stamps
    convert to US/Eastern before the date is taken. A non-scalar cell, or a
    stamp whose conversion raises, is not a date (xang1234 21194ec).
    """
    if raw is None or _is_nonscalar_cell(raw):
        return None
    if hasattr(raw, "to_pydatetime"):
        try:
            raw = raw.to_pydatetime()
        except (TypeError, ValueError, OverflowError):
            return None
    if raw is None or _is_nonscalar_cell(raw):
        return None
    if isinstance(raw, datetime):
        if raw.tzinfo is not None:
            return raw.astimezone(pytz.timezone(US_TZ)).date()
        return raw.date()
    if isinstance(raw, date):
        return raw
    return None


def _usable_session_date(raw: Any) -> Optional[date]:
    """Session date, or None when the stamp is missing, junk, or epoch-stale."""
    event_day = _event_session_date(raw)
    if event_day is None or event_day.year < EARNINGS_MIN_YEAR:
        return None
    return event_day


def earnings_day_delta(event: Any, now: Optional[datetime] = None) -> Optional[float]:
    """Whole US-session days until ``event`` (negative if already reported)."""
    event_day = _usable_session_date(event)
    if event_day is None:
        return None
    clock = earnings_session_now(now)
    return float((event_day - clock.date()).days)


def _days_from_earnings_dates(ed: Any, now: datetime) -> Optional[float]:
    future: list[float] = []
    past: list[float] = []
    for ts in ed.index:
        delta = earnings_day_delta(ts, now)
        if delta is None:
            continue
        if delta >= 0:
            future.append(delta)
        else:
            past.append(delta)
    if future:
        return min(future)
    if past:
        return max(past)  # most recent past (least negative)
    return None


def _days_from_calendar(cal: Any, now: datetime) -> tuple[Optional[float], bool]:
    """Return ``(days, unusable)``.

    ``unusable`` is true when ``Earnings Date`` is present but not a real
    date (missing cell, epoch, junk). A missing key is not unusable — that
    is an empty window, not a bad payload (xang1234 e433265).

    A list cell is several values, not one stamp. Skip nested lists and
    dicts. The first later scalar date still counts (xang1234 21194ec).
    """
    if not isinstance(cal, dict) or "Earnings Date" not in cal:
        return None, False
    raw = cal.get("Earnings Date")
    if raw is None:
        return None, True
    cells = raw if isinstance(raw, (list, tuple)) else (raw,)
    for item in cells:
        if _is_nonscalar_cell(item):
            continue
        days = earnings_day_delta(item, now)
        if days is not None:
            return days, False
    return None, True


def probe_earnings_calendar(
    symbol: str, *, now: Optional[datetime] = None
) -> Tuple[Optional[float], str]:
    """Return (days_to_next, status).

    ``empty_window`` means Yahoo exposed ``earnings_dates`` but it was empty
    and calendar also had no date — suspicious empty window (tradermonty #379
    pattern). ``malformed`` means a nonempty payload or an ``Earnings Date``
    cell yielded no usable date (epoch / junk — xang1234 e433265). That is
    not a successful “no earnings” lookup. Fail-open still allows; status is
    for honesty / soft-allow why.
    """
    if not symbol or "-USD" in symbol.upper() or symbol.upper().endswith("USDT"):
        return None, STATUS_CRYPTO

    try:
        import yfinance as yf
    except ImportError:
        return None, STATUS_MISSING

    try:
        ticker = yf.Ticker(symbol)
        clock = earnings_session_now(now)
        empty_dates = False
        malformed = False

        ed = getattr(ticker, "earnings_dates", None)
        if ed is not None and hasattr(ed, "empty"):
            if ed.empty:
                empty_dates = True
            else:
                days = _days_from_earnings_dates(ed, clock)
                if days is not None:
                    return days, STATUS_DATED
                malformed = True

        days, cal_bad = _days_from_calendar(
            getattr(ticker, "calendar", None), clock
        )
        if days is not None:
            return days, STATUS_DATED
        if cal_bad:
            malformed = True

        if malformed:
            return None, STATUS_MALFORMED
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
    now: Optional[datetime] = None,
) -> Tuple[bool, str]:
    """
    True if we should block NEW entries near earnings.

    Window: [-days_after, +days_before] in whole US-session days
    (America/New_York date, not UTC). Positive days_to means earnings ahead.

    Missing Yahoo calendar fail-opens: allow entry.
    Empty Yahoo ``earnings_dates`` with no calendar date also fail-opens, but
    returns an explicit why so Ops soft-allow memory can show the suspect case.
    A nonempty or present-but-junk calendar fail-opens the same way
    (``malformed``) — it is not proof that earnings are far away.
    """
    days, status = probe_earnings_calendar(symbol, now=now)
    if days is None:
        if status == STATUS_EMPTY_WINDOW:
            return False, "empty Yahoo earnings window · fail-open"
        if status == STATUS_MALFORMED:
            return False, "malformed Yahoo earnings · fail-open"
        return False, ""

    # Upcoming earnings within days_before
    if 0 <= days <= days_before:
        return True, f"earnings in {days:.1f}d (blackout {days_before:.0f}d before)"

    # Just reported within days_after
    if -days_after <= days < 0:
        return True, f"earnings {-days:.1f}d ago (blackout {days_after:.0f}d after)"

    return False, ""
