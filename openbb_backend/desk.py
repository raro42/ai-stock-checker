"""
Paper Desk — local web UI for ai-stock-checker.

Open http://127.0.0.1:7779/desk
JSON:  http://127.0.0.1:7779/desk/api
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from openbb_backend.symbol_names import display_name, resolve_symbol_names
from stock_checker.trade_postmortem import DEFAULT_LIMIT as POSTMORTEM_LIMIT
from stock_checker.trade_postmortem import closed_rounds


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return default


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    try:
        for line in path.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        return []
    return rows


RECENT_FILLS_LIMIT = 20


def _serialize_trade_row(t: dict, names: dict[str, str]) -> dict[str, Any]:
    sym = t.get("symbol") or "—"
    return {
        "timestamp": t.get("timestamp") or "—",
        "type": t.get("type") or "—",
        "symbol": sym,
        "name": display_name(str(sym), names),
        "quantity": float(t.get("quantity") or 0),
        "price": float(t.get("price") or 0),
        "commission": float(t.get("commission") or 0),
        "profit_loss": t.get("profit_loss"),
        "profit_loss_pct": t.get("profit_loss_pct"),
        "strategy": t.get("strategy"),
        "note": t.get("note"),
        "score": t.get("score"),
        "confidence": t.get("confidence"),
        "source": t.get("source"),
        "exit_reason": t.get("exit_reason"),
        "total_cost": t.get("total_cost"),
        "cash_remaining": t.get("cash_remaining"),
    }


def _parse_book_ts(raw: Any) -> Optional[datetime]:
    """Parse portfolio reset_at or trade timestamp into aware UTC."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    # ISO with optional Z
    try:
        iso = text.replace("Z", "+00:00") if text.endswith("Z") else text
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19] if len(text) >= 19 else text, fmt).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
    return None


def book_start_meta(
    portfolio: dict,
    trades: list[dict],
    *,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Book start date + age for Overview (reset_at, else first fill)."""
    start = _parse_book_ts(portfolio.get("reset_at"))
    if start is None:
        for t in trades:
            cand = _parse_book_ts(t.get("timestamp"))
            if cand is not None:
                start = cand
                break
    if start is None:
        return {
            "book_start": "",
            "book_age_days": None,
            "book_age_label": "",
        }
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    days = max(0, (clock.date() - start.astimezone(timezone.utc).date()).days)
    date_s = start.strftime("%Y-%m-%d")
    return {
        "book_start": date_s,
        "book_age_days": days,
        "book_age_label": f"{date_s} ({days}d)",
    }



def _format_age_short(age_sec: float) -> str:
    """Human age for scan freshness (display only)."""
    sec = max(0, int(age_sec))
    if sec < 60:
        return "just now"
    if sec < 3600:
        return f"{sec // 60}m ago"
    if sec < 36 * 3600:
        return f"{sec // 3600}h ago"
    return f"{sec // 86400}d ago"


def build_scan_freshness(
    scan_time: Any,
    *,
    now: Optional[datetime] = None,
    scan_interval_sec: int = 900,
) -> dict[str, Any]:
    """Scan archive age honesty (RyanJHamby cache-freshness pattern; display only).

    fresh < 2× scan interval · aging < 8× · else stale. Not an entry gate.
    """
    empty = {
        "ready": False,
        "tone": "unknown",
        "age_sec": None,
        "age_label": "",
        "line": "",
        "scan_time": "",
    }
    raw = str(scan_time or "").strip()
    if not raw:
        return empty
    when = _parse_book_ts(raw)
    if when is None:
        return {
            **empty,
            "ready": True,
            "tone": "unknown",
            "line": f"Scan {raw} · age unknown",
            "scan_time": raw,
        }
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    age_sec = max(0.0, (clock - when).total_seconds())
    interval = max(60, int(scan_interval_sec or 900))
    if age_sec < 2 * interval:
        tone = "fresh"
    elif age_sec < 8 * interval:
        tone = "aging"
    else:
        tone = "stale"
    age_label = _format_age_short(age_sec)
    return {
        "ready": True,
        "tone": tone,
        "age_sec": int(age_sec),
        "age_label": age_label,
        "line": f"Scan {age_label} · {tone}",
        "scan_time": raw,
    }


def build_soft_allow_glance(
    events: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Compact fail-open soft-allow memory (tradermonty; display only).

    Shows only when the ring buffer has rows — links friends to Ops detail.
    """
    empty = {
        "ready": False,
        "tone": "flat",
        "count": 0,
        "line": "",
        "last_gate": "",
        "last_reason": "",
    }
    rows = [e for e in (events or []) if isinstance(e, dict)]
    if not rows:
        return empty
    last = rows[0]
    gate = str(last.get("gate") or "?").strip() or "?"
    reason = str(last.get("reason") or "").strip()
    reason_short = reason if len(reason) <= 72 else (reason[:71] + "…")
    n = len(rows)
    noun = "soft-allow" if n == 1 else "soft-allows"
    line = f"{n} recent {noun} · last [{gate}]"
    if reason_short:
        line = f"{line} {reason_short}"
    return {
        "ready": True,
        "tone": "warn",
        "count": n,
        "line": line,
        "last_gate": gate,
        "last_reason": reason_short,
    }


def build_pretrade_glance(
    level: str | None,
    notes: list[str] | None,
) -> dict[str, Any]:
    """Compact PASS/WARN/FAIL checklist (tradermonty pre-trade gate; display only).

    Overview / Ops keep the full section + size hint; other screens get this line.
    """
    empty = {
        "ready": False,
        "tone": "flat",
        "level": "",
        "line": "",
        "notes": [],
    }
    raw = str(level or "").strip().upper()
    if raw not in {"PASS", "WARN", "FAIL"}:
        return empty
    note_list = [str(n).strip() for n in (notes or []) if str(n).strip()]
    joined = "; ".join(note_list) if note_list else "ok"
    if len(joined) > 96:
        joined = joined[:95] + "…"
    tone = raw.lower()
    return {
        "ready": True,
        "tone": tone,
        "level": raw,
        "line": f"{raw} · {joined}",
        "notes": note_list,
    }


def build_book_risk_glance(
    book_risk: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compact slots/posture line (staskh + portfolio AI; display only).

    Book keeps the full risk strip; other desk screens get this glance so
    friends see overweight / at_cap before chasing scan names or flipping knobs.
    """
    empty = {
        "ready": False,
        "tone": "flat",
        "posture": "",
        "line": "",
        "slots": "",
        "concentration_warn": False,
    }
    if not isinstance(book_risk, dict):
        return empty
    posture = str(book_risk.get("posture") or "").strip().lower()
    slots = str(book_risk.get("slots") or "").strip()
    if posture not in {"open", "at_cap", "overweight"} or not slots:
        return empty
    note = str(book_risk.get("note") or "").strip()
    line = note if note else f"{slots} slots · {posture}"
    if len(line) > 96:
        line = line[:95] + "…"
    tone = {
        "open": "open",
        "at_cap": "at_cap",
        "overweight": "overweight",
    }.get(posture, "flat")
    return {
        "ready": True,
        "tone": tone,
        "posture": posture,
        "line": line,
        "slots": slots,
        "concentration_warn": bool(book_risk.get("concentration_warn")),
    }


def build_concentration_glance(
    book_risk: dict[str, Any] | None,
    *,
    max_name_pct: float | None = None,
) -> dict[str, Any]:
    """Largest name vs entry concentration cap (staskh / portfolio AI; display only).

    Soft entry cap blocks a new fill whose notional exceeds max_name_pct of equity.
    Book risk already lists the largest weight; this line shows headroom vs the
    30% default so friends see single-name risk before adds. Not a new gate.
    """
    from stock_checker.risk_halts import DEFAULT_MAX_NAME_PCT

    empty = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "symbol": "",
        "largest_pct": 0.0,
        "cap_pct": 0.0,
        "headroom_pp": 0.0,
        "warn": False,
    }
    try:
        cap = float(
            max_name_pct if max_name_pct is not None else DEFAULT_MAX_NAME_PCT
        )
    except (TypeError, ValueError):
        cap = float(DEFAULT_MAX_NAME_PCT)
    if cap <= 0:
        return {
            "ready": True,
            "tone": "off",
            "line": "concentration cap off",
            "symbol": "",
            "largest_pct": 0.0,
            "cap_pct": 0.0,
            "headroom_pp": 0.0,
            "warn": False,
        }
    if not isinstance(book_risk, dict):
        return empty
    sym = str(book_risk.get("largest_symbol") or "").strip().upper()
    try:
        pct = float(book_risk.get("largest_pct") or 0.0)
    except (TypeError, ValueError):
        pct = 0.0
    cap_txt = f"{cap:g}"
    if not sym:
        return {
            "ready": True,
            "tone": "clear",
            "line": f"no open names · entry cap {cap_txt}% equity",
            "symbol": "",
            "largest_pct": 0.0,
            "cap_pct": cap,
            "headroom_pp": cap,
            "warn": False,
        }
    warn = bool(book_risk.get("concentration_warn")) or pct >= cap
    headroom = max(0.0, cap - pct)
    if warn:
        line = f"WARN · {sym} {pct:.0f}% ≥ {cap_txt}% entry cap"
        tone = "warn"
    else:
        hr = f"{headroom:.0f}"
        line = f"{sym} {pct:.0f}% · cap {cap_txt}% · {hr}pp headroom"
        tone = "clear"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "symbol": sym,
        "largest_pct": round(pct, 1),
        "cap_pct": cap,
        "headroom_pp": round(headroom, 1),
        "warn": warn,
    }


def build_entry_gates_glance(
    runtime: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compact soft-gate on/off line (RyanJHamby regime UX; display only).

    Shows regime / RS / breadth / promote so friends see active filters before
    chasing scan names. Ops keeps the toggles; this is honesty, not a new gate.
    """
    empty = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "regime": False,
        "rs": False,
        "breadth": False,
        "promote": False,
        "soft_on": 0,
    }
    if not isinstance(runtime, dict) or not runtime:
        return empty
    regime = bool(runtime.get("regime_gate"))
    rs = bool(runtime.get("rs_gate"))
    breadth = bool(runtime.get("breadth_gate"))
    promote = bool(runtime.get("promote_experiment_strategy"))
    soft_on = int(regime) + int(rs) + int(breadth)
    parts = [
        f"regime {'on' if regime else 'off'}",
        f"RS {'on' if rs else 'off'}",
        f"breadth {'on' if breadth else 'off'}",
        f"promote {'on' if promote else 'off'}",
    ]
    line = " · ".join(parts)
    if soft_on == 3:
        tone = "strict"
    elif soft_on == 0:
        tone = "loose"
    else:
        tone = "mixed"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "regime": regime,
        "rs": rs,
        "breadth": breadth,
        "promote": promote,
        "soft_on": soft_on,
    }


def build_calm_streak_glance(
    runtime: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compact paper-calm promote-unlock line (Phase A / portfolio AI; display only).

    Surfaces streak progress outside Ops facts. Calm days unlock compose promote
    default — not live edge. Not an entry gate.
    """
    empty = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "streak": 0,
        "required": 0,
        "calm_ready": False,
    }
    if not isinstance(runtime, dict) or not runtime:
        return empty
    if "calm_streak_days" not in runtime and "calm_required_days" not in runtime:
        return empty
    streak = max(0, int(runtime.get("calm_streak_days") or 0))
    need = max(1, int(runtime.get("calm_required_days") or 30))
    calm_ready = bool(runtime.get("calm_ready"))
    detail = str(runtime.get("calm_detail") or "").strip()
    if calm_ready:
        tone = "ready"
        status = "compose promote default ready"
    elif streak <= 0:
        tone = "blocked"
        status = "streak not started"
    else:
        tone = "progress"
        status = "building"
    line = f"{streak}/{need} calm days · {status}"
    if detail and not calm_ready:
        short = detail if len(detail) <= 48 else (detail[:47] + "…")
        line = f"{line} · {short}"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "streak": streak,
        "required": need,
        "calm_ready": calm_ready,
    }



def build_promote_ab_glance(
    runtime: dict[str, Any] | None,
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Compact promote A/B window line (Phase A / portfolio AI; display only).

    Shows Window A/B trading-day progress and whether live promote matches the
    protocol (A = off, B = on). Calm ≠ edge; fee-adjusted verdict still required.
    Not an entry gate.
    """
    from stock_checker.promote_ab import promote_ab_snapshot

    empty = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "window": "",
        "trading_days": 0,
        "target_days": 0,
        "target_met": False,
        "protocol_ok": False,
        "promote_on": False,
    }
    if not isinstance(runtime, dict):
        return empty
    promote_on = bool(runtime.get("promote_experiment_strategy"))
    snap = promote_ab_snapshot(promote_on, as_of=as_of or date.today())
    window = str(snap.get("window") or "A")
    days = int(snap.get("trading_days") or 0)
    need = int(snap.get("target_days") or 10)
    target_met = bool(snap.get("target_met"))
    protocol_ok = bool(snap.get("protocol_ok"))
    promote_label = "on" if promote_on else "off"
    if not protocol_ok:
        tone = "warn"
        if window == "A":
            status = "promote should be OFF for control"
        else:
            status = "promote should be ON for Window B"
    elif target_met:
        tone = "ready"
        status = (
            "target met · summarize before B"
            if window == "A"
            else "target met · write fee-adjusted verdict"
        )
    else:
        tone = "progress"
        status = "running"
    line = f"Window {window} · promote {promote_label} · {days}/{need} days · {status}"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "window": window,
        "trading_days": days,
        "target_days": need,
        "target_met": target_met,
        "protocol_ok": protocol_ok,
        "promote_on": promote_on,
    }


def build_exit_policy_glance() -> dict[str, Any]:
    """Compact stock exit asymmetry line (portfolio AI / exit_policy; display only).

    Live stock exits are TP +8% / SL −5% / rotate ≥+5%. Crypto uses wider bands
    (see crypto_policy glance). Not ATR stops; not a new entry gate.
    """
    from stock_checker.exit_policy import (
        DEFAULT_ROTATE_MIN_PROFIT_PCT,
        DEFAULT_STOP_LOSS_PCT,
        DEFAULT_TAKE_PROFIT_PCT,
    )

    tp = float(DEFAULT_TAKE_PROFIT_PCT)
    sl = float(DEFAULT_STOP_LOSS_PCT)
    rot = float(DEFAULT_ROTATE_MIN_PROFIT_PCT)
    line = f"stocks TP +{tp:g}% · SL −{sl:g}% · rotate ≥+{rot:g}%"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": "stock",
        "line": line,
        "take_profit_pct": tp,
        "stop_loss_pct": sl,
        "rotate_min_pct": rot,
    }


def build_earnings_blackout_glance() -> dict[str, Any]:
    """Stock earnings blackout + Yahoo calendar fail-open (tradermonty; display only).

    New stock entries stay blocked DEFAULT_DAYS_BEFORE before and DEFAULT_DAYS_AFTER
    after earnings. Crypto is exempt. Missing Yahoo calendar date → allow (fail-open),
    not a silent waiver. Policy honesty only — no live calendar poll.
    Not a new gate (gate already in earnings_guard).
    """
    from stock_checker.earnings_guard import (
        DEFAULT_DAYS_AFTER,
        DEFAULT_DAYS_BEFORE,
    )

    before = float(DEFAULT_DAYS_BEFORE)
    after = float(DEFAULT_DAYS_AFTER)
    line = (
        f"stocks · {before:g}d before / {after:g}d after · "
        "no Yahoo date → allow · crypto exempt"
    )
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": "stock",
        "line": line,
        "days_before": before,
        "days_after": after,
        "fail_open": True,
        "missing_calendar": "allow",
    }


def build_session_glance(
    *,
    weekend: bool | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """UTC session mode honesty (xang1234 screener session UX; display only).

    Weekday: stocks + crypto. Weekend: crypto-only (US equities paused).
    Not a new gate — mirrors existing weekend trading rule.
    """
    if weekend is None:
        ts = now if now is not None else datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        weekend = ts.astimezone(timezone.utc).weekday() >= 5
    if weekend:
        line = "weekend · crypto-only · stocks paused"
        tone = "weekend"
    else:
        line = "weekday · stocks + crypto"
        tone = "weekday"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "weekend_mode": bool(weekend),
    }


def build_equity_hours_glance(
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """US RTH vs Xetra cash-hours honesty (xang1234 / portfolio AI; display only).

    Session glance covers weekend crypto-only. This line shows live US vs
    German .DE hours so friends do not treat all equities as one clock.
    Crypto stays 24/7. Not a new entry gate — mirrors market_hours.py.
    """
    from stock_checker.market_hours import (
        is_us_cash_session_closed,
        is_xetra_session_closed,
    )

    us_closed = bool(is_us_cash_session_closed(now=now))
    xetra_closed = bool(is_xetra_session_closed(now=now))
    us_bit = "closed" if us_closed else "open"
    xetra_bit = "closed" if xetra_closed else "open"
    if not us_closed and not xetra_closed:
        tone = "open"
    elif us_closed and xetra_closed:
        tone = "closed"
    else:
        tone = "split"
    line = f"US RTH {us_bit} · Xetra {xetra_bit} · crypto 24/7"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "us_open": not us_closed,
        "xetra_open": not xetra_closed,
    }


def build_breakout_guard_glance() -> dict[str, Any]:
    """Stock breakout entry honesty (portfolio AI / screener risk UX; display only).

    Breakouts need AI BUY, reject LOW confidence, and a mild pullback band
    (EXPE/NTRA lesson). Mirrors entry_guards — not a new gate.
    """
    from stock_checker.entry_guards import BREAKOUT_PCT_MAX, BREAKOUT_PCT_MIN

    lo = float(BREAKOUT_PCT_MIN)
    hi = float(BREAKOUT_PCT_MAX)
    line = f"breakouts · AI BUY · LOW blocked · pullback {lo:g}%…{hi:g}%"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": "breakout",
        "line": line,
        "pullback_min_pct": lo,
        "pullback_max_pct": hi,
    }


def build_loss_rotation_glance() -> dict[str, Any]:
    """No-loss-rotation honesty (portfolio AI / tradermonty risk UX; display only).

    Scan rotation never sells losers to chase new names (ESP/BANK lesson).
    Winners need rotate ≥ DEFAULT_ROTATE_MIN_PROFIT_PCT; overweight trims
    prefer winners first. Pairs with exit_policy glance — not a new gate.
    """
    from stock_checker.exit_policy import DEFAULT_ROTATE_MIN_PROFIT_PCT

    rot = float(DEFAULT_ROTATE_MIN_PROFIT_PCT)
    line = (
        f"no loss-rotation · rotate winners ≥+{rot:g}% · overweight trims winners first"
    )
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": "protect",
        "line": line,
        "rotate_min_pct": rot,
        "loss_rotation": False,
    }


