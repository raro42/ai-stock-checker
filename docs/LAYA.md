# LAYA / JEV System-1 (optional advisory)

Typed **System-1** decisions beside Ollama multi-role validate — inspired by
[QuantDinger’s JEV pre-trade filter](https://github.com/OpenByteInc/QuantDinger)
and open-source [Laya](https://github.com/NandhaKishorM/laya) / [jev-trader](https://github.com/jarrodwatts/jev-trader).

## What shipped (GitHub #2)

| Piece | Status |
| --- | --- |
| Question schema `pass` / `hold` / `reject` + edge score + fee-churn noul | Yes — `stock_checker/laya_decision.py` |
| HTTP `POST {BASE}/v1/systemone` client | Yes — fail-open on timeout/parse/missing URL |
| Validate-path **advisory** record (`data/laya_decisions.json`) | Yes when `LAYA_ADVISORY=1` |
| Ops + Overview glance | Yes — pass/hold/reject counts + last row + scan-cadence age |
| Last-row vs scan-clock clash | Yes — `clash · scan fresh` when bands disagree (same band silent) |
| Last-row vs last-debate clash | Yes — append `debate fresh` when validate memory band disagrees |
| Clash vs staler clock tone | Yes — fresh last-row vs stale/aging scan paints `stale`/`aging`, not calm advisory |
| Last-row vs last-debate name/verb | Yes — `vs NVDA BUY` / `vs BUY` when ticker or verb disagrees; same ticker + same polarity (`pass`↔`BUY`) or same literal verb speaks `agree` |
| Bull↔bear verb oppose tone | Yes — `reject` vs `BUY` / `pass` vs `SELL` paints `aging` (hold silent; not calm advisory) |
| Desk parity (Screener/Book/Ideas/Breadth/scan-log/Charts) | Yes — display only |
| Live **buy gate** / exits blocked by LAYA | **No** — deferred until paper evidence |

Rules, soft gates, and `exit_policy` stay authoritative. Provider outage must never trap a position (QuantDinger fail-open pattern).

## Enable

In `.env` (never commit secrets):

```bash
# Local Laya serve or TypeSafe Jev-compatible endpoint
LAYA_BASE_URL=http://host.docker.internal:8080
# or: JEV_BASE_URL=https://api.typesafe.ai
# LAYA_API_KEY=...   # or JEV_API_KEY
LAYA_ADVISORY=1
# LAYA_TIMEOUT_SECONDS=8
# LAYA_MODEL=systemone
```

Default is **off** (no URL → glance says `off · no LAYA/JEV URL`). Setting a URL without `LAYA_ADVISORY=1` shows `URL set · advisory off`.

This stack does **not** vendor torch/ONNX Laya weights into Docker. Run Laya/Jev elsewhere and point the URL at it.

## Not yet

- Using `reject` to filter paper buys (would be a new entry gate — wait for promote A/B honesty + calm evidence)
- Fine-tuned paper-desk checkpoint

See [IMPROVEMENT.md](../IMPROVEMENT.md) for the deferral checkbox.
