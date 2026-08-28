"""
Soft risk halts for paper entries (daily loss + concentration).

Does not change exits. Fail-open on unreadable trade logs.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

# Realized loss vs initial capital (UTC day) → block new buys.
DEFAULT_DAILY_LOSS_PCT = 2.0
# Cap one new fill notional vs marked equity.
DEFAULT_MAX_NAME_PCT = 30.0


def utc_day_key(when: Optional[datetime] = None) -> str:
    dt = when or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _parse_trade_day(timestamp: str) -> Optional[str]:
    """Best-effort UTC calendar day from trade timestamp strings."""
    if not timestamp:
        return None
    raw = str(timestamp).strip()
    try:
        if raw.endswith("Z"):
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            # Paper desk writes naive local-ish stamps; treat as UTC for halt day.
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
    except ValueError:
        if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
            return raw[:10]
    return None


def iter_trades(data_dir: Path | str) -> Iterable[dict[str, Any]]:
    path = Path(data_dir) / "trades.jsonl"
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            yield row


def realized_pnl_for_utc_day(data_dir: Path | str, day: Optional[str] = None) -> float:
    """Sum SELL profit_loss for the given UTC day (default today)."""
    target = day or utc_day_key()
    total = 0.0
    for row in iter_trades(data_dir):
        if str(row.get("type") or "").upper() != "SELL":
            continue
        if _parse_trade_day(str(row.get("timestamp") or "")) != target:
            continue
        try:
            total += float(row.get("profit_loss") or 0.0)
        except (TypeError, ValueError):
            continue
    return total


def daily_loss_halt(
    data_dir: Path | str,
    *,
    initial_cash: float,
    threshold_pct: float = DEFAULT_DAILY_LOSS_PCT,
    day: Optional[str] = None,
) -> Tuple[bool, str, float]:
    """
    Returns (block_buys?, reason, realized_pnl_today).

    Blocks when realized sell P&L for the UTC day ≤ −threshold_pct of initial cash.
    """
    try:
        capital = float(initial_cash)
    except (TypeError, ValueError):
        return False, "no capital", 0.0
    if capital <= 0:
        return False, "no capital", 0.0
    try:
        thr = abs(float(threshold_pct))
    except (TypeError, ValueError):
        thr = DEFAULT_DAILY_LOSS_PCT
    if thr <= 0:
        return False, "halt off", 0.0

    pnl = realized_pnl_for_utc_day(data_dir, day=day)
    limit = -capital * (thr / 100.0)
    if pnl <= limit:
        return (
            True,
            f"daily loss halt (realized €{pnl:,.2f} ≤ −{thr:g}% of capital)",
            pnl,
        )
    return False, "ok", pnl


def concentration_allows(
    *,
    notional: float,
    portfolio_value: float,
    max_name_pct: float = DEFAULT_MAX_NAME_PCT,
) -> Tuple[bool, str]:
    """Block a new buy whose notional exceeds max_name_pct of marked equity."""
    try:
        equity = float(portfolio_value)
        cost = float(notional)
        cap = abs(float(max_name_pct))
    except (TypeError, ValueError):
        return True, "unreadable size"
    if equity <= 0 or cost <= 0 or cap <= 0:
        return True, "skip"
    pct = (cost / equity) * 100.0
    if pct > cap:
        return False, f"concentration {pct:.1f}% > {cap:g}% equity cap"
    return True, f"concentration {pct:.1f}% ok"


def pretrade_status(
    data_dir: Path | str,
    *,
    initial_cash: float,
    buy_block_until: float = 0.0,
    now: Optional[float] = None,
) -> Tuple[str, list[str]]:
    """
    Lightweight desk checklist: PASS / WARN / FAIL.

    FAIL only for hard daily-loss halt. WARN for fee burn or active post-SL cooldown.
    """
    import time as _time

    notes: list[str] = []
    level = "PASS"
    halt, why, pnl = daily_loss_halt(data_dir, initial_cash=initial_cash)
    if halt:
        return "FAIL", [why]
    if pnl < 0:
        notes.append(f"UTC day realized €{pnl:,.2f}")
        level = "WARN"

    try:
        from stock_checker.fee_burn import fee_burn_warning

        burn = fee_burn_warning(str(data_dir))
        if burn:
            notes.append(burn)
            level = "WARN"
    except Exception:  # noqa: BLE001
        pass

    ts = float(now if now is not None else _time.time())
    if ts < float(buy_block_until or 0.0):
        notes.append("post-SL buy cooldown active")
        level = "WARN"

    if not notes:
        notes.append("ok")
    return level, notes

