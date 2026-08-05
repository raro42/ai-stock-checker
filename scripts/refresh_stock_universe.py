#!/usr/bin/env python3
"""One-shot: merge curated seed + Yahoo movers into data/stock_universe.json."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stock_checker.stock_universe_manager import StockUniverseManager  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", default=str(ROOT / "data"))
    p.add_argument("--skip-yahoo", action="store_true", help="Only merge curated seed")
    p.add_argument("--per-screen", type=int, default=25)
    p.add_argument("--max-new", type=int, default=40)
    args = p.parse_args()

    mgr = StockUniverseManager(data_dir=args.data_dir)
    added = mgr.ensure_curated_seed()
    if not args.skip_yahoo:
        added += mgr.discover_yahoo_movers(
            per_screen=args.per_screen, max_new=args.max_new
        )
    stats = mgr.get_stats()
    print(
        f"done: +{added} · universe={stats['total_stocks']} "
        f"scanned={stats['scanned_stocks']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
