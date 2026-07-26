# Walk-forward re-baseline — 2026-07-26

After switching autoresearch `val_score` to walk-forward folds (`0.75*mean + 0.25*min`):

## Current strategy (`4f12af9`)

| Metric | Value |
|--------|-------|
| WF blend (experiment `val_score`) | **≈ 0.82–0.87** |
| WF mean / min | ≈ 3.07 / -5.72 |
| Full-sample score / sharpe / ret | ≈ 14.3 / 1.42 / +27% |

## vs buy-and-hold (aligned metrics)

| | Full-sample | Walk-forward blend |
|--|-------------|-------------------|
| experiment_strategy | ≈ 14.3 | ≈ **0.87** |
| buy_hold_spy | ≈ 8.4 | ≈ **7.06** |

**Verdict:** `mixed_vs_baselines` — wins full-sample, **loses walk-forward vs SPY**. Do **not** promote to live defaults.

## Autoresearch

Old keeps near `val_score≈9.6` are obsolete. New keep floor: beat **≈0.82** WF blend (row logged in `results.tsv`). Still must eventually beat SPY WF (~7) before promote.
