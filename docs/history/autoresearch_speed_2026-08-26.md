# Autoresearch speed (2026-08-26)

## Misconception

One idea does **not** run for 8 hours. Each idea is one tick (propose → score → keep/revert). The old loop then **slept 8 minutes**, so a 9h night capped ~60 ticks.

## Where time goes

| Step | Time |
|------|------|
| Walk-forward backtest | ~0.3–1s |
| Docker vs host score | both ~0.5s warm |
| Ollama rewrite | 30s–5m (real limit for LLM mode) |
| Idle after tick (old) | **+480s** (main waste) |

`TIME_BUDGET_SEC = 120` in the harness is a legacy ceiling label, not actual runtime.

## Efficiency levers (shipped)

1. **Net interval** — sleep only `INTERVAL - elapsed` (default interval **120s**).
2. **2h sprint** — `./scripts/run_ollama_autoresearch_sprint.sh` (45s net, FORCE=1).
3. **Param grid** — `./scripts/run_param_autoresearch_loop.sh` for ~100× volume without Ollama (knob mutations only).
4. **`AUTOSEARCH_HOST_SCORE=1`** — score with host Python (param loop default).

## 100× iterations

Ollama cannot deliver 100× overnight volume. Use the **param grid** for dense numeric search; keep Ollama for structural code ideas. Never run both loops at once.