def build_stale_rotation_glance() -> dict[str, Any]:
    """Stale-name rotation honesty (tradermonty / portfolio AI; display only).

    SCHW lesson: a name is stale only when it drops off the *entire* scan
    list — not when rank noise bumps it out of top-N. Even then, sell only
    when a stronger top-N replacement exists, and only winners at the rotate
    hurdle. Pairs with loss-rotation + rebuy-cooldown — not a new gate.
    """
    from stock_checker.exit_policy import DEFAULT_ROTATE_MIN_PROFIT_PCT

    rot = float(DEFAULT_ROTATE_MIN_PROFIT_PCT)
    line = (
        f"stale · off full scan list · need top-N replacement · winners ≥+{rot:g}%"
    )
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": "stale",
        "line": line,
        "require_off_scan_list": True,
        "require_replacement": True,
        "winners_only": True,
        "rotate_min_pct": rot,
    }



def build_book_posture_glance(
    holdings: list[dict[str, Any]] | None = None,
    *,
    max_positions: int = 5,
    min_hold_hours: float = 24.0,
    suggest_trim: bool = True,
) -> dict[str, Any]:
    """Live book posture + next overweight trim (staskh + portfolio AI).

    Shows open / at_cap / overweight from ``book_action_mode`` with slot count.
    When overweight and ``suggest_trim``, names the next trim from
    ``pick_overweight_trim_candidate`` (winners first). Charts may pass
    ``suggest_trim=False`` when marks are cost-flat. Display only — not a new gate.
    """
    from stock_checker.exit_policy import (
        book_action_mode,
        pick_overweight_trim_candidate,
    )

    try:
        max_n = max(1, int(max_positions))
    except (TypeError, ValueError):
        max_n = 5
    try:
        hold_h = float(min_hold_hours or 0)
    except (TypeError, ValueError):
        hold_h = 24.0
    hold_s = max(4.0, hold_h) * 3600.0 if hold_h > 0 else 0.0

    rows: list[dict[str, Any]] = []
    if isinstance(holdings, list):
        for r in holdings:
            if not isinstance(r, dict):
                continue
            sym = str(r.get("symbol") or "").strip()
            if not sym:
                continue
            held = r.get("held_seconds")
            if held is None:
                held = r.get("hold_seconds")
            try:
                held_s = max(0.0, float(held)) if held is not None else 0.0
            except (TypeError, ValueError):
                held_s = 0.0
            pnl_raw = r.get("unrealized_pct")
            if pnl_raw is None:
                pnl_raw = r.get("profit_pct")
            try:
                pnl = float(pnl_raw) if pnl_raw is not None else 0.0
            except (TypeError, ValueError):
                pnl = 0.0
            rows.append(
                {
                    "symbol": sym,
                    "hold_seconds": held_s,
                    "profit_pct": pnl,
                }
            )

    open_n = len(rows)
    posture = book_action_mode(open_n, max_n)
    slots = f"{open_n}/{max_n}"
    trim_sym = ""
    trim_why = ""
    if posture == "open":
        tone = "open"
        line = f"live {posture} {slots} · adds OK"
    elif posture == "at_cap":
        tone = "at_cap"
        line = f"live {posture} {slots} · no buys · rotate OK"
    else:
        tone = "overweight"
        if suggest_trim:
            pick, why = pick_overweight_trim_candidate(
                rows, min_hold_seconds=hold_s
            )
            if pick:
                trim_sym = str(pick)
                trim_why = str(why or "")
                pnl = next(
                    (float(r["profit_pct"]) for r in rows if r["symbol"] == pick),
                    0.0,
                )
                kind = "winner" if "winner" in trim_why.lower() else "worst"
                line = (
                    f"live overweight {slots} · next trim {trim_sym} "
                    f"({pnl:+.1f}% {kind})"
                )
            else:
                trim_why = str(why or "no trim candidates past min hold")
                line = f"live overweight {slots} · trim paused (min-hold)"
        else:
            line = f"live overweight {slots} · TP/SL+trim only"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "posture": posture,
        "slots": slots,
        "open_positions": open_n,
        "max_positions": max_n,
        "trim_symbol": trim_sym,
        "trim_why": trim_why,
        "modes": ("open", "at_cap", "overweight"),
        "overweight_scan_rotation": False,
        "overweight_new_buys": False,
    }


def build_junk_filter_glance() -> dict[str, Any]:
    """Junk / noise filter honesty (screener + portfolio AI; display only).

    Scan and entries drop stables, leveraged tokens, and known noise bases.
    Crypto new buys also need price ≥ DEFAULT_CRYPTO_ENTRY_MIN_USD (ESP/BANK).
    Mirrors symbol_filters + exit_policy — not a new gate.
    """
    from stock_checker.exit_policy import DEFAULT_CRYPTO_ENTRY_MIN_USD

    min_usd = float(DEFAULT_CRYPTO_ENTRY_MIN_USD)
    line = f"no stables/leveraged/noise · crypto entries ≥ ${min_usd:g}"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": "filter",
        "line": line,
        "crypto_min_usd": min_usd,
        "stables_blocked": True,
        "leveraged_blocked": True,
    }


def build_universe_discovery_glance(
    data_dir: Path | None = None,
    *,
    now: Optional[datetime] = None,
    max_age_hours: int | None = None,
) -> dict[str, Any]:
    """Universe / movers discovery honesty (xang1234 + RyanJHamby cache; display only).

    Equity scan list is curated US + German Xetra (.DE). Yahoo day
    gainers/losers/actives only grow that list — not an auto-buy firehose.
    Shows last Yahoo discovery age vs the 24h throttle (fresh / aging / stale).
    Buys still need regime/RS/breadth/fees. Not a new gate.
    """
    from stock_checker.yahoo_universe_discovery import (
        DEFAULT_MOVER_COUNT,
        DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS,
    )

    per = int(DEFAULT_MOVER_COUNT)
    age_limit_h = (
        DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS
        if max_age_hours is None
        else max(1, int(max_age_hours))
    )
    age_limit_sec = float(age_limit_h) * 3600.0

    last_raw = ""
    last_added: int | None = None
    if data_dir is not None:
        uni = _load_json(Path(data_dir) / "stock_universe.json", {})
        meta = uni.get("meta") if isinstance(uni, dict) else None
        if isinstance(meta, dict):
            last_raw = str(meta.get("last_yahoo_discovery") or "").strip()
            try:
                last_added = int(meta.get("last_yahoo_added"))
            except (TypeError, ValueError):
                last_added = None

    tone = "unknown"
    age_sec: int | None = None
    age_label = ""
    if not last_raw:
        tone = "stale"
        age_label = "never"
    else:
        when = _parse_book_ts(last_raw)
        if when is None:
            tone = "unknown"
            age_label = "unknown"
        else:
            clock = now or datetime.now(timezone.utc)
            if clock.tzinfo is None:
                clock = clock.replace(tzinfo=timezone.utc)
            age_sec = max(0, int((clock - when).total_seconds()))
            age_label = _format_age_short(float(age_sec))
            if age_sec < age_limit_sec:
                tone = "fresh"
            elif age_sec < 2 * age_limit_sec:
                tone = "aging"
            else:
                tone = "stale"

    line = f"US+DE · Yahoo ≤{per} · cache {age_label} · {tone} · discovery-only"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "mover_count": per,
        "discovery_only": True,
        "auto_buy": False,
        "max_age_hours": age_limit_h,
        "age_sec": age_sec,
        "age_label": age_label,
        "last_yahoo_discovery": last_raw,
        "last_yahoo_added": last_added,
    }


def build_atr_display_glance() -> dict[str, Any]:
    """Screener ATR / R:R honesty (RyanJHamby stop framing + portfolio AI; display only).

    Screener may show ~2×ATR stop notes. Live stock exits stay TP/SL via
    exit_policy — not ATR stops. Guardrail mirror — not a new gate.
    """
    from stock_checker.atr_risk import DEFAULT_ATR_MULT
    from stock_checker.exit_policy import (
        DEFAULT_STOP_LOSS_PCT,
        DEFAULT_TAKE_PROFIT_PCT,
    )

    mult = float(DEFAULT_ATR_MULT)
    tp = float(DEFAULT_TAKE_PROFIT_PCT)
    sl = float(DEFAULT_STOP_LOSS_PCT)
    line = (
        f"Screener ATR ~{mult:g}× notes · display only · "
        f"live TP +{tp:g}% / SL −{sl:g}% (not ATR)"
    )
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": "display",
        "line": line,
        "atr_mult": mult,
        "take_profit_pct": tp,
        "stop_loss_pct": sl,
        "live_atr_stops": False,
    }


def build_entry_slots_glance() -> dict[str, Any]:
    """Entry score band + interleave honesty (xang1234 ranking / A11; display only).

    Stock breakouts use score = base + pct_from_high so near-highs can compete
    with crypto momentum. Execution interleaves top crypto/stock slots instead
    of a pure global sort. Not a new gate — ranking honesty only.
    """
    from stock_checker.entry_slots import (
        DEFAULT_MAX_CRYPTO_SLOTS,
        DEFAULT_MAX_STOCK_SLOTS,
        STOCK_BREAKOUT_SCORE_BASE,
    )

    base = float(STOCK_BREAKOUT_SCORE_BASE)
    max_c = int(DEFAULT_MAX_CRYPTO_SLOTS)
    max_s = int(DEFAULT_MAX_STOCK_SLOTS)
    line = (
        f"stock score {base:g}+pct_from_high · "
        f"interleave ≤{max_c} crypto / ≤{max_s} stock · not pure sort"
    )
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": "slots",
        "line": line,
        "score_base": base,
        "max_crypto_slots": max_c,
        "max_stock_slots": max_s,
        "pure_global_sort": False,
    }


def build_promote_contract_glance(
    runtime: dict[str, Any] | None,
) -> dict[str, Any]:
    """Promote = entry veto only (A18 / portfolio AI; display only).

    Overnight champion filters new buys when promote is on. Exits stay in
    exit_policy; champion SELL never becomes a live buy. Not a new gate —
    contract honesty before flipping Ops promote.
    """
    from stock_checker.promoted_strategy import PROMOTED_SOURCE

    empty: dict[str, Any] = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "promote_on": False,
        "entry_veto_only": True,
        "exits_via_champion": False,
        "source": "",
    }
    if not isinstance(runtime, dict):
        return empty

    on = bool(runtime.get("promote_experiment_strategy"))
    src = str(PROMOTED_SOURCE).rsplit(".", 1)[-1]
    if on:
        tone = "on"
        line = f"on · entry veto only · SELL ≠ buy · exits exit_policy · {src}"
    else:
        tone = "off"
        line = f"off · when on: entry veto only · exits stay exit_policy"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "promote_on": on,
        "entry_veto_only": True,
        "exits_via_champion": False,
        "source": src,
    }


def build_gate_params_glance() -> dict[str, Any]:
    """Soft-gate numeric thresholds (RyanJHamby / xang1234; display only).

    Complements ``build_gate_roles_glance``: roles say *what* each gate is;
    this line shows the live knobs (SMA periods, RS lookback, scan A/D mins).
    Fail-open on short bars stays. Not a new gate.
    """
    from stock_checker.market_regime import (
        CRYPTO_BENCHMARK,
        CRYPTO_SMA_PERIOD,
        STOCK_BENCHMARK,
        STOCK_SMA_PERIOD,
    )
    from stock_checker.relative_strength import rs_lookback
    from stock_checker.scan_breadth_gate import min_advance_ratio, min_stock_leaders

    lookback = int(rs_lookback())
    adv = float(min_advance_ratio())
    leaders = int(min_stock_leaders())
    crypto_label = str(CRYPTO_BENCHMARK).replace("USDT", "").replace("USD", "")
    adv_pct = f"{adv * 100:.0f}%"
    line = (
        f"{STOCK_BENCHMARK}≥SMA{STOCK_SMA_PERIOD} · "
        f"{crypto_label}≥SMA{CRYPTO_SMA_PERIOD} · "
        f"RS≥bench {lookback}d · "
        f"A/D≥{adv_pct} · ≥{leaders} leader · fail-open"
    )
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": "params",
        "line": line,
        "stock_benchmark": STOCK_BENCHMARK,
        "stock_sma": int(STOCK_SMA_PERIOD),
        "crypto_benchmark": CRYPTO_BENCHMARK,
        "crypto_sma": int(CRYPTO_SMA_PERIOD),
        "rs_lookback": lookback,
        "min_advance_ratio": adv,
        "min_stock_leaders": leaders,
        "fail_open": True,
    }


def build_gate_roles_glance(
    runtime: dict[str, Any] | None,
) -> dict[str, Any]:
    """Regime vs RS vs breadth role map (A14 / RyanJHamby; display only).

    Regime = absolute benchmark trend; RS = name vs benchmark; breadth =
    scan-list A/D (not full universe). Prefer RS off first if the book
    starves. Not a new gate — role honesty beside entry-gates toggles.
    """
    from stock_checker.gate_roles import BREADTH_ROLE, REGIME_ROLE, RS_ROLE

    empty: dict[str, Any] = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "regime": False,
        "rs": False,
        "breadth": False,
        "overlap": False,
        "prefer_rs_off_if_starved": True,
        "regime_role": "",
        "rs_role": "",
        "breadth_role": "",
    }
    if not isinstance(runtime, dict):
        return empty

    regime = bool(runtime.get("regime_gate"))
    rs = bool(runtime.get("rs_gate"))
    breadth = bool(runtime.get("breadth_gate"))
    overlap = bool(regime and rs)
    if overlap:
        tone = "overlap"
        line = (
            "regime+RS both on · abs vs rel · breadth scan A/D · "
            "starve→RS off first"
        )
    else:
        tone = "roles"
        line = (
            f"regime {'on' if regime else 'off'} (abs) · "
            f"RS {'on' if rs else 'off'} (rel) · "
            f"breadth {'on' if breadth else 'off'} (scan) · "
            "starve→RS off first"
        )
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "regime": regime,
        "rs": rs,
        "breadth": breadth,
        "overlap": overlap,
        "prefer_rs_off_if_starved": True,
        "regime_role": REGIME_ROLE,
        "rs_role": RS_ROLE,
        "breadth_role": BREADTH_ROLE,
    }


def build_ai_mode_glance(runtime: dict[str, Any] | None) -> dict[str, Any]:
    """AI mode + multi-role honesty (FinRobot / TradingAgents; display only).

    Shows Ops ai_mode / model / ai_multi_role so friends see whether rules-only,
    validate, or full LLM path is live. Not a new gate — config mirror only.
    """
    empty: dict[str, Any] = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "ai_mode": "",
        "ai_model": "",
        "ai_multi_role": False,
    }
    if not isinstance(runtime, dict):
        return empty

    mode = str(runtime.get("ai_mode") or "off").strip().lower() or "off"
    model = str(runtime.get("ai_model") or "gemma4:latest").strip() or "gemma4:latest"
    model_short = model.split("/")[-1]
    if len(model_short) > 28:
        model_short = model_short[:27] + "…"
    multi = bool(runtime.get("ai_multi_role", True))
    multi_txt = "multi-role on" if multi else "multi-role off"

    if mode == "off":
        tone = "off"
        line = f"off · rules only · {multi_txt}"
    elif mode == "validate":
        tone = "validate"
        line = f"validate · {model_short} · {multi_txt}"
    elif mode == "full":
        tone = "full"
        line = f"full · {model_short} · {multi_txt}"
    else:
        tone = "flat"
        line = f"{mode} · {model_short} · {multi_txt}"

    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "ai_mode": mode,
        "ai_model": model,
        "ai_multi_role": multi,
    }


_FEE_PRESET_SHORT: dict[str, str] = {
    "revolut_standard": "Revolut Std 0.25%·€1",
    "revolut_plus": "Revolut Plus 0.25%·€1",
    "revolut_ultra": "Revolut Ultra 0.12%·€1",
    "binance_like": "Spot-like 0.1%",
    "custom": "Custom fees",
}



def build_ai_roles_glance() -> dict[str, Any]:
    """FinRobot / TradingAgents role contract (display only).

    Validate multi-role uses bull / bear / risk officers. Disagreement or
    risk.ok=false forces HOLD. Not a research score and not a new gate —
    mirrors ``ai_multi_role.py`` honesty beside Ideas candidates.
    """
    roles = ("bull", "bear", "risk")
    line = "bull · bear · risk · disagree→HOLD · risk.ok=false→HOLD"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": "roles",
        "line": line,
        "roles": roles,
        "disagree_forces_hold": True,
        "risk_veto_forces_hold": True,
    }


def build_ai_debate_glance(
    data_dir: Path | str | None = None,
    *,
    now: Optional[datetime] = None,
    scan_interval_sec: int = 900,
) -> dict[str, Any]:
    """FinRobot validate debate memory strip (display only).

    One-line BUY/HOLD/SELL + multi-role gated counts from
    ``ai_validate_memory`` so Overview/Ops/Charts see research memory without
    opening Ideas. Includes RyanJHamby/xang1234 ``as of`` age on the newest
    debate (fresh/aging/stale vs scan cadence). Not a research score and not
    a new gate.
    """
    from stock_checker.ai_validate_memory import summarize_ai_debates

    root = data_dir if data_dir is not None else Path(os.getenv("DATA_DIR", "data"))
    stats = summarize_ai_debates(root)
    count = int(stats.get("count") or 0)
    empty_fresh = {
        "age_sec": None,
        "age_label": "",
        "freshness": "",
        "latest_at": "",
    }
    if count <= 0:
        return {
            "ready": True,
            "tone": "empty",
            "line": "No validate debates yet · Ideas empty",
            "count": 0,
            "buy": 0,
            "hold": 0,
            "sell": 0,
            "gated": 0,
            "latest_symbol": "",
            "latest_action": "",
            **empty_fresh,
        }

    buy = int(stats.get("buy") or 0)
    hold = int(stats.get("hold") or 0)
    sell = int(stats.get("sell") or 0)
    gated = int(stats.get("gated") or 0)
    sym = str(stats.get("latest_symbol") or "").strip()
    action = str(stats.get("latest_action") or "HOLD").upper()
    latest_at = str(stats.get("latest_at") or "").strip()
    fresh = build_scan_freshness(
        latest_at, now=now, scan_interval_sec=scan_interval_sec
    )
    age_label = str(fresh.get("age_label") or "")
    freshness = str(fresh.get("tone") or "")
    age_sec = fresh.get("age_sec")
    bits = [f"{count} debates", f"{buy} BUY", f"{hold} HOLD", f"{sell} SELL"]
    if gated:
        bits.append(f"{gated} gated")
    if sym:
        bits.append(f"last {sym} {action}")
    if age_label and freshness and freshness != "unknown":
        bits.append(f"{age_label} · {freshness}")
    elif age_label:
        bits.append(age_label)
    line = " · ".join(bits)
    if len(line) > 96:
        line = line[:95] + "…"
    if freshness == "stale":
        tone = "stale"
    elif gated > 0 and gated >= max(1, count // 2):
        tone = "gated"
    elif buy > hold and buy > sell:
        tone = "buy"
    elif freshness == "aging":
        tone = "aging"
    elif freshness == "fresh":
        tone = "fresh"
    else:
        tone = "flat"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "count": count,
        "buy": buy,
        "hold": hold,
        "sell": sell,
        "gated": gated,
        "latest_symbol": sym,
        "latest_action": action,
        "age_sec": age_sec,
        "age_label": age_label,
        "freshness": freshness,
        "latest_at": latest_at,
    }


