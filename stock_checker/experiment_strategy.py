#!/usr/bin/env python3
"""
EDITABLE overnight experiment strategy (autoresearch target file).

The agent may only modify THIS file during autoresearch runs.
Harness: scripts/run_experiment.py (read-only).

Export generate_signals(bars_by_symbol, index, portfolio) -> {symbol: 'BUY'|'SELL'}
"""

from __future__ import annotations

from typing import Dict, List
import math


# idea: Tightening the volatility gate (MAX_RETURN_STDEV) to increase robustness by only entering during periods of stable, moderate volatility, filtering out high-chop periods.
# ----------------------------------------------------------------------------
# --- hyperparameters the agent may tune ---
SHORT_SMA = 20  # Core entry trigger (Increased from 15 for more stable trend confirmation)
SHORT_MOMENTUM_SMA = 5 # NEW: Short-term filter to confirm immediate momentum
MED_SMA = 50    # Secondary filter/reference SMA (Used for entry confirmation)
LONG_SMA = 40   # Primary exit structural guide (Reduced from 60 to 40 for faster exit)
# Require short > med to enter; exit when price drops significantly below the LONG_SMA AND price confirms weakness relative to Short Momentum SMA.
REQUIRE_VOLUME_CONFIRM = True
VOLUME_LOOKBACK = 20
MIN_VOLUME_RATIO = 1.0 # MODIFIED: Loosened from 1.1 to 1.0 to increase signal volume
# Skip entries when recent daily-return stdev is elevated
VOLATILITY_LOOKBACK = 15
MAX_RETURN_STDEV = 0.013  # TIGHTENED: Reduced from 0.015 to 1.3% daily stdev for higher robustness
# Only buy non-SPY names when SPY medium SMA is rising
REQUIRE_SPY_UPTREND = True
# Prefer names beating SPY over this lookback (relative strength)
REQUIRE_REL_STRENGTH = False # Disabled relative strength requirement for robustness
RS_LOOKBACK = 20 # CHANGED: Reduced lookback for faster reaction

# --- IMPROVEMENT: RSI Filters ---
RSI_PERIOD = 14
MIN_ENTRY_RSI = 35.0   # Minimum acceptable RSI (avoiding oversold entries)
MAX_ENTRY_RSI = 65.0   # Maximum acceptable RSI (avoiding overbought entries)

# New exit requirement: Price must drop below 95% of the Short Momentum SMA for confirmation.
EXIT_PRICE_CONFIRMATION_MULTIPLIER = 0.95


def _sma(closes: List[float], period: int, exclude_last: bool = False) -> float:
    """Calculates the Simple Moving Average. If exclude_last is True, calculates SMA on closes[:-1]."""
    if not closes or len(closes) < period:
        return 0.0
    
    # Determine the window to use
    if exclude_last:
        window = closes[:-1]
    else:
        window = closes
        
    if len(window) < period:
        return 0.0
        
    return sum(window[-period:]) / period


def _return_stdev(closes: List[float], lookback: int) -> float:
    """Calculates the standard deviation of returns over a lookback period."""
    if len(closes) < lookback + 1:
        return 0.0
    rets = []
    # Calculate returns for the last 'lookback' periods
    # We need 'lookback' returns, meaning 'lookback + 1' data points
    for i in range(len(closes) - 1, len(closes) - lookback - 1, -1):
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


