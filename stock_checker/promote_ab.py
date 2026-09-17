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
# Fee-adjusted edge needs closed rounds. All-buy = open-only; 1–2 sells = thin closes.
# One lucky close after many buys is not a fair control sample (portfolio AI).
WINDOW_A_TARGET_SELLS = 3
# staskh confirm-against-latest-closed → Window A closes must be fresh.
WINDOW_A_MAX_SELL_STALE_DAYS = 5
# RyanJHamby fresh/aging/stale — warn before hard stale (display only).
WINDOW_A_AGING_SELL_DAYS = 3
# Fee-drag severity from fees÷realized (portfolio AI + xang1234 severity bands).
# mild <2× · heavy ≥2× · severe ≥5× · total when realized ≤0 (no multiple).
WINDOW_A_FEE_DRAG_HEAVY_RATIO = 2.0
WINDOW_A_FEE_DRAG_SEVERE_RATIO = 5.0
# Fees ≤ realized but churn ate ≥ half the edge → thin (warn, still ready for B).
# Complements fee-drag severity (portfolio AI quiet vs high + xang1234 bands).
WINDOW_A_FEES_THIN_RATIO = 0.5
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


def _weekday_days_since(earlier: date, later: date) -> int:
    """Weekday trading days strictly after ``earlier`` through ``later``."""
    if later <= earlier:
        return 0
    return weekday_trading_days(earlier + timedelta(days=1), later)


