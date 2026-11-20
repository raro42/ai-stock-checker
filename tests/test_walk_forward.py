"""Tests for walk-forward harness helpers."""

from scripts.run_experiment import compute_val_score, estimate_fees_pct
from stock_checker.walk_forward import (
    aggregate_fold_scores,
    coerce_fold_score,
    slice_walk_forward,
    walk_forward_val_score,
)


def test_slice_three_folds():
    bars = {"A": [{"close": float(i)} for i in range(300)]}
    folds = slice_walk_forward(bars, n_folds=3, min_bars=80)
    assert len(folds) == 3
    assert sum(len(f["A"]) for f in folds) == 300


def test_slice_falls_back_when_short():
    bars = {"A": [{"close": 1.0} for _ in range(50)]}
    folds = slice_walk_forward(bars, n_folds=3, min_bars=80)
    assert len(folds) == 1


def test_aggregate_fold_scores():
    mean, mn, mx = aggregate_fold_scores([1.0, 3.0, 5.0])
    assert mean == 3.0
    assert mn == 1.0
    assert mx == 5.0


def test_slice_refuses_bool_fold_knobs():
    """tradermonty #700/#655: True→1 must not invent a one-bar / one-fold WF."""
    bars = {"A": [{"close": float(i)} for i in range(300)]}
    # Bool folds → single window (not True→1 fold-len math).
    assert len(slice_walk_forward(bars, n_folds=True, min_bars=80)) == 1
    # Bool min_bars → default 80; still three real folds.
    assert len(slice_walk_forward(bars, n_folds=3, min_bars=True)) == 3
    assert len(slice_walk_forward(bars, n_folds=False, min_bars=False)) == 1


def test_coerce_fold_score_refuses_bool():
    assert coerce_fold_score(True) == -100.0
    assert coerce_fold_score(False) == -100.0
    assert coerce_fold_score(2.5) == 2.5


def test_walk_forward_val_score_refuses_bool_fold_return():
    bars = {"A": [{"close": 1.0} for _ in range(100)]}
    mean, scores = walk_forward_val_score(bars, lambda _d: True, n_folds=2, min_bars=40)
    assert mean == -100.0
    assert scores == [-100.0] or all(s == -100.0 for s in scores)


def test_aggregate_drops_bool_scores():
    mean, mn, mx = aggregate_fold_scores([1.0, True, 5.0])
    assert mean == 3.0
    assert mn == 1.0
    assert mx == 5.0


def test_compute_val_score_refuses_bool_metrics():
    """True→1.0 Sharpe / True→1 trade must not invent a keepable val_score."""
    # Bool trades → inactive fail (not True→1 activity).
    assert compute_val_score({"sharpe_ratio": 2.0, "total_trades": True}) == -100.0
    # Bool sharpe → treated as 0; real trades still score from other meters.
    score = compute_val_score(
        {
            "sharpe_ratio": True,
            "max_drawdown": 0.0,
            "total_return_pct": 0.0,
            "fees_pct": 0.0,
            "total_trades": 5,
        }
    )
    assert score == 0.0
    # Healthy path still works.
    ok = compute_val_score(
        {
            "sharpe_ratio": 1.0,
            "max_drawdown": 10.0,
            "total_return_pct": 20.0,
            "fees_pct": 2.0,
            "total_trades": 5,
        }
    )
    assert ok == 1.0 * 10.0 + 20.0 * 0.05 - 10.0 * 0.15 - 2.0 * 0.5


class _BadTrade:
    def __init__(self, shares, entry_price, exit_price):
        self.shares = shares
        self.entry_price = entry_price
        self.exit_price = exit_price
        self.entry_time = None
        self.exit_time = None


def test_estimate_fees_pct_refuses_bool_fills():
    """True→1 share / True→€1 price must not invent fee burn into val_score."""
    assert estimate_fees_pct([_BadTrade(True, 100.0, 110.0)]) == 0.0
    assert estimate_fees_pct([_BadTrade(10.0, True, 110.0)]) == 0.0
    assert estimate_fees_pct([_BadTrade(10.0, 100.0, 110.0)], capital=True) == 0.0
