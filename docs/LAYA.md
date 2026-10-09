# LAYA / JEV System-1 (optional advisory)

Typed **System-1** decisions beside Ollama multi-role validate — inspired by
[QuantDinger’s JEV pre-trade filter](https://github.com/OpenByteInc/QuantDinger)
and open-source [Laya](https://github.com/NandhaKishorM/laya) / [jev-trader](https://github.com/jarrodwatts/jev-trader).

## Are we using LAYA now? (GitHub #3)

**Code yes · live default no.** The client, Ops/Overview glance, and fail-open path shipped
([GitHub #2](https://github.com/raro42/ai-stock-checker/issues/2)). Shared desk and compose
do **not** set `LAYA_BASE_URL` / `LAYA_ADVISORY=1`, so the trader does not call LAYA/JEV
unless you opt in. Ops glance reads `off · no LAYA/JEV URL` in that case.

LAYA is **never** a buy gate today — `reject` does not block paper entries. Rules, soft gates,
and `exit_policy` stay authoritative.

### How to profit from the advisory (opt-in)

1. Run a Laya/Jev-compatible `POST /v1/systemone` endpoint **outside** this Docker image
   (no torch/ONNX weights vendored here).
2. In `.env`: set `LAYA_BASE_URL` (or `JEV_BASE_URL`) + `LAYA_ADVISORY=1` (see **Enable** below).
3. Restart `intelligent-trader` (+ `openbb-backend` if you want Ops to see env immediately).
4. Prefer `AI_MODE=validate` so the advisory records on the validate path; watch Ops/Overview
   LAYA glance (`pass`/`hold`/`reject`, edge/fee, clash vs debate/scan).
5. Treat the print as **second opinion**, not alpha. Do **not** flip LAYA into a live entry
   veto until promote A/B is honest and a calm paper sample exists
   ([IMPROVEMENT.md](../IMPROVEMENT.md) deferral).

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
| Last-row vs last-debate name/verb | Yes — same ticker + same polarity (`pass`↔`BUY`) or same literal verb speaks `agree`; same ticker + hold/fail-open vs directional speaks `mixed · vs BUY`; cross-ticker mixed / same-side speak `mixed · vs NVDA BUY` / `align · vs NVDA BUY`; bare `vs` keeps bull↔bear |
| Bull↔bear verb oppose tone | Yes — `reject` vs `BUY` / `pass` vs `SELL` paints `aging` (hold silent; not calm advisory) |
| Last-row edge + fee-churn | Yes — `edge none/thin/ok/strong` + `fee quiet/ok/hot` when typed scores present; thin/none or fee hot paints `aging` (pass alone ≠ strong edge) |
| Edge/fee vs debate conf | Yes — same ticker: edge/conf and fee/conf clash or align on extremes (`hot·hi` / `quiet·lo` clash; mid silent; clash paints `aging`) |
| Edge vs fee (same row) | Yes — `edge/fee clash · strong · hot` / `align · strong · quiet` (fee polarity inverted; mid fee silent; clash paints `aging`) |
| Decision vs edge | Yes — `pass/edge clash · thin` / `reject/edge clash · strong` (and debate `BUY`/`SELL`); extremes only; mid `ok` silent; clash paints `aging` |
| Decision vs conf | Yes — `pass/conf clash · lo` / `BUY/conf align · hi` (conviction model; mid `med` silent; clash paints `aging`) |
| Sample lead (ring tilt) | Yes — decided ≥2 with a strict lead speaks `lead pass · N%` / debate `lead BUY · N%` after counts; 1 decided speaks `n=1`; ≥2 with no lead speaks `tied` (last-row ≠ sample tilt); runner present also speaks `ahead wide\|thin · +K` then `vs hold · N · P%` / `vs HOLD · N · P%` when #2 is clear (ownership % ≠ margin ≠ who is #2; absolute count ≠ runner share; sole-bucket / tied runners omit vs) |
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
