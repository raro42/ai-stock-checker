# Autoresearch (stock-checker edition)

Overnight keep/revert loop inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch).

- **Human edits:** `program.md`
- **Agent / Ollama edits:** `../stock_checker/experiment_strategy.py` only
- **Harness:** `../scripts/run_experiment.py` (fixed ~120s budget, `val_score` higher=better)
- **Log:** `results.tsv` (gitignored)

## Local Ollama (recommended overnight)

Zero Cursor tokens — Ollama proposes the next strategy file; Docker scores it:

```bash
./scripts/run_ollama_autoresearch_once.sh
./scripts/run_ollama_autoresearch_loop.sh   # every 8m until killed
```

Model default: `qwen2.5-coder:latest` (`OLLAMA_AUTOSEARCH_MODEL`). Set `OLLAMA_AUTOSEARCH_PUSH=1` to push keeps.

## Cursor agent loop

Still works via `AGENT_LOOP_TICK_autoresearch` (see `AGENTS.md`) — uses cloud tokens. Do not run both loops together.

Review `results.tsv` in the morning (CEST).
