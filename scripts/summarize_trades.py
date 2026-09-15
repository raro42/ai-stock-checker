#!/usr/bin/env python3
"""Summarize paper-trading fees vs realized P&L from trades.jsonl."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path

from stock_checker.promote_ab import (
    WINDOW_A_START_UTC,
    summarize_window_trades,
)


def _parse_since(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip()
    if text.lower() in {"window-a", "a", "promote-a"}:
        return WINDOW_A_START_UTC
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        d = date.fromisoformat(text)
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize paper trades / fees")
    parser.add_argument(
        "--trades",
        default="data/trades.jsonl",
        help="Path to trades.jsonl",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="UTC start (ISO date/time, or 'window-a' for promote Window A)",
    )
    parser.add_argument(
        "--until",
        default=None,
        help="UTC end inclusive (ISO date/time)",
    )
    args = parser.parse_args()
    path = Path(args.trades)
    if not path.exists():
        print(f"No trades file at {path}")
        return

    start = _parse_since(args.since)
    end = _parse_since(args.until)
    # Load via summarize helper (filters when start set).
    import json

    trades: list[dict] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                trades.append(json.loads(line))

    if start is None and end is None:
        s = summarize_window_trades(
            trades,
            start=datetime(1970, 1, 1, tzinfo=timezone.utc),
        )
        period = f"{s['first']} → {s['last']}"
    else:
        s = summarize_window_trades(
            trades,
            start=start or datetime(1970, 1, 1, tzinfo=timezone.utc),
            end=end,
        )
        period = f"{s['start_utc']} → {s['end_utc'] or s['last']}"

    print("Paper trading summary")
    print(f"  Period: {period}")
    print(f"  Trades: {s['trades']} (buys={s['buys']}, sells={s['sells']})")
    print(f"  Fees paid: €{s['fees']:,.2f}")
    print(f"  Realized P&L (sells): €{s['realized_pnl']:,.2f}")
    print(f"  Net after sell fees: €{s['net_after_sell_fees']:,.2f}")
    print(f"  Net after all fees: €{s['net_after_all_fees']:,.2f}")
    print(f"  Wins/Losses: {s['wins']}/{s['losses']}")
    print(f"  Legs: stock={s['stock_legs']} crypto={s['crypto_legs']}")


if __name__ == "__main__":
    main()
