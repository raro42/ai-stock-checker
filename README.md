# AI Stock Checker

Local, Docker-first stock and crypto checker with paper trading and optional Ollama AI.

Built for a small group of friends: **honest signals, low churn, fees-aware**, validated before going aggressive.

## Features

- **Intelligent trader**: scan markets → rank opportunities → paper trade with persistence
- **Anti-churn defaults**: ≥4h min hold, 15m scans, 5m trade checks (fees are 0.1%/side)
- **Symbol filters**: drop stablecoins, leveraged tokens, and known noise
- **AI modes**: `off` (rules), `validate` (AI gates high-conviction ideas), `full` (AI-led)
- **Multi-factor scoring**: momentum, technicals, fundamentals, volume/sentiment
- **Backtester**: OHLCV long-only simulation with commission + slippage
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
docker compose up -d --build intelligent-trader
docker logs -f intelligent-trader
```

Data persists in `./data/` (`portfolio.json`, `trades.jsonl`, archives). This directory is gitignored.

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
## Project layout

```
stock_checker/
  intelligent_trader.py   # primary paper-trading loop
  market_scanner.py       # opportunity scan + market-hours archive
  symbol_filters.py       # stables / leveraged / noise filters
  recommender.py          # multi-factor scoring
  technical_indicators.py # RSI (Wilder), MACD, Bollinger, ATR
  backtester.py           # OHLCV backtests + metrics
  portfolio.py / persistence.py
  ai_recommender.py / ai_analyzer.py
  fetcher.py / finnhub_fetcher.py / binance_fetcher.py
  cli.py / monitor.py / paper_trader.py
tests/                    # offline unit tests preferred
IMPROVEMENT.md            # agent backlog
AGENTS.md                 # coding + product rules for agents
```

## Strategy notes

- Momentum and technicals matter, but **turnover kills** at 0.1% fees.
- Crypto is limited (`--top-crypto-count`, default 2) and filtered.
- Prefer backtesting rule changes before tightening AI or live loops.
- Docs must not claim Sharpe/win-rate gains without a saved backtest.

## More detail

- [USAGE.md](USAGE.md) — CLI flags and examples
- [OPENBB.md](OPENBB.md) — OpenBB Pro earnings workspace (research layer)
- [PAPER_TRADING.md](PAPER_TRADING.md) — paper trading deep dive (verify flags vs compose)
- [MONITORING.md](MONITORING.md) — monitor service
- [IMPROVEMENT.md](IMPROVEMENT.md) — what agents should do next

## Security

Never commit `.env` or API keys. Rotate any key that was previously checked into compose history.