def build_ai_validate_scope_glance(
    runtime: dict[str, Any] | None,
) -> dict[str, Any]:
    """FinRobot / TradingAgents AI top-N scope (display only).

    Validate checks top 5; full checks top 10; remainder keeps scanner score
    without LLM. Validate drops SELL and HOLD·LOW. Not a new gate — mirrors
    ``intelligent_trader._ai_validate_opportunities`` honesty.
    """
    from stock_checker.intelligent_trader import AI_FULL_TOP_N, AI_VALIDATE_TOP_N

    empty: dict[str, Any] = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "ai_mode": "",
        "top_n": 0,
        "rest_unscored": True,
    }
    if not isinstance(runtime, dict):
        return empty

    mode = str(runtime.get("ai_mode") or "off").strip().lower() or "off"
    if mode == "off":
        tone = "off"
        top_n = 0
        line = "off · no LLM check · scanner score only"
    elif mode == "validate":
        tone = "validate"
        top_n = int(AI_VALIDATE_TOP_N)
        line = f"validate · AI top {top_n} · SELL/LOW-HOLD drop · rest pass"
    elif mode == "full":
        tone = "full"
        top_n = int(AI_FULL_TOP_N)
        line = f"full · AI top {top_n} · score<-20 drop · rest pass"
    else:
        tone = "flat"
        top_n = int(AI_VALIDATE_TOP_N)
        line = f"{mode} · AI top {top_n} · rest may pass unscored"

    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "ai_mode": mode,
        "top_n": top_n,
        "rest_unscored": True,
    }



def _fmt_cooldown_left(seconds: float) -> str:
    """Short remaining-time label for rebuy cooldown glance."""
    s = max(0.0, float(seconds))
    if s >= 3600.0:
        h = s / 3600.0
        if h >= 10:
            return f"~{h:.0f}h"
        txt = f"{h:.1f}".rstrip("0").rstrip(".")
        return f"~{txt}h"
    if s >= 60.0:
        return f"~{int(s // 60)}m"
    return f"~{int(s)}s"


def build_rebuy_cooldown_glance(
    exit_times: dict[str, Any] | None,
    *,
    cooldown_seconds: float,
    now: float | None = None,
) -> dict[str, Any]:
    """Compact anti flip-flop rebuy cooldown (tradermonty / SCHW; display only).

    After an exit, the same symbol stays blocked for min-hold seconds.
    Desk shows how many names are still cooling — not a new entry gate.
    """
    empty = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "cooling": 0,
        "cooldown_hours": 0.0,
        "symbols": [],
    }
    try:
        cd = float(cooldown_seconds)
    except (TypeError, ValueError):
        return empty
    if cd <= 0:
        return {
            "ready": True,
            "tone": "off",
            "line": "rebuy cooldown off",
            "cooling": 0,
            "cooldown_hours": 0.0,
            "symbols": [],
        }
    ts_now = float(now if now is not None else time.time())
    cooling: list[tuple[str, float]] = []
    if isinstance(exit_times, dict):
        for raw_sym, raw_ts in exit_times.items():
            sym = str(raw_sym or "").strip().upper()
            if not sym:
                continue
            try:
                exit_ts = float(raw_ts)
            except (TypeError, ValueError):
                continue
            left = cd - (ts_now - exit_ts)
            if left > 0:
                cooling.append((sym, left))
    cooling.sort(key=lambda row: row[1])  # soonest clear first
    n = len(cooling)
    hold_h = cd / 3600.0
    hold_txt = f"{hold_h:g}h" if hold_h != int(hold_h) else f"{int(hold_h)}h"
    shown = [f"{sym} {_fmt_cooldown_left(left)}" for sym, left in cooling[:3]]
    if n == 0:
        tone = "clear"
        status = "clear"
    elif n >= 3:
        tone = "warn"
        status = f"{n} cooling"
    else:
        tone = "cooling"
        status = f"{n} cooling"
    line = f"{status} · ≥{hold_txt} rebuy lock"
    if shown:
        line = f"{status} · {', '.join(shown)} · ≥{hold_txt} lock"
    if n >= 3:
        line = f"{line} · flip-flop pressure"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "cooling": n,
        "cooldown_hours": hold_h,
        "symbols": [sym for sym, _ in cooling[:5]],
    }


def build_book_limits_glance(
    runtime: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compact book caps + fee schedule (portfolio AI / Ops; display only).

    Anti-churn packaging: max slots, min hold, Revolut-like fees. Not edge.
    Not a new entry gate.
    """
    empty = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "max_positions": 0,
        "min_hold_hours": 0.0,
        "fee_preset": "",
    }
    if not isinstance(runtime, dict):
        return empty
    try:
        slots = int(runtime.get("max_positions") or 0)
    except (TypeError, ValueError):
        slots = 0
    try:
        hold_h = float(runtime.get("min_hold_hours") or 0)
    except (TypeError, ValueError):
        hold_h = 0.0
    preset = str(runtime.get("fee_preset") or "").strip().lower()
    if slots < 1 or hold_h <= 0:
        return empty
    fee_label = _FEE_PRESET_SHORT.get(preset) or (
        f"{preset or 'fees'}" if preset else "fees unset"
    )
    hold_txt = f"{hold_h:g}h" if hold_h != int(hold_h) else f"{int(hold_h)}h"
    # Product floor is ≥4h; warn when Ops dips below anti-churn packaging.
    if hold_h < 4.0:
        tone = "warn"
    elif preset == "binance_like":
        tone = "optimistic"
    else:
        tone = "book"
    line = f"{slots} slots · ≥{hold_txt} hold · {fee_label}"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "max_positions": slots,
        "min_hold_hours": hold_h,
        "fee_preset": preset or "revolut_standard",
    }


def build_crypto_policy_glance(
    holdings: list[Any] | None,
    *,
    max_crypto: int | None = None,
) -> dict[str, Any]:
    """Compact live crypto policy line (portfolio AI / crypto_policy; display only).

    Screener may list crypto leaders for research. Live buys stay BTC/ETH only,
    max one crypto slot, wider ±10% exits. Not a new entry gate.
    """
    from stock_checker.crypto_policy import (
        CRYPTO_STOP_LOSS_PCT,
        CRYPTO_TAKE_PROFIT_PCT,
        DEFAULT_MAX_CRYPTO_POSITIONS,
        count_crypto_holdings,
        is_crypto_symbol,
    )

    empty = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "count": 0,
        "cap": 0,
        "slot_open": False,
        "symbols": [],
    }
    if holdings is None or not isinstance(holdings, list):
        return empty
    symbols: list[str] = []
    for row in holdings:
        if isinstance(row, dict):
            sym = str(row.get("symbol") or "").strip()
        else:
            sym = str(row or "").strip()
        if sym:
            symbols.append(sym)
    cap = max(0, int(max_crypto if max_crypto is not None else DEFAULT_MAX_CRYPTO_POSITIONS))
    n = count_crypto_holdings(symbols)
    held = [s for s in symbols if is_crypto_symbol(s)][:3]
    slot_open = n < cap
    tp = float(CRYPTO_TAKE_PROFIT_PCT)
    sl = float(CRYPTO_STOP_LOSS_PCT)
    if n > cap:
        tone = "warn"
        status = f"over cap {n}/{cap}"
    elif slot_open:
        tone = "open"
        status = f"slot open {n}/{cap}"
    else:
        tone = "full"
        status = f"slot full {n}/{cap}"
    exits = f"exits ±{tp:g}%" if tp == sl else f"exits +{tp:g}%/−{sl:g}%"
    line = f"{status} · BTC/ETH only · {exits}"
    if held:
        line = f"{line} · {', '.join(held)}"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "count": n,
        "cap": cap,
        "slot_open": slot_open,
        "symbols": held,
    }


def build_post_sl_cooldown_glance(
    last_sl_symbol: str | None,
    last_sl_epoch: float | None,
    *,
    cooldown_seconds: float | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Compact post-stop-loss buy cooldown (tradermonty anti-revenge; display only).

    After an SL sell, new buys stay blocked ≥4h (trader floor). Desk derives the
    window from trades.jsonl so pretrade WARN stays honest without in-memory state.
    Not a new entry gate.
    """
    from stock_checker.risk_halts import DEFAULT_POST_SL_COOLDOWN_SEC

    empty = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "symbol": "",
        "active": False,
        "seconds_left": 0.0,
        "cooldown_hours": 0.0,
    }
    try:
        cd = float(
            cooldown_seconds
            if cooldown_seconds is not None
            else DEFAULT_POST_SL_COOLDOWN_SEC
        )
    except (TypeError, ValueError):
        cd = float(DEFAULT_POST_SL_COOLDOWN_SEC)
    hold_h = cd / 3600.0 if cd > 0 else 0.0
    hold_txt = f"{hold_h:g}h" if hold_h != int(hold_h) else f"{int(hold_h)}h"
    if cd <= 0:
        return {
            "ready": True,
            "tone": "off",
            "line": "post-SL cooldown off",
            "symbol": "",
            "active": False,
            "seconds_left": 0.0,
            "cooldown_hours": 0.0,
        }
    ts_now = float(now if now is not None else time.time())
    try:
        epoch = float(last_sl_epoch) if last_sl_epoch is not None else None
    except (TypeError, ValueError):
        epoch = None
    sym = str(last_sl_symbol or "").strip().upper()
    if epoch is None:
        return {
            "ready": True,
            "tone": "clear",
            "line": f"no recent SL · ≥{hold_txt} buy block after stop",
            "symbol": "",
            "active": False,
            "seconds_left": 0.0,
            "cooldown_hours": hold_h,
        }
    left = cd - (ts_now - epoch)
    if left <= 0:
        age = ts_now - epoch
        age_txt = _fmt_cooldown_left(age).lstrip("~")
        bit = f"{sym} " if sym else ""
        line = f"clear · last SL {bit}{age_txt} ago · ≥{hold_txt} block"
        if len(line) > 96:
            line = line[:95] + "…"
        return {
            "ready": True,
            "tone": "clear",
            "line": line,
            "symbol": sym,
            "active": False,
            "seconds_left": 0.0,
            "cooldown_hours": hold_h,
        }
    left_txt = _fmt_cooldown_left(left)
    bit = f"{sym} " if sym else ""
    line = f"ACTIVE · {bit}{left_txt} left · ≥{hold_txt} after SL — buys blocked"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": "active",
        "line": line,
        "symbol": sym,
        "active": True,
        "seconds_left": left,
        "cooldown_hours": hold_h,
    }


def build_daily_loss_glance(
    realized_pnl: float | None,
    initial: float | None,
    *,
    threshold_pct: float | None = None,
) -> dict[str, Any]:
    """Compact UTC-day loss halt progress (tradermonty / portfolio AI; display only).

    Soft halt blocks new buys after ≥threshold% realized loss vs start capital.
    Pretrade FAIL when tripped; this line shows headroom before that. Not a new gate.
    """
    from stock_checker.risk_halts import DEFAULT_DAILY_LOSS_PCT

    empty = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "pnl": 0.0,
        "initial": 0.0,
        "threshold_pct": 0.0,
        "halted": False,
        "ratio": 0.0,
    }
    try:
        pnl_v = float(realized_pnl) if realized_pnl is not None else 0.0
        init_v = float(initial) if initial is not None else 0.0
    except (TypeError, ValueError):
        return empty
    if init_v <= 0:
        return empty
    try:
        thr = abs(float(threshold_pct if threshold_pct is not None else DEFAULT_DAILY_LOSS_PCT))
    except (TypeError, ValueError):
        thr = float(DEFAULT_DAILY_LOSS_PCT)
    if thr <= 0:
        return {
            "ready": True,
            "tone": "off",
            "line": "daily loss halt off",
            "pnl": pnl_v,
            "initial": init_v,
            "threshold_pct": 0.0,
            "halted": False,
            "ratio": 0.0,
        }
    limit = -init_v * (thr / 100.0)
    ratio = pnl_v / init_v
    halted = pnl_v <= limit
    if halted:
        tone = "halt"
        line = (
            f"HALT · UTC day €{pnl_v:,.2f} · ≤ −{thr:g}% of start — buys blocked"
        )
    elif pnl_v < 0:
        tone = "warn"
        line = (
            f"UTC day €{pnl_v:,.2f} · {abs(ratio) * 100:.1f}% of start · "
            f"halt at −{thr:g}%"
        )
    else:
        tone = "clear"
        line = f"UTC day €{pnl_v:,.2f} · halt at −{thr:g}% of start · clear"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "pnl": pnl_v,
        "initial": init_v,
        "threshold_pct": thr,
        "halted": halted,
        "ratio": ratio,
    }


# Product anti-churn floors (AGENTS / compose): scan ≥15m, trade check ≥5m.
LOOP_CADENCE_SCAN_FLOOR_MIN = 15
LOOP_CADENCE_TRADE_FLOOR_MIN = 5


def build_loop_cadence_glance(
    runtime: dict[str, Any] | None,
) -> dict[str, Any]:
    """Scan / trade loop cadence honesty (portfolio AI + screener; display only).

    Book-limits covers slots/hold/fees. This line shows scan vs trade sleep
    against product floors (≥15m / ≥5m). RyanJHamby / MonsterDeveloper
    screeners advertise schedule — we surface ours so friends do not assume
    a hot tick. Not a new entry gate.
    """
    empty: dict[str, Any] = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "scan_min": 0,
        "trade_min": 0,
        "scan_floor_min": LOOP_CADENCE_SCAN_FLOOR_MIN,
        "trade_floor_min": LOOP_CADENCE_TRADE_FLOOR_MIN,
        "below_floor": False,
    }
    if not isinstance(runtime, dict):
        return empty
    try:
        scan_m = int(runtime.get("scan_interval_min") or 0)
    except (TypeError, ValueError):
        scan_m = 0
    try:
        trade_m = int(runtime.get("trade_interval_min") or 0)
    except (TypeError, ValueError):
        trade_m = 0
    if scan_m < 1 or trade_m < 1:
        return empty
    below = (
        scan_m < LOOP_CADENCE_SCAN_FLOOR_MIN
        or trade_m < LOOP_CADENCE_TRADE_FLOOR_MIN
    )
    floor_bit = (
        f"floors ≥{LOOP_CADENCE_SCAN_FLOOR_MIN}m/"
        f"≥{LOOP_CADENCE_TRADE_FLOOR_MIN}m"
    )
    if below:
        tone = "warn"
        line = f"scan {scan_m}m · trade {trade_m}m · below {floor_bit}"
    else:
        tone = "ok"
        line = f"scan {scan_m}m · trade {trade_m}m · {floor_bit}"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "scan_min": scan_m,
        "trade_min": trade_m,
        "scan_floor_min": LOOP_CADENCE_SCAN_FLOOR_MIN,
        "trade_floor_min": LOOP_CADENCE_TRADE_FLOOR_MIN,
        "below_floor": below,
    }


def build_fee_allowance_glance(
    runtime: dict[str, Any] | None,
) -> dict[str, Any]:
    """Revolut-like free legs left this month (portfolio AI; display only).

    Ops already lists allowance facts. Overview shows remaining free fills
    before churn burns the quota. Crypto fee schedules stay unmodeled
    (fees.py). Not a new entry gate.
    """
    empty: dict[str, Any] = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "free_legs": 0,
        "remaining": 0,
        "used": 0,
        "month": "",
        "fee_preset": "",
        "crypto_modeled": False,
    }
    if not isinstance(runtime, dict):
        return empty
    try:
        free = max(0, int(runtime.get("free_legs_per_month") or 0))
    except (TypeError, ValueError):
        free = 0
    try:
        remaining = max(0, int(runtime.get("fee_allowance_remaining") or 0))
    except (TypeError, ValueError):
        remaining = 0
    try:
        used = max(0, int(runtime.get("fee_allowance_used") or 0))
    except (TypeError, ValueError):
        used = 0
    if "fee_allowance_remaining" not in runtime and free > 0:
        remaining = max(0, free - used)
    elif free > 0:
        remaining = min(remaining, free)
    month = str(runtime.get("fee_allowance_month") or "").strip()
    preset = str(runtime.get("fee_preset") or "").strip().lower()
    fee_label = _FEE_PRESET_SHORT.get(preset) or (
        preset if preset else "fees unset"
    )
    if free <= 0:
        tone = "none"
        line = f"no free legs · {fee_label} · crypto fees not modeled"
    elif remaining <= 0:
        tone = "spent"
        month_bit = f"{month} · " if month else ""
        line = (
            f"0/{free} free left · {month_bit}then paid legs · "
            f"crypto fees not modeled"
        )
    else:
        tone = "open"
        month_bit = f" · {month}" if month else ""
        line = (
            f"{remaining}/{free} free left{month_bit} · then {fee_label} · "
            f"crypto not modeled"
        )
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "free_legs": free,
        "remaining": remaining,
        "used": used,
        "month": month,
        "fee_preset": preset or "revolut_standard",
        "crypto_modeled": False,
    }


