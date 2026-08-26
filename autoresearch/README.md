# Autoresearch (Karpathy-style overnight)

Overnight keep/revert loop inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch).

- **Human edits:** `program.md`
- **Agent / Ollama edits:** `../stock_checker/experiment_strategy.py` only
- **Harness:** `../scripts/run_experiment.py` (backtest ≈ **1s**; legacy 120s label is not the real runtime)
- **Log:** `results.tsv` (gitignored)

## Speed (honest math)

| Bottleneck | Typical | Notes |
|------------|---------|--------|
| Backtest + walk-forward | **~0.3–1s** | Not the limit |
| Ollama rewrite | **30s–5m** | Model + prompt size |
| Loop interval (old) | **+8m idle after each tick** | Capped ~60 ideas / 9h night |
| Loop interval (now) | **120s net** default | Work time counts toward interval |

One idea is **one tick**, not an 8-hour job. The night window runs **many** ticks.

| Mode | Command | Rough throughput |
|------|---------|------------------|
| Night Ollama | `./scripts/run_ollama_autoresearch_loop.sh` | ~200–400 / night if model is fast |
| **2h sprint** | `./scripts/run_ollama_autoresearch_sprint.sh` | denser (45s net, FORCE=1) |
| **100× volume** | `./scripts/run_param_autoresearch_loop.sh` | ~500–1000 / 2h (no LLM; param grid) |

Never run Ollama + param loops together (git race on `experiment_strategy.py`).

Host score (skip Docker cold path): `AUTOSEARCH_HOST_SCORE=1` (param loop default on).

## Local Ollama (recommended overnight)

Zero Cursor tokens — Ollama proposes the next strategy file; Docker (or host) scores it.

**Night window only:** experiments run **23:00–08:00** in the **host local timezone** (`ASC_LOCAL_TZ` / `OLLAMA_AUTOSEARCH_TZ` / system). The loop process can stay up all day; it sleeps until the window opens. Manual daytime run: `OLLAMA_AUTOSEARCH_FORCE=1`.

```bash
./scripts/run_ollama_autoresearch_once.sh
./scripts/run_ollama_autoresearch_loop.sh      # ~120s net ticks inside night window
./scripts/run_ollama_autoresearch_sprint.sh    # fixed 2h burst (default)
./scripts/run_param_autoresearch_loop.sh      # no Ollama; mutate knobs from grid
```

Model default: `gemma4:latest` (`OLLAMA_AUTOSEARCH_MODEL`). Set `OLLAMA_AUTOSEARCH_PUSH=1` to push keeps. See [MODELS.md](../MODELS.md).

Env overrides: `OLLAMA_AUTOSEARCH_NIGHT_START` (default 23), `OLLAMA_AUTOSEARCH_NIGHT_END` (default 8), `OLLAMA_AUTOSEARCH_TZ` or `ASC_LOCAL_TZ` (default = system local), `OLLAMA_AUTOSEARCH_INTERVAL_SEC` (default 120), `OLLAMA_AUTOSEARCH_SPRINT_SEC` (default 7200).

## Cursor agent loop

Still works via `AGENT_LOOP_TICK_autoresearch` (see `AGENTS.md`) — uses cloud tokens. Do not run both loops together.

Review `results.tsv` in the morning (local TZ).
