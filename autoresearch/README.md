# Autoresearch (stock-checker edition)

Overnight keep/revert loop inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch).

- **Human edits:** `program.md`
- **Agent / Ollama edits:** `../stock_checker/experiment_strategy.py` only
- **Harness:** `../scripts/run_experiment.py` (fixed ~120s budget, `val_score` higher=better)
- **Log:** `results.tsv` (gitignored)

## Local Ollama (recommended overnight)

Zero Cursor tokens — Ollama proposes the next strategy file; Docker scores it.

**Night window only:** experiments run **23:00–08:00** in the **host local timezone** (`ASC_LOCAL_TZ` / `OLLAMA_AUTOSEARCH_TZ` / system). The loop process can stay up all day; it sleeps until the window opens. Manual daytime run: `OLLAMA_AUTOSEARCH_FORCE=1`.

```bash
./scripts/run_ollama_autoresearch_once.sh
./scripts/run_ollama_autoresearch_loop.sh   # ticks every 8m inside the night window
```

Model default: `gemma4:latest` (`OLLAMA_AUTOSEARCH_MODEL`). Set `OLLAMA_AUTOSEARCH_PUSH=1` to push keeps. See [MODELS.md](../MODELS.md).

Env overrides: `OLLAMA_AUTOSEARCH_NIGHT_START` (default 23), `OLLAMA_AUTOSEARCH_NIGHT_END` (default 8), `OLLAMA_AUTOSEARCH_TZ` or `ASC_LOCAL_TZ` (default = system local).

## Cursor agent loop

Still works via `AGENT_LOOP_TICK_autoresearch` (see `AGENTS.md`) — uses cloud tokens. Do not run both loops together.

Review `results.tsv` in the morning (local TZ).
