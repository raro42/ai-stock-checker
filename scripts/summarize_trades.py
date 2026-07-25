#!/usr/bin/env python3
"""Summarize paper-trading fees vs realized P&L from trades.jsonl."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def summarize(trades_path: Path) -> dict:
    trades = []
    with trades_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                trades.append(json.loads(line))

    buys = [t for t in trades if t.get("type") == "BUY"]
    sells = [t for t in trades if t.get("type") == "SELL"]
    fees = sum(float(t.get("commission", 0) or 0) for t in trades)
    realized = sum(float(t.get("profit_loss", 0) or 0) for t in sells)
    wins = sum(1 for t in sells if float(t.get("profit_loss", 0) or 0) > 0)
    losses = sum(1 for t in sells if float(t.get("profit_loss", 0) or 0) < 0)
    symbols = Counter(t.get("symbol") for t in trades)

    return {
        "trades": len(trades),
        "buys": len(buys),
        "sells": len(sells),
        "fees": fees,
        "realized_pnl": realized,
        "net_after_fees_approx": realized - sum(
            float(t.get("commission", 0) or 0) for t in sells
        ),
        "wins": wins,
        "losses": losses,
        "top_symbols": symbols.most_common(10),
        "first": trades[0].get("timestamp") if trades else None,
        "last": trades[-1].get("timestamp") if trades else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize paper trades / fees")
    parser.add_argument(
        "--trades",
        default="data/trades.jsonl",
        help="Path to trades.jsonl",
    )
    args = parser.parse_args()
    path = Path(args.trades)
    if not path.exists():
        print(f"No trades file at {path}")
        return

    s = summarize(path)
    print("Paper trading summary")
    print(f"  Period: {s['first']} → {s['last']}")
    print(f"  Trades: {s['trades']} (buys={s['buys']}, sells={s['sells']})")
    print(f"  Fees paid: €{s['fees']:,.2f}")
    print(f"  Realized P&L (sells): €{s['realized_pnl']:,.2f}")
    print(f"  Wins/Losses: {s['wins']}/{s['losses']}")
    print("  Top symbols:")
    for sym, n in s["top_symbols"]:
        print(f"    {sym}: {n}")


if __name__ == "__main__":
    main()
