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
# Protocol records days *and* fills — day count alone is a thin sample (PROMOTE_AB).
WINDOW_A_TARGET_FILLS = 10
# Window B (promote ON) — not started
WINDOW_B_START: date | None = None
WINDOW_B_START_UTC: datetime | None = None
# Protocol table in docs/PROMOTE_AB.md — restore before starting B
PROTOCOL_MAX_POSITIONS = 5
PROTOCOL_MIN_HOLD_HOURS = 24.0
PROTOCOL_FEE_PRESET = "revolut_standard"
# Soft entry gates stay ON for A and B (only promote flips). Not new gates.
PROTOCOL_REGIME_GATE = True
PROTOCOL_RS_GATE = True
PROTOCOL_BREADTH_GATE = True
# Window A/B knobs table: AI validate (not off/full). Model may still be
# gemma4 or another instruct — mode drift changes churn more than the tag.
PROTOCOL_AI_MODE = "validate"
# FinRobot / TradingAgents multi-role stays ON for A and B (bull·bear·risk).
PROTOCOL_AI_MULTI_ROLE = True
# Anti-churn floors (AUTOPILOT / loop-cadence glance). Faster loops skew A/B.
PROTOCOL_SCAN_INTERVAL_MIN = 15
PROTOCOL_TRADE_INTERVAL_MIN = 5


def window_b_readiness(
    *,
    max_positions: int | None = None,
    open_positions: int | None = None,
    min_hold_hours: float | None = None,
    fee_preset: str | None = None,
    regime_gate: bool | None = None,
    rs_gate: bool | None = None,
    breadth_gate: bool | None = None,
    ai_mode: str | None = None,
    ai_multi_role: bool | None = None,
    scan_interval_min: int | None = None,
    trade_interval_min: int | None = None,
    protocol_max: int = PROTOCOL_MAX_POSITIONS,
    protocol_min_hold_hours: float = PROTOCOL_MIN_HOLD_HOURS,
    protocol_fee_preset: str = PROTOCOL_FEE_PRESET,
    protocol_regime_gate: bool = PROTOCOL_REGIME_GATE,
    protocol_rs_gate: bool = PROTOCOL_RS_GATE,
    protocol_breadth_gate: bool = PROTOCOL_BREADTH_GATE,
    protocol_ai_mode: str = PROTOCOL_AI_MODE,
    protocol_ai_multi_role: bool = PROTOCOL_AI_MULTI_ROLE,
    protocol_scan_interval_min: int = PROTOCOL_SCAN_INTERVAL_MIN,
    protocol_trade_interval_min: int = PROTOCOL_TRADE_INTERVAL_MIN,
) -> dict[str, Any]:
    """Why Window B should wait (display / ops honesty; not a gate).

    Protocol wants the same book caps, min hold, fee preset, soft entry
    gates, AI mode, multi-role, and loop cadence floors for A and B
    (default max 5 / 24h / revolut_standard / regime·RS·breadth on /
    AI validate / multi-role on / scan ≥15m / trade ≥5m).
    Only promote should flip between windows. Live Ops drift pauses a fair
    A/B compare — surface it on the desk instead of saying "ready for B".
    FinRobot / TradingAgents AI honesty + RyanJHamby schedule floors +
    portfolio AI readiness.
    """
    cap = max(1, int(protocol_max))
    hold_need = float(protocol_min_hold_hours)
    fee_need = str(protocol_fee_preset or PROTOCOL_FEE_PRESET).strip().lower()
    ai_need = (
        str(protocol_ai_mode or PROTOCOL_AI_MODE).strip().lower() or PROTOCOL_AI_MODE
    )
    scan_need = max(1, int(protocol_scan_interval_min))
    trade_need = max(1, int(protocol_trade_interval_min))
    blockers: list[str] = []
    if max_positions is not None:
        slots = int(max_positions)
        if slots != cap:
            blockers.append(f"max pos {slots}≠{cap}")
    if open_positions is not None:
        n = int(open_positions)
        if n > cap:
            blockers.append(f"{n} open >{cap}")
    if min_hold_hours is not None:
        hold_h = float(min_hold_hours)
        if abs(hold_h - hold_need) > 0.05:
            blockers.append(f"hold {hold_h:g}h≠{hold_need:g}h")
    if fee_preset is not None:
        preset = str(fee_preset).strip().lower()
        if preset and preset != fee_need:
            short = fee_need.replace("revolut_", "")
            blockers.append(f"fee {preset}≠{short}")
    if regime_gate is not None and bool(regime_gate) != bool(protocol_regime_gate):
        want = "on" if protocol_regime_gate else "off"
        blockers.append(f"regime {'on' if regime_gate else 'off'}≠{want}")
    if rs_gate is not None and bool(rs_gate) != bool(protocol_rs_gate):
        want = "on" if protocol_rs_gate else "off"
        blockers.append(f"RS {'on' if rs_gate else 'off'}≠{want}")
    if breadth_gate is not None and bool(breadth_gate) != bool(protocol_breadth_gate):
        want = "on" if protocol_breadth_gate else "off"
        blockers.append(f"breadth {'on' if breadth_gate else 'off'}≠{want}")
    if ai_mode is not None:
        mode = str(ai_mode).strip().lower()
        if mode and mode != ai_need:
            blockers.append(f"AI {mode}≠{ai_need}")
    if ai_multi_role is not None and bool(ai_multi_role) != bool(
        protocol_ai_multi_role
    ):
        want = "on" if protocol_ai_multi_role else "off"
        blockers.append(f"multi-role {'on' if ai_multi_role else 'off'}≠{want}")
    if scan_interval_min is not None:
        scan_m = int(scan_interval_min)
        if scan_m < scan_need:
            blockers.append(f"scan {scan_m}m<{scan_need}m")
    if trade_interval_min is not None:
        trade_m = int(trade_interval_min)
        if trade_m < trade_need:
            blockers.append(f"trade {trade_m}m<{trade_need}m")
    return {
        "ready": not blockers,
        "blockers": blockers,
        "protocol_max_positions": cap,
        "protocol_min_hold_hours": hold_need,
        "protocol_fee_preset": fee_need,
        "protocol_regime_gate": bool(protocol_regime_gate),
        "protocol_rs_gate": bool(protocol_rs_gate),
        "protocol_breadth_gate": bool(protocol_breadth_gate),
        "protocol_ai_mode": ai_need,
        "protocol_ai_multi_role": bool(protocol_ai_multi_role),
        "protocol_scan_interval_min": scan_need,
        "protocol_trade_interval_min": trade_need,
    }


