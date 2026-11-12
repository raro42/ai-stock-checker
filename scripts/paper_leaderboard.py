#!/usr/bin/env python3
"""Offline paper-account leaderboard (GitHub #4 Mode A)."""

from __future__ import annotations

import argparse
from pathlib import Path

from stock_checker.paper_accounts import build_leaderboard, leaderboard_missing_share


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rank legacy + named paper books by cost-basis equity"
    )
    parser.add_argument("--data-dir", default="data", help="Data directory")
    args = parser.parse_args()
    root = Path(args.data_dir)
    rows = build_leaderboard(root)
    if not rows:
        print("No paper books found.")
        return
    print("Paper leaderboard (cost-basis equity · fees shown · not live marks)")
    print(f"{'#':>2}  {'account':<16}  {'equity':>12}  {'cash':>12}  {'fees':>10}  {'pos':>3}  last trade")
    for i, row in enumerate(rows, 1):
        aid = row.get("account_id") or "legacy"
        if row.get("missing"):
            print(
                f"{i:>2}  {aid:<16}  "
                f"{'missing':>12}  {'—':>12}  {'—':>10}  {'—':>3}  "
                f"missing ledger"
            )
            continue
        print(
            f"{i:>2}  {aid:<16}  "
            f"€{float(row.get('equity_cost') or 0):>10,.2f}  "
            f"€{float(row.get('cash') or 0):>10,.2f}  "
            f"€{float(row.get('fees') or 0):>8,.2f}  "
            f"{int(row.get('open_positions') or 0):>3}  "
            f"{row.get('last_trade_age') or '—'}"
        )
    share = leaderboard_missing_share(rows)
    bit = str(share.get("bit") or "")
    if bit:
        print(bit)


if __name__ == "__main__":
    main()
