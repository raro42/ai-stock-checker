# Ways to hold metals — not a stock screen

Date: 2026-09-20. This is a product note, not advice. Figures are from the sources below. This desk does not claim those returns.

The live book screens shares (and BTC/ETH). A metal holding is a different object. In the EU, UCITS does not allow a fund that holds only one metal. The listed product is an **ETC** (a note), not a UCITS ETF. Source: [justETF precious metals](https://www.justetf.com/en/how-to/invest-in-precious-metals.html) (page read 2026-09-20).

The scanner already lists US `GLD` and `SLV`. Those are exchange funds. They are still a stock-market check. They are not bars in a vault.

## Paths that are not share screens

| Path | What you hold | Fit for this group |
|------|----------------|--------------------|
| Allocated bars or coins | The metal, in your name or at home | Best match for “not a stock”. Storage, spread, and VAT on delivery of silver, platinum, and palladium. |
| German gold note with a delivery claim | A bearer note. Each note is a claim on grams of gold. | Best listed path on Xetra. Still issuer and custody risk. |
| Physical ETC (gold, silver, platinum, palladium) | A note backed by allocated metal in a vault | Same broker ticket as a share. Fee is the TER. No EU single-metal ETF. |
| App vault (Revolut) | Unallocated metal in Revolut’s name. No delivery. | **Closed for German customers.** Do not plan new buys here. |
| Futures or swap ETC | Collateral and futures, not bars | Extra roll cost. Skip for a low-churn paper book. |
| Mining shares | A company, not the metal | This is the stock screen. Out of scope for this note. |

## 1. Physical metal

Buy bars or coins from a dealer. Store them at home, in a bank, or in an allocated vault (the bar number is yours).

Example of allocated storage: [AUVESTA](https://www.auvesta.eu/lagerung.php) stores numbered bars (Frankfurt, Munich, and other sites). Delivery starts at 1 g gold, 50 g silver, 100 g platinum, 100 g palladium. Their page says German VAT applies when silver, platinum, or palladium is delivered.

This path has no ticker. The paper desk cannot scan it.

## 2. German gold notes (delivery claim)

These trade on an exchange, but the asset is gold, not a company.

**Xetra-Gold** — ticker `4GLD`, ISIN `DE000A0S9GB0`, issuer Deutsche Börse Commodities GmbH.

- One note = one gram of gold. Trade on Xetra 09:00–17:30.
- No management fee. Clearstream charges the custodian bank **0.025% of the holding per month** (0.3% per year) plus VAT. The bank may pass all, part, or none of that fee to you.
- Cash repayment fee: €0.02 per note. Physical delivery is possible; forming and shipping are extra.
- Sources: [trading and holdings](https://www.xetra-gold.com/en/investing-in-gold/trading-holdings/), [trading information](https://www.xetra-gold.com/en/product/trading-information).

**EUWAX Gold II** — WKN `EWG2LD`, ISIN `DE000EWG2LD7`, issuer Boerse Stuttgart Commodities GmbH.

- Physical gold, TER **0%** on the [Q3 2026 factsheet](https://www.euwax-gold.de/files/2026/07/Factsheet_EUWAX_GOLD_II_Q3.pdf).
- One piece = 1 gram. Delivery claim on bars. Factsheet: free delivery of 100 g, or a whole multiple, inside Germany.
- The trade-off vs Xetra-Gold is the spread, not a yearly TER. A 2026 [BÖRSE ONLINE](https://www.boerse-online.de/nachrichten/geld-und-vorsorge/warnung-bei-gold-etcs-diese-versteckten-kosten-lauern-20405200.html) note says EUWAX Gold II has no running vault fee and a wider spread. Xetra-Gold has the tighter spread and the monthly vault fee above.

Hold time matters for German tax on these delivery notes. That is a tax question for a tax adviser, not a scanner signal. Bundesfinanzhof cases on Xetra-Gold are cited in the BÖRSE ONLINE article (VIII R 4/15; VIII R 35/14). Do not treat this note as a tax ruling.

## 3. Other physical ETCs

justETF, read 2026-09-20, lists these large physical lines (size in million EUR, TER per year):

| Metal | Example | ISIN | TER | Size (m EUR) |
|-------|---------|------|-----|-------------:|
| Gold | iShares Physical Gold | IE00B4ND3602 | 0.12% | 34,503 |
| Gold | Invesco Physical Gold | IE00B579F325 | 0.12% | 26,838 |
| Gold | Xetra-Gold | DE000A0S9GB0 | 0.00% listed; vault fee separate | 21,515 |
| Silver | iShares Physical Silver | IE00B4NCWG09 | 0.20% | 2,851 |
| Platinum | iShares Physical Platinum | IE00B4LHWP62 | 0.20% | 316 |
| Palladium | iShares Physical Palladium | IE00B4556L06 | 0.20% | 66 |

A basket line also exists (WisdomTree Physical Precious Metals, JE00B1VS3W29, TER 0.44%). That is still metal, not miners.

EUR-hedged lines cost more (often about 0.25–0.75%). A euro hedge is a second bet. It is not the metal price.

## 4. Revolut app metals — not available in Germany

Revolut Ltd still describes gold, silver, platinum, and palladium for some customers: unallocated vault metal, no bar delivery, not a MiFID instrument, not FSCS. Fee on the [Germany terms](https://www.revolut.com/en-DE/legal/precious-metals/) (updated 8 June 2026): the higher of **€1** or **0.99%** (Standard/Plus) or **0.49%** (Premium/Metal/Ultra), plus the spread.

The [German help page](https://help.revolut.com/en-DE/help/wealth/precious-metals/2026-question-what-can-i-do-with-my-precious-metals-position/) says Commodities Services are **unavailable** for customers in Germany: no new buys, and existing holdings could be sold until **15 June 2026**. That date is past. Do not use Revolut metals as the plan for this group.

The paper scan now includes this short list (`stock_checker/listed_funds.py`). It is not the full ETF market. Leveraged funds stay out.

| Symbol | What it is |
|--------|------------|
| `VWCE.DE` | Vanguard FTSE All-World ETF |
| `SXR8.DE` | iShares Core S&P 500 ETF (euro) |
| `SPY` | SPDR S&P 500 ETF (US) |
| `4GLD.DE` | Xetra-Gold (ETC) |
| `XAD6.DE` | Xtrackers Physical Silver (ETC) |
| `GLD` / `SLV` | US gold and silver funds |

Same stock gates apply (hold, fees, take-profit, stop). An ETC has no company earnings, so the earnings blackout does not apply.

## What this desk should not add

- Mining shares. That is the stock screen again.
- Leveraged or futures metal notes. They fight the anti-churn fee model.
- A claim that `GLD` / `SLV` are bars in your vault. They are US funds. `4GLD.DE` is the German gold note.
