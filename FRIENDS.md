# AI Stock Checker — for friends

Short path to share signals and paper-trade together.

## 1. Install

- Docker Desktop
- Optional: [Ollama](https://ollama.com) + `ollama pull gemma4:latest`
- Optional: free [Finnhub](https://finnhub.io) API key

## 2. Configure

```bash
git clone <this-repo>
cd ai-stock-checker
cp .env.example .env
# put FINNHUB_API_KEY=... and AI_MODEL=gemma4:latest in .env
```

## 3. Run paper trader

```bash
docker compose up -d --build intelligent-trader
docker logs -f intelligent-trader
```

Defaults avoid fee-burn: 15m scans, 5m checks, **4h minimum hold**.

## 4. Useful commands

```bash
# Portfolio / fee summary (host)
python3 scripts/summarize_trades.py --trades data/trades.jsonl

# Fresh start (€10k)
python3 scripts/reset_paper_portfolio.py --capital 10000

# One-off check
docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli info AAPL

# Backtest
docker run --rm --network host ai-stock-checker \
  python3 -m stock_checker.cli backtest AAPL -p 1y
```

## Rules of the group

1. Paper trade only until a strategy survives backtests **and** a calm paper month.
2. Do not paste API keys in chat — use `.env`.
3. Prefer boring holdings over meme churn.
4. If fees > realized edge, slow down (raise min hold / cut crypto count).
