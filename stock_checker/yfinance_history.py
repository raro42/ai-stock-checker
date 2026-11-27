"""Bounded yfinance ``Ticker`` joins — hung Yahoo ≠ quiet success.

tradermonty #904/#905 + xang1234/portfolio AI: Yahoo ``yf.screen`` already
joins with a 20s ceiling; bare ``Ticker.history`` / ``.info`` / earnings /
``fast_info`` could stall forever and look like a calm hang. Timeout raises
``TimeoutError`` (callers map to fail-open empty / ValueError) — never invent
a finished empty frame or quote from a still-running worker.
"""

from __future__ import annotations

import threading
from typing import Any, Callable

from stock_checker.technical_indicators import coerce_nonneg_int

DEFAULT_YF_HISTORY_TIMEOUT_SEC = 20
DEFAULT_YF_INFO_TIMEOUT_SEC = DEFAULT_YF_HISTORY_TIMEOUT_SEC
DEFAULT_YF_EARNINGS_TIMEOUT_SEC = DEFAULT_YF_HISTORY_TIMEOUT_SEC
DEFAULT_YF_FAST_INFO_TIMEOUT_SEC = DEFAULT_YF_HISTORY_TIMEOUT_SEC


def coerce_yf_history_timeout_sec(
    value: object, default: int = DEFAULT_YF_HISTORY_TIMEOUT_SEC
) -> int:
    """Join ceiling seconds, or ``default`` when bool/gap/NaN.

    ``int(True)→1`` must not invent a 1s history timeout (Yahoo screen peer).
    """
    n = coerce_nonneg_int(value)
    if n is None or n < 1:
        return int(default)
    return n


def coerce_yf_info_timeout_sec(
    value: object, default: int = DEFAULT_YF_INFO_TIMEOUT_SEC
) -> int:
    """Join ceiling for ``Ticker.info`` — same bool/gap refuse as history."""
    return coerce_yf_history_timeout_sec(value, default=default)


def coerce_yf_earnings_timeout_sec(
    value: object, default: int = DEFAULT_YF_EARNINGS_TIMEOUT_SEC
) -> int:
    """Join ceiling for earnings_dates/calendar — same bool/gap refuse."""
    return coerce_yf_history_timeout_sec(value, default=default)


def coerce_yf_fast_info_timeout_sec(
    value: object, default: int = DEFAULT_YF_FAST_INFO_TIMEOUT_SEC
) -> int:
    """Join ceiling for ``Ticker.fast_info`` — same bool/gap refuse."""
    return coerce_yf_history_timeout_sec(value, default=default)


def _join_yf_call(
    *,
    label: str,
    symbol: str,
    timeout_sec: object,
    default_timeout: int,
    call: Callable[[], Any],
) -> Any:
    """Run ``call`` on a daemon thread; raise TimeoutError if still alive."""
    limit = coerce_yf_history_timeout_sec(
        default_timeout if timeout_sec is None else timeout_sec,
        default=default_timeout,
    )
    sym = str(symbol or "").strip() or "UNKNOWN"
    box: dict[str, Any] = {}

    def _worker() -> None:
        try:
            box["value"] = call()
        except Exception as e:
            box["error"] = e

    worker = threading.Thread(
        target=_worker, name=f"yf-{label}-{sym}", daemon=True
    )
    worker.start()
    worker.join(timeout=float(limit))
    if worker.is_alive():
        raise TimeoutError(f"yfinance {label} {sym} timed out after {limit}s")
    if "error" in box:
        raise box["error"]
    return box.get("value")


def fetch_yfinance_history(
    symbol: str,
    *,
    period: str = "1mo",
    interval: str = "1d",
    timeout_sec: object = None,
):
    """Return a Yahoo history DataFrame, or raise on timeout / provider error.

    Network call — offline tests should mock. Empty frames are returned as-is
    (caller decides empty vs missing); a still-alive worker after the join
    ceiling raises ``TimeoutError`` so hung Yahoo cannot look finished.
    """
    import yfinance as yf

    sym = str(symbol or "").strip() or "UNKNOWN"

    def _call() -> Any:
        return yf.Ticker(sym).history(period=period, interval=interval)

    return _join_yf_call(
        label="history",
        symbol=sym,
        timeout_sec=timeout_sec,
        default_timeout=DEFAULT_YF_HISTORY_TIMEOUT_SEC,
        call=_call,
    )


def fetch_yfinance_info(
    symbol: str,
    *,
    timeout_sec: object = None,
) -> dict:
    """Return Yahoo ``Ticker.info`` dict, or raise on timeout / provider error.

    Network call — offline tests should mock. Non-dict / empty info is returned
    as ``{}`` (caller decides missing); a still-alive worker after the join
    ceiling raises ``TimeoutError`` so hung Yahoo quote cannot look finished.
    """
    import yfinance as yf

    sym = str(symbol or "").strip() or "UNKNOWN"

    def _call() -> Any:
        return yf.Ticker(sym).info

    raw = _join_yf_call(
        label="info",
        symbol=sym,
        timeout_sec=timeout_sec,
        default_timeout=DEFAULT_YF_INFO_TIMEOUT_SEC,
        call=_call,
    )
    return raw if isinstance(raw, dict) else {}


def fetch_yfinance_earnings_attrs(
    symbol: str,
    *,
    timeout_sec: object = None,
) -> dict[str, Any]:
    """Return ``{"earnings_dates", "calendar"}`` or raise on timeout / error.

    Both attrs are read inside one join so a hung Yahoo earnings path cannot
    stall the blackout probe forever and look like a calm allow.
    """
    import yfinance as yf

    sym = str(symbol or "").strip() or "UNKNOWN"

    def _call() -> dict[str, Any]:
        ticker = yf.Ticker(sym)
        return {
            "earnings_dates": getattr(ticker, "earnings_dates", None),
            "calendar": getattr(ticker, "calendar", None),
        }

    raw = _join_yf_call(
        label="earnings",
        symbol=sym,
        timeout_sec=timeout_sec,
        default_timeout=DEFAULT_YF_EARNINGS_TIMEOUT_SEC,
        call=_call,
    )
    return raw if isinstance(raw, dict) else {}


def fetch_yfinance_fast_info(
    symbol: str,
    *,
    timeout_sec: object = None,
) -> Any:
    """Return Yahoo ``Ticker.fast_info`` (or None), or raise on timeout / error.

    Desk mark fallback after empty history — must not hang forever on Yahoo.
    """
    import yfinance as yf

    sym = str(symbol or "").strip() or "UNKNOWN"

    def _call() -> Any:
        return getattr(yf.Ticker(sym), "fast_info", None)

    return _join_yf_call(
        label="fast_info",
        symbol=sym,
        timeout_sec=timeout_sec,
        default_timeout=DEFAULT_YF_FAST_INFO_TIMEOUT_SEC,
        call=_call,
    )