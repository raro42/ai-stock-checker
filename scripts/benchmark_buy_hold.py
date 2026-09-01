#!/usr/bin/env python3
"""
Benchmark experiment_strategy vs buy-and-hold baselines (same bars, same fees).

Uses the live-shaped harness (Revolut-standard fees, max positions, min hold).
Prints machine-readable lines and a short verdict. Does not claim live edge.
"""

from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.run_experiment import (  # noqa: E402
    COMMISSION,
    COMMISSION_MIN_EUR,
    DEFAULT_SYMBOLS,
    FEE_PRESET,
    FREE_LEGS_PER_MONTH,
    INITIAL_CAPITAL,
    MAX_POSITIONS,
    MIN_HOLD_BARS,
    POSITION_FRACTION,
    SLIPPAGE,
    estimate_fees_pct,
    load_bars,
    make_backtester,
)
from stock_checker.backtester import BacktestResult, Backtester, Trade  # noqa: E402
from stock_checker.experiment_strategy import generate_signals as strategy_signals  # noqa: E402
from stock_checker.fees import FeeAllowanceLedger  # noqa: E402
from stock_checker.walk_forward import walk_forward_val_score  # noqa: E402


def buy_and_hold_spy(
    bars_by_symbol: Dict[str, List[Dict]],
    index: int,
    portfolio: Dict,
) -> Dict[str, str]:
    """All-in SPY once; hold forever."""
    if "SPY" not in bars_by_symbol:
        return {}
    if "SPY" in portfolio.get("positions", {}):
        return {}
    if index < 1:
        return {}
    return {"SPY": "BUY"}


def buy_and_hold_equal_weight(
    bars_by_symbol: Dict[str, List[Dict]],
    index: int,
    portfolio: Dict,
) -> Dict[str, str]:
    """Signal helper for tests; fair EW uses run_equal_weight_buy_hold."""
    signals: Dict[str, str] = {}
    if index < 1:
        return signals
    positions = portfolio.get("positions", {})
    for symbol in bars_by_symbol:
        if symbol not in positions:
            signals[symbol] = "BUY"
    return signals


def benchmark_score(metrics: dict) -> float:
    """Like experiment val_score but allows a single round-trip (buy-and-hold)."""

    def _f(key: str, default: float = 0.0) -> float:
        try:
            v = float(metrics.get(key, default) or default)
        except (TypeError, ValueError):
            return default
        if v != v:
            return default
        return v

    trades = int(metrics.get("total_trades", 0) or 0)
    if trades < 1:
        return -100.0
    sharpe = _f("sharpe_ratio")
    dd = _f("max_drawdown")
    ret = _f("total_return_pct")
    fees_pct = _f("fees_pct")
    score = sharpe * 10.0 + ret * 0.05 - dd * 0.15 - fees_pct * 0.5
    if score != score:
        return -100.0
    return float(score)