def format_window_b_block_bit(blockers: list[str] | None) -> str:
    """Short Window B block bit for promote A/B glance."""
    if not blockers:
        return ""
    clean = [str(b).strip() for b in blockers if str(b).strip()]
    if not clean:
        return ""
    return "B blocked · " + " · ".join(clean)


def window_a_sample_readiness(
    stats: dict[str, Any] | None,
    *,
    target_fills: int = WINDOW_A_TARGET_FILLS,
) -> dict[str, Any]:
    """Whether Window A has enough fills to start B (display / ops honesty).

    PROMOTE_AB records trading days *and* fills. Hitting the day target with a
    thin ledger is not a fair control sample — portfolio AI sample-size
    honesty before ``ready for B``. Missing stats → unknown (keep summarize).
    Not a gate; does not flip compose promote.
    """
    need = max(1, int(target_fills))
    if not isinstance(stats, dict):
        return {
            "ready": False,
            "known": False,
            "fills": 0,
            "target_fills": need,
            "thin": False,
            "thin_bit": "",
        }
    try:
        fills = int(stats.get("trades") or 0)
    except (TypeError, ValueError):
        fills = 0
    thin = fills < need
    thin_bit = ""
    if thin:
        thin_bit = f"A thin · {fills} fills <{need}"
    return {
        "ready": not thin,
        "known": True,
        "fills": fills,
        "target_fills": need,
        "thin": thin,
        "thin_bit": thin_bit,
    }


def format_window_a_thin_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A thin-sample bit for promote A/B glance."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("thin_bit") or "").strip()
    return bit


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
    # Fee-adjusted edge for A/B: realized sell P&L minus *all* in-window fees
    # (buy+sell). net_after_sell_fees keeps sell-leg-only for summarize_trades.
    net_all = realized - fees
    return {
        "trades": len(window),
        "buys": len(buys),
        "sells": len(sells),
        "fees": fees,
        "realized_pnl": realized,
        "net_after_sell_fees": realized - sell_fees,
        "net_after_all_fees": net_all,
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
    """Short fee / fee-adjusted net / fill bit for promote A/B glance.

    Prefers ``net_after_all_fees`` (realized − all buy+sell fees) so the desk
    does not read gross sell P&L as edge. Falls back to realized − fees when
    older stats dicts omit the field. Portfolio AI fee honesty; display only.
    """
    if not isinstance(stats, dict):
        return ""
    try:
        n = int(stats.get("trades") or 0)
        fees = float(stats.get("fees") or 0)
        realized = float(stats.get("realized_pnl") or 0)
        if stats.get("net_after_all_fees") is not None:
            net = float(stats.get("net_after_all_fees") or 0)
        else:
            net = realized - fees
    except (TypeError, ValueError):
        return ""
    if n <= 0 and fees <= 0 and realized == 0 and net == 0:
        return "0 fills"
    sign = "+" if net >= 0 else "−"
    abs_n = abs(net)
    if abs_n >= 1000:
        pnl = f"{sign}€{abs_n / 1000:.1f}k"
    else:
        pnl = f"{sign}€{abs_n:,.0f}"
    return f"€{fees:,.0f} fees · {pnl} net · {n} fills"
