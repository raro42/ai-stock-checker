"""
Promoted champion adapter — live entry filter for experiment_strategy rules.

Overnight autoresearch still edits only experiment_strategy.py.
This module is the deliberate promote path: when enabled, scanner opportunities
must also pass the champion BUY filter (exits stay in exit_policy).

Default: off. Enable via PROMOTE_EXPERIMENT_STRATEGY=1 or trader_config.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from stock_checker.experiment_strategy import generate_signals as champion_signals

# Stable name for docs / Ops — always the current experiment champion file.
PROMOTED_SOURCE = "stock_checker.experiment_strategy"


def promote_enabled_from_env(default: bool = False) -> bool:
    raw = os.getenv("PROMOTE_EXPERIMENT_STRATEGY")
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"0", "false", "no", "off", ""}


def bars_from_closes(
    closes: List[float],
    *,
    start: Optional[datetime] = None,
    volumes: Optional[List[float]] = None,
) -> List[Dict[str, Any]]:
    """Build minimal OHLCV bars for champion generate_signals."""
    day0 = start or datetime(2020, 1, 1)
    bars: List[Dict[str, Any]] = []
    for i, close in enumerate(closes):
        px = float(close)
        vol = float(volumes[i]) if volumes and i < len(volumes) else 1_000_000.0
        bars.append(
            {
                "date": day0 + timedelta(days=i),
                "open": px,
                "high": px,
                "low": px,
                "close": px,
                "volume": vol,
            }
        )
    return bars


def champion_wants_buy(
    bars_by_symbol: Dict[str, List[Dict[str, Any]]],
    symbol: str,
    *,
    signal_fn: Callable = champion_signals,
) -> Optional[bool]:
    """
    True if champion emits BUY for symbol on the last bar.
    None if insufficient data / error (caller should not veto).
    """
    if symbol not in bars_by_symbol:
        return None
    bars = bars_by_symbol[symbol]
    if len(bars) < 60:
        return None
    # Include SPY when present so REQUIRE_SPY_UPTREND can evaluate.
    portfolio = {"cash": 0.0, "positions": {}}
    index = len(bars) - 1
    # Align: use min length across provided series
    min_len = min(len(b) for b in bars_by_symbol.values())
    if min_len < 60:
        return None
    index = min_len - 1
    try:
        signals = signal_fn(bars_by_symbol, index, portfolio) or {}
    except Exception:
        return None
    action = str(signals.get(symbol) or "").upper()
    return action == "BUY"


def filter_opportunities(
    opportunities: List[Dict[str, Any]],
    bars_by_symbol: Dict[str, List[Dict[str, Any]]],
    *,
    signal_fn: Callable = champion_signals,
) -> List[Dict[str, Any]]:
    """
    Keep opportunities the champion would BUY; drop clear non-BUYs.
    If bars missing for a symbol, keep the opportunity (no false veto).
    """
    if not opportunities:
        return opportunities
    kept: List[Dict[str, Any]] = []
    for opp in opportunities:
        symbol = str(opp.get("symbol") or "")
        if not symbol:
            continue
        verdict = champion_wants_buy(bars_by_symbol, symbol, signal_fn=signal_fn)
        if verdict is False:
            opp = dict(opp)
            opp["promoted_filter"] = "reject"
            continue
        opp = dict(opp)
        if verdict is True:
            opp["promoted_filter"] = "buy"
            # Mild boost so champion-confirmed names rank ahead of unknowns
            try:
                opp["score"] = float(opp.get("score") or 0) * 1.15
            except (TypeError, ValueError):
                pass
        else:
            opp["promoted_filter"] = "skip_no_bars"
        kept.append(opp)
    kept.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
    for i, rec in enumerate(kept, 1):
        rec["rank"] = i
    return kept


def load_daily_closes_yfinance(symbol: str, *, period: str = "1y") -> List[float]:
    """Best-effort daily closes; empty on failure (offline-safe)."""
    try:
        import yfinance as yf
    except ImportError:
        return []
    try:
        hist = yf.Ticker(symbol).history(period=period, interval="1d")
        if hist is None or hist.empty:
            return []
        return [float(x) for x in hist["Close"].tolist() if x == x]
    except Exception:
        return []


def build_bars_for_symbols(symbols: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch daily bars for candidates + SPY (for trend filter)."""
    needed = list(dict.fromkeys([*symbols, "SPY"]))
    out: Dict[str, List[Dict[str, Any]]] = {}
    for sym in needed:
        closes = load_daily_closes_yfinance(sym)
        if len(closes) >= 60:
            out[sym] = bars_from_closes(closes)
    return out
