"""Walk-forward style OOS slices for autoresearch (freqtrade/vectorbt-inspired)."""

from __future__ import annotations

from typing import Callable, Dict, List, Tuple


def slice_walk_forward(
    bars_by_symbol: Dict[str, List[dict]],
    *,
    n_folds: int = 3,
    min_bars: int = 80,
) -> List[Dict[str, List[dict]]]:
    """
    Split aligned bars into contiguous out-of-sample folds (no fit step).

    Strategies here are rule-based (no train params), so each fold is pure OOS.
    """
    if n_folds < 2:
        return [bars_by_symbol]
    symbols = list(bars_by_symbol.keys())
    if not symbols:
        return []
    min_len = min(len(bars_by_symbol[s]) for s in symbols)
    fold_len = min_len // n_folds
    if fold_len < min_bars:
        # Not enough history — single full window
        return [bars_by_symbol]

    folds: List[Dict[str, List[dict]]] = []
    for i in range(n_folds):
        start = i * fold_len
        end = (i + 1) * fold_len if i < n_folds - 1 else min_len
        if end - start < min_bars:
            continue
        folds.append({s: bars_by_symbol[s][start:end] for s in symbols})
    return folds or [bars_by_symbol]


def aggregate_fold_scores(scores: List[float]) -> Tuple[float, float, float]:
    """Return (mean, min, max). Empty → (-100, -100, -100)."""
    if not scores:
        return -100.0, -100.0, -100.0
    return sum(scores) / len(scores), min(scores), max(scores)


def walk_forward_val_score(
    bars_by_symbol: Dict[str, List[dict]],
    backtest_fn: Callable[[Dict[str, List[dict]]], float],
    *,
    n_folds: int = 3,
    min_bars: int = 80,
) -> Tuple[float, List[float]]:
    """
    Score = mean of per-fold scores (robustness over peak in-sample).

    `backtest_fn` maps a bars dict → scalar val_score for that window.
    """
    folds = slice_walk_forward(bars_by_symbol, n_folds=n_folds, min_bars=min_bars)
    scores = [float(backtest_fn(fold)) for fold in folds]
    mean, _, _ = aggregate_fold_scores(scores)
    return mean, scores
