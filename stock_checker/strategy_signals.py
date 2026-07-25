#!/usr/bin/env python3
"""Signal helpers bridging scoring ideas to the backtester."""

from __future__ import annotations

from typing import Dict, List


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
    """
    signals: Dict[str, str] = {}
    need = max(short, medium, long)
    for symbol, bars in bars_by_symbol.items():
        if index < need or index >= len(bars):
            continue
        closes = [float(b["close"]) for b in bars[: index + 1]]
        sma_s = sum(closes[-short:]) / short
        sma_m = sum(closes[-medium:]) / medium
        sma_l = sum(closes[-long:]) / long
        in_pos = symbol in portfolio.get("positions", {})
        if sma_s > sma_m > sma_l and not in_pos:
            signals[symbol] = "BUY"
        elif sma_s < sma_m and in_pos:
            signals[symbol] = "SELL"
    return signals
