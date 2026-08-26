# Trading skills repos for Ideas watch (2026-08-26)

Research note: public Claude/Cursor **trading skill** repos to screen for transferable desk ideas.  
**Do not clone wholesale.** No live broker wiring. Secrets stay in `.env`.

## Added to `config/github_watchlist.json`

| Repo | Stars (approx) | Why watch |
|------|----------------|-----------|
| [tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills) | ~2.7k | Workflows: position sizer, pre-trade gate, trader memory, postmortem |
| [staskh/trading_skills](https://github.com/staskh/trading_skills) | ~340 | Risk/portfolio report patterns (IBKR-heavy — ideas only) |
| [mphinance/alpha-skills](https://github.com/mphinance/alpha-skills) | ~19 | Quant/alpha workflow ideas |

## Removed from watch (marketing-heavy / low substance)

| Repo | Why removed |
|------|-------------|
| VictorVVedtion/trading-skills | Persona + vibe-sensei upsell; ideas already captured in IMPROVEMENT C-* |
| agiprolabs/claude-trading-skills | Marketplace catalog marketing |
| pedrobraiti/vizier-trading-skill | Product framing; little ongoing signal |

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
