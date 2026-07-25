#!/usr/bin/env python3
"""
Fixed-budget paper-strategy experiment runner (autoresearch harness).

Do NOT modify this file during overnight experiments — only edit
stock_checker/experiment_strategy.py.

Prints machine-readable metrics for the agent keep/revert loop:
  val_score: <float>          # higher is better (risk-adjusted)
  total_return_pct: ...
  max_drawdown_pct: ...
  sharpe_ratio: ...
  total_trades: ...
  fees_pct: ...
  experiment_seconds: ...
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

# Ensure project root is importable when run as a script
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from stock_checker.backtester import Backtester
from stock_checker.experiment_strategy import generate_signals
from stock_checker.walk_forward import walk_forward_val_score

# Fixed harness constants (do not change in overnight runs)
TIME_BUDGET_SEC = 120  # wall-clock compute budget inside the experiment
DATA_DIR = Path("data/experiment_bars")
DEFAULT_SYMBOLS = ["SPY", "QQQ", "IWM", "GLD", "AAPL", "MSFT", "NVDA", "JNJ"]
INITIAL_CAPITAL = 100_000.0
COMMISSION = 0.001
SLIPPAGE = 0.0005
POSITION_FRACTION = 0.15


def _synthetic_bars(symbol: str, n: int = 504, seed: int = 0) -> List[Dict]:
    """Deterministic multi-regime synthetic OHLCV (offline fallback)."""
    # Simple LCG for reproducibility without numpy RandomState coupling
    state = (hash(symbol) ^ seed) & 0xFFFFFFFF

    def rnd() -> float:
        nonlocal state
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        return state / 0xFFFFFFFF

    bars: List[Dict] = []
    price = 100.0 + (hash(symbol) % 50)
    day0 = datetime(2023, 1, 3)
    for i in range(n):
        # Regime: trend / mean-revert / chop
        regime = (i // 84) % 3
        if regime == 0:
            drift = 0.0015
            vol = 0.012
        elif regime == 1:
            drift = -0.0005
            vol = 0.02
        else:
            drift = 0.0002
            vol = 0.008
        shock = (rnd() - 0.5) * 2 * vol
        price = max(1.0, price * (1 + drift + shock))
        high = price * (1 + abs(shock))
        low = price * (1 - abs(shock))
        bars.append(
            {
                "date": day0 + timedelta(days=i),
                "open": price,
                "high": high,
                "low": low,
                "close": price,
                "volume": 1_000_000 + int(rnd() * 500_000),
            }
        )
    return bars


def load_bars(symbols: List[str]) -> Dict[str, List[Dict]]:
    """Load cached bars, else try yfinance once, else synthetic."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out: Dict[str, List[Dict]] = {}

    missing = []
    for symbol in symbols:
        cache = DATA_DIR / f"{symbol}.json"
        if cache.exists():
            raw = json.loads(cache.read_text())
            bars = []
            for row in raw:
                row = dict(row)
                if isinstance(row.get("date"), str):
                    row["date"] = datetime.fromisoformat(row["date"])
                bars.append(row)
            out[symbol] = bars
        else:
            missing.append(symbol)

    if missing:
        try:
            import yfinance as yf

            for symbol in missing:
                hist = yf.Ticker(symbol).history(period="2y", interval="1d")
                if hist is None or hist.empty:
                    out[symbol] = _synthetic_bars(symbol)
                    continue
                bars = []
                serializable = []
                for idx, row in hist.iterrows():
                    dt = idx.to_pydatetime().replace(tzinfo=None)
                    bar = {
                        "date": dt,
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": float(row.get("Volume", 0) or 0),
                    }
                    bars.append(bar)
                    serializable.append({**bar, "date": dt.isoformat()})
                (DATA_DIR / f"{symbol}.json").write_text(json.dumps(serializable))
                out[symbol] = bars
                print(f"cached_bars: {symbol} n={len(bars)}")
        except Exception as exc:
            print(f"yfinance_fallback: {exc}")
            for symbol in missing:
                if symbol not in out:
                    out[symbol] = _synthetic_bars(symbol)

    for symbol in symbols:
        if symbol not in out:
            out[symbol] = _synthetic_bars(symbol)

    return out


def compute_val_score(metrics: dict) -> float:
    """
    Single scalar for keep/revert (higher is better).

    Sharpe primary, penalize drawdown and fee burn, require some activity.
    """
    def _f(key: str, default: float = 0.0) -> float:
        try:
            v = float(metrics.get(key, default) or default)
        except (TypeError, ValueError):
            return default
        if v != v:  # NaN
            return default
        return v

    sharpe = _f("sharpe_ratio")
    dd = _f("max_drawdown")  # already in %
    ret = _f("total_return_pct")
    trades = int(metrics.get("total_trades", 0) or 0)
    fees_pct = _f("fees_pct")

    if trades < 2:
        return -100.0  # inactive strategy is a failure

    score = sharpe * 10.0 + ret * 0.05 - dd * 0.15 - fees_pct * 0.5
    if score != score:  # NaN guard
        return -100.0
    return float(score)


def _metrics_for_bars(bt: Backtester, data: Dict[str, List[Dict]]) -> dict:
    result = bt.backtest(data, generate_signals)
    metrics = result.calculate_metrics()
    fees_pct = 0.0
    if result.trades:
        notional = sum(abs(t.shares * t.entry_price) for t in result.trades)
        fees_pct = (notional * COMMISSION * 2) / INITIAL_CAPITAL * 100.0
    metrics["fees_pct"] = fees_pct
    return metrics


def run() -> int:
    t0 = time.time()
    symbols = list(DEFAULT_SYMBOLS)
    data = load_bars(symbols)

    bt = Backtester(
        initial_capital=INITIAL_CAPITAL,
        commission_rate=COMMISSION,
        slippage_pct=SLIPPAGE,
        position_fraction=POSITION_FRACTION,
    )

    # Full-sample metrics (reporting) + walk-forward mean score (keep/revert)
    full_metrics = _metrics_for_bars(bt, data)

    def fold_score(fold_data: Dict[str, List[Dict]]) -> float:
        return compute_val_score(_metrics_for_bars(bt, fold_data))

    wf_score, fold_scores = walk_forward_val_score(data, fold_score, n_folds=3, min_bars=80)
    # Conservative blend: mean OOS, lightly penalize weak worst fold
    worst = min(fold_scores) if fold_scores else -100.0
    best_score = 0.75 * wf_score + 0.25 * worst
    if best_score != best_score:
        best_score = -100.0

    elapsed = time.time() - t0
    runs = 1 + len(fold_scores)

    print("---")
    print(f"val_score:            {best_score:.6f}")
    print(f"wf_score_mean:        {wf_score:.6f}")
    print(f"wf_score_min:         {worst:.6f}")
    print(f"wf_fold_scores:       {','.join(f'{s:.4f}' for s in fold_scores)}")
    print(f"total_return_pct:     {full_metrics['total_return_pct']:.6f}")
    print(f"max_drawdown_pct:     {full_metrics['max_drawdown']:.6f}")
    print(f"sharpe_ratio:         {full_metrics['sharpe_ratio']:.6f}")
    print(f"total_trades:         {full_metrics['total_trades']}")
    print(f"win_rate:             {full_metrics['win_rate']:.6f}")
    print(f"fees_pct:             {full_metrics.get('fees_pct', 0):.6f}")
    print(f"experiment_seconds:   {elapsed:.1f}")
    print(f"runs:                 {runs}")
    print(f"symbols:              {','.join(symbols)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