def build_fee_burn_glance(
    fees: float | None,
    initial: float | None,
    *,
    threshold: float = 0.02,
    realized_pnl: float | None = None,
) -> dict[str, Any]:
    """Compact fee-drag line (portfolio AI / summarize_trades honesty; display only).

    Overview strip shows raw fees; this line adds % of start capital and, when
    known, fees vs realized sell P&L so friends see churn eat edge before the
    2% pretrade WARN. Not an entry gate.
    """
    empty = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "fees": 0.0,
        "initial": 0.0,
        "ratio": 0.0,
        "high": False,
        "realized": None,
        "fees_gt_realized": False,
    }
    try:
        fee_v = float(fees) if fees is not None else 0.0
        init_v = float(initial) if initial is not None else 0.0
    except (TypeError, ValueError):
        return empty
    if fee_v <= 0 or init_v <= 0:
        return empty
    realized_v: float | None
    try:
        realized_v = float(realized_pnl) if realized_pnl is not None else None
    except (TypeError, ValueError):
        realized_v = None
    ratio = fee_v / init_v
    thr = float(threshold) if threshold > 0 else 0.02
    fees_gt = bool(realized_v is not None and fee_v > realized_v)
    high = ratio >= thr or fees_gt
    tone = "warn" if high else "quiet"
    if fees_gt and ratio < thr:
        status = "fees>P&L"
    elif high:
        status = "high"
    else:
        status = "quiet"
    if realized_v is None:
        line = (
            f"€{fee_v:,.2f} fees · {ratio * 100:.1f}% of €{init_v:,.0f} start · {status}"
        )
    else:
        line = (
            f"€{fee_v:,.2f} fees · {ratio * 100:.1f}% start · "
            f"vs €{realized_v:,.2f} P&L · {status}"
        )
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "fees": fee_v,
        "initial": init_v,
        "ratio": ratio,
        "high": high,
        "realized": realized_v,
        "fees_gt_realized": fees_gt,
    }


def build_stuck_capital_glance(
    stuck: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Compact A15 min-hold capital-trap line (portfolio AI risk UX; display only).

    Overview keeps the detailed stuck list; other screens get this one-liner so
    friends see trapped underwater names before chasing scan adds. Not a gate.
    """
    empty = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "count": 0,
        "symbols": [],
    }
    if not isinstance(stuck, list) or not stuck:
        return empty
    rows = [r for r in stuck if isinstance(r, dict) and str(r.get("symbol") or "").strip()]
    if not rows:
        return empty
    count = len(rows)
    symbols = [str(r.get("symbol") or "").strip() for r in rows][:5]
    bits: list[str] = []
    for r in rows[:3]:
        sym = str(r.get("symbol") or "").strip()
        try:
            pct = float(r.get("unrealized_pct") or 0)
        except (TypeError, ValueError):
            pct = 0.0
        bits.append(f"{sym} {pct:+.1f}%")
    line = f"{count} past min-hold underwater"
    if bits:
        line = f"{line} · {' · '.join(bits)}"
    if count > 3:
        line = f"{line} · +{count - 3} more"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": "warn",
        "line": line,
        "count": count,
        "symbols": symbols,
    }


def apply_min_hold_lock_fields(
    row: dict[str, Any],
    min_hold_seconds: float,
) -> dict[str, Any]:
    """Annotate one holding with min-hold lock state (display only).

    Complements stuck-capital: locked lots cannot rotate/trim for scan-chase yet.
    Missing entry time → empty note (A7: do not treat as already past min-hold).
    """
    hold_s = max(0.0, float(min_hold_seconds or 0.0))
    held = row.get("held_seconds")
    if held is None:
        row["past_min_hold"] = False
        row["min_hold_left_seconds"] = None
        row["min_hold_left"] = ""
        row["min_hold_note"] = ""
        return row
    try:
        held_s = max(0.0, float(held))
    except (TypeError, ValueError):
        row["past_min_hold"] = False
        row["min_hold_left_seconds"] = None
        row["min_hold_left"] = ""
        row["min_hold_note"] = ""
        return row
    left = max(0.0, hold_s - held_s)
    past = left <= 0.0
    row["past_min_hold"] = past
    row["min_hold_left_seconds"] = left
    row["min_hold_left"] = "" if past else _fmt_hold(left)
    row["min_hold_note"] = "past min-hold" if past else f"unlock {_fmt_hold(left)}"
    return row


def build_min_hold_lock_glance(
    holdings: list[dict[str, Any]] | None,
    *,
    min_hold_hours: float = 24.0,
) -> dict[str, Any]:
    """Open lots still inside min-hold (portfolio AI / tradermonty; display only).

    Pairs with stuck-capital (underwater *after* unlock) and book-limits.
    Anti-churn packaging honesty — not a new gate.
    """
    empty = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "locked": 0,
        "timed": 0,
        "min_hold_hours": float(min_hold_hours or 0),
        "earliest_symbol": "",
        "earliest_left": "",
    }
    if not isinstance(holdings, list) or not holdings:
        return empty
    try:
        hold_h = float(min_hold_hours or 0)
    except (TypeError, ValueError):
        hold_h = 0.0
    hold_s = max(4.0, hold_h) * 3600.0 if hold_h > 0 else 0.0
    timed: list[dict[str, Any]] = []
    for r in holdings:
        if not isinstance(r, dict):
            continue
        sym = str(r.get("symbol") or "").strip()
        if not sym:
            continue
        held = r.get("held_seconds")
        if held is None:
            continue
        try:
            held_s = max(0.0, float(held))
        except (TypeError, ValueError):
            continue
        left = max(0.0, hold_s - held_s)
        timed.append({"symbol": sym, "left": left, "past": left <= 0.0})
    if not timed:
        return empty
    locked_rows = [t for t in timed if not t["past"]]
    locked_n = len(locked_rows)
    timed_n = len(timed)
    hold_txt = f"{hold_h:g}h" if hold_h else "min-hold"
    if locked_n <= 0:
        line = f"all {timed_n} past min-hold ({hold_txt}) · rotate/trim OK"
        return {
            "ready": True,
            "tone": "quiet",
            "line": line[:96] if len(line) > 96 else line,
            "locked": 0,
            "timed": timed_n,
            "min_hold_hours": hold_h,
            "earliest_symbol": "",
            "earliest_left": "",
        }
    locked_rows.sort(key=lambda t: t["left"])
    earliest = locked_rows[0]
    left_txt = _fmt_hold(float(earliest["left"]))
    line = (
        f"{locked_n}/{timed_n} in min-hold lock ({hold_txt}) · "
        f"earliest {earliest['symbol']} {left_txt}"
    )
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": "warn" if locked_n == timed_n else "flat",
        "line": line,
        "locked": locked_n,
        "timed": timed_n,
        "min_hold_hours": hold_h,
        "earliest_symbol": str(earliest["symbol"]),
        "earliest_left": left_txt,
    }


def build_next_buy_glance(
    entry_size: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compact next-buy € line (tradermonty sizer / portfolio AI; display only).

    Overview keeps the full pre-trade size block. Other screens get this glance
    so friends see suggested notional before chasing scan names. Not a gate.
    """
    empty = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "eur": 0.0,
        "slots_open": 0,
        "capped_by": "",
    }
    if not isinstance(entry_size, dict):
        return empty
    note = str(entry_size.get("note") or "").strip()
    capped_by = str(entry_size.get("capped_by") or "").strip()
    if not note and not capped_by:
        return empty
    try:
        eur = float(entry_size.get("eur") or 0.0)
    except (TypeError, ValueError):
        eur = 0.0
    try:
        slots_open = max(0, int(entry_size.get("slots_open") or 0))
    except (TypeError, ValueError):
        slots_open = 0
    if eur > 0:
        line = f"Next buy ~€{eur:,.0f}"
        if note:
            line = f"{line} · {note}"
        tone = "warn" if capped_by == "concentration" else "open"
    else:
        line = f"No new buy · {note}" if note else "No new buy"
        tone = "warn" if capped_by in {"book_full", "no_cash"} else "flat"
    if len(line) > 96:
        line = line[:95] + "…"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "eur": round(eur, 2),
        "slots_open": slots_open,
        "capped_by": capped_by,
    }


