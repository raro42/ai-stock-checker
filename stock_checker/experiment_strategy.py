#!/usr/bin/env python3
"""
EDITABLE overnight experiment strategy (autoresearch target file).

The agent may only modify THIS file during autoresearch runs.
Harness: scripts/run_experiment.py (read-only).

Export generate_signals(bars_by_symbol, index, portfolio) -> {symbol: 'BUY'|'SELL'}
"""

from __future__ import annotations

from typing import Dict, List

# --- hyperparameters the agent may tune ---
SHORT_SMA = 10
MED_SMA = 30
LONG_SMA = 60
# Require short > med > long to enter; exit when short < med
REQUIRE_VOLUME_CONFIRM = False
VOLUME_LOOKBACK = 20
MIN_VOLUME_RATIO = 1.1


def _sma(closes: List[float], period: int) -> float:
    window = closes[-period:]
    return sum(window) / period


def generate_signals(
    bars_by_symbol: Dict[str, List[Dict]],
    index: int,
    portfolio: Dict,
) -> Dict[str, str]:
    """Baseline: multi-SMA trend alignment (long-only)."""
    signals: Dict[str, str] = {}
    need = max(SHORT_SMA, MED_SMA, LONG_SMA, VOLUME_LOOKBACK if REQUIRE_VOLUME_CONFIRM else 0)

    for symbol, bars in bars_by_symbol.items():
        if index < need or index >= len(bars):
            continue

        closes = [float(b["close"]) for b in bars[: index + 1]]
        sma_s = _sma(closes, SHORT_SMA)
        sma_m = _sma(closes, MED_SMA)
        sma_l = _sma(closes, LONG_SMA)
        in_pos = symbol in portfolio.get("positions", {})

        vol_ok = True
        if REQUIRE_VOLUME_CONFIRM:
            vols = [float(b.get("volume", 0) or 0) for b in bars[: index + 1]]
            avg_vol = sum(vols[-VOLUME_LOOKBACK:]) / VOLUME_LOOKBACK
            cur_vol = vols[-1]
            vol_ok = avg_vol > 0 and (cur_vol / avg_vol) >= MIN_VOLUME_RATIO

        if sma_s > sma_m > sma_l and vol_ok and not in_pos:
            signals[symbol] = "BUY"
        elif sma_s < sma_m and in_pos:
            signals[symbol] = "SELL"

    return signals
