"""Equity session helpers — US cash hours vs Xetra (German .DE).

Crypto is 24/7 and is not gated here.
"""

from __future__ import annotations

from datetime import datetime, time as dt_time
from typing import Optional

import pytz

# Xetra continuous cash session (approx; ignores short auctions / holidays).
XETRA_OPEN = dt_time(9, 0)
XETRA_CLOSE = dt_time(17, 30)
XETRA_TZ = "Europe/Berlin"

US_OPEN = dt_time(9, 30)
US_CLOSE = dt_time(16, 0)
US_TZ = "US/Eastern"


def is_crypto_symbol(symbol: str) -> bool:
    s = str(symbol or "").upper().strip()
    return s.endswith(("-USD", "-USDT", "USDT")) or "/" in s


def is_german_equity(symbol: str) -> bool:
    """Yahoo Xetra / Frankfurt common stocks use the .DE suffix."""
    return str(symbol or "").upper().strip().endswith(".DE")


def _to_local(tz_name: str, now: Optional[datetime] = None) -> datetime:
    tz = pytz.timezone(tz_name)
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return tz.localize(now)
    return now.astimezone(tz)


def _session_closed(
    *,
    tz_name: str,
    open_t: dt_time,
    close_t: dt_time,
    now: Optional[datetime] = None,
) -> bool:
    local = _to_local(tz_name, now)
    if local.weekday() >= 5:
        return True
    t = local.time()
    return t < open_t or t >= close_t


def is_us_cash_session_closed(*, now: Optional[datetime] = None) -> bool:
    return _session_closed(tz_name=US_TZ, open_t=US_OPEN, close_t=US_CLOSE, now=now)


def is_xetra_session_closed(*, now: Optional[datetime] = None) -> bool:
    return _session_closed(
        tz_name=XETRA_TZ, open_t=XETRA_OPEN, close_t=XETRA_CLOSE, now=now
    )


def is_equity_session_closed(symbol: str, *, now: Optional[datetime] = None) -> bool:
    """
    True when this equity should not open a new paper buy/sell for hours.

    - Crypto → never closed here (caller skips)
    - *.DE → Xetra 09:00–17:30 Europe/Berlin
    - else → US 09:30–16:00 America/New_York
    """
    if is_crypto_symbol(symbol):
        return False
    if is_german_equity(symbol):
        return is_xetra_session_closed(now=now)
    return is_us_cash_session_closed(now=now)
