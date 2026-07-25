# Autoresearch (stock-checker edition)

Overnight keep/revert loop inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch).

- **Human edits:** `program.md`
- **Agent edits:** `../stock_checker/experiment_strategy.py` only
- **Harness:** `../scripts/run_experiment.py` (fixed ~120s budget, `val_score` higher=better)
- **Log:** `results.tsv` (gitignored)

Start / resume with the Cursor overnight loop (see `AGENTS.md`). Review `results.tsv` in the morning (CEST).
