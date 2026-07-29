# AI Stock Checker — for friends

Short path to share signals and paper-trade together.

Repo: https://github.com/raro42/ai-stock-checker

## 1. Install

- Docker Desktop
- Optional LLM: [Ollama](https://ollama.com) **or** a free Groq/OpenRouter key ([MODELS.md](MODELS.md))
- Optional: free [Finnhub](https://finnhub.io) API key

## 2. Configure

```bash
git clone https://github.com/raro42/ai-stock-checker.git
cd ai-stock-checker
cp .env.example .env
# Defaults: AI_MODE=off (no LLM needed). Paper desk still works.
# Optional: FINNHUB_API_KEY=...
# Optional cloud AI (no local Ollama):
#   AI_MODE=validate
#   LLM_BACKEND=openai
#   OPENAI_API_KEY=...
#   OPENAI_BASE_URL=https://api.groq.com/openai/v1
#   AI_MODEL=llama-3.1-8b-instant
```

## 3. Run paper trader (+ OpenBB widgets)

```bash
docker compose up -d --build intelligent-trader openbb-backend
docker compose logs -f --tail 50 intelligent-trader openbb-backend
```

Defaults avoid fee-burn: 15m scans, 5m checks, **4h minimum hold**.
Paper fees default to **Revolut-like 0.25%/side · €1 min** (change on Ops).

Paper desk UI: [http://127.0.0.1:7779/desk](http://127.0.0.1:7779/desk) (Overview / Charts / Screener / Breadth / Book / Ideas / Ops) · Design: [DESIGN.md](DESIGN.md) · OpenBB widgets: same host — see [OPENBB.md](OPENBB.md).

## 4. Useful commands

```bash
# Portfolio / fee summary (host)
python3 scripts/summarize_trades.py --trades data/trades.jsonl

# Fresh start (€10k) — use when startup warns about fee burn
python3 scripts/reset_paper_portfolio.py --capital 10000

# Strategy vs buy-and-hold (offline; do not trust until it beats SPY)
./scripts/run_benchmark_buy_hold.sh

# One-off check
docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli info AAPL

# Backtest
docker run --rm --network host ai-stock-checker \
  python3 -m stock_checker.cli backtest AAPL -p 1y

# Docs / health hygiene
./scripts/healthcheck.sh
./scripts/docs_weekly_check.sh
```

## If the trader warns about fees

On startup you may see `High fee burn: …`. That means the old paper book churned too hard.

1. Stop: `docker compose stop intelligent-trader`
2. Reset: `python3 scripts/reset_paper_portfolio.py --capital 10000`
3. Start again: `docker compose up -d intelligent-trader`
4. Keep the **4h min hold** — do not “fix” fees by trading faster.

## Rules of the group

1. Paper trade only until a strategy survives **walk-forward vs SPY under live-shaped fees** **and** a calm paper month.
2. Do not paste API keys in chat — use `.env`.
3. Prefer boring holdings over meme churn (current fresh book: **WMT** + cash).
4. If fees > realized edge, slow down or reset:

```bash
KEEP_SYMBOLS=WMT RESET_CAPITAL=100000 ./scripts/fresh_start_keep.sh
```

5. Health anytime: `./scripts/healthcheck.sh`

History summaries land in `docs/history/` (committed). Full JSONL backups stay in `data/backup_*`.

As of **2026-07-29**: offline walk-forward **beats SPY** under Revolut-standard fees (0.25%/side · €1 min, max 5 positions). Ops can enable **Promote champion entry filter** so scanner buys also pass `experiment_strategy` rules. That is **not** live proof yet — keep paper, watch fees, wait a calm month before treating it as the group default.