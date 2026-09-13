"""Promote A/B window honesty (display / docs; not an entry gate).

Protocol: docs/PROMOTE_AB.md and docs/history/promote_ab_2026-08-12.md.
Calm streak unlocks compose default — A/B measures fee-adjusted live edge.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

# Window A control (promote OFF) — started 2026-08-12 ~15:22 UTC
WINDOW_A_START = date(2026, 8, 12)
WINDOW_A_START_UTC = datetime(2026, 8, 12, 15, 22, tzinfo=timezone.utc)
WINDOW_A_TARGET_TRADING_DAYS = 10
# Window B (promote ON) — not started
WINDOW_B_START: date | None = None
WINDOW_B_START_UTC: datetime | None = None
# Protocol table in docs/PROMOTE_AB.md — restore before starting B
PROTOCOL_MAX_POSITIONS = 5


def window_b_readiness(
    *,
    max_positions: int | None = None,
    open_positions: int | None = None,
    protocol_max: int = PROTOCOL_MAX_POSITIONS,
) -> dict[str, Any]:
    """Why Window B should wait (display / ops honesty; not a gate).

    Protocol wants the same book caps for A and B (default max 5). Live Ops
    drift (e.g. max_positions=8) pauses a fair A/B compare — surface it on the
    desk instead of saying "ready for B". Portfolio AI readiness pattern.
    """
    cap = max(1, int(protocol_max))
    blockers: list[str] = []
    if max_positions is not None:
        slots = int(max_positions)
        if slots != cap:
            blockers.append(f"max pos {slots}≠{cap}")
    if open_positions is not None:
        n = int(open_positions)
        if n > cap:
            blockers.append(f"{n} open >{cap}")
    return {
        "ready": not blockers,
        "blockers": blockers,
        "protocol_max_positions": cap,
    }


def format_window_b_block_bit(blockers: list[str] | None) -> str:
    """Short Window B block bit for promote A/B glance."""
    if not blockers:
        return ""
    clean = [str(b).strip() for b in blockers if str(b).strip()]
    if not clean:
        return ""
    return "B blocked · " + " · ".join(clean)


def weekday_trading_days(start: date, end: date) -> int:
    """Count Mon–Fri calendar days from start through end (inclusive)."""
    if end < start:
        return 0
    days = 0
    cur = start
    one = timedelta(days=1)
    while cur <= end:
        if cur.weekday() < 5:
            days += 1
        cur += one
    return days


def promote_ab_snapshot(
    promote_on: bool,
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Compact Window A/B status for desk honesty (not a gate)."""
    today = as_of or date.today()
    if WINDOW_B_START is not None:
        b_days = weekday_trading_days(WINDOW_B_START, today)
        return {
            "window": "B",
            "promote_expected": True,
            "promote_on": bool(promote_on),
            "trading_days": b_days,
            "target_days": WINDOW_A_TARGET_TRADING_DAYS,
            "target_met": b_days >= WINDOW_A_TARGET_TRADING_DAYS,
            "protocol_ok": bool(promote_on),
            "window_a_start": WINDOW_A_START.isoformat(),
            "window_b_start": WINDOW_B_START.isoformat(),
        }

    a_days = weekday_trading_days(WINDOW_A_START, today)
    return {
        "window": "A",
        "promote_expected": False,
        "promote_on": bool(promote_on),
        "trading_days": a_days,
        "target_days": WINDOW_A_TARGET_TRADING_DAYS,
        "target_met": a_days >= WINDOW_A_TARGET_TRADING_DAYS,
        "protocol_ok": not bool(promote_on),
        "window_a_start": WINDOW_A_START.isoformat(),
        "window_b_start": None,
    }


