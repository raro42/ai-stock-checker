#!/usr/bin/env python3
"""Reset paper portfolio for a fresh start (friends / new experiments)."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset paper trading data directory")
    parser.add_argument("--data-dir", default="data", help="Data directory (default: data)")
    parser.add_argument("--capital", type=float, default=10000.0, help="Starting cash")
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

    if not args.no_backup:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = data_dir / f"backup_{stamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        for name in ("portfolio.json", "trades.jsonl", "entry_times.json", "state.json"):
            src = data_dir / name
            if src.exists():
                shutil.copy2(src, backup_dir / name)
        print(f"Backup written to {backup_dir}")

    portfolio = {
        "initial_cash": args.capital,
        "cash": args.capital,
        "commission_rate": 0.001,
        "holdings": {},
        "avg_buy_price": {},
        "total_fees_paid": 0.0,
        "last_updated": datetime.now().isoformat(),
    }
    (data_dir / "portfolio.json").write_text(json.dumps(portfolio, indent=2))
    (data_dir / "trades.jsonl").write_text("")
    (data_dir / "entry_times.json").write_text("{}")
    print(f"Reset portfolio to €{args.capital:,.2f} in {data_dir}")


if __name__ == "__main__":
    main()