def window_a_sample_readiness(
    stats: dict[str, Any] | None,
    *,
    target_fills: int = WINDOW_A_TARGET_FILLS,
    target_sells: int = WINDOW_A_TARGET_SELLS,
    max_sell_stale_days: int = WINDOW_A_MAX_SELL_STALE_DAYS,
    aging_sell_days: int = WINDOW_A_AGING_SELL_DAYS,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Whether Window A has enough fills to start B (display / ops honesty).

    PROMOTE_AB records trading days *and* fills. Hitting the day target with a
    thin ledger is not a fair control sample — portfolio AI sample-size
    honesty before ``ready for B``. When ``buys``/``sells`` are present, an
    all-buy ledger is ``open-only`` (no closed rounds → fee-adjusted edge is
    just −fees). Sparse closes (``0 < sells < target_sells``) are ``thin
    closes`` — one lucky SELL after many buys is not a fair control (staskh
    confirm-against-latest-closed + portfolio AI close floor). When a last
    SELL timestamp is present and the close floor is met, closes use
    RyanJHamby fresh/aging/stale vs ``aging_sell_days`` / ``max_sell_stale_days``
    weekday days. Fresh and aging speak on the glance; stale blocks ready.
    Missing stats → unknown (keep summarize). Missing side keys / last_sell →
    fail-open on those checks. When closed rounds exist and in-window fees
    exceed realized sell P&L, ``fee_drag`` warns (portfolio AI fee-burn
    adapted) — bit prefers fee-adjusted ``net −€N`` when known so friends
    see the € damage without parsing the fees strip; appends ``fees N×``
    (fees÷realized) when realized > 0; labels severity ``mild`` / ``heavy`` /
    ``severe`` / ``total`` from the multiple (xang1234 severity bands +
    portfolio AI); does not block ready. When closes exist and fees ≤
    realized, ``fees_ok`` speaks the quiet complement
    (``A fees ok · net +€N · fees N×``) — portfolio AI fee-burn quiet vs
    high + xang1234 speak-both-sides (like fresh completes freshness).
    When fees÷realized ≥ ``WINDOW_A_FEES_THIN_RATIO`` (still ≤1×), label
    ``A fees thin`` (warn tone, does not block ready) — thin edge before
    fee drag. Not a gate; does not flip compose promote.
    """
    need = max(1, int(target_fills))
    sell_need = max(1, int(target_sells))
    stale_need = max(1, int(max_sell_stale_days))
    aging_need = max(0, min(int(aging_sell_days), stale_need))
    empty = {
        "ready": False,
        "known": False,
        "fills": 0,
        "target_fills": need,
        "buys": 0,
        "sells": 0,
        "sides_known": False,
        "target_sells": sell_need,
        "thin": False,
        "thin_bit": "",
        "open_only": False,
        "open_only_bit": "",
        "thin_closes": False,
        "thin_closes_bit": "",
        "stale_closes": False,
        "stale_closes_bit": "",
        "aging_closes": False,
        "aging_closes_bit": "",
        "fresh_closes": False,
        "fresh_closes_bit": "",
        "closes_freshness": "",
        "fee_drag": False,
        "fee_drag_bit": "",
        "fee_drag_net": None,
        "fee_drag_ratio": None,
        "fee_drag_severity": "",
        "fees_ok": False,
        "fees_ok_bit": "",
        "fees_ok_net": None,
        "fees_ok_ratio": None,
        "fees_ok_severity": "",
        "sell_stale_days": None,
        "max_sell_stale_days": stale_need,
        "aging_sell_days": aging_need,
        "last_sell": None,
    }
    if not isinstance(stats, dict):
        return empty
    try:
        fills = int(stats.get("trades") or 0)
    except (TypeError, ValueError):
        fills = 0
    sides_known = "sells" in stats or "buys" in stats
    buys = 0
    sells = 0
    if sides_known:
        try:
            buys = int(stats.get("buys") or 0)
        except (TypeError, ValueError):
            buys = 0
        try:
            sells = int(stats.get("sells") or 0)
        except (TypeError, ValueError):
            sells = 0
        if "buys" not in stats and "sells" in stats:
            buys = max(0, fills - sells)
        elif "sells" not in stats and "buys" in stats:
            sells = max(0, fills - buys)
    thin = fills < need
    thin_bit = ""
    if thin:
        thin_bit = f"A thin · {fills} fills <{need}"
    open_only = sides_known and fills > 0 and sells == 0
    open_only_bit = ""
    if open_only:
        open_only_bit = "A open-only · 0 sells"
    thin_closes = sides_known and sells > 0 and sells < sell_need
    thin_closes_bit = ""
    if thin_closes:
        thin_closes_bit = f"A thin closes · {sells} sells <{sell_need}"

    last_sell_raw = stats.get("last_sell")
    last_sell_dt = parse_trade_timestamp(last_sell_raw)
    sell_stale_days: int | None = None
    stale_closes = False
    stale_closes_bit = ""
    aging_closes = False
    aging_closes_bit = ""
    fresh_closes = False
    fresh_closes_bit = ""
    closes_freshness = ""
    if (
        last_sell_dt is not None
        and not open_only
        and not thin_closes
        and sells >= sell_need
    ):
        today = as_of or date.today()
        sell_stale_days = _weekday_days_since(last_sell_dt.date(), today)
        if sell_stale_days > stale_need:
            stale_closes = True
            closes_freshness = "stale"
            stale_closes_bit = (
                f"A stale closes · last sell {sell_stale_days}d >{stale_need}d"
            )
        elif aging_need > 0 and sell_stale_days > aging_need:
            aging_closes = True
            closes_freshness = "aging"
            aging_closes_bit = (
                f"A aging closes · last sell {sell_stale_days}d"
            )
        else:
            fresh_closes = True
            closes_freshness = "fresh"
            fresh_closes_bit = (
                f"A fresh closes · last sell {sell_stale_days}d"
            )

    # Portfolio AI fee-burn: fees > realized on closed rounds → fee drag warn.
    # Prefer net −€N on the bit (same math as format_window_stats_bit).
    # Append fees÷realized multiple when realized > 0; label mild/heavy/severe
    # (or total when closed red) so friends see severity without math
    # (xang1234 severity bands + portfolio AI). When fees ≤ realized, speak
    # quiet complement ``A fees ok``; when fees÷realized ≥ thin floor, speak
    # ``A fees thin`` (warn, still ready) — portfolio AI quiet vs high.
    # Open-only is already −fees.
    fee_drag = False
    fee_drag_bit = ""
    fee_drag_net: float | None = None
    fee_drag_ratio: float | None = None
    fee_drag_severity = ""
    fees_ok = False
    fees_ok_bit = ""
    fees_ok_net: float | None = None
    fees_ok_ratio: float | None = None
    fees_ok_severity = ""
    if sides_known and sells > 0 and not open_only:
        try:
            fees = float(stats.get("fees") or 0)
            realized = float(stats.get("realized_pnl") or 0)
            if stats.get("net_after_all_fees") is not None:
                net = float(stats.get("net_after_all_fees") or 0)
            else:
                net = realized - fees
        except (TypeError, ValueError):
            fees = 0.0
            realized = 0.0
            net = 0.0

        def _ratio_bit(fees_v: float, realized_v: float) -> tuple[float | None, str]:
            if realized_v <= 0:
                return None, ""
            ratio = fees_v / realized_v
            rounded = round(ratio, 2)
            if abs(ratio - round(ratio)) < 0.05:
                return rounded, f"fees {int(round(ratio))}×"
            return rounded, f"fees {ratio:.1f}×"

        def _net_s(net_v: float) -> str:
            abs_n = abs(net_v)
            if abs_n >= 1000:
                body = f"€{abs_n / 1000:.1f}k"
            else:
                body = f"€{abs_n:,.0f}"
            if net_v < 0:
                return f"−{body}"
            if net_v > 0:
                return f"+{body}"
            return body

        if fees > 0 and fees > realized:
            fee_drag = True
            fee_drag_net = net
            fee_drag_ratio, ratio_bit = _ratio_bit(fees, realized)
            if realized > 0:
                if fee_drag_ratio is not None and fee_drag_ratio >= WINDOW_A_FEE_DRAG_SEVERE_RATIO:
                    fee_drag_severity = "severe"
                elif fee_drag_ratio is not None and fee_drag_ratio >= WINDOW_A_FEE_DRAG_HEAVY_RATIO:
                    fee_drag_severity = "heavy"
                else:
                    fee_drag_severity = "mild"
            else:
                fee_drag_severity = "total"
            head = f"A fee drag {fee_drag_severity}"
            if net < 0:
                fee_drag_bit = f"{head} · net {_net_s(net)}"
                if ratio_bit:
                    fee_drag_bit = f"{fee_drag_bit} · {ratio_bit}"
            elif ratio_bit:
                fee_drag_bit = f"{head} · {ratio_bit}"
            else:
                fee_drag_bit = f"{head} · fees > realized"
        elif fees >= 0 and fees <= realized and (fees > 0 or realized > 0):
            # Quiet complement when churn did not eat closed-round edge.
            # Thin = fees still ≤ realized but ≥ half the edge (warn only).
            fees_ok = True
            fees_ok_net = net
            fees_ok_ratio, ratio_bit = _ratio_bit(fees, realized)
            if (
                fees_ok_ratio is not None
                and fees_ok_ratio >= WINDOW_A_FEES_THIN_RATIO
            ):
                fees_ok_severity = "thin"
                fees_ok_bit = "A fees thin"
            else:
                fees_ok_bit = "A fees ok"
            if net != 0:
                fees_ok_bit = f"{fees_ok_bit} · net {_net_s(net)}"
            if ratio_bit:
                fees_ok_bit = f"{fees_ok_bit} · {ratio_bit}"

    ready = (
        (not thin)
        and (not open_only)
        and (not thin_closes)
        and (not stale_closes)
    )
    return {
        "ready": ready,
        "known": True,
        "fills": fills,
        "target_fills": need,
        "buys": buys,
        "sells": sells,
        "sides_known": sides_known,
        "target_sells": sell_need,
        "thin": thin,
        "thin_bit": thin_bit,
        "open_only": open_only,
        "open_only_bit": open_only_bit,
        "thin_closes": thin_closes,
        "thin_closes_bit": thin_closes_bit,
        "stale_closes": stale_closes,
        "stale_closes_bit": stale_closes_bit,
        "aging_closes": aging_closes,
        "aging_closes_bit": aging_closes_bit,
        "fresh_closes": fresh_closes,
        "fresh_closes_bit": fresh_closes_bit,
        "closes_freshness": closes_freshness,
        "fee_drag": fee_drag,
        "fee_drag_bit": fee_drag_bit,
        "fee_drag_net": fee_drag_net,
        "fee_drag_ratio": fee_drag_ratio,
        "fee_drag_severity": fee_drag_severity,
        "fees_ok": fees_ok,
        "fees_ok_bit": fees_ok_bit,
        "fees_ok_net": fees_ok_net,
        "fees_ok_ratio": fees_ok_ratio,
        "fees_ok_severity": fees_ok_severity,
        "sell_stale_days": sell_stale_days,
        "max_sell_stale_days": stale_need,
        "aging_sell_days": aging_need,
        "last_sell": last_sell_dt.isoformat() if last_sell_dt else None,
    }



def format_window_a_thin_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A thin-sample bit for promote A/B glance."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("thin_bit") or "").strip()
    return bit


def format_window_a_open_only_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A open-only (no closed rounds) bit for promote A/B glance."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("open_only_bit") or "").strip()
    return bit


def format_window_a_thin_closes_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A thin-closes bit (sparse sells vs close floor; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("thin_closes_bit") or "").strip()
    return bit


def format_window_a_stale_closes_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A stale-closes bit (last sell too old) for promote A/B glance."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("stale_closes_bit") or "").strip()
    return bit


def format_window_a_aging_closes_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A aging-closes bit (warn before hard stale; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("aging_closes_bit") or "").strip()
    return bit


def format_window_a_fresh_closes_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A fresh-closes bit (completes fresh/aging/stale; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("fresh_closes_bit") or "").strip()
    return bit


def format_window_a_fee_drag_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A fee-drag bit (net −€N · fees N× when known; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("fee_drag_bit") or "").strip()
    return bit


def format_window_a_fees_ok_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A fees-ok bit (quiet complement to fee drag; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("fees_ok_bit") or "").strip()
    return bit


def format_window_a_side_bit(sample: dict[str, Any] | None) -> str:
    """Compact buy/sell composition: ``Nb/Ns`` (portfolio AI sample honesty).

    Unknown sides → empty. Display only; not a gate.
    Prefer ``format_window_a_sell_progress_bit`` on the glance meter.
    """
    if not isinstance(sample, dict) or not sample.get("known"):
        return ""
    if not sample.get("sides_known"):
        return ""
    try:
        buys = int(sample.get("buys") or 0)
        sells = int(sample.get("sells") or 0)
    except (TypeError, ValueError):
        return ""
    return f"{buys}b/{sells}s"


def format_window_a_sell_progress_bit(sample: dict[str, Any] | None) -> str:
    """Close-floor meter: ``N/M sells`` (portfolio AI + xang1234 multi-meter).

    Fills alone mislead after the ≥3 close floor — show sell progress beside
    days/fills. Unknown / no sides → empty. Display only; not a gate.
    """
    if not isinstance(sample, dict) or not sample.get("known"):
        return ""
    if not sample.get("sides_known"):
        return ""
    try:
        sells = int(sample.get("sells") or 0)
        need = int(sample.get("target_sells") or WINDOW_A_TARGET_SELLS)
    except (TypeError, ValueError):
        return ""
    need = max(1, need)
    return f"{sells}/{need} sells"


def format_window_a_fill_progress_bit(sample: dict[str, Any] | None) -> str:
    """Triple sample meter: ``N/M fills`` · ``N/M sells`` beside days.

    Days alone mislead — show fill progress while Window A is still running.
    When buy/sell sides are known, append close-floor ``N/M sells`` (not
    ``Nb/Ns`` — sell progress toward the floor is the honest dual meter).
    Unknown stats → empty (keep summarize). Display only; not a gate.
    """
    if not isinstance(sample, dict) or not sample.get("known"):
        return ""
    try:
        fills = int(sample.get("fills") or 0)
        need = int(sample.get("target_fills") or WINDOW_A_TARGET_FILLS)
    except (TypeError, ValueError):
        return ""
    need = max(1, need)
    bit = f"{fills}/{need} fills"
    sells = format_window_a_sell_progress_bit(sample)
    if sells:
        bit = f"{bit} · {sells}"
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
    last_sell_ts = None
    last_sell_dt: datetime | None = None
    for sell in sells:
        ts = parse_trade_timestamp(sell.get("timestamp"))
        if ts is None:
            continue
        if last_sell_dt is None or ts > last_sell_dt:
            last_sell_dt = ts
            last_sell_ts = sell.get("timestamp")
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
        "last_sell": last_sell_ts,
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


def format_window_stats_bit(
    stats: dict[str, Any] | None,
    *,
    include_fills: bool = True,
) -> str:
    """Short fee / fee-adjusted net / fill bit for promote A/B glance.

    Prefers ``net_after_all_fees`` (realized − all buy+sell fees) so the desk
    does not read gross sell P&L as edge. Falls back to realized − fees when
    older stats dicts omit the field. When ``include_fills`` is False, omit the
    trailing fill count (glance already shows ``N/M fills`` dual progress).
    Portfolio AI fee honesty; display only.
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
        return "0 fills" if include_fills else ""
    sign = "+" if net >= 0 else "−"
    abs_n = abs(net)
    if abs_n >= 1000:
        pnl = f"{sign}€{abs_n / 1000:.1f}k"
    else:
        pnl = f"{sign}€{abs_n:,.0f}"
    bit = f"€{fees:,.0f} fees · {pnl} net"
    if include_fills:
        bit = f"{bit} · {n} fills"
    return bit
