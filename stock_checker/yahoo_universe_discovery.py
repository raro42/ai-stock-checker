"""
Yahoo Finance movers → curated universe discovery (not auto-buy).

Pulls day gainers / losers via yfinance screen presets and proposes symbols
for StockUniverseManager. Trading still goes through regime / RS / breadth /
fees gates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Sequence

from stock_checker.symbol_filters import is_tradeable_symbol

# Keep discovery calm — we are not RyanJHamby's 3800-name firehose.
DEFAULT_MOVER_COUNT = 25
# Re-pull Yahoo movers when last discovery is older than this (desk shows age).
DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS = 24
# xang1234 dfb6a86: do not refetch an empty/dead slice every scan cycle.
# Failed Yahoo still retries sooner than the 24h success throttle, but not
# on every 15m scan — calm the thrash when movers stay blocked.
DEFAULT_YAHOO_FAIL_BACKOFF_HOURS = 1
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


def screens_bundle_failed(ok: int, failed: int) -> bool:
    """True when the mover bundle is blocked or majority-failed.

    xang1234: a 403 / empty Finviz snapshot must not raise, and a mostly
    dead refresh is a failed fetch — do not stamp cache fresh or mix in
    leftover quotes from the one screen that still answered.
    """
    ok_n = max(0, int(ok))
    fail_n = max(0, int(failed))
    if ok_n <= 0:
        return True
    return fail_n > ok_n


def screens_bundle_partial(ok: int, failed: int) -> bool:
    """True when some screens answered and some failed (not majority-dead).

    xang1234 7e0df1e: skip prune baselines for partly failed fetches — leftover
    quotes from the live screens are still addable, but missing names are not
    a complete drop list.
    """
    if screens_bundle_failed(ok, failed):
        return False
    return max(0, int(failed)) > 0


def yahoo_cache_freshness(
    age_sec: float | None,
    *,
    max_age_hours: int = DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS,
    parsed: bool = True,
) -> str:
    """Bound a reused seed by last-good discovery age (xang1234 317b6bb).

    ``never`` = no stamp. ``unknown`` = stamp present but unparsed.
    Otherwise fresh < max_age, aging < 2×, else stale.
    """
    if not parsed:
        return "unknown"
    if age_sec is None:
        return "never"
    limit = max(1, int(max_age_hours)) * 3600.0
    age = max(0.0, float(age_sec))
    if age < limit:
        return "fresh"
    if age < 2 * limit:
        return "aging"
    return "stale"


def _naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def yahoo_fail_retry_remaining_sec(
    meta: Any,
    *,
    now: datetime | None = None,
    fail_backoff_hours: int = DEFAULT_YAHOO_FAIL_BACKOFF_HOURS,
) -> int | None:
    """Seconds left on the fail backoff, or ``0`` when retry is due.

    ``None`` when status is not failed or the fail stamp is missing/unparsed
    (caller should treat missing stamp as retry-due immediately).
    """
    if not isinstance(meta, dict):
        return None
    status = str(meta.get("last_yahoo_discovery_status") or "").strip().lower()
    if status != "failed":
        return None
    fail_raw = str(meta.get("last_yahoo_discovery_fail") or "").strip()
    if not fail_raw:
        return None
    try:
        then = datetime.fromisoformat(fail_raw.replace("Z", "+00:00"))
        then = _naive_utc(then)
        clock = _naive_utc(now) if now is not None else datetime.now()
        age_sec = max(0.0, (clock - then).total_seconds())
        limit = max(0, int(fail_backoff_hours)) * 3600.0
        return max(0, int(limit - age_sec))
    except (TypeError, ValueError):
        return None


def yahoo_discovery_due_from_meta(
    meta: Any,
    *,
    now: datetime | None = None,
    max_age_hours: int = DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS,
    fail_backoff_hours: int = DEFAULT_YAHOO_FAIL_BACKOFF_HOURS,
) -> bool:
    """True when movers have never succeeded or last success is older than max_age.

    xang1234: a failed fetch does not inherit the success-age throttle.
    xang1234 dfb6a86: after a failed fetch, wait ``fail_backoff_hours`` before
    retrying (missing fail stamp → retry immediately).
    """
    if not isinstance(meta, dict):
        return True
    status = str(meta.get("last_yahoo_discovery_status") or "").strip().lower()
    if status == "failed":
        remain = yahoo_fail_retry_remaining_sec(
            meta, now=now, fail_backoff_hours=fail_backoff_hours
        )
        # No / bad fail stamp → try again (cannot apply backoff).
        if remain is None:
            return True
        return remain <= 0
    last = str(meta.get("last_yahoo_discovery") or "").strip()
    if not last:
        return True
    try:
        then = datetime.fromisoformat(last.replace("Z", "+00:00"))
        then = _naive_utc(then)
        clock = _naive_utc(now) if now is not None else datetime.now()
        age_h = (clock - then).total_seconds() / 3600.0
        return age_h >= float(max(1, int(max_age_hours)))
    except (TypeError, ValueError):
        return True


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
    try:
        payload = yf.screen(screen, count=want)
    except Exception as e:
        # xang1234 008f0ca: HTTP 403 / soft block → failed screen, not a raise
        # out of universe refresh.
        raise YahooScreenEmptyError(screen) from e
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
