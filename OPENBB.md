# OpenBB Pro workspace

Verified working via Chrome MCP (2026-07-25 CEST).

**Earnings dashboard:** [Earnings Update](https://pro.openbb.co/app/37a492ef-62d8-49ec-b08d-f01d663ad45a)

## Paper desk backend (our data → OpenBB)

We ship a FastAPI custom backend that exposes paper portfolio widgets:

```bash
docker compose up -d --build openbb-backend
curl -s http://127.0.0.1:7779/health
curl -s http://127.0.0.1:7779/widgets.json | head
```

### Connect in OpenBB Workspace

1. Open [Connections](https://pro.openbb.co/app/connections) → **Connect Backend**
2. Name: `AI Stock Checker`
3. URL: `http://127.0.0.1:7779` (backend must be running locally)
4. Optional header: `X-API-KEY` = value of `OPENBB_BACKEND_API_KEY` in `.env` (if set)
5. If **Test** spins forever: Chrome may be blocking local-network access from `https://pro.openbb.co` — allow local network for the site, or click **Add** after a manual `curl http://127.0.0.1:7779/widgets.json` check
6. Open Apps → **AI Stock Checker Paper Desk**

Widgets:

| Widget | Endpoint |
|--------|----------|
| Paper Portfolio Summary | `/portfolio_markdown` |
| Paper Holdings | `/portfolio_table` |
| Recent Paper Trades | `/trades_table` |
| Latest Opportunities | `/opportunities_markdown` |

## Research layer vs execution

| Layer | Tool |
|-------|------|
| Execution / scoring | `intelligent-trader` (Docker) |
| Earnings / filings / Copilot | OpenBB Earnings Update app |
| Bot state in OpenBB | `openbb-backend` widgets |

Typical friend flow:

1. Signal from paper trader
2. If HIGH conviction equity → OpenBB Earnings Update + Copilot
3. Check Paper Desk widgets for fees / concentration
4. Hold or skip

## Product rules wired in code

- **Earnings blackout:** no new stock entries within 2d before / 1d after earnings (`earnings_guard.py`)
- **Sentiment soft factor:** `news_sentiment` / `openbb_sentiment` / near-earnings penalty in recommender (±10 cap)
- **Do not** put OpenBB account tokens in compose

## Workspace MCP (agents)

For Cursor / Claude agents to see the live OpenBB UI state, enable **Workspace MCP Companion** in OpenBB (hamburger menu) and add the hosted MCP URL + bearer token to your MCP client. See [OpenBB MCP quickstart](https://docs.openbb.co/agents/workspace-mcp-quickstart).

## Example Copilot prompt

> Summarize the Q2 2025 NVDA guidance table on this dashboard in 3 bullets for a paper trader: revenue outlook, margins, and biggest risk signal.

## Agent note

When the user points at `pro.openbb.co`, prefer Chrome MCP to verify/use the live workspace rather than guessing from docs.
