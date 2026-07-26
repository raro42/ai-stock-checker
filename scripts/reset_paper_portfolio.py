#!/usr/bin/env python3
"""Reset paper portfolio for a fresh start (friends / new experiments)."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def _summarize_trades(trades_path: Path) -> Dict:
    buys = sells = 0
    fees = 0.0
    realized = 0.0
    symbols: Dict[str, int] = {}
    if not trades_path.exists():
        return {
            "trade_lines": 0,
            "buys": 0,
            "sells": 0,
            "fees_approx": 0.0,
            "realized_pnl_approx": 0.0,
            "symbols": {},
        }
    lines = [ln for ln in trades_path.read_text().splitlines() if ln.strip()]
    for ln in lines:
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            continue
        t = row.get("type", "")
        sym = row.get("symbol", "?")
        symbols[sym] = symbols.get(sym, 0) + 1
        if t == "BUY":
            buys += 1
            fees += float(row.get("commission") or 0)
        elif t == "SELL":
            sells += 1
            fees += float(row.get("commission") or 0)
            realized += float(row.get("profit_loss") or 0)
    return {
        "trade_lines": len(lines),
        "buys": buys,
        "sells": sells,
        "fees_approx": fees,
        "realized_pnl_approx": realized,
        "symbols": dict(sorted(symbols.items(), key=lambda kv: -kv[1])[:30]),
    }


def write_history_markdown(
    out: Path,
    *,
    stamp: str,
    capital: float,
    keep: List[str],
    old_portfolio: Dict,
    summary: Dict,
    backup_dir: Path,
) -> None:
    keep_holdings = {
        s: old_portfolio.get("holdings", {}).get(s)
        for s in keep
        if s in (old_portfolio.get("holdings") or {})
    }
    lines = [
        f"# Paper reset — {stamp}",
        "",
        f"Fresh start with capital €{capital:,.2f}. Kept holdings: "
        + (", ".join(keep) if keep else "(none)")
        + ".",
        "",
        "## Prior book (archived)",
        "",
        f"- Backup dir: `{backup_dir}` (local; may be gitignored under `data/`)",
        f"- Initial cash (old): €{float(old_portfolio.get('initial_cash') or 0):,.2f}",
        f"- Cash (old): €{float(old_portfolio.get('cash') or 0):,.2f}",
        f"- Fees paid (old): €{float(old_portfolio.get('total_fees_paid') or 0):,.2f}",
        f"- Holdings (old): `{json.dumps(old_portfolio.get('holdings') or {})}`",
        "",
        "## Trade log summary",
        "",
        f"- Lines: {summary['trade_lines']}",
        f"- Buys / sells: {summary['buys']} / {summary['sells']}",
        f"- Fees (sum of commissions in log): €{summary['fees_approx']:,.2f}",
        f"- Realized PnL on sells (approx): €{summary['realized_pnl_approx']:,.2f}",
        f"- Top symbols by fill count: `{json.dumps(summary['symbols'])}`",
        "",
        "## Kept into new book",
        "",
        f"```json",
        json.dumps(keep_holdings, indent=2),
        "```",
        "",
        "## Lessons carried forward",
        "",
        "- High fee burn came from churn; keep ≥4h min hold.",
        "- Do not promote autoresearch champions until they beat buy-and-hold.",
        "- Prefer boring holdings (e.g. WMT) over meme crypto churn.",
        "",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset paper trading data directory")
    parser.add_argument("--data-dir", default="data", help="Data directory (default: data)")
    parser.add_argument("--capital", type=float, default=100000.0, help="Starting cash")
    parser.add_argument(
        "--keep",
        action="append",
        default=[],
        help="Symbol to keep (repeatable), e.g. --keep WMT",
    )
    parser.add_argument(
        "--history-dir",
        default="docs/history",
        help="Committed markdown history directory",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        default=True,
        help="Backup existing trades/portfolio before reset (default)",
    )
    parser.add_argument("--no-backup", action="store_true", help="Skip backup")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    keep = [s.strip().upper() for s in (args.keep or []) if s.strip()]

    old_portfolio: Dict = {}
    portfolio_path = data_dir / "portfolio.json"
    if portfolio_path.exists():
        try:
            old_portfolio = json.loads(portfolio_path.read_text())
        except json.JSONDecodeError:
            old_portfolio = {}

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = data_dir / f"backup_{stamp}"
    if not args.no_backup:
        backup_dir.mkdir(parents=True, exist_ok=True)
        for name in ("portfolio.json", "trades.jsonl", "entry_times.json", "state.json"):
            src = data_dir / name
            if src.exists():
                shutil.copy2(src, backup_dir / name)
        print(f"Backup written to {backup_dir}")

    summary = _summarize_trades(data_dir / "trades.jsonl")
    history_path = Path(args.history_dir) / f"reset_{stamp}.md"
    write_history_markdown(
        history_path,
        stamp=stamp,
        capital=args.capital,
        keep=keep,
        old_portfolio=old_portfolio,
        summary=summary,
        backup_dir=backup_dir,
    )
    print(f"History markdown: {history_path}")

    holdings: Dict[str, float] = {}
    avg_buy: Dict[str, float] = {}
    reserved = 0.0
    old_holdings = old_portfolio.get("holdings") or {}
    old_avg = old_portfolio.get("avg_buy_price") or {}
    for sym in keep:
        if sym not in old_holdings:
            print(f"WARN: --keep {sym} not in current holdings; skipping")
            continue
        qty = float(old_holdings[sym])
        px = float(old_avg.get(sym) or 0)
        holdings[sym] = qty
        avg_buy[sym] = px
        reserved += qty * px

    cash = max(0.0, float(args.capital) - reserved)
    portfolio = {
        "initial_cash": args.capital,
        "cash": cash,
        "commission_rate": 0.0025,
        "commission_min_eur": 1.0,
        "fee_preset": "revolut_standard",
        "holdings": holdings,
        "avg_buy_price": avg_buy,
        "total_fees_paid": 0.0,
        "reset_at": datetime.now().isoformat(),
        "reset_note": f"Fresh start; kept {','.join(holdings) or 'none'}; prior book archived",
        "last_updated": datetime.now().isoformat(),
    }
    (data_dir / "portfolio.json").write_text(json.dumps(portfolio, indent=2))
    (data_dir / "trades.jsonl").write_text("")
    # Preserve entry times only for kept symbols
    entry_src = data_dir / "entry_times.json"
    entry: Dict = {}
    if entry_src.exists():
        try:
            old_entry = json.loads(entry_src.read_text() or "{}")
            entry = {k: v for k, v in old_entry.items() if k in holdings}
        except json.JSONDecodeError:
            entry = {}
    # If missing entry time for kept symbol, set now (anti-churn min-hold starts fresh)
    now_ts = datetime.now().timestamp()
    for sym in holdings:
        entry.setdefault(sym, now_ts)
    (data_dir / "entry_times.json").write_text(json.dumps(entry, indent=2))

    print(
        f"Reset portfolio to €{args.capital:,.2f} "
        f"(cash €{cash:,.2f}, kept {list(holdings.keys())}) in {data_dir}"
    )


if __name__ == "__main__":
    main()
