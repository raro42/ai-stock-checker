# Clean-code agent report — 2026-07-25

Mode: `apply` · model review: `gemma4:latest`

## Findings

- **ruff** (`open`) `.` — unused import/var findings:
F841 Local variable `sma_l` is assigned to but never used
   --> stock_checker/experiment_strategy.py:117:9
    |
115 |         sma_s = _sma(closes, SHORT_SMA)
116 |         sma_m = _sma(closes, MED_SMA)
117 |         sma_l = _sma(closes, LONG_SMA)
    |         ^^^^^
118 |         in_pos = symbol in portfolio.get("positions", {})
    |
help: Remove assignment to unused variable `sma_l`

Found 1 error.
No fixes available (1 hidden fix can be enabled with the `--unsafe-fixes` option).

- **ruff_fix** (`fixed`) `.` — F841 Local variable `sma_l` is assigned to but never used
   --> stock_checker/experiment_strategy.py:117:9
    |
115 |         sma_s = _sma(closes, SHORT_SMA)
116 |         sma_m = _sma(closes, MED_SMA)
117 |         sma_l = _sma(closes, LONG_SMA)
    |         ^^^^^
118 |         in_pos = symbol in portfolio.get("positions", {})
    |
help: Remove assignment to unused variable `sma_l`

Found 1 error.
No fixes available (1 hidden fix can be enabled with the `--unsafe-fixes` option).


## Next

- Re-run with `--apply` after dry-run review
- Keep trading log emoji (product voice); do not “sanitize” UX prints
