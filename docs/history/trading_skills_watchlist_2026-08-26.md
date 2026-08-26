# Trading skills repos for Ideas watch (2026-08-26)

Research note: public Claude/Cursor **trading skill** repos to screen for transferable desk ideas.  
**Do not clone wholesale.** No live broker wiring. Secrets stay in `.env`.

## Added to `config/github_watchlist.json`

| Repo | Stars (approx) | Why watch |
|------|----------------|-----------|
| [tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills) | ~2.7k | Best-known pack: position sizer, pre-trade gate, trader memory, postmortem |
| [staskh/trading_skills](https://github.com/staskh/trading_skills) | ~340 | Risk/portfolio report patterns (IBKR-heavy — ideas only) |
| [agiprolabs/claude-trading-skills](https://github.com/agiprolabs/claude-trading-skills) | ~320 | Large Agent Skills catalog (risk, sizing, backtest) |
| [mphinance/alpha-skills](https://github.com/mphinance/alpha-skills) | ~19 | Quant/alpha workflow ideas |
| [pedrobraiti/vizier-trading-skill](https://github.com/pedrobraiti/vizier-trading-skill) | ~5 | Paper-first framing — cultural fit |

## Skipped (low signal or risk)

| Repo | Reason |
|------|--------|
| Fabio29T/Trading-Skills | Near-duplicate of tradermonty content; low stars |
| ssurmic/claude-investment-skills | Very low stars / activity |
| skeny65/Trading-skill | Near-zero stars |

## Borrow filter (same as prior reviews)

- Prefer: discipline gates, postmortems, sizing, drawdown halts, honest labels  
- Avoid: FMP/Finviz as required deps, Alpaca/IBKR live MCP, launchd auto-PR agents, `--api-key` on CLI  

## Desk change (same day)

Breadth **Allocation** removed — it duplicated Overview/Book weight bars. Charts still has allocation chart.
