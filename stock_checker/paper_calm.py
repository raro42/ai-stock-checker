"""
Calm-paper streak tracker for the promote → compose-default gate.

AUTOPILOT: enable `promote_experiment_strategy` default-on in compose only after a
calm paper month. This module records UTC days that look calm while promote is on.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from stock_checker.exit_policy import book_action_mode
from stock_checker.fee_burn import fee_burn_warning

# Target streak before compose may default promote on.
CALM_DAYS_REQUIRED = 30


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def calm_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / "paper_calm.json"


def load_paper_calm(data_dir: Path | str) -> dict[str, Any]:
    path = calm_path(data_dir)
    if not path.is_file():
        return {
            "updated_at": "",
            "promote_on": False,
            "streak_days": 0,
            "required_days": CALM_DAYS_REQUIRED,
            "last_calm_day": "",
            "ready_for_compose_default": False,
            "detail": "no snapshot yet",
            "days": [],
        }
    try:
        raw = json.loads(path.read_text())
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_paper_calm(data_dir: Path | str, snap: dict[str, Any]) -> None:
    path = calm_path(data_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snap, indent=2) + "\n")
    except OSError:
        pass


def evaluate_calm_day(
    *,
    promote_on: bool,
    holdings_count: int,
    max_positions: int,
    data_dir: Path | str,
    flip_flop_blocked_today: int = 0,
) -> tuple[bool, str]:
    """
    One UTC day is calm when promote is on, book is not overweight, fee burn is quiet,
    and we are not thrashing rebuy cooldowns.
    """
    if not promote_on:
        return False, "promote filter off — streak paused"
    mode = book_action_mode(holdings_count, max_positions)
    if mode == "overweight":
        return False, f"overweight book ({holdings_count}/{max_positions})"
    burn = fee_burn_warning(str(data_dir))
    if burn:
        return False, burn
    if flip_flop_blocked_today >= 3:
        return False, f"flip-flop pressure ({flip_flop_blocked_today} rebuy blocks)"
    return True, "calm"


def upsert_calm_day(
    data_dir: Path | str,
    *,
    promote_on: bool,
    holdings_count: int,
    max_positions: int,
    flip_flop_blocked_today: int = 0,
    day: Optional[str] = None,
) -> dict[str, Any]:
    """
    Upsert today's calm verdict and recompute streak of consecutive calm UTC days.
    """
    today = day or _today_utc()
    ok, why = evaluate_calm_day(
        promote_on=promote_on,
        holdings_count=holdings_count,
        max_positions=max_positions,
        data_dir=data_dir,
        flip_flop_blocked_today=flip_flop_blocked_today,
    )
    prev = load_paper_calm(data_dir)
    days = [d for d in (prev.get("days") or []) if isinstance(d, dict)]
    days = [d for d in days if d.get("day") != today]
    days.append({"day": today, "calm": ok, "detail": why})
    days.sort(key=lambda d: str(d.get("day") or ""))
    days = days[-60:]

    streak = 0
    for d in reversed(days):
        if d.get("calm"):
            streak += 1
        else:
            break

    ready = bool(promote_on and streak >= CALM_DAYS_REQUIRED)
    snap = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "promote_on": bool(promote_on),
        "streak_days": streak,
        "required_days": CALM_DAYS_REQUIRED,
        "last_calm_day": today if ok else str(prev.get("last_calm_day") or ""),
        "ready_for_compose_default": ready,
        "detail": why,
        "days": days,
    }
    if ok:
        snap["last_calm_day"] = today
    save_paper_calm(data_dir, snap)
    return snap
