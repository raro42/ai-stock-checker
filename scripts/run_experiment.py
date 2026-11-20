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
from stock_checker.fees import (
    DEFAULT_FEE_PRESET,
    FeeAllowanceLedger,
    _coerce_fee_money,
    free_legs_for_preset,
    rates_for_preset,
)
from stock_checker.portfolio import fill_price_ok, long_only_quantity_ok
from stock_checker.technical_indicators import (
    _finite_signed,
    coerce_nonneg_int,
    coerce_ohlcv_bar,
)
from stock_checker.walk_forward import coerce_fold_score, walk_forward_val_score

# Live-shaped harness (match Ops / paper desk defaults — do not soften overnight)
TIME_BUDGET_SEC = 120  # wall-clock compute budget inside the experiment
DATA_DIR = Path("data/experiment_bars")
DEFAULT_SYMBOLS = ["SPY", "QQQ", "IWM", "GLD", "AAPL", "MSFT", "NVDA", "JNJ"]
INITIAL_CAPITAL = 100_000.0
FEE_PRESET = DEFAULT_FEE_PRESET  # revolut_standard
COMMISSION, COMMISSION_MIN_EUR = rates_for_preset(FEE_PRESET)
FREE_LEGS_PER_MONTH = free_legs_for_preset(FEE_PRESET)
SLIPPAGE = 0.0005
MAX_POSITIONS = 5
# Daily bars ≈ 24h min hold → 1 bar; position size fills up to max book
MIN_HOLD_BARS = 1
POSITION_FRACTION = 1.0 / MAX_POSITIONS


def make_backtester() -> Backtester:
    """Backtester configured like paper Ops (Revolut fees + book caps)."""
    return Backtester(
        initial_capital=INITIAL_CAPITAL,
        commission_rate=COMMISSION,
        commission_min_eur=COMMISSION_MIN_EUR,
        slippage_pct=SLIPPAGE,
        position_fraction=POSITION_FRACTION,
        max_positions=MAX_POSITIONS,
        min_hold_bars=MIN_HOLD_BARS,
        free_legs_per_month=FREE_LEGS_PER_MONTH,
    )


