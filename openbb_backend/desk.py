"""
Paper Desk — local web UI for ai-stock-checker.

Open http://127.0.0.1:7779/desk
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_desk_snapshot(data_dir: Path) -> dict[str, Any]:
    portfolio_path = data_dir / "portfolio.json"
    trades_path = data_dir / "trades.jsonl"
    portfolio: dict[str, Any] = {}
    if portfolio_path.exists():
        try:
            portfolio = json.loads(portfolio_path.read_text())
        except (json.JSONDecodeError, OSError):
            portfolio = {}

    trades: list[dict] = []
    if trades_path.exists():
        try:
            for line in trades_path.read_text().splitlines():
                if line.strip():
                    trades.append(json.loads(line))
        except (json.JSONDecodeError, OSError):
            trades = []

    cash = float(portfolio.get("cash") or 0)
    initial = float(portfolio.get("initial_cash") or 0)
    fees = float(portfolio.get("total_fees_paid") or 0)
    holdings = portfolio.get("holdings") or {}
    avg = portfolio.get("avg_buy_price") or {}

    rows = []
    cost = 0.0
    for symbol, qty in holdings.items():
        q = float(qty)
        buy = float(avg.get(symbol, 0) or 0)
        basis = q * buy
        cost += basis
        rows.append(
            {
                "symbol": symbol,
                "quantity": q,
                "avg_buy": buy,
                "cost_basis": basis,
                "kind": "crypto" if "-USD" in str(symbol) else "stock",
            }
        )
    rows.sort(key=lambda r: r["cost_basis"], reverse=True)

    equity = cash + cost
    ret_pct = ((equity / initial) - 1) * 100 if initial else 0.0
    sells = [t for t in trades if t.get("type") == "SELL"]
    realized = sum(float(t.get("profit_loss") or 0) for t in sells)

    recent = list(reversed(trades[-12:]))
    weekend = datetime.now(timezone.utc).weekday() >= 5

    return {
        "brand": "AI Stock Checker",
        "tagline": "Paper desk — honest marks, low churn.",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "initial": initial,
        "cash": cash,
        "fees": fees,
        "equity": equity,
        "ret_pct": ret_pct,
        "positions": len(rows),
        "holdings": rows,
        "realized": realized,
        "trade_count": len(trades),
        "recent_trades": recent,
        "reset_note": portfolio.get("reset_note") or "",
        "weekend_mode": weekend,
        "weekend_hint": "Weekend: crypto-only trading; US stocks paused."
        if weekend
        else "Weekday session: stocks + crypto per scan rules.",
    }
