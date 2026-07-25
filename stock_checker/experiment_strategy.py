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
SHORT_SMA = 15
MED_SMA = 40
LONG_SMA = 60
# Require short > med to enter; exit when short < med
REQUIRE_VOLUME_CONFIRM = True
VOLUME_LOOKBACK = 20
MIN_VOLUME_RATIO = 1.3
# Skip entries when recent daily-return stdev is elevated
VOLATILITY_LOOKBACK = 15
MAX_RETURN_STDEV = 0.020  # ~2.0% daily stdev
# Only buy non-SPY names when SPY medium SMA is rising
REQUIRE_SPY_UPTREND = True
# Prefer names beating SPY over this lookback (relative strength)
REQUIRE_REL_STRENGTH = True
RS_LOOKBACK = 30


def _sma(closes: List[float], period: int, exclude_last: bool = False) -> float:
    """Calculates the Simple Moving Average. If exclude_last is True, calculates SMA on closes[:-1]."""
    if not closes or len(closes) < period:
        return 0.0
    
    window = closes[-period:] if not exclude_last else closes[:-1][-period:]
    return sum(window) / period


def _return_stdev(closes: List[float], lookback: int) -> float:
    """Calculates the standard deviation of returns over a lookback period."""
    if len(closes) < lookback + 1:
        return 0.0
    rets = []
    # Calculate returns for the last 'lookback' periods
    for i in range(-lookback, 0):
        prev = closes[i - 1]
        current = closes[i]
        if prev <= 0:
            continue
        rets.append((current - prev) / prev)

    if len(rets) < 2:
        return 0.0
    
    # Calculate sample standard deviation (N-1 denominator)
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return var ** 0.5


def _period_return(closes: List[float], lookback: int) -> float:
    """Calculates the total percentage return over a lookback period."""
    if len(closes) < lookback + 1:
        return 0.0
    start = closes[-(lookback + 1)]
    end = closes[-1]
    if start <= 0:
        return 0.0
    return (end - start) / start


def generate_signals(
    bars_by_symbol: Dict[str, List[Dict]],
    index: int,
    portfolio: Dict,
) -> Dict[str, str]:
    """Multi-SMA + volume + vol/SPY filters + relative strength vs SPY. 
       Improved exit logic using medium SMA momentum confirmation."""
    signals: Dict[str, str] = {}
    
    # Determine minimum required data length for all checks
    need = max(
        SHORT_SMA,
        MED_SMA,
        LONG_SMA,
        VOLUME_LOOKBACK if REQUIRE_VOLUME_CONFIRM else 0,
        VOLATILITY_LOOKBACK + 1,
        RS_LOOKBACK + 1 if REQUIRE_REL_STRENGTH else 0,
        MED_SMA + 1, # Need at least one previous bar for exit check
    )

    # --- SPY Filters (Market Context) ---
    spy_ok = True
    spy_ret = 0.0
    if "SPY" in bars_by_symbol and index >= need:
        spy_closes = [float(b["close"]) for b in bars_by_symbol["SPY"][: index + 1]]
        
        # Check SPY UPTREND (Medium SMA)
        if REQUIRE_SPY_UPTREND and index >= MED_SMA + 1:
            spy_m_now = _sma(spy_closes, MED_SMA)
            # Calculate previous medium SMA using the helper function with exclusion
            spy_m_prev = _sma(spy_closes, MED_SMA, exclude_last=True)
            spy_ok = spy_m_now >= spy_m_prev

        # Calculate SPY Relative Strength (for comparison)
        if REQUIRE_REL_STRENGTH:
            spy_ret = _period_return(spy_closes, RS_LOOKBACK)

    # --- Signal Generation Loop ---
    for symbol, bars in bars_by_symbol.items():
        if index < need or index >= len(bars):
            continue

        closes = [float(b["close"]) for b in bars[: index + 1]]
        in_pos = symbol in portfolio.get("positions", {})

        # Calculate current and previous SMAs
        sma_s = _sma(closes, SHORT_SMA)
        sma_m = _sma(closes, MED_SMA)
        sma_l = _sma(closes, LONG_SMA)
        
        # Previous Medium SMA (Used for exit confirmation)
        sma_m_prev = _sma(closes, MED_SMA, exclude_last=True)

        # 1. Volume Confirmation Check
        vol_ok = True
        if REQUIRE_VOLUME_CONFIRM:
            vols = [float(b.get("volume", 0) or 0) for b in bars[: index + 1]]
            avg_vol = sum(vols[-VOLUME_LOOKBACK:]) / VOLUME_LOOKBACK
            cur_vol = vols[-1]
            if avg_vol > 0:
                vol_ok = (cur_vol / avg_vol) >= MIN_VOLUME_RATIO

        # 2. Volatility Gate Check
        calm = _return_stdev(closes, VOLATILITY_LOOKBACK) <= MAX_RETURN_STDEV
        
        # 3. Market Context Checks
        market_ok = spy_ok or symbol == "SPY" # Allow SPY regardless of SPY trend check
        rs_ok = True
        if REQUIRE_REL_STRENGTH and symbol != "SPY":
            current_ret = _period_return(closes, RS_LOOKBACK)
            # Check if the asset's relative strength beats or matches SPY's return
            rs_ok = current_ret >= spy_ret

        # --- ENTRY LOGIC (BUY) ---
        if (
            sma_s > sma_m  # Core signal: Short crosses above Medium
            and vol_ok
            and calm
            and market_ok
            and rs_ok
            and not in_pos
        ):
            signals[symbol] = "BUY"

        # --- EXIT LOGIC (SELL) ---
        # Improvement: Exit only if short crosses below medium AND the medium SMA is losing momentum 
        # (i.e., current Medium < Previous Medium). This filters out temporary pullbacks.
        elif sma_s < sma_m and in_pos and sma_m < sma_m_prev:
            signals[symbol] = "SELL"

    return signals
