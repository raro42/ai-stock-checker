"""Walk-forward style OOS slices for autoresearch (freqtrade/vectorbt-inspired)."""

from __future__ import annotations

from typing import Callable, Dict, List, Tuple

from stock_checker.technical_indicators import _finite_signed, coerce_nonneg_int

_DEFAULT_FOLDS = 3
_DEFAULT_MIN_BARS = 80
_FAIL_SCORE = -100.0


def _coerce_folds(n_folds: object) -> int:
    """Fold count ≥2, or 1 (single window). Bool/gap → single (never ``True→1`` fold math)."""
    n = coerce_nonneg_int(n_folds)
    if n is None or n < 2:
        return 1
    return n


def _coerce_min_bars(min_bars: object) -> int:
    """Min bars per fold; bool/gap → default 80 (never ``True→1`` thin fold)."""
    n = coerce_nonneg_int(min_bars)
    return _DEFAULT_MIN_BARS if n is None else n


def coerce_fold_score(raw: object) -> float:
    """Finite fold score, or fail sentinel when bool/gap/NaN (never ``True→1.0``)."""
    if not _finite_signed(raw):
        return _FAIL_SCORE
    return float(raw)  # type: ignore[arg-type]


def slice_walk_forward(
    bars_by_symbol: Dict[str, List[dict]],
    *,
    n_folds: int = _DEFAULT_FOLDS,
    min_bars: int = _DEFAULT_MIN_BARS,
) -> List[Dict[str, List[dict]]]:
    """
    Split aligned bars into contiguous out-of-sample folds (no fit step).

    Strategies here are rule-based (no train params), so each fold is pure OOS.

    tradermonty #700/#655 + xang1234/portfolio AI: refuse bool fold knobs so
    ``True→1`` cannot invent a one-bar / one-fold walk-forward.
    """
    folds_n = _coerce_folds(n_folds)
    bars_need = _coerce_min_bars(min_bars)
    if folds_n < 2:
        return [bars_by_symbol]
    symbols = list(bars_by_symbol.keys())
    if not symbols:
        return []
    min_len = min(len(bars_by_symbol[s]) for s in symbols)
    fold_len = min_len // folds_n
    if fold_len < bars_need:
        # Not enough history — single full window
        return [bars_by_symbol]

    folds: List[Dict[str, List[dict]]] = []
    for i in range(folds_n):
        start = i * fold_len
        end = (i + 1) * fold_len if i < folds_n - 1 else min_len
        if end - start < bars_need:
            continue
        folds.append({s: bars_by_symbol[s][start:end] for s in symbols})
    return folds or [bars_by_symbol]


def aggregate_fold_scores(scores: List[float]) -> Tuple[float, float, float]:
    """Return (mean, min, max). Empty → (-100, -100, -100). Bool scores dropped."""
    clean = [coerce_fold_score(s) for s in scores if _finite_signed(s)]
    if not clean:
        return _FAIL_SCORE, _FAIL_SCORE, _FAIL_SCORE
    return sum(clean) / len(clean), min(clean), max(clean)


def walk_forward_val_score(
    bars_by_symbol: Dict[str, List[dict]],
    backtest_fn: Callable[[Dict[str, List[dict]]], float],
    *,
    n_folds: int = _DEFAULT_FOLDS,
    min_bars: int = _DEFAULT_MIN_BARS,
) -> Tuple[float, List[float]]:
    """
    Score = mean of per-fold scores (robustness over peak in-sample).

    `backtest_fn` maps a bars dict → scalar val_score for that window.

    tradermonty #700/#655: bool fold returns cannot invent ``True→1.0`` mean.
    """
    folds = slice_walk_forward(bars_by_symbol, n_folds=n_folds, min_bars=min_bars)
    scores = [coerce_fold_score(backtest_fn(fold)) for fold in folds]
    mean, _, _ = aggregate_fold_scores(scores)
    return mean, scores
