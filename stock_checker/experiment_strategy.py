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
LONG_SMA = 100
# Require short > med > long to enter; exit when short < med
REQUIRE_VOLUME_CONFIRM = True
VOLUME_LOOKBACK = 20
MIN_VOLUME_RATIO = 1.2
# Skip entries when recent daily-return stdev is elevated
VOLATILITY_LOOKBACK = 15
MAX_RETURN_STDEV = 0.025  # ~2.5% daily stdev
# Only buy non-SPY names when SPY medium SMA is rising
REQUIRE_SPY_UPTREND = True
# Prefer names beating SPY over this lookback (relative strength)
REQUIRE_REL_STRENGTH = True
RS_LOOKBACK = 20


def _sma(closes: List[float], period: int) -> float:
    window = closes[-period:]
    return sum(window) / period


def _return_stdev(closes: List[float], lookback: int) -> float:
    if len(closes) < lookback + 1:
        return 0.0
    rets = []
    for i in range(-lookback, 0):
        prev = closes[i - 1]
        if prev <= 0:
            continue
        rets.append((closes[i] - prev) / prev)
    if len(rets) < 2:
        return 0.0
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return var ** 0.5


def _period_return(closes: List[float], lookback: int) -> float:
    if len(closes) < lookback + 1:
        return 0.0
    start = closes[-(lookback + 1)]
    if start <= 0:
        return 0.0
    return (closes[-1] - start) / start


def generate_signals(
    bars_by_symbol: Dict[str, List[Dict]],
    index: int,
    portfolio: Dict,
) -> Dict[str, str]:
    """Multi-SMA + volume + vol/SPY filters + relative strength vs SPY."""
    signals: Dict[str, str] = {}
    need = max(
        SHORT_SMA,
        MED_SMA,
        LONG_SMA,
        VOLUME_LOOKBACK if REQUIRE_VOLUME_CONFIRM else 0,
        VOLATILITY_LOOKBACK + 1,
        RS_LOOKBACK + 1 if REQUIRE_REL_STRENGTH else 0,
        MED_SMA + 1,
    )

    spy_ok = True
    spy_ret = 0.0
    if "SPY" in bars_by_symbol and index >= need:
        spy_closes = [float(b["close"]) for b in bars_by_symbol["SPY"][: index + 1]]
        if REQUIRE_SPY_UPTREND and index >= MED_SMA + 1:
            spy_m_now = _sma(spy_closes, MED_SMA)
            spy_m_prev = _sma(spy_closes[:-1], MED_SMA)
            spy_ok = spy_m_now >= spy_m_prev
        if REQUIRE_REL_STRENGTH:
            spy_ret = _period_return(spy_closes, RS_LOOKBACK)

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

        calm = _return_stdev(closes, VOLATILITY_LOOKBACK) <= MAX_RETURN_STDEV
        market_ok = spy_ok or symbol == "SPY"
        rs_ok = True
        if REQUIRE_REL_STRENGTH and symbol != "SPY":
            rs_ok = _period_return(closes, RS_LOOKBACK) >= spy_ret

        if (
            sma_s > sma_m > sma_l
            and vol_ok
            and calm
            and market_ok
            and rs_ok
            and not in_pos
        ):
            signals[symbol] = "BUY"
        elif sma_s < sma_m and in_pos:
            signals[symbol] = "SELL"

    return signals