def build_postmortem_glance(
    postmortems: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Compact last closed-round line (tradermonty / portfolio AI; display only).

    Book keeps the full FIFO postmortem list. Other screens get the newest exit
    so friends see recent paper memory before chasing scan adds. Not a gate.
    No MAE/MFE without a price path.
    """
    empty = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "count": 0,
        "symbol": "",
        "exit_reason": "",
        "profit_loss_pct": None,
    }
    if not isinstance(postmortems, list) or not postmortems:
        return empty
    rows = [r for r in postmortems if isinstance(r, dict) and str(r.get("symbol") or "").strip()]
    if not rows:
        return empty
    latest = rows[0]
    sym = str(latest.get("symbol") or "").strip()
    exit_reason = str(latest.get("exit_reason") or "").strip()[:24]
    held = str(latest.get("held") or "").strip()
    try:
        pnl_pct = latest.get("profit_loss_pct")
        pnl_pct_f = float(pnl_pct) if pnl_pct is not None else None
    except (TypeError, ValueError):
        pnl_pct_f = None
    count = len(rows)
    bits = [f"Last exit · {sym}"]
    if exit_reason:
        bits.append(exit_reason)
    if held:
        bits.append(held)
    if pnl_pct_f is not None:
        bits.append(f"{pnl_pct_f:+.1f}%")
    if count > 1:
        bits.append(f"{count} closed")
    line = " · ".join(bits)
    if len(line) > 96:
        line = line[:95] + "…"
    if pnl_pct_f is None:
        tone = "flat"
    elif pnl_pct_f >= 0:
        tone = "up"
    else:
        tone = "down"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "count": count,
        "symbol": sym,
        "exit_reason": exit_reason,
        "profit_loss_pct": pnl_pct_f,
    }


def _trader_runtime_view() -> dict[str, Any]:
    """Read-only + editable trader/desk knobs for Ops — never include API keys."""
    from stock_checker import __version__
    from stock_checker.trader_config import load_trader_config

    data_dir = Path(os.getenv("DATA_DIR", "/data"))
    cfg = load_trader_config(data_dir)

    ai_mode = str(cfg.get("ai_mode") or "off")
    ai_model = str(cfg.get("ai_model") or "gemma4:latest")
    explicit = (os.getenv("LLM_BACKEND") or "").strip().lower()
    if explicit in {"ollama", "openai", "openai-compatible", "off", "none"}:
        llm_backend = "none" if explicit in {"off", "none"} else explicit
    elif any(
        (os.getenv(k) or "").strip()
        for k in ("OPENAI_BASE_URL", "OPENAI_API_KEY", "LLM_API_KEY", "GROQ_API_KEY")
    ):
        llm_backend = "openai-compatible"
    elif ai_mode != "off":
        llm_backend = "ollama"
    else:
        # Still show ollama if host is configured — Ops can flip AI on without
        # implying the trade loop is already calling it.
        if (os.getenv("OLLAMA_HOST") or "").strip():
            llm_backend = "ollama"
        else:
            llm_backend = "none"

    key_set = any(
        (os.getenv(k) or "").strip()
        for k in ("OPENAI_API_KEY", "LLM_API_KEY", "GROQ_API_KEY")
    )
    live_marks = os.getenv("DESK_LIVE_MARKS", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    regime_snap = _load_json(data_dir / "market_regime.json", {})
    if not isinstance(regime_snap, dict):
        regime_snap = {}
    calm_snap = _load_json(data_dir / "paper_calm.json", {})
    if not isinstance(calm_snap, dict):
        calm_snap = {}
    portfolio = _load_json(data_dir / "portfolio.json", {})
    if not isinstance(portfolio, dict):
        portfolio = {}
    free_legs = int(
        portfolio.get("free_legs_per_month")
        or cfg.get("free_legs_per_month")
        or 0
    )
    allowance_used = int(portfolio.get("fee_allowance_used") or 0)
    allowance_month = str(portfolio.get("fee_allowance_month") or "")
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    if allowance_month != current_month:
        allowance_used = 0
    allowance_remaining = max(0, free_legs - allowance_used)

    return {
        "trader_version": __version__,
        "ai_mode": ai_mode,
        "ai_model": ai_model,
        "llm_backend": llm_backend,
        "llm_key_set": key_set,
        "ai_multi_role": bool(cfg.get("ai_multi_role", True)),
        # Match docker-compose intelligent-trader defaults (not live-parsed argv).
        # Prefer Ops/file knobs over hard-coded compose display defaults.
        "max_positions": int(cfg.get("max_positions") or 5),
        "min_hold_hours": float(cfg.get("min_hold_hours") or 24),
        "scan_interval_min": 15,
        "trade_interval_min": 5,
        "desk_live_marks": live_marks,
        "regime_gate": bool(cfg.get("regime_gate", True)),
        "rs_gate": bool(cfg.get("rs_gate", True)),
        "breadth_gate": bool(cfg.get("breadth_gate", True)),
        "promote_experiment_strategy": bool(
            cfg.get("promote_experiment_strategy", False)
        ),
        "fee_preset": str(cfg.get("fee_preset") or "revolut_standard"),
        "commission_rate": float(cfg.get("commission_rate") or 0.0025),
        "commission_min_eur": float(cfg.get("commission_min_eur") or 1.0),
        "free_legs_per_month": free_legs,
        "fee_allowance_used": allowance_used,
        "fee_allowance_remaining": allowance_remaining,
        "fee_allowance_month": current_month,
        "stock_regime": str(regime_snap.get("stock_regime") or "—"),
        "crypto_regime": str(regime_snap.get("crypto_regime") or "—"),
        "regime_updated": str(regime_snap.get("updated_at") or ""),
        "calm_streak_days": int(calm_snap.get("streak_days") or 0),
        "calm_required_days": int(calm_snap.get("required_days") or 30),
        "calm_ready": bool(calm_snap.get("ready_for_compose_default")),
        "calm_detail": str(calm_snap.get("detail") or ""),
        "calm_hint": (
            "Compose promote default unlocks after 30 calm UTC days "
            "(promote on, book ≤ max, quiet fees)."
        ),
        "config_source": "file"
        if (data_dir / "trader_config.json").is_file()
        else "env",
        "ollama_host": (os.getenv("OLLAMA_HOST") or "").strip() or "—",
    }


def _upsert_scan_breadth_daily(
    data_dir: Path, pulse: dict[str, Any], scan_time: str
) -> list[dict[str, Any]]:
    """Persist one UTC-day scan-pulse row (upsert). Keeps last 30 days."""
    path = data_dir / "scan_breadth_daily.json"
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows_raw = _load_json(path, [])
    rows: list[dict[str, Any]] = [
        r for r in rows_raw if isinstance(r, dict) and r.get("day")
    ] if isinstance(rows_raw, list) else []
    archive_name = ""
    arch = find_day_scan_archive(data_dir, day)
    if arch is not None:
        archive_name = arch.name
    entry = {
        "day": day,
        "scan_time": scan_time or "",
        "crypto_n": int(pulse.get("crypto_n") or 0),
        "crypto_up": int(pulse.get("crypto_up") or 0),
        "crypto_down": int(pulse.get("crypto_down") or 0),
        "crypto_avg_chg": float(pulse.get("crypto_avg_chg") or 0.0),
        "crypto_big_movers": int(pulse.get("crypto_big_movers") or 0),
        "stock_breakouts_n": int(pulse.get("stock_breakouts_n") or 0),
        "stock_within_5pct_high": int(pulse.get("stock_within_5pct_high") or 0),
        "stock_scan_n": int(pulse.get("stock_scan_n") or 0),
        "stock_scan_up": int(pulse.get("stock_scan_up") or 0),
        "stock_scan_down": int(pulse.get("stock_scan_down") or 0),
        "archive_file": archive_name,
    }
    out = [r for r in rows if str(r.get("day")) != day]
    out.append(entry)
    out.sort(key=lambda r: str(r.get("day") or ""))
    out = out[-30:]
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=2) + "\n")
    except OSError:
        return _annotate_scan_history(data_dir, rows[-14:])
    return _annotate_scan_history(data_dir, out[-14:])


def find_day_scan_archive(data_dir: Path, day: str) -> Optional[Path]:
    """Latest opportunities_YYYYMMDD_*.txt for a UTC calendar day."""
    day_s = str(day or "").strip()
    if len(day_s) != 10 or day_s[4] != "-" or day_s[7] != "-":
        return None
    ymd = day_s.replace("-", "")
    if not ymd.isdigit():
        return None
    arch = Path(data_dir) / "archive"
    if not arch.is_dir():
        return None
    files = sorted(arch.glob(f"opportunities_{ymd}_*.txt"))
    return files[-1] if files else None


def scan_list_ratio_pct(part: int, whole: int) -> float | None:
    """Share of a scan-list count vs its denominator (StockBee-lite; display only)."""
    n = int(whole or 0)
    if n <= 0:
        return None
    m = max(0, int(part or 0))
    return round(100.0 * m / n, 1)


def crypto_mover_ratio_pct(movers: int, leaders_n: int) -> float | None:
    """Share of scan crypto leaders with |24h| ≥ 4% (StockBee-lite; display only)."""
    return scan_list_ratio_pct(movers, leaders_n)


def near_high_ratio_pct(near: int, breakouts_n: int) -> float | None:
    """Share of stock breakouts within 5% of high (StockBee-lite; display only)."""
    return scan_list_ratio_pct(near, breakouts_n)


def stock_advance_ratio_pct(up: int, priced_n: int) -> float | None:
    """Share of priced scan stocks advancing (StockBee participation; display only)."""
    return scan_list_ratio_pct(up, priced_n)


def crypto_advance_ratio_pct(up: int, leaders_n: int) -> float | None:
    """Share of scan crypto leaders advancing (StockBee participation; display only)."""
    return scan_list_ratio_pct(up, leaders_n)


# StockBee-lite thrust: both ±4% and near-high ratios at/above this % (display only).
DEFAULT_BREADTH_THRUST_MIN_PCT = 25.0
# Dual advance: stock + crypto majority participation (risk-on tape; display only).
DEFAULT_DUAL_ADVANCE_MIN_PCT = 50.0
# Tape split: one sleeve strong, the other weak (cross-asset divergence; display only).
DEFAULT_TAPE_SPLIT_STRONG_PCT = 60.0
DEFAULT_TAPE_SPLIT_WEAK_PCT = 40.0
# Risk-off: both sleeves weak (mirror of dual-advance; display only).
DEFAULT_RISK_OFF_MAX_PCT = DEFAULT_TAPE_SPLIT_WEAK_PCT


def is_dual_advance_day(
    stock_adv_pct: float | None,
    crypto_adv_pct: float | None,
    *,
    min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
) -> bool:
    """True when stock and crypto advance % both clear min_pct (scan-list; display only)."""
    if stock_adv_pct is None or crypto_adv_pct is None:
        return False
    floor = float(min_pct)
    return float(stock_adv_pct) >= floor and float(crypto_adv_pct) >= floor


def is_tape_split_day(
    stock_adv_pct: float | None,
    crypto_adv_pct: float | None,
    *,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
) -> bool:
    """True when one advance % is strong and the other weak (scan-list; display only).

    Mutually exclusive with dual-advance at the default floors (50/50 vs 60/40).
    """
    if stock_adv_pct is None or crypto_adv_pct is None:
        return False
    a = float(stock_adv_pct)
    b = float(crypto_adv_pct)
    hi = max(a, b)
    lo = min(a, b)
    return hi >= float(strong_pct) and lo <= float(weak_pct)


def is_risk_off_day(
    stock_adv_pct: float | None,
    crypto_adv_pct: float | None,
    *,
    max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
) -> bool:
    """True when stock and crypto advance % are both ≤ max_pct (scan-list; display only).

    Completes StockBee-lite tape: risk-on · split · risk-off. Exclusive of dual /
    split at defaults (both ≤40% cannot be ≥50% or 60/40).
    """
    if stock_adv_pct is None or crypto_adv_pct is None:
        return False
    ceiling = float(max_pct)
    return float(stock_adv_pct) <= ceiling and float(crypto_adv_pct) <= ceiling


def breadth_tape_label(
    stock_adv_pct: float | None,
    crypto_adv_pct: float | None,
    *,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    risk_off_max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
) -> str:
    """Short tape tag: risk-on · split · risk-off · mixed · empty. Display only.

    Empty means a sleeve is missing (not priced). Mid-range both-sleeved days
    are ``mixed`` — do not conflate with missing data (StockBee honesty).
    """
    if stock_adv_pct is None or crypto_adv_pct is None:
        return ""
    if is_dual_advance_day(stock_adv_pct, crypto_adv_pct, min_pct=dual_min_pct):
        return "risk-on"
    if is_tape_split_day(
        stock_adv_pct,
        crypto_adv_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
    ):
        return "split"
    if is_risk_off_day(
        stock_adv_pct, crypto_adv_pct, max_pct=risk_off_max_pct
    ):
        return "risk-off"
    return "mixed"


def is_tape_flip(
    prev_label: str | None,
    curr_label: str | None,
) -> bool:
    """True when both labels are known and differ (scan-list; display only)."""
    prev = str(prev_label or "").strip()
    curr = str(curr_label or "").strip()
    if not prev or not curr:
        return False
    return prev != curr


def breadth_prev_tape_label(
    rows: list[dict[str, Any]],
    *,
    through_day: str | None = None,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    risk_off_max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
) -> str:
    """Tape label of the day before newest (or before through_day). Display only."""
    usable: list[dict[str, Any]] = []
    want = str(through_day or "").strip()
    for r in rows:
        if not isinstance(r, dict):
            continue
        usable.append(r)
        if want and str(r.get("day") or "") == want:
            break
    else:
        if want:
            return ""
    if len(usable) < 2:
        return ""
    return _row_tape_label(
        usable[-2],
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )

def is_breadth_thrust_day(
    mover_pct: float | None,
    near_high_pct: float | None,
    *,
    min_pct: float = DEFAULT_BREADTH_THRUST_MIN_PCT,
) -> bool:
    """True when ±4% and near-high ratios both clear min_pct (scan-list; display only)."""
    if mover_pct is None or near_high_pct is None:
        return False
    floor = float(min_pct)
    return float(mover_pct) >= floor and float(near_high_pct) >= floor


def _breadth_ending_streak(
    rows: list[dict[str, Any]],
    predicate: Callable[[dict[str, Any]], bool],
    *,
    through_day: str | None = None,
) -> int:
    """Consecutive True days ending at newest (or through_day). Display only."""
    usable: list[dict[str, Any]] = []
    want = str(through_day or "").strip()
    for r in rows:
        if not isinstance(r, dict):
            continue
        usable.append(r)
        if want and str(r.get("day") or "") == want:
            break
    else:
        if want:
            return 0
    streak = 0
    for r in reversed(usable):
        if predicate(r):
            streak += 1
        else:
            break
    return streak


def _breadth_days_since(
    rows: list[dict[str, Any]],
    predicate: Callable[[dict[str, Any]], bool],
    *,
    through_day: str | None = None,
) -> int | None:
    """History rows since last True day (0 if newest matches). Display only.

    StockBee-lite: when the tape is quiet, friends need staleness of the last
    confirmation — not only ending streaks. ``None`` means never seen.
    """
    usable: list[dict[str, Any]] = []
    want = str(through_day or "").strip()
    for r in rows:
        if not isinstance(r, dict):
            continue
        usable.append(r)
        if want and str(r.get("day") or "") == want:
            break
    else:
        if want:
            return None
    for i, r in enumerate(reversed(usable)):
        if predicate(r):
            return i
    return None


def breadth_days_since_thrust(
    rows: list[dict[str, Any]],
    *,
    min_pct: float = DEFAULT_BREADTH_THRUST_MIN_PCT,
    through_day: str | None = None,
) -> int | None:
    """Days since last thrust (0 = now). Display only; scan-list history."""
    return _breadth_days_since(
        rows,
        lambda r: _row_is_thrust(r, min_pct=min_pct),
        through_day=through_day,
    )


def breadth_days_since_risk_on(
    rows: list[dict[str, Any]],
    *,
    min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    through_day: str | None = None,
) -> int | None:
    """Days since last risk-on / dual-advance (0 = now). Display only."""
    return _breadth_days_since(
        rows,
        lambda r: _row_is_dual_advance(r, min_pct=min_pct),
        through_day=through_day,
    )


def breadth_days_since_risk_off(
    rows: list[dict[str, Any]],
    *,
    max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
    through_day: str | None = None,
) -> int | None:
    """Days since last risk-off (0 = now). Display only; scan-list history.

    StockBee-lite: when the tape recovers, friends need washout staleness —
    how long since both sleeves were weak — not only ending risk-off streaks.
    """
    return _breadth_days_since(
        rows,
        lambda r: _row_is_risk_off(r, max_pct=max_pct),
        through_day=through_day,
    )


def _row_is_thrust(
    row: dict[str, Any],
    *,
    min_pct: float = DEFAULT_BREADTH_THRUST_MIN_PCT,
) -> bool:
    """Resolve thrust flag from annotated or raw daily pulse row."""
    if "is_thrust" in row:
        return bool(row.get("is_thrust"))
    return is_breadth_thrust_day(
        _resolve_crypto_mover_pct(row),
        _resolve_near_high_pct(row),
        min_pct=min_pct,
    )


def _row_is_dual_advance(
    row: dict[str, Any],
    *,
    min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
) -> bool:
    """Resolve dual-advance / risk-on from annotated or raw daily pulse row."""
    if "is_dual_advance" in row:
        return bool(row.get("is_dual_advance"))
    return is_dual_advance_day(
        _resolve_stock_advance_pct(row),
        _resolve_crypto_advance_pct(row),
        min_pct=min_pct,
    )


def _row_is_tape_split(
    row: dict[str, Any],
    *,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
) -> bool:
    """Resolve tape-split from annotated or raw daily pulse row."""
    if "is_tape_split" in row:
        return bool(row.get("is_tape_split"))
    return is_tape_split_day(
        _resolve_stock_advance_pct(row),
        _resolve_crypto_advance_pct(row),
        strong_pct=strong_pct,
        weak_pct=weak_pct,
    )


def _row_is_risk_off(
    row: dict[str, Any],
    *,
    max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
) -> bool:
    """Resolve risk-off from annotated or raw daily pulse row."""
    if "is_risk_off" in row:
        return bool(row.get("is_risk_off"))
    return is_risk_off_day(
        _resolve_stock_advance_pct(row),
        _resolve_crypto_advance_pct(row),
        max_pct=max_pct,
    )


def _row_tape_label(
    row: dict[str, Any],
    *,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    risk_off_max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
) -> str:
    """Resolve tape tag from annotated or raw daily pulse row."""
    if "tape_label" in row:
        return str(row.get("tape_label") or "").strip()
    if _row_is_dual_advance(row, min_pct=dual_min_pct):
        return "risk-on"
    if _row_is_tape_split(row, strong_pct=strong_pct, weak_pct=weak_pct):
        return "split"
    if _row_is_risk_off(row, max_pct=risk_off_max_pct):
        return "risk-off"
    if row.get("is_mixed"):
        return "mixed"
    return breadth_tape_label(
        _resolve_stock_advance_pct(row),
        _resolve_crypto_advance_pct(row),
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )


def _row_is_mixed(
    row: dict[str, Any],
    *,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    risk_off_max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
) -> bool:
    """True when both sleeves priced and tape is mid-range mixed."""
    return (
        _row_tape_label(
            row,
            dual_min_pct=dual_min_pct,
            strong_pct=strong_pct,
            weak_pct=weak_pct,
            risk_off_max_pct=risk_off_max_pct,
        )
        == "mixed"
    )


def breadth_thrust_streak(
    rows: list[dict[str, Any]],
    *,
    min_pct: float = DEFAULT_BREADTH_THRUST_MIN_PCT,
    through_day: str | None = None,
) -> int:
    """Consecutive thrust days ending at newest (or through_day). Display only.

    StockBee-lite: a multi-day thrust streak is more useful than a raw count.
    Rows are chronological (oldest → newest). Optional ``through_day`` cuts the
    series at that UTC day (scan-log drill-down).
    """
    return _breadth_ending_streak(
        rows,
        lambda r: _row_is_thrust(r, min_pct=min_pct),
        through_day=through_day,
    )


def breadth_dual_advance_streak(
    rows: list[dict[str, Any]],
    *,
    min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    through_day: str | None = None,
) -> int:
    """Consecutive risk-on (dual-advance) days ending at newest. Display only."""
    return _breadth_ending_streak(
        rows,
        lambda r: _row_is_dual_advance(r, min_pct=min_pct),
        through_day=through_day,
    )


def breadth_tape_split_streak(
    rows: list[dict[str, Any]],
    *,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    through_day: str | None = None,
) -> int:
    """Consecutive tape-split days ending at newest. Display only."""
    return _breadth_ending_streak(
        rows,
        lambda r: _row_is_tape_split(r, strong_pct=strong_pct, weak_pct=weak_pct),
        through_day=through_day,
    )


def breadth_risk_off_streak(
    rows: list[dict[str, Any]],
    *,
    max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
    through_day: str | None = None,
) -> int:
    """Consecutive risk-off days ending at newest. Display only."""
    return _breadth_ending_streak(
        rows,
        lambda r: _row_is_risk_off(r, max_pct=max_pct),
        through_day=through_day,
    )


def build_breadth_thrust_summary(
    rows: list[dict[str, Any]],
    *,
    min_pct: float = DEFAULT_BREADTH_THRUST_MIN_PCT,
) -> dict[str, Any]:
    """Count recent scan-list thrust days + ending streak. Display only."""
    days = 0
    thrust_n = 0
    latest = False
    for r in rows:
        if not isinstance(r, dict):
            continue
        flag = _row_is_thrust(r, min_pct=min_pct)
        days += 1
        if flag:
            thrust_n += 1
            latest = True
        else:
            latest = False
    empty = {
        "ready": False,
        "days": 0,
        "thrust_n": 0,
        "streak": 0,
        "days_since": None,
        "latest": False,
        "min_pct": float(min_pct),
        "line": "",
        "tone": "flat",
    }
    if days <= 0:
        return empty
    streak = breadth_thrust_streak(rows, min_pct=min_pct)
    days_since = breadth_days_since_thrust(rows, min_pct=min_pct)
    tone = "up" if latest else ("flat" if thrust_n else "down")
    bits: list[str] = []
    if latest:
        bits.append("thrust now")
    elif days_since is not None and days_since > 0:
        bits.append(f"{days_since}d since thrust")
    if streak >= 2:
        bits.append(f"streak {streak}")
    bits.append(f"{thrust_n}/{days} thrust days (≥{min_pct:.0f}% ±4% + near-high)")
    return {
        "ready": True,
        "days": days,
        "thrust_n": thrust_n,
        "streak": streak,
        "days_since": days_since,
        "latest": latest,
        "min_pct": float(min_pct),
        "line": " · ".join(bits),
        "tone": tone,
    }


def build_breadth_tape_summary(
    rows: list[dict[str, Any]],
    *,
    dual_min_pct: float = DEFAULT_DUAL_ADVANCE_MIN_PCT,
    strong_pct: float = DEFAULT_TAPE_SPLIT_STRONG_PCT,
    weak_pct: float = DEFAULT_TAPE_SPLIT_WEAK_PCT,
    risk_off_max_pct: float = DEFAULT_RISK_OFF_MAX_PCT,
) -> dict[str, Any]:
    """Count risk-on / split / risk-off / mixed days + ending streaks. Display only."""
    days = 0
    dual_n = 0
    split_n = 0
    risk_off_n = 0
    mixed_n = 0
    latest_dual = False
    latest_split = False
    latest_risk_off = False
    latest_mixed = False
    latest_label = ""
    for r in rows:
        if not isinstance(r, dict):
            continue
        days += 1
        dual = _row_is_dual_advance(r, min_pct=dual_min_pct)
        split = _row_is_tape_split(r, strong_pct=strong_pct, weak_pct=weak_pct)
        risk_off = _row_is_risk_off(r, max_pct=risk_off_max_pct)
        label = _row_tape_label(
            r,
            dual_min_pct=dual_min_pct,
            strong_pct=strong_pct,
            weak_pct=weak_pct,
            risk_off_max_pct=risk_off_max_pct,
        )
        latest_label = label
        if dual:
            dual_n += 1
            latest_dual = True
            latest_split = False
            latest_risk_off = False
            latest_mixed = False
        elif split:
            split_n += 1
            latest_dual = False
            latest_split = True
            latest_risk_off = False
            latest_mixed = False
        elif risk_off:
            risk_off_n += 1
            latest_dual = False
            latest_split = False
            latest_risk_off = True
            latest_mixed = False
        elif label == "mixed":
            mixed_n += 1
            latest_dual = False
            latest_split = False
            latest_risk_off = False
            latest_mixed = True
        else:
            latest_dual = False
            latest_split = False
            latest_risk_off = False
            latest_mixed = False
    empty = {
        "ready": False,
        "days": 0,
        "dual_n": 0,
        "split_n": 0,
        "risk_off_n": 0,
        "mixed_n": 0,
        "dual_streak": 0,
        "split_streak": 0,
        "risk_off_streak": 0,
        "days_since_risk_on": None,
        "days_since_risk_off": None,
        "latest_dual": False,
        "latest_split": False,
        "latest_risk_off": False,
        "latest_mixed": False,
        "latest_label": "",
        "prev_label": "",
        "tape_flip": False,
        "line": "",
        "tone": "flat",
    }
    if days <= 0:
        return empty
    dual_streak = breadth_dual_advance_streak(rows, min_pct=dual_min_pct)
    split_streak = breadth_tape_split_streak(
        rows, strong_pct=strong_pct, weak_pct=weak_pct
    )
    risk_off_streak = breadth_risk_off_streak(rows, max_pct=risk_off_max_pct)
    days_since_risk_on = breadth_days_since_risk_on(rows, min_pct=dual_min_pct)
    days_since_risk_off = breadth_days_since_risk_off(
        rows, max_pct=risk_off_max_pct
    )
    prev_label = breadth_prev_tape_label(
        rows,
        dual_min_pct=dual_min_pct,
        strong_pct=strong_pct,
        weak_pct=weak_pct,
        risk_off_max_pct=risk_off_max_pct,
    )
    flip = is_tape_flip(prev_label, latest_label)
    if latest_dual:
        tone = "up"
    elif latest_split or latest_risk_off:
        tone = "down"
    else:
        tone = "flat"
    bits: list[str] = []
    if latest_dual:
        bits.append("risk-on now")
        if dual_streak >= 2:
            bits.append(f"streak {dual_streak}")
    elif latest_split:
        bits.append("split now")
        if split_streak >= 2:
            bits.append(f"streak {split_streak}")
    elif latest_risk_off:
        bits.append("risk-off now")
        if risk_off_streak >= 2:
            bits.append(f"streak {risk_off_streak}")
    elif latest_mixed:
        bits.append("mixed now")
    if (
        not latest_dual
        and days_since_risk_on is not None
        and days_since_risk_on > 0
    ):
        bits.append(f"{days_since_risk_on}d since risk-on")
    if (
        not latest_risk_off
        and days_since_risk_off is not None
        and days_since_risk_off > 0
    ):
        bits.append(f"{days_since_risk_off}d since risk-off")
    if flip:
        bits.append(f"flipped {prev_label}→{latest_label}")
    bits.append(
        f"{dual_n}/{days} risk-on · {split_n}/{days} split · "
        f"{risk_off_n}/{days} risk-off · {mixed_n}/{days} mixed"
    )
    return {
        "ready": True,
        "days": days,
        "dual_n": dual_n,
        "split_n": split_n,
        "risk_off_n": risk_off_n,
        "mixed_n": mixed_n,
        "dual_streak": dual_streak,
        "split_streak": split_streak,
        "risk_off_streak": risk_off_streak,
        "days_since_risk_on": days_since_risk_on,
        "days_since_risk_off": days_since_risk_off,
        "latest_dual": latest_dual,
        "latest_split": latest_split,
        "latest_risk_off": latest_risk_off,
        "latest_mixed": latest_mixed,
        "latest_label": latest_label,
        "prev_label": prev_label,
        "tape_flip": flip,
        "line": " · ".join(bits),
        "tone": tone,
    }


def _annotate_scan_history(
    data_dir: Path, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Attach scan-log link flags + ±4% / near-high ratios for Breadth Recent days."""
    out: list[dict[str, Any]] = []
    for r in rows:
        row = dict(r)
        day = str(row.get("day") or "")
        path = find_day_scan_archive(data_dir, day)
        row["has_scan_log"] = path is not None
        if path is not None:
            row["archive_file"] = path.name
            row["scan_log_href"] = f"/desk/scan-log/{day}"
        else:
            row["scan_log_href"] = ""
        crypto_n = int(row.get("crypto_n") or 0)
        if crypto_n <= 0:
            # Legacy daily rows often omit crypto_n — infer from A/D counts.
            crypto_n = int(row.get("crypto_up") or 0) + int(row.get("crypto_down") or 0)
        movers = int(row.get("crypto_big_movers") or 0)
        pct = crypto_mover_ratio_pct(movers, crypto_n)
        row["crypto_n_resolved"] = crypto_n
        row["crypto_mover_pct"] = pct
        breakouts_n = int(row.get("stock_breakouts_n") or 0)
        near = int(row.get("stock_within_5pct_high") or 0)
        near_pct = near_high_ratio_pct(near, breakouts_n)
        row["near_high_pct"] = near_pct
        row["is_thrust"] = is_breadth_thrust_day(pct, near_pct)
        stock_up = int(row.get("stock_scan_up") or 0)
        stock_down = int(row.get("stock_scan_down") or 0)
        stock_n = int(row.get("stock_scan_n") or 0) or (stock_up + stock_down)
        row["stock_scan_n_resolved"] = stock_n
        stock_adv = stock_advance_ratio_pct(stock_up, stock_n)
        crypto_up = int(row.get("crypto_up") or 0)
        crypto_adv = crypto_advance_ratio_pct(crypto_up, crypto_n)
        row["stock_advance_pct"] = stock_adv
        row["crypto_advance_pct"] = crypto_adv
        row["is_dual_advance"] = is_dual_advance_day(stock_adv, crypto_adv)
        row["is_tape_split"] = is_tape_split_day(stock_adv, crypto_adv)
        row["is_risk_off"] = is_risk_off_day(stock_adv, crypto_adv)
        row["tape_label"] = breadth_tape_label(stock_adv, crypto_adv)
        row["is_mixed"] = row["tape_label"] == "mixed"
        out.append(row)
    # Second pass: prior-day tape + flip (needs chronological neighbors).
    for i, row in enumerate(out):
        prev = out[i - 1] if i > 0 else None
        prev_label = str((prev or {}).get("tape_label") or "").strip()
        curr_label = str(row.get("tape_label") or "").strip()
        row["prev_tape_label"] = prev_label
        row["tape_flip"] = is_tape_flip(prev_label, curr_label)
    return out


def scan_breadth_pulse_for_day(
    data_dir: Path, day: str
) -> dict[str, Any] | None:
    """UTC-day scan-list pulse row from Breadth history (display only)."""
    rows = _load_json(data_dir / "scan_breadth_daily.json", [])
    if not isinstance(rows, list):
        return None
    want = str(day or "").strip()
    if not want:
        return None
    for row in rows:
        if isinstance(row, dict) and str(row.get("day") or "") == want:
            return row
    return None


def build_breadth_glance(
    pulse: dict[str, Any] | None,
    *,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One-line scan-list glance for HTML screens + Charts API (display only; not a gate).

    tradermonty “verified estimate snapshots” + xang1234: show priced counts and
    label the pulse as a scan-list **estimate**, never full-universe A/D.
    Optional ``history`` adds StockBee thrust/risk-on/risk-off streak and days-since
    when the ending day is quiet.
    """
    empty = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "crypto_net": 0,
        "stock_net": 0,
        "near_high": 0,
        "near_high_pct": None,
        "big_movers": 0,
        "mover_pct": None,
        "is_thrust": False,
        "thrust_streak": 0,
        "days_since_thrust": None,
        "is_dual_advance": False,
        "is_tape_split": False,
        "is_risk_off": False,
        "is_mixed": False,
        "tape_label": "",
        "prev_tape_label": "",
        "tape_flip": False,
        "dual_advance_streak": 0,
        "tape_split_streak": 0,
        "risk_off_streak": 0,
        "days_since_risk_on": None,
        "days_since_risk_off": None,
        "crypto_n": 0,
        "stock_n": 0,
        "stock_advance_pct": None,
        "crypto_advance_pct": None,
        "estimate": True,
        "full_universe": False,
    }
    if not isinstance(pulse, dict):
        return empty
    crypto_up = int(pulse.get("crypto_up") or 0)
    crypto_down = int(pulse.get("crypto_down") or 0)
    stock_up = int(pulse.get("stock_scan_up") or 0)
    stock_down = int(pulse.get("stock_scan_down") or 0)
    # Infer n from up+down when daily rows omit crypto_n / stock_scan_n.
    crypto_n = int(pulse.get("crypto_n") or 0) or (crypto_up + crypto_down)
    stock_n = int(pulse.get("stock_scan_n") or 0) or (stock_up + stock_down)
    near = int(pulse.get("stock_within_5pct_high") or 0)
    breakouts_n = int(pulse.get("stock_breakouts_n") or 0)
    movers = int(pulse.get("crypto_big_movers") or 0)
    mover_pct = crypto_mover_ratio_pct(movers, crypto_n)
    near_pct = near_high_ratio_pct(near, breakouts_n)
    advance_pct = stock_advance_ratio_pct(stock_up, stock_n)
    crypto_adv_pct = crypto_advance_ratio_pct(crypto_up, crypto_n)
    thrust = is_breadth_thrust_day(mover_pct, near_pct)
    dual = is_dual_advance_day(advance_pct, crypto_adv_pct)
    split = is_tape_split_day(advance_pct, crypto_adv_pct)
    risk_off = is_risk_off_day(advance_pct, crypto_adv_pct)
    tape = breadth_tape_label(advance_pct, crypto_adv_pct)
    mixed = tape == "mixed"
    if crypto_n <= 0 and stock_n <= 0 and breakouts_n <= 0:
        return empty

    crypto_net = crypto_up - crypto_down
    stock_net = stock_up - stock_down
    hist = [r for r in (history or []) if isinstance(r, dict)]
    day = str(pulse.get("day") or "").strip()
    day_cut = day or None
    streak = breadth_thrust_streak(hist, through_day=day_cut) if hist else 0
    dual_streak = (
        breadth_dual_advance_streak(hist, through_day=day_cut) if hist else 0
    )
    split_streak = (
        breadth_tape_split_streak(hist, through_day=day_cut) if hist else 0
    )
    risk_off_streak = (
        breadth_risk_off_streak(hist, through_day=day_cut) if hist else 0
    )
    days_since_thrust = (
        breadth_days_since_thrust(hist, through_day=day_cut) if hist else None
    )
    days_since_risk_on = (
        breadth_days_since_risk_on(hist, through_day=day_cut) if hist else None
    )
    days_since_risk_off = (
        breadth_days_since_risk_off(hist, through_day=day_cut) if hist else None
    )
    prev_tape = (
        breadth_prev_tape_label(hist, through_day=day_cut) if hist else ""
    )
    flip = is_tape_flip(prev_tape, tape)
    parts: list[str] = []
    score = 0
    if crypto_n > 0:
        if crypto_adv_pct is not None:
            parts.append(
                f"crypto {crypto_up}/{crypto_down} ({crypto_net:+d}) of {crypto_n}"
                f" · adv {crypto_adv_pct:.0f}%"
            )
        else:
            parts.append(
                f"crypto {crypto_up}/{crypto_down} ({crypto_net:+d}) of {crypto_n}"
            )
        score += crypto_net
    if stock_n > 0:
        if advance_pct is not None:
            parts.append(
                f"stock {stock_up}/{stock_down} ({stock_net:+d}) of {stock_n}"
                f" · adv {advance_pct:.0f}%"
            )
        else:
            parts.append(
                f"stock {stock_up}/{stock_down} ({stock_net:+d}) of {stock_n}"
            )
        score += stock_net
    if breakouts_n > 0 or near > 0:
        if near_pct is not None and breakouts_n > 0:
            parts.append(f"{near} near-high ({near_pct:.0f}%)")
        else:
            parts.append(f"{near} near-high")
    if movers > 0:
        if mover_pct is not None and crypto_n > 0:
            parts.append(f"{movers} ±4% ({mover_pct:.0f}%)")
        else:
            parts.append(f"{movers} ±4% movers")
    if thrust and streak >= 2:
        parts.append(f"thrust · streak {streak}")
    elif thrust:
        parts.append("thrust")
    elif days_since_thrust is not None and days_since_thrust > 0:
        parts.append(f"{days_since_thrust}d since thrust")
    if dual and dual_streak >= 2:
        parts.append(f"risk-on · streak {dual_streak}")
    elif split and split_streak >= 2:
        parts.append(f"split · streak {split_streak}")
    elif risk_off and risk_off_streak >= 2:
        parts.append(f"risk-off · streak {risk_off_streak}")
    elif tape:
        parts.append(tape)
    if (
        not dual
        and days_since_risk_on is not None
        and days_since_risk_on > 0
    ):
        parts.append(f"{days_since_risk_on}d since risk-on")
    if (
        not risk_off
        and days_since_risk_off is not None
        and days_since_risk_off > 0
    ):
        parts.append(f"{days_since_risk_off}d since risk-off")
    if flip:
        parts.append(f"flipped {prev_tape}→{tape}")
    if not parts:
        return empty
    # Coverage honesty: verified *scan-list* estimate, never full-universe.
    # Keep this suffix when truncating — days-since / streaks can push length.
    coverage = "estimate · not full-universe"
    core = " · ".join(parts)
    line = f"{core} · {coverage}"
    # StockBee days-since / tape bits grow the line; keep coverage when trimming.
    max_len = 180
    if len(line) > max_len:
        keep = f"… · {coverage}"
        budget = max_len - len(keep)
        if budget < 12:
            line = coverage if len(coverage) <= max_len else coverage[: max_len - 1] + "…"
        else:
            line = core[:budget].rstrip(" ·") + keep
    if score > 0:
        tone = "up"
    elif score < 0:
        tone = "down"
    else:
        tone = "flat"
    return {
        "ready": True,
        "tone": tone,
        "line": line,
        "crypto_net": crypto_net,
        "stock_net": stock_net if stock_n > 0 else 0,
        "near_high": near,
        "near_high_pct": near_pct,
        "big_movers": movers,
        "mover_pct": mover_pct,
        "is_thrust": thrust,
        "thrust_streak": streak,
        "days_since_thrust": days_since_thrust,
        "is_dual_advance": dual,
        "is_tape_split": split,
        "is_risk_off": risk_off,
        "is_mixed": mixed,
        "tape_label": tape,
        "prev_tape_label": prev_tape,
        "tape_flip": flip,
        "dual_advance_streak": dual_streak,
        "tape_split_streak": split_streak,
        "risk_off_streak": risk_off_streak,
        "days_since_risk_on": days_since_risk_on,
        "days_since_risk_off": days_since_risk_off,
        "crypto_n": crypto_n,
        "stock_n": stock_n if stock_n > 0 else 0,
        "stock_advance_pct": advance_pct if stock_n > 0 else None,
        "crypto_advance_pct": crypto_adv_pct if crypto_n > 0 else None,
        "estimate": True,
        "full_universe": False,
    }


def build_breadth_ad_spark(
    rows: list[dict[str, Any]],
    *,
    up_key: str = "crypto_up",
    down_key: str = "crypto_down",
    label: str = "Crypto",
    aria_unit: str = "leaders up minus down",
    width: float = 320.0,
    height: float = 52.0,
    pad: float = 5.0,
) -> dict[str, Any]:
    """Inline SVG: multi-day A/D net (up−down). Display only; needs ≥2 days."""
    series: list[tuple[str, int]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        day = str(r.get("day") or "").strip()
        if not day:
            continue
        # Skip days that never recorded this A/D pair (old history rows).
        if up_key not in r and down_key not in r:
            continue
        up = int(r.get(up_key) or 0)
        down = int(r.get(down_key) or 0)
        series.append((day, up - down))
    empty = {
        "ready": False,
        "n": len(series),
        "svg": "",
        "aria": "",
        "latest_net": 0,
        "first_day": "",
        "last_day": "",
        "label": label,
    }
    if len(series) < 2:
        return empty

    nets = [net for _, net in series]
    y_min = min(min(nets), 0)
    y_max = max(max(nets), 0)
    if y_min == y_max:
        y_min -= 1
        y_max += 1
    span = float(y_max - y_min)
    inner_w = width - 2 * pad
    inner_h = height - 2 * pad
    n = len(series)

    def _xy(i: int, net: int) -> tuple[float, float]:
        x = pad + (inner_w * i / (n - 1))
        y = pad + inner_h * (1.0 - ((net - y_min) / span))
        return x, y

    coords = [_xy(i, net) for i, (_, net) in enumerate(series)]
    points = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    y0 = pad + inner_h * (1.0 - ((0 - y_min) / span))
    last_net = nets[-1]
    tone = "up" if last_net >= 0 else "down"
    first_day, last_day = series[0][0], series[-1][0]
    aria = (
        f"{label} advance/decline net over {n} UTC days from {first_day} to {last_day}. "
        f"Latest net {last_net:+d} ({aria_unit})."
    )
    lx, ly = coords[-1]
    svg = (
        f'<svg class="breadth-ad-spark-svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'width="{width:.0f}" height="{height:.0f}" role="img" aria-label="{aria}">'
        f'<line class="breadth-spark-zero" x1="{pad:.1f}" y1="{y0:.1f}" '
        f'x2="{width - pad:.1f}" y2="{y0:.1f}" />'
        f'<polyline class="breadth-spark-line is-{tone}" fill="none" '
        f'points="{points}" />'
        f'<circle class="breadth-spark-dot is-{tone}" cx="{lx:.1f}" cy="{ly:.1f}" r="2.6" />'
        f"</svg>"
    )
    return {
        "ready": True,
        "n": n,
        "svg": svg,
        "aria": aria,
        "latest_net": last_net,
        "first_day": first_day,
        "last_day": last_day,
        "label": label,
    }


def build_breadth_ratio_spark(
    rows: list[dict[str, Any]],
    *,
    count_key: str,
    pct_key: str,
    resolve_pct,
    label: str,
    aria_noun: str,
    width: float = 320.0,
    height: float = 52.0,
    pad: float = 5.0,
) -> dict[str, Any]:
    """Inline SVG: multi-day scan-list ratio (%). Display only; needs ≥2 days."""
    series: list[tuple[str, float]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        day = str(r.get("day") or "").strip()
        if not day:
            continue
        if count_key not in r and pct_key not in r:
            continue
        pct = r.get(pct_key)
        if pct is None:
            pct = resolve_pct(r)
        if pct is None:
            continue
        series.append((day, float(pct)))
    empty = {
        "ready": False,
        "n": len(series),
        "svg": "",
        "aria": "",
        "latest_pct": 0.0,
        "delta_pct": None,
        "first_day": "",
        "last_day": "",
        "label": label,
    }
    if len(series) < 2:
        return empty

    vals = [v for _, v in series]
    y_min = 0.0
    y_max = max(max(vals), 1.0)
    if y_max < 10.0:
        y_max = 10.0
    span = float(y_max - y_min)
    inner_w = width - 2 * pad
    inner_h = height - 2 * pad
    n = len(series)

    def _xy(i: int, val: float) -> tuple[float, float]:
        x = pad + (inner_w * i / (n - 1))
        y = pad + inner_h * (1.0 - ((val - y_min) / span))
        return x, y

    coords = [_xy(i, val) for i, (_, val) in enumerate(series)]
    points = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    y0 = pad + inner_h  # 0% baseline at bottom
    last_pct = vals[-1]
    prior = vals[-2]
    delta = round(last_pct - prior, 1)
    if delta > 0:
        tone = "up"
    elif delta < 0:
        tone = "down"
    else:
        tone = "flat"
    first_day, last_day = series[0][0], series[-1][0]
    aria = (
        f"{aria_noun} over {n} UTC days from {first_day} to {last_day}. "
        f"Latest {last_pct:.0f}% ({delta:+.0f} pp vs prior day). Scan-list only."
    )
    lx, ly = coords[-1]
    svg = (
        f'<svg class="breadth-ad-spark-svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'width="{width:.0f}" height="{height:.0f}" role="img" aria-label="{aria}">'
        f'<line class="breadth-spark-zero" x1="{pad:.1f}" y1="{y0:.1f}" '
        f'x2="{width - pad:.1f}" y2="{y0:.1f}" />'
        f'<polyline class="breadth-spark-line is-{tone}" fill="none" '
        f'points="{points}" />'
        f'<circle class="breadth-spark-dot is-{tone}" cx="{lx:.1f}" cy="{ly:.1f}" r="2.6" />'
        f"</svg>"
    )
    return {
        "ready": True,
        "n": n,
        "svg": svg,
        "aria": aria,
        "latest_pct": last_pct,
        "delta_pct": delta,
        "first_day": first_day,
        "last_day": last_day,
        "label": label,
        "tone": tone,
    }


def _resolve_crypto_mover_pct(row: dict[str, Any]) -> float | None:
    crypto_n = int(row.get("crypto_n") or 0) or (
        int(row.get("crypto_up") or 0) + int(row.get("crypto_down") or 0)
    )
    return crypto_mover_ratio_pct(int(row.get("crypto_big_movers") or 0), crypto_n)


def _resolve_near_high_pct(row: dict[str, Any]) -> float | None:
    return near_high_ratio_pct(
        int(row.get("stock_within_5pct_high") or 0),
        int(row.get("stock_breakouts_n") or 0),
    )


def _resolve_stock_advance_pct(row: dict[str, Any]) -> float | None:
    stock_up = int(row.get("stock_scan_up") or 0)
    stock_down = int(row.get("stock_scan_down") or 0)
    stock_n = int(row.get("stock_scan_n") or 0) or (stock_up + stock_down)
    return stock_advance_ratio_pct(stock_up, stock_n)


def _resolve_crypto_advance_pct(row: dict[str, Any]) -> float | None:
    crypto_up = int(row.get("crypto_up") or 0)
    crypto_down = int(row.get("crypto_down") or 0)
    crypto_n = int(row.get("crypto_n") or 0) or (crypto_up + crypto_down)
    return crypto_advance_ratio_pct(crypto_up, crypto_n)


def build_breadth_mover_spark(
    rows: list[dict[str, Any]],
    *,
    width: float = 320.0,
    height: float = 52.0,
    pad: float = 5.0,
) -> dict[str, Any]:
    """Inline SVG: multi-day ±4% mover ratio (% of crypto leaders). Display only."""
    return build_breadth_ratio_spark(
        rows,
        count_key="crypto_big_movers",
        pct_key="crypto_mover_pct",
        resolve_pct=_resolve_crypto_mover_pct,
        label="±4% ratio",
        aria_noun="Crypto leaders ±4% mover ratio",
        width=width,
        height=height,
        pad=pad,
    )


def build_breadth_near_high_spark(
    rows: list[dict[str, Any]],
    *,
    width: float = 320.0,
    height: float = 52.0,
    pad: float = 5.0,
) -> dict[str, Any]:
    """Inline SVG: multi-day near-high ratio (% of stock breakouts). Display only."""
    return build_breadth_ratio_spark(
        rows,
        count_key="stock_within_5pct_high",
        pct_key="near_high_pct",
        resolve_pct=_resolve_near_high_pct,
        label="Near-high ratio",
        aria_noun="Stock breakouts within 5% of high ratio",
        width=width,
        height=height,
        pad=pad,
    )


def build_breadth_stock_advance_spark(
    rows: list[dict[str, Any]],
    *,
    width: float = 320.0,
    height: float = 52.0,
    pad: float = 5.0,
) -> dict[str, Any]:
    """Inline SVG: multi-day stock advance % (priced scan up/n). Display only."""
    return build_breadth_ratio_spark(
        rows,
        count_key="stock_scan_up",
        pct_key="stock_advance_pct",
        resolve_pct=_resolve_stock_advance_pct,
        label="Stock advance %",
        aria_noun="Priced scan stock advance participation",
        width=width,
        height=height,
        pad=pad,
    )


def build_breadth_crypto_advance_spark(
    rows: list[dict[str, Any]],
    *,
    width: float = 320.0,
    height: float = 52.0,
    pad: float = 5.0,
) -> dict[str, Any]:
    """Inline SVG: multi-day crypto advance % (leaders up/n). Display only."""
    return build_breadth_ratio_spark(
        rows,
        count_key="crypto_up",
        pct_key="crypto_advance_pct",
        resolve_pct=_resolve_crypto_advance_pct,
        label="Crypto advance %",
        aria_noun="Crypto leaders advance participation",
        width=width,
        height=height,
        pad=pad,
    )


def _fmt_hold(seconds: float) -> str:
    if seconds < 0:
        return "—"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def _prices_from_scan(opp: dict[str, Any]) -> dict[str, float]:
    prices: dict[str, float] = {}
    for key in ("crypto_leaders", "stock_breakouts"):
        for row in opp.get(key) or []:
            sym = row.get("symbol")
            px = row.get("price")
            if sym is not None and px is not None:
                try:
                    prices[str(sym)] = float(px)
                except (TypeError, ValueError):
                    continue
    return prices


def _fetch_yfinance_prices(
    symbols: list[str], timeout_s: float = 4.0
) -> dict[str, float]:
    if not symbols:
        return {}

    def _one(sym: str) -> tuple[str, Optional[float]]:
        try:
            import yfinance as yf

            t = yf.Ticker(sym)
            hist = t.history(period="1d")
            if hist is not None and not hist.empty:
                return sym, float(hist["Close"].iloc[-1])
            info = getattr(t, "fast_info", None)
            if info is not None:
                last = getattr(info, "last_price", None) or (
                    info.get("lastPrice") if hasattr(info, "get") else None
                )
                if last is not None:
                    return sym, float(last)
        except Exception:
            return sym, None
        return sym, None

    out: dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=min(6, len(symbols))) as pool:
        futs = [pool.submit(_one, s) for s in symbols]
        deadline = time.time() + timeout_s
        for fut in futs:
            remaining = max(0.05, deadline - time.time())
            try:
                sym, px = fut.result(timeout=remaining)
                if px is not None and px > 0:
                    out[sym] = px
            except FuturesTimeout:
                continue
            except Exception:
                continue
    return out


def load_desk_snapshot(
    data_dir: Path,
    *,
    live_marks: Optional[bool] = None,
    price_fetcher: Optional[Callable[[list[str]], dict[str, float]]] = None,
) -> dict[str, Any]:
    """Build the paper desk view model from on-disk trader state."""
    if live_marks is None:
        live_marks = os.getenv("DESK_LIVE_MARKS", "1").strip() not in {
            "0",
            "false",
            "False",
            "no",
        }

    portfolio = _load_json(data_dir / "portfolio.json", {})
    trades = _load_jsonl(data_dir / "trades.jsonl")
    age = book_start_meta(portfolio if isinstance(portfolio, dict) else {}, trades)
    entry_times = _load_json(data_dir / "entry_times.json", {})
    exit_times_raw = _load_json(data_dir / "exit_times.json", {})
    if not isinstance(exit_times_raw, dict):
        exit_times_raw = {}
    scan_history = _load_json(data_dir / "stock_scan_history.json", {})
    scanned = _load_json(data_dir / "scanned_symbols.json", {})
    watchdog_path = data_dir / "watchdog" / "status.txt"
    watchdog = watchdog_path.read_text().strip() if watchdog_path.exists() else ""

    opp_path = data_dir / "archive" / "opportunities_latest.json"
    if not opp_path.exists():
        arch = data_dir / "archive"
        candidates = (
            sorted(arch.glob("opportunities_2*.json")) if arch.exists() else []
        )
        opp_path = candidates[-1] if candidates else opp_path
    opportunities = _load_json(opp_path, {})

    cash = float(portfolio.get("cash") or 0)
    initial = float(portfolio.get("initial_cash") or 0)
    fees = float(portfolio.get("total_fees_paid") or 0)
    from stock_checker.trader_config import load_trader_config

    cfg_fees = load_trader_config(data_dir)
    try:
        commission_rate = float(
            portfolio.get("commission_rate")
            if portfolio.get("commission_rate") is not None
            else cfg_fees.get("commission_rate")
            or 0.0025
        )
    except (TypeError, ValueError):
        commission_rate = 0.0025
    try:
        commission_min_eur = float(
            portfolio.get("commission_min_eur")
            if portfolio.get("commission_min_eur") is not None
            else cfg_fees.get("commission_min_eur")
            or 1.0
        )
    except (TypeError, ValueError):
        commission_min_eur = 1.0
    fee_preset = str(
        portfolio.get("fee_preset")
        or cfg_fees.get("fee_preset")
        or "revolut_standard"
    )
    holdings = portfolio.get("holdings") or {}
    avg = portfolio.get("avg_buy_price") or {}
    now = time.time()

    scan_prices = _prices_from_scan(opportunities)
    marks = dict(scan_prices)
    mark_source = "scan" if scan_prices else "cost"
    missing = [s for s in holdings if s not in marks or marks[s] <= 0]
    if live_marks and missing:
        fetcher = price_fetcher or (
            lambda syms: _fetch_yfinance_prices(syms, timeout_s=4.0)
        )
        try:
            live = fetcher(missing)
            if live:
                marks.update(live)
                mark_source = "live+scan" if scan_prices else "live"
        except Exception:
            pass
    if not marks:
        mark_source = "cost"

    rows: list[dict[str, Any]] = []
    cost = 0.0
    market_value = 0.0
    for symbol, qty in holdings.items():
        q = float(qty)
        buy = float(avg.get(symbol, 0) or 0)
        basis = q * buy
        cost += basis
        last = marks.get(symbol)
        if last is None or last <= 0:
            last = buy
            marked = False
        else:
            marked = True
        mv = q * last
        market_value += mv
        unreal = mv - basis
        unreal_pct = (unreal / basis * 100) if basis else 0.0
        entry_ts = float(entry_times.get(symbol) or 0) or None
        held_s = (now - entry_ts) if entry_ts else None
        rows.append(
            {
                "symbol": symbol,
                "quantity": q,
                "avg_buy": buy,
                "cost_basis": basis,
                "last": last,
                "market_value": mv,
                "unrealized": unreal,
                "unrealized_pct": unreal_pct,
                "marked": marked,
                "kind": "crypto" if "-USD" in str(symbol) else "stock",
                "held": _fmt_hold(held_s) if held_s is not None else "—",
                "held_seconds": held_s,
                "bought_at": (
                    datetime.fromtimestamp(entry_ts, tz=timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    )
                    if entry_ts
                    else ""
                ),
                "weight_pct": 0.0,
                "weight_bar_pct": 0.0,
            }
        )

    equity_cost = cash + cost
    equity_mtm = cash + market_value
    if any(r["marked"] for r in rows):
        equity = equity_mtm
    else:
        equity = equity_cost
        mark_source = "cost"

    ret_pct = ((equity / initial) - 1) * 100 if initial else 0.0
    unrealized_total = market_value - cost
    unrealized_pct = (unrealized_total / cost * 100) if cost else 0.0
    deployed_pct = ((equity - cash) / equity * 100) if equity else 0.0

    for r in rows:
        w = (r["market_value"] / equity * 100) if equity else 0.0
        r["weight_pct"] = w
        r["weight_bar_pct"] = min(max(w, 0.0), 100.0)
    rows.sort(key=lambda r: r["market_value"], reverse=True)

    # Stuck capital (A15): past min-hold and underwater — visible, not silent.
    # Min-hold lock: which lots still cannot rotate/trim (portfolio AI honesty).
    min_hold_h = float(cfg_fees.get("min_hold_hours") or 24)
    min_hold_s = max(4.0, min_hold_h) * 3600.0
    for r in rows:
        apply_min_hold_lock_fields(r, min_hold_s)
    stuck = [
        {
            "symbol": r["symbol"],
            "unrealized_pct": r["unrealized_pct"],
            "held": r["held"],
            "held_seconds": r.get("held_seconds"),
        }
        for r in rows
        if (r.get("held_seconds") or 0) >= min_hold_s and float(r.get("unrealized_pct") or 0) < 0
    ]

    sells = [t for t in trades if t.get("type") == "SELL"]
    buys = [t for t in trades if t.get("type") == "BUY"]
    realized = sum(float(t.get("profit_loss") or 0) for t in sells)

    recs_raw = (opportunities.get("recommendations") or [])[:8]
    crypto_raw_all = list(opportunities.get("crypto_leaders") or [])
    stock_raw_all = list(opportunities.get("stock_breakouts") or [])
    crypto_raw = crypto_raw_all[:6]
    stock_raw = stock_raw_all[:6]

    # StockBee-lite pulse from latest scan lists (not a full market A/D line).
    crypto_up = sum(
        1 for r in crypto_raw_all if float(r.get("change_24h") or 0) > 0
    )
    crypto_down = sum(
        1 for r in crypto_raw_all if float(r.get("change_24h") or 0) < 0
    )
    crypto_changes = [float(r.get("change_24h") or 0) for r in crypto_raw_all]
    crypto_avg = (
        sum(crypto_changes) / len(crypto_changes) if crypto_changes else 0.0
    )
    crypto_big = sum(1 for c in crypto_changes if abs(c) >= 4.0)
    stock_near = sum(
        1 for r in stock_raw_all if float(r.get("pct_from_high") or 99) <= 5.0
    )
    crypto_mover_pct = crypto_mover_ratio_pct(crypto_big, len(crypto_raw_all))
    near_high_pct = near_high_ratio_pct(stock_near, len(stock_raw_all))
    crypto_advance_pct = crypto_advance_ratio_pct(crypto_up, len(crypto_raw_all))
    stock_pulse = opportunities.get("stock_scan_pulse") or {}
    if not isinstance(stock_pulse, dict):
        stock_pulse = {}
    stock_scan_n = int(stock_pulse.get("stock_scan_n") or 0)
    stock_scan_up = int(stock_pulse.get("stock_scan_up") or 0)
    stock_scan_down = int(stock_pulse.get("stock_scan_down") or 0)
    stock_scan_flat = int(stock_pulse.get("stock_scan_flat") or 0)
    stock_advance_pct = stock_advance_ratio_pct(stock_scan_up, stock_scan_n)
    if stock_scan_n > 0:
        adv_bit = (
            f" · advance {stock_advance_pct:.0f}%"
            if stock_advance_pct is not None
            else ""
        )
        stock_ad_note = (
            f"Stock batch A/D {stock_scan_up}/{stock_scan_down} "
            f"of {stock_scan_n} priced names this scan{adv_bit}"
        )
    else:
        stock_ad_note = "Stock batch A/D awaits next equity scan"
    if crypto_raw_all and crypto_advance_pct is not None:
        crypto_adv_bit = f" · crypto advance {crypto_advance_pct:.0f}%"
    else:
        crypto_adv_bit = ""
    tape_label = breadth_tape_label(stock_advance_pct, crypto_advance_pct)
    scan_breadth = {
        "crypto_n": len(crypto_raw_all),
        "crypto_up": crypto_up,
        "crypto_down": crypto_down,
        "crypto_flat": max(0, len(crypto_raw_all) - crypto_up - crypto_down),
        "crypto_avg_chg": crypto_avg,
        "crypto_big_movers": crypto_big,
        "crypto_mover_pct": crypto_mover_pct,
        "crypto_advance_pct": crypto_advance_pct,
        "stock_breakouts_n": len(stock_raw_all),
        "stock_within_5pct_high": stock_near,
        "near_high_pct": near_high_pct,
        "is_thrust": is_breadth_thrust_day(crypto_mover_pct, near_high_pct),
        "is_dual_advance": is_dual_advance_day(stock_advance_pct, crypto_advance_pct),
        "is_tape_split": is_tape_split_day(stock_advance_pct, crypto_advance_pct),
        "is_risk_off": is_risk_off_day(stock_advance_pct, crypto_advance_pct),
        "tape_label": tape_label,
        "is_mixed": tape_label == "mixed",
        "stock_scan_n": stock_scan_n,
        "stock_scan_up": stock_scan_up,
        "stock_scan_down": stock_scan_down,
        "stock_scan_flat": stock_scan_flat,
        "stock_advance_pct": stock_advance_pct,
        "note": (
            "Scan-list pulse: crypto leaders + this-cycle stock batch A/D "
            "(not full-universe advance/decline). "
            + stock_ad_note
            + crypto_adv_bit
            + "."
        ),
    }
    scan_time = opportunities.get("scan_time") or ""
    # First slice toward multi-day A/D: upsert today's pulse when a scan exists.
    if crypto_raw_all or stock_raw_all or scan_time:
        scan_breadth_history = _upsert_scan_breadth_daily(
            data_dir, scan_breadth, str(scan_time)
        )
    else:
        hist_raw = _load_json(data_dir / "scan_breadth_daily.json", [])
        scan_breadth_history = _annotate_scan_history(
            data_dir,
            (
                [r for r in hist_raw if isinstance(r, dict)][-14:]
                if isinstance(hist_raw, list)
                else []
            ),
        )

    name_symbols: list[str] = []
    for sym in list(holdings.keys()):
        name_symbols.append(str(sym))
    for t in trades[-20:]:
        if t.get("symbol"):
            name_symbols.append(str(t["symbol"]))
    postmortems_raw = closed_rounds(trades, limit=POSTMORTEM_LIMIT)
    for r in postmortems_raw:
        if r.get("symbol"):
            name_symbols.append(str(r["symbol"]))
    for r in recs_raw + crypto_raw + stock_raw:
        if r.get("symbol"):
            name_symbols.append(str(r["symbol"]))
    # unique, preserve order
    seen: set[str] = set()
    uniq_syms: list[str] = []
    for s in name_symbols:
        if s not in seen:
            seen.add(s)
            uniq_syms.append(s)
    names = resolve_symbol_names(uniq_syms, data_dir)

    for r in rows:
        r["name"] = display_name(r["symbol"], names)

    all_trade_rows = [_serialize_trade_row(t, names) for t in reversed(trades)]
    recent = all_trade_rows[:RECENT_FILLS_LIMIT]
    older_trades = all_trade_rows[RECENT_FILLS_LIMIT:]
    postmortems = [
        {
            **r,
            "name": display_name(str(r.get("symbol") or ""), names),
        }
        for r in postmortems_raw
    ]

    recs = []
    for r in recs_raw:
        sym = r.get("symbol")
        recs.append(
            {
                "rank": r.get("rank"),
                "symbol": sym,
                "name": display_name(str(sym or ""), names),
                "asset_class": r.get("asset_class"),
                "strategy": r.get("strategy"),
                "score": float(r.get("score") or 0),
                "reasoning": r.get("reasoning") or "",
                "risk_note": r.get("risk_note") or "",
                "risk_rr": r.get("risk_rr"),
                "risk_rr_ok": r.get("risk_rr_ok"),
            }
        )

    crypto_leaders = []
    for r in crypto_raw:
        sym = r.get("symbol")
        crypto_leaders.append(
            {
                "symbol": sym,
                "name": display_name(str(sym or ""), names),
                "price": float(r.get("price") or 0),
                "change_24h": float(r.get("change_24h") or 0),
                "score": float(r.get("score") or 0),
                "volume_surge_pct": float(r.get("volume_surge_pct") or 0),
                "tradeable": bool(r.get("tradeable", True)),
                "risk_note": r.get("risk_note") or "",
                "risk_rr": r.get("risk_rr"),
                "risk_rr_ok": r.get("risk_rr_ok"),
            }
        )

    stock_breakouts = []
    for r in stock_raw:
        sym = r.get("symbol")
        stock_breakouts.append(
            {
                "symbol": sym,
                "name": display_name(str(sym or ""), names),
                "sector": r.get("sector") or "",
                "price": float(r.get("price") or 0),
                "pct_from_high": float(r.get("pct_from_high") or 0),
                "strength": r.get("strength") or "",
                "risk_note": r.get("risk_note") or "",
                "risk_rr": r.get("risk_rr"),
                "risk_rr_ok": r.get("risk_rr_ok"),
            }
        )

    scanned_count = len(scanned) if isinstance(scanned, dict) else 0
    hist_scanned = (
        scan_history.get("scanned") if isinstance(scan_history, dict) else {}
    )
    last_full = (
        scan_history.get("last_full_cycle") if isinstance(scan_history, dict) else None
    )
    weekend = datetime.now(timezone.utc).weekday() >= 5

    gh_watch = _load_json(data_dir / "github_watch" / "latest.json", {})
    gh_ideas = list(gh_watch.get("idea_bullets") or [])[:8]
    gh_updates = int(gh_watch.get("update_count") or 0)
    gh_at = gh_watch.get("generated_at") or ""
    gh_repo_count = int(gh_watch.get("repo_count") or 0)
    gh_checked = int(gh_watch.get("checked_count") or 0)
    gh_repos: list[dict[str, Any]] = []
    for row in (gh_watch.get("repos") or [])[:12]:
        tip = str(row.get("tip_message") or "").strip()
        if len(tip) > 110:
            tip = tip[:109] + "…"
        sha = str(row.get("tip_sha") or "")
        tip_short = sha[:7] if sha else ""
        # Prefer tip commit date, else newest listed commit, else repo pushed_at.
        last_commit_at = ""
        commits = row.get("commits") if isinstance(row.get("commits"), list) else []
        if sha and commits:
            for c in commits:
                if not isinstance(c, dict):
                    continue
                csha = str(c.get("sha") or "")
                if csha == sha or csha.startswith(sha[:7]):
                    last_commit_at = str(c.get("date") or "")[:10]
                    break
        if not last_commit_at and commits:
            c0 = commits[0]
            if isinstance(c0, dict):
                last_commit_at = str(c0.get("date") or "")[:10]
        if not last_commit_at:
            last_commit_at = str(row.get("pushed_at") or "")[:10]
        gh_repos.append(
            {
                "repo": row.get("repo") or "",
                "url": row.get("url") or "",
                "why": row.get("why") or "",
                "stars": int(row.get("stars") or 0),
                "status": (
                    "update"
                    if row.get("has_updates")
                    else ("error" if row.get("error") else "quiet")
                ),
                "tip_short": tip_short,
                "tip_message": tip,
                "pushed_at": (row.get("pushed_at") or "")[:10],
                "last_commit_at": last_commit_at,
            }
        )
    # Newest tip / activity first (ISO dates sort lexicographically).
    gh_repos.sort(
        key=lambda r: r.get("last_commit_at") or r.get("pushed_at") or "",
        reverse=True,
    )
    # When the watch is quiet, still surface latest tip per repo so Ideas isn't blank.
    gh_watch_notes: list[str] = []
    if not gh_ideas and gh_repos:
        for r in gh_repos[:6]:
            if r["tip_message"]:
                when = r.get("last_commit_at") or r.get("pushed_at") or ""
                when_bit = f" · {when}" if when else ""
                gh_watch_notes.append(
                    f"{r['repo']}: latest {r['tip_short'] or '—'}{when_bit} — {r['tip_message']}"
                )

    adopted_ideas = [
        {
            "title": "StockBee mixed tape + flip",
            "from": "xang1234/stock-screener (StockBee-lite)",
            "note": "Mid-range both-sleeved days are mixed (not blank); Breadth + glance show prior-day flips; display only; not a gate.",
        },
        {
            "title": "StockBee thrust streak",
            "from": "xang1234/stock-screener (StockBee-lite)",
            "note": "Consecutive scan-list thrust days (ending streak) on Breadth summary + glance when streak ≥2; display only; not a gate.",
        },
        {
            "title": "StockBee thrust day (±4% + near-high)",
            "from": "xang1234/stock-screener (StockBee-lite)",
            "note": "Breadth flags a thrust day when both ±4% mover ratio and near-high ratio are ≥25%; glance + Recent days; scan-list only.",
        },
        {
            "title": "Multi-day ±4% mover ratio",
            "from": "xang1234/stock-screener (StockBee-lite)",
            "note": "Breadth spark + Recent days % of crypto leaders with |24h|≥4%; glance shows count and share — scan-list only.",
        },
        {
            "title": "Live book posture + next trim",
            "from": "staskh / portfolio AI risk strip",
            "note": "Book posture glance shows live open/at_cap/overweight slots; overweight names next trim (winners first) — display only.",
        },
        {
            "title": "AI debate memory glance",
            "from": "FinRobot / TradingAgents research memory",
            "note": "Desk one-liner: BUY/HOLD/SELL + multi-role gated counts from ai_validate_memory — display only; Ideas keeps transcripts.",
        },
        {
            "title": "AI validate debate memory on Ideas",
            "from": "FinRobot / TradingAgents multi-role",
            "note": "Persists last bull/bear/risk validate rows; expandable transcript JSON on Ideas — display only; not a research score.",
        },
        {
            "title": "Scan pulse on Breadth",
            "from": "xang1234/stock-screener (StockBee-style A/D)",
            "note": "Crypto leaders advance/decline + ±4% movers from our scan lists.",
        },
        {
            "title": "Since-buy holding paths",
            "from": "portfolio-AI style position charts",
            "note": "Book + Charts show price since fill vs avg cost — no forecast lines.",
        },
        {
            "title": "Multi-screen paper desk",
            "from": "xang1234 screener page map",
            "note": "Overview / Charts / Screener / Breadth / Book / Ideas / Ops.",
        },
        {
            "title": "Daily scan-pulse history + A/D spark",
            "from": "xang1234/StockBee-style breadth over time",
            "note": "Breadth keeps UTC daily A/D snapshots and a multi-day net A/D sparkline.",
        },
        {
            "title": "Screener breadth beside lists",
            "from": "xang1234/stock-screener (StockBee-lite next to screen)",
            "note": "Screener shows scan-list A/D + near-high / ±4% movers above opportunity lists — display only.",
        },
        {
            "title": "Ideas breadth beside candidates",
            "from": "xang1234/stock-screener (breadth next to research picks)",
            "note": "Ideas shows the same scan-list A/D glance above paper candidates — display only.",
        },
        {
            "title": "Screener counts strip",
            "from": "MonsterDeveloper/simple-stock-screener (simplicity)",
            "note": "One glance: recommendation / crypto / breakout counts + session hint.",
        },
        {
            "title": "SMA market-regime gate",
            "from": "RyanJHamby/stock-screener (regime filtering)",
            "note": "Soft block new buys when SPY is below SMA200 or BTC below SMA50; holds untouched.",
        },
        {
            "title": "Relative-strength entry gate",
            "from": "RyanJHamby/stock-screener (RS as primary filter)",
            "note": "Soft block new buys lagging SPY/BTC over ~63 sessions; Ops toggle; fail-open.",
        },
        {
            "title": "Scan-breadth entry gate",
            "from": "RyanJHamby/stock-screener (market breadth)",
            "note": "Soft block new buys when scan-list A/D looks weak; not full-universe A/D.",
        },
        {
            "title": "ATR / R:R risk notes",
            "from": "RyanJHamby/stock-screener (stop + R:R framing)",
            "note": "Screener shows day-range / vol proxy stops + rough R:R — display only, not exits.",
        },
        {
            "title": "Yahoo movers → universe only",
            "from": "Yahoo Finance day gainers/losers/actives",
            "note": "Discovery into the scan list; buys still need regime/RS/breadth/fees.",
        },
        {
            "title": "Universe discovery glance",
            "from": "xang1234/stock-screener + portfolio AI (discovery ≠ firehose)",
            "note": "Overview / Ops one-line curated US+DE · Yahoo movers discovery-only — not auto-buy; display only.",
        },
        {
            "title": "Closed-round postmortem",
            "from": "tradermonty/claude-trading-skills (trader memory)",
            "note": "Book pairs BUY→SELL: thesis → exit → hold → mark P&L. No inventing MAE/MFE.",
        },
        {
            "title": "Pre-trade + position sizer",
            "from": "tradermonty/claude-trading-skills (pre-trade gate / sizer)",
            "note": "Overview shows PASS/WARN/FAIL + suggested next-buy € (cash frac · concentration · slots).",
        },
        {
            "title": "Next-buy sizer glance",
            "from": "tradermonty/claude-trading-skills + portfolio AI (position sizer)",
            "note": "Screener / Ideas / Book / Ops / Charts / Breadth / scan-log show one-line next-buy € — Overview keeps the full size block; display only.",
        },
        {
            "title": "Book risk report strip",
            "from": "staskh/trading_skills + portfolio AI (risk / mix report)",
            "note": "Book shows slots, posture, cash %, largest name, equity/crypto mix — display only.",
        },
        {
            "title": "Book breadth beside holdings",
            "from": "xang1234/stock-screener + portfolio AI (risk context)",
            "note": "Book shows scan-list A/D glance next to risk strip — context for adds, not a gate.",
        },
        {
            "title": "Charts breadth beside paths",
            "from": "xang1234/stock-screener (StockBee-lite on JS Charts root)",
            "note": "Charts API carries scan-list A/D glance above equity/allocation — display only.",
        },
        {
            "title": "Fail-open soft-allow memory",
            "from": "tradermonty/claude-trading-skills (trader memory) + A5",
            "note": "Ops lists recent regime/RS/breadth/promote soft-allows when bars/data are missing.",
        },
        {
            "title": "Ops breadth beside gate knobs",
            "from": "xang1234/stock-screener (StockBee-lite next to controls)",
            "note": "Ops shows scan-list A/D above trader knobs — context before flipping breadth gate.",
        },
        {
            "title": "Scan-log day breadth glance",
            "from": "xang1234/stock-screener (StockBee day drill-down)",
            "note": "Scan log shows that UTC day’s scan-list A/D above the archive report — display only.",
        },
        {
            "title": "Scan freshness honesty",
            "from": "RyanJHamby/stock-screener (cache / daily-scan age)",
            "note": "Overview / Screener / Breadth / Ops / Book / Ideas / Charts show scan age as fresh / aging / stale — display only, not a gate.",
        },
        {
            "title": "Yahoo movers cache age",
            "from": "RyanJHamby/stock-screener (fundamental cache + daily scan)",
            "note": "Universe glance shows last Yahoo movers discovery age vs 24h throttle (fresh/aging/stale) — discovery-only, not a gate.",
        },
        {
            "title": "Loop cadence honesty",
            "from": "RyanJHamby / MonsterDeveloper screeners + portfolio AI (schedule UX)",
            "note": "Overview / Ops show scan · trade minutes vs floors ≥15m/≥5m — packaging ≠ edge; display only.",
        },
        {
            "title": "Soft-allow glance on Overview / Book",
            "from": "tradermonty/claude-trading-skills (trader memory)",
            "note": "One-line fail-open soft-allow count beside pretrade / risk — Ops keeps the full list; display only.",
        },
        {
            "title": "Pretrade glance on Screener / Ideas / Book / Charts / Breadth",
            "from": "tradermonty/claude-trading-skills (pre-trade gate)",
            "note": "PASS/WARN/FAIL one-liner before lists, holdings, charts, and breadth — Overview/Ops keep full checklist; display only.",
        },
        {
            "title": "Book risk glance on Overview / Screener / Ideas",
            "from": "staskh/trading_skills + portfolio AI (risk / mix report)",
            "note": "One-line slots/posture beside holdings and opportunity lists — Book keeps the full strip; display only.",
        },
    ]

    from stock_checker.ai_validate_memory import recent_ai_debates
    from stock_checker.gate_audit import recent_soft_allows
    from stock_checker.risk_halts import (
        book_risk_report,
        latest_stop_loss_sell,
        pretrade_status,
        realized_pnl_for_utc_day,
        suggest_entry_notional,
    )

    soft_allows = recent_soft_allows(data_dir, limit=12)
    ai_debates = recent_ai_debates(data_dir, limit=8)

    max_pos = int(cfg_fees.get("max_positions") or 5)
    pretrade_level, pretrade_notes = pretrade_status(data_dir, initial_cash=initial)
    last_sl = latest_stop_loss_sell(data_dir)
    post_sl_sym = last_sl[0] if last_sl else None
    post_sl_epoch = last_sl[1] if last_sl else None
    entry_size = suggest_entry_notional(
        cash=cash,
        equity=equity,
        open_positions=len(rows),
        max_positions=max_pos,
        position_size=0.10,
    )
    book_risk = book_risk_report(
        cash=cash,
        equity=equity,
        holdings=rows,
        max_positions=max_pos,
    )
    runtime = _trader_runtime_view()
    scan_interval_sec = max(60, int(runtime.get("scan_interval_min") or 15) * 60)
    scan_time_raw = opportunities.get("scan_time") or ""

    return {
        "brand": "AI Stock Checker",
        "tagline": "Paper desk — honest marks, low churn.",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "portfolio_updated": portfolio.get("last_updated") or "",
        "initial": initial,
        "cash": cash,
        "fees": fees,
        "commission_rate_pct": commission_rate * 100,
        "commission_min_eur": commission_min_eur,
        "fee_preset": fee_preset,
        "cost_basis_total": cost,
        "market_value": market_value,
        "equity": equity,
        "equity_cost": equity_cost,
        "ret_pct": ret_pct,
        "book_start": age["book_start"],
        "book_age_days": age["book_age_days"],
        "book_age_label": age["book_age_label"],
        "unrealized_total": unrealized_total,
        "unrealized_pct": unrealized_pct,
        "deployed_pct": deployed_pct,
        "positions": len(rows),
        "holdings": rows,
        "stuck_underwater": stuck,
        "stuck_note": (
            f"{len(stuck)} name(s) past min-hold and underwater — capital trapped until TP/SL/trim"
            if stuck
            else ""
        ),
        "pretrade_level": pretrade_level,
        "pretrade_notes": pretrade_notes,
        "pretrade_glance": build_pretrade_glance(pretrade_level, pretrade_notes),
        "entry_size": entry_size,
        "next_buy_glance": build_next_buy_glance(entry_size),
        "book_risk": book_risk,
        "book_risk_glance": build_book_risk_glance(book_risk),
        "concentration_glance": build_concentration_glance(book_risk),
        "soft_allows": soft_allows,
        "ai_debates": ai_debates,
        "soft_allow_glance": build_soft_allow_glance(soft_allows),
        "entry_gates_glance": build_entry_gates_glance(runtime),
        "calm_streak_glance": build_calm_streak_glance(runtime),
        "promote_ab_glance": build_promote_ab_glance(runtime),
        "crypto_policy_glance": build_crypto_policy_glance(rows),
        "exit_policy_glance": build_exit_policy_glance(),
        "earnings_blackout_glance": build_earnings_blackout_glance(),
        "ai_mode_glance": build_ai_mode_glance(runtime),
        "ai_roles_glance": build_ai_roles_glance(),
        "ai_debate_glance": build_ai_debate_glance(
            data_dir, scan_interval_sec=scan_interval_sec
        ),
        "ai_validate_scope_glance": build_ai_validate_scope_glance(runtime),
        "session_glance": build_session_glance(weekend=weekend),
        "equity_hours_glance": build_equity_hours_glance(),
        "breakout_guard_glance": build_breakout_guard_glance(),
        "loss_rotation_glance": build_loss_rotation_glance(),
        "stale_rotation_glance": build_stale_rotation_glance(),
        "book_posture_glance": build_book_posture_glance(
            rows,
            max_positions=max_pos,
            min_hold_hours=float(runtime.get("min_hold_hours") or 24),
        ),
        "junk_filter_glance": build_junk_filter_glance(),
        "universe_discovery_glance": build_universe_discovery_glance(data_dir),
        "atr_display_glance": build_atr_display_glance(),
        "entry_slots_glance": build_entry_slots_glance(),
        "promote_contract_glance": build_promote_contract_glance(runtime),
        "gate_roles_glance": build_gate_roles_glance(runtime),
        "gate_params_glance": build_gate_params_glance(),
        "book_limits_glance": build_book_limits_glance(runtime),
        "rebuy_cooldown_glance": build_rebuy_cooldown_glance(
            exit_times_raw,
            cooldown_seconds=max(0.0, float(runtime.get("min_hold_hours") or 24))
            * 3600.0,
        ),
        "daily_loss_glance": build_daily_loss_glance(
            realized_pnl_for_utc_day(data_dir),
            initial,
        ),
        "post_sl_cooldown_glance": build_post_sl_cooldown_glance(
            post_sl_sym,
            post_sl_epoch,
        ),
        "loop_cadence_glance": build_loop_cadence_glance(runtime),
        "fee_allowance_glance": build_fee_allowance_glance(runtime),
        "fee_burn_glance": build_fee_burn_glance(
            fees,
            initial,
            realized_pnl=realized if sells else None,
        ),
        "stuck_capital_glance": build_stuck_capital_glance(stuck),
        "min_hold_lock_glance": build_min_hold_lock_glance(
            rows, min_hold_hours=min_hold_h
        ),
        "postmortem_glance": build_postmortem_glance(postmortems),
        "realized": realized,
        "trade_count": len(trades),
        "buy_count": len(buys),
        "sell_count": len(sells),
        "recent_trades": recent,
        "older_trades": older_trades,
        "recent_fills_limit": RECENT_FILLS_LIMIT,
        "postmortems": postmortems,
        "postmortem_limit": POSTMORTEM_LIMIT,
        "reset_note": portfolio.get("reset_note") or "",
        "weekend_mode": weekend,
        "weekend_hint": "Weekend: crypto-only trading; US stocks paused."
        if weekend
        else "Weekday session: stocks + crypto per scan rules.",
        "mark_source": mark_source,
        "mark_note": {
            "live": "Marks from live quotes + latest scan.",
            "live+scan": "Marks from live quotes + latest scan.",
            "scan": "Marks from latest scan prices (live quotes skipped/unavailable).",
            "cost": "Showing cost basis — no fresh marks yet.",
        }.get(mark_source, ""),
        "recommendations": recs,
        "crypto_leaders": crypto_leaders,
        "stock_breakouts": stock_breakouts,
        "scan_breadth": scan_breadth,
        "scan_breadth_history": scan_breadth_history,
        "breadth_glance": build_breadth_glance(
            scan_breadth, history=scan_breadth_history
        ),
        "breadth_ad_spark": build_breadth_ad_spark(scan_breadth_history),
        "breadth_stock_ad_spark": build_breadth_ad_spark(
            scan_breadth_history,
            up_key="stock_scan_up",
            down_key="stock_scan_down",
            label="Stock batch",
            aria_unit="priced scan names up minus down",
        ),
        "breadth_mover_spark": build_breadth_mover_spark(scan_breadth_history),
        "breadth_near_high_spark": build_breadth_near_high_spark(scan_breadth_history),
        "breadth_stock_advance_spark": build_breadth_stock_advance_spark(
            scan_breadth_history
        ),
        "breadth_crypto_advance_spark": build_breadth_crypto_advance_spark(
            scan_breadth_history
        ),
        "breadth_thrust_summary": build_breadth_thrust_summary(scan_breadth_history),
        "breadth_tape_summary": build_breadth_tape_summary(scan_breadth_history),
        "scan_time": scan_time_raw,
        "scan_freshness": build_scan_freshness(
            scan_time_raw,
            scan_interval_sec=scan_interval_sec,
        ),
        "scanned_symbols": scanned_count,
        "scan_history_symbols": len(hist_scanned) if isinstance(hist_scanned, dict) else 0,
        "last_full_cycle": last_full or "",
        "watchdog": watchdog,
        "has_scan": bool(opportunities),
        "github_watch_at": gh_at,
        "github_watch_updates": gh_updates,
        "github_watch_repos": gh_repo_count,
        "github_watch_checked": gh_checked,
        "github_watch_has_digest": bool(gh_watch),
        "github_ideas": gh_ideas,
        "github_watch_notes": gh_watch_notes,
        "github_repos": gh_repos,
        "adopted_ideas": adopted_ideas,
        "runtime": runtime,
    }
