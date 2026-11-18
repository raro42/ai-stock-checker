# Desk idle cash — 2026-11-18

## Symptom

`https://stock.zeitfenster.de/desk` showed ~€101.5k cash and 0% deployed.
Last buy: 2026-09-22 (BTC-USD). Last sell: 2026-10-30 (BTC-USD). Holdings empty.

## Host

Live desk and trader run on **amvara3** (`/home/amvara/projects/ai-stock-checker`).
Containers were up. Scans still ran. Opportunities appeared (ETH-USD, MUV2.DE, GILD, ABBV).

## Root cause (primary)

Ops `data/trader_config.json` had `ai_mode: validate`.
amvara3 has **no Ollama** (port 11434 refused; move note already said keep AI off).
`.env` had `AI_MODE=off`, but Ops JSON hot-reloads and overrode it.

Every candidate became HOLD LOW:

`AI response missing structured ACTION/CONFIDENCE; defaulting to HOLD`

→ validate filter dropped all names → no buys.

## Secondary block (still true after AI fix)

Regime snapshot (2026-11-18T16:38:20Z):

- SPY `risk_off` (close below SMA200)
- BTC `risk_off` (close below SMA50)

Regime gate blocks **new** entries while risk-off. That is intended.

## Fix applied

1. Live Ops config on amvara3: `ai_mode` → `off` (matches move runbook).
2. Code: when the LLM backend is unreachable, validate mode **fail-open**
   (`parse_mode=unavailable`) so a dead Ollama cannot freeze the book again.
3. Code: `ai_entry_allows` treats missing AI verdict as rules-only. Before this,
   AI-off still blocked every stock **breakout** (`breakout needs AI BUY`).

## Expectation

With AI off, stock breakouts can pass the AI guard again.
Regime gate can still block new entries while SPY/BTC are risk-off.
Do not re-enable validate on amvara3 until a model is reachable.
