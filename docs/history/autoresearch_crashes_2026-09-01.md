# Autoresearch crash review — 2026-09-01

## GPU / runtime

- **Main GPU use:** host Ollama (`gemma4:latest`), not Docker trading containers.
- **Context:** model was loaded with **131k context** (~3.9 GB VRAM) even when the loop was idle.
- **Loop state (06:49 CEST):** outside night window; sleeping until 23:00 Europe/Berlin.
- **Action taken:** unloaded model via `keep_alive=0`; restarted `intelligent-trader` + `openbb-backend`.

## results.tsv (2469 rows)

| Status  | Count |
|---------|------:|
| discard | 2256  |
| crash   | 177   |
| keep    | 36    |

**Last 200 rows:** 175 discard, 25 crash, **0 keep**.

### Crash reasons (all time, heuristic)

| Count | Reason |
|------:|--------|
| 141 | Invalid / syntax proposal from Ollama (`(` never closed, bad Python) |
| 36 | Experiment harness failed (score −999) |

### Last night (Sep 1 ~04:38–04:46 UTC watchdog)

Repeated **`crash: experiment failed`** with:

```text
docker: pull access denied for ai-stock-checker
```

Root cause: no local `ai-stock-checker` Docker tag (only compose images like `ai-stock-checker-intelligent-trader`). Loop did not export `AUTOSEARCH_HOST_SCORE=1`, so backtests tried `docker run ai-stock-checker` and failed.

Host score (`AUTOSEARCH_HOST_SCORE=1`) was tried next. Host Python has no `numpy`. That path crashed from 2026-09-01 21:00Z through 2026-09-07 (`ModuleNotFoundError`). The Ollama loop does **not** export `AUTOSEARCH_HOST_SCORE`. The param loop still does.

## Same pull error again — 2026-09-08

`data/run_ollama_autoresearch_loop.log` shows `pull access denied` on every tick from 03:46Z through **04:14Z**. The 04:16Z tick scored again. Later nights score inside `/app` (the local image).

Checked 2026-09-20: local tag `ai-stock-checker:latest` exists. The pull error has not returned since 2026-09-08 04:14Z.

**Fix (2026-09-20):** `scripts/run_autoresearch_once.sh` builds `ai-stock-checker:latest` when the tag is missing. It does not pull from Docker Hub.

## Mitigations

1. **Daytime GPU:** loop already sleeps outside 23:00–05:00 Berlin; unload Ollama model when not experimenting.
2. **Syntax crashes:** prefer param grid (`run_param_autoresearch_loop.sh`) or filter-only idea families; gemma4 often emits broken Python.
3. **Docker path:** keep the local tag. Do not score the Ollama loop on host Python (no numpy).
4. **Single loop:** do not run Cursor autoresearch tick and Ollama loop together (git index.lock races).