def _rsi(closes: List[float], period: int) -> float:
    """Calculates the Relative Strength Index."""
    if len(closes) < period + 1:
        return 50.0 # Neutral default if not enough data

    diffs = []
    # We need to calculate 'period' changes ending at the current bar
    for i in range(len(closes) - 1, len(closes) - period - 2, -1):
        change = closes[i] - closes[i-1]
        diffs.append(change)
    
    if len(diffs) < period:
        return 50.0

    gains = [max(0, d) for d in diffs]
    losses = [-min(0, d) for d in diffs]
    
    # Since we gathered the last 'period' changes, we use these lists directly
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def generate_signals(
    bars_by_symbol: Dict[str, List[Dict]],
    index: int,
    portfolio: Dict,
) -> Dict[str, str]:
    """Multi-SMA + volume + vol/SPY filters + relative strength vs SPY. 
       Entry uses Short > Medium SMA AND Short Momentum SMA confirms strength AND Medium SMA is rising. 
       Exit uses structural price confirmation (Price < LONG_SMA) AND tight price confirmation relative to Short Momentum SMA."""
    signals: Dict[str, str] = {}
    
    # Determine minimum required data length for all checks
    need = max(
        SHORT_SMA,
        SHORT_MOMENTUM_SMA,
        MED_SMA,
        LONG_SMA,
        VOLUME_LOOKBACK if REQUIRE_VOLUME_CONFIRM else 0,
        VOLATILITY_LOOKBACK + 1,
        RSI_PERIOD + 1,
        LONG_SMA + 1,
    )

    # --- SPY Filters (Market Context) ---
    spy_ok = True
    spy_ret = 0.0
    spy_m_prev = 0.0 # Initialize previous SMA value
    if "SPY" in bars_by_symbol and index >= need:
        # Use float conversion on the fly for safety
        spy_closes = [float(b["close"]) for b in bars_by_symbol["SPY"][: index + 1]]
        
        # Check SPY UPTREND (Medium SMA)
        if REQUIRE_SPY_UPTREND and index >= MED_SMA + 1:
            spy_m_now = _sma(spy_closes, MED_SMA)
            # Calculate previous medium SMA using the helper function with exclusion
            spy_m_prev = _sma(spy_closes, MED_SMA, exclude_last=True)
            spy_ok = spy_m_now >= spy_m_prev

        # SPY Relative Strength calculation (used only if REQUIRE_REL_STRENGTH is True)
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
        sma_mon = _sma(closes, SHORT_MOMENTUM_SMA)
        
        # NEW: Calculate previous Medium SMA
        sma_m_prev = _sma(closes, MED_SMA, exclude_last=True)
        
        current_close = float(bars[-1]["close"])

        # 1. Volume Confirmation Check
        vol_ok = True
        if REQUIRE_VOLUME_CONFIRM:
            vols = [float(b.get("volume", 0) or 0) for b in bars[: index + 1]]
            avg_vol = sum(vols[-VOLUME_LOOKBACK:]) / VOLUME_LOOKBACK
            cur_vol = vols[-1]
            if avg_vol > 0:
                # Changed ratio check to >= 1.0
                vol_ok = (cur_vol / avg_vol) >= MIN_VOLUME_RATIO

        # 2. Volatility Gate Check
        calm = _return_stdev(closes, VOLATILITY_LOOKBACK) <= MAX_RETURN_STDEV
        
        # 3. RSI Filter Check
        rsi_val = _rsi(closes, RSI_PERIOD)
        # Ensure RSI is within the neutral band [MIN_ENTRY_RSI, MAX_ENTRY_RSI]
        rsi_ok = (rsi_val >= MIN_ENTRY_RSI and rsi_val <= MAX_ENTRY_RSI)

        # 4. Market Context Checks
        market_ok = spy_ok or symbol == "SPY"
        rs_ok = True
        if REQUIRE_REL_STRENGTH and symbol != "SPY":
            current_ret = _period_return(closes, RS_LOOKBACK)
            # Check if the asset's relative strength beats or matches SPY's return
            rs_ok = current_ret >= spy_ret

        # --- ENTRY LOGIC (BUY) ---
        # Entry requires: 1. Short > Medium, 2. Short > Momentum SMA, 3. Medium SMA is rising, 4. Volume/Vol/RSI/Market checks pass.
        if (
            sma_s > sma_m  # Core signal: Short crosses above Medium
            and sma_s > sma_mon # Momentum confirmation: Short SMA must be above its 5-period SMA
            and sma_m >= sma_m_prev # Medium SMA must be non-decreasing (confirming accelerating trend)
            and vol_ok
            and calm
            and market_ok
            and rs_ok
            and rsi_ok # RSI filter must be within the neutral band
            and not in_pos
        ):
            signals[symbol] = "BUY"

        # --- EXIT LOGIC (SELL) ---
        # Exit if price drops below the long-term structural average (LONG_SMA) AND price confirms weakness relative to Short Momentum SMA.
        elif (
            current_close < sma_l # STRUCTURAL CHANGE: Using current price vs LONG_SMA instead of SMA_M < SMA_L
            and in_pos
            and current_close < sma_mon * EXIT_PRICE_CONFIRMATION_MULTIPLIER # Exit uses Short Momentum SMA for tighter, faster confirmation
        ):
            signals[symbol] = "SELL"

    return signals