def run_equal_weight_buy_hold(data: Dict[str, List[Dict]]) -> dict:
    """True equal-weight: split cash across symbols on bar 1, hold to end."""
    symbols = list(data.keys())
    min_len = min(len(data[s]) for s in symbols)
    result = BacktestResult(INITIAL_CAPITAL)
    if min_len < 2:
        metrics = result.calculate_metrics()
        metrics["fees_pct"] = 0.0
        metrics["val_score"] = benchmark_score(metrics)
        metrics["name"] = "buy_hold_equal_weight"
        return metrics

    cash = float(INITIAL_CAPITAL)
    positions: Dict[str, dict] = {}
    alloc = cash / len(symbols)
    entry_i = 1

    def ts(i: int) -> datetime:
        raw = data[symbols[0]][i].get("date")
        if isinstance(raw, datetime):
            return raw
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                pass
        return datetime(2000, 1, 1) + timedelta(days=i)

    entry_t = ts(entry_i)
    fees = 0.0
    ledger = FeeAllowanceLedger(FREE_LEGS_PER_MONTH)
    entry_ts = entry_t.strftime("%Y-%m-%d")
    for symbol in symbols:
        px = float(data[symbol][entry_i]["close"]) * (1 + SLIPPAGE)
        if px <= 0:
            continue
        shares = alloc / px
        cost = shares * px
        commission = ledger.commission_for_leg(
            cost, entry_ts, rate=COMMISSION, min_eur=COMMISSION_MIN_EUR
        )
        fees += commission
        cash -= cost + commission
        positions[symbol] = {"shares": shares, "entry_price": px, "entry_time": entry_t}

    result.equity_curve = [INITIAL_CAPITAL]
    for i in range(entry_i, min_len):
        mtm = cash + sum(
            positions[s]["shares"] * float(data[s][i]["close"]) for s in positions
        )
        result.equity_curve.append(mtm)
        result.timestamps.append(ts(i))

    last_i = min_len - 1
    last_t = ts(last_i)
    exit_ts = last_t.strftime("%Y-%m-%d")
    for symbol, pos in list(positions.items()):
        exit_px = float(data[symbol][last_i]["close"]) * (1 - SLIPPAGE)
        proceeds = pos["shares"] * exit_px
        commission = ledger.commission_for_leg(
            proceeds, exit_ts, rate=COMMISSION, min_eur=COMMISSION_MIN_EUR
        )
        fees += commission
        cash += proceeds - commission
        pnl = (exit_px - pos["entry_price"]) * pos["shares"] - commission
        entry_notional = pos["shares"] * pos["entry_price"]
        result.add_trade(
            Trade(
                symbol=symbol,
                entry_time=pos["entry_time"],
                exit_time=last_t,
                entry_price=pos["entry_price"],
                exit_price=exit_px,
                shares=pos["shares"],
                pnl=pnl,
                pnl_pct=(pnl / entry_notional) * 100 if entry_notional else 0.0,
                reason="end_of_data",
            )
        )
    result.equity_curve.append(cash)
    metrics = result.calculate_metrics()
    fee_pct = fees / INITIAL_CAPITAL * 100.0
    metrics["fees_pct"] = fee_pct if math.isfinite(fee_pct) else 0.0
    if math.isfinite(cash) and INITIAL_CAPITAL > 0:
        metrics["total_return_pct"] = (cash / INITIAL_CAPITAL - 1.0) * 100.0
    elif not math.isfinite(float(metrics.get("total_return_pct") or 0)):
        metrics["total_return_pct"] = 0.0
    metrics["val_score"] = benchmark_score(metrics)
    metrics["name"] = "buy_hold_equal_weight"
    return metrics


def _run(
    name: str,
    data: Dict[str, List[Dict]],
    fn: Callable,
    *,
    position_fraction: float,
    max_positions: int = 0,
) -> dict:
    bt = Backtester(
        initial_capital=INITIAL_CAPITAL,
        commission_rate=COMMISSION,
        commission_min_eur=COMMISSION_MIN_EUR,
        slippage_pct=SLIPPAGE,
        position_fraction=position_fraction,
        max_positions=max_positions,
        min_hold_bars=MIN_HOLD_BARS if name == "experiment_strategy" or name == "fold" else 0,
    )
    # SPY B&H: single name — no max-position / min-hold constraints
    if name == "buy_hold_spy":
        bt.max_positions = 0
        bt.min_hold_bars = 0
    result = bt.backtest(data, fn)
    metrics = result.calculate_metrics()
    metrics["fees_pct"] = estimate_fees_pct(result.trades)
    # Prefer last finite equity-curve point for return
    final = None
    for eq in reversed(result.equity_curve or []):
        try:
            v = float(eq)
        except (TypeError, ValueError):
            continue
        if math.isfinite(v):
            final = v
            break
    if final is not None and INITIAL_CAPITAL > 0:
        metrics["total_return_pct"] = (final / INITIAL_CAPITAL - 1.0) * 100.0
    ret = metrics.get("total_return_pct")
    if ret is None or not math.isfinite(float(ret)):
        metrics["total_return_pct"] = 0.0
    metrics["val_score"] = benchmark_score(metrics)
    metrics["name"] = name
    return metrics


