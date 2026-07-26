# AI Stock Checker

Local, Docker-first stock and crypto checker with paper trading and optional Ollama AI.

**Started October 2025** (paper trading through Nov–Dec 2025; revived and hardened July 2026).

Built for a small group of friends: **honest signals, low churn, fees-aware**, validated before going aggressive.

## Features

- **Intelligent trader**: scan markets → rank opportunities → paper trade with persistence
- **Anti-churn defaults**: ≥4h min hold, 15m scans, 5m trade checks (fees are 0.1%/side)
- **Symbol filters**: drop stablecoins, leveraged tokens, and known noise
- **AI modes**: `off` (rules), `validate` (AI gates high-conviction ideas), `full` (AI-led)
- **Multi-factor scoring**: momentum, technicals, fundamentals, volume/sentiment
- **Earnings blackout**: skip new entries near earnings when Finnhub has dates
- **Paper desk UI**: browser UI at `http://127.0.0.1:7779/desk` (equity, holdings, fills)
- **OpenBB backend**: FastAPI widgets on `:7779` (portfolio / trades / opportunities)
- **Backtester**: OHLCV long-only simulation with commission + slippage
- **Autoresearch**: overnight strategy loop on `experiment_strategy.py` (see `autoresearch/`)
- **CLI**: one-off info, history, Bitcoin, S&P movers
- **Archive**: opportunity lists saved when the US market is closed

## Quick Start

### Prerequisites

- Docker (or Podman)
- Optional: [Ollama](https://ollama.com) + an **instruct** model (`gemma4:latest`, `qwen3.5:9b`, … — not coder models)
- Optional: [Finnhub](https://finnhub.io) free API key for richer quotes

### Configure secrets

```bash
cp .env.example .env
# edit .env — set FINNHUB_API_KEY and AI_MODEL
```

Finnhub: free key at [finnhub.io](https://finnhub.io) (≈60 calls/min on free tier). Leave blank to use yfinance only.

### Paper trading (recommended)

```bash
docker compose up -d --build intelligent-trader openbb-backend
docker compose logs -f --tail 50 intelligent-trader openbb-backend
```

Data persists in `./data/` (`portfolio.json`, `trades.jsonl`, archives). This directory is gitignored.

Paper desk: [http://127.0.0.1:7779/desk](http://127.0.0.1:7779/desk) · OpenBB widgets: same host — see [OPENBB.md](OPENBB.md).

Defaults (anti-churn):

| Setting | Default |
|---------|---------|
| Capital | €100,000 |
| Scan interval | 900s (15m) |
| Trade interval | 300s (5m) |
| Min hold | 14400s (4h) |
| Max positions | 8 |
| AI mode | validate |
| AI model | `gemma4:latest` (override with `AI_MODEL` in `.env`) |

### Monitor only (no trades)

```bash
docker compose --profile monitor up -d monitor
docker logs -f ai-stock-monitor
```

### One-off CLI

```bash
docker build -t ai-stock-checker .
docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli info AAPL
docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli info AAPL --analyze
docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli history TSLA -p 1mo
docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli bitcoin --analyze
docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli movers -l 10
```

### Tests

```bash
docker build -t ai-stock-checker .
docker run --rm ai-stock-checker pytest -q
```

### Backtest a symbol

```bash
docker run --rm --network host ai-stock-checker \
  python3 -m stock_checker.cli backtest AAPL MSFT -p 1y
```

### Reset paper portfolio (fresh €10k)

```bash
python3 scripts/reset_paper_portfolio.py --capital 10000
# or inside Docker with ./data mounted
```

### For friends

See [FRIENDS.md](FRIENDS.md) — shortest path to run together.

Public repo: https://github.com/raro42/ai-stock-checker

## Project layout

```
stock_checker/
  intelligent_trader.py   # primary paper-trading loop
  market_scanner.py       # opportunity scan + market-hours archive
  symbol_filters.py       # stables / leveraged / noise filters
  recommender.py          # multi-factor scoring
  earnings_guard.py       # earnings blackout
  fee_burn.py             # startup fee-churn warning
  technical_indicators.py # RSI (Wilder), MACD, Bollinger, ATR
  backtester.py           # OHLCV backtests + metrics
  experiment_strategy.py  # autoresearch editable strategy
  portfolio.py / persistence.py
  ai_recommender.py / ai_analyzer.py
  fetcher.py / finnhub_fetcher.py / binance_fetcher.py
  cli.py / monitor.py / paper_trader.py
openbb_backend/           # FastAPI widgets for OpenBB Pro
autoresearch/             # overnight strategy search program
scripts/                  # healthcheck, summarize, docs weekly, reset
tests/                    # offline unit tests preferred
IMPROVEMENT.md            # agent backlog
DOCS_MAINTENANCE.md       # weekly docs checklist
AGENTS.md                 # coding + product rules for agents
```

## Strategy notes

- Momentum and technicals matter, but **turnover kills** at 0.1% fees.
- Crypto is limited (`--top-crypto-count`, default 2) and filtered.
- Prefer backtesting rule changes before tightening AI or live loops.
- Docs must not claim Sharpe/win-rate gains without a saved backtest.
- **Promote rule (2026-07-26):** experiment strategies must beat SPY on **walk-forward** blend before changing live `intelligent_trader` defaults (full-sample alone is not enough).

## More detail

- [USAGE.md](USAGE.md) — CLI flags and examples
- [OPENBB.md](OPENBB.md) — OpenBB Pro + local widgets backend
- [GIT.md](GIT.md) — commit & push ASAP rules for humans and agents
- [MODELS.md](MODELS.md) — which Ollama model to use for trading vs autoresearch
- [AUTOPILOT.md](AUTOPILOT.md) — continuous improvement without waiting for prompts
- [GITHUB_WATCH.md](GITHUB_WATCH.md) — watch external screener/agent repos for ideas
- `./scripts/run_clean_code_agent.sh` — clean-code agent (slop review / safe fixes)
- [DOCS_MAINTENANCE.md](DOCS_MAINTENANCE.md) — weekly documentation loop
- [autoresearch/README.md](autoresearch/README.md) — strategy search overnight (Ollama worker or Cursor loop)
- [PAPER_TRADING.md](PAPER_TRADING.md) — paper trading deep dive (verify flags vs compose)
- [MONITORING.md](MONITORING.md) — monitor service
- [IMPROVEMENT.md](IMPROVEMENT.md) — what agents should do next

## Security

Never commit `.env` or API keys. Rotate any key that was previously checked into compose history.
