"""Tests for walk-forward harness helpers."""

from stock_checker.walk_forward import aggregate_fold_scores, slice_walk_forward


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