def _wf_blend(data, fn, *, position_fraction: float, max_positions: int = 0) -> tuple[float, float, float]:
    """Walk-forward blend matching scripts/run_experiment.py."""

    def fold_score(fold: Dict[str, List[Dict]]) -> float:
        return float(
            _run(
                "fold",
                fold,
                fn,
                position_fraction=position_fraction,
                max_positions=max_positions,
            )["val_score"]
        )

    mean, scores = walk_forward_val_score(data, fold_score, n_folds=3, min_bars=80)
    worst = min(scores) if scores else -100.0
    blend = 0.75 * mean + 0.25 * worst
    if blend != blend:
        blend = -100.0
    return blend, mean, worst


def main() -> int:
    symbols = list(DEFAULT_SYMBOLS)
    data = load_bars(symbols)

    # Sanity: make_backtester matches strategy path
    _ = make_backtester()

    rows = [
        _run(
            "experiment_strategy",
            data,
            strategy_signals,
            position_fraction=POSITION_FRACTION,
            max_positions=MAX_POSITIONS,
        ),
        _run("buy_hold_spy", data, buy_and_hold_spy, position_fraction=0.99),
        run_equal_weight_buy_hold(data),
    ]
    strat_wf, strat_mean, strat_min = _wf_blend(
        data,
        strategy_signals,
        position_fraction=POSITION_FRACTION,
        max_positions=MAX_POSITIONS,
    )
    spy_wf, spy_mean, spy_min = _wf_blend(
        data, buy_and_hold_spy, position_fraction=0.99, max_positions=0
    )

    print("--- benchmark ---")
    print(
        f"harness: fee_preset={FEE_PRESET} rate={COMMISSION} min_eur={COMMISSION_MIN_EUR} "
        f"free_legs={FREE_LEGS_PER_MONTH} "
        f"max_positions={MAX_POSITIONS} min_hold_bars={MIN_HOLD_BARS}"
    )
    for m in rows:
        print(
            f"{m['name']}: full_score={m['val_score']:.6f} "
            f"ret={m['total_return_pct']:.4f}% dd={m['max_drawdown']:.4f}% "
            f"sharpe={m['sharpe_ratio']:.4f} trades={m['total_trades']} fees={m['fees_pct']:.4f}%"
        )
    print(
        f"experiment_strategy_wf: blend={strat_wf:.6f} mean={strat_mean:.6f} min={strat_min:.6f}"
    )
    print(f"buy_hold_spy_wf: blend={spy_wf:.6f} mean={spy_mean:.6f} min={spy_min:.6f}")

    beats_spy_full = rows[0]["val_score"] > rows[1]["val_score"]
    beats_ew_full = rows[0]["val_score"] > rows[2]["val_score"]
    beats_spy_wf = strat_wf > spy_wf
    print("---")
    print(f"beats_buy_hold_spy_full: {str(beats_spy_full).lower()}")
    print(f"beats_buy_hold_equal_weight_full: {str(beats_ew_full).lower()}")
    print(f"beats_buy_hold_spy_walkforward: {str(beats_spy_wf).lower()}")
    # Promote gate uses walk-forward vs SPY under live-shaped fees
    if beats_spy_wf and beats_spy_full and beats_ew_full:
        print("verdict: strategy_beats_baselines (offline only; not live proof)")
    elif beats_spy_wf:
        print("verdict: beats_spy_walkforward_only (do not promote yet)")
    elif beats_spy_full or beats_ew_full:
        print("verdict: mixed_vs_baselines (do not promote yet)")
    else:
        print("verdict: underperforms_baselines (keep researching; do not promote)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