def estimate_fees_pct(trades, *, capital: float = INITIAL_CAPITAL) -> float:
    """Round-trip fee estimate with monthly free-leg allowance.

    tradermonty #700/#655 + xang1234/portfolio AI: refuse bool qty·price·capital
    so ``True→1`` share / ``True→€1`` fill / ``True→€1`` capital cannot invent
    fee burn into ``val_score`` (parity with paper fill + backtester refuse).
    """
    cap = _coerce_fee_money(capital)
    if not trades or cap is None or cap <= 0:
        return 0.0
    ledger = FeeAllowanceLedger(FREE_LEGS_PER_MONTH)
    fees = 0.0
    for t in trades:
        if not long_only_quantity_ok(getattr(t, "shares", None)):
            continue
        if not fill_price_ok(getattr(t, "entry_price", None)):
            continue
        shares = float(t.shares)
        entry_px = float(t.entry_price)
        entry = abs(shares * entry_px)
        entry_ts = t.entry_time.strftime("%Y-%m-%d") if hasattr(t, "entry_time") else ""
        exit_ts = t.exit_time.strftime("%Y-%m-%d") if hasattr(t, "exit_time") else entry_ts
        fees += ledger.commission_for_leg(
            entry, entry_ts, rate=COMMISSION, min_eur=COMMISSION_MIN_EUR
        )
        exit_px = getattr(t, "exit_price", None)
        if fill_price_ok(exit_px):
            exit_ = abs(shares * float(exit_px))
            fees += ledger.commission_for_leg(
                exit_, exit_ts, rate=COMMISSION, min_eur=COMMISSION_MIN_EUR
            )
        else:
            fees += ledger.commission_for_leg(
                entry, exit_ts, rate=COMMISSION, min_eur=COMMISSION_MIN_EUR
            )
    pct = fees / cap * 100.0
    return pct if pct == pct else 0.0

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
                if not isinstance(row, dict):
                    continue
                dt = row.get("date")
                if isinstance(dt, str):
                    try:
                        dt = datetime.fromisoformat(dt)
                    except ValueError:
                        continue
                bar = coerce_ohlcv_bar(
                    open_=row.get("open"),
                    high=row.get("high"),
                    low=row.get("low"),
                    close=row.get("close"),
                    volume=row.get("volume"),
                    date=dt,
                )
                if bar is not None:
                    bars.append(bar)
            if bars:
                out[symbol] = bars
            else:
                missing.append(symbol)
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
                    # Prefer raw Volume (None→0); never ``or 0`` (True→1).
                    vol = row["Volume"] if "Volume" in row.index else None
                    bar = coerce_ohlcv_bar(
                        open_=row["Open"],
                        high=row["High"],
                        low=row["Low"],
                        close=row["Close"],
                        volume=vol,
                        date=dt,
                    )
                    if bar is None:
                        continue
                    bars.append(bar)
                    serializable.append({**bar, "date": dt.isoformat()})
                if not bars:
                    out[symbol] = _synthetic_bars(symbol)
                    continue
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

    tradermonty #700/#655 + xang1234/portfolio AI: refuse bool metrics so
    ``True→1.0`` Sharpe / ``True→1`` trade / ``True→1%`` fees cannot invent
    a keepable ``val_score`` after backtester knob refuse.
    """
    def _f(key: str, default: float = 0.0) -> float:
        raw = metrics.get(key, default) if isinstance(metrics, dict) else default
        if not _finite_signed(raw):
            return default
        return float(raw)  # type: ignore[arg-type]

    sharpe = _f("sharpe_ratio")
    dd = _f("max_drawdown")  # already in %
    ret = _f("total_return_pct")
    trades_n = coerce_nonneg_int(
        metrics.get("total_trades", 0) if isinstance(metrics, dict) else 0
    )
    trades = 0 if trades_n is None else trades_n
    fees_pct = _f("fees_pct")

    if trades < 2:
        return -100.0  # inactive strategy is a failure

    score = sharpe * 10.0 + ret * 0.05 - dd * 0.15 - fees_pct * 0.5
    return coerce_fold_score(score)


def _metrics_for_bars(bt: Backtester, data: Dict[str, List[Dict]]) -> dict:
    result = bt.backtest(data, generate_signals)
    metrics = result.calculate_metrics()
    metrics["fees_pct"] = estimate_fees_pct(result.trades)
    return metrics


def _buy_and_hold_spy(bars_by_symbol, index, portfolio):
    """All-in SPY once; hold forever (keep-gate baseline)."""
    if "SPY" not in bars_by_symbol:
        return {}
    if "SPY" in portfolio.get("positions", {}):
        return {}
    if index < 1:
        return {}
    return {"SPY": "BUY"}


def _spy_walkforward_blend(data: Dict[str, List[Dict]]) -> float:
    """SPY buy-and-hold WF blend on the same bars (live-shaped fees)."""
    bt = Backtester(
        initial_capital=INITIAL_CAPITAL,
        commission_rate=COMMISSION,
        commission_min_eur=COMMISSION_MIN_EUR,
        slippage_pct=SLIPPAGE,
        position_fraction=0.99,
        max_positions=0,
        min_hold_bars=MIN_HOLD_BARS,
    )

    def fold_score(fold_data: Dict[str, List[Dict]]) -> float:
        result = bt.backtest(fold_data, _buy_and_hold_spy)
        metrics = result.calculate_metrics()
        metrics["fees_pct"] = estimate_fees_pct(result.trades)
        # Allow single round-trip (buy-and-hold); still refuse bool meters.
        def _f(key: str, default: float = 0.0) -> float:
            raw = metrics.get(key, default)
            if not _finite_signed(raw):
                return default
            return float(raw)  # type: ignore[arg-type]

        score = (
            _f("sharpe_ratio") * 10.0
            + _f("total_return_pct") * 0.05
            - _f("max_drawdown") * 0.15
            - _f("fees_pct") * 0.5
        )
        return coerce_fold_score(score)

    wf_score, fold_scores = walk_forward_val_score(data, fold_score, n_folds=3, min_bars=80)
    worst = min(fold_scores) if fold_scores else -100.0
    blend = 0.75 * wf_score + 0.25 * worst
    return blend if blend == blend else -100.0


def run() -> int:
    t0 = time.time()
    symbols = list(DEFAULT_SYMBOLS)
    data = load_bars(symbols)

    bt = make_backtester()

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

    spy_wf = _spy_walkforward_blend(data)
    beats_spy = best_score > spy_wf

    elapsed = time.time() - t0
    runs = 1 + len(fold_scores)

    print("---")
    print(f"val_score:            {best_score:.6f}")
    print(f"wf_score_mean:        {wf_score:.6f}")
    print(f"wf_score_min:         {worst:.6f}")
    print(f"wf_fold_scores:       {','.join(f'{s:.4f}' for s in fold_scores)}")
    print(f"spy_wf_blend:         {spy_wf:.6f}")
    print(f"beats_buy_hold_spy_walkforward: {str(beats_spy).lower()}")
    print(f"total_return_pct:     {full_metrics['total_return_pct']:.6f}")
    print(f"max_drawdown_pct:     {full_metrics['max_drawdown']:.6f}")
    print(f"sharpe_ratio:         {full_metrics['sharpe_ratio']:.6f}")
    print(f"total_trades:         {full_metrics['total_trades']}")
    print(f"win_rate:             {full_metrics['win_rate']:.6f}")
    print(f"fees_pct:             {full_metrics.get('fees_pct', 0):.6f}")
    print(f"fee_preset:           {FEE_PRESET}")
    print(f"commission_rate:      {COMMISSION}")
    print(f"commission_min_eur:   {COMMISSION_MIN_EUR}")
    print(f"free_legs_per_month:  {FREE_LEGS_PER_MONTH}")
    print(f"max_positions:        {MAX_POSITIONS}")
    print(f"min_hold_bars:        {MIN_HOLD_BARS}")
    print(f"experiment_seconds:   {elapsed:.1f}")
    print(f"runs:                 {runs}")
    print(f"symbols:              {','.join(symbols)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(run())
