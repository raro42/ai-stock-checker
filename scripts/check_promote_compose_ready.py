#!/usr/bin/env python3
"""Exit 0 when paper calm streak is ready for compose promote default-on."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stock_checker.paper_calm import CALM_DAYS_REQUIRED, load_paper_calm  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--data-dir",
        default=str(ROOT / "data"),
        help="Paper data directory (default: ./data)",
    )
    args = p.parse_args()
    snap = load_paper_calm(args.data_dir)
    streak = int(snap.get("streak_days") or 0)
    need = int(snap.get("required_days") or CALM_DAYS_REQUIRED)
    ready = bool(snap.get("ready_for_compose_default"))
    detail = snap.get("detail") or ""
    print(
        json.dumps(
            {
                "streak_days": streak,
                "required_days": need,
                "ready_for_compose_default": ready,
                "detail": detail,
            },
            indent=2,
        )
    )
    if ready:
        print(
            "READY: set promote_experiment_strategy default-on in compose / "
            "trader_config DEFAULTS after review.",
            file=sys.stderr,
        )
        return 0
    print(
        f"NOT READY: {streak}/{need} calm days with promote on "
        f"({detail}). Do not flip compose default yet.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
