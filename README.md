# AI Stock Checker

**A local paper-trading desk that refuses to lie to you.**

Docker-first stock & crypto scanning with anti-churn defaults, fee-aware paper fills, optional Ollama AI, and a quiet editorial UI — built for friends who want honest marks, not dashboard theater.

[![License: MIT](https://img.shields.io/badge/License-MIT-d4a574?style=flat-square)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-7dcea0?style=flat-square)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/runtime-Docker-15241c?style=flat-square)](docker-compose.yml)
[![Release](https://img.shields.io/github/v/release/raro42/ai-stock-checker?style=flat-square&color=d4a574)](https://github.com/raro42/ai-stock-checker/releases)

<p align="center">
  <img src="docs/screenshots/01-overview.jpg" alt="Paper desk Overview — equity, holdings, honest marks" width="920" />
</p>

<p align="center"><em>Overview — forest ink, brass accents, numbers you can trust.</em></p>

---

## Why this exists

Most “AI trading” repos ship vibes: purple glow, fake Sharpe, hourly churn that dies to fees.

This one is the opposite:

- **Fees are real** — 0.1% per side; min hold defaults to **4 hours**
- **Forecasts are banned** until walk-forward beats SPY — charts show *what happened*, not fortune-telling
- **Paper desk first** — browse the book in your browser before you ever trust a loop
- **Docker-only runtime** — no “works on my laptop” dependency soup

If that sounds boring: good. Boring compounds.

---

## The desk

Seven screens. One chrome. Local D3 — no CDN roulette.

| Screen | Job |
|--------|-----|
| **Overview** | Equity, unrealized %, top holdings |
| **Charts** | Book path, allocation, since-buy, relative prices |
| **Screener** | Ranked paper candidates from the latest scan |
| **Breadth** | Session exposure + scan pulse (A/D on leaders) |
| **Book** | Holdings with dated paths since your buy |
| **Ideas** | Scanner picks + open research watch |
| **Ops** | Runtime / watchdog honesty |

<p align="center">
  <img src="docs/screenshots/02-charts.jpg" alt="Charts — book equity and allocation" width="920" />
</p>

<p align="center">
  <img src="docs/screenshots/03-book.jpg" alt="Book — since-buy paths with UTC timing" width="920" />
</p>

<p align="center">
  <img src="docs/screenshots/04-breadth.jpg" alt="Breadth — scan pulse and exposure" width="920" />
</p>

Open locally after compose: **[http://127.0.0.1:7779/desk](http://127.0.0.1:7779/desk)**

Design brief: [`DESIGN.md`](DESIGN.md) — editorial trading room, not AI-SaaS defaults.

---

## Quick start

**Need:** Docker. Optional: [Ollama](https://ollama.com) + an instruct model, [Finnhub](https://finnhub.io) free key.

```bash
git clone https://github.com/raro42/ai-stock-checker.git
cd ai-stock-checker
cp .env.example .env   # optional: FINNHUB_API_KEY, AI_MODEL

docker compose up -d --build intelligent-trader openbb-backend
```

Then open the desk:

```text
http://127.0.0.1:7779/desk
```

Paper state lives in `./data/` (gitignored). Friends’ short path: [`FRIENDS.md`](FRIENDS.md).

### Defaults (anti-churn)

| | |
|--|--|
| Capital | €100,000 paper |
| Scan / trade | 15m / 5m |
| Min hold | **4h** |
| Max positions | 8 |
| AI mode | `validate` (gates ideas; doesn’t hallucinate fills) |

---

## What’s inside

- **Intelligent trader** — scan → rank → paper trade with persistence
- **Symbol filters** — stables, leveraged junk, known noise out
- **Earnings blackout** — skip new entries near earnings when Finnhub has dates
- **OpenBB widgets** — same `:7779` backend for Pro workspace ([OPENBB.md](OPENBB.md))
- **Autoresearch** — overnight strategy search with walk-forward promote gate
- **GitHub research watch** — adapt one transferable pattern at a time ([GITHUB_WATCH.md](GITHUB_WATCH.md))
- **CLI** — `info`, `history`, `bitcoin`, `movers`, `backtest`

```bash
docker build -t ai-stock-checker .
docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli info AAPL --analyze
docker run --rm ai-stock-checker pytest -q
```

---

## Honesty policy

We do **not** claim live edge without walk-forward evidence vs SPY.

Promote rule: experiment strategies must beat SPY on the walk-forward blend before changing live trader defaults. Full-sample hero curves alone are not enough.

If a README ever reads like a hedge-fund pitch deck, open an issue and yell.

---

## Releases

We cut tagged releases when the desk or trader meaningfully changes — screenshots refreshed, notes honest.

- Latest: [Releases](https://github.com/raro42/ai-stock-checker/releases)
- How we cut them: [`RELEASES.md`](RELEASES.md)
- Refresh screenshots: `./scripts/capture_desk_screenshots.sh` (desk must be running)

---

## Docs map

| Doc | |
|-----|--|
| [USAGE.md](USAGE.md) | CLI flags |
| [PAPER_TRADING.md](PAPER_TRADING.md) | Paper loop deep dive |
| [AUTOPILOT.md](AUTOPILOT.md) | Continuous improvement |
| [IMPROVEMENT.md](IMPROVEMENT.md) | Backlog |
| [MODELS.md](MODELS.md) | Which Ollama model for what |
| [GIT.md](GIT.md) | Commit / push ASAP |

---

## Star if you believe this

If you want another repo that promises “10× returns with GPT,” keep scrolling.

If you want a **local, fee-aware, paper-honest** desk you can actually run with friends — star it, fork it, open a PR with one small improvement.

<p align="center">
  <a href="https://github.com/raro42/ai-stock-checker/stargazers">⭐ Star on GitHub</a>
  ·
  <a href="https://github.com/raro42/ai-stock-checker/issues">Issues</a>
  ·
  <a href="FRIENDS.md">Run with friends</a>
</p>

---

## License

[MIT](LICENSE) © 2026 Ralf Roeber

Started Oct 2025 · paper through late 2025 · revived & hardened Jul 2026.
