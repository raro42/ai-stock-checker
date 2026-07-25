# autoresearch — overnight strategy experiments (CEST)

Adapted from [karpathy/autoresearch](https://github.com/karpathy/autoresearch) for this paper-trading stock checker.

You are autonomous. The human may be asleep (CEST). **NEVER STOP** to ask permission once the loop has started. Continue until manually interrupted.

## Goal

Maximize **`val_score`** (higher is better) from walk-forward OOS folds
(`0.75 * mean_fold + 0.25 * worst_fold` — see `stock_checker/walk_forward.py`).
Pre-walk-forward keep scores are **not** comparable; beat the best keep **after** the harness change.

Maximize via:

```bash
docker run --rm -e PYTHONPATH=/app -w /app \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/stock_checker:/app/stock_checker" \
  -v "$(pwd)/scripts:/app/scripts" \
  ai-stock-checker \
  python3 scripts/run_experiment.py > autoresearch/run.log 2>&1
```
Or locally if deps exist:

```bash
python3 scripts/run_experiment.py > autoresearch/run.log 2>&1
```

Extract:

```bash
grep "^val_score:" autoresearch/run.log
```

## Files

| File | Role |
|------|------|
| `stock_checker/experiment_strategy.py` | **ONLY file you edit** |
| `scripts/run_experiment.py` | Read-only harness (time budget, data, metric) |
| `autoresearch/results.tsv` | Append-only log (do **not** git-commit this file) |
| `autoresearch/run.log` | Latest run output (gitignored) |

## Setup (once per overnight tag)

1. Agree tag from CEST date, e.g. `jul25`.
2. Branch: `git checkout -b autoresearch/<tag>` (or continue if already on it).
3. Ensure `results.tsv` header exists.
4. First experiment = **baseline** (run strategy as-is, record, status `keep`).

## Experiment loop (FOREVER)

1. Note current `git rev-parse --short HEAD` and best `val_score` so far from `results.tsv` (`keep` rows).
2. Edit **only** `stock_checker/experiment_strategy.py` with one clear idea (hyperparams and/or signal logic).
3. `git add stock_checker/experiment_strategy.py && git commit -m "exp: <short idea>"`
4. Run the experiment (redirect to `autoresearch/run.log`). Budget ≈ **120s** compute inside the harness; kill if wall clock > **10 minutes** and treat as crash.
5. `grep "^val_score:\|^total_return_pct:\|^max_drawdown_pct:\|^sharpe_ratio:\|^total_trades:" autoresearch/run.log`
6. If empty → crash: `tail -n 80 autoresearch/run.log`, try a small fix once or twice, else discard.
7. Append a row to `autoresearch/results.tsv` (tab-separated):

```
commit	val_score	status	description
```

8. If `val_score` **strictly improved** vs current best keep → status `keep` (leave commit).
9. If equal/worse/crash → status `discard` or `crash`, then:
   `git reset --hard <previous_keep_commit>`
10. Immediately start the next idea. Do not wait for the human.

## What you MAY change

- SMA periods, filters, exits, volatility gates, RSI/MACD-from-closes, multi-timeframe rules, symbol-agnostic logic inside `generate_signals`.
- Simplicity wins: equal score + simpler code → keep.

## What you MUST NOT do

- Edit `scripts/run_experiment.py`, portfolio live trader defaults, compose secrets, or install host packages.
- Claim live profitability; this is offline/cached bar research only.
- Reintroduce fee-blind hyper-churn (very short holds / huge trade counts that crush `val_score` via fees).
- Stop after N experiments or ask “should I continue?”

## Ideas when stuck

- Longer vs shorter SMA stacks
- Volume confirmation on/off
- Trend filter: only trade if SPY medium SMA rising (if SPY in universe)
- Volatility targeting: skip entries when recent true-range% high
- Asymmetric exit (faster cut, slower hold)
- Dual momentum: relative strength rank across symbols (still long-only)
- Combine near-miss keepers that almost won

## Local Ollama worker (save Cursor tokens)

Preferred for overnight when Ollama is up — **no Cursor agent tokens**:

```bash
# one experiment
./scripts/run_ollama_autoresearch_once.sh
# optional: push keeps
OLLAMA_AUTOSEARCH_PUSH=1 ./scripts/run_ollama_autoresearch_once.sh

# overnight loop (default every 480s)
./scripts/run_ollama_autoresearch_loop.sh
```

Env: `OLLAMA_HOST` (default `http://127.0.0.1:11434`), `OLLAMA_AUTOSEARCH_MODEL` (default `gemma4:latest`).

Do **not** run Cursor `AGENT_LOOP_TICK_autoresearch` and the Ollama loop at the same time (git races). Pick one.

## CEST overnight note

Human timezone is **CEST**. Prefer steady progress until morning. Log every run in `results.tsv` so breakfast review is easy.