def parse_trade_timestamp(raw: Any) -> datetime | None:
    """Parse trade timestamp to aware UTC datetime, or None."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
    else:
        text = str(raw).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        # Allow "YYYY-MM-DD HH:MM:SS" from paper ledger
        if "T" not in text and " " in text and "+" not in text:
            text = text.replace(" ", "T", 1)
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def active_window_start_utc(*, promote_on: bool | None = None) -> datetime:
    """UTC start of the active promote A/B window (B if started, else A)."""
    if WINDOW_B_START_UTC is not None:
        return WINDOW_B_START_UTC
    if WINDOW_B_START is not None:
        return datetime(
            WINDOW_B_START.year,
            WINDOW_B_START.month,
            WINDOW_B_START.day,
            tzinfo=timezone.utc,
        )
    _ = promote_on  # protocol uses calendar start; promote flag checked elsewhere
    return WINDOW_A_START_UTC


def filter_trades_in_window(
    trades: Iterable[dict[str, Any]],
    *,
    start: datetime,
    end: datetime | None = None,
) -> list[dict[str, Any]]:
    """Keep trades with timestamp in [start, end] (end inclusive if set)."""
    out: list[dict[str, Any]] = []
    for trade in trades:
        if not isinstance(trade, dict):
            continue
        ts = parse_trade_timestamp(trade.get("timestamp"))
        if ts is None:
            continue
        if ts < start:
            continue
        if end is not None and ts > end:
            continue
        out.append(trade)
    return out


def summarize_window_trades(
    trades: Iterable[dict[str, Any]],
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, Any]:
    """Fee vs realized fill stats for a promote window (portfolio AI honesty).

    Realized P&L is sell ``profit_loss`` only. Fees sum all legs in-window.
    Crypto legs use ``is_crypto_symbol`` (historical alts included). Not a gate.
    """
    from stock_checker.crypto_policy import is_crypto_symbol

    start_dt = start if start is not None else WINDOW_A_START_UTC
    window = filter_trades_in_window(trades, start=start_dt, end=end)
    buys = [t for t in window if str(t.get("type") or "").upper() == "BUY"]
    sells = [t for t in window if str(t.get("type") or "").upper() == "SELL"]
    fees = sum(float(t.get("commission") or 0) for t in window)
    realized = sum(float(t.get("profit_loss") or 0) for t in sells)
    sell_fees = sum(float(t.get("commission") or 0) for t in sells)
    crypto_legs = sum(
        1 for t in window if is_crypto_symbol(str(t.get("symbol") or ""))
    )
    wins = sum(1 for t in sells if float(t.get("profit_loss") or 0) > 0)
    losses = sum(1 for t in sells if float(t.get("profit_loss") or 0) < 0)
    first_ts = window[0].get("timestamp") if window else None
    last_ts = window[-1].get("timestamp") if window else None
    return {
        "trades": len(window),
        "buys": len(buys),
        "sells": len(sells),
        "fees": fees,
        "realized_pnl": realized,
        "net_after_sell_fees": realized - sell_fees,
        "wins": wins,
        "losses": losses,
        "crypto_legs": crypto_legs,
        "stock_legs": len(window) - crypto_legs,
        "first": first_ts,
        "last": last_ts,
        "start_utc": start_dt.isoformat(),
        "end_utc": end.isoformat() if end is not None else None,
    }


def load_trades_jsonl(path: Path | str) -> list[dict[str, Any]]:
    """Load trades.jsonl rows (skip bad lines)."""
    p = Path(path)
    if not p.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def window_stats_from_data_dir(
    data_dir: Path | str | None,
    *,
    promote_on: bool = False,
) -> dict[str, Any] | None:
    """Summarize active window fills from ``data/trades.jsonl``, or None."""
    if data_dir is None:
        return None
    root = Path(data_dir)
    trades = load_trades_jsonl(root / "trades.jsonl")
    if not trades:
        return None
    start = active_window_start_utc(promote_on=promote_on)
    return summarize_window_trades(trades, start=start)


def format_window_stats_bit(stats: dict[str, Any] | None) -> str:
    """Short fee / P&L / fill bit for promote A/B glance."""
    if not isinstance(stats, dict):
        return ""
    try:
        n = int(stats.get("trades") or 0)
        fees = float(stats.get("fees") or 0)
        realized = float(stats.get("realized_pnl") or 0)
    except (TypeError, ValueError):
        return ""
    if n <= 0 and fees <= 0 and realized == 0:
        return "0 fills"
    sign = "+" if realized >= 0 else "−"
    abs_r = abs(realized)
    if abs_r >= 1000:
        pnl = f"{sign}€{abs_r / 1000:.1f}k"
    else:
        pnl = f"{sign}€{abs_r:,.0f}"
    return f"€{fees:,.0f} fees · {pnl} · {n} fills"
