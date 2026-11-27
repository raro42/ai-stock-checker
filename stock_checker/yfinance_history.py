"""Bounded yfinance ``Ticker.history`` / ``.info`` — hung Yahoo ≠ quiet success.

tradermonty #904/#905 + xang1234/portfolio AI: Yahoo ``yf.screen`` already
joins with a 20s ceiling; bare ``Ticker.history`` / ``.info`` could stall the
trader / quote / AI-validate path forever and look like a calm hang. Timeout
raises ``TimeoutError`` (callers map to fail-open empty / ValueError) — never
invent a finished empty frame or quote from a still-running worker.
"""

from __future__ import annotations

import threading
from typing import Any

from stock_checker.technical_indicators import coerce_nonneg_int

DEFAULT_YF_HISTORY_TIMEOUT_SEC = 20
DEFAULT_YF_INFO_TIMEOUT_SEC = DEFAULT_YF_HISTORY_TIMEOUT_SEC


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

    limit = coerce_yf_history_timeout_sec(
        DEFAULT_YF_HISTORY_TIMEOUT_SEC if timeout_sec is None else timeout_sec
    )
    sym = str(symbol or "").strip() or "UNKNOWN"
    box: dict[str, Any] = {}

    def _call() -> None:
        try:
            box["hist"] = yf.Ticker(sym).history(period=period, interval=interval)
        except Exception as e:
            box["error"] = e

    worker = threading.Thread(
        target=_call, name=f"yf-history-{sym}", daemon=True
    )
    worker.start()
    worker.join(timeout=float(limit))
    if worker.is_alive():
        raise TimeoutError(
            f"yfinance history {sym} timed out after {limit}s"
        )
    if "error" in box:
        raise box["error"]
    return box.get("hist")


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

    limit = coerce_yf_info_timeout_sec(
        DEFAULT_YF_INFO_TIMEOUT_SEC if timeout_sec is None else timeout_sec
    )
    sym = str(symbol or "").strip() or "UNKNOWN"
    box: dict[str, Any] = {}

    def _call() -> None:
        try:
            box["info"] = yf.Ticker(sym).info
        except Exception as e:
            box["error"] = e

    worker = threading.Thread(
        target=_call, name=f"yf-info-{sym}", daemon=True
    )
    worker.start()
    worker.join(timeout=float(limit))
    if worker.is_alive():
        raise TimeoutError(f"yfinance info {sym} timed out after {limit}s")
    if "error" in box:
        raise box["error"]
    raw = box.get("info")
    return raw if isinstance(raw, dict) else {}
