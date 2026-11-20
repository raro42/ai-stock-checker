#!/usr/bin/env python3
"""Signal helpers bridging scoring ideas to the backtester."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from stock_checker.technical_indicators import _coerce_indicator_period, _valid_close


def _valid_close_tail(
    bars: Sequence[Dict], index: int, n: int
) -> Optional[List[float]]:
    """Last ``n`` closes at ``index``, or None if any bar is gap/zero/NaN/non-numeric."""
    if n <= 0 or index + 1 < n or index >= len(bars):
        return None
    out: List[float] = []
    for bar in bars[index + 1 - n : index + 1]:
        close = bar.get("close") if isinstance(bar, dict) else None
        if not _valid_close(close):
            return None
        out.append(float(close))
    return out


def multi_timeframe_momentum_strategy(
    bars_by_symbol: Dict[str, List[Dict]],
    index: int,
    portfolio: Dict,
    short: int = 5,
    medium: int = 20,
    long: int = 50,
) -> Dict[str, str]:
    """
    Long-only multi-timeframe momentum.

    BUY when short SMA > medium SMA > long SMA (aligned uptrend).
    SELL when short SMA < medium SMA.

    Gap/zero/NaN closes in the SMA windows are unavailable (no BUY/SELL invent).
    Bool SMA windows refuse (``True→SMA(1)`` invent).
    """
    # tradermonty #700/#655: refuse bool periods — True→1 invents a 1-bar SMA.
    s = _coerce_indicator_period(short)
    m = _coerce_indicator_period(medium)
    lo = _coerce_indicator_period(long)
    if s is None or m is None or lo is None:
        return {}
    signals: Dict[str, str] = {}
    need = max(s, m, lo)
    for symbol, bars in bars_by_symbol.items():
        closes = _valid_close_tail(bars, index, need)
        if closes is None:
            continue
        sma_s = sum(closes[-s:]) / s
        sma_m = sum(closes[-m:]) / m
        sma_l = sum(closes[-lo:]) / lo
        in_pos = symbol in portfolio.get("positions", {})
        if sma_s > sma_m > sma_l and not in_pos:
            signals[symbol] = "BUY"
        elif sma_s < sma_m and in_pos:
            signals[symbol] = "SELL"
    return signals
